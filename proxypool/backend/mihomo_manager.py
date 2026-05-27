from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import yaml

from proxypool.backend.egress_backend import ChainInstanceSpec, StartedInstance
from proxypool.backend.mihomo_config import build_mihomo_chain_config


class MihomoEgressBackend:
    backend_type = "mihomo"

    def __init__(self, binary: str = "mihomo", runtime_dir: Path | str = Path("data/runtime/mihomo")) -> None:
        self.binary = str(binary or "mihomo")
        self.runtime_dir = Path(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._processes: dict[str, subprocess.Popen[Any]] = {}
        self._lock = threading.RLock()

    def build_config(self, spec: ChainInstanceSpec) -> dict[str, Any]:
        return build_mihomo_chain_config(spec)

    def start(self, spec: ChainInstanceSpec) -> StartedInstance:
        if shutil.which(self.binary) is None:
            raise RuntimeError(f"mihomo binary not found: {self.binary}")

        config = self.build_config(spec)
        config_file = self.runtime_dir / f"{spec.instance_id}.yaml"
        log_file = self.runtime_dir / f"{spec.instance_id}.log"
        config_file.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

        log_handle = log_file.open("a", encoding="utf-8")
        env = dict(os.environ)
        env["HOME"] = str(self.runtime_dir)
        env["XDG_CONFIG_HOME"] = str(self.runtime_dir)
        try:
            process = subprocess.Popen(
                [self.binary, "-f", str(config_file)],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=env,
            )
        except Exception:
            log_handle.close()
            raise
        with self._lock:
            self._processes[spec.instance_id] = process
        return StartedInstance(pid=int(process.pid), config_file=config_file, log_file=log_file)

    def stop(self, instance_id: str) -> None:
        with self._lock:
            process = self._processes.pop(str(instance_id or ""), None)
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    def is_running(self, instance_id: str) -> bool:
        """Check if a mihomo instance is running."""
        with self._lock:
            process = self._processes.get(instance_id)
            if process is None:
                return False
            return process.poll() is None

    def health_check(self, instance_id: str, port: int = 0, timeout_sec: float = 1.0) -> dict[str, Any]:
        """Check health of a mihomo instance.

        Args:
            instance_id: Instance identifier
            port: Mixed port to check (if 0, skip port check)
            timeout_sec: Timeout for port check

        Returns:
            dict with 'running' and 'ok' keys
        """
        with self._lock:
            process = self._processes.get(instance_id)

        if process is None:
            return {"running": False, "ok": False, "reason": "not running"}

        if process.poll() is not None:
            return {"running": False, "ok": False, "reason": "process exited"}

        # Optionally check if mixed port is listening
        if port > 0:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=timeout_sec):
                    return {"running": True, "ok": True}
            except OSError:
                return {"running": True, "ok": False, "reason": "port not reachable"}

        return {"running": True, "ok": True}

    def status(self) -> dict[str, Any]:
        """Get status of all mihomo instances."""
        with self._lock:
            instances = {}
            for instance_id, process in self._processes.items():
                if process.poll() is None:
                    instances[instance_id] = {"status": "running", "pid": process.pid}
                else:
                    instances[instance_id] = {"status": "exited", "pid": process.pid}
        return {"backend": "mihomo", "instances": instances}

    async def start_async(self, spec: ChainInstanceSpec) -> StartedInstance:
        """Async wrapper for start()."""
        return await asyncio.to_thread(self.start, spec)

    async def stop_async(self, instance_id: str) -> None:
        """Async wrapper for stop()."""
        await asyncio.to_thread(self.stop, instance_id)

    async def health_check_async(self, instance_id: str, port: int = 0, timeout_sec: float = 1.0) -> dict[str, Any]:
        """Async wrapper for health_check()."""
        return await asyncio.to_thread(self.health_check, instance_id, port, timeout_sec)
