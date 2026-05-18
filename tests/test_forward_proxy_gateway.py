from __future__ import annotations

import asyncio
import socket
from pathlib import Path

import pytest

from proxypool.gateway.config import HttpGatewayConfig
from proxypool.gateway.connect_session import ConnectSessionRegistry
from proxypool.gateway.forward_proxy import ForwardProxyGateway
from proxypool.gateway.runtime import ForwardProxyGatewayRuntime
from proxypool.storage.sqlite import SQLiteProxyStorage


class FakePoolService:
    def __init__(self, pool: dict):
        self.pool = pool

    def get_pool(self, pool_id: int):
        return self.pool if int(self.pool["id"]) == int(pool_id) else None


class FakeChainService:
    def __init__(self):
        self.calls = []
        self.failures = []

    def route_request(self, session_id="", pool_id=0, target_domain="", live_instance_ids=None):
        self.calls.append((session_id, pool_id, target_domain, live_instance_ids))
        return {
            "front_node": {"key": "front-1"},
            "exit_node": {"key": "exit-1"},
            "lease_created": bool(session_id),
            "bound_instance_id": "",
            "instance_reused": False,
        }

    def bind_instance_to_session(self, session_id: str, pool_id: int, instance_id: str, endpoint_id: int = 0):
        return {
            "session_id": session_id,
            "pool_id": pool_id,
            "instance_id": instance_id,
            "endpoint_id": endpoint_id,
        }

    def report_endpoint_route_failure(
        self,
        endpoint_id: int,
        pool_id: int,
        session_id: str = "",
        hop_node_keys: list[str] | None = None,
    ) -> None:
        self.failures.append({
            "endpoint_id": endpoint_id,
            "pool_id": pool_id,
            "session_id": session_id,
            "hop_node_keys": list(hop_node_keys or []),
        })


class FakeInstanceManager:
    def list_running_instance_ids(self, pool_id=None, endpoint_id=None):
        return set()

    def ensure_instance(
        self,
        pool_id,
        front_node_key,
        exit_node_key,
        inbound_type="http",
        listen=None,
        endpoint_id=0,
        hop_node_keys=None,
        route_signature="",
    ):
        return {"instance_id": "inst-1", "listen": "127.0.0.1", "port": 18080, "status": "running"}


@pytest.mark.anyio
async def test_forward_proxy_gateway_extracts_http_session_header() -> None:
    gateway = ForwardProxyGateway(
        storage=SQLiteProxyStorage(Path("/tmp/test-forward-gateway.db")),
        pool_service=FakePoolService({"id": 7}),
        chain_service=FakeChainService(),
        chain_instance_manager=FakeInstanceManager(),
        config=HttpGatewayConfig(enabled=True, default_pool_id=7),
    )

    session_id = gateway.extract_http_session_key(
        headers={"X-ProxyPool-Session": "sess-1"},
        query_params={},
        target_host="api.example.com",
        target_path="/v1/chat",
        rules=[],
    )

    assert session_id == "sess-1"


@pytest.mark.anyio
async def test_forward_proxy_gateway_generates_connect_fallback_key() -> None:
    registry = ConnectSessionRegistry()
    session_id = registry.get_or_create("conn-1")
    assert session_id.startswith("connect:")
    assert registry.get_or_create("conn-1") == session_id


class ForwardingInstanceManager(FakeInstanceManager):
    def __init__(self):
        self.ensure_calls = []

    def ensure_instance(
        self,
        pool_id,
        front_node_key,
        exit_node_key,
        inbound_type="http",
        listen=None,
        endpoint_id=0,
        hop_node_keys=None,
        route_signature="",
    ):
        self.ensure_calls.append((pool_id, front_node_key, exit_node_key, inbound_type, listen))
        return {"instance_id": "inst-1", "listen": "127.0.0.1", "port": 18080, "status": "running"}


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _read_until_headers(reader: asyncio.StreamReader) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = await reader.read(4096)
        if not chunk:
            break
        data += chunk
    return data


def test_forward_proxy_gateway_parse_proxy_target() -> None:
    gateway = ForwardProxyGateway(
        storage=None,
        pool_service=FakePoolService({"id": 7}),
        chain_service=FakeChainService(),
        chain_instance_manager=ForwardingInstanceManager(),
        config=HttpGatewayConfig(enabled=True, default_pool_id=7),
    )

    scheme, host, path = gateway.parse_proxy_target("https://api.example.com/v1/chat?x=1")

    assert scheme == "https"
    assert host == "api.example.com"
    assert path == "/v1/chat"


@pytest.mark.anyio
async def test_forward_proxy_gateway_route_http_request_uses_instance_manager(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "gateway.db")
    manager = ForwardingInstanceManager()
    gateway = ForwardProxyGateway(
        storage=storage,
        pool_service=FakePoolService({"id": 7}),
        chain_service=FakeChainService(),
        chain_instance_manager=manager,
        config=HttpGatewayConfig(enabled=True, default_pool_id=7),
    )

    route = gateway.resolve_route_for_http(
        raw_target="https://api.example.com/v1/chat",
        headers={"X-ProxyPool-Session": "sess-1"},
    )

    assert route["instance"]["instance_id"] == "inst-1"
    assert manager.ensure_calls[0][0] == 7


@pytest.mark.anyio
async def test_forward_proxy_gateway_retries_endpoint_route_when_instance_start_fails(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "gateway-retry-endpoint.db")
    endpoint = storage.create_http_proxy_endpoint("ep", listen_host="127.0.0.1", listen_port=18899)
    storage.replace_http_proxy_endpoint_hops(endpoint["id"], [11, 12])
    endpoint = storage.get_http_proxy_endpoint(endpoint["id"])
    assert endpoint is not None

    class EndpointPoolService(FakePoolService):
        def get_pool(self, pool_id: int):
            return {"id": 11}

    class EndpointChainService(FakeChainService):
        def __init__(self):
            super().__init__()
            self.index = 0

        def route_request(self, session_id="", pool_id=0, endpoint_id=0, target_domain="", live_instance_ids=None):
            self.calls.append((session_id, pool_id, endpoint_id, target_domain, live_instance_ids))
            front = "front-bad" if self.index == 0 else "front-good"
            self.index += 1
            return {
                "front_node": {"key": front},
                "exit_node": {"key": "exit-1"},
                "hop_node_keys": [front, "exit-1"],
                "endpoint_id": endpoint_id,
                "pool_id": pool_id,
                "route_signature": f"{front}>exit-1",
                "lease_created": bool(session_id),
                "bound_instance_id": "",
                "instance_reused": False,
            }

    class EndpointInstanceManager(FakeInstanceManager):
        def __init__(self):
            self.ensure_calls = []

        def list_running_instance_ids(self, pool_id=None, endpoint_id=None):
            return set()

        def ensure_instance(
            self,
            pool_id,
            front_node_key,
            exit_node_key,
            inbound_type="http",
            listen=None,
            endpoint_id=0,
            hop_node_keys=None,
            route_signature="",
        ):
            self.ensure_calls.append(front_node_key)
            if front_node_key == "front-bad":
                raise RuntimeError("chain instance did not become ready on 127.0.0.1:1150")
            return {"instance_id": "inst-good", "listen": "127.0.0.1", "port": 18080, "status": "running"}

    chain_service = EndpointChainService()
    manager = EndpointInstanceManager()
    gateway = ForwardProxyGateway(
        storage=storage,
        pool_service=EndpointPoolService({"id": 11}),
        chain_service=chain_service,
        chain_instance_manager=manager,
        config=HttpGatewayConfig(enabled=True, endpoint_id=endpoint["id"], default_pool_id=11),
    )

    gateway._route_instance_attempts = lambda endpoint: 2
    route = gateway.resolve_route_for_http(
        raw_target="https://api.example.com/v1/chat",
        headers={"X-ProxyPool-Session": "sess-1"},
    )

    assert route["instance"]["instance_id"] == "inst-good"
    assert manager.ensure_calls == ["front-bad", "front-good"]
    assert chain_service.failures == [{
        "endpoint_id": endpoint["id"],
        "pool_id": 11,
        "session_id": "sess-1",
        "hop_node_keys": ["front-bad", "exit-1"],
    }]


@pytest.mark.anyio
async def test_forward_proxy_gateway_route_connect_request_generates_connection_session(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "gateway-connect.db")
    gateway = ForwardProxyGateway(
        storage=storage,
        pool_service=FakePoolService({"id": 7}),
        chain_service=FakeChainService(),
        chain_instance_manager=ForwardingInstanceManager(),
        config=HttpGatewayConfig(enabled=True, default_pool_id=7, session_missing_action="RANDOM"),
    )

    route = gateway.resolve_route_for_connect(
        target_host="api.example.com:443",
        headers={},
        connection_id="conn-1",
    )

    assert route["session_id"].startswith("connect:")
    assert route["instance"]["instance_id"] == "inst-1"


@pytest.mark.anyio
async def test_forward_proxy_gateway_runtime_handles_http_and_connect(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "gateway-runtime.db")
    proxy_port = _pick_free_port()
    listen_port = _pick_free_port()
    captured: dict[str, object] = {"http_requests": [], "connect_payloads": []}

    async def proxy_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await _read_until_headers(reader)
            request_line = head.split(b"\r\n", 1)[0].decode("latin-1")
            captured.setdefault("http_requests", []).append(request_line)
            method, _, _ = request_line.split(" ", 2)
            if method.upper() == "CONNECT":
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                payload = await reader.read(1024)
                captured.setdefault("connect_payloads", []).append(payload)
                if payload:
                    writer.write(payload)
                    await writer.drain()
                return

            body = b"proxy-ok"
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("latin-1")
                + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    proxy_server = await asyncio.start_server(proxy_handler, "127.0.0.1", proxy_port)

    class RuntimeInstanceManager(FakeInstanceManager):
        def ensure_instance(
            self,
            pool_id,
            front_node_key,
            exit_node_key,
            inbound_type="http",
            listen=None,
            endpoint_id=0,
            hop_node_keys=None,
            route_signature="",
        ):
            return {
                "instance_id": "inst-1",
                "listen": "127.0.0.1",
                "port": proxy_port,
                "status": "running",
            }

    chain_service = FakeChainService()
    gateway = ForwardProxyGateway(
        storage=storage,
        pool_service=FakePoolService({"id": 7}),
        chain_service=chain_service,
        chain_instance_manager=RuntimeInstanceManager(),
        config=HttpGatewayConfig(
            enabled=True,
            listen_host="127.0.0.1",
            listen_port=listen_port,
            default_pool_id=7,
            session_missing_action="RANDOM",
        ),
        connect_registry=ConnectSessionRegistry(),
    )
    runtime = ForwardProxyGatewayRuntime(gateway)
    runtime.CONNECT_ROUTE_ATTEMPTS = 1
    runtime._connect_preflight_url = lambda target: ""

    try:
        await runtime.start()
        assert runtime.status()["running"] is True

        reader, writer = await asyncio.open_connection("127.0.0.1", listen_port)
        writer.write(
            b"GET http://example.com/hello HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"X-ProxyPool-Session: sess-http\r\n\r\n"
        )
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()

        assert b"200 OK" in response
        assert response.endswith(b"proxy-ok")
        assert chain_service.calls[0][0] == "sess-http"

        reader, writer = await asyncio.open_connection("127.0.0.1", listen_port)
        writer.write(b"CONNECT api.example.com:443 HTTP/1.1\r\nHost: api.example.com:443\r\n\r\n")
        await writer.drain()
        connect_response = await _read_until_headers(reader)
        assert b"200 Connection Established" in connect_response
        writer.write(b"ping")
        await writer.drain()
        echoed = await reader.readexactly(4)
        writer.close()
        await writer.wait_closed()

        assert echoed == b"ping"
        assert captured["connect_payloads"] == [b"ping"]
        assert str(chain_service.calls[1][0]).startswith("connect:")

        reader, writer = await asyncio.open_connection("127.0.0.1", listen_port)
        writer.write(
            b"CONNECT api.example.com:443 HTTP/1.1\r\n"
            b"Host: api.example.com:443\r\n\r\n"
            b"early"
        )
        await writer.drain()
        connect_response = await _read_until_headers(reader)
        assert b"200 Connection Established" in connect_response
        echoed = await reader.readexactly(5)
        writer.close()
        await writer.wait_closed()

        assert echoed == b"early"
        assert captured["connect_payloads"][-1] == b"early"
    finally:
        await runtime.stop()
        proxy_server.close()
        await proxy_server.wait_closed()


@pytest.mark.anyio
async def test_forward_proxy_gateway_connect_preflight_retries_failed_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = SQLiteProxyStorage(tmp_path / "gateway-runtime-retry.db")
    good_port = _pick_free_port()
    listen_port = _pick_free_port()
    captured: dict[str, object] = {"failures": [], "ensured": []}

    async def good_proxy_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await _read_until_headers(reader)
            request_line = head.split(b"\r\n", 1)[0]
            if request_line.startswith(b"CONNECT "):
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                payload = await reader.read(1024)
                if payload:
                    writer.write(payload)
                    await writer.drain()
                return
            body = b"ok"
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("latin-1")
                + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    good_server = await asyncio.start_server(good_proxy_handler, "127.0.0.1", good_port)

    class RetryChainService(FakeChainService):
        def __init__(self):
            super().__init__()
            self.index = 0

        def route_request(self, session_id="", pool_id=0, target_domain="", live_instance_ids=None):
            self.calls.append((session_id, pool_id, target_domain, live_instance_ids))
            key = "front-bad" if self.index == 0 else "front-good"
            self.index += 1
            return {
                "front_node": {"key": key},
                "exit_node": {"key": "exit-1"},
                "hop_node_keys": [key, "exit-1"],
                "endpoint_id": 0,
                "route_signature": f"{key}>exit-1",
                "lease_created": bool(session_id),
                "bound_instance_id": "",
                "instance_reused": False,
            }

    class RetryInstanceManager(FakeInstanceManager):
        def ensure_instance(
            self,
            pool_id,
            front_node_key,
            exit_node_key,
            inbound_type="http",
            listen=None,
            endpoint_id=0,
            hop_node_keys=None,
            route_signature="",
        ):
            captured.setdefault("ensured", []).append(front_node_key)
            if front_node_key == "front-bad":
                return {"instance_id": "bad-inst", "listen": "127.0.0.1", "port": good_port, "status": "running"}
            return {"instance_id": "good-inst", "listen": "127.0.0.1", "port": good_port, "status": "running"}

        def mark_instance_failed(self, instance_id: str, error: str = "") -> None:
            captured.setdefault("failures", []).append((instance_id, error))

    chain_service = RetryChainService()
    gateway = ForwardProxyGateway(
        storage=storage,
        pool_service=FakePoolService({"id": 7}),
        chain_service=chain_service,
        chain_instance_manager=RetryInstanceManager(),
        config=HttpGatewayConfig(
            enabled=True,
            listen_host="127.0.0.1",
            listen_port=listen_port,
            default_pool_id=7,
            session_missing_action="RANDOM",
        ),
        connect_registry=ConnectSessionRegistry(),
    )
    runtime = ForwardProxyGatewayRuntime(gateway)
    runtime.CONNECT_ROUTE_ATTEMPTS = 2
    runtime.CONNECT_PREFLIGHT_TIMEOUT_SEC = 1

    async def fake_preflight(route: dict, target_url: str, headers: dict[str, str]) -> None:
        del target_url, headers
        if route["instance"]["instance_id"] == "bad-inst":
            raise RuntimeError("preflight failed")

    monkeypatch.setattr(runtime, "_preflight_instance_http_request", fake_preflight)

    try:
        await runtime.start()
        reader, writer = await asyncio.open_connection("127.0.0.1", listen_port)
        writer.write(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
        await writer.drain()
        response = await _read_until_headers(reader)
        assert b"200 Connection Established" in response
        writer.write(b"ping")
        await writer.drain()
        echoed = await reader.readexactly(4)
        writer.close()
        await writer.wait_closed()

        assert echoed == b"ping"
        assert captured["ensured"] == ["front-bad", "front-good"]
        assert captured["failures"][0][0] == "bad-inst"
    finally:
        await runtime.stop()
        good_server.close()
        await good_server.wait_closed()
