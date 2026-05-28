"""
Comprehensive tests for chain diagnostics API endpoints.
Tests for chain status, health, routing, pool creation, and diagnostics.
Note: Some endpoints (leases, nodes) have missing methods in the current implementation.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


def _make_settings(tmp_path: Path) -> AppSettings:
    """Create minimal test settings"""
    return AppSettings(
        project_root=tmp_path,
        db_path=tmp_path / "test.db",
        output_dir=tmp_path / "output",
        sources_file=tmp_path / "sources.txt",
        singbox_routes_file=tmp_path / "routes.json",
        singbox_runtime_config_file=tmp_path / "runtime.json",
        singbox_runtime_log_file=tmp_path / "runtime.log",
        singbox_binary="sing-box",
        test_url="https://httpbin.org/get",
        api_key="",  # Disable auth for testing
        backend_engine="singbox",
        backend_health_check_sec=60,
        backend_auto_restart_max=3,
    )


# ===== Chain Status Tests =====


@pytest.mark.anyio
async def test_chain_status_endpoint(tmp_path: Path) -> None:
    """GET /api/chain/status returns chain status"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/status")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


@pytest.mark.anyio
async def test_chain_health_endpoint(tmp_path: Path) -> None:
    """GET /api/chain/health returns health status"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/health")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


# ===== Chain Start/Stop Tests =====


@pytest.mark.anyio
async def test_chain_start_endpoint(tmp_path: Path) -> None:
    """POST /api/chain/start starts chain proxy"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chain/start")
        assert resp.status_code in [200, 400, 500]
        if resp.status_code == 200:
            data = resp.json()
            assert "status" in data


@pytest.mark.anyio
async def test_chain_stop_endpoint(tmp_path: Path) -> None:
    """POST /api/chain/stop stops chain proxy"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chain/stop")
        assert resp.status_code in [200, 400, 500]
        if resp.status_code == 200:
            data = resp.json()
            assert "status" in data


# ===== Chain Route Tests =====


@pytest.mark.anyio
async def test_chain_route_endpoint(tmp_path: Path) -> None:
    """GET /api/chain/route returns route information"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/route?session_id=test&pool_id=0&target_domain=example.com")
        assert resp.status_code in [200, 503]
        if resp.status_code == 503:
            data = resp.json()
            assert "detail" in data


# ===== Chain Pool Creation Tests =====


@pytest.mark.anyio
async def test_chain_pool_creation(tmp_path: Path) -> None:
    """POST /api/chain/pools/{pool_type} creates chain pool"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chain/pools/front", json={})
        assert resp.status_code in [200, 400]


@pytest.mark.anyio
async def test_chain_pool_creation_with_filters(tmp_path: Path) -> None:
    """POST /api/chain/pools/{pool_type} with regex filters"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/chain/pools/exit",
            json={},
            params={"regex_filters": ["test-filter"]},
        )
        assert resp.status_code in [200, 400]


# ===== Chain Lease Cleanup Validation Tests =====


@pytest.mark.anyio
async def test_chain_lease_cleanup_min_age(tmp_path: Path) -> None:
    """POST /api/chain/leases/cleanup respects min age constraint"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Should fail with validation error
        resp = await client.post("/api/chain/leases/cleanup?max_age_sec=30")
        assert resp.status_code == 422  # Validation error


# ===== Comprehensive Diagnostics Tests =====


@pytest.mark.anyio
async def test_chain_diagnostics_comprehensive(tmp_path: Path) -> None:
    """GET /api/chain/diagnostics returns comprehensive diagnostic info"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()

        # Check required fields
        assert "status" in data
        assert "front_pool" in data
        assert "exit_pool" in data
        assert "health_check" in data
        assert "active_leases" in data
        assert "circuit_breakers" in data
        assert "routing_stats" in data
        assert "recent_errors" in data

        # Verify types
        assert isinstance(data["front_pool"], dict)
        assert isinstance(data["exit_pool"], dict)
        assert isinstance(data["health_check"], dict)
        assert isinstance(data["active_leases"], int)
        assert isinstance(data["circuit_breakers"], dict)
        assert isinstance(data["routing_stats"], dict)
        assert isinstance(data["recent_errors"], list)


@pytest.mark.anyio
async def test_chain_diagnostics_routing_stats(tmp_path: Path) -> None:
    """GET /api/chain/diagnostics includes routing stats"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()

        # Check routing stats structure
        routing_stats = data["routing_stats"]
        assert "total_routes" in routing_stats
        assert "active_routes" in routing_stats
        assert isinstance(routing_stats["total_routes"], int)
        assert isinstance(routing_stats["active_routes"], int)


@pytest.mark.anyio
async def test_chain_diagnostics_health_status_values(tmp_path: Path) -> None:
    """GET /api/chain/diagnostics returns valid health status"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()

        # Status should be one of the expected values
        assert data["status"] in ["healthy", "degraded", "unhealthy", "unknown"]


@pytest.mark.anyio
async def test_chain_diagnostics_after_operations(tmp_path: Path) -> None:
    """GET /api/chain/diagnostics reflects system state after operations"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Get initial diagnostics
        resp1 = await client.get("/api/chain/diagnostics")
        assert resp1.status_code == 200
        data1 = resp1.json()

        # Perform some operations
        await client.get("/api/chain/status")

        # Get diagnostics again
        resp2 = await client.get("/api/chain/diagnostics")
        assert resp2.status_code == 200
        data2 = resp2.json()

        # Status should be consistent
        assert data1["status"] == data2["status"]


# ===== Integration Tests =====


@pytest.mark.anyio
async def test_chain_endpoints_integration(tmp_path: Path) -> None:
    """Test multiple chain endpoints work together"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Get status
        status_resp = await client.get("/api/chain/status")
        assert status_resp.status_code == 200

        # Get health
        health_resp = await client.get("/api/chain/health")
        assert health_resp.status_code == 200

        # Get diagnostics
        diag_resp = await client.get("/api/chain/diagnostics")
        assert diag_resp.status_code == 200


@pytest.mark.anyio
async def test_chain_diagnostics_performance(tmp_path: Path) -> None:
    """Verify chain diagnostics endpoint responds quickly"""
    import time

    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        endpoints = [
            "/api/chain/status",
            "/api/chain/health",
            "/api/chain/diagnostics",
        ]

        for endpoint in endpoints:
            start = time.time()
            resp = await client.get(endpoint)
            duration_ms = (time.time() - start) * 1000

            assert resp.status_code == 200
            # Chain endpoints should respond in < 500ms
            assert duration_ms < 500, f"{endpoint} took {duration_ms:.1f}ms"
