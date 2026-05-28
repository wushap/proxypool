"""Tests for task management API endpoints."""

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


# ---- GET /api/tasks ----


@pytest.mark.anyio
async def test_list_tasks_empty_initially(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/tasks")

    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["items"] == []


@pytest.mark.anyio
async def test_list_tasks_respects_limit_param(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/tasks", params={"limit": 10})

    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ---- GET /api/tasks/{task_id} ----


@pytest.mark.anyio
async def test_get_nonexistent_task_returns_404(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/tasks/nonexistent-id")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "task not found"


# ---- GET /api/tasks/auto-config ----


@pytest.mark.anyio
async def test_get_auto_task_config_returns_defaults(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/tasks/auto-config")

    assert resp.status_code == 200
    body = resp.json()
    assert "item" in body
    assert "last_run" in body
    assert "running" in body

    item = body["item"]
    assert item["enabled"] is False
    assert item["subscription_refresh_enabled"] is True
    assert item["subscription_refresh_minutes"] == 60
    assert item["tester_enabled"] is False
    assert item["speed_test_enabled"] is False
    assert body["running"] is False


# ---- PUT /api/tasks/auto-config ----


@pytest.mark.anyio
async def test_update_auto_task_config(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/tasks/auto-config",
            json={
                "enabled": True,
                "subscription_refresh_enabled": False,
                "subscription_refresh_minutes": 30,
                "tester_enabled": True,
                "tester_minutes": 120,
                "speed_test_enabled": False,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    item = body["item"]
    assert item["enabled"] is True
    assert item["subscription_refresh_enabled"] is False
    assert item["subscription_refresh_minutes"] == 30
    assert item["tester_enabled"] is True
    assert item["tester_minutes"] == 120


@pytest.mark.anyio
async def test_update_auto_task_config_persists(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.put(
            "/api/tasks/auto-config",
            json={"enabled": True, "tester_concurrency": 100},
        )
        resp = await client.get("/api/tasks/auto-config")

    assert resp.status_code == 200
    assert resp.json()["item"]["enabled"] is True
    assert resp.json()["item"]["tester_concurrency"] == 100


@pytest.mark.anyio
async def test_update_auto_task_config_rejects_invalid_speed_test_url(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/tasks/auto-config",
            json={
                "speed_test_enabled": True,
                "speed_test_url": "not-a-valid-url",
            },
        )

    assert resp.status_code == 422
    assert "speed_test_url" in resp.text or "URL" in resp.text


@pytest.mark.anyio
async def test_update_auto_task_config_accepts_valid_speed_test_url(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/tasks/auto-config",
            json={
                "speed_test_enabled": True,
                "speed_test_url": "https://example.com/speed-test",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["item"]["speed_test_url"] == "https://example.com/speed-test"
