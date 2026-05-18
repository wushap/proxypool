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

    def test_runtime_config_preserves_vless_reality_options(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            storage = SQLiteProxyStorage(base / "proxies.db")
            front = ProxyNode(
                protocol="vmess",
                host="45.192.101.134",
                port=9527,
                raw_link="vmess://front",
                extra={"uuid": "ae862e1d-3b8c-443a-027b-37c6c69ef43c"},
            )
            exit_node = ProxyNode(
                protocol="vless",
                host="aws-link9.liangxin1.xyz",
                port=23587,
                raw_link="vless://exit",
                extra={
                    "uuid": "502e73b5-8662-4332-8168-8ecdb8fc6b63",
                    "flow": "xtls-rprx-vision",
                    "packetEncoding": "xudp",
                    "sni": "iosapps.itunes.apple.com",
                    "fp": "ios",
                    "pbk": "public-key",
                    "sid": "short-id",
                    "allowInsecure": "0",
                    "security": "tls",
                },
            )
            storage.upsert_proxy(front)
            storage.upsert_proxy(exit_node)
            manager = SingBoxBackendManager(
                storage=storage,
                binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                routes_file=base / "routes.json",
                runtime_config_file=base / "runtime" / "singbox.json",
                log_file=base / "runtime" / "singbox.log",
                backend_engine="singbox",
            )
            manager.set_routes(
                [
                    SingBoxRoute(
                        inbound_port=40005,
                        inbound_type="http",
                        front_proxy_key=front.normalized_key(),
                        exit_proxy_key=exit_node.normalized_key(),
                    )
                ]
            )

            config = manager.build_runtime_config()
            outbound = next(item for item in config["outbounds"] if item.get("type") == "vless")
            self.assertEqual(outbound["flow"], "xtls-rprx-vision")
            self.assertEqual(outbound["packet_encoding"], "xudp")
            self.assertEqual(outbound["detour"], "out-0-hop-0")
            self.assertEqual(outbound["tls"]["server_name"], "iosapps.itunes.apple.com")
            self.assertFalse(outbound["tls"]["insecure"])
            self.assertEqual(outbound["tls"]["utls"]["fingerprint"], "ios")
            self.assertEqual(outbound["tls"]["reality"]["public_key"], "public-key")
            self.assertEqual(outbound["tls"]["reality"]["short_id"], "short-id")

    def test_backend_instances_are_persisted_and_reconciled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            storage = SQLiteProxyStorage(base / "proxies.db")
            manager = SingBoxBackendManager(
                storage=storage,
                binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                routes_file=base / "routes.json",
                runtime_config_file=base / "runtime" / "singbox.json",
                log_file=base / "runtime" / "singbox.log",
                backend_engine="singbox",
            )
            storage.upsert_backend_instance(
                instance_id="alpha",
                pid=12345,
                config_file=str(base / "runtime" / "singbox-alpha.json"),
                routes_file=str(base / "routes-alpha.json"),
                log_file=str(base / "runtime" / "singbox-alpha.log"),
                listen="127.0.0.1",
                ports=[1081, 1082],
                status="running",
            )

            with patch("proxypool.backend.singbox_manager._is_process_alive", return_value=True):
                instances = manager.list_instances()

            self.assertEqual(len(instances), 1)
            self.assertEqual(instances[0]["instance_id"], "alpha")
            self.assertEqual(instances[0]["status"], "running")
            self.assertEqual(instances[0]["ports"], [1081, 1082])

            with patch("proxypool.backend.singbox_manager._is_process_alive", return_value=False):
                instances = manager.list_instances()
            self.assertEqual(instances[0]["status"], "exited")

    def test_delete_backend_instance_removes_persisted_record(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            storage = SQLiteProxyStorage(base / "proxies.db")
            manager = SingBoxBackendManager(
                storage=storage,
                binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                routes_file=base / "routes.json",
                runtime_config_file=base / "runtime" / "singbox.json",
                log_file=base / "runtime" / "singbox.log",
                backend_engine="singbox",
            )
            storage.upsert_backend_instance(
                instance_id="alpha",
                pid=-1,
                config_file=str(base / "runtime" / "singbox-alpha.json"),
                routes_file=str(base / "routes-alpha.json"),
                log_file=str(base / "runtime" / "singbox-alpha.log"),
                listen="127.0.0.1",
                ports=[1081],
                status="stopped",
            )

            self.assertTrue(manager.delete_instance("alpha"))

            self.assertEqual(storage.list_backend_instances(), [])
            events = storage.list_backend_process_events(limit=5)
            self.assertEqual(events[0]["action"], "delete_instance")
            self.assertEqual(events[0]["result"], "success")

    def test_instance_routes_use_separate_routes_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            storage = SQLiteProxyStorage(base / "proxies.db")
            manager = SingBoxBackendManager(
                storage=storage,
                binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                routes_file=base / "routes.json",
                runtime_config_file=base / "runtime" / "singbox.json",
                log_file=base / "runtime" / "singbox.log",
                backend_engine="singbox",
            )

            manager.set_routes([SingBoxRoute(inbound_port=1081, exit_proxy_key="default-key")])
            manager.set_instance_routes("alpha", [SingBoxRoute(inbound_port=2081, exit_proxy_key="alpha-key")])

            self.assertEqual(manager.get_routes()[0].inbound_port, 1081)
            alpha_routes = manager.get_instance_routes("alpha")
            self.assertEqual(alpha_routes[0].inbound_port, 2081)
            self.assertEqual(alpha_routes[0].exit_proxy_key, "alpha-key")

    def test_create_backend_instance_is_persisted_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            storage = SQLiteProxyStorage(base / "proxies.db")
            manager = SingBoxBackendManager(
                storage=storage,
                binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                routes_file=base / "routes.json",
                runtime_config_file=base / "runtime" / "singbox.json",
                log_file=base / "runtime" / "singbox.log",
                backend_engine="singbox",
            )

            item = manager.create_instance("alpha")

            self.assertEqual(item["instance_id"], "alpha")
            self.assertEqual(item["status"], "stopped")
            self.assertEqual(item["pid"], -1)
            self.assertEqual(manager.list_instances()[0]["status"], "stopped")

    def test_updating_stopped_instance_routes_does_not_start_process(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            storage = SQLiteProxyStorage(base / "proxies.db")
            manager = SingBoxBackendManager(
                storage=storage,
                binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                routes_file=base / "routes.json",
                runtime_config_file=base / "runtime" / "singbox.json",
                log_file=base / "runtime" / "singbox.log",
                backend_engine="singbox",
            )
            manager.create_instance("alpha")

            with patch.object(manager, "start_instance") as start_instance:
                manager.set_instance_routes(
                    "alpha",
                    [SingBoxRoute(inbound_port=2081, exit_proxy_key="alpha-key")],
                    auto_restart=True,
                )

            start_instance.assert_not_called()
            instances = manager.list_instances()
            self.assertEqual(instances[0]["status"], "stopped")

    def test_default_listen_setting(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = SQLiteProxyStorage(Path(td) / "proxies.db")
            self.assertEqual(storage.get_backend_default_listen(), "127.0.0.1")
            self.assertEqual(storage.set_backend_default_listen("0.0.0.0"), "0.0.0.0")
            self.assertEqual(storage.get_backend_default_listen(), "0.0.0.0")

    def test_replace_failed_exit_proxy_updates_routes_and_records_event(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            storage = SQLiteProxyStorage(base / "proxies.db")
            old = ProxyNode(protocol="trojan", host="old.example.com", port=443, raw_link="trojan://old", extra={"password": "p"})
            new = ProxyNode(protocol="trojan", host="new.example.com", port=443, raw_link="trojan://new", extra={"password": "p"})
            storage.upsert_proxy(old)
            storage.upsert_proxy(new)
            manager = SingBoxBackendManager(
                storage=storage,
                binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                routes_file=base / "routes.json",
                runtime_config_file=base / "runtime" / "singbox.json",
                log_file=base / "runtime" / "singbox.log",
                backend_engine="singbox",
            )
            manager.set_routes([SingBoxRoute(inbound_port=1081, exit_proxy_key=old.normalized_key())])

            changed = manager.replace_failed_exit_proxy(old.normalized_key(), new.normalized_key())

            self.assertEqual(changed, 1)
            self.assertEqual(manager.get_routes()[0].exit_proxy_key, new.normalized_key())
            events = storage.list_backend_process_events(limit=5)
            self.assertEqual(events[0]["action"], "replace_proxy")
            self.assertIn(old.normalized_key(), events[0]["detail"])
            self.assertIn(new.normalized_key(), events[0]["detail"])

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
