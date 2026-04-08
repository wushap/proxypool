import tempfile
import unittest
import socket
from unittest.mock import patch
from pathlib import Path

from proxypool.backend.singbox_manager import SingBoxBackendManager, SingBoxRoute
from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


class TestSingBoxBackendManager(unittest.TestCase):
    def test_routes_and_runtime_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            storage = SQLiteProxyStorage(base / "proxies.db")

            n1 = ProxyNode(
                protocol="trojan",
                host="a.example.com",
                port=443,
                raw_link="trojan://a",
                extra={"password": "p1"},
            )
            n2 = ProxyNode(
                protocol="ss",
                host="b.example.com",
                port=8388,
                raw_link="ss://b",
                extra={"cipher": "aes-128-gcm", "password": "p2"},
            )
            n3 = ProxyNode(
                protocol="trojan",
                host="c.example.com",
                port=443,
                raw_link="trojan://c",
                extra={"password": "p3"},
            )
            n4 = ProxyNode(
                protocol="trojan",
                host="d.example.com",
                port=443,
                raw_link="trojan://d",
                extra={"password": "p4"},
            )
            storage.upsert_proxy(n1)
            storage.upsert_proxy(n2)
            storage.upsert_proxy(n3)
            storage.upsert_proxy(n4)

            routes = [
                SingBoxRoute(inbound_port=1081, proxy_key=n1.normalized_key(), inbound_type="socks"),
                SingBoxRoute(
                    inbound_port=1082,
                    inbound_type="http",
                    front_proxy_key=n2.normalized_key(),
                    middle_proxy_key=n3.normalized_key(),
                    exit_proxy_key=n4.normalized_key(),
                ),
            ]

            manager = SingBoxBackendManager(
                storage=storage,
                binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                routes_file=base / "routes.json",
                runtime_config_file=base / "runtime" / "singbox.json",
                log_file=base / "runtime" / "singbox.log",
                backend_engine="singbox",
            )

            manager.set_routes(routes)
            loaded = manager.get_routes()
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].inbound_port, 1081)

            config = manager.build_runtime_config()
            self.assertEqual(len(config["inbounds"]), 2)
            self.assertEqual(len(config["outbounds"]), 5)  # 1 + 3 chain + direct
            self.assertEqual(config["route"]["rules"][0]["outbound"], "out-0-hop-0")
            self.assertEqual(config["route"]["rules"][1]["outbound"], "out-1-hop-2")
            self.assertEqual(config["outbounds"][3]["detour"], "out-1-hop-1")
            self.assertEqual(config["outbounds"][2]["detour"], "out-1-hop-0")

            status = manager.status()
            self.assertEqual(status["backend"], "singbox")
            self.assertFalse(status["running"])
            self.assertEqual(status["pid"], -1)
            self.assertEqual(status["routes_count"], 2)

            latency_items = manager.measure_all_routes_latency(timeout_sec=2)
            self.assertEqual(len(latency_items), 2)
            self.assertEqual(latency_items[0]["route_index"], 0)
            self.assertEqual(latency_items[1]["route_index"], 1)
            self.assertFalse(latency_items[0]["available"])
            self.assertIn("not running", latency_items[0]["error"])

    def test_start_rejects_occupied_inbound_port(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            storage = SQLiteProxyStorage(base / "proxies.db")
            node = ProxyNode(
                protocol="trojan",
                host="a.example.com",
                port=443,
                raw_link="trojan://a",
                extra={"password": "p1"},
            )
            storage.upsert_proxy(node)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            try:
                port = int(sock.getsockname()[1])
                manager = SingBoxBackendManager(
                    storage=storage,
                    binary="sh",
                    test_url="https://www.cloudflare.com/cdn-cgi/trace",
                    routes_file=base / "routes.json",
                    runtime_config_file=base / "runtime" / "singbox.json",
                    log_file=base / "runtime" / "singbox.log",
                    backend_engine="singbox",
                )
                manager.set_routes([SingBoxRoute(inbound_port=port, proxy_key=node.normalized_key())])
                with self.assertRaises(RuntimeError) as ctx:
                    manager.start()
                self.assertIn("already in use", str(ctx.exception))
                events = storage.list_backend_process_events(limit=5)
                self.assertGreaterEqual(len(events), 1)
                self.assertEqual(events[0]["action"], "start")
                self.assertEqual(events[0]["result"], "failed")
            finally:
                sock.close()

    def test_health_check_auto_restart_respects_max_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            storage = SQLiteProxyStorage(base / "proxies.db")
            node = ProxyNode(
                protocol="trojan",
                host="a.example.com",
                port=443,
                raw_link="trojan://a",
                extra={"password": "p1"},
            )
            storage.upsert_proxy(node)
            manager = SingBoxBackendManager(
                storage=storage,
                binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                routes_file=base / "routes.json",
                runtime_config_file=base / "runtime" / "singbox.json",
                log_file=base / "runtime" / "singbox.log",
                backend_engine="singbox",
                auto_restart_max=2,
            )
            manager.set_routes([SingBoxRoute(inbound_port=1081, proxy_key=node.normalized_key())])
            with patch.object(manager, "start", side_effect=RuntimeError("boot failed")) as mocked_start:
                r1 = manager.health_check(auto_restart=True)
                r2 = manager.health_check(auto_restart=True)
                r3 = manager.health_check(auto_restart=True)
            self.assertEqual(mocked_start.call_count, 2)
            self.assertFalse(r1["ok"])
            self.assertTrue(r1.get("restart_attempted"))
            self.assertFalse(r2["ok"])
            self.assertTrue(r2.get("restart_attempted"))
            self.assertFalse(r3["ok"])
            self.assertFalse(r3.get("restart_attempted"))
            self.assertIn("limit reached", str(r3.get("reason")))


if __name__ == "__main__":
    unittest.main()
