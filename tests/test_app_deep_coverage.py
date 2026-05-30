"""
Tests for app.py: targeting specific uncovered lines.

Covers:
- Lines 73-109: _request_via_forward_proxy (module-level)
- Lines 203-206, 227-256: gateway inner helpers via status endpoint with data
- Line 475: lifespan shutdown path
- Line 1060: string response body in ETag middleware
- Lines 1100-1101: response size tracking exception
- Lines 1148-1149: metrics recording exception
- Lines 1293-1297: _published_subscription_clash_yaml exception path
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from proxypool.api.app import (
    _request_via_forward_proxy,
    create_app,
)
from proxypool.settings import AppSettings


def _make_settings(tmp_path: Path, *, api_key: str = "") -> AppSettings:
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
        api_key=api_key,
        http_gateway_default_host="127.0.0.1",
        http_gateway_default_port=8899,
        backend_engine="singbox",
        backend_health_check_sec=30,
        backend_auto_restart_max=3,
        mihomo_binary="mihomo",
        mihomo_runtime_dir=tmp_path / "runtime" / "mihomo",
    )


# ---------------------------------------------------------------------------
# 1. _request_via_forward_proxy (lines 73-109)
# ---------------------------------------------------------------------------


class TestRequestViaForwardProxy:
    """Test the module-level _request_via_forward_proxy function."""

    @pytest.mark.anyio
    async def test_success_path(self) -> None:
        """Successful proxy request returns expected fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "hello world"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("proxypool.api.app.httpx.AsyncClient", return_value=mock_client):
            result = await _request_via_forward_proxy(
                target_url="https://example.com",
                proxy_url="http://proxy:8080",
                proxy_headers={"Authorization": "Bearer tok"},
                timeout_sec=5.0,
            )

        assert result["request_ok"] is True
        assert result["status_code"] == 200
        assert "elapsed_ms" in result
        assert result["body_preview"] == "hello world"

    @pytest.mark.anyio
    async def test_error_path(self) -> None:
        """Failed proxy request returns error info."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("proxypool.api.app.httpx.AsyncClient", return_value=mock_client):
            result = await _request_via_forward_proxy(
                target_url="https://example.com",
                proxy_url="http://proxy:8080",
                proxy_headers=None,
            )

        assert result["request_ok"] is False
        assert result["error_type"] == "ConnectError"
        assert "elapsed_ms" in result

    @pytest.mark.anyio
    async def test_empty_proxy_headers(self) -> None:
        """Empty proxy_headers dict is treated as None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("proxypool.api.app.httpx.AsyncClient", return_value=mock_client):
            result = await _request_via_forward_proxy(
                target_url="https://example.com",
                proxy_url="http://proxy:8080",
                proxy_headers={},
            )

        assert result["request_ok"] is True

    @pytest.mark.anyio
    async def test_long_body_truncated(self) -> None:
        """Long response body is truncated to 2048 chars in preview."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "x" * 5000

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("proxypool.api.app.httpx.AsyncClient", return_value=mock_client):
            result = await _request_via_forward_proxy(
                target_url="https://example.com",
                proxy_url="http://proxy:8080",
                proxy_headers=None,
            )

        assert result["request_ok"] is True
        assert len(result["body_preview"]) <= 2048

    @pytest.mark.anyio
    async def test_body_preview_error_suppressed(self) -> None:
        """Exception in body reading is suppressed."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Accessing .text raises an exception
        type(mock_response).text = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("read error"))
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("proxypool.api.app.httpx.AsyncClient", return_value=mock_client):
            result = await _request_via_forward_proxy(
                target_url="https://example.com",
                proxy_url="http://proxy:8080",
                proxy_headers=None,
            )

        assert result["request_ok"] is True
        # body_preview should be empty since the exception was suppressed
        assert result["body_preview"] == ""


# ---------------------------------------------------------------------------
# 2. Middleware string body path (line 1060)
# ---------------------------------------------------------------------------


class TestMiddlewareStringBody:
    @pytest.mark.anyio
    async def test_string_response_body_in_etag(self, tmp_path: Path) -> None:
        """GET endpoint returning a string body exercises line 1060."""
        app = create_app(_make_settings(tmp_path))
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # /api/openapi.json returns JSON via body_iterator which may be str chunks
            resp = await client.get("/api/openapi.json")
            assert resp.status_code == 200
            assert "etag" in resp.headers or "ETag" in resp.headers


# ---------------------------------------------------------------------------
# 3. Response size tracking exception (lines 1100-1101)
# ---------------------------------------------------------------------------


class TestResponseSizeTrackingException:
    @pytest.mark.anyio
    async def test_response_size_tracking_exception_suppressed(
        self, tmp_path: Path
    ) -> None:
        """Exception in metrics.record_response_size is suppressed."""
        app = create_app(_make_settings(tmp_path))
        transport = httpx.ASGITransport(app=app)

        with patch.object(
            app.state.metrics_service,
            "record_response_size",
            side_effect=RuntimeError("metrics broken"),
        ):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # GET request triggers ETag block which calls record_response_size
                resp = await client.get("/api/health")
                assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Metrics recording exception (lines 1148-1149)
# ---------------------------------------------------------------------------


class TestMetricsRecordingException:
    @pytest.mark.anyio
    async def test_metrics_recording_exception_suppressed(
        self, tmp_path: Path
    ) -> None:
        """Exception in metrics.record_request is suppressed."""
        app = create_app(_make_settings(tmp_path))
        transport = httpx.ASGITransport(app=app)

        with patch.object(
            app.state.metrics_service,
            "record_request",
            side_effect=RuntimeError("metrics broken"),
        ):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/api/health")
                # Should still work despite metrics failure
                assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 5. Lifespan shutdown (line 475)
# ---------------------------------------------------------------------------


class TestLifespanShutdown:
    @pytest.mark.anyio
    async def test_lifespan_cancel_tasks_on_shutdown(self, tmp_path: Path) -> None:
        """Lifespan shutdown cancels background tasks."""
        app = create_app(_make_settings(tmp_path))

        async with app.router.lifespan_context(app):
            # Tasks are running
            assert app.state.backend_health_task is not None
            assert app.state.auto_task_runner is not None
            assert app.state.gateway_health_task is not None

        # After context exits, tasks should be cancelled and set to None
        assert app.state.backend_health_task is None
        assert app.state.auto_task_runner is None
        assert app.state.gateway_health_task is None

    @pytest.mark.anyio
    async def test_lifespan_cancel_already_done_task(self, tmp_path: Path) -> None:
        """Lifespan handles tasks that are already done."""
        app = create_app(_make_settings(tmp_path))

        async with app.router.lifespan_context(app):
            assert app.state.backend_health_task is not None
            # Cancel one task before shutdown
            app.state.backend_health_task.cancel()

        # All tasks should be None after shutdown
        assert app.state.backend_health_task is None
        assert app.state.auto_task_runner is None
        assert app.state.gateway_health_task is None


# ---------------------------------------------------------------------------
# 6. Gateway status with endpoint data (triggers helper functions)
# ---------------------------------------------------------------------------


class TestGatewayStatusWithEndpoint:
    """Test gateway status endpoint with an actual endpoint configured."""

    @pytest.mark.anyio
    async def test_gateway_status_with_endpoint(self, tmp_path: Path) -> None:
        """Gateway status with endpoint_id triggers hop pool building."""
        from proxypool.models import ProxyNode
        from proxypool.storage.sqlite import SQLiteProxyStorage

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        storage: SQLiteProxyStorage = app.state.storage

        # Create a pool and endpoint with hops
        pool = storage.create_proxy_pool(
            name="test-pool",
            gateway_path_prefix="/proxy/testpool",
        )
        pool_id = int(pool.get("id") or 0)

        # Create a published proxy in the pool for candidates
        node = ProxyNode(
            protocol="trojan",
            host="1.2.3.4",
            port=443,
            raw_link="trojan://1.2.3.4:443",
            extra={"password": "test", "sni": "example.com"},
            name="test-proxy-1",
        )
        storage.upsert_proxy(node, source="test")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/gateway/http-status")
            assert resp.status_code == 200
            data = resp.json()
            assert "config" in data
            assert "runtime" in data

    @pytest.mark.anyio
    async def test_gateway_health_endpoint(self, tmp_path: Path) -> None:
        """Gateway health check endpoint exercises health check path."""
        app = create_app(_make_settings(tmp_path))
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/gateway/http-health-check")
            assert resp.status_code == 200
            data = resp.json()
            assert "item" in data


# ---------------------------------------------------------------------------
# 7. Test _published_subscription_clash_yaml exception path (line 1295-1296)
# ---------------------------------------------------------------------------


class TestClashYamlExceptionPath:
    def test_build_mihomo_proxy_exception_suppressed(self) -> None:
        """Exception during _build_mihomo_proxy is suppressed for that proxy."""
        from proxypool.api.app import _published_subscription_clash_yaml

        # Create a proxy that will cause _build_mihomo_proxy to fail
        # by providing invalid data
        bad_proxy = {"protocol": "http", "host": None, "port": "not-a-number"}
        result = _published_subscription_clash_yaml([bad_proxy])
        # Should still produce valid YAML (proxy is skipped)
        assert "proxies:" in result

    def test_multiple_proxies_some_fail(self) -> None:
        """Mix of working and failing proxies."""
        from proxypool.api.app import _published_subscription_clash_yaml

        proxies = [
            {"protocol": "http", "host": "1.2.3.4", "port": 8080, "name": "good"},
            {"protocol": "unknown", "host": None, "port": 0, "name": "bad"},
            {"protocol": "http", "host": "5.6.7.8", "port": 3128, "name": "good2"},
        ]
        result = _published_subscription_clash_yaml(proxies)
        assert "proxies:" in result
        # At least the good proxies should be in the output
        assert "good" in result


# ---------------------------------------------------------------------------
# 8. Auto-task loop exercise (lines 911-956)
# ---------------------------------------------------------------------------


class TestAutoTaskLoop:
    @pytest.mark.anyio
    async def test_auto_config_toggle(self, tmp_path: Path) -> None:
        """Toggling auto-config exercises the config state management."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Get default config
            resp = await client.get("/api/tasks/auto-config")
            assert resp.status_code == 200
            data = resp.json()
            assert data["item"]["enabled"] is False

            # Enable auto config
            resp = await client.put(
                "/api/tasks/auto-config",
                json={
                    "enabled": True,
                    "subscription_refresh_enabled": True,
                    "subscription_refresh_minutes": 1,
                    "tester_enabled": False,
                    "speed_test_enabled": False,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["item"]["enabled"] is True

    @pytest.mark.anyio
    async def test_auto_config_all_enabled(self, tmp_path: Path) -> None:
        """Setting all auto-config options to enabled."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/tasks/auto-config",
                json={
                    "enabled": True,
                    "subscription_refresh_enabled": True,
                    "subscription_refresh_minutes": 5,
                    "tester_enabled": True,
                    "tester_minutes": 10,
                    "tester_limit": 50,
                    "tester_concurrency": 25,
                    "speed_test_enabled": True,
                    "speed_test_minutes": 30,
                    "speed_test_url": "https://speed.cloudflare.com/__down?bytes=1000000",
                    "speed_test_limit": 10,
                    "speed_test_timeout_sec": 15.0,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["item"]["tester_enabled"] is True
            assert data["item"]["speed_test_enabled"] is True


# ---------------------------------------------------------------------------
# 9. Task start endpoints exercise app state
# ---------------------------------------------------------------------------


class TestTaskEndpoints:
    @pytest.mark.anyio
    async def test_list_tasks(self, tmp_path: Path) -> None:
        """List tasks endpoint works."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/tasks")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data

    @pytest.mark.anyio
    async def test_get_nonexistent_task(self, tmp_path: Path) -> None:
        """Getting a nonexistent task returns 404."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/tasks/nonexistent")
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_stop_nonexistent_task(self, tmp_path: Path) -> None:
        """Stopping a nonexistent task returns 404."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/tasks/nonexistent/stop")
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_task(self, tmp_path: Path) -> None:
        """Deleting a nonexistent task returns 404."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/tasks/nonexistent")
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_speed_test_invalid_url(self, tmp_path: Path) -> None:
        """Speed test with invalid URL returns 400 or 422."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/speed-test/start",
                json={"url": "ftp://invalid-protocol.example.com"},
            )
            # Schema validation may reject (422) or handler may reject (400)
            assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 10. Gateway endpoint with endpoint_id query param
# ---------------------------------------------------------------------------


class TestGatewayEndpointId:
    @pytest.mark.anyio
    async def test_gateway_status_with_zero_endpoint_id(self, tmp_path: Path) -> None:
        """Gateway status with endpoint_id=0 returns no endpoint."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/gateway/http-status?endpoint_id=0")
            assert resp.status_code == 200
            data = resp.json()
            assert data["endpoint_id"] == 0

    @pytest.mark.anyio
    async def test_gateway_status_with_nonexistent_endpoint(self, tmp_path: Path) -> None:
        """Gateway status with nonexistent endpoint_id returns null endpoint."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/gateway/http-status?endpoint_id=99999")
            assert resp.status_code == 200
            data = resp.json()
            assert data["endpoint"] is None


# ---------------------------------------------------------------------------
# 11. Request logger for slow and error paths
# ---------------------------------------------------------------------------


class TestRequestLoggerPaths:
    @pytest.mark.anyio
    async def test_404_response_triggers_error_logging(self, tmp_path: Path) -> None:
        """404 response triggers the error logging path."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/nonexistent-endpoint")
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_405_response_triggers_error_logging(self, tmp_path: Path) -> None:
        """405 response triggers the error logging path (4xx)."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/health")
            assert resp.status_code in (404, 405)


# ---------------------------------------------------------------------------
# 12. Security guard: API key accepted path
# ---------------------------------------------------------------------------


class TestSecurityGuardAPIKey:
    @pytest.mark.anyio
    async def test_valid_api_key_passes(self, tmp_path: Path) -> None:
        """Valid API key allows access to protected endpoints."""
        settings = _make_settings(tmp_path, api_key="my-secret")
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/tester/start",
                json={},
                headers={"X-API-Key": "my-secret"},
            )
            # Should not be 401 (may be other status)
            assert resp.status_code != 401

    @pytest.mark.anyio
    async def test_no_api_key_configured_allows_all(self, tmp_path: Path) -> None:
        """When no API key is configured, all requests are authorized."""
        settings = _make_settings(tmp_path, api_key="")
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 13. Cache headers on various endpoints
# ---------------------------------------------------------------------------


class TestCacheHeaders:
    @pytest.mark.anyio
    async def test_cache_headers_on_health(self, tmp_path: Path) -> None:
        """Cache headers are added to health endpoint response."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200
            # Cache headers should be present
            assert any("cache" in h.lower() for h in resp.headers)


# ---------------------------------------------------------------------------
# 14. Gateway proxy with POST method
# ---------------------------------------------------------------------------


class TestGatewayProxyPOST:
    @pytest.mark.anyio
    async def test_gateway_proxy_post_method(self, tmp_path: Path) -> None:
        """POST to gateway proxy works."""
        from proxypool.storage.sqlite import SQLiteProxyStorage

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        storage: SQLiteProxyStorage = app.state.storage

        storage.create_proxy_pool(
            name="post-pool",
            gateway_path_prefix="/proxy/postpool",
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/proxy/postpool/https/api.example.com/data")
            assert resp.status_code == 200
            data = resp.json()
            assert data["pool_name"] == "postpool"


# ---------------------------------------------------------------------------
# 15. Gateway proxy with custom session headers
# ---------------------------------------------------------------------------


class TestGatewayProxyCustomSession:
    @pytest.mark.anyio
    async def test_custom_session_header_names(self, tmp_path: Path) -> None:
        """Pool with custom session header names works."""
        from proxypool.storage.sqlite import SQLiteProxyStorage

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        storage: SQLiteProxyStorage = app.state.storage

        pool = storage.create_proxy_pool(
            name="custom-session-pool",
            gateway_path_prefix="/proxy/customsession",
        )
        pool_id = int(pool.get("id") or 0)
        storage.update_proxy_pool(
            pool_id=pool_id,
            session_missing_action="REJECT",
            session_header_names=["X-Custom-Token", "Authorization"],
            session_query_param_names=["token", "access_token"],
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # No session -> 400
            resp = await client.get("/proxy/customsession/https/example.com/path")
            assert resp.status_code == 400

            # First custom header
            resp = await client.get(
                "/proxy/customsession/https/example.com/path",
                headers={"X-Custom-Token": "tok123"},
            )
            assert resp.status_code == 200

            # Second custom header
            resp = await client.get(
                "/proxy/customsession/https/example.com/path",
                headers={"Authorization": "Bearer tok456"},
            )
            assert resp.status_code == 200

            # Query param (first name)
            resp = await client.get(
                "/proxy/customsession/https/example.com/path",
                params={"token": "q123"},
            )
            assert resp.status_code == 200

            # Query param (second name)
            resp = await client.get(
                "/proxy/customsession/https/example.com/path",
                params={"access_token": "q456"},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 16. Gateway config update
# ---------------------------------------------------------------------------


class TestGatewayConfigUpdate:
    @pytest.mark.anyio
    async def test_get_gateway_config(self, tmp_path: Path) -> None:
        """Get gateway config returns valid data."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/gateway/http-config")
            assert resp.status_code == 200
            data = resp.json()
            assert "item" in data

    @pytest.mark.anyio
    async def test_update_gateway_config(self, tmp_path: Path) -> None:
        """Update gateway config works."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/gateway/http-config",
                json={"enabled": True, "listen_port": 9999},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["item"]["enabled"] is True


# ---------------------------------------------------------------------------
# 17. HTTP proxy endpoints CRUD
# ---------------------------------------------------------------------------


class TestHTTPProxyEndpointsCRUD:
    @pytest.mark.anyio
    async def test_list_endpoints(self, tmp_path: Path) -> None:
        """List HTTP proxy endpoints returns empty list."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/http-proxy-endpoints")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data

    @pytest.mark.anyio
    async def test_create_and_get_endpoint(self, tmp_path: Path) -> None:
        """Create and retrieve an HTTP proxy endpoint."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Create
            resp = await client.post(
                "/api/http-proxy-endpoints",
                json={
                    "name": "test-endpoint",
                    "listen_host": "127.0.0.1",
                    "listen_port": 18080,
                    "enabled": True,
                },
            )
            assert resp.status_code == 200
            endpoint_id = resp.json()["item"]["id"]

            # Get
            resp = await client.get(
                f"/api/http-proxy-endpoints/{endpoint_id}"
            )
            assert resp.status_code == 200

            # Delete
            resp = await client.delete(
                f"/api/http-proxy-endpoints/{endpoint_id}"
            )
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_get_nonexistent_endpoint(self, tmp_path: Path) -> None:
        """Getting a nonexistent endpoint returns 404."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/http-proxy-endpoints/99999")
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 18. Gateway port conflicts
# ---------------------------------------------------------------------------


class TestGatewayPortConflicts:
    @pytest.mark.anyio
    async def test_check_port_conflicts(self, tmp_path: Path) -> None:
        """Check port conflicts endpoint works."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/gateway/port-conflicts")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 19. Subscription refresh via router (exercises collector path)
# ---------------------------------------------------------------------------


class TestSubscriptionRefresh:
    @pytest.mark.anyio
    async def test_batch_refresh_subscriptions(self, tmp_path: Path) -> None:
        """Batch refresh subscriptions with empty list."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/subscriptions/batch-refresh",
                json={"subscription_ids": [], "timeout_sec": 10.0},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 20. Settings update
# ---------------------------------------------------------------------------


class TestSettingsUpdate:
    @pytest.mark.anyio
    async def test_get_settings(self, tmp_path: Path) -> None:
        """Get settings endpoint works."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/settings")
            assert resp.status_code == 200
            data = resp.json()
            assert "item" in data

    @pytest.mark.anyio
    async def test_update_settings(self, tmp_path: Path) -> None:
        """Update settings endpoint works."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/settings",
                json={"test_url": "https://new.example.com/trace"},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 21. Health endpoints
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    @pytest.mark.anyio
    async def test_health_check(self, tmp_path: Path) -> None:
        """Health check returns 200."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_stats(self, tmp_path: Path) -> None:
        """Stats endpoint returns 200."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/stats")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 22. Collector and proxy list endpoints
# ---------------------------------------------------------------------------


class TestProxyEndpoints:
    @pytest.mark.anyio
    async def test_list_proxies(self, tmp_path: Path) -> None:
        """List proxies endpoint works."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/proxies")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data

    @pytest.mark.anyio
    async def test_list_pools(self, tmp_path: Path) -> None:
        """List pools endpoint works."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/pools")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 23. Gateway test endpoint
# ---------------------------------------------------------------------------


class TestGatewayTest:
    @pytest.mark.anyio
    async def test_gateway_test_endpoint(self, tmp_path: Path) -> None:
        """Gateway test endpoint with proxy not found."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        storage = app.state.storage

        pool = storage.create_proxy_pool(
            name="test-gw",
            gateway_path_prefix="/proxy/testgw",
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/gateway/http-test",
                json={"pool_id": pool["id"], "target_url": "https://example.com"},
            )
            # May return various statuses depending on backend state
            assert resp.status_code in (200, 400, 500, 502)


# ---------------------------------------------------------------------------
# 24. Endpoint connectivity test
# ---------------------------------------------------------------------------


class TestEndpointConnectivity:
    @pytest.mark.anyio
    async def test_connectivity_nonexistent_endpoint(self, tmp_path: Path) -> None:
        """Connectivity test with nonexistent endpoint returns 404."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/gateway/gateway/endpoints/99999/test-connectivity"
            )
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 25. Gateway startup in lifespan (lines 465-469)
# ---------------------------------------------------------------------------


class TestLifespanGatewayStartup:
    @pytest.mark.anyio
    async def test_lifespan_with_gateway_enabled(self, tmp_path: Path) -> None:
        """Lifespan with gateway enabled triggers startup path."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        # Enable gateway config before starting lifespan
        app.state.gateway_config_service.update_config(enabled=True)

        async with app.router.lifespan_context(app):
            # Tasks should be created
            assert app.state.backend_health_task is not None
            assert app.state.auto_task_runner is not None
            assert app.state.gateway_health_task is not None

        # After shutdown, tasks should be None
        assert app.state.backend_health_task is None
        assert app.state.auto_task_runner is None
        assert app.state.gateway_health_task is None

    @pytest.mark.anyio
    async def test_lifespan_gateway_startup_failure(self, tmp_path: Path) -> None:
        """Lifespan gateway startup failure is handled gracefully."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        # Enable gateway config
        app.state.gateway_config_service.update_config(enabled=True)

        # Mock gateway_runtime.start to raise
        with patch.object(
            app.state.gateway_runtime, "start", new_callable=AsyncMock,
            side_effect=RuntimeError("gateway start failed"),
        ):
            async with app.router.lifespan_context(app):
                # Should still work despite gateway startup failure
                assert app.state.backend_health_task is not None

        assert app.state.backend_health_task is None


# ---------------------------------------------------------------------------
# 26. Slow request logging (lines 1169-1170)
# ---------------------------------------------------------------------------


class TestSlowRequestLogging:
    @pytest.mark.anyio
    async def test_slow_request_triggers_logging(self, tmp_path: Path) -> None:
        """Request taking > 1 second triggers slow request logging."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        # Mock time.perf_counter to simulate slow request
        # Middlewares call perf_counter in nested order:
        # request_logger.start -> metrics_tracker.start -> ... ->
        # metrics_tracker.end -> request_logger.end
        call_count = [0]

        def mock_perf_counter():
            call_count[0] += 1
            # Odd calls are start times, even calls are end times
            # Return values so request_logger elapsed > 1000ms
            # request_logger.start: call 1 -> 0.0
            # metrics_tracker.start: call 2 -> 0.0
            # metrics_tracker.end: call 3 -> 0.1
            # request_logger.end: call 4 -> 1.5 (elapsed = 1500ms)
            vals = {1: 0.0, 2: 0.0, 3: 0.1, 4: 1.5}
            return vals.get(call_count[0], 1.5)

        with patch("time.perf_counter", side_effect=mock_perf_counter):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/api/health")
                assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 27. Non-GET response skipping ETag body reconstruction (line 1085-1090)
# ---------------------------------------------------------------------------


class TestNonGETResponseNoETagReconstruction:
    @pytest.mark.anyio
    async def test_post_skips_etag_body_reconstruction(self, tmp_path: Path) -> None:
        """Non-GET response does not go through ETag body reconstruction."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/settings", json={"test_url": "https://x.com"}
            )
            assert resp.status_code == 200
            # PUT should not have ETag
            assert "etag" not in resp.headers


# ---------------------------------------------------------------------------
# 28. Endpoint status with endpoint_id
# ---------------------------------------------------------------------------


class TestEndpointStatusWithID:
    @pytest.mark.anyio
    async def test_endpoint_status_nonexistent(self, tmp_path: Path) -> None:
        """Endpoint status for nonexistent endpoint returns 404."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/http-proxy-endpoints/99999/status")
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_endpoint_route_test_nonexistent(self, tmp_path: Path) -> None:
        """Route test for nonexistent endpoint returns 404."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/http-proxy-endpoints/99999/route-test")
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_endpoint_health_nonexistent(self, tmp_path: Path) -> None:
        """Endpoint health for nonexistent endpoint returns 404."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/gateway/gateway/endpoints/99999/health")
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 29. Service config endpoints
# ---------------------------------------------------------------------------


class TestServiceConfig:
    @pytest.mark.anyio
    async def test_get_service_config(self, tmp_path: Path) -> None:
        """Get HTTP proxy endpoint service config."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/http-proxy-endpoints/service-config")
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_service_config(self, tmp_path: Path) -> None:
        """Update HTTP proxy endpoint service config."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/http-proxy-endpoints/service-config",
                json={"default_pool_id": 0},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 30. Endpoint CRUD: update and get
# ---------------------------------------------------------------------------


class TestEndpointUpdate:
    @pytest.mark.anyio
    async def test_update_endpoint(self, tmp_path: Path) -> None:
        """Update an existing HTTP proxy endpoint."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Create
            resp = await client.post(
                "/api/http-proxy-endpoints",
                json={
                    "name": "update-test",
                    "listen_host": "127.0.0.1",
                    "listen_port": 18081,
                    "enabled": True,
                },
            )
            assert resp.status_code == 200
            endpoint_id = resp.json()["item"]["id"]

            # Update
            resp = await client.put(
                f"/api/http-proxy-endpoints/{endpoint_id}",
                json={"name": "updated-name", "enabled": False},
            )
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_delete_nonexistent_endpoint(self, tmp_path: Path) -> None:
        """Delete nonexistent endpoint returns 404."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/http-proxy-endpoints/99999")
            assert resp.status_code == 404
