from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _pid_alive(pid: int) -> bool:
    """Check whether a process with *pid* is still running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


@dataclass
class ResinConfig:
    port: int = 2260
    admin_token: str = ""
    data_dir: Path = field(default_factory=lambda: Path("data/resin"))
    log_file: Path = field(default_factory=lambda: Path("data/runtime/resin.log"))


class ResinBackendManager:
    """Manages a Resin proxy pool gateway process.

    State is persisted to disk so that the manager can reattach to an
    already-running Resin process after the API server restarts.

    Files written (under *runtime_dir*)::

        resin.pid        – PID of the running Resin process (removed on stop)
        resin_state.json – desired state: {"desired_running": true/false}
    """

    def __init__(
        self,
        binary: str,
        port: int = 2260,
        admin_token: str = "",
        proxy_token: str = "",
        auth_version: str = "V1",
        data_dir: Path | str = "data/resin",
        log_file: Path | str = "data/runtime/resin.log",
        runtime_dir: Path | str = "data/runtime",
    ) -> None:
        self.binary = binary
        self.port = port
        self.admin_token = admin_token
        self.proxy_token = proxy_token
        self.auth_version = auth_version
        self.data_dir = Path(data_dir)
        self.log_file = Path(log_file)
        self.runtime_dir = Path(runtime_dir)
        self._pid_file = self.runtime_dir / "resin.pid"
        self._state_file = self.runtime_dir / "resin_state.json"
        self._process: subprocess.Popen[Any] | None = None
        self._lock = threading.Lock()
        self._pid_state: int = -1

        # Try to reattach to an already-running Resin process.
        self._try_reattach()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _save_pid(self, pid: int) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file.write_text(str(pid), encoding="utf-8")

    def _clear_pid(self) -> None:
        try:
            self._pid_file.unlink(missing_ok=True)
        except OSError:
            pass

    def _read_pid(self) -> int:
        try:
            return int(self._pid_file.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError, OSError):
            return -1

    def _save_desired_state(self, desired_running: bool) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps({"desired_running": desired_running}),
            encoding="utf-8",
        )

    def get_desired_running(self) -> bool:
        """Return whether Resin *should* be running (persisted preference)."""
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            return bool(data.get("desired_running"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return False

    def _try_reattach(self) -> None:
        """If a Resin process from a previous run is still alive, adopt it."""
        pid = self._read_pid()
        if pid > 0 and _pid_alive(pid) and self._port_responds():
            self._pid_state = pid
            # _process stays None – we didn't spawn it, so we won't
            # wait() on it.  is_running() checks the port instead.

    def _port_responds(self) -> bool:
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/healthz", method="GET",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Process lifecycle
    # ------------------------------------------------------------------

    def is_running(self) -> bool:
        if self._process is not None:
            if self._process.poll() is not None:
                self._process = None
                self._pid_state = -1
                self._clear_pid()
                return False
            return True
        # We didn't spawn the process (reattach case) – check PID file.
        pid = self._pid_state if self._pid_state > 0 else self._read_pid()
        if pid > 0 and _pid_alive(pid) and self._port_responds():
            self._pid_state = pid
            return True
        self._pid_state = -1
        self._clear_pid()
        return False

    def start(self) -> None:
        with self._lock:
            if self.is_running():
                self._save_desired_state(True)
                return

            if shutil.which(self.binary) is None:
                raise RuntimeError(f"resin binary not found: {self.binary}")

            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self.runtime_dir.mkdir(parents=True, exist_ok=True)

            state_dir = self.data_dir / "state"
            cache_dir = self.data_dir / "cache"
            log_dir = self.data_dir / "log"
            state_dir.mkdir(parents=True, exist_ok=True)
            cache_dir.mkdir(parents=True, exist_ok=True)
            log_dir.mkdir(parents=True, exist_ok=True)

            env = {
                "RESIN_STATE_DIR": str(state_dir),
                "RESIN_CACHE_DIR": str(cache_dir),
                "RESIN_LOG_DIR": str(log_dir),
                "RESIN_PORT": str(self.port),
                "RESIN_AUTH_VERSION": self.auth_version,
                "RESIN_ADMIN_TOKEN": self.admin_token,
                "RESIN_PROXY_TOKEN": self.proxy_token,
            }

            merged_env = {**os.environ, **env}

            log_handle = self.log_file.open("a", encoding="utf-8")
            try:
                self._process = subprocess.Popen(
                    [self.binary],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    env=merged_env,
                    start_new_session=True,
                )
                self._pid_state = int(self._process.pid)
                self._save_pid(self._pid_state)

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
                self._clear_pid()
                raise
            self._save_desired_state(True)

    def stop(self) -> None:
        with self._lock:
            self._save_desired_state(False)
            if not self._process:
                # Reattach case – kill by PID file.
                pid = self._pid_state if self._pid_state > 0 else self._read_pid()
                if pid > 0 and _pid_alive(pid):
                    try:
                        os.kill(pid, 15)  # SIGTERM
                        deadline = time.monotonic() + 5.0
                        while time.monotonic() < deadline and _pid_alive(pid):
                            time.sleep(0.3)
                        if _pid_alive(pid):
                            os.kill(pid, 9)  # SIGKILL
                    except (ProcessLookupError, OSError):
                        pass
                self._pid_state = -1
                self._clear_pid()
                return
            if self._process.poll() is not None:
                self._process = None
                self._pid_state = -1
                self._clear_pid()
                return
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=3.0)
            self._process = None
            self._pid_state = -1
            self._clear_pid()

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
