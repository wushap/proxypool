from __future__ import annotations

from pathlib import Path

import pytest

from proxypool.gateway.config import HttpGatewayConfig
from proxypool.gateway.connect_session import ConnectSessionRegistry
from proxypool.gateway.forward_proxy import ForwardProxyGateway
from proxypool.storage.sqlite import SQLiteProxyStorage


class FakePoolService:
    def __init__(self, pool: dict):
        self.pool = pool

    def get_pool(self, pool_id: int):
        return self.pool if int(self.pool["id"]) == int(pool_id) else None


class FakeChainService:
    def __init__(self):
        self.calls = []

    def route_request(self, session_id="", pool_id=0, target_domain="", live_instance_ids=None):
        self.calls.append((session_id, pool_id, target_domain, live_instance_ids))
        return {
            "front_node": {"key": "front-1"},
            "exit_node": {"key": "exit-1"},
            "lease_created": bool(session_id),
            "bound_instance_id": "",
            "instance_reused": False,
        }

    def bind_instance_to_session(self, session_id: str, pool_id: int, instance_id: str):
        return {"session_id": session_id, "pool_id": pool_id, "instance_id": instance_id}


class FakeInstanceManager:
    def list_running_instance_ids(self, pool_id=None):
        return set()

    def ensure_instance(self, pool_id, front_node_key, exit_node_key, inbound_type="http", listen=None):
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

    def ensure_instance(self, pool_id, front_node_key, exit_node_key, inbound_type="http", listen=None):
        self.ensure_calls.append((pool_id, front_node_key, exit_node_key, inbound_type, listen))
        return {"instance_id": "inst-1", "listen": "127.0.0.1", "port": 18080, "status": "running"}


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
