"""Proxy chain service coordinating node pools, routing, and health."""
from __future__ import annotations

import logging
import threading
from typing import Any

from proxypool.pool.chain_builder import ChainBuilder
from proxypool.pool.health_manager import HealthConfig, HealthManager
from proxypool.pool.node_pool import NodeEntry, NodePool
from proxypool.pool.sticky_router import StickyRouter
from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.tester.singbox import SingboxProber

logger = logging.getLogger(__name__)


class ProxyChainService:
    """High-level service for proxy chain management."""
    
    def __init__(
        self,
        storage: SQLiteProxyStorage,
        singbox_binary: str = "sing-box",
        test_url: str = "https://cloudflare.com/cdn-cgi/trace",
        health_config: HealthConfig | None = None,
        sticky_ttl_sec: int = 3600,
    ) -> None:
        self.storage = storage
        self.singbox_binary = singbox_binary
        self.test_url = test_url
        
        # Initialize components
        self.front_pool = NodePool("front", "front", [])
        self.exit_pool = NodePool("exit", "exit", [])
        self.chain_builder = ChainBuilder(storage)
        self.prober = SingboxProber(binary=singbox_binary, test_url=test_url)
        self.health_manager = HealthManager(
            storage=storage,
            front_pool=self.front_pool,
            exit_pool=self.exit_pool,
            config=health_config or HealthConfig(),
            build_chain_proxy_url=self.chain_builder.build_chain_proxy_url,
            probe_chain=self._probe_exit_chain,
            singbox_binary=singbox_binary,
        )
        self.sticky_router = StickyRouter(
            front_pool=self.front_pool,
            exit_pool=self.exit_pool,
            sticky_ttl_sec=sticky_ttl_sec,
        )

        self._initialized = False
        self._lock = threading.RLock()

    def initialize(self) -> None:
        """Initialize pools from storage."""
        with self._lock:
            if self._initialized:
                return
            self._load_pool_configs()
            self._refresh_pools_locked()
            self._initialized = True
            logger.info("ProxyChainService initialized")

    def refresh_pools(self) -> None:
        """Refresh pools from storage while preserving persisted health state."""
        with self._lock:
            self.initialize()
            self._refresh_pools_locked()

    def _load_pool_configs(self) -> None:
        """Load persisted pool filters into the in-memory pools."""
        pools = self.storage.list_proxy_pools_v2()
        pool_filters = {
            str(pool_config.get("pool_type") or ""): list(pool_config.get("regex_filters") or [])
            for pool_config in pools
        }
        self.front_pool.regex_filters = pool_filters.get("front", [])
        self.front_pool._compiled_filters = self.front_pool.compile_filters(self.front_pool.regex_filters)
        self.exit_pool.regex_filters = pool_filters.get("exit", [])
        self.exit_pool._compiled_filters = self.exit_pool.compile_filters(self.exit_pool.regex_filters)

    def _refresh_pools_locked(self) -> None:
        """Rebuild pools and reapply persisted health state."""
        self._rebuild_pools()
        self._load_health_state()

    def _rebuild_pools(self) -> None:
        """Rebuild both pools from all proxies in storage."""
        all_proxies = self.storage.list_proxies(limit=100000)

        # Convert to dict format for pool rebuild
        nodes_dict = {}
        for proxy in all_proxies:
            key = proxy.get("normalized_key", "")
            if key:
                nodes_dict[key] = {
                    "protocol": proxy.get("protocol", ""),
                    "host": proxy.get("host", ""),
                    "port": proxy.get("port", 0),
                    "raw_link": proxy.get("raw_link", ""),
                    "name": proxy.get("name", ""),
                    "tags": [proxy.get("name", ""), proxy.get("source", "")],
                }
        
        front_matched = self.front_pool.rebuild(nodes_dict)
        exit_matched = self.exit_pool.rebuild(nodes_dict)
        
        logger.info("Pools rebuilt: front=%s, exit=%s", len(front_matched), len(exit_matched))

    def _load_health_state(self) -> None:
        """Load persisted health state into pools."""
        health_records = self.storage.list_node_health()
        for record in health_records:
            node_key = record.get("node_key", "")
            
            # Update front pool
            front_node = self.front_pool.get_node(node_key)
            if front_node:
                front_node.failure_count = record.get("failure_count", 0)
                front_node.circuit_open = bool(record.get("circuit_open_since"))
                front_node.egress_ip = record.get("egress_ip", "")
                front_node.latency_ms = record.get("latency_avg_ms")
            
            # Update exit pool
            exit_node = self.exit_pool.get_node(node_key)
            if exit_node:
                exit_node.failure_count = record.get("failure_count", 0)
                exit_node.circuit_open = bool(record.get("circuit_open_since"))
                exit_node.egress_ip = record.get("egress_ip", "")
                exit_node.latency_ms = record.get("latency_avg_ms")

    def _probe_exit_chain(self, front_node: NodeEntry, exit_node: NodeEntry) -> tuple[bool, str, int | None]:
        """Probe an exit node through a specific front node using sing-box."""
        front_proxy = self.storage.get_proxy_by_key(front_node.key)
        exit_proxy = self.storage.get_proxy_by_key(exit_node.key)
        if front_proxy is None or exit_proxy is None:
            return False, "", None

        result = self.prober.probe_with_front_proxy(exit_proxy, front_proxy)
        return result.available, "", result.latency_ms

    def start(self) -> None:
        """Start the service and health probing."""
        self.initialize()
        self.refresh_pools()
        self.health_manager.start()
        logger.info("ProxyChainService started")

    def stop(self) -> None:
        """Stop the service."""
        self.health_manager.stop()
        logger.info("ProxyChainService stopped")

    def update_pool_config(
        self,
        pool_type: str,
        regex_filters: list[str],
    ) -> dict[str, Any]:
        """Update pool configuration."""
        with self._lock:
            self.initialize()
            self.storage.upsert_proxy_pool_v2(
                name=pool_type,
                pool_type=pool_type,
                regex_filters=regex_filters,
            )
            self._load_pool_configs()
            self._refresh_pools_locked()
            return self.get_pool_status()

    def get_pool_status(self, refresh: bool = False) -> dict[str, Any]:
        """Get status of both pools."""
        if refresh:
            self.refresh_pools()
        front_nodes = self.front_pool.get_all_nodes()
        exit_nodes = self.exit_pool.get_all_nodes()

        return {
            "front_pool": {
                "name": "front",
                "regex_filters": self.front_pool.regex_filters,
                "total_nodes": len(front_nodes),
                "healthy_nodes": len(self.front_pool.get_healthy_nodes()),
                "nodes": [self._node_summary(n) for n in front_nodes[:50]],
            },
            "exit_pool": {
                "name": "exit",
                "regex_filters": self.exit_pool.regex_filters,
                "total_nodes": len(exit_nodes),
                "healthy_nodes": len(self.exit_pool.get_healthy_nodes()),
                "nodes": [self._node_summary(n) for n in exit_nodes[:50]],
            },
        }

    def _node_summary(self, node: NodeEntry) -> dict[str, Any]:
        """Create a summary of a node."""
        return {
            "key": node.key,
            "name": node.name,
            "protocol": node.protocol,
            "host": node.host,
            "port": node.port,
            "healthy": not node.circuit_open,
            "failure_count": node.failure_count,
            "egress_ip": node.egress_ip,
            "latency_ms": node.latency_ms,
        }

    def route_request(
        self,
        account: str = "",
        pool_id: int = 0,
        target_domain: str = "",
    ) -> dict[str, Any] | None:
        """Route a request and return the chain configuration."""
        self.refresh_pools()
        result = self.sticky_router.route(account, pool_id, target_domain)

        if result is None:
            return None

        return {
            "front_node": self._node_summary(result.front_node),
            "exit_node": self._node_summary(result.exit_node),
            "lease_created": result.lease_created,
        }

    def get_leases(self, pool_id: int | None = None) -> list[dict[str, Any]]:
        """Get sticky leases."""
        return self.sticky_router.get_leases(pool_id)

    def cleanup_leases(self) -> int:
        """Cleanup expired leases."""
        return self.sticky_router.cleanup_expired_leases()

    def get_health_status(self) -> dict[str, Any]:
        """Get health manager status."""
        return {
            "running": self.health_manager._running,
            "config": {
                "max_consecutive_failures": self.health_manager.config.max_consecutive_failures,
                "probe_interval_sec": self.health_manager.config.probe_interval_sec,
                "probe_timeout_sec": self.health_manager.config.probe_timeout_sec,
            },
        }


def health_manager_running(manager: HealthManager) -> bool:
    """Check if health manager is running."""
    return manager._running
