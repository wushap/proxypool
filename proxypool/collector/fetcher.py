from __future__ import annotations

import json
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.request import ProxyHandler, Request, build_opener

from proxypool.tester.singbox import build_singbox_outbound


class FetchError(RuntimeError):
    pass


def fetch_text(url: str, timeout_sec: float = 12.0) -> str:
    req = Request(url, headers={"User-Agent": "proxypool/0.1"})
    try:
        with _open_url_no_proxy(req, timeout=timeout_sec) as resp:  # nosec B310
            raw = resp.read()
            content_type = str(resp.headers.get("Content-Type", ""))
    except Exception as exc:  # pragma: no cover - exercised by integration calls
        raise FetchError(str(exc)) from exc

    encoding = _extract_charset(content_type) or "utf-8"
    try:
        return raw.decode(encoding, errors="ignore")
    except Exception:
        return raw.decode("utf-8", errors="ignore")


def fetch_text_via_proxy_node(
    url: str,
    proxy_node: dict[str, Any],
    timeout_sec: float = 12.0,
    singbox_binary: str = "sing-box",
) -> str:
    outbound = build_singbox_outbound(proxy_node, tag="fetch-out")
    if outbound is None:
        raise FetchError("unsupported proxy protocol for subscription update")
    if shutil.which(singbox_binary) is None:
        raise FetchError("sing-box not found")
    curl = shutil.which("curl")
    if curl is None:
        raise FetchError("curl not found")

    try:
        local_port = _find_free_port()
    except OSError as exc:
        raise FetchError(f"local socket unavailable: {exc}") from exc

    config = {
        "log": {"disabled": True},
        "inbounds": [
            {
                "type": "socks",
                "tag": "fetch-in",
                "listen": "127.0.0.1",
                "listen_port": local_port,
            }
        ],
        "outbounds": [outbound],
        "route": {"final": "fetch-out"},
    }

    with tempfile.TemporaryDirectory(prefix="pp-sub-fetch-") as td:
        config_path = Path(td) / "config.json"
        config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.Popen(
            [singbox_binary, "run", "-c", str(config_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            if not _wait_port("127.0.0.1", local_port, timeout_sec=min(4.0, max(1.5, timeout_sec / 2))):
                raise FetchError("subscription proxy startup timeout")

            cmd = [
                curl,
                "-sS",
                "-L",
                "--max-time",
                str(max(2, int(timeout_sec))),
                "--proxy",
                f"socks5h://127.0.0.1:{local_port}",
                str(url),
            ]
            completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if completed.returncode != 0:
                err = (completed.stderr or f"curl exit={completed.returncode}").strip()
                raise FetchError(err[:500])
            return str(completed.stdout or "")
        finally:
            _stop_process(proc)


def _extract_charset(content_type: str) -> str | None:
    lowered = content_type.lower()
    marker = "charset="
    if marker not in lowered:
        return None
    return lowered.split(marker, 1)[1].split(";", 1)[0].strip()


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_port(host: str, port: int, timeout_sec: float) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with socket.create_connection((host, int(port)), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def _stop_process(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=1.0)


def _open_url_no_proxy(req: Request, timeout: float):
    opener = build_opener(ProxyHandler({}))
    return opener.open(req, timeout=timeout)
