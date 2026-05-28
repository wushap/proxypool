from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from proxypool.backend.chain_instance_manager import ChainInstanceManager
from proxypool.gateway.session_extractor import SessionExtractor
from proxypool.pool.chain_service import ProxyChainService
from proxypool.storage.sqlite import SQLiteProxyStorage


@dataclass(slots=True)
class GatewayError(Exception):
    status_code: int
    detail: str


class UnifiedHttpGateway:
    def __init__(
        self,
        storage: SQLiteProxyStorage,
        pool_service: Any,
        chain_service: ProxyChainService,
        chain_instance_manager: ChainInstanceManager,
        transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
        session_extractor: SessionExtractor | None = None,
    ) -> None:
        self.storage = storage
        self.pool_service = pool_service
        self.chain_service = chain_service
        self.chain_instance_manager = chain_instance_manager
        self.transport = transport
        self.session_extractor = session_extractor or SessionExtractor()

    async def handle(
        self,
        method: str,
        pool_name: str,
        scheme: str,
        target_host: str,
        target_path: str,
        headers: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: bytes,
    ) -> httpx.Response:
        pool = self._get_pool_by_name(pool_name)
        if pool is None:
            raise GatewayError(status_code=404, detail="pool not found")
        if not bool(pool.get("chain_enabled")):
            raise GatewayError(status_code=409, detail="pool chain is not enabled")
        endpoint = self._get_endpoint_for_pool(pool_name=pool_name, pool_id=int(pool["id"]))

        session_id, _, extraction_failed = self.session_extractor.extract(
            headers=headers,
            query_params=query_params,
            target_host=target_host,
            target_path=target_path,
            header_names=list(
                (endpoint or {}).get("session_header_names")
                or list(pool.get("session_header_names") or [])
            ),
            query_names=list(
                (endpoint or {}).get("session_query_param_names")
                or list(pool.get("session_query_param_names") or [])
            ),
            rules=self.storage.list_pool_session_rules(int(pool["id"])),
        )
        if (
            extraction_failed
            and str(
                (endpoint or {}).get("session_missing_action")
                or pool.get("session_missing_action")
                or "RANDOM"
            ).upper()
            == "REJECT"
        ):
            raise GatewayError(status_code=400, detail="session_id is required")

        self.chain_service.initialize()
        route = self.chain_service.route_request(
            session_id=session_id,
            pool_id=int(pool["id"]),
            endpoint_id=int((endpoint or {}).get("id") or 0),
            target_domain=str(target_host or ""),
        )
        if route is None:
            raise GatewayError(status_code=503, detail="no available chain route")

        instance = self._ensure_route_instance(
            pool_id=int(pool["id"]),
            endpoint_id=int((endpoint or {}).get("id") or 0),
            route=route,
        )
        if session_id:
            self._bind_lease_instance_id(
                session_id=session_id,
                pool_id=int(pool["id"]),
                endpoint_id=int((endpoint or {}).get("id") or 0),
                instance_id=str(instance["instance_id"]),
            )

        target_url = self._build_target_url(
            scheme=scheme,
            target_host=target_host,
            target_path=target_path,
            query_params=query_params,
        )
        forward_headers = self._build_forward_headers(headers, pool=pool)
        proxy_url = f"http://{instance['listen']}:{int(instance['port'])}"

        client_kwargs: dict[str, Any] = {
            "transport": self.transport,
            "follow_redirects": False,
            "timeout": 60.0,
        }
        if self.transport is None:
            client_kwargs["proxy"] = proxy_url

        async with httpx.AsyncClient(**client_kwargs) as client:
            return await client.request(
                method=method.upper(),
                url=target_url,
                headers=forward_headers,
                content=body,
            )

    def _get_pool_by_name(self, pool_name: str) -> dict[str, Any] | None:
        if self.pool_service is not None and hasattr(self.pool_service, "get_pool_by_name"):
            return self.pool_service.get_pool_by_name(pool_name)
        safe_name = str(pool_name or "").strip()
        for item in self.storage.list_proxy_pools(limit=1000):
            if str(item.get("name") or "") == safe_name:
                return item
        return None

    def _get_endpoint_for_pool(self, pool_name: str, pool_id: int) -> dict[str, Any] | None:
        safe_name = str(pool_name or "").strip()
        for endpoint in self.storage.list_http_proxy_endpoints():
            hops = list(endpoint.get("hops") or [])
            if not hops or int(hops[0].get("pool_id") or 0) != int(pool_id):
                continue
            if str(endpoint.get("name") or "").strip() == safe_name:
                return endpoint
        for endpoint in self.storage.list_http_proxy_endpoints():
            hops = list(endpoint.get("hops") or [])
            if hops and int(hops[0].get("pool_id") or 0) == int(pool_id):
                return endpoint
        return None

    def _ensure_route_instance(
        self, pool_id: int, endpoint_id: int, route: dict[str, Any]
    ) -> dict[str, Any]:
        front_key = str(route.get("front_node", {}).get("key") or "").strip()
        exit_key = str(route.get("exit_node", {}).get("key") or "").strip()
        if not front_key or not exit_key:
            raise GatewayError(status_code=503, detail="invalid chain route")
        try:
            return self.chain_instance_manager.ensure_instance(
                pool_id=pool_id,
                front_node_key=front_key,
                exit_node_key=exit_key,
                inbound_type="http",
                endpoint_id=int(endpoint_id),
                hop_node_keys=list(route.get("hop_node_keys") or []),
                route_signature=str(route.get("route_signature") or ""),
            )
        except RuntimeError as exc:
            raise GatewayError(status_code=503, detail=str(exc)) from exc

    def _bind_lease_instance_id(
        self, session_id: str, pool_id: int, endpoint_id: int, instance_id: str
    ) -> None:
        self.chain_service.bind_instance_to_session(
            session_id=session_id,
            pool_id=pool_id,
            instance_id=instance_id,
            endpoint_id=endpoint_id,
        )

    def _build_target_url(
        self,
        scheme: str,
        target_host: str,
        target_path: str,
        query_params: Mapping[str, Any],
    ) -> str:
        safe_scheme = str(scheme or "").strip().lower()
        if safe_scheme not in {"http", "https"}:
            raise GatewayError(status_code=400, detail="unsupported target scheme")
        path = "/" + str(target_path or "").lstrip("/")
        query_string = urlencode(self._normalize_query_params(query_params), doseq=True)
        if query_string:
            return f"{safe_scheme}://{target_host}{path}?{query_string}"
        return f"{safe_scheme}://{target_host}{path}"

    def _build_forward_headers(
        self, headers: Mapping[str, Any], pool: Mapping[str, Any]
    ) -> dict[str, str]:
        stripped = {str(name).lower() for name in list(pool.get("session_header_names") or [])}
        forward_headers: dict[str, str] = {}
        for key, value in dict(headers).items():
            text = str(value or "")
            if str(key).lower() in stripped:
                continue
            if text:
                forward_headers[str(key)] = text
        return forward_headers

    def _normalize_query_params(self, query_params: Mapping[str, Any]) -> list[tuple[str, Any]]:
        normalized: list[tuple[str, Any]] = []
        for key, value in dict(query_params).items():
            if isinstance(value, (list, tuple)):
                for item in value:
                    normalized.append((str(key), item))
                continue
            normalized.append((str(key), value))
        return normalized
