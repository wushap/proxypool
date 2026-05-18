from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(slots=True)
class ChainInstanceSpec:
    instance_id: str
    pool_id: int
    listen: str
    port: int
    inbound_type: str
    endpoint_id: int = 0
    hop_proxies: list[dict[str, Any]] = field(default_factory=list)
    route_signature: str = ""
    front_proxy: dict[str, Any] | None = None
    exit_proxy: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.hop_proxies:
            self.hop_proxies = list(self.hop_proxies)
            return
        hop_proxies: list[dict[str, Any]] = []
        if isinstance(self.front_proxy, dict) and self.front_proxy:
            hop_proxies.append(self.front_proxy)
        if isinstance(self.exit_proxy, dict) and self.exit_proxy:
            if not hop_proxies or self.exit_proxy is not hop_proxies[-1]:
                hop_proxies.append(self.exit_proxy)
        self.hop_proxies = hop_proxies


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
