from __future__ import annotations

from dataclasses import dataclass, field


def _normalize_names(values: list[str] | None, default: list[str]) -> list[str]:
    items = [str(item or "").strip() for item in list(values or [])]
    cleaned = [item for item in items if item]
    return cleaned or list(default)


@dataclass(slots=True)
class HttpGatewayConfig:
    enabled: bool = False
    listen_host: str = "127.0.0.1"
    listen_port: int = 8899
    endpoint_id: int = 0
    default_pool_id: int = 0
    sticky_ttl_sec: int = 3600
    session_missing_action: str = "RANDOM"
    http_session_header_names: list[str] = field(default_factory=lambda: ["X-ProxyPool-Session"])
    http_session_query_names: list[str] = field(default_factory=lambda: ["session"])
    connect_session_header_names: list[str] = field(default_factory=lambda: ["X-ProxyPool-Session"])

    def __post_init__(self) -> None:
        self.listen_host = str(self.listen_host or "127.0.0.1").strip() or "127.0.0.1"
        self.listen_port = int(self.listen_port)
        if self.listen_port < 1 or self.listen_port > 65535:
            raise ValueError("listen_port must be between 1 and 65535")
        self.endpoint_id = max(0, int(self.endpoint_id))
        self.default_pool_id = max(0, int(self.default_pool_id))
        self.sticky_ttl_sec = max(1, int(self.sticky_ttl_sec))
        action = str(self.session_missing_action or "RANDOM").strip().upper() or "RANDOM"
        if action not in {"RANDOM", "REJECT"}:
            raise ValueError("session_missing_action must be RANDOM or REJECT")
        self.session_missing_action = action
        self.http_session_header_names = _normalize_names(self.http_session_header_names, ["X-ProxyPool-Session"])
        self.http_session_query_names = _normalize_names(self.http_session_query_names, ["session"])
        self.connect_session_header_names = _normalize_names(self.connect_session_header_names, ["X-ProxyPool-Session"])
