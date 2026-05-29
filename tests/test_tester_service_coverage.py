"""Tests for proxypool.tester.service – targeting uncovered lines."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.tasks.manager import TaskCancelled
from proxypool.tester.service import (
    BatchOpenAIReport,
    BatchTestReport,
    TesterService,
    _clean_proxy_keys,
    _select_openai_result,
    _select_preferred_success,
)
from proxypool.tester.singbox import ProbeResult


# ---------------------------------------------------------------------------
# Fake / stub probers
# ---------------------------------------------------------------------------

class _SyncProber:
    """Sync prober without probe_async – forces the sync fallback path."""

    def probe(self, node: dict) -> ProbeResult:
        key = str(node.get("normalized_key") or "")
        host = str(node.get("host") or "")
        if host.startswith("up"):
            return ProbeResult(normalized_key=key, available=True, latency_ms=55)
        return ProbeResult(normalized_key=key, available=False, error="sync-down")


class _AsyncProber:
    """Standard async prober for run_one tests."""

    async def probe_async(self, node: dict) -> ProbeResult:
        key = str(node.get("normalized_key") or "")
        return ProbeResult(normalized_key=key, available=True, latency_ms=12)

    async def probe_with_front_proxy_async(
        self, node: dict, front_proxy: dict
    ) -> ProbeResult:
        node_key = str(node.get("normalized_key") or "")
        return ProbeResult(
            normalized_key=node_key, available=True, latency_ms=44
        )


class _AsyncUnavailableProber:
    """Async prober that always reports unavailable, triggering fallback chain."""

    async def probe_async(self, node: dict) -> ProbeResult:
        key = str(node.get("normalized_key") or "")
        return ProbeResult(normalized_key=key, available=False, error="unavail")

    async def probe_with_front_proxy_async(
        self, node: dict, front_proxy: dict
    ) -> ProbeResult:
        node_key = str(node.get("normalized_key") or "")
        front_key = str(front_proxy.get("normalized_key") or "")
        # Front starting with "good" makes chain succeed
        if str(front_proxy.get("host") or "").startswith("good"):
            return ProbeResult(
                normalized_key=node_key, available=True, latency_ms=77
            )
        return ProbeResult(normalized_key=node_key, available=False, error="chain-fail")


class _OpenAIUnlockedProber:
    async def probe_async(self, node: dict) -> ProbeResult:
        key = str(node.get("normalized_key") or "")
        return ProbeResult(
            normalized_key=key,
            available=True,
            latency_ms=20,
            openai_unlocked=True,
            openai_status="401 unauthorized",
        )


class _OpenAINoneProber:
    """Returns openai_unlocked=None to exercise fallback chain in openai check."""

    async def probe_async(self, node: dict) -> ProbeResult:
        key = str(node.get("normalized_key") or "")
        return ProbeResult(
            normalized_key=key,
            available=True,
            openai_unlocked=None,
            openai_status="",
        )

    async def probe_with_front_proxy_async(
        self, node: dict, front_proxy: dict
    ) -> ProbeResult:
        node_key = str(node.get("normalized_key") or "")
        front_key = str(front_proxy.get("normalized_key") or "")
        if str(front_proxy.get("host") or "").startswith("good"):
            return ProbeResult(
                normalized_key=node_key,
                available=True,
                openai_unlocked=True,
                openai_status="401 unauthorized",
            )
        return ProbeResult(
            normalized_key=node_key,
            available=False,
            openai_unlocked=None,
            openai_status="",
        )


class _OpenAISyncProber:
    """Sync prober for openai check batch sync fallback path."""

    def probe(self, node: dict) -> ProbeResult:
        key = str(node.get("normalized_key") or "")
        return ProbeResult(
            normalized_key=key,
            available=True,
            openai_unlocked=False,
            openai_status="403 blocked",
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_storage(td: str) -> SQLiteProxyStorage:
    return SQLiteProxyStorage(Path(td) / "db.sqlite3")


def _add_proxy(storage: SQLiteProxyStorage, host: str) -> ProxyNode:
    node = ProxyNode(
        protocol="trojan",
        host=host,
        port=443,
        raw_link=f"trojan://{host}",
        extra={"password": "p"},
    )
    storage.upsert_proxy(node)
    return node


# ===================================================================
# Tests for _clean_proxy_keys
# ===================================================================

class TestCleanProxyKeys(unittest.TestCase):
    def test_none_returns_empty(self) -> None:
        self.assertEqual(_clean_proxy_keys(None), [])

    def test_empty_list(self) -> None:
        self.assertEqual(_clean_proxy_keys([]), [])

    def test_deduplicates_and_strips(self) -> None:
        result = _clean_proxy_keys(["  a  ", "b", "a", None, "", "  b  "])
        self.assertEqual(result, ["a", "b"])

    def test_all_whitespace_returns_empty(self) -> None:
        self.assertEqual(_clean_proxy_keys(["  ", " "]), [])


# ===================================================================
# Tests for _select_preferred_success
# ===================================================================

class TestSelectPreferredSuccess(unittest.TestCase):
    def test_empty_returns_no_result(self) -> None:
        r = _select_preferred_success([])
        self.assertFalse(r.available)
        self.assertEqual(r.error, "no result")

    def test_single_result_returned(self) -> None:
        item = ProbeResult(normalized_key="k1", available=True, latency_ms=50)
        self.assertIs(_select_preferred_success([item]), item)

    def test_picks_lowest_latency(self) -> None:
        slow = ProbeResult(normalized_key="slow", available=True, latency_ms=200)
        fast = ProbeResult(normalized_key="fast", available=True, latency_ms=30)
        best = _select_preferred_success([slow, fast])
        self.assertEqual(best.normalized_key, "fast")

    def test_prefers_result_with_latency_over_none(self) -> None:
        no_lat = ProbeResult(normalized_key="nl", available=True, latency_ms=None)
        has_lat = ProbeResult(normalized_key="hl", available=True, latency_ms=100)
        best = _select_preferred_success([no_lat, has_lat])
        self.assertEqual(best.normalized_key, "hl")

    def test_all_none_latency_returns_first(self) -> None:
        a = ProbeResult(normalized_key="a", available=True, latency_ms=None)
        b = ProbeResult(normalized_key="b", available=True, latency_ms=None)
        best = _select_preferred_success([a, b])
        self.assertEqual(best.normalized_key, "a")


# ===================================================================
# Tests for _select_openai_result
# ===================================================================

class TestSelectOpenaiResult(unittest.TestCase):
    def test_empty_returns_no_result(self) -> None:
        r = _select_openai_result([])
        self.assertFalse(r.available)
        self.assertEqual(r.openai_status, "no result")

    def test_prefers_openai_unlocked_not_none(self) -> None:
        none = ProbeResult(
            normalized_key="n", available=True, openai_unlocked=None
        )
        yes = ProbeResult(
            normalized_key="y", available=True, openai_unlocked=True,
            openai_status="ok",
        )
        best = _select_openai_result([none, yes])
        self.assertEqual(best.normalized_key, "y")

    def test_falls_back_to_preferred_when_all_none(self) -> None:
        a = ProbeResult(
            normalized_key="a", available=True, latency_ms=100, openai_unlocked=None
        )
        b = ProbeResult(
            normalized_key="b", available=True, latency_ms=20, openai_unlocked=None
        )
        best = _select_openai_result([a, b])
        self.assertEqual(best.normalized_key, "b")


# ===================================================================
# Tests for BatchTestReport / BatchOpenAIReport dataclasses
# ===================================================================

class TestReportDataclasses(unittest.TestCase):
    def test_batch_test_report_defaults(self) -> None:
        r = BatchTestReport(requested=10)
        self.assertEqual(r.requested, 10)
        self.assertEqual(r.tested, 0)
        self.assertEqual(r.available, 0)
        self.assertEqual(r.unavailable, 0)
        self.assertIsNone(r.avg_latency_ms)
        self.assertEqual(r.stale_deleted, 0)

    def test_batch_openai_report_defaults(self) -> None:
        r = BatchOpenAIReport(requested=5)
        self.assertEqual(r.requested, 5)
        self.assertEqual(r.checked, 0)
        self.assertEqual(r.unlocked, 0)
        self.assertEqual(r.blocked, 0)
        self.assertEqual(r.unknown, 0)


# ===================================================================
# Tests for TesterService.__init__
# ===================================================================

class TestServiceInit(unittest.TestCase):
    def test_init_creates_default_prober(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            svc = TesterService(storage)
            self.assertIsNotNone(svc.prober)
            self.assertIsNone(svc.replace_failed_proxy_cb)
            self.assertIs(svc.storage, storage)

    def test_init_with_custom_prober_and_callback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            cb = lambda old, new: None
            svc = TesterService(storage, prober=_SyncProber(), replace_failed_proxy_cb=cb)
            self.assertIsInstance(svc.prober, _SyncProber)
            self.assertIs(svc.replace_failed_proxy_cb, cb)


# ===================================================================
# Tests for run_one
# ===================================================================

class TestRunOne(unittest.TestCase):
    def test_run_one_empty_key_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            svc = TesterService(storage, prober=_AsyncProber())
            with self.assertRaises(ValueError):
                asyncio.run(svc.run_one(""))

    def test_run_one_whitespace_key_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            svc = TesterService(storage, prober=_AsyncProber())
            with self.assertRaises(ValueError):
                asyncio.run(svc.run_one("   "))

    def test_run_one_missing_proxy_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            svc = TesterService(storage, prober=_AsyncProber())
            with self.assertRaises(LookupError):
                asyncio.run(svc.run_one("nonexistent-key"))

    def test_run_one_success_updates_storage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            node = _add_proxy(storage, "up.example.com")
            svc = TesterService(storage, prober=_AsyncProber())
            result = asyncio.run(svc.run_one(node.normalized_key()))
            self.assertTrue(result.available)
            self.assertEqual(result.latency_ms, 12)
            row = storage.get_proxy_by_key(node.normalized_key())
            self.assertIsNotNone(row)
            assert row is not None
            self.assertTrue(bool(row["available"]))

    def test_run_one_with_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            target = _add_proxy(storage, "down.example.com")
            front = _add_proxy(storage, "good-front.example.com")
            svc = TesterService(storage, prober=_AsyncUnavailableProber())
            result = asyncio.run(
                svc.run_one(
                    target.normalized_key(),
                    fallback_front_proxy_keys=[front.normalized_key()],
                    fallback_front_max_attempts=1,
                )
            )
            self.assertTrue(result.available)
            self.assertEqual(result.latency_ms, 77)


# ===================================================================
# Tests for run_batch – sync prober path (no probe_async)
# ===================================================================

class TestRunBatchSyncPath(unittest.TestCase):
    def test_sync_prober_batch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            up = _add_proxy(storage, "up-a.example.com")
            down = _add_proxy(storage, "down-b.example.com")
            svc = TesterService(storage, prober=_SyncProber())
            report = asyncio.run(svc.run_batch(limit=10))
            self.assertEqual(report.requested, 2)
            self.assertEqual(report.tested, 2)
            self.assertEqual(report.available, 1)
            self.assertEqual(report.unavailable, 1)

    def test_sync_prober_with_stop_cb_triggers_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            _add_proxy(storage, "up.example.com")
            svc = TesterService(storage, prober=_SyncProber())
            call_count = 0

            def stop_cb() -> bool:
                nonlocal call_count
                call_count += 1
                # Return True on second call (first is at start of run_batch)
                return call_count >= 2

            with self.assertRaises(TaskCancelled):
                asyncio.run(svc.run_batch(limit=10, stop_cb=stop_cb))

    def test_stop_cb_at_start_raises_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            _add_proxy(storage, "up.example.com")
            svc = TesterService(storage, prober=_SyncProber())
            with self.assertRaises(TaskCancelled):
                asyncio.run(svc.run_batch(limit=10, stop_cb=lambda: True))


# ===================================================================
# Tests for run_batch – latency tracking and stale deletion
# ===================================================================

class TestRunBatchLatencyAndStale(unittest.TestCase):
    def test_avg_latency_calculated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            _add_proxy(storage, "up-a.example.com")
            _add_proxy(storage, "up-b.example.com")
            svc = TesterService(storage, prober=_SyncProber())
            report = asyncio.run(svc.run_batch(limit=10))
            # Both up proxies report latency 55
            self.assertIsNotNone(report.avg_latency_ms)
            self.assertEqual(report.avg_latency_ms, 55)

    def test_stale_deleted_counted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            node = _add_proxy(storage, "down-stale.example.com")
            # Mark it unavailable with high fail count so stale deletion picks it up
            storage.update_test_result(
                node.normalized_key(),
                available=False,
                latency_ms=None,
                error="down",
            )
            svc = TesterService(storage, prober=_SyncProber())
            report = asyncio.run(
                svc.run_batch(limit=10, max_fail_count=0)
            )
            self.assertGreaterEqual(report.stale_deleted, 1)


# ===================================================================
# Tests for run_batch – empty candidates
# ===================================================================

class TestRunBatchEmpty(unittest.TestCase):
    def test_empty_candidates_returns_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            svc = TesterService(storage, prober=_SyncProber())
            report = asyncio.run(svc.run_batch(limit=10))
            self.assertEqual(report.requested, 0)
            self.assertEqual(report.tested, 0)

    def test_empty_candidates_with_progress_cb(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            svc = TesterService(storage, prober=_SyncProber())
            events: list[dict] = []
            report = asyncio.run(
                svc.run_batch(limit=10, progress_cb=lambda e: events.append(dict(e)))
            )
            self.assertEqual(report.requested, 0)
            # Should have at least a "prepare" event
            self.assertTrue(any(e.get("phase") == "prepare" for e in events))


# ===================================================================
# Tests for run_batch – replace_failed_with_available
# ===================================================================

class TestRunBatchReplaceFailed(unittest.TestCase):
    def test_replace_failed_calls_callback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            down = _add_proxy(storage, "down-x.example.com")
            up = _add_proxy(storage, "up-y.example.com")
            storage.update_test_result(up.normalized_key(), available=True, latency_ms=10)
            replacements: list[tuple[str, str]] = []
            svc = TesterService(
                storage,
                prober=_SyncProber(),
                replace_failed_proxy_cb=lambda o, n: replacements.append((o, n)),
            )
            report = asyncio.run(
                svc.run_batch(limit=10, replace_failed_with_available=True)
            )
            self.assertEqual(report.unavailable, 1)
            self.assertEqual(len(replacements), 1)
            self.assertEqual(replacements[0][0], down.normalized_key())
            self.assertEqual(replacements[0][1], up.normalized_key())

    def test_replace_failed_no_callback(self) -> None:
        """When no replace callback is set, _replace_failed_proxy_config is a no-op."""
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            _add_proxy(storage, "down-x.example.com")
            svc = TesterService(storage, prober=_SyncProber())
            # Should not raise
            report = asyncio.run(
                svc.run_batch(limit=10, replace_failed_with_available=True)
            )
            self.assertEqual(report.unavailable, 1)

    def test_replace_failed_empty_key_skipped(self) -> None:
        """_replace_failed_proxy_config returns early if old_key is empty."""
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            svc = TesterService(
                storage,
                prober=_SyncProber(),
                replace_failed_proxy_cb=lambda o, n: (_ for _ in ()).throw(
                    AssertionError("should not be called")
                ),
            )
            # Call directly with empty key - should not raise or call cb
            svc._replace_failed_proxy_config("")
            svc._replace_failed_proxy_config("  ")


# ===================================================================
# Tests for run_batch – fallback chain via async prober
# ===================================================================

class TestRunBatchFallbackChain(unittest.TestCase):
    def test_fallback_chain_recovers_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            target = _add_proxy(storage, "down-target.example.com")
            good_front = _add_proxy(storage, "good-front.example.com")
            bad_front = _add_proxy(storage, "bad-front.example.com")
            svc = TesterService(storage, prober=_AsyncUnavailableProber())
            report = asyncio.run(
                svc.run_batch(
                    limit=10,
                    fallback_front_proxy_keys=[
                        bad_front.normalized_key(),
                        good_front.normalized_key(),
                    ],
                    fallback_front_max_attempts=2,
                )
            )
            # target recovered via chain with good-front; bad-front recovered via chain with good-front
            # good-front itself stays unavailable (skips self in chain, bad-front chain fails)
            self.assertEqual(report.available, 2)
            self.assertEqual(report.unavailable, 1)


# ===================================================================
# Tests for run_openai_check_batch
# ===================================================================

class TestOpenAICheckBatch(unittest.TestCase):
    def test_stop_cb_at_start_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            _add_proxy(storage, "up.example.com")
            svc = TesterService(storage, prober=_OpenAIUnlockedProber())
            with self.assertRaises(TaskCancelled):
                asyncio.run(
                    svc.run_openai_check_batch(limit=10, stop_cb=lambda: True)
                )

    def test_empty_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            svc = TesterService(storage, prober=_OpenAIUnlockedProber())
            events: list[dict] = []
            report = asyncio.run(
                svc.run_openai_check_batch(
                    limit=10, progress_cb=lambda e: events.append(dict(e))
                )
            )
            self.assertEqual(report.requested, 0)
            self.assertTrue(any(e.get("phase") == "prepare" for e in events))

    def test_async_openai_unlocked(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            node = _add_proxy(storage, "up.example.com")
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)
            svc = TesterService(storage, prober=_OpenAIUnlockedProber())
            report = asyncio.run(
                svc.run_openai_check_batch(limit=10, only_available=True)
            )
            self.assertEqual(report.requested, 1)
            self.assertEqual(report.unlocked, 1)

    def test_sync_fallback_openai_check(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            node = _add_proxy(storage, "up.example.com")
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)
            svc = TesterService(storage, prober=_OpenAISyncProber())
            report = asyncio.run(
                svc.run_openai_check_batch(limit=10, only_available=True)
            )
            self.assertEqual(report.checked, 1)
            self.assertEqual(report.blocked, 1)

    def test_openai_unknown_status(self) -> None:
        """openai_unlocked=None counts as 'unknown'."""
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            node = _add_proxy(storage, "up.example.com")
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)

            class UnknownProber:
                def probe(self, node: dict) -> ProbeResult:
                    key = str(node.get("normalized_key") or "")
                    return ProbeResult(
                        normalized_key=key,
                        available=True,
                        openai_unlocked=None,
                        openai_status="",
                    )

            svc = TesterService(storage, prober=UnknownProber())
            report = asyncio.run(
                svc.run_openai_check_batch(limit=10, only_available=True)
            )
            self.assertEqual(report.unknown, 1)
            self.assertEqual(report.unlocked, 0)
            self.assertEqual(report.blocked, 0)

    def test_openai_fallback_chain(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            target = _add_proxy(storage, "down-target.example.com")
            good_front = _add_proxy(storage, "good-front.example.com")
            storage.update_test_result(target.normalized_key(), available=True, latency_ms=10)
            storage.update_test_result(good_front.normalized_key(), available=True, latency_ms=10)
            storage.update_test_result(
                target.normalized_key(),
                available=True,
                latency_ms=10,
                fallback_front_keys=[good_front.normalized_key()],
            )
            svc = TesterService(storage, prober=_OpenAINoneProber())
            report = asyncio.run(
                svc.run_openai_check_batch(
                    limit=0,
                    only_available=True,
                )
            )
            self.assertGreaterEqual(report.unlocked, 1)

    def test_openai_stop_cb_during_batch(self) -> None:
        """Cancellation during openai async batch."""
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            for i in range(4):
                n = _add_proxy(storage, f"up-{i}.example.com")
                storage.update_test_result(n.normalized_key(), available=True, latency_ms=10)
            svc = TesterService(storage, prober=_OpenAIUnlockedProber())
            started = False

            def stop_cb() -> bool:
                nonlocal started
                if not started:
                    started = True
                    return False
                return True

            with self.assertRaises(TaskCancelled):
                asyncio.run(
                    svc.run_openai_check_batch(
                        limit=10, concurrency=2, stop_cb=stop_cb
                    )
                )

    def test_sync_stop_cb_during_openai_batch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            node = _add_proxy(storage, "up.example.com")
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)
            svc = TesterService(storage, prober=_OpenAISyncProber())
            started = False

            def stop_cb() -> bool:
                nonlocal started
                if not started:
                    started = True
                    return False
                return True

            with self.assertRaises(TaskCancelled):
                asyncio.run(
                    svc.run_openai_check_batch(limit=10, stop_cb=stop_cb)
                )

    def test_openai_done_progress_event(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            node = _add_proxy(storage, "up.example.com")
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)
            svc = TesterService(storage, prober=_OpenAIUnlockedProber())
            events: list[dict] = []
            report = asyncio.run(
                svc.run_openai_check_batch(
                    limit=10,
                    only_available=True,
                    progress_cb=lambda e: events.append(dict(e)),
                )
            )
            self.assertEqual(report.checked, 1)
            done_events = [e for e in events if e.get("phase") == "done"]
            self.assertGreaterEqual(len(done_events), 1)
            self.assertEqual(done_events[-1]["completed"], 1)

    def test_openai_sync_stop_at_start(self) -> None:
        """Sync openai batch with stop_cb returning True immediately."""
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            _add_proxy(storage, "up.example.com")
            svc = TesterService(storage, prober=_OpenAISyncProber())
            with self.assertRaises(TaskCancelled):
                asyncio.run(
                    svc.run_openai_check_batch(limit=10, stop_cb=lambda: True)
                )


# ===================================================================
# Tests for run_batch – async cancellation
# ===================================================================

class TestRunBatchAsyncCancellation(unittest.TestCase):
    def test_cancel_during_async_batch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _make_storage(td)
            for i in range(6):
                _add_proxy(storage, f"up-{i}.example.com")
            svc = TesterService(storage, prober=_AsyncProber())
            started = False

            def stop_cb() -> bool:
                nonlocal started
                if not started:
                    started = True
                    return False
                return True

            with self.assertRaises(TaskCancelled):
                asyncio.run(
                    svc.run_batch(limit=10, concurrency=2, stop_cb=stop_cb)
                )


if __name__ == "__main__":
    unittest.main()
