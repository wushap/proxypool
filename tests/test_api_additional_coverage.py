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


# =====================================================================
# Unit tests for api/errors.py — async error handlers and edge cases
# =====================================================================


import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from proxypool.api.errors import (
    APIError,
    ConflictError,
    InternalError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    api_error_handler,
    create_error_response,
    generic_exception_handler,
    http_exception_handler,
)


def _make_request(state_correlation_id=None):
    """Build a minimal mock Request for error handler tests."""
    req = MagicMock()
    req.method = "GET"
    req.url.path = "/api/test"
    req.state = SimpleNamespace(correlation_id=state_correlation_id)
    return req


class TestErrorClasses:
    def test_api_error_attributes(self):
        err = APIError(
            status_code=418, error_code="ERR_TEAPOT", detail="I'm a teapot",
            field="body", suggestion="Use a coffee maker",
        )
        assert err.status_code == 418
        assert err.error_code == "ERR_TEAPOT"
        assert err.field == "body"
        assert err.suggestion == "Use a coffee maker"

    def test_not_found_error(self):
        err = NotFoundError("pool", 42)
        assert err.status_code == 404
        assert "42" in err.detail

    def test_validation_error(self):
        err = ValidationError("bad input", field="name")
        assert err.status_code == 422
        assert err.field == "name"

    def test_conflict_error(self):
        err = ConflictError("duplicate", field="name")
        assert err.status_code == 409
        assert err.field == "name"

    def test_rate_limit_error(self):
        err = RateLimitError(retry_after=30)
        assert err.status_code == 429
        assert err.retry_after == 30

    def test_internal_error_default(self):
        err = InternalError()
        assert err.status_code == 500


class TestCreateErrorResponse:
    def test_minimal(self):
        resp = create_error_response(400, "ERR_BAD", "oops")
        assert resp.status_code == 400
        body = resp.body
        assert b"ERR_BAD" in body

    def test_with_correlation_id(self):
        resp = create_error_response(400, "ERR_BAD", "oops", correlation_id="abc-123")
        assert b"abc-123" in resp.body

    def test_with_field_and_suggestion(self):
        resp = create_error_response(422, "ERR_V", "nope", field="x", suggestion="try y")
        body = resp.body
        assert b"field" in body
        assert b"suggestion" in body


class TestAsyncErrorHandlers:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_api_error_handler(self):
        req = _make_request(state_correlation_id="corr-1")
        exc = APIError(400, "ERR_TEST", "test detail", field="f", suggestion="s")
        resp = self._run(api_error_handler(req, exc))
        assert resp.status_code == 400
        assert b"corr-1" in resp.body

    def test_api_error_handler_no_correlation(self):
        req = _make_request(state_correlation_id=None)
        exc = APIError(400, "ERR_TEST", "detail")
        resp = self._run(api_error_handler(req, exc))
        assert resp.status_code == 400

    def test_http_exception_handler(self):
        from fastapi import HTTPException
        req = _make_request(state_correlation_id="corr-2")
        exc = HTTPException(status_code=403, detail="forbidden")
        resp = self._run(http_exception_handler(req, exc))
        assert resp.status_code == 403
        assert b"corr-2" in resp.body

    def test_generic_exception_handler(self):
        req = _make_request(state_correlation_id="corr-3")
        exc = RuntimeError("something broke")
        resp = self._run(generic_exception_handler(req, exc))
        assert resp.status_code == 500
        assert b"corr-3" in resp.body

    def test_generic_exception_handler_no_correlation(self):
        req = _make_request(state_correlation_id=None)
        exc = ValueError("oops")
        resp = self._run(generic_exception_handler(req, exc))
        assert resp.status_code == 500


# =====================================================================
# Unit tests for api/security.py — uncovered edge cases
# =====================================================================


from proxypool.api.security import (
    APIKeyManager,
    ConcurrentRequestLimiter,
    RateLimiter,
    is_api_key_required,
    normalize_path,
)


class TestRateLimiterEdgeCases:
    def test_invalid_limit_string(self):
        """Malformed limit_str falls back to 60/minute defaults (lines 147-149)."""
        limiter = RateLimiter()
        # "invalid" has no "/" so split will raise ValueError
        is_limited, remaining, retry = limiter.is_limited("k", "invalid")
        assert is_limited is False

    def test_headers_invalid_limit_string(self):
        """get_rate_limit_headers with malformed string (lines 175-176)."""
        limiter = RateLimiter()
        headers = limiter.get_rate_limit_headers("k", "bad-string", 5)
        assert headers["X-RateLimit-Limit"] == "60"

    def test_is_limited_returns_retry_after(self):
        """When limited and timestamps exist, retry_after > 0."""
        limiter = RateLimiter()
        for _ in range(3):
            limiter.is_limited("k", "2/second")
        is_limited, remaining, retry_after = limiter.is_limited("k", "2/second")
        assert is_limited is True
        assert retry_after > 0


class TestAPIKeyManagerEdgeCases:
    def test_validate_key_nonexistent(self):
        """validate_key returns False for unknown key (line 220)."""
        mgr = APIKeyManager()
        assert mgr.validate_key("does-not-exist") is False

    def test_validate_key_expired(self):
        """validate_key returns False for expired key (line 225)."""
        mgr = APIKeyManager()
        key = mgr.generate_key()
        info = mgr.register_key(key, expires_in_days=1)
        # Force expires_at to the past so the expiry check triggers
        info["expires_at"] = time.time() - 100
        assert mgr.validate_key(key) is False

    def test_rotate_key_nonexistent_old(self):
        """rotate_key when old key is not registered (lines 242-247 skipped)."""
        mgr = APIKeyManager()
        new_key, info = mgr.rotate_key("nonexistent-key")
        assert mgr.validate_key(new_key) is True

    def test_revoke_key_nonexistent(self):
        """revoke_key returns False for unknown key (line 263)."""
        mgr = APIKeyManager()
        assert mgr.revoke_key("unknown") is False

    def test_register_key_no_expiry(self):
        """register_key with expires_in_days=0 sets expires_at=0."""
        mgr = APIKeyManager()
        key = mgr.generate_key()
        info = mgr.register_key(key, expires_in_days=0)
        assert info["expires_at"] == 0


class TestNormalizePathEdgeCases:
    def test_empty_string(self):
        """Empty string normalizes to '/' (line 290)."""
        assert normalize_path("") == "/"

    def test_whitespace_only(self):
        assert normalize_path("   ") == "/"

    def test_trailing_slash(self):
        assert normalize_path("/api/proxies/") == "/api/proxies"

    def test_root_slash_preserved(self):
        assert normalize_path("/") == "/"


class TestIsApiKeyRequiredEdgeCases:
    def test_task_stop_requires_auth(self):
        """GET /api/tasks/{id}/stop should require auth (line 358)."""
        assert is_api_key_required("GET", "/api/tasks/abc-123/stop") is True

    def test_task_list_no_auth(self):
        assert is_api_key_required("GET", "/api/tasks") is False
        assert is_api_key_required("GET", "/api/tasks/abc-123") is False

    def test_unknown_endpoint_requires_auth(self):
        assert is_api_key_required("GET", "/api/unknown") is True


class TestGetClientIpNoClient:
    def test_no_client_no_headers(self):
        """When request.client is None and no forwarded headers (line 512)."""
        from proxypool.api.security import get_client_ip as _get_ip

        class MockReq:
            headers = {}
            client = None

        assert _get_ip(MockReq()) == "unknown"


class TestConcurrentLimiterReleaseAtZero:
    def test_release_at_zero_no_crash(self):
        """Release when count is 0 should not go negative (line 630)."""
        limiter = ConcurrentRequestLimiter()
        # Release without acquiring — should not crash
        limiter.release("/api/test")
        assert limiter.get_concurrent_count("/api/test") == 0


# =====================================================================
# Unit tests for api/monitoring.py — uncovered edge cases
# =====================================================================


from proxypool.api.monitoring import (
    CorrelationIdGenerator,
    ErrorAggregator,
    PerformanceMonitor,
    RequestTrace,
)

import time


class TestRequestTraceEdgeCases:
    def test_duration_ms_no_end_time(self):
        """duration_ms returns 0.0 when end_time is None (line 30)."""
        trace = RequestTrace(
            correlation_id="c1", path="/", method="GET",
            start_time=time.time(),
        )
        assert trace.end_time is None
        assert trace.duration_ms == 0.0


class TestPerformanceMonitorEdgeCases:
    def test_bottleneck_warning_severity(self):
        """Bottleneck with warning-level latency (line 197)."""
        monitor = PerformanceMonitor()
        # p95 above threshold but below 2*threshold -> warning
        for _ in range(15):
            monitor.record_request(path="/api/med", latency_ms=120.0, status_code=200)
        bottlenecks = monitor.detect_bottlenecks(threshold_ms=100.0)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].severity == "warning"

    def test_bottleneck_high_error_rate_critical(self):
        """Critical from high error rate (>0.1) with normal latency."""
        monitor = PerformanceMonitor()
        for i in range(20):
            status = 500 if i < 3 else 200  # 15% error rate -> critical
            monitor.record_request(path="/api/err", latency_ms=10.0, status_code=status)
        bottlenecks = monitor.detect_bottlenecks(threshold_ms=100.0)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].severity == "critical"

    def test_capacity_metrics_empty(self):
        """get_capacity_metrics with no data returns zeros (lines 226->225)."""
        monitor = PerformanceMonitor()
        metrics = monitor.get_capacity_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["error_rate"] == 0.0
        assert metrics["latency_stats"] == {}

    def test_bottleneck_insufficient_data_points(self):
        """No bottleneck detected with fewer than 10 data points."""
        monitor = PerformanceMonitor()
        for _ in range(5):
            monitor.record_request(path="/api/few", latency_ms=500.0, status_code=200)
        assert monitor.detect_bottlenecks(threshold_ms=100.0) == []


class TestErrorAggregatorEdgeCases:
    def test_summary_with_zero_minutes(self):
        """get_error_summary with last_minutes=0."""
        agg = ErrorAggregator()
        summary = agg.get_error_summary(last_minutes=0)
        assert summary["total_errors"] == 0
        assert summary["error_rate_per_minute"] == 0.0

    def test_error_with_correlation_id(self):
        """record_error with correlation_id."""
        agg = ErrorAggregator()
        agg.record_error(
            path="/api/test", method="POST", status_code=500,
            error_type="http_500", error_message="err",
            correlation_id="cid-1",
        )
        assert len(agg._errors) == 1
        assert agg._errors[0].correlation_id == "cid-1"


# =====================================================================
# Unit tests for api/metrics.py — uncovered edge cases
# =====================================================================


from proxypool.api.metrics import MetricsService, MetricsWindowData


class TestMetricsWindowDataProperties:
    def test_error_rate_zero_requests(self):
        """error_rate is 0.0 when total_requests=0 (lines 42-44)."""
        data = MetricsWindowData(
            window_name="test", duration_seconds=60,
            start_time=0, end_time=0,
        )
        assert data.error_rate == 0.0

    def test_avg_latency_ms_empty(self):
        """avg_latency_ms is 0.0 with no latencies (lines 48-50)."""
        data = MetricsWindowData(
            window_name="test", duration_seconds=60,
            start_time=0, end_time=0,
        )
        assert data.avg_latency_ms == 0.0

    def test_latency_percentiles_empty(self):
        """latency_percentiles returns zeros when latencies empty (lines 54-65)."""
        data = MetricsWindowData(
            window_name="test", duration_seconds=60,
            start_time=0, end_time=0,
        )
        pcts = data.latency_percentiles
        assert pcts["p50"] == 0.0
        assert pcts["p90"] == 0.0
        assert pcts["p95"] == 0.0
        assert pcts["p99"] == 0.0

    def test_latency_percentiles_with_data(self):
        """latency_percentiles with actual data."""
        data = MetricsWindowData(
            window_name="test", duration_seconds=60,
            start_time=0, end_time=10,
            total_requests=10, successful_requests=8, failed_requests=2,
            latencies=list(range(1, 11)),
        )
        assert data.error_rate == 0.2
        assert data.avg_latency_ms == 5.5
        pcts = data.latency_percentiles
        assert pcts["p50"] > 0
        assert pcts["p99"] > 0


class TestMetricsServiceWithStorage:
    def test_system_metrics_with_mock_storage(self):
        """get_system_metrics with storage that returns stats (lines 178-186)."""
        svc = MetricsService()
        mock_storage = MagicMock()
        mock_storage.get_stats.return_value = {"total": 100, "available": 80}
        result = svc.get_system_metrics(storage=mock_storage)
        assert result["total_proxies_tested"] == 100
        assert result["proxy_test_success_rate"] == 0.8

    def test_system_metrics_with_storage_exception(self):
        """get_system_metrics with storage that raises (line 183)."""
        svc = MetricsService()
        mock_storage = MagicMock()
        mock_storage.get_stats.side_effect = RuntimeError("db error")
        result = svc.get_system_metrics(storage=mock_storage)
        # Should not crash, returns 0 defaults
        assert result["total_proxies_tested"] == 0

    def test_system_metrics_with_storage_healthy_fallback(self):
        """get_system_metrics when 'available' is missing but 'healthy' present (line 182)."""
        svc = MetricsService()
        mock_storage = MagicMock()
        mock_storage.get_stats.return_value = {"total": 50, "healthy": 40}
        result = svc.get_system_metrics(storage=mock_storage)
        assert result["proxy_test_success_rate"] == 0.8

    def test_pool_metrics_with_mock_storage(self):
        """get_pool_metrics with storage (lines 213-223)."""
        svc = MetricsService()
        mock_storage = MagicMock()
        mock_storage.get_proxy_pool_stats.return_value = {
            "total": 30, "healthy": 25, "active": 20,
        }
        result = svc.get_pool_metrics(
            pool_id=1, pool_name="test", storage=mock_storage,
        )
        assert result["total_proxies"] == 30
        assert result["healthy_proxies"] == 25
        assert result["active_proxies"] == 20
        assert result["proxy_health_rate"] > 0

    def test_pool_metrics_with_storage_exception(self):
        """get_pool_metrics when storage raises."""
        svc = MetricsService()
        mock_storage = MagicMock()
        mock_storage.get_proxy_pool_stats.side_effect = RuntimeError("fail")
        result = svc.get_pool_metrics(pool_id=1, pool_name="test", storage=mock_storage)
        assert result["total_proxies"] == 0

    def test_pool_metrics_with_storage_none_pool_stats(self):
        """get_pool_metrics when pool_stats is None (line 216 skipped)."""
        svc = MetricsService()
        mock_storage = MagicMock()
        mock_storage.get_proxy_pool_stats.return_value = None
        result = svc.get_pool_metrics(pool_id=1, pool_name="test", storage=mock_storage)
        assert result["total_proxies"] == 0

    def test_system_metrics_with_no_storage(self):
        """get_system_metrics without storage."""
        svc = MetricsService()
        result = svc.get_system_metrics(storage=None)
        assert result["total_proxies_tested"] == 0
        assert result["proxy_test_success_rate"] == 0.0

    def test_pool_metrics_with_no_storage(self):
        """get_pool_metrics without storage."""
        svc = MetricsService()
        result = svc.get_pool_metrics(pool_id=1, pool_name="test", storage=None)
        assert result["total_proxies"] == 0
