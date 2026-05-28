import base64
import json
import tempfile
import unittest
from pathlib import Path

from proxypool.collector.service import CollectorService
from proxypool.storage.sqlite import SQLiteProxyStorage


class TestCollectorService(unittest.TestCase):
    def test_collect_from_files_and_deduplicate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            db_path = temp_dir / "proxies.db"
            source_file = temp_dir / "nodes.txt"

            vmess_payload = {
                "v": "2",
                "ps": "node-1",
                "add": "example.com",
                "port": "443",
                "id": "33333333-3333-3333-3333-333333333333",
                "aid": "0",
                "net": "tcp",
            }
            vmess = "vmess://" + base64.b64encode(json.dumps(vmess_payload).encode()).decode()
            source_file.write_text(
                "\n".join(
                    [
                        vmess,
                        "trojan://pwd@example.org:443#t-1",
                        "invalid-entry",
                        vmess,
                    ]
                ),
                encoding="utf-8",
            )

            storage = SQLiteProxyStorage(db_path)
            service = CollectorService(storage)
            report = service.collect_from_files([source_file])

            self.assertEqual(report.total_sources, 1)
            self.assertEqual(report.total_parsed, 3)
            self.assertEqual(report.total_invalid, 1)
            self.assertEqual(report.total_inserted, 2)
            self.assertEqual(report.total_updated, 0)
            self.assertEqual(report.total_deduped, 1)

            rows = storage.list_proxies(limit=10)
            self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
