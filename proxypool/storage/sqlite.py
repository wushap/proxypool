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
        CREATE TABLE IF NOT EXISTS backend_instances (
            instance_id TEXT PRIMARY KEY,
            pid INTEGER NOT NULL DEFAULT -1,
            config_file TEXT NOT NULL DEFAULT '',
            routes_file TEXT NOT NULL DEFAULT '',
            log_file TEXT NOT NULL DEFAULT '',
            listen TEXT NOT NULL DEFAULT '127.0.0.1',
            ports_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'stopped',
            last_error TEXT NOT NULL DEFAULT '',
            started_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_backend_instances_status ON backend_instances(status);
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
        CREATE TABLE IF NOT EXISTS published_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            filters_json TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_published_subscriptions_enabled ON published_subscriptions(enabled);
        CREATE TABLE IF NOT EXISTS proxy_pools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            published_subscription_id INTEGER,
            resin_subscription_id TEXT NOT NULL DEFAULT '',
            resin_platform_id TEXT NOT NULL DEFAULT '',
            filters_json TEXT NOT NULL DEFAULT '{}',
            listen TEXT NOT NULL DEFAULT '0.0.0.0',
            inbound_type TEXT NOT NULL DEFAULT 'http',
            status TEXT NOT NULL DEFAULT 'stopped',
            last_synced_at TEXT,
            last_error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_proxy_pools_status ON proxy_pools(status);
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
        latency_min: int | None = None,
        latency_max: int | None = None,
        freshness_hours: int | None = None,
        exclude_keys: set[str] | None = None,
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
        if latency_min is not None and int(latency_min) >= 0:
            where.append("latency_ms >= ?")
            params.append(int(latency_min))
        if latency_max is not None and int(latency_max) >= 0:
            where.append("latency_ms <= ?")
            params.append(int(latency_max))
        if freshness_hours is not None and int(freshness_hours) > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=int(freshness_hours))).isoformat()
            where.append("last_checked_at >= ?")
            params.append(cutoff)
        if exclude_keys:
            placeholders = ", ".join("?" for _ in exclude_keys)
            where.append(f"normalized_key NOT IN ({placeholders})")
            params.extend(exclude_keys)

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

    def upsert_backend_instance(
        self,
        instance_id: str,
        pid: int,
        config_file: str,
        routes_file: str,
        log_file: str,
        listen: str,
        ports: list[int],
        status: str,
        last_error: str = "",
    ) -> dict[str, Any]:
        safe_id = str(instance_id or "").strip() or "default"
        now = _utc_now()
        clean_ports = [int(port) for port in ports if 0 < int(port) <= 65535]
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO backend_instances (
                        instance_id, pid, config_file, routes_file, log_file, listen,
                        ports_json, status, last_error, started_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(instance_id) DO UPDATE SET
                        pid = excluded.pid,
                        config_file = excluded.config_file,
                        routes_file = excluded.routes_file,
                        log_file = excluded.log_file,
                        listen = excluded.listen,
                        ports_json = excluded.ports_json,
                        status = excluded.status,
                        last_error = excluded.last_error,
                        started_at = excluded.started_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        safe_id,
                        int(pid),
                        str(config_file or ""),
                        str(routes_file or ""),
                        str(log_file or ""),
                        str(listen or "127.0.0.1"),
                        json.dumps(clean_ports, separators=(",", ":")),
                        str(status or "stopped")[:32],
                        str(last_error or "")[:1000],
                        now if str(status or "") == "running" else None,
                        now,
                        now,
                    ),
                )
                row = conn.execute("SELECT * FROM backend_instances WHERE instance_id = ?", (safe_id,)).fetchone()
                conn.commit()
        if row is None:
            raise RuntimeError("failed to upsert backend instance")
        return self._backend_instance_row_to_dict(row)

    def list_backend_instances(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM backend_instances
                ORDER BY updated_at DESC, instance_id ASC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [self._backend_instance_row_to_dict(row) for row in rows]

    def update_backend_instance_status(
        self,
        instance_id: str,
        status: str,
        pid: int | None = None,
        last_error: str = "",
    ) -> None:
        updates = ["status = ?", "last_error = ?", "updated_at = ?"]
        params: list[Any] = [str(status or "stopped")[:32], str(last_error or "")[:1000], _utc_now()]
        if pid is not None:
            updates.append("pid = ?")
            params.append(int(pid))
        params.append(str(instance_id or "").strip() or "default")
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE backend_instances SET {', '.join(updates)} WHERE instance_id = ?",
                    params,
                )
                conn.commit()

    def delete_backend_instance(self, instance_id: str) -> int:
        safe_id = str(instance_id or "").strip() or "default"
        with self._write_lock:
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM backend_instances WHERE instance_id = ?", (safe_id,))
                deleted = int(cur.rowcount or 0)
                conn.commit()
        return deleted

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
    ) -> dict[str, Any]:
        now = _utc_now()
        filters_json = json.dumps(_normalize_published_subscription_filters(filters), ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO published_subscriptions (name, filters_json, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        (str(name or "").strip() or "published-subscription")[:120],
                        filters_json,
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
    ) -> dict[str, Any]:
        updates: list[str] = []
        params: list[Any] = []
        if name is not None:
            updates.append("name = ?")
            params.append((str(name or "").strip() or "published-subscription")[:120])
        if filters is not None:
            updates.append("filters_json = ?")
            params.append(json.dumps(_normalize_published_subscription_filters(filters), ensure_ascii=False, separators=(",", ":")))
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(int(subscription_id))

        with self._write_lock:
            with self._connect() as conn:
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
                cur = conn.execute("DELETE FROM published_subscriptions WHERE id = ?", (int(subscription_id),))
                conn.commit()
                return int(cur.rowcount)

    def get_published_subscription_links(self, subscription_id: int, limit: int = 5000) -> list[str]:
        item = self.get_published_subscription(subscription_id)
        if item is None:
            raise ValueError("published subscription not found")
        return self.get_subscription_links(limit=limit, **_filters_to_subscription_link_kwargs(item.get("filters") or {}))

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

    def get_backend_default_listen(self) -> str:
        return self.get_app_setting("backend_default_listen", "127.0.0.1") or "127.0.0.1"

    def set_backend_default_listen(self, listen: str) -> str:
        safe = str(listen or "").strip() or "127.0.0.1"
        if len(safe) > 80:
            raise ValueError("listen address is too long")
        self.set_app_setting("backend_default_listen", safe)
        return safe

    # ---- proxy pool CRUD ----

    def create_proxy_pool(
        self,
        name: str,
        filters: dict[str, Any] | None = None,
        listen: str = "0.0.0.0",
        inbound_type: str = "http",
    ) -> dict[str, Any]:
        now = _utc_now()
        filters_json = json.dumps(_normalize_pool_filters(filters), ensure_ascii=False, separators=(",", ":"))
        safe_name = (str(name or "").strip() or "proxy-pool")[:120]
        safe_listen = str(listen or "0.0.0.0").strip() or "0.0.0.0"
        safe_type = str(inbound_type or "http").strip().lower() or "http"
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO proxy_pools (name, filters_json, listen, inbound_type, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'stopped', ?, ?)
                    """,
                    (safe_name, filters_json, safe_listen, safe_type, now, now),
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
        resin_subscription_id: str | None = None,
        resin_platform_id: str | None = None,
    ) -> dict[str, Any]:
        updates: list[str] = []
        params: list[Any] = []
        if name is not None:
            updates.append("name = ?")
            params.append((str(name or "").strip() or "proxy-pool")[:120])
        if filters is not None:
            updates.append("filters_json = ?")
            params.append(json.dumps(_normalize_pool_filters(filters), ensure_ascii=False, separators=(",", ":")))
        if listen is not None:
            updates.append("listen = ?")
            params.append(str(listen or "0.0.0.0").strip() or "0.0.0.0")
        if inbound_type is not None:
            updates.append("inbound_type = ?")
            params.append(str(inbound_type or "http").strip().lower() or "http")
        if published_subscription_id is not None:
            updates.append("published_subscription_id = ?")
            params.append(int(published_subscription_id))
        if resin_subscription_id is not None:
            updates.append("resin_subscription_id = ?")
            params.append(str(resin_subscription_id))
        if resin_platform_id is not None:
            updates.append("resin_platform_id = ?")
            params.append(str(resin_platform_id))
        if not updates:
            return self.get_proxy_pool(pool_id) or {}
        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(int(pool_id))
        with self._write_lock:
            with self._connect() as conn:
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
        with self._write_lock:
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM proxy_pools WHERE id = ?", (int(pool_id),))
                deleted = int(cur.rowcount or 0)
                conn.commit()
        return deleted

    def get_proxy_pool(self, pool_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM proxy_pools WHERE id = ? LIMIT 1", (int(pool_id),)).fetchone()
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

    def update_proxy_pool_status(
        self,
        pool_id: int,
        status: str,
        last_error: str = "",
        last_synced_at: str | None = None,
    ) -> None:
        updates = ["status = ?", "last_error = ?", "updated_at = ?"]
        params: list[Any] = [str(status or "stopped")[:32], str(last_error or "")[:1000], _utc_now()]
        if last_synced_at is not None:
            updates.append("last_synced_at = ?")
            params.append(last_synced_at)
        params.append(int(pool_id))
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE proxy_pools SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                conn.commit()

    def _pool_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["filters"] = _normalize_pool_filters(_loads_json_object(data.get("filters_json")))
        data.pop("filters_json", None)
        data["match_count"] = len(
            self.list_proxies_filtered(limit=20000, **_pool_filters_to_list_kwargs(data.get("filters") or {}))
        )
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
        available: bool | None = None,
        source_keyword: str | None = None,
        geo_filter: str | None = None,
        geo_country: str | None = None,
        geo_location: str | None = None,
        openai_filter: str | None = None,
        ip_purity_filter: str | None = None,
        fallback_front_filter: str | None = None,
    ) -> list[str]:
        where: list[str] = []
        params: list[Any] = []

        if available is not None:
            where.append("available = ?")
            params.append(1 if available else 0)
        elif only_available:
            where.append("available = 1")
        if protocol:
            where.append("protocol = ?")
            params.append(protocol)
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

    def _backend_instance_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            ports = json.loads(str(data.get("ports_json") or "[]"))
        except json.JSONDecodeError:
            ports = []
        data["ports"] = [int(port) for port in ports if str(port).strip().isdigit()]
        data.pop("ports_json", None)
        return data

    def _published_subscription_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["enabled"] = bool(data.get("enabled"))
        filters = _normalize_published_subscription_filters(_loads_json_object(data.get("filters_json")))
        data["filters"] = filters
        data["match_count"] = len(self.list_proxies_filtered(limit=20000, **_filters_to_proxy_list_kwargs(filters)))
        data.pop("filters_json", None)
        return data


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads_json_object(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_pool_filters(filters: dict[str, Any] | None) -> dict[str, str]:
    out = _normalize_published_subscription_filters(filters)
    raw = filters or {}
    for key in ("latency_min", "latency_max", "freshness_hours"):
        value = str(raw.get(key) or "").strip()
        if value:
            try:
                num = int(float(value))
                if num >= 0:
                    out[key] = str(num)
            except (ValueError, TypeError):
                pass
    return out


def _pool_filters_to_list_kwargs(filters: dict[str, Any]) -> dict[str, Any]:
    kwargs = _filters_to_proxy_list_kwargs(filters)
    for key in ("latency_min", "latency_max", "freshness_hours"):
        value = str(filters.get(key) or "").strip()
        if value:
            try:
                kwargs[key] = int(float(value))
            except (ValueError, TypeError):
                pass
    return kwargs


def _normalize_published_subscription_filters(filters: dict[str, Any] | None) -> dict[str, str]:
    raw = filters or {}
    out: dict[str, str] = {}
    allowed = {
        "protocol",
        "available",
        "source",
        "geo_filter",
        "geo_country",
        "geo_location",
        "openai_filter",
        "ip_purity_filter",
        "fallback_front_filter",
    }
    for key in allowed:
        value = str(raw.get(key) or "").strip()
        if value:
            out[key] = value[:300]
    if out.get("available") not in {None, "true", "false"}:
        out.pop("available", None)
    if out.get("geo_filter") not in {None, "has", "none"}:
        out.pop("geo_filter", None)
    if out.get("openai_filter") not in {None, "unlocked", "blocked", "unchecked"}:
        out.pop("openai_filter", None)
    if out.get("ip_purity_filter") not in {None, "checked", "unchecked", "residential", "non_residential", "unknown"}:
        out.pop("ip_purity_filter", None)
    if out.get("fallback_front_filter") not in {None, "has", "none"}:
        out.pop("fallback_front_filter", None)
    return out


def _filters_to_proxy_list_kwargs(filters: dict[str, Any]) -> dict[str, Any]:
    available_text = str(filters.get("available") or "").strip()
    available: bool | None
    if available_text == "true":
        available = True
    elif available_text == "false":
        available = False
    else:
        available = None
    return {
        "protocol": str(filters.get("protocol") or "").strip() or None,
        "available": available,
        "source_keyword": str(filters.get("source") or "").strip() or None,
        "geo_filter": str(filters.get("geo_filter") or "").strip() or None,
        "geo_country": str(filters.get("geo_country") or "").strip() or None,
        "geo_location": str(filters.get("geo_location") or "").strip() or None,
        "openai_filter": str(filters.get("openai_filter") or "").strip() or None,
        "ip_purity_filter": str(filters.get("ip_purity_filter") or "").strip() or None,
        "fallback_front_filter": str(filters.get("fallback_front_filter") or "").strip() or None,
        "sort_by": "latency",
        "sort_order": "asc",
    }


def _filters_to_subscription_link_kwargs(filters: dict[str, Any]) -> dict[str, Any]:
    kwargs = _filters_to_proxy_list_kwargs(filters)
    kwargs["only_available"] = kwargs.pop("available") is not False
    if str(filters.get("available") or "").strip() == "true":
        kwargs["available"] = True
    elif str(filters.get("available") or "").strip() == "false":
        kwargs["available"] = False
    kwargs.pop("sort_by", None)
    kwargs.pop("sort_order", None)
    return kwargs


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
