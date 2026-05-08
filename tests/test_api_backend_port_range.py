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


@pytest.mark.anyio
async def test_backend_default_port_range_get_and_set(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        get_resp = await client.get("/api/backend/default-port-range")
        assert get_resp.status_code == 200
        assert get_resp.json() == {"start": 1081, "end": 1180}

        put_resp = await client.put(
            "/api/backend/default-port-range",
            json={"start": 30001, "end": 30100},
        )
        assert put_resp.status_code == 200
        assert put_resp.json() == {"start": 30001, "end": 30100}

        get_resp2 = await client.get("/api/backend/default-port-range")
        assert get_resp2.status_code == 200
        assert get_resp2.json() == {"start": 30001, "end": 30100}


@pytest.mark.anyio
async def test_backend_default_port_range_rejects_invalid_range(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/backend/default-port-range",
            json={"start": 35000, "end": 34000},
        )
        assert resp.status_code == 400
