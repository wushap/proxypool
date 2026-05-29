"""Tests for settings router: export, import, and rollback endpoints.

Targets the untested branches in proxypool/api/routers/settings.py:
- export_config with pools, endpoints (with hops), and subscriptions
- import_config with endpoints, subscriptions, overwrite, gateway sync, exception
- rollback_config with actual rollback, gateway sync failure, exception
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

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


def _import_payload(**overrides) -> dict:
    base = {
        "data": {
            "version": "1.0",
            "exported_at": "2026-01-01T00:00:00Z",
            "settings": {},
            "pools": [],
            "endpoints": [],
            "subscriptions": [],
            "gateway_config": {},
            "chain_config": {},
        },
    }
    base.update(overrides)
    return base


# ---- GET /api/config/export with data ----


@pytest.mark.anyio
async def test_export_config_with_pools(tmp_path: Path) -> None:
    """Export includes pools when they exist in storage."""
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage
    storage.create_proxy_pool(
        name="export-pool",
        filters={"protocol": "http"},
        listen="0.0.0.0",
        inbound_type="http",
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config/export")

    assert resp.status_code == 200
    pools = resp.json()["data"]["pools"]
    assert len(pools) == 1
    assert pools[0]["name"] == "export-pool"
    assert pools[0]["filters"] == {"protocol": "http"}


@pytest.mark.anyio
async def test_export_config_with_endpoints(tmp_path: Path) -> None:
    """Export includes endpoints when they exist (without hops to avoid unrelated bug)."""
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage

    ep = storage.create_http_proxy_endpoint(
        name="test-ep",
        listen_host="127.0.0.1",
        listen_port=9999,
        inbound_type="http",
        enabled=True,
        sticky_ttl_sec=3600,
        session_missing_action="RANDOM",
        session_header_names=["X-Session"],
        session_query_param_names=["sid"],
        connect_session_header_names=["X-Connect"],
    )

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config/export")

    assert resp.status_code == 200
    endpoints = resp.json()["data"]["endpoints"]
    assert len(endpoints) == 1
    ep_data = endpoints[0]
    assert ep_data["name"] == "test-ep"
    assert ep_data["listen_port"] == 9999
    assert ep_data["hop_pool_ids"] == []
    assert ep_data["session_header_names"] == ["X-Session"]
    assert ep_data["session_query_param_names"] == ["sid"]
    assert ep_data["connect_session_header_names"] == ["X-Connect"]


@pytest.mark.anyio
async def test_export_config_with_subscriptions(tmp_path: Path) -> None:
    """Export includes subscriptions when they exist."""
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage
    storage.create_subscription(
        name="sub-1",
        url="https://example.com/sub1",
        enabled=True,
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config/export")

    assert resp.status_code == 200
    subs = resp.json()["data"]["subscriptions"]
    assert len(subs) == 1
    assert subs[0]["name"] == "sub-1"
    assert subs[0]["url"] == "https://example.com/sub1"
    assert subs[0]["enabled"] is True


# ---- POST /api/config/import with endpoints and subscriptions ----


@pytest.mark.anyio
async def test_import_config_creates_endpoints(tmp_path: Path) -> None:
    """Import creates HTTP proxy endpoints from config data."""
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    payload = _import_payload(
        import_endpoints=True,
        data={
            "version": "1.0",
            "exported_at": "2026-01-01T00:00:00Z",
            "settings": {},
            "pools": [],
            "endpoints": [
                {
                    "name": "imported-ep",
                    "listen_host": "127.0.0.1",
                    "listen_port": 7788,
                    "inbound_type": "http",
                    "enabled": True,
                    "sticky_ttl_sec": 1800,
                    "session_missing_action": "REJECT",
                    "session_header_names": ["X-Test"],
                    "session_query_param_names": [],
                    "connect_session_header_names": [],
                    "hop_pool_ids": [],
                },
            ],
            "subscriptions": [],
            "gateway_config": {},
            "chain_config": {},
        },
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/config/import", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["imported_items"]["endpoints"] == 1

    # Verify endpoint was created
    storage = app.state.storage
    endpoints = storage.list_http_proxy_endpoints()
    assert any(e.get("name") == "imported-ep" for e in endpoints)


@pytest.mark.anyio
async def test_import_config_skips_existing_endpoint_without_overwrite(tmp_path: Path) -> None:
    """Import skips endpoints that already exist when overwrite_existing=False."""
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage
    storage.create_http_proxy_endpoint(
        name="dup-ep",
        listen_host="127.0.0.1",
        listen_port=5555,
        inbound_type="http",
        enabled=True,
        sticky_ttl_sec=3600,
        session_missing_action="RANDOM",
        session_header_names=[],
        session_query_param_names=[],
        connect_session_header_names=[],
    )
    transport = httpx.ASGITransport(app=app)

    payload = _import_payload(
        import_endpoints=True,
        overwrite_existing=False,
        data={
            "version": "1.0",
            "exported_at": "2026-01-01T00:00:00Z",
            "settings": {},
            "pools": [],
            "endpoints": [
                {
                    "name": "dup-ep",
                    "listen_host": "127.0.0.1",
                    "listen_port": 6666,
                    "inbound_type": "http",
                    "enabled": True,
                    "sticky_ttl_sec": 3600,
                    "session_missing_action": "RANDOM",
                    "session_header_names": [],
                    "session_query_param_names": [],
                    "connect_session_header_names": [],
                },
            ],
            "subscriptions": [],
            "gateway_config": {},
            "chain_config": {},
        },
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/config/import", json=payload)

    body = resp.json()
    assert body["imported_items"]["endpoints"] == 0
    assert any("已存在" in w for w in body["warnings"])


@pytest.mark.anyio
async def test_import_config_creates_subscriptions(tmp_path: Path) -> None:
    """Import creates subscriptions from config data."""
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    payload = _import_payload(
        import_subscriptions=True,
        data={
            "version": "1.0",
            "exported_at": "2026-01-01T00:00:00Z",
            "settings": {},
            "pools": [],
            "endpoints": [],
            "subscriptions": [
                {"name": "imported-sub", "url": "https://example.com/sub", "enabled": True},
            ],
            "gateway_config": {},
            "chain_config": {},
        },
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/config/import", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["imported_items"]["subscriptions"] == 1

    # Verify subscription was created
    storage = app.state.storage
    subs = storage.list_subscriptions()
    assert any(s.get("name") == "imported-sub" for s in subs)


@pytest.mark.anyio
async def test_import_config_skips_existing_subscription_without_overwrite(tmp_path: Path) -> None:
    """Import skips subscriptions that already exist when overwrite_existing=False."""
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage
    storage.create_subscription(
        name="existing-sub",
        url="https://example.com/existing",
        enabled=True,
    )
    transport = httpx.ASGITransport(app=app)

    payload = _import_payload(
        import_subscriptions=True,
        overwrite_existing=False,
        data={
            "version": "1.0",
            "exported_at": "2026-01-01T00:00:00Z",
            "settings": {},
            "pools": [],
            "endpoints": [],
            "subscriptions": [
                {"name": "existing-sub", "url": "https://example.com/existing", "enabled": True},
            ],
            "gateway_config": {},
            "chain_config": {},
        },
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/config/import", json=payload)

    body = resp.json()
    assert body["imported_items"]["subscriptions"] == 0
    assert any("已存在" in w for w in body["warnings"])


@pytest.mark.anyio
async def test_import_config_endpoint_with_hops(tmp_path: Path) -> None:
    """Import creates endpoint and sets hop_pool_ids."""
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage

    # Create a pool first so hops can reference it
    pool = storage.create_proxy_pool(
        name="hop-target",
        filters={},
        listen="0.0.0.0",
        inbound_type="http",
    )
    pool_id = int(pool["id"])

    transport = httpx.ASGITransport(app=app)

    payload = _import_payload(
        import_endpoints=True,
        data={
            "version": "1.0",
            "exported_at": "2026-01-01T00:00:00Z",
            "settings": {},
            "pools": [],
            "endpoints": [
                {
                    "name": "ep-with-hops",
                    "listen_host": "127.0.0.1",
                    "listen_port": 7799,
                    "inbound_type": "http",
                    "enabled": True,
                    "sticky_ttl_sec": 3600,
                    "session_missing_action": "RANDOM",
                    "session_header_names": [],
                    "session_query_param_names": [],
                    "connect_session_header_names": [],
                    "hop_pool_ids": [pool_id],
                },
            ],
            "subscriptions": [],
            "gateway_config": {},
            "chain_config": {},
        },
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/config/import", json=payload)

    body = resp.json()
    assert body["success"] is True
    assert body["imported_items"]["endpoints"] == 1

    # Verify hops were set
    endpoints = storage.list_http_proxy_endpoints()
    ep = next(e for e in endpoints if e.get("name") == "ep-with-hops")
    ep_id = int(ep["id"])
    hops = storage.list_http_proxy_endpoint_hops(ep_id)
    assert len(hops) == 1
    assert int(hops[0]["pool_id"]) == pool_id


@pytest.mark.anyio
async def test_import_config_gateway_sync(tmp_path: Path) -> None:
    """Import syncs gateway when it is enabled."""
    app = create_app(_make_settings(tmp_path))

    # Enable gateway
    app.state.gateway_config_service.update_config(enabled=True)

    mock_sync = AsyncMock()
    app.state.gateway_runtime.sync = mock_sync

    transport = httpx.ASGITransport(app=app)

    payload = _import_payload(data={
        "version": "1.0",
        "exported_at": "2026-01-01T00:00:00Z",
        "settings": {},
        "pools": [],
        "endpoints": [],
        "subscriptions": [],
        "gateway_config": {},
        "chain_config": {},
    })

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/config/import", json=payload)

    assert resp.status_code == 200
    mock_sync.assert_called_once()


@pytest.mark.anyio
async def test_import_config_gateway_sync_failure_adds_warning(tmp_path: Path) -> None:
    """Import adds a warning when gateway sync fails."""
    app = create_app(_make_settings(tmp_path))
    app.state.gateway_config_service.update_config(enabled=True)
    app.state.gateway_runtime.sync = AsyncMock(side_effect=RuntimeError("sync failed"))

    transport = httpx.ASGITransport(app=app)

    payload = _import_payload(data={
        "version": "1.0",
        "exported_at": "2026-01-01T00:00:00Z",
        "settings": {},
        "pools": [],
        "endpoints": [],
        "subscriptions": [],
        "gateway_config": {},
        "chain_config": {},
    })

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/config/import", json=payload)

    body = resp.json()
    assert body["success"] is True
    assert any("同步网关失败" in w for w in body["warnings"])


@pytest.mark.anyio
async def test_import_config_settings_import_warning(tmp_path: Path) -> None:
    """Import with import_settings=True records a settings warning."""
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    payload = _import_payload(
        import_settings=True,
        data={
            "version": "1.0",
            "exported_at": "2026-01-01T00:00:00Z",
            "settings": {"test_url": "https://example.com"},
            "pools": [],
            "endpoints": [],
            "subscriptions": [],
            "gateway_config": {},
            "chain_config": {},
        },
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/config/import", json=payload)

    body = resp.json()
    assert body["success"] is True
    assert body["imported_items"]["settings"] == 1
    assert any("设置导入" in w for w in body["warnings"])


# ---- POST /api/system/rollback ----


@pytest.mark.anyio
async def test_rollback_dry_run(tmp_path: Path) -> None:
    """Dry-run rollback returns success without making changes."""
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/system/rollback",
            json={"dry_run": True},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["rolled_back_items"] == 0
    assert "试运行" in body["message"]


@pytest.mark.anyio
async def test_rollback_with_config_events(tmp_path: Path) -> None:
    """Rollback succeeds when there are config events and records a rollback event."""
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage

    # Seed a config event so rollback finds something
    storage.record_backend_process_event(
        backend="singbox",
        action="config",
        pid=1234,
        result="success",
        detail="test config",
    )

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/system/rollback",
            json={"target_version": "v1.0"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["rolled_back_items"] == 1
    assert body["previous_version"] == "v1.0"


@pytest.mark.anyio
async def test_rollback_without_config_events(tmp_path: Path) -> None:
    """Rollback succeeds but rolls back 0 items when no config events exist."""
    app = create_app(_make_settings(tmp_path))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/system/rollback",
            json={},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["rolled_back_items"] == 0


@pytest.mark.anyio
async def test_rollback_gateway_sync_failure(tmp_path: Path) -> None:
    """Rollback returns failure message when gateway sync fails."""
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage
    app.state.gateway_config_service.update_config(enabled=True)
    app.state.gateway_runtime.sync = AsyncMock(side_effect=RuntimeError("gateway down"))

    storage.record_backend_process_event(
        backend="singbox",
        action="config",
        pid=1234,
        result="success",
        detail="test",
    )

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/system/rollback",
            json={},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "网关同步失败" in body["message"]


@pytest.mark.anyio
async def test_rollback_exception_returns_500(tmp_path: Path) -> None:
    """Rollback returns 500 when an unexpected exception occurs."""
    app = create_app(_make_settings(tmp_path))
    storage = app.state.storage
    storage.record_backend_process_event(
        backend="singbox",
        action="config",
        pid=1234,
        result="success",
        detail="test",
    )

    # Patch list_backend_process_events to raise
    original = storage.list_backend_process_events

    def _boom(**kwargs):
        raise RuntimeError("storage failure")

    storage.list_backend_process_events = _boom

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/system/rollback",
            json={},
        )

    assert resp.status_code == 500
    assert "回滚失败" in resp.json()["detail"]

    # Restore
    storage.list_backend_process_events = original
