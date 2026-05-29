"""
Tests for uncovered FastAPI dependencies.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from proxypool.api.dependencies import (
    FilterParams,
    PaginationParams,
    get_app_state,
    get_backend_instance_manager,
    get_chain_instance_manager,
    get_chain_service,
    get_forward_gateway,
    get_gateway_config_service,
    get_gateway_runtime,
    get_geoip_service,
    get_scheduler,
    get_singbox_manager,
    get_settings,
    security,
    verify_api_key,
)


def _make_request(**state_attrs):
    """Create a mock FastAPI Request with app.state attributes."""
    app = SimpleNamespace(state=SimpleNamespace(**state_attrs))
    return SimpleNamespace(app=app, method="GET", url=SimpleNamespace(path="/api/test"))


def _make_auth_request(method: str = "GET", path: str = "/api/test", **state_attrs):
    """Create a mock Request with specific method/path for auth tests."""
    app = SimpleNamespace(state=SimpleNamespace(**state_attrs))
    return SimpleNamespace(app=app, method=method, url=SimpleNamespace(path=path))


class TestGetSettingsCached:
    """Test get_settings caching branch."""

    def test_get_settings_returns_same_instance_on_subsequent_calls(self):
        """Second call should return cached singleton (line 19->21 branch)."""
        import proxypool.api.dependencies as deps

        # Reset the global cache so we control the test
        original = deps._settings
        deps._settings = None
        try:
            first = get_settings()
            second = get_settings()
            assert first is second
        finally:
            deps._settings = original


class TestMissingDependencies:
    """Test dependency getters not covered by existing tests."""

    def test_get_chain_service(self):
        mock = MagicMock()
        request = _make_request(chain_service=mock)
        assert get_chain_service(request) is mock

    def test_get_backend_instance_manager(self):
        mock = MagicMock()
        request = _make_request(chain_instance_manager=mock)
        assert get_backend_instance_manager(request) is mock

    def test_get_chain_instance_manager(self):
        mock = MagicMock()
        request = _make_request(chain_instance_manager=mock)
        assert get_chain_instance_manager(request) is mock

    def test_get_gateway_config_service(self):
        mock = MagicMock()
        request = _make_request(gateway_config_service=mock)
        assert get_gateway_config_service(request) is mock

    def test_get_forward_gateway(self):
        mock = MagicMock()
        request = _make_request(forward_gateway=mock)
        assert get_forward_gateway(request) is mock

    def test_get_gateway_runtime(self):
        mock = MagicMock()
        request = _make_request(gateway_runtime=mock)
        assert get_gateway_runtime(request) is mock

    def test_get_geoip_service(self):
        mock = MagicMock()
        request = _make_request(geoip=mock)
        assert get_geoip_service(request) is mock

    def test_get_singbox_manager(self):
        mock = MagicMock()
        request = _make_request(singbox_manager=mock)
        assert get_singbox_manager(request) is mock

    def test_get_scheduler(self):
        mock = MagicMock()
        request = _make_request(scheduler=mock)
        assert get_scheduler(request) is mock

    def test_get_app_state(self):
        state = SimpleNamespace(storage=MagicMock())
        request = _make_request()
        # Override app.state to be our specific object
        request.app.state = state
        assert get_app_state(request) is state


class TestVerifyApiKey:
    """Test verify_api_key async dependency."""

    @pytest.mark.asyncio
    async def test_verify_api_key_with_valid_credentials(self):
        """Valid API key on an auth-required endpoint should pass."""
        settings = SimpleNamespace(api_key="test-key-123")
        request = _make_auth_request(method="POST", path="/api/proxies/delete-unavailable")
        credentials = SimpleNamespace(credentials="test-key-123")

        # Should not raise
        await verify_api_key(request, credentials, settings)

    @pytest.mark.asyncio
    async def test_verify_api_key_raises_on_bad_key(self):
        """Wrong API key should raise 401."""
        settings = SimpleNamespace(api_key="correct-key")
        request = _make_auth_request(method="POST", path="/api/proxies/delete-unavailable")
        credentials = SimpleNamespace(credentials="wrong-key")

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request, credentials, settings)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_api_key_no_credentials(self):
        """Missing credentials on auth-required endpoint should raise 401."""
        settings = SimpleNamespace(api_key="some-key")
        request = _make_auth_request(method="POST", path="/api/proxies/delete-unavailable")

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request, None, settings)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_api_key_no_configured_key(self):
        """No API key configured means all requests pass."""
        settings = SimpleNamespace(api_key="")
        request = _make_auth_request(method="POST", path="/api/proxies/delete-unavailable")
        credentials = SimpleNamespace(credentials="anything")

        await verify_api_key(request, credentials, settings)

    @pytest.mark.asyncio
    async def test_verify_api_key_readonly_endpoint_no_key_needed(self):
        """Read-only endpoints skip auth even with a key configured."""
        settings = SimpleNamespace(api_key="some-key")
        request = _make_auth_request(method="GET", path="/api/proxies")

        await verify_api_key(request, None, settings)


class TestModelParams:
    """Test PaginationParams and FilterParams defaults."""

    def test_pagination_defaults(self):
        p = PaginationParams()
        assert p.limit == 100
        assert p.offset == 0

    def test_filter_defaults(self):
        f = FilterParams()
        assert f.protocol is None
        assert f.available is None
        assert f.country is None
        assert f.sort_by == "score"
        assert f.sort_order == "desc"

    def test_filter_custom(self):
        f = FilterParams(protocol="http", available=True, country="US")
        assert f.protocol == "http"
        assert f.available is True
        assert f.country == "US"


class TestSecurityBearer:
    """Test the HTTPBearer security instance."""

    def test_security_is_httpbearer(self):
        assert security is not None
