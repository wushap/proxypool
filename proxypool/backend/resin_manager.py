from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ResinConfig:
    port: int = 2260
    admin_token: str = ""
    data_dir: Path = field(default_factory=lambda: Path("data/resin"))
    log_file: Path = field(default_factory=lambda: Path("data/runtime/resin.log"))


class ResinBackendManager:
    """Manages a Resin proxy pool gateway process."""

    def __init__(
        self,
        binary: str,
        port: int = 2260,
        admin_token: str = "",
        data_dir: Path | str = "data/resin",
        log_file: Path | str = "data/runtime/resin.log",
    ) -> None:
        self.binary = binary
        self.port = port
        self.admin_token = admin_token
        self.data_dir = Path(data_dir)
        self.log_file = Path(log_file)
        self._process: subprocess.Popen[Any] | None = None
        self._lock = threading.Lock()
        self._pid_state: int = -1

    def is_running(self) -> bool:
        if self._process is None:
            return False
        if self._process.poll() is not None:
            self._process = None
            self._pid_state = -1
            return False
        return True

    def start(self) -> None:
        with self._lock:
            if self.is_running():
                return

            if shutil.which(self.binary) is None:
                raise RuntimeError(f"resin binary not found: {self.binary}")

            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

            env = {
                "RESIN_DB_PATH": str(self.data_dir / "state.db"),
                "RESIN_CACHE_DB_PATH": str(self.data_dir / "cache.db"),
                "RESIN_METRICS_DB_PATH": str(self.data_dir / "metrics.db"),
                "RESIN_PORT": str(self.port),
            }
            if self.admin_token:
                env["RESIN_ADMIN_TOKEN"] = self.admin_token

            import os
            merged_env = {**os.environ, **env}

            log_handle = self.log_file.open("a", encoding="utf-8")
            try:
                self._process = subprocess.Popen(
                    [self.binary],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    env=merged_env,
                )
                self._pid_state = int(self._process.pid)

                if not self._wait_ready(timeout_sec=10.0):
                    raise RuntimeError("resin startup timeout: /healthz not responding")
            except Exception:
                if self._process and self._process.poll() is None:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                self._process = None
                self._pid_state = -1
                raise

    def stop(self) -> None:
        with self._lock:
            if not self._process:
                self._pid_state = -1
                return
            if self._process.poll() is not None:
                pid = int(self._process.pid)
                self._process = None
                self._pid_state = -1
                return
            pid = int(self._process.pid)
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=3.0)
            self._process = None
            self._pid_state = -1

    def restart(self) -> None:
        self.stop()
        self.start()

    def health_check(self, timeout_sec: float = 3.0) -> dict[str, Any]:
        if not self.is_running():
            return {"running": False, "healthy": False, "pid": -1, "error": "not running"}

        import urllib.request
        import urllib.error

        url = f"http://127.0.0.1:{self.port}/healthz"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return {
                    "running": True,
                    "healthy": resp.status == 200,
                    "pid": self._pid_state,
                    "status_code": resp.status,
                    "body": body[:500],
                }
        except Exception as exc:
            return {
                "running": True,
                "healthy": False,
                "pid": self._pid_state,
                "error": str(exc)[:300],
            }

    def status(self) -> dict[str, Any]:
        running = self.is_running()
        health = self.health_check() if running else {"running": False, "healthy": False, "pid": -1}
        return {
            "binary": self.binary,
            "port": self.port,
            "data_dir": str(self.data_dir),
            "running": running,
            "pid": self._pid_state,
            "healthy": health.get("healthy", False),
            "health": health,
        }

    def _wait_ready(self, timeout_sec: float = 10.0) -> bool:
        import urllib.request
        import urllib.error

        deadline = time.monotonic() + timeout_sec
        url = f"http://127.0.0.1:{self.port}/healthz"
        while time.monotonic() < deadline:
            if self._process and self._process.poll() is not None:
                return False
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        return False
