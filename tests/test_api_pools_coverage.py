"""
Tests for pools router endpoints to improve coverage.

Covers: GET/POST /pools, GET/PUT/DELETE /pools/{id},
POST /pools/{id}/sync, /start, /stop, /preview-config, /validate,
GET /pools/{id}/health-summary, /metrics.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


def _make_settings(tmp_path_factory) -> AppSettings:
    from pathlib import Path

    tmp = tmp_path_factory.mktemp("test_pools_coverage")
    return AppSettings(
        project_root=tmp,
        db_path=tmp / "test.db",
        output_dir=tmp / "output",
        sources_file=tmp / "sources.txt",
        singbox_routes_file=tmp / "routes.json",
        singbox_runtime_config_file=tmp / "runtime.json",
        singbox_runtime_log_file=tmp / "runtime.log",
        singbox_binary="sing-box",
        test_url="https://httpbin.org/get",
        api_key="",
        backend_engine="singbox",
        backend_health_check_sec=60,
        backend_auto_restart_max=3,
    )


def _mock_pool_service():
    svc = MagicMock()
    svc.list_pools.return_value = [
        {
            "id": 1,
            "name": "test-pool",
            "filters": {"protocol": "http"},
            "listen": "0.0.0.0:8080",
            "inbound_type": "http",
        }
    ]
    svc.get_pool.return_value = {
        "id": 1,
        "name": "test-pool",
        "filters": {"protocol": "http"},
        "listen": "0.0.0.0:8080",
        "inbound_type": "http",
    }
    svc.create_pool.return_value = {
        "id": 2,
        "name": "new-pool",
        "filters": {},
        "listen": "0.0.0.0",
        "inbound_type": "http",
    }
    svc.update_pool.return_value = {
        "id": 1,
        "name": "updated-pool",
        "filters": {"protocol": "socks5"},
        "listen": "0.0.0.0:9090",
        "inbound_type": "socks5",
    }
    svc.delete_pool.return_value = True
    svc.sync_pool.return_value = {
        "id": 1,
        "name": "test-pool",
        "status": "synced",
    }
    svc.start_pool.return_value = {
        "id": 1,
        "name": "test-pool",
        "status": "running",
    }
    svc.stop_pool.return_value = {
        "id": 1,
        "name": "test-pool",
        "status": "stopped",
    }
    return svc


def _mock_storage():
    storage = MagicMock()
    storage.list_http_proxy_endpoints.return_value = []
    storage.list_proxy_pool_candidates.return_value = [
        {
            "normalized_key": "key1",
            "name": "node1",
            "protocol": "http",
            "host": "1.2.3.4",
            "port": 8080,
            "available": True,
            "failure_count": 0,
            "latency_ms": 50,
            "speed_mbps": 10.0,
            "country": "US",
            "city": "NYC",
            "last_checked": "2026-05-29T10:00:00Z",
            "openai_unlocked": True,
        },
        {
            "normalized_key": "key2",
            "name": "node2",
            "protocol": "socks5",
            "host": "5.6.7.8",
            "port": 1080,
            "available": False,
            "failure_count": 3,
            "latency_ms": None,
            "speed_mbps": None,
            "country": "CN",
            "city": "Beijing",
            "last_checked": "2026-05-29T09:00:00Z",
            "openai_unlocked": False,
        },
    ]
    storage.get_proxy_pool.return_value = {
        "id": 1,
        "name": "test-pool",
    }
    storage.get_proxy_pool_stats.return_value = {
        "total": 50,
        "healthy": 42,
        "active": 30,
    }
    return storage


# ===== GET /api/pools =====


@pytest.mark.anyio
async def test_list_pools(tmp_path_factory):
    """GET /api/pools returns pool list from service."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "test-pool"


# ===== POST /api/pools =====


@pytest.mark.anyio
async def test_create_pool(tmp_path_factory):
    """POST /api/pools creates a pool."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/pools",
            json={
                "name": "new-pool",
                "filters": {},
                "listen": "0.0.0.0",
                "inbound_type": "http",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        assert data["item"]["name"] == "new-pool"


@pytest.mark.anyio
async def test_create_pool_duplicate_name(tmp_path_factory):
    """POST /api/pools with duplicate name returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.create_pool.side_effect = Exception("name already exist in database")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/pools",
            json={"name": "dup", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
        )
        assert resp.status_code == 400
        assert "已存在" in resp.json()["detail"]


@pytest.mark.anyio
async def test_create_pool_empty_name(tmp_path_factory):
    """POST /api/pools with name-empty error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.create_pool.side_effect = Exception("name is empty or required")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/pools",
            json={"name": "x", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
        )
        assert resp.status_code == 400
        assert "不能为空" in resp.json()["detail"]


@pytest.mark.anyio
async def test_create_pool_filter_error(tmp_path_factory):
    """POST /api/pools with filter error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.create_pool.side_effect = Exception("invalid filter format")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/pools",
            json={"name": "x", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
        )
        assert resp.status_code == 400
        assert "筛选条件" in resp.json()["detail"]


@pytest.mark.anyio
async def test_create_pool_inbound_error(tmp_path_factory):
    """POST /api/pools with inbound error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.create_pool.side_effect = Exception("inbound type invalid")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/pools",
            json={"name": "x", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
        )
        assert resp.status_code == 400
        assert "入站类型" in resp.json()["detail"]


@pytest.mark.anyio
async def test_create_pool_generic_error(tmp_path_factory):
    """POST /api/pools with generic error returns 400 with raw message."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.create_pool.side_effect = RuntimeError("something broke")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/pools",
            json={"name": "x", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
        )
        assert resp.status_code == 400
        assert "something broke" in resp.json()["detail"]


# ===== POST /api/pools/batch =====


@pytest.mark.anyio
async def test_batch_create_pools(tmp_path_factory):
    """POST /api/pools/batch creates multiple pools."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/pools/batch",
            json={
                "pools": [
                    {"name": "pool-a", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
                    {"name": "pool-b", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
                ],
                "stop_on_error": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2
        assert data["failed"] == 0


@pytest.mark.anyio
async def test_batch_create_pools_stop_on_error(tmp_path_factory):
    """POST /api/pools/batch with stop_on_error stops on first failure."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    call_count = 0

    def _create_side_effect(name, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("second pool failed")
        return {"id": call_count, "name": name, "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"}

    svc.create_pool.side_effect = _create_side_effect
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/pools/batch",
            json={
                "pools": [
                    {"name": "pool-a", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
                    {"name": "pool-b", "filters": {}, "listen": "0.0.0.0", "inbound_type": "http"},
                ],
                "stop_on_error": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["failed"] == 1


# ===== GET /api/pools/{id} =====


@pytest.mark.anyio
async def test_get_pool(tmp_path_factory):
    """GET /api/pools/1 returns pool details."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1")
        assert resp.status_code == 200
        assert resp.json()["item"]["name"] == "test-pool"


@pytest.mark.anyio
async def test_get_pool_not_found(tmp_path_factory):
    """GET /api/pools/999 returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/999")
        assert resp.status_code == 404


# ===== PUT /api/pools/{id} =====


@pytest.mark.anyio
async def test_update_pool(tmp_path_factory):
    """PUT /api/pools/1 updates pool."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put(
            "/api/pools/1",
            json={"name": "updated-pool"},
        )
        assert resp.status_code == 200
        assert resp.json()["item"]["name"] == "updated-pool"


@pytest.mark.anyio
async def test_update_pool_not_found(tmp_path_factory):
    """PUT /api/pools/999 returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put("/api/pools/999", json={"name": "x"})
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_update_pool_name_conflict(tmp_path_factory):
    """PUT /api/pools/1 with duplicate name returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.update_pool.side_effect = Exception("name already exist in another pool")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put("/api/pools/1", json={"name": "dup"})
        assert resp.status_code == 400
        assert "已被其他池使用" in resp.json()["detail"]


@pytest.mark.anyio
async def test_update_pool_not_found_error(tmp_path_factory):
    """PUT /api/pools/1 with not-found error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = {"id": 1, "name": "x"}  # exists for initial check
    svc.update_pool.side_effect = Exception("pool not found")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put("/api/pools/1", json={"name": "x"})
        assert resp.status_code == 400
        assert "不存在" in resp.json()["detail"]


# ===== DELETE /api/pools/{id} =====


@pytest.mark.anyio
async def test_delete_pool(tmp_path_factory):
    """DELETE /api/pools/1 deletes pool."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete("/api/pools/1")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


@pytest.mark.anyio
async def test_delete_pool_not_found(tmp_path_factory):
    """DELETE /api/pools/999 returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete("/api/pools/999")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_pool_in_use(tmp_path_factory):
    """DELETE /api/pools/1 returns 409 when pool is used by an endpoint."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_http_proxy_endpoints.return_value = [
        {"id": 10, "name": "my-endpoint", "listen_host": "0.0.0.0", "listen_port": 8899}
    ]
    storage.get_http_proxy_endpoint_hops.return_value = [{"pool_id": 1}]
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete("/api/pools/1")
        assert resp.status_code == 409
        assert "依赖" in resp.json()["detail"]


# ===== POST /api/pools/{id}/sync =====


@pytest.mark.anyio
async def test_sync_pool(tmp_path_factory):
    """POST /api/pools/1/sync syncs pool."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/sync")
        assert resp.status_code == 200
        assert resp.json()["item"]["status"] == "synced"


@pytest.mark.anyio
async def test_sync_pool_not_found(tmp_path_factory):
    """POST /api/pools/999/sync returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/999/sync")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_sync_pool_timeout(tmp_path_factory):
    """POST /api/pools/1/sync with timeout error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.sync_pool.side_effect = Exception("request timeout")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/sync")
        assert resp.status_code == 400
        assert "超时" in resp.json()["detail"]


@pytest.mark.anyio
async def test_sync_pool_connect_error(tmp_path_factory):
    """POST /api/pools/1/sync with connect error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.sync_pool.side_effect = Exception("connection refused")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/sync")
        assert resp.status_code == 400
        assert "连接" in resp.json()["detail"]


# ===== POST /api/pools/{id}/start =====


@pytest.mark.anyio
async def test_start_pool(tmp_path_factory):
    """POST /api/pools/1/start starts pool."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/start")
        assert resp.status_code == 200
        assert resp.json()["item"]["status"] == "running"


@pytest.mark.anyio
async def test_start_pool_not_found(tmp_path_factory):
    """POST /api/pools/999/start returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/999/start")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_start_pool_port_error(tmp_path_factory):
    """POST /api/pools/1/start with port error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.start_pool.side_effect = Exception("port already in use")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/start")
        assert resp.status_code == 400
        assert "端口" in resp.json()["detail"]


@pytest.mark.anyio
async def test_start_pool_already_running(tmp_path_factory):
    """POST /api/pools/1/start with already-running error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.start_pool.side_effect = Exception("already running")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/start")
        assert resp.status_code == 400
        assert "已经在运行中" in resp.json()["detail"]


@pytest.mark.anyio
async def test_start_pool_backend_error(tmp_path_factory):
    """POST /api/pools/1/start with backend error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.start_pool.side_effect = Exception("backend service not available")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/start")
        assert resp.status_code == 400
        assert "后端服务" in resp.json()["detail"]


@pytest.mark.anyio
async def test_start_pool_generic_error(tmp_path_factory):
    """POST /api/pools/1/start with generic error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.start_pool.side_effect = Exception("unknown failure")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/start")
        assert resp.status_code == 400
        assert "unknown failure" in resp.json()["detail"]


# ===== POST /api/pools/{id}/stop =====


@pytest.mark.anyio
async def test_stop_pool(tmp_path_factory):
    """POST /api/pools/1/stop stops pool."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/stop")
        assert resp.status_code == 200
        assert resp.json()["item"]["status"] == "stopped"


@pytest.mark.anyio
async def test_stop_pool_not_found(tmp_path_factory):
    """POST /api/pools/999/stop returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/999/stop")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_stop_pool_not_running(tmp_path_factory):
    """POST /api/pools/1/stop with not-running error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.stop_pool.side_effect = Exception("pool is not running")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/stop")
        assert resp.status_code == 400
        assert "未在运行" in resp.json()["detail"]


@pytest.mark.anyio
async def test_stop_pool_generic_error(tmp_path_factory):
    """POST /api/pools/1/stop with generic error returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.stop_pool.side_effect = Exception("kill failed")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/stop")
        assert resp.status_code == 400
        assert "kill failed" in resp.json()["detail"]


# ===== POST /api/pools/{id}/preview-config =====


@pytest.mark.anyio
async def test_preview_pool_config(tmp_path_factory):
    """POST /api/pools/1/preview-config returns config preview."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/preview-config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pool_id"] == 1
        assert data["candidate_count"] == 2


@pytest.mark.anyio
async def test_preview_pool_config_not_found(tmp_path_factory):
    """POST /api/pools/999/preview-config returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/999/preview-config")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_preview_pool_config_no_candidates(tmp_path_factory):
    """POST /api/pools/1/preview-config with no candidates returns warning."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_proxy_pool_candidates.return_value = []
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/preview-config")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "warning" in data


@pytest.mark.anyio
async def test_preview_pool_config_storage_error(tmp_path_factory):
    """POST /api/pools/1/preview-config with storage error returns 500."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_proxy_pool_candidates.side_effect = RuntimeError("db corrupted")
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/preview-config")
        assert resp.status_code == 500


# ===== POST /api/pools/{id}/validate =====


@pytest.mark.anyio
async def test_validate_pool_config(tmp_path_factory):
    """POST /api/pools/1/validate returns validation result."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pool_id"] == 1
        assert "is_valid" in data
        assert "issues" in data
        assert "validated_at" in data


@pytest.mark.anyio
async def test_validate_pool_config_not_found(tmp_path_factory):
    """POST /api/pools/999/validate returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/999/validate")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_validate_pool_config_short_name(tmp_path_factory):
    """POST /api/pools/1/validate with short name returns warning."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = {
        "id": 1,
        "name": "x",
        "filters": {},
        "listen": "0.0.0.0",
        "inbound_type": "http",
    }
    app.state.pool_service = svc
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        warnings = [i for i in data["issues"] if i["field"] == "name"]
        assert len(warnings) >= 1


@pytest.mark.anyio
async def test_validate_pool_config_long_name(tmp_path_factory):
    """POST /api/pools/1/validate with long name returns error."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = {
        "id": 1,
        "name": "a" * 60,
        "filters": {},
        "listen": "0.0.0.0",
        "inbound_type": "http",
    }
    app.state.pool_service = svc
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        name_errors = [i for i in data["issues"] if i["field"] == "name"]
        assert len(name_errors) >= 1


@pytest.mark.anyio
async def test_validate_pool_config_empty_name(tmp_path_factory):
    """POST /api/pools/1/validate with empty name returns error."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = {
        "id": 1,
        "name": "",
        "filters": {},
        "listen": "0.0.0.0",
        "inbound_type": "http",
    }
    app.state.pool_service = svc
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False


@pytest.mark.anyio
async def test_validate_pool_config_invalid_filters(tmp_path_factory):
    """POST /api/pools/1/validate with invalid filter values returns errors."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = {
        "id": 1,
        "name": "test-pool",
        "filters": {
            "route_mode_filter": "invalid_mode",
            "openai_filter": "invalid_openai",
            "ip_purity_filter": "invalid_purity",
            "latency_min": 100,
            "latency_max": 50,
            "freshness_hours": -1,
            "geo_countries": "not_a_list",
        },
        "listen": "0.0.0.0",
        "inbound_type": "http",
    }
    app.state.pool_service = svc
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        fields = {i["field"] for i in data["issues"]}
        assert "filters.route_mode_filter" in fields
        assert "filters.openai_filter" in fields
        assert "filters.ip_purity_filter" in fields
        assert "filters.latency_range" in fields
        assert "filters.freshness_hours" in fields
        assert "filters.geo_countries" in fields


@pytest.mark.anyio
async def test_validate_pool_config_invalid_inbound(tmp_path_factory):
    """POST /api/pools/1/validate with invalid inbound_type returns error."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = {
        "id": 1,
        "name": "test-pool",
        "filters": {},
        "listen": "0.0.0.0",
        "inbound_type": "grpc",
    }
    app.state.pool_service = svc
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        inbound_issues = [i for i in data["issues"] if i["field"] == "inbound_type"]
        assert len(inbound_issues) >= 1


@pytest.mark.anyio
async def test_validate_pool_config_empty_listen(tmp_path_factory):
    """POST /api/pools/1/validate with empty listen returns warning."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = {
        "id": 1,
        "name": "test-pool",
        "filters": {},
        "listen": "",
        "inbound_type": "http",
    }
    app.state.pool_service = svc
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        listen_issues = [i for i in data["issues"] if i["field"] == "listen"]
        assert len(listen_issues) >= 1


@pytest.mark.anyio
async def test_validate_pool_config_chain_enabled_no_action(tmp_path_factory):
    """POST /api/pools/1/validate with chain enabled but no session action."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = {
        "id": 1,
        "name": "test-pool",
        "filters": {},
        "listen": "0.0.0.0",
        "inbound_type": "http",
        "chain_enabled": True,
        "chain_config": {},
    }
    app.state.pool_service = svc
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        chain_issues = [i for i in data["issues"] if "session_missing_action" in i["field"]]
        assert len(chain_issues) >= 1


@pytest.mark.anyio
async def test_validate_pool_config_no_candidates(tmp_path_factory):
    """POST /api/pools/1/validate with no candidates returns warning."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_proxy_pool_candidates.return_value = []
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        candidate_issues = [i for i in data["issues"] if i["field"] == "candidates"]
        assert len(candidate_issues) >= 1


@pytest.mark.anyio
async def test_validate_pool_config_all_unavailable(tmp_path_factory):
    """POST /api/pools/1/validate with all unavailable candidates."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_proxy_pool_candidates.return_value = [
        {"normalized_key": "k1", "available": False, "failure_count": 5},
        {"normalized_key": "k2", "available": False, "failure_count": 3},
    ]
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        candidate_issues = [i for i in data["issues"] if i["field"] == "candidates"]
        assert len(candidate_issues) >= 1
        assert "不可用" in candidate_issues[0]["message"]


@pytest.mark.anyio
async def test_validate_pool_config_few_available(tmp_path_factory):
    """POST /api/pools/1/validate with only 1 available candidate."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_proxy_pool_candidates.return_value = [
        {"normalized_key": "k1", "available": True, "failure_count": 0},
        {"normalized_key": "k2", "available": False, "failure_count": 3},
    ]
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/pools/1/validate")
        assert resp.status_code == 200
        data = resp.json()
        candidate_issues = [i for i in data["issues"] if i["field"] == "candidates"]
        assert len(candidate_issues) >= 1
        assert "较少" in candidate_issues[0]["message"]


# ===== GET /api/pools/{id}/health-summary =====


@pytest.mark.anyio
async def test_health_summary(tmp_path_factory):
    """GET /api/pools/1/health-summary returns health data."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1/health-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pool_id"] == 1
        assert data["total_nodes"] == 2
        assert data["healthy_nodes"] == 1
        assert data["unavailable_nodes"] == 1
        assert "status" in data
        assert "healthy_rate" in data


@pytest.mark.anyio
async def test_health_summary_not_found(tmp_path_factory):
    """GET /api/pools/999/health-summary returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/999/health-summary")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_health_summary_empty_pool(tmp_path_factory):
    """GET /api/pools/1/health-summary with no candidates reports 0 nodes."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_proxy_pool_candidates.return_value = []
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1/health-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_nodes"] == 0
        assert data["status"] == "unhealthy"
        assert data["healthy_rate"] == 0.0


@pytest.mark.anyio
async def test_health_summary_degraded_status(tmp_path_factory):
    """GET /api/pools/1/health-summary with 60% healthy = degraded."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_proxy_pool_candidates.return_value = [
        {"available": True, "failure_count": 0, "last_checked": "2026-05-29T10:00:00Z"},
        {"available": True, "failure_count": 0, "last_checked": "2026-05-29T10:00:00Z"},
        {"available": True, "failure_count": 0, "last_checked": "2026-05-29T10:00:00Z"},
        {"available": False, "failure_count": 5, "last_checked": "2026-05-29T09:00:00Z"},
        {"available": False, "failure_count": 3, "last_checked": "2026-05-29T09:00:00Z"},
    ]
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1/health-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_nodes"] == 5
        assert data["healthy_nodes"] == 3
        assert data["unavailable_nodes"] == 2
        assert data["status"] == "degraded"


@pytest.mark.anyio
async def test_health_summary_healthy_status(tmp_path_factory):
    """GET /api/pools/1/health-summary with 80%+ healthy = healthy."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_proxy_pool_candidates.return_value = [
        {"available": True, "failure_count": 0, "last_checked": None},
        {"available": True, "failure_count": 0, "last_checked": None},
        {"available": True, "failure_count": 0, "last_checked": None},
        {"available": True, "failure_count": 0, "last_checked": None},
        {"available": False, "failure_count": 5, "last_checked": None},
    ]
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1/health-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


@pytest.mark.anyio
async def test_health_summary_degraded_nodes(tmp_path_factory):
    """GET /api/pools/1/health-summary tracks degraded nodes (available but with failures)."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_proxy_pool_candidates.return_value = [
        {"available": True, "failure_count": 0, "last_checked": "2026-05-29T10:00:00Z"},
        {"available": True, "failure_count": 2, "last_checked": "2026-05-29T10:05:00Z"},
    ]
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1/health-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy_nodes"] == 1
        assert data["degraded_nodes"] == 1


# ===== GET /api/pools/{id}/metrics =====


@pytest.mark.anyio
async def test_get_pool_metrics(tmp_path_factory):
    """GET /api/pools/1/metrics returns pool metrics."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pool_id"] == 1
        assert data["pool_name"] == "test-pool"
        assert "requests" in data
        assert "timestamp" in data


@pytest.mark.anyio
async def test_get_pool_metrics_not_found(tmp_path_factory):
    """GET /api/pools/999/metrics returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    storage = _mock_storage()
    storage.get_proxy_pool.return_value = None
    app.state.storage = storage
    app.state.pool_service = _mock_pool_service()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/999/metrics")
        assert resp.status_code == 404


# ===== GET /api/pools/{id}/chain =====


@pytest.mark.anyio
async def test_get_pool_chain(tmp_path_factory):
    """GET /api/pools/1/chain returns chain config."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool_chain_config.return_value = {
        "chain_enabled": True,
        "session_missing_action": "RANDOM",
    }
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1/chain")
        assert resp.status_code == 200
        assert resp.json()["item"]["chain_enabled"] is True


@pytest.mark.anyio
async def test_get_pool_chain_not_found(tmp_path_factory):
    """GET /api/pools/999/chain returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool_chain_config.return_value = None
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/999/chain")
        assert resp.status_code == 404


# ===== PUT /api/pools/{id}/chain =====


@pytest.mark.anyio
async def test_update_pool_chain(tmp_path_factory):
    """PUT /api/pools/1/chain updates chain config."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.update_pool_chain_config.return_value = {
        "chain_enabled": True,
        "session_missing_action": "RANDOM",
    }
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put(
            "/api/pools/1/chain",
            json={"chain_enabled": True},
        )
        assert resp.status_code == 200
        assert resp.json()["item"]["chain_enabled"] is True


@pytest.mark.anyio
async def test_update_pool_chain_not_found(tmp_path_factory):
    """PUT /api/pools/1/chain with ValueError returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.update_pool_chain_config.side_effect = ValueError("pool not found")
    app.state.pool_service = svc

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put(
            "/api/pools/1/chain",
            json={"chain_enabled": True},
        )
        assert resp.status_code == 404


# ===== GET /api/pools/{id}/dependencies =====


@pytest.mark.anyio
async def test_get_pool_dependencies(tmp_path_factory):
    """GET /api/pools/1/dependencies returns dependency info."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    storage = _mock_storage()
    storage.list_http_proxy_endpoints.return_value = [
        {"id": 10, "name": "ep1", "listen_host": "0.0.0.0", "listen_port": 8899, "enabled": True}
    ]
    storage.get_http_proxy_endpoint_hops.return_value = [{"pool_id": 1}]
    app.state.storage = storage

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1/dependencies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pool_id"] == 1
        assert data["has_dependencies"] is True
        assert len(data["dependent_endpoints"]) == 1


@pytest.mark.anyio
async def test_get_pool_dependencies_not_found(tmp_path_factory):
    """GET /api/pools/999/dependencies returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/999/dependencies")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_pool_dependencies_no_deps(tmp_path_factory):
    """GET /api/pools/1/dependencies with no deps."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1/dependencies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_dependencies"] is False
        assert len(data["dependent_endpoints"]) == 0


# ===== GET /api/pools/{id}/export =====


@pytest.mark.anyio
async def test_export_pool_csv(tmp_path_factory):
    """GET /api/pools/1/export returns CSV."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    app.state.pool_service = _mock_pool_service()
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/1/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        assert "地址" in content
        assert "test-pool" in resp.headers.get("content-disposition", "")


@pytest.mark.anyio
async def test_export_pool_csv_not_found(tmp_path_factory):
    """GET /api/pools/999/export returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)
    svc = _mock_pool_service()
    svc.get_pool.return_value = None
    app.state.pool_service = svc
    app.state.storage = _mock_storage()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/pools/999/export")
        assert resp.status_code == 404
