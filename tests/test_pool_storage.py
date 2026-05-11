from __future__ import annotations

from pathlib import Path

from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


def test_create_and_list_proxy_pool(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    pool = storage.create_proxy_pool(name="test-pool", filters={"available": "true", "protocol": "trojan"})
    assert pool["name"] == "test-pool"
    assert pool["status"] == "stopped"
    assert pool["filters"]["available"] == "true"
    assert pool["filters"]["protocol"] == "trojan"

    pools = storage.list_proxy_pools()
    assert len(pools) == 1
    assert pools[0]["id"] == pool["id"]


def test_update_proxy_pool(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    pool = storage.create_proxy_pool(name="old-name")
    updated = storage.update_proxy_pool(pool["id"], name="new-name", filters={"geo_country": "US"})
    assert updated["name"] == "new-name"
    assert updated["filters"]["geo_country"] == "US"


def test_delete_proxy_pool(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    pool = storage.create_proxy_pool(name="to-delete")
    deleted = storage.delete_proxy_pool(pool["id"])
    assert deleted == 1
    assert storage.get_proxy_pool(pool["id"]) is None


def test_update_proxy_pool_status(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    pool = storage.create_proxy_pool(name="status-test")
    storage.update_proxy_pool_status(pool["id"], "running", last_synced_at="2026-01-01T00:00:00")
    loaded = storage.get_proxy_pool(pool["id"])
    assert loaded["status"] == "running"
    assert loaded["last_synced_at"] == "2026-01-01T00:00:00"


def test_pool_filters_with_latency_and_freshness(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    pool = storage.create_proxy_pool(
        name="latency-pool",
        filters={"latency_min": "50", "latency_max": "500", "freshness_hours": "24"},
    )
    assert pool["filters"]["latency_min"] == "50"
    assert pool["filters"]["latency_max"] == "500"
    assert pool["filters"]["freshness_hours"] == "24"


def test_match_count_in_pool(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    proxy = ProxyNode(protocol="trojan", host="us.example.com", port=443, raw_link="trojan://us", extra={"password": "p"})
    storage.upsert_proxy(proxy)
    storage.update_test_result(proxy.normalized_key(), available=True, latency_ms=100)

    pool = storage.create_proxy_pool(name="count-pool", filters={"available": "true"})
    assert pool["match_count"] >= 1


def test_list_proxies_filtered_with_new_params(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    p1 = ProxyNode(protocol="trojan", host="a.example.com", port=443, raw_link="trojan://a", extra={"password": "p"})
    p2 = ProxyNode(protocol="trojan", host="b.example.com", port=443, raw_link="trojan://b", extra={"password": "p"})
    storage.upsert_proxy(p1)
    storage.upsert_proxy(p2)
    storage.update_test_result(p1.normalized_key(), available=True, latency_ms=50)
    storage.update_test_result(p2.normalized_key(), available=True, latency_ms=500)

    # latency filter
    results = storage.list_proxies_filtered(available=True, latency_max=200)
    keys = {r["normalized_key"] for r in results}
    assert p1.normalized_key() in keys
    assert p2.normalized_key() not in keys

    results = storage.list_proxies_filtered(available=True, latency_min=200)
    keys = {r["normalized_key"] for r in results}
    assert p2.normalized_key() in keys
    assert p1.normalized_key() not in keys

    # exclude_keys
    results = storage.list_proxies_filtered(available=True, exclude_keys={p1.normalized_key()})
    keys = {r["normalized_key"] for r in results}
    assert p1.normalized_key() not in keys
    assert p2.normalized_key() in keys


def test_published_subscription_id_stored(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    pool = storage.create_proxy_pool(name="linked-pool")
    updated = storage.update_proxy_pool(pool["id"], published_subscription_id=42, resin_subscription_id="sub-uuid", resin_platform_id="plat-uuid")
    assert updated["published_subscription_id"] == 42
    assert updated["resin_subscription_id"] == "sub-uuid"
    assert updated["resin_platform_id"] == "plat-uuid"
