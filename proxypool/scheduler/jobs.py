from __future__ import annotations

import asyncio
import logging
from typing import Any

from proxypool.collector.service import CollectorService
from proxypool.tester.service import TesterService

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(
        self,
        collector: CollectorService,
        tester: TesterService,
        storage: Any | None = None,
        max_failures_threshold: int = 5,
    ) -> None:
        self.collector = collector
        self.tester = tester
        self.storage = storage
        self.max_failures_threshold = max_failures_threshold
        self._scheduler: Any | None = None

    def _safe_collect(self, sources: list[str]) -> None:
        try:
            self.collector.collect_from_sources(sources)
        except Exception:
            logger.exception("Scheduled collection failed")

    def _safe_test(self, test_limit: int, test_concurrency: int) -> None:
        try:
            asyncio.run(self.tester.run_batch(limit=test_limit, concurrency=test_concurrency))
        except Exception:
            logger.exception("Scheduled test run failed")

    def _safe_cleanup_unavailable(self) -> None:
        """清理连续失败超过阈值的代理"""
        if self.storage is None:
            return
        try:
            count = self.storage.mark_unavailable_by_fail_count(self.max_failures_threshold)
            if count > 0:
                logger.info("Marked %d proxies as unavailable (fail_count >= %d)", count, self.max_failures_threshold)
        except Exception:
            logger.exception("Scheduled cleanup job failed")

    def start(
        self,
        sources: list[str],
        collect_minutes: int = 60,
        test_minutes: int = 10,
        test_limit: int = 300,
        test_concurrency: int = 80,
        cleanup_minutes: int = 30,
    ) -> None:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("APScheduler is required for SchedulerService") from exc

        scheduler = BackgroundScheduler(timezone="UTC")

        scheduler.add_job(
            func=lambda: self._safe_collect(sources),
            trigger="interval",
            minutes=max(1, collect_minutes),
            id="collector-job",
            replace_existing=True,
        )

        scheduler.add_job(
            func=lambda: self._safe_test(test_limit, test_concurrency),
            trigger="interval",
            minutes=max(1, test_minutes),
            id="tester-job",
            replace_existing=True,
        )

        # 添加失败代理清理任务
        if self.storage is not None:
            scheduler.add_job(
                func=self._safe_cleanup_unavailable,
                trigger="interval",
                minutes=max(1, cleanup_minutes),
                id="cleanup-job",
                replace_existing=True,
            )

        scheduler.start()
        self._scheduler = scheduler

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
