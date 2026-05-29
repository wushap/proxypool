"""
Tests to cover remaining uncovered lines in pool/scoring.py.

Targets:
- WindowManager.get_all_stats (line 187-188)
- NodeScorerManager.update_score logging branch (lines 373-375)
- CircuitBreaker record_success while OPEN (branch 486->exit)
- CircuitBreaker record_failure while OPEN (branch 500->exit)
- CircuitBreakerManager.is_allow_probe (line 582)
- CircuitBreakerManager.record_success (line 585)
"""

from __future__ import annotations

import time

from proxypool.pool.scoring import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerManager,
    CircuitState,
    NodeScorerManager,
    SlidingWindow,
    WindowManager,
)


# ---------------------------------------------------------------------------
# WindowManager.get_all_stats
# ---------------------------------------------------------------------------


class TestWindowManagerGetAllStats:
    def test_get_all_stats_empty(self) -> None:
        mgr = WindowManager()
        assert mgr.get_all_stats() == {}

    def test_get_all_stats_populated(self) -> None:
        mgr = WindowManager()
        mgr.record("n1", success=True, latency_ms=100)
        mgr.record("n2", success=False, latency_ms=200)
        stats = mgr.get_all_stats()
        assert len(stats) == 2
        assert "n1" in stats
        assert "n2" in stats
        assert stats["n1"]["size"] == 1
        assert stats["n1"]["success_rate"] == 1.0
        assert stats["n2"]["success_rate"] == 0.0


# ---------------------------------------------------------------------------
# NodeScorerManager logging branch
# ---------------------------------------------------------------------------


class TestNodeScorerManagerLogging:
    def test_large_score_change_triggers_logging(self) -> None:
        """update_score logs when delta > 0.1 between consecutive updates."""
        mgr = NodeScorerManager()

        # First update: low score (all failures)
        w1 = SlidingWindow()
        for _ in range(20):
            w1.record(success=False, latency_ms=1000)
        mgr.update_score("node1", w1)

        # Second update: high score (all successes, low latency) -> big delta
        w2 = SlidingWindow()
        for _ in range(20):
            w2.record(success=True, latency_ms=30)
        score = mgr.update_score("node1", w2)

        # Verify score changed significantly (the logging branch was hit)
        assert score.final_score > 0.1

    def test_small_score_change_no_logging(self) -> None:
        """Small deltas do not trigger the logging branch."""
        mgr = NodeScorerManager()

        w1 = SlidingWindow()
        for _ in range(20):
            w1.record(success=True, latency_ms=100)
        mgr.update_score("node1", w1)

        # Similar conditions -> small delta
        w2 = SlidingWindow()
        for _ in range(20):
            w2.record(success=True, latency_ms=110)
        score = mgr.update_score("node1", w2)
        assert score.final_score > 0.0


# ---------------------------------------------------------------------------
# CircuitBreaker OPEN-state branches
# ---------------------------------------------------------------------------


class TestCircuitBreakerOpenStateBranches:
    def test_record_success_while_open(self) -> None:
        """record_success called while state is OPEN (not HALF_OPEN)."""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # record_success while OPEN: resets consecutive_successes
        # but does NOT change state (stays OPEN until backoff expires)
        cb.record_success()
        with cb._lock:
            assert cb._state == CircuitState.OPEN
            assert cb._consecutive_successes == 1

    def test_record_failure_while_open(self) -> None:
        """record_failure called while state is OPEN."""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # record_failure while OPEN: increments count, no transition
        cb.record_failure()
        with cb._lock:
            assert cb._state == CircuitState.OPEN
            assert cb._failure_count == 3


# ---------------------------------------------------------------------------
# CircuitBreakerManager delegated methods
# ---------------------------------------------------------------------------


class TestCircuitBreakerManagerDelegates:
    def test_is_allow_probe(self) -> None:
        mgr = CircuitBreakerManager(CircuitBreakerConfig(failure_threshold=2))
        # CLOSED state -> allowed
        assert mgr.is_allow_probe("n1") is True

        # Trip the breaker
        mgr.record_failure("n1")
        mgr.record_failure("n1")
        assert mgr.is_allow_probe("n1") is False

    def test_record_success(self) -> None:
        mgr = CircuitBreakerManager()
        mgr.record_failure("n1")
        mgr.record_success("n1")
        breaker = mgr.get_breaker("n1")
        assert breaker.failure_count == 0
