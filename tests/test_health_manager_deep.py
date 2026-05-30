"""Deep edge-case tests for pool/health_manager.py to reach 100% branch coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from proxypool.pool.health_manager import HealthManager
from proxypool.pool.node_pool import NodeEntry, NodePool
from proxypool.pool.scoring import CircuitState
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
# Branch 163->165: stop() when _probe_task is None
# ---------------------------------------------------------------------------

class TestStopWithoutStart:
    def test_stop_without_start_skips_join(self, storage, front_pool, exit_pool):
        """Calling stop() without start() means _probe_task is None, skip join."""
        mgr = _make_manager(storage, front_pool, exit_pool)
        assert mgr._probe_task is None
        # Should not raise — the if-branch is False so join is skipped
        mgr.stop()
        assert mgr._running is False


# ---------------------------------------------------------------------------
# Branch 438->449 and 475->490: score is None paths
# ---------------------------------------------------------------------------

class TestUpdateNodeHealthScoreNone:
    def test_score_none_skips_log_and_persists_breaker(self, storage, front_pool, exit_pool):
        """When scorer_manager.update_score returns None, the score-related
        log at line 438 and the score persistence at line 475 are skipped,
        but the circuit breaker is still persisted."""
        mgr = _make_manager(storage, front_pool, exit_pool)
        mgr.scorer_manager.update_score = MagicMock(return_value=None)
        mgr._update_node_health(front_pool, "f1", success=True, latency_ms=30)
        node = front_pool.get_node("f1")
        assert node is not None
        # score should be None on the node
        assert node.score is None

    def test_score_none_with_health_storage(self, storage, front_pool, exit_pool, health_storage):
        """With health_storage set and score=None, circuit breaker is still
        persisted but node score upsert is skipped (branch 475->490)."""
        mgr = _make_manager(storage, front_pool, exit_pool, health_storage=health_storage)
        mgr.scorer_manager.update_score = MagicMock(return_value=None)
        mgr._update_node_health(front_pool, "f1", success=True, latency_ms=30)
        # Probe record should still be inserted
        records = health_storage.get_probe_records("f1")
        assert len(records) > 0
        # Circuit breaker should be persisted
        cb_data = health_storage.get_circuit_breaker("f1")
        assert cb_data is not None
        # Node score should NOT be persisted (upsert_node_score was skipped)
        score_data = health_storage.get_node_score("f1")
        assert score_data is None
