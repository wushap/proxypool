from __future__ import annotations

import os
import shutil
import subprocess
import threading
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
