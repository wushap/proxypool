"""Deep edge-case tests for proxypool.backend.singbox_manager to push coverage above 94%."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from proxypool.backend.singbox_manager import (
    SingBoxBackendManager,
    SingBoxRoute,
    _is_bind_available,
    _is_tcp_open,
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
    if extra is None:
        extra = {"password": "testpass"}
    node = ProxyNode(
        protocol=protocol, host=host, port=port,
        raw_link=f"{protocol}://{host}:{port}",
        extra=extra,
    )
    stor.upsert_proxy(node)
    return node.normalized_key()


# ===== Line 79: set_routes with auto_restart when running =====


class TestSetRoutesAutoRestart:
    def test_set_routes_auto_restart_when_running(self, manager: SingBoxBackendManager) -> None:
        """Line 79: set_routes with auto_restart=True triggers restart when running."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 12345
        manager._process = proc
        manager._processes["default"] = proc
        with patch.object(manager, "restart") as mock_restart:
            manager.set_routes([_route(10801)], auto_restart=True)
            mock_restart.assert_called_once()


# ===== Lines 106-107: set_instance_routes auto_restart when running =====


class TestSetInstanceRoutesAutoRestart:
    def test_set_instance_routes_auto_restart_was_running(
        self, manager: SingBoxBackendManager, storage: SQLiteProxyStorage
    ) -> None:
        """Lines 106-107: set_instance_routes with auto_restart stops and starts."""
        key = _insert_proxy(storage)
        manager.create_instance("inst1")
        # Set status to "running" in storage so was_running is True
        storage.upsert_backend_instance(
            instance_id="inst1", pid=12345, config_file="/tmp/c.json",
            routes_file="/tmp/r.json", log_file="/tmp/l.log",
            listen="127.0.0.1", ports=[10801], status="running",
        )
        with patch.object(manager, "stop_instance") as mock_stop, \
             patch.object(manager, "start_instance") as mock_start:
            manager.set_instance_routes("inst1", [_route(10801)], auto_restart=True)
            mock_stop.assert_called_once()
            mock_start.assert_called_once()


# ===== Line 251: build_singbox_outbound returns None =====


class TestBuildConfigUnsupportedProxy:
    def test_build_config_unsupported_outbound(self, storage: SQLiteProxyStorage) -> None:
        """Line 251: proxy exists but build_singbox_outbound returns None."""
        key = _insert_proxy(storage)
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=Path("/tmp/r.json"),
            runtime_config_file=Path("/tmp/c.json"),
            log_file=Path("/tmp/l.log"),
        )
        routes = [SingBoxRoute(inbound_port=10801, proxy_key=key)]
        with patch("proxypool.backend.singbox_manager.build_singbox_outbound", return_value=None):
            with pytest.raises(RuntimeError, match="unsupported for sing-box"):
                mgr.build_runtime_config(routes)


# ===== Lines 316-335: start_instance success path =====


class TestStartInstanceSuccess:
    def test_start_instance_success(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        """Lines 316-335: Full success path for start_instance."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="sing-box", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
        )
        key = _insert_proxy(storage)
        mgr.set_routes([SingBoxRoute(inbound_port=10801, proxy_key=key)])

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = None
        mock_proc.pid = 9999

        with patch("shutil.which", return_value="/usr/bin/sing-box"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(mgr, "_wait_inbound_ports_ready", return_value=True), \
             patch.object(mgr, "_assert_inbound_ports_available"):
            mgr.start_instance("default")

        assert mgr._process is mock_proc
        assert mgr._pid_state == 9999
        assert mgr._last_health_ok is True
        assert mgr._auto_restart_attempts == 0

    def test_start_instance_success_non_default(
        self, storage: SQLiteProxyStorage, tmp_path: Path
    ) -> None:
        """Lines 316-335: Success path for non-default instance."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="sing-box", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
        )
        key = _insert_proxy(storage)

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = None
        mock_proc.pid = 8888

        with patch("shutil.which", return_value="/usr/bin/sing-box"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(mgr, "_wait_inbound_ports_ready", return_value=True), \
             patch.object(mgr, "_assert_inbound_ports_available"):
            mgr.start_instance("inst1", routes=[SingBoxRoute(inbound_port=10801, proxy_key=key)])

        assert mgr._process is not mock_proc  # non-default doesn't set _process
        assert "inst1" in mgr._processes


# ===== Lines 344-350: start_instance exception handler =====


class TestStartInstanceExceptionHandler:
    def test_start_exception_process_terminates_timeout(
        self, storage: SQLiteProxyStorage, tmp_path: Path
    ) -> None:
        """Lines 344-346: Exception handler with process that times out on wait."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="sing-box", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
        )
        key = _insert_proxy(storage)
        mgr.set_routes([SingBoxRoute(inbound_port=10801, proxy_key=key)])

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = None
        mock_proc.pid = 7777
        mock_proc.wait.side_effect = [
            subprocess.TimeoutExpired("cmd", 2.0),
            None,
        ]

        with patch("shutil.which", return_value="/usr/bin/sing-box"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(mgr, "_wait_inbound_ports_ready", side_effect=RuntimeError("fail")), \
             patch.object(mgr, "_assert_inbound_ports_available"):
            with pytest.raises(RuntimeError, match="fail"):
                mgr.start_instance("default")

        mock_proc.kill.assert_called_once()

    def test_start_exception_default_instance_clears_process(
        self, storage: SQLiteProxyStorage, tmp_path: Path
    ) -> None:
        """Lines 348-350: Exception handler clears _process for default instance."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="sing-box", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
        )
        key = _insert_proxy(storage)
        mgr.set_routes([SingBoxRoute(inbound_port=10801, proxy_key=key)])

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = None
        mock_proc.pid = 5555

        with patch("shutil.which", return_value="/usr/bin/sing-box"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(mgr, "_wait_inbound_ports_ready", side_effect=RuntimeError("timeout")), \
             patch.object(mgr, "_assert_inbound_ports_available"):
            with pytest.raises(RuntimeError, match="timeout"):
                mgr.start_instance("default")

        assert mgr._process is None
        assert mgr._pid_state == -1
        assert "default" not in mgr._processes


# ===== Lines 391-393, 407-409: stop_instance non-default =====


class TestStopInstanceNonDefault:
    def test_stop_non_default_already_exited(self, manager: SingBoxBackendManager) -> None:
        """Lines 391-393: stop_instance for non-default with already-exited process."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = 1  # already exited
        proc.pid = 4444
        manager._processes["inst1"] = proc
        manager.stop_instance("inst1")
        assert "inst1" not in manager._processes

    def test_stop_non_default_terminate_success(self, manager: SingBoxBackendManager) -> None:
        """Lines 407-409: stop_instance for non-default with running process."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 3333
        manager._processes["inst1"] = proc
        manager.stop_instance("inst1")
        proc.terminate.assert_called_once()
        assert "inst1" not in manager._processes


# ===== Lines 525-532: health_check ports down, _last_health_ok already False =====


class TestHealthCheckPortsDownAlreadyFalse:
    def test_ports_down_already_marked_false(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        """Lines 525-532: When ports are down and _last_health_ok is already False,
        the event is NOT recorded again (skips lines 526-531)."""
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
        mgr._last_health_ok = False  # already marked as not ok
        with patch.object(mgr, "_wait_inbound_ports_ready", return_value=False):
            h = mgr.health_check(timeout_sec=0.3)
            assert h["ok"] is False


# ===== Lines 545-552: health_check ports up, _last_health_ok already True =====


class TestHealthCheckPortsUpAlreadyTrue:
    def test_ports_up_already_ok(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        """Lines 545-552: When ports are up and _last_health_ok is True,
        no recovery event is recorded."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
        )
        mgr.set_routes([_route(10801)])
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.pid = 22222
        mgr._process = proc
        mgr._last_health_ok = True
        with patch.object(mgr, "_wait_inbound_ports_ready", return_value=True):
            h = mgr.health_check()
            assert h["ok"] is True


# ===== Lines 708, 712-718: _wait_inbound_ports_ready =====


class TestWaitInboundPortsReady:
    def test_empty_routes_returns_true(self, manager: SingBoxBackendManager) -> None:
        """Line 708: _wait_inbound_ports_ready with empty routes returns True."""
        assert manager._wait_inbound_ports_ready([], timeout_sec=1.0) is True

    def test_ports_ready_immediately(self, manager: SingBoxBackendManager) -> None:
        """Lines 712-718: Ports are open on first check."""
        with patch("proxypool.backend.singbox_manager._is_tcp_open", return_value=True):
            routes = [SingBoxRoute(inbound_port=10801, proxy_key="p1")]
            assert manager._wait_inbound_ports_ready(routes, timeout_sec=1.0) is True

    def test_ports_not_ready_timeout(self, manager: SingBoxBackendManager) -> None:
        """Lines 712-717: Ports never become ready."""
        with patch("proxypool.backend.singbox_manager._is_tcp_open", return_value=False), \
             patch("time.sleep"):
            routes = [SingBoxRoute(inbound_port=10801, proxy_key="p1")]
            assert manager._wait_inbound_ports_ready(routes, timeout_sec=0.4) is False

    def test_ports_become_ready_after_delay(self, manager: SingBoxBackendManager) -> None:
        """Lines 712-718: Ports become ready after one failed attempt."""
        call_count = 0

        def flip_flop(host: str, port: int, timeout_sec: float = 0.5) -> bool:
            nonlocal call_count
            call_count += 1
            return call_count >= 2

        with patch("proxypool.backend.singbox_manager._is_tcp_open", side_effect=flip_flop), \
             patch("time.sleep"):
            routes = [SingBoxRoute(inbound_port=10801, proxy_key="p1")]
            assert manager._wait_inbound_ports_ready(routes, timeout_sec=2.0) is True


# ===== Line 790: _try_auto_restart, start succeeds but not running =====


class TestTryAutoRestartStartNotRunning:
    def test_auto_restart_start_succeeds_but_not_running(
        self, storage: SQLiteProxyStorage, tmp_path: Path
    ) -> None:
        """Line 790: Auto-restart attempt succeeds but process is not actually running."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="x", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
            auto_restart_max=3,
        )
        mgr.set_routes([_route(10801)])

        # start() succeeds (no exception) but is_running() returns False
        with patch.object(mgr, "start"), \
             patch.object(mgr, "is_running", return_value=False):
            result = mgr._try_auto_restart(
                reason="process died", routes=[_route(10801)], pid=-1
            )
        assert result["running"] is False
        assert result["ok"] is False
        assert result["restart_attempted"] is True
        assert "auto-restart failed" in result["reason"]


# ===== Lines 809, 817, 821: async wrappers =====


class TestAsyncWrappersDeep:
    @pytest.mark.anyio
    async def test_start_instance_async(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        """Line 809: start_instance_async."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="sing-box", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
        )
        with pytest.raises(RuntimeError, match="binary not found"):
            await mgr.start_instance_async("inst1")

    @pytest.mark.anyio
    async def test_stop_instance_async(self, manager: SingBoxBackendManager) -> None:
        """Line 817: stop_instance_async."""
        await manager.stop_instance_async("inst1")

    @pytest.mark.anyio
    async def test_restart_async(self, manager: SingBoxBackendManager) -> None:
        """Line 821: restart_async."""
        with patch.object(manager, "stop"), \
             patch.object(manager, "start"):
            await manager.restart_async()


# ===== Lines 873, 882-883: _is_bind_available =====


class TestIsBindAvailableDeep:
    def test_is_bind_available_bind_succeeds(self) -> None:
        """Line 873: _is_bind_available when bind succeeds."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        assert _is_bind_available("127.0.0.1", port) is True

    def test_is_bind_available_bind_fails_on_all_addresses(self) -> None:
        """Lines 882-883: All addresses fail to bind."""
        mock_info = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 1))
        with patch("socket.getaddrinfo", return_value=[mock_info]), \
             patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.bind.side_effect = OSError("bind failed")
            mock_sock_cls.return_value = mock_sock
            assert _is_bind_available("192.0.2.1", 12345) is False

    def test_is_bind_available_gaierror(self) -> None:
        """Lines 882-883: getaddrinfo raises gaierror."""
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("no such host")):
            assert _is_bind_available("invalid.host", 12345) is False

    def test_is_bind_available_empty_host_defaults(self) -> None:
        """_is_bind_available with empty host defaults to 127.0.0.1."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        assert _is_bind_available("", port) is True


# ===== Line 321: startup timeout when ports not ready =====


class TestStartInstanceStartupTimeout:
    def test_start_instance_startup_timeout(self, storage: SQLiteProxyStorage, tmp_path: Path) -> None:
        """Line 321: _wait_inbound_ports_ready returns False -> raises startup timeout."""
        mgr = SingBoxBackendManager(
            storage=storage, binary="sing-box", test_url="u",
            routes_file=tmp_path / "r.json",
            runtime_config_file=tmp_path / "c.json",
            log_file=tmp_path / "l.log",
        )
        key = _insert_proxy(storage)
        mgr.set_routes([SingBoxRoute(inbound_port=10801, proxy_key=key)])

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = None
        mock_proc.pid = 6666

        with patch("shutil.which", return_value="/usr/bin/sing-box"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(mgr, "_wait_inbound_ports_ready", return_value=False), \
             patch.object(mgr, "_assert_inbound_ports_available"):
            with pytest.raises(RuntimeError, match="startup timeout"):
                mgr.start_instance("default")


# ===== Line 873: _is_tcp_open succeeds =====


class TestIsTcpOpen:
    def test_is_tcp_open_success(self) -> None:
        """Line 873: _is_tcp_open returns True when port is open."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            port = s.getsockname()[1]
            assert _is_tcp_open("127.0.0.1", port, timeout_sec=0.5) is True
