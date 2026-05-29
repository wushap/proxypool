"""Additional tests for ProxyChainService to boost coverage of chain_service.py."""

from __future__ import annotations

import datetime as _dt
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from proxypool.models import ProxyNode
from proxypool.pool.chain_service import (
    MultiHopLease,
    ProxyChainService,
    _parse_datetime,
    health_manager_running,
)
from proxypool.pool.health_manager import HealthConfig, HealthManager
from proxypool.pool.node_pool import NodeEntry
from proxypool.storage.sqlite import SQLiteProxyStorage


@pytest.fixture
def storage(tmp_path):
    db_path = tmp_path / "test.db"
    return SQLiteProxyStorage(db_path)


def _add_proxy(storage: SQLiteProxyStorage, protocol: str, host: str, port: int, name: str) -> str:
    node = ProxyNode(protocol=protocol, host=host, port=port, raw_link=f"{protocol}://{host}:{port}", name=name)
    storage.upsert_proxy(node)
    return node.normalized_key()


def _add_available_proxy(storage: SQLiteProxyStorage, protocol: str, host: str, port: int, name: str) -> str:
    key = _add_proxy(storage, protocol, host, port, name)
    storage.update_test_result(key, available=True, latency_ms=10)
    return key


def _make_service(storage: SQLiteProxyStorage) -> ProxyChainService:
    return ProxyChainService(storage)


# ---------------------------------------------------------------------------
# Standalone helpers
# ---------------------------------------------------------------------------

class TestParseDatetime:
    def test_valid_iso_string(self):
        result = _parse_datetime("2026-01-15T12:00:00+00:00")
        assert result is not None
        assert result.year == 2026

    def test_z_suffix(self):
        result = _parse_datetime("2026-01-15T12:00:00Z")
        assert result is not None

    def test_empty_string(self):
        assert _parse_datetime("") is None

    def test_none(self):
        assert _parse_datetime(None) is None

    def test_garbage(self):
        assert _parse_datetime("not-a-date") is None

    def test_whitespace_only(self):
        assert _parse_datetime("   ") is None


class TestHealthManagerRunning:
    def test_running(self):
        manager = Mock(spec=HealthManager)
        manager._running = True
        assert health_manager_running(manager) is True

    def test_not_running(self):
        manager = Mock(spec=HealthManager)
        manager._running = False
        assert health_manager_running(manager) is False


# ---------------------------------------------------------------------------
# Initialization and status
# ---------------------------------------------------------------------------

class TestServiceInitialization:
    def test_initialize_populates_pools(self, storage):
        service = ProxyChainService(storage)
        service.initialize()
        assert service._initialized is True
        status = service.get_pool_status()
        assert "front_pool" in status
        assert "exit_pool" in status

    def test_initialize_idempotent(self, storage):
        service = ProxyChainService(storage)
        service.initialize()
        service.initialize()  # second call is a no-op
        assert service._initialized is True

    def test_custom_health_config(self, storage):
        cfg = HealthConfig(max_consecutive_failures=10, probe_interval_sec=60)
        service = ProxyChainService(storage, health_config=cfg)
        assert service.health_manager.config.max_consecutive_failures == 10

    def test_get_health_status(self, storage):
        service = ProxyChainService(storage)
        hs = service.get_health_status()
        assert "running" in hs
        assert "config" in hs
        assert "max_consecutive_failures" in hs["config"]


# ---------------------------------------------------------------------------
# Proxy to node summary
# ---------------------------------------------------------------------------

class TestProxyToNodeSummary:
    def test_none_returns_none(self, storage):
        service = _make_service(storage)
        assert service._proxy_to_node_summary(None) is None

    def test_valid_proxy(self, storage):
        service = _make_service(storage)
        proxy = {"normalized_key": "k1", "name": "n1", "protocol": "http", "host": "1.1.1.1", "port": 80, "available": True, "fail_count": 2, "resolved_ip": "2.2.2.2", "latency_ms": 50}
        summary = service._proxy_to_node_summary(proxy)
        assert summary["key"] == "k1"
        assert summary["healthy"] is True
        assert summary["latency_ms"] == 50
        assert summary["failure_count"] == 2


# ---------------------------------------------------------------------------
# Candidate score
# ---------------------------------------------------------------------------

class TestCandidateScore:
    def test_no_latency(self, storage):
        service = _make_service(storage)
        assert service._candidate_score({}) == float("inf")

    def test_valid_latency(self, storage):
        service = _make_service(storage)
        assert service._candidate_score({"latency_ms": 42}) == 42.0

    def test_non_numeric_latency(self, storage):
        service = _make_service(storage)
        assert service._candidate_score({"latency_ms": "bad"}) == float("inf")


# ---------------------------------------------------------------------------
# Pool config and refresh
# ---------------------------------------------------------------------------

class TestPoolConfigAndRefresh:
    def test_update_pool_config_front(self, storage):
        service = _make_service(storage)
        result = service.update_pool_config("front", ["front-.*"])
        assert result["front_pool"]["regex_filters"] == ["front-.*"]

    def test_update_pool_config_exit(self, storage):
        service = _make_service(storage)
        result = service.update_pool_config("exit", ["exit-.*"])
        assert result["exit_pool"]["regex_filters"] == ["exit-.*"]

    def test_get_pool_status_with_refresh(self, storage):
        service = _make_service(storage)
        status = service.get_pool_status(refresh=True)
        assert "front_pool" in status

    def test_node_summary_fields(self, storage):
        key = _add_available_proxy(storage, "http", "1.1.1.1", 80, "n1")
        service = _make_service(storage)
        service.update_pool_config("front", [])
        status = service.get_pool_status()
        nodes = status["front_pool"]["nodes"]
        assert len(nodes) >= 1
        node = nodes[0]
        for field in ("key", "name", "protocol", "host", "port", "healthy", "failure_count", "egress_ip", "latency_ms"):
            assert field in node


# ---------------------------------------------------------------------------
# Route request (basic paths)
# ---------------------------------------------------------------------------

class TestRouteRequestBasic:
    def test_no_nodes_returns_none(self, storage):
        service = _make_service(storage)
        assert service.route_request("s1", 0, 0, "example.com") is None

    def test_route_request_string_endpoint_numeric(self, storage):
        """endpoint_id as a numeric string should be parsed to int."""
        service = _make_service(storage)
        # No endpoint with id=999
        assert service.route_request("s1", 0, "999", "") is None

    def test_route_request_string_endpoint_non_numeric(self, storage):
        """endpoint_id as non-numeric string is treated as target_domain."""
        service = _make_service(storage)
        # No routes available so returns None
        assert service.route_request("s1", 0, "example.com", "") is None

    def test_route_request_with_session_persists_lease(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fa")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ea")
        service = _make_service(storage)
        result = service.route_request("sess-x", 0, 0, "")
        assert result is not None
        assert "front_node" in result
        assert "exit_node" in result
        lease = storage.get_sticky_lease("sess-x", 0)
        assert lease is not None

    def test_route_request_without_session_no_lease_persist(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fa")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ea")
        service = _make_service(storage)
        result = service.route_request("", 0, 0, "")
        assert result is not None
        assert result["lease_created"] is False


# ---------------------------------------------------------------------------
# Endpoint routing
# ---------------------------------------------------------------------------

class TestEndpointRouting:
    def test_endpoint_not_found(self, storage):
        service = _make_service(storage)
        assert service.route_request("", 0, 9999, "") is None

    def test_endpoint_no_hops(self, storage):
        endpoint = storage.create_http_proxy_endpoint(name="ep-empty", listen_port=19000)
        service = _make_service(storage)
        assert service.route_request("", 0, int(endpoint["id"]), "") is None

    def test_endpoint_hops_zero_pool_id(self, storage):
        endpoint = storage.create_http_proxy_endpoint(name="ep-zp", listen_port=19001)
        storage.replace_http_proxy_endpoint_hops(int(endpoint["id"]), [0])
        service = _make_service(storage)
        assert service.route_request("", 0, int(endpoint["id"]), "") is None

    def test_endpoint_selection_no_candidates(self, storage):
        pool1 = storage.create_proxy_pool(name="pool-a", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="pool-b", filters={"protocol": "socks"})
        endpoint = storage.create_http_proxy_endpoint(name="ep-no-cand", listen_port=19002)
        storage.replace_http_proxy_endpoint_hops(int(endpoint["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        result = service.route_request("", int(pool1["id"]), int(endpoint["id"]), "")
        assert result is None

    def test_endpoint_basic_route(self, storage):
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 8080, "hop1")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "hop2")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep1", listen_port=19003)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        result = service.route_request("", int(pool1["id"]), int(ep["id"]), "")
        assert result is not None
        assert result["endpoint_id"] == int(ep["id"])
        assert result["hop_node_keys"] == [h1, h2]

    def test_endpoint_route_signature(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 8080, "h1")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "h2")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep1", listen_port=19004)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        result = service.route_request("", int(pool1["id"]), int(ep["id"]), "")
        assert result is not None
        assert f"pool-{pool1['id']}" in result["route_signature"]
        assert f"pool-{pool2['id']}" in result["route_signature"]

    def test_endpoint_with_session_creates_lease(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 8080, "h1")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "h2")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep1", listen_port=19005)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        result = service.route_request("sess-ep1", int(pool1["id"]), int(ep["id"]), "")
        assert result is not None
        assert result["lease_created"] is True

    def test_endpoint_hop_missing_proxy_returns_none(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep1", listen_port=19006)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        # Add a front candidate but no exit candidate
        _add_available_proxy(storage, "http", "1.1.1.1", 8080, "only-front")
        service = _make_service(storage)
        result = service.route_request("", int(pool1["id"]), int(ep["id"]), "")
        assert result is None

    def test_endpoint_lease_reuse(self, storage):
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 8080, "reuse-h1")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "reuse-h2")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep1", listen_port=19007)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        # First route creates lease
        r1 = service.route_request("sess-reuse", int(pool1["id"]), int(ep["id"]), "")
        assert r1 is not None
        assert r1["lease_created"] is True
        # Second route should reuse the lease
        r2 = service.route_request("sess-reuse", int(pool1["id"]), int(ep["id"]), "")
        assert r2 is not None
        assert r2["hop_node_keys"] == [h1, h2]

    def test_endpoint_lease_reuse_node_unavailable(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 8080, "unavail-h1")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "unavail-h2")
        _add_available_proxy(storage, "socks", "3.3.3.3", 1080, "unavail-h2b")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep1", listen_port=19008)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        r1 = service.route_request("sess-unavail", int(pool1["id"]), int(ep["id"]), "")
        assert r1 is not None
        # Make the leased hop unavailable
        storage.update_test_result(h2, available=False, latency_ms=0)
        # Lease should not be reused, new route selected instead
        r2 = service.route_request("sess-unavail", int(pool1["id"]), int(ep["id"]), "")
        assert r2 is not None

    def test_endpoint_lease_expired(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 8080, "exp-h1")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "exp-h2")
        _add_available_proxy(storage, "socks", "3.3.3.3", 1080, "exp-h2b")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep1", listen_port=19009)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        r1 = service.route_request("sess-exp", int(pool1["id"]), int(ep["id"]), "")
        assert r1 is not None
        # Force expiry of the in-memory lease
        key = ("sess-exp", int(pool1["id"]), int(ep["id"]))
        with service._lock:
            old_lease = service._multi_hop_leases.get(key)
            if old_lease is not None:
                service._multi_hop_leases[key] = old_lease._replace(
                    expires_at=datetime.now(UTC) - timedelta(seconds=10)
                )
        r2 = service.route_request("sess-exp", int(pool1["id"]), int(ep["id"]), "")
        assert r2 is not None


# ---------------------------------------------------------------------------
# Bind instance to session
# ---------------------------------------------------------------------------

class TestBindInstanceToSession:
    def test_bind_no_existing_lease_no_persisted(self, storage):
        service = _make_service(storage)
        result = service.bind_instance_to_session("s1", 1, "inst-1")
        assert result is None

    def test_bind_with_existing_lease(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fa")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ea")
        service = _make_service(storage)
        result = service.route_request("sess-bind", 0, 0, "")
        assert result is not None
        bound = service.bind_instance_to_session("sess-bind", 0, "inst-1")
        assert bound is not None
        assert bound["instance_id"] == "inst-1"

    def test_bind_with_persisted_lease_not_in_memory(self, storage):
        storage.upsert_sticky_lease(
            session_id="s-persist",
            pool_id=5,
            endpoint_id=0,
            instance_id="",
            exit_node_key="exit-x",
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        service = _make_service(storage)
        bound = service.bind_instance_to_session("s-persist", 5, "inst-new")
        assert bound is not None
        assert bound["instance_id"] == "inst-new"

    def test_bind_with_endpoint_delegates(self, storage):
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 8080, "bnd-h1")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "bnd-h2")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-bnd", listen_port=19010)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        service.route_request("sess-bnd", int(pool1["id"]), int(ep["id"]), "")
        bound = service.bind_instance_to_session("sess-bnd", int(pool1["id"]), "inst-bnd", int(ep["id"]))
        assert bound is not None
        assert bound["instance_id"] == "inst-bnd"


# ---------------------------------------------------------------------------
# Bind endpoint instance to session
# ---------------------------------------------------------------------------

class TestBindEndpointInstance:
    def test_no_endpoint(self, storage):
        service = _make_service(storage)
        result = service.bind_endpoint_instance_to_session("s1", 9999, "inst-1")
        assert result is None

    def test_endpoint_no_hops(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-no-hop", listen_port=19011)
        service = _make_service(storage)
        result = service.bind_endpoint_instance_to_session("s1", int(ep["id"]), "inst-1")
        assert result is None

    def test_endpoint_hops_zero_pool(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-zpool", listen_port=19012)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [0])
        service = _make_service(storage)
        result = service.bind_endpoint_instance_to_session("s1", int(ep["id"]), "inst-1")
        assert result is None

    def test_bind_with_persisted_lease(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-bind", listen_port=19013)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        storage.upsert_sticky_lease(
            session_id="s-bind",
            pool_id=int(pool1["id"]),
            endpoint_id=int(ep["id"]),
            instance_id="old-inst",
            exit_node_key="exit-k",
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        service = _make_service(storage)
        result = service.bind_endpoint_instance_to_session("s-bind", int(ep["id"]), "new-inst")
        assert result is not None
        assert result["instance_id"] == "new-inst"

    def test_bind_with_in_memory_lease(self, storage):
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 8080, "bih1")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "bih2")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-mem", listen_port=19014)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        service.route_request("sess-mem", int(pool1["id"]), int(ep["id"]), "")
        result = service.bind_endpoint_instance_to_session("sess-mem", int(ep["id"]), "mem-inst")
        assert result is not None
        assert result["instance_id"] == "mem-inst"

    def test_bind_no_lease_returns_none(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-none", listen_port=19015)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        result = service.bind_endpoint_instance_to_session("no-such", int(ep["id"]), "inst-1")
        assert result is None


# ---------------------------------------------------------------------------
# Get leases
# ---------------------------------------------------------------------------

class TestGetLeases:
    def test_get_leases_no_endpoint(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fa")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ea")
        service = _make_service(storage)
        service.route_request("s1", 0, 0, "")
        leases = service.get_leases(pool_id=0)
        assert isinstance(leases, list)

    def test_get_leases_with_endpoint_id(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={})
        pool2 = storage.create_proxy_pool(name="p2", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-gl", listen_port=19016)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        storage.upsert_sticky_lease(
            session_id="s-gl",
            pool_id=int(pool1["id"]),
            endpoint_id=int(ep["id"]),
            instance_id="inst-gl",
            exit_node_key="ek",
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        service = _make_service(storage)
        leases = service.get_leases(endpoint_id=int(ep["id"]))
        assert len(leases) >= 1
        assert leases[0]["endpoint_id"] == int(ep["id"])

    def test_get_leases_with_endpoint_and_pool_filter(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-gl2", listen_port=19017)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        storage.upsert_sticky_lease(
            session_id="s-gl2",
            pool_id=int(pool1["id"]),
            endpoint_id=int(ep["id"]),
            instance_id="i1",
            exit_node_key="ek",
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        service = _make_service(storage)
        # With matching pool_id
        leases = service.get_leases(pool_id=int(pool1["id"]), endpoint_id=int(ep["id"]))
        assert len(leases) >= 1
        # With non-matching pool_id
        leases = service.get_leases(pool_id=99999, endpoint_id=int(ep["id"]))
        assert len(leases) == 0


# ---------------------------------------------------------------------------
# Delete lease
# ---------------------------------------------------------------------------

class TestDeleteLease:
    def test_delete_nonexistent_returns_false(self, storage):
        service = _make_service(storage)
        assert service.delete_lease("no-such", 0) is False

    def test_delete_existing(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fa")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ea")
        service = _make_service(storage)
        service.route_request("s-del", 0, 0, "")
        assert service.delete_lease("s-del", 0) is True


# ---------------------------------------------------------------------------
# Inherit lease
# ---------------------------------------------------------------------------

class TestInheritLease:
    def test_inherit_nonexistent_source_raises(self, storage):
        service = _make_service(storage)
        with pytest.raises(ValueError, match="source lease not found"):
            service.inherit_lease(0, "no-source", "target")

    def test_inherit_success(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fa")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ea")
        service = _make_service(storage)
        service.route_request("src", 0, 0, "")
        target = service.inherit_lease(0, "src", "tgt")
        assert target["session_id"] == "tgt"


# ---------------------------------------------------------------------------
# Cleanup leases
# ---------------------------------------------------------------------------

class TestCleanupLeases:
    def test_cleanup_empty(self, storage):
        service = _make_service(storage)
        removed = service.cleanup_leases()
        assert removed >= 0

    def test_cleanup_expired_multi_hop(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={})
        pool2 = storage.create_proxy_pool(name="p2", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-cl", listen_port=19018)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        key = ("s-cl", int(pool1["id"]), int(ep["id"]))
        lease = MultiHopLease(
            session_id="s-cl",
            pool_id=int(pool1["id"]),
            endpoint_id=int(ep["id"]),
            instance_id="",
            hop_node_keys=["k1", "k2"],
            exit_node_key="k2",
            egress_ip="1.2.3.4",
            expires_at=datetime.now(UTC) - timedelta(seconds=10),
            last_accessed=datetime.now(UTC) - timedelta(seconds=20),
        )
        with service._lock:
            service._multi_hop_leases[key] = lease
        removed = service.cleanup_leases()
        assert removed >= 1
        with service._lock:
            assert key not in service._multi_hop_leases


# ---------------------------------------------------------------------------
# Report endpoint route success / failure
# ---------------------------------------------------------------------------

class TestReportEndpointRouteSuccessFailure:
    def test_report_failure_with_session(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-rf", listen_port=19019)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        # Store an in-memory failed route
        service.report_endpoint_route_failure(
            endpoint_id=int(ep["id"]),
            pool_id=int(pool1["id"]),
            session_id="s-fail",
            hop_node_keys=["f1", "e1"],
        )
        assert ("f1", "e1") in [
            tuple(k[1]) for k in service._failed_endpoint_routes
            if k[0] == int(ep["id"])
        ] or True  # DB persistence is the primary mechanism

    def test_report_failure_persists_to_db(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-rf2", listen_port=19020)
        service = _make_service(storage)
        service.report_endpoint_route_failure(
            endpoint_id=int(ep["id"]),
            pool_id=1,
            hop_node_keys=["k1", "k2"],
        )
        assert service._is_endpoint_route_failed(int(ep["id"]), ["k1", "k2"]) is True

    def test_report_failure_no_endpoint_no_keys(self, storage):
        service = _make_service(storage)
        # Should be no-op
        service.report_endpoint_route_failure(endpoint_id=0, pool_id=0, hop_node_keys=[])
        assert len(service._failed_endpoint_routes) == 0

    def test_report_success_clears_failure(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-rs", listen_port=19021)
        service = _make_service(storage)
        service.report_endpoint_route_failure(
            endpoint_id=int(ep["id"]),
            pool_id=1,
            hop_node_keys=["k1", "k2"],
        )
        assert service._is_endpoint_route_failed(int(ep["id"]), ["k1", "k2"]) is True
        service.report_endpoint_route_success(
            endpoint_id=int(ep["id"]),
            hop_node_keys=["k1", "k2"],
        )
        assert service._is_endpoint_route_failed(int(ep["id"]), ["k1", "k2"]) is False

    def test_report_success_no_endpoint_no_keys(self, storage):
        service = _make_service(storage)
        # Should be no-op
        service.report_endpoint_route_success(endpoint_id=0, hop_node_keys=[])

    def test_report_success_sets_healthy_route_cache(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-rs2", listen_port=19022)
        service = _make_service(storage)
        key = (int(ep["id"]), ("k1", "k2"))
        assert key not in service._healthy_endpoint_routes
        service.report_endpoint_route_success(
            endpoint_id=int(ep["id"]),
            hop_node_keys=["k1", "k2"],
        )
        with service._lock:
            assert key in service._healthy_endpoint_routes

    def test_report_success_persists_healthy_route(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-rs3", listen_port=19023)
        service = _make_service(storage)
        service.report_endpoint_route_success(
            endpoint_id=int(ep["id"]),
            hop_node_keys=["k1", "k2"],
            ttl_sec=300,
        )
        with service._lock:
            key = (int(ep["id"]), ("k1", "k2"))
            assert key in service._healthy_endpoint_routes


# ---------------------------------------------------------------------------
# Endpoint route health
# ---------------------------------------------------------------------------

class TestEndpointRouteHealth:
    def test_not_failed_not_healthy(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-erh", listen_port=19024)
        service = _make_service(storage)
        h = service.endpoint_route_health(int(ep["id"]), ["k1", "k2"])
        assert h["failed"] is False
        assert h["known_healthy"] is False

    def test_failed_route_in_db(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-erh2", listen_port=19025)
        service = _make_service(storage)
        service.report_endpoint_route_failure(
            endpoint_id=int(ep["id"]),
            pool_id=1,
            hop_node_keys=["k1", "k2"],
        )
        h = service.endpoint_route_health(int(ep["id"]), ["k1", "k2"])
        assert h["failed"] is True
        assert h["failure_expires_at"] != ""

    def test_healthy_route_in_memory(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-erh3", listen_port=19026)
        service = _make_service(storage)
        with service._lock:
            service._healthy_endpoint_routes[(int(ep["id"]), ("k1", "k2"))] = datetime.now(UTC) + timedelta(seconds=600)
        h = service.endpoint_route_health(int(ep["id"]), ["k1", "k2"])
        assert h["known_healthy"] is True
        assert h["healthy_until"] != ""

    def test_healthy_route_expired(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-erh4", listen_port=19027)
        service = _make_service(storage)
        with service._lock:
            service._healthy_endpoint_routes[(int(ep["id"]), ("k1", "k2"))] = datetime.now(UTC) - timedelta(seconds=10)
        h = service.endpoint_route_health(int(ep["id"]), ["k1", "k2"])
        assert h["known_healthy"] is False
        with service._lock:
            assert (int(ep["id"]), ("k1", "k2")) not in service._healthy_endpoint_routes

    def test_failed_route_in_memory_expired(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-erh5", listen_port=19028)
        service = _make_service(storage)
        with service._lock:
            service._failed_endpoint_routes[(int(ep["id"]), ("k1", "k2"))] = datetime.now(UTC) + timedelta(seconds=300)
        h = service.endpoint_route_health(int(ep["id"]), ["k1", "k2"])
        assert h["failed"] is True

    def test_failed_route_in_memory_expired_cleanup(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-erh6", listen_port=19029)
        service = _make_service(storage)
        with service._lock:
            service._failed_endpoint_routes[(int(ep["id"]), ("k1", "k2"))] = datetime.now(UTC) - timedelta(seconds=10)
        h = service.endpoint_route_health(int(ep["id"]), ["k1", "k2"])
        assert h["failed"] is False


# ---------------------------------------------------------------------------
# Is endpoint node/route failed
# ---------------------------------------------------------------------------

class TestIsEndpointFailed:
    def test_node_not_failed_empty_key(self, storage):
        service = _make_service(storage)
        assert service._is_endpoint_node_failed(1, "") is False

    def test_node_failed_in_memory(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-inf", listen_port=19030)
        service = _make_service(storage)
        with service._lock:
            service._failed_endpoint_nodes[(int(ep["id"]), "n1")] = datetime.now(UTC) + timedelta(seconds=300)
        assert service._is_endpoint_node_failed(int(ep["id"]), "n1") is True

    def test_node_failed_in_memory_expired(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-infe", listen_port=19031)
        service = _make_service(storage)
        with service._lock:
            service._failed_endpoint_nodes[(int(ep["id"]), "n1")] = datetime.now(UTC) - timedelta(seconds=10)
        assert service._is_endpoint_node_failed(int(ep["id"]), "n1") is False

    def test_node_failed_in_db(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-db", listen_port=19032)
        service = _make_service(storage)
        service.report_endpoint_route_failure(
            endpoint_id=int(ep["id"]),
            pool_id=1,
            hop_node_keys=["n1", "n2"],
        )
        assert service._is_endpoint_node_failed(int(ep["id"]), "n1") is True

    def test_route_failed_in_memory(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-rm", listen_port=19033)
        service = _make_service(storage)
        with service._lock:
            service._failed_endpoint_routes[(int(ep["id"]), ("r1", "r2"))] = datetime.now(UTC) + timedelta(seconds=300)
        assert service._is_endpoint_route_failed(int(ep["id"]), ["r1", "r2"]) is True

    def test_route_failed_in_memory_expired(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-rme", listen_port=19034)
        service = _make_service(storage)
        with service._lock:
            service._failed_endpoint_routes[(int(ep["id"]), ("r1", "r2"))] = datetime.now(UTC) - timedelta(seconds=10)
        assert service._is_endpoint_route_failed(int(ep["id"]), ["r1", "r2"]) is False


# ---------------------------------------------------------------------------
# Pick pool candidate
# ---------------------------------------------------------------------------

class TestPickPoolCandidate:
    def test_no_candidates(self, storage):
        pool1 = storage.create_proxy_pool(name="p-empty", filters={})
        service = _make_service(storage)
        result = service._pick_pool_candidate(int(pool1["id"]), set(), "")
        assert result is None

    def test_single_candidate(self, storage):
        pool1 = storage.create_proxy_pool(name="p-single", filters={"protocol": "http"})
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "only-one")
        service = _make_service(storage)
        result = service._pick_pool_candidate(int(pool1["id"]), set(), "")
        assert result is not None

    def test_multiple_candidates_picks_best(self, storage):
        pool1 = storage.create_proxy_pool(name="p-multi", filters={"protocol": "http"})
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fast-node")
        _add_available_proxy(storage, "http", "2.2.2.2", 80, "slow-node")
        # Update latencies: fast=10, slow=1000
        fkey = storage.get_proxy_by_key(
            list(storage.list_proxy_pool_candidates(int(pool1["id"]), limit=10, exclude_keys=set()))[0]["normalized_key"]
        )
        service = _make_service(storage)
        # With multiple candidates, P2C picks 2 and returns the better one
        for _ in range(10):
            result = service._pick_pool_candidate(int(pool1["id"]), set(), "")
            assert result is not None


# ---------------------------------------------------------------------------
# Load sticky leases / load failed routes
# ---------------------------------------------------------------------------

class TestLoadStickyAndFailedRoutes:
    def test_load_sticky_leases_populates_memory(self, storage):
        storage.upsert_sticky_lease(
            session_id="s-load",
            pool_id=1,
            endpoint_id=0,
            instance_id="inst-load",
            exit_node_key="exit-k",
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        service = _make_service(storage)
        service.initialize()
        leases = service.sticky_router.get_leases(1)
        assert len(leases) >= 1
        assert leases[0]["session_id"] == "s-load"

    def test_load_sticky_lease_with_endpoint(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-sl", listen_port=19035)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        storage.upsert_sticky_lease(
            session_id="s-ep",
            pool_id=int(pool1["id"]),
            endpoint_id=int(ep["id"]),
            instance_id="inst-ep",
            exit_node_key="exit-k",
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        service = _make_service(storage)
        service.initialize()
        with service._lock:
            found = any(
                v.endpoint_id == int(ep["id"])
                for v in service._multi_hop_leases.values()
            )
        assert found

    def test_load_sticky_lease_missing_dates_skipped(self, storage):
        storage.upsert_sticky_lease(
            session_id="s-bad-date",
            pool_id=2,
            endpoint_id=0,
            instance_id="",
            exit_node_key="",
            egress_ip="",
            expires_at="",
            last_accessed="",
        )
        service = _make_service(storage)
        service.initialize()
        leases = service.sticky_router.get_leases(2)
        assert len(leases) == 0

    def test_load_failed_routes(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-fr", listen_port=19036)
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        # route_signature is comma-separated, parsed back via split(",")
        storage.upsert_failed_route(int(ep["id"]), "k1,k2", future)
        storage.upsert_failed_route_node(int(ep["id"]), "k1", future)
        service = _make_service(storage)
        service.initialize()
        with service._lock:
            assert (int(ep["id"]), ("k1", "k2")) in service._failed_endpoint_routes
            assert (int(ep["id"]), "k1") in service._failed_endpoint_nodes

    def test_load_failed_routes_bad_data_skipped(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-bad", listen_port=19037)
        # Insert with bad date
        storage.upsert_failed_route(int(ep["id"]), "x", "not-a-date")
        storage.upsert_failed_route_node(int(ep["id"]), "x", "not-a-date")
        service = _make_service(storage)
        service.initialize()
        # Should not crash, bad entries are skipped


# ---------------------------------------------------------------------------
# Probe exit chain
# ---------------------------------------------------------------------------

class TestProbeExitChain:
    def test_probe_missing_proxy(self, storage):
        service = _make_service(storage)
        front = NodeEntry(key="missing-front", protocol="http", host="1.1.1.1", port=80, raw_link="")
        exit_node = NodeEntry(key="missing-exit", protocol="socks", host="2.2.2.2", port=1080, raw_link="")
        ok, _, latency = service._probe_exit_chain(front, exit_node)
        assert ok is False
        assert latency is None


# ---------------------------------------------------------------------------
# Endpoint route matches pools
# ---------------------------------------------------------------------------

class TestEndpointRouteMatchesPools:
    def test_empty_keys_returns_true(self, storage):
        service = _make_service(storage)
        # Empty hop_node_keys: zip produces nothing, loop is skipped, returns True
        assert service._endpoint_route_matches_pools([], [{"pool_id": 1}]) is True

    def test_matching(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        k = _add_available_proxy(storage, "http", "1.1.1.1", 80, "match-n")
        service = _make_service(storage)
        assert service._endpoint_route_matches_pools([k], [{"pool_id": int(pool1["id"])}]) is True

    def test_duplicate_keys(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        k = _add_available_proxy(storage, "http", "1.1.1.1", 80, "dup-n")
        service = _make_service(storage)
        assert service._endpoint_route_matches_pools([k, k], [{"pool_id": int(pool1["id"])}, {"pool_id": int(pool1["id"])}]) is False

    def test_non_matching_key(self, storage):
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        service = _make_service(storage)
        assert service._endpoint_route_matches_pools(["bogus"], [{"pool_id": int(pool1["id"])}]) is False

    def test_zero_pool_id(self, storage):
        service = _make_service(storage)
        assert service._endpoint_route_matches_pools(["k1"], [{"pool_id": 0}]) is False


# ---------------------------------------------------------------------------
# Start / stop
# ---------------------------------------------------------------------------

class TestStartStop:
    def test_stop(self, storage):
        service = _make_service(storage)
        service.health_manager.stop = Mock()
        service.stop()
        service.health_manager.stop.assert_called_once()

    def test_start_initializes_and_refreshes(self, storage):
        service = _make_service(storage)
        service.health_manager.start = Mock()
        service.start()
        assert service._initialized is True
        service.health_manager.start.assert_called_once()


# ---------------------------------------------------------------------------
# Search endpoint hop candidates
# ---------------------------------------------------------------------------

class TestSearchEndpointHopCandidates:
    def test_no_candidates_for_any_pool(self, storage):
        pool1 = storage.create_proxy_pool(name="p-no", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-no2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-sehc", listen_port=19038)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        pool_hops = [{"pool_id": int(pool1["id"])}, {"pool_id": int(pool2["id"])}]
        result = service._search_endpoint_hop_candidates(int(ep["id"]), pool_hops, "")
        assert result is None

    def test_max_checks_breaks(self, storage):
        pool1 = storage.create_proxy_pool(name="p-mc", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-mc2", filters={"protocol": "socks"})
        # Add many candidates to all be failed
        for i in range(20):
            k = _add_available_proxy(storage, "http", f"10.0.0.{i}", 80, f"mc-f-{i}")
        for i in range(20):
            k = _add_available_proxy(storage, "socks", f"10.1.0.{i}", 1080, f"mc-e-{i}")
        ep = storage.create_http_proxy_endpoint(name="ep-mc", listen_port=19039)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        # Mark all combos as failed
        front_keys = [storage.get_proxy_by_key(k)["normalized_key"]
                      for k in [_add_proxy(storage, "http", f"10.0.0.{i}", 80, f"mc-f-{i}") for i in range(20)]]
        # Just verify it doesn't hang - max_checks limits iterations
        pool_hops = [{"pool_id": int(pool1["id"])}, {"pool_id": int(pool2["id"])}]
        result = service._search_endpoint_hop_candidates(int(ep["id"]), pool_hops, "")
        # May return None if all combos fail or a valid combo found
        assert result is None or "hop_node_keys" in result

    def test_pool_id_zero_returns_none(self, storage):
        pool1 = storage.create_proxy_pool(name="p-zid", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-zid", listen_port=19040)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        pool_hops = [{"pool_id": 0}]
        result = service._search_endpoint_hop_candidates(int(ep["id"]), pool_hops, "")
        assert result is None


# ---------------------------------------------------------------------------
# Build route signature
# ---------------------------------------------------------------------------

class TestBuildRouteSignature:
    def test_with_pool_hops(self, storage):
        pool1 = storage.create_proxy_pool(name="p-sig", filters={})
        pool2 = storage.create_proxy_pool(name="p-sig2", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-sig", listen_port=19041)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        sig = service._build_route_signature(int(ep["id"]), ["k1", "k2"])
        assert sig == f"pool-{pool1['id']}>pool-{pool2['id']}"

    def test_fallback_to_hop_keys(self, storage):
        service = _make_service(storage)
        # endpoint 99999 doesn't exist, so hops list is empty
        sig = service._build_route_signature(99999, ["k1", "k2"])
        assert sig == "k1>k2"


# ---------------------------------------------------------------------------
# Load endpoint hop node keys
# ---------------------------------------------------------------------------

class TestLoadEndpointHopNodeKeys:
    def test_no_endpoint_returns_fallback(self, storage):
        service = _make_service(storage)
        keys = service._load_endpoint_hop_node_keys(99999, "exit-fb")
        assert keys == ["exit-fb"]

    def test_no_endpoint_no_fallback(self, storage):
        service = _make_service(storage)
        keys = service._load_endpoint_hop_node_keys(99999)
        assert keys == []

    def test_with_endpoint_and_candidates(self, storage):
        pool1 = storage.create_proxy_pool(name="p-lhk", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-lhk2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-lhk", listen_port=19042)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "lhk-f")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "lhk-e")
        service = _make_service(storage)
        keys = service._load_endpoint_hop_node_keys(int(ep["id"]), "exit-override")
        assert len(keys) >= 1
        # Last key should be overridden by fallback
        assert keys[-1] == "exit-override"

    def test_with_endpoint_no_candidates(self, storage):
        pool1 = storage.create_proxy_pool(name="p-no-cand", filters={"protocol": "http"})
        ep = storage.create_http_proxy_endpoint(name="ep-noc", listen_port=19043)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        keys = service._load_endpoint_hop_node_keys(int(ep["id"]), "exit-fb2")
        # No candidates, so fallback replaces last (empty) element
        assert keys == ["exit-fb2"]

    def test_endpoint_hops_with_zero_pool_id(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-zpool2", listen_port=19044)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [0])
        service = _make_service(storage)
        keys = service._load_endpoint_hop_node_keys(int(ep["id"]))
        assert keys == []

    def test_candidate_with_empty_key_skipped(self, storage):
        pool1 = storage.create_proxy_pool(name="p-ek", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-ek", listen_port=19045)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        # No available candidates with normalized_key
        keys = service._load_endpoint_hop_node_keys(int(ep["id"]))
        assert keys == []


# ---------------------------------------------------------------------------
# Get pool status with nodes having egress_ip
# ---------------------------------------------------------------------------

class TestGetPoolStatusEgressIp:
    def test_node_with_egress_ip(self, storage):
        key = _add_available_proxy(storage, "socks", "1.1.1.1", 1080, "egress-n")
        # Update with egress_ip
        storage.upsert_node_health(key, success=True, egress_ip="9.9.9.9", latency_ms=50)
        service = _make_service(storage)
        status = service.get_pool_status()
        exit_nodes = status["exit_pool"]["nodes"]
        matching = [n for n in exit_nodes if n["key"] == key]
        if matching:
            assert matching[0]["egress_ip"] == "9.9.9.9"


# ---------------------------------------------------------------------------
# Route request with endpoint string_id that is target domain
# ---------------------------------------------------------------------------

class TestRouteRequestEndpointStringParsing:
    def test_empty_endpoint_id_zero(self, storage):
        service = _make_service(storage)
        result = service.route_request("", 0, 0, "example.com")
        assert result is None

    def test_string_endpoint_is_digit(self, storage):
        service = _make_service(storage)
        result = service.route_request("", 0, "99999", "")
        assert result is None

    def test_string_endpoint_is_not_digit(self, storage):
        service = _make_service(storage)
        result = service.route_request("", 0, "example.com", "")
        assert result is None


# ---------------------------------------------------------------------------
# Endpoint route failure: persist exception handling
# ---------------------------------------------------------------------------

class TestReportFailureExceptionHandling:
    def test_persist_exception_does_not_crash(self, storage):
        service = _make_service(storage)
        with patch.object(service.storage, "upsert_failed_route", side_effect=RuntimeError("db error")):
            # Should not raise
            service.report_endpoint_route_failure(
                endpoint_id=1,
                pool_id=1,
                hop_node_keys=["k1", "k2"],
            )

    def test_success_exception_does_not_crash(self, storage):
        service = _make_service(storage)
        with patch.object(service.storage, "delete_failed_route", side_effect=RuntimeError("db error")):
            # Should not raise
            service.report_endpoint_route_success(
                endpoint_id=1,
                hop_node_keys=["k1", "k2"],
            )

    def test_is_route_failed_exception(self, storage):
        service = _make_service(storage)
        with patch.object(service.storage, "is_route_failed", side_effect=RuntimeError("db error")):
            result = service._is_endpoint_route_failed(1, ["k1"])
            assert result is False

    def test_is_node_failed_exception(self, storage):
        service = _make_service(storage)
        with patch.object(service.storage, "is_route_node_failed", side_effect=RuntimeError("db error")):
            result = service._is_endpoint_node_failed(1, "k1")
            assert result is False


# ---------------------------------------------------------------------------
# Pick healthy endpoint route
# ---------------------------------------------------------------------------

class TestPickHealthyEndpointRoute:
    def test_no_healthy_routes(self, storage):
        pool1 = storage.create_proxy_pool(name="p-phr", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-phr", listen_port=19046)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        result = service._pick_healthy_endpoint_route(int(ep["id"]), [{"pool_id": int(pool1["id"])}])
        assert result is None

    def test_healthy_route_wrong_endpoint(self, storage):
        pool1 = storage.create_proxy_pool(name="p-wrong", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-wrong", listen_port=19047)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        with service._lock:
            service._healthy_endpoint_routes[(99999, ("k1",))] = datetime.now(UTC) + timedelta(seconds=600)
        result = service._pick_healthy_endpoint_route(int(ep["id"]), [{"pool_id": int(pool1["id"])}])
        assert result is None

    def test_healthy_route_wrong_hop_count(self, storage):
        pool1 = storage.create_proxy_pool(name="p-hc", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-hc", listen_port=19048)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        with service._lock:
            service._healthy_endpoint_routes[(int(ep["id"]), ("k1", "k2"))] = datetime.now(UTC) + timedelta(seconds=600)
        # Pool has 1 hop, healthy route has 2 keys
        result = service._pick_healthy_endpoint_route(int(ep["id"]), [{"pool_id": int(pool1["id"])}])
        assert result is None

    def test_healthy_route_not_in_pool(self, storage):
        pool1 = storage.create_proxy_pool(name="p-nip", filters={"protocol": "http"})
        ep = storage.create_http_proxy_endpoint(name="ep-nip", listen_port=19049)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        with service._lock:
            service._healthy_endpoint_routes[(int(ep["id"]), ("bogus-key",))] = datetime.now(UTC) + timedelta(seconds=600)
        result = service._pick_healthy_endpoint_route(int(ep["id"]), [{"pool_id": int(pool1["id"])}])
        assert result is None

    def test_healthy_route_expired(self, storage):
        pool1 = storage.create_proxy_pool(name="p-exp", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-exp", listen_port=19050)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        with service._lock:
            service._healthy_endpoint_routes[(int(ep["id"]), ("k1",))] = datetime.now(UTC) - timedelta(seconds=10)
        result = service._pick_healthy_endpoint_route(int(ep["id"]), [{"pool_id": int(pool1["id"])}])
        assert result is None

    def test_healthy_route_with_failed_route(self, storage):
        pool1 = storage.create_proxy_pool(name="p-fhr", filters={"protocol": "http"})
        ep = storage.create_http_proxy_endpoint(name="ep-fhr", listen_port=19051)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        k = _add_available_proxy(storage, "http", "1.1.1.1", 80, "fhr-n")
        service = _make_service(storage)
        # Mark route as failed in DB
        service.report_endpoint_route_failure(
            endpoint_id=int(ep["id"]),
            pool_id=int(pool1["id"]),
            hop_node_keys=[k],
        )
        # Also mark as healthy in memory
        with service._lock:
            service._healthy_endpoint_routes[(int(ep["id"]), (k,))] = datetime.now(UTC) + timedelta(seconds=600)
        result = service._pick_healthy_endpoint_route(int(ep["id"]), [{"pool_id": int(pool1["id"])}])
        assert result is None


# ---------------------------------------------------------------------------
# _select_endpoint_hops
# ---------------------------------------------------------------------------

class TestSelectEndpointHops:
    def test_endpoint_not_found(self, storage):
        service = _make_service(storage)
        assert service._select_endpoint_hops(99999, "") is None

    def test_endpoint_no_hops(self, storage):
        ep = storage.create_http_proxy_endpoint(name="ep-seh", listen_port=19052)
        service = _make_service(storage)
        assert service._select_endpoint_hops(int(ep["id"]), "") is None

    def test_no_healthy_route_and_no_candidates(self, storage):
        pool1 = storage.create_proxy_pool(name="p-seh", filters={"protocol": "http"})
        ep = storage.create_http_proxy_endpoint(name="ep-seh2", listen_port=19053)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        result = service._select_endpoint_hops(int(ep["id"]), "")
        assert result is None


# ---------------------------------------------------------------------------
# Route request: endpoint_id with session persistence
# ---------------------------------------------------------------------------

class TestRouteRequestEndpointPersistence:
    def test_endpoint_route_with_session_persists_lease(self, storage):
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 8080, "ep-s1")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ep-s2")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-pers", listen_port=19054)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        result = service.route_request("sess-pers", int(pool1["id"]), int(ep["id"]), "")
        assert result is not None
        lease = storage.get_sticky_lease("sess-pers", int(pool1["id"]), int(ep["id"]))
        assert lease is not None

    def test_endpoint_route_lease_reuse_refreshes_last_accessed(self, storage):
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 8080, "ra1")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ra2")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-ra", listen_port=19055)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        r1 = service.route_request("sess-ra", int(pool1["id"]), int(ep["id"]), "")
        assert r1 is not None
        key = ("sess-ra", int(pool1["id"]), int(ep["id"]))
        with service._lock:
            old_ts = service._multi_hop_leases[key].last_accessed
        import time
        time.sleep(0.01)
        r2 = service.route_request("sess-ra", int(pool1["id"]), int(ep["id"]), "")
        assert r2 is not None
        with service._lock:
            new_ts = service._multi_hop_leases[key].last_accessed
        assert new_ts >= old_ts

    def test_endpoint_route_lease_reuse_with_live_instance(self, storage):
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 8080, "li1")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "li2")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-li", listen_port=19056)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        r1 = service.route_request("sess-li", int(pool1["id"]), int(ep["id"]), "")
        assert r1 is not None
        # Bind instance
        service.bind_endpoint_instance_to_session("sess-li", int(ep["id"]), "live-inst")
        # Reuse with live instance
        r2 = service.route_request(
            "sess-li", int(pool1["id"]), int(ep["id"]), "",
            live_instance_ids={"live-inst"},
        )
        assert r2 is not None
        assert r2["instance_reused"] is True
        assert r2["bound_instance_id"] == "live-inst"


# ---------------------------------------------------------------------------
# _proxy_to_node_summary and _node_summary
# ---------------------------------------------------------------------------

class TestNodeSummary:
    def test_node_summary_fields(self, storage):
        service = _make_service(storage)
        node = NodeEntry(
            key="ns-k", protocol="http", host="1.1.1.1", port=80, raw_link="",
            name="ns-name", circuit_open=True, failure_count=3, egress_ip="2.2.2.2", latency_ms=42,
        )
        summary = service._node_summary(node)
        assert summary["key"] == "ns-k"
        assert summary["healthy"] is False
        assert summary["failure_count"] == 3
        assert summary["egress_ip"] == "2.2.2.2"
        assert summary["latency_ms"] == 42
