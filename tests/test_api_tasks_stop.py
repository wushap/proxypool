from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.models import ProxyNode
from proxypool.settings import AppSettings
from proxypool.tasks.manager import TaskCancelled
from proxypool.tester.singbox import SpeedTestResult


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


@pytest.mark.anyio
async def test_speed_test_task_runs_serial_speed_probe(tmp_path, monkeypatch) -> None:
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage
    node = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="node-a")
    storage.upsert_proxy(node)
    storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)
    calls: list[str] = []

    async def fake_speed_test_async(node, url, timeout_sec=30.0):
        calls.append(str(url))
        return SpeedTestResult(
            normalized_key=str(node.get("normalized_key") or ""),
            ok=True,
            elapsed_ms=1000,
            bytes_downloaded=10_000_000,
            speed_mbps=80.0,
        )

    monkeypatch.setattr(app.state.tester.prober, "speed_test_async", fake_speed_test_async)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_resp = await client.post(
            "/api/tasks/speed-test/start",
            json={
                "url": "https://speed.cloudflare.com/__down?bytes=10000000",
                "limit": 1,
                "timeout_sec": 10,
                "only_available": True,
            },
        )
        assert start_resp.status_code == 200
        task_id = start_resp.json()["task_id"]

        for _ in range(80):
            task_resp = await client.get(f"/api/tasks/{task_id}")
            assert task_resp.status_code == 200
            task = task_resp.json()
            if str(task.get("status")) == "success":
                break
            await asyncio.sleep(0.02)

        final = (await client.get(f"/api/tasks/{task_id}")).json()

    assert calls == ["https://speed.cloudflare.com/__down?bytes=10000000"]
    assert final["kind"] == "speed_test"
    assert final["success"] == 1
    assert final["result"]["items"][0]["speed_mbps"] == 80.0
    row = storage.get_proxy_by_key(node.normalized_key())
    assert row is not None
    assert row["speed_mbps"] == 80.0
    assert row["speed_tested_at"]


@pytest.mark.anyio
async def test_speed_test_only_direct_filters_out_chained_nodes(tmp_path, monkeypatch) -> None:
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage
    direct = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="direct")
    chained = ProxyNode(protocol="http", host="2.2.2.2", port=8080, raw_link="http://2.2.2.2:8080", name="chained")
    storage.upsert_proxy(direct)
    storage.upsert_proxy(chained)
    storage.update_test_result(direct.normalized_key(), available=True, latency_ms=10, fallback_front_keys=[])
    storage.update_test_result(chained.normalized_key(), available=True, latency_ms=20, fallback_front_keys=["front-a"])
    tested_keys: list[str] = []

    async def fake_speed_test_async(node, url, timeout_sec=30.0):
        tested_keys.append(str(node.get("normalized_key") or ""))
        return SpeedTestResult(
            normalized_key=str(node.get("normalized_key") or ""),
            ok=True,
            elapsed_ms=1000,
            bytes_downloaded=10_000_000,
            speed_mbps=80.0,
        )

    monkeypatch.setattr(app.state.tester.prober, "speed_test_async", fake_speed_test_async)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_resp = await client.post(
            "/api/tasks/speed-test/start",
            json={
                "url": "https://speed.cloudflare.com/__down?bytes=10000000",
                "limit": 0,
                "timeout_sec": 10,
                "only_available": True,
                "only_direct": True,
            },
        )
        assert start_resp.status_code == 200
        task_id = start_resp.json()["task_id"]

        for _ in range(80):
            task_resp = await client.get(f"/api/tasks/{task_id}")
            assert task_resp.status_code == 200
            task = task_resp.json()
            if str(task.get("status")) == "success":
                break
            await asyncio.sleep(0.02)

    assert tested_keys == [direct.normalized_key()]


@pytest.mark.anyio
async def test_speed_test_legacy_only_available_defaults_to_direct_nodes(tmp_path, monkeypatch) -> None:
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage
    direct = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="direct")
    chained = ProxyNode(protocol="http", host="2.2.2.2", port=8080, raw_link="http://2.2.2.2:8080", name="chained")
    storage.upsert_proxy(direct)
    storage.upsert_proxy(chained)
    storage.update_test_result(direct.normalized_key(), available=True, latency_ms=10, fallback_front_keys=[])
    storage.update_test_result(chained.normalized_key(), available=True, latency_ms=20, fallback_front_keys=["front-a"])
    tested_keys: list[str] = []

    async def fake_speed_test_async(node, url, timeout_sec=30.0):
        tested_keys.append(str(node.get("normalized_key") or ""))
        return SpeedTestResult(
            normalized_key=str(node.get("normalized_key") or ""),
            ok=True,
            elapsed_ms=1000,
            bytes_downloaded=10_000_000,
            speed_mbps=80.0,
        )

    monkeypatch.setattr(app.state.tester.prober, "speed_test_async", fake_speed_test_async)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_resp = await client.post(
            "/api/tasks/speed-test/start",
            json={
                "url": "https://speed.cloudflare.com/__down?bytes=10000000",
                "limit": 0,
                "timeout_sec": 10,
                "only_available": True,
            },
        )
        assert start_resp.status_code == 200
        task_id = start_resp.json()["task_id"]

        for _ in range(80):
            task_resp = await client.get(f"/api/tasks/{task_id}")
            assert task_resp.status_code == 200
            task = task_resp.json()
            if str(task.get("status")) == "success":
                break
            await asyncio.sleep(0.02)

    assert tested_keys == [direct.normalized_key()]


@pytest.mark.anyio
async def test_auto_task_config_round_trip(tmp_path) -> None:
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    payload = {
        "enabled": True,
        "subscription_refresh_enabled": True,
        "subscription_refresh_minutes": 30,
        "tester_enabled": True,
        "tester_minutes": 45,
        "tester_limit": 10,
        "tester_concurrency": 2,
        "speed_test_enabled": True,
        "speed_test_minutes": 90,
        "speed_test_url": "https://speed.cloudflare.com/__down?bytes=10000000",
        "speed_test_limit": 3,
        "speed_test_timeout_sec": 20,
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        put_resp = await client.put("/api/tasks/auto-config", json=payload)
        assert put_resp.status_code == 200
        get_resp = await client.get("/api/tasks/auto-config")

    assert get_resp.status_code == 200
    assert get_resp.json()["item"]["enabled"] is True
    assert get_resp.json()["item"]["tester_limit"] == 10


@pytest.mark.anyio
async def test_delete_selected_proxies_endpoint(tmp_path) -> None:
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage
    node_a = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="node-a")
    node_b = ProxyNode(protocol="http", host="2.2.2.2", port=8080, raw_link="http://2.2.2.2:8080", name="node-b")
    storage.upsert_proxy(node_a)
    storage.upsert_proxy(node_b)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/delete-selected",
            json={"normalized_keys": [node_a.normalized_key(), "missing"]},
        )

    assert resp.status_code == 200
    assert resp.json()["deleted"] == 1
    assert storage.get_proxy_by_key(node_a.normalized_key()) is None
    assert storage.get_proxy_by_key(node_b.normalized_key()) is not None
