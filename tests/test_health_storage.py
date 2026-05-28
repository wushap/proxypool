"""
Tests for health-related storage methods in SQLiteProxyStorage.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from proxypool.storage.sqlite import SQLiteProxyStorage


@pytest.fixture()
def storage(tmp_path: Path) -> SQLiteProxyStorage:
    return SQLiteProxyStorage(tmp_path / "test.db")


# ---- Node Health ----


class TestNodeHealth:
    def test_upsert_and_get_node_health_success(self, storage: SQLiteProxyStorage):
        result = storage.upsert_node_health("node-a", success=True, egress_ip="1.2.3.4", latency_ms=50)
        assert result["node_key"] == "node-a"
        assert result["failure_count"] == 0
        assert result["circuit_open_since"] is None
        assert result["last_success_at"] is not None
        assert result["last_failure_at"] is None
        assert result["egress_ip"] == "1.2.3.4"
        assert result["latency_avg_ms"] == 50

        fetched = storage.get_node_health("node-a")
        assert fetched is not None
        assert fetched["node_key"] == "node-a"
        assert fetched["failure_count"] == 0

    def test_upsert_node_health_failure_increments(self, storage: SQLiteProxyStorage):
        storage.upsert_node_health("node-b", success=False)
        result = storage.upsert_node_health("node-b", success=False)
        assert result["failure_count"] == 2
        assert result["last_failure_at"] is not None

    def test_upsert_node_health_success_resets_failures(self, storage: SQLiteProxyStorage):
        storage.upsert_node_health("node-c", success=False)
        storage.upsert_node_health("node-c", success=False)
        result = storage.upsert_node_health("node-c", success=True)
        assert result["failure_count"] == 0
        assert result["circuit_open_since"] is None

    def test_upsert_node_health_circuit_opens_at_threshold(self, storage: SQLiteProxyStorage):
        for _ in range(5):
            storage.upsert_node_health("node-d", success=False, max_failures=5)
        result = storage.get_node_health("node-d")
        assert result is not None
        assert result["circuit_open_since"] is not None

    def test_get_node_health_missing(self, storage: SQLiteProxyStorage):
        assert storage.get_node_health("nonexistent") is None

    def test_list_node_health(self, storage: SQLiteProxyStorage):
        storage.upsert_node_health("node-x", success=True)
        storage.upsert_node_health("node-y", success=False)
        records = storage.list_node_health()
        assert len(records) == 2
        keys = [r["node_key"] for r in records]
        assert keys == sorted(keys)

    def test_delete_node_health(self, storage: SQLiteProxyStorage):
        storage.upsert_node_health("node-e", success=True)
        assert storage.delete_node_health("node-e") == 1
        assert storage.get_node_health("node-e") is None

    def test_delete_node_health_missing(self, storage: SQLiteProxyStorage):
        assert storage.delete_node_health("nonexistent") == 0

    def test_upsert_preserves_egress_ip_on_empty(self, storage: SQLiteProxyStorage):
        storage.upsert_node_health("node-f", success=True, egress_ip="5.6.7.8")
        result = storage.upsert_node_health("node-f", success=True, egress_ip="")
        assert result["egress_ip"] == "5.6.7.8"

    def test_upsert_preserves_latency_on_none(self, storage: SQLiteProxyStorage):
        storage.upsert_node_health("node-g", success=True, latency_ms=100)
        result = storage.upsert_node_health("node-g", success=True, latency_ms=None)
        assert result["latency_avg_ms"] == 100


# ---- Chain Egress Instances ----


class TestChainEgressInstances:
    def _make_instance(self, instance_id: str = "inst-1", **overrides):
        defaults = dict(
            instance_id=instance_id,
            pool_id=1,
            endpoint_id=0,
            backend_type="mihomo",
            front_node_key="front-key",
            exit_node_key="exit-key",
            hop_node_keys=["hop1", "hop2"],
            route_signature="sig-abc",
            listen="127.0.0.1",
            port=9090,
            inbound_type="http",
            status="running",
            pid=12345,
            config_file="/tmp/cfg.yaml",
            log_file="/tmp/log.txt",
            egress_ip="10.0.0.1",
        )
        defaults.update(overrides)
        return defaults

    def test_upsert_and_get_chain_egress_instance(self, storage: SQLiteProxyStorage):
        data = self._make_instance()
        result = storage.upsert_chain_egress_instance(**data)
        assert result["instance_id"] == "inst-1"
        assert result["pool_id"] == 1
        assert result["hop_node_keys"] == ["hop1", "hop2"]
        assert result["port"] == 9090
        assert result["status"] == "running"

        fetched = storage.get_chain_egress_instance("inst-1")
        assert fetched is not None
        assert fetched["instance_id"] == "inst-1"

    def test_get_chain_egress_instance_missing(self, storage: SQLiteProxyStorage):
        assert storage.get_chain_egress_instance("no-such") is None

    def test_upsert_updates_existing(self, storage: SQLiteProxyStorage):
        storage.upsert_chain_egress_instance(**self._make_instance(status="running"))
        result = storage.upsert_chain_egress_instance(**self._make_instance(status="stopped", pid=-1))
        assert result["status"] == "stopped"
        assert result["pid"] == -1

    def test_list_chain_egress_instances_all(self, storage: SQLiteProxyStorage):
        storage.upsert_chain_egress_instance(**self._make_instance("inst-a"))
        storage.upsert_chain_egress_instance(**self._make_instance("inst-b", pool_id=2))
        all_inst = storage.list_chain_egress_instances()
        assert len(all_inst) == 2

    def test_list_chain_egress_instances_by_pool(self, storage: SQLiteProxyStorage):
        storage.upsert_chain_egress_instance(**self._make_instance("inst-a", pool_id=1))
        storage.upsert_chain_egress_instance(**self._make_instance("inst-b", pool_id=2))
        result = storage.list_chain_egress_instances(pool_id=1)
        assert len(result) == 1
        assert result[0]["instance_id"] == "inst-a"

    def test_list_chain_egress_instances_by_endpoint(self, storage: SQLiteProxyStorage):
        storage.upsert_chain_egress_instance(**self._make_instance("inst-a", endpoint_id=10))
        storage.upsert_chain_egress_instance(**self._make_instance("inst-b", endpoint_id=20))
        result = storage.list_chain_egress_instances(endpoint_id=10)
        assert len(result) == 1

    def test_list_chain_egress_instances_by_pool_and_endpoint(self, storage: SQLiteProxyStorage):
        storage.upsert_chain_egress_instance(**self._make_instance("inst-a", pool_id=1, endpoint_id=10))
        storage.upsert_chain_egress_instance(**self._make_instance("inst-b", pool_id=1, endpoint_id=20))
        result = storage.list_chain_egress_instances(pool_id=1, endpoint_id=10)
        assert len(result) == 1

    def test_delete_chain_egress_instance(self, storage: SQLiteProxyStorage):
        storage.upsert_chain_egress_instance(**self._make_instance())
        assert storage.delete_chain_egress_instance("inst-1") == 1
        assert storage.get_chain_egress_instance("inst-1") is None

    def test_delete_chain_egress_instance_missing(self, storage: SQLiteProxyStorage):
        assert storage.delete_chain_egress_instance("nope") == 0


# ---- Pool Session Rules ----


class TestPoolSessionRules:
    def test_upsert_and_list_pool_session_rules(self, storage: SQLiteProxyStorage):
        storage.upsert_pool_session_rule(1, "/api/v1", ["X-Token", "Authorization"])
        storage.upsert_pool_session_rule(1, "/api/v2", ["X-Session"])
        rules = storage.list_pool_session_rules(1)
        assert len(rules) == 2
        assert all(r["pool_id"] == 1 for r in rules)

    def test_upsert_pool_session_rule_updates(self, storage: SQLiteProxyStorage):
        storage.upsert_pool_session_rule(1, "/test", ["Header-A"])
        storage.upsert_pool_session_rule(1, "/test", ["Header-B", "Header-C"])
        rules = storage.list_pool_session_rules(1)
        assert len(rules) == 1
        assert rules[0]["headers"] == ["Header-B", "Header-C"]

    def test_list_pool_session_rules_empty(self, storage: SQLiteProxyStorage):
        assert storage.list_pool_session_rules(999) == []

    def test_delete_pool_session_rule(self, storage: SQLiteProxyStorage):
        storage.upsert_pool_session_rule(2, "/del", ["X-Del"])
        assert storage.delete_pool_session_rule(2, "/del") == 1
        assert storage.list_pool_session_rules(2) == []

    def test_delete_pool_session_rule_missing(self, storage: SQLiteProxyStorage):
        assert storage.delete_pool_session_rule(999, "/none") == 0

    def test_upsert_pool_session_rule_empty_prefix_raises(self, storage: SQLiteProxyStorage):
        with pytest.raises(ValueError, match="url_prefix"):
            storage.upsert_pool_session_rule(1, "")

    def test_list_ordered_by_prefix_length_desc(self, storage: SQLiteProxyStorage):
        storage.upsert_pool_session_rule(1, "a", ["H1"])
        storage.upsert_pool_session_rule(1, "a/b/c", ["H2"])
        storage.upsert_pool_session_rule(1, "a/b", ["H3"])
        rules = storage.list_pool_session_rules(1)
        prefixes = [r["url_prefix"] for r in rules]
        assert prefixes == ["a/b/c", "a/b", "a"]


# ---- Sticky Leases ----


class TestStickyLeases:
    def _future(self, seconds: int = 3600) -> str:
        return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()

    def _past(self, seconds: int = 3600) -> str:
        return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()

    def test_upsert_and_get_sticky_lease(self, storage: SQLiteProxyStorage):
        now = datetime.now(UTC).isoformat()
        result = storage.upsert_sticky_lease(
            session_id="sess-1", pool_id=1, endpoint_id=0,
            instance_id="inst-1", exit_node_key="exit-key",
            egress_ip="10.0.0.1", expires_at=self._future(), last_accessed=now,
        )
        assert result["session_id"] == "sess-1"
        assert result["exit_node_key"] == "exit-key"

        fetched = storage.get_sticky_lease("sess-1", 1, 0)
        assert fetched is not None
        assert fetched["egress_ip"] == "10.0.0.1"

    def test_get_sticky_lease_missing(self, storage: SQLiteProxyStorage):
        assert storage.get_sticky_lease("nope", 1, 0) is None

    def test_upsert_sticky_lease_updates(self, storage: SQLiteProxyStorage):
        now = datetime.now(UTC).isoformat()
        storage.upsert_sticky_lease("s1", 1, 0, "inst-a", "exit-a", "ip-a", self._future(), now)
        storage.upsert_sticky_lease("s1", 1, 0, "inst-b", "exit-b", "ip-b", self._future(), now)
        lease = storage.get_sticky_lease("s1", 1, 0)
        assert lease is not None
        assert lease["instance_id"] == "inst-b"
        assert lease["egress_ip"] == "ip-b"

    def test_list_sticky_leases_all(self, storage: SQLiteProxyStorage):
        now = datetime.now(UTC).isoformat()
        storage.upsert_sticky_lease("s1", 1, 0, "i1", "e1", "ip1", self._future(), now)
        storage.upsert_sticky_lease("s2", 2, 0, "i2", "e2", "ip2", self._future(), now)
        assert len(storage.list_sticky_leases()) == 2

    def test_list_sticky_leases_by_pool(self, storage: SQLiteProxyStorage):
        now = datetime.now(UTC).isoformat()
        storage.upsert_sticky_lease("s1", 1, 0, "i1", "e1", "ip1", self._future(), now)
        storage.upsert_sticky_lease("s2", 2, 0, "i2", "e2", "ip2", self._future(), now)
        result = storage.list_sticky_leases(pool_id=1)
        assert len(result) == 1
        assert result[0]["session_id"] == "s1"

    def test_list_sticky_leases_by_endpoint(self, storage: SQLiteProxyStorage):
        now = datetime.now(UTC).isoformat()
        storage.upsert_sticky_lease("s1", 1, 0, "i1", "e1", "ip1", self._future(), now)
        storage.upsert_sticky_lease("s2", 1, 5, "i2", "e2", "ip2", self._future(), now)
        result = storage.list_sticky_leases(endpoint_id=5)
        assert len(result) == 1

    def test_list_sticky_leases_by_pool_and_endpoint(self, storage: SQLiteProxyStorage):
        now = datetime.now(UTC).isoformat()
        storage.upsert_sticky_lease("s1", 1, 0, "i1", "e1", "ip1", self._future(), now)
        storage.upsert_sticky_lease("s2", 1, 5, "i2", "e2", "ip2", self._future(), now)
        result = storage.list_sticky_leases(pool_id=1, endpoint_id=5)
        assert len(result) == 1
        assert result[0]["session_id"] == "s2"

    def test_delete_sticky_lease(self, storage: SQLiteProxyStorage):
        now = datetime.now(UTC).isoformat()
        storage.upsert_sticky_lease("s1", 1, 0, "i1", "e1", "ip1", self._future(), now)
        assert storage.delete_sticky_lease("s1", 1, 0) == 1
        assert storage.get_sticky_lease("s1", 1, 0) is None

    def test_delete_sticky_lease_missing(self, storage: SQLiteProxyStorage):
        assert storage.delete_sticky_lease("nope", 1, 0) == 0


# ---- Failed Routes ----


class TestFailedRoutes:
    """Failed routes use SQLite datetime('now') for comparison, so timestamps
    must be in 'YYYY-MM-DD HH:MM:SS' format to match."""

    def _future_iso(self, hours: int = 2) -> str:
        return (datetime.now(UTC) + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    def _past_iso(self, hours: int = 2) -> str:
        return (datetime.now(UTC) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    def test_upsert_and_is_route_failed(self, storage: SQLiteProxyStorage):
        storage.upsert_failed_route(1, "sig-abc", self._future_iso())
        assert storage.is_route_failed(1, "sig-abc") is True

    def test_is_route_failed_missing(self, storage: SQLiteProxyStorage):
        assert storage.is_route_failed(1, "no-such") is False

    def test_is_route_failed_expired(self, storage: SQLiteProxyStorage):
        storage.upsert_failed_route(1, "sig-old", self._past_iso())
        assert storage.is_route_failed(1, "sig-old") is False

    def test_upsert_failed_route_updates_expiry(self, storage: SQLiteProxyStorage):
        storage.upsert_failed_route(1, "sig-x", self._past_iso())
        assert storage.is_route_failed(1, "sig-x") is False
        storage.upsert_failed_route(1, "sig-x", self._future_iso())
        assert storage.is_route_failed(1, "sig-x") is True

    def test_delete_failed_route(self, storage: SQLiteProxyStorage):
        storage.upsert_failed_route(1, "sig-del", self._future_iso())
        assert storage.delete_failed_route(1, "sig-del") == 1
        assert storage.is_route_failed(1, "sig-del") is False

    def test_delete_failed_route_missing(self, storage: SQLiteProxyStorage):
        assert storage.delete_failed_route(1, "none") == 0

    def test_list_active_failed_routes(self, storage: SQLiteProxyStorage):
        storage.upsert_failed_route(1, "sig-a", self._future_iso())
        storage.upsert_failed_route(2, "sig-b", self._future_iso())
        storage.upsert_failed_route(3, "sig-old", self._past_iso())
        active = storage.list_active_failed_routes()
        assert len(active) == 2
        sigs = {r["route_signature"] for r in active}
        assert sigs == {"sig-a", "sig-b"}

    def test_list_active_failed_routes_empty(self, storage: SQLiteProxyStorage):
        assert storage.list_active_failed_routes() == []

    def test_cleanup_expired_failed_routes(self, storage: SQLiteProxyStorage):
        storage.upsert_failed_route(1, "live", self._future_iso())
        storage.upsert_failed_route(2, "dead", self._past_iso())
        storage.upsert_failed_route(3, "also-dead", self._past_iso())
        deleted = storage.cleanup_expired_failed_routes()
        assert deleted == 2
        assert len(storage.list_active_failed_routes()) == 1


# ---- Cleanup Expired Leases ----


class TestCleanupExpiredLeases:
    def _future_iso(self, seconds: int = 3600) -> str:
        return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()

    def _past_iso(self, seconds: int = 3600) -> str:
        return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()

    def test_cleanup_removes_expired_leases(self, storage: SQLiteProxyStorage):
        now = datetime.now(UTC).isoformat()
        storage.upsert_sticky_lease("live", 1, 0, "i1", "e1", "ip1", self._future_iso(), now)
        storage.upsert_sticky_lease("expired", 1, 0, "i2", "e2", "ip2", self._past_iso(), now)
        storage.upsert_sticky_lease("also-expired", 1, 0, "i3", "e3", "ip3", self._past_iso(2), now)
        deleted = storage.cleanup_expired_leases()
        assert deleted == 2
        remaining = storage.list_sticky_leases()
        assert len(remaining) == 1
        assert remaining[0]["session_id"] == "live"

    def test_cleanup_no_expired(self, storage: SQLiteProxyStorage):
        now = datetime.now(UTC).isoformat()
        storage.upsert_sticky_lease("s1", 1, 0, "i1", "e1", "ip1", self._future_iso(), now)
        assert storage.cleanup_expired_leases() == 0

    def test_cleanup_empty_table(self, storage: SQLiteProxyStorage):
        assert storage.cleanup_expired_leases() == 0
