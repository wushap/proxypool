"""
Authentication Security Tests - Validates API authentication.
"""
from __future__ import annotations

import pytest

from proxypool.api.security import (
    is_api_key_required,
    is_request_authorized,
    validate_task_id,
)


class TestAuthenticationSecurity:
    """Authentication security test suite."""

    # ---- API Key Required Tests ----

    def test_readonly_endpoints_no_auth(self):
        """Read-only endpoints should not require authentication."""
        assert is_api_key_required("GET", "/") is False
        assert is_api_key_required("GET", "/api/health") is False

    def test_mutation_endpoints_require_auth(self):
        """Mutation endpoints should require authentication."""
        assert is_api_key_required("POST", "/api/backend/start") is True
        assert is_api_key_required("DELETE", "/api/subscriptions/1") is True
        assert is_api_key_required("POST", "/api/proxies/delete-unavailable") is True

    def test_collector_import_requires_auth(self):
        """Collector import endpoints should require auth (SSRF risk)."""
        assert is_api_key_required("POST", "/api/collector/import-urls") is True
        assert is_api_key_required("POST", "/api/collector/import-files") is True
        assert is_api_key_required("POST", "/api/collector/import-sources") is True

    def test_gateway_test_requires_auth(self):
        """Gateway test endpoints should require auth (SSRF risk)."""
        assert is_api_key_required("POST", "/api/gateway/http-test") is True
        assert is_api_key_required("POST", "/api/gateway/http-health-check") is True

    def test_task_list_no_auth(self):
        """GET /api/tasks should not require auth."""
        assert is_api_key_required("GET", "/api/tasks") is False
        assert is_api_key_required("GET", "/api/tasks/abc123") is False

    def test_task_stop_requires_auth(self):
        """Stopping tasks should require auth."""
        assert is_api_key_required("POST", "/api/tasks/abc123/stop") is True

    # ---- Request Authorization Tests ----

    def test_no_api_key_configured_allows_all(self):
        """When no API key configured, all requests allowed."""
        assert is_request_authorized("POST", "/api/backend/start", "", None) is True
        assert is_request_authorized("POST", "/api/backend/start", "", "") is True

    def test_api_key_required_no_key_provided(self):
        """When API key required but not provided, deny."""
        assert is_request_authorized("POST", "/api/backend/start", "", "secret") is False

    def test_api_key_required_wrong_key(self):
        """When wrong API key provided, deny."""
        assert is_request_authorized("POST", "/api/backend/start", "wrong", "secret") is False

    def test_api_key_required_correct_key(self):
        """When correct API key provided, allow."""
        assert is_request_authorized("POST", "/api/backend/start", "secret", "secret") is True

    def test_readonly_endpoint_with_api_key(self):
        """Read-only endpoints should work even with API key configured."""
        assert is_request_authorized("GET", "/api/health", "", "secret") is True

    # ---- Task ID Validation Tests ----

    def test_valid_task_id(self):
        """Valid task ID formats."""
        assert validate_task_id("abc12345") is True
        assert validate_task_id("abc12345-6789-def0") is True
        assert validate_task_id("ABCDEF01-2345-6789") is True

    def test_invalid_task_id(self):
        """Invalid task ID formats."""
        assert validate_task_id("") is False
        assert validate_task_id(None) is False  # type: ignore
        assert validate_task_id("short") is False
        assert validate_task_id("has spaces") is False
        assert validate_task_id("has@special!") is False
