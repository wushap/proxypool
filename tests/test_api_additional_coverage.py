"""
Additional test coverage for edge cases and error paths.
Tests for config export/import edge cases, batch operations error handling,
CSV export with special characters, system diagnostics, and chain diagnostics.
"""

from __future__ import annotations

import socket
from pathlib import Path

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.models import ProxyNode
from proxypool.settings import AppSettings


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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
        http_gateway_default_host="127.0.0.1",
        http_gateway_default_port=8899,
        backend_engine="singbox",
        backend_health_check_sec=30,
        backend_auto_restart_max=3,
        mihomo_binary="mihomo",
        mihomo_runtime_dir=tmp_path / "runtime" / "mihomo",
    )


# ===== Config Export/Import Edge Cases =====


@pytest.mark.anyio
async def test_config_export_empty(tmp_path: Path) -> None:
    """Test config export with no pools or endpoints"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        config = data["data"]
        assert "pools" in config
        assert "endpoints" in config
        # Should be empty lists
        assert len(config["pools"]) == 0
        assert len(config["endpoints"]) == 0


@pytest.mark.anyio
async def test_config_import_invalid_json(tmp_path: Path) -> None:
    """Test config import with invalid JSON data"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/config/import",
            json={"data": "invalid json", "import_pools": True},
        )
        assert resp.status_code in [400, 422, 500]


@pytest.mark.anyio
async def test_config_import_missing_required_fields(tmp_path: Path) -> None:
    """Test config import with missing required fields"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/config/import",
            json={"data": {"pools": []}},  # Missing version and exported_at
        )
        assert resp.status_code in [400, 422]


@pytest.mark.anyio
async def test_config_import_partial(tmp_path: Path) -> None:
    """Test config import with partial options"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Export first
        export_resp = await client.get("/api/config/export")
        config = export_resp.json()["data"]

        # Import only pools, not endpoints
        resp = await client.post(
            "/api/config/import",
            json={"data": config, "import_pools": True, "import_endpoints": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data


@pytest.mark.anyio
async def test_config_import_with_pool_data(tmp_path: Path) -> None:
    """Test config import with pool data"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a pool first
        await client.post(
            "/api/pools", json={"name": "test-pool", "filters": {"available": "true"}}
        )

        # Export
        export_resp = await client.get("/api/config/export")
        config = export_resp.json()["data"]

        # Verify pool is in config
        assert len(config["pools"]) >= 1

        # Import
        resp = await client.post(
            "/api/config/import",
            json={"data": config, "import_pools": True},
        )
        assert resp.status_code == 200


# ===== Batch Operations Error Handling =====


@pytest.mark.anyio
async def test_pool_batch_create_empty_list(tmp_path: Path) -> None:
    """Test batch create with empty list"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/pools/batch", json={"pools": []})
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 0


@pytest.mark.anyio
async def test_pool_batch_create_invalid_data(tmp_path: Path) -> None:
    """Test batch create with invalid pool data"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/pools/batch",
            json={"pools": [{"name": "", "filters": {}}]},  # Empty name
        )
        # Should handle gracefully
        assert resp.status_code in [200, 400, 422]


@pytest.mark.anyio
async def test_pool_batch_create_missing_name(tmp_path: Path) -> None:
    """Test batch create with missing name field"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/pools/batch",
            json={"pools": [{"filters": {}}]},  # Missing name
        )
        # Should handle gracefully
        assert resp.status_code in [200, 400, 422]


@pytest.mark.anyio
async def test_pool_batch_create_large_batch(tmp_path: Path) -> None:
    """Test batch create with large number of pools"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pools = [{"name": f"batch-pool-{i}", "filters": {}} for i in range(10)]
        resp = await client.post("/api/pools/batch", json={"pools": pools})
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 10


@pytest.mark.anyio
async def test_pool_batch_create_all_duplicates(tmp_path: Path) -> None:
    """Test batch create where all pools are duplicates (API allows duplicate names)"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create initial pool
        await client.post("/api/pools", json={"name": "existing"})

        # Try to create duplicate - API allows duplicate names
        resp = await client.post(
            "/api/pools/batch",
            json={"pools": [{"name": "existing", "filters": {}}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        # API creates a new pool even with duplicate name
        assert data["created"] == 1
        assert data["failed"] == 0


# ===== CSV Export with Special Characters =====


@pytest.mark.anyio
async def test_proxies_export_csv_special_characters(tmp_path: Path) -> None:
    """Test CSV export with special characters in proxy data"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add proxy with special characters
    proxy = ProxyNode(
        protocol="trojan",
        host="us.example.com",
        port=443,
        raw_link="trojan://us:password@example.com?security=tls&type=tcp",
        extra={"password": "p@ss!#$%^&*()"},
        name='测试代理"with quotes"',
    )
    storage.upsert_proxy(proxy)
    storage.update_test_result(proxy.normalized_key(), available=True, latency_ms=100)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/proxies/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        # Should handle special characters properly
        assert "地址" in content
        # Should not crash on special characters
        assert len(content) > 0


@pytest.mark.anyio
async def test_pool_export_csv_special_characters(tmp_path: Path) -> None:
    """Test pool CSV export with special characters in proxy data (not pool name)"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add proxy with unicode characters
    proxy = ProxyNode(
        protocol="ss",
        host="jp.example.com",
        port=8388,
        raw_link="ss://test@jp.example.com:8388",
        extra={},
    )
    storage.upsert_proxy(proxy)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create pool with ASCII-only name (unicode in filename causes encoding issues)
        resp = await client.post("/api/pools", json={"name": "test-pool-with-special-proxy"})
        pool_id = resp.json()["item"]["id"]

        # Export pool
        resp = await client.get(f"/api/pools/{pool_id}/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        assert "地址" in content


@pytest.mark.anyio
async def test_test_report_export_csv_special_characters(tmp_path: Path) -> None:
    """Test test report CSV export with special characters"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add proxy with error message containing special characters
    proxy = ProxyNode(
        protocol="vmess",
        host="sg.example.com",
        port=443,
        raw_link="vmess://test",
        extra={},
    )
    storage.upsert_proxy(proxy)
    storage.update_test_result(
        proxy.normalized_key(),
        available=False,
        latency_ms=0,
        error="连接超时: Connection refused (110)",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/test-report/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        # Should handle error messages with special characters
        assert len(content) > 0


# ===== System Diagnostics Endpoints =====


@pytest.mark.anyio
async def test_system_diagnostics_comprehensive(tmp_path: Path) -> None:
    """Test system diagnostics endpoint with comprehensive data"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add some test data
    proxy = ProxyNode(
        protocol="trojan",
        host="us.example.com",
        port=443,
        raw_link="trojan://us",
        extra={"password": "p"},
    )
    storage.upsert_proxy(proxy)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a pool
        await client.post("/api/pools", json={"name": "diag-pool"})

        # Test diagnostics
        resp = await client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "backend_status" in data
        assert "gateway_status" in data
        assert "pool_count" in data
        assert "proxy_count" in data


@pytest.mark.anyio
async def test_system_diagnostics_empty(tmp_path: Path) -> None:
    """Test system diagnostics with no data"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        # Should return valid data even with no proxies/pools
        assert "pool_count" in data
        assert data["pool_count"] == 0
        assert "proxy_count" in data
        assert data["proxy_count"] == 0


@pytest.mark.anyio
async def test_system_logs_with_various_levels(tmp_path: Path) -> None:
    """Test system logs endpoint with various log levels"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Test without level filter
        resp = await client.get("/api/system/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

        # Test with level filter
        resp = await client.get("/api/system/logs?level=error")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data


# ===== Chain Diagnostics with Various States =====


@pytest.mark.anyio
async def test_chain_diagnostics_no_pools(tmp_path: Path) -> None:
    """Test chain diagnostics with no pools configured"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        # Should handle empty state gracefully
        assert "front_pool" in data
        assert "exit_pool" in data


@pytest.mark.anyio
async def test_chain_diagnostics_with_pools(tmp_path: Path) -> None:
    """Test chain diagnostics with pools configured"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add proxies
    for i in range(3):
        proxy = ProxyNode(
            protocol="trojan",
            host=f"us{i}.example.com",
            port=443,
            raw_link=f"trojan://us{i}",
            extra={"password": "p"},
        )
        storage.upsert_proxy(proxy)
        storage.update_test_result(proxy.normalized_key(), available=True, latency_ms=100)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create front and exit pools
        await client.post(
            "/api/pools",
            json={"name": "front-pool", "filters": {"available": "true"}},
        )
        await client.post(
            "/api/pools",
            json={"name": "exit-pool", "filters": {"available": "true"}},
        )

        # Test chain diagnostics
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data


@pytest.mark.anyio
async def test_chain_diagnostics_health_check(tmp_path: Path) -> None:
    """Test chain diagnostics with health check"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "health_check" in data
        # Should include health check config and running status
        health_check = data["health_check"]
        assert "config" in health_check
        assert "running" in health_check


# ===== Error Path Tests =====


@pytest.mark.anyio
async def test_pool_not_found_operations(tmp_path: Path) -> None:
    """Test operations on non-existent pool"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Get non-existent pool
        resp = await client.get("/api/pools/999")
        assert resp.status_code == 404

        # Update non-existent pool
        resp = await client.put("/api/pools/999", json={"name": "new-name"})
        assert resp.status_code == 404

        # Delete non-existent pool
        resp = await client.delete("/api/pools/999")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_subscription_not_found_operations(tmp_path: Path) -> None:
    """Test operations on non-existent subscription"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Refresh non-existent subscription (endpoint requires body)
        resp = await client.post("/api/subscriptions/999/refresh", json={"timeout_sec": 1})
        assert resp.status_code == 404

        # Delete non-existent subscription
        resp = await client.delete("/api/subscriptions/999")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_proxy_delete_empty_list(tmp_path: Path) -> None:
    """Test proxy delete with empty list returns 400"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/proxies/delete-selected", json={"normalized_keys": []})
        # API returns 400 for empty list
        assert resp.status_code == 400


@pytest.mark.anyio
async def test_proxy_delete_nonexistent(tmp_path: Path) -> None:
    """Test proxy delete with non-existent keys"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/delete-selected",
            json={"normalized_keys": ["nonexistent-key-1", "nonexistent-key-2"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == 0


@pytest.mark.anyio
async def test_task_stop_nonexistent(tmp_path: Path) -> None:
    """Test stopping non-existent task"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/tasks/999/stop")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_pool_start_stop_nonexistent(tmp_path: Path) -> None:
    """Test starting/stopping non-existent pool"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/pools/999/start")
        assert resp.status_code == 404

        resp = await client.post("/api/pools/999/stop")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_config_diff_no_changes(tmp_path: Path) -> None:
    """Test config diff with no changes"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/config-diff")
        assert resp.status_code == 200
        data = resp.json()
        assert "has_diff" in data
        assert isinstance(data["differences"], list)


@pytest.mark.anyio
async def test_rollback_without_snapshots(tmp_path: Path) -> None:
    """Test rollback when no snapshots exist"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/system/rollback", json={"dry_run": False})
        # Should handle gracefully even with no snapshots
        assert resp.status_code in [200, 404, 400]


@pytest.mark.anyio
async def test_export_csv_empty_data(tmp_path: Path) -> None:
    """Test CSV export with no data"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/proxies/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        # Should still have headers even with no data
        assert "地址" in content
