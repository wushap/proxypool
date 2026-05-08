from __future__ import annotations

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings
from proxypool.tester.service import BatchTestReport


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
async def test_tester_run_passes_unavailable_and_min_age_filters(tmp_path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    captured: dict = {}

    async def fake_run_batch(**kwargs):
        captured.update(kwargs)
        return BatchTestReport(requested=1, tested=0, available=0, unavailable=0)

    monkeypatch.setattr(app.state.tester, "run_batch", fake_run_batch)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/tester/run",
            json={
                "limit": 0,
                "concurrency": 60,
                "only_unavailable": True,
                "min_last_checked_age_hours": 24,
            },
        )
        assert resp.status_code == 200
        assert captured.get("only_unavailable") is True
        assert int(captured.get("min_last_checked_age_hours") or 0) == 24

