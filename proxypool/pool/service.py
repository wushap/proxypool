from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from proxypool.storage.sqlite import SQLiteProxyStorage


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProxyPoolService:
    """High-level proxy pool management orchestrating published subscriptions."""

    def __init__(
        self,
        storage: SQLiteProxyStorage,
    ) -> None:
        self.storage = storage

    def create_pool(
        self,
        name: str,
        filters: dict[str, Any] | None = None,
        listen: str = "0.0.0.0",
        inbound_type: str = "http",
    ) -> dict[str, Any]:
        pool = self.storage.create_proxy_pool(
            name=name,
            filters=filters,
            listen=listen,
            inbound_type=inbound_type,
        )
        return pool

    def update_pool(self, pool_id: int, **kwargs: Any) -> dict[str, Any]:
        return self.storage.update_proxy_pool(pool_id, **kwargs)

    def get_pool_by_name(self, name: str) -> dict[str, Any] | None:
        safe_name = str(name or "").strip()
        if not safe_name:
            return None
        for pool in self.storage.list_proxy_pools(limit=1000):
            if str(pool.get("name") or "") == safe_name:
                return self._enrich_pool(pool)
        return None

    def get_pool_chain_config(self, pool_id: int) -> dict[str, Any] | None:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            return None
        return self._enrich_pool(pool)

    def update_pool_chain_config(self, pool_id: int, **kwargs: Any) -> dict[str, Any]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        return self._enrich_pool(self.storage.update_proxy_pool(pool_id, **kwargs))

    def upsert_pool_session_rule(self, pool_id: int, url_prefix: str, headers: list[str] | None = None) -> dict[str, Any]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        return self.storage.upsert_pool_session_rule(pool_id=pool_id, url_prefix=url_prefix, headers=headers)

    def list_pool_session_rules(self, pool_id: int) -> list[dict[str, Any]]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        return self.storage.list_pool_session_rules(pool_id)

    def delete_pool_session_rule(self, pool_id: int, url_prefix: str) -> bool:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        return self.storage.delete_pool_session_rule(pool_id, url_prefix) > 0

    def list_pool_chain_leases(self, pool_id: int) -> list[dict[str, Any]]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        return self.storage.list_sticky_leases(pool_id=pool_id)

    def delete_pool_chain_lease(self, pool_id: int, session_id: str) -> bool:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        deleted = self.storage.delete_sticky_lease(session_id, pool_id)
        return deleted > 0

    def inherit_pool_chain_lease(self, pool_id: int, from_session_id: str, to_session_id: str) -> dict[str, Any]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        lease = self.storage.get_sticky_lease(from_session_id, pool_id)
        if lease is None:
            raise ValueError("source sticky lease not found")
        self.storage.upsert_sticky_lease(
            session_id=to_session_id,
            pool_id=pool_id,
            endpoint_id=int(lease.get("endpoint_id") or 0),
            instance_id=str(lease.get("instance_id") or ""),
            exit_node_key=str(lease["exit_node_key"]),
            egress_ip=str(lease["egress_ip"]),
            expires_at=str(lease["expires_at"]),
            last_accessed=str(lease["last_accessed"]),
        )
        inherited = self.storage.get_sticky_lease(to_session_id, pool_id)
        if inherited is None:
            raise RuntimeError("failed to inherit sticky lease")
        return inherited

    def get_pool(self, pool_id: int) -> dict[str, Any] | None:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            return None
        return self._enrich_pool(pool)

    def list_pools(self) -> list[dict[str, Any]]:
        pools = self.storage.list_proxy_pools()
        return [self._enrich_pool(p) for p in pools]

    def delete_pool(self, pool_id: int) -> bool:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            return False
        self._cleanup_published_subscription(pool)
        deleted = self.storage.delete_proxy_pool(pool_id)
        return deleted > 0

    def sync_pool(self, pool_id: int) -> dict[str, Any]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")

        pub_sub_id = pool.get("published_subscription_id")

        # Ensure published subscription exists
        if not pub_sub_id:
            pub_sub = self.storage.create_published_subscription(
                name=f"pool-{pool_id}",
                filters=pool.get("filters") or {},
                enabled=True,
            )
            pub_sub_id = int(pub_sub["id"])
            self.storage.update_proxy_pool(pool_id, published_subscription_id=pub_sub_id)
        else:
            self.storage.update_published_subscription(
                int(pub_sub_id),
                filters=pool.get("filters") or {},
            )

        base_url = f"http://127.0.0.1:8080"
        pub_sub_url = f"{base_url}/api/published-subscriptions/{pub_sub_id}/subscription"
        self.storage.update_proxy_pool_status(pool_id, "running", last_synced_at=_utc_now())
        latest = self.storage.get_proxy_pool(pool_id) or {}
        latest["export_url"] = pub_sub_url
        return self._enrich_pool(latest)

    def start_pool(self, pool_id: int) -> dict[str, Any]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        self.storage.update_proxy_pool_status(pool_id, "running")
        return self._enrich_pool(self.storage.get_proxy_pool(pool_id) or {})

    def stop_pool(self, pool_id: int) -> dict[str, Any]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        self.storage.update_proxy_pool_status(pool_id, "stopped")
        return self._enrich_pool(self.storage.get_proxy_pool(pool_id) or {})

    def _cleanup_published_subscription(self, pool: dict[str, Any]) -> None:
        pub_sub_id = pool.get("published_subscription_id")
        if pub_sub_id:
            try:
                self.storage.delete_published_subscription(int(pub_sub_id))
            except Exception:
                pass

    def _enrich_pool(self, pool: dict[str, Any]) -> dict[str, Any]:
        out = dict(pool)
        pub_sub_id = pool.get("published_subscription_id")

        if pub_sub_id:
            out["export_url"] = f"/api/published-subscriptions/{pub_sub_id}/subscription"

        return out
