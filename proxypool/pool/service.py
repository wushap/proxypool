from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from proxypool.backend.resin_client import ResinClient
from proxypool.backend.resin_manager import ResinBackendManager
from proxypool.storage.sqlite import SQLiteProxyStorage


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProxyPoolService:
    """High-level proxy pool management orchestrating published subscriptions and Resin."""

    def __init__(
        self,
        storage: SQLiteProxyStorage,
        resin_manager: ResinBackendManager,
        resin_client: ResinClient,
    ) -> None:
        self.storage = storage
        self.resin_manager = resin_manager
        self.resin_client = resin_client

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
        self._cleanup_resin_resources(pool)
        self._cleanup_published_subscription(pool)
        deleted = self.storage.delete_proxy_pool(pool_id)
        return deleted > 0

    def sync_pool(self, pool_id: int) -> dict[str, Any]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")

        pub_sub_id = pool.get("published_subscription_id")
        resin_sub_id = str(pool.get("resin_subscription_id") or "")
        resin_platform_id = str(pool.get("resin_platform_id") or "")

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

        # Ensure Resin subscription exists
        if not resin_sub_id:
            result = self.resin_client.create_subscription(
                name=f"pool-{pool_id}",
                url=pub_sub_url,
                format="uri-lines",
                interval_sec=60,
            )
            resin_sub_id = str(result.get("id") or result.get("subscription_id") or "")
            if resin_sub_id:
                self.storage.update_proxy_pool(pool_id, resin_subscription_id=resin_sub_id)
        else:
            self.resin_client.refresh_subscription(resin_sub_id)

        # Ensure Resin platform exists
        if not resin_platform_id:
            result = self.resin_client.create_platform(
                name=f"pool-{pool_id}",
                subscription_ids=[resin_sub_id] if resin_sub_id else [],
                allocation_policy="BALANCED",
            )
            resin_platform_id = str(result.get("id") or result.get("platform_id") or "")
            if resin_platform_id:
                self.storage.update_proxy_pool(pool_id, resin_platform_id=resin_platform_id)

        self.storage.update_proxy_pool_status(pool_id, "running", last_synced_at=_utc_now())
        return self._enrich_pool(self.storage.get_proxy_pool(pool_id) or {})

    def start_pool(self, pool_id: int) -> dict[str, Any]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")

        if not pool.get("resin_subscription_id") or not pool.get("resin_platform_id"):
            return self.sync_pool(pool_id)

        self.storage.update_proxy_pool_status(pool_id, "running")
        return self._enrich_pool(self.storage.get_proxy_pool(pool_id) or {})

    def stop_pool(self, pool_id: int) -> dict[str, Any]:
        pool = self.storage.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        self.storage.update_proxy_pool_status(pool_id, "stopped")
        return self._enrich_pool(self.storage.get_proxy_pool(pool_id) or {})

    def _cleanup_resin_resources(self, pool: dict[str, Any]) -> None:
        resin_sub_id = str(pool.get("resin_subscription_id") or "")
        resin_platform_id = str(pool.get("resin_platform_id") or "")
        if resin_platform_id:
            try:
                self.resin_client.delete_platform(resin_platform_id)
            except Exception:
                pass
        if resin_sub_id:
            try:
                self.resin_client.delete_subscription(resin_sub_id)
            except Exception:
                pass

    def _cleanup_published_subscription(self, pool: dict[str, Any]) -> None:
        pub_sub_id = pool.get("published_subscription_id")
        if pub_sub_id:
            try:
                self.storage.delete_published_subscription(int(pub_sub_id))
            except Exception:
                pass

    def _enrich_pool(self, pool: dict[str, Any]) -> dict[str, Any]:
        out = dict(pool)
        resin_sub_id = str(pool.get("resin_subscription_id") or "")
        resin_platform_id = str(pool.get("resin_platform_id") or "")
        pub_sub_id = pool.get("published_subscription_id")

        if pub_sub_id:
            out["export_url"] = f"/api/published-subscriptions/{pub_sub_id}/subscription"

        out["resin_running"] = self.resin_manager.is_running()

        if resin_platform_id and self.resin_manager.is_running():
            try:
                platform = self.resin_client.get_platform(resin_platform_id)
                out["resin_platform"] = platform
            except Exception:
                out["resin_platform"] = None
        else:
            out["resin_platform"] = None

        if self.resin_manager.is_running():
            try:
                info = self.resin_client.get_system_info()
                out["resin_node_count"] = info.get("node_count", 0)
            except Exception:
                out["resin_node_count"] = 0
        else:
            out["resin_node_count"] = 0

        return out
