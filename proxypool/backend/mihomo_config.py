from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from proxypool.backend.egress_backend import ChainInstanceSpec


def build_mihomo_chain_config(spec: ChainInstanceSpec) -> dict[str, Any]:
    listener_type = str(spec.inbound_type or "http").strip().lower() or "http"
    if listener_type not in {"http", "socks", "mixed"}:
        raise RuntimeError(f"unsupported mihomo inbound_type: {spec.inbound_type}")

    hop_proxies = list(spec.hop_proxies or [])
    if not hop_proxies:
        raise RuntimeError("mihomo chain requires at least one hop proxy")

    proxies: list[dict[str, Any]] = []
    previous_name = ""
    final_name = ""
    for idx, proxy in enumerate(hop_proxies):
        default_name = f"hop-{idx + 1}"
        name = str(proxy.get("name") or default_name).strip() or default_name
        item = _build_mihomo_proxy(proxy, name=name, dialer_proxy=previous_name or None)
        proxies.append(item)
        previous_name = name
        final_name = name

    return {
        "listeners": [
            {
                "name": spec.instance_id,
                "type": listener_type,
                "listen": str(spec.listen or "127.0.0.1"),
                "port": int(spec.port),
            }
        ],
        "proxies": proxies,
        "rules": ["MATCH," + final_name],
    }


def _build_mihomo_proxy(proxy: dict[str, Any], name: str, dialer_proxy: str | None = None) -> dict[str, Any]:
    protocol = str(proxy.get("protocol") or "").strip().lower()
    host = str(proxy.get("host") or "").strip()
    port = int(proxy.get("port") or 0)
    extra = proxy.get("extra")
    if not isinstance(extra, dict):
        extra = proxy.get("extra_json")
    if not isinstance(extra, dict):
        extra = {}

    if not host or port <= 0:
        raise RuntimeError("invalid proxy host/port for mihomo config")

    item: dict[str, Any] = {
        "name": name,
        "server": host,
        "port": port,
    }
    if dialer_proxy:
        item["dialer-proxy"] = dialer_proxy

    if protocol == "http":
        item["type"] = "http"
        _apply_auth(item, extra)
        _apply_common_tls(item, extra)
        return item
    if protocol == "socks":
        item["type"] = "socks5"
        _apply_auth(item, extra)
        _apply_common_tls(item, extra)
        return item
    if protocol == "ss":
        cipher = str(extra.get("cipher") or "").strip()
        password = str(extra.get("password") or "").strip()
        if not cipher or not password:
            raise RuntimeError("mihomo shadowsocks proxy requires cipher and password")
        item["type"] = "ss"
        item["cipher"] = cipher
        item["password"] = password
        _apply_common_tls(item, extra)
        _apply_network_opts(item, extra)
        return item
    if protocol == "trojan":
        password = str(extra.get("password") or "").strip()
        if not password:
            raise RuntimeError("mihomo trojan proxy requires password")
        item["type"] = "trojan"
        item["password"] = password
        _apply_common_tls(item, extra)
        _apply_network_opts(item, extra)
        return item
    if protocol == "vless":
        uuid = str(extra.get("uuid") or "").strip()
        if not uuid:
            raise RuntimeError("mihomo vless proxy requires uuid")
        item["type"] = "vless"
        item["uuid"] = uuid
        flow = str(extra.get("flow") or "").strip()
        if flow:
            item["flow"] = flow
        _apply_common_tls(item, extra)
        _apply_network_opts(item, extra)
        return item
    if protocol == "vmess":
        uuid = str(extra.get("uuid") or "").strip()
        if not uuid:
            raise RuntimeError("mihomo vmess proxy requires uuid")
        item["type"] = "vmess"
        item["uuid"] = uuid
        alter_id = int(extra.get("alterId") or extra.get("alter_id") or 0)
        item["alterId"] = alter_id
        item["cipher"] = str(extra.get("cipher") or extra.get("security") or "auto").strip() or "auto"
        _apply_common_tls(item, extra)
        _apply_network_opts(item, extra)
        return item
    if protocol == "hysteria2":
        password = str(extra.get("password") or "").strip()
        if not password:
            raise RuntimeError("mihomo hysteria2 proxy requires password")
        item["type"] = "hysteria2"
        item["password"] = password
        _apply_common_tls(item, extra)
        obfs = str(extra.get("obfs") or "").strip()
        obfs_password = str(extra.get("obfs-password") or extra.get("obfs_password") or "").strip()
        if obfs:
            item["obfs"] = obfs
        if obfs_password:
            item["obfs-password"] = obfs_password
        return item

    raise RuntimeError(f"unsupported mihomo proxy protocol: {protocol}")


def _apply_auth(item: dict[str, Any], extra: dict[str, Any]) -> None:
    username = _decode_auth_value(extra.get("username"))
    password = str(extra.get("password") or "").strip()
    if username:
        item["username"] = username
    if password:
        item["password"] = password


def _apply_common_tls(item: dict[str, Any], extra: dict[str, Any]) -> None:
    security = str(extra.get("security") or extra.get("tls") or "").strip().lower()
    sni = str(extra.get("sni") or extra.get("peer") or extra.get("servername") or "").strip()
    fingerprint = str(extra.get("fp") or extra.get("client_fingerprint") or "").strip()
    insecure = _is_truthy(extra.get("allowInsecure") or extra.get("allow_insecure") or extra.get("insecure"))

    if not (security == "tls" or sni or fingerprint or insecure):
        return
    item["tls"] = True
    if sni:
        item["servername"] = sni
        item["sni"] = sni
    if fingerprint:
        item["client-fingerprint"] = fingerprint
    if insecure:
        item["skip-cert-verify"] = True


def _apply_network_opts(item: dict[str, Any], extra: dict[str, Any]) -> None:
    network = str(extra.get("type") or extra.get("network") or extra.get("net") or "").strip().lower()
    if not network or network in {"tcp", "none"}:
        return

    item["network"] = network
    host = str(extra.get("host") or "").strip()
    path = str(extra.get("path") or "/").strip() or "/"
    if network == "ws":
        ws_opts: dict[str, Any] = {"path": path}
        if host:
            ws_opts["headers"] = {"Host": host}
        item["ws-opts"] = ws_opts
        return
    if network == "grpc":
        service_name = str(extra.get("serviceName") or extra.get("service_name") or "").strip()
        if service_name:
            item["grpc-opts"] = {"grpc-service-name": service_name}
        return
    if network == "http":
        http_opts: dict[str, Any] = {"path": [path]}
        if host:
            http_opts["host"] = [host]
        item["http-opts"] = http_opts


def _decode_auth_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    decoded = _safe_b64decode_text(text)
    if decoded and ":" in decoded:
        left, _, right = decoded.partition(":")
        if right:
            return unquote(left).strip()
        nested = _safe_b64decode_text(unquote(left))
        if nested and ":" in nested:
            inner_left, _, _ = nested.partition(":")
            return unquote(inner_left).strip()
    return text


def _safe_b64decode_text(value: str) -> str:
    import base64

    try:
        padded = value + ("=" * (-len(value) % 4))
        return base64.b64decode(padded).decode("utf-8")
    except Exception:
        return ""


def _is_truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
