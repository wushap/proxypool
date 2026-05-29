"""
Tests for pool modules: health_manager, sticky_router, protocol_compat.

Targets low-coverage code paths:
- health_manager.py: _parse_trace_ip, _persist_health, _update_node_health,
  record_request_result, _restore_state, start/stop lifecycle, probe methods.
- sticky_router.py: lease creation/reuse, P2C selection, cleanup, bind, get_leases.
- protocol_compat.py: edge cases in find_backend, filter, check_nodes_compatibility.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from proxypool.pool.health_manager import HealthConfig, HealthManager
from proxypool.pool.node_pool import NodeEntry, NodePool
from proxypool.pool.protocol_compat import (
    ALL_SUPPORTED_PROTOCOLS,
    COMMON_PROTOCOLS,
    SINGBOX_PROTOCOLS,
    check_nodes_compatibility,
    find_backend_for_protocol,
    filter_compatible_nodes,
    get_supported_protocols,
    supports_protocol,
)
from proxypool.pool.scoring import (
    CircuitBreakerConfig,
    CircuitBreakerManager,
    CircuitState,
    NodeScore,
    NodeScorerManager,
    ScoreGrade,
    WindowManager,
)
from proxypool.pool.sticky_router import StickyRouter
from proxypool.storage.health_storage import HealthStorage
from proxypool.storage.sqlite import SQLiteProxyStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(
    key: str = "n1",
    protocol: str = "http",
    host: str = "1.2.3.4",
    port: int = 8080,
    egress_ip: str = "10.0.0.1",
    latency_ms: int | None = 100,
    routeable: bool = True,
    circuit_open: bool = False,
    name: str = "",
    tags: list[str] | None = None,
) -> NodeEntry:
    return NodeEntry(
        key=key,
        protocol=protocol,
        host=host,
        port=port,
        raw_link=f"{protocol}://{host}:{port}",
        name=name or key,
        tags=tags or [],
        egress_ip=egress_ip,
        latency_ms=latency_ms,
        routeable=routeable,
        circuit_open=circuit_open,
    )


def _make_pool(
    name: str = "test-pool",
    pool_type: str = "exit",
    nodes: list[NodeEntry] | None = None,
) -> NodePool:
    pool = NodePool(name=name, pool_type=pool_type, regex_filters=[".*"])
    for node in (nodes or []):
        pool.add_node(node)
    return pool


def _make_score(node_key: str = "n1", final_score: float = 0.8) -> NodeScore:
    return NodeScore(
        node_key=node_key,
        timestamp=time.time(),
        final_score=final_score,
        grade=ScoreGrade.A,
        raw_score=final_score,
        confidence=0.9,
        success_rate=0.9,
        avg_latency_ms=100,
        stability_score=0.85,
        availability_score=0.0,
        latency_score=0.0,
        purity_score=None,
        purity_score_normalized=0.0,
    )


# ===========================================================================
# HealthManager Tests
# ===========================================================================


class TestHealthManagerParseTraceIp:
    """Test _parse_trace_ip helper."""

    def test_parse_valid_trace(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        hm = HealthManager(storage, front, exit_p)
        body = "ip=1.2.3.4\ncountry=US\n"
        assert hm._parse_trace_ip(body) == "1.2.3.4"

    def test_parse_empty_body(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        hm = HealthManager(storage, front, exit_p)
        assert hm._parse_trace_ip("") == ""

    def test_parse_body_no_ip_line(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        hm = HealthManager(storage, front, exit_p)
        assert hm._parse_trace_ip("country=US\n") == ""

    def test_parse_ip_with_whitespace(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        hm = HealthManager(storage, front, exit_p)
        assert hm._parse_trace_ip("ip=  5.6.7.8\n") == "5.6.7.8"


class TestHealthManagerPersistHealth:
    """Test _persist_health calls storage correctly."""

    def test_persist_health_success(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        hm = HealthManager(storage, front, exit_p)
        # Should not raise
        hm._persist_health("node-1", success=True, egress_ip="1.2.3.4", latency_ms=50)

    def test_persist_health_failure(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        hm = HealthManager(storage, front, exit_p)
        hm._persist_health("node-1", success=False)

    def test_persist_health_storage_error(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        storage.upsert_node_health = MagicMock(side_effect=Exception("db error"))
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        hm = HealthManager(storage, front, exit_p)
        # Should not raise - errors are caught and logged
        hm._persist_health("node-1", success=True)


class TestHealthManagerRecordRequestResult:
    """Test record_request_result passive probing."""

    def test_record_request_front_only(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front_node = _make_node(key="f1")
        exit_node = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [front_node])
        exit_p = _make_pool("exit", "exit", [exit_node])
        hm = HealthManager(storage, front, exit_p)
        # Record result - front exists, exit key not in exit pool
        hm.record_request_result("f1", "missing", success=True)
        # f1 should have been updated
        f1 = front.get_node("f1")
        assert f1 is not None
        assert f1.failure_count == 0

    def test_record_request_both_pools(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front_node = _make_node(key="f1")
        exit_node = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [front_node])
        exit_p = _make_pool("exit", "exit", [exit_node])
        hm = HealthManager(storage, front, exit_p)
        hm.record_request_result("f1", "e1", success=False)
        assert front.get_node("f1").failure_count == 1
        assert exit_p.get_node("e1").failure_count == 1

    def test_record_request_missing_front(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        exit_node = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit", [exit_node])
        hm = HealthManager(storage, front, exit_p)
        # Neither node exists - should not raise
        hm.record_request_result("missing", "e1", success=True)


class TestHealthManagerUpdateNodeHealth:
    """Test _update_node_health scoring and circuit breaker logic."""

    def test_update_success(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        node = _make_node(key="n1")
        pool = _make_pool("pool", "exit", [node])
        hm = HealthManager(storage, _make_pool("f", "front"), pool)
        hm._update_node_health(pool, "n1", success=True, latency_ms=50, egress_ip="1.1.1.1")
        # Node should be updated
        n = pool.get_node("n1")
        assert n is not None
        assert n.failure_count == 0
        assert n.egress_ip == "1.1.1.1"
        assert n.latency_ms == 50

    def test_update_failure_increments_count(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        node = _make_node(key="n1")
        pool = _make_pool("pool", "exit", [node])
        hm = HealthManager(storage, _make_pool("f", "front"), pool)
        hm._update_node_health(pool, "n1", success=False)
        assert pool.get_node("n1").failure_count == 1

    def test_update_failure_opens_circuit(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        node = _make_node(key="n1")
        pool = _make_pool("pool", "exit", [node])
        cb_config = CircuitBreakerConfig(failure_threshold=2)
        config = HealthConfig(
            max_consecutive_failures=2,
            circuit_breaker_config=cb_config,
        )
        hm = HealthManager(storage, _make_pool("f", "front"), pool, config=config)
        hm._update_node_health(pool, "n1", success=False)
        hm._update_node_health(pool, "n1", success=False)
        # Circuit breaker also trips at 2 failures, so circuit_open should be True
        assert hm.circuit_breaker_manager.get_state("n1") == CircuitState.OPEN
        assert pool.get_node("n1").circuit_open is True

    def test_update_success_resets_failure_count(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        node = _make_node(key="n1")
        pool = _make_pool("pool", "exit", [node])
        hm = HealthManager(storage, _make_pool("f", "front"), pool)
        hm._update_node_health(pool, "n1", success=False)
        hm._update_node_health(pool, "n1", success=False)
        hm._update_node_health(pool, "n1", success=True)
        assert pool.get_node("n1").failure_count == 0
        assert pool.get_node("n1").circuit_open is False

    def test_update_with_health_storage(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        health_db = tmp_path / "health.db"
        health_storage = HealthStorage(health_db)
        node = _make_node(key="n1")
        pool = _make_pool("pool", "exit", [node])
        hm = HealthManager(
            storage,
            _make_pool("f", "front"),
            pool,
            health_storage=health_storage,
        )
        hm._update_node_health(pool, "n1", success=True, latency_ms=100, egress_ip="1.1.1.1")
        # Verify probe record persisted
        records = health_storage.get_probe_records("n1")
        assert len(records) == 1
        assert records[0]["success"] == 1

        # Verify score persisted
        score_data = health_storage.get_node_score("n1")
        assert score_data is not None

        # Verify circuit breaker persisted
        cb = health_storage.get_circuit_breaker("n1")
        assert cb is not None

    def test_update_with_health_storage_error(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        health_storage = MagicMock(spec=HealthStorage)
        health_storage.insert_probe_record.side_effect = Exception("db error")
        node = _make_node(key="n1")
        pool = _make_pool("pool", "exit", [node])
        hm = HealthManager(
            storage,
            _make_pool("f", "front"),
            pool,
            health_storage=health_storage,
        )
        # Should not raise
        hm._update_node_health(pool, "n1", success=True)

    def test_update_node_not_in_pool(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        pool = _make_pool("pool", "exit")
        hm = HealthManager(storage, _make_pool("f", "front"), pool)
        # Should not raise even if node doesn't exist in pool
        hm._update_node_health(pool, "missing", success=True)


class TestHealthManagerStartStop:
    """Test start/stop lifecycle."""

    def test_start_stop(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        hm = HealthManager(storage, front, exit_p, config=HealthConfig(probe_interval_sec=1))
        hm.start()
        assert hm._running is True
        assert hm._probe_task is not None
        # Start again is idempotent
        hm.start()
        hm.stop()
        assert hm._running is False

    def test_stop_without_start(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        hm = HealthManager(storage, front, exit_p)
        # Should not raise
        hm.stop()
        assert hm._running is False


class TestHealthManagerRestoreState:
    """Test _restore_state from health_storage."""

    def test_restore_no_storage(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        hm = HealthManager(storage, _make_pool("f", "front"), _make_pool("e", "exit"))
        # Should not raise
        hm._restore_state()

    def test_restore_with_storage(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        health_db = tmp_path / "health.db"
        health_storage = HealthStorage(health_db)
        hm = HealthManager(
            storage,
            _make_pool("f", "front"),
            _make_pool("e", "exit"),
            health_storage=health_storage,
        )
        # Pre-populate data in health_storage
        health_storage.upsert_circuit_breaker(
            node_key="n1",
            state="open",
            failure_count=3,
            consecutive_successes=0,
            current_backoff_sec=60.0,
        )
        health_storage.upsert_node_score(
            node_key="n2",
            final_score=0.75,
            grade="B",
            raw_score=0.75,
            confidence=0.8,
            success_rate=0.8,
            avg_latency_ms=120,
            stability_score=0.7,
        )
        hm._restore_state()
        # Check restored circuit breaker
        cb = hm.circuit_breaker_manager.get_breaker("n1")
        assert cb.failure_count == 3

        # Check restored score
        score = hm.scorer_manager.get_score("n2")
        assert score is not None
        assert score.final_score == 0.75

    def test_restore_with_unknown_state_string(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        health_db = tmp_path / "health.db"
        health_storage = HealthStorage(health_db)
        hm = HealthManager(
            storage,
            _make_pool("f", "front"),
            _make_pool("e", "exit"),
            health_storage=health_storage,
        )
        health_storage.upsert_circuit_breaker(
            node_key="n1",
            state="unknown_state",
            failure_count=0,
            consecutive_successes=0,
        )
        # Should fall back to CLOSED, not raise
        hm._restore_state()

    def test_restore_storage_error(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        health_storage = MagicMock(spec=HealthStorage)
        health_storage.get_all_circuit_breakers.side_effect = Exception("db error")
        hm = HealthManager(
            storage,
            _make_pool("f", "front"),
            _make_pool("e", "exit"),
            health_storage=health_storage,
        )
        # Should not raise - error is caught
        hm._restore_state()


class TestHealthManagerProbeSingleFront:
    """Test _probe_single_front with mocked subprocess."""

    def test_probe_success(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        node = _make_node(key="f1", protocol="http", host="1.2.3.4", port=8080)
        pool = _make_pool("front", "front", [node])
        hm = HealthManager(storage, pool, _make_pool("e", "exit"))
        mock_result = MagicMock(returncode=0, stdout="0.150")
        with patch("subprocess.run", return_value=mock_result):
            success, latency = hm._probe_single_front(node)
        assert success is True
        assert latency == 150

    def test_probe_failure_nonzero(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        node = _make_node(key="f1", protocol="http", host="1.2.3.4", port=8080)
        pool = _make_pool("front", "front", [node])
        hm = HealthManager(storage, pool, _make_pool("e", "exit"))
        mock_result = MagicMock(returncode=1, stdout="")
        with patch("subprocess.run", return_value=mock_result):
            success, latency = hm._probe_single_front(node)
        assert success is False
        assert latency is None

    def test_probe_exception(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        node = _make_node(key="f1", protocol="http", host="1.2.3.4", port=8080)
        pool = _make_pool("front", "front", [node])
        hm = HealthManager(storage, pool, _make_pool("e", "exit"))
        with patch("subprocess.run", side_effect=TimeoutError("timeout")):
            success, latency = hm._probe_single_front(node)
        assert success is False
        assert latency is None

    def test_probe_with_auth(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        node = _make_node(key="f1", protocol="http", host="1.2.3.4", port=8080)
        pool = _make_pool("front", "front", [node])
        hm = HealthManager(storage, pool, _make_pool("e", "exit"))
        # Mock get_proxy_by_key to return auth
        storage.get_proxy_by_key = MagicMock(
            return_value={"extra": {"username": "user", "password": "pass"}}
        )
        mock_result = MagicMock(returncode=0, stdout="0.200")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            success, latency = hm._probe_single_front(node)
        # Verify -U flag was passed
        call_args = mock_run.call_args[0][0]
        assert "-U" in call_args
        assert "user:pass" in call_args


class TestHealthManagerProbeSingleExit:
    """Test _probe_single_exit with various callback configurations."""

    def test_probe_with_probe_chain_callback(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front_node = _make_node(key="f1")
        exit_node = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        hm = HealthManager(storage, _make_pool("f", "front"), _make_pool("e", "exit"))
        hm.probe_chain = MagicMock(return_value=(True, "9.9.9.9", 200))
        success, ip, latency = hm._probe_single_exit(front_node, exit_node)
        assert success is True
        assert ip == "9.9.9.9"
        assert latency == 200

    def test_probe_with_build_chain_url(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front_node = _make_node(key="f1")
        exit_node = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        hm = HealthManager(storage, _make_pool("f", "front"), _make_pool("e", "exit"))
        hm.build_chain_proxy_url = MagicMock(return_value="http://chain-proxy:9090")
        mock_result = MagicMock(
            returncode=0,
            stdout="ip=3.4.5.6\nother=data\n0.300",
        )
        with patch("subprocess.run", return_value=mock_result):
            success, ip, latency = hm._probe_single_exit(front_node, exit_node)
        assert success is True
        assert ip == "3.4.5.6"
        assert latency == 300

    def test_probe_fallback_direct(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front_node = _make_node(key="f1")
        exit_node = _make_node(key="e1", protocol="socks5", host="5.6.7.8", port=1080, egress_ip="5.6.7.8")
        hm = HealthManager(storage, _make_pool("f", "front"), _make_pool("e", "exit"))
        # No probe_chain, no build_chain_proxy_url
        mock_result = MagicMock(returncode=0, stdout="ip=7.8.9.0\n0.100")
        with patch("subprocess.run", return_value=mock_result):
            success, ip, latency = hm._probe_single_exit(front_node, exit_node)
        assert success is True
        assert ip == "7.8.9.0"

    def test_probe_exit_failure(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front_node = _make_node(key="f1")
        exit_node = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        hm = HealthManager(storage, _make_pool("f", "front"), _make_pool("e", "exit"))
        mock_result = MagicMock(returncode=1, stdout="")
        with patch("subprocess.run", return_value=mock_result):
            success, ip, latency = hm._probe_single_exit(front_node, exit_node)
        assert success is False
        assert ip == ""

    def test_probe_exit_exception(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front_node = _make_node(key="f1")
        exit_node = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        hm = HealthManager(storage, _make_pool("f", "front"), _make_pool("e", "exit"))
        with patch("subprocess.run", side_effect=OSError("fail")):
            success, ip, latency = hm._probe_single_exit(front_node, exit_node)
        assert success is False


class TestHealthManagerProbeAllNodes:
    """Test _probe_all_nodes orchestration."""

    def test_probe_all_nodes(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        hm = HealthManager(storage, front, exit_p)
        # Mock probe_single_front and probe_single_exit
        with patch.object(hm, "_probe_single_front", return_value=(True, 50)):
            with patch.object(hm, "_probe_single_exit", return_value=(True, "9.9.9.9", 100)):
                hm._probe_all_nodes()
        assert front.get_node("f1").failure_count == 0

    def test_probe_all_nodes_empty_pools(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        hm = HealthManager(storage, front, exit_p)
        # Should not raise
        hm._probe_all_nodes()


class TestHealthManagerProbeExitNodes:
    """Test _probe_exit_nodes with edge cases."""

    def test_probe_exit_nodes_empty_front(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        exit_p = _make_pool("exit", "exit", [_make_node("e1")])
        hm = HealthManager(storage, _make_pool("f", "front"), exit_p)
        # Empty front_nodes list
        hm._probe_exit_nodes([_make_node("e1")], [])
        # Should not raise

    def test_probe_exit_nodes_empty_exits(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        front = _make_pool("front", "front", [_make_node("f1")])
        hm = HealthManager(storage, front, _make_pool("e", "exit"))
        hm._probe_exit_nodes([], [_make_node("f1")])


class TestHealthManagerProbeFrontNodes:
    """Test _probe_front_nodes edge cases."""

    def test_probe_front_nodes_empty(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        hm = HealthManager(storage, _make_pool("f", "front"), _make_pool("e", "exit"))
        # Should return immediately
        hm._probe_front_nodes([])

    def test_probe_front_nodes_with_exception(self, tmp_path: Path) -> None:
        storage = SQLiteProxyStorage(tmp_path / "db.db")
        f1 = _make_node(key="f1")
        pool = _make_pool("front", "front", [f1])
        hm = HealthManager(storage, pool, _make_pool("e", "exit"))
        with patch.object(hm, "_probe_single_front", side_effect=Exception("boom")):
            # Should not raise
            hm._probe_front_nodes([f1])


# ===========================================================================
# StickyRouter Tests
# ===========================================================================


class TestStickyRouterRoute:
    """Test StickyRouter.route main path."""

    def test_route_no_healthy_nodes(self, tmp_path: Path) -> None:
        front = _make_pool("front", "front")
        exit_p = _make_pool("exit", "exit")
        router = StickyRouter(front, exit_p)
        result = router.route("session-1", pool_id=1)
        assert result is None

    def test_route_creates_lease(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        result = router.route("session-1", pool_id=1)
        assert result is not None
        assert result.lease_created is True
        # Verify lease was created
        leases = router.get_leases()
        assert len(leases) == 1
        assert leases[0]["session_id"] == "session-1"

    def test_route_no_session_id(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        result = router.route("", pool_id=1)
        assert result is not None
        assert result.lease_created is False

    def test_route_reuse_lease(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        # First call creates lease
        r1 = router.route("session-1", pool_id=1)
        assert r1.lease_created is True
        # Second call reuses lease
        r2 = router.route("session-1", pool_id=1)
        assert r2.lease_created is False
        assert r2.exit_node.key == "e1"

    def test_route_expired_lease_falls_back(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p, sticky_ttl_sec=1)
        router.route("session-1", pool_id=1)
        # Manually expire the lease
        key = ("session-1", 1)
        with router._lock:
            router._leases[key].expires_at = datetime.now(UTC) - timedelta(hours=1)
        # Should create new lease since old one expired
        result = router.route("session-1", pool_id=1)
        assert result is not None
        assert result.lease_created is True

    def test_route_lease_exit_node_ip_changed(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        router.route("session-1", pool_id=1)
        # Change egress IP on exit node
        e1.egress_ip = "9.9.9.9"
        # Lease still valid but IP doesn't match - should try finding same IP
        # No other node has the old IP, so it will fall through
        result = router.route("session-1", pool_id=1)
        # Either reuses (if find_same_ip finds nothing and falls to P2C) or creates new
        assert result is not None


class TestStickyRouterP2C:
    """Test P2C selection algorithm."""

    def test_p2c_single_node(self, tmp_path: Path) -> None:
        n1 = _make_node(key="n1", latency_ms=100)
        pool = _make_pool("pool", "exit", [n1])
        router = StickyRouter(_make_pool("f", "front"), pool)
        result = router._p2c_select([n1], "")
        assert result.key == "n1"

    def test_p2c_empty_list(self, tmp_path: Path) -> None:
        router = StickyRouter(_make_pool("f", "front"), _make_pool("e", "exit"))
        assert router._p2c_select([], "") is None

    def test_p2c_multiple_nodes(self, tmp_path: Path) -> None:
        n1 = _make_node(key="n1", latency_ms=100, egress_ip="1.1.1.1")
        n2 = _make_node(key="n2", latency_ms=200, egress_ip="2.2.2.2")
        pool = _make_pool("pool", "exit", [n1, n2])
        router = StickyRouter(_make_pool("f", "front"), pool)
        # With load, pick lower score
        router._ip_load["1.1.1.1"] = 0
        router._ip_load["2.2.2.2"] = 10
        result = router._p2c_select([n1, n2], "")
        assert result.key == "n1"  # lower load * latency

    def test_calculate_score_with_latency(self, tmp_path: Path) -> None:
        router = StickyRouter(_make_pool("f", "front"), _make_pool("e", "exit"))
        n1 = _make_node(key="n1", latency_ms=100, egress_ip="1.1.1.1")
        router._ip_load["1.1.1.1"] = 2
        # score = (lease_count + 1) * latency = (2+1) * 100 = 300
        assert router._calculate_score(n1) == 300.0

    def test_calculate_score_no_latency(self, tmp_path: Path) -> None:
        router = StickyRouter(_make_pool("f", "front"), _make_pool("e", "exit"))
        n1 = _make_node(key="n1", latency_ms=None, egress_ip="1.1.1.1")
        router._ip_load["1.1.1.1"] = 3
        # score = lease_count = 3
        assert router._calculate_score(n1) == 3.0

    def test_calculate_score_zero_latency(self, tmp_path: Path) -> None:
        router = StickyRouter(_make_pool("f", "front"), _make_pool("e", "exit"))
        n1 = _make_node(key="n1", latency_ms=0, egress_ip="1.1.1.1")
        router._ip_load["1.1.1.1"] = 1
        # latency <= 0 -> score = lease_count
        assert router._calculate_score(n1) == 1.0


class TestStickyRouterSelectDistinctPair:
    """Test _select_distinct_pair."""

    def test_select_distinct_pair_basic(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = [_f1 := f1]
        exits = [e1]
        router = StickyRouter(
            _make_pool("f", "front", front),
            _make_pool("e", "exit", exits),
        )
        f, e = router._select_distinct_pair(front, exits, "")
        assert f is not None
        assert e is not None
        assert f.key != e.key

    def test_select_distinct_pair_same_key_fallback(self, tmp_path: Path) -> None:
        # Only one node in each pool, both with same key - should fail
        n1 = _make_node(key="same", egress_ip="1.1.1.1")
        front = [n1]
        exits = [_make_node(key="same", host="5.6.7.8", egress_ip="5.6.7.8")]
        router = StickyRouter(
            _make_pool("f", "front", front),
            _make_pool("e", "exit", exits),
        )
        f, e = router._select_distinct_pair(front, exits, "")
        # front selection filters out exit_node.key, so if only one front with same key, fallback
        # The second P2C will have empty remaining exits -> returns None
        # This tests the fallback path where front == None for first exit


class TestStickyRouterFindSameIpExit:
    """Test _find_same_ip_exit."""

    def test_find_same_ip_found(self, tmp_path: Path) -> None:
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="10.0.0.1", latency_ms=50)
        e2 = _make_node(key="e2", host="9.10.11.12", egress_ip="10.0.0.1", latency_ms=20)
        router = StickyRouter(_make_pool("f", "front"), _make_pool("e", "exit"))
        result = router._find_same_ip_exit("10.0.0.1", [e1, e2])
        # Should pick the one with lower latency
        assert result.key == "e2"

    def test_find_same_ip_not_found(self, tmp_path: Path) -> None:
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="20.0.0.1")
        router = StickyRouter(_make_pool("f", "front"), _make_pool("e", "exit"))
        assert router._find_same_ip_exit("10.0.0.1", [e1]) is None


class TestStickyRouterLeaseManagement:
    """Test bind_instance, delete_lease, cleanup_expired_leases."""

    def test_bind_instance(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        router.route("session-1", pool_id=1)
        router.bind_instance("session-1", 1, "inst-42")
        leases = router.get_leases()
        assert leases[0]["instance_id"] == "inst-42"

    def test_bind_instance_missing_lease(self, tmp_path: Path) -> None:
        router = StickyRouter(_make_pool("f", "front"), _make_pool("e", "exit"))
        # Should not raise
        router.bind_instance("missing", 1, "inst-42")

    def test_delete_lease_exists(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        router.route("session-1", pool_id=1)
        assert router.delete_lease("session-1", 1) is True
        assert router.get_leases() == []

    def test_delete_lease_not_exists(self, tmp_path: Path) -> None:
        router = StickyRouter(_make_pool("f", "front"), _make_pool("e", "exit"))
        assert router.delete_lease("missing", 1) is False

    def test_cleanup_expired_leases(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p, sticky_ttl_sec=1)
        router.route("s1", pool_id=1)
        router.route("s2", pool_id=1)
        # Expire one
        with router._lock:
            router._leases[("s1", 1)].expires_at = datetime.now(UTC) - timedelta(hours=1)
        removed = router.cleanup_expired_leases()
        assert removed == 1
        leases = router.get_leases()
        assert len(leases) == 1
        assert leases[0]["session_id"] == "s2"

    def test_cleanup_no_expired(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        router.route("s1", pool_id=1)
        removed = router.cleanup_expired_leases()
        assert removed == 0


class TestStickyRouterGetLeases:
    """Test get_leases filtering."""

    def test_get_leases_all(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        router.route("s1", pool_id=1)
        router.route("s2", pool_id=2)
        assert len(router.get_leases()) == 2

    def test_get_leases_by_pool_id(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        router.route("s1", pool_id=1)
        router.route("s2", pool_id=2)
        assert len(router.get_leases(pool_id=1)) == 1
        assert router.get_leases(pool_id=1)[0]["session_id"] == "s1"

    def test_get_leases_empty(self, tmp_path: Path) -> None:
        router = StickyRouter(_make_pool("f", "front"), _make_pool("e", "exit"))
        assert router.get_leases() == []


class TestStickyRouterReuseLeaseEdgeCases:
    """Test _try_reuse_lease various code paths."""

    def test_reuse_with_live_instance(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        router.route("s1", pool_id=1)
        router.bind_instance("s1", 1, "inst-1")
        result = router.route("s1", pool_id=1, live_instance_ids={"inst-1"})
        assert result is not None
        assert result.instance_reused is True
        assert result.bound_instance_id == "inst-1"

    def test_reuse_with_dead_instance(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        router.route("s1", pool_id=1)
        router.bind_instance("s1", 1, "inst-dead")
        # instance_id not in live set
        result = router.route("s1", pool_id=1, live_instance_ids={"other"})
        assert result is not None
        assert result.instance_reused is False

    def test_reuse_with_different_ip_node(self, tmp_path: Path) -> None:
        """When the original exit node's IP changes, try to find same-IP node."""
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        e2 = _make_node(key="e2", host="9.10.11.12", egress_ip="5.6.7.8", latency_ms=30)
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1, e2])
        router = StickyRouter(front, exit_p)
        router.route("s1", pool_id=1)
        # Change e1's IP to something else
        e1.egress_ip = "changed"
        # _try_reuse_lease should find e2 via _find_same_ip_exit
        result = router.route("s1", pool_id=1)
        assert result is not None

    def test_reuse_exit_node_removed(self, tmp_path: Path) -> None:
        f1 = _make_node(key="f1", egress_ip="10.0.0.1")
        e1 = _make_node(key="e1", host="5.6.7.8", egress_ip="5.6.7.8")
        front = _make_pool("front", "front", [f1])
        exit_p = _make_pool("exit", "exit", [e1])
        router = StickyRouter(front, exit_p)
        router.route("s1", pool_id=1)
        # Remove e1 from pool
        exit_p.remove_node("e1")
        result = router.route("s1", pool_id=1)
        # Exit node not in healthy list, no same-IP match -> fallback to P2C
        # But we still have e1 in the pool (removed), so no healthy exit nodes -> None
        assert result is None


# ===========================================================================
# ProtocolCompat Tests
# ===========================================================================


class TestProtocolCompatGetSupported:
    """Test get_supported_protocols."""

    def test_singbox(self) -> None:
        protos = get_supported_protocols("singbox")
        assert "snell" in protos
        assert protos == SINGBOX_PROTOCOLS

    def test_mihomo(self) -> None:
        protos = get_supported_protocols("mihomo")
        assert "snell" not in protos

    def test_unknown_backend(self) -> None:
        with pytest.raises(ValueError, match="unknown backend type"):
            get_supported_protocols("unknown")

    def test_returns_copy(self) -> None:
        protos = get_supported_protocols("singbox")
        protos.add("custom")
        assert "custom" not in get_supported_protocols("singbox")


class TestProtocolCompatSupportsProtocol:
    """Test supports_protocol."""

    def test_supported(self) -> None:
        assert supports_protocol("vmess", "singbox") is True
        assert supports_protocol("snell", "singbox") is True

    def test_not_supported(self) -> None:
        assert supports_protocol("snell", "mihomo") is False

    def test_case_insensitive(self) -> None:
        assert supports_protocol("VMESS", "singbox") is True
        assert supports_protocol("Snell", "singbox") is True


class TestProtocolCompatFindBackend:
    """Test find_backend_for_protocol."""

    def test_singbox_only_protocol(self) -> None:
        assert find_backend_for_protocol("snell") == "singbox"

    def test_common_protocol(self) -> None:
        # vmess is in both; singbox is checked first
        assert find_backend_for_protocol("vmess") == "singbox"

    def test_unknown_protocol(self) -> None:
        assert find_backend_for_protocol("unknown") is None


class TestProtocolCompatCheckNodesCompatibility:
    """Test check_nodes_compatibility."""

    def test_all_compatible(self) -> None:
        nodes = [
            {"protocol": "vmess", "normalized_key": "k1"},
            {"protocol": "trojan", "normalized_key": "k2"},
        ]
        result = check_nodes_compatibility(nodes, "singbox")
        assert result["compatible"] is True
        assert result["incompatible_nodes"] == []

    def test_incompatible_node(self) -> None:
        nodes = [
            {"protocol": "vmess", "normalized_key": "k1"},
            {"protocol": "wireguard", "normalized_key": "k3"},
        ]
        result = check_nodes_compatibility(nodes, "singbox")
        assert result["compatible"] is False
        assert len(result["incompatible_nodes"]) == 1
        assert result["incompatible_nodes"][0]["protocol"] == "wireguard"

    def test_empty_nodes(self) -> None:
        result = check_nodes_compatibility([], "mihomo")
        assert result["compatible"] is True

    def test_missing_protocol_key(self) -> None:
        nodes = [{"normalized_key": "k1"}]
        result = check_nodes_compatibility(nodes, "singbox")
        assert result["compatible"] is True  # empty string protocol is not unsupported

    def test_mihomo_incompatible_with_snell(self) -> None:
        nodes = [{"protocol": "snell", "normalized_key": "k1"}]
        result = check_nodes_compatibility(nodes, "mihomo")
        assert result["compatible"] is False


class TestProtocolCompatFilterCompatibleNodes:
    """Test filter_compatible_nodes."""

    def test_filter_removes_incompatible(self) -> None:
        nodes = [
            {"protocol": "vmess"},
            {"protocol": "wireguard"},
            {"protocol": "trojan"},
        ]
        result = filter_compatible_nodes(nodes, "singbox")
        assert len(result) == 2
        assert all(n["protocol"] in ("vmess", "trojan") for n in result)

    def test_filter_all_compatible(self) -> None:
        nodes = [{"protocol": "vmess"}, {"protocol": "ss"}]
        result = filter_compatible_nodes(nodes, "singbox")
        assert len(result) == 2

    def test_filter_empty_input(self) -> None:
        assert filter_compatible_nodes([], "mihomo") == []


class TestProtocolCompatConstants:
    """Test module-level constants."""

    def test_all_supported_is_union(self) -> None:
        assert ALL_SUPPORTED_PROTOCOLS == SINGBOX_PROTOCOLS | {"vmess", "trojan", "ss", "vless", "hysteria2", "http", "https", "socks5"}

    def test_common_is_intersection(self) -> None:
        assert COMMON_PROTOCOLS == SINGBOX_PROTOCOLS & {"vmess", "trojan", "ss", "vless", "hysteria2", "http", "https", "socks5"}

    def test_snell_singbox_only(self) -> None:
        assert "snell" in SINGBOX_PROTOCOLS
        assert "snell" not in COMMON_PROTOCOLS
