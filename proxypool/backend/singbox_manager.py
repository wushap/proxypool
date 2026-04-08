from __future__ import annotations

import json
import socket
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.tester.singbox import build_singbox_outbound


@dataclass(slots=True)
class SingBoxRoute:
    inbound_port: int
    proxy_key: str = ""
    front_proxy_key: str = ""
    middle_proxy_key: str = ""
    exit_proxy_key: str = ""
    inbound_type: str = "http"
    listen: str = "127.0.0.1"

    def chain_keys(self) -> list[str]:
        chain = [self.front_proxy_key, self.middle_proxy_key, self.exit_proxy_key]
        resolved = [key.strip() for key in chain if key and key.strip()]
        if resolved:
            return resolved
        if self.proxy_key and self.proxy_key.strip():
            return [self.proxy_key.strip()]
        return []


class SingBoxBackendManager:
    def __init__(
        self,
        storage: SQLiteProxyStorage,
        binary: str,
        test_url: str,
        routes_file: Path,
        runtime_config_file: Path,
        log_file: Path,
        backend_engine: str = "singbox",
        auto_restart_max: int = 3,
    ) -> None:
        self.storage = storage
        self.binary = binary
        self.test_url = test_url
        self.routes_file = routes_file
        self.runtime_config_file = runtime_config_file
        self.log_file = log_file
        self.backend_engine = backend_engine
        self.auto_restart_max = max(0, int(auto_restart_max))

        self._process: subprocess.Popen[Any] | None = None
        self._current_runtime_config_file: Path | None = None
        self._pid_state: int = -1
        self._last_health_ok: bool | None = None
        self._auto_restart_attempts: int = 0
        self._lock = threading.Lock()

        self.routes_file.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_config_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def set_routes(self, routes: list[SingBoxRoute], auto_restart: bool = False) -> None:
        _validate_routes(routes)
        self.routes_file.write_text(
            json.dumps([asdict(route) for route in routes], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if auto_restart and self.is_running():
            self.restart()

    def get_routes(self) -> list[SingBoxRoute]:
        if not self.routes_file.exists():
            return []

        data = json.loads(self.routes_file.read_text(encoding="utf-8") or "[]")
        routes: list[SingBoxRoute] = []
        for item in data:
            routes.append(
                SingBoxRoute(
                    inbound_port=int(item["inbound_port"]),
                    proxy_key=str(item.get("proxy_key") or ""),
                    front_proxy_key=str(item.get("front_proxy_key") or ""),
                    middle_proxy_key=str(item.get("middle_proxy_key") or ""),
                    exit_proxy_key=str(item.get("exit_proxy_key") or ""),
                    inbound_type=str(item.get("inbound_type") or "http"),
                    listen=str(item.get("listen") or "127.0.0.1"),
                )
            )
        return routes

    def build_runtime_config(self, routes: list[SingBoxRoute] | None = None) -> dict[str, Any]:
        use_routes = routes if routes is not None else self.get_routes()
        _validate_routes(use_routes)

        inbounds: list[dict[str, Any]] = []
        outbounds: list[dict[str, Any]] = []
        rules: list[dict[str, Any]] = []

        for idx, route in enumerate(use_routes):
            inbound_tag = f"in-{idx}"

            inbound_type = route.inbound_type.lower()
            if inbound_type not in {"socks", "http"}:
                raise RuntimeError(f"unsupported inbound_type: {route.inbound_type}")

            inbounds.append(
                {
                    "type": inbound_type,
                    "tag": inbound_tag,
                    "listen": route.listen,
                    "listen_port": route.inbound_port,
                }
            )

            chain_keys = route.chain_keys()
            chain_outbounds: list[dict[str, Any]] = []
            for hop_idx, key in enumerate(chain_keys):
                proxy = self.storage.get_proxy_by_key(key)
                if not proxy:
                    raise RuntimeError(f"proxy not found: {key}")
                hop_tag = f"out-{idx}-hop-{hop_idx}"
                outbound = build_singbox_outbound(proxy, tag=hop_tag)
                if outbound is None:
                    raise RuntimeError(f"proxy unsupported for sing-box outbound: {key}")
                chain_outbounds.append(outbound)

            # sing-box detour works from the selected outbound back to upstream.
            # Selected outbound is the last hop (exit), and detours point backward:
            # exit -> middle -> front.
            if len(chain_outbounds) >= 2:
                for hop_idx in range(1, len(chain_outbounds)):
                    chain_outbounds[hop_idx]["detour"] = str(chain_outbounds[hop_idx - 1]["tag"])

            outbounds.extend(chain_outbounds)
            rules.append({"inbound": [inbound_tag], "outbound": str(chain_outbounds[-1]["tag"])})

        outbounds.append({"type": "direct", "tag": "direct"})

        return {
            "log": {"disabled": False, "level": "warn", "timestamp": True},
            "inbounds": inbounds,
            "outbounds": outbounds,
            "route": {
                "rules": rules,
                "final": "direct",
            },
        }

    def start(self) -> None:
        with self._lock:
            self._pid_state = 0
            try:
                if self.backend_engine != "singbox":
                    raise RuntimeError(f"backend engine not supported: {self.backend_engine}")

                if self._process and self._process.poll() is None:
                    self._pid_state = int(self._process.pid)
                    return

                routes = self.get_routes()
                self._assert_inbound_ports_available(routes)

                if shutil.which(self.binary) is None:
                    raise RuntimeError(f"sing-box binary not found: {self.binary}")

                config = self.build_runtime_config(routes=routes)
                runtime_config_file = self._new_runtime_config_file()
                runtime_config_file.write_text(
                    json.dumps(config, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                log_handle = self.log_file.open("a", encoding="utf-8")
                self._process = subprocess.Popen(
                    [self.binary, "run", "-c", str(runtime_config_file)],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                )
                self._current_runtime_config_file = runtime_config_file
                if not self._wait_inbound_ports_ready(routes, timeout_sec=4.0):
                    raise RuntimeError("sing-box startup timeout: inbound ports not ready")
                self._pid_state = int(self._process.pid)
                self._last_health_ok = True
                self._auto_restart_attempts = 0
                self._record_process_event(action="start", pid=self._pid_state, result="success", detail="started")
            except Exception as exc:
                if self._process and self._process.poll() is None:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=2.0)
                self._process = None
                self._pid_state = -1
                self._record_process_event(action="start", pid=-1, result="failed", detail=str(exc))
                raise

    def stop(self) -> None:
        with self._lock:
            if not self._process:
                self._pid_state = -1
                self._record_process_event(action="stop", pid=-1, result="noop", detail="already stopped")
                return
            if self._process.poll() is not None:
                pid = int(self._process.pid)
                self._process = None
                self._pid_state = -1
                self._record_process_event(action="stop", pid=pid, result="success", detail="already exited")
                return
            pid = int(self._process.pid)
            self._process.terminate()
            try:
                self._process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2.0)
            self._process = None
            self._pid_state = -1
            self._auto_restart_attempts = 0
            self._record_process_event(action="stop", pid=pid, result="success", detail="stopped")

    def restart(self) -> None:
        self.stop()
        self.start()

    def is_running(self) -> bool:
        with self._lock:
            if self._process is None:
                self._pid_state = -1
                return False
            if self._process.poll() is None:
                self._pid_state = int(self._process.pid)
                return True
            self._pid_state = -1
            self._process = None
            return False

    def status(self) -> dict[str, Any]:
        routes = self.get_routes()
        running = self.is_running()
        return {
            "backend": self.backend_engine,
            "binary": self.binary,
            "test_url": self.test_url,
            "running": running,
            "pid": self._pid_state if not running else int(self._process.pid) if self._process else self._pid_state,
            "auto_restart_max": self.auto_restart_max,
            "auto_restart_attempts": self._auto_restart_attempts,
            "routes_count": len(routes),
            "routes": [asdict(route) for route in routes],
            "runtime_config_file": str(self._current_runtime_config_file or self.runtime_config_file),
            "log_file": str(self.log_file),
        }

    def health_check(self, timeout_sec: float = 1.5, auto_restart: bool = False) -> dict[str, Any]:
        routes = self.get_routes()
        needs_restart = False
        down_reason = ""
        pid = -1
        with self._lock:
            if self._process is None:
                self._pid_state = -1
                self._last_health_ok = False
                needs_restart = True
                down_reason = "not running"
            elif self._process.poll() is not None:
                dead_pid = int(self._process.pid)
                self._process = None
                self._pid_state = -1
                self._last_health_ok = False
                self._record_process_event(
                    action="stop",
                    pid=dead_pid,
                    result="exited",
                    detail="process exited unexpectedly",
                )
                needs_restart = True
                down_reason = "process exited"
            else:
                pid = int(self._process.pid)
                self._pid_state = pid

        if needs_restart:
            if auto_restart:
                return self._try_auto_restart(reason=down_reason, routes=routes, pid=pid)
            return {"running": False, "ok": False, "reason": down_reason, "pid": -1, "restart_attempted": False}

        ready = self._wait_inbound_ports_ready(routes, timeout_sec=max(0.3, timeout_sec))
        if not ready:
            if self._last_health_ok is not False:
                self._record_process_event(
                    action="health",
                    pid=pid,
                    result="failed",
                    detail="inbound ports not reachable",
                )
            self._last_health_ok = False
            if auto_restart:
                return self._try_auto_restart(reason="inbound ports not reachable", routes=routes, pid=pid)
            return {
                "running": True,
                "ok": False,
                "reason": "inbound ports not reachable",
                "pid": pid,
                "restart_attempted": False,
            }

        if self._last_health_ok is False:
            self._record_process_event(
                action="health",
                pid=pid,
                result="recovered",
                detail="inbound ports recovered",
            )
        self._last_health_ok = True
        return {"running": True, "ok": True, "pid": pid, "restart_attempted": False}

    def measure_all_routes_latency(self, timeout_sec: float = 10.0) -> list[dict[str, Any]]:
        routes = self.get_routes()
        if not routes:
            return []

        results: list[dict[str, Any]] = []
        workers = min(8, len(routes))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(self.measure_route_latency, route, timeout_sec, idx): idx
                for idx, route in enumerate(routes)
            }
            for fut in as_completed(future_map):
                idx = future_map[fut]
                try:
                    item = fut.result()
                except Exception as exc:  # pragma: no cover - runtime guard
                    route = routes[idx]
                    item = {
                        **asdict(route),
                        "route_index": idx,
                        "available": False,
                        "latency_ms": None,
                        "error": f"latency check exception: {exc}",
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    }
                results.append(item)

        return sorted(results, key=lambda x: int(x.get("route_index", 0)))

    def measure_route_latency(self, route: SingBoxRoute, timeout_sec: float = 10.0, route_index: int = -1) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        base = asdict(route)
        inbound_type = str(route.inbound_type or "").lower()
        if inbound_type not in {"socks", "http"}:
            return {
                **base,
                "route_index": route_index,
                "available": False,
                "latency_ms": None,
                "error": f"unsupported inbound_type: {route.inbound_type}",
                "checked_at": now,
            }
        if not self.is_running():
            return {
                **base,
                "route_index": route_index,
                "available": False,
                "latency_ms": None,
                "error": "sing-box backend not running",
                "checked_at": now,
            }

        curl = shutil.which("curl")
        if not curl:
            return {
                **base,
                "route_index": route_index,
                "available": False,
                "latency_ms": None,
                "error": "curl not found",
                "checked_at": now,
            }

        proxy_url = (
            f"socks5h://{route.listen}:{route.inbound_port}"
            if inbound_type == "socks"
            else f"http://{route.listen}:{route.inbound_port}"
        )
        cmd = [
            curl,
            "-sS",
            "-o",
            "/dev/null",
            "-w",
            "%{time_total}",
            "--max-time",
            str(max(1, int(timeout_sec))),
            "--proxy",
            proxy_url,
            self.test_url,
        ]
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            error = (completed.stderr or "").strip() or f"curl exit={completed.returncode}"
            return {
                **base,
                "route_index": route_index,
                "available": False,
                "latency_ms": None,
                "error": error[:240],
                "checked_at": now,
            }

        text = (completed.stdout or "").strip()
        latency_ms = _parse_curl_time_ms(text)
        return {
            **base,
            "route_index": route_index,
            "available": latency_ms is not None,
            "latency_ms": latency_ms,
            "error": "" if latency_ms is not None else "invalid curl output",
            "checked_at": now,
        }

    def _new_runtime_config_file(self) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        base_name = self.runtime_config_file.stem or "singbox"
        return self.runtime_config_file.with_name(f"{base_name}-{stamp}.json")

    def _record_process_event(self, action: str, pid: int, result: str, detail: str = "") -> None:
        try:
            self.storage.record_backend_process_event(
                backend=self.backend_engine,
                action=action,
                pid=pid,
                result=result,
                detail=detail,
                config_file=str(self._current_runtime_config_file or self.runtime_config_file),
            )
        except Exception:
            # Avoid affecting process control flow when persistence fails.
            return

    def _assert_inbound_ports_available(self, routes: list[SingBoxRoute]) -> None:
        occupied: list[str] = []
        for route in routes:
            if not _is_bind_available(route.listen, route.inbound_port):
                occupied.append(f"{route.listen}:{route.inbound_port}")
        if occupied:
            raise RuntimeError(f"inbound port already in use: {', '.join(occupied)}")

    def _wait_inbound_ports_ready(self, routes: list[SingBoxRoute], timeout_sec: float) -> bool:
        if not routes:
            return True
        deadline = time.monotonic() + max(0.3, timeout_sec)
        while time.monotonic() < deadline:
            all_ready = True
            for route in routes:
                host = _normalize_probe_host(route.listen)
                if not _is_tcp_open(host, route.inbound_port, timeout_sec=0.25):
                    all_ready = False
                    break
            if all_ready:
                return True
            time.sleep(0.1)
        return False

    def _try_auto_restart(self, reason: str, routes: list[SingBoxRoute], pid: int = -1) -> dict[str, Any]:
        if not routes:
            return {
                "running": False,
                "ok": False,
                "pid": -1,
                "reason": f"{reason}; no routes configured",
                "restart_attempted": False,
                "restart_attempt": self._auto_restart_attempts,
            }
        if self.auto_restart_max <= 0:
            return {
                "running": False,
                "ok": False,
                "pid": -1,
                "reason": f"{reason}; auto-restart disabled",
                "restart_attempted": False,
                "restart_attempt": self._auto_restart_attempts,
            }
        if self._auto_restart_attempts >= self.auto_restart_max:
            return {
                "running": False,
                "ok": False,
                "pid": -1,
                "reason": f"{reason}; auto-restart limit reached",
                "restart_attempted": False,
                "restart_attempt": self._auto_restart_attempts,
            }

        self._auto_restart_attempts += 1
        attempt = self._auto_restart_attempts
        self._record_process_event(
            action="health",
            pid=pid,
            result="restart_attempt",
            detail=f"{reason}; attempt {attempt}/{self.auto_restart_max}",
        )
        try:
            self.start()
        except Exception as exc:
            return {
                "running": False,
                "ok": False,
                "pid": -1,
                "reason": f"{reason}; auto-restart failed: {exc}",
                "restart_attempted": True,
                "restart_attempt": attempt,
            }

        running = self.is_running()
        if running:
            current_pid = int(self._process.pid) if self._process else -1
            self._record_process_event(
                action="health",
                pid=current_pid,
                result="restart_success",
                detail=f"{reason}; recovered by restart",
            )
            return {
                "running": True,
                "ok": True,
                "pid": current_pid,
                "reason": "auto-restart success",
                "restart_attempted": True,
                "restart_attempt": attempt,
            }
        return {
            "running": False,
            "ok": False,
            "pid": -1,
            "reason": f"{reason}; auto-restart failed",
            "restart_attempted": True,
            "restart_attempt": attempt,
        }


def _validate_routes(routes: list[SingBoxRoute]) -> None:
    ports: set[int] = set()
    for route in routes:
        if route.inbound_port <= 0 or route.inbound_port > 65535:
            raise RuntimeError(f"invalid inbound_port: {route.inbound_port}")
        if route.inbound_port in ports:
            raise RuntimeError(f"duplicated inbound_port: {route.inbound_port}")
        if not route.chain_keys():
            raise RuntimeError("proxy_key or (front/middle/exit proxy key) is required")
        ports.add(route.inbound_port)


def _parse_curl_time_ms(text: str) -> int | None:
    if not text:
        return None
    try:
        return int(float(text) * 1000)
    except ValueError:
        return None


def _normalize_probe_host(host: str) -> str:
    text = str(host or "").strip()
    if text in {"", "0.0.0.0", "::"}:
        return "127.0.0.1"
    return text


def _is_tcp_open(host: str, port: int, timeout_sec: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=max(0.1, timeout_sec)):
            return True
    except OSError:
        return False


def _is_bind_available(host: str, port: int) -> bool:
    bind_host = str(host or "").strip() or "127.0.0.1"
    try:
        infos = socket.getaddrinfo(bind_host, int(port), type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    for family, socktype, proto, _canonname, sockaddr in infos:
        sock = socket.socket(family, socktype, proto)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(sockaddr)
            return True
        except OSError:
            continue
        finally:
            sock.close()
    return False
