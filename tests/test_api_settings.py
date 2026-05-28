"""Tests for settings and backend management API endpoints."""

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
        backend_engine="singbox",
        backend_health_check_sec=30,
        backend_auto_restart_max=3,
    )


# ---- GET /api/settings ----


@pytest.mark.anyio
async def test_get_settings_returns_current_values(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/settings")

    assert resp.status_code == 200
    body = resp.json()
    assert "item" in body
    item = body["item"]
    assert item["test_url"] == "https://www.cloudflare.com/cdn-cgi/trace"
    assert item["backend_health_check_sec"] == 30
    assert "max_proxy_count" in item
    assert "max_failures_threshold" in item


# ---- PUT /api/settings ----


@pytest.mark.anyio
async def test_update_settings_returns_not_implemented(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/settings",
            json={"test_url": "https://example.com"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "not implemented"}


# ---- GET /api/config/export ----


@pytest.mark.anyio
async def test_export_config_returns_full_structure(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config/export")

    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["version"] == "1.0"
    assert "exported_at" in data
    assert isinstance(data["settings"], dict)
    assert isinstance(data["pools"], list)
    assert isinstance(data["endpoints"], list)
    assert isinstance(data["subscriptions"], list)
    assert isinstance(data["gateway_config"], dict)
    assert isinstance(data["chain_config"], dict)


@pytest.mark.anyio
async def test_export_config_settings_match(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config/export")

    data = resp.json()["data"]
    settings = data["settings"]
    assert settings["test_url"] == "https://www.cloudflare.com/cdn-cgi/trace"
    assert settings["backend_health_check_sec"] == 30


@pytest.mark.anyio
async def test_export_config_empty_db_has_no_pools(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config/export")

    data = resp.json()["data"]
    assert data["pools"] == []
    assert data["endpoints"] == []
    assert data["subscriptions"] == []


# ---- POST /api/config/import ----


@pytest.mark.anyio
async def test_import_config_empty_data_succeeds(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/config/import",
            json={
                "data": {
                    "version": "1.0",
                    "exported_at": "2026-01-01T00:00:00Z",
                    "settings": {},
                    "pools": [],
                    "endpoints": [],
                    "subscriptions": [],
                    "gateway_config": {},
                    "chain_config": {},
                },
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["imported_items"]["pools"] == 0
    assert body["errors"] == []


@pytest.mark.anyio
async def test_import_config_creates_pools(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/config/import",
            json={
                "data": {
                    "version": "1.0",
                    "exported_at": "2026-01-01T00:00:00Z",
                    "settings": {},
                    "pools": [
                        {"name": "imported-pool", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
                    ],
                    "endpoints": [],
                    "subscriptions": [],
                    "gateway_config": {},
                    "chain_config": {},
                },
                "import_pools": True,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["imported_items"]["pools"] == 1

    # Verify pool was created
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        export_resp = await client.get("/api/config/export")
    pools = export_resp.json()["data"]["pools"]
    assert any(p["name"] == "imported-pool" for p in pools)


@pytest.mark.anyio
async def test_import_config_skips_existing_pool_without_overwrite(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    import_data = {
        "data": {
            "version": "1.0",
            "exported_at": "2026-01-01T00:00:00Z",
            "settings": {},
            "pools": [
                {"name": "dup-pool", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
            ],
            "endpoints": [],
            "subscriptions": [],
            "gateway_config": {},
            "chain_config": {},
        },
        "import_pools": True,
        "overwrite_existing": False,
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # First import
        resp1 = await client.post("/api/config/import", json=import_data)
        assert resp1.json()["imported_items"]["pools"] == 1

        # Second import -- should skip
        resp2 = await client.post("/api/config/import", json=import_data)
        assert resp2.json()["imported_items"]["pools"] == 0
        assert any("已存在" in w for w in resp2.json()["warnings"])


# ---- GET /api/backend/status ----


@pytest.mark.anyio
async def test_backend_status_returns_dict(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/status")

    assert resp.status_code == 200
    body = resp.json()
    # status() returns a dict with at least 'running' key
    assert "running" in body


# ---- GET /api/backend/default-port-range ----


@pytest.mark.anyio
async def test_get_backend_default_port_range(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/default-port-range")

    assert resp.status_code == 200
    assert resp.json() == {"start": 1081, "end": 1180}


# ---- PUT /api/backend/default-port-range ----


@pytest.mark.anyio
async def test_set_backend_default_port_range(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/backend/default-port-range",
            json={"start": 20001, "end": 20100},
        )

    assert resp.status_code == 200
    assert resp.json() == {"start": 20001, "end": 20100}

    # Verify persisted
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        get_resp = await client.get("/api/backend/default-port-range")
    assert get_resp.json() == {"start": 20001, "end": 20100}


@pytest.mark.anyio
async def test_set_backend_default_port_range_rejects_invalid(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/backend/default-port-range",
            json={"start": 50000, "end": 40000},
        )

    assert resp.status_code == 422


# ---- GET /api/backend/default-listen ----


@pytest.mark.anyio
async def test_get_backend_default_listen(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/default-listen")

    assert resp.status_code == 200
    assert resp.json() == {"listen": "127.0.0.1"}
