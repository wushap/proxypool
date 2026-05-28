from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from proxypool.models import ProxyNode
from proxypool.storage._helpers import (
    _build_export_alias,
    _format_import_time,
    _normalize_string_list,
    _parse_fallback_keys,
    _rewrite_share_alias,
    _utc_now,
)


class ProxyMixin:
    """Proxy CRUD methods for SQLiteProxyStorage."""

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
                data["fallback_front_keys"] = [
                    str(item).strip() for item in parsed if str(item).strip()
                ]
            else:
                data["fallback_front_keys"] = []
        except json.JSONDecodeError:
            data["fallback_front_keys"] = []
        val = data.get("openai_unlocked")
        if val is None:
            data["openai_unlocked"] = None
        else:
            data["openai_unlocked"] = bool(val)

        # 计算成功率
        success_count = int(data.get("success_count") or 0)
        total_checks = int(data.get("total_checks") or 0)
        if total_checks > 0:
            data["success_rate"] = round(success_count / total_checks * 100, 2)
        else:
            data["success_rate"] = None

        return data

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
        route_mode_filter: str | None = None,
        source_keyword: str | None = None,
        geo_filter: str | None = None,
        geo_country: str | None = None,
        geo_countries: list[str] | None = None,
        geo_location: str | None = None,
        openai_filter: str | None = None,
        ip_purity_filter: str | None = None,
        fallback_front_filter: str | None = None,
        sort_by: str = "latency",
        sort_order: str = "asc",
        latency_min: int | None = None,
        latency_max: int | None = None,
        speed_min_mbps: float | None = None,
        freshness_hours: int | None = None,
        exclude_keys: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []

        if protocol:
            where.append("protocol = ?")
            params.append(protocol)
        if route_mode_filter == "direct":
            where.append("available = 1")
            where.append("fallback_front_keys_json = '[]'")
        elif route_mode_filter == "chain":
            where.append("available = 1")
            where.append("fallback_front_keys_json <> '[]'")
        elif route_mode_filter == "unreachable":
            where.append("available = 0")
        elif available is not None:
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
        if geo_countries:
            selected_countries = _normalize_string_list(geo_countries, max_items=64)
            concrete = [country for country in selected_countries if country != "-"]
            include_unknown = "-" in selected_countries
            clauses: list[str] = []
            if concrete:
                placeholders = ", ".join("?" for _ in concrete)
                clauses.append(f"country IN ({placeholders})")
                params.extend(concrete)
            if include_unknown:
                clauses.append("country = ''")
            if clauses:
                where.append(f"({' OR '.join(clauses)})")
        elif geo_country:
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
        if speed_min_mbps is not None and float(speed_min_mbps) >= 0:
            where.append("speed_mbps IS NOT NULL")
            where.append("speed_mbps > ?")
            params.append(float(speed_min_mbps))
        if freshness_hours is not None and int(freshness_hours) > 0:
            cutoff = (datetime.now(UTC) - timedelta(hours=int(freshness_hours))).isoformat()
            where.append("last_checked_at >= ?")
            params.append(cutoff)
        if exclude_keys:
            placeholders = ", ".join("?" for _ in exclude_keys)
            where.append(f"normalized_key NOT IN ({placeholders})")
            params.extend(exclude_keys)

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        params.extend([limit, offset])
        norm_order = "DESC" if str(sort_order).lower() == "desc" else "ASC"
        sort_key = str(sort_by).lower()
        if sort_key == "latency":
            order_clause = f"CASE WHEN latency_ms IS NULL THEN 1 ELSE 0 END ASC, latency_ms {norm_order}, updated_at DESC"
        elif sort_key in ("speed", "bandwidth", "speed_mbps"):
            order_clause = f"CASE WHEN speed_mbps IS NULL OR speed_mbps <= 0 THEN 1 ELSE 0 END ASC, speed_mbps {norm_order}, updated_at DESC"
        elif sort_key in ("fail_count", "failures"):
            order_clause = f"fail_count {norm_order}, updated_at DESC"
        elif sort_key in ("last_checked", "checked"):
            order_clause = f"CASE WHEN last_checked_at IS NULL THEN 1 ELSE 0 END ASC, last_checked_at {norm_order}, updated_at DESC"
        elif sort_key in ("success_rate", "success"):
            # 按可用性排序（作为成功率的代理指标）
            order_clause = "available DESC, fail_count ASC, updated_at DESC"
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
        only_direct: bool = False,
        min_last_checked_age_hours: int = 0,
        protocols: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []

        if only_unchecked:
            where.append("last_checked_at IS NULL")
        if only_available:
            where.append("available = 1")
        if only_direct:
            where.append("fallback_front_keys_json = '[]'")
        if only_unavailable:
            where.append("available = 0")
        if not only_unchecked:
            min_age_hours = max(0, int(min_last_checked_age_hours or 0))
            if min_age_hours > 0:
                cutoff = (datetime.now(UTC) - timedelta(hours=min_age_hours)).isoformat()
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
                        (
                            latency_ms,
                            now,
                            openai_val,
                            openai_status[:160],
                            now,
                            fallback_keys_json,
                            now,
                            normalized_key,
                        ),
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
                        (
                            now,
                            error[:1000],
                            openai_val,
                            openai_status[:160],
                            now,
                            fallback_keys_json,
                            now,
                            normalized_key,
                        ),
                    )
                conn.commit()

    def update_speed_test_result(
        self,
        normalized_key: str,
        ok: bool,
        speed_mbps: float | None = None,
    ) -> None:
        now = _utc_now()
        with self._write_lock, self._connect() as conn:
            if ok and speed_mbps is not None and float(speed_mbps) >= 0:
                conn.execute(
                    """
                        UPDATE proxies
                        SET speed_mbps = ?, speed_tested_at = ?, updated_at = ?
                        WHERE normalized_key = ?
                        """,
                    (round(float(speed_mbps), 3), now, now, normalized_key),
                )
            else:
                conn.execute(
                    """
                        UPDATE proxies
                        SET speed_tested_at = ?, updated_at = ?
                        WHERE normalized_key = ?
                        """,
                    (now, now, normalized_key),
                )
            conn.commit()

    def mark_unavailable_by_fail_count(self, threshold: int = 5) -> int:
        """将 fail_count >= threshold 的可用代理标记为不可用

        Returns:
            被标记为不可用的代理数量
        """
        now = _utc_now()
        with self._write_lock, self._connect() as conn:
            cursor = conn.execute(
                """
                    UPDATE proxies
                    SET available = 0, updated_at = ?
                    WHERE available = 1 AND fail_count >= ?
                    """,
                (now, threshold),
            )
            conn.commit()
            return cursor.rowcount

    def update_check_result(self, normalized_key: str, success: bool) -> None:
        """更新代理的检查结果统计

        Args:
            normalized_key: 代理的唯一标识
            success: 本次检查是否成功
        """
        now = _utc_now()
        with self._write_lock, self._connect() as conn:
            if success:
                conn.execute(
                    """
                        UPDATE proxies
                        SET success_count = success_count + 1,
                            total_checks = total_checks + 1,
                            updated_at = ?
                        WHERE normalized_key = ?
                        """,
                    (now, normalized_key),
                )
            else:
                conn.execute(
                    """
                        UPDATE proxies
                        SET total_checks = total_checks + 1,
                            updated_at = ?
                        WHERE normalized_key = ?
                        """,
                    (now, normalized_key),
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
        with self._write_lock, self._connect() as conn:
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
        with self._write_lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM proxies WHERE available = 0 AND fail_count >= ?",
                (max_fail_count,),
            )
            conn.commit()
            return int(cursor.rowcount)

    def delete_unavailable(self) -> int:
        with self._write_lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM proxies WHERE available = 0")
            conn.commit()
            return int(cursor.rowcount)

    def delete_proxies_by_keys(self, normalized_keys: list[str]) -> int:
        keys: list[str] = []
        seen: set[str] = set()
        for item in normalized_keys:
            key = str(item or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        if not keys:
            return 0
        placeholders = ",".join("?" for _ in keys)
        with self._write_lock, self._connect() as conn:
            cursor = conn.execute(
                f"DELETE FROM proxies WHERE normalized_key IN ({placeholders})",
                keys,
            )
            conn.commit()
        return int(cursor.rowcount or 0)

    def get_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM proxies").fetchone()[0])
            available = int(
                conn.execute("SELECT COUNT(*) FROM proxies WHERE available = 1").fetchone()[0]
            )
            checked = int(
                conn.execute(
                    "SELECT COUNT(*) FROM proxies WHERE last_checked_at IS NOT NULL"
                ).fetchone()[0]
            )
            avg_latency_row = conn.execute(
                "SELECT AVG(latency_ms) FROM proxies WHERE available = 1 AND latency_ms IS NOT NULL"
            ).fetchone()
            avg_latency_ms = (
                int(avg_latency_row[0]) if avg_latency_row and avg_latency_row[0] else None
            )

            # Country distribution
            country_rows = conn.execute(
                "SELECT country, COUNT(*) AS cnt FROM proxies WHERE country != '' GROUP BY country ORDER BY cnt DESC"
            ).fetchall()
            by_country = {str(r["country"]): int(r["cnt"]) for r in country_rows}

            # OpenAI unlock stats
            openai_unlocked = int(
                conn.execute("SELECT COUNT(*) FROM proxies WHERE openai_unlocked = 1").fetchone()[0]
            )
            openai_blocked = int(
                conn.execute(
                    "SELECT COUNT(*) FROM proxies WHERE openai_unlocked = 0 AND openai_status IS NOT NULL AND openai_status != ''"
                ).fetchone()[0]
            )

            # IP purity stats
            purity_rows = conn.execute(
                "SELECT ip_purity_level, COUNT(*) AS cnt FROM proxies WHERE ip_purity_level != '' GROUP BY ip_purity_level ORDER BY cnt DESC"
            ).fetchall()
            by_purity = {str(r["ip_purity_level"]): int(r["cnt"]) for r in purity_rows}

            # Average bandwidth
            avg_bw_row = conn.execute(
                "SELECT AVG(speed_mbps) FROM proxies WHERE available = 1 AND speed_mbps IS NOT NULL AND speed_mbps > 0"
            ).fetchone()
            avg_speed_mbps = (
                round(float(avg_bw_row[0]), 1) if avg_bw_row and avg_bw_row[0] else None
            )

            # Subscription count
            sub_count = int(conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0])

        return {
            "total": total,
            "available": available,
            "checked": checked,
            "availability_rate": round((available / total) * 100, 2) if total else 0.0,
            "avg_latency_ms": avg_latency_ms,
            "by_protocol": self.count_by_protocol(),
            "by_country": by_country,
            "openai_unlocked": openai_unlocked,
            "openai_blocked": openai_blocked,
            "by_purity": by_purity,
            "avg_speed_mbps": avg_speed_mbps,
            "subscription_count": sub_count,
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
        with self._write_lock, self._connect() as conn:
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
        where: list[str] = [
            "(resolved_ip = '' OR country = '' OR city = '' OR ip_purity_checked_at IS NULL)"
        ]
        if only_available:
            where.append("available = 1")
        if only_tested:
            where.append("last_checked_at IS NOT NULL")
        where_clause = " AND ".join(where)
        with self._connect() as conn:
            sql = f"""
            SELECT *
            FROM proxies
            WHERE {where_clause}
            ORDER BY updated_at DESC
            """
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

    def get_subscription_links(
        self,
        only_available: bool = True,
        protocol: str | None = None,
        limit: int = 5000,
        available: bool | None = None,
        route_mode_filter: str | None = None,
        source_keyword: str | None = None,
        geo_filter: str | None = None,
        geo_country: str | None = None,
        geo_countries: list[str] | None = None,
        geo_location: str | None = None,
        openai_filter: str | None = None,
        ip_purity_filter: str | None = None,
        fallback_front_filter: str | None = None,
    ) -> list[str]:
        where: list[str] = []
        params: list[Any] = []

        if route_mode_filter == "direct":
            where.append("available = 1")
            where.append("fallback_front_keys_json = '[]'")
        elif route_mode_filter == "chain":
            where.append("available = 1")
            where.append("fallback_front_keys_json <> '[]'")
        elif route_mode_filter == "unreachable":
            where.append("available = 0")
        elif available is not None:
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
        if geo_countries:
            selected_countries = _normalize_string_list(geo_countries, max_items=64)
            concrete = [country for country in selected_countries if country != "-"]
            include_unknown = "-" in selected_countries
            clauses: list[str] = []
            if concrete:
                placeholders = ", ".join("?" for _ in concrete)
                clauses.append(f"country IN ({placeholders})")
                params.extend(concrete)
            if include_unknown:
                clauses.append("country = ''")
            if clauses:
                where.append(f"({' OR '.join(clauses)})")
        elif geo_country:
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
