"""Tests for pool/health_manager.py — coverage-driven."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from proxypool.pool.health_manager import HealthConfig, HealthManager, _log_event
from proxypool.pool.node_pool import NodeEntry, NodePool
from proxypool.pool.scoring import CircuitBreakerConfig, CircuitState, ScoreWeights
from proxypool.storage.health_storage import HealthStorage
from proxypool.storage.sqlite import SQLiteProxyStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage(tmp_path: Path) -> SQLiteProxyStorage:
    return SQLiteProxyStorage(tmp_path / "test.db")


@pytest.fixture()
def health_storage(tmp_path: Path) -> HealthStorage:
    return HealthStorage(tmp_path / "health.db")


@pytest.fixture()
def front_pool() -> NodePool:
    pool = NodePool("front", "front", [])
    pool.add_node(
        NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="http://10.0.0.1:8080")
    )
    return pool


@pytest.fixture()
def exit_pool() -> NodePool:
    pool = NodePool("exit", "exit", [])
    pool.add_node(
        NodeEntry(key="e1", protocol="socks", host="10.0.0.2", port=1080, raw_link="socks://10.0.0.2:1080")
    )
    return pool


def _make_manager(storage, front_pool, exit_pool, health_storage=None, **overrides) -> HealthManager:
    defaults = dict(
        storage=storage,
        front_pool=front_pool,
        exit_pool=exit_pool,
        health_storage=health_storage,
    )
    defaults.update(overrides)
    return HealthManager(**defaults)


# ---------------------------------------------------------------------------
# HealthConfig
# ---------------------------------------------------------------------------

class TestHealthConfig:
    def test_defaults(self):
        cfg = HealthConfig()
        assert cfg.max_consecutive_failures == 5
        assert cfg.probe_interval_sec == 60
        assert cfg.probe_timeout_sec == 10.0
        assert cfg.egress_check_interval_sec == 300
        assert cfg.probe_concurrency == 50
        assert isinstance(cfg.score_weights, ScoreWeights)
        assert isinstance(cfg.circuit_breaker_config, CircuitBreakerConfig)

    def test_custom_values(self):
        cfg = HealthConfig(max_consecutive_failures=10, probe_interval_sec=120)
        assert cfg.max_consecutive_failures == 10
        assert cfg.probe_interval_sec == 120


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInitialization:
    def test_basic_init(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        assert mgr.storage is storage
        assert mgr.front_pool is front_pool
        assert mgr.exit_pool is exit_pool
        assert mgr.health_storage is None
        assert mgr._running is False
        assert mgr._probe_task is None

    def test_init_with_config(self, storage, front_pool, exit_pool):
        cfg = HealthConfig(probe_interval_sec=99)
        mgr = _make_manager(storage, front_pool, exit_pool, config=cfg)
        assert mgr.config.probe_interval_sec == 99

    def test_init_with_health_storage(self, storage, front_pool, exit_pool, health_storage):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        assert mgr.health_storage is health_storage

    def test_scoring_objects_created(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        assert mgr.window_manager is not None
        assert mgr.scorer_manager is not None
        assert mgr.circuit_breaker_manager is not None


# ---------------------------------------------------------------------------
# _log_event
# ---------------------------------------------------------------------------

class TestLogEvent:
    def test_log_event_callable(self):
        # Should not raise
        _log_event(10, "debug message", key="val")


# ---------------------------------------------------------------------------
# _parse_trace_ip
# ---------------------------------------------------------------------------

class TestParseTraceIP:
    def test_parse_valid_ip(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        body = "ip=1.2.3.4\ncountry=US"
        assert mgr._parse_trace_ip(body) == "1.2.3.4"

    def test_parse_no_ip(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        body = "country=US\nregion=west"
        assert mgr._parse_trace_ip(body) == ""

    def test_parse_empty_body(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        assert mgr._parse_trace_ip("") == ""

    def test_parse_ip_with_whitespace(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        body = "ip= 5.6.7.8 \nother=x"
        assert mgr._parse_trace_ip(body) == "5.6.7.8"


# ---------------------------------------------------------------------------
# _persist_health
# ---------------------------------------------------------------------------

class TestPersistHealth:
    def test_persist_calls_storage(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        mgr._persist_health("f1", True, egress_ip="1.2.3.4", latency_ms=42)
        record = storage.get_node_health("f1")
        assert record is not None

    def test_persist_handles_exception(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        storage.upsert_node_health = MagicMock(side_effect=Exception("db fail"))
        # Should not raise
        mgr._persist_health("f1", True)

    def test_persist_minimal_args(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        mgr._persist_health("f1", False)
        record = storage.get_node_health("f1")
        assert record is not None


# ---------------------------------------------------------------------------
# _update_node_health
# ---------------------------------------------------------------------------

class TestUpdateNodeHealth:
    def test_success_updates_pool_and_storage(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        mgr._update_node_health(front_pool, "f1", success=True, latency_ms=50, egress_ip="1.2.3.4")
        node = front_pool.get_node("f1")
        assert node is not None
        assert node.failure_count == 0
        assert node.latency_ms == 50
        assert node.egress_ip == "1.2.3.4"
        # Verify database persistence
        record = storage.get_node_health("f1")
        assert record is not None

    def test_failure_increments_count(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        mgr._update_node_health(front_pool, "f1", success=False)
        node = front_pool.get_node("f1")
        assert node is not None
        assert node.failure_count == 1

    def test_repeated_failures_open_circuit(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        for _ in range(5):
            mgr._update_node_health(front_pool, "f1", success=False)
        node = front_pool.get_node("f1")
        assert node is not None
        assert node.circuit_open is True

    def test_success_after_failure_resets(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        for _ in range(3):
            mgr._update_node_health(front_pool, "f1", success=False)
        mgr._update_node_health(front_pool, "f1", success=True)
        node = front_pool.get_node("f1")
        assert node is not None
        assert node.failure_count == 0
        assert node.circuit_open is False

    def test_circuit_breaker_state_changed_logged(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        with patch("proxypool.pool.health_manager._log_event") as mock_log:
            mgr._update_node_health(front_pool, "f1", success=True)
            # The state changes from default to something after success —
            # just ensure _log_event was called at least for the probe result
            assert mock_log.called

    def test_update_node_health_with_egress(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        mgr._update_node_health(exit_pool, "e1", success=True, latency_ms=100, egress_ip="5.6.7.8")
        node = exit_pool.get_node("e1")
        assert node is not None
        assert node.egress_ip == "5.6.7.8"

    def test_update_with_health_storage(self, storage, front_pool, exit_pool, health_storage):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        mgr._update_node_health(front_pool, "f1", success=True, latency_ms=30)
        # Verify probe record was persisted
        records = health_storage.get_probe_records("f1")
        assert len(records) > 0

    def test_update_with_health_storage_failure_persists_breaker(self, storage, front_pool, exit_pool, health_storage):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        for _ in range(3):
            mgr._update_node_health(front_pool, "f1", success=False)
        # Circuit breaker state should be persisted
        cb_data = health_storage.get_circuit_breaker("f1")
        assert cb_data is not None

    def test_update_health_storage_exception_handled(self, storage, front_pool, exit_pool, health_storage):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        health_storage.insert_probe_record = MagicMock(side_effect=Exception("fail"))
        # Should not raise
        mgr._update_node_health(front_pool, "f1", success=True)

    def test_score_assigned_to_node(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        mgr._update_node_health(front_pool, "f1", success=True, latency_ms=50)
        node = front_pool.get_node("f1")
        assert node is not None
        assert node.score is not None
        assert node.circuit_breaker is not None


# ---------------------------------------------------------------------------
# record_request_result
# ---------------------------------------------------------------------------

class TestRecordRequestResult:
    def test_records_front_and_exit(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        mgr.record_request_result("f1", "e1", success=True)
        node_f = front_pool.get_node("f1")
        node_e = exit_pool.get_node("e1")
        assert node_f is not None
        assert node_f.failure_count == 0
        assert node_e is not None
        assert node_e.failure_count == 0

    def test_records_failure(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        mgr.record_request_result("f1", "e1", success=False)
        node_f = front_pool.get_node("f1")
        assert node_f is not None
        assert node_f.failure_count == 1

    def test_missing_node_no_crash(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        # Non-existent keys should not raise
        mgr.record_request_result("missing-front", "missing-exit", success=True)


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------

class TestStartStop:
    def test_start_sets_running(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        with patch.object(mgr, "_restore_state"), patch.object(mgr, "_probe_loop"):
            mgr.start()
            assert mgr._running is True
            mgr._stop_event.set()
            if mgr._probe_task:
                mgr._probe_task.join(timeout=2)

    def test_start_idempotent(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        with patch.object(mgr, "_restore_state"), patch.object(mgr, "_probe_loop"):
            mgr.start()
            # Second call should be no-op
            mgr.start()
            mgr._stop_event.set()
            if mgr._probe_task:
                mgr._probe_task.join(timeout=2)

    def test_stop(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        with patch.object(mgr, "_restore_state"), patch.object(mgr, "_probe_loop"):
            mgr.start()
            mgr.stop()
            assert mgr._running is False


# ---------------------------------------------------------------------------
# _restore_state
# ---------------------------------------------------------------------------

class TestRestoreState:
    def test_restore_with_no_health_storage(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=None)
        # Should return early without error
        mgr._restore_state()

    def test_restore_with_empty_storage(self, storage, front_pool, exit_pool, health_storage):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        mgr._restore_state()
        # No crash with empty tables

    def test_restore_with_circuit_breaker_data(self, storage, front_pool, exit_pool, health_storage):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        # Pre-populate circuit breaker data
        health_storage.upsert_circuit_breaker(
            node_key="f1",
            state="open",
            failure_count=5,
            consecutive_successes=0,
        )
        mgr._restore_state()
        cb = mgr.circuit_breaker_manager.get_breaker("f1")
        assert cb.failure_count == 5

    def test_restore_with_score_data(self, storage, front_pool, exit_pool, health_storage):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        health_storage.upsert_node_score(
            node_key="f1",
            final_score=0.85,
            grade="A",
            raw_score=0.8,
            confidence=0.9,
            success_rate=0.9,
        )
        mgr._restore_state()
        score = mgr.scorer_manager.get_score("f1")
        assert score is not None
        assert score.final_score == 0.85

    def test_restore_handles_exception(self, storage, front_pool, exit_pool, health_storage):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        health_storage.get_all_circuit_breakers = MagicMock(side_effect=Exception("db fail"))
        # Should not raise
        mgr._restore_state()

    def test_restore_half_open_state(self, storage, front_pool, exit_pool, health_storage):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        health_storage.upsert_circuit_breaker(
            node_key="f1",
            state="half_open",
            failure_count=3,
            consecutive_successes=1,
        )
        mgr._restore_state()
        state = mgr.circuit_breaker_manager.get_state("f1")
        assert state == CircuitState.HALF_OPEN

    def test_restore_unknown_state_defaults_to_closed(self, storage, front_pool, exit_pool, health_storage):
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        health_storage.upsert_circuit_breaker(
            node_key="f1",
            state="bogus",
            failure_count=0,
            consecutive_successes=0,
        )
        mgr._restore_state()
        state = mgr.circuit_breaker_manager.get_state("f1")
        assert state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# _probe_single_exit (with probe_chain callback)
# ---------------------------------------------------------------------------

class TestProbeSingleExit:
    def test_uses_probe_chain_callback(self, storage, front_pool, exit_pool):
        callback = MagicMock(return_value=(True, "1.2.3.4", 50))
        mgr = _make_manager(storage, front_pool, exit_pool, probe_chain=callback)
        front = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        exit_node = NodeEntry(key="e1", protocol="socks", host="10.0.0.2", port=1080, raw_link="")
        result = mgr._probe_single_exit(front, exit_node)
        assert result == (True, "1.2.3.4", 50)
        callback.assert_called_once_with(front, exit_node)

    def test_fallback_without_callbacks(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        front = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        exit_node = NodeEntry(key="e1", protocol="socks", host="10.0.0.2", port=1080, raw_link="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fail")
            result = mgr._probe_single_exit(front, exit_node)
            assert result[0] is False

    def test_build_chain_proxy_url_callback(self, storage, front_pool, exit_pool):
        builder = MagicMock(return_value="http://chain:8080")
        mgr = _make_manager(storage, front_pool, exit_pool, build_chain_proxy_url=builder)
        front = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        exit_node = NodeEntry(key="e1", protocol="socks", host="10.0.0.2", port=1080, raw_link="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            mgr._probe_single_exit(front, exit_node)
            builder.assert_called_once_with(front, exit_node)

    def test_exception_returns_false(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        front = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        exit_node = NodeEntry(key="e1", protocol="socks", host="10.0.0.2", port=1080, raw_link="")
        with patch("subprocess.run", side_effect=Exception("timeout")):
            result = mgr._probe_single_exit(front, exit_node)
            assert result == (False, "", None)

    def test_parse_egress_ip_from_trace(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        front = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        exit_node = NodeEntry(key="e1", protocol="socks", host="10.0.0.2", port=1080, raw_link="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="ip=9.8.7.6\ncountry=US\n0.045",
            )
            success, egress_ip, latency = mgr._probe_single_exit(front, exit_node)
            assert success is True
            assert egress_ip == "9.8.7.6"
            assert latency == 45


# ---------------------------------------------------------------------------
# _probe_single_front
# ---------------------------------------------------------------------------

class TestProbeSingleFront:
    def test_success(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        # Mock storage.get_proxy_by_key to return None (no auth)
        storage.get_proxy_by_key = MagicMock(return_value=None)
        node = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="0.032")
            success, latency = mgr._probe_single_front(node)
            assert success is True
            assert latency == 32

    def test_failure(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        storage.get_proxy_by_key = MagicMock(return_value=None)
        node = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            success, latency = mgr._probe_single_front(node)
            assert success is False
            assert latency is None

    def test_exception_returns_false(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        storage.get_proxy_by_key = MagicMock(return_value=None)
        node = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        with patch("subprocess.run", side_effect=Exception("timeout")):
            success, latency = mgr._probe_single_front(node)
            assert success is False
            assert latency is None

    def test_with_proxy_auth(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        storage.get_proxy_by_key = MagicMock(
            return_value={"extra": {"username": "user", "password": "pass"}}
        )
        node = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="0.050")
            mgr._probe_single_front(node)
            cmd = mock_run.call_args[0][0]
            assert "-U" in cmd
            assert "user:pass" in cmd

    def test_with_empty_auth(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        storage.get_proxy_by_key = MagicMock(
            return_value={"extra": {"username": "", "password": ""}}
        )
        node = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="0.020")
            mgr._probe_single_front(node)
            cmd = mock_run.call_args[0][0]
            assert "-U" not in cmd

    def test_with_no_extra_field(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        storage.get_proxy_by_key = MagicMock(return_value={"extra": None})
        node = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="0.010")
            mgr._probe_single_front(node)
            cmd = mock_run.call_args[0][0]
            assert "-U" not in cmd


# ---------------------------------------------------------------------------
# _probe_front_nodes / _probe_exit_nodes / _probe_all_nodes
# ---------------------------------------------------------------------------

class TestProbeCollections:
    def test_probe_front_nodes_empty(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        # Should return early with no nodes
        mgr._probe_front_nodes([])

    def test_probe_exit_nodes_empty(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        mgr._probe_exit_nodes([], [])

    def test_probe_exit_nodes_no_fronts(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        node = NodeEntry(key="e1", protocol="socks", host="10.0.0.2", port=1080, raw_link="")
        mgr._probe_exit_nodes([node], [])

    def test_probe_all_nodes(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        with patch.object(mgr, "_probe_front_nodes") as mock_front, patch.object(
            mgr, "_probe_exit_nodes"
        ) as mock_exit:
            # Make get_healthy_nodes return the front pool's node
            front_pool.get_healthy_nodes = MagicMock(
                return_value=[NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="", routeable=True)]
            )
            mgr._probe_all_nodes()
            mock_front.assert_called_once()
            mock_exit.assert_called_once()

    def test_probe_all_nodes_no_healthy_fronts_skips_exit(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        front_pool.get_healthy_nodes = MagicMock(return_value=[])
        with patch.object(mgr, "_probe_front_nodes"), patch.object(
            mgr, "_probe_exit_nodes"
        ) as mock_exit:
            mgr._probe_all_nodes()
            mock_exit.assert_not_called()

    def test_probe_front_nodes_with_real_nodes(self, storage, front_pool, exit_pool):
        """Exercise the ThreadPoolExecutor path in _probe_front_nodes."""
        mgr = _make_manager(storage, front_pool, exit_pool)
        node = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        with patch.object(mgr, "_probe_single_front", return_value=(True, 50)):
            mgr._probe_front_nodes([node])
        node = front_pool.get_node("f1")
        assert node is not None
        assert node.failure_count == 0

    def test_probe_front_nodes_with_exception_in_future(self, storage, front_pool, exit_pool):
        """Exception during front probe is logged, not raised."""
        mgr = _make_manager(storage, front_pool, exit_pool)
        node = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        with patch.object(mgr, "_probe_single_front", side_effect=Exception("boom")):
            mgr._probe_front_nodes([node])

    def test_probe_exit_nodes_with_real_nodes(self, storage, front_pool, exit_pool):
        """Exercise the ThreadPoolExecutor path in _probe_exit_nodes."""
        mgr = _make_manager(storage, front_pool, exit_pool)
        front = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        exit_node = NodeEntry(key="e1", protocol="socks", host="10.0.0.2", port=1080, raw_link="")
        with patch.object(mgr, "_probe_single_exit", return_value=(True, "5.6.7.8", 80)):
            mgr._probe_exit_nodes([exit_node], [front])
        e = exit_pool.get_node("e1")
        assert e is not None
        assert e.egress_ip == "5.6.7.8"

    def test_probe_exit_nodes_with_exception_in_future(self, storage, front_pool, exit_pool):
        """Exception during exit probe is logged, not raised."""
        mgr = _make_manager(storage, front_pool, exit_pool)
        front = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        exit_node = NodeEntry(key="e1", protocol="socks", host="10.0.0.2", port=1080, raw_link="")
        with patch.object(mgr, "_probe_single_exit", side_effect=Exception("boom")):
            mgr._probe_exit_nodes([exit_node], [front])


# ---------------------------------------------------------------------------
# _probe_loop
# ---------------------------------------------------------------------------

class TestProbeLoop:
    def test_probe_loop_runs_once_and_stops(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        call_count = 0

        def fake_probe():
            nonlocal call_count
            call_count += 1
            mgr._stop_event.set()

        with patch.object(mgr, "_probe_all_nodes", side_effect=fake_probe):
            mgr._stop_event.clear()
            mgr._running = True
            mgr._probe_loop()
        assert call_count == 1

    def test_probe_loop_exception_in_probe_continues(self, storage, front_pool, exit_pool):
        """Exception inside _probe_all_nodes does not crash the loop."""
        mgr = _make_manager(storage, front_pool, exit_pool)
        call_count = 0

        def fake_probe():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("probe fail")
            mgr._stop_event.set()

        with patch.object(mgr, "_probe_all_nodes", side_effect=fake_probe):
            mgr._stop_event.clear()
            mgr._running = True
            mgr._probe_loop()
        assert call_count == 2


# ---------------------------------------------------------------------------
# _update_node_health — additional edge cases
# ---------------------------------------------------------------------------

class TestUpdateNodeHealthEdgeCases:
    def test_update_check_result_exception_handled(self, storage, front_pool, exit_pool):
        mgr = _make_manager(storage, front_pool, exit_pool)
        storage.update_check_result = MagicMock(side_effect=Exception("db fail"))
        # Should not raise
        mgr._update_node_health(front_pool, "f1", success=True)

    def test_update_node_not_in_pool(self, storage, front_pool, exit_pool):
        """When node_key doesn't exist in pool, update still records in window/breaker."""
        mgr = _make_manager(storage, front_pool, exit_pool)
        # Should not crash even though "ghost" node isn't in the pool
        mgr._update_node_health(front_pool, "nonexistent", success=True)

    def test_probe_single_exit_single_line_output(self, storage, front_pool, exit_pool):
        """When curl output has only one line (no newline), returns failure."""
        mgr = _make_manager(storage, front_pool, exit_pool)
        front = NodeEntry(key="f1", protocol="http", host="10.0.0.1", port=8080, raw_link="")
        exit_node = NodeEntry(key="e1", protocol="socks", host="10.0.0.2", port=1080, raw_link="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="0.045")
            success, egress_ip, latency = mgr._probe_single_exit(front, exit_node)
            assert success is False
