"""
Tests for app.py: router registration, static file mounting, error handlers,
and middleware paths (rate limiting, concurrent limiting, content-length validation).

Targets uncovered lines:
- Lines 1196: /assets static mount
- Lines 1200-1201: /css static mount
- Lines 996-1006: Rate limiter 429 response
- Line 1016: Concurrent request limiter 429 response
- Line 1036: Invalid content-length header passthrough
- Lines 1229-1249: Gateway proxy session handling (REJECT mode)
- Lines 59-71 (routers/__init__.py): Version alias routes
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from proxypool.settings import AppSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
# 1. Router registration: all expected routers are registered
# ---------------------------------------------------------------------------

class TestRouterRegistration:
    def _paths(self, tmp_path: Path) -> set[str]:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        return {r.path for r in app.routes if hasattr(r, "path")}

    def _has_route_prefix(self, paths: set[str], prefix: str) -> bool:
        return any(p.startswith(prefix) for p in paths)

    def test_health_router_registered(self, tmp_path: Path) -> None:
        assert self._has_route_prefix(self._paths(tmp_path), "/api/health")

    def test_proxies_router_registered(self, tmp_path: Path) -> None:
        assert self._has_route_prefix(self._paths(tmp_path), "/api/proxies")

    def test_pools_router_registered(self, tmp_path: Path) -> None:
        assert self._has_route_prefix(self._paths(tmp_path), "/api/pools")

    def test_subscriptions_router_registered(self, tmp_path: Path) -> None:
        assert self._has_route_prefix(self._paths(tmp_path), "/api/subscriptions")

    def test_backend_router_registered(self, tmp_path: Path) -> None:
        assert self._has_route_prefix(self._paths(tmp_path), "/api/backend")

    def test_tester_router_registered(self, tmp_path: Path) -> None:
        assert self._has_route_prefix(self._paths(tmp_path), "/api/tester")

    def test_chain_router_registered(self, tmp_path: Path) -> None:
        assert self._has_route_prefix(self._paths(tmp_path), "/api/chain")

    def test_gateway_router_registered(self, tmp_path: Path) -> None:
        assert self._has_route_prefix(self._paths(tmp_path), "/api/gateway")

    def test_tasks_router_registered(self, tmp_path: Path) -> None:
        assert self._has_route_prefix(self._paths(tmp_path), "/api/tasks")

    def test_settings_router_registered(self, tmp_path: Path) -> None:
        assert self._has_route_prefix(self._paths(tmp_path), "/api/settings")

    def test_gateway_proxy_route_registered(self, tmp_path: Path) -> None:
        assert "/proxy/{pool_name}/{protocol}/{target_path:path}" in self._paths(tmp_path)

    def test_root_route_registered(self, tmp_path: Path) -> None:
        assert "/" in self._paths(tmp_path)

    def test_all_routers_have_at_least_one_route(self, tmp_path: Path) -> None:
        """Each router domain has at least one registered route."""
        paths = self._paths(tmp_path)
        for prefix in ["/api/health", "/api/proxies", "/api/pools",
                        "/api/subscriptions", "/api/backend", "/api/tester",
                        "/api/chain", "/api/gateway", "/api/tasks", "/api/settings"]:
            assert self._has_route_prefix(paths, prefix), f"No routes found for {prefix}"


# ---------------------------------------------------------------------------
# 2. Version alias routes (routers/__init__.py lines 59-71)
# ---------------------------------------------------------------------------

class TestVersionAliases:
    @pytest.mark.anyio
    async def test_v1_health_endpoint(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "status" in data

    @pytest.mark.anyio
    async def test_v1_stats_endpoint(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/stats")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 3. Static file mounting: /assets and /css (lines 1196, 1200-1201)
# ---------------------------------------------------------------------------

class TestStaticFileMounting:
    def test_assets_mount_created_when_dir_exists(self, tmp_path: Path) -> None:
        """When dist/assets directory exists, /assets is mounted."""
        from proxypool.api.app import create_app

        webui = tmp_path / "proxypool" / "webui"
        assets = webui / "dist" / "assets"
        assets.mkdir(parents=True)
        (assets / "test.js").write_text("console.log('test');")

        settings = _make_settings(tmp_path)
        app = create_app(settings)

        # Check that /assets is in mounted paths
        mounted = []
        for route in app.routes:
            if hasattr(route, "path") and hasattr(route, "name"):
                mounted.append(route.path)
        assert "/assets" in mounted

    def test_css_mount_created_when_dir_exists(self, tmp_path: Path) -> None:
        """When webui/css directory exists, /css is mounted."""
        from proxypool.api.app import create_app

        webui = tmp_path / "proxypool" / "webui"
        css = webui / "css"
        css.mkdir(parents=True)
        (css / "style.css").write_text("body {}")

        settings = _make_settings(tmp_path)
        app = create_app(settings)

        mounted = []
        for route in app.routes:
            if hasattr(route, "path") and hasattr(route, "name"):
                mounted.append(route.path)
        assert "/css" in mounted

    def test_assets_not_mounted_when_dir_missing(self, tmp_path: Path) -> None:
        """When dist/assets does not exist, /assets is not mounted."""
        from proxypool.api.app import create_app

        webui = tmp_path / "proxypool" / "webui"
        webui.mkdir(parents=True)

        settings = _make_settings(tmp_path)
        app = create_app(settings)

        mounted = []
        for route in app.routes:
            if hasattr(route, "path") and hasattr(route, "name"):
                mounted.append(route.path)
        assert "/assets" not in mounted

    @pytest.mark.anyio
    async def test_serve_static_asset(self, tmp_path: Path) -> None:
        """Serving a file from /assets returns the file content."""
        from proxypool.api.app import create_app

        webui = tmp_path / "proxypool" / "webui"
        assets = webui / "dist" / "assets"
        assets.mkdir(parents=True)
        (assets / "app.js").write_text("var x = 1;")

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/assets/app.js")
            assert resp.status_code == 200
            assert "var x = 1" in resp.text

    @pytest.mark.anyio
    async def test_serve_css_file(self, tmp_path: Path) -> None:
        """Serving a file from /css returns the file content."""
        from proxypool.api.app import create_app

        webui = tmp_path / "proxypool" / "webui"
        css = webui / "css"
        css.mkdir(parents=True)
        (css / "main.css").write_text("body { color: red; }")

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/css/main.css")
            assert resp.status_code == 200
            assert "color: red" in resp.text


# ---------------------------------------------------------------------------
# 4. Error handler setup: verify handlers produce correct JSON responses
# ---------------------------------------------------------------------------

class TestErrorHandlers:
    @pytest.mark.anyio
    async def test_404_returns_json_detail(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/nonexistent")
            assert resp.status_code == 404
            body = resp.json()
            assert "detail" in body

    @pytest.mark.anyio
    async def test_method_not_allowed_returns_json(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/health")
            assert resp.status_code in (404, 405)

    @pytest.mark.anyio
    async def test_api_error_handler_via_api_error(self, tmp_path: Path) -> None:
        """Trigger APIError handler through the gateway proxy route (pool not found)."""
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/proxy/mypool/https/example.com")
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. Rate limiter 429 response (lines 996-1006)
# ---------------------------------------------------------------------------

class TestRateLimiter:
    @pytest.mark.anyio
    async def test_rate_limit_returns_429(self, tmp_path: Path) -> None:
        """Hammer an endpoint to trigger rate limiting."""
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Fire enough requests to exceed the 60/minute rate limit
            for _ in range(65):
                resp = await client.get("/api/health")
                if resp.status_code == 429:
                    body = resp.json()
                    assert "detail" in body
                    assert "Rate limit" in body["detail"]
                    # Rate limit headers should be present
                    assert "retry-after" in resp.headers or "Retry-After" in resp.headers
                    return
            pytest.fail("Rate limit was not triggered after 65 requests")


# ---------------------------------------------------------------------------
# 6. Concurrent request limiter (line 1016)
# ---------------------------------------------------------------------------

class TestConcurrentLimiter:
    @pytest.mark.anyio
    async def test_concurrent_limit_returns_429(self, tmp_path: Path) -> None:
        """Trigger concurrent request limit on batch endpoint."""
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        # The batch-test endpoint has limit 5. Simulate hitting the limit.
        # We'll mock the limiter's acquire method to return False.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(
                app.state.concurrent_limiter,
                "acquire",
                return_value=(False, "concurrent request limit reached"),
            ):
                resp = await client.post("/api/proxies/batch-test", json={})
                assert resp.status_code == 429
                body = resp.json()
                assert "concurrent" in body["detail"].lower()


# ---------------------------------------------------------------------------
# 7. Invalid content-length header (line 1036)
# ---------------------------------------------------------------------------

class TestContentLengthValidation:
    @pytest.mark.anyio
    async def test_invalid_content_length_does_not_crash(self, tmp_path: Path) -> None:
        """A non-numeric content-length header should be silently ignored."""
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/health",
                headers={"Content-Length": "not-a-number"},
            )
            # Should not crash; request should proceed normally
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 8. Gateway proxy session handling (lines 1229-1249)
# ---------------------------------------------------------------------------

class TestGatewayProxySession:
    @pytest.mark.anyio
    async def test_session_reject_without_session_id(self, tmp_path: Path) -> None:
        """Pool with session_missing_action=REJECT returns 400 when no session."""
        from proxypool.api.app import create_app
        from proxypool.storage.sqlite import SQLiteProxyStorage

        settings = _make_settings(tmp_path)
        app = create_app(settings)

        storage: SQLiteProxyStorage = app.state.storage
        storage.create_proxy_pool(
            name="test-pool",
            gateway_path_prefix="/proxy/testpool",
            session_missing_action="REJECT",
            session_header_names=["X-Session-ID"],
            session_query_param_names=["session_id"],
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/proxy/testpool/https/example.com/path")
            assert resp.status_code == 400
            body = resp.json()
            assert "session_id" in body["detail"]

    @pytest.mark.anyio
    async def test_session_reject_with_header_session_id(self, tmp_path: Path) -> None:
        """Pool with session_missing_action=REJECT passes when header has session."""
        from proxypool.api.app import create_app
        from proxypool.storage.sqlite import SQLiteProxyStorage

        settings = _make_settings(tmp_path)
        app = create_app(settings)

        storage: SQLiteProxyStorage = app.state.storage
        storage.create_proxy_pool(
            name="test-pool2",
            gateway_path_prefix="/proxy/testpool2",
            session_missing_action="REJECT",
            session_header_names=["X-Session-ID"],
            session_query_param_names=["session_id"],
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/proxy/testpool2/https/example.com/path",
                headers={"X-Session-ID": "abc123"},
            )
            assert resp.status_code != 400
            data = resp.json()
            assert data.get("status") == "proxy_not_connected"

    @pytest.mark.anyio
    async def test_session_reject_with_query_session_id(self, tmp_path: Path) -> None:
        """Pool with session_missing_action=REJECT passes when query has session."""
        from proxypool.api.app import create_app
        from proxypool.storage.sqlite import SQLiteProxyStorage

        settings = _make_settings(tmp_path)
        app = create_app(settings)

        storage: SQLiteProxyStorage = app.state.storage
        storage.create_proxy_pool(
            name="test-pool3",
            gateway_path_prefix="/proxy/testpool3",
            session_missing_action="REJECT",
            session_header_names=["X-Session-ID"],
            session_query_param_names=["session_id"],
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/proxy/testpool3/https/example.com/path?session_id=q123",
            )
            assert resp.status_code != 400
            data = resp.json()
            assert data.get("status") == "proxy_not_connected"

    @pytest.mark.anyio
    async def test_session_random_mode_does_not_reject(self, tmp_path: Path) -> None:
        """Pool with session_missing_action=RANDOM does not require session."""
        from proxypool.api.app import create_app
        from proxypool.storage.sqlite import SQLiteProxyStorage

        settings = _make_settings(tmp_path)
        app = create_app(settings)

        storage: SQLiteProxyStorage = app.state.storage
        pool = storage.create_proxy_pool(
            name="test-pool4",
            gateway_path_prefix="/proxy/testpool4",
            session_missing_action="RANDOM",
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/proxy/testpool4/https/example.com/path")
            # RANDOM mode does not reject, returns 200 with status
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("status") == "proxy_not_connected"

    @pytest.mark.anyio
    async def test_gateway_proxy_all_methods(self, tmp_path: Path) -> None:
        """Gateway proxy route handles all configured HTTP methods."""
        from proxypool.api.app import create_app

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Pool not found -> 404, regardless of method
            for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]:
                resp = await client.request(method, "/proxy/nopool/https/x.com")
                assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 9. Middleware metrics skip for /api/system/metrics (line 1139)
# ---------------------------------------------------------------------------

class TestMetricsSkip:
    @pytest.mark.anyio
    async def test_metrics_endpoint_not_tracked(self, tmp_path: Path) -> None:
        """Metrics tracker skips /api/system/metrics to avoid recursion."""
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/system/metrics")
            # Endpoint may or may not exist, but should not cause recursion error
            assert resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# 10. Gateway proxy returns target_url in response
# ---------------------------------------------------------------------------

class TestGatewayProxyResponse:
    @pytest.mark.anyio
    async def test_gateway_proxy_response_format(self, tmp_path: Path) -> None:
        """Gateway proxy returns pool_id, pool_name, target_url, status."""
        from proxypool.api.app import create_app
        from proxypool.storage.sqlite import SQLiteProxyStorage

        settings = _make_settings(tmp_path)
        app = create_app(settings)

        storage: SQLiteProxyStorage = app.state.storage
        pool = storage.create_proxy_pool(
            name="resp-pool",
            gateway_path_prefix="/proxy/resppool",
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/proxy/resppool/https/api.example.com/v1/data")
            assert resp.status_code == 200
            data = resp.json()
            assert data["pool_name"] == "resppool"
            assert data["target_url"] == "https://api.example.com/v1/data"
            assert data["status"] == "proxy_not_connected"
            assert data["pool_id"] == pool["id"]


# ---------------------------------------------------------------------------
# 11. CORS and GZip middleware present
# ---------------------------------------------------------------------------

class TestMiddlewareStack:
    def test_cors_middleware_registered(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in classes

    def test_gzip_middleware_registered(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        classes = [m.cls.__name__ for m in app.user_middleware]
        assert "GZipMiddleware" in classes

    def test_both_middlewares_present(self, tmp_path: Path) -> None:
        """Both CORS and GZip middleware are registered."""
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in classes
        assert "GZipMiddleware" in classes


# ---------------------------------------------------------------------------
# 12. App state settings propagation
# ---------------------------------------------------------------------------

class TestAppStateSettings:
    def test_settings_stored_on_state(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        assert app.state.settings is settings

    def test_settings_api_key_propagated(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path, api_key="my-secret")
        app = create_app(settings)
        assert app.state.settings.api_key == "my-secret"

    def test_settings_db_path_propagated(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        assert app.state.settings.db_path == settings.db_path


# ---------------------------------------------------------------------------
# 13. OpenAPI schema validation
# ---------------------------------------------------------------------------

class TestOpenAPISchema:
    @pytest.mark.anyio
    async def test_openapi_contains_all_routers(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/openapi.json")
            assert resp.status_code == 200
            schema = resp.json()
            paths = schema.get("paths", {})
            # Check representative paths from each router
            assert any("/health" in p for p in paths)
            assert any("/proxies" in p for p in paths)
            assert any("/pools" in p for p in paths)
            assert any("/tester" in p for p in paths)
            assert any("/tasks" in p for p in paths)
            assert any("/settings" in p for p in paths)


# ---------------------------------------------------------------------------
# 14. Gateway proxy 404 for unknown pool
# ---------------------------------------------------------------------------

class TestGatewayProxyNotFound:
    @pytest.mark.anyio
    async def test_unknown_pool_returns_404(self, tmp_path: Path) -> None:
        from proxypool.api.app import create_app
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/proxy/unknown/https/x.com")
            assert resp.status_code == 404
            assert "no pool configured" in resp.json()["detail"]
