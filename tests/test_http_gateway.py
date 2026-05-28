from __future__ import annotations

import os
import socket
import time
from pathlib import Path

import httpx
import pytest

from proxypool.backend.chain_instance_manager import ChainInstanceManager
from proxypool.backend.egress_backend import StartedInstance
from proxypool.models import ProxyNode
from proxypool.pool.chain_service import ProxyChainService
from proxypool.storage.sqlite import SQLiteProxyStorage


class FakeBackend:
    backend_type = "mihomo"

    def __init__(self) -> None:
        self.started: list[str] = []
        self.stopped: list[str] = []
        self.listeners: dict[str, socket.socket] = {}

    def build_config(self, spec):
        return {"listeners": [{"type": spec.inbound_type, "port": spec.port}]}

    def start(self, spec):
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
        for instance_id in list(self.listeners):
            self.stop(instance_id)


def test_pool_session_rule_round_trip(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    pool = storage.create_proxy_pool(name="pool-a")

    item = storage.upsert_pool_session_rule(
        pool_id=int(pool["id"]),
        url_prefix="example.com/api",
        headers=["X-Biz-Session", "Authorization"],
    )

    assert item["url_prefix"] == "example.com/api"
    assert item["headers"] == ["X-Biz-Session", "Authorization"]
    assert storage.list_pool_session_rules(int(pool["id"]))[0]["url_prefix"] == "example.com/api"


def test_session_extractor_prefers_header_over_query() -> None:
    from proxypool.gateway.session_extractor import SessionExtractor

    extractor = SessionExtractor()
    session_id, source, extraction_failed = extractor.extract(
        headers={"x-proxypool-session": "sess-header"},
        query_params={"session": "sess-query"},
        target_host="api.example.com",
        target_path="/v1/chat",
        header_names=["X-ProxyPool-Session"],
        query_names=["session"],
        rules=[],
    )

    assert session_id == "sess-header"
    assert source == "header:X-ProxyPool-Session"
    assert extraction_failed is False


def test_session_extractor_uses_rule_headers_on_longest_prefix_match() -> None:
    from proxypool.gateway.session_extractor import SessionExtractor

    extractor = SessionExtractor()
    session_id, source, extraction_failed = extractor.extract(
        headers={
            "authorization": "Bearer sess-123",
            "x-biz-session": "biz-fallback",
        },
        query_params={},
        target_host="api.example.com",
        target_path="/v1/private/chat",
        header_names=[],
        query_names=[],
        rules=[
            {"url_prefix": "api.example.com/v1", "headers": ["X-Biz-Session"]},
            {"url_prefix": "api.example.com/v1/private", "headers": ["Authorization"]},
        ],
    )

    assert session_id == "Bearer sess-123"
    assert source == "rule:api.example.com/v1/private:Authorization"
    assert extraction_failed is False


@pytest.mark.anyio
async def test_unified_gateway_strips_internal_session_header_and_creates_lease(
    tmp_path: Path,
) -> None:
    from proxypool.gateway.http_gateway import UnifiedHttpGateway

    storage = SQLiteProxyStorage(tmp_path / "test.db")
    storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])
    storage.upsert_proxy_pool_v2("exit", "exit", ["exit-.*"])
    pool = storage.create_proxy_pool(
        name="pool-a",
        chain_enabled=True,
        session_header_names=["X-ProxyPool-Session"],
        gateway_path_prefix="/proxy/pool-a",
    )
    pool_id = int(pool["id"])

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

    chain_service = ProxyChainService(storage=storage)
    chain_service.initialize()
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)

    captured: dict[str, object] = {}

    def upstream_handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(upstream_handler)
    gateway = UnifiedHttpGateway(
        storage=storage,
        pool_service=None,
        chain_service=chain_service,
        chain_instance_manager=manager,
        transport=transport,
    )

    try:
        response = await gateway.handle(
            method="GET",
            pool_name="pool-a",
            scheme="https",
            target_host="api.example.com",
            target_path="/v1/chat",
            headers={
                "X-ProxyPool-Session": "sess-1",
                "Authorization": "Bearer keep-me",
            },
            query_params={},
            body=b"",
        )

        assert response.status_code == 200
        assert captured["headers"]["authorization"] == "Bearer keep-me"
        assert "x-proxypool-session" not in captured["headers"]

        lease = storage.get_sticky_lease("sess-1", pool_id)
        assert lease is not None
        assert lease["instance_id"] != ""
        first_last_accessed = lease["last_accessed"]
        assert chain_service.get_leases(pool_id)[0]["instance_id"] != ""

        time.sleep(0.01)

        second = await gateway.handle(
            method="GET",
            pool_name="pool-a",
            scheme="https",
            target_host="api.example.com",
            target_path="/v1/chat",
            headers={
                "X-ProxyPool-Session": "sess-1",
                "Authorization": "Bearer keep-me",
            },
            query_params={},
            body=b"",
        )
        assert second.status_code == 200

        updated_lease = storage.get_sticky_lease("sess-1", pool_id)
        assert updated_lease is not None
        assert updated_lease["instance_id"] == lease["instance_id"]
        assert updated_lease["last_accessed"] != first_last_accessed
    finally:
        backend.close()


def test_chain_instance_manager_can_ensure_running_instance(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    front = ProxyNode(
        protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1"
    )
    exit_node = ProxyNode(
        protocol="socks",
        host="2.2.2.2",
        port=1080,
        raw_link="socks://2.2.2.2:1080",
        name="exit-1",
    )
    storage.upsert_proxy(front)
    storage.upsert_proxy(exit_node)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    try:
        first = manager.ensure_instance(
            pool_id=1,
            front_node_key=front.normalized_key(),
            exit_node_key=exit_node.normalized_key(),
            inbound_type="http",
        )
        assert first["status"] == "running"

        stopped = manager.stop_instance(first["instance_id"])
        assert stopped["status"] == "stopped"

        second = manager.ensure_instance(
            pool_id=1,
            front_node_key=front.normalized_key(),
            exit_node_key=exit_node.normalized_key(),
            inbound_type="http",
        )
        assert second["instance_id"] == first["instance_id"]
        assert second["port"] == first["port"]
        assert second["status"] == "running"
        assert backend.started.count(first["instance_id"]) == 2
    finally:
        backend.close()
