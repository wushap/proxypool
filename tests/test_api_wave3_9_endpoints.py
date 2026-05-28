"""
Tests for new backend APIs added in Waves 3-9.
Tests for system health, processes, resources, version, batch operations, CSV exports, and diagnostics.
"""

from __future__ import annotations

import socket
from pathlib import Path

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.models import ProxyNode
from proxypool.settings import AppSettings


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _make_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=tmp_path,
        db_path=tmp_path / "proxies.db",
        output_dir=tmp_path / "output",
        sources_file=tmp_path / "sources.txt",
        singbox_routes_file=tmp_path / "singbox-routes.json",
        singbox_runtime_config_file=tmp_path / "singbox-runtime.json",
        singbox_runtime_log_file=tmp_path / "singbox-runtime.log",
        singbox_binary="sing-box",
        test_url="https://www.cloudflare.com/cdn-cgi/trace",
        api_key="",
        http_gateway_default_host="127.0.0.1",
        http_gateway_default_port=8899,
        backend_engine="singbox",
        backend_health_check_sec=30,
        backend_auto_restart_max=3,
        mihomo_binary="mihomo",
        mihomo_runtime_dir=tmp_path / "runtime" / "mihomo",
    )


# ===== System Health & Activity Tests =====


@pytest.mark.anyio
async def test_system_health_endpoint(tmp_path: Path) -> None:
    """Test GET /api/system/health returns detailed health status"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "backend_status" in data
        assert "gateway_status" in data
        assert "active_processes" in data
        assert "pool_count" in data
        assert "proxy_count" in data
        assert "healthy_proxy_rate" in data
        assert "uptime_seconds" in data


@pytest.mark.anyio
async def test_system_activity_endpoint(tmp_path: Path) -> None:
    """Test GET /api/system/activity returns activity log"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/activity")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)


@pytest.mark.anyio
async def test_system_activity_with_limit(tmp_path: Path) -> None:
    """Test GET /api/system/activity with limit parameter"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/activity?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 10


# ===== Process List Tests =====


@pytest.mark.anyio
async def test_system_processes_endpoint(tmp_path: Path) -> None:
    """Test GET /api/system/processes returns process list"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/processes")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "running" in data
        assert isinstance(data["items"], list)


# ===== System Resources Tests =====


@pytest.mark.anyio
async def test_system_resources_endpoint(tmp_path: Path) -> None:
    """Test GET /api/system/resources returns resource usage"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data
        assert "uptime_seconds" in data
        assert "timestamp" in data


# ===== Version Tests =====


@pytest.mark.anyio
async def test_system_version_endpoint(tmp_path: Path) -> None:
    """Test GET /api/system/version returns version info"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "python_version" in data
        assert "platform" in data
        assert "architecture" in data
        assert "uptime_seconds" in data
        assert "api_uptime_seconds" in data


# ===== Batch Pool Tests =====


@pytest.mark.anyio
async def test_pool_batch_create(tmp_path: Path) -> None:
    """Test POST /api/pools/batch creates multiple pools"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/pools/batch",
            json={
                "pools": [
                    {"name": "batch-pool-1", "filters": {"available": "true"}},
                    {"name": "batch-pool-2", "filters": {"protocol": "trojan"}},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2
        assert data["failed"] == 0


@pytest.mark.anyio
async def test_pool_batch_create_with_errors(tmp_path: Path) -> None:
    """Test POST /api/pools/batch handles partial failures"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a pool first
        await client.post("/api/pools", json={"name": "existing-pool"})

        # Try batch create with duplicate name
        resp = await client.post(
            "/api/pools/batch",
            json={
                "pools": [
                    {"name": "new-pool", "filters": {}},
                    {"name": "existing-pool", "filters": {}},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] >= 1


@pytest.mark.anyio
async def test_pool_batch_create_stop_on_error(tmp_path: Path) -> None:
    """Test POST /api/pools/batch with stop_on_error flag"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/pools/batch",
            json={
                "pools": [
                    {"name": "pool-a", "filters": {}},
                    {"name": "pool-a", "filters": {}},  # duplicate
                ],
                "stop_on_error": True,
            },
        )
        assert resp.status_code == 200


# ===== Pool Validation Tests =====


@pytest.mark.anyio
async def test_pool_validate_endpoint(tmp_path: Path) -> None:
    """Test POST /api/pools/{id}/validate validates pool config"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create pool
        resp = await client.post("/api/pools", json={"name": "test-pool"})
        pool_id = resp.json()["item"]["id"]

        # Validate pool
        resp = await client.post(f"/api/pools/{pool_id}/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert "issues" in data
        assert "validated_at" in data


@pytest.mark.anyio
async def test_pool_validate_not_found(tmp_path: Path) -> None:
    """Test POST /api/pools/{id}/validate with invalid pool ID"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/pools/999/validate")
        assert resp.status_code == 404


# ===== CSV Export Tests =====


@pytest.mark.anyio
async def test_proxies_export_csv(tmp_path: Path) -> None:
    """Test GET /api/proxies/export returns CSV"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add test proxy
    proxy = ProxyNode(
        protocol="trojan",
        host="us.example.com",
        port=443,
        raw_link="trojan://us",
        extra={"password": "p"},
    )
    storage.upsert_proxy(proxy)
    storage.update_test_result(proxy.normalized_key(), available=True, latency_ms=100)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/proxies/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        # Check BOM
        assert content.startswith("﻿")
        # Check headers
        assert "地址" in content
        assert "协议" in content
        assert "延迟" in content


@pytest.mark.anyio
async def test_pool_export_csv(tmp_path: Path) -> None:
    """Test GET /api/pools/{id}/export returns CSV for pool"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add test proxy
    proxy = ProxyNode(
        protocol="ss",
        host="jp.example.com",
        port=8388,
        raw_link="ss://test",
        extra={},
    )
    storage.upsert_proxy(proxy)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create pool
        resp = await client.post("/api/pools", json={"name": "export-pool"})
        pool_id = resp.json()["item"]["id"]

        # Export pool
        resp = await client.get(f"/api/pools/{pool_id}/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        assert "地址" in content


@pytest.mark.anyio
async def test_pool_export_not_found(tmp_path: Path) -> None:
    """Test GET /api/pools/{id}/export with invalid pool ID"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/pools/999/export")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_test_report_export_csv(tmp_path: Path) -> None:
    """Test GET /api/system/test-report/export returns CSV"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add test proxy with test results
    proxy = ProxyNode(
        protocol="vmess",
        host="sg.example.com",
        port=443,
        raw_link="vmess://test",
        extra={},
    )
    storage.upsert_proxy(proxy)
    storage.update_test_result(
        proxy.normalized_key(),
        available=True,
        latency_ms=150,
        error="",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/test-report/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        assert "测试结果" in content
        assert "成功" in content


# ===== Config Export/Import Tests =====


@pytest.mark.anyio
async def test_config_export(tmp_path: Path) -> None:
    """Test GET /api/config/export returns config data"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        config_data = data["data"]
        assert "version" in config_data
        assert "exported_at" in config_data
        assert "pools" in config_data
        assert "endpoints" in config_data


@pytest.mark.anyio
async def test_config_import(tmp_path: Path) -> None:
    """Test POST /api/config/import imports config"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Export first to get valid config
        export_resp = await client.get("/api/config/export")
        config = export_resp.json()["data"]

        # Import config
        resp = await client.post(
            "/api/config/import",
            json={"data": config, "import_pools": True, "import_endpoints": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "imported_items" in data


# ===== Chain Diagnostics Tests =====


@pytest.mark.anyio
async def test_chain_diagnostics(tmp_path: Path) -> None:
    """Test GET /api/chain/diagnostics returns diagnostic info"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "front_pool" in data
        assert "exit_pool" in data
        assert "health_check" in data
        assert "active_leases" in data
        assert "recent_errors" in data


# ===== Config Diff Tests =====


@pytest.mark.anyio
async def test_config_diff(tmp_path: Path) -> None:
    """Test GET /api/system/config-diff returns config differences"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/config-diff")
        assert resp.status_code == 200
        data = resp.json()
        assert "has_diff" in data
        assert "differences" in data
        assert isinstance(data["differences"], list)


# ===== Rollback Tests =====


@pytest.mark.anyio
async def test_rollback_dry_run(tmp_path: Path) -> None:
    """Test POST /api/system/rollback with dry_run flag"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/system/rollback",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "rolled_back_items" in data


# ===== Logs Tests =====


@pytest.mark.anyio
async def test_system_logs(tmp_path: Path) -> None:
    """Test GET /api/system/logs returns log entries"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)


@pytest.mark.anyio
async def test_system_logs_with_level_filter(tmp_path: Path) -> None:
    """Test GET /api/system/logs with level filter"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/logs?level=INFO")
        assert resp.status_code == 200
        data = resp.json()
        assert data["level_filter"] == "INFO"
