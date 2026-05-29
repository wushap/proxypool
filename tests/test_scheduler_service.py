from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock

import pytest

from proxypool.scheduler.jobs import SchedulerService


class FakeCollector:
    """Minimal CollectorService stub."""

    def __init__(self) -> None:
        self.collect_calls: list[list[str]] = []

    def collect_from_sources(self, sources: list[str]) -> None:
        self.collect_calls.append(sources)


class FakeTester:
    """Minimal TesterService stub."""

    def __init__(self) -> None:
        self.batch_calls: list[dict] = []

    async def run_batch(self, limit: int = 300, concurrency: int = 80) -> None:
        self.batch_calls.append({"limit": limit, "concurrency": concurrency})


class FakeStorage:
    """Minimal storage stub with mark_unavailable_by_fail_count."""

    def __init__(self) -> None:
        self.cleanup_calls: list[int] = []
        self._mark_count = 0

    def mark_unavailable_by_fail_count(self, threshold: int) -> int:
        self.cleanup_calls.append(threshold)
        return self._mark_count


# --- Initialization ---


def test_init_stores_dependencies() -> None:
    collector = FakeCollector()
    tester = FakeTester()
    svc = SchedulerService(collector=collector, tester=tester)  # type: ignore[arg-type]
    assert svc.collector is collector
    assert svc.tester is tester
    assert svc.storage is None
    assert svc.max_failures_threshold == 5
    assert svc._scheduler is None


def test_init_with_storage_and_custom_threshold() -> None:
    storage = FakeStorage()
    svc = SchedulerService(
        collector=FakeCollector(),  # type: ignore[arg-type]
        tester=FakeTester(),  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
        max_failures_threshold=10,
    )
    assert svc.storage is storage
    assert svc.max_failures_threshold == 10


# --- start / stop ---


def test_start_creates_scheduler_with_jobs() -> None:
    collector = FakeCollector()
    tester = FakeTester()
    storage = FakeStorage()
    svc = SchedulerService(
        collector=collector,  # type: ignore[arg-type]
        tester=tester,  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
    )
    svc.start(sources=["http://example.com/proxies.txt"], collect_minutes=60, test_minutes=10)

    assert svc._scheduler is not None
    jobs = svc._scheduler.get_jobs()
    job_ids = {j.id for j in jobs}
    assert "collector-job" in job_ids
    assert "tester-job" in job_ids
    assert "cleanup-job" in job_ids

    svc.stop()
    assert svc._scheduler is None


def test_start_without_storage_no_cleanup_job() -> None:
    svc = SchedulerService(
        collector=FakeCollector(),  # type: ignore[arg-type]
        tester=FakeTester(),  # type: ignore[arg-type]
    )
    svc.start(sources=["http://example.com"])

    jobs = svc._scheduler.get_jobs()
    job_ids = {j.id for j in jobs}
    assert "collector-job" in job_ids
    assert "tester-job" in job_ids
    assert "cleanup-job" not in job_ids

    svc.stop()


def test_stop_without_start_is_noop() -> None:
    svc = SchedulerService(
        collector=FakeCollector(),  # type: ignore[arg-type]
        tester=FakeTester(),  # type: ignore[arg-type]
    )
    # should not raise
    svc.stop()
    assert svc._scheduler is None


# --- Job interval clamping ---


def test_start_clamps_intervals_to_minimum_1() -> None:
    svc = SchedulerService(
        collector=FakeCollector(),  # type: ignore[arg-type]
        tester=FakeTester(),  # type: ignore[arg-type]
    )
    # Pass intervals below 1; they should be clamped to 1
    svc.start(
        sources=["http://example.com"],
        collect_minutes=0,
        test_minutes=-5,
        cleanup_minutes=0,
    )

    jobs = svc._scheduler.get_jobs()
    for job in jobs:
        trigger = job.trigger
        # interval trigger has interval >= 60 seconds (1 minute)
        assert trigger.interval.total_seconds() >= 60

    svc.stop()


# --- _safe_collect ---


def test_safe_collect_calls_collector() -> None:
    collector = FakeCollector()
    svc = SchedulerService(collector=collector, tester=FakeTester())  # type: ignore[arg-type]
    svc._safe_collect(["a", "b"])
    assert collector.collect_calls == [["a", "b"]]


def test_safe_collect_swallows_exceptions(caplog: pytest.LogCaptureFixture) -> None:
    collector = FakeCollector()
    collector.collect_from_sources = MagicMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]
    svc = SchedulerService(collector=collector, tester=FakeTester())  # type: ignore[arg-type]
    with caplog.at_level(logging.ERROR, logger="proxypool.scheduler.jobs"):
        svc._safe_collect(["x"])
    assert "Scheduled collection failed" in caplog.text


# --- _safe_test ---


def test_safe_test_calls_tester() -> None:
    tester = FakeTester()
    svc = SchedulerService(collector=FakeCollector(), tester=tester)  # type: ignore[arg-type]
    svc._safe_test(test_limit=50, test_concurrency=10)
    assert tester.batch_calls == [{"limit": 50, "concurrency": 10}]


def test_safe_test_swallows_exceptions(caplog: pytest.LogCaptureFixture) -> None:
    tester = FakeTester()
    tester.run_batch = MagicMock(side_effect=RuntimeError("fail"))  # type: ignore[method-assign]
    svc = SchedulerService(collector=FakeCollector(), tester=tester)  # type: ignore[arg-type]
    with caplog.at_level(logging.ERROR, logger="proxypool.scheduler.jobs"):
        svc._safe_test(test_limit=10, test_concurrency=5)
    assert "Scheduled test run failed" in caplog.text


# --- _safe_cleanup_unavailable ---


def test_cleanup_unavailable_calls_storage() -> None:
    storage = FakeStorage()
    storage._mark_count = 3
    svc = SchedulerService(
        collector=FakeCollector(),  # type: ignore[arg-type]
        tester=FakeTester(),  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
        max_failures_threshold=5,
    )
    svc._safe_cleanup_unavailable()
    assert storage.cleanup_calls == [5]


def test_cleanup_unavailable_noop_without_storage(caplog: pytest.LogCaptureFixture) -> None:
    svc = SchedulerService(
        collector=FakeCollector(),  # type: ignore[arg-type]
        tester=FakeTester(),  # type: ignore[arg-type]
    )
    with caplog.at_level(logging.ERROR, logger="proxypool.scheduler.jobs"):
        svc._safe_cleanup_unavailable()
    # No error logged - just returns early
    assert "cleanup" not in caplog.text.lower()


def test_cleanup_unavailable_no_proxies_marked(caplog: pytest.LogCaptureFixture) -> None:
    """When mark_unavailable_by_fail_count returns 0, no info log is emitted."""
    storage = FakeStorage()
    storage._mark_count = 0
    svc = SchedulerService(
        collector=FakeCollector(),  # type: ignore[arg-type]
        tester=FakeTester(),  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
        max_failures_threshold=5,
    )
    with caplog.at_level(logging.INFO, logger="proxypool.scheduler.jobs"):
        svc._safe_cleanup_unavailable()
    assert "Marked" not in caplog.text


def test_cleanup_unavailable_swallows_exceptions(caplog: pytest.LogCaptureFixture) -> None:
    storage = FakeStorage()
    storage.mark_unavailable_by_fail_count = MagicMock(side_effect=RuntimeError("db error"))  # type: ignore[method-assign]
    svc = SchedulerService(
        collector=FakeCollector(),  # type: ignore[arg-type]
        tester=FakeTester(),  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
    )
    with caplog.at_level(logging.ERROR, logger="proxypool.scheduler.jobs"):
        svc._safe_cleanup_unavailable()
    assert "Scheduled cleanup job failed" in caplog.text
