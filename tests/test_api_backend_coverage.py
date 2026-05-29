"""
Tests for backend router endpoints to increase coverage of
proxypool/api/routers/backend.py.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


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


# ---- GET /api/backend/status ----


@pytest.mark.anyio
async def test_backend_status(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert "backend" in data
        assert data["running"] is False


# ---- GET /api/backend/routes ----


@pytest.mark.anyio
async def test_backend_routes(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/routes")
        assert resp.status_code == 200
        data = resp.json()
        assert "routes" in data
        assert isinstance(data["routes"], list)


# ---- GET /api/backend/default-port-range ----


@pytest.mark.anyio
async def test_backend_get_default_port_range(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/default-port-range")
        assert resp.status_code == 200
        data = resp.json()
        assert "start" in data
        assert "end" in data


# ---- PUT /api/backend/default-port-range ----


@pytest.mark.anyio
async def test_backend_set_default_port_range(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/backend/default-port-range",
            json={"start": 2000, "end": 3000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["start"] == 2000
        assert data["end"] == 3000


@pytest.mark.anyio
async def test_backend_set_default_port_range_invalid(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # start > end triggers Pydantic validation -> 422
        resp = await client.put(
            "/api/backend/default-port-range",
            json={"start": 5000, "end": 1000},
        )
        assert resp.status_code == 422


# ---- GET /api/backend/default-listen ----


@pytest.mark.anyio
async def test_backend_get_default_listen(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/default-listen")
        assert resp.status_code == 200
        data = resp.json()
        assert "listen" in data


# ---- PUT /api/backend/default-listen ----


@pytest.mark.anyio
async def test_backend_set_default_listen(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/backend/default-listen",
            json={"listen": "0.0.0.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["listen"] == "0.0.0.0"


@pytest.mark.anyio
async def test_backend_set_default_listen_too_long(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/backend/default-listen",
            json={"listen": "x" * 81},
        )
        assert resp.status_code == 400


# ---- GET /api/backend/instances ----


@pytest.mark.anyio
async def test_backend_instances(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/instances")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)


# ---- POST /api/backend/instances ----


@pytest.mark.anyio
async def test_backend_create_instance(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/backend/instances",
            json={"instance_id": "test-inst-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        assert "items" in data


@pytest.mark.anyio
async def test_backend_create_instance_duplicate(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create once
        resp = await client.post(
            "/api/backend/instances",
            json={"instance_id": "dup-inst"},
        )
        assert resp.status_code == 200
        # Create again - same ID should still succeed (upsert)
        resp = await client.post(
            "/api/backend/instances",
            json={"instance_id": "dup-inst"},
        )
        assert resp.status_code == 200


# ---- GET /api/backend/latency ----


@pytest.mark.anyio
async def test_backend_latency_no_routes(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/latency")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert "items" in data
        assert data["items"] == []


# ---- GET /api/backend/process-events ----


@pytest.mark.anyio
async def test_backend_process_events(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/process-events")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)


@pytest.mark.anyio
async def test_backend_process_events_custom_limit(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/process-events?limit=10")
        assert resp.status_code == 200


# ---- POST /api/backend/routes ----


@pytest.mark.anyio
async def test_backend_set_routes_empty(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/backend/routes",
            json={"routes": [], "auto_restart": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "routes" in data


@pytest.mark.anyio
async def test_backend_set_routes_with_items(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/backend/routes",
            json={
                "routes": [
                    {
                        "inbound_port": 11001,
                        "proxy_key": "pk1",
                        "inbound_type": "http",
                        "listen": "127.0.0.1",
                    }
                ],
                "auto_restart": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "routes" in data
        assert len(data["routes"]) == 1
        assert data["routes"][0]["inbound_port"] == 11001


# ---- POST /api/backend/routes - error path ----


@pytest.mark.anyio
async def test_backend_set_routes_validation_error(tmp_path: Path) -> None:
    """Routes with no proxy_key trigger RuntimeError -> 400."""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/backend/routes",
            json={
                "routes": [
                    {"inbound_port": 11002, "proxy_key": "", "inbound_type": "http"}
                ],
                "auto_restart": False,
            },
        )
        assert resp.status_code == 400


# ---- POST /api/backend/instances/{instance_id}/start ----


@pytest.mark.anyio
async def test_backend_instance_start(tmp_path: Path) -> None:
    """Start tries to launch binary; raises RuntimeError -> 400."""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/backend/instances/nonexistent/start")
        assert resp.status_code == 400


# ---- POST /api/backend/instances/{instance_id}/stop ----


@pytest.mark.anyio
async def test_backend_instance_stop(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/backend/instances/nonexistent/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data


# ---- GET /api/backend/instances/{instance_id}/routes ----


@pytest.mark.anyio
async def test_backend_instance_routes(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/instances/default/routes")
        assert resp.status_code == 200
        data = resp.json()
        assert "routes" in data
        assert data["instance_id"] == "default"


# ---- POST /api/backend/instances/{instance_id}/routes ----


@pytest.mark.anyio
async def test_backend_instance_set_routes(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/backend/instances/default/routes",
            json={
                "routes": [
                    {
                        "inbound_port": 12001,
                        "proxy_key": "test-key",
                        "inbound_type": "socks5",
                        "listen": "0.0.0.0",
                    }
                ],
                "auto_restart": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["instance_id"] == "default"
        assert len(data["routes"]) == 1


# ---- DELETE /api/backend/instances/{instance_id} ----


@pytest.mark.anyio
async def test_backend_instance_delete(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create an instance first, then delete it
        await client.post(
            "/api/backend/instances",
            json={"instance_id": "to-delete"},
        )
        resp = await client.delete("/api/backend/instances/to-delete")
        assert resp.status_code == 200
        data = resp.json()
        assert "deleted" in data
        assert "items" in data


@pytest.mark.anyio
async def test_backend_instance_delete_nonexistent(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/api/backend/instances/no-such-inst")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is False


# ---- POST /api/backend/start ----


@pytest.mark.anyio
async def test_backend_start(tmp_path: Path) -> None:
    """Start tries to launch binary; raises RuntimeError -> 400."""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/backend/start")
        assert resp.status_code == 400


# ---- POST /api/backend/stop ----


@pytest.mark.anyio
async def test_backend_stop(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/backend/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data


# ---- POST /api/backend/restart ----


@pytest.mark.anyio
async def test_backend_restart(tmp_path: Path) -> None:
    """Restart calls stop then start; start raises RuntimeError -> 400."""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/backend/restart")
        assert resp.status_code == 400
