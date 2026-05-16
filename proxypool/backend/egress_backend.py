from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(slots=True)
class ChainInstanceSpec:
    instance_id: str
    pool_id: int
    listen: str
    port: int
    inbound_type: str
    front_proxy: dict[str, Any]
    exit_proxy: dict[str, Any]


@dataclass(slots=True)
class StartedInstance:
    pid: int
    config_file: Path
    log_file: Path


class EgressBackend(Protocol):
    backend_type: str

    def build_config(self, spec: ChainInstanceSpec) -> dict[str, Any]:
        ...

    def start(self, spec: ChainInstanceSpec) -> StartedInstance:
        ...

    def stop(self, instance_id: str) -> None:
        ...
