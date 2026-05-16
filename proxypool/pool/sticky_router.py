"""Sticky session routing with P2C algorithm."""
from __future__ import annotations

import random
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from proxypool.pool.node_pool import NodeEntry, NodePool


@dataclass
class Lease:
    """Represents a sticky session lease."""
    account: str
    pool_id: int
    exit_node_key: str
    egress_ip: str
    expires_at: datetime
    last_accessed: datetime


@dataclass
class RouteResult:
    """Result of a routing decision."""
    front_node: NodeEntry
    exit_node: NodeEntry
    lease_created: bool = False


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
        
        # Lease table: (account, pool_id) -> Lease
        self._leases: dict[tuple[str, int], Lease] = {}
        # IP load stats: egress_ip -> count
        self._ip_load: dict[str, int] = {}
        self._lock = threading.RLock()
    
    def route(
        self,
        account: str,
        pool_id: int,
        target_domain: str = "",
    ) -> RouteResult | None:
        """Route a request, using sticky session if available."""
        now = datetime.now(timezone.utc)
        
        # Get healthy nodes
        front_nodes = self.front_pool.get_healthy_nodes()
        exit_nodes = self.exit_pool.get_healthy_nodes()
        
        if not front_nodes or not exit_nodes:
            return None
        
        # Try sticky session
        if account:
            lease = self._get_lease(account, pool_id, now)
            if lease:
                result = self._try_reuse_lease(lease, front_nodes, exit_nodes, now)
                if result:
                    return result
        
        # Fall back to P2C selection
        front = self._p2c_select(front_nodes, target_domain)
        exit_node = self._p2c_select(exit_nodes, target_domain)
        
        if not front or not exit_node:
            return None
        
        # Create lease if account provided
        lease_created = False
        if account:
            self._create_lease(account, pool_id, exit_node, now)
            lease_created = True
        
        return RouteResult(
            front_node=front,
            exit_node=exit_node,
            lease_created=lease_created,
        )
    
    def _get_lease(self, account: str, pool_id: int, now: datetime) -> Lease | None:
        """Get existing lease if valid."""
        key = (account, pool_id)
        lease = self._leases.get(key)
        
        if lease is None:
            return None
        
        # Check expiry
        if now >= lease.expires_at:
            self._remove_lease(account, pool_id)
            return None
        
        return lease
    
    def _try_reuse_lease(
        self,
        lease: Lease,
        front_nodes: list[NodeEntry],
        exit_nodes: list[NodeEntry],
        now: datetime,
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
        front = self._p2c_select(front_nodes, "")
        if front is None:
            return None
        
        # Update lease access time
        lease.last_accessed = now
        self._ip_load[lease.egress_ip] = self._ip_load.get(lease.egress_ip, 0)
        
        return RouteResult(front_node=front, exit_node=exit_node)
    
    def _find_same_ip_exit(self, egress_ip: str, exit_nodes: list[NodeEntry]) -> NodeEntry | None:
        """Find an exit node with the same egress IP."""
        candidates = [n for n in exit_nodes if n.egress_ip == egress_ip]
        if candidates:
            # Choose the one with lowest latency
            return min(candidates, key=lambda n: n.latency_ms or float('inf'))
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
    
    def _create_lease(self, account: str, pool_id: int, exit_node: NodeEntry, now: datetime) -> None:
        """Create a new sticky lease."""
        # Remove old lease if exists
        self._remove_lease(account, pool_id)
        
        egress_ip = exit_node.egress_ip or ""
        expires_at = now + timedelta(seconds=self.sticky_ttl_sec)
        
        lease = Lease(
            account=account,
            pool_id=pool_id,
            exit_node_key=exit_node.key,
            egress_ip=egress_ip,
            expires_at=expires_at,
            last_accessed=now,
        )
        
        key = (account, pool_id)
        self._leases[key] = lease
        
        # Update IP load stats
        self._ip_load[egress_ip] = self._ip_load.get(egress_ip, 0) + 1
    
    def _remove_lease(self, account: str, pool_id: int) -> None:
        """Remove a lease and update IP load stats."""
        key = (account, pool_id)
        lease = self._leases.pop(key, None)
        
        if lease and lease.egress_ip:
            count = self._ip_load.get(lease.egress_ip, 0)
            if count > 1:
                self._ip_load[lease.egress_ip] = count - 1
            else:
                self._ip_load.pop(lease.egress_ip, None)
    
    def cleanup_expired_leases(self) -> int:
        """Remove expired leases. Returns count of removed leases."""
        now = datetime.now(timezone.utc)
        removed = 0
        
        with self._lock:
            expired_keys = [
                key for key, lease in self._leases.items()
                if now >= lease.expires_at
            ]
            for key in expired_keys:
                account, pool_id = key
                self._remove_lease(account, pool_id)
                removed += 1
        
        return removed
    
    def get_leases(self, pool_id: int | None = None) -> list[dict[str, Any]]:
        """Get all leases, optionally filtered by pool_id."""
        with self._lock:
            result = []
            for (account, pid), lease in self._leases.items():
                if pool_id is not None and pid != pool_id:
                    continue
                result.append({
                    "account": account,
                    "pool_id": pid,
                    "exit_node_key": lease.exit_node_key,
                    "egress_ip": lease.egress_ip,
                    "expires_at": lease.expires_at.isoformat(),
                    "last_accessed": lease.last_accessed.isoformat(),
                })
            return result
