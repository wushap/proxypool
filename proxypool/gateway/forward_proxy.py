from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlsplit

from proxypool.gateway.config import HttpGatewayConfig
from proxypool.gateway.connect_session import ConnectSessionRegistry
from proxypool.gateway.session_extractor import SessionExtractor


class ForwardProxyGateway:
    ROUTE_INSTANCE_ATTEMPT_CAP = 50

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

    def _list_running_instance_ids(self, pool_id: int, endpoint_id: int) -> set[str]:
        if int(endpoint_id or 0) > 0:
            return self.chain_instance_manager.list_running_instance_ids(
                pool_id=int(pool_id),
                endpoint_id=int(endpoint_id),
            )
        return self.chain_instance_manager.list_running_instance_ids(int(pool_id))

    def _route_request(
        self,
        session_id: str,
        pool_id: int,
        endpoint_id: int,
        target_domain: str,
        live_instance_ids: set[str],
    ) -> dict[str, Any] | None:
        if int(endpoint_id or 0) > 0:
            return self.chain_service.route_request(
                session_id=session_id,
                pool_id=int(pool_id),
                endpoint_id=int(endpoint_id),
                target_domain=target_domain,
                live_instance_ids=live_instance_ids,
            )
        return self.chain_service.route_request(
            session_id=session_id,
            pool_id=int(pool_id),
            target_domain=target_domain,
            live_instance_ids=live_instance_ids,
        )

    def _ensure_instance(
        self,
        pool_id: int,
        endpoint_id: int,
        route: dict[str, Any],
    ) -> dict[str, Any]:
        front_node_key = str(route["front_node"]["key"])
        exit_node_key = str(route["exit_node"]["key"])
        if int(endpoint_id or 0) > 0:
            return self.chain_instance_manager.ensure_instance(
                pool_id=int(pool_id),
                front_node_key=front_node_key,
                exit_node_key=exit_node_key,
                inbound_type="http",
                endpoint_id=int(endpoint_id),
                hop_node_keys=list(route.get("hop_node_keys") or []),
                route_signature=str(route.get("route_signature") or ""),
            )
        return self.chain_instance_manager.ensure_instance(
            pool_id=int(pool_id),
            front_node_key=front_node_key,
            exit_node_key=exit_node_key,
            inbound_type="http",
        )

    def _route_instance_attempts(self, endpoint: dict[str, Any] | None) -> int:
        if endpoint is None:
            return 1
        total = 1
        for hop in list(endpoint.get("hops") or []):
            pool_id = int(hop.get("pool_id") or 0)
            if pool_id <= 0:
                return 1
            try:
                candidates = [
                    item for item in self.storage.list_proxy_pool_candidates(pool_id, limit=500)
                    if bool(item.get("available"))
                ]
            except Exception:
                return 1
            if not candidates:
                return 1
            total *= len(candidates)
            if total >= self.ROUTE_INSTANCE_ATTEMPT_CAP:
                return self.ROUTE_INSTANCE_ATTEMPT_CAP
        return max(1, min(self.ROUTE_INSTANCE_ATTEMPT_CAP, total))

    def _resolve_route_with_instance(
        self,
        pool: dict[str, Any],
        endpoint: dict[str, Any] | None,
        session_id: str,
        target_domain: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        import time as _time

        endpoint_id = int((endpoint or {}).get("id") or 0)
        pool_id = int(pool["id"])
        attempts = self._route_instance_attempts(endpoint)
        last_error: Exception | None = None
        failed_routes: list[str] = []  # Track failed route signatures to avoid retrying

        for attempt_idx in range(attempts):
            route = self._route_request(
                session_id=session_id,
                pool_id=pool_id,
                endpoint_id=endpoint_id,
                target_domain=target_domain,
                live_instance_ids=self._list_running_instance_ids(
                    pool_id=pool_id,
                    endpoint_id=endpoint_id,
                ),
            )
            if route is None:
                break

            # Skip routes we've already failed on
            route_sig = str(route.get("route_signature") or "")
            if route_sig in failed_routes:
                continue

            try:
                instance = self._ensure_instance(
                    pool_id=pool_id,
                    endpoint_id=endpoint_id,
                    route=route,
                )
                return route, instance
            except Exception as exc:
                last_error = exc
                failed_routes.append(route_sig)
                self.report_route_failure({
                    "endpoint": endpoint,
                    "pool": pool,
                    "session_id": session_id,
                    "route": route,
                    "instance": {},
                }, str(exc) or exc.__class__.__name__)

                # Small cooldown between retries to avoid rapid process spawning
                if attempt_idx < attempts - 1:
                    _time.sleep(0.1)

        if last_error is not None:
            raise RuntimeError(f"no available chain route: {last_error}") from last_error
        raise RuntimeError("no available chain route")

    def _bind_instance_to_session(
        self,
        session_id: str,
        pool_id: int,
        endpoint_id: int,
        instance_id: str,
    ) -> None:
        if int(endpoint_id or 0) > 0:
            self.chain_service.bind_instance_to_session(
                session_id,
                int(pool_id),
                str(instance_id or ""),
                endpoint_id=int(endpoint_id),
            )
            return
        self.chain_service.bind_instance_to_session(
            session_id,
            int(pool_id),
            str(instance_id or ""),
        )

    def report_route_failure(self, route: dict[str, Any], error: str = "") -> None:
        endpoint_id = int((route.get("endpoint") or {}).get("id") or (route.get("route") or {}).get("endpoint_id") or 0)
        pool_id = int((route.get("pool") or {}).get("id") or (route.get("route") or {}).get("pool_id") or 0)
        session_id = str(route.get("session_id") or "").strip()
        hop_node_keys = list((route.get("route") or {}).get("hop_node_keys") or [])
        if endpoint_id > 0 and hasattr(self.chain_service, "report_endpoint_route_failure"):
            self.chain_service.report_endpoint_route_failure(
                endpoint_id=endpoint_id,
                pool_id=pool_id,
                session_id=session_id,
                hop_node_keys=hop_node_keys,
            )
        instance_id = str((route.get("instance") or {}).get("instance_id") or "").strip()
        if instance_id and hasattr(self.chain_instance_manager, "mark_instance_failed"):
            self.chain_instance_manager.mark_instance_failed(instance_id, error)

    def report_route_success(self, route: dict[str, Any]) -> None:
        endpoint_id = int((route.get("endpoint") or {}).get("id") or (route.get("route") or {}).get("endpoint_id") or 0)
        hop_node_keys = list((route.get("route") or {}).get("hop_node_keys") or [])
        if endpoint_id > 0 and hasattr(self.chain_service, "report_endpoint_route_success"):
            self.chain_service.report_endpoint_route_success(
                endpoint_id=endpoint_id,
                hop_node_keys=hop_node_keys,
            )

    def _default_endpoint(self) -> dict[str, Any]:
        safe_endpoint_id = int(self.config.endpoint_id or 0)
        if safe_endpoint_id <= 0:
            raise ValueError("default endpoint not found")
        endpoint = self.storage.get_http_proxy_endpoint(safe_endpoint_id)
        if endpoint is None:
            raise ValueError("default endpoint not found")
        return endpoint

    def resolve_route_for_http(self, raw_target: str, headers: Mapping[str, Any]) -> dict[str, Any]:
        endpoint = None
        pool = None
        entry_pool_id = 0
        try:
            endpoint = self._default_endpoint()
        except ValueError:
            endpoint = None
        if endpoint is not None:
            hops = list(endpoint.get("hops") or [])
            if not hops:
                raise ValueError("endpoint hops are not configured")
            entry_pool_id = int(hops[0].get("pool_id") or 0)
            pool = self.pool_service.get_pool(entry_pool_id)
            if pool is None:
                raise ValueError("entry pool not found")
        else:
            pool = self._default_pool()
            entry_pool_id = int(pool["id"])
        parsed = urlsplit(str(raw_target or ""))
        query = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
        rules = self.storage.list_pool_session_rules(int(pool["id"])) if int(pool["id"]) > 0 else []
        session_id = self.extract_http_session_key(
            headers=headers,
            query_params=query,
            target_host=parsed.netloc,
            target_path=parsed.path or "/",
            rules=rules,
        )
        missing_action = str((endpoint or {}).get("session_missing_action") or self.config.session_missing_action or "RANDOM").upper()
        if not session_id and missing_action == "REJECT":
            raise ValueError("session_id is required")
        route, instance = self._resolve_route_with_instance(
            pool=pool,
            endpoint=endpoint,
            session_id=session_id,
            target_domain=parsed.netloc,
        )
        if session_id:
            self._bind_instance_to_session(
                session_id=session_id,
                pool_id=int(pool["id"]),
                endpoint_id=int((endpoint or {}).get("id") or 0),
                instance_id=str(instance["instance_id"]),
            )
        return {
            "endpoint": endpoint,
            "pool": pool,
            "session_id": session_id,
            "route": route,
            "instance": instance,
            "target": parsed,
        }

    def resolve_route_for_connect(self, target_host: str, headers: Mapping[str, Any], connection_id: str) -> dict[str, Any]:
        endpoint = None
        pool = None
        try:
            endpoint = self._default_endpoint()
        except ValueError:
            endpoint = None
        if endpoint is not None:
            hops = list(endpoint.get("hops") or [])
            if not hops:
                raise ValueError("endpoint hops are not configured")
            entry_pool_id = int(hops[0].get("pool_id") or 0)
            pool = self.pool_service.get_pool(entry_pool_id)
            if pool is None:
                raise ValueError("entry pool not found")
        else:
            pool = self._default_pool()
        session_id = self.extract_connect_session_key(headers=headers, connection_id=connection_id)
        if not session_id:
            raise ValueError("session_id is required")
        route, instance = self._resolve_route_with_instance(
            pool=pool,
            endpoint=endpoint,
            session_id=session_id,
            target_domain=str(target_host or ""),
        )
        self._bind_instance_to_session(
            session_id=session_id,
            pool_id=int(pool["id"]),
            endpoint_id=int((endpoint or {}).get("id") or 0),
            instance_id=str(instance["instance_id"]),
        )
        return {
            "endpoint": endpoint,
            "pool": pool,
            "session_id": session_id,
            "route": route,
            "instance": instance,
            "target_host": target_host,
        }
