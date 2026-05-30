"""
Tests for proxypool.api.routers.subscriptions targeting uncovered lines.
"""
from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
import httpx
import pytest
from proxypool.api.app import create_app
from proxypool.collector.service import CollectReport, SourceCollectReport
from proxypool.settings import AppSettings

SAFE_URL = "https://example.com/sub"

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
        mihomo_binary="mihomo",
        mihomo_runtime_dir=tmp_path / "runtime" / "mihomo",
    )

class TestCreateSubscriptionException:
    @pytest.mark.anyio
    async def test_create_subscription_storage_error(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        with patch.object(app.state.storage, "create_subscription", side_effect=RuntimeError("err")):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/subscriptions", json={"name": "test-sub", "url": SAFE_URL})
                assert resp.status_code == 400

class TestUpdateSubscriptionException:
    @pytest.mark.anyio
    async def test_update_subscription_storage_error(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        with patch.object(app.state.storage, "update_subscription", side_effect=RuntimeError("err")):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.put("/api/subscriptions/1", json={"name": "updated"})
                assert resp.status_code == 400

class TestSetSubscriptionUpdateProxy:
    @pytest.mark.anyio
    async def test_key_not_found(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put("/api/subscription-update-proxy", json={"update_proxy_key": "nope"})
            assert resp.status_code == 400
    @pytest.mark.anyio
    async def test_empty_key(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put("/api/subscription-update-proxy", json={"update_proxy_key": ""})
            assert resp.status_code == 200
    @pytest.mark.anyio
    async def test_get_key(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/subscription-update-proxy")
            assert resp.status_code == 200

class TestBatchRefresh:
    @pytest.mark.anyio
    async def test_nonexistent_id(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/subscriptions/batch-refresh", json={"subscription_ids": [99999], "timeout_sec": 5.0})
            assert resp.status_code == 200
            assert resp.json()["failed"] == 1
    @pytest.mark.anyio
    async def test_success_path(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/subscriptions", json={"name": "refresh-sub", "url": SAFE_URL, "enabled": True})
            assert r.status_code == 200
            sub_id = r.json()["item"]["id"]
        async def fake_refresh(*a, **kw): pass
        app.state.collector.refresh_subscription = fake_refresh
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/subscriptions/batch-refresh", json={"subscription_ids": [sub_id], "timeout_sec": 5.0})
            assert resp.status_code == 200
            assert resp.json()["success"] == 1
    @pytest.mark.anyio
    async def test_empty_url(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        storage = app.state.storage
        now = datetime.now(UTC).isoformat()
        with storage._connect() as conn:
            conn.execute("INSERT INTO subscriptions (name, url, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                         ("empty-url-sub", "", True, now, now))
            conn.commit()
            sub_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/subscriptions/batch-refresh", json={"subscription_ids": [sub_id], "timeout_sec": 5.0})
            assert resp.status_code == 200
            assert resp.json()["failed"] == 1
            assert "empty" in resp.json()["results"][0]["error"].lower()
    @pytest.mark.anyio
    async def test_collector_exception(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/subscriptions", json={"name": "error-sub", "url": SAFE_URL, "enabled": True})
            assert r.status_code == 200
            sub_id = r.json()["item"]["id"]
        async def failing(*a, **kw): raise RuntimeError("net err")
        app.state.collector.refresh_subscription = failing
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/subscriptions/batch-refresh", json={"subscription_ids": [sub_id], "timeout_sec": 5.0})
            assert resp.status_code == 200
            assert resp.json()["failed"] == 1
    @pytest.mark.anyio
    async def test_general_exception(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        with patch.object(app.state.storage, "get_subscription", side_effect=RuntimeError("db")):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/subscriptions/batch-refresh", json={"subscription_ids": [1], "timeout_sec": 5.0})
                assert resp.status_code == 200
                assert resp.json()["failed"] == 1

class TestPublishedSubscriptions:
    @pytest.mark.anyio
    async def test_create(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/published-subscriptions", json={"name": "pub", "format": "raw"})
            assert r.status_code == 200
            assert "export_url" in r.json()["item"]
    @pytest.mark.anyio
    async def test_create_error(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        with patch.object(app.state.storage, "create_published_subscription", side_effect=RuntimeError("err")):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                assert (await c.post("/api/published-subscriptions", json={"name": "p", "format": "raw"})).status_code == 400
    @pytest.mark.anyio
    async def test_update_error(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        with patch.object(app.state.storage, "update_published_subscription", side_effect=RuntimeError("err")):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                assert (await c.put("/api/published-subscriptions/1", json={"name": "u"})).status_code == 400
    @pytest.mark.anyio
    async def test_delete_404(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.delete("/api/published-subscriptions/99999")).status_code == 404
    @pytest.mark.anyio
    async def test_delete_success(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/published-subscriptions", json={"name": "del", "format": "raw"})
            sid = r.json()["item"]["id"]
            assert (await c.delete(f"/api/published-subscriptions/{sid}")).status_code == 200
    @pytest.mark.anyio
    async def test_get_not_found(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.get("/api/published-subscriptions/99999/subscription")).status_code == 404
    @pytest.mark.anyio
    async def test_get_disabled(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        item = app.state.storage.create_published_subscription(name="dis", enabled=False, format="raw")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.get(f"/api/published-subscriptions/{item['id']}/subscription")).status_code == 404
    @pytest.mark.anyio
    async def test_get_raw(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        item = app.state.storage.create_published_subscription(name="raw", enabled=True, format="raw")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.get(f"/api/published-subscriptions/{item['id']}/subscription")).status_code == 200
    @pytest.mark.anyio
    async def test_get_base64(self, tmp_path: Path) -> None:
        import base64
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        item = app.state.storage.create_published_subscription(name="b64", enabled=True, format="raw")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/published-subscriptions/{item['id']}/subscription", params={"encode_base64": True})
            assert r.status_code == 200
            assert isinstance(base64.b64decode(r.text), bytes)
    @pytest.mark.anyio
    async def test_list(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        app.state.storage.create_published_subscription(name="listed", enabled=True, format="raw")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/published-subscriptions")
            assert r.status_code == 200
            assert len(r.json()["items"]) >= 1
            assert "export_url" in r.json()["items"][0]
    @pytest.mark.anyio
    async def test_clash_format(self, tmp_path: Path) -> None:
        import yaml
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        item = app.state.storage.create_published_subscription(name="clash", enabled=True, format="clash")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/published-subscriptions/{item['id']}/subscription")
            assert r.status_code == 200
            parsed = yaml.safe_load(r.text)
            assert "proxies" in parsed or "proxy-groups" in parsed

class TestRefreshSubscription:
    @pytest.mark.anyio
    async def test_not_found(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.post("/api/subscriptions/99999/refresh", json={"timeout_sec": 10})).status_code == 404
    @pytest.mark.anyio
    async def test_success(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        item = app.state.storage.create_subscription(name="refresh-me", url=SAFE_URL, enabled=True)
        def fake_collect(**kw):
            return CollectReport(total_sources=1, total_parsed=10, total_inserted=5,
                                 by_source=[SourceCollectReport(source="test", parsed=10, inserted=5)])
        app.state.collector.collect_from_subscription = fake_collect
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/subscriptions/{item['id']}/refresh", json={"timeout_sec": 5})
            assert r.status_code == 200
            assert "report" in r.json()

class TestRefreshEnabled:
    @pytest.mark.anyio
    async def test_refresh_enabled(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        app.state.storage.create_subscription(name="enabled-sub", url=SAFE_URL, enabled=True)
        def fake_collect(**kw):
            return CollectReport(total_sources=1, total_parsed=3, total_inserted=1,
                                 by_source=[SourceCollectReport(source="test", parsed=3, inserted=1)])
        app.state.collector.collect_from_subscription = fake_collect
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/subscriptions/refresh-enabled", params={"timeout_sec": 5})
            assert r.status_code == 200
            assert r.json()["count"] >= 1
    @pytest.mark.anyio
    async def test_start_task(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        app.state.storage.create_subscription(name="task-sub", url=SAFE_URL, enabled=True)
        def fake_collect(**kw):
            return CollectReport(total_sources=1, total_parsed=1, total_inserted=0,
                                 by_source=[SourceCollectReport(source="test", parsed=1, inserted=0)])
        app.state.collector.collect_from_subscription = fake_collect
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/tasks/subscriptions-refresh/start", params={"timeout_sec": 5})
            assert r.status_code == 200
            assert "task_id" in r.json()

class TestDeleteSubscription404:
    @pytest.mark.anyio
    async def test_delete_nonexistent(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.delete("/api/subscriptions/99999")).status_code == 404

class TestDeleteUnavailable:
    @pytest.mark.anyio
    async def test_delete_unavailable(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/subscriptions/delete-unavailable", params={"include_disabled": True})
            assert r.status_code == 200
            assert "deleted" in r.json()
