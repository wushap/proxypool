import tempfile
import threading
import time
import unittest
from pathlib import Path

from proxypool.geoip.service import GeoIPService, _weighted_purity_score
from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


class TestGeoIPService(unittest.TestCase):
    def test_enrich_batch_geo_fallback_to_ipinfo_when_ip_api_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            node = ProxyNode(
                protocol="trojan",
                host="fallback.example.com",
                port=443,
                raw_link="trojan://fallback",
                extra={"password": "x"},
            )
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=11)

            calls: list[str] = []

            def proxy_fetcher(proxy_row: dict, url: str, timeout_sec: float, front_proxy: dict | None = None) -> dict:
                calls.append(url)
                if "ip-api.com/json/" in url:
                    return {"status": "fail", "message": "limit reached"}
                if "ipinfo.io/" in url and url.endswith("/json"):
                    return {"ip": "203.0.113.77", "country": "US", "city": "Seattle"}
                if "ipinfo.check.place" in url and "db=ip2location" in url:
                    return {"usage_type": "RES"}
                if "ipinfo.check.place" in url and "db=iplark" in url:
                    return {"is_residential": True}
                if "ipinfo.check.place" in url and "db=ippure" in url:
                    return {"residential": True}
                raise AssertionError(f"unexpected url: {url}")

            service = GeoIPService(storage=storage, proxy_json_fetcher=proxy_fetcher)
            report = service.enrich_batch(limit=1, concurrency=1)
            self.assertEqual(report["updated"], 1)
            row = storage.list_proxies_filtered(limit=1)[0]
            self.assertEqual(row["resolved_ip"], "203.0.113.77")
            self.assertEqual(row["country"], "US")
            self.assertEqual(row["city"], "Seattle")
            self.assertTrue(any("ip-api.com/json/" in u for u in calls))
            self.assertTrue(any("ipinfo.io/" in u for u in calls))

    def test_enrich_batch_uses_proxy_lookup_when_fetcher_provided(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            node = ProxyNode(
                protocol="trojan",
                host="a.example.com",
                port=443,
                raw_link="trojan://a",
                extra={"password": "x"},
            )
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=11)

            calls: list[str] = []

            def proxy_fetcher(proxy_row: dict, url: str, timeout_sec: float, front_proxy: dict | None = None) -> dict:
                calls.append(url)
                self.assertEqual(proxy_row.get("host"), "a.example.com")
                if "ip-api.com/json/" in url:
                    return {
                        "status": "success",
                        "country": "Japan",
                        "city": "Tokyo",
                        "query": "203.0.113.10",
                    }
                if "ipinfo.check.place" in url and "db=ip2location" in url:
                    return {"usage_type": "RES"}
                if "ipinfo.check.place" in url and "db=iplark" in url:
                    return {"is_residential": True}
                if "ipinfo.check.place" in url and "db=ippure" in url:
                    return {"residential": True}
                if "ipinfo.io/" in url and url.endswith("/json"):
                    return {"ip": "203.0.113.10", "org": "Comcast Cable"}
                raise AssertionError(f"unexpected url: {url}")

            service = GeoIPService(
                storage=storage,
                resolver=lambda host: (_ for _ in ()).throw(AssertionError("resolver should not be used")),
                geo_lookup=lambda ip: (_ for _ in ()).throw(AssertionError("geo_lookup should not be used")),
                purity_lookup=lambda ip: (_ for _ in ()).throw(AssertionError("purity_lookup should not be used")),
                proxy_json_fetcher=proxy_fetcher,
            )

            report = service.enrich_batch(limit=10, concurrency=1)
            self.assertEqual(report["updated"], 1)
            self.assertEqual(report["failed"], 0)

            row = storage.list_proxies_filtered(limit=1)[0]
            self.assertEqual(row["resolved_ip"], "203.0.113.10")
            self.assertEqual(row["country"], "Japan")
            self.assertEqual(row["city"], "Tokyo")
            self.assertTrue(any("ip-api.com/json/" in u for u in calls))
            self.assertTrue(any("db=ip2location" in u for u in calls))

    def test_enrich_ip_purity_batch_uses_proxy_lookup_when_fetcher_provided(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            node = ProxyNode(
                protocol="vless",
                host="b.example.com",
                port=443,
                raw_link="vless://b",
                extra={"uuid": "u"},
            )
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=11)

            calls: list[str] = []

            def proxy_fetcher(proxy_row: dict, url: str, timeout_sec: float, front_proxy: dict | None = None) -> dict:
                calls.append(url)
                self.assertEqual(proxy_row.get("host"), "b.example.com")
                if "ip-api.com/json/" in url:
                    return {"status": "success", "country": "US", "city": "Seattle", "query": "198.51.100.12"}
                if "ipinfo.check.place" in url and "db=ip2location" in url:
                    return {"usage_type": "DCH"}
                if "ipinfo.check.place" in url and "db=iplark" in url:
                    return {"is_datacenter": True}
                if "ipinfo.check.place" in url and "db=ippure" in url:
                    return {"is_proxy": True}
                if "ipinfo.io/" in url and url.endswith("/json"):
                    return {"ip": "198.51.100.12", "org": "Amazon.com, Inc."}
                raise AssertionError(f"unexpected url: {url}")

            service = GeoIPService(
                storage=storage,
                resolver=lambda host: (_ for _ in ()).throw(AssertionError("resolver should not be used")),
                geo_lookup=lambda ip: (_ for _ in ()).throw(AssertionError("geo_lookup should not be used")),
                purity_lookup=lambda ip: (_ for _ in ()).throw(AssertionError("purity_lookup should not be used")),
                proxy_json_fetcher=proxy_fetcher,
            )
            report = service.enrich_ip_purity_batch(limit=1, concurrency=1, only_unchecked=False)
            self.assertEqual(report["updated"], 1)
            self.assertEqual(report["failed"], 0)
            row = storage.list_proxies_filtered(limit=1)[0]
            self.assertEqual(row["resolved_ip"], "198.51.100.12")
            self.assertEqual(str(row["ip_purity_level"]), "非家宽")
            self.assertTrue(float(row["ip_purity_score"] or 0) < 40)
            self.assertTrue(any("ip-api.com/json/" in u for u in calls))
            self.assertTrue(any("db=ip2location" in u for u in calls))

    def test_enrich_batch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            n1 = ProxyNode(protocol="vless", host="a.example.com", port=443, raw_link="vless://a", extra={"uuid": "1"})
            n2 = ProxyNode(protocol="trojan", host="b.example.com", port=443, raw_link="trojan://b", extra={"password": "x"})
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=11)
            storage.update_test_result(n2.normalized_key(), available=True, latency_ms=12)

            ip_map = {
                "a.example.com": "1.1.1.1",
                "b.example.com": "8.8.8.8",
            }
            geo_map = {
                "1.1.1.1": ("Australia", "Sydney"),
                "8.8.8.8": ("United States", "Mountain View"),
            }

            service = GeoIPService(
                storage=storage,
                resolver=lambda host: ip_map[host],
                geo_lookup=lambda ip: geo_map[ip],
                purity_lookup=lambda ip: (1.56, "Elevated"),
            )
            report = service.enrich_batch(limit=10)
            self.assertEqual(report["requested"], 2)
            self.assertEqual(report["updated"], 2)
            self.assertEqual(report["failed"], 0)

            rows = storage.list_proxies_filtered(limit=10)
            rows_by_ip = {row["resolved_ip"]: row for row in rows}
            self.assertEqual(rows_by_ip["1.1.1.1"]["country"], "Australia")
            self.assertEqual(rows_by_ip["8.8.8.8"]["city"], "Mountain View")
            self.assertEqual(rows_by_ip["1.1.1.1"]["ip_purity_level"], "Elevated")
            self.assertAlmostEqual(float(rows_by_ip["1.1.1.1"]["ip_purity_score"] or 0), 1.56, places=2)

    def test_weighted_purity_score(self) -> None:
        score, level = _weighted_purity_score(
            {
                "ipapi": 2.0,
                "ipqualityscore": 50.0,
                "scamalytics": 30.0,
                "abuseipdb": None,
                "ip2location": 20.0,
                "ipdata": 10.0,
            }
        )
        self.assertIsNotNone(score)
        assert score is not None
        self.assertGreater(score, 20)
        self.assertLess(score, 40)
        self.assertEqual(level, "High")

    def test_enrich_ip_purity_batch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            n1 = ProxyNode(protocol="trojan", host="a.example.com", port=443, raw_link="trojan://a", extra={"password": "x"})
            n2 = ProxyNode(protocol="trojan", host="b.example.com", port=443, raw_link="trojan://b", extra={"password": "y"})
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=11)
            storage.update_test_result(n2.normalized_key(), available=True, latency_ms=12)
            storage.update_geo(n2.normalized_key(), resolved_ip="2.2.2.2", country="B", city="C")

            service = GeoIPService(
                storage=storage,
                resolver=lambda host: "1.1.1.1" if host == "a.example.com" else "2.2.2.2",
                geo_lookup=lambda ip: ("", ""),
                purity_lookup=lambda ip: (12.0 if ip == "1.1.1.1" else 34.0, "Elevated"),
            )
            report = service.enrich_ip_purity_batch(limit=0, only_unchecked=False)
            self.assertEqual(report["requested"], 2)
            self.assertEqual(report["updated"], 2)
            self.assertEqual(report["failed"], 0)

            rows = storage.list_proxies_filtered(limit=10)
            by_host = {str(row["host"]): row for row in rows}
            self.assertAlmostEqual(float(by_host["a.example.com"]["ip_purity_score"] or 0), 12.0, places=2)
            self.assertAlmostEqual(float(by_host["b.example.com"]["ip_purity_score"] or 0), 34.0, places=2)

    def test_enrich_batch_supports_parallel_workers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            for i in range(12):
                node = ProxyNode(
                        protocol="trojan",
                        host=f"h-{i}.example.com",
                        port=443,
                        raw_link=f"trojan://{i}",
                        extra={"password": "p"},
                    )
                storage.upsert_proxy(node)
                storage.update_test_result(node.normalized_key(), available=True, latency_ms=20)

            lock = threading.Lock()
            inflight = 0
            max_inflight = 0

            def resolver(host: str) -> str:
                nonlocal inflight, max_inflight
                with lock:
                    inflight += 1
                    max_inflight = max(max_inflight, inflight)
                time.sleep(0.02)
                with lock:
                    inflight -= 1
                idx = host.split("-")[1].split(".")[0]
                return f"1.1.1.{idx}"

            service = GeoIPService(
                storage=storage,
                resolver=resolver,
                geo_lookup=lambda ip: ("US", "Test"),
                purity_lookup=lambda ip: (2.0, "Low"),
            )
            report = service.enrich_batch(limit=12, concurrency=8)
            self.assertEqual(report["updated"], 12)
            self.assertGreater(max_inflight, 1)

    def test_enrich_ip_purity_batch_supports_parallel_workers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            for i in range(12):
                node = ProxyNode(
                    protocol="trojan",
                    host=f"h-{i}.example.com",
                    port=443,
                    raw_link=f"trojan://{i}",
                    extra={"password": "p"},
                )
                storage.upsert_proxy(node)
                storage.update_test_result(node.normalized_key(), available=True, latency_ms=20)

            lock = threading.Lock()
            inflight = 0
            max_inflight = 0

            def purity_lookup(ip: str) -> tuple[float, str]:
                nonlocal inflight, max_inflight
                with lock:
                    inflight += 1
                    max_inflight = max(max_inflight, inflight)
                time.sleep(0.02)
                with lock:
                    inflight -= 1
                return 7.0, "Elevated"

            service = GeoIPService(
                storage=storage,
                resolver=lambda host: "2.2.2.2",
                geo_lookup=lambda ip: ("", ""),
                purity_lookup=purity_lookup,
            )
            report = service.enrich_ip_purity_batch(limit=12, concurrency=6, only_unchecked=False)
            self.assertEqual(report["updated"], 12)
            self.assertGreater(max_inflight, 1)

    def test_enrich_batch_skips_unavailable_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            n1 = ProxyNode(protocol="trojan", host="ok.example.com", port=443, raw_link="trojan://ok", extra={"password": "p"})
            n2 = ProxyNode(protocol="trojan", host="down.example.com", port=443, raw_link="trojan://down", extra={"password": "p"})
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.update_test_result(n1.normalized_key(), available=True, latency_ms=12)

            service = GeoIPService(
                storage=storage,
                resolver=lambda host: "1.1.1.1",
                geo_lookup=lambda ip: ("US", "LA"),
                purity_lookup=lambda ip: (1.0, "Low"),
            )
            report = service.enrich_batch(limit=10)
            self.assertEqual(report["requested"], 1)
            self.assertEqual(report["updated"], 1)


if __name__ == "__main__":
    unittest.main()
