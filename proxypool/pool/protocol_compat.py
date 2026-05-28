"""Protocol compatibility checking for proxy backends."""

from __future__ import annotations

from typing import Any

# Protocol support matrix
SINGBOX_PROTOCOLS: set[str] = {
    "vmess",
    "trojan",
    "ss",
    "vless",
    "hysteria2",
    "snell",
    "http",
    "https",
    "socks5",
}
MIHOMO_PROTOCOLS: set[str] = {
    "vmess",
    "trojan",
    "ss",
    "vless",
    "hysteria2",
    "http",
    "https",
    "socks5",
}
# Protocols supported by at least one backend
ALL_SUPPORTED_PROTOCOLS: set[str] = SINGBOX_PROTOCOLS | MIHOMO_PROTOCOLS
# Protocols supported by both backends
COMMON_PROTOCOLS: set[str] = SINGBOX_PROTOCOLS & MIHOMO_PROTOCOLS


def get_supported_protocols(backend_type: str) -> set[str]:
    """Return the set of protocols supported by a backend."""
    if backend_type == "singbox":
        return SINGBOX_PROTOCOLS.copy()
    elif backend_type == "mihomo":
        return MIHOMO_PROTOCOLS.copy()
    raise ValueError(f"unknown backend type: {backend_type}")


def supports_protocol(protocol: str, backend_type: str) -> bool:
    """Check if a backend supports a given protocol."""
    return protocol.lower() in get_supported_protocols(backend_type)


def find_backend_for_protocol(protocol: str) -> str | None:
    """Find a backend that supports the given protocol. Returns 'singbox', 'mihomo', or None."""
    proto = protocol.lower()
    if proto in SINGBOX_PROTOCOLS:
        return "singbox"
    if proto in MIHOMO_PROTOCOLS:
        return "mihomo"
    return None


def check_nodes_compatibility(
    nodes: list[dict[str, Any]],
    backend_type: str = "singbox",
) -> dict[str, Any]:
    """Check if a list of proxy nodes are compatible with a backend.

    Each node dict must have at least a 'protocol' key and a 'normalized_key' key.

    Returns a dict with:
      - compatible: bool
      - supported_protocols: list[str]
      - incompatible_nodes: list of dicts with node_key and protocol
    """
    supported = get_supported_protocols(backend_type)
    incompatible: list[dict[str, Any]] = []
    for node in nodes:
        protocol = str(node.get("protocol") or "").lower()
        node_key = str(node.get("normalized_key") or "")
        if protocol and protocol not in supported:
            incompatible.append({"node_key": node_key, "protocol": protocol})
    return {
        "compatible": len(incompatible) == 0,
        "incompatible_nodes": incompatible,
        "backend": backend_type,
        "supported_protocols": sorted(supported),
    }


def filter_compatible_nodes(
    nodes: list[dict[str, Any]],
    backend_type: str = "singbox",
) -> list[dict[str, Any]]:
    """Return only nodes whose protocol is supported by the backend."""
    supported = get_supported_protocols(backend_type)
    return [n for n in nodes if str(n.get("protocol") or "").lower() in supported]
