from __future__ import annotations

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.models import ProxyNode
from proxypool.settings import AppSettings
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
async def test_single_proxy_test_endpoint_runs_only_target_proxy(tmp_path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    node = ProxyNode(
        protocol="trojan",
        host="demo.example.com",
        port=443,
        raw_link="trojan://demo",
        extra={"password": "p"},
    )
    app.state.storage.upsert_proxy(node, source="test")

    captured: dict = {}

    async def fake_run_one(normalized_key: str, **kwargs):
        captured["normalized_key"] = normalized_key
        captured.update(kwargs)
        return ProbeResult(
            normalized_key=normalized_key,
            available=True,
            latency_ms=123,
            openai_unlocked=True,
            openai_status="401 unauthorized",
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
        assert captured["normalized_key"] == node.normalized_key()
        assert data["normalized_key"] == node.normalized_key()
        assert data["available"] is True
        assert int(data["latency_ms"]) == 123


@pytest.mark.anyio
async def test_single_proxy_test_endpoint_rejects_unknown_proxy(tmp_path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/tester/run-one",
            json={"normalized_key": "missing-key"},
        )
        assert resp.status_code == 404
