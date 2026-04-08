from __future__ import annotations

import asyncio
from typing import Any

from proxypool.collector.service import CollectorService
from proxypool.tester.service import TesterService


class SchedulerService:
    def __init__(self, collector: CollectorService, tester: TesterService) -> None:
        self.collector = collector
        self.tester = tester
        self._scheduler: Any | None = None

    def start(
        self,
        sources: list[str],
        collect_minutes: int = 60,
        test_minutes: int = 10,
        test_limit: int = 300,
        test_concurrency: int = 80,
    ) -> None:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("APScheduler is required for SchedulerService") from exc

        scheduler = BackgroundScheduler(timezone="UTC")

        scheduler.add_job(
            func=lambda: self.collector.collect_from_sources(sources),
            trigger="interval",
            minutes=max(1, collect_minutes),
            id="collector-job",
            replace_existing=True,
        )

        scheduler.add_job(
            func=lambda: asyncio.run(
                self.tester.run_batch(limit=test_limit, concurrency=test_concurrency)
            ),
            trigger="interval",
            minutes=max(1, test_minutes),
            id="tester-job",
            replace_existing=True,
        )

        scheduler.start()
        self._scheduler = scheduler

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
