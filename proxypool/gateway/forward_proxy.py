from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlsplit

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

    def _default_pool(self) -> dict[str, Any]:
        pool = self.pool_service.get_pool(self.config.default_pool_id)
        if pool is None:
            raise ValueError("default pool not found")
        return pool

    def resolve_route_for_http(self, raw_target: str, headers: Mapping[str, Any]) -> dict[str, Any]:
        pool = self._default_pool()
        parsed = urlsplit(str(raw_target or ""))
        query = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
        rules = self.storage.list_pool_session_rules(int(pool["id"]))
        session_id = self.extract_http_session_key(
            headers=headers,
            query_params=query,
            target_host=parsed.netloc,
            target_path=parsed.path or "/",
            rules=rules,
        )
        if not session_id and self.config.session_missing_action == "REJECT":
            raise ValueError("session_id is required")
        route = self.chain_service.route_request(
            session_id=session_id,
            pool_id=int(pool["id"]),
            target_domain=parsed.netloc,
            live_instance_ids=self.chain_instance_manager.list_running_instance_ids(int(pool["id"])),
        )
        if route is None:
            raise RuntimeError("no available chain route")
        instance = self.chain_instance_manager.ensure_instance(
            pool_id=int(pool["id"]),
            front_node_key=str(route["front_node"]["key"]),
            exit_node_key=str(route["exit_node"]["key"]),
            inbound_type="http",
        )
        if session_id:
            self.chain_service.bind_instance_to_session(session_id, int(pool["id"]), str(instance["instance_id"]))
        return {
            "pool": pool,
            "session_id": session_id,
            "route": route,
            "instance": instance,
            "target": parsed,
        }

    def resolve_route_for_connect(self, target_host: str, headers: Mapping[str, Any], connection_id: str) -> dict[str, Any]:
        pool = self._default_pool()
        session_id = self.extract_connect_session_key(headers=headers, connection_id=connection_id)
        if not session_id:
            raise ValueError("session_id is required")
        route = self.chain_service.route_request(
            session_id=session_id,
            pool_id=int(pool["id"]),
            target_domain=str(target_host or ""),
            live_instance_ids=self.chain_instance_manager.list_running_instance_ids(int(pool["id"])),
        )
        if route is None:
            raise RuntimeError("no available chain route")
        instance = self.chain_instance_manager.ensure_instance(
            pool_id=int(pool["id"]),
            front_node_key=str(route["front_node"]["key"]),
            exit_node_key=str(route["exit_node"]["key"]),
            inbound_type="http",
        )
        self.chain_service.bind_instance_to_session(session_id, int(pool["id"]), str(instance["instance_id"]))
        return {
            "pool": pool,
            "session_id": session_id,
            "route": route,
            "instance": instance,
            "target_host": target_host,
        }
