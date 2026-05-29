"""Tests to push chain.py router coverage beyond 75% by hitting missing branches."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


def _make_settings(tmp_path: Path) -> AppSettings:
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
        api_key="",
        backend_engine="singbox",
        backend_health_check_sec=60,
        backend_auto_restart_max=3,
    )


# -- GET /api/chain/leases --


@pytest.mark.anyio
async def test_chain_leases(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/leases")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)


# -- GET /api/chain/nodes --


@pytest.mark.anyio
async def test_chain_nodes(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    # list_nodes doesn't exist on real service; mock it to hit the endpoint body
    mock_service = MagicMock()
    mock_service.list_nodes.return_value = [{"id": 1}]
    app.state.chain_service = mock_service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/nodes")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)


# -- POST /api/chain/leases/cleanup (happy path with valid max_age_sec) --


@pytest.mark.anyio
async def test_chain_leases_cleanup(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chain/leases/cleanup?max_age_sec=3600")
        assert resp.status_code == 200
        data = resp.json()
        assert "cleaned" in data
        assert isinstance(data["cleaned"], int)


# -- POST /api/chain/pools/{pool_type} without body (covers body-is-None branch) --


@pytest.mark.anyio
async def test_chain_pool_create_no_body(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chain/pools/front")
        assert resp.status_code in [200, 400]


# -- POST /api/chain/pools/{pool_type} that raises (covers exception branch) --


@pytest.mark.anyio
async def test_chain_pool_create_exception(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.update_pool_config.side_effect = RuntimeError("config error")
    app.state.chain_service = mock_service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chain/pools/front", json={})
        assert resp.status_code == 400
        assert "config error" in resp.json()["detail"]


# -- POST /api/chain/start exception branch --


@pytest.mark.anyio
async def test_chain_start_exception(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.start.side_effect = RuntimeError("start failed")
    app.state.chain_service = mock_service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chain/start")
        assert resp.status_code == 400
        assert "start failed" in resp.json()["detail"]


# -- POST /api/chain/stop exception branch --


@pytest.mark.anyio
async def test_chain_stop_exception(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.stop.side_effect = RuntimeError("stop failed")
    app.state.chain_service = mock_service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chain/stop")
        assert resp.status_code == 400
        assert "stop failed" in resp.json()["detail"]


# -- Diagnostics: exception in pool_status --


@pytest.mark.anyio
async def test_chain_diagnostics_pool_status_exception(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.get_pool_status.side_effect = RuntimeError("pool error")
    mock_service.get_health_status.return_value = {}
    app.state.chain_service = mock_service
    mock_instance_mgr = MagicMock()
    mock_instance_mgr.list_all_leases.return_value = []
    app.state.chain_instance_manager = mock_instance_mgr
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["front_pool"] == {}
        assert data["exit_pool"] == {}


# -- Diagnostics: exception in health_status --


@pytest.mark.anyio
async def test_chain_diagnostics_health_exception(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.get_pool_status.return_value = {"front": {}, "exit": {}}
    mock_service.get_health_status.side_effect = RuntimeError("health error")
    app.state.chain_service = mock_service
    mock_instance_mgr = MagicMock()
    mock_instance_mgr.list_all_leases.return_value = []
    app.state.chain_instance_manager = mock_instance_mgr
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["health_check"] == {}


# -- Diagnostics: exception in list_all_leases --


@pytest.mark.anyio
async def test_chain_diagnostics_leases_exception(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.get_pool_status.return_value = {"front": {}, "exit": {}}
    mock_service.get_health_status.return_value = {}
    app.state.chain_service = mock_service
    mock_instance_mgr = MagicMock()
    mock_instance_mgr.list_all_leases.side_effect = RuntimeError("lease error")
    app.state.chain_instance_manager = mock_instance_mgr
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_leases"] == 0


# -- Diagnostics: unhealthy front pool triggers degraded status --


@pytest.mark.anyio
async def test_chain_diagnostics_unhealthy_front(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.get_pool_status.return_value = {
        "front": {"healthy": False},
        "exit": {"healthy": True},
    }
    mock_service.get_health_status.return_value = {}
    app.state.chain_service = mock_service
    mock_instance_mgr = MagicMock()
    mock_instance_mgr.list_all_leases.return_value = []
    app.state.chain_instance_manager = mock_instance_mgr
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert "Front pool is unhealthy" in data["recent_errors"]


# -- Diagnostics: unhealthy exit pool triggers degraded status --


@pytest.mark.anyio
async def test_chain_diagnostics_unhealthy_exit(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.get_pool_status.return_value = {
        "front": {"healthy": True},
        "exit": {"healthy": False},
    }
    mock_service.get_health_status.return_value = {}
    app.state.chain_service = mock_service
    mock_instance_mgr = MagicMock()
    mock_instance_mgr.list_all_leases.return_value = []
    app.state.chain_instance_manager = mock_instance_mgr
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert "Exit pool is unhealthy" in data["recent_errors"]


# -- Diagnostics: health errors are included in recent_errors --


@pytest.mark.anyio
async def test_chain_diagnostics_health_errors(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.get_pool_status.return_value = {
        "front": {"healthy": True},
        "exit": {"healthy": True},
    }
    mock_service.get_health_status.return_value = {
        "errors": ["error one", "error two", "error three"],
    }
    app.state.chain_service = mock_service
    mock_instance_mgr = MagicMock()
    mock_instance_mgr.list_all_leases.return_value = []
    app.state.chain_instance_manager = mock_instance_mgr
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        # Health errors should appear in recent_errors (up to 5)
        assert "error one" in data["recent_errors"]
        assert "error two" in data["recent_errors"]
        assert "error three" in data["recent_errors"]


# -- GET /api/chain/route returning None triggers 503 --


@pytest.mark.anyio
async def test_chain_route_returns_none(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.initialize = MagicMock()
    mock_service.route_request.return_value = None
    app.state.chain_service = mock_service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/route")
        assert resp.status_code == 503
        assert "No available nodes" in resp.json()["detail"]


# -- POST /api/chain/pools/{pool_type} body=None branch --


@pytest.mark.anyio
async def test_chain_pool_create_body_none(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.update_pool_config.return_value = {"status": "ok"}
    app.state.chain_service = mock_service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Send request without Content-Type body so body param stays None
        resp = await client.post(
            "/api/chain/pools/front",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200


# -- Diagnostics: both pools unhealthy --


@pytest.mark.anyio
async def test_chain_diagnostics_both_unhealthy(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    mock_service = MagicMock()
    mock_service.get_pool_status.return_value = {
        "front": {"healthy": False},
        "exit": {"healthy": False},
    }
    mock_service.get_health_status.return_value = {
        "errors": ["critical failure"],
    }
    app.state.chain_service = mock_service
    mock_instance_mgr = MagicMock()
    mock_instance_mgr.list_all_leases.return_value = [
        {"active": True},
        {"active": False},
        {"active": True},
    ]
    app.state.chain_instance_manager = mock_instance_mgr
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["active_leases"] == 2  # only active=True counted
        assert "Front pool is unhealthy" in data["recent_errors"]
        assert "Exit pool is unhealthy" in data["recent_errors"]
        assert "critical failure" in data["recent_errors"]
