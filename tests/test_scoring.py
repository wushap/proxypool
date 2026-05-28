"""
Tests for Scoring module: SlidingWindow, NodeScorer, and CircuitBreaker.
"""

from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from proxypool.pool.scoring import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerManager,
    CircuitState,
    NodeScorer,
    NodeScorerManager,
    ScoreGrade,
    ScoreWeights,
    SlidingWindow,
    WindowManager,
)


class TestSlidingWindow(unittest.TestCase):
    """Test SlidingWindow class."""

    def test_empty_window(self):
        """Test empty window returns correct defaults."""
        window = SlidingWindow()
        self.assertEqual(window.size, 0)
        self.assertEqual(window.success_rate, 0.0)
        self.assertEqual(window.failure_rate, 1.0)
        self.assertIsNone(window.avg_latency)
        self.assertIsNone(window.p50_latency)
        self.assertIsNone(window.p95_latency)
        self.assertIsNone(window.p99_latency)
        self.assertEqual(window.stability_score, 0.0)

    def test_record_samples(self):
        """Test recording samples and basic statistics."""
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)
        window.record(success=False, latency_ms=200)
        window.record(success=True, latency_ms=150)

        self.assertEqual(window.size, 3)
        self.assertAlmostEqual(window.success_rate, 2 / 3, places=2)
        self.assertAlmostEqual(window.failure_rate, 1 / 3, places=2)
        self.assertEqual(window.avg_latency, 150)  # (100+200+150)/3

    def test_max_samples_limit(self):
        """Test max_samples limit."""
        window = SlidingWindow(max_samples=3)
        window.record(success=True, latency_ms=100)
        window.record(success=True, latency_ms=110)
        window.record(success=True, latency_ms=120)
        window.record(success=True, latency_ms=130)

        self.assertEqual(window.size, 3)  # Only keeps last 3

    def test_latency_percentiles(self):
        """Test latency percentile calculations."""
        window = SlidingWindow(max_samples=100)  # Increase max samples
        for i in range(100):
            window.record(success=True, latency_ms=i + 1)

        p50 = window.p50_latency
        p95 = window.p95_latency
        p99 = window.p99_latency

        self.assertIsNotNone(p50)
        self.assertIsNotNone(p95)
        self.assertIsNotNone(p99)
        # Allow some tolerance due to integer indexing
        self.assertGreaterEqual(p50, 49)
        self.assertLessEqual(p50, 52)
        self.assertGreaterEqual(p95, 94)
        self.assertLessEqual(p95, 96)
        self.assertEqual(p99, 100)

    def test_stability_score(self):
        """Test stability score calculation."""
        # Perfect stability (all same latency)
        window1 = SlidingWindow()
        for _ in range(10):
            window1.record(success=True, latency_ms=100)
        self.assertEqual(window1.stability_score, 1.0)

        # Low stability (high variance)
        window2 = SlidingWindow()
        window2.record(success=True, latency_ms=50)
        window2.record(success=True, latency_ms=200)
        window2.record(success=True, latency_ms=100)
        self.assertLess(window2.stability_score, 0.8)

    def test_time_cleanup(self):
        """Test time-based cleanup of old samples."""
        window = SlidingWindow(max_age_hours=0.001)  # ~3.6 seconds
        window.record(success=True, latency_ms=100)
        self.assertEqual(window.size, 1)

        # Mock time to simulate aging
        with patch("time.time", return_value=time.time() + 10):
            window.record(success=True, latency_ms=100)
            self.assertEqual(window.size, 1)  # Old sample cleaned up

    def test_to_dict(self):
        """Test to_dict serialization."""
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)
        d = window.to_dict()

        self.assertIn("size", d)
        self.assertIn("success_rate", d)
        self.assertIn("avg_latency", d)
        self.assertIn("stability_score", d)
        self.assertEqual(d["size"], 1)
        self.assertEqual(d["success_rate"], 1.0)
        self.assertEqual(d["avg_latency"], 100)


class TestWindowManager(unittest.TestCase):
    """Test WindowManager class."""

    def test_get_window_creates_new(self):
        """Test get_window creates new window if not exists."""
        manager = WindowManager()
        window = manager.get_window("node1")
        self.assertIsInstance(window, SlidingWindow)
        self.assertEqual(window.size, 0)

    def test_get_window_returns_existing(self):
        """Test get_window returns same window for same key."""
        manager = WindowManager()
        window1 = manager.get_window("node1")
        window2 = manager.get_window("node1")
        self.assertIs(window1, window2)

    def test_record_creates_window(self):
        """Test record creates window if not exists."""
        manager = WindowManager()
        manager.record("node1", success=True, latency_ms=100)
        window = manager.get_window("node1")
        self.assertEqual(window.size, 1)

    def test_remove_node(self):
        """Test remove_node removes window."""
        manager = WindowManager()
        manager.record("node1", success=True, latency_ms=100)
        manager.remove_node("node1")
        window = manager.get_window("node1")
        self.assertEqual(window.size, 0)


class TestScoreWeights(unittest.TestCase):
    """Test ScoreWeights class."""

    def test_default_weights(self):
        """Test default weights sum to 1.0."""
        weights = ScoreWeights()
        self.assertTrue(weights.validate())

    def test_custom_weights(self):
        """Test custom weights validation."""
        weights = ScoreWeights(success_rate=0.5, latency=0.3, purity=0.1, stability=0.1)
        self.assertTrue(weights.validate())

    def test_invalid_weights(self):
        """Test invalid weights fail validation."""
        weights = ScoreWeights(success_rate=0.5, latency=0.5, purity=0.5, stability=0.5)
        self.assertFalse(weights.validate())


class TestNodeScorer(unittest.TestCase):
    """Test NodeScorer class."""

    def test_score_with_good_node(self):
        """Test scoring a good node."""
        scorer = NodeScorer()
        window = SlidingWindow()

        # Record 20 successful probes with low latency (to increase confidence)
        for _ in range(20):
            window.record(success=True, latency_ms=50)

        score = scorer.score("node1", window, purity_score=80.0)

        self.assertEqual(score.node_key, "node1")
        self.assertGreater(score.raw_score, 0.7)  # Raw score should be high
        self.assertGreater(score.confidence, 0.5)
        # Final score may be lower due to time decay, but should still be reasonable
        self.assertGreater(score.final_score, 0.3)

    def test_score_with_bad_node(self):
        """Test scoring a bad node."""
        scorer = NodeScorer()
        window = SlidingWindow()

        # Record 10 failed probes
        for _ in range(10):
            window.record(success=False, latency_ms=1000)

        score = scorer.score("node1", window)

        self.assertLess(score.final_score, 0.3)
        self.assertEqual(score.grade, ScoreGrade.D)

    def test_score_availability(self):
        """Test availability scoring."""
        scorer = NodeScorer()

        self.assertEqual(scorer._score_availability(0.95), 1.0)
        self.assertEqual(scorer._score_availability(1.0), 1.0)
        self.assertLess(scorer._score_availability(0.80), 1.0)
        self.assertEqual(scorer._score_availability(0.0), 0.0)

    def test_score_latency(self):
        """Test latency scoring."""
        scorer = NodeScorer()

        # Excellent latency
        self.assertEqual(scorer._score_latency(50), 1.0)

        # Poor latency
        self.assertEqual(scorer._score_latency(500), 0.0)

        # Unknown latency
        self.assertEqual(scorer._score_latency(None), 0.5)

    def test_score_to_grade(self):
        """Test score to grade conversion."""
        self.assertEqual(NodeScorer._score_to_grade(0.9), ScoreGrade.A)
        self.assertEqual(NodeScorer._score_to_grade(0.7), ScoreGrade.B)
        self.assertEqual(NodeScorer._score_to_grade(0.5), ScoreGrade.C)
        self.assertEqual(NodeScorer._score_to_grade(0.3), ScoreGrade.D)


class TestCircuitBreaker(unittest.TestCase):
    """Test CircuitBreaker class."""

    def test_initial_state(self):
        """Test initial state is CLOSED."""
        cb = CircuitBreaker()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertFalse(cb.is_open)
        self.assertTrue(cb.is_allow_probe())

    def test_transition_to_open(self):
        """Test transition to OPEN on threshold failures."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker(config)

        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED)

        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED)

        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertTrue(cb.is_open)
        self.assertFalse(cb.is_allow_probe())

    def test_transition_to_half_open(self):
        """Test transition to HALF_OPEN after backoff."""
        config = CircuitBreakerConfig(failure_threshold=2, initial_backoff_sec=0.1)
        cb = CircuitBreaker(config)

        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)

        # Wait for backoff
        time.sleep(0.15)

        # Check state transitions to HALF_OPEN
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        self.assertTrue(cb.is_allow_probe())

    def test_recovery_to_closed(self):
        """Test recovery from HALF_OPEN to CLOSED."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            half_open_max_probes=3,
            recovery_threshold=2,
            initial_backoff_sec=0.1,
        )
        cb = CircuitBreaker(config)

        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)

        # Force transition to HALF_OPEN
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        cb.record_success()
        with cb._lock:
            self.assertEqual(cb._state, CircuitState.HALF_OPEN)

        cb.record_success()
        with cb._lock:
            self.assertEqual(cb._state, CircuitState.CLOSED)

    def test_failure_in_half_open_reopens(self):
        """Test failure in HALF_OPEN transitions back to OPEN."""
        config = CircuitBreakerConfig(failure_threshold=2, initial_backoff_sec=0.1)
        cb = CircuitBreaker(config)

        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)

        # Force transition to HALF_OPEN by checking state
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        # Record failure while in HALF_OPEN
        cb.record_failure()

        # Access internal state directly to avoid timeout check
        with cb._lock:
            self.assertEqual(cb._state, CircuitState.OPEN)

    def test_success_resets_failure_count(self):
        """Test success resets failure count in CLOSED state."""
        cb = CircuitBreaker()

        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.failure_count, 2)

        cb.record_success()
        self.assertEqual(cb.failure_count, 0)

    def test_force_open(self):
        """Test force_open."""
        cb = CircuitBreaker()
        cb.force_open()
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_force_close(self):
        """Test force_close."""
        cb = CircuitBreaker()
        cb.force_open()
        cb.force_close()
        self.assertEqual(cb.state, CircuitState.CLOSED)


class TestCircuitBreakerManager(unittest.TestCase):
    """Test CircuitBreakerManager class."""

    def test_get_breaker_creates_new(self):
        """Test get_breaker creates new breaker if not exists."""
        manager = CircuitBreakerManager()
        breaker = manager.get_breaker("node1")
        self.assertIsInstance(breaker, CircuitBreaker)

    def test_get_breaker_returns_existing(self):
        """Test get_breaker returns same breaker for same key."""
        manager = CircuitBreakerManager()
        breaker1 = manager.get_breaker("node1")
        breaker2 = manager.get_breaker("node1")
        self.assertIs(breaker1, breaker2)

    def test_remove_node(self):
        """Test remove_node removes breaker."""
        manager = CircuitBreakerManager()
        manager.record_failure("node1")
        self.assertEqual(manager.get_state("node1"), CircuitState.CLOSED)

        manager.remove_node("node1")
        # Should create new breaker
        self.assertEqual(manager.get_state("node1"), CircuitState.CLOSED)


class TestNodeScorerManager(unittest.TestCase):
    """Test NodeScorerManager class."""

    def test_update_and_get_score(self):
        """Test update_score and get_score."""
        manager = NodeScorerManager()
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)

        score = manager.update_score("node1", window)
        retrieved = manager.get_score("node1")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.node_key, "node1")
        self.assertEqual(score.final_score, retrieved.final_score)

    def test_get_top_nodes(self):
        """Test get_top_nodes returns sorted by score."""
        manager = NodeScorerManager()

        # Create windows with different quality
        window1 = SlidingWindow()
        for _ in range(20):
            window1.record(success=True, latency_ms=50)

        window2 = SlidingWindow()
        for _ in range(20):
            window2.record(success=True, latency_ms=200)

        manager.update_score("good_node", window1)
        manager.update_score("bad_node", window2)

        top = manager.get_top_nodes(limit=10, min_confidence=0.0)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].node_key, "good_node")

    def test_remove_node(self):
        """Test remove_node."""
        manager = NodeScorerManager()
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)

        manager.update_score("node1", window)
        self.assertIsNotNone(manager.get_score("node1"))

        manager.remove_node("node1")
        self.assertIsNone(manager.get_score("node1"))

    def test_get_all_scores(self):
        """Test get_all_scores."""
        manager = NodeScorerManager()
        window = SlidingWindow()
        window.record(success=True, latency_ms=100)

        manager.update_score("node1", window)
        manager.update_score("node2", window)

        all_scores = manager.get_all_scores()
        self.assertEqual(len(all_scores), 2)
        self.assertIn("node1", all_scores)
        self.assertIn("node2", all_scores)


if __name__ == "__main__":
    unittest.main()
