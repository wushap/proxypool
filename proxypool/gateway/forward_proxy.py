from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from proxypool.gateway.config import HttpGatewayConfig
from proxypool.gateway.connect_session import ConnectSessionRegistry
from proxypool.gateway.session_extractor import SessionExtractor


class ForwardProxyGateway:
    def __init__(
        self,
        storage,
        pool_service,
        chain_service,
        chain_instance_manager,
        config: HttpGatewayConfig,
        connect_registry: ConnectSessionRegistry | None = None,
    ) -> None:
        self.storage = storage
        self.pool_service = pool_service
        self.chain_service = chain_service
        self.chain_instance_manager = chain_instance_manager
        self.config = config
        self.session_extractor = SessionExtractor()
        self.connect_registry = connect_registry or ConnectSessionRegistry()

    def extract_http_session_key(
        self,
        headers: Mapping[str, Any],
        query_params: Mapping[str, Any],
        target_host: str,
        target_path: str,
        rules: list[dict[str, Any]],
    ) -> str:
        session_id, _, _ = self.session_extractor.extract(
            headers=headers,
            query_params=query_params,
            target_host=target_host,
            target_path=target_path,
            header_names=self.config.http_session_header_names,
            query_names=self.config.http_session_query_names,
            rules=rules,
        )
        return session_id

    def extract_connect_session_key(self, headers: Mapping[str, Any], connection_id: str) -> str:
        normalized = {str(k).lower(): str(v or "").strip() for k, v in dict(headers).items()}
        for name in self.config.connect_session_header_names:
            value = normalized.get(str(name).lower(), "")
            if value:
                return value
        if self.config.session_missing_action == "REJECT":
            return ""
        return self.connect_registry.get_or_create(connection_id)

    def parse_proxy_target(self, raw_target: str) -> tuple[str, str, str]:
        parsed = urlsplit(str(raw_target or ""))
        return parsed.scheme, parsed.netloc, parsed.path or "/"
