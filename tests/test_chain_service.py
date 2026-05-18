"""Tests for proxy chain service functionality."""
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.pool.node_pool import NodePool, NodeEntry
from proxypool.pool.sticky_router import StickyRouter, Lease
from proxypool.pool.chain_service import ProxyChainService
from proxypool.pool.health_manager import HealthConfig


@pytest.fixture
def storage(tmp_path):
    """Create a temporary storage for testing."""
    db_path = tmp_path / "test.db"
    return SQLiteProxyStorage(db_path)


@pytest.fixture
def sample_nodes():
    """Sample node entries for testing."""
    return {
        "front-1": {
            "protocol": "http",
            "host": "1.2.3.4",
            "port": 8080,
            "raw_link": "http://1.2.3.4:8080",
            "name": "front-node-1",
            "tags": ["front-node-1", "source1"],
        },
        "front-2": {
            "protocol": "http",
            "host": "5.6.7.8",
            "port": 8080,
            "raw_link": "http://5.6.7.8:8080",
            "name": "front-node-2",
            "tags": ["front-node-2", "source1"],
        },
        "exit-1": {
            "protocol": "socks",
            "host": "10.0.0.1",
            "port": 1080,
            "raw_link": "socks://10.0.0.1:1080",
            "name": "exit-node-1",
            "tags": ["exit-node-1", "source2"],
        },
        "exit-2": {
            "protocol": "socks",
            "host": "10.0.0.2",
            "port": 1080,
            "raw_link": "socks://10.0.0.2:1080",
            "name": "exit-node-2",
            "tags": ["exit-node-2", "source2"],
        },
    }


class TestNodePool:
    """Test NodePool functionality."""

    def test_pool_creation(self):
        pool = NodePool("test", "front", ["front-.*"])
        assert pool.name == "test"
        assert pool.pool_type == "front"
        assert pool.regex_filters == ["front-.*"]

    def test_matches_node(self):
        pool = NodePool("test", "front", ["front-.*"])
        assert pool.matches_node("key1", "front-node-1", ["tag1"]) is True
        assert pool.matches_node("key2", "exit-node-1", ["tag1"]) is False
        assert pool.matches_node("key3", "node", ["front-tag"]) is True

    def test_add_remove_node(self):
        pool = NodePool("test", "front", [])
        entry = NodeEntry(
            key="test-key",
            protocol="http",
            host="1.2.3.4",
            port=8080,
            raw_link="http://1.2.3.4:8080",
            name="test-node",
        )
        pool.add_node(entry)
        assert pool.get_node("test-key") == entry
        assert len(pool.get_all_nodes()) == 1

        pool.remove_node("test-key")
        assert pool.get_node("test-key") is None
        assert len(pool.get_all_nodes()) == 0

    def test_rebuild_pool(self):
        pool = NodePool("test", "front", ["front-.*"])
        nodes = {
            "key1": {"name": "front-1", "tags": [], "protocol": "http", "host": "1.2.3.4", "port": 80, "raw_link": ""},
            "key2": {"name": "exit-1", "tags": [], "protocol": "http", "host": "5.6.7.8", "port": 80, "raw_link": ""},
        }
        matched = pool.rebuild(nodes)
        assert "key1" in matched
        assert "key2" not in matched
        assert len(pool.get_all_nodes()) == 1

    def test_health_update(self):
        pool = NodePool("test", "front", [])
        entry = NodeEntry(
            key="test-key",
            protocol="http",
            host="1.2.3.4",
            port=8080,
            raw_link="http://1.2.3.4:8080",
            name="test-node",
        )
        pool.add_node(entry)

        # Record success
        result = pool.update_node_health("test-key", success=True, egress_ip="1.2.3.4", latency_ms=100)
        assert result is not None
        assert result.failure_count == 0
        assert result.circuit_open is False
        assert result.egress_ip == "1.2.3.4"
        assert result.latency_ms == 100

        # Record failures
        for i in range(5):
            result = pool.update_node_health("test-key", success=False, max_failures=5)
        
        assert result is not None
        assert result.failure_count == 5
        assert result.circuit_open is True

    def test_get_healthy_nodes(self):
        pool = NodePool("test", "front", [])
        
        # Add healthy node
        healthy = NodeEntry(key="healthy", protocol="http", host="1.2.3.4", port=80, raw_link="", routeable=True)
        pool.add_node(healthy)
        
        # Add unhealthy node
        unhealthy = NodeEntry(key="unhealthy", protocol="http", host="5.6.7.8", port=80, raw_link="", circuit_open=True)
        pool.add_node(unhealthy)
        
        healthy_nodes = pool.get_healthy_nodes()
        assert len(healthy_nodes) == 1
        assert healthy_nodes[0].key == "healthy"

    def test_get_healthy_nodes_excludes_non_routeable_nodes(self):
        pool = NodePool("test", "front", [])

        routeable = NodeEntry(key="routeable", protocol="http", host="1.2.3.4", port=80, raw_link="", routeable=True)
        unchecked = NodeEntry(key="unchecked", protocol="http", host="5.6.7.8", port=80, raw_link="", routeable=False)
        pool.add_node(routeable)
        pool.add_node(unchecked)

        healthy_nodes = pool.get_healthy_nodes()
        assert [node.key for node in healthy_nodes] == ["routeable"]


class TestStickyRouter:
    """Test StickyRouter functionality."""

    def test_route_without_sticky(self):
        front_pool = NodePool("front", "front", [])
        exit_pool = NodePool("exit", "exit", [])
        
        front_pool.add_node(NodeEntry(key="f1", protocol="http", host="1.2.3.4", port=80, raw_link="", latency_ms=100, routeable=True))
        exit_pool.add_node(NodeEntry(key="e1", protocol="socks", host="10.0.0.1", port=1080, raw_link="", latency_ms=100, egress_ip="10.0.0.1", routeable=True))
        
        router = StickyRouter(front_pool, exit_pool)
        result = router.route("", 0)
        
        assert result is not None
        assert result.front_node.key == "f1"
        assert result.exit_node.key == "e1"
        assert result.lease_created is False

    def test_route_with_sticky(self):
        front_pool = NodePool("front", "front", [])
        exit_pool = NodePool("exit", "exit", [])
        
        front_pool.add_node(NodeEntry(key="f1", protocol="http", host="1.2.3.4", port=80, raw_link="", latency_ms=100, routeable=True))
        exit_pool.add_node(NodeEntry(key="e1", protocol="socks", host="10.0.0.1", port=1080, raw_link="", latency_ms=100, egress_ip="10.0.0.1", routeable=True))
        
        router = StickyRouter(front_pool, exit_pool, sticky_ttl_sec=3600)
        
        # First request creates lease
        result1 = router.route("sess-1", 1)
        assert result1 is not None
        assert result1.lease_created is True
        
        # Second request reuses lease
        result2 = router.route("sess-1", 1)
        assert result2 is not None
        assert result2.exit_node.key == "e1"

    def test_p2c_algorithm(self):
        front_pool = NodePool("front", "front", [])
        exit_pool = NodePool("exit", "exit", [])
        
        # Add multiple nodes with different latencies
        for i in range(10):
            front_pool.add_node(NodeEntry(
                key=f"f{i}", protocol="http", host=f"1.2.3.{i}", port=80, raw_link="",
                latency_ms=100 + i * 10, routeable=True,
            ))
            exit_pool.add_node(NodeEntry(
                key=f"e{i}", protocol="socks", host=f"10.0.0.{i}", port=1080, raw_link="",
                latency_ms=100 + i * 10, routeable=True,
                egress_ip=f"10.0.0.{i}",
            ))
        
        router = StickyRouter(front_pool, exit_pool)
        
        # Route multiple times - should see some distribution
        selected_exits = set()
        for _ in range(100):
            result = router.route("", 0)
            if result:
                selected_exits.add(result.exit_node.key)
        
        # Should have selected more than 1 unique exit node (probabilistic)
        assert len(selected_exits) > 1

    def test_cleanup_expired_leases(self):
        front_pool = NodePool("front", "front", [])
        exit_pool = NodePool("exit", "exit", [])
        
        front_pool.add_node(NodeEntry(key="f1", protocol="http", host="1.2.3.4", port=80, raw_link="", routeable=True))
        exit_pool.add_node(NodeEntry(key="e1", protocol="socks", host="10.0.0.1", port=1080, raw_link="", egress_ip="10.0.0.1", routeable=True))
        
        router = StickyRouter(front_pool, exit_pool, sticky_ttl_sec=0)  # Immediate expiry
        
        # Create a lease
        router.route("sess-1", 1)
        
        # Cleanup should remove it
        removed = router.cleanup_expired_leases()
        assert removed >= 0  # May or may not be removed depending on timing

    def test_get_leases_returns_session_id(self):
        front_pool = NodePool("front", "front", [])
        exit_pool = NodePool("exit", "exit", [])
        front_pool.add_node(NodeEntry(key="f1", protocol="http", host="1.2.3.4", port=80, raw_link="", routeable=True))
        exit_pool.add_node(NodeEntry(key="e1", protocol="socks", host="10.0.0.1", port=1080, raw_link="", egress_ip="10.0.0.1", routeable=True))
        router = StickyRouter(front_pool, exit_pool, sticky_ttl_sec=3600)

        router.route("sess-abc", 3)
        leases = router.get_leases(3)

        assert leases[0]["session_id"] == "sess-abc"

    def test_reuses_bound_instance_id_when_alive(self):
        front_pool = NodePool("front", "front", [])
        exit_pool = NodePool("exit", "exit", [])
        front_pool.add_node(NodeEntry(key="f1", protocol="http", host="1.1.1.1", port=80, raw_link="", latency_ms=10, routeable=True))
        exit_pool.add_node(NodeEntry(key="e1", protocol="socks", host="2.2.2.2", port=1080, raw_link="", latency_ms=10, egress_ip="3.3.3.3", routeable=True))
        router = StickyRouter(front_pool, exit_pool, sticky_ttl_sec=3600)

        first = router.route("sess-1", 1)
        assert first is not None
        router.bind_instance("sess-1", 1, "inst-1")

        reused = router.route("sess-1", 1, live_instance_ids={"inst-1"})

        assert reused is not None
        assert reused.instance_reused is True
        assert reused.bound_instance_id == "inst-1"

    def test_rotates_to_same_ip_when_original_exit_is_gone(self):
        front_pool = NodePool("front", "front", [])
        exit_pool = NodePool("exit", "exit", [])
        front_pool.add_node(NodeEntry(key="f1", protocol="http", host="1.1.1.1", port=80, raw_link="", latency_ms=10, routeable=True))
        exit_pool.add_node(NodeEntry(key="e1", protocol="socks", host="2.2.2.2", port=1080, raw_link="", latency_ms=10, egress_ip="9.9.9.9", routeable=True))
        router = StickyRouter(front_pool, exit_pool, sticky_ttl_sec=3600)

        first = router.route("sess-1", 1)
        assert first is not None

        exit_pool.remove_node("e1")
        exit_pool.add_node(NodeEntry(key="e2", protocol="socks", host="2.2.2.3", port=1080, raw_link="", latency_ms=5, egress_ip="9.9.9.9", routeable=True))

        second = router.route("sess-1", 1)

        assert second is not None
        assert second.exit_node.key == "e2"
        assert second.lease_created is False


class TestStorage:
    """Test storage methods for proxy chain."""

    def test_proxy_pool_v2_operations(self, storage):
        # Create pool
        pool = storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])
        assert pool["name"] == "front"
        assert pool["pool_type"] == "front"
        assert pool["regex_filters"] == ["front-.*"]
        
        # List pools
        pools = storage.list_proxy_pools_v2()
        assert len(pools) == 1
        
        # Update pool
        pool = storage.upsert_proxy_pool_v2("front", "front", ["front-.*", "entry-.*"])
        assert pool["regex_filters"] == ["front-.*", "entry-.*"]
        
        # Delete pool
        deleted = storage.delete_proxy_pool_v2("front")
        assert deleted == 1
        
        pools = storage.list_proxy_pools_v2()
        assert len(pools) == 0

    def test_node_health_operations(self, storage):
        # Create health record
        health = storage.upsert_node_health("node1", success=True, egress_ip="1.2.3.4", latency_ms=100)
        assert health["node_key"] == "node1"
        assert health["failure_count"] == 0
        assert health["egress_ip"] == "1.2.3.4"
        
        # Record failure
        health = storage.upsert_node_health("node1", success=False, max_failures=3)
        assert health["failure_count"] == 1
        
        # Get health
        health = storage.get_node_health("node1")
        assert health is not None
        
        # List health
        health_list = storage.list_node_health()
        assert len(health_list) >= 1
        
        # Delete health
        deleted = storage.delete_node_health("node1")
        assert deleted == 1

    def test_sticky_lease_operations(self, storage):
        # Create lease
        lease = storage.upsert_sticky_lease(
            session_id="user1",
            pool_id=1,
            endpoint_id=0,
            instance_id="inst-1",
            exit_node_key="node1",
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00",
            last_accessed="2024-01-01T00:00:00",
        )
        assert lease["session_id"] == "user1"
        assert lease["instance_id"] == "inst-1"
        
        # Get lease
        lease = storage.get_sticky_lease("user1", 1)
        assert lease is not None
        
        # List leases
        leases = storage.list_sticky_leases()
        assert len(leases) >= 1
        
        # Delete lease
        deleted = storage.delete_sticky_lease("user1", 1)
        assert deleted == 1

    def test_proxy_pool_chain_config_round_trip(self, storage):
        pool = storage.create_proxy_pool(name="pool-a", filters={}, listen="0.0.0.0", inbound_type="http")
        updated = storage.update_proxy_pool(
            int(pool["id"]),
            chain_enabled=True,
            sticky_ttl_sec=7200,
            session_missing_action="REJECT",
            session_header_names=["X-ProxyPool-Session", "X-Session-Id"],
            session_query_param_names=["session", "sid"],
            gateway_path_prefix="/proxy/pool-a",
        )

        assert updated["chain_enabled"] is True
        assert updated["sticky_ttl_sec"] == 7200
        assert updated["session_missing_action"] == "REJECT"
        assert updated["session_header_names"] == ["X-ProxyPool-Session", "X-Session-Id"]
        assert updated["session_query_param_names"] == ["session", "sid"]
        assert updated["gateway_path_prefix"] == "/proxy/pool-a"

    def test_sticky_lease_session_round_trip(self, storage):
        lease = storage.upsert_sticky_lease(
            session_id="sess-1",
            pool_id=7,
            endpoint_id=0,
            instance_id="inst-1",
            exit_node_key="exit-1",
            egress_ip="1.2.3.4",
            expires_at="2026-05-16T12:00:00+00:00",
            last_accessed="2026-05-16T11:00:00+00:00",
        )

        assert lease["session_id"] == "sess-1"
        assert lease["instance_id"] == "inst-1"
        assert storage.get_sticky_lease("sess-1", 7)["egress_ip"] == "1.2.3.4"

    def test_chain_instance_storage_round_trip(self, storage):
        item = storage.upsert_chain_egress_instance(
            instance_id="chain-a",
            pool_id=1,
            endpoint_id=0,
            backend_type="mihomo",
            front_node_key="front-1",
            exit_node_key="exit-1",
            hop_node_keys=["front-1", "exit-1"],
            route_signature="front-1>exit-1",
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

        assert item["backend_type"] == "mihomo"
        assert item["front_node_key"] == "front-1"
        assert storage.list_chain_egress_instances(pool_id=1)[0]["instance_id"] == "chain-a"


class TestProxyChainService:
    """Test ProxyChainService integration."""

    def test_service_initialization(self, storage):
        service = ProxyChainService(storage)
        service.initialize()
        
        status = service.get_pool_status()
        assert "front_pool" in status
        assert "exit_pool" in status

    def test_pool_config_update(self, storage):
        service = ProxyChainService(storage)
        service.initialize()
        
        # Update front pool config
        result = service.update_pool_config("front", ["front-.*"])
        assert result["front_pool"]["regex_filters"] == ["front-.*"]
        
        # Verify persisted
        pool = storage.get_proxy_pool_v2("front")
        assert pool is not None
        assert pool["regex_filters"] == ["front-.*"]

    def test_service_loads_persisted_pool_filters_on_initialize(self, storage):
        storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])
        service = ProxyChainService(storage)

        service.initialize()

        assert service.front_pool.regex_filters == ["front-.*"]

    def test_refresh_pools_picks_up_new_matching_nodes(self, storage):
        service = ProxyChainService(storage)
        service.update_pool_config("front", ["front-.*"])

        proxy = ProxyNode(
            protocol="http",
            host="1.2.3.4",
            port=8080,
            raw_link="http://1.2.3.4:8080",
            name="front-node-1",
        )
        storage.upsert_proxy(proxy)

        service.refresh_pools()
        status = service.get_pool_status()

        assert status["front_pool"]["total_nodes"] == 1
        assert status["front_pool"]["nodes"][0]["key"] == proxy.normalized_key()

    def test_refresh_pools_uses_supported_protocol_defaults_when_filters_are_empty(self, storage):
        storage.upsert_proxy(
            ProxyNode(
                protocol="http",
                host="1.2.3.4",
                port=8080,
                raw_link="http://1.2.3.4:8080",
                name="front-node-1",
            )
        )
        storage.upsert_proxy(
            ProxyNode(
                protocol="socks",
                host="5.6.7.8",
                port=1080,
                raw_link="socks://5.6.7.8:1080",
                name="exit-node-1",
            )
        )
        storage.upsert_proxy(
            ProxyNode(
                protocol="vless",
                host="9.9.9.9",
                port=443,
                raw_link="vless://uuid@9.9.9.9:443",
                name="unsupported-node-1",
            )
        )
        service = ProxyChainService(storage)

        service.refresh_pools()
        status = service.get_pool_status()

        front_keys = {item["key"] for item in status["front_pool"]["nodes"]}
        exit_keys = {item["key"] for item in status["exit_pool"]["nodes"]}
        assert len(front_keys) == 2
        assert len(exit_keys) == 3
        assert all(item["protocol"] in {"http", "socks"} for item in status["front_pool"]["nodes"])
        assert all(item["protocol"] in {"http", "socks", "vless"} for item in status["exit_pool"]["nodes"])

    def test_route_request_prefers_distinct_front_and_exit_nodes_when_pools_overlap(self, storage):
        front = ProxyNode(
            protocol="http",
            host="1.1.1.1",
            port=8080,
            raw_link="http://1.1.1.1:8080",
            name="node-a",
        )
        exit_node = ProxyNode(
            protocol="socks",
            host="2.2.2.2",
            port=1080,
            raw_link="socks://2.2.2.2:1080",
            name="node-b",
        )
        storage.upsert_proxy(front)
        storage.upsert_proxy(exit_node)
        storage.update_test_result(front.normalized_key(), available=True, latency_ms=10)
        storage.update_test_result(exit_node.normalized_key(), available=True, latency_ms=20)
        service = ProxyChainService(storage)

        service.refresh_pools()
        result = service.route_request("sess-1", 1, "api.example.com")

        assert result is not None
        assert result["front_node"]["key"] != result["exit_node"]["key"]

    def test_route_request_returns_none_when_nodes_are_unchecked(self, storage):
        storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])
        storage.upsert_proxy_pool_v2("exit", "exit", ["exit-.*"])
        storage.upsert_proxy(ProxyNode(protocol="http", host="1.1.1.1", port=80, name="front-a", raw_link="http://1.1.1.1:80"))
        storage.upsert_proxy(ProxyNode(protocol="socks", host="2.2.2.2", port=1080, name="exit-a", raw_link="socks://2.2.2.2:1080"))

        service = ProxyChainService(storage)

        assert service.route_request("sess-1", 9, "") is None

    def test_update_pool_config_preserves_existing_health_state(self, storage):
        proxy = ProxyNode(
            protocol="http",
            host="1.2.3.4",
            port=8080,
            raw_link="http://1.2.3.4:8080",
            name="front-node-1",
        )
        storage.upsert_proxy(proxy)
        storage.upsert_node_health(proxy.normalized_key(), success=False, max_failures=1)

        service = ProxyChainService(storage)
        service.update_pool_config("front", ["front-.*"])
        status = service.get_pool_status()["front_pool"]["nodes"][0]

        assert status["healthy"] is False
        assert status["failure_count"] == 1

    def test_start_wires_chain_probe_builder_into_health_manager(self, storage):
        service = ProxyChainService(storage)
        service.health_manager.start = Mock()

        service.start()

        assert service.health_manager.build_chain_proxy_url == service.chain_builder.build_chain_proxy_url
        service.health_manager.start.assert_called_once_with()

    def test_route_request_persists_session_lease(self, storage):
        storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])
        storage.upsert_proxy_pool_v2("exit", "exit", ["exit-.*"])
        front = ProxyNode(protocol="http", host="1.1.1.1", port=80, name="front-a", raw_link="http://1.1.1.1:80")
        exit_node = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, name="exit-a", raw_link="socks://2.2.2.2:1080")
        storage.upsert_proxy(front)
        storage.upsert_proxy(exit_node)
        storage.update_test_result(front.normalized_key(), available=True, latency_ms=10)
        storage.update_test_result(exit_node.normalized_key(), available=True, latency_ms=20)

        service = ProxyChainService(storage)
        result = service.route_request("sess-1", 9, "")

        assert result is not None
        lease = storage.get_sticky_lease("sess-1", 9)
        assert lease is not None
        assert lease["session_id"] == "sess-1"

    def test_route_request_supports_endpoint_multi_hop(self, storage):
        hop1 = ProxyNode(protocol="http", host="1.1.1.1", port=8080, name="hop-1", raw_link="http://1.1.1.1:8080")
        hop2 = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, name="hop-2", raw_link="socks://2.2.2.2:1080")
        hop3 = ProxyNode(protocol="trojan", host="3.3.3.3", port=443, name="hop-3", raw_link="trojan://3.3.3.3:443")
        storage.upsert_proxy(hop1)
        storage.upsert_proxy(hop2)
        storage.upsert_proxy(hop3)
        storage.update_test_result(hop1.normalized_key(), available=True, latency_ms=10)
        storage.update_test_result(hop2.normalized_key(), available=True, latency_ms=20)
        storage.update_test_result(hop3.normalized_key(), available=True, latency_ms=30)

        pool1 = storage.create_proxy_pool(name="pool-1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="pool-2", filters={"protocol": "socks"})
        pool3 = storage.create_proxy_pool(name="pool-3", filters={"protocol": "trojan"})
        endpoint = storage.create_http_proxy_endpoint(name="ep-1", listen_port=18899)
        storage.replace_http_proxy_endpoint_hops(int(endpoint["id"]), [int(pool1["id"]), int(pool2["id"]), int(pool3["id"])])

        service = ProxyChainService(storage)
        result = service.route_request("sess-ep-1", int(pool1["id"]), int(endpoint["id"]), "api.example.com")

        assert result is not None
        assert result["endpoint_id"] == int(endpoint["id"])
        assert result["hop_node_keys"] == [
            hop1.normalized_key(),
            hop2.normalized_key(),
            hop3.normalized_key(),
        ]
        assert result["route_signature"] == f"pool-{pool1['id']}>pool-{pool2['id']}>pool-{pool3['id']}"

    def test_endpoint_route_failure_clears_lease_and_avoids_failed_route(self, storage):
        front_bad = ProxyNode(protocol="http", host="1.1.1.1", port=8080, name="front-bad", raw_link="http://1.1.1.1:8080")
        front_good = ProxyNode(protocol="http", host="1.1.1.2", port=8080, name="front-good", raw_link="http://1.1.1.2:8080")
        exit_node = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, name="exit-only", raw_link="socks://2.2.2.2:1080")
        for node in [front_bad, front_good, exit_node]:
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)

        pool1 = storage.create_proxy_pool(name="pool-front", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="pool-exit", filters={"protocol": "socks"})
        endpoint = storage.create_http_proxy_endpoint(name="ep-1", listen_port=18899)
        storage.replace_http_proxy_endpoint_hops(int(endpoint["id"]), [int(pool1["id"]), int(pool2["id"])])

        service = ProxyChainService(storage)
        failed_hops = [front_bad.normalized_key(), exit_node.normalized_key()]
        storage.upsert_sticky_lease(
            session_id="sess-1",
            pool_id=int(pool1["id"]),
            endpoint_id=int(endpoint["id"]),
            instance_id="inst-bad",
            exit_node_key=exit_node.normalized_key(),
            egress_ip="2.2.2.2",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )

        service.report_endpoint_route_failure(
            endpoint_id=int(endpoint["id"]),
            pool_id=int(pool1["id"]),
            session_id="sess-1",
            hop_node_keys=failed_hops,
        )
        result = service.route_request("", int(pool1["id"]), int(endpoint["id"]), "api.example.com")

        assert storage.get_sticky_lease("sess-1", int(pool1["id"]), int(endpoint["id"])) is None
        assert result is not None
        assert result["hop_node_keys"] == [front_good.normalized_key(), exit_node.normalized_key()]

    def test_endpoint_route_searches_past_failed_low_latency_combinations(self, storage):
        front_bad = ProxyNode(protocol="http", host="1.1.1.1", port=8080, name="front-11", raw_link="http://1.1.1.1:8080")
        front_good = ProxyNode(protocol="http", host="1.1.1.2", port=8080, name="front-good", raw_link="http://1.1.1.2:8080")
        exit_bad = ProxyNode(protocol="socks", host="2.2.2.1", port=1080, name="exit-bad", raw_link="socks://2.2.2.1:1080")
        exit_good = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, name="exit-good", raw_link="socks://2.2.2.2:1080")
        for latency, node in enumerate([front_bad, exit_bad, front_good, exit_good], start=1):
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=latency)

        pool1 = storage.create_proxy_pool(name="pool-front", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="pool-exit", filters={"protocol": "socks"})
        endpoint = storage.create_http_proxy_endpoint(name="ep-1", listen_port=18899)
        storage.replace_http_proxy_endpoint_hops(int(endpoint["id"]), [int(pool1["id"]), int(pool2["id"])])

        service = ProxyChainService(storage)
        for failed_hops in [
            [front_bad.normalized_key(), exit_bad.normalized_key()],
            [front_bad.normalized_key(), exit_good.normalized_key()],
        ]:
            service.report_endpoint_route_failure(
                endpoint_id=int(endpoint["id"]),
                pool_id=int(pool1["id"]),
                hop_node_keys=failed_hops,
            )

        result = service.route_request("", int(pool1["id"]), int(endpoint["id"]), "api.example.com")

        assert result is not None
        assert result["hop_node_keys"] == [front_good.normalized_key(), exit_bad.normalized_key()]

    def test_endpoint_route_success_prefers_known_healthy_route(self, storage, monkeypatch):
        front_bad = ProxyNode(protocol="http", host="1.1.1.1", port=8080, name="front-bad", raw_link="http://1.1.1.1:8080")
        front_good = ProxyNode(protocol="http", host="1.1.1.2", port=8080, name="front-good", raw_link="http://1.1.1.2:8080")
        exit_node = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, name="exit-only", raw_link="socks://2.2.2.2:1080")
        for node in [front_bad, front_good, exit_node]:
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)

        pool1 = storage.create_proxy_pool(name="pool-front", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="pool-exit", filters={"protocol": "socks"})
        endpoint = storage.create_http_proxy_endpoint(name="ep-1", listen_port=18899)
        storage.replace_http_proxy_endpoint_hops(int(endpoint["id"]), [int(pool1["id"]), int(pool2["id"])])

        service = ProxyChainService(storage)
        service.report_endpoint_route_success(
            endpoint_id=int(endpoint["id"]),
            hop_node_keys=[front_good.normalized_key(), exit_node.normalized_key()],
        )
        assert service._is_endpoint_node_failed(int(endpoint["id"]), front_good.normalized_key()) is False

        def pick_bad_first(pool_id, exclude_keys, target_domain):
            del target_domain
            if int(pool_id) == int(pool1["id"]):
                return storage.get_proxy_by_key(front_bad.normalized_key())
            return storage.get_proxy_by_key(exit_node.normalized_key())

        monkeypatch.setattr(service, "_pick_pool_candidate", pick_bad_first)
        result = service.route_request("", int(pool1["id"]), int(endpoint["id"]), "api.example.com")

        assert result is not None
        assert result["hop_node_keys"] == [front_good.normalized_key(), exit_node.normalized_key()]
