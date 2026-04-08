from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import yaml

from proxypool.models import ProxyNode


class ParseError(ValueError):
    pass


_SUPPORTED_SCHEMES = {
    "vmess",
    "trojan",
    "ss",
    "ssr",
    "snell",
    "hysteria2",
    "hy2",
    "vless",
    "hysteria",
    "http",
    "https",
    "socks",
    "socks5",
}

_SCHEME_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_INLINE_LINK_REGEX = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://\S+)")


def parse_source_content(content: str, source_name: str = "") -> tuple[list[ProxyNode], list[str]]:
    if _looks_like_clash_yaml(content, source_name):
        return _parse_clash_yaml(content)

    nodes: list[ProxyNode] = []
    invalid: list[str] = []

    lines = [line.strip() for line in content.replace("\ufeff", "").splitlines()]

    for line in lines:
        if not line or line.startswith("#"):
            continue

        matches = _INLINE_LINK_REGEX.findall(line)
        if matches:
            for match in matches:
                try:
                    nodes.append(parse_proxy_link(match))
                except ParseError:
                    invalid.append(match)
            continue

        if _looks_like_base64(line):
            decoded = _safe_b64_decode_to_text(line)
            if decoded and "://" in decoded:
                sub_nodes, sub_invalid = parse_source_content(decoded, source_name="")
                nodes.extend(sub_nodes)
                invalid.extend(sub_invalid)
                continue

        invalid.append(line)

    return nodes, invalid


def parse_proxy_link(raw_link: str) -> ProxyNode:
    text = raw_link.strip()
    if not _SCHEME_REGEX.match(text):
        raise ParseError("missing URI scheme")

    scheme = text.split("://", 1)[0].lower()
    if scheme not in _SUPPORTED_SCHEMES:
        raise ParseError(f"unsupported scheme: {scheme}")

    if scheme == "vmess":
        return _parse_vmess(text)
    if scheme == "ss":
        return _parse_ss(text)
    if scheme == "ssr":
        return _parse_ssr(text)

    return _parse_url_like(text, scheme)


def _parse_vmess(link: str) -> ProxyNode:
    payload = link.removeprefix("vmess://")
    decoded = payload
    if not payload.startswith("{"):
        decoded = _safe_b64_decode_to_text(payload)
        if not decoded:
            raise ParseError("invalid vmess base64 payload")

    try:
        data = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ParseError("invalid vmess json") from exc

    host = str(data.get("add") or data.get("host") or "").strip()
    port = _to_port(data.get("port"))
    if not host or port is None:
        raise ParseError("vmess missing host or port")

    name = str(data.get("ps") or "")
    extra = {
        "uuid": str(data.get("id") or ""),
        "network": str(data.get("net") or ""),
        "path": str(data.get("path") or ""),
        "tls": str(data.get("tls") or ""),
    }
    return ProxyNode(protocol="vmess", host=host, port=port, raw_link=link, name=name, extra=extra)


def _parse_ss(link: str) -> ProxyNode:
    payload = link.removeprefix("ss://")
    fragment = ""
    if "#" in payload:
        payload, fragment = payload.split("#", 1)
    name = unquote(fragment)

    query = ""
    if "?" in payload:
        payload, query = payload.split("?", 1)

    if "@" in payload:
        userinfo, hostport = payload.rsplit("@", 1)
        if ":" not in userinfo:
            decoded = _safe_b64_decode_to_text(userinfo)
            if not decoded or ":" not in decoded:
                raise ParseError("invalid ss userinfo")
            userinfo = decoded
    else:
        decoded = _safe_b64_decode_to_text(payload)
        if not decoded or "@" not in decoded:
            raise ParseError("invalid ss payload")
        userinfo, hostport = decoded.rsplit("@", 1)

    if ":" not in userinfo:
        raise ParseError("invalid ss method/password")

    method, password = userinfo.split(":", 1)
    host, port = _split_host_port(hostport)

    extra: dict[str, Any] = {
        "cipher": method,
        "password": password,
    }
    if query:
        for key, values in parse_qs(query, keep_blank_values=True).items():
            extra[key] = values[0] if values else ""

    return ProxyNode(protocol="ss", host=host, port=port, raw_link=link, name=name, extra=extra)


def _parse_ssr(link: str) -> ProxyNode:
    payload = link.removeprefix("ssr://")
    decoded = _safe_b64_decode_to_text(payload)
    if not decoded:
        raise ParseError("invalid ssr payload")

    main = decoded
    query = ""
    if "/?" in decoded:
        main, query = decoded.split("/?", 1)

    parts = main.split(":", 5)
    if len(parts) != 6:
        raise ParseError("invalid ssr fields")

    server, port_raw, protocol, method, obfs, password_b64 = parts
    port = _to_port(port_raw)
    if port is None:
        raise ParseError("invalid ssr port")

    password = _safe_b64_decode_to_text(password_b64) or ""
    params = parse_qs(query, keep_blank_values=True)
    remarks = _safe_b64_decode_to_text(_first(params.get("remarks"))) if params.get("remarks") else ""

    extra: dict[str, Any] = {
        "protocol": protocol,
        "method": method,
        "obfs": obfs,
        "password": password,
    }
    return ProxyNode(protocol="ssr", host=server, port=port, raw_link=link, name=remarks, extra=extra)


def _parse_url_like(link: str, scheme: str) -> ProxyNode:
    split = urlsplit(link)
    host = split.hostname or ""
    port = split.port
    if not host:
        raise ParseError(f"{scheme} missing host")

    if port is None:
        defaults = {
            "trojan": 443,
            "vless": 443,
            "hysteria": 443,
            "hysteria2": 443,
            "hy2": 443,
            "http": 80,
            "https": 443,
            "socks": 1080,
            "socks5": 1080,
            "snell": 443,
        }
        port = defaults.get(scheme)
    if port is None:
        raise ParseError(f"{scheme} missing port")

    proto = _normalize_protocol(scheme)
    query = {k: v[0] if v else "" for k, v in parse_qs(split.query, keep_blank_values=True).items()}

    extra: dict[str, Any] = dict(query)
    if split.username:
        user = unquote(split.username)
        if proto in {"trojan", "hysteria", "hysteria2", "snell"}:
            extra["password"] = user
        elif proto == "vless":
            extra["uuid"] = user
        else:
            extra["username"] = user
    if split.password and proto in {"http", "socks"}:
        extra["password"] = unquote(split.password)

    name = unquote(split.fragment or "")
    return ProxyNode(protocol=proto, host=host, port=port, raw_link=link, name=name, extra=extra)


def _parse_clash_yaml(content: str) -> tuple[list[ProxyNode], list[str]]:
    nodes: list[ProxyNode] = []
    invalid: list[str] = []

    try:
        data = yaml.safe_load(content) or {}
    except Exception as exc:  # pragma: no cover - parser errors are rare in test fixtures
        raise ParseError("invalid yaml source") from exc

    proxies = data.get("proxies") if isinstance(data, dict) else None
    if not isinstance(proxies, list):
        return [], []

    type_map = {
        "ss": "ss",
        "ssr": "ssr",
        "trojan": "trojan",
        "vmess": "vmess",
        "vless": "vless",
        "hysteria": "hysteria",
        "hysteria2": "hysteria2",
        "hy2": "hysteria2",
        "snell": "snell",
        "http": "http",
        "socks5": "socks",
        "socks": "socks",
    }

    for item in proxies:
        if not isinstance(item, dict):
            invalid.append(str(item))
            continue

        raw_type = str(item.get("type") or "").lower()
        protocol = type_map.get(raw_type)
        host = str(item.get("server") or "").strip()
        port = _to_port(item.get("port"))

        if not protocol or not host or port is None:
            invalid.append(json.dumps(item, ensure_ascii=False))
            continue

        link_stub = f"clash://{protocol}@{host}:{port}"
        name = str(item.get("name") or "")

        extra = dict(item)
        extra.pop("name", None)
        extra.pop("type", None)
        extra.pop("server", None)
        extra.pop("port", None)

        node = ProxyNode(
            protocol=protocol,
            host=host,
            port=port,
            raw_link=link_stub,
            name=name,
            extra=extra,
        )
        nodes.append(node)

    return nodes, invalid


def _first(values: list[str] | None) -> str:
    if not values:
        return ""
    return values[0]


def _looks_like_clash_yaml(content: str, source_name: str) -> bool:
    lowered = source_name.lower()
    if lowered.endswith(".yaml") or lowered.endswith(".yml"):
        return True
    return "proxies:" in content and "type:" in content and "server:" in content


def _looks_like_base64(value: str) -> bool:
    if len(value) < 12:
        return False
    return re.fullmatch(r"[A-Za-z0-9+/=_-]+", value) is not None


def _safe_b64_decode_to_text(value: str) -> str:
    candidates = [value.strip()]
    normalized = value.strip().replace("-", "+").replace("_", "/")
    candidates.append(normalized)

    for candidate in candidates:
        try:
            padded = _pad_b64(candidate)
            return base64.b64decode(padded).decode("utf-8")
        except Exception:
            continue
    return ""


def _pad_b64(value: str) -> str:
    padding = (-len(value)) % 4
    return value + ("=" * padding)


def _to_port(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if port <= 0 or port > 65535:
        return None
    return port


def _split_host_port(hostport: str) -> tuple[str, int]:
    split = urlsplit(f"//{hostport}")
    host = split.hostname
    port = split.port
    if not host or port is None:
        raise ParseError("missing host/port")
    return host, port


def _normalize_protocol(scheme: str) -> str:
    if scheme in {"hy2", "hysteria2"}:
        return "hysteria2"
    if scheme in {"socks", "socks5"}:
        return "socks"
    if scheme in {"http", "https"}:
        return "http"
    return scheme
