"""
Scoring module: SlidingWindow statistics, NodeScorer, and CircuitBreaker.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProbeSample:
    """A single probe sample for sliding window."""
    timestamp: float
    success: bool
    latency_ms: int | None
    error_type: str = ""

    def age_hours(self) -> float:
        return (time.time() - self.timestamp) / 3600.0


class SlidingWindow:
    """Fixed-size sliding window for success rate and latency statistics."""

    def __init__(
        self,
        max_samples: int = 20,
        max_age_hours: float = 24.0,
    ) -> None:
        self.max_samples = max_samples
        self.max_age_hours = max_age_hours
        self._samples: deque[ProbeSample] = deque(maxlen=max_samples)
        self._lock = threading.RLock()

    def record(self, success: bool, latency_ms: int | None = None, error_type: str = "") -> None:
        sample = ProbeSample(timestamp=time.time(), success=success, latency_ms=latency_ms, error_type=error_type)
        with self._lock:
            self._samples.append(sample)
            self._cleanup()

    def _cleanup(self) -> None:
        if self.max_age_hours <= 0:
            return
        cutoff = time.time() - self.max_age_hours * 3600
        while self._samples and self._samples[0].timestamp < cutoff:
            self._samples.popleft()

    @property
    def size(self) -> int:
        with self._lock:
            self._cleanup()
            return len(self._samples)

    @property
    def success_rate(self) -> float:
        with self._lock:
            self._cleanup()
            if not self._samples:
                return 0.0
            return sum(1 for s in self._samples if s.success) / len(self._samples)

    @property
    def failure_rate(self) -> float:
        return 1.0 - self.success_rate

    def get_percentile(self, percentile: int) -> int | None:
        with self._lock:
            latencies = [s.latency_ms for s in self._samples if s.latency_ms is not None]
        if not latencies:
            return None
        latencies.sort()
        idx = min(int(len(latencies) * percentile / 100), len(latencies) - 1)
        return latencies[idx]

    @property
    def p50_latency(self) -> int | None:
        return self.get_percentile(50)

    @property
    def p95_latency(self) -> int | None:
        return self.get_percentile(95)

    @property
    def p99_latency(self) -> int | None:
        return self.get_percentile(99)

    @property
    def avg_latency(self) -> int | None:
        with self._lock:
            latencies = [s.latency_ms for s in self._samples if s.latency_ms is not None]
        if not latencies:
            return None
        return int(sum(latencies) / len(latencies))

    @property
    def stability_score(self) -> float:
        """Stability based on coefficient of variation. 1.0 = perfectly stable."""
        avg = self.avg_latency
        if avg is None or avg == 0:
            return 0.0
        with self._lock:
            latencies = [s.latency_ms for s in self._samples if s.latency_ms is not None]
        if len(latencies) < 2:
            return 1.0
        mean = sum(latencies) / len(latencies)
        variance = sum((x - mean) ** 2 for x in latencies) / (len(latencies) - 1)
        stddev = math.sqrt(variance)
        cv = stddev / avg
        return max(0.0, 1.0 - cv / 2)

    @property
    def last_success_age_hours(self) -> float | None:
        with self._lock:
            for s in reversed(self._samples):
                if s.success:
                    return s.age_hours()
            return None

    @property
    def last_failure_age_hours(self) -> float | None:
        with self._lock:
            for s in reversed(self._samples):
                if not s.success:
                    return s.age_hours()
            return None

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "success_rate": round(self.success_rate, 4),
            "p50_latency": self.p50_latency,
            "p95_latency": self.p95_latency,
            "p99_latency": self.p99_latency,
            "avg_latency": self.avg_latency,
            "stability_score": round(self.stability_score, 4),
        }


class WindowManager:
    """Manages sliding windows for multiple nodes."""

    def __init__(self, max_samples: int = 20, max_age_hours: float = 24.0) -> None:
        self.max_samples = max_samples
        self.max_age_hours = max_age_hours
        self._windows: dict[str, SlidingWindow] = {}
        self._lock = threading.RLock()

    def get_window(self, node_key: str) -> SlidingWindow:
        with self._lock:
            if node_key not in self._windows:
                self._windows[node_key] = SlidingWindow(
                    max_samples=self.max_samples,
                    max_age_hours=self.max_age_hours,
                )
            return self._windows[node_key]

    def record(self, node_key: str, success: bool, latency_ms: int | None = None, error_type: str = "") -> None:
        window = self.get_window(node_key)
        window.record(success, latency_ms, error_type)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {key: w.to_dict() for key, w in self._windows.items()}

    def remove_node(self, node_key: str) -> None:
        with self._lock:
            self._windows.pop(node_key, None)


# ---------------------------------------------------------------------------
# Node Scorer
# ---------------------------------------------------------------------------

class ScoreGrade(Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass
class ScoreWeights:
    success_rate: float = 0.40
    latency: float = 0.30
    purity: float = 0.20
    stability: float = 0.10
    excellent_latency_ms: int = 50
    poor_latency_ms: int = 500
    decay_lambda: float = 0.02

    def validate(self) -> bool:
        total = self.success_rate + self.latency + self.purity + self.stability
        return abs(total - 1.0) < 0.001


@dataclass
class NodeScore:
    node_key: str
    timestamp: float
    success_rate: float
    avg_latency_ms: int | None
    purity_score: float | None
    stability_score: float
    availability_score: float
    latency_score: float
    purity_score_normalized: float
    raw_score: float
    final_score: float
    grade: ScoreGrade
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_key": self.node_key,
            "final_score": round(self.final_score, 4),
            "grade": self.grade.value,
            "confidence": round(self.confidence, 4),
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": self.avg_latency_ms,
            "raw_score": round(self.raw_score, 4),
        }


class NodeScorer:
    """Multi-dimensional node scorer with time decay and confidence."""

    def __init__(self, weights: ScoreWeights | None = None) -> None:
        self.weights = weights or ScoreWeights()
        if not self.weights.validate():
            raise ValueError("Score weights must sum to 1.0")

    def score(
        self,
        node_key: str,
        window: SlidingWindow,
        purity_score: float | None = None,
    ) -> NodeScore:
        availability_score = self._score_availability(window.success_rate)
        latency_score = self._score_latency(window.avg_latency)
        purity_normalized = self._normalize_purity(purity_score)
        purity_score_val = self._score_purity(purity_normalized)
        stability_score_val = window.stability_score

        raw_score = (
            availability_score * self.weights.success_rate
            + latency_score * self.weights.latency
            + purity_score_val * self.weights.purity
            + stability_score_val * self.weights.stability
        )

        confidence = self._calculate_confidence(window.size)

        age = window.last_success_age_hours
        time_decay = self._calculate_time_decay(age)

        final_score = max(0.0, min(1.0, raw_score * confidence * time_decay))
        grade = self._score_to_grade(final_score)

        return NodeScore(
            node_key=node_key,
            timestamp=time.time(),
            success_rate=window.success_rate,
            avg_latency_ms=window.avg_latency,
            purity_score=purity_score,
            stability_score=stability_score_val,
            availability_score=availability_score,
            latency_score=latency_score,
            purity_score_normalized=purity_normalized,
            raw_score=raw_score,
            final_score=final_score,
            grade=grade,
            confidence=confidence,
        )

    def _score_availability(self, success_rate: float) -> float:
        if success_rate >= 0.95:
            return 1.0
        if success_rate >= 0.80:
            return 0.6 + (success_rate - 0.80) / 0.15 * 0.4
        return success_rate / 0.80 * 0.6

    def _score_latency(self, latency_ms: int | None) -> float:
        if latency_ms is None:
            return 0.5
        if latency_ms <= self.weights.excellent_latency_ms:
            return 1.0
        if latency_ms >= self.weights.poor_latency_ms:
            return 0.0
        return 1.0 - (latency_ms - self.weights.excellent_latency_ms) / (
            self.weights.poor_latency_ms - self.weights.excellent_latency_ms
        )

    def _normalize_purity(self, purity_score: float | None) -> float:
        if purity_score is None:
            return 0.5
        return max(0.0, min(1.0, purity_score / 100.0))

    def _score_purity(self, normalized: float) -> float:
        if normalized >= 0.7:
            return 1.0
        if normalized <= 0.3:
            return 0.3
        return 0.3 + (normalized - 0.3) / 0.4 * 0.7

    def _calculate_confidence(self, sample_count: int) -> float:
        if sample_count <= 0:
            return 0.0
        return 1.0 / (1.0 + math.exp(-0.5 * (sample_count - 10)))

    def _calculate_time_decay(self, age_hours: float | None) -> float:
        if age_hours is None:
            return 0.5
        return math.exp(-self.weights.decay_lambda * age_hours)

    @staticmethod
    def _score_to_grade(score: float) -> ScoreGrade:
        if score >= 0.8:
            return ScoreGrade.A
        if score >= 0.6:
            return ScoreGrade.B
        if score >= 0.4:
            return ScoreGrade.C
        return ScoreGrade.D


class NodeScorerManager:
    """Manages scores for all nodes."""

    def __init__(self, weights: ScoreWeights | None = None) -> None:
        self.scorer = NodeScorer(weights)
        self._scores: dict[str, NodeScore] = {}
        self._lock = threading.RLock()

    def update_score(
        self,
        node_key: str,
        window: SlidingWindow,
        purity_score: float | None = None,
    ) -> NodeScore:
        score = self.scorer.score(node_key, window, purity_score)
        with self._lock:
            old_score = self._scores.get(node_key)
            self._scores[node_key] = score

        # Log significant score changes (more than 0.1)
        if old_score is not None:
            delta = score.final_score - old_score.final_score
            if abs(delta) > 0.1:
                logger.info(
                    "Score changed",
                    extra={"extra_data": {
                        "node_key": node_key,
                        "old_score": round(old_score.final_score, 4),
                        "new_score": round(score.final_score, 4),
                        "delta": round(delta, 4),
                        "grade": score.grade.value,
                    }}
                )

        return score

    def get_score(self, node_key: str) -> NodeScore | None:
        with self._lock:
            return self._scores.get(node_key)

    def get_all_scores(self) -> dict[str, NodeScore]:
        with self._lock:
            return dict(self._scores)

    def get_top_nodes(self, limit: int = 10, min_confidence: float = 0.5) -> list[NodeScore]:
        with self._lock:
            candidates = [s for s in self._scores.values() if s.confidence >= min_confidence]
        candidates.sort(key=lambda s: s.final_score, reverse=True)
        return candidates[:limit]

    def remove_node(self, node_key: str) -> None:
        with self._lock:
            self._scores.pop(node_key, None)

    def set_score(self, node_key: str, score: NodeScore) -> None:
        """Set score directly (used for restoring from storage)."""
        with self._lock:
            self._scores[node_key] = score


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    half_open_max_probes: int = 3
    recovery_threshold: int = 2
    initial_backoff_sec: float = 30.0
    max_backoff_sec: float = 600.0
    backoff_multiplier: float = 2.0


class CircuitBreaker:
    """Three-state circuit breaker with exponential backoff."""

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._consecutive_successes = 0
        self._last_failure_time: float | None = None
        self._last_success_time: float | None = None
        self._open_since: float | None = None
        self._backoff_until: float | None = None
        self._current_backoff_sec = self.config.initial_backoff_sec
        self._half_open_probes = 0
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._check_open_timeout()
            return self._state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    @property
    def current_backoff_sec(self) -> float:
        with self._lock:
            return self._current_backoff_sec

    def is_allow_probe(self) -> bool:
        with self._lock:
            self._check_open_timeout()
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.HALF_OPEN:
                return self._half_open_probes < self.config.half_open_max_probes
            return False

    def record_success(self) -> None:
        with self._lock:
            self._last_success_time = time.time()
            self._consecutive_successes += 1
            if self._state == CircuitState.CLOSED:
                self._failure_count = 0
            elif self._state == CircuitState.HALF_OPEN:
                self._half_open_probes += 1
                if self._consecutive_successes >= self.config.recovery_threshold:
                    self._transition_to_closed()

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._consecutive_successes = 0
            self._last_failure_time = time.time()

            if self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to_open()
            elif self._state == CircuitState.HALF_OPEN:
                self._transition_to_open()

    def _transition_to_open(self) -> None:
        self._state = CircuitState.OPEN
        self._open_since = time.time()
        self._half_open_probes = 0
        self._backoff_until = time.time() + self._current_backoff_sec

    def _transition_to_half_open(self) -> None:
        self._state = CircuitState.HALF_OPEN
        self._half_open_probes = 0
        self._consecutive_successes = 0
        self._backoff_until = None

    def _transition_to_closed(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._consecutive_successes = 0
        self._open_since = None
        self._backoff_until = None
        self._current_backoff_sec = self.config.initial_backoff_sec

    def _check_open_timeout(self) -> None:
        if self._state != CircuitState.OPEN or self._backoff_until is None:
            return
        if time.time() >= self._backoff_until:
            self._transition_to_half_open()

    def force_open(self) -> None:
        with self._lock:
            self._transition_to_open()

    def force_close(self) -> None:
        with self._lock:
            self._transition_to_closed()


class CircuitBreakerManager:
    """Manages circuit breakers for all nodes."""

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()

    def get_breaker(self, node_key: str) -> CircuitBreaker:
        with self._lock:
            if node_key not in self._breakers:
                self._breakers[node_key] = CircuitBreaker(self.config)
            return self._breakers[node_key]

    def is_allow_probe(self, node_key: str) -> bool:
        return self.get_breaker(node_key).is_allow_probe()

    def record_success(self, node_key: str) -> None:
        self.get_breaker(node_key).record_success()

    def record_failure(self, node_key: str) -> None:
        self.get_breaker(node_key).record_failure()

    def get_state(self, node_key: str) -> CircuitState:
        return self.get_breaker(node_key).state

    def remove_node(self, node_key: str) -> None:
        with self._lock:
            self._breakers.pop(node_key, None)
