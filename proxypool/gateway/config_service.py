from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from proxypool.gateway.config import HttpGatewayConfig
from proxypool.storage.sqlite import SQLiteProxyStorage


class HttpGatewayConfigService:
    STORAGE_KEY = "http_gateway_config_v1"

    def __init__(self, storage: SQLiteProxyStorage) -> None:
        self.storage = storage

    def get_config(self) -> HttpGatewayConfig:
        raw = self.storage.get_app_setting(self.STORAGE_KEY, "")
        if not raw:
            return HttpGatewayConfig()
        data = json.loads(raw)
        if "endpoint_id" not in data:
            data["endpoint_id"] = 0
        if "health_check_enabled" not in data:
            data["health_check_enabled"] = True
        if "health_check_interval_sec" not in data:
            data["health_check_interval_sec"] = 30
        return HttpGatewayConfig(**data)

    def update_config(self, **kwargs: Any) -> HttpGatewayConfig:
        current = self.get_config()
        payload = asdict(current)
        payload.update(kwargs)
        updated = HttpGatewayConfig(**payload)
        self.storage.set_app_setting(
            self.STORAGE_KEY,
            json.dumps(asdict(updated), ensure_ascii=False, separators=(",", ":")),
        )
        return updated
