from __future__ import annotations

import asyncio
import json
import shutil
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ProbeResult:
    normalized_key: str
    available: bool
    latency_ms: int | None = None
    openai_unlocked: bool | None = None
    openai_status: str = ""
    error: str = ""


def build_singbox_outbound(node: dict[str, Any], tag: str = "probe-out") -> dict[str, Any] | None:
    protocol = str(node.get("protocol") or "").lower()
    host = str(node.get("host") or "")
    port = int(node.get("port") or 0)
    extra = node.get("extra") or {}

    if not host or port <= 0:
        return None

    if protocol == "ss":
        method = str(extra.get("cipher") or "")
        password = str(extra.get("password") or "")
        if not method or not password:
            return None
        return {
            "type": "shadowsocks",
            "tag": tag,
            "server": host,
            "server_port": port,
            "method": method,
            "password": password,
        }

    if protocol == "trojan":
        password = str(extra.get("password") or "")
        if not password:
            return None
        outbound: dict[str, Any] = {
            "type": "trojan",
            "tag": tag,
            "server": host,
            "server_port": port,
            "password": password,
        }
        sni = str(extra.get("sni") or extra.get("peer") or "")
        if sni:
            outbound["tls"] = {"enabled": True, "server_name": sni}
        return outbound

    if protocol == "vless":
        uuid = str(extra.get("uuid") or "")
        if not uuid:
            return None
        outbound = {
            "type": "vless",
            "tag": tag,
            "server": host,
            "server_port": port,
            "uuid": uuid,
        }
        security = str(extra.get("security") or "")
        sni = str(extra.get("sni") or extra.get("servername") or "")
        if security == "tls" or sni:
            outbound["tls"] = {"enabled": True}
            if sni:
                outbound["tls"]["server_name"] = sni
        return outbound

    if protocol == "vmess":
        uuid = str(extra.get("uuid") or "")
        if not uuid:
            return None
        outbound = {
            "type": "vmess",
            "tag": tag,
            "server": host,
            "server_port": port,
            "uuid": uuid,
            "security": "auto",
        }
        if str(extra.get("tls") or "") == "tls":
            outbound["tls"] = {"enabled": True}
        return outbound

    if protocol == "hysteria2":
        password = str(extra.get("password") or "")
        outbound = {
            "type": "hysteria2",
            "tag": tag,
            "server": host,
            "server_port": port,
        }
        if password:
            outbound["password"] = password
        sni = str(extra.get("sni") or "")
        if sni:
            outbound["tls"] = {"enabled": True, "server_name": sni}
        return outbound

    if protocol == "hysteria":
        auth = str(extra.get("password") or extra.get("auth") or "")
        outbound = {
            "type": "hysteria",
            "tag": tag,
            "server": host,
            "server_port": port,
        }
        if auth:
            outbound["auth_str"] = auth
        return outbound

    if protocol == "snell":
        psk = str(extra.get("password") or "")
        if not psk:
            return None
        return {
            "type": "snell",
            "tag": tag,
            "server": host,
            "server_port": port,
            "psk": psk,
            "version": 3,
        }

    if protocol == "http":
        outbound = {
            "type": "http",
            "tag": tag,
            "server": host,
            "server_port": port,
        }
        username = str(extra.get("username") or "")
        password = str(extra.get("password") or "")
        if username:
            outbound["username"] = username
        if password:
            outbound["password"] = password
        return outbound

    if protocol == "socks":
        outbound = {
            "type": "socks",
            "tag": tag,
            "server": host,
            "server_port": port,
        }
        username = str(extra.get("username") or "")
        password = str(extra.get("password") or "")
        if username:
            outbound["username"] = username
        if password:
            outbound["password"] = password
        return outbound

    return None


class SingboxProber:
    def __init__(
        self,
        binary: str = "sing-box",
        test_url: str = "https://www.cloudflare.com/cdn-cgi/trace",
        timeout_sec: float = 8.0,
        startup_timeout_sec: float = 2.0,
        openai_check_timeout_sec: float = 6.0,
    ) -> None:
        self.binary = binary
        self.test_url = test_url
        self.timeout_sec = timeout_sec
        self.startup_timeout_sec = startup_timeout_sec
        self.openai_check_timeout_sec = openai_check_timeout_sec

    def fetch_json_via_proxy(
        self,
        node: dict[str, Any],
        url: str,
        timeout_sec: float = 8.0,
        front_proxy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = str(node.get("normalized_key") or "")
        target_outbound = build_singbox_outbound(node, tag="probe-out")
        if target_outbound is None:
            raise RuntimeError(f"unsupported protocol: {key}")
        config: dict[str, Any]
        final_tag = "probe-out"
        outbounds: list[dict[str, Any]] = [target_outbound]
        if front_proxy is not None:
            front_key = str(front_proxy.get("normalized_key") or "")
            front_outbound = build_singbox_outbound(front_proxy, tag="probe-front")
            if front_outbound is None:
                raise RuntimeError(f"unsupported front protocol: {front_key}")
            target_outbound["tag"] = "probe-target"
            target_outbound["detour"] = "probe-front"
            outbounds = [front_outbound, target_outbound]
            final_tag = "probe-target"

        if shutil.which(self.binary) is None:
            raise RuntimeError("sing-box not found")
        curl = shutil.which("curl")
        if curl is None:
            raise RuntimeError("curl not found")

        try:
            local_port = _find_free_port()
        except OSError as exc:
            raise RuntimeError(f"local socket unavailable: {exc}") from exc

        config = self._build_runtime_config_with_chain(outbounds=outbounds, final_tag=final_tag, local_port=local_port)
        with tempfile.TemporaryDirectory(prefix="pp-singbox-") as td:
            config_path = Path(td) / "config.json"
            config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            proc = subprocess.Popen(
                [self.binary, "run", "-c", str(config_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                if not self._wait_port("127.0.0.1", local_port, self.startup_timeout_sec):
                    raise RuntimeError("sing-box startup timeout")
                cmd = [
                    curl,
                    "-sS",
                    "--max-time",
                    str(max(1, int(timeout_sec))),
                    "--proxy",
                    f"socks5h://127.0.0.1:{local_port}",
                    url,
                ]
                completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
                if completed.returncode != 0:
                    err = (completed.stderr or "").strip() or f"curl exit={completed.returncode}"
                    raise RuntimeError(err[:300])
                text = (completed.stdout or "").strip()
                if not text:
                    raise RuntimeError("empty response")
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"invalid json response: {exc}") from exc
                if not isinstance(payload, dict):
                    raise RuntimeError("json payload is not object")
                return payload
            finally:
                _stop_process(proc)

    def probe(self, node: dict[str, Any]) -> ProbeResult:
        key = str(node.get("normalized_key") or "")
        if not key:
            return ProbeResult(normalized_key="", available=False, error="missing normalized_key")

        outbound = build_singbox_outbound(node, tag="probe-out")
        if outbound is None:
            return self._tcp_fallback(node, key, error_prefix="unsupported protocol")

        if shutil.which(self.binary) is None:
            return self._tcp_fallback(node, key, error_prefix="sing-box not found")

        try:
            local_port = _find_free_port()
        except OSError as exc:
            return ProbeResult(normalized_key=key, available=False, error=f"local socket unavailable: {exc}")
        config = self._build_runtime_config(outbound, local_port)

        with tempfile.TemporaryDirectory(prefix="pp-singbox-") as td:
            config_path = Path(td) / "config.json"
            config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

            proc = subprocess.Popen(
                [self.binary, "run", "-c", str(config_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                if not self._wait_port("127.0.0.1", local_port, self.startup_timeout_sec):
                    return self._tcp_fallback(node, key, error_prefix="sing-box startup timeout")

                curl = shutil.which("curl")
                if curl is None:
                    return self._tcp_fallback(node, key, error_prefix="curl not found")

                started = time.perf_counter()
                cmd = [
                    curl,
                    "-sS",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{time_total}",
                    "--max-time",
                    str(int(self.timeout_sec)),
                    "--proxy",
                    f"socks5h://127.0.0.1:{local_port}",
                    self.test_url,
                ]
                completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
                elapsed_ms = int((time.perf_counter() - started) * 1000)

                if completed.returncode == 0:
                    text = (completed.stdout or "").strip()
                    latency_ms = _parse_curl_time_ms(text) or elapsed_ms
                    unlocked, unlock_status = self._check_openai_unlock(local_port)
                    return ProbeResult(
                        normalized_key=key,
                        available=True,
                        latency_ms=latency_ms,
                        openai_unlocked=unlocked,
                        openai_status=unlock_status,
                    )

                error = (completed.stderr or "").strip() or f"curl exit={completed.returncode}"
                return ProbeResult(normalized_key=key, available=False, error=error[:1000])
            finally:
                _stop_process(proc)

    async def probe_async(self, node: dict[str, Any]) -> ProbeResult:
        key = str(node.get("normalized_key") or "")
        if not key:
            return ProbeResult(normalized_key="", available=False, error="missing normalized_key")

        outbound = build_singbox_outbound(node, tag="probe-out")
        if outbound is None:
            return await self._tcp_fallback_async(node, key, error_prefix="unsupported protocol")

        if shutil.which(self.binary) is None:
            return await self._tcp_fallback_async(node, key, error_prefix="sing-box not found")

        try:
            local_port = _find_free_port()
        except OSError as exc:
            return ProbeResult(normalized_key=key, available=False, error=f"local socket unavailable: {exc}")

        config = self._build_runtime_config(outbound, local_port)
        with tempfile.TemporaryDirectory(prefix="pp-singbox-") as td:
            config_path = Path(td) / "config.json"
            config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            proc = await asyncio.create_subprocess_exec(
                self.binary,
                "run",
                "-c",
                str(config_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                if not await self._wait_port_async("127.0.0.1", local_port, self.startup_timeout_sec):
                    return await self._tcp_fallback_async(node, key, error_prefix="sing-box startup timeout")

                curl = shutil.which("curl")
                if curl is None:
                    return await self._tcp_fallback_async(node, key, error_prefix="curl not found")

                started = time.perf_counter()
                cmd = [
                    curl,
                    "-sS",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{time_total}",
                    "--max-time",
                    str(int(self.timeout_sec)),
                    "--proxy",
                    f"socks5h://127.0.0.1:{local_port}",
                    self.test_url,
                ]
                returncode, stdout_text, stderr_text = await _run_command_async(cmd, timeout_sec=self.timeout_sec + 1.0)
                elapsed_ms = int((time.perf_counter() - started) * 1000)

                if returncode == 0:
                    text = (stdout_text or "").strip()
                    latency_ms = _parse_curl_time_ms(text) or elapsed_ms
                    unlocked, unlock_status = await self._check_openai_unlock_async(local_port)
                    return ProbeResult(
                        normalized_key=key,
                        available=True,
                        latency_ms=latency_ms,
                        openai_unlocked=unlocked,
                        openai_status=unlock_status,
                    )

                error = (stderr_text or "").strip() or f"curl exit={returncode}"
                return ProbeResult(normalized_key=key, available=False, error=error[:1000])
            finally:
                await _stop_process_async(proc)

    async def probe_with_front_proxy_async(
        self,
        node: dict[str, Any],
        front_proxy: dict[str, Any],
    ) -> ProbeResult:
        key = str(node.get("normalized_key") or "")
        if not key:
            return ProbeResult(normalized_key="", available=False, error="missing normalized_key")

        target_outbound = build_singbox_outbound(node, tag="probe-target")
        if target_outbound is None:
            return ProbeResult(normalized_key=key, available=False, error="unsupported target protocol")
        front_outbound = build_singbox_outbound(front_proxy, tag="probe-front")
        if front_outbound is None:
            return ProbeResult(normalized_key=key, available=False, error="unsupported front protocol")
        target_outbound["detour"] = "probe-front"

        if shutil.which(self.binary) is None:
            return ProbeResult(normalized_key=key, available=False, error="sing-box not found")

        try:
            local_port = _find_free_port()
        except OSError as exc:
            return ProbeResult(normalized_key=key, available=False, error=f"local socket unavailable: {exc}")

        config = self._build_runtime_config_with_chain(
            outbounds=[front_outbound, target_outbound],
            final_tag="probe-target",
            local_port=local_port,
        )
        with tempfile.TemporaryDirectory(prefix="pp-singbox-") as td:
            config_path = Path(td) / "config.json"
            config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            proc = await asyncio.create_subprocess_exec(
                self.binary,
                "run",
                "-c",
                str(config_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                if not await self._wait_port_async("127.0.0.1", local_port, self.startup_timeout_sec):
                    return ProbeResult(normalized_key=key, available=False, error="sing-box startup timeout")

                curl = shutil.which("curl")
                if curl is None:
                    return ProbeResult(normalized_key=key, available=False, error="curl not found")

                started = time.perf_counter()
                cmd = [
                    curl,
                    "-sS",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{time_total}",
                    "--max-time",
                    str(int(self.timeout_sec)),
                    "--proxy",
                    f"socks5h://127.0.0.1:{local_port}",
                    self.test_url,
                ]
                returncode, stdout_text, stderr_text = await _run_command_async(cmd, timeout_sec=self.timeout_sec + 1.0)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                if returncode == 0:
                    text = (stdout_text or "").strip()
                    latency_ms = _parse_curl_time_ms(text) or elapsed_ms
                    unlocked, unlock_status = await self._check_openai_unlock_async(local_port)
                    return ProbeResult(
                        normalized_key=key,
                        available=True,
                        latency_ms=latency_ms,
                        openai_unlocked=unlocked,
                        openai_status=unlock_status,
                    )
                error = (stderr_text or "").strip() or f"curl exit={returncode}"
                return ProbeResult(normalized_key=key, available=False, error=error[:1000])
            finally:
                await _stop_process_async(proc)

    def _build_runtime_config(self, outbound: dict[str, Any], local_port: int) -> dict[str, Any]:
        return self._build_runtime_config_with_chain(outbounds=[outbound], final_tag="probe-out", local_port=local_port)

    def _build_runtime_config_with_chain(
        self,
        outbounds: list[dict[str, Any]],
        final_tag: str,
        local_port: int,
    ) -> dict[str, Any]:
        return {
            "log": {"disabled": True},
            "inbounds": [
                {
                    "type": "socks",
                    "tag": "probe-in",
                    "listen": "127.0.0.1",
                    "listen_port": local_port,
                }
            ],
            "outbounds": outbounds,
            "route": {"final": final_tag},
        }

    def _wait_port(self, host: str, port: int, timeout_sec: float) -> bool:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=0.2):
                    return True
            except OSError:
                time.sleep(0.05)
        return False

    async def _wait_port_async(self, host: str, port: int, timeout_sec: float) -> bool:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            try:
                reader, writer = await asyncio.open_connection(host, port)
                writer.close()
                await writer.wait_closed()
                return True
            except OSError:
                await asyncio.sleep(0.05)
        return False

    def _tcp_fallback(self, node: dict[str, Any], key: str, error_prefix: str) -> ProbeResult:
        host = str(node.get("host") or "")
        port = int(node.get("port") or 0)
        if not host or port <= 0:
            return ProbeResult(normalized_key=key, available=False, error=f"{error_prefix}: invalid host/port")

        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=self.timeout_sec):
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                return ProbeResult(
                    normalized_key=key,
                    available=True,
                    latency_ms=elapsed_ms,
                    openai_unlocked=None,
                    openai_status="not checked (tcp fallback)",
                )
        except OSError as exc:
            return ProbeResult(normalized_key=key, available=False, error=f"{error_prefix}: {exc}")

    async def _tcp_fallback_async(self, node: dict[str, Any], key: str, error_prefix: str) -> ProbeResult:
        host = str(node.get("host") or "")
        port = int(node.get("port") or 0)
        if not host or port <= 0:
            return ProbeResult(normalized_key=key, available=False, error=f"{error_prefix}: invalid host/port")

        started = time.perf_counter()
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=self.timeout_sec)
            writer.close()
            await writer.wait_closed()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return ProbeResult(
                normalized_key=key,
                available=True,
                latency_ms=elapsed_ms,
                openai_unlocked=None,
                openai_status="not checked (tcp fallback)",
            )
        except OSError as exc:
            return ProbeResult(normalized_key=key, available=False, error=f"{error_prefix}: {exc}")
        except asyncio.TimeoutError:
            return ProbeResult(normalized_key=key, available=False, error=f"{error_prefix}: timed out")

    def _check_openai_unlock(self, local_port: int) -> tuple[bool | None, str]:
        curl = shutil.which("curl")
        if curl is None:
            return None, "curl not found"

        cmd = [
            curl,
            "-sS",
            "--max-time",
            str(int(self.openai_check_timeout_sec)),
            "--proxy",
            f"socks5h://127.0.0.1:{local_port}",
            "-H",
            "Authorization: Bearer sk-invalid",
            "-w",
            "\n%{http_code}",
            "https://api.openai.com/v1/models",
        ]
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            return None, (completed.stderr or f"curl exit={completed.returncode}").strip()[:160]

        raw = (completed.stdout or "").strip()
        if not raw:
            return None, "empty response"
        if "\n" not in raw:
            return None, "unexpected response"

        body, status_code = raw.rsplit("\n", 1)
        status_code = status_code.strip()
        body_lower = body.lower()

        if status_code == "401":
            return True, "401 unauthorized"
        if status_code == "200":
            return True, "200 ok"
        if status_code == "403":
            if "unsupported_country_region_territory" in body_lower or "unsupported country" in body_lower:
                return False, "403 region blocked"
            return False, "403 forbidden"
        if status_code == "429":
            return True, "429 rate limited"
        return None, f"http {status_code}"

    async def _check_openai_unlock_async(self, local_port: int) -> tuple[bool | None, str]:
        curl = shutil.which("curl")
        if curl is None:
            return None, "curl not found"

        cmd = [
            curl,
            "-sS",
            "--max-time",
            str(int(self.openai_check_timeout_sec)),
            "--proxy",
            f"socks5h://127.0.0.1:{local_port}",
            "-H",
            "Authorization: Bearer sk-invalid",
            "-w",
            "\n%{http_code}",
            "https://api.openai.com/v1/models",
        ]
        returncode, stdout_text, stderr_text = await _run_command_async(cmd, timeout_sec=self.openai_check_timeout_sec + 1.0)
        if returncode != 0:
            return None, (stderr_text or f"curl exit={returncode}").strip()[:160]

        raw = (stdout_text or "").strip()
        if not raw:
            return None, "empty response"
        if "\n" not in raw:
            return None, "unexpected response"

        body, status_code = raw.rsplit("\n", 1)
        status_code = status_code.strip()
        body_lower = body.lower()

        if status_code == "401":
            return True, "401 unauthorized"
        if status_code == "200":
            return True, "200 ok"
        if status_code == "403":
            if "unsupported_country_region_territory" in body_lower or "unsupported country" in body_lower:
                return False, "403 region blocked"
            return False, "403 forbidden"
        if status_code == "429":
            return True, "429 rate limited"
        return None, f"http {status_code}"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _parse_curl_time_ms(text: str) -> int | None:
    if not text:
        return None
    try:
        return int(float(text) * 1000)
    except ValueError:
        return None


def _stop_process(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=1.0)


async def _stop_process_async(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=1.0)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()


async def _run_command_async(cmd: list[str], timeout_sec: float | None = None) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        if timeout_sec and timeout_sec > 0:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        else:
            stdout, stderr = await proc.communicate()
    except asyncio.TimeoutError:
        await _stop_process_async(proc)
        return 124, "", "command timeout"

    stdout_text = (stdout or b"").decode("utf-8", errors="ignore")
    stderr_text = (stderr or b"").decode("utf-8", errors="ignore")
    return int(proc.returncode or 0), stdout_text, stderr_text
