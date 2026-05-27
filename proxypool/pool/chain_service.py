"""Proxy chain service coordinating node pools, routing, and health."""
from __future__ import annotations

import itertools
import logging
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import NamedTuple
from typing import Any

from proxypool.pool.chain_builder import ChainBuilder
from proxypool.pool.health_manager import HealthConfig, HealthManager
from proxypool.pool.node_pool import NodeEntry, NodePool
from proxypool.pool.sticky_router import Lease, StickyRouter
from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.tester.singbox import SingboxProber

logger = logging.getLogger(__name__)


class MultiHopLease(NamedTuple):
    session_id: str
    pool_id: int
    endpoint_id: int
    instance_id: str
    hop_node_keys: list[str]
    exit_node_key: str
    egress_ip: str
    expires_at: datetime
    last_accessed: datetime


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
        self._multi_hop_leases: dict[tuple[str, int, int], MultiHopLease] = {}
        self._failed_endpoint_routes: dict[tuple[int, tuple[str, ...]], datetime] = {}
        self._failed_endpoint_nodes: dict[tuple[int, str], datetime] = {}
        self._healthy_endpoint_routes: dict[tuple[int, tuple[str, ...]], datetime] = {}

        self._initialized = False
        self._lock = threading.RLock()

    def initialize(self) -> None:
        """Initialize pools from storage."""
        with self._lock:
            if self._initialized:
                return
            self._load_pool_configs()
            self._refresh_pools_locked()
            self._load_sticky_leases()
            self._load_failed_routes()
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

    def _load_sticky_leases(self) -> None:
        with self._lock:
            self.sticky_router._leases.clear()
            self.sticky_router._ip_load.clear()
            self._multi_hop_leases.clear()
            for item in self.storage.list_sticky_leases():
                expires_at = _parse_datetime(item.get("expires_at"))
                last_accessed = _parse_datetime(item.get("last_accessed"))
                if expires_at is None or last_accessed is None:
                    continue
                endpoint_id = int(item.get("endpoint_id") or 0)
                if endpoint_id > 0:
                    hop_node_keys = self._load_endpoint_hop_node_keys(endpoint_id, str(item.get("exit_node_key") or ""))
                    lease = MultiHopLease(
                        session_id=str(item.get("session_id") or ""),
                        pool_id=int(item.get("pool_id") or 0),
                        endpoint_id=endpoint_id,
                        instance_id=str(item.get("instance_id") or ""),
                        hop_node_keys=hop_node_keys,
                        exit_node_key=str(item.get("exit_node_key") or ""),
                        egress_ip=str(item.get("egress_ip") or ""),
                        expires_at=expires_at,
                        last_accessed=last_accessed,
                    )
                    self._multi_hop_leases[(lease.session_id, lease.pool_id, lease.endpoint_id)] = lease
                    continue
                lease = Lease(
                    session_id=str(item.get("session_id") or ""),
                    pool_id=int(item.get("pool_id") or 0),
                    instance_id=str(item.get("instance_id") or ""),
                    exit_node_key=str(item.get("exit_node_key") or ""),
                    egress_ip=str(item.get("egress_ip") or ""),
                    expires_at=expires_at,
                    last_accessed=last_accessed,
                )
                key = (lease.session_id, lease.pool_id)
                self.sticky_router._leases[key] = lease
                if lease.egress_ip:
                    self.sticky_router._ip_load[lease.egress_ip] = self.sticky_router._ip_load.get(lease.egress_ip, 0) + 1

    def _load_failed_routes(self) -> None:
        """Load persisted failed routes and nodes from database into memory."""
        # Load failed routes
        for route in self.storage.list_active_failed_routes():
            endpoint_id = int(route.get("endpoint_id") or 0)
            route_signature = str(route.get("route_signature") or "").strip()
            expires_at_str = str(route.get("expires_at") or "")
            if endpoint_id > 0 and route_signature:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    # Parse route_signature back into tuple key
                    # Format: "node_key_1,node_key_2,..." (comma-separated)
                    keys = tuple(k.strip() for k in route_signature.split(",") if k.strip())
                    if keys:
                        self._failed_endpoint_routes[(endpoint_id, keys)] = expires_at
                except (ValueError, AttributeError):
                    pass

        # Load failed route nodes
        for node_record in self.storage.list_active_failed_route_nodes():
            endpoint_id = int(node_record.get("endpoint_id") or 0)
            node_key = str(node_record.get("node_key") or "").strip()
            expires_at_str = str(node_record.get("expires_at") or "")
            if endpoint_id > 0 and node_key:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    self._failed_endpoint_nodes[(endpoint_id, node_key)] = expires_at
                except (ValueError, AttributeError):
                    pass

        # Cleanup expired records from database
        self.storage.cleanup_expired_failed_routes()
        self.storage.cleanup_expired_failed_route_nodes()

    def _rebuild_pools(self) -> None:
        """Rebuild both pools from all proxies in storage."""
        all_proxies = self.storage.list_proxies(limit=100000)
        proxy_status = {
            str(proxy.get("normalized_key") or ""): {
                "available": bool(proxy.get("available")),
                "latency_ms": proxy.get("latency_ms"),
                "egress_ip": str(proxy.get("resolved_ip") or ""),
            }
            for proxy in all_proxies
            if str(proxy.get("normalized_key") or "")
        }

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
        self._apply_probe_status(self.front_pool, proxy_status)
        self._apply_probe_status(self.exit_pool, proxy_status)
        
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
                exit_node.routeable = exit_node.routeable or bool(record.get("last_success_at"))

    def _apply_probe_status(self, pool: NodePool, proxy_status: dict[str, dict[str, Any]]) -> None:
        for node in pool.get_all_nodes():
            status = proxy_status.get(node.key, {})
            node.routeable = bool(status.get("available"))
            if status.get("latency_ms") is not None:
                node.latency_ms = int(status["latency_ms"])
            if status.get("egress_ip"):
                node.egress_ip = str(status["egress_ip"])

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
        session_id: str = "",
        pool_id: int = 0,
        endpoint_id: int | str = 0,
        target_domain: str = "",
        live_instance_ids: set[str] | None = None,
    ) -> dict[str, Any] | None:
        """Route a request and return the chain configuration."""
        resolved_endpoint_id = 0
        if isinstance(endpoint_id, str):
            text = str(endpoint_id or "").strip()
            if text.isdigit():
                resolved_endpoint_id = int(text)
            elif not target_domain:
                target_domain = text
        else:
            resolved_endpoint_id = int(endpoint_id or 0)
        if resolved_endpoint_id > 0:
            self.refresh_pools()
            return self._route_endpoint_request(
                session_id=session_id,
                endpoint_id=resolved_endpoint_id,
                target_domain=target_domain,
                live_instance_ids=live_instance_ids,
            )
        self.refresh_pools()
        result = self.sticky_router.route(
            session_id,
            pool_id,
            target_domain,
            live_instance_ids=live_instance_ids,
        )

        if result is None:
            return None

        if session_id:
            leases = self.sticky_router.get_leases(pool_id)
            for lease in leases:
                if lease["session_id"] != session_id:
                    continue
                self.storage.upsert_sticky_lease(
                    session_id=lease["session_id"],
                    pool_id=int(lease["pool_id"]),
                    endpoint_id=int(lease.get("endpoint_id") or 0),
                    instance_id=str(lease.get("instance_id") or ""),
                    exit_node_key=str(lease["exit_node_key"]),
                    egress_ip=str(lease["egress_ip"]),
                    expires_at=str(lease["expires_at"]),
                    last_accessed=str(lease["last_accessed"]),
                )
                break

        return {
            "front_node": self._node_summary(result.front_node),
            "exit_node": self._node_summary(result.exit_node),
            "hop_nodes": [self._node_summary(result.front_node), self._node_summary(result.exit_node)],
            "hop_node_keys": [result.front_node.key, result.exit_node.key],
            "endpoint_id": 0,
            "route_signature": f"{result.front_node.key}>{result.exit_node.key}",
            "lease_created": result.lease_created,
            "bound_instance_id": result.bound_instance_id,
            "instance_reused": result.instance_reused,
        }

    def bind_instance_to_session(
        self,
        session_id: str,
        pool_id: int,
        instance_id: str,
        endpoint_id: int = 0,
    ) -> dict[str, Any] | None:
        self.initialize()
        if int(endpoint_id) > 0:
            return self.bind_endpoint_instance_to_session(
                session_id=session_id,
                endpoint_id=int(endpoint_id),
                instance_id=instance_id,
            )
        lease = self.sticky_router._leases.get((session_id, pool_id))
        if lease is None:
            persisted = self.storage.get_sticky_lease(session_id, pool_id)
            if persisted is None:
                return None
            self.storage.upsert_sticky_lease(
                session_id=session_id,
                pool_id=pool_id,
                endpoint_id=int(persisted.get("endpoint_id") or 0),
                instance_id=instance_id,
                exit_node_key=str(persisted.get("exit_node_key") or ""),
                egress_ip=str(persisted.get("egress_ip") or ""),
                expires_at=str(persisted.get("expires_at") or ""),
                last_accessed=str(persisted.get("last_accessed") or ""),
            )
            return self.storage.get_sticky_lease(session_id, pool_id)

        self.sticky_router.bind_instance(session_id, pool_id, instance_id)
        lease = self.sticky_router._leases.get((session_id, pool_id))
        if lease is None:
            return self.storage.get_sticky_lease(session_id, pool_id)
        self.storage.upsert_sticky_lease(
            session_id=session_id,
            pool_id=pool_id,
            endpoint_id=0,
            instance_id=lease.instance_id,
            exit_node_key=lease.exit_node_key,
            egress_ip=lease.egress_ip,
            expires_at=lease.expires_at.isoformat(),
            last_accessed=lease.last_accessed.isoformat(),
        )
        return self.storage.get_sticky_lease(session_id, pool_id)

    def bind_endpoint_instance_to_session(
        self,
        session_id: str,
        endpoint_id: int,
        instance_id: str,
    ) -> dict[str, Any] | None:
        self.initialize()
        endpoint = self.storage.get_http_proxy_endpoint(endpoint_id)
        if endpoint is None:
            return None
        hops = list(endpoint.get("hops") or [])
        if not hops:
            return None
        entry_pool_id = int(hops[0].get("pool_id") or 0)
        if entry_pool_id <= 0:
            return None

        key = (str(session_id or "").strip(), entry_pool_id, int(endpoint_id))
        with self._lock:
            lease = self._multi_hop_leases.get(key)
        if lease is None:
            persisted = self.storage.get_sticky_lease(session_id, entry_pool_id, endpoint_id)
            if persisted is None:
                return None
            hop_node_keys = self._load_endpoint_hop_node_keys(endpoint_id, str(persisted.get("exit_node_key") or ""))
            lease = MultiHopLease(
                session_id=str(session_id or "").strip(),
                pool_id=entry_pool_id,
                endpoint_id=int(endpoint_id),
                instance_id=str(instance_id or ""),
                hop_node_keys=hop_node_keys,
                exit_node_key=str(persisted.get("exit_node_key") or ""),
                egress_ip=str(persisted.get("egress_ip") or ""),
                expires_at=_parse_datetime(persisted.get("expires_at")) or datetime.now(timezone.utc),
                last_accessed=_parse_datetime(persisted.get("last_accessed")) or datetime.now(timezone.utc),
            )
        else:
            lease = lease._replace(instance_id=str(instance_id or ""))
        with self._lock:
            self._multi_hop_leases[key] = lease
        self.storage.upsert_sticky_lease(
            session_id=lease.session_id,
            pool_id=lease.pool_id,
            endpoint_id=lease.endpoint_id,
            instance_id=lease.instance_id,
            exit_node_key=lease.exit_node_key,
            egress_ip=lease.egress_ip,
            expires_at=lease.expires_at.isoformat(),
            last_accessed=lease.last_accessed.isoformat(),
        )
        return self.storage.get_sticky_lease(lease.session_id, lease.pool_id, lease.endpoint_id)

    def get_leases(
        self,
        pool_id: int | None = None,
        endpoint_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get sticky leases."""
        if endpoint_id is not None:
            self.initialize()
            items: list[dict[str, Any]] = []
            with self._lock:
                for lease in self._multi_hop_leases.values():
                    if int(lease.endpoint_id) != int(endpoint_id):
                        continue
                    if pool_id is not None and int(lease.pool_id) != int(pool_id):
                        continue
                    items.append({
                        "session_id": lease.session_id,
                        "pool_id": lease.pool_id,
                        "endpoint_id": lease.endpoint_id,
                        "instance_id": lease.instance_id,
                        "exit_node_key": lease.exit_node_key,
                        "hop_node_keys": list(lease.hop_node_keys),
                        "egress_ip": lease.egress_ip,
                        "expires_at": lease.expires_at.isoformat(),
                        "last_accessed": lease.last_accessed.isoformat(),
                    })
            items.sort(key=lambda item: (item["pool_id"], item["session_id"]))
            return items
        return self.sticky_router.get_leases(pool_id)

    def cleanup_leases(self) -> int:
        """Cleanup expired leases."""
        removed = self.sticky_router.cleanup_expired_leases()
        now = datetime.now(timezone.utc)
        with self._lock:
            expired_multi_keys = [
                key for key, lease in self._multi_hop_leases.items()
                if now >= lease.expires_at
            ]
            for key in expired_multi_keys:
                self._multi_hop_leases.pop(key, None)
        removed += len(expired_multi_keys)
        self.storage.cleanup_expired_leases()
        return removed

    def report_endpoint_route_failure(
        self,
        endpoint_id: int,
        pool_id: int,
        session_id: str = "",
        hop_node_keys: list[str] | None = None,
        cooldown_sec: int = 300,
    ) -> None:
        """Temporarily exclude a failed multi-hop route without condemning its nodes."""
        safe_endpoint_id = int(endpoint_id or 0)
        safe_pool_id = int(pool_id or 0)
        safe_session_id = str(session_id or "").strip()
        keys = tuple(str(item or "").strip() for item in list(hop_node_keys or []) if str(item or "").strip())
        with self._lock:
            if safe_endpoint_id > 0 and safe_pool_id > 0 and safe_session_id:
                self._multi_hop_leases.pop((safe_session_id, safe_pool_id, safe_endpoint_id), None)
                self.storage.delete_sticky_lease(safe_session_id, safe_pool_id, safe_endpoint_id)
            if safe_endpoint_id > 0 and keys:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(1, int(cooldown_sec or 300)))
                expires_at_str = expires_at.isoformat()
                route_signature = ">".join(keys)

                # Update in-memory cache
                self._failed_endpoint_routes[(safe_endpoint_id, keys)] = expires_at
                self._healthy_endpoint_routes.pop((safe_endpoint_id, keys), None)
                self._failed_endpoint_nodes[(safe_endpoint_id, keys[0])] = expires_at

                # Persist to database
                try:
                    self.storage.upsert_failed_route(safe_endpoint_id, route_signature, expires_at_str)
                    self.storage.upsert_failed_route_node(safe_endpoint_id, keys[0], expires_at_str)
                except Exception as e:
                    logger.error(f"Failed to persist failed route: {e}")

    def report_endpoint_route_success(
        self,
        endpoint_id: int,
        hop_node_keys: list[str] | None = None,
        ttl_sec: int = 600,
    ) -> None:
        safe_endpoint_id = int(endpoint_id or 0)
        keys = tuple(str(item or "").strip() for item in list(hop_node_keys or []) if str(item or "").strip())
        if safe_endpoint_id <= 0 or not keys:
            return

        route_signature = ">".join(keys)

        with self._lock:
            # Update in-memory cache
            self._failed_endpoint_routes.pop((safe_endpoint_id, keys), None)
            for node_key in keys:
                self._failed_endpoint_nodes.pop((safe_endpoint_id, node_key), None)
            self._healthy_endpoint_routes[(safe_endpoint_id, keys)] = datetime.now(timezone.utc) + timedelta(
                seconds=max(1, int(ttl_sec or 600))
            )

            # Remove from database
            try:
                self.storage.delete_failed_route(safe_endpoint_id, route_signature)
                for node_key in keys:
                    self.storage.delete_failed_route_node(safe_endpoint_id, node_key)
            except Exception as e:
                logger.error(f"Failed to delete failed route: {e}")

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

    def _route_endpoint_request(
        self,
        session_id: str,
        endpoint_id: int,
        target_domain: str,
        live_instance_ids: set[str] | None = None,
    ) -> dict[str, Any] | None:
        endpoint = self.storage.get_http_proxy_endpoint(endpoint_id)
        if endpoint is None:
            return None
        hops = list(endpoint.get("hops") or [])
        if not hops:
            return None

        entry_pool_id = int(hops[0].get("pool_id") or 0)
        if entry_pool_id <= 0:
            return None

        now = datetime.now(timezone.utc)
        lease_created = False
        instance_reused = False
        bound_instance_id = ""
        hop_node_keys: list[str] | None = None
        egress_ip = ""
        exit_node_key = ""

        if session_id:
            lease = self._get_multi_hop_lease(session_id, entry_pool_id, endpoint_id, now)
            if lease is not None:
                reused_hops = self._reuse_multi_hop_lease(
                    lease=lease,
                    target_domain=target_domain,
                    live_instance_ids=live_instance_ids,
                )
                if reused_hops is not None:
                    hop_node_keys = reused_hops
                    egress_ip = lease.egress_ip
                    exit_node_key = lease.exit_node_key
                    bound_instance_id = lease.instance_id
                    instance_reused = bool(bound_instance_id and bound_instance_id in set(live_instance_ids or set()))
                    refreshed_lease = lease._replace(last_accessed=now)
                    with self._lock:
                        self._multi_hop_leases[(lease.session_id, lease.pool_id, lease.endpoint_id)] = refreshed_lease

        if not hop_node_keys:
            selection = self._select_endpoint_hops(endpoint_id=endpoint_id, target_domain=target_domain)
            if selection is None:
                return None
            hop_node_keys = selection["hop_node_keys"]
            egress_ip = selection["egress_ip"]
            exit_node_key = hop_node_keys[-1]
            if session_id:
                ttl_sec = max(1, int(endpoint.get("sticky_ttl_sec") or self.sticky_router.sticky_ttl_sec or 3600))
                created = MultiHopLease(
                    session_id=str(session_id or "").strip(),
                    pool_id=entry_pool_id,
                    endpoint_id=int(endpoint_id),
                    instance_id="",
                    hop_node_keys=list(hop_node_keys),
                    exit_node_key=exit_node_key,
                    egress_ip=egress_ip,
                    expires_at=now + timedelta(seconds=ttl_sec),
                    last_accessed=now,
                )
                with self._lock:
                    self._multi_hop_leases[(created.session_id, created.pool_id, created.endpoint_id)] = created
                lease_created = True

        hop_nodes = [self._proxy_to_node_summary(self.storage.get_proxy_by_key(key)) for key in hop_node_keys]
        if any(node is None for node in hop_nodes):
            return None
        hop_nodes_clean = [node for node in hop_nodes if node is not None]
        route_signature = self._build_route_signature(endpoint_id, hop_node_keys)

        if session_id:
            with self._lock:
                lease_key = (str(session_id or "").strip(), entry_pool_id, int(endpoint_id))
                stored_lease = self._multi_hop_leases.get(lease_key)
            self.storage.upsert_sticky_lease(
                session_id=str(session_id or "").strip(),
                pool_id=entry_pool_id,
                endpoint_id=int(endpoint_id),
                instance_id=bound_instance_id,
                exit_node_key=exit_node_key,
                egress_ip=egress_ip,
                expires_at=stored_lease.expires_at.isoformat() if stored_lease else now.isoformat(),
                last_accessed=now.isoformat(),
            )

        return {
            "front_node": hop_nodes_clean[0],
            "exit_node": hop_nodes_clean[-1],
            "hop_nodes": hop_nodes_clean,
            "hop_node_keys": list(hop_node_keys),
            "endpoint_id": int(endpoint_id),
            "pool_id": entry_pool_id,
            "route_signature": route_signature,
            "lease_created": lease_created,
            "bound_instance_id": bound_instance_id,
            "instance_reused": instance_reused,
        }

    def _select_endpoint_hops(self, endpoint_id: int, target_domain: str) -> dict[str, Any] | None:
        endpoint = self.storage.get_http_proxy_endpoint(endpoint_id)
        if endpoint is None:
            return None
        pool_hops = list(endpoint.get("hops") or [])
        if not pool_hops:
            return None

        hop_node_keys: list[str] = []
        preferred_hops = self._pick_healthy_endpoint_route(endpoint_id, pool_hops)
        if preferred_hops is not None:
            hop_node_keys = preferred_hops
            exit_proxy = self.storage.get_proxy_by_key(hop_node_keys[-1]) or {}
            return {
                "hop_node_keys": hop_node_keys,
                "egress_ip": str(exit_proxy.get("resolved_ip") or ""),
            }

        selection = self._search_endpoint_hop_candidates(
            endpoint_id=endpoint_id,
            pool_hops=pool_hops,
            target_domain=target_domain,
        )
        if selection is None:
            return None
        hop_node_keys = selection["hop_node_keys"]
        if not hop_node_keys:
            return None
        exit_proxy = self.storage.get_proxy_by_key(hop_node_keys[-1]) or {}
        return {
            "hop_node_keys": hop_node_keys,
            "egress_ip": str(exit_proxy.get("resolved_ip") or selection.get("egress_ip") or ""),
        }

    def _search_endpoint_hop_candidates(
        self,
        endpoint_id: int,
        pool_hops: list[dict[str, Any]],
        target_domain: str,
    ) -> dict[str, Any] | None:
        del target_domain
        candidate_groups: list[list[dict[str, Any]]] = []
        for hop in pool_hops:
            pool_id = int(hop.get("pool_id") or 0)
            if pool_id <= 0:
                return None
            candidates = [
                item for item in self.storage.list_proxy_pool_candidates(pool_id, limit=200, exclude_keys=set())
                if bool(item.get("available")) and str(item.get("normalized_key") or "").strip()
            ]
            candidates = [
                item for item in candidates
                if not self._is_endpoint_node_failed(endpoint_id, str(item.get("normalized_key") or "").strip())
            ]
            candidates.sort(key=self._candidate_score)
            if not candidates:
                return None
            candidate_groups.append(candidates)

        checked = 0
        max_checks = max(1, min(1000, max(100, sum(len(group) for group in candidate_groups) * len(candidate_groups))))
        for combo in itertools.product(*candidate_groups):
            checked += 1
            if checked > max_checks:
                break
            keys = [str(item.get("normalized_key") or "").strip() for item in combo]
            if len(set(keys)) != len(keys):
                continue
            if self._is_endpoint_route_failed(endpoint_id, keys):
                continue
            exit_proxy = combo[-1]
            return {
                "hop_node_keys": keys,
                "egress_ip": str(exit_proxy.get("resolved_ip") or ""),
            }
        return None

    def _pick_pool_candidate(
        self,
        pool_id: int,
        exclude_keys: set[str],
        target_domain: str,
    ) -> dict[str, Any] | None:
        del target_domain
        candidates = [
            item for item in self.storage.list_proxy_pool_candidates(pool_id, limit=200, exclude_keys=exclude_keys)
            if bool(item.get("available"))
        ]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        a, b = random.sample(candidates, 2)
        return a if self._candidate_score(a) <= self._candidate_score(b) else b

    def _candidate_score(self, proxy: dict[str, Any]) -> float:
        latency = proxy.get("latency_ms")
        if latency is None:
            return float("inf")
        try:
            return float(latency)
        except Exception:
            return float("inf")

    def _pick_healthy_endpoint_route(self, endpoint_id: int, pool_hops: list[dict[str, Any]]) -> list[str] | None:
        now = datetime.now(timezone.utc)
        pool_count = len(pool_hops)
        candidates: list[tuple[datetime, list[str]]] = []
        with self._lock:
            healthy_routes = list(self._healthy_endpoint_routes.items())
        for (stored_endpoint_id, keys), expires_at in healthy_routes:
            if now >= expires_at:
                with self._lock:
                    self._healthy_endpoint_routes.pop((stored_endpoint_id, keys), None)
                continue
            if int(stored_endpoint_id) != int(endpoint_id):
                continue
            hop_node_keys = list(keys)
            if len(hop_node_keys) != pool_count:
                continue
            if self._is_endpoint_route_failed(endpoint_id, hop_node_keys):
                continue
            if not self._endpoint_route_matches_pools(hop_node_keys, pool_hops):
                continue
            candidates.append((expires_at, hop_node_keys))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _endpoint_route_matches_pools(self, hop_node_keys: list[str], pool_hops: list[dict[str, Any]]) -> bool:
        used: set[str] = set()
        for key, hop in zip(hop_node_keys, pool_hops, strict=False):
            if key in used:
                return False
            used.add(key)
            pool_id = int(hop.get("pool_id") or 0)
            if pool_id <= 0:
                return False
            candidates = self.storage.list_proxy_pool_candidates(pool_id, limit=500, exclude_keys=set())
            matched = [
                item for item in candidates
                if str(item.get("normalized_key") or "") == str(key)
                and bool(item.get("available"))
            ]
            if not matched:
                return False
        return True

    def _is_endpoint_route_failed(self, endpoint_id: int, hop_node_keys: list[str]) -> bool:
        route_signature = ">".join(str(item or "").strip() for item in hop_node_keys if str(item or "").strip())
        key = (int(endpoint_id or 0), tuple(str(item or "").strip() for item in hop_node_keys if str(item or "").strip()))

        # Check in-memory cache first
        with self._lock:
            expires_at = self._failed_endpoint_routes.get(key)
            if expires_at is not None:
                if datetime.now(timezone.utc) >= expires_at:
                    self._failed_endpoint_routes.pop(key, None)
                else:
                    return True

        # Check database
        try:
            if self.storage.is_route_failed(endpoint_id, route_signature):
                return True
        except Exception as e:
            logger.error(f"Failed to check route failure in DB: {e}")

        return False

    def _is_endpoint_node_failed(self, endpoint_id: int, node_key: str) -> bool:
        safe_key = str(node_key or "").strip()
        if not safe_key:
            return False

        key = (int(endpoint_id or 0), safe_key)

        # Check in-memory cache first
        with self._lock:
            expires_at = self._failed_endpoint_nodes.get(key)
            if expires_at is not None:
                if datetime.now(timezone.utc) >= expires_at:
                    self._failed_endpoint_nodes.pop(key, None)
                else:
                    return True

        # Check database
        try:
            if self.storage.is_route_node_failed(endpoint_id, safe_key):
                return True
        except Exception as e:
            logger.error(f"Failed to check node failure in DB: {e}")

        return False

    def endpoint_route_health(self, endpoint_id: int, hop_node_keys: list[str]) -> dict[str, Any]:
        clean_keys = tuple(str(item or "").strip() for item in hop_node_keys if str(item or "").strip())
        key = (int(endpoint_id or 0), clean_keys)
        failed = self._is_endpoint_route_failed(endpoint_id, list(clean_keys))
        failure_expires_at = ""
        with self._lock:
            expires_at = self._failed_endpoint_routes.get(key)
        if expires_at is not None:
            failure_expires_at = expires_at.isoformat()

        healthy_until = ""
        now = datetime.now(timezone.utc)
        with self._lock:
            healthy_exp = self._healthy_endpoint_routes.get(key)
            if healthy_exp is not None:
                if now >= healthy_exp:
                    self._healthy_endpoint_routes.pop(key, None)
                else:
                    healthy_until = healthy_exp.isoformat()
        return {
            "failed": failed,
            "failure_expires_at": failure_expires_at,
            "known_healthy": bool(healthy_until),
            "healthy_until": healthy_until,
        }

    def _get_multi_hop_lease(
        self,
        session_id: str,
        pool_id: int,
        endpoint_id: int,
        now: datetime,
    ) -> MultiHopLease | None:
        key = (str(session_id or "").strip(), int(pool_id), int(endpoint_id))
        with self._lock:
            lease = self._multi_hop_leases.get(key)
            if lease is None:
                return None
            if now >= lease.expires_at:
                self._multi_hop_leases.pop(key, None)
                return None
        return lease

    def _reuse_multi_hop_lease(
        self,
        lease: MultiHopLease,
        target_domain: str,
        live_instance_ids: set[str] | None = None,
    ) -> list[str] | None:
        del target_domain
        del live_instance_ids
        if not lease.hop_node_keys:
            return None
        for key in lease.hop_node_keys:
            proxy = self.storage.get_proxy_by_key(key)
            if proxy is None or not bool(proxy.get("available")):
                return None
        return list(lease.hop_node_keys)

    def _load_endpoint_hop_node_keys(self, endpoint_id: int, fallback_exit_node_key: str = "") -> list[str]:
        endpoint = self.storage.get_http_proxy_endpoint(endpoint_id)
        if endpoint is None:
            return [str(fallback_exit_node_key or "").strip()] if fallback_exit_node_key else []
        hop_keys: list[str] = []
        used_keys: set[str] = set()
        for hop in list(endpoint.get("hops") or []):
            pool_id = int(hop.get("pool_id") or 0)
            if pool_id <= 0:
                continue
            candidate = self._pick_pool_candidate(pool_id=pool_id, exclude_keys=used_keys, target_domain="")
            if candidate is None:
                continue
            key = str(candidate.get("normalized_key") or "").strip()
            if not key:
                continue
            hop_keys.append(key)
            used_keys.add(key)
        if fallback_exit_node_key:
            safe_exit = str(fallback_exit_node_key or "").strip()
            if hop_keys:
                hop_keys[-1] = safe_exit
            else:
                hop_keys = [safe_exit]
        return hop_keys

    def _build_route_signature(self, endpoint_id: int, hop_node_keys: list[str]) -> str:
        endpoint = self.storage.get_http_proxy_endpoint(endpoint_id) or {}
        pool_hops = list(endpoint.get("hops") or [])
        pool_parts = [f"pool-{int(item.get('pool_id') or 0)}" for item in pool_hops if int(item.get("pool_id") or 0) > 0]
        if pool_parts:
            return ">".join(pool_parts)
        return ">".join(hop_node_keys)

    def _proxy_to_node_summary(self, proxy: dict[str, Any] | None) -> dict[str, Any] | None:
        if proxy is None:
            return None
        return {
            "key": str(proxy.get("normalized_key") or ""),
            "name": str(proxy.get("name") or ""),
            "protocol": str(proxy.get("protocol") or ""),
            "host": str(proxy.get("host") or ""),
            "port": int(proxy.get("port") or 0),
            "healthy": bool(proxy.get("available")),
            "failure_count": int(proxy.get("fail_count") or 0),
            "egress_ip": str(proxy.get("resolved_ip") or ""),
            "latency_ms": proxy.get("latency_ms"),
        }


def health_manager_running(manager: HealthManager) -> bool:
    """Check if health manager is running."""
    return manager._running


def _parse_datetime(value: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
