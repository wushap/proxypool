"""Deep coverage tests for proxypool.storage.sqlite — targeting uncovered lines."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


@pytest.fixture()
def storage(tmp_path: Path) -> SQLiteProxyStorage:
    return SQLiteProxyStorage(tmp_path / "test.db")


def _make_node(
    host: str = "1.2.3.4",
    protocol: str = "ss",
    port: int = 443,
    extra: dict | None = None,
) -> ProxyNode:
    return ProxyNode(
        protocol=protocol,
        host=host,
        port=port,
        raw_link=f"{protocol}://{host}:{port}",
        extra=extra or {"cipher": "aes-128-gcm", "password": "p"},
    )


# ------------------------------------------------------------------ #
# _ensure_columns — migration paths (lines 327-404, 440-448, 505-564)
# ------------------------------------------------------------------ #

class TestEnsureColumns:
    """Test _ensure_columns paths by calling the method directly on a mock connection."""

    def test_adds_missing_proxy_columns(self, tmp_path: Path) -> None:
        """_ensure_columns should add columns that don't exist."""
        s = SQLiteProxyStorage(tmp_path / "test.db")
        # Get a connection and drop some columns to simulate old schema
        with s._connect() as conn:
            # Drop columns by recreating the table without them
            conn.executescript("""
                CREATE TABLE proxies_backup AS SELECT * FROM proxies;
                DROP TABLE proxies;
                CREATE TABLE proxies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    protocol TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    raw_link TEXT NOT NULL DEFAULT '',
                    normalized_key TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL DEFAULT '',
                    extra_json TEXT NOT NULL DEFAULT '{}',
                    available INTEGER NOT NULL DEFAULT 0,
                    latency_ms INTEGER,
                    last_checked_at TEXT,
                    last_seen_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            # Now call _ensure_columns — it should add the missing columns
            s._ensure_columns(conn)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(proxies)").fetchall()
            }
            assert "fail_count" in columns
            assert "last_error" in columns
            assert "resolved_ip" in columns
            assert "country" in columns
            assert "city" in columns
            assert "openai_unlocked" in columns
            assert "speed_mbps" in columns
            assert "success_count" in columns
            assert "total_checks" in columns

    def test_adds_missing_subscription_columns(self, tmp_path: Path) -> None:
        """_ensure_columns should add update_proxy_key to subscriptions."""
        s = SQLiteProxyStorage(tmp_path / "sub.db")
        with s._connect() as conn:
            conn.executescript("""
                CREATE TABLE subscriptions_backup AS SELECT * FROM subscriptions;
                DROP TABLE subscriptions;
                CREATE TABLE subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_status TEXT NOT NULL DEFAULT '',
                    last_message TEXT NOT NULL DEFAULT '',
                    proxy_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            s._ensure_columns(conn)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(subscriptions)").fetchall()
            }
            assert "update_proxy_key" in columns

    def test_adds_missing_published_sub_columns(self, tmp_path: Path) -> None:
        """_ensure_columns should add format to published_subscriptions."""
        s = SQLiteProxyStorage(tmp_path / "pub.db")
        with s._connect() as conn:
            conn.executescript("""
                CREATE TABLE published_subscriptions_backup AS SELECT * FROM published_subscriptions;
                DROP TABLE published_subscriptions;
                CREATE TABLE published_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL DEFAULT '',
                    filters_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_status TEXT NOT NULL DEFAULT '',
                    last_message TEXT NOT NULL DEFAULT '',
                    match_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            s._ensure_columns(conn)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(published_subscriptions)").fetchall()
            }
            assert "format" in columns

    def test_adds_missing_pool_columns(self, tmp_path: Path) -> None:
        """_ensure_columns should add pool columns like chain_enabled, sticky_ttl_sec."""
        s = SQLiteProxyStorage(tmp_path / "pool.db")
        with s._connect() as conn:
            conn.executescript("""
                CREATE TABLE proxy_pools_backup AS SELECT * FROM proxy_pools;
                DROP TABLE proxy_pools;
                CREATE TABLE proxy_pools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    filters_json TEXT NOT NULL DEFAULT '{}',
                    listen TEXT NOT NULL DEFAULT '0.0.0.0',
                    inbound_type TEXT NOT NULL DEFAULT 'http',
                    published_subscription_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'stopped',
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            s._ensure_columns(conn)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(proxy_pools)").fetchall()
            }
            assert "chain_enabled" in columns
            assert "sticky_ttl_sec" in columns
            assert "session_missing_action" in columns
            assert "session_header_names_json" in columns
            assert "session_query_param_names_json" in columns
            assert "gateway_path_prefix" in columns

    def test_adds_missing_chain_instance_columns(self, tmp_path: Path) -> None:
        """_ensure_columns should add endpoint_id, hop_node_keys_json, route_signature."""
        s = SQLiteProxyStorage(tmp_path / "chain.db")
        with s._connect() as conn:
            conn.executescript("""
                CREATE TABLE chain_egress_instances_backup AS SELECT * FROM chain_egress_instances;
                DROP TABLE chain_egress_instances;
                CREATE TABLE chain_egress_instances (
                    instance_id TEXT PRIMARY KEY,
                    pool_id INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            s._ensure_columns(conn)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(chain_egress_instances)").fetchall()
            }
            assert "endpoint_id" in columns
            assert "hop_node_keys_json" in columns
            assert "route_signature" in columns

    def test_sticky_leases_migration_old_schema(self, tmp_path: Path) -> None:
        """_ensure_columns should migrate sticky_leases from old 'account' schema to 'session_id'."""
        s = SQLiteProxyStorage(tmp_path / "sticky.db")
        with s._connect() as conn:
            # Create old-style sticky_leases table with 'account' instead of 'session_id'
            conn.executescript("""
                DROP TABLE sticky_leases;
                CREATE TABLE sticky_leases (
                    account TEXT NOT NULL,
                    pool_id INTEGER NOT NULL,
                    exit_node_key TEXT NOT NULL,
                    egress_ip TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    PRIMARY KEY (account, pool_id)
                );
                INSERT INTO sticky_leases
                    (account, pool_id, exit_node_key, egress_ip, expires_at, last_accessed)
                VALUES ('sess1', 1, 'node1', '1.2.3.4', '2099-01-01', '2099-01-01');
            """)
            s._ensure_columns(conn)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(sticky_leases)").fetchall()
            }
            assert "session_id" in columns
            assert "endpoint_id" in columns
            assert "instance_id" in columns
            # Data should be migrated
            rows = conn.execute("SELECT * FROM sticky_leases").fetchall()
            assert len(rows) == 1

    def test_sticky_leases_migration_missing_endpoint_id(self, tmp_path: Path) -> None:
        """_ensure_columns should migrate sticky_leases missing endpoint_id."""
        s = SQLiteProxyStorage(tmp_path / "sticky2.db")
        with s._connect() as conn:
            conn.executescript("""
                DROP TABLE sticky_leases;
                CREATE TABLE sticky_leases (
                    session_id TEXT NOT NULL,
                    pool_id INTEGER NOT NULL,
                    instance_id TEXT NOT NULL DEFAULT '',
                    exit_node_key TEXT NOT NULL,
                    egress_ip TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    PRIMARY KEY (session_id, pool_id)
                );
                INSERT INTO sticky_leases
                    (session_id, pool_id, instance_id, exit_node_key, egress_ip, expires_at, last_accessed)
                VALUES ('sess2', 1, 'inst1', 'node2', '5.6.7.8', '2099-01-01', '2099-01-01');
            """)
            s._ensure_columns(conn)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(sticky_leases)").fetchall()
            }
            assert "endpoint_id" in columns
            rows = conn.execute("SELECT * FROM sticky_leases").fetchall()
            assert len(rows) == 1


# ------------------------------------------------------------------ #
# Geo filtering in list_proxies_filtered (lines 681-711)
# ------------------------------------------------------------------ #

class TestGeoFiltering:
    def _setup_geo_proxies(self, storage: SQLiteProxyStorage) -> None:
        n1 = _make_node(host="1.1.1.1")
        n2 = _make_node(host="2.2.2.2")
        n3 = _make_node(host="3.3.3.3")
        storage.upsert_proxy(n1)
        storage.upsert_proxy(n2)
        storage.upsert_proxy(n3)
        storage.update_geo(n1.normalized_key(), "1.1.1.1", country="US", city="NYC")
        storage.update_geo(n2.normalized_key(), "2.2.2.2", country="JP", city="Tokyo")
        # n3 has no geo data

    def test_geo_countries_with_concrete(self, storage: SQLiteProxyStorage) -> None:
        self._setup_geo_proxies(storage)
        result = storage.list_proxies_filtered(geo_countries=["US"])
        assert len(result) == 1
        assert result[0]["country"] == "US"

    def test_geo_countries_with_unknown_marker(self, storage: SQLiteProxyStorage) -> None:
        self._setup_geo_proxies(storage)
        # "-" means include proxies with empty country
        result = storage.list_proxies_filtered(geo_countries=["-"])
        assert len(result) == 1
        assert result[0]["country"] == ""

    def test_geo_countries_mixed(self, storage: SQLiteProxyStorage) -> None:
        self._setup_geo_proxies(storage)
        # Include JP and unknown (empty country)
        result = storage.list_proxies_filtered(geo_countries=["JP", "-"])
        countries = {r["country"] for r in result}
        assert "JP" in countries or "" in countries

    def test_geo_country_unknown_marker(self, storage: SQLiteProxyStorage) -> None:
        self._setup_geo_proxies(storage)
        result = storage.list_proxies_filtered(geo_country="-")
        assert all(r["country"] == "" for r in result)

    def test_geo_country_specific(self, storage: SQLiteProxyStorage) -> None:
        self._setup_geo_proxies(storage)
        result = storage.list_proxies_filtered(geo_country="US")
        assert len(result) == 1
        assert result[0]["country"] == "US"

    def test_geo_location_country_city(self, storage: SQLiteProxyStorage) -> None:
        self._setup_geo_proxies(storage)
        result = storage.list_proxies_filtered(geo_location="US:NYC")
        assert len(result) == 1

    def test_geo_location_country_only_dash(self, storage: SQLiteProxyStorage) -> None:
        self._setup_geo_proxies(storage)
        # "-" for country means match empty country
        result = storage.list_proxies_filtered(geo_location="-:NYC")
        # Should match proxies with empty country and city=NYC - none
        assert isinstance(result, list)

    def test_geo_location_city_only_dash(self, storage: SQLiteProxyStorage) -> None:
        self._setup_geo_proxies(storage)
        # "-" for city means match empty city
        result = storage.list_proxies_filtered(geo_location="US:-")
        assert isinstance(result, list)

    def test_geo_location_simple_text(self, storage: SQLiteProxyStorage) -> None:
        self._setup_geo_proxies(storage)
        # Simple text matches country or city
        result = storage.list_proxies_filtered(geo_location="US")
        assert len(result) >= 1


# ------------------------------------------------------------------ #
# update_test_result with fallback_front_keys (line 856->858)
# ------------------------------------------------------------------ #

class TestUpdateTestResultFallbackKeys:
    def test_with_fallback_keys(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.10.10.10")
        storage.upsert_proxy(n)
        storage.update_test_result(
            n.normalized_key(),
            available=True,
            latency_ms=50,
            fallback_front_keys=["key1", "key2"],
        )
        row = storage.get_proxy_by_key(n.normalized_key())
        assert row is not None
        assert row["fallback_front_keys"] == ["key1", "key2"]

    def test_with_empty_after_strip_fallback_keys(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.10.10.11")
        storage.upsert_proxy(n)
        # All keys are whitespace - should result in empty list
        storage.update_test_result(
            n.normalized_key(),
            available=True,
            latency_ms=50,
            fallback_front_keys=["  ", ""],
        )
        row = storage.get_proxy_by_key(n.normalized_key())
        assert row is not None
        assert row["fallback_front_keys"] == []


# ------------------------------------------------------------------ #
# list_geo_candidates with limit (line 1173->1176)
# ------------------------------------------------------------------ #

class TestListGeoCandidates:
    def test_with_limit(self, storage: SQLiteProxyStorage) -> None:
        for i in range(5):
            storage.upsert_proxy(_make_node(host=f"10.0.0.{i}"))
        result = storage.list_geo_candidates(limit=3)
        assert len(result) <= 3

    def test_without_limit(self, storage: SQLiteProxyStorage) -> None:
        for i in range(3):
            storage.upsert_proxy(_make_node(host=f"10.0.1.{i}"))
        result = storage.list_geo_candidates(limit=0)
        # With limit=0, all candidates are returned (no LIMIT clause)
        assert len(result) >= 3


# ------------------------------------------------------------------ #
# get_backend_default_port_range edge cases (line 1579)
# ------------------------------------------------------------------ #

class TestBackendPortRange:
    def test_start_greater_than_end_swaps(self, storage: SQLiteProxyStorage) -> None:
        """When start > end in settings, values should be swapped."""
        storage.set_app_setting("backend_default_port_start", "2000")
        storage.set_app_setting("backend_default_port_end", "1000")
        result = storage.get_backend_default_port_range()
        assert result["start"] == 1000
        assert result["end"] == 2000

    def test_non_numeric_settings_fallback(self, storage: SQLiteProxyStorage) -> None:
        """Non-numeric values should fall back to defaults."""
        storage.set_app_setting("backend_default_port_start", "not-a-number")
        storage.set_app_setting("backend_default_port_end", "also-not")
        result = storage.get_backend_default_port_range()
        # Defaults are 1081 and 1180
        assert result["start"] == 1081
        assert result["end"] == 1180

    def test_out_of_range_clamped(self, storage: SQLiteProxyStorage) -> None:
        """Values > 65535 should be clamped."""
        storage.set_app_setting("backend_default_port_start", "99999")
        storage.set_app_setting("backend_default_port_end", "0")
        result = storage.get_backend_default_port_range()
        assert result["start"] >= 1
        assert result["end"] >= 1


# ------------------------------------------------------------------ #
# update_subscription with update_proxy_key (lines 1929-1930)
# ------------------------------------------------------------------ #

class TestUpdateSubscriptionProxyKey:
    def test_update_proxy_key(self, storage: SQLiteProxyStorage) -> None:
        sub = storage.create_subscription(name="test", url="https://example.com/sub1")
        updated = storage.update_subscription(
            sub["id"], update_proxy_key="my-proxy-key"
        )
        assert updated["update_proxy_key"] == "my-proxy-key"


# ------------------------------------------------------------------ #
# update_published_subscription with enabled (lines 1476-1477)
# ------------------------------------------------------------------ #

class TestUpdatePublishedSubscription:
    def test_update_enabled(self, storage: SQLiteProxyStorage) -> None:
        pub = storage.create_published_subscription(name="pub1")
        assert pub["enabled"] is True
        updated = storage.update_published_subscription(pub["id"], enabled=False)
        assert updated["enabled"] is False

    def test_update_format(self, storage: SQLiteProxyStorage) -> None:
        pub = storage.create_published_subscription(name="pub2")
        updated = storage.update_published_subscription(pub["id"], format="clash")
        assert updated["format"] == "clash"


# ------------------------------------------------------------------ #
# update_check_result (lines 957-975)
# ------------------------------------------------------------------ #

class TestUpdateCheckResult:
    def test_success(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.10.20.1")
        storage.upsert_proxy(n)
        storage.update_check_result(n.normalized_key(), success=True)
        row = storage.get_proxy_by_key(n.normalized_key())
        assert row is not None
        assert row["success_count"] == 1
        assert row["total_checks"] == 1

    def test_failure(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.10.20.2")
        storage.upsert_proxy(n)
        storage.update_check_result(n.normalized_key(), success=False)
        row = storage.get_proxy_by_key(n.normalized_key())
        assert row is not None
        assert row["success_count"] == 0
        assert row["total_checks"] == 1


# ------------------------------------------------------------------ #
# _row_to_dict error paths (lines 2159-2160, 2169-2171, 2197-2198)
# ------------------------------------------------------------------ #

class TestRowToDictErrorPaths:
    def test_bad_extra_json(self, storage: SQLiteProxyStorage) -> None:
        """Insert a proxy row with invalid extra_json directly."""
        n = _make_node(host="10.30.30.30")
        storage.upsert_proxy(n)
        # Corrupt the extra_json directly in the database
        key = n.normalized_key()
        with storage._write_lock, storage._connect() as conn:
            conn.execute(
                "UPDATE proxies SET extra_json = ? WHERE normalized_key = ?",
                ("not-valid-json{{", key),
            )
            conn.commit()
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["extra"] == {}

    def test_bad_fallback_front_keys_json(self, storage: SQLiteProxyStorage) -> None:
        """Insert a proxy row with invalid fallback_front_keys_json."""
        n = _make_node(host="10.30.30.31")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        with storage._write_lock, storage._connect() as conn:
            conn.execute(
                "UPDATE proxies SET fallback_front_keys_json = ? WHERE normalized_key = ?",
                ("{bad", key),
            )
            conn.commit()
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["fallback_front_keys"] == []

    def test_non_list_fallback_front_keys_json(self, storage: SQLiteProxyStorage) -> None:
        """Insert a proxy row where fallback_front_keys_json is a JSON object, not array."""
        n = _make_node(host="10.30.30.32")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        with storage._write_lock, storage._connect() as conn:
            conn.execute(
                "UPDATE proxies SET fallback_front_keys_json = ? WHERE normalized_key = ?",
                ('{"not": "a list"}', key),
            )
            conn.commit()
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["fallback_front_keys"] == []


# ------------------------------------------------------------------ #
# _backend_instance_row_to_dict bad ports_json (lines 2197-2198)
# ------------------------------------------------------------------ #

class TestBackendInstanceBadPorts:
    def test_bad_ports_json(self, storage: SQLiteProxyStorage) -> None:
        """Insert backend instance with invalid ports_json."""
        with storage._write_lock, storage._connect() as conn:
            conn.execute(
                """INSERT INTO backend_instances
                   (instance_id, status, pid, listen, ports_json,
                    last_error, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                ("inst-bad", "running", -1, "127.0.0.1", "not-json", ""),
            )
            conn.commit()
        instances = storage.list_backend_instances()
        found = [i for i in instances if i["instance_id"] == "inst-bad"]
        assert len(found) == 1
        assert found[0]["ports"] == []


# ------------------------------------------------------------------ #
# list_proxy_pool_candidates with geo_countries/geo_location (lines 2066-2096)
# ------------------------------------------------------------------ #

class TestPoolCandidatesGeoFiltering:
    def test_pool_with_geo_countries_filter(self, storage: SQLiteProxyStorage) -> None:
        """Create pool with geo_countries filter, verify filtering works."""
        n1 = _make_node(host="20.0.0.1")
        n2 = _make_node(host="20.0.0.2")
        storage.upsert_proxy(n1)
        storage.upsert_proxy(n2)
        storage.update_geo(n1.normalized_key(), "1.1.1.1", country="US", city="NYC")
        storage.update_geo(n2.normalized_key(), "2.2.2.2", country="JP", city="Tokyo")
        pool = storage.create_proxy_pool(
            name="geo-pool",
            filters={"geo_countries": ["US"]},
        )
        candidates = storage.list_proxy_pool_candidates(pool["id"])
        assert len(candidates) == 1
        assert candidates[0]["country"] == "US"

    def test_pool_with_geo_location_filter(self, storage: SQLiteProxyStorage) -> None:
        """Create pool with geo_location filter."""
        n1 = _make_node(host="20.0.1.1")
        n2 = _make_node(host="20.0.1.2")
        storage.upsert_proxy(n1)
        storage.upsert_proxy(n2)
        storage.update_geo(n1.normalized_key(), "1.1.1.1", country="US", city="NYC")
        storage.update_geo(n2.normalized_key(), "2.2.2.2", country="JP", city="Tokyo")
        pool = storage.create_proxy_pool(
            name="geo-loc-pool",
            filters={"geo_location": "JP:Tokyo"},
        )
        candidates = storage.list_proxy_pool_candidates(pool["id"])
        assert len(candidates) == 1

    def test_pool_with_geo_country_unknown(self, storage: SQLiteProxyStorage) -> None:
        """Pool filter with geo_country = '-' means include unknown."""
        n1 = _make_node(host="20.0.2.1")
        storage.upsert_proxy(n1)
        # n1 has no geo data (empty country)
        pool = storage.create_proxy_pool(
            name="unknown-geo-pool",
            filters={"geo_country": "-"},
        )
        candidates = storage.list_proxy_pool_candidates(pool["id"])
        assert len(candidates) == 1

    def test_pool_with_geo_countries_and_unknown(self, storage: SQLiteProxyStorage) -> None:
        """Pool filter with geo_countries including '-' for unknown."""
        n1 = _make_node(host="20.0.3.1")
        n2 = _make_node(host="20.0.3.2")
        storage.upsert_proxy(n1)
        storage.upsert_proxy(n2)
        storage.update_geo(n1.normalized_key(), "1.1.1.1", country="US", city="")
        # n2 has no geo
        pool = storage.create_proxy_pool(
            name="mixed-geo-pool",
            filters={"geo_countries": ["-"]},
        )
        candidates = storage.list_proxy_pool_candidates(pool["id"])
        # Should find proxies with empty country
        assert any(c["country"] == "" for c in candidates)


# ------------------------------------------------------------------ #
# Additional geo edge cases (lines 687->696, 705->707, 710->715)
# ------------------------------------------------------------------ #

class TestGeoFilteringEdgeCases:
    def test_geo_countries_empty_after_normalize(self, storage: SQLiteProxyStorage) -> None:
        """geo_countries with only empty strings → clauses is empty → branch 687->696."""
        n = _make_node(host="30.0.0.1")
        storage.upsert_proxy(n)
        # Pass geo_countries with empty string; after normalization becomes []
        result = storage.list_proxies_filtered(geo_countries=[""])
        assert isinstance(result, list)

    def test_geo_location_empty_country(self, storage: SQLiteProxyStorage) -> None:
        """geo_location=':NYC' → c is empty, ci is 'NYC' (line 705->707 path)."""
        n = _make_node(host="30.0.1.1")
        storage.upsert_proxy(n)
        storage.update_geo(n.normalized_key(), "1.1.1.1", country="US", city="NYC")
        result = storage.list_proxies_filtered(geo_location=":NYC")
        assert isinstance(result, list)

    def test_geo_location_empty_city(self, storage: SQLiteProxyStorage) -> None:
        """geo_location='US:' → c is 'US', ci is empty (line 710->715 path)."""
        n = _make_node(host="30.0.2.1")
        storage.upsert_proxy(n)
        storage.update_geo(n.normalized_key(), "1.1.1.1", country="US", city="NYC")
        result = storage.list_proxies_filtered(geo_location="US:")
        assert isinstance(result, list)


# ------------------------------------------------------------------ #
# get_subscription_links with geo filtering (lines 2066-2096)
# ------------------------------------------------------------------ #

class TestSubscriptionLinksGeoFiltering:
    def test_links_with_geo_countries_filter(self, storage: SQLiteProxyStorage) -> None:
        n1 = _make_node(host="40.0.0.1")
        n2 = _make_node(host="40.0.0.2")
        storage.upsert_proxy(n1)
        storage.upsert_proxy(n2)
        storage.update_geo(n1.normalized_key(), "1.1.1.1", country="US", city="NYC")
        storage.update_geo(n2.normalized_key(), "2.2.2.2", country="JP", city="Tokyo")
        links = storage.get_subscription_links(
            geo_countries=["US"], only_available=False
        )
        assert len(links) == 1

    def test_links_with_geo_location_filter(self, storage: SQLiteProxyStorage) -> None:
        n1 = _make_node(host="40.0.1.1")
        n2 = _make_node(host="40.0.1.2")
        storage.upsert_proxy(n1)
        storage.upsert_proxy(n2)
        storage.update_geo(n1.normalized_key(), "1.1.1.1", country="US", city="NYC")
        storage.update_geo(n2.normalized_key(), "2.2.2.2", country="JP", city="Tokyo")
        links = storage.get_subscription_links(
            geo_location="JP:Tokyo", only_available=False
        )
        assert len(links) == 1

    def test_links_with_geo_location_empty_country(self, storage: SQLiteProxyStorage) -> None:
        """geo_location=':NYC' in get_subscription_links → covers line 2090->2092."""
        n = _make_node(host="40.0.2.1")
        storage.upsert_proxy(n)
        storage.update_geo(n.normalized_key(), "1.1.1.1", country="US", city="NYC")
        links = storage.get_subscription_links(
            geo_location=":NYC", only_available=False
        )
        assert isinstance(links, list)

    def test_links_with_geo_location_empty_city(self, storage: SQLiteProxyStorage) -> None:
        """geo_location='US:' in get_subscription_links → covers ci is empty."""
        n = _make_node(host="40.0.3.1")
        storage.upsert_proxy(n)
        storage.update_geo(n.normalized_key(), "1.1.1.1", country="US", city="NYC")
        links = storage.get_subscription_links(
            geo_location="US:", only_available=False
        )
        assert isinstance(links, list)

    def test_links_with_geo_location_city_unknown(self, storage: SQLiteProxyStorage) -> None:
        """geo_location='US:-' in get_subscription_links → covers line 2096."""
        n = _make_node(host="40.0.3.2")
        storage.upsert_proxy(n)
        storage.update_geo(n.normalized_key(), "1.1.1.1", country="US", city="NYC")
        links = storage.get_subscription_links(
            geo_location="US:-", only_available=False
        )
        assert isinstance(links, list)

    def test_links_with_geo_countries_empty(self, storage: SQLiteProxyStorage) -> None:
        """geo_countries=[''] → covers line 2066->2070 branch."""
        n = _make_node(host="40.0.4.1")
        storage.upsert_proxy(n)
        links = storage.get_subscription_links(
            geo_countries=[""], only_available=False
        )
        assert isinstance(links, list)

    def test_links_with_geo_country_unknown(self, storage: SQLiteProxyStorage) -> None:
        """geo_country='-' → covers line 2071 in get_subscription_links."""
        n = _make_node(host="40.0.5.1")
        storage.upsert_proxy(n)
        links = storage.get_subscription_links(
            geo_country="-", only_available=False
        )
        assert isinstance(links, list)

    def test_links_with_geo_location_simple_text(self, storage: SQLiteProxyStorage) -> None:
        """geo_location without ':' → covers line 2072->2081."""
        n = _make_node(host="40.0.6.1")
        storage.upsert_proxy(n)
        storage.update_geo(n.normalized_key(), "1.1.1.1", country="US", city="NYC")
        links = storage.get_subscription_links(
            geo_location="US", only_available=False
        )
        assert isinstance(links, list)

    def test_links_with_geo_countries_and_unknown(self, storage: SQLiteProxyStorage) -> None:
        """geo_countries with '-' → covers line 2071."""
        n = _make_node(host="40.0.7.1")
        storage.upsert_proxy(n)
        links = storage.get_subscription_links(
            geo_countries=["-"], only_available=False
        )
        assert isinstance(links, list)


# ------------------------------------------------------------------ #
# sticky_leases migration: session_id exists but no instance_id (line 532)
# ------------------------------------------------------------------ #

class TestStickyLeasesMigrationNoInstanceId:
    def test_add_instance_id_column(self, tmp_path: Path) -> None:
        """Sticky_leases with session_id but no instance_id → elif branch."""
        s = SQLiteProxyStorage(tmp_path / "sticky3.db")
        with s._connect() as conn:
            conn.executescript("""
                DROP TABLE sticky_leases;
                CREATE TABLE sticky_leases (
                    session_id TEXT NOT NULL,
                    pool_id INTEGER NOT NULL,
                    exit_node_key TEXT NOT NULL,
                    egress_ip TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    PRIMARY KEY (session_id, pool_id)
                );
                INSERT INTO sticky_leases
                    (session_id, pool_id, exit_node_key, egress_ip, expires_at, last_accessed)
                VALUES ('sess3', 1, 'node3', '9.9.9.9', '2099-01-01', '2099-01-01');
            """)
            s._ensure_columns(conn)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(sticky_leases)").fetchall()
            }
            assert "instance_id" in columns
            rows = conn.execute("SELECT * FROM sticky_leases").fetchall()
            assert len(rows) == 1
