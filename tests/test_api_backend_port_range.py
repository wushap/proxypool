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


@pytest.mark.anyio
async def test_backend_default_listen_get_and_set(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        get_resp = await client.get("/api/backend/default-listen")
        assert get_resp.status_code == 200
        assert get_resp.json() == {"listen": "127.0.0.1"}

        put_resp = await client.put("/api/backend/default-listen", json={"listen": "0.0.0.0"})
        assert put_resp.status_code == 200
        assert put_resp.json() == {"listen": "0.0.0.0"}


@pytest.mark.anyio
async def test_backend_instances_endpoint_lists_reconciled_instances(tmp_path: Path, monkeypatch) -> None:
    app = create_app(_make_settings(tmp_path))
    app.state.storage.upsert_backend_instance(
        instance_id="alpha",
        pid=12345,
        config_file=str(tmp_path / "singbox-alpha.json"),
        routes_file=str(tmp_path / "routes-alpha.json"),
        log_file=str(tmp_path / "singbox-alpha.log"),
        listen="127.0.0.1",
        ports=[1081],
        status="running",
    )
    monkeypatch.setattr("proxypool.backend.singbox_manager._is_process_alive", lambda _pid: True)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/backend/instances")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["instance_id"] == "alpha"
        assert resp.json()["items"][0]["status"] == "running"


@pytest.mark.anyio
async def test_backend_instance_start_and_stop_endpoints(tmp_path: Path, monkeypatch) -> None:
    app = create_app(_make_settings(tmp_path))
    calls: list[tuple[str, str]] = []

    def fake_start_instance(instance_id: str = "default") -> None:
        calls.append(("start", instance_id))

    def fake_stop_instance(instance_id: str = "default") -> None:
        calls.append(("stop", instance_id))

    monkeypatch.setattr(app.state.singbox_manager, "start_instance", fake_start_instance)
    monkeypatch.setattr(app.state.singbox_manager, "stop_instance", fake_stop_instance)
    monkeypatch.setattr(app.state.singbox_manager, "status", lambda: {"ok": True})
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_resp = await client.post("/api/backend/instances/alpha/start")
        stop_resp = await client.post("/api/backend/instances/alpha/stop")

    assert start_resp.status_code == 200
    assert stop_resp.status_code == 200
    assert calls == [("start", "alpha"), ("stop", "alpha")]


@pytest.mark.anyio
async def test_backend_instance_delete_endpoint(tmp_path: Path, monkeypatch) -> None:
    app = create_app(_make_settings(tmp_path))
    calls: list[str] = []

    def fake_delete_instance(instance_id: str) -> bool:
        calls.append(instance_id)
        return True

    monkeypatch.setattr(app.state.singbox_manager, "delete_instance", fake_delete_instance)
    monkeypatch.setattr(app.state.singbox_manager, "list_instances", lambda: [])
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/api/backend/instances/alpha")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "items": []}
    assert calls == ["alpha"]


@pytest.mark.anyio
async def test_backend_instance_create_endpoint_creates_stopped_instance(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/backend/instances", json={"instance_id": "alpha"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["item"]["instance_id"] == "alpha"
    assert body["item"]["status"] == "stopped"
    assert body["item"]["pid"] == -1


@pytest.mark.anyio
async def test_backend_instance_routes_get_and_set(tmp_path: Path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        put_resp = await client.post(
            "/api/backend/instances/alpha/routes",
            json={
                "routes": [
                    {
                        "inbound_port": 2081,
                        "proxy_key": "alpha-key",
                        "exit_proxy_key": "alpha-key",
                        "inbound_type": "http",
                        "listen": "127.0.0.1",
                    }
                ],
                "auto_restart": False,
            },
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["instance_id"] == "alpha"
        assert put_resp.json()["routes"][0]["inbound_port"] == 2081

        get_resp = await client.get("/api/backend/instances/alpha/routes")
        assert get_resp.status_code == 200
        assert get_resp.json()["instance_id"] == "alpha"
        assert get_resp.json()["routes"][0]["exit_proxy_key"] == "alpha-key"
