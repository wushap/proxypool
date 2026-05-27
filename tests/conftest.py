"""
Pytest shared configuration and fixtures.
"""
from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from typing import AsyncGenerator, Generator

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.models import ProxyNode
from proxypool.settings import AppSettings
from proxypool.storage.sqlite import SQLiteProxyStorage


# ============================================================
# Base Fixtures
# ============================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop (shared across test session)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Temporary directory fixture with subdirectories."""
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "output").mkdir(exist_ok=True)
    (tmp_path / "configs").mkdir(exist_ok=True)
    return tmp_path


@pytest.fixture
def db_path(tmp_dir: Path) -> Path:
    """Database path."""
    return tmp_dir / "data" / "proxies.db"


@pytest.fixture
def settings(tmp_dir: Path) -> AppSettings:
    """Default test configuration (no auth)."""
    return AppSettings(
        project_root=tmp_dir,
        db_path=tmp_dir / "data" / "proxies.db",
        output_dir=tmp_dir / "output",
        sources_file=tmp_dir / "configs" / "sources.txt",
        singbox_routes_file=tmp_dir / "configs" / "singbox-routes.json",
        singbox_runtime_config_file=tmp_dir / "data" / "runtime" / "singbox.json",
        singbox_runtime_log_file=tmp_dir / "data" / "runtime" / "singbox.log",
        singbox_binary="sing-box",
        test_url="https://www.cloudflare.com/cdn-cgi/trace",
        api_key="",  # No API key by default
        http_gateway_default_host="127.0.0.1",
        http_gateway_default_port=8899,
        backend_engine="singbox",
        backend_health_check_sec=30,
        backend_auto_restart_max=3,
        mihomo_binary="mihomo",
        mihomo_runtime_dir=tmp_dir / "data" / "runtime" / "mihomo",
    )


@pytest.fixture
def settings_with_auth(tmp_dir: Path) -> AppSettings:
    """Test configuration with authentication enabled."""
    return AppSettings(
        project_root=tmp_dir,
        db_path=tmp_dir / "data" / "proxies.db",
        output_dir=tmp_dir / "output",
        sources_file=tmp_dir / "configs" / "sources.txt",
        singbox_routes_file=tmp_dir / "configs" / "singbox-routes.json",
        singbox_runtime_config_file=tmp_dir / "data" / "runtime" / "singbox.json",
        singbox_runtime_log_file=tmp_dir / "data" / "runtime" / "singbox.log",
        singbox_binary="sing-box",
        test_url="https://www.cloudflare.com/cdn-cgi/trace",
        api_key="test-secret-key-123",  # Test API key
        http_gateway_default_host="127.0.0.1",
        http_gateway_default_port=8899,
        backend_engine="singbox",
        backend_health_check_sec=30,
        backend_auto_restart_max=3,
        mihomo_binary="mihomo",
        mihomo_runtime_dir=tmp_dir / "data" / "runtime" / "mihomo",
    )


# ============================================================
# Application and Storage Fixtures
# ============================================================


@pytest.fixture
def storage(db_path: Path) -> Generator[SQLiteProxyStorage, None, None]:
    """Database storage instance."""
    store = SQLiteProxyStorage(db_path)
    yield store


@pytest.fixture
def app(settings: AppSettings) -> Generator:
    """FastAPI application instance (no auth)."""
    application = create_app(settings)
    yield application


@pytest.fixture
def app_with_auth(settings_with_auth: AppSettings) -> Generator:
    """FastAPI application instance (with auth)."""
    application = create_app(settings_with_auth)
    yield application


@pytest.fixture
async def client(app) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client (no auth)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_client(app_with_auth) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client (with auth)."""
    transport = httpx.ASGITransport(app=app_with_auth)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def auth_client_with_key(auth_client: httpx.AsyncClient) -> httpx.AsyncClient:
    """HTTP client with API key header set."""
    auth_client.headers["X-API-Key"] = "test-secret-key-123"
    return auth_client


# ============================================================
# Test Data Factories
# ============================================================


class ProxyNodeFactory:
    """Factory for creating test proxy nodes."""

    @staticmethod
    def create(
        protocol: str = "trojan",
        host: str = "us.example.com",
        port: int = 443,
        **kwargs,
    ) -> ProxyNode:
        raw_link = f"{protocol}://{host}:{port}"
        extra = kwargs.pop("extra", {"password": "test-password"})
        return ProxyNode(
            protocol=protocol,
            host=host,
            port=port,
            raw_link=raw_link,
            extra=extra,
            **kwargs,
        )

    @staticmethod
    def create_batch(count: int = 5) -> list[ProxyNode]:
        """Create batch of test proxy nodes."""
        protocols = ["trojan", "vmess", "ss", "hysteria2"]
        nodes = []
        for i in range(count):
            nodes.append(
                ProxyNodeFactory.create(
                    protocol=protocols[i % len(protocols)],
                    host=f"node-{i}.example.com",
                    port=443 + i,
                )
            )
        return nodes


@pytest.fixture
def proxy_factory() -> type[ProxyNodeFactory]:
    """Proxy node factory fixture."""
    return ProxyNodeFactory


@pytest.fixture
def sample_proxy() -> ProxyNode:
    """Single test proxy node."""
    return ProxyNodeFactory.create()


@pytest.fixture
def sample_proxies() -> list[ProxyNode]:
    """Batch of test proxy nodes."""
    return ProxyNodeFactory.create_batch()


# ============================================================
# Utility Fixtures
# ============================================================


@pytest.fixture
def pick_free_port():
    """Function to get a free port."""
    def _pick() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    return _pick


@pytest.fixture
def tmp_file(tmp_dir: Path):
    """Function to create temporary files."""
    created_files = []

    def _create(content: str, name: str = "test.txt") -> Path:
        path = tmp_dir / name
        path.write_text(content, encoding="utf-8")
        created_files.append(path)
        return path

    yield _create

    # Cleanup
    for f in created_files:
        f.unlink(missing_ok=True)


# ============================================================
# Mock Objects
# ============================================================


class FakePoolService:
    """Mock pool service."""

    def __init__(self, pool: dict | None = None):
        self.pool = pool or {"id": 1, "name": "test-pool"}
        self.calls: list[str] = []

    def get_pool(self, pool_id: int) -> dict | None:
        self.calls.append(f"get_pool({pool_id})")
        if int(self.pool["id"]) == int(pool_id):
            return self.pool
        return None

    def get_pool_by_name(self, name: str) -> dict | None:
        self.calls.append(f"get_pool_by_name({name})")
        if self.pool.get("name") == name:
            return self.pool
        return None


class FakeChainService:
    """Mock chain service."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.failures: list[dict] = []

    def route_request(
        self,
        session_id: str = "",
        pool_id: int = 0,
        target_domain: str = "",
        live_instance_ids: set | None = None,
    ) -> dict | None:
        self.calls.append((session_id, pool_id, target_domain, live_instance_ids))
        return {
            "front_node": {"key": "front-1"},
            "exit_node": {"key": "exit-1"},
            "lease_created": bool(session_id),
            "bound_instance_id": "",
            "instance_reused": False,
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
    """Mock instance manager."""

    def list_running_instance_ids(
        self, pool_id: int | None = None, endpoint_id: int | None = None
    ) -> set[str]:
        return set()

    def ensure_instance(
        self,
        pool_id: int,
        front_node_key: str,
        exit_node_key: str,
        inbound_type: str = "http",
        listen: str | None = None,
        endpoint_id: int = 0,
        hop_node_keys: list[str] | None = None,
        route_signature: str = "",
    ) -> dict:
        return {
            "instance_id": "inst-1",
            "listen": "127.0.0.1",
            "port": 18080,
            "status": "running",
        }


@pytest.fixture
def fake_pool_service() -> FakePoolService:
    return FakePoolService()


@pytest.fixture
def fake_chain_service() -> FakeChainService:
    return FakeChainService()


@pytest.fixture
def fake_instance_manager() -> FakeInstanceManager:
    return FakeInstanceManager()
