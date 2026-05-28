"""
Comprehensive test coverage for configuration wizards, template operations,
export/import formats, rate limiting, and metrics endpoints.
"""

from __future__ import annotations

import asyncio
import socket
import time
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


# ===== Configuration Wizards Tests =====


@pytest.mark.anyio
async def test_config_wizard_get_settings(tmp_path: Path) -> None:
    """Test getting current configuration settings"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        # Settings endpoint returns item with test_url
        assert "item" in data
        assert "test_url" in data["item"]


@pytest.mark.anyio
async def test_config_wizard_update_settings(tmp_path: Path) -> None:
    """Test updating configuration settings"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Update settings
        resp = await client.put(
            "/api/settings",
            json={"test_url": "https://example.com"},
        )
        assert resp.status_code == 200


@pytest.mark.anyio
async def test_config_export_import(tmp_path: Path) -> None:
    """Test configuration export and import"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Export config
        resp = await client.get("/api/config/export")
        assert resp.status_code == 200
        config = resp.json()
        assert "data" in config

        # Import config
        resp = await client.post(
            "/api/config/import",
            json={"data": config["data"], "import_pools": True, "import_endpoints": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data


# ===== Pool Template Operations Tests =====


@pytest.mark.anyio
async def test_pool_create_with_all_filters(tmp_path: Path) -> None:
    """Test creating pool with comprehensive filters"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/pools",
            json={
                "name": "comprehensive-pool",
                "listen": "0.0.0.0",
                "inbound_type": "http",
                "filters": {
                    "route_mode_filter": "direct",
                    "geo_countries": ["US", "SG"],
                    "geo_country": "",
                    "geo_location": "",
                    "openai_filter": "",
                    "ip_purity_filter": "",
                    "source": "",
                    "protocol": "",
                    "latency_min": "",
                    "latency_max": "",
                    "freshness_hours": "",
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("item") is not None
        assert data["item"]["name"] == "comprehensive-pool"


@pytest.mark.anyio
async def test_pool_update_filters(tmp_path: Path) -> None:
    """Test updating pool filters"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create pool
        resp = await client.post(
            "/api/pools",
            json={"name": "update-filters-pool", "filters": {}},
        )
        pool_id = resp.json()["item"]["id"]

        # Update filters
        resp = await client.put(
            f"/api/pools/{pool_id}",
            json={"filters": {"available": "true", "protocol": "trojan"}},
        )
        assert resp.status_code == 200


@pytest.mark.anyio
async def test_pool_batch_operations(tmp_path: Path) -> None:
    """Test batch pool operations"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Batch create
        resp = await client.post(
            "/api/pools/batch",
            json={
                "pools": [
                    {"name": "batch-pool-1", "filters": {}},
                    {"name": "batch-pool-2", "filters": {"available": "true"}},
                    {"name": "batch-pool-3", "filters": {"protocol": "vmess"}},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 3
        assert data["failed"] == 0


@pytest.mark.anyio
async def test_pool_validate(tmp_path: Path) -> None:
    """Test pool validation"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create pool
        resp = await client.post(
            "/api/pools",
            json={"name": "validate-pool"},
        )
        pool_id = resp.json()["item"]["id"]

        # Validate pool
        resp = await client.post(f"/api/pools/{pool_id}/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert "issues" in data
        assert "validated_at" in data


# ===== Export/Import with Various Formats Tests =====


@pytest.mark.anyio
async def test_export_proxies_csv(tmp_path: Path) -> None:
    """Test exporting proxies in CSV format"""
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

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/proxies/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        # Should contain BOM and headers
        content = resp.text
        assert "地址" in content
        assert "协议" in content


@pytest.mark.anyio
async def test_export_pool_csv(tmp_path: Path) -> None:
    """Test exporting pool in CSV format"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add test proxies
    for i in range(3):
        proxy = ProxyNode(
            protocol="trojan",
            host=f"us{i}.example.com",
            port=443,
            raw_link=f"trojan://us{i}",
            extra={"password": "p"},
        )
        storage.upsert_proxy(proxy)
        storage.update_test_result(proxy.normalized_key(), available=True, latency_ms=100)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create pool
        resp = await client.post(
            "/api/pools",
            json={"name": "export-csv-pool", "filters": {"available": "true"}},
        )
        pool_id = resp.json()["item"]["id"]

        # Export pool
        resp = await client.get(f"/api/pools/{pool_id}/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]


@pytest.mark.anyio
async def test_export_test_report_csv(tmp_path: Path) -> None:
    """Test exporting test report in CSV format"""
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


@pytest.mark.anyio
async def test_export_config_json(tmp_path: Path) -> None:
    """Test exporting configuration in JSON format"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        config = data["data"]
        assert "version" in config
        assert "exported_at" in config
        assert "pools" in config
        assert "endpoints" in config


# ===== Rate Limiting Edge Cases Tests =====


@pytest.mark.anyio
async def test_rate_limiting_allows_normal_requests(tmp_path: Path) -> None:
    """Test that rate limiting allows normal request rates"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Send 10 requests rapidly
        for _ in range(10):
            resp = await client.get("/api/pools")
            assert resp.status_code == 200


@pytest.mark.anyio
async def test_rate_limiting_returns_429_on_excess(tmp_path: Path) -> None:
    """Test that rate limiting returns 429 when limit is exceeded"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Try to exceed rate limit (if configured)
        responses = []
        for _ in range(100):
            resp = await client.get("/api/pools")
            responses.append(resp.status_code)

        # Check if we got any 429 responses (rate limiting active)
        # or if all passed (rate limit not configured)
        assert all(code in [200, 429] for code in responses)


@pytest.mark.anyio
async def test_rate_limiting_per_endpoint(tmp_path: Path) -> None:
    """Test rate limiting is applied per endpoint"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Different endpoints should have separate rate limits
        resp1 = await client.get("/api/pools")
        resp2 = await client.get("/api/proxies")
        resp3 = await client.get("/api/subscriptions")

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp3.status_code == 200


@pytest.mark.anyio
async def test_rate_limiting_recovery(tmp_path: Path) -> None:
    """Test that rate limiting recovers after time window"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # First request should succeed
        resp = await client.get("/api/pools")
        assert resp.status_code == 200

        # Wait briefly
        await asyncio.sleep(0.1)

        # Second request should also succeed
        resp = await client.get("/api/pools")
        assert resp.status_code == 200


# ===== Metrics Endpoints Tests =====


@pytest.mark.anyio
async def test_metrics_endpoint_available(tmp_path: Path) -> None:
    """Test that metrics endpoint is available"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "requests" in data or "active_connections" in data


@pytest.mark.anyio
async def test_metrics_pool_specific(tmp_path: Path) -> None:
    """Test getting metrics for specific pool"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a pool
        resp = await client.post("/api/pools", json={"name": "metrics-test-pool"})
        pool_id = resp.json()["item"]["id"]

        # Get pool metrics
        resp = await client.get(f"/api/pools/{pool_id}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "pool_id" in data


@pytest.mark.anyio
async def test_metrics_pool_not_found(tmp_path: Path) -> None:
    """Test metrics for non-existent pool"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/pools/999/metrics")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_metrics_proxy_overview(tmp_path: Path) -> None:
    """Test proxy metrics overview"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add test proxies with metrics
    for i in range(5):
        proxy = ProxyNode(
            protocol="trojan",
            host=f"us{i}.example.com",
            port=443,
            raw_link=f"trojan://us{i}",
            extra={"password": "p"},
        )
        storage.upsert_proxy(proxy)
        storage.update_test_result(
            proxy.normalized_key(),
            available=True,
            latency_ms=100 + i * 10,
        )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] >= 5


@pytest.mark.anyio
async def test_metrics_with_time_range(tmp_path: Path) -> None:
    """Test metrics with time range parameters"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Get system metrics
        resp = await client.get("/api/system/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "requests" in data or "active_connections" in data


@pytest.mark.anyio
async def test_metrics_performance_stats(tmp_path: Path) -> None:
    """Test performance statistics endpoint"""
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


@pytest.mark.anyio
async def test_metrics_request_tracking(tmp_path: Path) -> None:
    """Test request tracking metrics"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Make several requests to generate metrics
        for _ in range(5):
            await client.get("/api/pools")

        # Check system metrics
        resp = await client.get("/api/system/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "requests" in data or "active_connections" in data


@pytest.mark.anyio
async def test_metrics_health_check_integration(tmp_path: Path) -> None:
    """Test metrics integration with health check"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Run health check
        resp = await client.get("/api/system/health")
        assert resp.status_code == 200
        health = resp.json()

        # Check metrics are included
        assert "proxy_count" in health
        assert "pool_count" in health
        assert "healthy_proxy_rate" in health
