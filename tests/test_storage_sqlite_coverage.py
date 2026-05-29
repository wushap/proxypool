"""Tests for proxypool.storage.sqlite — targeting uncovered lines."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

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
# Storage initialization
# ------------------------------------------------------------------ #

class TestStorageInit:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        db = tmp_path / "sub" / "db.sqlite3"
        s = SQLiteProxyStorage(db)
        assert db.exists()

    def test_init_existing_db_is_idempotent(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite3"
        s1 = SQLiteProxyStorage(db)
        s1.upsert_proxy(_make_node(host="10.0.0.1"))
        s2 = SQLiteProxyStorage(db)
        rows = s2.list_proxies()
        assert len(rows) == 1


# ------------------------------------------------------------------ #
# Proxy CRUD
# ------------------------------------------------------------------ #

class TestProxyCRUD:
    def test_upsert_insert_and_update(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="1.1.1.1")
        assert storage.upsert_proxy(n) == "inserted"
        assert storage.upsert_proxy(n) == "updated"

    def test_get_proxy_by_key_found_and_missing(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="2.2.2.2")
        storage.upsert_proxy(n)
        assert storage.get_proxy_by_key(n.normalized_key()) is not None
        assert storage.get_proxy_by_key("nonexistent") is None

    def test_list_proxies_and_list_proxies_filtered(self, storage: SQLiteProxyStorage) -> None:
        for i in range(3):
            storage.upsert_proxy(_make_node(host=f"10.0.0.{i}"))
        assert len(storage.list_proxies(limit=10)) == 3
        assert len(storage.list_proxies_filtered(limit=2)) == 2

    def test_get_proxies_by_keys(self, storage: SQLiteProxyStorage) -> None:
        n1 = _make_node(host="3.3.3.3")
        n2 = _make_node(host="4.4.4.4")
        storage.upsert_proxy(n1)
        storage.upsert_proxy(n2)
        result = storage.get_proxies_by_keys([n1.normalized_key(), n2.normalized_key()])
        assert len(result) == 2

    def test_get_proxies_by_keys_empty_and_dedup(self, storage: SQLiteProxyStorage) -> None:
        # Empty keys list
        assert storage.get_proxies_by_keys([]) == []
        # Duplicate keys
        n = _make_node(host="5.5.5.5")
        storage.upsert_proxy(n)
        result = storage.get_proxies_by_keys([n.normalized_key(), n.normalized_key()])
        assert len(result) == 1

    def test_delete_proxies_by_keys(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="6.6.6.6")
        storage.upsert_proxy(n)
        deleted = storage.delete_proxies_by_keys([n.normalized_key()])
        assert deleted == 1
        assert storage.get_proxy_by_key(n.normalized_key()) is None

    def test_delete_proxies_by_keys_empty(self, storage: SQLiteProxyStorage) -> None:
        assert storage.delete_proxies_by_keys([]) == 0

    def test_delete_unavailable(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="7.7.7.7")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=False, latency_ms=None, error="fail")
        assert storage.delete_unavailable() == 1

    def test_delete_stale_unavailable(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="8.8.8.8")
        storage.upsert_proxy(n)
        # Set high fail count
        for _ in range(25):
            storage.update_test_result(n.normalized_key(), available=False, latency_ms=None, error="fail")
        assert storage.delete_stale_unavailable(max_fail_count=20) == 1

    def test_count_by_protocol(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_proxy(_make_node(host="1.1.1.1", protocol="ss"))
        storage.upsert_proxy(_make_node(host="2.2.2.2", protocol="trojan"))
        counts = storage.count_by_protocol()
        assert counts.get("ss") == 1
        assert counts.get("trojan") == 1


# ------------------------------------------------------------------ #
# Test result updates
# ------------------------------------------------------------------ #

class TestUpdateResults:
    def test_update_test_result_available_and_unavailable(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.0.0.1")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_test_result(key, available=True, latency_ms=50)
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["available"] == 1
        assert row["latency_ms"] == 50
        assert row["fail_count"] == 0

        storage.update_test_result(key, available=False, latency_ms=None, error="timeout")
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["available"] == 0
        assert row["latency_ms"] is None
        assert row["fail_count"] == 1

    def test_update_test_result_with_fallback_keys(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.0.0.2")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_test_result(key, available=True, latency_ms=100, fallback_front_keys=["f1", "f2"])
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["fallback_front_keys"] == ["f1", "f2"]

    def test_update_test_result_with_empty_fallback_keys(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.0.0.3")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_test_result(key, available=True, latency_ms=80, fallback_front_keys=[])
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["fallback_front_keys"] == []

    def test_update_speed_test_result(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.0.0.4")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_speed_test_result(key, ok=True, speed_mbps=55.5)
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert float(row["speed_mbps"]) == 55.5

    def test_update_speed_test_result_not_ok(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.0.0.5")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_speed_test_result(key, ok=False)
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["speed_tested_at"] is not None

    def test_mark_unavailable_by_fail_count(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.0.0.6")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_test_result(key, available=True, latency_ms=50)
        # Manually set fail_count high while keeping available=1 to exercise the path
        with storage._connect() as conn:
            conn.execute(
                "UPDATE proxies SET fail_count = 6 WHERE normalized_key = ?",
                (key,),
            )
            conn.commit()
        marked = storage.mark_unavailable_by_fail_count(threshold=5)
        assert marked >= 1

    def test_update_check_result_success_and_failure(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.0.0.7")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_check_result(key, success=True)
        storage.update_check_result(key, success=True)
        storage.update_check_result(key, success=False)
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["success_count"] == 2
        assert row["total_checks"] == 3
        assert row["success_rate"] is not None

    def test_update_openai_result(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.0.0.8")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_openai_result(key, openai_unlocked=True, openai_status="ok")
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["openai_unlocked"] is True

    def test_update_ip_purity(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.0.0.9")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_ip_purity(key, score=0.95, level="residential")
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert float(row["ip_purity_score"]) == 0.95
        assert row["ip_purity_level"] == "residential"

    def test_update_geo(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.0.0.10")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_geo(key, resolved_ip="8.8.8.8", country="US", city="LA")
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["resolved_ip"] == "8.8.8.8"
        assert row["country"] == "US"
        assert row["city"] == "LA"


# ------------------------------------------------------------------ #
# list_proxies_filtered — filter branches
# ------------------------------------------------------------------ #

class TestFilterBranches:
    def _setup_proxies(self, storage: SQLiteProxyStorage) -> dict:
        n1 = _make_node(host="10.1.1.1", protocol="ss")
        n2 = _make_node(host="10.1.1.2", protocol="trojan")
        n3 = _make_node(host="10.1.1.3", protocol="ss")
        storage.upsert_proxy(n1, source="sourceA")
        storage.upsert_proxy(n2, source="sourceB")
        storage.upsert_proxy(n3, source="")
        storage.update_test_result(n1.normalized_key(), available=True, latency_ms=50)
        storage.update_test_result(n2.normalized_key(), available=True, latency_ms=100,
                                   fallback_front_keys=["front1"])
        storage.update_test_result(n3.normalized_key(), available=False, latency_ms=None, error="down")
        return {"n1": n1, "n2": n2, "n3": n3}

    def test_filter_by_protocol(self, storage: SQLiteProxyStorage) -> None:
        self._setup_proxies(storage)
        ss_rows = storage.list_proxies_filtered(protocol="ss")
        assert all(r["protocol"] == "ss" for r in ss_rows)

    def test_filter_route_mode_direct(self, storage: SQLiteProxyStorage) -> None:
        self._setup_proxies(storage)
        rows = storage.list_proxies_filtered(route_mode_filter="direct")
        assert len(rows) == 1  # only n1: available + no fallback

    def test_filter_route_mode_chain(self, storage: SQLiteProxyStorage) -> None:
        self._setup_proxies(storage)
        rows = storage.list_proxies_filtered(route_mode_filter="chain")
        assert len(rows) == 1  # only n2

    def test_filter_route_mode_unreachable(self, storage: SQLiteProxyStorage) -> None:
        self._setup_proxies(storage)
        rows = storage.list_proxies_filtered(route_mode_filter="unreachable")
        assert len(rows) == 1  # n3

    def test_filter_source_keyword(self, storage: SQLiteProxyStorage) -> None:
        self._setup_proxies(storage)
        rows = storage.list_proxies_filtered(source_keyword="sourceA")
        assert len(rows) == 1
        rows_neg = storage.list_proxies_filtered(source_keyword="-")
        assert len(rows_neg) == 1  # only n3 with empty source

    def test_filter_geo_filter(self, storage: SQLiteProxyStorage) -> None:
        n_geo = _make_node(host="10.2.1.1")
        storage.upsert_proxy(n_geo)
        storage.update_geo(n_geo.normalized_key(), resolved_ip="1.1.1.1", country="JP", city="Tokyo")
        n_plain = _make_node(host="10.2.1.2")
        storage.upsert_proxy(n_plain)
        has = storage.list_proxies_filtered(geo_filter="has")
        assert len(has) == 1
        none_rows = storage.list_proxies_filtered(geo_filter="none")
        assert len(none_rows) == 1

    def test_filter_geo_countries(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.3.1.1")
        storage.upsert_proxy(n)
        storage.update_geo(n.normalized_key(), resolved_ip="1.1.1.1", country="US")
        rows = storage.list_proxies_filtered(geo_countries=["US"])
        assert len(rows) == 1
        # Include unknown
        n2 = _make_node(host="10.3.1.2")
        storage.upsert_proxy(n2)
        rows2 = storage.list_proxies_filtered(geo_countries=["US", "-"])
        assert len(rows2) == 2

    def test_filter_geo_location_colon_format(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.4.1.1")
        storage.upsert_proxy(n)
        storage.update_geo(n.normalized_key(), resolved_ip="1.1.1.1", country="DE", city="Berlin")
        rows = storage.list_proxies_filtered(geo_location="DE:Berlin")
        assert len(rows) == 1
        # With dash for country means country='' AND city='Berlin'
        n2 = _make_node(host="10.4.1.2")
        storage.upsert_proxy(n2)
        storage.update_geo(n2.normalized_key(), resolved_ip="2.2.2.2", country="", city="Berlin")
        rows2 = storage.list_proxies_filtered(geo_location="-:Berlin")
        assert len(rows2) == 1

    def test_filter_geo_location_keyword(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.5.1.1")
        storage.upsert_proxy(n)
        storage.update_geo(n.normalized_key(), resolved_ip="1.1.1.1", country="FR", city="Paris")
        rows = storage.list_proxies_filtered(geo_location="FR")
        assert len(rows) == 1

    def test_filter_openai_unchecked(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.6.1.1")
        storage.upsert_proxy(n)
        rows = storage.list_proxies_filtered(openai_filter="unchecked")
        assert len(rows) == 1

    def test_filter_ip_purity_non_residential_and_unknown(self, storage: SQLiteProxyStorage) -> None:
        n1 = _make_node(host="10.7.1.1")
        n2 = _make_node(host="10.7.1.2")
        storage.upsert_proxy(n1)
        storage.upsert_proxy(n2)
        storage.update_ip_purity(n1.normalized_key(), score=0.5, level="非家宽")
        storage.update_ip_purity(n2.normalized_key(), score=0.3, level="未知")
        non_res = storage.list_proxies_filtered(ip_purity_filter="non_residential")
        assert len(non_res) == 1
        unknown = storage.list_proxies_filtered(ip_purity_filter="unknown")
        assert len(unknown) == 1

    def test_filter_exclude_keys(self, storage: SQLiteProxyStorage) -> None:
        n1 = _make_node(host="10.8.1.1")
        n2 = _make_node(host="10.8.1.2")
        storage.upsert_proxy(n1)
        storage.upsert_proxy(n2)
        rows = storage.list_proxies_filtered(exclude_keys={n1.normalized_key()})
        assert len(rows) == 1
        assert rows[0]["normalized_key"] == n2.normalized_key()

    def test_filter_latency_min_max(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.9.1.1")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=75)
        rows = storage.list_proxies_filtered(latency_min=50, latency_max=100)
        assert len(rows) == 1

    def test_filter_freshness_hours(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.10.1.1")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
        rows = storage.list_proxies_filtered(freshness_hours=1)
        assert len(rows) == 1

    def test_sort_by_speed(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.11.1.1")
        storage.upsert_proxy(n)
        storage.update_speed_test_result(n.normalized_key(), ok=True, speed_mbps=100.0)
        rows = storage.list_proxies_filtered(sort_by="speed")
        assert len(rows) >= 1

    def test_sort_by_fail_count(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.12.1.1")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
        rows = storage.list_proxies_filtered(sort_by="fail_count")
        assert len(rows) >= 1

    def test_sort_by_last_checked(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.13.1.1")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
        rows = storage.list_proxies_filtered(sort_by="last_checked")
        assert len(rows) >= 1

    def test_sort_by_success_rate(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.14.1.1")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
        rows = storage.list_proxies_filtered(sort_by="success_rate")
        assert len(rows) >= 1

    def test_sort_desc(self, storage: SQLiteProxyStorage) -> None:
        for i in range(3):
            n = _make_node(host=f"10.15.1.{i}")
            storage.upsert_proxy(n)
            storage.update_test_result(n.normalized_key(), available=True, latency_ms=50 + i * 10)
        rows = storage.list_proxies_filtered(sort_by="latency", sort_order="desc")
        assert len(rows) == 3

    def test_sort_by_bandwidth(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.16.1.1")
        storage.upsert_proxy(n)
        storage.update_speed_test_result(n.normalized_key(), ok=True, speed_mbps=50.0)
        rows = storage.list_proxies_filtered(sort_by="bandwidth")
        assert len(rows) >= 1

    def test_sort_unknown_key(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="10.17.1.1")
        storage.upsert_proxy(n)
        rows = storage.list_proxies_filtered(sort_by="unknown_field")
        assert len(rows) == 1


# ------------------------------------------------------------------ #
# get_candidates_for_test
# ------------------------------------------------------------------ #

class TestGetCandidates:
    def test_only_unchecked(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="20.0.0.1")
        storage.upsert_proxy(n)
        rows = storage.get_candidates_for_test(only_unchecked=True)
        assert len(rows) == 1

    def test_only_unchecked_with_min_age(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="20.0.0.2")
        storage.upsert_proxy(n)
        # min_last_checked_age_hours is only used when NOT only_unchecked
        rows = storage.get_candidates_for_test(limit=10, only_unchecked=True, min_last_checked_age_hours=1)
        assert len(rows) == 1

    def test_with_protocols_filter(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_proxy(_make_node(host="20.0.0.3", protocol="ss"))
        storage.upsert_proxy(_make_node(host="20.0.0.4", protocol="trojan"))
        rows = storage.get_candidates_for_test(limit=10, protocols=["ss"])
        assert len(rows) == 1
        assert rows[0]["protocol"] == "ss"

    def test_min_last_checked_age_hours(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="20.0.0.5")
        storage.upsert_proxy(n)
        # Set as checked recently
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
        rows_old = storage.get_candidates_for_test(min_last_checked_age_hours=9999)
        assert len(rows_old) == 0
        rows_all = storage.get_candidates_for_test(min_last_checked_age_hours=0)
        assert len(rows_all) == 1


# ------------------------------------------------------------------ #
# get_stats
# ------------------------------------------------------------------ #

class TestGetStats:
    def test_empty(self, storage: SQLiteProxyStorage) -> None:
        stats = storage.get_stats()
        assert stats["total"] == 0
        assert stats["available"] == 0
        assert stats["availability_rate"] == 0.0

    def test_with_proxies(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="30.0.0.1")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=100)
        storage.update_geo(n.normalized_key(), resolved_ip="1.1.1.1", country="US", city="NY")
        storage.update_ip_purity(n.normalized_key(), score=0.8, level="residential")
        storage.update_speed_test_result(n.normalized_key(), ok=True, speed_mbps=50.0)
        storage.update_openai_result(n.normalized_key(), openai_unlocked=True, openai_status="ok")
        stats = storage.get_stats()
        assert stats["total"] == 1
        assert stats["available"] == 1
        assert stats["avg_latency_ms"] == 100
        assert stats["by_country"].get("US") == 1
        assert stats["openai_unlocked"] == 1
        assert stats["by_purity"].get("residential") == 1
        assert float(stats["avg_speed_mbps"]) == 50.0


# ------------------------------------------------------------------ #
# App settings
# ------------------------------------------------------------------ #

class TestAppSettings:
    def test_get_set(self, storage: SQLiteProxyStorage) -> None:
        assert storage.get_app_setting("foo", "bar") == "bar"
        storage.set_app_setting("foo", "baz")
        assert storage.get_app_setting("foo") == "baz"

    def test_get_empty_key(self, storage: SQLiteProxyStorage) -> None:
        assert storage.get_app_setting("", "default") == "default"
        assert storage.get_app_setting("   ", "default") == "default"

    def test_set_empty_key_raises(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.set_app_setting("", "value")

    def test_subscription_update_proxy_key(self, storage: SQLiteProxyStorage) -> None:
        storage.set_subscription_update_proxy_key("key123")
        assert storage.get_subscription_update_proxy_key() == "key123"

    def test_backend_default_port_range(self, storage: SQLiteProxyStorage) -> None:
        result = storage.set_backend_default_port_range(1080, 2000)
        assert result == {"start": 1080, "end": 2000}
        assert storage.get_backend_default_port_range() == {"start": 1080, "end": 2000}

    def test_backend_default_port_range_invalid(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.set_backend_default_port_range(5000, 1000)

    def test_backend_default_port_range_non_numeric(self, storage: SQLiteProxyStorage) -> None:
        storage.set_app_setting("backend_default_port_start", "abc")
        storage.set_app_setting("backend_default_port_end", "xyz")
        result = storage.get_backend_default_port_range()
        assert result["start"] == 1081  # default
        assert result["end"] == 1180  # default

    def test_backend_default_listen(self, storage: SQLiteProxyStorage) -> None:
        storage.set_backend_default_listen("0.0.0.0")
        assert storage.get_backend_default_listen() == "0.0.0.0"

    def test_backend_default_listen_too_long(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.set_backend_default_listen("a" * 100)


# ------------------------------------------------------------------ #
# Proxy pool CRUD
# ------------------------------------------------------------------ #

class TestProxyPoolCRUD:
    def test_create_and_get(self, storage: SQLiteProxyStorage) -> None:
        pool = storage.create_proxy_pool(name="test-pool")
        assert pool["name"] == "test-pool"
        assert pool["id"] > 0
        fetched = storage.get_proxy_pool(pool["id"])
        assert fetched is not None
        assert fetched["name"] == "test-pool"

    def test_get_missing(self, storage: SQLiteProxyStorage) -> None:
        assert storage.get_proxy_pool(999) is None

    def test_list_proxy_pools(self, storage: SQLiteProxyStorage) -> None:
        storage.create_proxy_pool(name="p1")
        storage.create_proxy_pool(name="p2")
        assert len(storage.list_proxy_pools()) == 2

    def test_delete_proxy_pool(self, storage: SQLiteProxyStorage) -> None:
        pool = storage.create_proxy_pool(name="to-delete")
        assert storage.delete_proxy_pool(pool["id"]) == 1
        assert storage.get_proxy_pool(pool["id"]) is None

    def test_update_proxy_pool(self, storage: SQLiteProxyStorage) -> None:
        pool = storage.create_proxy_pool(name="original")
        updated = storage.update_proxy_pool(
            pool["id"],
            name="updated",
            filters={"available": "true"},
            listen="0.0.0.0:8080",
            inbound_type="socks5",
            chain_enabled=True,
            sticky_ttl_sec=7200,
            session_missing_action="LEAST",
            session_header_names=["X-Header"],
            session_query_param_names=["q"],
            gateway_path_prefix="/my-gw",
        )
        assert updated["name"] == "updated"
        assert updated["chain_enabled"] is True
        assert updated["sticky_ttl_sec"] == 7200
        assert updated["gateway_path_prefix"] == "/my-gw"

    def test_update_proxy_pool_no_changes(self, storage: SQLiteProxyStorage) -> None:
        pool = storage.create_proxy_pool(name="unchanged")
        result = storage.update_proxy_pool(pool["id"])
        assert result["name"] == "unchanged"

    def test_update_proxy_pool_missing(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.update_proxy_pool(999, name="x")

    def test_update_proxy_pool_status(self, storage: SQLiteProxyStorage) -> None:
        pool = storage.create_proxy_pool(name="status-test")
        storage.update_proxy_pool_status(pool["id"], status="running", last_synced_at="2024-01-01")
        updated = storage.get_proxy_pool(pool["id"])
        assert updated is not None
        assert updated["status"] == "running"

    def test_get_proxy_pool_by_gateway_prefix(self, storage: SQLiteProxyStorage) -> None:
        storage.create_proxy_pool(name="gw-pool", gateway_path_prefix="/my-api")
        result = storage.get_proxy_pool_by_gateway_prefix("/my-api")
        assert result is not None
        assert result["name"] == "gw-pool"
        # Empty prefix
        assert storage.get_proxy_pool_by_gateway_prefix("") is None

    def test_list_proxy_pool_candidates(self, storage: SQLiteProxyStorage) -> None:
        pool = storage.create_proxy_pool(name="cand-pool")
        n = _make_node(host="40.0.0.1")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
        candidates = storage.list_proxy_pool_candidates(pool["id"])
        assert len(candidates) >= 1

    def test_list_proxy_pool_candidates_missing_pool(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.list_proxy_pool_candidates(999)


# ------------------------------------------------------------------ #
# Proxy pools v2
# ------------------------------------------------------------------ #

class TestProxyPoolV2:
    def test_upsert_list_get_delete(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_proxy_pool_v2("pool-a", "front", ["regex1"])
        storage.upsert_proxy_pool_v2("pool-b", "exit", ["regex2", "regex3"])
        pools = storage.list_proxy_pools_v2()
        assert len(pools) == 2

        got = storage.get_proxy_pool_v2("pool-a")
        assert got is not None
        assert got["pool_type"] == "front"
        assert "regex1" in got["regex_filters"]

        assert storage.delete_proxy_pool_v2("pool-a") == 1
        assert storage.get_proxy_pool_v2("pool-a") is None

    def test_get_missing(self, storage: SQLiteProxyStorage) -> None:
        assert storage.get_proxy_pool_v2("nonexistent") is None

    def test_upsert_update(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_proxy_pool_v2("pool-x", "front", ["r1"])
        storage.upsert_proxy_pool_v2("pool-x", "exit", ["r2"])
        got = storage.get_proxy_pool_v2("pool-x")
        assert got is not None
        assert got["pool_type"] == "exit"


# ------------------------------------------------------------------ #
# Subscriptions
# ------------------------------------------------------------------ #

class TestSubscriptionsCRUD:
    def test_create_and_get(self, storage: SQLiteProxyStorage) -> None:
        sub = storage.create_subscription(name="sub1", url="https://example.com/sub1")
        assert sub["name"] == "sub1"
        fetched = storage.get_subscription(sub["id"])
        assert fetched is not None

    def test_get_by_url(self, storage: SQLiteProxyStorage) -> None:
        storage.create_subscription(name="s", url="https://example.com/x")
        found = storage.get_subscription_by_url("https://example.com/x")
        assert found is not None
        assert storage.get_subscription_by_url("") is None

    def test_update(self, storage: SQLiteProxyStorage) -> None:
        sub = storage.create_subscription(name="old", url="https://example.com/old")
        updated = storage.update_subscription(sub["id"], name="new", url="https://example.com/new")
        assert updated["name"] == "new"

    def test_update_empty_url_raises(self, storage: SQLiteProxyStorage) -> None:
        sub = storage.create_subscription(name="s", url="https://example.com/s")
        with pytest.raises(ValueError):
            storage.update_subscription(sub["id"], url="")

    def test_update_missing(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.update_subscription(999, name="x")

    def test_update_no_changes(self, storage: SQLiteProxyStorage) -> None:
        sub = storage.create_subscription(name="unchanged", url="https://example.com/unchanged")
        updated = storage.update_subscription(sub["id"])
        assert updated["name"] == "unchanged"

    def test_delete(self, storage: SQLiteProxyStorage) -> None:
        sub = storage.create_subscription(name="to-del", url="https://example.com/del")
        assert storage.delete_subscription(sub["id"]) == 1

    def test_list_enabled(self, storage: SQLiteProxyStorage) -> None:
        storage.create_subscription(name="enabled", url="https://example.com/en", enabled=True)
        storage.create_subscription(name="disabled", url="https://example.com/dis", enabled=False)
        enabled = storage.list_enabled_subscriptions()
        assert len(enabled) == 1
        assert enabled[0]["name"] == "enabled"

    def test_delete_unavailable_with_disabled(self, storage: SQLiteProxyStorage) -> None:
        storage.create_subscription(name="ok", url="https://example.com/ok")
        disabled = storage.create_subscription(name="dis", url="https://example.com/dis", enabled=False)
        storage.mark_subscription_result(disabled["id"], status="success")
        deleted = storage.delete_unavailable_subscriptions(include_disabled=True)
        assert deleted == 1

    def test_create_empty_url_raises(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.create_subscription(name="s", url="")


# ------------------------------------------------------------------ #
# Published subscriptions
# ------------------------------------------------------------------ #

class TestPublishedSubscriptions:
    def test_crud(self, storage: SQLiteProxyStorage) -> None:
        ps = storage.create_published_subscription(name="pub1")
        assert ps["name"] == "pub1"
        assert ps["id"] > 0

        fetched = storage.get_published_subscription(ps["id"])
        assert fetched is not None
        assert fetched["name"] == "pub1"

        updated = storage.update_published_subscription(ps["id"], name="pub2")
        assert updated["name"] == "pub2"

        listed = storage.list_published_subscriptions()
        assert len(listed) == 1

        assert storage.delete_published_subscription(ps["id"]) == 1

    def test_get_missing(self, storage: SQLiteProxyStorage) -> None:
        assert storage.get_published_subscription(999) is None

    def test_update_missing_raises(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.update_published_subscription(999, name="x")

    def test_get_links_missing_raises(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.get_published_subscription_links(999)

    def test_get_proxies_missing_raises(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.get_published_subscription_proxies(999)

    def test_get_links(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="50.0.0.1")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
        ps = storage.create_published_subscription(
            name="links-test", filters={"available": "true"}
        )
        links = storage.get_published_subscription_links(ps["id"])
        assert len(links) == 1

    def test_get_proxies(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="50.0.0.2")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
        ps = storage.create_published_subscription(
            name="proxies-test", filters={"available": "true"}
        )
        proxies = storage.get_published_subscription_proxies(ps["id"])
        assert len(proxies) == 1

    def test_update_with_format(self, storage: SQLiteProxyStorage) -> None:
        ps = storage.create_published_subscription(name="fmt")
        updated = storage.update_published_subscription(ps["id"], format="clash")
        assert updated["format"] == "clash"


# ------------------------------------------------------------------ #
# Backend instances
# ------------------------------------------------------------------ #

class TestBackendInstances:
    def test_upsert_and_list(self, storage: SQLiteProxyStorage) -> None:
        inst = storage.upsert_backend_instance(
            instance_id="inst-1",
            pid=100,
            config_file="/tmp/c.json",
            routes_file="/tmp/r.json",
            log_file="/tmp/l.log",
            listen="127.0.0.1",
            ports=[1080, 1081],
            status="running",
        )
        assert inst["instance_id"] == "inst-1"
        assert inst["ports"] == [1080, 1081]

        listed = storage.list_backend_instances()
        assert len(listed) == 1

    def test_upsert_update(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_backend_instance(
            instance_id="inst-2", pid=200,
            config_file="", routes_file="", log_file="",
            listen="127.0.0.1", ports=[], status="stopped",
        )
        updated = storage.upsert_backend_instance(
            instance_id="inst-2", pid=300,
            config_file="", routes_file="", log_file="",
            listen="0.0.0.0", ports=[9090], status="running",
        )
        assert updated["pid"] == 300
        assert updated["ports"] == [9090]

    def test_update_status(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_backend_instance(
            instance_id="inst-3", pid=400,
            config_file="", routes_file="", log_file="",
            listen="127.0.0.1", ports=[], status="running",
        )
        storage.update_backend_instance_status("inst-3", "stopped", pid=400, last_error="err")
        listed = storage.list_backend_instances()
        assert listed[0]["status"] == "stopped"

    def test_update_status_without_pid(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_backend_instance(
            instance_id="inst-4", pid=500,
            config_file="", routes_file="", log_file="",
            listen="127.0.0.1", ports=[], status="running",
        )
        storage.update_backend_instance_status("inst-4", "stopped")
        listed = storage.list_backend_instances()
        assert listed[0]["status"] == "stopped"

    def test_delete(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_backend_instance(
            instance_id="inst-5", pid=600,
            config_file="", routes_file="", log_file="",
            listen="127.0.0.1", ports=[], status="running",
        )
        assert storage.delete_backend_instance("inst-5") == 1
        assert storage.list_backend_instances() == []

    def test_upsert_empty_id(self, storage: SQLiteProxyStorage) -> None:
        inst = storage.upsert_backend_instance(
            instance_id="", pid=700,
            config_file="", routes_file="", log_file="",
            listen="127.0.0.1", ports=[], status="running",
        )
        assert inst["instance_id"] == "default"


# ------------------------------------------------------------------ #
# Chain egress instances
# ------------------------------------------------------------------ #

class TestChainEgressInstances:
    def _create(self, storage: SQLiteProxyStorage, pool_id: int = 1, eid: int = 0, iid: str = "ci-1"):
        return storage.upsert_chain_egress_instance(
            instance_id=iid, pool_id=pool_id, endpoint_id=eid,
            backend_type="mihomo", front_node_key="f1", exit_node_key="e1",
            hop_node_keys=["h1"], route_signature="sig", listen="127.0.0.1",
            port=9090, inbound_type="http", status="running", pid=100,
            config_file="", log_file="", egress_ip="1.2.3.4",
        )

    def test_upsert_and_get(self, storage: SQLiteProxyStorage) -> None:
        inst = self._create(storage)
        assert inst["instance_id"] == "ci-1"
        got = storage.get_chain_egress_instance("ci-1")
        assert got is not None
        assert got["hop_node_keys"] == ["h1"]

    def test_get_missing(self, storage: SQLiteProxyStorage) -> None:
        assert storage.get_chain_egress_instance("missing") is None

    def test_list_all(self, storage: SQLiteProxyStorage) -> None:
        self._create(storage, iid="ci-a")
        self._create(storage, iid="ci-b")
        all_inst = storage.list_chain_egress_instances()
        assert len(all_inst) == 2

    def test_list_by_pool_id(self, storage: SQLiteProxyStorage) -> None:
        self._create(storage, pool_id=1, iid="ci-1a")
        self._create(storage, pool_id=2, iid="ci-2a")
        rows = storage.list_chain_egress_instances(pool_id=1)
        assert len(rows) == 1

    def test_list_by_endpoint_id(self, storage: SQLiteProxyStorage) -> None:
        self._create(storage, eid=0, iid="ci-e0")
        self._create(storage, eid=1, iid="ci-e1")
        rows = storage.list_chain_egress_instances(endpoint_id=1)
        assert len(rows) == 1

    def test_list_by_both(self, storage: SQLiteProxyStorage) -> None:
        self._create(storage, pool_id=1, eid=0, iid="ci-both-a")
        self._create(storage, pool_id=1, eid=1, iid="ci-both-b")
        rows = storage.list_chain_egress_instances(pool_id=1, endpoint_id=0)
        assert len(rows) == 1

    def test_delete(self, storage: SQLiteProxyStorage) -> None:
        self._create(storage, iid="ci-del")
        assert storage.delete_chain_egress_instance("ci-del") == 1


# ------------------------------------------------------------------ #
# Sticky leases
# ------------------------------------------------------------------ #

class TestStickyLeases:
    def test_upsert_and_get(self, storage: SQLiteProxyStorage) -> None:
        lease = storage.upsert_sticky_lease(
            session_id="s1", pool_id=1, endpoint_id=0,
            instance_id="inst", exit_node_key="en1",
            egress_ip="1.1.1.1", expires_at="2099-01-01T00:00:00",
            last_accessed="2024-01-01T00:00:00",
        )
        assert lease["session_id"] == "s1"
        got = storage.get_sticky_lease("s1", 1, 0)
        assert got is not None

    def test_list_all(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_sticky_lease(
            session_id="s1", pool_id=1, endpoint_id=0,
            instance_id="", exit_node_key="e1", egress_ip="1.1.1.1",
            expires_at="2099-01-01T00:00:00", last_accessed="2024-01-01T00:00:00",
        )
        assert len(storage.list_sticky_leases()) == 1

    def test_list_by_pool_and_endpoint(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_sticky_lease(
            session_id="s1", pool_id=1, endpoint_id=0,
            instance_id="", exit_node_key="e1", egress_ip="1.1.1.1",
            expires_at="2099-01-01T00:00:00", last_accessed="2024-01-01T00:00:00",
        )
        storage.upsert_sticky_lease(
            session_id="s2", pool_id=2, endpoint_id=1,
            instance_id="", exit_node_key="e2", egress_ip="2.2.2.2",
            expires_at="2099-01-01T00:00:00", last_accessed="2024-01-01T00:00:00",
        )
        by_pool = storage.list_sticky_leases(pool_id=1)
        assert len(by_pool) == 1
        by_endpoint = storage.list_sticky_leases(endpoint_id=1)
        assert len(by_endpoint) == 1
        by_both = storage.list_sticky_leases(pool_id=1, endpoint_id=0)
        assert len(by_both) == 1

    def test_delete(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_sticky_lease(
            session_id="s-del", pool_id=1, endpoint_id=0,
            instance_id="", exit_node_key="e1", egress_ip="1.1.1.1",
            expires_at="2099-01-01T00:00:00", last_accessed="2024-01-01T00:00:00",
        )
        assert storage.delete_sticky_lease("s-del", 1, 0) == 1

    def test_cleanup_expired(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_sticky_lease(
            session_id="s-exp", pool_id=1, endpoint_id=0,
            instance_id="", exit_node_key="e1", egress_ip="1.1.1.1",
            expires_at="2020-01-01T00:00:00", last_accessed="2020-01-01T00:00:00",
        )
        cleaned = storage.cleanup_expired_leases()
        assert cleaned == 1


# ------------------------------------------------------------------ #
# Pool session rules
# ------------------------------------------------------------------ #

class TestPoolSessionRules:
    def test_upsert_and_list(self, storage: SQLiteProxyStorage) -> None:
        rule = storage.upsert_pool_session_rule(1, "api", ["X-Token"])
        assert rule["url_prefix"] == "api"
        assert rule["headers"] == ["X-Token"]
        rules = storage.list_pool_session_rules(1)
        assert len(rules) == 1

    def test_upsert_empty_prefix_raises(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.upsert_pool_session_rule(1, "")

    def test_delete(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_pool_session_rule(1, "/del", [])
        assert storage.delete_pool_session_rule(1, "/del") == 1

    def test_upsert_update(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_pool_session_rule(1, "/upd", ["old"])
        storage.upsert_pool_session_rule(1, "/upd", ["new"])
        rules = storage.list_pool_session_rules(1)
        assert len(rules) == 1
        assert rules[0]["headers"] == ["new"]


# ------------------------------------------------------------------ #
# Failed routes
# ------------------------------------------------------------------ #

class TestFailedRoutes:
    def test_upsert_and_check(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_failed_route(1, "sig-1", "2099-01-01T00:00:00")
        assert storage.is_route_failed(1, "sig-1") is True
        assert storage.is_route_failed(1, "sig-2") is False

    def test_delete(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_failed_route(1, "sig-del", "2099-01-01T00:00:00")
        assert storage.delete_failed_route(1, "sig-del") == 1

    def test_list_active(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_failed_route(1, "sig-active", "2099-01-01T00:00:00")
        active = storage.list_active_failed_routes()
        assert len(active) == 1

    def test_cleanup_expired(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_failed_route(1, "sig-exp", "2020-01-01T00:00:00")
        cleaned = storage.cleanup_expired_failed_routes()
        assert cleaned == 1


# ------------------------------------------------------------------ #
# Failed route nodes
# ------------------------------------------------------------------ #

class TestFailedRouteNodes:
    def test_upsert_and_check(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_failed_route_node(1, "node-1", "2099-01-01T00:00:00")
        assert storage.is_route_node_failed(1, "node-1") is True
        assert storage.is_route_node_failed(1, "node-2") is False

    def test_delete(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_failed_route_node(1, "node-del", "2099-01-01T00:00:00")
        assert storage.delete_failed_route_node(1, "node-del") == 1

    def test_list_active(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_failed_route_node(1, "node-active", "2099-01-01T00:00:00")
        active = storage.list_active_failed_route_nodes()
        assert len(active) == 1

    def test_cleanup_expired(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_failed_route_node(1, "node-exp", "2020-01-01T00:00:00")
        cleaned = storage.cleanup_expired_failed_route_nodes()
        assert cleaned == 1


# ------------------------------------------------------------------ #
# HTTP proxy endpoints
# ------------------------------------------------------------------ #

class TestHTTPProxyEndpoints:
    def test_create_and_get(self, storage: SQLiteProxyStorage) -> None:
        ep = storage.create_http_proxy_endpoint(
            name="ep1", listen_host="0.0.0.0", listen_port=8080,
            session_header_names=["X-Forward-For"],
            connect_session_header_names=["X-Connect"],
        )
        assert ep["name"] == "ep1"
        assert ep["listen_port"] == 8080
        assert "X-Forward-For" in ep["session_header_names"]
        assert "X-Connect" in ep["connect_session_header_names"]
        fetched = storage.get_http_proxy_endpoint(ep["id"])
        assert fetched is not None

    def test_list(self, storage: SQLiteProxyStorage) -> None:
        storage.create_http_proxy_endpoint(name="ep-a")
        storage.create_http_proxy_endpoint(name="ep-b")
        assert len(storage.list_http_proxy_endpoints()) == 2

    def test_update(self, storage: SQLiteProxyStorage) -> None:
        ep = storage.create_http_proxy_endpoint(name="ep-upd")
        updated = storage.update_http_proxy_endpoint(
            ep["id"], name="ep-updated", listen_host="0.0.0.0",
            listen_port=9090, inbound_type="socks5", enabled=False,
            sticky_ttl_sec=1800, session_missing_action="LEAST",
            status="running", last_error="err",
            session_header_names=["H1"],
            session_query_param_names=["Q1"],
            connect_session_header_names=["C1"],
        )
        assert updated["name"] == "ep-updated"
        assert updated["listen_port"] == 9090
        assert updated["enabled"] is False

    def test_update_no_changes(self, storage: SQLiteProxyStorage) -> None:
        ep = storage.create_http_proxy_endpoint(name="ep-nc")
        result = storage.update_http_proxy_endpoint(ep["id"])
        assert result["name"] == "ep-nc"

    def test_update_missing(self, storage: SQLiteProxyStorage) -> None:
        with pytest.raises(ValueError):
            storage.update_http_proxy_endpoint(999, name="x")

    def test_delete(self, storage: SQLiteProxyStorage) -> None:
        ep = storage.create_http_proxy_endpoint(name="ep-del")
        assert storage.delete_http_proxy_endpoint(ep["id"]) == 1

    def test_replace_hops(self, storage: SQLiteProxyStorage) -> None:
        ep = storage.create_http_proxy_endpoint(name="ep-hops")
        hops = storage.replace_http_proxy_endpoint_hops(ep["id"], [1, 2, 3])
        assert len(hops) == 3
        assert hops[0]["hop_index"] == 0
        assert hops[0]["pool_id"] == 1

        # Replace with different set
        hops2 = storage.replace_http_proxy_endpoint_hops(ep["id"], [5])
        assert len(hops2) == 1
        assert hops2[0]["pool_id"] == 5


# ------------------------------------------------------------------ #
# Node health
# ------------------------------------------------------------------ #

class TestNodeHealth:
    def test_upsert_and_get(self, storage: SQLiteProxyStorage) -> None:
        health = storage.upsert_node_health("node-1", success=True, egress_ip="1.1.1.1", latency_ms=50)
        assert health["node_key"] == "node-1"
        assert health["failure_count"] == 0

    def test_upsert_failure_increments(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_node_health("node-2", success=False)
        h = storage.get_node_health("node-2")
        assert h is not None
        assert h["failure_count"] == 1

    def test_upsert_existing_success_resets(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_node_health("node-3", success=False)
        storage.upsert_node_health("node-3", success=False)
        storage.upsert_node_health("node-3", success=True)
        h = storage.get_node_health("node-3")
        assert h is not None
        assert h["failure_count"] == 0

    def test_list_and_delete(self, storage: SQLiteProxyStorage) -> None:
        storage.upsert_node_health("node-a", success=True)
        storage.upsert_node_health("node-b", success=True)
        assert len(storage.list_node_health()) == 2
        assert storage.delete_node_health("node-a") == 1
        assert len(storage.list_node_health()) == 1

    def test_get_missing(self, storage: SQLiteProxyStorage) -> None:
        assert storage.get_node_health("missing") is None


# ------------------------------------------------------------------ #
# get_subscription_links filter branches
# ------------------------------------------------------------------ #

class TestSubscriptionLinksFilters:
    def _setup(self, storage: SQLiteProxyStorage):
        n1 = _make_node(host="60.0.0.1", protocol="ss")
        n2 = _make_node(host="60.0.0.2", protocol="trojan")
        storage.upsert_proxy(n1, source="src1")
        storage.upsert_proxy(n2, source="src2")
        storage.update_test_result(n1.normalized_key(), available=True, latency_ms=50)
        storage.update_test_result(n2.normalized_key(), available=True, latency_ms=100,
                                   fallback_front_keys=["fk1"])
        storage.update_geo(n1.normalized_key(), resolved_ip="1.1.1.1", country="US", city="NY")
        storage.update_geo(n2.normalized_key(), resolved_ip="2.2.2.2", country="JP", city="Tokyo")
        storage.update_ip_purity(n1.normalized_key(), score=0.9, level="家宽")
        storage.update_openai_result(n1.normalized_key(), openai_unlocked=True, openai_status="ok")
        return n1, n2

    def test_only_available_false(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        links = storage.get_subscription_links(only_available=False)
        assert len(links) == 2

    def test_route_mode_direct(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        links = storage.get_subscription_links(route_mode_filter="direct")
        assert len(links) == 1

    def test_route_mode_chain(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        links = storage.get_subscription_links(route_mode_filter="chain")
        assert len(links) == 1

    def test_route_mode_unreachable(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        links = storage.get_subscription_links(route_mode_filter="unreachable")
        assert len(links) == 0

    def test_protocol_filter(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        links = storage.get_subscription_links(protocol="ss", only_available=False)
        assert len(links) == 1

    def test_source_keyword(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        links = storage.get_subscription_links(source_keyword="src1", only_available=False)
        assert len(links) == 1

    def test_source_keyword_dash(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        n3 = _make_node(host="60.0.0.3")
        storage.upsert_proxy(n3)
        links = storage.get_subscription_links(source_keyword="-", only_available=False)
        assert len(links) == 1

    def test_geo_filter_has_none(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        has = storage.get_subscription_links(geo_filter="has", only_available=False)
        assert len(has) == 2
        none_rows = storage.get_subscription_links(geo_filter="none", only_available=False)
        assert len(none_rows) == 0

    def test_geo_countries(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        links = storage.get_subscription_links(geo_countries=["US"], only_available=False)
        assert len(links) == 1

    def test_geo_country(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        links = storage.get_subscription_links(geo_country="JP", only_available=False)
        assert len(links) == 1

    def test_geo_country_dash(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        n3 = _make_node(host="60.0.0.3")
        storage.upsert_proxy(n3)
        links = storage.get_subscription_links(geo_country="-", only_available=False)
        assert len(links) == 1

    def test_geo_location_colon(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        links = storage.get_subscription_links(geo_location="US:NY", only_available=False)
        assert len(links) == 1

    def test_geo_location_colon_dash_country(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        # n2 has country="JP", city="Tokyo". "-:Tokyo" means country='' AND city='Tokyo'
        # That won't match n2. We need a proxy with empty country and city=Tokyo.
        n3 = _make_node(host="60.0.0.10")
        storage.upsert_proxy(n3)
        storage.update_geo(n3.normalized_key(), resolved_ip="3.3.3.3", country="", city="Tokyo")
        links = storage.get_subscription_links(geo_location="-:Tokyo", only_available=False)
        assert len(links) == 1

    def test_geo_location_keyword(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        links = storage.get_subscription_links(geo_location="JP", only_available=False)
        assert len(links) == 1

    def test_openai_filters(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        unlocked = storage.get_subscription_links(openai_filter="unlocked", only_available=False)
        assert len(unlocked) == 1
        blocked = storage.get_subscription_links(openai_filter="blocked", only_available=False)
        assert len(blocked) == 0
        unchecked = storage.get_subscription_links(openai_filter="unchecked", only_available=False)
        assert len(unchecked) == 1

    def test_ip_purity_filters(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        checked = storage.get_subscription_links(ip_purity_filter="checked", only_available=False)
        assert len(checked) == 1
        unchecked = storage.get_subscription_links(ip_purity_filter="unchecked", only_available=False)
        assert len(unchecked) == 1
        residential = storage.get_subscription_links(ip_purity_filter="residential", only_available=False)
        assert len(residential) == 1
        non_res = storage.get_subscription_links(ip_purity_filter="non_residential", only_available=False)
        assert len(non_res) == 0
        unknown = storage.get_subscription_links(ip_purity_filter="unknown", only_available=False)
        assert len(unknown) == 0

    def test_fallback_front_filters(self, storage: SQLiteProxyStorage) -> None:
        n1, n2 = self._setup(storage)
        has = storage.get_subscription_links(fallback_front_filter="has", only_available=False)
        assert len(has) == 1
        none_rows = storage.get_subscription_links(fallback_front_filter="none", only_available=False)
        assert len(none_rows) == 1


# ------------------------------------------------------------------ #
# list_geo_candidates and list_ip_purity_candidates
# ------------------------------------------------------------------ #

class TestGeoAndPurityCandidates:
    def test_list_geo_candidates(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="70.0.0.1")
        storage.upsert_proxy(n)
        candidates = storage.list_geo_candidates(limit=10)
        assert len(candidates) == 1

    def test_list_geo_candidates_only_available(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="70.0.0.2")
        storage.upsert_proxy(n)
        # Unavailable proxy should not show up
        rows = storage.list_geo_candidates(only_available=True)
        assert len(rows) == 0

    def test_list_geo_candidates_only_tested(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="70.0.0.3")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
        rows = storage.list_geo_candidates(only_tested=True)
        assert len(rows) == 1

    def test_list_ip_purity_candidates(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="71.0.0.1")
        storage.upsert_proxy(n)
        candidates = storage.list_ip_purity_candidates(limit=10)
        assert len(candidates) == 1

    def test_list_ip_purity_candidates_filters(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="71.0.0.2")
        storage.upsert_proxy(n)
        storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
        unchecked = storage.list_ip_purity_candidates(only_unchecked=True)
        assert len(unchecked) == 1
        available = storage.list_ip_purity_candidates(only_available=True)
        assert len(available) == 1
        tested = storage.list_ip_purity_candidates(only_tested=True)
        assert len(tested) == 1


# ------------------------------------------------------------------ #
# _row_to_dict edge cases
# ------------------------------------------------------------------ #

class TestRowToDict:
    def test_success_rate_calculation(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="80.0.0.1")
        storage.upsert_proxy(n)
        key = n.normalized_key()
        storage.update_check_result(key, success=True)
        storage.update_check_result(key, success=True)
        storage.update_check_result(key, success=False)
        row = storage.get_proxy_by_key(key)
        assert row is not None
        assert row["success_rate"] is not None
        assert abs(row["success_rate"] - 66.67) < 1

    def test_success_rate_no_checks(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="80.0.0.2")
        storage.upsert_proxy(n)
        row = storage.get_proxy_by_key(n.normalized_key())
        assert row is not None
        assert row["success_rate"] is None

    def test_openai_unlocked_none(self, storage: SQLiteProxyStorage) -> None:
        n = _make_node(host="80.0.0.3")
        storage.upsert_proxy(n)
        row = storage.get_proxy_by_key(n.normalized_key())
        assert row is not None
        assert row["openai_unlocked"] is None


# ------------------------------------------------------------------ #
# Backend process events
# ------------------------------------------------------------------ #

class TestBackendProcessEvents:
    def test_record_and_list(self, storage: SQLiteProxyStorage) -> None:
        storage.record_backend_process_event(
            backend="mihomo", action="start", pid=123,
            result="ok", detail="detail", config_file="/tmp/c.json",
        )
        events = storage.list_backend_process_events(limit=10)
        assert len(events) == 1
        assert events[0]["backend"] == "mihomo"
        assert events[0]["action"] == "start"


# ------------------------------------------------------------------ #
# Concurrency (basic smoke test)
# ------------------------------------------------------------------ #

class TestConcurrency:
    def test_concurrent_upserts(self, storage: SQLiteProxyStorage) -> None:
        import threading

        errors: list[Exception] = []

        def worker(i: int) -> None:
            try:
                n = _make_node(host=f"90.0.0.{i}")
                storage.upsert_proxy(n)
                storage.update_test_result(n.normalized_key(), available=True, latency_ms=50)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        rows = storage.list_proxies(limit=100)
        assert len(rows) == 20
