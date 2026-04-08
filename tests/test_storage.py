import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


class TestSQLiteProxyStorage(unittest.TestCase):
    def test_filter_and_subscription(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            nodes = [
                ProxyNode(protocol="ss", host="1.1.1.1", port=443, raw_link="ss://a", extra={"cipher": "aes-128-gcm", "password": "p"}),
                ProxyNode(protocol="trojan", host="2.2.2.2", port=443, raw_link="trojan://b", extra={"password": "x"}),
            ]
            for node in nodes:
                storage.upsert_proxy(node, source="test")

            rows = storage.list_proxies_filtered(limit=10)
            self.assertEqual(len(rows), 2)

            first_key = rows[0]["normalized_key"]
            storage.update_test_result(
                first_key,
                available=True,
                latency_ms=120,
                openai_unlocked=True,
                openai_status="401 unauthorized",
                fallback_front_keys=["front-key-1", "front-key-2"],
            )

            up_rows = storage.list_proxies_filtered(limit=10, available=True)
            self.assertEqual(len(up_rows), 1)
            self.assertEqual(up_rows[0]["latency_ms"], 120)
            self.assertEqual(up_rows[0]["openai_unlocked"], True)
            self.assertEqual(up_rows[0]["openai_status"], "401 unauthorized")
            self.assertEqual(up_rows[0]["fallback_front_keys"], ["front-key-1", "front-key-2"])

            links = storage.get_subscription_links(only_available=True)
            self.assertEqual(len(links), 1)

            stats = storage.get_stats()
            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["available"], 1)

            storage.update_geo(first_key, resolved_ip="1.1.1.1", country="US", city="LA")
            storage.update_ip_purity(first_key, score=0.88, level="Low")
            with_geo = storage.list_proxies_filtered(limit=10, geo_filter="has")
            self.assertEqual(len(with_geo), 1)
            us_la = storage.list_proxies_filtered(limit=10, geo_location="US:LA")
            self.assertEqual(len(us_la), 1)
            us_keyword = storage.list_proxies_filtered(limit=10, geo_location="US")
            self.assertEqual(len(us_keyword), 1)
            self.assertEqual(str(us_keyword[0]["ip_purity_level"]), "Low")
            self.assertAlmostEqual(float(us_keyword[0]["ip_purity_score"] or 0), 0.88, places=2)

            unlocked = storage.list_proxies_filtered(limit=10, openai_filter="unlocked")
            self.assertEqual(len(unlocked), 1)
            blocked = storage.list_proxies_filtered(limit=10, openai_filter="blocked")
            self.assertEqual(len(blocked), 0)

            source_rows = storage.list_proxies_filtered(limit=10, source_keyword="test")
            self.assertEqual(len(source_rows), 2)

            deleted = storage.delete_unavailable()
            self.assertEqual(deleted, 1)
            left = storage.list_proxies_filtered(limit=10)
            self.assertEqual(len(left), 1)

    def test_backend_process_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            storage.record_backend_process_event(
                backend="singbox",
                action="start",
                pid=12345,
                result="success",
                detail="ok",
                config_file="/tmp/singbox-1.json",
            )
            storage.record_backend_process_event(
                backend="singbox",
                action="stop",
                pid=12345,
                result="success",
                detail="manual stop",
                config_file="/tmp/singbox-1.json",
            )
            rows = storage.list_backend_process_events(limit=10)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["action"], "stop")
            self.assertEqual(rows[1]["action"], "start")

    def test_subscriptions_crud(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            created = storage.create_subscription(
                name="demo-sub",
                url="https://example.com/sub.txt",
                enabled=True,
            )
            self.assertTrue(int(created["id"]) > 0)
            self.assertEqual(created["name"], "demo-sub")
            self.assertEqual(created["enabled"], True)

            updated = storage.update_subscription(
                subscription_id=int(created["id"]),
                name="demo-sub-2",
                enabled=False,
            )
            self.assertEqual(updated["name"], "demo-sub-2")
            self.assertEqual(updated["enabled"], False)

            storage.mark_subscription_result(
                subscription_id=int(created["id"]),
                status="success",
                error="",
                parsed=10,
                inserted=8,
                updated=2,
                invalid=0,
                deduped=1,
            )
            listed = storage.list_subscriptions(limit=10)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["last_status"], "success")
            self.assertEqual(int(listed[0]["last_inserted"] or 0), 8)

            deleted = storage.delete_subscription(int(created["id"]))
            self.assertEqual(deleted, 1)
            self.assertEqual(storage.list_subscriptions(limit=10), [])

    def test_delete_unavailable_subscriptions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            ok = storage.create_subscription(name="ok", url="https://example.com/ok")
            bad = storage.create_subscription(name="bad", url="https://example.com/bad")
            storage.mark_subscription_result(int(ok["id"]), status="success", parsed=1, inserted=1)
            storage.mark_subscription_result(int(bad["id"]), status="failed", error="fetch failed", invalid=1)

            deleted = storage.delete_unavailable_subscriptions()
            self.assertEqual(deleted, 1)
            left = storage.list_subscriptions(limit=10)
            self.assertEqual(len(left), 1)
            self.assertEqual(left[0]["name"], "ok")

    def test_get_candidates_for_test_limit_zero_means_all(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            for i in range(3):
                storage.upsert_proxy(
                    ProxyNode(
                        protocol="trojan",
                        host=f"h{i}.example.com",
                        port=443,
                        raw_link=f"trojan://{i}",
                        extra={"password": "p"},
                    )
                )
            all_rows = storage.get_candidates_for_test(limit=0)
            self.assertEqual(len(all_rows), 3)

    def test_filter_by_fallback_front_connectivity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            n1 = ProxyNode(protocol="trojan", host="up-1.example.com", port=443, raw_link="trojan://1", extra={"password": "p"})
            n2 = ProxyNode(protocol="trojan", host="up-2.example.com", port=443, raw_link="trojan://2", extra={"password": "p"})
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=100, fallback_front_keys=["front-a"])
            storage.update_test_result(n2.normalized_key(), available=True, latency_ms=120, fallback_front_keys=[])

            has_rows = storage.list_proxies_filtered(limit=10, fallback_front_filter="has")
            none_rows = storage.list_proxies_filtered(limit=10, fallback_front_filter="none")
            self.assertEqual(len(has_rows), 1)
            self.assertEqual(len(none_rows), 1)
            self.assertEqual(has_rows[0]["normalized_key"], n1.normalized_key())

    def test_global_subscription_update_proxy_setting(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            self.assertEqual(storage.get_subscription_update_proxy_key(), "")
            storage.set_subscription_update_proxy_key("abc123")
            self.assertEqual(storage.get_subscription_update_proxy_key(), "abc123")
            storage.set_subscription_update_proxy_key("")
            self.assertEqual(storage.get_subscription_update_proxy_key(), "")

    def test_concurrent_write_updates_are_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            nodes = []
            for i in range(60):
                node = ProxyNode(
                    protocol="trojan",
                    host=f"c{i}.example.com",
                    port=443,
                    raw_link=f"trojan://{i}",
                    extra={"password": "p"},
                )
                storage.upsert_proxy(node)
                nodes.append(node)

            def _write_one(idx: int) -> None:
                key = nodes[idx].normalized_key()
                storage.update_test_result(
                    normalized_key=key,
                    available=True,
                    latency_ms=20 + idx,
                )
                storage.update_openai_result(
                    normalized_key=key,
                    openai_unlocked=(idx % 2 == 0),
                    openai_status="ok",
                )
                storage.update_geo(
                    normalized_key=key,
                    resolved_ip=f"1.1.1.{idx % 255}",
                    country="X",
                    city="Y",
                )
                storage.update_ip_purity(
                    normalized_key=key,
                    score=float(idx),
                    level="Low",
                )

            with ThreadPoolExecutor(max_workers=30) as pool:
                futures = [pool.submit(_write_one, i) for i in range(len(nodes))]
                for fut in futures:
                    fut.result()

            rows = storage.list_proxies_filtered(limit=1000)
            self.assertEqual(len(rows), 60)
            available = [row for row in rows if bool(row.get("available"))]
            self.assertEqual(len(available), 60)


if __name__ == "__main__":
    unittest.main()
