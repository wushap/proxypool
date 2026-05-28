"""Sticky session routing with P2C algorithm."""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from proxypool.pool.node_pool import NodeEntry, NodePool


@dataclass
class Lease:
    """Represents a sticky session lease."""

    session_id: str
    pool_id: int
    exit_node_key: str
    egress_ip: str
    expires_at: datetime
    last_accessed: datetime
    instance_id: str = ""


@dataclass
class RouteResult:
    """Result of a routing decision."""

    front_node: NodeEntry
    exit_node: NodeEntry
    lease_created: bool = False
    bound_instance_id: str = ""
    instance_reused: bool = False


class StickyRouter:
    """Routes requests with sticky session support and P2C algorithm."""

    def __init__(
        self,
        front_pool: NodePool,
        exit_pool: NodePool,
        sticky_ttl_sec: int = 3600,
    ) -> None:
        self.front_pool = front_pool
        self.exit_pool = exit_pool
        self.sticky_ttl_sec = sticky_ttl_sec

        # Lease table: (session_id, pool_id) -> Lease
        self._leases: dict[tuple[str, int], Lease] = {}
        # IP load stats: egress_ip -> count
        self._ip_load: dict[str, int] = {}
        self._lock = threading.RLock()

    def route(
        self,
        session_id: str,
        pool_id: int,
        target_domain: str = "",
        live_instance_ids: set[str] | None = None,
    ) -> RouteResult | None:
        """Route a request, using sticky session if available."""
        now = datetime.now(UTC)

        # Get healthy nodes
        front_nodes = self.front_pool.get_healthy_nodes()
        exit_nodes = self.exit_pool.get_healthy_nodes()

        if not front_nodes or not exit_nodes:
            return None

        # Try sticky session
        if session_id:
            lease = self._get_lease(session_id, pool_id, now)
            if lease:
                result = self._try_reuse_lease(
                    lease,
                    front_nodes,
                    exit_nodes,
                    now,
                    live_instance_ids=live_instance_ids,
                )
                if result:
                    return result

        # Fall back to P2C selection
        front, exit_node = self._select_distinct_pair(front_nodes, exit_nodes, target_domain)

        if not front or not exit_node:
            return None

        # Create lease if account provided
        lease_created = False
        if session_id:
            self._create_lease(session_id, pool_id, exit_node, now)
            lease_created = True

        return RouteResult(
            front_node=front,
            exit_node=exit_node,
            lease_created=lease_created,
        )

    def _get_lease(self, session_id: str, pool_id: int, now: datetime) -> Lease | None:
        """Get existing lease if valid."""
        key = (session_id, pool_id)
        with self._lock:
            lease = self._leases.get(key)

            if lease is None:
                return None

            # Check expiry
            if now >= lease.expires_at:
                self._remove_lease(session_id, pool_id)
                return None

        return lease

    def _try_reuse_lease(
        self,
        lease: Lease,
        front_nodes: list[NodeEntry],
        exit_nodes: list[NodeEntry],
        now: datetime,
        live_instance_ids: set[str] | None = None,
    ) -> RouteResult | None:
        """Try to reuse existing lease."""
        # Find the exit node in healthy nodes
        exit_node = None
        for node in exit_nodes:
            if node.key == lease.exit_node_key:
                exit_node = node
                break

        # Check if exit node still has same egress IP
        if exit_node and exit_node.egress_ip == lease.egress_ip:
            # Try same-IP rotation if exit node not found
            pass
        else:
            # Try to find another node with same egress IP
            exit_node = self._find_same_ip_exit(lease.egress_ip, exit_nodes)

        if exit_node is None:
            return None

        # Select a front node
        front = self._select_front_for_exit(front_nodes, exit_node)
        if front is None:
            return None

        # Update lease access time
        lease.last_accessed = now
        with self._lock:
            self._ip_load[lease.egress_ip] = self._ip_load.get(lease.egress_ip, 0)
        if lease.instance_id and lease.instance_id in set(live_instance_ids or set()):
            return RouteResult(
                front_node=front,
                exit_node=exit_node,
                lease_created=False,
                bound_instance_id=lease.instance_id,
                instance_reused=True,
            )

        return RouteResult(
            front_node=front,
            exit_node=exit_node,
            bound_instance_id=lease.instance_id,
        )

    def _select_distinct_pair(
        self,
        front_nodes: list[NodeEntry],
        exit_nodes: list[NodeEntry],
        target_domain: str,
    ) -> tuple[NodeEntry | None, NodeEntry | None]:
        exit_node = self._p2c_select(exit_nodes, target_domain)
        if exit_node is None:
            return None, None
        front = self._select_front_for_exit(front_nodes, exit_node)
        if front is not None:
            return front, exit_node

        remaining_exits = [node for node in exit_nodes if node.key != exit_node.key]
        fallback_exit = self._p2c_select(remaining_exits, target_domain)
        if fallback_exit is None:
            return None, None
        return self._select_front_for_exit(front_nodes, fallback_exit), fallback_exit

    def _select_front_for_exit(
        self, front_nodes: list[NodeEntry], exit_node: NodeEntry
    ) -> NodeEntry | None:
        candidates = [node for node in front_nodes if node.key != exit_node.key]
        return self._p2c_select(candidates, "")

    def _find_same_ip_exit(self, egress_ip: str, exit_nodes: list[NodeEntry]) -> NodeEntry | None:
        """Find an exit node with the same egress IP."""
        candidates = [n for n in exit_nodes if n.egress_ip == egress_ip]
        if candidates:
            # Choose the one with lowest latency
            return min(candidates, key=lambda n: n.latency_ms or float("inf"))
        return None

    def _p2c_select(self, nodes: list[NodeEntry], target_domain: str) -> NodeEntry | None:
        """P2C algorithm for node selection."""
        if not nodes:
            return None
        if len(nodes) == 1:
            return nodes[0]

        # Randomly select two candidates
        a, b = random.sample(nodes, 2)

        # Calculate scores
        score_a = self._calculate_score(a)
        score_b = self._calculate_score(b)

        return a if score_a <= score_b else b

    def _calculate_score(self, node: NodeEntry) -> float:
        """Calculate node score for P2C: (LeaseCount + 1) * Latency."""
        lease_count = self._ip_load.get(node.egress_ip, 0)
        latency = node.latency_ms

        if latency is None or latency <= 0:
            return float(lease_count)

        return (lease_count + 1) * latency

    def _create_lease(
        self, session_id: str, pool_id: int, exit_node: NodeEntry, now: datetime
    ) -> None:
        """Create a new sticky lease."""
        # Remove old lease if exists
        self._remove_lease(session_id, pool_id)

        egress_ip = exit_node.egress_ip or ""
        expires_at = now + timedelta(seconds=self.sticky_ttl_sec)

        lease = Lease(
            session_id=session_id,
            pool_id=pool_id,
            instance_id="",
            exit_node_key=exit_node.key,
            egress_ip=egress_ip,
            expires_at=expires_at,
            last_accessed=now,
        )

        key = (session_id, pool_id)
        with self._lock:
            self._leases[key] = lease

            # Update IP load stats
            self._ip_load[egress_ip] = self._ip_load.get(egress_ip, 0) + 1

    def _remove_lease(self, session_id: str, pool_id: int) -> None:
        """Remove a lease and update IP load stats."""
        key = (session_id, pool_id)
        with self._lock:
            lease = self._leases.pop(key, None)

            if lease and lease.egress_ip:
                count = self._ip_load.get(lease.egress_ip, 0)
                if count > 1:
                    self._ip_load[lease.egress_ip] = count - 1
                else:
                    self._ip_load.pop(lease.egress_ip, None)

    def bind_instance(self, session_id: str, pool_id: int, instance_id: str) -> None:
        with self._lock:
            lease = self._leases.get((session_id, pool_id))
            if lease is not None:
                lease.instance_id = str(instance_id or "")

    def delete_lease(self, session_id: str, pool_id: int) -> bool:
        with self._lock:
            exists = (session_id, pool_id) in self._leases
        self._remove_lease(session_id, pool_id)
        return exists

    def cleanup_expired_leases(self) -> int:
        """Remove expired leases. Returns count of removed leases."""
        now = datetime.now(UTC)
        removed = 0

        with self._lock:
            expired_keys = [key for key, lease in self._leases.items() if now >= lease.expires_at]
            for key in expired_keys:
                session_id, pool_id = key
                self._remove_lease(session_id, pool_id)
                removed += 1

        return removed

    def get_leases(self, pool_id: int | None = None) -> list[dict[str, Any]]:
        """Get all leases, optionally filtered by pool_id."""
        with self._lock:
            result = []
            for (session_id, pid), lease in self._leases.items():
                if pool_id is not None and pid != pool_id:
                    continue
                result.append(
                    {
                        "session_id": session_id,
                        "pool_id": pid,
                        "instance_id": lease.instance_id,
                        "exit_node_key": lease.exit_node_key,
                        "egress_ip": lease.egress_ip,
                        "expires_at": lease.expires_at.isoformat(),
                        "last_accessed": lease.last_accessed.isoformat(),
                    }
                )
            return result
