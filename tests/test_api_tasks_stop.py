from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings
from proxypool.tasks.manager import TaskCancelled


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
async def test_stop_task_endpoint_can_cancel_running_tester_task(tmp_path, monkeypatch) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async def fake_run_batch(**kwargs):
        stop_cb = kwargs.get("stop_cb")
        for i in range(120):
            if callable(stop_cb) and stop_cb():
                raise TaskCancelled("cancel requested")
            await asyncio.sleep(0.01)
        return {"requested": 1, "tested": 1, "available": 1, "unavailable": 0}

    monkeypatch.setattr(app.state.tester, "run_batch", fake_run_batch)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_resp = await client.post("/api/tasks/tester/start", json={"limit": 1, "concurrency": 1})
        assert start_resp.status_code == 200
        task_id = start_resp.json()["task_id"]

        stop_resp = await client.post(f"/api/tasks/{task_id}/stop")
        assert stop_resp.status_code == 200
        assert stop_resp.json().get("stopped") is True

        for _ in range(80):
            task_resp = await client.get(f"/api/tasks/{task_id}")
            assert task_resp.status_code == 200
            status = str(task_resp.json().get("status") or "")
            if status == "cancelled":
                break
            await asyncio.sleep(0.03)

        final = (await client.get(f"/api/tasks/{task_id}")).json()
        assert final["status"] == "cancelled"


@pytest.mark.anyio
async def test_delete_task_endpoint_can_delete_finished_task(tmp_path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_resp = await client.post("/api/tasks/tester/start", json={"limit": 0, "concurrency": 1})
        assert start_resp.status_code == 200
        task_id = start_resp.json()["task_id"]

        for _ in range(120):
            task_resp = await client.get(f"/api/tasks/{task_id}")
            assert task_resp.status_code == 200
            status = str(task_resp.json().get("status") or "")
            if status in {"success", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.02)

        del_resp = await client.delete(f"/api/tasks/{task_id}")
        assert del_resp.status_code == 200
        assert del_resp.json().get("deleted") is True

        missing = await client.get(f"/api/tasks/{task_id}")
        assert missing.status_code == 404
