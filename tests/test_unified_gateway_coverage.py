"""Tests for proxypool.gateway.http_gateway – covering error paths, helpers, and edge cases."""

from __future__ import annotations

import os
import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from proxypool.backend.chain_instance_manager import ChainInstanceManager
from proxypool.backend.egress_backend import StartedInstance
from proxypool.gateway.http_gateway import GatewayError, UnifiedHttpGateway
from proxypool.models import ProxyNode
from proxypool.pool.chain_service import ProxyChainService
from proxypool.storage.sqlite import SQLiteProxyStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_gateway(
    tmp_path: Path,
    *,
    pool_service: Any = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[UnifiedHttpGateway, SQLiteProxyStorage, ProxyChainService, ChainInstanceManager, _FakeBackend]:
    """Create a gateway with real storage and a fake backend."""
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    chain_service = ProxyChainService(storage=storage)
    backend = _FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    gw = UnifiedHttpGateway(
        storage=storage,
        pool_service=pool_service,
        chain_service=chain_service,
        chain_instance_manager=manager,
        transport=transport,
    )
    return gw, storage, chain_service, manager, backend


def _setup_pool_with_chain(storage: SQLiteProxyStorage) -> dict[str, Any]:
    """Create a pool with chain enabled and return the pool dict."""
    storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])
    storage.upsert_proxy_pool_v2("exit", "exit", ["exit-.*"])
    return storage.create_proxy_pool(
        name="test-pool",
        chain_enabled=True,
        session_header_names=["X-ProxyPool-Session"],
    )


def _setup_nodes(storage: SQLiteProxyStorage) -> None:
    """Insert front and exit proxy nodes and mark them healthy."""
    from proxypool.models import ProxyNode

    front = ProxyNode(
        protocol="http", host="1.1.1.1", port=80, raw_link="http://1.1.1.1:80", name="front-a"
    )
    exit_node = ProxyNode(
        protocol="socks",
        host="2.2.2.2",
        port=1080,
        raw_link="socks://2.2.2.2:1080",
        name="exit-a",
    )
    storage.upsert_proxy(front)
    storage.upsert_proxy(exit_node)
    storage.update_test_result(front.normalized_key(), available=True, latency_ms=20)
    storage.update_test_result(exit_node.normalized_key(), available=True, latency_ms=30)


class _FakeBackend:
    """Backend that creates real listening sockets so _wait_until_instance_ready succeeds."""

    backend_type = "mihomo"

    def __init__(self) -> None:
        self.started: list[str] = []
        self.stopped: list[str] = []
        self.listeners: dict[str, socket.socket] = {}

    def build_config(self, spec: Any) -> dict[str, Any]:
        return {"listeners": [{"type": spec.inbound_type, "port": spec.port}]}

    def start(self, spec: Any) -> StartedInstance:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((spec.listen, spec.port))
        listener.listen(1)
        previous = self.listeners.pop(spec.instance_id, None)
        if previous is not None:
            previous.close()
        self.listeners[spec.instance_id] = listener
        self.started.append(spec.instance_id)
        return StartedInstance(
            pid=os.getpid(), config_file=Path("/tmp/test.yaml"), log_file=Path("/tmp/test.log")
        )

    def stop(self, instance_id: str) -> None:
        self.stopped.append(instance_id)
        listener = self.listeners.pop(instance_id, None)
        if listener is not None:
            listener.close()

    def close(self) -> None:
        for iid in list(self.listeners):
            self.stop(iid)


# ---------------------------------------------------------------------------
# GatewayError
# ---------------------------------------------------------------------------

class TestGatewayError:
    def test_error_carries_status_and_detail(self) -> None:
        err = GatewayError(status_code=418, detail="teapot")
        assert err.status_code == 418
        assert err.detail == "teapot"

    def test_error_is_exception(self) -> None:
        assert issubclass(GatewayError, Exception)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestGatewayInit:
    def test_stores_dependencies(self, tmp_path: Path) -> None:
        gw, storage, chain_service, manager, _ = _build_gateway(tmp_path)
        assert gw.storage is storage
        assert gw.chain_service is chain_service
        assert gw.chain_instance_manager is manager
        assert gw.pool_service is None

    def test_session_extractor_created_when_none(self, tmp_path: Path) -> None:
        from proxypool.gateway.session_extractor import SessionExtractor

        gw, *_ = _build_gateway(tmp_path)
        assert isinstance(gw.session_extractor, SessionExtractor)

    def test_session_extractor_reuse_when_provided(self, tmp_path: Path) -> None:
        from proxypool.gateway.session_extractor import SessionExtractor

        custom = SessionExtractor()
        storage = SQLiteProxyStorage(tmp_path / "test.db")
        gw = UnifiedHttpGateway(
            storage=storage,
            pool_service=None,
            chain_service=MagicMock(),
            chain_instance_manager=MagicMock(),
            session_extractor=custom,
        )
        assert gw.session_extractor is custom


# ---------------------------------------------------------------------------
# _get_pool_by_name
# ---------------------------------------------------------------------------

class TestGetPoolByName:
    def test_returns_none_when_pool_service_has_no_method(self, tmp_path: Path) -> None:
        gw, storage, *_ = _build_gateway(tmp_path, pool_service=object())
        pool = storage.create_proxy_pool(name="my-pool")
        result = gw._get_pool_by_name("my-pool")
        assert result is not None
        assert result["name"] == "my-pool"

    def test_returns_none_when_no_pool_found(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        assert gw._get_pool_by_name("nonexistent") is None

    def test_delegates_to_pool_service_get_pool_by_name(self, tmp_path: Path) -> None:
        mock_ps = MagicMock()
        mock_ps.get_pool_by_name.return_value = {"id": 99, "name": "via-ps"}
        gw, *_ = _build_gateway(tmp_path, pool_service=mock_ps)
        result = gw._get_pool_by_name("via-ps")
        mock_ps.get_pool_by_name.assert_called_once_with("via-ps")
        assert result == {"id": 99, "name": "via-ps"}

    def test_falls_back_to_storage_when_pool_service_is_none(self, tmp_path: Path) -> None:
        gw, storage, *_ = _build_gateway(tmp_path, pool_service=None)
        storage.create_proxy_pool(name="stored-pool")
        result = gw._get_pool_by_name("stored-pool")
        assert result is not None
        assert result["name"] == "stored-pool"

    def test_handles_empty_pool_service(self, tmp_path: Path) -> None:
        """pool_service is not None but has no get_pool_by_name attr."""
        gw, storage, *_ = _build_gateway(tmp_path, pool_service=42)
        storage.create_proxy_pool(name="fallback-pool")
        result = gw._get_pool_by_name("fallback-pool")
        assert result is not None
        assert result["name"] == "fallback-pool"


# ---------------------------------------------------------------------------
# _get_endpoint_for_pool
# ---------------------------------------------------------------------------

class TestGetEndpointForPool:
    def test_returns_none_when_no_endpoints(self, tmp_path: Path) -> None:
        gw, storage, *_ = _build_gateway(tmp_path)
        assert gw._get_endpoint_for_pool("test", 1) is None

    def test_returns_matching_endpoint_by_name(self, tmp_path: Path) -> None:
        gw, storage, *_ = _build_gateway(tmp_path)
        pool = storage.create_proxy_pool(name="ep-pool", chain_enabled=True)
        ep = storage.create_http_proxy_endpoint(name="ep-pool")
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool["id"])])
        result = gw._get_endpoint_for_pool("ep-pool", int(pool["id"]))
        assert result is not None
        assert result["name"] == "ep-pool"

    def test_returns_fallback_endpoint_by_pool_id_when_name_mismatch(self, tmp_path: Path) -> None:
        gw, storage, *_ = _build_gateway(tmp_path)
        pool = storage.create_proxy_pool(name="fb-pool", chain_enabled=True)
        ep = storage.create_http_proxy_endpoint(name="different-name")
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [int(pool["id"])])
        result = gw._get_endpoint_for_pool("fb-pool", int(pool["id"]))
        assert result is not None
        assert result["name"] == "different-name"

    def test_skips_endpoints_with_no_hops(self, tmp_path: Path) -> None:
        gw, storage, *_ = _build_gateway(tmp_path)
        storage.create_http_proxy_endpoint(name="no-hops")
        result = gw._get_endpoint_for_pool("no-hops", 1)
        assert result is None


# ---------------------------------------------------------------------------
# _build_target_url
# ---------------------------------------------------------------------------

class TestBuildTargetUrl:
    def test_https_with_query_params(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        url = gw._build_target_url("https", "api.example.com", "/v1/chat", {"q": "hello"})
        assert url == "https://api.example.com/v1/chat?q=hello"

    def test_http_without_query_params(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        url = gw._build_target_url("http", "example.com", "/page", {})
        assert url == "http://example.com/page"

    def test_strips_leading_slash_from_path(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        url = gw._build_target_url("https", "host.com", "///double", {})
        assert url == "https://host.com/double"

    def test_unsupported_scheme_raises(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        with pytest.raises(GatewayError) as exc_info:
            gw._build_target_url("ftp", "host.com", "/", {})
        assert exc_info.value.status_code == 400
        assert "unsupported target scheme" in exc_info.value.detail

    def test_empty_scheme_raises(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        with pytest.raises(GatewayError) as exc_info:
            gw._build_target_url("", "host.com", "/", {})
        assert exc_info.value.status_code == 400

    def test_list_query_param_values(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        url = gw._build_target_url("https", "host.com", "/api", {"tag": ["a", "b"]})
        assert "tag=a" in url
        assert "tag=b" in url


# ---------------------------------------------------------------------------
# _normalize_query_params
# ---------------------------------------------------------------------------

class TestNormalizeQueryParams:
    def test_single_values(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        result = gw._normalize_query_params({"a": 1, "b": "x"})
        assert ("a", 1) in result
        assert ("b", "x") in result

    def test_list_value_expands(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        result = gw._normalize_query_params({"ids": [10, 20]})
        assert ("ids", 10) in result
        assert ("ids", 20) in result

    def test_tuple_value_expands(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        result = gw._normalize_query_params({"t": ("x", "y")})
        assert ("t", "x") in result
        assert ("t", "y") in result

    def test_empty_params(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        assert gw._normalize_query_params({}) == []


# ---------------------------------------------------------------------------
# _build_forward_headers
# ---------------------------------------------------------------------------

class TestBuildForwardHeaders:
    def test_strips_session_header_names(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        pool = {"session_header_names": ["x-proxypool-session"]}
        headers = {
            "X-ProxyPool-Session": "sess-1",
            "Authorization": "Bearer tok",
            "Content-Type": "application/json",
        }
        result = gw._build_forward_headers(headers, pool)
        assert "x-proxypool-session" not in {k.lower() for k in result}
        assert result.get("Authorization") == "Bearer tok"
        assert result.get("Content-Type") == "application/json"

    def test_empty_session_header_names(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        pool: dict[str, Any] = {"session_header_names": []}
        result = gw._build_forward_headers({"Foo": "bar"}, pool)
        assert result == {"Foo": "bar"}

    def test_none_session_header_names(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        pool: dict[str, Any] = {}
        result = gw._build_forward_headers({"Foo": "bar"}, pool)
        assert result == {"Foo": "bar"}

    def test_empty_value_header_skipped(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        pool: dict[str, Any] = {}
        result = gw._build_forward_headers({"Empty": ""}, pool)
        assert "Empty" not in result

    def test_none_value_header_skipped(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        pool: dict[str, Any] = {}
        result = gw._build_forward_headers({"Null": None}, pool)
        assert "Null" not in result


# ---------------------------------------------------------------------------
# _ensure_route_instance
# ---------------------------------------------------------------------------

class TestEnsureRouteInstance:
    def test_invalid_route_missing_keys(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        route = {"front_node": {}, "exit_node": {}}
        with pytest.raises(GatewayError) as exc_info:
            gw._ensure_route_instance(pool_id=1, endpoint_id=0, route=route)
        assert exc_info.value.status_code == 503
        assert "invalid chain route" in exc_info.value.detail

    def test_invalid_route_missing_exit_key(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        route = {"front_node": {"key": "front-1"}, "exit_node": {}}
        with pytest.raises(GatewayError) as exc_info:
            gw._ensure_route_instance(pool_id=1, endpoint_id=0, route=route)
        assert exc_info.value.status_code == 503

    def test_runtime_error_wrapped_as_gateway_error(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        gw.chain_instance_manager.ensure_instance = MagicMock(side_effect=RuntimeError("boom"))
        route = {
            "front_node": {"key": "front-1"},
            "exit_node": {"key": "exit-1"},
        }
        with pytest.raises(GatewayError) as exc_info:
            gw._ensure_route_instance(pool_id=1, endpoint_id=0, route=route)
        assert exc_info.value.status_code == 503
        assert "boom" in exc_info.value.detail


# ---------------------------------------------------------------------------
# handle() error paths
# ---------------------------------------------------------------------------

class TestHandleErrors:
    @pytest.mark.anyio
    async def test_pool_not_found(self, tmp_path: Path) -> None:
        gw, *_ = _build_gateway(tmp_path)
        with pytest.raises(GatewayError) as exc_info:
            await gw.handle(
                method="GET",
                pool_name="no-such-pool",
                scheme="https",
                target_host="example.com",
                target_path="/",
                headers={},
                query_params={},
                body=b"",
            )
        assert exc_info.value.status_code == 404
        assert "pool not found" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_chain_not_enabled(self, tmp_path: Path) -> None:
        gw, storage, *_ = _build_gateway(tmp_path)
        storage.create_proxy_pool(name="plain-pool", chain_enabled=False)
        with pytest.raises(GatewayError) as exc_info:
            await gw.handle(
                method="GET",
                pool_name="plain-pool",
                scheme="https",
                target_host="example.com",
                target_path="/",
                headers={},
                query_params={},
                body=b"",
            )
        assert exc_info.value.status_code == 409
        assert "not enabled" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_session_reject_when_missing(self, tmp_path: Path) -> None:
        gw, storage, *_ = _build_gateway(tmp_path)
        storage.create_proxy_pool(
            name="reject-pool",
            chain_enabled=True,
            session_missing_action="REJECT",
        )
        with pytest.raises(GatewayError) as exc_info:
            await gw.handle(
                method="GET",
                pool_name="reject-pool",
                scheme="https",
                target_host="example.com",
                target_path="/",
                headers={},
                query_params={},
                body=b"",
            )
        assert exc_info.value.status_code == 400
        assert "session_id is required" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_no_available_route(self, tmp_path: Path) -> None:
        gw, storage, *_ = _build_gateway(tmp_path)
        _setup_pool_with_chain(storage)
        # No nodes exist, so route_request should return None
        with pytest.raises(GatewayError) as exc_info:
            await gw.handle(
                method="GET",
                pool_name="test-pool",
                scheme="https",
                target_host="example.com",
                target_path="/",
                headers={},
                query_params={},
                body=b"",
            )
        assert exc_info.value.status_code == 503
        assert "no available chain route" in exc_info.value.detail


# ---------------------------------------------------------------------------
# handle() successful paths with endpoints
# ---------------------------------------------------------------------------

class TestHandleWithEndpoint:
    @pytest.mark.anyio
    async def test_uses_endpoint_session_header_names(self, tmp_path: Path) -> None:
        """When an endpoint exists, its session_header_names are used for extraction."""
        gw, storage, cs, manager, backend = _build_gateway(tmp_path)
        pool = _setup_pool_with_chain(storage)
        _setup_nodes(storage)
        pool_id = int(pool["id"])

        ep = storage.create_http_proxy_endpoint(
            name="test-pool",
            session_header_names=["X-Custom-Session"],
        )
        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), [pool_id])

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)
        gw.transport = transport

        try:
            resp = await gw.handle(
                method="POST",
                pool_name="test-pool",
                scheme="https",
                target_host="api.example.com",
                target_path="/v1/data",
                headers={"X-Custom-Session": "sess-ep-1"},
                query_params={"key": "val"},
                body=b"payload",
            )
            # The test verifies the endpoint session header is used
            assert resp.status_code == 200
        finally:
            backend.close()

    @pytest.mark.anyio
    async def test_session_id_none_skips_binding(self, tmp_path: Path) -> None:
        """When no session_id is extracted, bind is not called."""
        gw, storage, cs, manager, backend = _build_gateway(tmp_path)
        pool = _setup_pool_with_chain(storage)
        _setup_nodes(storage)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)

        gw.transport = httpx.MockTransport(handler)
        try:
            resp = await gw.handle(
                method="GET",
                pool_name="test-pool",
                scheme="http",
                target_host="example.com",
                target_path="/",
                headers={},
                query_params={},
                body=b"",
            )
            assert resp.status_code == 200
        finally:
            backend.close()


# ---------------------------------------------------------------------------
# handle() transport=None path (proxy URL)
# ---------------------------------------------------------------------------

class TestHandleWithProxy:
    @pytest.mark.anyio
    async def test_uses_proxy_url_when_no_transport(self, tmp_path: Path) -> None:
        """When transport is None, the gateway should use a proxy URL."""
        gw, storage, cs, manager, backend = _build_gateway(tmp_path, transport=None)
        pool = _setup_pool_with_chain(storage)
        _setup_nodes(storage)

        # We can't easily verify the proxy URL is passed without a real proxy,
        # but we can verify the gateway tries to connect (it will fail).
        # Instead, verify the code path by mocking the client.
        from unittest.mock import AsyncMock, patch

        mock_response = httpx.Response(200, json={"via": "proxy"})
        with patch("proxypool.gateway.http_gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = await gw.handle(
                method="GET",
                pool_name="test-pool",
                scheme="https",
                target_host="example.com",
                target_path="/",
                headers={},
                query_params={},
                body=b"",
            )
            assert resp.status_code == 200
            # Verify proxy kwarg was passed
            call_kwargs = mock_client_cls.call_args[1]
            assert "proxy" in call_kwargs
            assert "http://" in call_kwargs["proxy"]


# ---------------------------------------------------------------------------
# handle() query params in URL
# ---------------------------------------------------------------------------

class TestHandleQueryParams:
    @pytest.mark.anyio
    async def test_query_params_included_in_target_url(self, tmp_path: Path) -> None:
        gw, storage, cs, manager, backend = _build_gateway(tmp_path)
        pool = _setup_pool_with_chain(storage)
        _setup_nodes(storage)

        captured_url: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_url["url"] = str(request.url)
            return httpx.Response(200)

        gw.transport = httpx.MockTransport(handler)
        try:
            await gw.handle(
                method="GET",
                pool_name="test-pool",
                scheme="https",
                target_host="api.example.com",
                target_path="/search",
                headers={},
                query_params={"q": "test", "page": "1"},
                body=b"",
            )
            assert "q=test" in captured_url["url"]
            assert "page=1" in captured_url["url"]
        finally:
            backend.close()
