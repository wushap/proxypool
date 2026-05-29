"""Tests for proxypool.backend.singbox_manager – covering initialization,
route management, status, lifecycle, helper functions, and error paths."""

from __future__ import annotations

import json
import socket
import subprocess
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from proxypool.backend.singbox_manager import (
    SingBoxBackendManager,
    SingBoxRoute,
    _is_bind_available,
    _is_process_alive,
    _is_tcp_open,
    _normalize_probe_host,
    _parse_curl_time_ms,
    _routes_listen_summary,
    _safe_instance_id,
    _validate_routes,
)
from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage(tmp_path: Path) -> SQLiteProxyStorage:
    return SQLiteProxyStorage(tmp_path / "test.db")


@pytest.fixture()
def manager(storage: SQLiteProxyStorage, tmp_path: Path) -> SingBoxBackendManager:
    return SingBoxBackendManager(
        storage=storage,
        binary="sing-box",
        test_url="https://example.com",
        routes_file=tmp_path / "routes.json",
        runtime_config_file=tmp_path / "runtime.json",
        log_file=tmp_path / "singbox.log",
    )


def _route(port: int = 10801, proxy_key: str = "p1", **kw: object) -> SingBoxRoute:
    return SingBoxRoute(inbound_port=port, proxy_key=proxy_key, **kw)


def _insert_proxy(
    stor: SQLiteProxyStorage,
    host: str = "1.2.3.4",
    port: int = 1080,
    protocol: str = "trojan",
    extra: dict | None = None,
) -> str:
    """Insert a proxy into storage and return its normalized_key."""
    if extra is None:
        extra = {"password": "testpass"}
    node = ProxyNode(
        protocol=protocol, host=host, port=port,
        raw_link=f"{protocol}://{host}:{port}",
        extra=extra,
    )
    stor.upsert_proxy(node)
    return node.normalized_key()


# ===== SingBoxRoute dataclass =====


class TestSingBoxRoute:
    def test_chain_keys_with_proxy_key(self) -> None:
        r = SingBoxRoute(inbound_port=8080, proxy_key="pk1")
        assert r.chain_keys() == ["pk1"]

    def test_chain_keys_with_chain(self) -> None:
        r = SingBoxRoute(
            inbound_port=8080,
            front_proxy_key="f1",
            middle_proxy_key="m1",
            exit_proxy_key="e1",
        )
        assert r.chain_keys() == ["f1", "m1", "e1"]

    def test_chain_keys_partial_chain(self) -> None:
        r = SingBoxRoute(inbound_port=8080, front_proxy_key="f1", exit_proxy_key="e1")
        assert r.chain_keys() == ["f1", "e1"]

    def test_chain_keys_empty_when_no_keys(self) -> None:
        r = SingBoxRoute(inbound_port=8080)
        assert r.chain_keys() == []

    def test_chain_keys_blank_proxy_key(self) -> None:
        r = SingBoxRoute(inbound_port=8080, proxy_key="   ")
        assert r.chain_keys() == []

    def test_chain_keys_blank_chain_falls_back_to_proxy(self) -> None:
        r = SingBoxRoute(
            inbound_port=8080,
            proxy_key="pk1",
            front_proxy_key="   ",
            middle_proxy_key="",
            exit_proxy_key="  ",
        )
        assert r.chain_keys() == ["pk1"]

    def test_defaults(self) -> None:
        r = SingBoxRoute(inbound_port=1)
        assert r.inbound_type == "http"
        assert r.listen == "127.0.0.1"
        assert r.proxy_key == ""


# ===== Initialization =====


class TestManagerInit:
    def test_init_creates_directories(self, tmp_path: Path) -> None:
        db = SQLiteProxyStorage(tmp_path / "db.sqlite")
        routes = tmp_path / "sub" / "routes.json"
        config = tmp_path / "sub" / "config.json"
        log = tmp_path / "sub" / "log.log"
        mgr = SingBoxBackendManager(
            storage=db, binary="x", test_url="u",
            routes_file=routes, runtime_config_file=config, log_file=log,
        )
        assert routes.parent.exists()
        assert config.parent.exists()
        assert log.parent.exists()
        assert mgr.auto_restart_max == 3

    def test_init_auto_restart_max_clamped(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
            auto_restart_max=-5,
        )
        assert mgr.auto_restart_max == 0


# ===== Route management =====


class TestRouteManagement:
    def test_set_and_get_routes(self, manager: SingBoxBackendManager) -> None:
        routes = [_route(10801), _route(10802, "p2")]
        manager.set_routes(routes)
        got = manager.get_routes()
        assert len(got) == 2
        assert got[0].inbound_port == 10801
        assert got[1].proxy_key == "p2"

    def test_get_routes_empty_when_no_file(self, manager: SingBoxBackendManager) -> None:
        assert manager.get_routes() == []

    def test_set_routes_invalid_port(self, manager: SingBoxBackendManager) -> None:
        with pytest.raises(RuntimeError, match="invalid inbound_port"):
            manager.set_routes([_route(0)])

    def test_set_routes_duplicate_port(self, manager: SingBoxBackendManager) -> None:
        with pytest.raises(RuntimeError, match="duplicated inbound_port"):
            manager.set_routes([_route(10801), _route(10801, "p2")])

    def test_set_routes_no_proxy(self, manager: SingBoxBackendManager) -> None:
        with pytest.raises(RuntimeError, match="proxy_key"):
            manager.set_routes([SingBoxRoute(inbound_port=10801)])

    def test_set_routes_auto_restart_not_running(self, manager: SingBoxBackendManager) -> None:
        """auto_restart=True but process not running should just write routes."""
        manager.set_routes([_route(10801)], auto_restart=True)
        assert len(manager.get_routes()) == 1


# ===== Instance routes =====


class TestInstanceRoutes:
    def test_instance_routes_fallback_to_global(self, manager: SingBoxBackendManager) -> None:
        manager.set_routes([_route(10801)])
        got = manager.get_instance_routes("nonexistent")
        assert len(got) == 1

    def test_set_and_get_instance_routes(self, manager: SingBoxBackendManager) -> None:
        routes = [_route(20801)]
        manager.set_instance_routes("inst1", routes)
        got = manager.get_instance_routes("inst1")
        assert len(got) == 1
        assert got[0].inbound_port == 20801

    def test_instance_routes_file_naming(self, manager: SingBoxBackendManager) -> None:
        p = manager._instance_routes_file("myinst")
        assert "myinst" in p.name


# ===== validate_routes helper =====


class TestValidateRoutes:
    def test_valid_routes(self) -> None:
        _validate_routes([_route(10801), _route(10802, "p2")])

    def test_port_zero(self) -> None:
        with pytest.raises(RuntimeError, match="invalid inbound_port"):
            _validate_routes([_route(0)])

    def test_port_over_65535(self) -> None:
        with pytest.raises(RuntimeError, match="invalid inbound_port"):
            _validate_routes([_route(65536)])

    def test_duplicate_ports(self) -> None:
        with pytest.raises(RuntimeError, match="duplicated"):
            _validate_routes([_route(10801), _route(10801, "p2")])

    def test_no_proxy_keys(self) -> None:
        with pytest.raises(RuntimeError, match="proxy_key"):
            _validate_routes([SingBoxRoute(inbound_port=10801)])


# ===== Helper functions =====


class TestHelpers:
    def test_parse_curl_time_ms_normal(self) -> None:
        assert _parse_curl_time_ms("0.123") == 123

    def test_parse_curl_time_ms_empty(self) -> None:
        assert _parse_curl_time_ms("") is None

    def test_parse_curl_time_ms_none_str(self) -> None:
        assert _parse_curl_time_ms("not_a_number") is None

    def test_normalize_probe_host_empty(self) -> None:
        assert _normalize_probe_host("") == "127.0.0.1"

    def test_normalize_probe_host_zero(self) -> None:
        assert _normalize_probe_host("0.0.0.0") == "127.0.0.1"

    def test_normalize_probe_host_ipv6(self) -> None:
        assert _normalize_probe_host("::") == "127.0.0.1"

    def test_normalize_probe_host_normal(self) -> None:
        assert _normalize_probe_host("10.0.0.1") == "10.0.0.1"

    def test_normalize_probe_host_whitespace(self) -> None:
        assert _normalize_probe_host("  10.0.0.1  ") == "10.0.0.1"

    def test_is_process_alive_negative(self) -> None:
        assert _is_process_alive(-1) is False

    def test_is_process_alive_zero(self) -> None:
        assert _is_process_alive(0) is False

    def test_is_process_alive_nonexistent(self) -> None:
        assert _is_process_alive(999999999) is False

    def test_is_process_alive_current(self) -> None:
        import os
        assert _is_process_alive(os.getpid()) is True

    def test_safe_instance_id_normal(self) -> None:
        assert _safe_instance_id("my-inst_1") == "my-inst_1"

    def test_safe_instance_id_empty(self) -> None:
        assert _safe_instance_id("") == "default"

    def test_safe_instance_id_none(self) -> None:
        assert _safe_instance_id(None) == "default"  # type: ignore[arg-type]

    def test_safe_instance_id_strips_special(self) -> None:
        result = _safe_instance_id("a@b#c")
        assert result == "a-b-c"

    def test_safe_instance_id_truncates(self) -> None:
        long_id = "x" * 100
        assert len(_safe_instance_id(long_id)) == 80

    def test_routes_listen_summary_empty(self) -> None:
        assert _routes_listen_summary([]) == "127.0.0.1"

    def test_routes_listen_summary_single(self) -> None:
        r = _routes_listen_summary([SingBoxRoute(inbound_port=1, listen="10.0.0.1")])
        assert r == "10.0.0.1"

    def test_routes_listen_summary_dedup(self) -> None:
        r = _routes_listen_summary([
            SingBoxRoute(inbound_port=1, listen="10.0.0.1"),
            SingBoxRoute(inbound_port=2, listen="10.0.0.1"),
            SingBoxRoute(inbound_port=3, listen="192.168.1.1"),
        ])
        assert "10.0.0.1" in r
        assert "192.168.1.1" in r

    def test_is_bind_available_free_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        assert _is_bind_available("127.0.0.1", port) is True

    def test_is_bind_available_occupied(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            port = s.getsockname()[1]
            assert _is_bind_available("127.0.0.1", port) is False

    def test_is_tcp_open_closed(self) -> None:
        assert _is_tcp_open("127.0.0.1", 1, timeout_sec=0.1) is False


# ===== Status =====


class TestStatus:
    def test_status_not_running(self, manager: SingBoxBackendManager) -> None:
        s = manager.status()
        assert s["backend"] == "singbox"
        assert s["running"] is False
        assert s["pid"] == -1
        assert s["auto_restart_max"] == 3
        assert s["auto_restart_attempts"] == 0
        assert "routes_count" in s
        assert "instances" in s

    def test_is_running_false_initially(self, manager: SingBoxBackendManager) -> None:
        assert manager.is_running() is False

    def test_is_running_cleans_dead_process(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = 1  # exited
        manager._process = proc
        assert manager.is_running() is False
        assert manager._process is None

    def test_is_running_true_with_live_process(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None  # still running
        proc.pid = 12345
        manager._process = proc
        assert manager.is_running() is True
        assert manager._pid_state == 12345


# ===== Start/Stop lifecycle (mocked) =====


class TestLifecycle:
    def test_stop_when_not_running(self, manager: SingBoxBackendManager) -> None:
        manager.stop()

    def test_stop_instance_not_running(self, manager: SingBoxBackendManager) -> None:
        manager.stop_instance("inst1")

    def test_stop_running_process(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 12345
        manager._process = proc
        manager._processes["default"] = proc
        manager.stop()
        proc.terminate.assert_called_once()
        proc.wait.assert_called()
        assert manager._process is None

    def test_stop_already_exited(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = 1  # already exited
        proc.pid = 12345
        manager._process = proc
        manager._processes["default"] = proc
        manager.stop()
        assert manager._process is None

    def test_stop_timeout_kills(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 12345
        proc.wait.side_effect = [subprocess.TimeoutExpired("cmd", 2.0), None]
        manager._process = proc
        manager._processes["default"] = proc
        manager.stop()
        proc.kill.assert_called_once()

    def test_start_unsupported_engine(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        mgr = SingBoxBackendManager(
            storage=storage, binary="sing-box", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
            backend_engine="mihomo",
        )
        with pytest.raises(RuntimeError, match="not supported"):
            mgr.start()

    def test_start_binary_not_found(self, manager: SingBoxBackendManager) -> None:
        manager.set_routes([_route(10801)])
        with pytest.raises(RuntimeError, match="binary not found"):
            manager.start()

    def test_start_ports_occupied(self, manager: SingBoxBackendManager) -> None:
        manager.set_routes([_route(10801)])
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 10801))
        s.listen(1)
        try:
            with pytest.raises(RuntimeError, match="already in use"):
                manager.start()
        finally:
            s.close()

    def test_start_already_running(self, manager: SingBoxBackendManager) -> None:
        """If the process is already running, start_instance is a noop."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 9999
        manager._processes["default"] = proc
        manager.start_instance("default")

    def test_start_failure_terminates_process(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        """If process launch fails after Popen, cleanup terminates the process."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="sing-box", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
        )
        key = _insert_proxy(storage, extra={"password": "testpass"})
        mgr.set_routes([SingBoxRoute(inbound_port=10801, proxy_key=key)])
        proc_mock = MagicMock(spec=subprocess.Popen)
        proc_mock.poll.return_value = None
        proc_mock.pid = 1111
        with patch("shutil.which", return_value="/usr/bin/sing-box"), \
             patch("subprocess.Popen", return_value=proc_mock), \
             patch.object(mgr, "_wait_inbound_ports_ready", side_effect=RuntimeError("startup timeout")), \
             patch.object(mgr, "_assert_inbound_ports_available"):
            with pytest.raises(RuntimeError, match="startup timeout"):
                mgr.start_instance("default")
            proc_mock.terminate.assert_called()

    def test_restart(self, manager: SingBoxBackendManager) -> None:
        """restart() calls stop then start."""
        with patch.object(manager, "stop") as mock_stop, \
             patch.object(manager, "start") as mock_start:
            manager.restart()
            mock_stop.assert_called_once()
            mock_start.assert_called_once()


# ===== build_runtime_config =====


class TestBuildRuntimeConfig:
    def test_build_config_with_proxy(self, storage: SQLiteProxyStorage) -> None:
        key = _insert_proxy(storage)
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=Path("/tmp/r.json"),
            runtime_config_file=Path("/tmp/c.json"),
            log_file=Path("/tmp/l.log"),
        )
        routes = [SingBoxRoute(inbound_port=10801, proxy_key=key)]
        cfg = mgr.build_runtime_config(routes)
        assert "inbounds" in cfg
        assert "outbounds" in cfg
        assert cfg["inbounds"][0]["type"] == "http"
        assert cfg["inbounds"][0]["listen_port"] == 10801

    def test_build_config_socks_inbound(self, storage: SQLiteProxyStorage) -> None:
        key = _insert_proxy(storage)
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=Path("/tmp/r.json"),
            runtime_config_file=Path("/tmp/c.json"),
            log_file=Path("/tmp/l.log"),
        )
        routes = [SingBoxRoute(inbound_port=10801, proxy_key=key, inbound_type="socks")]
        cfg = mgr.build_runtime_config(routes)
        assert cfg["inbounds"][0]["type"] == "socks"

    def test_build_config_unsupported_inbound_type(self, storage: SQLiteProxyStorage) -> None:
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=Path("/tmp/r.json"),
            runtime_config_file=Path("/tmp/c.json"),
            log_file=Path("/tmp/l.log"),
        )
        routes = [SingBoxRoute(inbound_port=10801, proxy_key="p1", inbound_type="grpc")]
        with pytest.raises(RuntimeError, match="unsupported inbound_type"):
            mgr.build_runtime_config(routes)

    def test_build_config_proxy_not_found(self, storage: SQLiteProxyStorage) -> None:
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=Path("/tmp/r.json"),
            runtime_config_file=Path("/tmp/c.json"),
            log_file=Path("/tmp/l.log"),
        )
        routes = [SingBoxRoute(inbound_port=10801, proxy_key="nonexistent")]
        with pytest.raises(RuntimeError, match="proxy not found"):
            mgr.build_runtime_config(routes)

    def test_build_config_chain(self, storage: SQLiteProxyStorage) -> None:
        keys = []
        for port in (1081, 1082, 1083):
            keys.append(_insert_proxy(storage, host="1.2.3.4", port=port))
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=Path("/tmp/r.json"),
            runtime_config_file=Path("/tmp/c.json"),
            log_file=Path("/tmp/l.log"),
        )
        routes = [SingBoxRoute(
            inbound_port=10801, front_proxy_key=keys[0],
            middle_proxy_key=keys[1], exit_proxy_key=keys[2],
        )]
        cfg = mgr.build_runtime_config(routes)
        outbounds = [o for o in cfg["outbounds"] if o.get("type") != "direct"]
        assert len(outbounds) == 3
        # Middle hop should have detour to front
        assert "detour" in outbounds[1]

    def test_build_config_uses_routes_param(self, storage: SQLiteProxyStorage) -> None:
        key = _insert_proxy(storage)
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=Path("/tmp/r.json"),
            runtime_config_file=Path("/tmp/c.json"),
            log_file=Path("/tmp/l.log"),
        )
        cfg = mgr.build_runtime_config(routes=[SingBoxRoute(inbound_port=9999, proxy_key=key)])
        assert cfg["inbounds"][0]["listen_port"] == 9999

    def test_build_config_direct_outbound_appended(self, storage: SQLiteProxyStorage) -> None:
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=Path("/tmp/r.json"),
            runtime_config_file=Path("/tmp/c.json"),
            log_file=Path("/tmp/l.log"),
        )
        cfg = mgr.build_runtime_config(routes=[])
        outbounds = cfg["outbounds"]
        assert outbounds[-1] == {"type": "direct", "tag": "direct"}


# ===== Instance management =====


class TestInstanceManagement:
    def test_create_instance_new(self, manager: SingBoxBackendManager) -> None:
        result = manager.create_instance("myinst")
        assert result["instance_id"] == "myinst"
        assert result["status"] == "stopped"

    def test_create_instance_existing(self, manager: SingBoxBackendManager) -> None:
        manager.create_instance("myinst")
        result = manager.create_instance("myinst")
        assert result["instance_id"] == "myinst"

    def test_list_instances(self, manager: SingBoxBackendManager) -> None:
        manager.create_instance("a")
        manager.create_instance("b")
        instances = manager.list_instances()
        ids = {i["instance_id"] for i in instances}
        assert "a" in ids
        assert "b" in ids

    def test_delete_instance(self, manager: SingBoxBackendManager) -> None:
        manager.create_instance("del1")
        assert manager.delete_instance("del1") is True

    def test_delete_nonexistent_instance(self, manager: SingBoxBackendManager) -> None:
        assert manager.delete_instance("ghost") is False


# ===== Health check =====


class TestHealthCheck:
    def test_health_not_running(self, manager: SingBoxBackendManager) -> None:
        h = manager.health_check()
        assert h["running"] is False
        assert h["ok"] is False

    def test_health_process_exited(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = 1  # exited
        proc.pid = 5555
        manager._process = proc
        h = manager.health_check()
        assert h["running"] is False
        assert h["ok"] is False
        assert h["reason"] == "process exited"

    def test_health_running_but_ports_down(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 5555
        manager._process = proc
        manager.set_routes([SingBoxRoute(inbound_port=59999, proxy_key="p1")])
        h = manager.health_check(timeout_sec=0.3)
        assert h["ok"] is False

    def test_health_auto_restart_not_running(self, manager: SingBoxBackendManager) -> None:
        h = manager.health_check(auto_restart=True)
        assert h["running"] is False
        assert h["restart_attempted"] is False  # no routes -> no restart

    def test_health_auto_restart_disabled(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
            auto_restart_max=0,
        )
        mgr.set_routes([_route(10801)])
        h = mgr.health_check(auto_restart=True)
        assert "auto-restart disabled" in h["reason"]

    def test_health_auto_restart_limit_reached(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
            auto_restart_max=1,
        )
        mgr.set_routes([_route(10801)])
        mgr._auto_restart_attempts = 1
        h = mgr.health_check(auto_restart=True)
        assert "limit reached" in h["reason"]

    def test_health_auto_restart_start_fails(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
            auto_restart_max=3,
        )
        mgr.set_routes([_route(10801)])
        with patch.object(mgr, "start", side_effect=RuntimeError("fail")):
            h = mgr.health_check(auto_restart=True)
            assert h["restart_attempted"] is True
            assert h["ok"] is False

    def test_health_auto_restart_success(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
            auto_restart_max=3,
        )
        mgr.set_routes([_route(10801)])
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = None
        mock_proc.pid = 7777

        def fake_start() -> None:
            mgr._processes["default"] = mock_proc
            mgr._process = mock_proc

        with patch.object(mgr, "start", side_effect=fake_start):
            h = mgr.health_check(auto_restart=True)
            assert h["running"] is True
            assert h["ok"] is True

    def test_health_auto_restart_process_exited(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        """Health check when process has exited + auto_restart."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
            auto_restart_max=3,
        )
        mgr.set_routes([_route(10801)])
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = 1
        proc.pid = 8888
        mgr._process = proc
        h = mgr.health_check(auto_restart=True)
        assert h["restart_attempted"] is True

    def test_health_check_ports_down_auto_restart_fails(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        """Ports unreachable + auto_restart -> restart fails."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
            auto_restart_max=3,
        )
        mgr.set_routes([SingBoxRoute(inbound_port=59999, proxy_key="p1")])
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 9999
        mgr._process = proc
        with patch.object(mgr, "start", side_effect=RuntimeError("cannot start")):
            h = mgr.health_check(timeout_sec=0.3, auto_restart=True)
            assert h["restart_attempted"] is True
            assert h["ok"] is False

    def test_health_recovered_event(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        """When _last_health_ok was False and now ports are up, records recovered event."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
        )
        mgr.set_routes([_route(10801)])
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 11111
        mgr._process = proc
        mgr._last_health_ok = False
        with patch.object(mgr, "_wait_inbound_ports_ready", return_value=True):
            h = mgr.health_check()
            assert h["ok"] is True


# ===== Latency measurement =====


class TestLatencyMeasurement:
    def test_measure_route_latency_not_running(self, manager: SingBoxBackendManager) -> None:
        r = _route(10801)
        result = manager.measure_route_latency(r)
        assert result["available"] is False
        assert "not running" in result["error"]

    def test_measure_route_latency_unsupported_type(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 12345
        manager._process = proc
        r = SingBoxRoute(inbound_port=10801, proxy_key="p1", inbound_type="grpc")
        result = manager.measure_route_latency(r)
        assert result["available"] is False
        assert "unsupported" in result["error"]

    def test_measure_all_routes_empty(self, manager: SingBoxBackendManager) -> None:
        assert manager.measure_all_routes_latency() == []

    def test_measure_route_latency_curl_not_found(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 12345
        manager._process = proc
        with patch("shutil.which", return_value=None):
            r = _route(10801)
            result = manager.measure_route_latency(r)
            assert result["available"] is False
            assert "curl not found" in result["error"]

    def test_measure_route_latency_curl_fails(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 12345
        manager._process = proc
        completed = MagicMock()
        completed.returncode = 7
        completed.stderr = "connection refused"
        completed.stdout = ""
        with patch("shutil.which", return_value="/usr/bin/curl"), \
             patch("subprocess.run", return_value=completed):
            r = _route(10801)
            result = manager.measure_route_latency(r)
            assert result["available"] is False

    def test_measure_route_latency_curl_success(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 12345
        manager._process = proc
        completed = MagicMock()
        completed.returncode = 0
        completed.stderr = ""
        completed.stdout = "0.042"
        with patch("shutil.which", return_value="/usr/bin/curl"), \
             patch("subprocess.run", return_value=completed):
            r = _route(10801)
            result = manager.measure_route_latency(r)
            assert result["available"] is True
            assert result["latency_ms"] == 42

    def test_measure_route_latency_curl_bad_output(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 12345
        manager._process = proc
        completed = MagicMock()
        completed.returncode = 0
        completed.stderr = ""
        completed.stdout = "garbage"
        with patch("shutil.which", return_value="/usr/bin/curl"), \
             patch("subprocess.run", return_value=completed):
            r = _route(10801)
            result = manager.measure_route_latency(r)
            assert result["available"] is False
            assert "invalid curl output" in result["error"]

    def test_measure_route_latency_socks_proxy_url(self, manager: SingBoxBackendManager) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 12345
        manager._process = proc
        completed = MagicMock()
        completed.returncode = 0
        completed.stderr = ""
        completed.stdout = "0.050"
        with patch("shutil.which", return_value="/usr/bin/curl"), \
             patch("subprocess.run", return_value=completed) as mock_run:
            r = SingBoxRoute(inbound_port=10801, proxy_key="p1", inbound_type="socks")
            manager.measure_route_latency(r)
            call_args = mock_run.call_args[0][0]
            assert any("socks5h://" in str(a) for a in call_args)

    def test_measure_all_routes_with_latency(self, manager: SingBoxBackendManager) -> None:
        manager.set_routes([_route(10801), _route(10802, "p2")])
        with patch.object(manager, "measure_route_latency") as mock_lat:
            mock_lat.return_value = {
                "available": True, "latency_ms": 100,
                "route_index": 0, "error": "", "checked_at": "",
                "inbound_port": 10801, "proxy_key": "p1",
                "front_proxy_key": "", "middle_proxy_key": "",
                "exit_proxy_key": "", "inbound_type": "http", "listen": "127.0.0.1",
            }
            results = manager.measure_all_routes_latency()
            assert len(results) == 2
            assert mock_lat.call_count == 2


# ===== replace_failed_exit_proxy =====


class TestReplaceFailedExitProxy:
    def test_replace_empty_keys(self, manager: SingBoxBackendManager) -> None:
        assert manager.replace_failed_exit_proxy("", "new") == 0
        assert manager.replace_failed_exit_proxy("old", "") == 0
        assert manager.replace_failed_exit_proxy("a", "a") == 0

    def test_replace_new_proxy_not_in_db(self, manager: SingBoxBackendManager) -> None:
        manager.set_routes([SingBoxRoute(
            inbound_port=10801, proxy_key="p1", exit_proxy_key="old",
        )])
        assert manager.replace_failed_exit_proxy("old", "nonexistent") == 0

    def test_replace_no_matching_route(self, manager: SingBoxBackendManager, storage: SQLiteProxyStorage) -> None:
        new_key = _insert_proxy(storage)
        manager.set_routes([SingBoxRoute(
            inbound_port=10801, proxy_key="p1", exit_proxy_key="different",
        )])
        assert manager.replace_failed_exit_proxy("old", new_key) == 0

    def test_replace_matching_exit_proxy(self, manager: SingBoxBackendManager, storage: SQLiteProxyStorage) -> None:
        new_key = _insert_proxy(storage)
        manager.set_routes([SingBoxRoute(
            inbound_port=10801, proxy_key="p1", exit_proxy_key="old",
        )])
        changed = manager.replace_failed_exit_proxy("old", new_key)
        assert changed == 1
        routes = manager.get_routes()
        assert routes[0].exit_proxy_key == new_key

    def test_replace_matching_proxy_key_fallback(self, manager: SingBoxBackendManager, storage: SQLiteProxyStorage) -> None:
        new_key = _insert_proxy(storage)
        manager.set_routes([SingBoxRoute(
            inbound_port=10801, proxy_key="old",
        )])
        changed = manager.replace_failed_exit_proxy("old", new_key)
        assert changed == 1
        assert manager.get_routes()[0].proxy_key == new_key


# ===== list_instances edge cases =====


class TestListInstancesEdgeCases:
    def test_list_instances_marks_dead_running_as_exited(self, manager: SingBoxBackendManager) -> None:
        """list_instances detects stale 'running' instances with dead PIDs."""
        manager.storage.upsert_backend_instance(
            instance_id="stale",
            pid=999999999,
            config_file="/tmp/c.json",
            routes_file="/tmp/r.json",
            log_file="/tmp/l.log",
            listen="127.0.0.1",
            ports=[10801],
            status="running",
        )
        instances = manager.list_instances()
        stale = [i for i in instances if i["instance_id"] == "stale"]
        assert len(stale) == 1
        assert stale[0]["status"] == "exited"


# ===== _record_process_event edge cases =====


class TestRecordProcessEvent:
    def test_record_event_does_not_propagate_exceptions(self, manager: SingBoxBackendManager) -> None:
        """If record_backend_process_event raises, the caller should not fail."""
        with patch.object(
            manager.storage, "record_backend_process_event",
            side_effect=RuntimeError("db error"),
        ):
            manager._record_process_event(action="test", pid=1, result="ok")


# ===== async wrappers =====


class TestAsyncWrappers:
    @pytest.mark.anyio
    async def test_stop_async(self, manager: SingBoxBackendManager) -> None:
        await manager.stop_async()

    @pytest.mark.anyio
    async def test_start_async_binary_missing(self, manager: SingBoxBackendManager) -> None:
        with pytest.raises(RuntimeError, match="binary not found"):
            await manager.start_async()

    @pytest.mark.anyio
    async def test_health_check_async(self, manager: SingBoxBackendManager) -> None:
        h = await manager.health_check_async()
        assert h["running"] is False

    @pytest.mark.anyio
    async def test_measure_all_routes_latency_async(self, manager: SingBoxBackendManager) -> None:
        results = await manager.measure_all_routes_latency_async()
        assert results == []

    @pytest.mark.anyio
    async def test_measure_route_latency_async(self, manager: SingBoxBackendManager) -> None:
        r = _route(10801)
        result = await manager.measure_route_latency_async(r)
        assert result["available"] is False
