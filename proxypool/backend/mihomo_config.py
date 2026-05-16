from __future__ import annotations

from typing import Any

from proxypool.backend.egress_backend import ChainInstanceSpec


def build_mihomo_chain_config(spec: ChainInstanceSpec) -> dict[str, Any]:
    listener_type = str(spec.inbound_type or "http").strip().lower() or "http"
    if listener_type not in {"http", "socks", "mixed"}:
        raise RuntimeError(f"unsupported mihomo inbound_type: {spec.inbound_type}")

    front_name = str(spec.front_proxy.get("name") or "front").strip() or "front"
    exit_name = str(spec.exit_proxy.get("name") or "exit").strip() or "exit"
    front_proxy = _build_mihomo_proxy(spec.front_proxy, name=front_name)
    exit_proxy = _build_mihomo_proxy(spec.exit_proxy, name=exit_name, dialer_proxy=front_name)

    return {
        "listeners": [
            {
                "name": spec.instance_id,
                "type": listener_type,
                "listen": str(spec.listen or "127.0.0.1"),
                "port": int(spec.port),
            }
        ],
        "proxies": [front_proxy, exit_proxy],
        "rules": ["MATCH," + exit_name],
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
        return item
    if protocol == "socks":
        item["type"] = "socks5"
        _apply_auth(item, extra)
        return item
    if protocol == "ss":
        cipher = str(extra.get("cipher") or "").strip()
        password = str(extra.get("password") or "").strip()
        if not cipher or not password:
            raise RuntimeError("mihomo shadowsocks proxy requires cipher and password")
        item["type"] = "ss"
        item["cipher"] = cipher
        item["password"] = password
        return item
    if protocol == "trojan":
        password = str(extra.get("password") or "").strip()
        if not password:
            raise RuntimeError("mihomo trojan proxy requires password")
        item["type"] = "trojan"
        item["password"] = password
        sni = str(extra.get("sni") or extra.get("peer") or "").strip()
        if sni:
            item["sni"] = sni
        return item

    raise RuntimeError(f"unsupported mihomo proxy protocol: {protocol}")


def _apply_auth(item: dict[str, Any], extra: dict[str, Any]) -> None:
    username = str(extra.get("username") or "").strip()
    password = str(extra.get("password") or "").strip()
    if username:
        item["username"] = username
    if password:
        item["password"] = password
