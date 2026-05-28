"""
Extended tests for scoring module edge cases.

Covers: restore_state, set_score, ProbeSample, NodeScore.to_dict,
score normalization boundaries, and backoff escalation.
"""

from __future__ import annotations

import time

import pytest

from proxypool.pool.scoring import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    NodeScorer,
    NodeScore,
    ProbeSample,
    ScoreGrade,
    ScoreWeights,
    SlidingWindow,
    NodeScorerManager,
)


class TestProbeSample:
    def test_age_hours(self) -> None:
        sample = ProbeSample(timestamp=time.time() - 7200, success=True, latency_ms=100)
        age = sample.age_hours()
        assert 1.9 < age < 2.1

    def test_age_hours_zero(self) -> None:
        sample = ProbeSample(timestamp=time.time(), success=True, latency_ms=50)
        assert sample.age_hours() < 0.01

    def test_error_type_default(self) -> None:
        sample = ProbeSample(timestamp=time.time(), success=False, latency_ms=None)
        assert sample.error_type == ""

    def test_error_type_custom(self) -> None:
        sample = ProbeSample(timestamp=time.time(), success=False, latency_ms=None, error_type="timeout")
        assert sample.error_type == "timeout"


class TestSlidingWindowEdgeCases:
    def test_get_percentile_no_latencies(self) -> None:
        window = SlidingWindow()
        assert window.get_percentile(50) is None

    def test_get_percentile_single_sample(self) -> None:
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)
        assert window.get_percentile(50) == 100

    def test_stability_single_sample(self) -> None:
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)
        assert window.stability_score == 1.0

    def test_stability_zero_latency(self) -> None:
        """Zero avg latency returns 0.0 to avoid division by zero."""
        window = SlidingWindow()
        window.record(success=True, latency_ms=0)
        assert window.stability_score == 0.0

    def test_last_success_and_failure_age(self) -> None:
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)
        window.record(success=False, latency_ms=200)
        assert window.last_success_age_hours is not None
        assert window.last_failure_age_hours is not None
        assert window.last_failure_age_hours < 0.01

    def test_last_success_none_when_no_successes(self) -> None:
        window = SlidingWindow()
        window.record(success=False, latency_ms=100)
        assert window.last_success_age_hours is None

    def test_last_failure_none_when_no_failures(self) -> None:
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)
        assert window.last_failure_age_hours is None

    def test_clear(self) -> None:
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)
        window.record(success=True, latency_ms=200)
        window.clear()
        assert window.size == 0

    def test_max_age_zero_disables_cleanup(self) -> None:
        """max_age_hours=0 should disable time-based cleanup."""
        window = SlidingWindow(max_age_hours=0)
        window.record(success=True, latency_ms=100)
        assert window.size == 1


class TestNodeScorerEdgeCases:
    def test_invalid_weights_raises(self) -> None:
        with pytest.raises(ValueError, match="sum to 1.0"):
            NodeScorer(ScoreWeights(success_rate=0.5, latency=0.5, purity=0.5, stability=0.5))

    def test_score_availability_boundary_80_95(self) -> None:
        scorer = NodeScorer()
        # At 87.5% (midpoint), should be between 0.6 and 1.0
        mid = scorer._score_availability(0.875)
        assert 0.6 < mid < 1.0

    def test_score_latency_midrange(self) -> None:
        scorer = NodeScorer()
        # Midpoint between 50 and 500
        mid = scorer._score_latency(275)
        assert 0.4 < mid < 0.6

    def test_normalize_purity_none(self) -> None:
        scorer = NodeScorer()
        assert scorer._normalize_purity(None) == 0.5

    def test_normalize_purity_clamping(self) -> None:
        scorer = NodeScorer()
        assert scorer._normalize_purity(150) == 1.0
        assert scorer._normalize_purity(-10) == 0.0

    def test_score_purity_boundaries(self) -> None:
        scorer = NodeScorer()
        assert scorer._score_purity(0.8) == 1.0
        assert scorer._score_purity(0.2) == 0.3
        mid = scorer._score_purity(0.5)
        assert 0.3 < mid < 1.0

    def test_confidence_zero_samples(self) -> None:
        scorer = NodeScorer()
        assert scorer._calculate_confidence(0) == 0.0

    def test_confidence_large_sample_count(self) -> None:
        scorer = NodeScorer()
        conf = scorer._calculate_confidence(100)
        assert conf > 0.99

    def test_time_decay_none_age(self) -> None:
        scorer = NodeScorer()
        assert scorer._calculate_time_decay(None) == 0.5

    def test_time_decay_zero_age(self) -> None:
        scorer = NodeScorer()
        assert scorer._calculate_time_decay(0) == 1.0

    def test_score_grades_boundary(self) -> None:
        assert NodeScorer._score_to_grade(0.8) == ScoreGrade.A
        assert NodeScorer._score_to_grade(0.79) == ScoreGrade.B
        assert NodeScorer._score_to_grade(0.6) == ScoreGrade.B
        assert NodeScorer._score_to_grade(0.59) == ScoreGrade.C
        assert NodeScorer._score_to_grade(0.4) == ScoreGrade.C
        assert NodeScorer._score_to_grade(0.39) == ScoreGrade.D

    def test_score_clamped_to_0_1(self) -> None:
        """Final score is clamped to [0.0, 1.0]."""
        scorer = NodeScorer()
        window = SlidingWindow()
        for _ in range(20):
            window.record(success=True, latency_ms=10)
        score = scorer.score("node", window, purity_score=100)
        assert score.final_score <= 1.0
        assert score.final_score >= 0.0


class TestNodeScoreToDict:
    def test_to_dict_keys(self) -> None:
        scorer = NodeScorer()
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)
        score = scorer.score("node1", window)
        d = score.to_dict()
        assert "node_key" in d
        assert "final_score" in d
        assert "grade" in d
        assert "confidence" in d
        assert "success_rate" in d
        assert "avg_latency_ms" in d
        assert "raw_score" in d

    def test_to_dict_grade_is_string(self) -> None:
        scorer = NodeScorer()
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)
        score = scorer.score("n", window)
        assert score.to_dict()["grade"] in ("A", "B", "C", "D")


class TestNodeScorerManagerEdgeCases:
    def test_set_score(self) -> None:
        manager = NodeScorerManager()
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)
        score = manager.update_score("n1", window)
        # Directly set a different score
        new_score = NodeScore(
            node_key="n2", timestamp=time.time(), success_rate=1.0,
            avg_latency_ms=50, purity_score=None, stability_score=1.0,
            availability_score=1.0, latency_score=1.0, purity_score_normalized=0.5,
            raw_score=0.9, final_score=0.9, grade=ScoreGrade.A, confidence=0.95,
        )
        manager.set_score("n2", new_score)
        assert manager.get_score("n2").final_score == 0.9

    def test_get_score_missing(self) -> None:
        manager = NodeScorerManager()
        assert manager.get_score("nope") is None

    def test_get_top_nodes_filters_by_confidence(self) -> None:
        manager = NodeScorerManager()
        # Low confidence window (1 sample)
        w1 = SlidingWindow()
        w1.record(success=True, latency_ms=50)
        manager.update_score("low-conf", w1)

        # High confidence window (20 samples)
        w2 = SlidingWindow()
        for _ in range(20):
            w2.record(success=True, latency_ms=100)
        manager.update_score("high-conf", w2)

        top = manager.get_top_nodes(limit=10, min_confidence=0.5)
        # Low-confidence node should be filtered out
        keys = [s.node_key for s in top]
        assert "high-conf" in keys


class TestCircuitBreakerRestoreState:
    def test_restore_closed(self) -> None:
        cb = CircuitBreaker()
        cb.force_open()
        cb.restore_state(CircuitState.CLOSED, failure_count=0)
        assert cb.state == CircuitState.CLOSED

    def test_restore_open(self) -> None:
        cb = CircuitBreaker()
        cb.restore_state(
            CircuitState.OPEN,
            failure_count=3,
            backoff_until=time.time() + 60,
        )
        with cb._lock:
            assert cb._state == CircuitState.OPEN
            assert cb._failure_count == 3

    def test_restore_half_open(self) -> None:
        cb = CircuitBreaker()
        cb.restore_state(CircuitState.HALF_OPEN, consecutive_successes=1)
        with cb._lock:
            assert cb._state == CircuitState.HALF_OPEN
            assert cb._half_open_probes == 0

    def test_restore_with_custom_backoff(self) -> None:
        cb = CircuitBreaker()
        cb.restore_state(
            CircuitState.OPEN,
            current_backoff_sec=120.0,
        )
        assert cb.current_backoff_sec == 120.0


class TestCircuitBreakerBackoffEscalation:
    def test_backoff_resets_on_recovery(self) -> None:
        """After recovery to CLOSED, current_backoff_sec resets to initial."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            initial_backoff_sec=0.05,
            backoff_multiplier=2.0,
        )
        cb = CircuitBreaker(config)

        # Open -> half-open -> closed
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        # Backoff resets to initial after recovery
        assert cb.current_backoff_sec == config.initial_backoff_sec

    def test_half_open_probe_limit(self) -> None:
        config = CircuitBreakerConfig(
            failure_threshold=1,
            half_open_max_probes=2,
            initial_backoff_sec=0.05,
        )
        cb = CircuitBreaker(config)
        cb.record_failure()
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        # Use up probes
        assert cb.is_allow_probe() is True
        cb.record_success()
        assert cb.is_allow_probe() is True
        cb.record_success()
        # After recovery, should be CLOSED, still allow
        assert cb.state == CircuitState.CLOSED
        assert cb.is_allow_probe() is True
