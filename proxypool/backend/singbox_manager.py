from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
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
        self._processes: dict[str, subprocess.Popen[Any]] = {}
        self._current_runtime_config_file: Path | None = None
        self._runtime_config_files: dict[str, Path] = {}
        self._pid_state: int = -1
        self._last_health_ok: bool | None = None
        self._auto_restart_attempts: int = 0
        self._lock = threading.Lock()

        self.routes_file.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_config_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def set_routes(self, routes: list[SingBoxRoute], auto_restart: bool = False) -> None:
        self._write_routes_file(self.routes_file, routes)

        if auto_restart and self.is_running():
            self.restart()

    def set_instance_routes(
        self, instance_id: str, routes: list[SingBoxRoute], auto_restart: bool = False
    ) -> None:
        safe_id = _safe_instance_id(instance_id)
        routes_file = self._instance_routes_file(safe_id)
        self._write_routes_file(routes_file, routes)
        existing = {
            str(item.get("instance_id") or ""): item
            for item in self.storage.list_backend_instances()
        }
        item = existing.get(safe_id, {})
        status = str(item.get("status") or "stopped")
        was_running = status == "running" or self._is_instance_process_running(safe_id)
        self.storage.upsert_backend_instance(
            instance_id=safe_id,
            pid=int(item.get("pid") or -1),
            config_file=str(item.get("config_file") or self.runtime_config_file),
            routes_file=str(routes_file),
            log_file=str(item.get("log_file") or self._instance_log_file(safe_id)),
            listen=_routes_listen_summary(routes),
            ports=[route.inbound_port for route in routes],
            status=status,
            last_error=str(item.get("last_error") or ""),
        )
        if auto_restart and was_running:
            self.stop_instance(safe_id)
            self.start_instance(safe_id, routes=routes)

    def create_instance(self, instance_id: str) -> dict[str, Any]:
        safe_id = _safe_instance_id(instance_id)
        existing = {
            str(item.get("instance_id") or ""): item
            for item in self.storage.list_backend_instances()
        }
        item = existing.get(safe_id)
        routes = self.get_instance_routes(safe_id)
        if item is not None:
            status = str(item.get("status") or "stopped")
            return self.storage.upsert_backend_instance(
                instance_id=safe_id,
                pid=int(item.get("pid") or -1),
                config_file=str(item.get("config_file") or self.runtime_config_file),
                routes_file=str(item.get("routes_file") or self._instance_routes_file(safe_id)),
                log_file=str(item.get("log_file") or self._instance_log_file(safe_id)),
                listen=_routes_listen_summary(routes),
                ports=[route.inbound_port for route in routes],
                status=status,
                last_error=str(item.get("last_error") or ""),
            )

        created = self.storage.upsert_backend_instance(
            instance_id=safe_id,
            pid=-1,
            config_file=str(self.runtime_config_file),
            routes_file=str(self._instance_routes_file(safe_id)),
            log_file=str(self._instance_log_file(safe_id)),
            listen=_routes_listen_summary(routes),
            ports=[route.inbound_port for route in routes],
            status="stopped",
        )
        self._record_process_event(
            action="create_instance",
            pid=-1,
            result="success",
            detail=f"created stopped instance {safe_id}",
        )
        return created

    def replace_failed_exit_proxy(
        self, old_key: str, new_key: str, auto_restart: bool = False
    ) -> int:
        old = str(old_key or "").strip()
        new = str(new_key or "").strip()
        if not old or not new or old == new:
            return 0
        if self.storage.get_proxy_by_key(new) is None:
            return 0
        routes = self.get_routes()
        changed = 0
        next_routes: list[SingBoxRoute] = []
        for route in routes:
            item = SingBoxRoute(**asdict(route))
            if item.exit_proxy_key == old:
                item.exit_proxy_key = new
                changed += 1
            elif item.proxy_key == old and not item.exit_proxy_key:
                item.proxy_key = new
                changed += 1
            next_routes.append(item)
        if changed <= 0:
            return 0
        self.set_routes(next_routes, auto_restart=auto_restart)
        self._record_process_event(
            action="replace_proxy",
            pid=self._pid_state,
            result="success",
            detail=f"replaced failed exit proxy {old} -> {new}; routes={changed}",
        )
        return changed

    def get_routes(self) -> list[SingBoxRoute]:
        return self._read_routes_file(self.routes_file)

    def get_instance_routes(self, instance_id: str) -> list[SingBoxRoute]:
        routes_file = self._instance_routes_file(_safe_instance_id(instance_id))
        if routes_file.exists():
            return self._read_routes_file(routes_file)
        return self.get_routes()

    def _write_routes_file(self, routes_file: Path, routes: list[SingBoxRoute]) -> None:
        _validate_routes(routes)
        routes_file.parent.mkdir(parents=True, exist_ok=True)
        routes_file.write_text(
            json.dumps([asdict(route) for route in routes], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_routes_file(self, routes_file: Path) -> list[SingBoxRoute]:
        if not routes_file.exists():
            return []

        data = json.loads(routes_file.read_text(encoding="utf-8") or "[]")
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
        self.start_instance("default")

    def start_instance(
        self, instance_id: str = "default", routes: list[SingBoxRoute] | None = None
    ) -> None:
        safe_id = _safe_instance_id(instance_id)
        with self._lock:
            self._pid_state = 0
            runtime_config_file: Path | None = None
            try:
                if self.backend_engine != "singbox":
                    raise RuntimeError(f"backend engine not supported: {self.backend_engine}")

                existing = self._processes.get(safe_id)
                if existing and existing.poll() is None:
                    self._pid_state = int(existing.pid)
                    return

                use_routes = routes if routes is not None else self.get_instance_routes(safe_id)
                self._assert_inbound_ports_available(use_routes)

                if shutil.which(self.binary) is None:
                    raise RuntimeError(f"sing-box binary not found: {self.binary}")

                config = self.build_runtime_config(routes=use_routes)
                runtime_config_file = self._new_runtime_config_file(safe_id)
                runtime_config_file.write_text(
                    json.dumps(config, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                log_file = self._instance_log_file(safe_id)
                log_handle = log_file.open("a", encoding="utf-8")
                process = subprocess.Popen(
                    [self.binary, "run", "-c", str(runtime_config_file)],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                )
                self._processes[safe_id] = process
                if safe_id == "default":
                    self._process = process
                self._current_runtime_config_file = runtime_config_file
                self._runtime_config_files[safe_id] = runtime_config_file
                if not self._wait_inbound_ports_ready(use_routes, timeout_sec=4.0):
                    raise RuntimeError("sing-box startup timeout: inbound ports not ready")
                self._pid_state = int(process.pid)
                self._last_health_ok = True
                self._auto_restart_attempts = 0
                self.storage.upsert_backend_instance(
                    instance_id=safe_id,
                    pid=self._pid_state,
                    config_file=str(runtime_config_file),
                    routes_file=str(self._instance_routes_file(safe_id)),
                    log_file=str(log_file),
                    listen=_routes_listen_summary(use_routes),
                    ports=[route.inbound_port for route in use_routes],
                    status="running",
                )
                self._record_process_event(
                    action="start", pid=self._pid_state, result="success", detail="started"
                )
            except Exception as exc:
                process = self._processes.get(safe_id)
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2.0)
                self._processes.pop(safe_id, None)
                if safe_id == "default":
                    self._process = None
                self._pid_state = -1
                self.storage.upsert_backend_instance(
                    instance_id=safe_id,
                    pid=-1,
                    config_file=str(runtime_config_file or self.runtime_config_file),
                    routes_file=str(self._instance_routes_file(safe_id)),
                    log_file=str(self._instance_log_file(safe_id)),
                    listen=_routes_listen_summary(
                        routes if routes is not None else self.get_instance_routes(safe_id)
                    ),
                    ports=[
                        route.inbound_port
                        for route in (
                            routes if routes is not None else self.get_instance_routes(safe_id)
                        )
                    ],
                    status="failed",
                    last_error=str(exc),
                )
                self._record_process_event(action="start", pid=-1, result="failed", detail=str(exc))
                raise

    def stop(self) -> None:
        self.stop_instance("default")

    def stop_instance(self, instance_id: str = "default") -> None:
        safe_id = _safe_instance_id(instance_id)
        with self._lock:
            process = self._processes.get(safe_id)
            if not process:
                if safe_id == "default":
                    self._process = None
                self._pid_state = -1
                self.storage.update_backend_instance_status(safe_id, "stopped", pid=-1)
                self._record_process_event(
                    action="stop", pid=-1, result="noop", detail="already stopped"
                )
                return
            if process.poll() is not None:
                pid = int(process.pid)
                self._processes.pop(safe_id, None)
                if safe_id == "default":
                    self._process = None
                self._pid_state = -1
                self.storage.update_backend_instance_status(safe_id, "exited", pid=pid)
                self._record_process_event(
                    action="stop", pid=pid, result="success", detail="already exited"
                )
                return
            pid = int(process.pid)
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)
            self._processes.pop(safe_id, None)
            if safe_id == "default":
                self._process = None
            self._pid_state = -1
            self._auto_restart_attempts = 0
            self.storage.update_backend_instance_status(safe_id, "stopped", pid=pid)
            self._record_process_event(action="stop", pid=pid, result="success", detail="stopped")

    def delete_instance(self, instance_id: str) -> bool:
        safe_id = _safe_instance_id(instance_id)
        self.stop_instance(safe_id)
        deleted = self.storage.delete_backend_instance(safe_id)
        result = "success" if deleted > 0 else "noop"
        self._record_process_event(
            action="delete_instance",
            pid=-1,
            result=result,
            detail=f"deleted instance {safe_id}"
            if deleted > 0
            else f"instance not found: {safe_id}",
        )
        return deleted > 0

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

    def _is_instance_process_running(self, instance_id: str) -> bool:
        process = self._processes.get(_safe_instance_id(instance_id))
        return bool(process and process.poll() is None)

    def status(self) -> dict[str, Any]:
        routes = self.get_routes()
        running = self.is_running()
        return {
            "backend": self.backend_engine,
            "binary": self.binary,
            "test_url": self.test_url,
            "running": running,
            "pid": self._pid_state
            if not running
            else int(self._process.pid)
            if self._process
            else self._pid_state,
            "auto_restart_max": self.auto_restart_max,
            "auto_restart_attempts": self._auto_restart_attempts,
            "routes_count": len(routes),
            "routes": [asdict(route) for route in routes],
            "runtime_config_file": str(
                self._current_runtime_config_file or self.runtime_config_file
            ),
            "log_file": str(self.log_file),
            "instances": self.list_instances(),
        }

    def list_instances(self) -> list[dict[str, Any]]:
        instances = self.storage.list_backend_instances()
        for item in instances:
            if str(item.get("status") or "") == "running" and not _is_process_alive(
                int(item.get("pid") or -1)
            ):
                self.storage.update_backend_instance_status(
                    str(item.get("instance_id") or ""), "exited", pid=int(item.get("pid") or -1)
                )
        return self.storage.list_backend_instances()

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
            return {
                "running": False,
                "ok": False,
                "reason": down_reason,
                "pid": -1,
                "restart_attempted": False,
            }

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
                return self._try_auto_restart(
                    reason="inbound ports not reachable", routes=routes, pid=pid
                )
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
                        "checked_at": datetime.now(UTC).isoformat(),
                    }
                results.append(item)

        return sorted(results, key=lambda x: int(x.get("route_index", 0)))

    def measure_route_latency(
        self, route: SingBoxRoute, timeout_sec: float = 10.0, route_index: int = -1
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
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

    def _new_runtime_config_file(self, instance_id: str = "default") -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        base_name = self.runtime_config_file.stem or "singbox"
        suffix = _safe_instance_id(instance_id)
        return self.runtime_config_file.with_name(f"{base_name}-{suffix}-{stamp}.json")

    def _instance_log_file(self, instance_id: str) -> Path:
        safe_id = _safe_instance_id(instance_id)
        if safe_id == "default":
            return self.log_file
        return self.log_file.with_name(
            f"{self.log_file.stem}-{safe_id}{self.log_file.suffix or '.log'}"
        )

    def _instance_routes_file(self, instance_id: str) -> Path:
        safe_id = _safe_instance_id(instance_id)
        if safe_id == "default":
            return self.routes_file
        return self.routes_file.with_name(
            f"{self.routes_file.stem}-{safe_id}{self.routes_file.suffix or '.json'}"
        )

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

    def _try_auto_restart(
        self, reason: str, routes: list[SingBoxRoute], pid: int = -1
    ) -> dict[str, Any]:
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

    # ---- Async wrappers to avoid blocking the event loop ----

    async def start_async(self) -> None:
        """Async wrapper for start()."""
        await asyncio.to_thread(self.start)

    async def start_instance_async(
        self, instance_id: str = "default", routes: list[SingBoxRoute] | None = None
    ) -> None:
        """Async wrapper for start_instance()."""
        await asyncio.to_thread(self.start_instance, instance_id, routes)

    async def stop_async(self) -> None:
        """Async wrapper for stop()."""
        await asyncio.to_thread(self.stop)

    async def stop_instance_async(self, instance_id: str = "default") -> None:
        """Async wrapper for stop_instance()."""
        await asyncio.to_thread(self.stop_instance, instance_id)

    async def restart_async(self) -> None:
        """Async wrapper for restart()."""
        await asyncio.to_thread(self.restart)

    async def health_check_async(
        self, timeout_sec: float = 1.5, auto_restart: bool = False
    ) -> dict[str, Any]:
        """Async wrapper for health_check()."""
        return await asyncio.to_thread(self.health_check, timeout_sec, auto_restart)

    async def measure_route_latency_async(
        self, route: SingBoxRoute, timeout_sec: float = 10.0, route_index: int = -1
    ) -> dict[str, Any]:
        """Async wrapper for measure_route_latency()."""
        return await asyncio.to_thread(self.measure_route_latency, route, timeout_sec, route_index)

    async def measure_all_routes_latency_async(
        self, timeout_sec: float = 10.0
    ) -> list[dict[str, Any]]:
        """Async wrapper for measure_all_routes_latency()."""
        return await asyncio.to_thread(self.measure_all_routes_latency, timeout_sec)


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


def _is_process_alive(pid: int) -> bool:
    if int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _safe_instance_id(instance_id: str) -> str:
    text = str(instance_id or "").strip() or "default"
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text)
    return safe[:80] or "default"


def _routes_listen_summary(routes: list[SingBoxRoute]) -> str:
    values = sorted({str(route.listen or "127.0.0.1") for route in routes})
    if not values:
        return "127.0.0.1"
    return ",".join(values)[:300]
