"""Tests for proxypool.backend.mihomo_manager – covering initialization,
start/stop lifecycle, status, health_check, is_running, config generation,
and async wrappers."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from proxypool.backend.egress_backend import ChainInstanceSpec, StartedInstance
from proxypool.backend.mihomo_manager import MihomoEgressBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spec(
    instance_id: str = "test-instance",
    port: int = 18080,
    front: dict | None = None,
    exit: dict | None = None,
) -> ChainInstanceSpec:
    front = front or {
        "protocol": "socks",
        "host": "front.example.com",
        "port": 1080,
        "raw_link": "socks://front.example.com:1080",
        "name": "front",
    }
    exit = exit or {
        "protocol": "ss",
        "host": "exit.example.com",
        "port": 443,
        "raw_link": "ss://exit.example.com:443",
        "name": "exit",
        "extra_json": {"cipher": "aes-128-gcm", "password": "secret"},
    }
    return ChainInstanceSpec(
        instance_id=instance_id,
        pool_id=1,
        listen="127.0.0.1",
        port=port,
        inbound_type="http",
        front_proxy=front,
        exit_proxy=exit,
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_binary(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        assert backend.binary == "mihomo"
        assert backend.runtime_dir == tmp_path
        assert tmp_path.exists()

    def test_custom_binary(self, tmp_path: Path):
        backend = MihomoEgressBackend(binary="/custom/mihomo", runtime_dir=tmp_path)
        assert backend.binary == "/custom/mihomo"

    def test_empty_binary_defaults_to_mihomo(self, tmp_path: Path):
        backend = MihomoEgressBackend(binary="", runtime_dir=tmp_path)
        assert backend.binary == "mihomo"

    def test_none_binary_defaults_to_mihomo(self, tmp_path: Path):
        backend = MihomoEgressBackend(binary=None, runtime_dir=tmp_path)
        assert backend.binary == "mihomo"

    def test_backend_type(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        assert backend.backend_type == "mihomo"

    def test_process_dict_initially_empty(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        assert backend._processes == {}

    def test_runtime_dir_created(self, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "c"
        MihomoEgressBackend(runtime_dir=nested)
        assert nested.is_dir()


# ---------------------------------------------------------------------------
# Build config
# ---------------------------------------------------------------------------

class TestBuildConfig:
    def test_returns_dict(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        spec = _make_spec()
        config = backend.build_config(spec)
        assert isinstance(config, dict)
        assert "listeners" in config
        assert "proxies" in config


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

class TestStart:
    def test_start_returns_started_instance(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        spec = _make_spec()
        with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
            with patch("proxypool.backend.mihomo_manager.subprocess.Popen") as popen:
                popen.return_value.pid = 1234
                result = backend.start(spec)
        assert isinstance(result, StartedInstance)
        assert result.pid == 1234

    def test_start_writes_config_file(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        spec = _make_spec(instance_id="my-inst")
        with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
            with patch("proxypool.backend.mihomo_manager.subprocess.Popen") as popen:
                popen.return_value.pid = 5678
                result = backend.start(spec)
        assert result.config_file.exists()
        assert result.config_file.name == "my-inst.yaml"
        content = result.config_file.read_text(encoding="utf-8")
        assert "exit.example.com" in content

    def test_start_writes_log_file(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        spec = _make_spec(instance_id="log-test")
        with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
            with patch("proxypool.backend.mihomo_manager.subprocess.Popen") as popen:
                popen.return_value.pid = 9999
                result = backend.start(spec)
        assert result.log_file.name == "log-test.log"

    def test_start_raises_when_binary_not_found(self, tmp_path: Path):
        backend = MihomoEgressBackend(binary="nonexistent_binary_xyz", runtime_dir=tmp_path)
        spec = _make_spec()
        with patch("proxypool.backend.mihomo_manager.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="mihomo binary not found"):
                backend.start(spec)

    def test_start_stores_process_in_dict(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        spec = _make_spec(instance_id="stored")
        with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
            with patch("proxypool.backend.mihomo_manager.subprocess.Popen") as popen:
                popen.return_value.pid = 1111
                backend.start(spec)
        assert "stored" in backend._processes

    def test_start_sets_env_variables(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        spec = _make_spec()
        with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
            with patch("proxypool.backend.mihomo_manager.subprocess.Popen") as popen:
                popen.return_value.pid = 2222
                backend.start(spec)
        _, kwargs = popen.call_args
        env = kwargs["env"]
        assert env["HOME"] == str(tmp_path)
        assert env["XDG_CONFIG_HOME"] == str(tmp_path)

    def test_start_popen_failure_closes_log(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        spec = _make_spec()
        with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
            with patch("proxypool.backend.mihomo_manager.subprocess.Popen", side_effect=OSError("fail")):
                with pytest.raises(OSError, match="fail"):
                    backend.start(spec)
        # Log handle should be closed; no lingering open handles
        assert "started" not in backend._processes


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

class TestStop:
    def _start_backend(self, tmp_path: Path, instance_id: str = "inst1") -> MihomoEgressBackend:
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        spec = _make_spec(instance_id=instance_id)
        with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
            with patch("proxypool.backend.mihomo_manager.subprocess.Popen") as popen:
                popen.return_value.pid = 3333
                popen.return_value.poll.return_value = None
                backend.start(spec)
        return backend

    def test_stop_removes_process(self, tmp_path: Path):
        backend = self._start_backend(tmp_path)
        assert "inst1" in backend._processes
        backend.stop("inst1")
        assert "inst1" not in backend._processes

    def test_stop_terminates_running_process(self, tmp_path: Path):
        backend = self._start_backend(tmp_path)
        process = backend._processes["inst1"]
        process.poll.return_value = None
        process.wait.return_value = 0
        backend.stop("inst1")
        process.terminate.assert_called_once()

    def test_stop_kills_on_timeout(self, tmp_path: Path):
        backend = self._start_backend(tmp_path)
        process = backend._processes["inst1"]
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired(cmd="mihomo", timeout=5)
        backend.stop("inst1")
        process.kill.assert_called_once()

    def test_stop_noop_for_unknown_id(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        # Should not raise
        backend.stop("nonexistent")

    def test_stop_noop_for_empty_id(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        backend.stop("")

    def test_stop_already_exited_process(self, tmp_path: Path):
        backend = self._start_backend(tmp_path)
        process = backend._processes["inst1"]
        process.poll.return_value = 1  # already exited
        backend.stop("inst1")
        process.terminate.assert_not_called()

    def test_stop_multiple_instances(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        for iid in ("a", "b"):
            spec = _make_spec(instance_id=iid)
            with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
                with patch("proxypool.backend.mihomo_manager.subprocess.Popen") as popen:
                    popen.return_value.pid = ord(iid)
                    popen.return_value.poll.return_value = None
                    backend.start(spec)
        backend.stop("a")
        assert "a" not in backend._processes
        assert "b" in backend._processes


# ---------------------------------------------------------------------------
# Is running
# ---------------------------------------------------------------------------

class TestIsRunning:
    def test_not_running_when_no_process(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        assert backend.is_running("missing") is False

    def test_running_when_process_alive(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        backend._processes["alive"] = mock_proc
        assert backend.is_running("alive") is True

    def test_not_running_when_process_exited(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        backend._processes["dead"] = mock_proc
        assert backend.is_running("dead") is False


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_not_running(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        result = backend.health_check("missing")
        assert result["running"] is False
        assert result["ok"] is False
        assert "not running" in result["reason"]

    def test_process_exited(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        backend._processes["exited"] = mock_proc
        result = backend.health_check("exited")
        assert result["running"] is False
        assert result["ok"] is False
        assert "exited" in result["reason"]

    def test_running_no_port_check(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        backend._processes["alive"] = mock_proc
        result = backend.health_check("alive", port=0)
        assert result["running"] is True
        assert result["ok"] is True

    def test_running_port_check_success(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        backend._processes["alive"] = mock_proc
        with patch("proxypool.backend.mihomo_manager.socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            result = backend.health_check("alive", port=1080)
        assert result["running"] is True
        assert result["ok"] is True

    def test_running_port_check_failure(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        backend._processes["alive"] = mock_proc
        with patch("proxypool.backend.mihomo_manager.socket.create_connection", side_effect=OSError("refused")):
            result = backend.health_check("alive", port=1080, timeout_sec=0.5)
        assert result["running"] is True
        assert result["ok"] is False
        assert "not reachable" in result["reason"]


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_empty_status(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        result = backend.status()
        assert result["backend"] == "mihomo"
        assert result["instances"] == {}

    def test_status_running_instance(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 4444
        backend._processes["s1"] = mock_proc
        result = backend.status()
        assert "s1" in result["instances"]
        assert result["instances"]["s1"]["status"] == "running"
        assert result["instances"]["s1"]["pid"] == 4444

    def test_status_exited_instance(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        mock_proc.pid = 5555
        backend._processes["s2"] = mock_proc
        result = backend.status()
        assert result["instances"]["s2"]["status"] == "exited"

    def test_status_mixed_instances(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        alive = MagicMock()
        alive.poll.return_value = None
        alive.pid = 100
        dead = MagicMock()
        dead.poll.return_value = 1
        dead.pid = 200
        backend._processes["alive"] = alive
        backend._processes["dead"] = dead
        result = backend.status()
        assert result["instances"]["alive"]["status"] == "running"
        assert result["instances"]["dead"]["status"] == "exited"


# ---------------------------------------------------------------------------
# Async wrappers
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    @pytest.mark.asyncio
    async def test_start_async(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        spec = _make_spec(instance_id="async-start")
        with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
            with patch("proxypool.backend.mihomo_manager.subprocess.Popen") as popen:
                popen.return_value.pid = 7777
                result = await backend.start_async(spec)
        assert result.pid == 7777

    @pytest.mark.asyncio
    async def test_stop_async(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        # No-op stop should not raise
        await backend.stop_async("nonexistent")

    @pytest.mark.asyncio
    async def test_health_check_async(self, tmp_path: Path):
        backend = MihomoEgressBackend(runtime_dir=tmp_path)
        result = await backend.health_check_async("missing")
        assert result["running"] is False
