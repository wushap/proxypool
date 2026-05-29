"""
Tests for proxypool.storage.proxy_mixin.ProxyMixin to increase coverage.
"""

from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import sqlite3

from proxypool.models import ProxyNode
from proxypool.storage.proxy_mixin import ProxyMixin


# Minimum schema required by ProxyMixin methods.
_SCHEMA_SQL = """
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
    speed_mbps REAL,
    speed_tested_at TEXT,
    fail_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    total_checks INTEGER NOT NULL DEFAULT 0,
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
"""


class _TestableProxyMixin(ProxyMixin):
    """Concrete subclass providing the two things ProxyMixin expects from its host."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._write_lock = threading.RLock()
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA_SQL)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._db_path,
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn


def _make_node(
    host: str = "1.1.1.1",
    port: int = 443,
    protocol: str = "ss",
    name: str = "",
    raw_link: str = "",
    extra: dict | None = None,
) -> ProxyNode:
    if not raw_link:
        raw_link = f"{protocol}://{host}:{port}"
    return ProxyNode(
        protocol=protocol,
        host=host,
        port=port,
        name=name,
        raw_link=raw_link,
        extra=extra or {},
    )


class TestProxyMixinUpsert(unittest.TestCase):
    def test_upsert_inserts_new_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.2.3.4")
            result = storage.upsert_proxy(node, source="test-src")
            self.assertEqual(result, "inserted")
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertIsNotNone(row)
            self.assertEqual(row["host"], "1.2.3.4")
            self.assertEqual(row["source"], "test-src")

    def test_upsert_updates_existing_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="5.6.7.8", name="old")
            storage.upsert_proxy(node)
            updated = _make_node(host="5.6.7.8", name="new")
            result = storage.upsert_proxy(updated, source="updated")
            self.assertEqual(result, "updated")
            row = storage.get_proxy_by_key(updated.normalized_key())
            self.assertEqual(row["name"], "new")
            self.assertEqual(row["source"], "updated")

    def test_upsert_preserves_extra_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(extra={"cipher": "aes-256-gcm", "password": "secret"})
            storage.upsert_proxy(node)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertEqual(row["extra"]["cipher"], "aes-256-gcm")


class TestProxyMixinList(unittest.TestCase):
    def test_list_proxies(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            for i in range(5):
                storage.upsert_proxy(_make_node(host=f"10.0.0.{i}"))
            rows = storage.list_proxies(limit=10)
            self.assertEqual(len(rows), 5)

    def test_list_proxies_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            rows = storage.list_proxies(limit=10)
            self.assertEqual(len(rows), 0)

    def test_list_proxies_offset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            for i in range(5):
                storage.upsert_proxy(_make_node(host=f"10.0.0.{i}"))
            rows = storage.list_proxies_filtered(limit=2, offset=2)
            self.assertEqual(len(rows), 2)

    def test_list_proxies_protocol_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            storage.upsert_proxy(_make_node(protocol="ss", host="1.1.1.1"))
            storage.upsert_proxy(_make_node(protocol="trojan", host="2.2.2.2"))
            ss_rows = storage.list_proxies_filtered(limit=10, protocol="ss")
            self.assertEqual(len(ss_rows), 1)
            self.assertEqual(ss_rows[0]["protocol"], "ss")

    def test_list_proxies_available_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            avail = storage.list_proxies_filtered(limit=10, available=True)
            self.assertEqual(len(avail), 1)

    def test_list_proxies_route_mode_direct(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=50,
                                       fallback_front_keys=[])
            storage.update_test_result(n2.normalized_key(), available=True, latency_ms=50,
                                       fallback_front_keys=["front-key"])
            rows = storage.list_proxies_filtered(limit=10, route_mode_filter="direct")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_route_mode_chain(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=50,
                                       fallback_front_keys=["front-key"])
            rows = storage.list_proxies_filtered(limit=10, route_mode_filter="chain")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_route_mode_unreachable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=False, latency_ms=None,
                                       error="timeout")
            rows = storage.list_proxies_filtered(limit=10, route_mode_filter="unreachable")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_source_keyword(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            storage.upsert_proxy(_make_node(host="1.1.1.1"), source="upload:test.txt")
            storage.upsert_proxy(_make_node(host="2.2.2.2"), source="other")
            rows = storage.list_proxies_filtered(limit=10, source_keyword="upload")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_source_keyword_dash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            storage.upsert_proxy(_make_node(host="1.1.1.1"), source="upload:test.txt")
            storage.upsert_proxy(_make_node(host="2.2.2.2"), source="")
            rows = storage.list_proxies_filtered(limit=10, source_keyword="-")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_geo_filter_has(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US", city="LA")
            rows = storage.list_proxies_filtered(limit=10, geo_filter="has")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_geo_filter_none(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            rows = storage.list_proxies_filtered(limit=10, geo_filter="none")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_geo_countries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US")
            # n2 has default empty country -> matches "-"
            rows = storage.list_proxies_filtered(limit=10, geo_countries=["US", "-"])
            self.assertEqual(len(rows), 2)

    def test_list_proxies_geo_country(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US")
            rows = storage.list_proxies_filtered(limit=10, geo_country="US")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_geo_country_dash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            rows = storage.list_proxies_filtered(limit=10, geo_country="-")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_geo_location_with_colon(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US", city="LA")
            rows = storage.list_proxies_filtered(limit=10, geo_location="US:LA")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_geo_location_keyword(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US")
            rows = storage.list_proxies_filtered(limit=10, geo_location="US")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_geo_location_dash_country(self) -> None:
        """geo_location="-:LA" filters country='' AND city='LA'"""
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            # Set city=LA but leave country empty
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="", city="LA")
            rows = storage.list_proxies_filtered(limit=10, geo_location="-:LA")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_geo_location_dash_city(self) -> None:
        """geo_location="US:-" filters country='US' AND city=''"""
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US", city="")
            rows = storage.list_proxies_filtered(limit=10, geo_location="US:-")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_openai_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100,
                                       openai_unlocked=True)
            unlocked = storage.list_proxies_filtered(limit=10, openai_filter="unlocked")
            self.assertEqual(len(unlocked), 1)
            blocked = storage.list_proxies_filtered(limit=10, openai_filter="blocked")
            self.assertEqual(len(blocked), 0)
            unchecked = storage.list_proxies_filtered(limit=10, openai_filter="unchecked")
            self.assertEqual(len(unchecked), 0)

    def test_list_proxies_ip_purity_filters(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_ip_purity(n1.normalized_key(), score=0.9, level="家宽")
            self.assertEqual(len(storage.list_proxies_filtered(limit=10, ip_purity_filter="checked")), 1)
            self.assertEqual(len(storage.list_proxies_filtered(limit=10, ip_purity_filter="unchecked")), 1)
            self.assertEqual(len(storage.list_proxies_filtered(limit=10, ip_purity_filter="residential")), 1)
            self.assertEqual(len(storage.list_proxies_filtered(limit=10, ip_purity_filter="non_residential")), 0)
            self.assertEqual(len(storage.list_proxies_filtered(limit=10, ip_purity_filter="unknown")), 0)

    def test_list_proxies_ip_purity_unknown_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_ip_purity(n1.normalized_key(), score=0.0, level="未知")
            rows = storage.list_proxies_filtered(limit=10, ip_purity_filter="unknown")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_fallback_front_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100,
                                       fallback_front_keys=["front-a"])
            storage.update_test_result(n2.normalized_key(), available=True, latency_ms=100,
                                       fallback_front_keys=[])
            has = storage.list_proxies_filtered(limit=10, fallback_front_filter="has")
            none = storage.list_proxies_filtered(limit=10, fallback_front_filter="none")
            self.assertEqual(len(has), 1)
            self.assertEqual(len(none), 1)

    def test_list_proxies_latency_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=50)
            storage.update_test_result(n2.normalized_key(), available=True, latency_ms=200)
            rows = storage.list_proxies_filtered(limit=10, latency_min=100, latency_max=300)
            self.assertEqual(len(rows), 1)

    def test_list_proxies_speed_min(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_speed_test_result(n1.normalized_key(), ok=True, speed_mbps=80.5)
            rows = storage.list_proxies_filtered(limit=10, speed_min_mbps=80)
            self.assertEqual(len(rows), 1)

    def test_list_proxies_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            rows = storage.list_proxies_filtered(limit=10, freshness_hours=24)
            self.assertEqual(len(rows), 1)

    def test_list_proxies_exclude_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            rows = storage.list_proxies_filtered(limit=10, exclude_keys={n1.normalized_key()})
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["host"], "2.2.2.2")

    def test_list_proxies_sort_by_speed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_speed_test_result(n1.normalized_key(), ok=True, speed_mbps=10.0)
            storage.update_speed_test_result(n2.normalized_key(), ok=True, speed_mbps=100.0)
            rows = storage.list_proxies_filtered(limit=10, sort_by="speed", sort_order="desc")
            self.assertEqual(rows[0]["host"], "2.2.2.2")

    def test_list_proxies_sort_by_fail_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            rows = storage.list_proxies_filtered(limit=10, sort_by="fail_count")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_sort_by_last_checked(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            rows = storage.list_proxies_filtered(limit=10, sort_by="last_checked")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_sort_by_success_rate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            rows = storage.list_proxies_filtered(limit=10, sort_by="success_rate")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_sort_unknown_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            rows = storage.list_proxies_filtered(limit=10, sort_by="unknown_field")
            self.assertEqual(len(rows), 1)

    def test_list_proxies_sort_desc(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            rows = storage.list_proxies_filtered(limit=10, sort_order="desc")
            self.assertEqual(len(rows), 1)


class TestProxyMixinDelete(unittest.TestCase):
    def test_delete_proxies_by_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            deleted = storage.delete_proxies_by_keys([n1.normalized_key()])
            self.assertEqual(deleted, 1)
            self.assertIsNone(storage.get_proxy_by_key(n1.normalized_key()))
            self.assertIsNotNone(storage.get_proxy_by_key(n2.normalized_key()))

    def test_delete_proxies_by_keys_dedup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            deleted = storage.delete_proxies_by_keys([n1.normalized_key(), n1.normalized_key()])
            self.assertEqual(deleted, 1)

    def test_delete_proxies_by_keys_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            deleted = storage.delete_proxies_by_keys([])
            self.assertEqual(deleted, 0)

    def test_delete_proxies_by_keys_whitespace_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            deleted = storage.delete_proxies_by_keys(["  ", ""])
            self.assertEqual(deleted, 0)

    def test_delete_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            storage.update_test_result(n2.normalized_key(), available=False, latency_ms=None)
            deleted = storage.delete_unavailable()
            self.assertEqual(deleted, 1)
            self.assertIsNone(storage.get_proxy_by_key(n2.normalized_key()))

    def test_delete_stale_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            # Give it high fail count
            storage.update_test_result(n1.normalized_key(), available=False, latency_ms=None)
            storage.update_test_result(n1.normalized_key(), available=False, latency_ms=None)
            deleted = storage.delete_stale_unavailable(max_fail_count=2)
            self.assertEqual(deleted, 1)


class TestProxyMixinUpdate(unittest.TestCase):
    def test_update_test_result_available(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_test_result(
                node.normalized_key(),
                available=True,
                latency_ms=50,
                openai_unlocked=True,
                openai_status="401",
                fallback_front_keys=["fk1"],
            )
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertTrue(row["available"])
            self.assertEqual(row["latency_ms"], 50)
            self.assertTrue(row["openai_unlocked"])
            self.assertEqual(row["fallback_front_keys"], ["fk1"])

    def test_update_test_result_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=False, latency_ms=None,
                                       error="timeout")
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertFalse(row["available"])
            self.assertEqual(row["fail_count"], 1)

    def test_update_speed_test_result_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_speed_test_result(node.normalized_key(), ok=True, speed_mbps=42.5)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertAlmostEqual(row["speed_mbps"], 42.5, places=2)

    def test_update_speed_test_result_not_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_speed_test_result(node.normalized_key(), ok=False)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertIsNone(row["speed_mbps"])

    def test_update_check_result_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_check_result(node.normalized_key(), success=True)
            storage.update_check_result(node.normalized_key(), success=True)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertEqual(row["success_count"], 2)
            self.assertEqual(row["total_checks"], 2)

    def test_update_check_result_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_check_result(node.normalized_key(), success=False)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertEqual(row["success_count"], 0)
            self.assertEqual(row["total_checks"], 1)

    def test_update_openai_result(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_openai_result(node.normalized_key(), openai_unlocked=True,
                                         openai_status="401 unauthorized")
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertTrue(row["openai_unlocked"])
            self.assertEqual(row["openai_status"], "401 unauthorized")

    def test_update_openai_result_none(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_openai_result(node.normalized_key(), openai_unlocked=None)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertIsNone(row["openai_unlocked"])

    def test_update_geo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_geo(node.normalized_key(), resolved_ip="8.8.8.8",
                               country="US", city="NYC")
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertEqual(row["resolved_ip"], "8.8.8.8")
            self.assertEqual(row["country"], "US")
            self.assertEqual(row["city"], "NYC")

    def test_update_ip_purity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_ip_purity(node.normalized_key(), score=0.88, level="家宽")
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertAlmostEqual(row["ip_purity_score"], 0.88, places=2)
            self.assertEqual(row["ip_purity_level"], "家宽")

    def test_update_ip_purity_none_score(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_ip_purity(node.normalized_key(), score=None, level="")
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertIsNone(row["ip_purity_score"])

    def test_mark_unavailable_by_fail_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=50)
            # Bump fail_count to 5 via unavailable updates
            for _ in range(5):
                storage.update_test_result(node.normalized_key(), available=False, latency_ms=None)
            # Re-set as available
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=50)
            storage.update_check_result(node.normalized_key(), success=False)
            # Now set fail_count to 5
            key = node.normalized_key()
            with storage._connect() as conn:
                conn.execute("UPDATE proxies SET fail_count = 5 WHERE normalized_key = ?", (key,))
                conn.commit()
            marked = storage.mark_unavailable_by_fail_count(threshold=5)
            self.assertEqual(marked, 1)
            row = storage.get_proxy_by_key(key)
            self.assertFalse(row["available"])


class TestProxyMixinCandidates(unittest.TestCase):
    def test_get_candidates_for_test_basic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            for i in range(3):
                storage.upsert_proxy(_make_node(host=f"10.0.0.{i}"))
            rows = storage.get_candidates_for_test(limit=2)
            self.assertEqual(len(rows), 2)

    def test_get_candidates_limit_zero_means_all(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            for i in range(5):
                storage.upsert_proxy(_make_node(host=f"10.0.0.{i}"))
            rows = storage.get_candidates_for_test(limit=0)
            self.assertEqual(len(rows), 5)

    def test_get_candidates_only_unchecked(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            rows = storage.get_candidates_for_test(limit=0, only_unchecked=True)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["host"], "2.2.2.2")

    def test_get_candidates_only_available(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            rows = storage.get_candidates_for_test(limit=0, only_available=True)
            self.assertEqual(len(rows), 1)

    def test_get_candidates_only_direct(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100,
                                       fallback_front_keys=["front"])
            storage.update_test_result(n2.normalized_key(), available=True, latency_ms=100,
                                       fallback_front_keys=[])
            rows = storage.get_candidates_for_test(limit=0, only_direct=True)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["host"], "2.2.2.2")

    def test_get_candidates_only_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=False, latency_ms=None)
            rows = storage.get_candidates_for_test(limit=0, only_unavailable=True)
            self.assertEqual(len(rows), 1)

    def test_get_candidates_min_age(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=False, latency_ms=None)
            storage.update_test_result(n2.normalized_key(), available=False, latency_ms=None)
            now = datetime.now(UTC)
            with storage._connect() as conn:
                conn.execute(
                    "UPDATE proxies SET last_checked_at = ? WHERE normalized_key = ?",
                    ((now - timedelta(days=2)).isoformat(), n1.normalized_key()),
                )
                conn.execute(
                    "UPDATE proxies SET last_checked_at = ? WHERE normalized_key = ?",
                    ((now - timedelta(hours=2)).isoformat(), n2.normalized_key()),
                )
                conn.commit()
            rows = storage.get_candidates_for_test(
                limit=0, only_unavailable=True, min_last_checked_age_hours=24
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["host"], "1.1.1.1")

    def test_get_candidates_protocols_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            storage.upsert_proxy(_make_node(host="1.1.1.1", protocol="ss"))
            storage.upsert_proxy(_make_node(host="2.2.2.2", protocol="trojan"))
            rows = storage.get_candidates_for_test(limit=0, protocols=["ss"])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["protocol"], "ss")


class TestProxyMixinEdgeCases(unittest.TestCase):
    """Cover remaining branch misses in geo_countries, geo_location, and get_subscription_links."""

    def test_list_proxies_geo_countries_unknown_only(self) -> None:
        """geo_countries=["-"] -> only country='' (no concrete countries)."""
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            rows = storage.list_proxies_filtered(limit=10, geo_countries=["-"])
            self.assertEqual(len(rows), 1)

    def test_list_proxies_geo_countries_concrete_only(self) -> None:
        """geo_countries=["US"] -> only concrete, no unknown."""
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US")
            rows = storage.list_proxies_filtered(limit=10, geo_countries=["US"])
            self.assertEqual(len(rows), 1)

    def test_update_test_result_fallback_empty_strings(self) -> None:
        """All-blank fallback keys should result in empty clean list."""
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node()
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=100,
                                       fallback_front_keys=["", "  "])
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertEqual(row["fallback_front_keys"], [])

    def test_get_subscription_links_geo_countries_unknown_only(self) -> None:
        """get_subscription_links with geo_countries=["-"]"""
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            links = storage.get_subscription_links(only_available=True, geo_countries=["-"])
            self.assertEqual(len(links), 1)

    def test_get_subscription_links_geo_location_dash_country(self) -> None:
        """get_subscription_links with geo_location="-:NYC" """
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="", city="NYC")
            links = storage.get_subscription_links(only_available=True, geo_location="-:NYC")
            self.assertEqual(len(links), 1)

    def test_get_subscription_links_geo_location_dash_city(self) -> None:
        """get_subscription_links with geo_location="US:-" """
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US", city="")
            links = storage.get_subscription_links(only_available=True, geo_location="US:-")
            self.assertEqual(len(links), 1)

    def test_get_subscription_links_ip_purity_unchecked(self) -> None:
        """get_subscription_links with ip_purity_filter='unchecked'"""
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            links = storage.get_subscription_links(only_available=True, ip_purity_filter="unchecked")
            self.assertEqual(len(links), 1)


class TestProxyMixinQuery(unittest.TestCase):
    def test_get_proxies_by_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            rows = storage.get_proxies_by_keys([n1.normalized_key(), n2.normalized_key()])
            self.assertEqual(len(rows), 2)

    def test_get_proxies_by_keys_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            rows = storage.get_proxies_by_keys([])
            self.assertEqual(rows, [])

    def test_get_proxies_by_keys_dedup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            rows = storage.get_proxies_by_keys([n1.normalized_key(), n1.normalized_key()])
            self.assertEqual(len(rows), 1)

    def test_get_proxies_by_keys_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            rows = storage.get_proxies_by_keys(["nonexistent"])
            self.assertEqual(len(rows), 0)

    def test_get_proxy_by_key_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.1.1.1")
            storage.upsert_proxy(node)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertIsNotNone(row)
            self.assertEqual(row["host"], "1.1.1.1")

    def test_get_proxy_by_key_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            row = storage.get_proxy_by_key("nonexistent")
            self.assertIsNone(row)

    def test_count_by_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            storage.upsert_proxy(_make_node(host="1.1.1.1", protocol="ss"))
            storage.upsert_proxy(_make_node(host="2.2.2.2", protocol="ss"))
            storage.upsert_proxy(_make_node(host="3.3.3.3", protocol="trojan"))
            counts = storage.count_by_protocol()
            self.assertEqual(counts["ss"], 2)
            self.assertEqual(counts["trojan"], 1)

    def test_list_geo_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            # Give n1 full geo AND ip_purity so it's fully resolved
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US", city="LA")
            storage.update_ip_purity(n1.normalized_key(), score=0.5, level="家宽")
            # n1 is fully resolved, n2 still needs geo
            rows = storage.list_geo_candidates(limit=10)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["host"], "2.2.2.2")

    def test_list_geo_candidates_only_available(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            rows = storage.list_geo_candidates(limit=10, only_available=True)
            self.assertEqual(len(rows), 1)

    def test_list_geo_candidates_only_tested(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            rows = storage.list_geo_candidates(limit=10, only_tested=True)
            self.assertEqual(len(rows), 1)

    def test_list_geo_candidates_limit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            for i in range(3):
                storage.upsert_proxy(_make_node(host=f"10.0.0.{i}"))
            rows = storage.list_geo_candidates(limit=0)
            self.assertEqual(len(rows), 3)

    def test_list_ip_purity_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_ip_purity(n1.normalized_key(), score=0.5, level="家宽")
            rows = storage.list_ip_purity_candidates(limit=0, only_unchecked=True)
            self.assertEqual(len(rows), 0)

    def test_list_ip_purity_candidates_all(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            for i in range(3):
                storage.upsert_proxy(_make_node(host=f"10.0.0.{i}"))
            rows = storage.list_ip_purity_candidates(limit=0)
            self.assertEqual(len(rows), 3)

    def test_list_ip_purity_candidates_only_available(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            rows = storage.list_ip_purity_candidates(limit=0, only_available=True)
            self.assertEqual(len(rows), 1)

    def test_list_ip_purity_candidates_only_tested(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            rows = storage.list_ip_purity_candidates(limit=0, only_tested=True)
            self.assertEqual(len(rows), 1)

    def test_list_ip_purity_candidates_limit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            for i in range(5):
                storage.upsert_proxy(_make_node(host=f"10.0.0.{i}"))
            rows = storage.list_ip_purity_candidates(limit=2)
            self.assertEqual(len(rows), 2)

    def test_get_stats_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            stats = storage.get_stats()
            self.assertEqual(stats["total"], 0)
            self.assertEqual(stats["available"], 0)

    def test_get_stats_with_proxies(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1", protocol="ss")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US")
            stats = storage.get_stats()
            self.assertEqual(stats["total"], 1)
            self.assertEqual(stats["available"], 1)
            self.assertEqual(stats["avg_latency_ms"], 100)
            self.assertIn("US", stats["by_country"])


class TestProxyMixinRowToDict(unittest.TestCase):
    def test_row_to_dict_fallback_not_list(self) -> None:
        """fallback_front_keys_json is not a list -> should be empty."""
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.1.1.1")
            storage.upsert_proxy(node)
            key = node.normalized_key()
            with storage._connect() as conn:
                conn.execute(
                    "UPDATE proxies SET fallback_front_keys_json = ? WHERE normalized_key = ?",
                    ('"not-a-list"', key),
                )
                conn.commit()
            row = storage.get_proxy_by_key(key)
            self.assertEqual(row["fallback_front_keys"], [])

    def test_row_to_dict_fallback_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.1.1.1")
            storage.upsert_proxy(node)
            key = node.normalized_key()
            with storage._connect() as conn:
                conn.execute(
                    "UPDATE proxies SET fallback_front_keys_json = ? WHERE normalized_key = ?",
                    ("not json", key),
                )
                conn.commit()
            row = storage.get_proxy_by_key(key)
            self.assertEqual(row["fallback_front_keys"], [])

    def test_row_to_dict_extra_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.1.1.1")
            storage.upsert_proxy(node)
            key = node.normalized_key()
            with storage._connect() as conn:
                conn.execute(
                    "UPDATE proxies SET extra_json = ? WHERE normalized_key = ?",
                    ("not json", key),
                )
                conn.commit()
            row = storage.get_proxy_by_key(key)
            self.assertEqual(row["extra"], {})

    def test_row_to_dict_success_rate_computed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.1.1.1")
            storage.upsert_proxy(node)
            storage.update_check_result(node.normalized_key(), success=True)
            storage.update_check_result(node.normalized_key(), success=True)
            storage.update_check_result(node.normalized_key(), success=False)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertAlmostEqual(row["success_rate"], 66.67, places=0)

    def test_row_to_dict_success_rate_none_when_no_checks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.1.1.1")
            storage.upsert_proxy(node)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertIsNone(row["success_rate"])

    def test_row_to_dict_openai_unlocked_none(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.1.1.1")
            storage.upsert_proxy(node)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertIsNone(row["openai_unlocked"])

    def test_row_to_dict_openai_unlocked_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.1.1.1")
            storage.upsert_proxy(node)
            storage.update_openai_result(node.normalized_key(), openai_unlocked=False)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertFalse(row["openai_unlocked"])

    def test_row_to_dict_fallback_empty_strings_filtered(self) -> None:
        """Blank/whitespace-only fallback keys should be stripped."""
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.1.1.1")
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=100,
                                       fallback_front_keys=["", "  ", "valid-key"])
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertEqual(row["fallback_front_keys"], ["valid-key"])


class TestProxyMixinGetSubscriptionLinks(unittest.TestCase):
    def test_get_subscription_links_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            links = storage.get_subscription_links(only_available=True)
            self.assertEqual(links, [])

    def test_get_subscription_links_returns_raw_link(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            node = _make_node(host="1.1.1.1")
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=100)
            links = storage.get_subscription_links(only_available=True)
            self.assertEqual(len(links), 1)
            self.assertIn("1.1.1.1", links[0])

    def test_get_subscription_links_protocol_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            storage.upsert_proxy(_make_node(host="1.1.1.1", protocol="ss"))
            storage.upsert_proxy(_make_node(host="2.2.2.2", protocol="trojan"))
            storage.update_test_result(_make_node(host="1.1.1.1").normalized_key(),
                                       available=True, latency_ms=100)
            storage.update_test_result(_make_node(host="2.2.2.2").normalized_key(),
                                       available=True, latency_ms=100)
            links = storage.get_subscription_links(only_available=True, protocol="ss")
            self.assertEqual(len(links), 1)

    def test_get_subscription_links_route_mode_filters(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=50,
                                       fallback_front_keys=[])
            storage.update_test_result(n2.normalized_key(), available=True, latency_ms=50,
                                       fallback_front_keys=["front"])
            links_direct = storage.get_subscription_links(route_mode_filter="direct")
            links_chain = storage.get_subscription_links(route_mode_filter="chain")
            links_unreachable = storage.get_subscription_links(route_mode_filter="unreachable")
            self.assertEqual(len(links_direct), 1)
            self.assertEqual(len(links_chain), 1)
            self.assertEqual(len(links_unreachable), 0)

    def test_get_subscription_links_geo_filters(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US", city="NYC")
            links = storage.get_subscription_links(only_available=True, geo_filter="has")
            self.assertEqual(len(links), 1)
            links_none = storage.get_subscription_links(only_available=True, geo_filter="none")
            self.assertEqual(len(links_none), 0)

    def test_get_subscription_links_source_keyword(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            storage.upsert_proxy(_make_node(host="1.1.1.1"), source="upload:file.txt")
            storage.update_test_result(_make_node(host="1.1.1.1").normalized_key(),
                                       available=True, latency_ms=100)
            links = storage.get_subscription_links(only_available=True, source_keyword="upload")
            self.assertEqual(len(links), 1)
            links_dash = storage.get_subscription_links(only_available=True, source_keyword="-")
            self.assertEqual(len(links_dash), 0)

    def test_get_subscription_links_openai_filters(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100,
                                       openai_unlocked=True)
            links = storage.get_subscription_links(only_available=True, openai_filter="unlocked")
            self.assertEqual(len(links), 1)
            links_blocked = storage.get_subscription_links(only_available=True, openai_filter="blocked")
            self.assertEqual(len(links_blocked), 0)
            links_unchecked = storage.get_subscription_links(only_available=True, openai_filter="unchecked")
            self.assertEqual(len(links_unchecked), 0)

    def test_get_subscription_links_ip_purity_filters(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            storage.update_ip_purity(n1.normalized_key(), score=0.9, level="家宽")
            links_checked = storage.get_subscription_links(only_available=True, ip_purity_filter="checked")
            self.assertEqual(len(links_checked), 1)
            links_residential = storage.get_subscription_links(only_available=True, ip_purity_filter="residential")
            self.assertEqual(len(links_residential), 1)
            links_non_residential = storage.get_subscription_links(only_available=True, ip_purity_filter="non_residential")
            self.assertEqual(len(links_non_residential), 0)
            links_unknown = storage.get_subscription_links(only_available=True, ip_purity_filter="unknown")
            self.assertEqual(len(links_unknown), 0)

    def test_get_subscription_links_fallback_front_filters(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100,
                                       fallback_front_keys=["front"])
            storage.update_test_result(n2.normalized_key(), available=True, latency_ms=100,
                                       fallback_front_keys=[])
            links_has = storage.get_subscription_links(only_available=True, fallback_front_filter="has")
            links_none = storage.get_subscription_links(only_available=True, fallback_front_filter="none")
            self.assertEqual(len(links_has), 1)
            self.assertEqual(len(links_none), 1)

    def test_get_subscription_links_available_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=False, latency_ms=None)
            # only_available=False just skips the "available=1" filter -> returns all
            links = storage.get_subscription_links(only_available=False)
            self.assertEqual(len(links), 1)
            # explicit available=False filters to unavailable only
            links_explicit = storage.get_subscription_links(available=False)
            self.assertEqual(len(links_explicit), 1)

    def test_get_subscription_links_geo_countries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            n2 = _make_node(host="2.2.2.2")
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            storage.update_test_result(n2.normalized_key(), available=True, latency_ms=100)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US")
            storage.update_geo(n2.normalized_key(), resolved_ip="2.2.2.2", country="JP")
            links = storage.get_subscription_links(only_available=True, geo_countries=["US"])
            self.assertEqual(len(links), 1)

    def test_get_subscription_links_geo_location(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US", city="NYC")
            links = storage.get_subscription_links(only_available=True, geo_location="US:NYC")
            self.assertEqual(len(links), 1)
            links_kw = storage.get_subscription_links(only_available=True, geo_location="US")
            self.assertEqual(len(links_kw), 1)

    def test_get_subscription_links_geo_country(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableProxyMixin(Path(td) / "db.sqlite3")
            n1 = _make_node(host="1.1.1.1")
            storage.upsert_proxy(n1)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100)
            storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US")
            links = storage.get_subscription_links(only_available=True, geo_country="US")
            self.assertEqual(len(links), 1)
            links_dash = storage.get_subscription_links(only_available=True, geo_country="-")
            self.assertEqual(len(links_dash), 0)


if __name__ == "__main__":
    unittest.main()
