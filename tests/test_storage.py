import base64
import json
import re
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

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
            storage.update_ip_purity(first_key, score=0.88, level="家宽")
            with_geo = storage.list_proxies_filtered(limit=10, geo_filter="has")
            self.assertEqual(len(with_geo), 1)
            us_country = storage.list_proxies_filtered(limit=10, geo_country="US")
            self.assertEqual(len(us_country), 1)
            self.assertEqual(str(us_country[0]["country"]), "US")
            unknown_country = storage.list_proxies_filtered(limit=10, geo_country="-")
            self.assertEqual(len(unknown_country), 1)
            self.assertEqual(str(unknown_country[0]["country"]), "")
            us_la = storage.list_proxies_filtered(limit=10, geo_location="US:LA")
            self.assertEqual(len(us_la), 1)
            us_keyword = storage.list_proxies_filtered(limit=10, geo_location="US")
            self.assertEqual(len(us_keyword), 1)
            self.assertEqual(str(us_keyword[0]["ip_purity_level"]), "家宽")
            self.assertAlmostEqual(float(us_keyword[0]["ip_purity_score"] or 0), 0.88, places=2)
            purity_checked = storage.list_proxies_filtered(limit=10, ip_purity_filter="checked")
            self.assertEqual(len(purity_checked), 1)
            purity_unchecked = storage.list_proxies_filtered(limit=10, ip_purity_filter="unchecked")
            self.assertEqual(len(purity_unchecked), 1)
            purity_home = storage.list_proxies_filtered(limit=10, ip_purity_filter="residential")
            self.assertEqual(len(purity_home), 1)
            purity_dc = storage.list_proxies_filtered(limit=10, ip_purity_filter="non_residential")
            self.assertEqual(len(purity_dc), 0)

            unlocked = storage.list_proxies_filtered(limit=10, openai_filter="unlocked")
            self.assertEqual(len(unlocked), 1)
            blocked = storage.list_proxies_filtered(limit=10, openai_filter="blocked")
            self.assertEqual(len(blocked), 0)

            source_rows = storage.list_proxies_filtered(limit=10, source_keyword="test")
            self.assertEqual(len(source_rows), 2)
            unknown_source_rows = storage.list_proxies_filtered(limit=10, source_keyword="-")
            self.assertEqual(len(unknown_source_rows), 0)

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

    def test_published_subscriptions_filter_export_links(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            us = ProxyNode(protocol="trojan", host="us.example.com", port=443, raw_link="trojan://us", extra={"password": "p"})
            jp = ProxyNode(protocol="trojan", host="jp.example.com", port=443, raw_link="trojan://jp", extra={"password": "p"})
            storage.upsert_proxy(us)
            storage.upsert_proxy(jp)
            storage.update_test_result(us.normalized_key(), available=True, latency_ms=100, openai_unlocked=True)
            storage.update_test_result(jp.normalized_key(), available=True, latency_ms=120, openai_unlocked=False)
            storage.update_geo(us.normalized_key(), resolved_ip="1.1.1.1", country="US", city="LA")
            storage.update_geo(jp.normalized_key(), resolved_ip="2.2.2.2", country="JP", city="Tokyo")

            created = storage.create_published_subscription(
                name="US GPT",
                filters={
                    "available": "true",
                    "geo_location": "US:LA",
                    "openai_filter": "unlocked",
                },
            )
            self.assertTrue(int(created["id"]) > 0)
            self.assertEqual(created["name"], "US GPT")
            self.assertEqual(created["filters"]["geo_location"], "US:LA")
            self.assertEqual(created["match_count"], 1)

            links = storage.get_published_subscription_links(int(created["id"]))
            self.assertEqual(len(links), 1)
            self.assertIn("trojan://us", links[0])

            updated = storage.update_published_subscription(
                int(created["id"]),
                name="JP blocked",
                filters={"geo_country": "JP", "openai_filter": "blocked"},
            )
            self.assertEqual(updated["name"], "JP blocked")
            self.assertEqual(updated["match_count"], 1)
            self.assertIn("trojan://jp", storage.get_published_subscription_links(int(created["id"]))[0])

            listed = storage.list_published_subscriptions()
            self.assertEqual(len(listed), 1)
            self.assertEqual(storage.delete_published_subscription(int(created["id"])), 1)
            self.assertEqual(storage.list_published_subscriptions(), [])

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

    def test_get_candidates_for_test_supports_only_unavailable_and_min_age(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            old_down = ProxyNode(protocol="trojan", host="down-old.example.com", port=443, raw_link="trojan://old", extra={"password": "p"})
            recent_down = ProxyNode(protocol="trojan", host="down-recent.example.com", port=443, raw_link="trojan://recent", extra={"password": "p"})
            up_node = ProxyNode(protocol="trojan", host="up.example.com", port=443, raw_link="trojan://up", extra={"password": "p"})
            storage.upsert_proxy(old_down)
            storage.upsert_proxy(recent_down)
            storage.upsert_proxy(up_node)
            storage.update_test_result(old_down.normalized_key(), available=False, latency_ms=None, error="down")
            storage.update_test_result(recent_down.normalized_key(), available=False, latency_ms=None, error="down")
            storage.update_test_result(up_node.normalized_key(), available=True, latency_ms=20)

            now = datetime.now(timezone.utc)
            with storage._connect() as conn:
                conn.execute(
                    "UPDATE proxies SET last_checked_at = ? WHERE normalized_key = ?",
                    ((now - timedelta(days=2)).isoformat(), old_down.normalized_key()),
                )
                conn.execute(
                    "UPDATE proxies SET last_checked_at = ? WHERE normalized_key = ?",
                    ((now - timedelta(hours=2)).isoformat(), recent_down.normalized_key()),
                )
                conn.execute(
                    "UPDATE proxies SET last_checked_at = ? WHERE normalized_key = ?",
                    ((now - timedelta(days=2)).isoformat(), up_node.normalized_key()),
                )
                conn.commit()

            rows = storage.get_candidates_for_test(
                limit=0,
                only_unavailable=True,
                min_last_checked_age_hours=24,
            )
            self.assertEqual([str(r["host"]) for r in rows], ["down-old.example.com"])

    def test_subscription_export_alias_format_in_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            relay = ProxyNode(protocol="trojan", host="relay.example.com", port=443, raw_link="trojan://pass2@relay.example.com:443#old2", extra={"password": "pass2"})
            target = ProxyNode(protocol="trojan", host="target.example.com", port=443, raw_link="trojan://pass1@target.example.com:443#old1", extra={"password": "pass1"})
            storage.upsert_proxy(relay, source="upload:test.txt")
            storage.upsert_proxy(target, source="upload:test.txt")

            storage.update_geo(relay.normalized_key(), resolved_ip="1.1.1.2", country="日本", city="东京")
            storage.update_geo(target.normalized_key(), resolved_ip="1.1.1.1", country="新加坡", city="新加坡")
            storage.update_ip_purity(relay.normalized_key(), score=0.1, level="非家宽")
            storage.update_ip_purity(target.normalized_key(), score=0.9, level="家宽")
            storage.update_test_result(
                relay.normalized_key(),
                available=True,
                latency_ms=20,
                openai_unlocked=False,
                openai_status="403 region blocked",
            )
            storage.update_test_result(
                target.normalized_key(),
                available=True,
                latency_ms=10,
                openai_unlocked=True,
                openai_status="401 unauthorized",
                fallback_front_keys=[relay.normalized_key()],
            )

            links = storage.get_subscription_links(only_available=True, limit=10)
            self.assertEqual(len(links), 2)
            frag_1 = unquote(urlsplit(links[0]).fragment)
            frag_2 = unquote(urlsplit(links[1]).fragment)
            self.assertIn("1_新加坡:新加坡_链式(2)_家宽_已解锁GPT_", frag_1)
            self.assertIn("2_日本:东京_直连_非家宽_未解锁GPT_", frag_2)
            self.assertRegex(frag_1, r"_\d{14}$")
            self.assertRegex(frag_2, r"_\d{14}$")

    def test_subscription_export_alias_rewrites_vmess_ps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            vmess_payload = {
                "v": "2",
                "ps": "old-name",
                "add": "vm.example.com",
                "port": "443",
                "id": "11111111-1111-1111-1111-111111111111",
                "aid": "0",
                "net": "ws",
                "type": "none",
                "host": "",
                "path": "/",
                "tls": "tls",
            }
            raw = "vmess://" + base64.urlsafe_b64encode(
                json.dumps(vmess_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).decode("utf-8").rstrip("=")
            node = ProxyNode(
                protocol="vmess",
                host="vm.example.com",
                port=443,
                raw_link=raw,
                extra={"uuid": "11111111-1111-1111-1111-111111111111"},
            )
            storage.upsert_proxy(node, source="upload:test.txt")
            storage.update_geo(node.normalized_key(), resolved_ip="1.2.3.4", country="美国", city="洛杉矶")
            storage.update_ip_purity(node.normalized_key(), score=0.5, level="未知")
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)

            links = storage.get_subscription_links(only_available=True, limit=10)
            self.assertEqual(len(links), 1)
            self.assertTrue(links[0].startswith("vmess://"))
            encoded = links[0][len("vmess://") :]
            pad = "=" * ((4 - len(encoded) % 4) % 4)
            parsed = json.loads(base64.urlsafe_b64decode((encoded + pad).encode("utf-8")).decode("utf-8"))
            self.assertTrue(str(parsed.get("ps") or "").startswith("1_美国:洛杉矶_直连_未知_未检测GPT_"))
            self.assertRegex(str(parsed.get("ps") or ""), r"_\d{14}$")

    def test_global_subscription_update_proxy_setting(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            self.assertEqual(storage.get_subscription_update_proxy_key(), "")
            storage.set_subscription_update_proxy_key("abc123")
            self.assertEqual(storage.get_subscription_update_proxy_key(), "abc123")
            storage.set_subscription_update_proxy_key("")
            self.assertEqual(storage.get_subscription_update_proxy_key(), "")

    def test_backend_default_port_range_setting(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            self.assertEqual(storage.get_backend_default_port_range(), {"start": 1081, "end": 1180})
            saved = storage.set_backend_default_port_range(20000, 20100)
            self.assertEqual(saved, {"start": 20000, "end": 20100})
            self.assertEqual(storage.get_backend_default_port_range(), {"start": 20000, "end": 20100})
            with self.assertRaises(ValueError):
                storage.set_backend_default_port_range(30000, 20000)

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
