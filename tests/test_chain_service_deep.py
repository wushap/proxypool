"""Deep edge-case tests to push chain_service.py from 99% to 100% coverage."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from proxypool.models import ProxyNode
from proxypool.pool.chain_service import (
    MultiHopLease,
    ProxyChainService,
)
from proxypool.storage.sqlite import SQLiteProxyStorage


@pytest.fixture
def storage(tmp_path):
    db_path = tmp_path / "test_deep.db"
    return SQLiteProxyStorage(db_path)


def _add_proxy(
    storage: SQLiteProxyStorage, protocol: str, host: str, port: int, name: str
) -> str:
    node = ProxyNode(
        protocol=protocol,
        host=host,
        port=port,
        raw_link=f"{protocol}://{host}:{port}",
        name=name,
    )
    storage.upsert_proxy(node)
    return node.normalized_key()


def _add_available_proxy(
    storage: SQLiteProxyStorage,
    protocol: str,
    host: str,
    port: int,
    name: str,
    latency_ms: int = 10,
) -> str:
    key = _add_proxy(storage, protocol, host, port, name)
    storage.update_test_result(key, available=True, latency_ms=latency_ms)
    return key


# ---------------------------------------------------------------------------
# Branch 379->394: route_request session loop exits without break
# ---------------------------------------------------------------------------


class TestRouteRequestSessionNoMatch:
    """When route succeeds but get_leases returns no matching session lease,
    the for loop at line 379 exits without break, going directly to line 394."""

    def test_session_lease_not_in_get_leases(self, storage):
        """Mock get_leases to return empty list so the for loop never matches."""
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fa")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ea")
        service = ProxyChainService(storage)
        # Patch get_leases to return empty list even though route created a lease
        with patch.object(
            service.sticky_router,
            "get_leases",
            return_value=[],
        ):
            result = service.route_request("sess-nomatch", 0, 0, "")
        assert result is not None
        assert result["front_node"]["key"]
        # The lease was NOT persisted because get_leases returned empty
        lease = storage.get_sticky_lease("sess-nomatch", 0)
        assert lease is None

    def test_session_lease_wrong_session_id(self, storage):
        """get_leases returns leases but none match the session_id."""
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "fa2")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "ea2")
        service = ProxyChainService(storage)
        # Return a lease for a DIFFERENT session
        other_lease = {
            "session_id": "other-session",
            "pool_id": 0,
            "endpoint_id": 0,
            "instance_id": "",
            "exit_node_key": "e1",
            "egress_ip": "1.2.3.4",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "last_accessed": "2026-01-01T00:00:00+00:00",
        }
        with patch.object(
            service.sticky_router,
            "get_leases",
            return_value=[other_lease],
        ):
            result = service.route_request("sess-my", 0, 0, "")
        assert result is not None


# ---------------------------------------------------------------------------
# Branch 570: inherit_lease raises ValueError on target creation failure
# ---------------------------------------------------------------------------


class TestInheritLeaseTargetFailure:
    """When inherit_lease can't create the target lease, it raises ValueError."""

    def test_target_lease_creation_fails(self, storage):
        _add_available_proxy(storage, "http", "1.1.1.1", 80, "src-f")
        _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "src-e")
        service = ProxyChainService(storage)
        # Create source lease via normal routing
        service.route_request("source-sess", 0, 0, "")
        # Now mock route to return None for the target lease creation
        with patch.object(service.sticky_router, "route", return_value=None):
            with pytest.raises(ValueError, match="failed to create inherited lease"):
                service.inherit_lease(0, "source-sess", "target-sess")


# ---------------------------------------------------------------------------
# Branch 702->716: endpoint lease reuse fails (hops unavailable)
# ---------------------------------------------------------------------------


class TestEndpointLeaseReuseFails:
    """When a multi-hop lease exists but its hops are no longer available,
    _reuse_multi_hop_lease returns None and the code falls through to
    line 716 (select new hops)."""

    def test_leased_hop_becomes_unavailable(self, storage):
        """Make the ACTUAL leased hop node unavailable."""
        h1 = _add_available_proxy(storage, "http", "1.1.1.1", 8080, "rl-h1")
        h2 = _add_available_proxy(storage, "socks", "2.2.2.2", 1080, "rl-h2")
        _add_available_proxy(storage, "socks", "3.3.3.3", 1080, "rl-h2b")
        pool1 = storage.create_proxy_pool(name="p1", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p2", filters={"protocol": "socks"})
        ep = storage.create_http_proxy_endpoint(name="ep-rl", listen_port=19100)
        storage.replace_http_proxy_endpoint_hops(
            int(ep["id"]), [int(pool1["id"]), int(pool2["id"])]
        )
        service = ProxyChainService(storage)
        # First route creates a lease
        r1 = service.route_request(
            "sess-rl", int(pool1["id"]), int(ep["id"]), ""
        )
        assert r1 is not None
        # Identify the ACTUAL leased exit node (could be h2 or h2b)
        lease_key = ("sess-rl", int(pool1["id"]), int(ep["id"]))
        with service._lock:
            lease = service._multi_hop_leases.get(lease_key)
        assert lease is not None
        # Make the ACTUAL leased exit hop unavailable
        leased_exit = lease.hop_node_keys[-1]
        storage.update_test_result(leased_exit, available=False, latency_ms=0)
        # Second route: lease exists but hop unavailable -> reuse fails -> new route
        r2 = service.route_request(
            "sess-rl", int(pool1["id"]), int(ep["id"]), ""
        )
        assert r2 is not None
        # The new route should use a different exit node
        assert r2["hop_node_keys"][-1] != leased_exit


# ---------------------------------------------------------------------------
# Branch 861: _search_endpoint_hop_candidates max_checks break
# ---------------------------------------------------------------------------


class TestMaxChecksBreak:
    """When the combo count exceeds max_checks, the loop breaks at line 861."""

    def test_many_combos_exceed_max_checks(self, storage):
        """Create enough candidates so that all combos checked before
        max_checks are marked failed, forcing the break."""
        pool1 = storage.create_proxy_pool(name="p-mc", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-mc2", filters={"protocol": "socks"})
        # Create 20 http and 20 socks proxies, all with same latency
        for i in range(20):
            _add_available_proxy(
                storage, "http", f"10.0.0.{i}", 80, f"mc-h-{i}", latency_ms=50
            )
        for i in range(20):
            _add_available_proxy(
                storage, "socks", f"10.1.0.{i}", 1080, f"mc-s-{i}", latency_ms=50
            )

        ep = storage.create_http_proxy_endpoint(name="ep-mc", listen_port=19101)
        storage.replace_http_proxy_endpoint_hops(
            int(ep["id"]), [int(pool1["id"]), int(pool2["id"])]
        )
        service = ProxyChainService(storage)
        # max_checks = max(1, min(1000, max(100, (20+20)*2))) = 100
        # Get the actual sorted candidates to mark the right combos
        c1 = service.storage.list_proxy_pool_candidates(
            int(pool1["id"]), limit=200, exclude_keys=set()
        )
        c2 = service.storage.list_proxy_pool_candidates(
            int(pool2["id"]), limit=200, exclude_keys=set()
        )
        c1_sorted = sorted(c1, key=service._candidate_score)
        c2_sorted = sorted(c2, key=service._candidate_score)
        ep_id = int(ep["id"])
        # Mark the first 5 http x all 20 socks = 100 combos as failed
        for i in range(5):
            for j in range(20):
                h_key = c1_sorted[i]["normalized_key"]
                s_key = c2_sorted[j]["normalized_key"]
                service._failed_endpoint_routes[
                    (ep_id, (h_key, s_key))
                ] = datetime.now(UTC) + timedelta(hours=1)

        pool_hops = [
            {"pool_id": int(pool1["id"])},
            {"pool_id": int(pool2["id"])},
        ]
        result = service._search_endpoint_hop_candidates(
            ep_id, pool_hops, ""
        )
        # After 100 failed combos, checked=101 > max_checks=100 -> break -> None
        assert result is None


# ---------------------------------------------------------------------------
# Branch 866: _search_endpoint_hop_candidates route-failed continue
# ---------------------------------------------------------------------------


class TestRouteFailedContinue:
    """When the best-scored combo is a failed route, the continue at
    line 866 is hit and the next combo is tried."""

    def test_best_combo_is_failed_route(self, storage):
        """Create two pools where the lowest-latency combo is marked
        as a failed route, forcing the continue at line 866."""
        pool1 = storage.create_proxy_pool(name="p-rf", filters={"protocol": "http"})
        pool2 = storage.create_proxy_pool(name="p-rf2", filters={"protocol": "socks"})
        # k_a: low latency (best score) for pool1
        k_a = _add_available_proxy(
            storage, "http", "1.1.1.1", 80, "rf-best-f", latency_ms=1
        )
        # k_b: high latency for pool1
        k_b = _add_available_proxy(
            storage, "http", "2.2.2.2", 80, "rf-slow-f", latency_ms=100
        )
        # k_c: low latency (best score) for pool2
        k_c = _add_available_proxy(
            storage, "socks", "3.3.3.3", 1080, "rf-best-e", latency_ms=1
        )
        # k_d: high latency for pool2
        k_d = _add_available_proxy(
            storage, "socks", "4.4.4.4", 1080, "rf-slow-e", latency_ms=100
        )
        ep = storage.create_http_proxy_endpoint(name="ep-rf", listen_port=19104)
        storage.replace_http_proxy_endpoint_hops(
            int(ep["id"]), [int(pool1["id"]), int(pool2["id"])]
        )
        service = ProxyChainService(storage)
        ep_id = int(ep["id"])
        # Product order (sorted by score): (k_a,k_c), (k_a,k_d), (k_b,k_c), (k_b,k_d)
        # Mark the BEST combo (k_a, k_c) as failed
        service._failed_endpoint_routes[
            (ep_id, (k_a, k_c))
        ] = datetime.now(UTC) + timedelta(hours=1)
        pool_hops = [
            {"pool_id": int(pool1["id"])},
            {"pool_id": int(pool2["id"])},
        ]
        result = service._search_endpoint_hop_candidates(
            ep_id, pool_hops, ""
        )
        # First combo (k_a,k_c) is failed -> continue at line 866
        # Second combo (k_a,k_d) is valid -> returns
        assert result is not None
        assert result["hop_node_keys"] == [k_a, k_d]
