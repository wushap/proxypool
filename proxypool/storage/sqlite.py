from __future__ import annotations

import base64
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlsplit, urlunsplit

from proxypool.models import ProxyNode


class SQLiteProxyStorage:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _init_db(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS proxies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocol TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            raw_link TEXT NOT NULL,
            normalized_key TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL DEFAULT '',
            extra_json TEXT NOT NULL DEFAULT '{}',
            available INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER,
            fail_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL DEFAULT '',
            resolved_ip TEXT NOT NULL DEFAULT '',
            country TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            geo_updated_at TEXT,
            ip_purity_score REAL,
            ip_purity_level TEXT NOT NULL DEFAULT '',
            ip_purity_checked_at TEXT,
            openai_unlocked INTEGER,
            openai_status TEXT NOT NULL DEFAULT '',
            openai_checked_at TEXT,
            fallback_front_keys_json TEXT NOT NULL DEFAULT '[]',
            last_checked_at TEXT,
            last_seen_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_proxies_protocol ON proxies(protocol);
        CREATE INDEX IF NOT EXISTS idx_proxies_available ON proxies(available);
        CREATE TABLE IF NOT EXISTS backend_process_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backend TEXT NOT NULL,
            action TEXT NOT NULL,
            pid INTEGER NOT NULL DEFAULT -1,
            result TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '',
            config_file TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_backend_events_created ON backend_process_events(created_at DESC);
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            update_proxy_key TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            last_status TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            last_parsed INTEGER NOT NULL DEFAULT 0,
            last_inserted INTEGER NOT NULL DEFAULT 0,
            last_updated INTEGER NOT NULL DEFAULT 0,
            last_invalid INTEGER NOT NULL DEFAULT 0,
            last_deduped INTEGER NOT NULL DEFAULT 0,
            last_fetched_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_subscriptions_enabled ON subscriptions(enabled);
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        """
        with self._connect() as conn:
            conn.executescript(sql)
            self._ensure_columns(conn)
            conn.commit()

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(proxies)").fetchall()
        }
        if "fail_count" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN fail_count INTEGER NOT NULL DEFAULT 0")
        if "last_error" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN last_error TEXT NOT NULL DEFAULT ''")
        if "resolved_ip" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN resolved_ip TEXT NOT NULL DEFAULT ''")
        if "country" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN country TEXT NOT NULL DEFAULT ''")
        if "city" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN city TEXT NOT NULL DEFAULT ''")
        if "geo_updated_at" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN geo_updated_at TEXT")
        if "ip_purity_score" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN ip_purity_score REAL")
        if "ip_purity_level" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN ip_purity_level TEXT NOT NULL DEFAULT ''")
        if "ip_purity_checked_at" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN ip_purity_checked_at TEXT")
        if "openai_unlocked" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN openai_unlocked INTEGER")
        if "openai_status" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN openai_status TEXT NOT NULL DEFAULT ''")
        if "openai_checked_at" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN openai_checked_at TEXT")
        if "fallback_front_keys_json" not in columns:
            conn.execute("ALTER TABLE proxies ADD COLUMN fallback_front_keys_json TEXT NOT NULL DEFAULT '[]'")

        sub_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(subscriptions)").fetchall()
        }
        if "update_proxy_key" not in sub_columns:
            conn.execute("ALTER TABLE subscriptions ADD COLUMN update_proxy_key TEXT NOT NULL DEFAULT ''")

    def upsert_proxy(self, node: ProxyNode, source: str = "") -> str:
        now = _utc_now()
        key = node.normalized_key()
        extra_json = json.dumps(node.extra, ensure_ascii=False, separators=(",", ":"))

        with self._write_lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id FROM proxies WHERE normalized_key = ?",
                    (key,),
                ).fetchone()

                if row is None:
                    conn.execute(
                        """
                        INSERT INTO proxies (
                            protocol, host, port, name, raw_link, normalized_key,
                            source, extra_json, last_seen_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            node.protocol,
                            node.host,
                            node.port,
                            node.name,
                            node.raw_link,
                            key,
                            source,
                            extra_json,
                            now,
                            now,
                            now,
                        ),
                    )
                    conn.commit()
                    return "inserted"

                conn.execute(
                    """
                    UPDATE proxies
                    SET name = ?, raw_link = ?, source = ?, extra_json = ?, last_seen_at = ?, updated_at = ?
                    WHERE normalized_key = ?
                    """,
                    (
                        node.name,
                        node.raw_link,
                        source,
                        extra_json,
                        now,
                        now,
                        key,
                    ),
                )
                conn.commit()
                return "updated"

    def list_proxies(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.list_proxies_filtered(limit=limit)

    def list_proxies_filtered(
        self,
        limit: int = 100,
        offset: int = 0,
        protocol: str | None = None,
        available: bool | None = None,
        source_keyword: str | None = None,
        geo_filter: str | None = None,
        geo_country: str | None = None,
        geo_location: str | None = None,
        openai_filter: str | None = None,
        ip_purity_filter: str | None = None,
        fallback_front_filter: str | None = None,
        sort_by: str = "latency",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []

        if protocol:
            where.append("protocol = ?")
            params.append(protocol)
        if available is not None:
            where.append("available = ?")
            params.append(1 if available else 0)
        if source_keyword:
            source_text = str(source_keyword).strip()
            if source_text == "-":
                where.append("source = ''")
            else:
                where.append("source LIKE ?")
                params.append(f"%{source_text}%")
        if geo_filter == "has":
            where.append("(country <> '' OR city <> '')")
        elif geo_filter == "none":
            where.append("(country = '' AND city = '')")
        if geo_country:
            country_text = str(geo_country).strip()
            if country_text == "-":
                where.append("country = ''")
            else:
                where.append("country = ?")
                params.append(country_text)
        if geo_location:
            text = str(geo_location).strip()
            if ":" in text:
                country, city = text.split(":", 1)
                c = country.strip()
                ci = city.strip()
                if c and c != "-":
                    where.append("country = ?")
                    params.append(c)
                elif c == "-":
                    where.append("country = ''")
                if ci and ci != "-":
                    where.append("city = ?")
                    params.append(ci)
                elif ci == "-":
                    where.append("city = ''")
            else:
                where.append("(country = ? OR city = ?)")
                params.extend([text, text])
        if openai_filter == "unlocked":
            where.append("openai_unlocked = 1")
        elif openai_filter == "blocked":
            where.append("openai_unlocked = 0")
        elif openai_filter == "unchecked":
            where.append("openai_unlocked IS NULL")
        if ip_purity_filter == "checked":
            where.append("ip_purity_checked_at IS NOT NULL")
        elif ip_purity_filter == "unchecked":
            where.append("ip_purity_checked_at IS NULL")
        elif ip_purity_filter == "residential":
            where.append("ip_purity_level = '家宽'")
        elif ip_purity_filter == "non_residential":
            where.append("ip_purity_level = '非家宽'")
        elif ip_purity_filter == "unknown":
            where.append("ip_purity_level = '未知'")
        if fallback_front_filter == "has":
            where.append("fallback_front_keys_json <> '[]'")
        elif fallback_front_filter == "none":
            where.append("fallback_front_keys_json = '[]'")

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        params.extend([limit, offset])
        norm_order = "DESC" if str(sort_order).lower() == "desc" else "ASC"
        if str(sort_by).lower() == "latency":
            order_clause = f"CASE WHEN latency_ms IS NULL THEN 1 ELSE 0 END ASC, latency_ms {norm_order}, updated_at DESC"
        else:
            order_clause = "updated_at DESC"

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM proxies
                {where_clause}
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def count_by_protocol(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT protocol, COUNT(*) AS cnt FROM proxies GROUP BY protocol ORDER BY cnt DESC"
            ).fetchall()
        return {str(row["protocol"]): int(row["cnt"]) for row in rows}

    def get_candidates_for_test(
        self,
        limit: int = 200,
        only_unchecked: bool = False,
        only_available: bool = False,
        only_unavailable: bool = False,
        min_last_checked_age_hours: int = 0,
        protocols: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []

        if only_unchecked:
            where.append("last_checked_at IS NULL")
        if only_available:
            where.append("available = 1")
        if only_unavailable:
            where.append("available = 0")
        if not only_unchecked:
            min_age_hours = max(0, int(min_last_checked_age_hours or 0))
            if min_age_hours > 0:
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=min_age_hours)).isoformat()
                where.append("last_checked_at IS NOT NULL")
                where.append("last_checked_at <= ?")
                params.append(cutoff)
        if protocols:
            placeholders = ",".join("?" for _ in protocols)
            where.append(f"protocol IN ({placeholders})")
            params.extend(protocols)

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect() as conn:
            sql = f"""
            SELECT * FROM proxies
            {where_clause}
            ORDER BY
                CASE WHEN last_checked_at IS NULL THEN 0 ELSE 1 END ASC,
                last_checked_at ASC,
                fail_count ASC,
                updated_at DESC
            """
            if int(limit) > 0:
                sql += "\nLIMIT ?"
                params.append(int(limit))
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update_test_result(
        self,
        normalized_key: str,
        available: bool,
        latency_ms: int | None,
        openai_unlocked: bool | None = None,
        openai_status: str = "",
        fallback_front_keys: list[str] | None = None,
        error: str = "",
    ) -> None:
        now = _utc_now()
        openai_val = None if openai_unlocked is None else (1 if openai_unlocked else 0)
        fallback_keys_json = "[]"
        if fallback_front_keys:
            clean = [str(key).strip() for key in fallback_front_keys if str(key).strip()]
            if clean:
                fallback_keys_json = json.dumps(clean, ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            with self._connect() as conn:
                if available:
                    conn.execute(
                        """
                        UPDATE proxies
                        SET available = 1, latency_ms = ?, last_checked_at = ?, last_error = '', fail_count = 0,
                            openai_unlocked = ?, openai_status = ?, openai_checked_at = ?, fallback_front_keys_json = ?, updated_at = ?
                        WHERE normalized_key = ?
                        """,
                        (latency_ms, now, openai_val, openai_status[:160], now, fallback_keys_json, now, normalized_key),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE proxies
                        SET available = 0, latency_ms = NULL, last_checked_at = ?, last_error = ?,
                            fail_count = fail_count + 1, openai_unlocked = ?, openai_status = ?, openai_checked_at = ?,
                            fallback_front_keys_json = ?, updated_at = ?
                        WHERE normalized_key = ?
                        """,
                        (now, error[:1000], openai_val, openai_status[:160], now, fallback_keys_json, now, normalized_key),
                    )
                conn.commit()

    def get_proxies_by_keys(self, normalized_keys: list[str]) -> list[dict[str, Any]]:
        keys = [str(key).strip() for key in normalized_keys if str(key).strip()]
        if not keys:
            return []
        uniq_keys: list[str] = []
        seen: set[str] = set()
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            uniq_keys.append(key)

        placeholders = ",".join("?" for _ in uniq_keys)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM proxies WHERE normalized_key IN ({placeholders})",
                uniq_keys,
            ).fetchall()
        by_key = {str(row["normalized_key"]): self._row_to_dict(row) for row in rows}
        return [by_key[key] for key in uniq_keys if key in by_key]

    def update_openai_result(
        self,
        normalized_key: str,
        openai_unlocked: bool | None,
        openai_status: str = "",
    ) -> None:
        now = _utc_now()
        openai_val = None if openai_unlocked is None else (1 if openai_unlocked else 0)
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE proxies
                    SET openai_unlocked = ?, openai_status = ?, openai_checked_at = ?
                    WHERE normalized_key = ?
                    """,
                    (openai_val, openai_status[:160], now, normalized_key),
                )
                conn.commit()

    def delete_stale_unavailable(self, max_fail_count: int = 20) -> int:
        with self._write_lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM proxies WHERE available = 0 AND fail_count >= ?",
                    (max_fail_count,),
                )
                conn.commit()
                return int(cursor.rowcount)

    def delete_unavailable(self) -> int:
        with self._write_lock:
            with self._connect() as conn:
                cursor = conn.execute("DELETE FROM proxies WHERE available = 0")
                conn.commit()
                return int(cursor.rowcount)

    def get_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM proxies").fetchone()[0])
            available = int(conn.execute("SELECT COUNT(*) FROM proxies WHERE available = 1").fetchone()[0])
            checked = int(
                conn.execute("SELECT COUNT(*) FROM proxies WHERE last_checked_at IS NOT NULL").fetchone()[0]
            )
            avg_latency_row = conn.execute(
                "SELECT AVG(latency_ms) FROM proxies WHERE available = 1 AND latency_ms IS NOT NULL"
            ).fetchone()
            avg_latency_ms = int(avg_latency_row[0]) if avg_latency_row and avg_latency_row[0] else None

        return {
            "total": total,
            "available": available,
            "checked": checked,
            "availability_rate": round((available / total) * 100, 2) if total else 0.0,
            "avg_latency_ms": avg_latency_ms,
            "by_protocol": self.count_by_protocol(),
        }

    def get_proxy_by_key(self, normalized_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM proxies WHERE normalized_key = ? LIMIT 1",
                (normalized_key,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def update_geo(
        self,
        normalized_key: str,
        resolved_ip: str,
        country: str = "",
        city: str = "",
    ) -> None:
        now = _utc_now()
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE proxies
                    SET resolved_ip = ?, country = ?, city = ?, geo_updated_at = ?, updated_at = ?
                    WHERE normalized_key = ?
                    """,
                    (resolved_ip, country, city, now, now, normalized_key),
                )
                conn.commit()

    def list_geo_candidates(
        self,
        limit: int = 200,
        only_available: bool = False,
        only_tested: bool = False,
    ) -> list[dict[str, Any]]:
        norm_limit = max(0, int(limit))
        where: list[str] = ["(resolved_ip = '' OR country = '' OR city = '' OR ip_purity_checked_at IS NULL)"]
        if only_available:
            where.append("available = 1")
        if only_tested:
            where.append("last_checked_at IS NOT NULL")
        where_clause = " AND ".join(where)
        with self._connect() as conn:
            sql = """
            SELECT *
            FROM proxies
            WHERE {where_clause}
            ORDER BY updated_at DESC
            """.format(where_clause=where_clause)
            params: tuple[Any, ...] = ()
            if norm_limit > 0:
                sql += "\nLIMIT ?"
                params = (norm_limit,)
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def list_ip_purity_candidates(
        self,
        limit: int = 0,
        only_unchecked: bool = False,
        only_available: bool = False,
        only_tested: bool = False,
    ) -> list[dict[str, Any]]:
        norm_limit = max(0, int(limit))
        where_items: list[str] = []
        if only_unchecked:
            where_items.append("ip_purity_checked_at IS NULL")
        if only_available:
            where_items.append("available = 1")
        if only_tested:
            where_items.append("last_checked_at IS NOT NULL")
        where = f"WHERE {' AND '.join(where_items)}" if where_items else ""
        with self._connect() as conn:
            sql = f"""
            SELECT *
            FROM proxies
            {where}
            ORDER BY updated_at DESC
            """
            params: tuple[Any, ...] = ()
            if norm_limit > 0:
                sql += "\nLIMIT ?"
                params = (norm_limit,)
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update_ip_purity(
        self,
        normalized_key: str,
        score: float | None,
        level: str = "",
    ) -> None:
        now = _utc_now()
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE proxies
                    SET ip_purity_score = ?, ip_purity_level = ?, ip_purity_checked_at = ?, updated_at = ?
                    WHERE normalized_key = ?
                    """,
                    (
                        None if score is None else float(score),
                        str(level or "")[:64],
                        now,
                        now,
                        normalized_key,
                    ),
                )
                conn.commit()

    def record_backend_process_event(
        self,
        backend: str,
        action: str,
        pid: int,
        result: str,
        detail: str = "",
        config_file: str = "",
    ) -> None:
        now = _utc_now()
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO backend_process_events (
                        backend, action, pid, result, detail, config_file, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(backend or "")[:32],
                        str(action or "")[:32],
                        int(pid),
                        str(result or "")[:32],
                        str(detail or "")[:1000],
                        str(config_file or "")[:300],
                        now,
                    ),
                )
                conn.commit()

    def list_backend_process_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, backend, action, pid, result, detail, config_file, created_at
                FROM backend_process_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [dict(row) for row in rows]

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

    def get_app_setting(self, key: str, default: str = "") -> str:
        safe_key = str(key or "").strip()
        if not safe_key:
            return str(default or "")
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM app_settings WHERE key = ? LIMIT 1", (safe_key,)).fetchone()
        if row is None:
            return str(default or "")
        return str(row["value"] or "")

    def set_app_setting(self, key: str, value: str) -> None:
        safe_key = str(key or "").strip()
        if not safe_key:
            raise ValueError("setting key is empty")
        now = _utc_now()
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (safe_key, str(value or ""), now),
                )
                conn.commit()

    def get_subscription_update_proxy_key(self) -> str:
        return self.get_app_setting("subscription_update_proxy_key", "")

    def set_subscription_update_proxy_key(self, normalized_key: str) -> None:
        self.set_app_setting("subscription_update_proxy_key", str(normalized_key or "").strip()[:64])

    def get_backend_default_port_range(self) -> dict[str, int]:
        start_raw = self.get_app_setting("backend_default_port_start", "1081")
        end_raw = self.get_app_setting("backend_default_port_end", "1180")
        try:
            start = int(start_raw)
        except Exception:
            start = 1081
        try:
            end = int(end_raw)
        except Exception:
            end = 1180
        start = max(1, min(65535, start))
        end = max(1, min(65535, end))
        if start > end:
            start, end = end, start
        return {"start": start, "end": end}

    def set_backend_default_port_range(self, start: int, end: int) -> dict[str, int]:
        safe_start = max(1, min(65535, int(start)))
        safe_end = max(1, min(65535, int(end)))
        if safe_start > safe_end:
            raise ValueError("invalid port range: start must be <= end")
        self.set_app_setting("backend_default_port_start", str(safe_start))
        self.set_app_setting("backend_default_port_end", str(safe_end))
        return {"start": safe_start, "end": safe_end}

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

        with self._write_lock:
            with self._connect() as conn:
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
        with self._write_lock:
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM subscriptions WHERE id = ?", (int(subscription_id),))
                conn.commit()
                return int(cur.rowcount)

    def delete_unavailable_subscriptions(self, include_disabled: bool = False) -> int:
        where = "last_status = 'failed'"
        if include_disabled:
            where = f"({where} OR enabled = 0)"
        with self._write_lock:
            with self._connect() as conn:
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

    def get_subscription_links(
        self,
        only_available: bool = True,
        protocol: str | None = None,
        limit: int = 5000,
    ) -> list[str]:
        where: list[str] = []
        params: list[Any] = []

        if only_available:
            where.append("available = 1")
        if protocol:
            where.append("protocol = ?")
            params.append(protocol)

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    normalized_key,
                    raw_link,
                    country,
                    city,
                    fallback_front_keys_json,
                    ip_purity_level,
                    openai_unlocked,
                    created_at
                FROM proxies
                {where_clause}
                ORDER BY latency_ms ASC, updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        records = [dict(row) for row in rows]
        serial_map: dict[str, int] = {
            str(item.get("normalized_key") or ""): idx + 1 for idx, item in enumerate(records)
        }
        links: list[str] = []
        for idx, item in enumerate(records, start=1):
            alias = _build_export_alias(item, serial=idx, serial_map=serial_map)
            links.append(_rewrite_share_alias(str(item.get("raw_link") or ""), alias))
        return links

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        extra_json = str(data.get("extra_json") or "{}")
        try:
            data["extra"] = json.loads(extra_json)
        except json.JSONDecodeError:
            data["extra"] = {}
        fallback_json = str(data.get("fallback_front_keys_json") or "[]")
        try:
            parsed = json.loads(fallback_json)
            if isinstance(parsed, list):
                data["fallback_front_keys"] = [str(item).strip() for item in parsed if str(item).strip()]
            else:
                data["fallback_front_keys"] = []
        except json.JSONDecodeError:
            data["fallback_front_keys"] = []
        val = data.get("openai_unlocked")
        if val is None:
            data["openai_unlocked"] = None
        else:
            data["openai_unlocked"] = bool(val)
        return data

    def _subscription_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["enabled"] = bool(data.get("enabled"))
        return data


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_export_alias(row: dict[str, Any], serial: int, serial_map: dict[str, int]) -> str:
    country = str(row.get("country") or "").strip() or "未知"
    city = str(row.get("city") or "").strip() or "未知"
    geo = f"{country}:{city}"

    fallback_keys = _parse_fallback_keys(row.get("fallback_front_keys_json"))
    chain_serials = [str(serial_map[key]) for key in fallback_keys if key in serial_map]
    if chain_serials:
        route = f"链式({'.'.join(chain_serials)})"
    elif fallback_keys:
        route = "链式(?)"
    else:
        route = "直连"

    purity_raw = str(row.get("ip_purity_level") or "").strip()
    if purity_raw == "家宽":
        purity = "家宽"
    elif purity_raw == "非家宽":
        purity = "非家宽"
    else:
        purity = "未知"

    unlocked = row.get("openai_unlocked")
    if unlocked is None:
        gpt = "未检测GPT"
    elif bool(unlocked):
        gpt = "已解锁GPT"
    else:
        gpt = "未解锁GPT"

    imported = _format_import_time(row.get("created_at"))
    return f"{int(serial)}_{geo}_{route}_{purity}_{gpt}_{imported}"


def _parse_fallback_keys(value: Any) -> list[str]:
    text = str(value or "[]")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    keys: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _format_import_time(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "00000000000000"
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y%m%d%H%M%S")
    except Exception:
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) >= 14:
            return digits[:14]
        return "00000000000000"


def _rewrite_share_alias(raw_link: str, alias: str) -> str:
    link = str(raw_link or "").strip()
    if not link:
        return link
    if link.startswith("vmess://"):
        return _rewrite_vmess_alias(link, alias)
    if link.startswith("ssr://"):
        return _rewrite_ssr_alias(link, alias)
    if "://" in link:
        return _rewrite_url_fragment_alias(link, alias)
    return link


def _rewrite_url_fragment_alias(link: str, alias: str) -> str:
    encoded = quote(alias, safe="")
    try:
        split = urlsplit(link)
        return urlunsplit(split._replace(fragment=encoded))
    except Exception:
        if "#" in link:
            return link.split("#", 1)[0] + "#" + encoded
        return link + "#" + encoded


def _rewrite_vmess_alias(link: str, alias: str) -> str:
    payload = link[len("vmess://") :]
    text = _safe_b64_decode_to_text(payload)
    if not text:
        return _rewrite_url_fragment_alias(link, alias)
    try:
        data = json.loads(text)
    except Exception:
        return _rewrite_url_fragment_alias(link, alias)
    if not isinstance(data, dict):
        return _rewrite_url_fragment_alias(link, alias)
    data["ps"] = alias
    encoded = base64.urlsafe_b64encode(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("utf-8").rstrip("=")
    return "vmess://" + encoded


def _rewrite_ssr_alias(link: str, alias: str) -> str:
    payload = link[len("ssr://") :]
    text = _safe_b64_decode_to_text(payload)
    if not text:
        return _rewrite_url_fragment_alias(link, alias)
    if "/?" in text:
        base, query = text.split("/?", 1)
        params = parse_qs(query, keep_blank_values=True)
    else:
        base = text
        params = {}
    remarks = base64.urlsafe_b64encode(alias.encode("utf-8")).decode("utf-8").rstrip("=")
    params["remarks"] = [remarks]
    rebuilt = f"{base}/?{urlencode(params, doseq=True)}"
    encoded = base64.urlsafe_b64encode(rebuilt.encode("utf-8")).decode("utf-8").rstrip("=")
    return "ssr://" + encoded


def _safe_b64_decode_to_text(payload: str) -> str:
    text = str(payload or "").strip()
    if not text:
        return ""
    padded = text + "=" * ((4 - len(text) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
    except Exception:
        return ""
    try:
        return raw.decode("utf-8")
    except Exception:
        return ""
