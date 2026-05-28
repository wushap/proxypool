"""Builds sing-box configurations for proxy chains."""

from __future__ import annotations

import logging
from typing import Any

from proxypool.pool.node_pool import NodeEntry
from proxypool.pool.protocol_compat import (
    check_nodes_compatibility,
    filter_compatible_nodes,
)
from proxypool.tester.singbox import build_singbox_outbound

logger = logging.getLogger(__name__)


class ChainBuilder:
    """Builds sing-box configurations for dynamic proxy chains."""

    def __init__(self, storage, backend_type: str = "singbox") -> None:
        self.storage = storage
        self.backend_type = backend_type

    def build_chain_config(
        self,
        inbound_port: int,
        front_node: NodeEntry,
        exit_node: NodeEntry,
        listen: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """Build a config for a proxy chain, checking protocol compatibility."""
        # Check protocol compatibility before building
        nodes_data = [
            {"protocol": front_node.protocol, "normalized_key": front_node.key},
            {"protocol": exit_node.protocol, "normalized_key": exit_node.key},
        ]
        compat = check_nodes_compatibility(nodes_data, self.backend_type)
        if not compat["compatible"]:
            incompatible = compat["incompatible_nodes"]
            raise RuntimeError(
                f"Protocol incompatible with {self.backend_type}: "
                + ", ".join(f"{n['node_key']}({n['protocol']})" for n in incompatible)
            )

        inbound_tag = "in-0"
        front_tag = "out-0-hop-0"
        exit_tag = "out-0-hop-1"

        # Build front outbound
        front_outbound = self._build_outbound(front_node, front_tag)
        if front_outbound is None:
            raise RuntimeError(f"Cannot build outbound for front node: {front_node.key}")

        # Build exit outbound with detour to front
        exit_outbound = self._build_outbound(exit_node, exit_tag)
        if exit_outbound is None:
            raise RuntimeError(f"Cannot build outbound for exit node: {exit_node.key}")

        # Chain: exit -> front (detour)
        exit_outbound["detour"] = front_tag

        return {
            "log": {"disabled": True, "level": "warn", "timestamp": True},
            "inbounds": [
                {
                    "type": "http",
                    "tag": inbound_tag,
                    "listen": listen,
                    "listen_port": inbound_port,
                }
            ],
            "outbounds": [exit_outbound, front_outbound, {"type": "direct", "tag": "direct"}],
            "route": {
                "rules": [{"inbound": [inbound_tag], "outbound": exit_tag}],
                "final": "direct",
            },
        }

    def build_probe_config(
        self,
        front_node: NodeEntry,
        exit_node: NodeEntry,
        target_url: str,
    ) -> dict[str, Any]:
        """Build a sing-box config for probing through a chain."""
        inbound_tag = "in-probe"
        front_tag = "out-front"
        exit_tag = "out-exit"

        front_outbound = self._build_outbound(front_node, front_tag)
        exit_outbound = self._build_outbound(exit_node, exit_tag)

        if front_outbound is None or exit_outbound is None:
            raise RuntimeError("Cannot build outbound for probe")

        exit_outbound["detour"] = front_tag

        return {
            "log": {"disabled": True},
            "inbounds": [
                {
                    "type": "http",
                    "tag": inbound_tag,
                    "listen": "127.0.0.1",
                    "listen_port": 0,  # Random port
                }
            ],
            "outbounds": [exit_outbound, front_outbound, {"type": "direct", "tag": "direct"}],
            "route": {
                "rules": [{"inbound": [inbound_tag], "outbound": exit_tag}],
                "final": "direct",
            },
        }

    def _build_outbound(self, node: NodeEntry, tag: str) -> dict[str, Any] | None:
        """Build a sing-box outbound from a node entry."""
        # Get proxy data from storage
        proxy = self.storage.get_proxy_by_key(node.key)
        if proxy is None:
            return None

        return build_singbox_outbound(proxy, tag=tag)

    def build_chain_proxy_url(
        self,
        front_node: NodeEntry,
        exit_node: NodeEntry,
        temp_port: int = 0,
    ) -> str:
        """Build a proxy URL for curl testing through a chain."""
        return f"{exit_node.protocol}://{exit_node.host}:{exit_node.port}"

    def check_nodes_compatibility(
        self,
        nodes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Check if nodes are compatible with this builder's backend."""
        return check_nodes_compatibility(nodes, self.backend_type)

    def filter_compatible_nodes(
        self,
        nodes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Filter nodes to only those compatible with this builder's backend."""
        return filter_compatible_nodes(nodes, self.backend_type)
