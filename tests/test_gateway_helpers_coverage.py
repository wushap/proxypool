"""Tests to cover remaining uncovered lines in gateway_helpers."""

from types import SimpleNamespace

from proxypool.api.gateway_helpers import (
    build_endpoint_status_response,
    build_hop_pool_status,
    build_hop_transition_status,
    endpoint_route_health,
    latest_active_hop_keys,
    proxy_status_summary,
)


# -- proxy_status_summary ---------------------------------------------------


def test_proxy_status_summary_none_returns_empty() -> None:
    """Line 11: proxy=None should return {}."""
    assert proxy_status_summary(None) == {}


def test_proxy_status_summary_populates_fields() -> None:
    result = proxy_status_summary(
        {"normalized_key": "k1", "name": "n", "protocol": "http"},
        active_key="k1",
    )
    assert result["key"] == "k1"
    assert result["active"] is True


# -- latest_active_hop_keys -------------------------------------------------


def test_latest_active_hop_keys_falls_back_to_instances() -> None:
    """Line 63: no leases with hop_node_keys, use instance candidates."""
    leases: list[dict] = []
    instances = [
        {
            "instance_id": "i1",
            "endpoint_id": 1,
            "hop_node_keys": ["a", "b"],
            "status": "running",
            "updated_at": "2025-01-01",
        }
    ]
    result = latest_active_hop_keys(1, leases, instances)
    assert result == ["a", "b"]


def test_latest_active_hop_keys_uses_live_lease() -> None:
    """Line 48: lease with hop_node_keys and running instance."""
    leases = [
        {
            "instance_id": "i1",
            "hop_node_keys": ["x"],
            "last_accessed": "2025-06-01",
        }
    ]
    instances = [{"instance_id": "i1", "status": "running"}]
    result = latest_active_hop_keys(1, leases, instances)
    assert result == ["x"]


def test_latest_active_hop_keys_empty_when_nothing_matches() -> None:
    result = latest_active_hop_keys(99, [], [])
    assert result == []


# -- endpoint_route_health --------------------------------------------------


def test_endpoint_route_health_returns_method_result() -> None:
    """Line 71: chain_service has the method and returns a dict."""
    svc = SimpleNamespace(
        endpoint_route_health=lambda eid, keys: {"failed": True, "known_healthy": True}
    )
    result = endpoint_route_health(svc, 1, ["a", "b"])
    assert result["failed"] is True
    assert result["known_healthy"] is True


def test_endpoint_route_health_suppresses_exception() -> None:
    """Exception from endpoint_route_health is suppressed, falls to default."""

    def _boom(eid, keys):
        raise RuntimeError("nope")

    svc = SimpleNamespace(endpoint_route_health=_boom)
    result = endpoint_route_health(svc, 1, ["a"])
    assert result["failed"] is False


def test_endpoint_route_health_default_when_no_method() -> None:
    svc = object()
    result = endpoint_route_health(svc, 1, ["a"])
    assert result["failed"] is False


# -- build_hop_pool_status --------------------------------------------------


def test_build_hop_pool_status_active_proxy_not_in_candidates() -> None:
    """Line 106: active_proxy exists but is not in pool candidates -> insert."""

    class FakeStorage:
        def get_proxy_pool(self, pid):
            return {"id": pid}

        def list_proxy_pool_candidates(self, pid, limit=500):
            # Return a candidate with a different key than the active one
            return [{"normalized_key": "other", "available": True}]

        def get_proxy_by_key(self, key):
            if key == "active1":
                return {"normalized_key": "active1", "available": True}
            return None

    endpoint = {"hops": [{"pool_id": 1}]}
    result = build_hop_pool_status(FakeStorage(), 1, endpoint, ["active1"])
    assert len(result) == 1
    hop = result[0]
    # The active proxy should have been inserted as first node
    assert hop["nodes"][0]["key"] == "active1"
    assert hop["nodes"][0]["active"] is True


def test_build_hop_pool_status_no_active_key() -> None:
    """When active_hop_keys is shorter than hops, active_key defaults to ''."""

    class FakeStorage:
        def get_proxy_pool(self, pid):
            return {"id": pid}

        def list_proxy_pool_candidates(self, pid, limit=500):
            return []

        def get_proxy_by_key(self, key):
            return None

    endpoint = {"hops": [{"pool_id": 1}]}
    result = build_hop_pool_status(FakeStorage(), 1, endpoint, [])
    assert result[0]["active_node_key"] == ""
    assert result[0]["active_node"] is None


# -- build_hop_transition_status --------------------------------------------


def test_build_transition_status_capped_at_80_pairs() -> None:
    """Lines 176, 178: break when pairs >= 80."""

    def _dummy_health(eid, keys):
        return {"failed": False, "failure_expires_at": "", "known_healthy": False, "healthy_until": ""}

    svc = SimpleNamespace(endpoint_route_health=_dummy_health)

    # Create two hops with many healthy nodes each -> many pairs
    left_nodes = [{"key": f"l{i}", "healthy": True} for i in range(10)]
    right_nodes = [{"key": f"r{i}", "healthy": True} for i in range(10)]
    hop_pools = [
        {
            "nodes": left_nodes,
            "active_node_key": "",
            "active_node": None,
            "available": True,
        },
        {
            "nodes": right_nodes,
            "active_node_key": "",
            "active_node": None,
            "available": True,
        },
    ]
    result = build_hop_transition_status(svc, 1, hop_pools)
    assert len(result) == 1
    # Should be capped at 80 shown pairs (10*10=100 possible)
    assert result[0]["shown_pairs"] <= 80


def test_build_transition_status_active_pair_included() -> None:
    """Active pair should be included in pairs when both keys exist."""

    def _dummy_health(eid, keys):
        return {"failed": False, "failure_expires_at": "", "known_healthy": False, "healthy_until": ""}

    svc = SimpleNamespace(endpoint_route_health=_dummy_health)

    hop_pools = [
        {
            "nodes": [{"key": "a1", "healthy": True}],
            "active_node_key": "a1",
            "active_node": {"key": "a1", "healthy": True},
            "available": True,
        },
        {
            "nodes": [{"key": "b1", "healthy": True}],
            "active_node_key": "b1",
            "active_node": {"key": "b1", "healthy": True},
            "available": True,
        },
    ]
    result = build_hop_transition_status(svc, 1, hop_pools)
    assert len(result) == 1
    active_pairs = [p for p in result[0]["pairs"] if p.get("active")]
    assert len(active_pairs) == 1
    assert active_pairs[0]["hop_node_keys"] == ["a1", "b1"]


# -- build_endpoint_status_response -----------------------------------------


def test_build_endpoint_status_response_none_endpoint() -> None:
    """Line 203: storage returns None for endpoint -> empty dict."""

    class FakeStorage:
        def get_http_proxy_endpoint(self, eid):
            return None

    result = build_endpoint_status_response(FakeStorage(), object(), object(), 1)
    assert result == {}


def test_build_endpoint_status_response_full_flow() -> None:
    """Exercise the happy path through build_endpoint_status_response."""

    class FakeStorage:
        def get_http_proxy_endpoint(self, eid):
            return {"id": eid, "hops": [{"pool_id": 1}]}

        def get_proxy_pool(self, pid):
            return {"id": pid}

        def list_proxy_pool_candidates(self, pid, limit=500):
            return [{"normalized_key": "n1", "available": True}]

        def get_proxy_by_key(self, key):
            return None

    class FakeChainService:
        def get_leases(self, pool_id=None, endpoint_id=None):
            return []

        def endpoint_route_health(self, eid, keys):
            return {"failed": False, "failure_expires_at": "", "known_healthy": False, "healthy_until": ""}

    class FakeInstanceManager:
        def list_instances(self, endpoint_id=None):
            return [{"instance_id": "i1", "status": "running", "endpoint_id": endpoint_id, "hop_node_keys": ["n1"], "updated_at": ""}]

    result = build_endpoint_status_response(FakeStorage(), FakeChainService(), FakeInstanceManager(), 1)
    assert result["item"]["id"] == 1
    assert "hop_pools" in result
    assert "transitions" in result
    assert "summary" in result
