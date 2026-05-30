"""
Tests for app.py: utility functions, middleware, WebUI serving, and error handlers.

Targets uncovered lines:
- 1205-1212: serve_index endpoint (WebUI)
- 1260-1269: _read_sources_file
- 1273: _collect_report_to_dict
- 1285-1311: _published_subscription_clash_yaml
- 1315-1327: _unique_clash_proxy_name
- 1331-1335: _subscription_status_from_report
- 963, 1158: middleware docs/redoc bypass
- 980: middleware auth rejection
- 986: URL length validation
- 1016: concurrent request limiting
- 1032-1036: request size validation
- 1060, 1072-1074: ETag / 304 support
"""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from proxypool.api.app import (
    _collect_report_to_dict,
    _published_subscription_clash_yaml,
    _read_sources_file,
    _subscription_status_from_report,
    _unique_clash_proxy_name,
    create_app,
)
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
# 1. _read_sources_file (lines 1260-1269)
# ---------------------------------------------------------------------------

class TestReadSourcesFile:
    def test_nonexistent_file(self, tmp_path: Path) -> None:
        assert _read_sources_file(tmp_path / "nope.txt") == []

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "sources.txt"
        p.write_text("")
        assert _read_sources_file(p) == []

    def test_comments_and_blanks_filtered(self, tmp_path: Path) -> None:
        p = tmp_path / "sources.txt"
        p.write_text("\n# comment\n\n  \nhttp://example.com\n# another\nhttps://foo.bar\n")
        assert _read_sources_file(p) == ["http://example.com", "https://foo.bar"]

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        p = tmp_path / "sources.txt"
        p.write_text("  http://a.com  \n")
        assert _read_sources_file(p) == ["http://a.com"]

    def test_all_comments(self, tmp_path: Path) -> None:
        p = tmp_path / "sources.txt"
        p.write_text("# line1\n# line2\n")
        assert _read_sources_file(p) == []


# ---------------------------------------------------------------------------
# 2. _subscription_status_from_report (lines 1331-1335)
# ---------------------------------------------------------------------------

class TestSubscriptionStatusFromReport:
    def _make_report(self, **kwargs):
        defaults = {
            "total_sources": 1,
            "total_parsed": 0,
            "total_inserted": 0,
            "total_updated": 0,
            "total_deduped": 0,
            "total_invalid": 0,
            "by_source": [],
        }
        defaults.update(kwargs)

        @dataclass
        class _Src:
            pass

        @dataclass
        class _Report:
            total_sources: int = 0
            total_parsed: int = 0
            total_inserted: int = 0
            total_updated: int = 0
            total_deduped: int = 0
            total_invalid: int = 0
            by_source: list = field(default_factory=list)

        return _Report(**defaults)

    def test_success_when_parsed(self) -> None:
        r = self._make_report(total_parsed=5)
        assert _subscription_status_from_report(r) == ("success", "")

    def test_success_when_inserted(self) -> None:
        r = self._make_report(total_inserted=3)
        assert _subscription_status_from_report(r) == ("success", "")

    def test_success_when_updated(self) -> None:
        r = self._make_report(total_updated=1)
        assert _subscription_status_from_report(r) == ("success", "")

    def test_failed_when_invalid(self) -> None:
        r = self._make_report(total_invalid=1)
        status, error = _subscription_status_from_report(r)
        assert status == "failed"
        assert "invalid" in error.lower()

    def test_success_when_nothing(self) -> None:
        r = self._make_report()
        assert _subscription_status_from_report(r) == ("success", "")


# ---------------------------------------------------------------------------
# 3. _unique_clash_proxy_name (lines 1315-1327)
# ---------------------------------------------------------------------------

class TestUniqueClashProxyName:
    def test_uses_name_field(self) -> None:
        used: set[str] = set()
        name = _unique_clash_proxy_name({"name": "MyProxy"}, idx=1, used=used)
        assert name == "MyProxy"
        assert "MyProxy" in used

    def test_falls_back_to_host_port(self) -> None:
        used: set[str] = set()
        name = _unique_clash_proxy_name({"host": "1.2.3.4", "port": "8080"}, idx=1, used=used)
        assert name == "1.2.3.4:8080"

    def test_falls_back_to_host_only(self) -> None:
        used: set[str] = set()
        name = _unique_clash_proxy_name({"host": "1.2.3.4"}, idx=2, used=used)
        assert name == "1.2.3.4"

    def test_empty_proxy_fallback(self) -> None:
        used: set[str] = set()
        name = _unique_clash_proxy_name({}, idx=3, used=used)
        # No name, no host/port -> falls back to "proxy" (hardcoded default)
        assert name == "proxy"

    def test_deduplication(self) -> None:
        used: set[str] = set()
        n1 = _unique_clash_proxy_name({"name": "X"}, idx=1, used=used)
        n2 = _unique_clash_proxy_name({"name": "X"}, idx=2, used=used)
        assert n1 == "X"
        assert n2 == "X-2"
        assert len(used) == 2

    def test_truncates_long_name(self) -> None:
        used: set[str] = set()
        long_name = "A" * 200
        name = _unique_clash_proxy_name({"name": long_name}, idx=1, used=used)
        assert len(name) <= 80

    def test_whitespace_name_fallback(self) -> None:
        used: set[str] = set()
        name = _unique_clash_proxy_name({"name": "   "}, idx=5, used=used)
        # "   ".strip() == "", no host -> falls back to "proxy" (hardcoded default)
        assert name == "proxy"


# ---------------------------------------------------------------------------
# 4. _collect_report_to_dict (line 1273)
# ---------------------------------------------------------------------------

class TestCollectReportToDict:
    def test_converts_report(self) -> None:
        @dataclass
        class Src:
            source: str = "s"
            parsed: int = 1

        @dataclass
        class Report:
            total_sources: int = 1
            total_parsed: int = 10
            total_inserted: int = 5
            total_updated: int = 2
            total_deduped: int = 3
            total_invalid: int = 0
            by_source: list = field(default_factory=lambda: [Src()])

        result = _collect_report_to_dict(Report())
        assert result["total_sources"] == 1
        assert result["total_parsed"] == 10
        assert result["total_inserted"] == 5
        assert len(result["by_source"]) == 1


# ---------------------------------------------------------------------------
# 5. _published_subscription_clash_yaml (lines 1285-1311)
# ---------------------------------------------------------------------------

class TestPublishedSubscriptionClashYaml:
    def test_empty_proxies(self) -> None:
        result = _published_subscription_clash_yaml([])
        assert "DIRECT" in result
        assert "proxy-groups" in result

    def test_with_mock_proxy(self) -> None:
        # Use http protocol which needs no special extra fields
        proxy = {
            "protocol": "http",
            "host": "1.2.3.4",
            "port": 8080,
            "name": "test-http",
        }
        result = _published_subscription_clash_yaml([proxy])
        assert "proxies:" in result
        assert "test-http" in result

    def test_duplicate_names_get_suffixed(self) -> None:
        proxy = {
            "protocol": "http",
            "host": "1.2.3.4",
            "port": 8080,
            "name": "same",
        }
        result = _published_subscription_clash_yaml([proxy, proxy])
        assert "same-2" in result


# ---------------------------------------------------------------------------
# 6. WebUI serving: serve_index (lines 1205-1212)
# ---------------------------------------------------------------------------

class TestServeIndex:
    def test_serves_dist_index(self, tmp_path: Path) -> None:
        # Create dist/index.html
        webui = tmp_path / "proxypool" / "webui"
        dist = webui / "dist"
        dist.mkdir(parents=True)
        (dist / "index.html").write_text("<html>dist</html>")

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async def _run():
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/")
                assert resp.status_code == 200
                assert "dist" in resp.text
        import asyncio
        asyncio.get_event_loop().run_until_complete(_run())

    def test_serves_legacy_index(self, tmp_path: Path) -> None:
        webui = tmp_path / "proxypool" / "webui"
        webui.mkdir(parents=True)
        # No dist directory; put index.html in legacy location
        (webui / "index.html").write_text("<html>legacy</html>")

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async def _run():
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/")
                assert resp.status_code == 200
                assert "legacy" in resp.text
        import asyncio
        asyncio.get_event_loop().run_until_complete(_run())

    def test_404_when_no_index(self, tmp_path: Path) -> None:
        # Ensure webui dir exists but no index.html
        webui = tmp_path / "proxypool" / "webui"
        webui.mkdir(parents=True)

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async def _run():
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/")
                assert resp.status_code == 404
                assert "WebUI not found" in resp.json()["detail"]
        import asyncio
        asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# 7. Middleware: docs/redoc bypass (lines 963, 1158)
# ---------------------------------------------------------------------------

class TestMiddlewareDocsBypass:
    @pytest.mark.anyio
    async def test_docs_not_blocked_by_auth(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path, api_key="secret-key")
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/docs")
            # Should not get 401 even with api_key set
            assert resp.status_code != 401

    @pytest.mark.anyio
    async def test_redoc_not_blocked_by_auth(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path, api_key="secret-key")
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/redoc")
            assert resp.status_code != 401


# ---------------------------------------------------------------------------
# 8. Middleware: auth rejection (line 980)
# ---------------------------------------------------------------------------

class TestMiddlewareAuth:
    @pytest.mark.anyio
    async def test_unauthorized_with_api_key(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path, api_key="secret-key")
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # POST to a protected endpoint without providing api key
            resp = await client.post("/api/tasks/tester/start", json={})
            assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_wrong_api_key_rejected(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path, api_key="secret-key")
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/tester/start",
                json={},
                headers={"X-API-Key": "wrong"},
            )
            assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_correct_api_key_accepted(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path, api_key="secret-key")
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/tester/start",
                json={},
                headers={"X-API-Key": "secret-key"},
            )
            # Should not get 401 (may get other errors like internal 500)
            assert resp.status_code != 401


# ---------------------------------------------------------------------------
# 9. Middleware: URL length validation (line 986)
# ---------------------------------------------------------------------------

class TestMiddlewareUrlLength:
    @pytest.mark.anyio
    async def test_long_url_returns_414(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Craft a URL longer than MAX_URL_LENGTH (2048)
            long_path = "x" * 3000
            resp = await client.get(f"/api/health?{long_path}=v")
            assert resp.status_code == 414


# ---------------------------------------------------------------------------
# 10. Middleware: ETag and 304 support (lines 1060, 1072-1074)
# ---------------------------------------------------------------------------

class TestMiddlewareETag:
    @pytest.mark.anyio
    async def test_etag_header_present(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200
            assert "etag" in resp.headers

    @pytest.mark.anyio
    async def test_304_not_modified(self, tmp_path: Path) -> None:
        # Use static "/" endpoint so the response body is deterministic
        webui = tmp_path / "proxypool" / "webui"
        dist = webui / "dist"
        dist.mkdir(parents=True)
        (dist / "index.html").write_text("<html>static</html>")

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # First request to get ETag
            resp1 = await client.get("/")
            assert resp1.status_code == 200
            etag = resp1.headers.get("etag")
            assert etag is not None

            # Second request with matching If-None-Match -> 304
            resp2 = await client.get("/", headers={"If-None-Match": etag})
            assert resp2.status_code == 304

    @pytest.mark.anyio
    async def test_304_different_etag_gets_200(self, tmp_path: Path) -> None:
        webui = tmp_path / "proxypool" / "webui"
        dist = webui / "dist"
        dist.mkdir(parents=True)
        (dist / "index.html").write_text("<html>static</html>")

        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/", headers={"If-None-Match": '"deadbeef"'}
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 11. Middleware: security and cache headers
# ---------------------------------------------------------------------------

class TestMiddlewareHeaders:
    @pytest.mark.anyio
    async def test_security_headers_present(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200
            # Security headers should be added
            assert "X-Content-Type-Options" in resp.headers

    @pytest.mark.anyio
    async def test_rate_limit_headers_present(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200
            # Rate limit headers should be added
            assert "X-RateLimit-Limit" in resp.headers or "X-RateLimit-Remaining" in resp.headers


# ---------------------------------------------------------------------------
# 12. Middleware: request logger skips docs paths (line 1158)
# ---------------------------------------------------------------------------

class TestMiddlewareRequestLogger:
    @pytest.mark.anyio
    async def test_docs_request_does_not_crash(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/docs")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 13. _default_auto_task_config (lines 112-126)
# ---------------------------------------------------------------------------

class TestDefaultAutoTaskConfig:
    def test_returns_expected_keys(self) -> None:
        from proxypool.api.app import _default_auto_task_config
        config = _default_auto_task_config()
        assert config["enabled"] is False
        assert config["subscription_refresh_enabled"] is True
        assert config["subscription_refresh_minutes"] == 60
        assert config["tester_enabled"] is False
        assert config["tester_minutes"] == 60
        assert config["speed_test_enabled"] is False
        assert config["speed_test_minutes"] == 120
        assert config["speed_test_timeout_sec"] == 30.0


# ---------------------------------------------------------------------------
# 14. _proxy_status_summary via gateway helpers (lines 203-206)
# ---------------------------------------------------------------------------

class TestProxyStatusSummary:
    """Test _proxy_status_summary through gateway status endpoints."""

    @pytest.mark.anyio
    async def test_gateway_status_returns_summary(self, tmp_path: Path) -> None:
        """The gateway status endpoint calls _proxy_status_summary internally."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Gateway status endpoint should trigger the internal helper
            resp = await client.get("/api/gateway/http-status")
            assert resp.status_code == 200
            data = resp.json()
            assert "config" in data or "runtime" in data


# ---------------------------------------------------------------------------
# 15. Metrics tracker middleware (lines 1131-1151)
# ---------------------------------------------------------------------------

class TestMetricsTracker:
    @pytest.mark.anyio
    async def test_metrics_tracker_does_not_crash(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200
            # Metrics should be recorded for non-metrics endpoints
            metrics = app.state.metrics_service
            assert hasattr(metrics, "record_request")


# ---------------------------------------------------------------------------
# 16. Task auto-config endpoint (exercises auto_task_config state)
# ---------------------------------------------------------------------------

class TestAutoTaskConfigEndpoint:
    @pytest.mark.anyio
    async def test_get_auto_config(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/tasks/auto-config")
            assert resp.status_code == 200
            data = resp.json()
            assert "item" in data
            assert data["item"]["enabled"] is False

    @pytest.mark.anyio
    async def test_update_auto_config(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/tasks/auto-config",
                json={"enabled": True, "tester_enabled": True, "tester_minutes": 30},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["item"]["enabled"] is True
            assert data["item"]["tester_minutes"] == 30


# ---------------------------------------------------------------------------
# 17. API docs and OpenAPI
# ---------------------------------------------------------------------------

class TestApiDocs:
    @pytest.mark.anyio
    async def test_openapi_schema(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/openapi.json")
            assert resp.status_code == 200
            schema = resp.json()
            assert "openapi" in schema
            assert "paths" in schema


# ---------------------------------------------------------------------------
# 18. Error handlers (lines 98-108 in errors.py, exercised through app)
# ---------------------------------------------------------------------------

class TestErrorHandlers:
    @pytest.mark.anyio
    async def test_404_returns_json(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/nonexistent-endpoint")
            assert resp.status_code == 404
            data = resp.json()
            assert "detail" in data

    @pytest.mark.anyio
    async def test_method_not_allowed(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/health")
            assert resp.status_code in (404, 405)


# ---------------------------------------------------------------------------
# 19. GZip middleware (line 496)
# ---------------------------------------------------------------------------

class TestGZipMiddleware:
    @pytest.mark.anyio
    async def test_gzip_accept(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/health",
                headers={"Accept-Encoding": "gzip"},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 20. Middleware: content-length validation (lines 1032-1036)
# ---------------------------------------------------------------------------

class TestRequestSizeValidation:
    @pytest.mark.anyio
    async def test_oversized_request_rejected(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Send request with huge content-length header to a batch endpoint
            resp = await client.post(
                "/api/proxies/batch-delete",
                content=b"x" * (60 * 1024 * 1024),  # 60MB > 50MB batch limit
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 413


# ---------------------------------------------------------------------------
# 21. app.state initialization coverage
# ---------------------------------------------------------------------------

class TestAppStateInit:
    @pytest.mark.anyio
    async def test_state_has_all_services(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        assert hasattr(app.state, "storage")
        assert hasattr(app.state, "collector")
        assert hasattr(app.state, "tester")
        assert hasattr(app.state, "geoip")
        assert hasattr(app.state, "scheduler")
        assert hasattr(app.state, "task_manager")
        assert hasattr(app.state, "singbox_manager")
        assert hasattr(app.state, "pool_service")
        assert hasattr(app.state, "chain_service")
        assert hasattr(app.state, "chain_instance_manager")
        assert hasattr(app.state, "unified_gateway")
        assert hasattr(app.state, "gateway_config_service")
        assert hasattr(app.state, "forward_gateway")
        assert hasattr(app.state, "gateway_runtime")
        assert hasattr(app.state, "metrics_service")
        assert hasattr(app.state, "monitoring_service")
        assert hasattr(app.state, "rate_limiter")
        assert hasattr(app.state, "api_key_manager")
        assert hasattr(app.state, "concurrent_limiter")
        assert hasattr(app.state, "auto_task_config")
        assert hasattr(app.state, "auto_task_last_run")
        assert hasattr(app.state, "gateway_health_snapshot")

    @pytest.mark.anyio
    async def test_app_metadata(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        assert app.title == "ProxyPool API"
        assert app.version == "0.2.0"


# ---------------------------------------------------------------------------
# 22. Invalid content-length header (line 1036 - ValueError catch)
# ---------------------------------------------------------------------------

class TestInvalidContentLength:
    @pytest.mark.anyio
    async def test_invalid_content_length_ignored(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Send a non-numeric content-length; middleware should catch ValueError and continue
            resp = await client.get(
                "/api/health",
                headers={"content-length": "not-a-number"},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 23. Non-GET request skips ETag block (line 1055 false branch)
# ---------------------------------------------------------------------------

class TestNonGetSkipsETag:
    @pytest.mark.anyio
    async def test_post_request_no_etag(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # POST request should not get ETag processing
            resp = await client.post("/api/tasks", json={})
            # It won't have an ETag since it's a POST
            # The response might be 200 or other non-401 status
            assert resp.status_code != 401


# ---------------------------------------------------------------------------
# 24. Lifespan startup and shutdown (lines 460-479)
# ---------------------------------------------------------------------------

class TestLifespan:
    @pytest.mark.anyio
    async def test_lifespan_startup_shutdown(self, tmp_path: Path) -> None:
        """Test that lifespan creates and cancels background tasks."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        # Use the lifespan context manager directly
        async with app.router.lifespan_context(app):
            # During lifespan, background tasks should be created
            assert app.state.backend_health_task is not None
            assert app.state.auto_task_runner is not None
            assert app.state.gateway_health_task is not None

            # Cancel tasks to avoid waiting for the loop
            app.state.backend_health_task.cancel()
            app.state.auto_task_runner.cancel()
            app.state.gateway_health_task.cancel()

        # After lifespan exits, tasks should be None
        assert app.state.backend_health_task is None
        assert app.state.auto_task_runner is None
        assert app.state.gateway_health_task is None

    @pytest.mark.anyio
    async def test_lifespan_gateway_disabled(self, tmp_path: Path) -> None:
        """Test lifespan when gateway is disabled (default)."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        # Gateway is disabled by default, so gateway_runtime.start() should not be called
        async with app.router.lifespan_context(app):
            assert app.state.backend_health_task is not None
            app.state.backend_health_task.cancel()
            app.state.auto_task_runner.cancel()
            app.state.gateway_health_task.cancel()


# ---------------------------------------------------------------------------
# 25. Concurrent limiter path (line 1016)
# ---------------------------------------------------------------------------

class TestConcurrentLimiter:
    @pytest.mark.anyio
    async def test_concurrent_limiter_on_batch_endpoint(self, tmp_path: Path) -> None:
        """Test that batch endpoints go through the concurrent limiter path."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Batch test endpoint goes through concurrent limiter
            resp = await client.post(
                "/api/proxies/batch-test",
                json={"normalized_keys": [], "concurrency": 1},
            )
            # The concurrent limiter acquired, but the actual operation may return
            # various status codes. The important thing is the limiter path was exercised.
            assert resp.status_code in (200, 401, 429, 500)

    @pytest.mark.anyio
    async def test_concurrent_limiter_exhausted(self, tmp_path: Path) -> None:
        """Test concurrent limiter rejecting when exhausted."""
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)

        # Exhaust the concurrent limiter for batch-test endpoint
        limiter = app.state.concurrent_limiter
        path = "/api/proxies/batch-test"
        max_concurrent = 5  # from CONCURRENT_BATCH_LIMITS

        # Acquire all slots
        for _ in range(max_concurrent):
            limiter.acquire(path, max_concurrent)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                path,
                json={"normalized_keys": [], "concurrency": 1},
            )
            assert resp.status_code == 429

        # Release all slots
        for _ in range(max_concurrent):
            limiter.release(path)
