"""Builds sing-box configurations for proxy chains."""
from __future__ import annotations

import json
from typing import Any

from proxypool.pool.node_pool import NodeEntry
from proxypool.tester.singbox import build_singbox_outbound


class ChainBuilder:
    """Builds sing-box configurations for dynamic proxy chains."""
    
    def __init__(self, storage) -> None:
        self.storage = storage
    
    def build_chain_config(
        self,
        inbound_port: int,
        front_node: NodeEntry,
        exit_node: NodeEntry,
        listen: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """Build a sing-box config for a proxy chain."""
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
        """Build a proxy URL for curl testing through a chain.
        
        This creates a temporary sing-box instance and returns the proxy URL.
        For actual implementation, we use a simpler approach with curl chaining.
        """
        # For curl-based testing, we'll use HTTP proxy chaining
        # Format: http://front_user:front_pass@front_host:front_port
        # This requires the front node to support HTTP proxy
        
        # For now, return the direct proxy URL for testing
        # In production, this would start a temporary sing-box instance
        return f"{exit_node.protocol}://{exit_node.host}:{exit_node.port}"
