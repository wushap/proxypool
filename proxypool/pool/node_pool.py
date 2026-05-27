"""Node pool management for proxy chain routing."""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Any

from proxypool.pool.scoring import CircuitBreaker, CircuitBreakerConfig, CircuitState, NodeScore

DEFAULT_PROTOCOLS_BY_POOL_TYPE: dict[str, set[str]] = {
    "front": {"http", "socks", "ss"},
    "exit": {"http", "socks", "ss", "trojan", "vless", "vmess", "hysteria2"},
}


@dataclass
class NodeEntry:
    """Represents a node in the pool with health state."""
    key: str
    protocol: str
    host: str
    port: int
    raw_link: str
    name: str = ""
    tags: list[str] = field(default_factory=list)

    # Health state
    failure_count: int = 0
    circuit_open: bool = False
    egress_ip: str = ""
    egress_region: str = ""
    latency_ms: int | None = None
    routeable: bool = False

    # Scoring
    score: NodeScore | None = None
    circuit_breaker: CircuitBreaker | None = None

    # Timestamps
    last_success_at: str = ""
    last_failure_at: str = ""


class NodePool:
    """Manages a filtered set of nodes matching regex patterns."""

    def __init__(self, name: str, pool_type: str, regex_filters: list[str]) -> None:
        self.name = name
        self.pool_type = pool_type  # 'front' or 'exit'
        self.regex_filters = regex_filters
        self._compiled_filters = self.compile_filters(regex_filters)
        self._nodes: dict[str, NodeEntry] = {}
        self._lock = threading.RLock()

    @staticmethod
    def compile_filters(regex_filters: list[str]) -> list[re.Pattern[str]]:
        """Compile regex filters for efficient node matching."""
        return [re.compile(pattern) for pattern in regex_filters]

    def matches_node(self, node_key: str, node_name: str, node_tags: list[str]) -> bool:
        """Check if a node matches this pool's filters."""
        if not self._compiled_filters:
            return False

        # Match against node name and tags
        match_targets = [node_name] + node_tags
        for pattern in self._compiled_filters:
            for target in match_targets:
                if pattern.search(target):
                    return True
        return False

    def should_include_by_default(self, node_data: dict[str, Any]) -> bool:
        protocol = str(node_data.get("protocol") or "").strip().lower()
        return protocol in DEFAULT_PROTOCOLS_BY_POOL_TYPE.get(self.pool_type, set())

    def add_node(self, entry: NodeEntry) -> None:
        """Add a node to the pool."""
        with self._lock:
            self._nodes[entry.key] = entry
    
    def remove_node(self, node_key: str) -> None:
        """Remove a node from the pool."""
        with self._lock:
            self._nodes.pop(node_key, None)
    
    def get_node(self, node_key: str) -> NodeEntry | None:
        """Get a node by key."""
        with self._lock:
            return self._nodes.get(node_key)
    
    def get_healthy_nodes(self) -> list[NodeEntry]:
        """Get all healthy nodes, sorted by score (highest first)."""
        with self._lock:
            healthy = [n for n in self._nodes.values() if not n.circuit_open and n.routeable]
        # Sort by score descending (nodes with None score go to end)
        def _sort_key(n: NodeEntry) -> float:
            if n.score is not None:
                return -n.score.final_score
            return 0.0
        healthy.sort(key=_sort_key)
        return healthy
    
    def get_all_nodes(self) -> list[NodeEntry]:
        """Get all nodes."""
        with self._lock:
            return list(self._nodes.values())
    
    def update_node_health(
        self,
        node_key: str,
        success: bool,
        egress_ip: str = "",
        latency_ms: int | None = None,
        max_failures: int = 5,
    ) -> NodeEntry | None:
        """Update node health state based on probe result."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        
        with self._lock:
            entry = self._nodes.get(node_key)
            if entry is None:
                return None
            
            if success:
                entry.failure_count = 0
                entry.circuit_open = False
                entry.last_success_at = now
                if egress_ip:
                    entry.egress_ip = egress_ip
                if latency_ms is not None:
                    entry.latency_ms = latency_ms
            else:
                entry.failure_count += 1
                entry.last_failure_at = now
                if entry.failure_count >= max_failures:
                    entry.circuit_open = True
            
            return entry
    
    def rebuild(self, all_nodes: dict[str, dict[str, Any]]) -> set[str]:
        """Rebuild pool from all nodes. Returns set of matched node keys."""
        matched = set()
        with self._lock:
            self._nodes.clear()
            for key, node_data in all_nodes.items():
                name = node_data.get("name", "")
                tags = node_data.get("tags", [])
                if self.matches_node(key, name, tags) or (
                    not self._compiled_filters and self.should_include_by_default(node_data)
                ):
                    entry = NodeEntry(
                        key=key,
                        protocol=node_data.get("protocol", ""),
                        host=node_data.get("host", ""),
                        port=node_data.get("port", 0),
                        raw_link=node_data.get("raw_link", ""),
                        name=name,
                        tags=tags,
                    )
                    self._nodes[key] = entry
                    matched.add(key)
        return matched
