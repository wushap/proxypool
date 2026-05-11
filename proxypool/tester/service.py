from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.tasks.manager import TaskCancelled
from proxypool.tester.singbox import ProbeResult, SingboxProber


@dataclass(slots=True)
class BatchTestReport:
    requested: int
    tested: int = 0
    available: int = 0
    unavailable: int = 0
    avg_latency_ms: int | None = None
    stale_deleted: int = 0


@dataclass(slots=True)
class BatchOpenAIReport:
    requested: int
    checked: int = 0
    unlocked: int = 0
    blocked: int = 0
    unknown: int = 0


class TesterService:
    def __init__(
        self,
        storage: SQLiteProxyStorage,
        prober: SingboxProber | None = None,
        replace_failed_proxy_cb: Callable[[str, str], None] | None = None,
    ) -> None:
        self.storage = storage
        self.prober = prober or SingboxProber()
        self.replace_failed_proxy_cb = replace_failed_proxy_cb

    async def run_one(
        self,
        normalized_key: str,
        fallback_front_proxy_keys: list[str] | None = None,
        fallback_front_max_attempts: int = 0,
    ) -> ProbeResult:
        key = str(normalized_key or "").strip()
        if not key:
            raise ValueError("normalized_key is empty")
        node = self.storage.get_proxy_by_key(key)
        if not node:
            raise LookupError("proxy not found")

        fallback_nodes: list[dict] = []
        fallback_limit = max(0, int(fallback_front_max_attempts or 0))
        if fallback_limit > 0:
            fallback_nodes = self.storage.get_proxies_by_keys(_clean_proxy_keys(fallback_front_proxy_keys))[:fallback_limit]

        result, fallback_success_keys = await self._probe_node_once(node=node, fallback_nodes=fallback_nodes)
        self.storage.update_test_result(
            normalized_key=result.normalized_key,
            available=result.available,
            latency_ms=result.latency_ms,
            openai_unlocked=result.openai_unlocked,
            openai_status=result.openai_status,
            fallback_front_keys=fallback_success_keys,
            error=result.error,
        )
        return result

    async def run_batch(
        self,
        limit: int = 0,
        concurrency: int = 50,
        only_unchecked: bool = False,
        only_available: bool = False,
        only_unavailable: bool = False,
        min_last_checked_age_hours: int = 0,
        protocols: list[str] | None = None,
        fallback_front_proxy_keys: list[str] | None = None,
        fallback_front_max_attempts: int = 0,
        max_fail_count: int = 20,
        replace_failed_with_available: bool = False,
        progress_cb: Callable[[dict], None] | None = None,
        stop_cb: Callable[[], bool] | None = None,
    ) -> BatchTestReport:
        if stop_cb and stop_cb():
            raise TaskCancelled("cancel requested")
        candidates = self.storage.get_candidates_for_test(
            limit=limit,
            only_unchecked=only_unchecked,
            only_available=only_available,
            only_unavailable=only_unavailable,
            min_last_checked_age_hours=min_last_checked_age_hours,
            protocols=protocols,
        )
        report = BatchTestReport(requested=len(candidates))
        if progress_cb:
            progress_cb(
                {
                    "total": report.requested,
                    "completed": 0,
                    "available": 0,
                    "unavailable": 0,
                    "phase": "prepare",
                }
            )

        if not candidates:
            return report

        concurrency = max(1, int(concurrency or 1))
        latency_values: list[int] = []
        async_probe = getattr(self.prober, "probe_async", None)
        async_chain_probe = getattr(self.prober, "probe_with_front_proxy_async", None)
        fallback_nodes: list[dict] = []
        fallback_limit = max(0, int(fallback_front_max_attempts or 0))
        if fallback_limit > 0:
            fallback_nodes = self.storage.get_proxies_by_keys(_clean_proxy_keys(fallback_front_proxy_keys))[:fallback_limit]

        def _handle_result(result: ProbeResult, fallback_success_keys: list[str]) -> None:
            report.tested += 1
            if result.available:
                report.available += 1
                if result.latency_ms is not None:
                    latency_values.append(result.latency_ms)
            else:
                report.unavailable += 1

            self.storage.update_test_result(
                normalized_key=result.normalized_key,
                available=result.available,
                latency_ms=result.latency_ms,
                openai_unlocked=result.openai_unlocked,
                openai_status=result.openai_status,
                fallback_front_keys=fallback_success_keys,
                error=result.error,
            )
            if replace_failed_with_available and not result.available:
                self._replace_failed_proxy_config(result.normalized_key)
            if progress_cb:
                progress_cb(
                    {
                        "total": report.requested,
                        "completed": report.tested,
                        "available": report.available,
                        "unavailable": report.unavailable,
                        "phase": "testing",
                    }
                )

        if callable(async_probe):
            sem = asyncio.Semaphore(concurrency)

            async def _probe_one(node: dict) -> tuple[ProbeResult, list[str]]:
                async with sem:
                    try:
                        result = await async_probe(node)
                        fallback_success_keys: list[str] = []
                        if (
                            not result.available
                            and fallback_nodes
                            and callable(async_chain_probe)
                        ):
                            chain_results: list[ProbeResult] = []
                            for front in fallback_nodes:
                                front_key = str(front.get("normalized_key") or "")
                                node_key = str(node.get("normalized_key") or "")
                                if not front_key or front_key == node_key:
                                    continue
                                chain_result = await async_chain_probe(node, front)
                                if chain_result.available:
                                    fallback_success_keys.append(front_key)
                                    chain_results.append(chain_result)
                            if chain_results:
                                result = _select_preferred_success(chain_results)
                        return result, fallback_success_keys
                    except Exception as exc:  # pragma: no cover - runtime guard
                        return (
                            ProbeResult(
                                normalized_key=str(node.get("normalized_key") or ""),
                                available=False,
                                error=f"probe exception: {exc}",
                            ),
                            [],
                        )

            probe_tasks = [asyncio.create_task(_probe_one(node)) for node in candidates]
            for fut in asyncio.as_completed(probe_tasks):
                if stop_cb and stop_cb():
                    for task in probe_tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*probe_tasks, return_exceptions=True)
                    raise TaskCancelled("cancel requested")
                result, fallback_success_keys = await fut
                _handle_result(result, fallback_success_keys)
        else:
            # Fallback for non-async prober implementations.
            for node in candidates:
                if stop_cb and stop_cb():
                    raise TaskCancelled("cancel requested")
                try:
                    result = self.prober.probe(node)
                except Exception as exc:  # pragma: no cover - runtime guard
                    result = ProbeResult(
                        normalized_key=str(node.get("normalized_key") or ""),
                        available=False,
                        error=f"probe exception: {exc}",
                    )
                _handle_result(result, [])

        if latency_values:
            report.avg_latency_ms = int(sum(latency_values) / len(latency_values))

        report.stale_deleted = self.storage.delete_stale_unavailable(max_fail_count=max_fail_count)
        if progress_cb:
            progress_cb(
                {
                    "total": report.requested,
                    "completed": report.tested,
                    "available": report.available,
                    "unavailable": report.unavailable,
                    "phase": "done",
                }
            )
        return report

    def _replace_failed_proxy_config(self, old_key: str) -> None:
        if not self.replace_failed_proxy_cb:
            return
        old = str(old_key or "").strip()
        if not old:
            return
        candidates = self.storage.list_proxies_filtered(limit=20, available=True, sort_by="latency", sort_order="asc")
        for candidate in candidates:
            new_key = str(candidate.get("normalized_key") or "").strip()
            if new_key and new_key != old:
                self.replace_failed_proxy_cb(old, new_key)
                return

    async def _probe_node_once(self, node: dict, fallback_nodes: list[dict] | None = None) -> tuple[ProbeResult, list[str]]:
        async_probe = getattr(self.prober, "probe_async", None)
        async_chain_probe = getattr(self.prober, "probe_with_front_proxy_async", None)
        fallback_success_keys: list[str] = []
        try:
            if callable(async_probe):
                result = await async_probe(node)
                if (
                    not result.available
                    and fallback_nodes
                    and callable(async_chain_probe)
                ):
                    chain_results: list[ProbeResult] = []
                    for front in fallback_nodes:
                        front_key = str(front.get("normalized_key") or "")
                        node_key = str(node.get("normalized_key") or "")
                        if not front_key or front_key == node_key:
                            continue
                        chain_result = await async_chain_probe(node, front)
                        if chain_result.available:
                            fallback_success_keys.append(front_key)
                            chain_results.append(chain_result)
                    if chain_results:
                        result = _select_preferred_success(chain_results)
            else:
                result = self.prober.probe(node)
        except Exception as exc:  # pragma: no cover - runtime guard
            result = ProbeResult(
                normalized_key=str(node.get("normalized_key") or ""),
                available=False,
                error=f"probe exception: {exc}",
            )
        return result, fallback_success_keys

    async def run_openai_check_batch(
        self,
        limit: int = 200,
        concurrency: int = 30,
        only_available: bool = True,
        protocols: list[str] | None = None,
        progress_cb: Callable[[dict], None] | None = None,
        stop_cb: Callable[[], bool] | None = None,
    ) -> BatchOpenAIReport:
        if stop_cb and stop_cb():
            raise TaskCancelled("cancel requested")
        candidates = self.storage.get_candidates_for_test(
            limit=limit,
            only_unchecked=False,
            only_available=True,
            protocols=protocols,
        )
        report = BatchOpenAIReport(requested=len(candidates))
        if progress_cb:
            progress_cb(
                {
                    "total": report.requested,
                    "completed": 0,
                    "available": 0,
                    "unavailable": 0,
                    "phase": "prepare",
                }
            )
        if not candidates:
            return report

        concurrency = max(1, int(concurrency or 1))
        async_probe = getattr(self.prober, "probe_async", None)
        async_chain_probe = getattr(self.prober, "probe_with_front_proxy_async", None)

        def _handle_result(result: ProbeResult) -> None:
            report.checked += 1
            if result.openai_unlocked is True:
                report.unlocked += 1
            elif result.openai_unlocked is False:
                report.blocked += 1
            else:
                report.unknown += 1
            self.storage.update_openai_result(
                normalized_key=result.normalized_key,
                openai_unlocked=result.openai_unlocked,
                openai_status=result.openai_status or result.error,
            )
            if progress_cb:
                progress_cb(
                    {
                        "total": report.requested,
                        "completed": report.checked,
                        "available": report.unlocked,
                        "unavailable": report.blocked + report.unknown,
                        "phase": "checking",
                    }
                )

        if callable(async_probe):
            sem = asyncio.Semaphore(concurrency)

            async def _probe_one(node: dict) -> ProbeResult:
                async with sem:
                    try:
                        result = await async_probe(node)
                        if result.openai_unlocked is not None:
                            return result
                        if callable(async_chain_probe):
                            raw_fallback_keys = node.get("fallback_front_keys")
                            fallback_keys = _clean_proxy_keys(raw_fallback_keys if isinstance(raw_fallback_keys, list) else [])
                            if fallback_keys:
                                front_nodes = self.storage.get_proxies_by_keys(fallback_keys)
                                chain_results: list[ProbeResult] = []
                                for front in front_nodes:
                                    front_key = str(front.get("normalized_key") or "")
                                    node_key = str(node.get("normalized_key") or "")
                                    if not front_key or front_key == node_key:
                                        continue
                                    chain_result = await async_chain_probe(node, front)
                                    if chain_result.openai_unlocked is not None or chain_result.available:
                                        chain_results.append(chain_result)
                                if chain_results:
                                    return _select_openai_result(chain_results)
                        return result
                    except Exception as exc:  # pragma: no cover - runtime guard
                        return ProbeResult(
                            normalized_key=str(node.get("normalized_key") or ""),
                            available=False,
                            openai_unlocked=None,
                            openai_status="",
                            error=f"probe exception: {exc}",
                        )

            tasks = [asyncio.create_task(_probe_one(node)) for node in candidates]
            for fut in asyncio.as_completed(tasks):
                if stop_cb and stop_cb():
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    raise TaskCancelled("cancel requested")
                _handle_result(await fut)
        else:
            for node in candidates:
                if stop_cb and stop_cb():
                    raise TaskCancelled("cancel requested")
                try:
                    result = self.prober.probe(node)
                except Exception as exc:  # pragma: no cover - runtime guard
                    result = ProbeResult(
                        normalized_key=str(node.get("normalized_key") or ""),
                        available=False,
                        openai_unlocked=None,
                        openai_status="",
                        error=f"probe exception: {exc}",
                    )
                _handle_result(result)

        if progress_cb:
            progress_cb(
                {
                    "total": report.requested,
                    "completed": report.checked,
                    "available": report.unlocked,
                    "unavailable": report.blocked + report.unknown,
                    "phase": "done",
                }
            )
        return report


def _clean_proxy_keys(keys: list[str] | None) -> list[str]:
    if not keys:
        return []
    uniq: list[str] = []
    seen: set[str] = set()
    for item in keys:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(key)
    return uniq


def _select_preferred_success(results: list[ProbeResult]) -> ProbeResult:
    if not results:
        return ProbeResult(normalized_key="", available=False, error="no result")
    best: ProbeResult | None = None
    for item in results:
        if best is None:
            best = item
            continue
        if best.latency_ms is None and item.latency_ms is not None:
            best = item
            continue
        if (
            best.latency_ms is not None
            and item.latency_ms is not None
            and item.latency_ms < best.latency_ms
        ):
            best = item
    return best or results[0]


def _select_openai_result(results: list[ProbeResult]) -> ProbeResult:
    if not results:
        return ProbeResult(normalized_key="", available=False, openai_unlocked=None, openai_status="no result")
    for item in results:
        if item.openai_unlocked is not None:
            return item
    return _select_preferred_success(results)
