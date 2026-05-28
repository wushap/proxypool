from __future__ import annotations

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.models import ProxyNode
from proxypool.settings import AppSettings
from proxypool.tester.service import BatchTestReport
from proxypool.tester.singbox import ProbeResult


def _make_settings(tmp_path) -> AppSettings:
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
async def test_single_proxy_test(tmp_path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    node = ProxyNode(
        protocol="trojan",
        host="tester.example.com",
        port=443,
        raw_link="trojan://tester",
        extra={"password": "pass"},
    )
    app.state.storage.upsert_proxy(node, source="test")

    async def fake_run_one(normalized_key: str, **kwargs):
        return ProbeResult(
            normalized_key=normalized_key,
            available=True,
            latency_ms=88,
            openai_unlocked=False,
            openai_status="403 forbidden",
            error="",
        )

    monkeypatch.setattr(app.state.tester, "run_one", fake_run_one)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/tester/run-one",
            json={"normalized_key": node.normalized_key()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["latency_ms"] == 88
        assert data["normalized_key"] == node.normalized_key()


@pytest.mark.anyio
async def test_single_proxy_test_empty_key(tmp_path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/tester/run-one",
            json={"normalized_key": "   "},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "empty" in data["detail"].lower()


@pytest.mark.anyio
async def test_run_batch_tester(tmp_path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    captured: dict = {}

    async def fake_run_batch(**kwargs):
        captured.update(kwargs)
        return BatchTestReport(
            requested=10,
            tested=10,
            available=7,
            unavailable=3,
            avg_latency_ms=150,
        )

    monkeypatch.setattr(app.state.tester, "run_batch", fake_run_batch)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/tester/run",
            json={
                "limit": 10,
                "concurrency": 20,
                "only_available": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["requested"] == 10
        assert data["tested"] == 10
        assert data["available"] == 7
        assert data["unavailable"] == 3
        assert captured.get("limit") == 10
        assert captured.get("concurrency") == 20
        assert captured.get("only_available") is True


@pytest.mark.anyio
async def test_start_speed_test_task(tmp_path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/tasks/speed-test/start",
            json={
                "url": "https://example.com/speed",
                "limit": 5,
                "timeout_sec": 15.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert isinstance(data["task_id"], str)
        assert len(data["task_id"]) > 0
