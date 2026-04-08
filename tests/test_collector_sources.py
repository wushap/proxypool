import tempfile
import unittest
from urllib.parse import quote
from pathlib import Path
from unittest.mock import patch

from proxypool.collector.service import CollectorService
from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


class TestCollectorSources(unittest.TestCase):
    def test_collect_from_urls(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            collector = CollectorService(storage)

            text = "\n".join(
                ["trojan://pwd@example.com:443#t1", "ss://YWVzLTEyOC1nY206cGFzcw==@1.1.1.1:443#ss1", "invalid-line"]
            )
            data_url = f"data:text/plain,{quote(text)}"

            report = collector.collect_from_urls([data_url])

            self.assertEqual(report.total_sources, 1)
            self.assertEqual(report.total_parsed, 2)
            self.assertEqual(report.total_invalid, 1)

    def test_collect_from_sources_aggregates_deduped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            db = tmp / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            collector = CollectorService(storage)

            f1 = tmp / "a.txt"
            f1.write_text(
                "\n".join(
                    [
                        "trojan://pwd@example.com:443#t1",
                        "trojan://pwd@example.com:443#t1",
                    ]
                ),
                encoding="utf-8",
            )
            text = "\n".join(
                [
                    "ss://YWVzLTEyOC1nY206cGFzcw==@1.1.1.1:443#ss1",
                    "ss://YWVzLTEyOC1nY206cGFzcw==@1.1.1.1:443#ss1",
                ]
            )
            data_url = f"data:text/plain,{quote(text)}"

            report = collector.collect_from_sources([str(f1), data_url])

            self.assertEqual(report.total_sources, 2)
            self.assertEqual(report.total_parsed, 4)
            self.assertEqual(report.total_inserted, 2)
            self.assertEqual(report.total_deduped, 2)

    def test_collect_from_subscription_tags_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            collector = CollectorService(storage)

            text = "trojan://pwd@example.com:443#t1"
            data_url = f"data:text/plain,{quote(text)}"
            report = collector.collect_from_subscription(
                subscription_id=7,
                subscription_name="my-sub",
                subscription_url=data_url,
            )
            self.assertEqual(report.total_sources, 1)
            self.assertEqual(report.total_inserted, 1)
            rows = storage.list_proxies_filtered(limit=10)
            self.assertEqual(len(rows), 1)
            self.assertIn("subscription#7", str(rows[0]["source"]))
            self.assertIn("my-sub", str(rows[0]["source"]))

    def test_collect_from_text_items_with_subscription_links(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            collector = CollectorService(storage)

            with patch(
                "proxypool.collector.service.fetch_text",
                return_value="trojan://pwd@example.com:443#from-sub",
            ):
                report = collector.collect_from_text_items(
                    [
                        (
                            "upload.txt",
                            "\n".join(
                                [
                                    "https://example.com/subscription/list.txt?token=abc",
                                    "http://10.0.0.1:8080#http-proxy",
                                ]
                            ),
                        )
                    ]
                )

            self.assertEqual(report.total_inserted, 2)
            rows = storage.list_proxies_filtered(limit=10)
            self.assertEqual(len(rows), 2)
            protocols = sorted(str(item["protocol"]) for item in rows)
            self.assertEqual(protocols, ["http", "trojan"])
            self.assertTrue(any("subscription#" in str(item["source"]) for item in rows))
            self.assertTrue(any("example.com/subscription" in str(item["source"]) for item in rows))
            subs = storage.list_subscriptions(limit=10)
            self.assertEqual(len(subs), 1)
            self.assertEqual(subs[0]["url"], "https://example.com/subscription/list.txt?token=abc")
            self.assertEqual(subs[0]["last_status"], "success")

    def test_collect_from_subscription_uses_configured_update_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            collector = CollectorService(storage)

            node = ProxyNode(
                protocol="trojan",
                host="proxy.example.com",
                port=443,
                raw_link="trojan://p@proxy.example.com:443",
                extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            storage.set_subscription_update_proxy_key(node.normalized_key())

            with patch(
                "proxypool.collector.service.fetch_text_via_proxy_node",
                return_value="trojan://pwd@example.com:443#from-sub-proxy",
            ) as mocked_proxy_fetch:
                report = collector.collect_from_subscription(
                    subscription_id=8,
                    subscription_name="proxy-sub",
                    subscription_url="https://example.com/sub.txt",
                )

            self.assertEqual(report.total_inserted, 1)
            mocked_proxy_fetch.assert_called_once()

    def test_collect_from_text_items_subscription_refs_use_global_update_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            collector = CollectorService(storage)

            node = ProxyNode(
                protocol="trojan",
                host="proxy.example.com",
                port=443,
                raw_link="trojan://p@proxy.example.com:443",
                extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            storage.set_subscription_update_proxy_key(node.normalized_key())

            with patch(
                "proxypool.collector.service.fetch_text_via_proxy_node",
                return_value="trojan://pwd@example.com:443#from-sub-proxy-2",
            ) as mocked_proxy_fetch:
                report = collector.collect_from_text_items(
                    [("upload.txt", "https://example.com/subscription/list.txt?token=abc")]
                )
            self.assertEqual(report.total_inserted, 1)
            mocked_proxy_fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
