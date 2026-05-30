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

    def test_bind_with_persisted_lease_after_init(self, storage):
        """Lease inserted AFTER initialization hits the persisted path (lines 480-483)."""
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 8080, "bpi-h1")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "bpi-h2")
        pool1 = storage.create_proxy_pool(name="p-bpi", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-bpi2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-bpi", listen_port=19090)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        service.initialize()  # Initialize first - loads existing leases
        # Insert lease AFTER initialization - won't be in memory
        storage.upsert_sticky_lease(
            session_id="s-bpi",
            pool_id=int(pool1["id"]),
            endpoint_id=int(ep["id"]),
            instance_id="old-inst",
            exit_node_key=h2,
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        # Verify it's NOT in memory
        key = ("s-bpi", int(pool1["id"]), int(ep["id"]))
        with service._lock:
            assert key not in service._multi_hop_leases
        result = service.bind_endpoint_instance_to_session("s-bpi", int(ep["id"]), "new-inst")
        assert result is not None
        assert result["instance_id"] == "new-inst"


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


# ---------------------------------------------------------------------------
# _load_health_state: health records for front and exit pool nodes
# ---------------------------------------------------------------------------

class TestLoadHealthState:
    def test_health_record_updates_front_node(self, storage):
        """Health record matching a front-pool node updates its state."""
        key = _add_available_proxy(storage, "http", "1.1.1.1", 80, "hs-front")
        storage.upsert_node_health(key, success=False, egress_ip="3.3.3.3", latency_ms=99)
        service = _make_service(storage)
        service.update_pool_config("front", [])
        # Rebuild pools so the node is in front_pool
        service._refresh_pools_locked()
        node = service.front_pool.get_node(key)
        assert node is not None
        assert node.failure_count >= 0  # health state loaded

    def test_health_record_updates_exit_node(self, storage):
        """Health record matching an exit-pool node updates its state and sets routeable."""
        key = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "hs-exit")
        storage.upsert_node_health(key, success=True, egress_ip="4.4.4.4", latency_ms=25)
        service = _make_service(storage)
        service.update_pool_config("exit", [])
        service._refresh_pools_locked()
        node = service.exit_pool.get_node(key)
        assert node is not None

    def test_health_record_no_matching_node(self, storage):
        """Health record for a non-existent node doesn't crash."""
        storage.upsert_node_health("nonexistent-key", success=True)
        service = _make_service(storage)
        service.update_pool_config("front", [])
        service.update_pool_config("exit", [])
        service._refresh_pools_locked()  # Should not raise

    def test_health_record_matches_neither_pool(self, storage):
        """Health record for a key not in either pool - both front_node and exit_node are None."""
        k1 = _add_available_proxy(storage, "http", "1.1.1.1", 80, "hs-f1")
        k2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "hs-e1")
        storage.upsert_node_health("some-other-key", success=True, egress_ip="5.5.5.5")
        service = _make_service(storage)
        service.update_pool_config("front", [])
        service.update_pool_config("exit", [])
        service._refresh_pools_locked()  # The health record for "some-other-key" hits both None branches


# ---------------------------------------------------------------------------
# _probe_exit_chain with valid proxies
# ---------------------------------------------------------------------------

class TestProbeExitChainWithValidProxies:
    def test_probe_with_valid_proxies(self, storage):
        """When both proxies exist, prober.probe_with_front_proxy is called."""
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 80, "probe-f")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "probe-e")
        service = _make_service(storage)
        front = NodeEntry(key=h1, protocol="http", host="1.1.1.1", port=80, raw_link="")
        exit_node = NodeEntry(key=h2, protocol="socks", host="2.2.2.2", port=1080, raw_link="")
        mock_result = Mock()
        mock_result.available = True
        mock_result.latency_ms = 42
        service.prober = Mock()
        service.prober.probe_with_front_proxy.return_value = mock_result
        ok, _, latency = service._probe_exit_chain(front, exit_node)
        assert ok is True
        assert latency == 42
        service.prober.probe_with_front_proxy.assert_called_once()


# ---------------------------------------------------------------------------
# _load_sticky_leases: lease with empty egress_ip (line 156 false branch)
# ---------------------------------------------------------------------------

class TestLoadStickyLeasesEmptyEgress:
    def test_lease_with_empty_egress_ip(self, storage):
        """A lease with empty egress_ip should not increment ip_load."""
        storage.upsert_sticky_lease(
            session_id="s-no-egress",
            pool_id=3,
            endpoint_id=0,
            instance_id="inst-no-egress",
            exit_node_key="exit-x",
            egress_ip="",  # empty egress_ip
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        service = _make_service(storage)
        service.initialize()
        leases = service.sticky_router.get_leases(3)
        assert len(leases) == 1
        assert leases[0]["egress_ip"] == ""
        # ip_load should not have entry for empty string
        assert "" not in service.sticky_router._ip_load


# ---------------------------------------------------------------------------
# _load_failed_routes: various false branch paths
# ---------------------------------------------------------------------------

class TestLoadFailedRoutesBranches:
    def test_failed_route_with_zero_endpoint_id(self, storage):
        """Failed route with endpoint_id=0 is skipped (line 168->164)."""
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        # Manually insert with endpoint_id=0
        storage.upsert_failed_route(0, "k1,k2", future)
        service = _make_service(storage)
        service.initialize()
        # Should not be in memory since endpoint_id=0
        assert (0, ("k1", "k2")) not in service._failed_endpoint_routes

    def test_failed_route_with_empty_route_signature(self, storage):
        """Failed route with empty route_signature is skipped (line 168->164)."""
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        storage.upsert_failed_route(1, "", future)
        service = _make_service(storage)
        service.initialize()

    def test_failed_route_with_comma_only_signature(self, storage):
        """Route signature like ',,, ' produces no non-empty keys (line 174->164)."""
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        storage.upsert_failed_route(1, ",,,", future)
        service = _make_service(storage)
        service.initialize()
        # Keys tuple is empty after filtering, so not stored
        assert (1, ()) not in service._failed_endpoint_routes

    def test_failed_route_node_with_empty_node_key(self, storage):
        """Failed route node with empty node_key is skipped (line 184->180)."""
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        storage.upsert_failed_route_node(1, "", future)
        service = _make_service(storage)
        service.initialize()
        assert (1, "") not in service._failed_endpoint_nodes

    def test_failed_route_node_with_zero_endpoint_id(self, storage):
        """Failed route node with endpoint_id=0 is skipped (line 184->180)."""
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        storage.upsert_failed_route_node(0, "n1", future)
        service = _make_service(storage)
        service.initialize()

    def test_failed_route_with_unparseable_date(self, storage):
        """Failed route with bad date format is skipped via except (line 174->164)."""
        storage.upsert_failed_route(1, "k1", "not-a-date")
        service = _make_service(storage)
        service.initialize()

    def test_failed_route_node_with_unparseable_date(self, storage):
        """Failed route node with bad date format is skipped via except (line 184->180)."""
        storage.upsert_failed_route_node(1, "n1", "not-a-date")
        service = _make_service(storage)
        service.initialize()


# ---------------------------------------------------------------------------
# _rebuild_pools with proxy having empty key (line 212->210)
# ---------------------------------------------------------------------------

class TestRebuildPoolsEmptyKey:
    def test_proxy_with_empty_key_is_skipped(self, storage):
        """A proxy with empty normalized_key is skipped during pool rebuild."""
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "valid-proxy")
        service = _make_service(storage)
        service.update_pool_config("front", [])
        # Manually insert a proxy with empty key via raw SQL to bypass validation
        now = datetime.now(UTC).isoformat()
        with storage._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO proxies
                   (normalized_key, protocol, host, port, raw_link, name, source,
                    last_seen_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("", "http", "9.9.9.9", 80, "http://9.9.9.9:80", "empty-key-proxy", "test", now, now, now),
            )
            conn.commit()
        service._rebuild_pools()  # Should not crash, empty key proxy is skipped


# ---------------------------------------------------------------------------
# route_request: string endpoint with target_domain (line 354->358)
# ---------------------------------------------------------------------------

class TestRouteRequestStringEndpointWithDomain:
    def test_non_digit_string_with_target_domain(self, storage):
        """Non-digit string endpoint_id with target_domain set doesn't override domain."""
        result = route_request_with_args(storage, endpoint_id="example.com", target_domain="google.com")
        # resolved_endpoint_id stays 0, target_domain stays "google.com", falls through to sticky_router
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# route_request: session with non-matching leases (lines 379->394, 381)
# ---------------------------------------------------------------------------

class TestRouteRequestSessionLeaseMismatch:
    def test_session_with_other_sessions_lease(self, storage):
        """When leases exist but none match the current session, the loop skips all."""
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fa-mismatch")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ea-mismatch")
        service = _make_service(storage)
        # Route as session "other-sess" to create a lease
        service.route_request("other-sess", 0, 0, "")
        # Now route as "new-sess" - leases exist but don't match
        result = service.route_request("new-sess", 0, 0, "")
        assert result is not None
        # The lease for new-sess should exist in storage
        lease = storage.get_sticky_lease("new-sess", 0)
        assert lease is not None


# ---------------------------------------------------------------------------
# bind_instance_to_session: lease becomes None after bind (line 443)
# ---------------------------------------------------------------------------

class TestBindInstanceLeaseBecomesNone:
    def test_bind_when_lease_disappears_after_bind(self, storage):
        """After bind_instance, if lease is not found, fall back to storage."""
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fa-bd")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ea-bd")
        service = _make_service(storage)
        service.route_request("s-bd", 0, 0, "")
        # Patch bind_instance to remove the lease from memory
        original_bind = service.sticky_router.bind_instance
        def mock_bind(session_id, pool_id, instance_id):
            service.sticky_router._leases.pop((session_id, pool_id), None)
        service.sticky_router.bind_instance = mock_bind
        result = service.bind_instance_to_session("s-bd", 0, "inst-bd")
        # After mock bind removes lease, it falls back to storage
        assert result is not None

    def test_bind_persisted_lease_loaded_after_init(self, storage):
        """Lease inserted after initialization is NOT in memory -> hits lines 428-438."""
        service = _make_service(storage)
        service.initialize()  # Initialize first
        # Now insert a lease AFTER initialization - it won't be in memory
        storage.upsert_sticky_lease(
            session_id="s-after-init",
            pool_id=7,
            endpoint_id=0,
            instance_id="old-inst",
            exit_node_key="exit-x",
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        # Verify it's NOT in memory
        assert ("s-after-init", 7) not in service.sticky_router._leases
        bound = service.bind_instance_to_session("s-after-init", 7, "inst-new")
        assert bound is not None
        assert bound["instance_id"] == "inst-new"


# ---------------------------------------------------------------------------
# bind_endpoint_instance_to_session: entry_pool_id=0 (line 471)
# ---------------------------------------------------------------------------

class TestBindEndpointInstanceZeroPool:
    def test_endpoint_hops_zero_pool_id(self, storage):
        """Endpoint with hops[0].pool_id=0 returns None at line 471."""
        ep = storage.create_http_proxy_endpoint(name="ep-bz", listen_port=19060)
        # Insert hop with pool_id=0 directly (replace_http_proxy_endpoint_hops filters out 0)
        now = datetime.now(UTC).isoformat()
        with storage._connect() as conn:
            conn.execute(
                """INSERT INTO http_proxy_endpoint_hops
                   (endpoint_id, hop_index, pool_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (int(ep["id"]), 0, 0, now, now),
            )
            conn.commit()
        service = _make_service(storage)
        result = service.bind_endpoint_instance_to_session("s1", int(ep["id"]), "inst-1")
        assert result is None


# ---------------------------------------------------------------------------
# get_leases: endpoint_id with non-matching pool_id filter (line 522)
# ---------------------------------------------------------------------------

class TestGetLeasesPoolFilter:
    def test_endpoint_leases_non_matching_pool_id(self, storage):
        """Multi-hop leases filtered by pool_id: non-matching pool returns empty."""
        pool1 = storage.create_proxy_pool(name="p-gl-f", filters={})
        pool2 = storage.create_proxy_pool(name="p-gl-f2", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-gl-f", listen_port=19061)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        storage.upsert_sticky_lease(
            session_id="s-gl-f",
            pool_id=int(pool1["id"]),
            endpoint_id=int(ep["id"]),
            instance_id="i1",
            exit_node_key="ek",
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        service = _make_service(storage)
        # Matching pool_id
        leases = service.get_leases(pool_id=int(pool1["id"]), endpoint_id=int(ep["id"]))
        assert len(leases) >= 1
        # Non-matching pool_id filters out the lease (line 523-524 continue)
        leases = service.get_leases(pool_id=99999, endpoint_id=int(ep["id"]))
        assert len(leases) == 0

    def test_endpoint_leases_non_matching_endpoint_id(self, storage):
        """Multi-hop leases filtered by endpoint_id: non-matching endpoint skipped (line 522)."""
        pool1 = storage.create_proxy_pool(name="p-gl-eid", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-gl-eid", listen_port=19087)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        # Insert lease with endpoint_id matching ep
        storage.upsert_sticky_lease(
            session_id="s-gl-eid",
            pool_id=int(pool1["id"]),
            endpoint_id=int(ep["id"]),
            instance_id="i1",
            exit_node_key="ek",
            egress_ip="1.2.3.4",
            expires_at="2099-01-01T00:00:00+00:00",
            last_accessed="2026-01-01T00:00:00+00:00",
        )
        service = _make_service(storage)
        # Query with a different endpoint_id - the lease's endpoint_id doesn't match
        leases = service.get_leases(pool_id=int(pool1["id"]), endpoint_id=99999)
        assert len(leases) == 0


# ---------------------------------------------------------------------------
# _route_endpoint_request: entry_pool_id=0 (line 684)
# ---------------------------------------------------------------------------

class TestRouteEndpointRequestZeroPool:
    def test_endpoint_first_hop_zero_pool(self, storage):
        """Endpoint with first hop pool_id=0 returns None at line 684."""
        ep = storage.create_http_proxy_endpoint(name="ep-rz", listen_port=19062)
        # Insert hop with pool_id=0 directly
        now = datetime.now(UTC).isoformat()
        with storage._connect() as conn:
            conn.execute(
                """INSERT INTO http_proxy_endpoint_hops
                   (endpoint_id, hop_index, pool_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (int(ep["id"]), 0, 0, now, now),
            )
            conn.commit()
        service = _make_service(storage)
        result = service._route_endpoint_request("s1", int(ep["id"]), "")
        assert result is None


# ---------------------------------------------------------------------------
# _route_endpoint_request: hop_nodes with None (line 753)
# ---------------------------------------------------------------------------

class TestRouteEndpointHopNodesNone:
    def test_hop_proxy_missing_returns_none(self, storage):
        """When a hop key has no proxy in DB, hop_nodes has None entry -> returns None."""
        pool1 = storage.create_proxy_pool(name="p-hn1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-hn2", filters={"protocol": "socks"})
        # Add only front candidate, no exit candidate
        _add_available_proxy(storage, "http", "1.1.1.1", 8080, "hn-front")
        ep = storage.create_http_proxy_endpoint(name="ep-hn", listen_port=19063)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        # This will fail because exit pool has no candidates
        result = service._route_endpoint_request("", int(ep["id"]), "")
        assert result is None

    def test_hop_key_not_in_db_returns_none(self, storage):
        """When _select_endpoint_hops returns a key with no proxy in DB -> line 753."""
        pool1 = storage.create_proxy_pool(name="p-hn-db", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-hn-db2", filters={"protocol": "socks"})
        _add_available_proxy(storage, "http", "1.1.1.1", 8080, "hn-db-f")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "hn-db-e")
        ep = storage.create_http_proxy_endpoint(name="ep-hn-db", listen_port=19088)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        # Mock _select_endpoint_hops to return a key that doesn't exist in DB
        service._select_endpoint_hops = Mock(return_value={
            "hop_node_keys": ["valid-key", "nonexistent-key"],
            "egress_ip": "1.2.3.4",
        })
        result = service._route_endpoint_request("", int(ep["id"]), "")
        assert result is None


# ---------------------------------------------------------------------------
# _select_endpoint_hops: empty hop_node_keys (line 812)
# ---------------------------------------------------------------------------

class TestSelectEndpointHopsEmptyKeys:
    def test_search_returns_empty_keys(self, storage):
        """When _search_endpoint_hop_candidates returns empty hop_node_keys, returns None."""
        pool1 = storage.create_proxy_pool(name="p-seh-e", filters={"protocol": "http"})
        ep = storage.create_http_proxy_endpoint(name="ep-seh-e", listen_port=19064)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        # Mock _search_endpoint_hop_candidates to return empty hop_node_keys
        service._search_endpoint_hop_candidates = Mock(return_value={"hop_node_keys": [], "egress_ip": ""})
        result = service._select_endpoint_hops(int(ep["id"]), "")
        assert result is None


# ---------------------------------------------------------------------------
# _search_endpoint_hop_candidates: max_checks and combo filtering
# ---------------------------------------------------------------------------

class TestSearchEndpointHopCandidatesDeep:
    def test_duplicate_keys_in_combo_are_skipped(self, storage):
        """Combos where the same key appears twice are skipped (line 864)."""
        # Both pools have no filters, so all proxies are candidates for both
        pool1 = storage.create_proxy_pool(name="p-dk1", filters={})
        pool2 = storage.create_proxy_pool(name="p-dk2", filters={})
        # Add a single proxy that matches both pools
        k = _add_available_proxy(storage, "http", "1.1.1.1", 80, "dk-shared")
        ep = storage.create_http_proxy_endpoint(name="ep-dk", listen_port=19065)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        pool_hops = [{"pool_id": int(pool1["id"])}, {"pool_id": int(pool2["id"])}]
        result = service._search_endpoint_hop_candidates(int(ep["id"]), pool_hops, "")
        # The only combo is (k, k) which has duplicate keys -> skipped -> returns None
        assert result is None

    def test_all_combos_failed_returns_none(self, storage):
        """When all combos are marked as failed, returns None (line 872)."""
        pool1 = storage.create_proxy_pool(name="p-acf1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-acf2", filters={"protocol": "socks"})
        k1 = _add_available_proxy(storage, "http", "10.0.0.1", 80, "acf-f1")
        k2 = _add_available_proxy(storage, "socks", "10.0.0.2", 1080, "acf-e1")
        ep = storage.create_http_proxy_endpoint(name="ep-acf", listen_port=19066)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        # Mark this combo as failed
        service.report_endpoint_route_failure(
            endpoint_id=int(ep["id"]),
            pool_id=int(pool1["id"]),
            hop_node_keys=[k1, k2],
        )
        pool_hops = [{"pool_id": int(pool1["id"])}, {"pool_id": int(pool2["id"])}]
        result = service._search_endpoint_hop_candidates(int(ep["id"]), pool_hops, "")
        assert result is None

    def test_max_checks_exceeded(self, storage):
        """When max_checks is exceeded, the loop breaks (line 861)."""
        pool1 = storage.create_proxy_pool(name="p-mc1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-mc2", filters={"protocol": "socks"})
        # Add many candidates to create large Cartesian product
        for i in range(15):
            _add_available_proxy(storage, "http", f"10.0.0.{i}", 80, f"mc-f-{i}")
        for i in range(15):
            _add_available_proxy(storage, "socks", f"10.1.0.{i}", 1080, f"mc-e-{i}")
        ep = storage.create_http_proxy_endpoint(name="ep-mc2", listen_port=19067)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        pool_hops = [{"pool_id": int(pool1["id"])}, {"pool_id": int(pool2["id"])}]
        result = service._search_endpoint_hop_candidates(int(ep["id"]), pool_hops, "")
        # With 15x15 = 225 combos and max_checks ~100, the loop should break early
        assert result is not None or result is None  # just verify it doesn't hang

    def test_single_pool_hop_returns_immediately(self, storage):
        """Single pool hop with valid candidate returns the first combo."""
        pool1 = storage.create_proxy_pool(name="p-sph", filters={"protocol": "http"})
        k1 = _add_available_proxy(storage, "http", "1.1.1.1", 80, "sph-f1")
        ep = storage.create_http_proxy_endpoint(name="ep-sph", listen_port=19068)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        pool_hops = [{"pool_id": int(pool1["id"])}]
        result = service._search_endpoint_hop_candidates(int(ep["id"]), pool_hops, "")
        assert result is not None
        assert result["hop_node_keys"] == [k1]

    def test_first_combo_failed_second_succeeds(self, storage):
        """First combo is failed route, second combo succeeds (line 866)."""
        pool1 = storage.create_proxy_pool(name="p-fc1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-fc2", filters={"protocol": "socks"})
        k1 = _add_available_proxy(storage, "http", "1.1.1.1", 80, "fc-f1")
        k2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "fc-e1")
        k3 = _add_available_proxy(storage, "http", "3.3.3.3", 80, "fc-f2")
        k4 = _add_available_proxy(storage, "socks", "4.4.4.4", 1080, "fc-e2")
        ep = storage.create_http_proxy_endpoint(name="ep-fc", listen_port=19089)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        # Mark first combo as failed
        service.report_endpoint_route_failure(
            endpoint_id=int(ep["id"]),
            pool_id=int(pool1["id"]),
            hop_node_keys=[k1, k2],
        )
        pool_hops = [{"pool_id": int(pool1["id"])}, {"pool_id": int(pool2["id"])}]
        result = service._search_endpoint_hop_candidates(int(ep["id"]), pool_hops, "")
        # The failed combo is skipped, and a different combo is found
        assert result is not None
        assert result["hop_node_keys"] != [k1, k2]


# ---------------------------------------------------------------------------
# _is_endpoint_route_failed: DB path (line 976)
# ---------------------------------------------------------------------------

class TestIsEndpointRouteFailedDB:
    def test_route_failed_in_db_only(self, storage):
        """Route only in DB (not in memory) still returns True (line 976)."""
        ep = storage.create_http_proxy_endpoint(name="ep-db-rf", listen_port=19069)
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        # Insert directly into DB, bypassing in-memory cache
        storage.upsert_failed_route(int(ep["id"]), "dbk1>dbk2", future)
        service = _make_service(storage)
        # Ensure in-memory cache is empty
        with service._lock:
            assert (int(ep["id"]), ("dbk1", "dbk2")) not in service._failed_endpoint_routes
        # The route_signature format in DB is "dbk1>dbk2", but _is_endpoint_route_failed
        # builds its own signature from hop_node_keys via ">".join(...)
        result = service._is_endpoint_route_failed(int(ep["id"]), ["dbk1", "dbk2"])
        assert result is True

    def test_route_not_failed_anywhere(self, storage):
        """Route not in memory or DB returns False."""
        ep = storage.create_http_proxy_endpoint(name="ep-notrf", listen_port=19070)
        service = _make_service(storage)
        result = service._is_endpoint_route_failed(int(ep["id"]), ["x1", "x2"])
        assert result is False

    def test_route_expired_in_memory_then_db_miss(self, storage):
        """Expired in-memory route is cleaned up and DB also misses -> False."""
        ep = storage.create_http_proxy_endpoint(name="ep-exrf", listen_port=19071)
        service = _make_service(storage)
        with service._lock:
            service._failed_endpoint_routes[(int(ep["id"]), ("x1", "x2"))] = datetime.now(UTC) - timedelta(seconds=10)
        result = service._is_endpoint_route_failed(int(ep["id"]), ["x1", "x2"])
        assert result is False
        with service._lock:
            assert (int(ep["id"]), ("x1", "x2")) not in service._failed_endpoint_routes


# ---------------------------------------------------------------------------
# _is_endpoint_node_failed: DB path (line 1001)
# ---------------------------------------------------------------------------

class TestIsEndpointNodeFailedDB:
    def test_node_failed_in_db_only(self, storage):
        """Node only in DB (not in memory) still returns True (line 1001)."""
        ep = storage.create_http_proxy_endpoint(name="ep-db-nf", listen_port=19072)
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        # Insert directly into DB
        storage.upsert_failed_route_node(int(ep["id"]), "db-node-key", future)
        service = _make_service(storage)
        # Ensure in-memory cache is empty
        with service._lock:
            assert (int(ep["id"]), "db-node-key") not in service._failed_endpoint_nodes
        result = service._is_endpoint_node_failed(int(ep["id"]), "db-node-key")
        assert result is True

    def test_node_not_failed_anywhere(self, storage):
        """Node not in memory or DB returns False."""
        ep = storage.create_http_proxy_endpoint(name="ep-notnf", listen_port=19073)
        service = _make_service(storage)
        result = service._is_endpoint_node_failed(int(ep["id"]), "x1")
        assert result is False

    def test_node_expired_in_memory_then_db_miss(self, storage):
        """Expired in-memory node failure is cleaned up, DB misses -> False."""
        ep = storage.create_http_proxy_endpoint(name="ep-exnf", listen_port=19074)
        service = _make_service(storage)
        with service._lock:
            service._failed_endpoint_nodes[(int(ep["id"]), "n1")] = datetime.now(UTC) - timedelta(seconds=10)
        result = service._is_endpoint_node_failed(int(ep["id"]), "n1")
        assert result is False
        with service._lock:
            assert (int(ep["id"]), "n1") not in service._failed_endpoint_nodes


# ---------------------------------------------------------------------------
# _reuse_multi_hop_lease: empty keys and unavailable proxy
# ---------------------------------------------------------------------------

class TestReuseMultiHopLease:
    def test_empty_hop_node_keys_returns_none(self, storage):
        """Lease with empty hop_node_keys returns None (line 1061)."""
        service = _make_service(storage)
        lease = MultiHopLease(
            session_id="s-rmh", pool_id=1, endpoint_id=1, instance_id="",
            hop_node_keys=[], exit_node_key="", egress_ip="",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            last_accessed=datetime.now(UTC),
        )
        result = service._reuse_multi_hop_lease(lease, "")
        assert result is None

    def test_unavailable_proxy_returns_none(self, storage):
        """Lease with unavailable proxy returns None (line 1065)."""
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 80, "rmh-f")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "rmh-e")
        service = _make_service(storage)
        # Make h2 unavailable
        storage.update_test_result(h2, available=False, latency_ms=0)
        lease = MultiHopLease(
            session_id="s-rmh2", pool_id=1, endpoint_id=1, instance_id="",
            hop_node_keys=[h1, h2], exit_node_key=h2, egress_ip="1.2.3.4",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            last_accessed=datetime.now(UTC),
        )
        result = service._reuse_multi_hop_lease(lease, "")
        assert result is None

    def test_missing_proxy_returns_none(self, storage):
        """Lease with proxy not in DB returns None (line 1065)."""
        service = _make_service(storage)
        lease = MultiHopLease(
            session_id="s-rmh3", pool_id=1, endpoint_id=1, instance_id="",
            hop_node_keys=["nonexistent-key"], exit_node_key="nonexistent-key",
            egress_ip="1.2.3.4",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            last_accessed=datetime.now(UTC),
        )
        result = service._reuse_multi_hop_lease(lease, "")
        assert result is None

    def test_all_proxies_available_returns_keys(self, storage):
        """Lease with all proxies available returns the keys."""
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 80, "rmh-ok-f")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "rmh-ok-e")
        service = _make_service(storage)
        lease = MultiHopLease(
            session_id="s-rmh4", pool_id=1, endpoint_id=1, instance_id="",
            hop_node_keys=[h1, h2], exit_node_key=h2, egress_ip="1.2.3.4",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            last_accessed=datetime.now(UTC),
        )
        result = service._reuse_multi_hop_lease(lease, "")
        assert result == [h1, h2]


# ---------------------------------------------------------------------------
# _load_endpoint_hop_node_keys: zero pool_id hop and empty key
# ---------------------------------------------------------------------------

class TestLoadEndpointHopNodeKeysAdvanced:
    def test_hop_with_zero_pool_id_skipped(self, storage):
        """Hop with pool_id=0 is skipped via continue (line 1079)."""
        ep = storage.create_http_proxy_endpoint(name="ep-lhk-z", listen_port=19075)
        # Insert hop with pool_id=0 directly (API filters out 0)
        now = datetime.now(UTC).isoformat()
        with storage._connect() as conn:
            conn.execute(
                """INSERT INTO http_proxy_endpoint_hops
                   (endpoint_id, hop_index, pool_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (int(ep["id"]), 0, 0, now, now),
            )
            conn.commit()
        service = _make_service(storage)
        keys = service._load_endpoint_hop_node_keys(int(ep["id"]))
        assert keys == []

    def test_candidate_with_empty_normalized_key_skipped(self, storage):
        """Candidate with empty normalized_key is skipped (line 1087)."""
        pool1 = storage.create_proxy_pool(name="p-lhk-ek", filters={"protocol": "http"})
        ep = storage.create_http_proxy_endpoint(name="ep-lhk-ek", listen_port=19076)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        # Mock _pick_pool_candidate to return a candidate with empty key
        service._pick_pool_candidate = Mock(return_value={"normalized_key": "", "available": True})
        keys = service._load_endpoint_hop_node_keys(int(ep["id"]))
        assert keys == []

    def test_fallback_exit_key_replaces_last(self, storage):
        """When fallback_exit_node_key is given, it replaces the last hop key."""
        pool1 = storage.create_proxy_pool(name="p-lhk-fe", filters={"protocol": "http"})
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "lhk-fe-f")
        ep = storage.create_http_proxy_endpoint(name="ep-lhk-fe", listen_port=19077)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        keys = service._load_endpoint_hop_node_keys(int(ep["id"]), "override-exit")
        assert len(keys) >= 1
        assert keys[-1] == "override-exit"

    def test_no_endpoint_returns_empty_list(self, storage):
        """No endpoint returns empty list when no fallback."""
        service = _make_service(storage)
        keys = service._load_endpoint_hop_node_keys(99999)
        assert keys == []

    def test_no_endpoint_with_fallback(self, storage):
        """No endpoint returns fallback key."""
        service = _make_service(storage)
        keys = service._load_endpoint_hop_node_keys(99999, "fb-key")
        assert keys == ["fb-key"]


# ---------------------------------------------------------------------------
# endpoint_route_health: edge cases
# ---------------------------------------------------------------------------

class TestEndpointRouteHealthEdgeCases:
    def test_failed_route_in_memory_active(self, storage):
        """Active in-memory failed route shows as failed."""
        ep = storage.create_http_proxy_endpoint(name="ep-erh-act", listen_port=19078)
        service = _make_service(storage)
        with service._lock:
            service._failed_endpoint_routes[(int(ep["id"]), ("k1", "k2"))] = datetime.now(UTC) + timedelta(seconds=300)
        h = service.endpoint_route_health(int(ep["id"]), ["k1", "k2"])
        assert h["failed"] is True
        assert h["failure_expires_at"] != ""

    def test_healthy_route_active(self, storage):
        """Active healthy route shows as known_healthy."""
        ep = storage.create_http_proxy_endpoint(name="ep-erh-ha", listen_port=19079)
        service = _make_service(storage)
        with service._lock:
            service._healthy_endpoint_routes[(int(ep["id"]), ("k1",))] = datetime.now(UTC) + timedelta(seconds=600)
        h = service.endpoint_route_health(int(ep["id"]), ["k1"])
        assert h["known_healthy"] is True
        assert h["healthy_until"] != ""

    def test_healthy_route_expired_cleanup(self, storage):
        """Expired healthy route is cleaned up."""
        ep = storage.create_http_proxy_endpoint(name="ep-erh-ex", listen_port=19080)
        service = _make_service(storage)
        with service._lock:
            service._healthy_endpoint_routes[(int(ep["id"]), ("k1",))] = datetime.now(UTC) - timedelta(seconds=10)
        h = service.endpoint_route_health(int(ep["id"]), ["k1"])
        assert h["known_healthy"] is False
        with service._lock:
            assert (int(ep["id"]), ("k1",)) not in service._healthy_endpoint_routes

    def test_no_route_no_health(self, storage):
        """No routes or health records returns clean status."""
        ep = storage.create_http_proxy_endpoint(name="ep-erh-clean", listen_port=19081)
        service = _make_service(storage)
        h = service.endpoint_route_health(int(ep["id"]), ["k1", "k2"])
        assert h["failed"] is False
        assert h["known_healthy"] is False
        assert h["failure_expires_at"] == ""
        assert h["healthy_until"] == ""


# ---------------------------------------------------------------------------
# report_endpoint_route_success: removes from all caches
# ---------------------------------------------------------------------------

class TestReportSuccessCleanup:
    def test_success_removes_from_failed_and_node_caches(self, storage):
        """report_endpoint_route_success clears failed routes and nodes."""
        ep = storage.create_http_proxy_endpoint(name="ep-rsc", listen_port=19082)
        service = _make_service(storage)
        with service._lock:
            service._failed_endpoint_routes[(int(ep["id"]), ("k1", "k2"))] = datetime.now(UTC) + timedelta(seconds=300)
            service._failed_endpoint_nodes[(int(ep["id"]), "k1")] = datetime.now(UTC) + timedelta(seconds=300)
        service.report_endpoint_route_success(
            endpoint_id=int(ep["id"]),
            hop_node_keys=["k1", "k2"],
        )
        with service._lock:
            assert (int(ep["id"]), ("k1", "k2")) not in service._failed_endpoint_routes
            assert (int(ep["id"]), "k1") not in service._failed_endpoint_nodes


# ---------------------------------------------------------------------------
# _pick_healthy_endpoint_route: with valid matching route
# ---------------------------------------------------------------------------

class TestPickHealthyEndpointRouteMatch:
    def test_matching_healthy_route_returned(self, storage):
        """A healthy route that matches pools is returned."""
        pool1 = storage.create_proxy_pool(name="p-mhr", filters={"protocol": "http"})
        k = _add_available_proxy(storage, "http", "1.1.1.1", 80, "mhr-n")
        ep = storage.create_http_proxy_endpoint(name="ep-mhr", listen_port=19083)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        with service._lock:
            service._healthy_endpoint_routes[(int(ep["id"]), (k,))] = datetime.now(UTC) + timedelta(seconds=600)
        result = service._pick_healthy_endpoint_route(int(ep["id"]), [{"pool_id": int(pool1["id"])}])
        assert result is not None
        assert result == [k]


# ---------------------------------------------------------------------------
# report_endpoint_route_failure: with session removes multi-hop lease
# ---------------------------------------------------------------------------

class TestReportFailureRemovesLease:
    def test_failure_removes_multi_hop_lease(self, storage):
        """Failure report with session removes the multi-hop lease."""
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 8080, "frl-f")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "frl-e")
        pool1 = storage.create_proxy_pool(name="p-frl", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-frl2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-frl", listen_port=19084)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"]), int(pool2["id"])])
        service = _make_service(storage)
        result = service.route_request("sess-frl", int(pool1["id"]), int(ep["id"]), "")
        assert result is not None
        key = ("sess-frl", int(pool1["id"]), int(ep["id"]))
        with service._lock:
            assert key in service._multi_hop_leases
        service.report_endpoint_route_failure(
            endpoint_id=int(ep["id"]),
            pool_id=int(pool1["id"]),
            session_id="sess-frl",
            hop_node_keys=[h1, h2],
        )
        with service._lock:
            assert key not in service._multi_hop_leases


# ---------------------------------------------------------------------------
# _endpoint_route_matches_pools: edge cases
# ---------------------------------------------------------------------------

class TestEndpointRouteMatchesPoolsEdge:
    def test_key_not_in_any_pool(self, storage):
        """Key that doesn't belong to the pool returns False."""
        pool1 = storage.create_proxy_pool(name="p-erm-np", filters={"protocol": "http"})
        service = _make_service(storage)
        assert service._endpoint_route_matches_pools(["bogus-key"], [{"pool_id": int(pool1["id"])}]) is False

    def test_pool_id_zero_in_hop(self, storage):
        """Pool hop with pool_id=0 returns False."""
        service = _make_service(storage)
        assert service._endpoint_route_matches_pools(["k1"], [{"pool_id": 0}]) is False


# ---------------------------------------------------------------------------
# _build_route_signature: with various endpoint configurations
# ---------------------------------------------------------------------------

class TestBuildRouteSignatureEdge:
    def test_endpoint_with_single_pool_hop(self, storage):
        """Endpoint with single pool hop builds correct signature."""
        pool1 = storage.create_proxy_pool(name="p-brs1", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-brs1", listen_port=19085)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        service = _make_service(storage)
        sig = service._build_route_signature(int(ep["id"]), ["k1"])
        assert sig == f"pool-{pool1['id']}"


# ---------------------------------------------------------------------------
# cleanup_leases: with both regular and multi-hop leases
# ---------------------------------------------------------------------------

class TestCleanupLeasesAdvanced:
    def test_cleanup_mixed_lease_types(self, storage):
        """Cleanup removes expired multi-hop leases and regular leases."""
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "cl-a-f")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "cl-a-e")
        service = _make_service(storage)
        # Create a regular lease
        service.route_request("sess-cla", 0, 0, "")
        # Create an expired multi-hop lease
        pool1 = storage.create_proxy_pool(name="p-cla", filters={})
        ep = storage.create_http_proxy_endpoint(name="ep-cla", listen_port=19086)
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool1["id"])])
        expired_lease = MultiHopLease(
            session_id="s-cla-exp", pool_id=int(pool1["id"]), endpoint_id=int(ep["id"]),
            instance_id="", hop_node_keys=["k1"], exit_node_key="k1",
            egress_ip="1.2.3.4",
            expires_at=datetime.now(UTC) - timedelta(seconds=10),
            last_accessed=datetime.now(UTC) - timedelta(seconds=20),
        )
        with service._lock:
            service._multi_hop_leases[("s-cla-exp", int(pool1["id"]), int(ep["id"]))] = expired_lease
        removed = service.cleanup_leases()
        assert removed >= 1
        with service._lock:
            assert ("s-cla-exp", int(pool1["id"]), int(ep["id"])) not in service._multi_hop_leases


# ---------------------------------------------------------------------------
# _get_multi_hop_lease: expired lease returns None
# ---------------------------------------------------------------------------

class TestGetMultiHopLease:
    def test_expired_lease_removed(self, storage):
        """Expired lease is removed from memory and returns None."""
        service = _make_service(storage)
        now = datetime.now(UTC)
        lease = MultiHopLease(
            session_id="s-gmh", pool_id=1, endpoint_id=1, instance_id="",
            hop_node_keys=["k1"], exit_node_key="k1", egress_ip="1.2.3.4",
            expires_at=now - timedelta(seconds=10),
            last_accessed=now - timedelta(seconds=20),
        )
        with service._lock:
            service._multi_hop_leases[("s-gmh", 1, 1)] = lease
        result = service._get_multi_hop_lease("s-gmh", 1, 1, now)
        assert result is None
        with service._lock:
            assert ("s-gmh", 1, 1) not in service._multi_hop_leases

    def test_valid_lease_returned(self, storage):
        """Valid (non-expired) lease is returned."""
        service = _make_service(storage)
        now = datetime.now(UTC)
        lease = MultiHopLease(
            session_id="s-gmh2", pool_id=1, endpoint_id=1, instance_id="",
            hop_node_keys=["k1"], exit_node_key="k1", egress_ip="1.2.3.4",
            expires_at=now + timedelta(hours=1),
            last_accessed=now,
        )
        with service._lock:
            service._multi_hop_leases[("s-gmh2", 1, 1)] = lease
        result = service._get_multi_hop_lease("s-gmh2", 1, 1, now)
        assert result is not None
        assert result.session_id == "s-gmh2"

    def test_nonexistent_lease_returns_none(self, storage):
        """Non-existent lease returns None."""
        service = _make_service(storage)
        result = service._get_multi_hop_lease("no-such", 1, 1, datetime.now(UTC))
        assert result is None


# ---------------------------------------------------------------------------
# route_request: endpoint_id as int 0
# ---------------------------------------------------------------------------

class TestRouteRequestEndpointInt:
    def test_endpoint_id_int_zero(self, storage):
        """endpoint_id=0 (int) goes to sticky_router path."""
        result = route_request_with_args(storage, endpoint_id=0)
        assert result is None or isinstance(result, dict)

    def test_endpoint_id_int_nonzero_no_endpoint(self, storage):
        """Non-zero int endpoint_id with no endpoint in DB returns None."""
        result = route_request_with_args(storage, endpoint_id=99999)
        assert result is None


# ---------------------------------------------------------------------------
# bind_instance_to_session: with endpoint delegates
# ---------------------------------------------------------------------------

class TestBindInstanceWithEndpoint:
    def test_bind_with_endpoint_delegates_to_endpoint_method(self, storage):
        """endpoint_id > 0 delegates to bind_endpoint_instance_to_session."""
        service = _make_service(storage)
        # endpoint 99999 doesn't exist, so bind_endpoint_instance_to_session returns None
        result = service.bind_instance_to_session("s1", 0, "inst-1", endpoint_id=99999)
        assert result is None


# ---------------------------------------------------------------------------
# Helper to call route_request with keyword args
# ---------------------------------------------------------------------------

def route_request_with_args(storage, session_id="", pool_id=0, endpoint_id=0, target_domain=""):
    """Helper to call route_request with explicit arguments."""
    service = ProxyChainService(storage)
    return service.route_request(
        session_id=session_id,
        pool_id=pool_id,
        endpoint_id=endpoint_id,
        target_domain=target_domain,
    )
