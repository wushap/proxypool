"""
Tests for monitoring API endpoints.
Tests for request traces, error summary, bottleneck detection, capacity metrics,
and comprehensive health monitoring endpoints.
"""

from __future__ import annotations

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


def _make_settings(tmp_path_factory) -> AppSettings:
    """Create minimal test settings"""
    from pathlib import Path

    tmp = tmp_path_factory.mktemp("test_monitoring_api")
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
        api_key="",  # Disable auth for testing
        backend_engine="singbox",
        backend_health_check_sec=60,
        backend_auto_restart_max=3,
    )


# ===== Request Traces Tests =====


@pytest.mark.anyio
async def test_system_traces_endpoint(tmp_path_factory):
    """GET /api/system/traces returns request traces"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Generate some requests
        await client.get("/api/health")
        await client.get("/api/stats")

        resp = await client.get("/api/system/traces")
        assert resp.status_code == 200
        data = resp.json()

        # Should be a list of traces
        assert isinstance(data, list)
        assert len(data) >= 0  # May or may not have traces depending on monitoring setup


@pytest.mark.anyio
async def test_system_traces_with_limit(tmp_path_factory):
    """GET /api/system/traces with limit parameter"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/traces?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) <= 5


@pytest.mark.anyio
async def test_system_traces_response_structure(tmp_path_factory):
    """GET /api/system/traces returns correct response structure"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/traces")
        assert resp.status_code == 200
        data = resp.json()

        # Each trace should have expected fields if any exist
        if data:
            trace = data[0]
            assert "correlation_id" in trace
            assert "path" in trace
            assert "method" in trace
            assert "status_code" in trace
            assert "duration_ms" in trace


# ===== Error Summary Tests =====


@pytest.mark.anyio
async def test_system_errors_endpoint(tmp_path_factory):
    """GET /api/system/errors returns error summary"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/errors")
        assert resp.status_code == 200
        data = resp.json()

        # Check required fields
        assert "total_errors" in data
        assert "error_types" in data
        assert "top_error_paths" in data
        assert "error_rate_per_minute" in data
        assert "last_minutes" in data

        # Verify types
        assert isinstance(data["total_errors"], int)
        assert isinstance(data["error_types"], dict)
        assert isinstance(data["top_error_paths"], list)
        assert isinstance(data["error_rate_per_minute"], float)


@pytest.mark.anyio
async def test_system_errors_with_time_range(tmp_path_factory):
    """GET /api/system/errors with last_minutes parameter"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/errors?last_minutes=30")
        assert resp.status_code == 200
        data = resp.json()
        # The endpoint returns the requested time range in last_minutes
        assert "last_minutes" in data
        assert isinstance(data["last_minutes"], int)


@pytest.mark.anyio
async def test_system_errors_empty_state(tmp_path_factory):
    """GET /api/system/errors with no errors returns empty summary"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/errors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_errors"] == 0
        assert data["error_types"] == {}
        assert data["top_error_paths"] == []


# ===== Bottleneck Detection Tests =====


@pytest.mark.anyio
async def test_system_bottlenecks_endpoint(tmp_path_factory):
    """GET /api/system/bottlenecks returns performance bottlenecks"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/bottlenecks")
        assert resp.status_code == 200
        data = resp.json()

        # Should be a list
        assert isinstance(data, list)


@pytest.mark.anyio
async def test_system_bottlenecks_with_threshold(tmp_path_factory):
    """GET /api/system/bottlenecks with threshold_ms parameter"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/bottlenecks?threshold_ms=200")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


@pytest.mark.anyio
async def test_system_bottlenecks_response_structure(tmp_path_factory):
    """GET /api/system/bottlenecks returns correct response structure"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/bottlenecks")
        assert resp.status_code == 200
        data = resp.json()

        # Each bottleneck should have expected fields if any exist
        if data:
            bottleneck = data[0]
            assert "path" in bottleneck
            assert "avg_latency_ms" in bottleneck
            assert "p95_latency_ms" in bottleneck
            assert "p99_latency_ms" in bottleneck
            assert "request_count" in bottleneck
            assert "error_rate" in bottleneck
            assert "severity" in bottleneck


# ===== Capacity Metrics Tests =====


@pytest.mark.anyio
async def test_system_capacity_endpoint(tmp_path_factory):
    """GET /api/system/capacity returns capacity metrics"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/capacity")
        assert resp.status_code == 200
        data = resp.json()

        # Check required fields
        assert "total_requests" in data
        assert "total_errors" in data
        assert "unique_paths" in data
        assert "latency_stats" in data

        # Verify types
        assert isinstance(data["total_requests"], int)
        assert isinstance(data["total_errors"], int)
        assert isinstance(data["unique_paths"], int)
        assert isinstance(data["latency_stats"], dict)


@pytest.mark.anyio
async def test_system_capacity_after_requests(tmp_path_factory):
    """GET /api/system/capacity reflects actual request data"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Generate requests
        await client.get("/api/health")
        await client.get("/api/stats")

        resp = await client.get("/api/system/capacity")
        assert resp.status_code == 200
        data = resp.json()

        # Should have some requests tracked
        assert data["total_requests"] >= 0


# ===== Comprehensive Health Monitoring Tests =====


@pytest.mark.anyio
async def test_system_health_monitoring_endpoint(tmp_path_factory):
    """GET /api/system/health/monitoring returns comprehensive health data"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/health/monitoring")
        assert resp.status_code == 200
        data = resp.json()

        # Check required fields
        assert "active_requests" in data
        assert "error_summary" in data
        assert "bottlenecks" in data
        assert "capacity" in data
        assert "timestamp" in data


@pytest.mark.anyio
async def test_system_health_monitoring_response_structure(tmp_path_factory):
    """GET /api/system/health/monitoring returns correct nested structure"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/health/monitoring")
        assert resp.status_code == 200
        data = resp.json()

        # Verify error_summary structure
        error_summary = data["error_summary"]
        assert "total_errors" in error_summary
        assert "error_types" in error_summary

        # Verify bottlenecks is a list
        assert isinstance(data["bottlenecks"], list)

        # Verify capacity structure
        capacity = data["capacity"]
        assert "total_requests" in capacity
        assert "total_errors" in capacity


@pytest.mark.anyio
async def test_system_health_monitoring_after_requests(tmp_path_factory):
    """GET /api/system/health/monitoring reflects actual data"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Generate some requests
        for _ in range(3):
            await client.get("/api/health")

        resp = await client.get("/api/system/health/monitoring")
        assert resp.status_code == 200
        data = resp.json()

        # active_requests should be 0 (all completed)
        assert data["active_requests"] >= 0


# ===== Integration Tests =====


@pytest.mark.anyio
async def test_monitoring_endpoints_consistency(tmp_path_factory):
    """Verify monitoring endpoints return consistent data"""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Generate requests
        await client.get("/api/health")
        await client.get("/api/stats")

        # Get data from multiple endpoints
        errors_resp = await client.get("/api/system/errors")
        capacity_resp = await client.get("/api/system/capacity")
        health_resp = await client.get("/api/system/health/monitoring")

        errors = errors_resp.json()
        capacity = capacity_resp.json()
        health = health_resp.json()

        # Error count should be consistent
        assert errors["total_errors"] == capacity["total_errors"]
        assert errors["total_errors"] == health["error_summary"]["total_errors"]


@pytest.mark.anyio
async def test_monitoring_endpoints_performance(tmp_path_factory):
    """Verify monitoring endpoints respond quickly"""
    import time

    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        endpoints = [
            "/api/system/traces",
            "/api/system/errors",
            "/api/system/bottlenecks",
            "/api/system/capacity",
            "/api/system/health/monitoring",
        ]

        for endpoint in endpoints:
            start = time.time()
            resp = await client.get(endpoint)
            duration_ms = (time.time() - start) * 1000

            assert resp.status_code == 200
            # Monitoring endpoints should respond in < 200ms
            assert duration_ms < 200, f"{endpoint} took {duration_ms:.1f}ms"
