from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.collector.service import CollectReport, SourceCollectReport
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
async def test_refresh_subscription_uses_to_thread(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/subscriptions",
            json={"name": "slow-sub", "url": "https://example.com/sub", "enabled": True},
        )
        assert create_resp.status_code == 200
        subscription_id = int(create_resp.json()["item"]["id"])

        def fast_collect_from_subscription(**_: object) -> CollectReport:
            return CollectReport(
                total_sources=1,
                total_parsed=1,
                total_inserted=1,
                by_source=[SourceCollectReport(source="slow", parsed=1, inserted=1)],
            )

        monkeypatch.setattr(
            app.state.collector, "collect_from_subscription", fast_collect_from_subscription
        )
        called = {"value": False}

        async def fake_to_thread(func, /, *args, **kwargs):
            called["value"] = True
            return func(*args, **kwargs)

        monkeypatch.setattr("proxypool.api.app.asyncio.to_thread", fake_to_thread)

        refresh_resp = await client.post(
            f"/api/subscriptions/{subscription_id}/refresh",
            json={"timeout_sec": 1},
        )
        assert called["value"] is True
        assert refresh_resp.status_code == 200


@pytest.mark.anyio
async def test_refresh_enabled_subscriptions_uses_to_thread(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/subscriptions",
            json={"name": "slow-sub", "url": "https://example.com/sub", "enabled": True},
        )
        assert create_resp.status_code == 200

        def fast_collect_from_subscription(**_: object) -> CollectReport:
            return CollectReport(
                total_sources=1,
                total_parsed=1,
                total_inserted=1,
                by_source=[SourceCollectReport(source="slow", parsed=1, inserted=1)],
            )

        monkeypatch.setattr(
            app.state.collector, "collect_from_subscription", fast_collect_from_subscription
        )
        called = {"value": False}

        async def fake_to_thread(func, /, *args, **kwargs):
            called["value"] = True
            return func(*args, **kwargs)

        monkeypatch.setattr("proxypool.api.app.asyncio.to_thread", fake_to_thread)

        refresh_resp = await client.post("/api/subscriptions/refresh-enabled?timeout_sec=1")
        assert called["value"] is True
        assert refresh_resp.status_code == 200
        payload = refresh_resp.json()
        assert payload["count"] == 1


@pytest.mark.anyio
async def test_start_refresh_enabled_subscriptions_task_returns_task_id(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/subscriptions",
            json={"name": "task-sub", "url": "https://example.com/sub", "enabled": True},
        )
        assert create_resp.status_code == 200

        started = asyncio.Event()

        def slow_collect_from_subscription(**_: object) -> CollectReport:
            started.set()
            return CollectReport(
                total_sources=1,
                total_parsed=1,
                total_inserted=1,
                by_source=[SourceCollectReport(source="task", parsed=1, inserted=1)],
            )

        monkeypatch.setattr(
            app.state.collector, "collect_from_subscription", slow_collect_from_subscription
        )

        start_resp = await client.post("/api/tasks/subscriptions-refresh/start?timeout_sec=1")
        assert start_resp.status_code == 200
        payload = start_resp.json()
        assert payload["task_id"]
        assert payload["task"]["kind"] == "subscriptions_refresh"
        await asyncio.wait_for(started.wait(), timeout=1)


@pytest.mark.anyio
async def test_refresh_enabled_subscriptions_task_tracks_progress(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for idx in range(2):
            create_resp = await client.post(
                "/api/subscriptions",
                json={
                    "name": f"task-sub-{idx}",
                    "url": f"https://example.com/sub/{idx}",
                    "enabled": True,
                },
            )
            assert create_resp.status_code == 200

        def fast_collect_from_subscription(**kwargs: object) -> CollectReport:
            sub_id = int(kwargs["subscription_id"])
            return CollectReport(
                total_sources=1,
                total_parsed=1,
                total_inserted=1,
                by_source=[SourceCollectReport(source=f"task-{sub_id}", parsed=1, inserted=1)],
            )

        monkeypatch.setattr(
            app.state.collector, "collect_from_subscription", fast_collect_from_subscription
        )

        start_resp = await client.post("/api/tasks/subscriptions-refresh/start?timeout_sec=1")
        assert start_resp.status_code == 200
        task_id = start_resp.json()["task_id"]

        final_task = None
        for _ in range(50):
            task_resp = await client.get(f"/api/tasks/{task_id}")
            assert task_resp.status_code == 200
            final_task = task_resp.json()
            if final_task["status"] in {"success", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.02)

        assert final_task is not None
        assert final_task["status"] == "success"
        assert final_task["total"] == 2
        assert final_task["completed"] == 2
        assert final_task["success"] == 2
        assert final_task["failed"] == 0
        assert final_task["progress"] == 100.0
        assert len(final_task["result"]["items"]) == 2
