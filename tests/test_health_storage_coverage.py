"""
Dedicated tests for proxypool.storage.health_storage.HealthStorage.

Covers probe records, node scores, and circuit breaker state operations.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from proxypool.storage.health_storage import HealthStorage


@pytest.fixture()
def hs(tmp_path: Path) -> HealthStorage:
    return HealthStorage(db_path=tmp_path / "health.db")


# ---- Probe Records ----


class TestProbeRecords:
    def test_insert_and_retrieve(self, hs: HealthStorage) -> None:
        hs.insert_probe_record("n1", success=True, latency_ms=30, source="test")
        records = hs.get_probe_records("n1")
        assert len(records) == 1
        assert records[0]["node_key"] == "n1"
        assert records[0]["success"] == 1
        assert records[0]["latency_ms"] == 30
        assert records[0]["source"] == "test"

    def test_insert_failure(self, hs: HealthStorage) -> None:
        hs.insert_probe_record("n1", success=False, error_type="timeout")
        records = hs.get_probe_records("n1")
        assert records[0]["success"] == 0
        assert records[0]["error_type"] == "timeout"

    def test_get_returns_descending_order(self, hs: HealthStorage) -> None:
        for i in range(3):
            hs.insert_probe_record("n1", success=True)
        records = hs.get_probe_records("n1")
        timestamps = [r["timestamp"] for r in records]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_get_limit(self, hs: HealthStorage) -> None:
        for _ in range(5):
            hs.insert_probe_record("n1", success=True)
        records = hs.get_probe_records("n1", limit=2)
        assert len(records) == 2

    def test_get_isolation_by_node(self, hs: HealthStorage) -> None:
        hs.insert_probe_record("n1", success=True)
        hs.insert_probe_record("n2", success=True)
        assert len(hs.get_probe_records("n1")) == 1
        assert len(hs.get_probe_records("n2")) == 1
        assert len(hs.get_probe_records("n3")) == 0

    def test_cleanup_old_records(self, hs: HealthStorage) -> None:
        hs.insert_probe_record("n1", success=True)
        # Set a very small max_age so the record is "old"
        deleted = hs.cleanup_old_probe_records(max_age_hours=0)
        assert deleted >= 1
        assert hs.get_probe_records("n1") == []

    def test_cleanup_keeps_recent(self, hs: HealthStorage) -> None:
        hs.insert_probe_record("n1", success=True)
        deleted = hs.cleanup_old_probe_records(max_age_hours=9999)
        assert deleted == 0
        assert len(hs.get_probe_records("n1")) == 1


# ---- Node Scores ----


class TestNodeScores:
    def test_upsert_and_get(self, hs: HealthStorage) -> None:
        hs.upsert_node_score("n1", final_score=0.9, grade="A", raw_score=0.85, confidence=0.95)
        score = hs.get_node_score("n1")
        assert score is not None
        assert score["final_score"] == 0.9
        assert score["grade"] == "A"
        assert score["confidence"] == 0.95

    def test_get_missing(self, hs: HealthStorage) -> None:
        assert hs.get_node_score("nope") is None

    def test_upsert_updates_existing(self, hs: HealthStorage) -> None:
        hs.upsert_node_score("n1", final_score=0.5, grade="C", raw_score=0.4, confidence=0.6)
        hs.upsert_node_score("n1", final_score=0.95, grade="A+", raw_score=0.9, confidence=0.98)
        score = hs.get_node_score("n1")
        assert score["final_score"] == 0.95
        assert score["grade"] == "A+"

    def test_upsert_with_optional_fields(self, hs: HealthStorage) -> None:
        hs.upsert_node_score(
            "n1", final_score=0.8, grade="B", raw_score=0.7, confidence=0.85,
            success_rate=0.9, avg_latency_ms=120, stability_score=0.75,
        )
        score = hs.get_node_score("n1")
        assert score["success_rate"] == 0.9
        assert score["avg_latency_ms"] == 120
        assert score["stability_score"] == 0.75

    def test_get_all_ordered_by_score(self, hs: HealthStorage) -> None:
        hs.upsert_node_score("low", final_score=0.3, grade="D", raw_score=0.2, confidence=0.5)
        hs.upsert_node_score("high", final_score=0.9, grade="A", raw_score=0.85, confidence=0.95)
        all_scores = hs.get_all_node_scores()
        assert len(all_scores) == 2
        assert all_scores[0]["node_key"] == "high"
        assert all_scores[1]["node_key"] == "low"

    def test_delete(self, hs: HealthStorage) -> None:
        hs.upsert_node_score("n1", final_score=0.5, grade="B", raw_score=0.4, confidence=0.6)
        assert hs.delete_node_score("n1") == 1
        assert hs.get_node_score("n1") is None

    def test_delete_missing(self, hs: HealthStorage) -> None:
        assert hs.delete_node_score("nope") == 0


# ---- Circuit Breaker State ----


class TestCircuitBreakerState:
    def test_upsert_and_get(self, hs: HealthStorage) -> None:
        now = time.time()
        hs.upsert_circuit_breaker(
            "n1", state="open", failure_count=5,
            last_failure_time=now, open_since=now, current_backoff_sec=60.0,
        )
        cb = hs.get_circuit_breaker("n1")
        assert cb is not None
        assert cb["state"] == "open"
        assert cb["failure_count"] == 5
        assert cb["current_backoff_sec"] == 60.0

    def test_get_missing(self, hs: HealthStorage) -> None:
        assert hs.get_circuit_breaker("nope") is None

    def test_upsert_updates_existing(self, hs: HealthStorage) -> None:
        hs.upsert_circuit_breaker("n1", state="open", failure_count=3)
        hs.upsert_circuit_breaker("n1", state="closed", failure_count=0, consecutive_successes=2)
        cb = hs.get_circuit_breaker("n1")
        assert cb["state"] == "closed"
        assert cb["failure_count"] == 0
        assert cb["consecutive_successes"] == 2

    def test_upsert_with_all_optional_fields(self, hs: HealthStorage) -> None:
        now = time.time()
        hs.upsert_circuit_breaker(
            "n1", state="half-open", failure_count=10,
            consecutive_successes=3, last_failure_time=now - 100,
            last_success_time=now, open_since=now - 200,
            backoff_until=now + 60, current_backoff_sec=120.0,
        )
        cb = hs.get_circuit_breaker("n1")
        assert cb["state"] == "half-open"
        assert cb["open_since"] == now - 200
        assert cb["backoff_until"] == now + 60

    def test_get_all_circuit_breakers(self, hs: HealthStorage) -> None:
        hs.upsert_circuit_breaker("n1", state="closed", failure_count=0)
        hs.upsert_circuit_breaker("n2", state="open", failure_count=3)
        all_cb = hs.get_all_circuit_breakers()
        assert len(all_cb) == 2
        keys = [c["node_key"] for c in all_cb]
        assert keys == sorted(keys)

    def test_delete(self, hs: HealthStorage) -> None:
        hs.upsert_circuit_breaker("n1", state="closed", failure_count=0)
        assert hs.delete_circuit_breaker("n1") == 1
        assert hs.get_circuit_breaker("n1") is None

    def test_delete_missing(self, hs: HealthStorage) -> None:
        assert hs.delete_circuit_breaker("nope") == 0


# ---- Initialization ----


class TestInit:
    def test_creates_tables(self, tmp_path: Path) -> None:
        hs = HealthStorage(db_path=tmp_path / "fresh.db")
        # All operations should work without error
        hs.insert_probe_record("n1", success=True)
        hs.upsert_node_score("n1", 0.9, "A", 0.85, 0.95)
        hs.upsert_circuit_breaker("n1", "closed", 0)
        assert len(hs.get_probe_records("n1")) == 1
        assert hs.get_node_score("n1") is not None
        assert hs.get_circuit_breaker("n1") is not None

    def test_reopen_existing_db(self, tmp_path: Path) -> None:
        db = tmp_path / "persist.db"
        hs1 = HealthStorage(db_path=db)
        hs1.insert_probe_record("n1", success=True)
        hs1.upsert_node_score("n1", 0.9, "A", 0.85, 0.95)
        hs1.upsert_circuit_breaker("n1", "open", 5)

        hs2 = HealthStorage(db_path=db)
        assert len(hs2.get_probe_records("n1")) == 1
        assert hs2.get_node_score("n1")["grade"] == "A"
        assert hs2.get_circuit_breaker("n1")["state"] == "open"
