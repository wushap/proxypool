from __future__ import annotations

import json
import sqlite3
from typing import Any

from proxypool.storage._helpers import (
    _filters_to_proxy_list_kwargs,
    _filters_to_subscription_link_kwargs,
    _loads_json_object,
    _normalize_published_subscription_filters,
    _normalize_published_subscription_format,
    _utc_now,
)


class SubscriptionMixin:
    """Subscription CRUD methods for SQLiteProxyStorage."""

    def _subscription_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["enabled"] = bool(data.get("enabled"))
        return data

    def _published_subscription_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["enabled"] = bool(data.get("enabled"))
        data["format"] = _normalize_published_subscription_format(data.get("format"))
        filters = _normalize_published_subscription_filters(
            _loads_json_object(data.get("filters_json"))
        )
        data["filters"] = filters
        data["match_count"] = len(
            self.list_proxies_filtered(limit=20000, **_filters_to_proxy_list_kwargs(filters))
        )
        data.pop("filters_json", None)
        return data

    def get_subscription(self, subscription_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE id = ? LIMIT 1",
                (int(subscription_id),),
            ).fetchone()
        if row is None:
            return None
        return self._subscription_row_to_dict(row)

    def get_subscription_by_url(self, url: str) -> dict[str, Any] | None:
        safe_url = str(url or "").strip()
        if not safe_url:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE url = ? LIMIT 1",
                (safe_url,),
            ).fetchone()
        if row is None:
            return None
        return self._subscription_row_to_dict(row)

    def create_subscription(
        self,
        name: str,
        url: str,
        enabled: bool = True,
        update_proxy_key: str = "",
    ) -> dict[str, Any]:
        safe_url = str(url or "").strip()
        if not safe_url:
            raise ValueError("subscription url is empty")
        now = _utc_now()
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO subscriptions (name, url, update_proxy_key, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        (str(name or "").strip() or "subscription")[:120],
                        safe_url[:1000],
                        str(update_proxy_key or "").strip()[:64],
                        1 if enabled else 0,
                        now,
                        now,
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM subscriptions WHERE id = last_insert_rowid()"
                ).fetchone()
                conn.commit()
        if row is None:
            raise RuntimeError("failed to create subscription")
        return self._subscription_row_to_dict(row)

    def update_subscription(
        self,
        subscription_id: int,
        name: str | None = None,
        url: str | None = None,
        update_proxy_key: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        updates: list[str] = []
        params: list[Any] = []
        if name is not None:
            updates.append("name = ?")
            params.append((str(name or "").strip() or "subscription")[:120])
        if url is not None:
            safe_url = str(url or "").strip()
            if not safe_url:
                raise ValueError("subscription url is empty")
            updates.append("url = ?")
            params.append(safe_url[:1000])
        if update_proxy_key is not None:
            updates.append("update_proxy_key = ?")
            params.append(str(update_proxy_key or "").strip()[:64])
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(int(subscription_id))

        with self._write_lock, self._connect() as conn:
            conn.execute(
                f"UPDATE subscriptions SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE id = ? LIMIT 1",
                (int(subscription_id),),
            ).fetchone()
            conn.commit()
        if row is None:
            raise ValueError("subscription not found")
        return self._subscription_row_to_dict(row)

    def delete_subscription(self, subscription_id: int) -> int:
        with self._write_lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM subscriptions WHERE id = ?", (int(subscription_id),))
            conn.commit()
            return int(cur.rowcount)

    def delete_unavailable_subscriptions(self, include_disabled: bool = False) -> int:
        where = "last_status = 'failed'"
        if include_disabled:
            where = f"({where} OR enabled = 0)"
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(f"DELETE FROM subscriptions WHERE {where}")
            conn.commit()
            return int(cur.rowcount)

    def list_enabled_subscriptions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM subscriptions
                WHERE enabled = 1
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        return [self._subscription_row_to_dict(row) for row in rows]

    def mark_subscription_result(
        self,
        subscription_id: int,
        status: str,
        error: str = "",
        parsed: int = 0,
        inserted: int = 0,
        updated: int = 0,
        invalid: int = 0,
        deduped: int = 0,
    ) -> None:
        now = _utc_now()
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE subscriptions
                    SET last_status = ?, last_error = ?, last_parsed = ?, last_inserted = ?, last_updated = ?,
                        last_invalid = ?, last_deduped = ?, last_fetched_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        str(status or "")[:32],
                        str(error or "")[:500],
                        max(0, int(parsed)),
                        max(0, int(inserted)),
                        max(0, int(updated)),
                        max(0, int(invalid)),
                        max(0, int(deduped)),
                        now,
                        now,
                        int(subscription_id),
                    ),
                )
                conn.commit()

    def list_subscriptions(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM subscriptions
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [self._subscription_row_to_dict(row) for row in rows]

    def list_published_subscriptions(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM published_subscriptions
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [self._published_subscription_row_to_dict(row) for row in rows]

    def get_published_subscription(self, subscription_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM published_subscriptions WHERE id = ? LIMIT 1",
                (int(subscription_id),),
            ).fetchone()
        if row is None:
            return None
        return self._published_subscription_row_to_dict(row)

    def create_published_subscription(
        self,
        name: str,
        filters: dict[str, Any] | None = None,
        enabled: bool = True,
        format: str = "raw",
    ) -> dict[str, Any]:
        now = _utc_now()
        filters_json = json.dumps(
            _normalize_published_subscription_filters(filters),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        output_format = _normalize_published_subscription_format(format)
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO published_subscriptions (name, filters_json, format, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        (str(name or "").strip() or "published-subscription")[:120],
                        filters_json,
                        output_format,
                        1 if enabled else 0,
                        now,
                        now,
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM published_subscriptions WHERE id = last_insert_rowid()"
                ).fetchone()
                conn.commit()
        if row is None:
            raise RuntimeError("failed to create published subscription")
        return self._published_subscription_row_to_dict(row)

    def update_published_subscription(
        self,
        subscription_id: int,
        name: str | None = None,
        filters: dict[str, Any] | None = None,
        enabled: bool | None = None,
        format: str | None = None,
    ) -> dict[str, Any]:
        updates: list[str] = []
        params: list[Any] = []
        if name is not None:
            updates.append("name = ?")
            params.append((str(name or "").strip() or "published-subscription")[:120])
        if filters is not None:
            updates.append("filters_json = ?")
            params.append(
                json.dumps(
                    _normalize_published_subscription_filters(filters),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        if format is not None:
            updates.append("format = ?")
            params.append(_normalize_published_subscription_format(format))
        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(int(subscription_id))

        with self._write_lock, self._connect() as conn:
            conn.execute(
                f"UPDATE published_subscriptions SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            row = conn.execute(
                "SELECT * FROM published_subscriptions WHERE id = ? LIMIT 1",
                (int(subscription_id),),
            ).fetchone()
            conn.commit()
        if row is None:
            raise ValueError("published subscription not found")
        return self._published_subscription_row_to_dict(row)

    def delete_published_subscription(self, subscription_id: int) -> int:
        with self._write_lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "DELETE FROM published_subscriptions WHERE id = ?", (int(subscription_id),)
                )
                conn.commit()
                return int(cur.rowcount)

    def get_published_subscription_links(
        self, subscription_id: int, limit: int = 5000
    ) -> list[str]:
        item = self.get_published_subscription(subscription_id)
        if item is None:
            raise ValueError("published subscription not found")
        return self.get_subscription_links(
            limit=limit, **_filters_to_subscription_link_kwargs(item.get("filters") or {})
        )

    def get_published_subscription_proxies(
        self, subscription_id: int, limit: int = 5000
    ) -> list[dict[str, Any]]:
        item = self.get_published_subscription(subscription_id)
        if item is None:
            raise ValueError("published subscription not found")
        return self.list_proxies_filtered(
            limit=limit, **_filters_to_proxy_list_kwargs(item.get("filters") or {})
        )
