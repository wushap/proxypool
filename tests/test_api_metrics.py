"""
Tests for Wave 17.3: Backend performance metrics endpoints.
Tests for system metrics, pool metrics, and metrics export.
"""

from __future__ import annotations

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


def _make_settings(tmp_path_factory) -> AppSettings:
    """Create minimal test settings"""
    import tempfile
    from pathlib import Path

    tmp = tmp_path_factory.mktemp("test_metrics")
    return AppSettings(
        project_root=tmp,
        db_path=tmp / "test.db",
        output_dir=tmp / "output",
        sources_file=tmp / "sources.txt",
        singbox_routes_file=tmp / "routes.json",
        singbox_runtime_config_file=tmp / "runtime.json",
        singbox_runtime_log_file=tmp / "runtime.log",
        singbox_binary="sing-box",
        test_url="https://httpbin.org/get",
        api_key="test-key",
        backend_engine="singbox",
        backend_health_check_sec=60,
        backend_auto_restart_max=3,
    )


async def test_system_metrics_endpoint(tmp_path_factory):
    """GET /api/system/metrics returns system metrics"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/metrics")
        assert resp.status_code == 200
        data = resp.json()

        # Check required fields
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert "requests" in data
        assert "active_connections" in data
        assert "total_proxies_tested" in data
        assert "proxy_test_success_rate" in data

        # Check requests structure
        requests = data["requests"]
        assert "total_requests" in requests
        assert "successful_requests" in requests
        assert "failed_requests" in requests
        assert "error_rate" in requests
        assert "avg_latency_ms" in requests
        assert "latency_percentiles" in requests

        # Check latency percentiles
        percentiles = requests["latency_percentiles"]
        assert "p50" in percentiles
        assert "p90" in percentiles
        assert "p95" in percentiles
        assert "p99" in percentiles


async def test_system_metrics_response_model(tmp_path_factory):
    """GET /api/system/metrics uses correct response model"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/metrics")
        assert resp.status_code == 200
        data = resp.json()

        # Verify response matches SystemMetricsResponse schema
        assert isinstance(data["requests"]["total_requests"], int)
        assert isinstance(data["requests"]["error_rate"], float)
        assert isinstance(data["requests"]["latency_percentiles"]["p50"], float)


async def test_metrics_export_endpoint(tmp_path_factory):
    """GET /api/system/metrics/export returns complete metrics"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/metrics/export")
        assert resp.status_code == 200
        data = resp.json()

        # Check required fields
        assert "exported_at" in data
        assert "system_metrics" in data
        assert "windows" in data
        assert "pools" in data

        # Check windows structure
        windows = data["windows"]
        assert len(windows) == 3  # 1min, 5min, 1hour

        # Check each window
        window_names = {w["window"] for w in windows}
        assert "1min" in window_names
        assert "5min" in window_names
        assert "1hour" in window_names

        # Check window structure
        for window in windows:
            assert "start_time" in window
            assert "end_time" in window
            assert "requests" in window
            assert "total_requests" in window["requests"]


async def test_metrics_export_response_model(tmp_path_factory):
    """GET /api/system/metrics/export uses correct response model"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/metrics/export")
        assert resp.status_code == 200
        data = resp.json()

        # Verify response matches MetricsExportResponse schema
        assert isinstance(data["exported_at"], str)
        assert isinstance(data["system_metrics"]["uptime_seconds"], int)
        assert isinstance(data["windows"], list)


async def test_pool_metrics_not_found(tmp_path_factory):
    """GET /api/pools/{id}/metrics returns 404 for non-existent pool"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/999/metrics")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]


async def test_pool_metrics_endpoint(tmp_path_factory):
    """GET /api/pools/{id}/metrics returns pool metrics"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # First create a pool
        pool_resp = await client.post(
            "/api/pools",
            json={"name": "Test Pool", "filters": {}, "inbound_type": "http"},
        )
        assert pool_resp.status_code == 200
        pool_id = pool_resp.json()["item"]["id"]

        # Get pool metrics
        resp = await client.get(f"/api/pools/{pool_id}/metrics")
        assert resp.status_code == 200
        data = resp.json()

        # Check required fields
        assert "pool_id" in data
        assert "pool_name" in data
        assert "timestamp" in data
        assert "requests" in data
        assert "active_proxies" in data
        assert "total_proxies" in data
        assert "healthy_proxies" in data
        assert "proxy_health_rate" in data
        assert "avg_latency_ms" in data

        # Verify pool info
        assert data["pool_id"] == pool_id
        assert data["pool_name"] == "Test Pool"


async def test_pool_metrics_response_model(tmp_path_factory):
    """GET /api/pools/{id}/metrics uses correct response model"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create a pool
        pool_resp = await client.post(
            "/api/pools",
            json={"name": "Test Pool 2", "filters": {}, "inbound_type": "http"},
        )
        pool_id = pool_resp.json()["item"]["id"]

        # Get metrics
        resp = await client.get(f"/api/pools/{pool_id}/metrics")
        assert resp.status_code == 200
        data = resp.json()

        # Verify response matches PoolMetricsResponse schema
        assert isinstance(data["pool_id"], int)
        assert isinstance(data["pool_name"], str)
        assert isinstance(data["proxy_health_rate"], float)
        assert isinstance(data["avg_latency_ms"], float)


async def test_metrics_tracking_works(tmp_path_factory):
    """Verify that metrics are actually being tracked"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Make some requests
        await client.get("/api/health")
        await client.get("/api/stats")
        await client.get("/api/health")

        # Check metrics
        resp = await client.get("/api/system/metrics")
        data = resp.json()

        # Should have at least 3 requests tracked (the 3 calls above)
        # Note: The metrics endpoint itself might not be tracked
        assert data["requests"]["total_requests"] >= 3
        assert data["uptime_seconds"] >= 0


async def test_metrics_windows_aggregation(tmp_path_factory):
    """Verify that metrics windows aggregate correctly"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Make some requests to generate data
        for _ in range(5):
            await client.get("/api/health")

        # Get metrics export
        resp = await client.get("/api/system/metrics/export")
        data = resp.json()

        # Check that windows have data
        windows = data["windows"]
        for window in windows:
            assert "requests" in window
            # At least some requests should be in 1min window
            if window["window"] == "1min":
                assert window["requests"]["total_requests"] >= 5
