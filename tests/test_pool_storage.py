from __future__ import annotations

from pathlib import Path

from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


def test_create_and_list_proxy_pool(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    pool = storage.create_proxy_pool(
        name="test-pool", filters={"available": "true", "protocol": "trojan"}
    )
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


def test_proxy_pool_supports_multiple_geo_countries(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    us = ProxyNode(
        protocol="trojan",
        host="us.example.com",
        port=443,
        raw_link="trojan://us",
        extra={"password": "p"},
    )
    jp = ProxyNode(
        protocol="trojan",
        host="jp.example.com",
        port=443,
        raw_link="trojan://jp",
        extra={"password": "p"},
    )
    de = ProxyNode(
        protocol="trojan",
        host="de.example.com",
        port=443,
        raw_link="trojan://de",
        extra={"password": "p"},
    )
    storage.upsert_proxy(us)
    storage.upsert_proxy(jp)
    storage.upsert_proxy(de)
    storage.update_geo(us.normalized_key(), resolved_ip="1.1.1.1", country="US", city="Los Angeles")
    storage.update_geo(jp.normalized_key(), resolved_ip="2.2.2.2", country="JP", city="Tokyo")
    storage.update_geo(de.normalized_key(), resolved_ip="3.3.3.3", country="DE", city="Berlin")
    storage.update_test_result(us.normalized_key(), available=True, latency_ms=50)
    storage.update_test_result(jp.normalized_key(), available=True, latency_ms=60)
    storage.update_test_result(de.normalized_key(), available=True, latency_ms=70)

    pool = storage.create_proxy_pool(name="multi-country", filters={"geo_countries": ["US", "JP"]})

    assert pool["filters"]["geo_countries"] == ["US", "JP"]
    assert pool["match_count"] == 2


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
    proxy = ProxyNode(
        protocol="trojan",
        host="us.example.com",
        port=443,
        raw_link="trojan://us",
        extra={"password": "p"},
    )
    storage.upsert_proxy(proxy)
    storage.update_test_result(proxy.normalized_key(), available=True, latency_ms=100)

    pool = storage.create_proxy_pool(name="count-pool", filters={"available": "true"})
    assert pool["match_count"] >= 1


def test_list_proxies_filtered_with_new_params(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    p1 = ProxyNode(
        protocol="trojan",
        host="a.example.com",
        port=443,
        raw_link="trojan://a",
        extra={"password": "p"},
    )
    p2 = ProxyNode(
        protocol="trojan",
        host="b.example.com",
        port=443,
        raw_link="trojan://b",
        extra={"password": "p"},
    )
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


def test_list_proxies_filtered_by_route_mode(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    direct = ProxyNode(
        protocol="trojan",
        host="direct.example.com",
        port=443,
        raw_link="trojan://direct",
        extra={"password": "p"},
    )
    chained = ProxyNode(
        protocol="trojan",
        host="chained.example.com",
        port=443,
        raw_link="trojan://chained",
        extra={"password": "p"},
    )
    down = ProxyNode(
        protocol="trojan",
        host="down.example.com",
        port=443,
        raw_link="trojan://down",
        extra={"password": "p"},
    )
    storage.upsert_proxy(direct)
    storage.upsert_proxy(chained)
    storage.upsert_proxy(down)
    storage.update_test_result(
        direct.normalized_key(), available=True, latency_ms=50, fallback_front_keys=[]
    )
    storage.update_test_result(
        chained.normalized_key(), available=True, latency_ms=60, fallback_front_keys=["front-a"]
    )
    storage.update_test_result(
        down.normalized_key(), available=False, latency_ms=None, error="down"
    )

    direct_rows = storage.list_proxies_filtered(limit=10, route_mode_filter="direct")
    chained_rows = storage.list_proxies_filtered(limit=10, route_mode_filter="chain")
    unreachable_rows = storage.list_proxies_filtered(limit=10, route_mode_filter="unreachable")

    assert [row["normalized_key"] for row in direct_rows] == [direct.normalized_key()]
    assert [row["normalized_key"] for row in chained_rows] == [chained.normalized_key()]
    assert [row["normalized_key"] for row in unreachable_rows] == [down.normalized_key()]


def test_proxy_pool_route_mode_filter_is_normalized_and_counted(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    direct = ProxyNode(
        protocol="trojan",
        host="direct.example.com",
        port=443,
        raw_link="trojan://direct",
        extra={"password": "p"},
    )
    chained = ProxyNode(
        protocol="trojan",
        host="chained.example.com",
        port=443,
        raw_link="trojan://chained",
        extra={"password": "p"},
    )
    storage.upsert_proxy(direct)
    storage.upsert_proxy(chained)
    storage.update_test_result(
        direct.normalized_key(), available=True, latency_ms=50, fallback_front_keys=[]
    )
    storage.update_test_result(
        chained.normalized_key(), available=True, latency_ms=60, fallback_front_keys=["front-a"]
    )

    pool = storage.create_proxy_pool(
        name="direct-only", filters={"route_mode_filter": "direct", "available": "true"}
    )

    assert pool["filters"]["route_mode_filter"] == "direct"
    assert "available" not in pool["filters"]
    assert pool["match_count"] == 1


def test_published_subscription_id_stored(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    pool = storage.create_proxy_pool(name="linked-pool")
    updated = storage.update_proxy_pool(pool["id"], published_subscription_id=42)
    assert updated["published_subscription_id"] == 42


def test_http_proxy_endpoint_and_hops_round_trip(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    pool1 = storage.create_proxy_pool(name="pool-1")
    pool2 = storage.create_proxy_pool(name="pool-2")
    endpoint = storage.create_http_proxy_endpoint(
        name="gateway-a",
        listen_host="127.0.0.1",
        listen_port=18899,
        enabled=True,
        sticky_ttl_sec=7200,
        session_header_names=["X-ProxyPool-Session"],
        session_query_param_names=["session"],
        connect_session_header_names=["X-ProxyPool-Session"],
    )

    hops = storage.replace_http_proxy_endpoint_hops(
        int(endpoint["id"]), [int(pool1["id"]), int(pool2["id"])]
    )
    loaded = storage.get_http_proxy_endpoint(int(endpoint["id"]))

    assert [item["pool_id"] for item in hops] == [int(pool1["id"]), int(pool2["id"])]
    assert loaded is not None
    assert loaded["listen_port"] == 18899
    assert loaded["session_header_names"] == ["X-ProxyPool-Session"]
    assert [item["pool_id"] for item in loaded["hops"]] == [int(pool1["id"]), int(pool2["id"])]


def test_chain_instance_storage_supports_multi_hop_signature(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    item = storage.upsert_chain_egress_instance(
        instance_id="chain-a",
        pool_id=1,
        endpoint_id=11,
        backend_type="mihomo",
        front_node_key="front-1",
        exit_node_key="exit-1",
        hop_node_keys=["front-1", "middle-1", "exit-1"],
        route_signature="pool-1>pool-3>pool-2",
        listen="127.0.0.1",
        port=18080,
        inbound_type="http",
        status="running",
        pid=4321,
        config_file="/tmp/mihomo-a.yaml",
        log_file="/tmp/mihomo-a.log",
        egress_ip="8.8.8.8",
        last_error="",
    )

    assert item["endpoint_id"] == 11
    assert item["hop_node_keys"] == ["front-1", "middle-1", "exit-1"]
    assert item["route_signature"] == "pool-1>pool-3>pool-2"


def test_sticky_lease_supports_endpoint_scope(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    lease = storage.upsert_sticky_lease(
        session_id="sess-1",
        pool_id=7,
        endpoint_id=9,
        instance_id="inst-1",
        exit_node_key="exit-1",
        egress_ip="1.2.3.4",
        expires_at="2026-05-16T12:00:00+00:00",
        last_accessed="2026-05-16T11:00:00+00:00",
    )

    assert lease["endpoint_id"] == 9
    assert storage.get_sticky_lease("sess-1", 7, 9)["instance_id"] == "inst-1"
    assert storage.get_sticky_lease("sess-1", 7, 0) is None
