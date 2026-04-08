import asyncio
import tempfile
import unittest
from pathlib import Path

from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.tester.service import TesterService
from proxypool.tester.singbox import ProbeResult


class FakeProber:
    def probe(self, node: dict):
        key = node["normalized_key"]
        if node["host"].startswith("up"):
            return ProbeResult(normalized_key=key, available=True, latency_ms=88)
        return ProbeResult(normalized_key=key, available=False, error="down")


class AsyncParallelProber:
    def __init__(self) -> None:
        self.inflight = 0
        self.max_inflight = 0

    async def probe_async(self, node: dict):
        key = node["normalized_key"]
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        try:
            await asyncio.sleep(0.05)
            return ProbeResult(normalized_key=key, available=True, latency_ms=40)
        finally:
            self.inflight -= 1


class RecordingProber:
    def __init__(self) -> None:
        self.hosts: list[str] = []

    def probe(self, node: dict):
        self.hosts.append(str(node.get("host") or ""))
        return ProbeResult(normalized_key=node["normalized_key"], available=True, latency_ms=20)


class OpenAICheckProber:
    def probe(self, node: dict):
        # connectivity result should not matter for openai-only mode
        return ProbeResult(
            normalized_key=node["normalized_key"],
            available=False,
            latency_ms=None,
            openai_unlocked=False,
            openai_status="403 region blocked",
            error="timeout",
        )


class RecordingOpenAIProber:
    def __init__(self) -> None:
        self.hosts: list[str] = []

    def probe(self, node: dict):
        self.hosts.append(str(node.get("host") or ""))
        return ProbeResult(
            normalized_key=node["normalized_key"],
            available=True,
            latency_ms=20,
            openai_unlocked=True,
            openai_status="401 unauthorized",
        )


class OpenAIFallbackProber:
    def __init__(self) -> None:
        self.chain_calls: list[tuple[str, str]] = []

    async def probe_async(self, node: dict):
        host = str(node.get("host") or "")
        key = str(node.get("normalized_key") or "")
        if host.startswith("target"):
            return ProbeResult(normalized_key=key, available=False, openai_unlocked=None, error="direct down")
        return ProbeResult(normalized_key=key, available=True, openai_unlocked=True, openai_status="401 unauthorized")

    async def probe_with_front_proxy_async(self, node: dict, front_proxy: dict):
        node_key = str(node.get("normalized_key") or "")
        front_key = str(front_proxy.get("normalized_key") or "")
        self.chain_calls.append((node_key, front_key))
        return ProbeResult(
            normalized_key=node_key,
            available=True,
            latency_ms=66,
            openai_unlocked=True,
            openai_status="401 unauthorized",
        )


class FallbackChainProber:
    def __init__(self) -> None:
        self.chain_calls: list[tuple[str, str]] = []

    async def probe_async(self, node: dict):
        key = node["normalized_key"]
        host = str(node.get("host") or "")
        if host.startswith("down"):
            return ProbeResult(normalized_key=key, available=False, error="direct down")
        return ProbeResult(normalized_key=key, available=True, latency_ms=30)

    async def probe_with_front_proxy_async(self, node: dict, front_proxy: dict):
        node_key = str(node.get("normalized_key") or "")
        front_key = str(front_proxy.get("normalized_key") or "")
        self.chain_calls.append((node_key, front_key))
        front_host = str(front_proxy.get("host") or "")
        if front_host.startswith("front-ok"):
            return ProbeResult(normalized_key=node_key, available=True, latency_ms=66)
        return ProbeResult(normalized_key=node_key, available=False, error="chain down")


class TestTesterService(unittest.TestCase):
    def test_run_batch_updates_storage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            storage.upsert_proxy(
                ProxyNode(protocol="trojan", host="up.example.com", port=443, raw_link="trojan://a", extra={"password": "p"})
            )
            storage.upsert_proxy(
                ProxyNode(protocol="trojan", host="down.example.com", port=443, raw_link="trojan://b", extra={"password": "p"})
            )

            tester = TesterService(storage, prober=FakeProber())
            report = asyncio.run(tester.run_batch(limit=10, concurrency=4))

            self.assertEqual(report.requested, 2)
            self.assertEqual(report.tested, 2)
            self.assertEqual(report.available, 1)
            self.assertEqual(report.unavailable, 1)

            up_rows = storage.list_proxies_filtered(limit=10, available=True)
            down_rows = storage.list_proxies_filtered(limit=10, available=False)
            self.assertEqual(len(up_rows), 1)
            self.assertEqual(len(down_rows), 1)

    def test_run_batch_reports_incremental_progress(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            storage.upsert_proxy(
                ProxyNode(protocol="trojan", host="up-1.example.com", port=443, raw_link="trojan://a", extra={"password": "p"})
            )
            storage.upsert_proxy(
                ProxyNode(protocol="trojan", host="down-2.example.com", port=443, raw_link="trojan://b", extra={"password": "p"})
            )

            tester = TesterService(storage, prober=FakeProber())
            progress_events: list[dict] = []

            def _progress(payload: dict) -> None:
                progress_events.append(dict(payload))

            asyncio.run(tester.run_batch(limit=10, concurrency=4, progress_cb=_progress))

            self.assertGreaterEqual(len(progress_events), 3)
            # prepare + first probe + second probe (+ optional done event)
            completed_values = [int(ev.get("completed", 0)) for ev in progress_events]
            self.assertIn(1, completed_values)
            self.assertEqual(completed_values[-1], 2)

    def test_run_batch_supports_parallel_probing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            for i in range(12):
                storage.upsert_proxy(
                    ProxyNode(
                        protocol="trojan",
                        host=f"up-{i}.example.com",
                        port=443,
                        raw_link=f"trojan://{i}",
                        extra={"password": "p"},
                    )
                )

            prober = AsyncParallelProber()
            tester = TesterService(storage, prober=prober)
            report = asyncio.run(tester.run_batch(limit=12, concurrency=30))

            self.assertEqual(report.tested, 12)
            self.assertGreater(prober.max_inflight, 1)

    def test_run_batch_only_available_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            n1 = ProxyNode(protocol="trojan", host="up.example.com", port=443, raw_link="trojan://a", extra={"password": "p"})
            n2 = ProxyNode(protocol="trojan", host="down.example.com", port=443, raw_link="trojan://b", extra={"password": "p"})
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=10)

            prober = RecordingProber()
            tester = TesterService(storage, prober=prober)
            report = asyncio.run(tester.run_batch(limit=10, concurrency=4, only_available=True))

            self.assertEqual(report.requested, 1)
            self.assertEqual(prober.hosts, ["up.example.com"])

    def test_run_batch_limit_zero_tests_all(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            for i in range(3):
                storage.upsert_proxy(
                    ProxyNode(
                        protocol="trojan",
                        host=f"up-{i}.example.com",
                        port=443,
                        raw_link=f"trojan://{i}",
                        extra={"password": "p"},
                    )
                )
            prober = RecordingProber()
            tester = TesterService(storage, prober=prober)
            report = asyncio.run(tester.run_batch(limit=0, concurrency=4))
            self.assertEqual(report.requested, 3)
            self.assertEqual(report.tested, 3)

    def test_openai_check_does_not_change_connectivity_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            node = ProxyNode(
                protocol="trojan",
                host="up.example.com",
                port=443,
                raw_link="trojan://a",
                extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            key = node.normalized_key()
            storage.update_test_result(
                key,
                available=True,
                latency_ms=123,
                openai_unlocked=True,
                openai_status="401 unauthorized",
            )

            tester = TesterService(storage, prober=OpenAICheckProber())
            report = asyncio.run(tester.run_openai_check_batch(limit=10, concurrency=2, only_available=True))
            self.assertEqual(report.requested, 1)
            self.assertEqual(report.checked, 1)
            self.assertEqual(report.blocked, 1)

            row = storage.get_proxy_by_key(key)
            self.assertIsNotNone(row)
            assert row is not None
            self.assertTrue(bool(row["available"]))
            self.assertEqual(int(row["latency_ms"]), 123)
            self.assertEqual(row["openai_status"], "403 region blocked")
            self.assertFalse(bool(row["openai_unlocked"]))

    def test_openai_check_always_filters_to_available_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            up = ProxyNode(protocol="trojan", host="up.example.com", port=443, raw_link="trojan://up", extra={"password": "p"})
            down = ProxyNode(protocol="trojan", host="down.example.com", port=443, raw_link="trojan://down", extra={"password": "p"})
            storage.upsert_proxy(up)
            storage.upsert_proxy(down)
            storage.update_test_result(up.normalized_key(), available=True, latency_ms=30)
            storage.update_test_result(down.normalized_key(), available=False, latency_ms=None, error="down")

            prober = RecordingOpenAIProber()
            tester = TesterService(storage, prober=prober)
            report = asyncio.run(tester.run_openai_check_batch(limit=10, concurrency=2, only_available=False))
            self.assertEqual(report.requested, 1)
            self.assertEqual(prober.hosts, ["up.example.com"])

    def test_openai_check_uses_saved_fallback_front_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            target = ProxyNode(
                protocol="trojan",
                host="target.example.com",
                port=443,
                raw_link="trojan://target",
                extra={"password": "p"},
            )
            front = ProxyNode(
                protocol="trojan",
                host="front-ok.example.com",
                port=443,
                raw_link="trojan://front",
                extra={"password": "p"},
            )
            storage.upsert_proxy(target)
            storage.upsert_proxy(front)
            storage.update_test_result(front.normalized_key(), available=True, latency_ms=20)
            storage.update_test_result(
                target.normalized_key(),
                available=True,
                latency_ms=30,
                fallback_front_keys=[front.normalized_key()],
            )

            prober = OpenAIFallbackProber()
            tester = TesterService(storage, prober=prober)
            report = asyncio.run(tester.run_openai_check_batch(limit=0, concurrency=2, only_available=True))
            self.assertEqual(report.requested, 2)
            self.assertEqual(report.checked, 2)
            self.assertEqual(report.unlocked, 2)
            self.assertGreaterEqual(len(prober.chain_calls), 1)

            row = storage.get_proxy_by_key(target.normalized_key())
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row["openai_unlocked"], True)
            self.assertEqual(row["openai_status"], "401 unauthorized")

    def test_failed_direct_probe_can_be_recovered_by_fallback_front_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            target = ProxyNode(
                protocol="trojan",
                host="down.example.com",
                port=443,
                raw_link="trojan://target",
                extra={"password": "p"},
            )
            front_1 = ProxyNode(
                protocol="trojan",
                host="front-bad.example.com",
                port=443,
                raw_link="trojan://front1",
                extra={"password": "p1"},
            )
            front_2 = ProxyNode(
                protocol="trojan",
                host="front-ok.example.com",
                port=443,
                raw_link="trojan://front2",
                extra={"password": "p2"},
            )
            storage.upsert_proxy(target)
            storage.upsert_proxy(front_1)
            storage.upsert_proxy(front_2)

            prober = FallbackChainProber()
            tester = TesterService(storage, prober=prober)
            report = asyncio.run(
                tester.run_batch(
                    limit=10,
                    concurrency=4,
                    fallback_front_proxy_keys=[front_1.normalized_key(), front_2.normalized_key()],
                    fallback_front_max_attempts=2,
                )
            )

            self.assertEqual(report.requested, 3)
            self.assertEqual(report.available, 3)
            self.assertEqual(report.unavailable, 0)

            target_row = storage.get_proxy_by_key(target.normalized_key())
            self.assertIsNotNone(target_row)
            assert target_row is not None
            self.assertTrue(bool(target_row["available"]))
            self.assertEqual(target_row["fallback_front_keys"], [front_2.normalized_key()])
            self.assertGreaterEqual(len(prober.chain_calls), 2)


if __name__ == "__main__":
    unittest.main()
