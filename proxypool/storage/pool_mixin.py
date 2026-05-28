from __future__ import annotations

import json
import sqlite3
from typing import Any

from proxypool.storage._helpers import (
    _loads_json_array,
    _loads_json_object,
    _normalize_pool_filters,
    _normalize_session_missing_action,
    _normalize_string_list,
    _pool_filters_to_list_kwargs,
    _utc_now,
)


class PoolMixin:
    """Pool CRUD methods for SQLiteProxyStorage."""

    def _pool_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["filters"] = _normalize_pool_filters(_loads_json_object(data.get("filters_json")))
        data["chain_enabled"] = bool(data.get("chain_enabled"))
        data["sticky_ttl_sec"] = int(data.get("sticky_ttl_sec") or 3600)
        data["session_missing_action"] = _normalize_session_missing_action(
            data.get("session_missing_action")
        )
        data["session_header_names"] = _loads_json_array(data.get("session_header_names_json"))
        data["session_query_param_names"] = _loads_json_array(
            data.get("session_query_param_names_json")
        )
        data["gateway_path_prefix"] = str(data.get("gateway_path_prefix") or "")
        data.pop("resin_subscription_id", None)
        data.pop("resin_platform_id", None)
        data.pop("filters_json", None)
        data.pop("session_header_names_json", None)
        data.pop("session_query_param_names_json", None)
        data["match_count"] = len(
            self.list_proxies_filtered(
                limit=20000, **_pool_filters_to_list_kwargs(data.get("filters") or {})
            )
        )
        return data

    def create_proxy_pool(
        self,
        name: str,
        filters: dict[str, Any] | None = None,
        listen: str = "0.0.0.0",
        inbound_type: str = "http",
        chain_enabled: bool = False,
        sticky_ttl_sec: int = 3600,
        session_missing_action: str = "RANDOM",
        session_header_names: list[str] | None = None,
        session_query_param_names: list[str] | None = None,
        gateway_path_prefix: str = "",
    ) -> dict[str, Any]:
        now = _utc_now()
        filters_json = json.dumps(
            _normalize_pool_filters(filters), ensure_ascii=False, separators=(",", ":")
        )
        safe_name = (str(name or "").strip() or "proxy-pool")[:120]
        safe_listen = str(listen or "0.0.0.0").strip() or "0.0.0.0"
        safe_type = str(inbound_type or "http").strip().lower() or "http"
        header_names_json = json.dumps(
            _normalize_string_list(session_header_names), ensure_ascii=False, separators=(",", ":")
        )
        query_names_json = json.dumps(
            _normalize_string_list(session_query_param_names),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        sticky_ttl = max(1, int(sticky_ttl_sec))
        missing_action = _normalize_session_missing_action(session_missing_action)
        safe_gateway_path_prefix = str(gateway_path_prefix or "").strip()[:200]
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO proxy_pools (
                        name, filters_json, listen, inbound_type,
                        chain_enabled, sticky_ttl_sec, session_missing_action,
                        session_header_names_json, session_query_param_names_json, gateway_path_prefix,
                        status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'stopped', ?, ?)
                    """,
                    (
                        safe_name,
                        filters_json,
                        safe_listen,
                        safe_type,
                        1 if chain_enabled else 0,
                        sticky_ttl,
                        missing_action,
                        header_names_json,
                        query_names_json,
                        safe_gateway_path_prefix,
                        now,
                        now,
                    ),
                )
                pool_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                row = conn.execute("SELECT * FROM proxy_pools WHERE id = ?", (pool_id,)).fetchone()
                conn.commit()
        if row is None:
            raise RuntimeError("failed to create proxy pool")
        return self._pool_row_to_dict(row)

    def update_proxy_pool(
        self,
        pool_id: int,
        name: str | None = None,
        filters: dict[str, Any] | None = None,
        listen: str | None = None,
        inbound_type: str | None = None,
        published_subscription_id: int | None = None,
        chain_enabled: bool | None = None,
        sticky_ttl_sec: int | None = None,
        session_missing_action: str | None = None,
        session_header_names: list[str] | None = None,
        session_query_param_names: list[str] | None = None,
        gateway_path_prefix: str | None = None,
    ) -> dict[str, Any]:
        updates: list[str] = []
        params: list[Any] = []
        if name is not None:
            updates.append("name = ?")
            params.append((str(name or "").strip() or "proxy-pool")[:120])
        if filters is not None:
            updates.append("filters_json = ?")
            params.append(
                json.dumps(
                    _normalize_pool_filters(filters), ensure_ascii=False, separators=(",", ":")
                )
            )
        if listen is not None:
            updates.append("listen = ?")
            params.append(str(listen or "0.0.0.0").strip() or "0.0.0.0")
        if inbound_type is not None:
            updates.append("inbound_type = ?")
            params.append(str(inbound_type or "http").strip().lower() or "http")
        if published_subscription_id is not None:
            updates.append("published_subscription_id = ?")
            params.append(int(published_subscription_id))
        if chain_enabled is not None:
            updates.append("chain_enabled = ?")
            params.append(1 if chain_enabled else 0)
        if sticky_ttl_sec is not None:
            updates.append("sticky_ttl_sec = ?")
            params.append(max(1, int(sticky_ttl_sec)))
        if session_missing_action is not None:
            updates.append("session_missing_action = ?")
            params.append(_normalize_session_missing_action(session_missing_action))
        if session_header_names is not None:
            updates.append("session_header_names_json = ?")
            params.append(
                json.dumps(
                    _normalize_string_list(session_header_names),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        if session_query_param_names is not None:
            updates.append("session_query_param_names_json = ?")
            params.append(
                json.dumps(
                    _normalize_string_list(session_query_param_names),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        if gateway_path_prefix is not None:
            updates.append("gateway_path_prefix = ?")
            params.append(str(gateway_path_prefix or "").strip()[:200])
        if not updates:
            return self.get_proxy_pool(pool_id) or {}
        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(int(pool_id))
        with self._write_lock, self._connect() as conn:
            conn.execute(
                f"UPDATE proxy_pools SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            row = conn.execute("SELECT * FROM proxy_pools WHERE id = ?", (int(pool_id),)).fetchone()
            conn.commit()
        if row is None:
            raise ValueError("proxy pool not found")
        return self._pool_row_to_dict(row)

    def delete_proxy_pool(self, pool_id: int) -> int:
        with self._write_lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM proxy_pools WHERE id = ?", (int(pool_id),))
            deleted = int(cur.rowcount or 0)
            conn.commit()
        return deleted

    def get_proxy_pool(self, pool_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM proxy_pools WHERE id = ? LIMIT 1", (int(pool_id),)
            ).fetchone()
        if row is None:
            return None
        return self._pool_row_to_dict(row)

    def list_proxy_pools(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM proxy_pools ORDER BY updated_at DESC, id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [self._pool_row_to_dict(row) for row in rows]

    def get_proxy_pool_by_gateway_prefix(self, path_prefix: str) -> dict[str, Any] | None:
        """Look up a pool by its gateway_path_prefix."""
        prefix = str(path_prefix or "").strip()
        if not prefix:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM proxy_pools WHERE gateway_path_prefix = ? LIMIT 1",
                (prefix,),
            ).fetchone()
        if row is None:
            return None
        return self._pool_row_to_dict(row)

    def list_proxy_pool_candidates(
        self,
        pool_id: int,
        limit: int = 500,
        exclude_keys: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        pool = self.get_proxy_pool(pool_id)
        if pool is None:
            raise ValueError("proxy pool not found")
        kwargs = _pool_filters_to_list_kwargs(pool.get("filters") or {})
        kwargs["limit"] = max(1, int(limit))
        kwargs["exclude_keys"] = exclude_keys
        return self.list_proxies_filtered(**kwargs)

    def update_proxy_pool_status(
        self,
        pool_id: int,
        status: str,
        last_error: str = "",
        last_synced_at: str | None = None,
    ) -> None:
        updates = ["status = ?", "last_error = ?", "updated_at = ?"]
        params: list[Any] = [
            str(status or "stopped")[:32],
            str(last_error or "")[:1000],
            _utc_now(),
        ]
        if last_synced_at is not None:
            updates.append("last_synced_at = ?")
            params.append(last_synced_at)
        params.append(int(pool_id))
        with self._write_lock, self._connect() as conn:
            conn.execute(
                f"UPDATE proxy_pools SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

    def list_proxy_pools_v2(self) -> list[dict[str, Any]]:
        """List all proxy chain pool configurations."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM proxy_pools_v2 ORDER BY name").fetchall()
            return [self._proxy_pool_v2_row_to_dict(row) for row in rows]

    def get_proxy_pool_v2(self, name: str) -> dict[str, Any] | None:
        """Get a proxy chain pool by name."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM proxy_pools_v2 WHERE name = ?",
                (name,),
            ).fetchone()
            if row is None:
                return None
            return self._proxy_pool_v2_row_to_dict(row)

    def upsert_proxy_pool_v2(
        self,
        name: str,
        pool_type: str,
        regex_filters: list[str],
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Create or update a proxy chain pool configuration."""
        now = _utc_now()
        filters_json = json.dumps(regex_filters, ensure_ascii=False)
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO proxy_pools_v2 (name, pool_type, regex_filters_json, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        pool_type = excluded.pool_type,
                        regex_filters_json = excluded.regex_filters_json,
                        enabled = excluded.enabled,
                        updated_at = excluded.updated_at
                    """,
                    (name, pool_type, filters_json, int(enabled), now, now),
                )
                conn.commit()
        return self.get_proxy_pool_v2(name) or {}

    def delete_proxy_pool_v2(self, name: str) -> int:
        """Delete a proxy chain pool configuration."""
        with self._write_lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM proxy_pools_v2 WHERE name = ?",
                (name,),
            )
            conn.commit()
            return cursor.rowcount

    def _proxy_pool_v2_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a proxy_pools_v2 row to dict."""
        data = dict(row)
        data["enabled"] = bool(data.get("enabled"))
        data["regex_filters"] = _loads_json_array(data.get("regex_filters_json"))
        data.pop("regex_filters_json", None)
        return data
