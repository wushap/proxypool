"""
Tests for API improvements - Versioning, error handling, validation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class TestAPIVersioning:
    """Test API versioning support."""

    def test_versioned_endpoint_exists(self):
        """Test that versioned endpoints exist."""
        from proxypool.api.app import create_app
        from proxypool.settings import AppSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AppSettings(
                project_root=Path(tmpdir),
                db_path=Path(tmpdir) / "test.db",
                output_dir=Path(tmpdir) / "output",
                sources_file=Path(tmpdir) / "sources.txt",
                singbox_routes_file=Path(tmpdir) / "routes.json",
                singbox_runtime_config_file=Path(tmpdir) / "runtime.json",
                singbox_runtime_log_file=Path(tmpdir) / "runtime.log",
                singbox_binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                api_key="",
                http_gateway_default_host="127.0.0.1",
                http_gateway_default_port=8899,
                backend_engine="singbox",
                backend_health_check_sec=30,
                backend_auto_restart_max=3,
                mihomo_binary="mihomo",
                mihomo_runtime_dir=Path(tmpdir) / "mihomo",
            )
            app = create_app(settings)
            client = TestClient(app)

            # Test versioned endpoint
            response = client.get("/api/v1/health")
            assert response.status_code == 200

            # Test unversioned endpoint (backward compatibility)
            response = client.get("/api/health")
            assert response.status_code == 200

    def test_versioned_stats_endpoint(self):
        """Test versioned stats endpoint."""
        from proxypool.api.app import create_app
        from proxypool.settings import AppSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AppSettings(
                project_root=Path(tmpdir),
                db_path=Path(tmpdir) / "test.db",
                output_dir=Path(tmpdir) / "output",
                sources_file=Path(tmpdir) / "sources.txt",
                singbox_routes_file=Path(tmpdir) / "routes.json",
                singbox_runtime_config_file=Path(tmpdir) / "runtime.json",
                singbox_runtime_log_file=Path(tmpdir) / "runtime.log",
                singbox_binary="sing-box",
                test_url="https://www.cloudflare.com/cdn-cgi/trace",
                api_key="",
                http_gateway_default_host="127.0.0.1",
                http_gateway_default_port=8899,
                backend_engine="singbox",
                backend_health_check_sec=30,
                backend_auto_restart_max=3,
                mihomo_binary="mihomo",
                mihomo_runtime_dir=Path(tmpdir) / "mihomo",
            )
            app = create_app(settings)
            client = TestClient(app)

            # Test versioned stats endpoint
            response = client.get("/api/v1/stats")
            assert response.status_code == 200


class TestAPIErrorHandling:
    """Test API error handling improvements."""

    def test_error_response_format(self):
        """Test that error responses have standardized format."""
        from proxypool.api.errors import create_error_response

        response = create_error_response(
            status_code=404,
            error_code="ERR_PROXY_NOT_FOUND",
            detail="Proxy not found",
            field="proxy_id",
            suggestion="Check if proxy exists",
            correlation_id="test-123",
        )

        assert response.status_code == 404
        content = response.body.decode()
        assert "ERR_PROXY_NOT_FOUND" in content
        assert "Proxy not found" in content
        assert "proxy_id" in content
        assert "Check if proxy exists" in content
        assert "test-123" in content

    def test_error_handler_imports(self):
        """Test that error handlers are properly imported."""
        from proxypool.api.errors import (
            APIError,
            NotFoundError,
            ValidationError,
            api_error_handler,
            generic_exception_handler,
            http_exception_handler,
        )

        # Test that all error classes can be instantiated
        api_error = APIError(
            status_code=400,
            error_code="ERR_TEST",
            detail="Test error",
        )
        assert api_error.status_code == 400
        assert api_error.error_code == "ERR_TEST"

        not_found = NotFoundError("proxy", "123")
        assert not_found.status_code == 404
        assert not_found.error_code == "ERR_PROXY_NOT_FOUND"

        validation = ValidationError("Invalid input", field="name")
        assert validation.status_code == 422
        assert validation.field == "name"


class TestAPIValidation:
    """Test API validation improvements."""

    def test_schema_validation(self):
        """Test that Pydantic schemas validate correctly."""
        from proxypool.api.schemas import (
            ProxyPoolCreateRequest,
            RunTestRequest,
        )

        # Test valid schema
        pool_request = ProxyPoolCreateRequest(
            name="Test Pool",
            filters={"protocol": "http"},
        )
        assert pool_request.name == "Test Pool"

        # Test schema with validation
        test_request = RunTestRequest(
            limit=100,
            concurrency=50,
        )
        assert test_request.limit == 100
        assert test_request.concurrency == 50

    def test_error_classes(self):
        """Test custom error classes."""
        from proxypool.api.errors import (
            APIError,
            ConflictError,
            InternalError,
            NotFoundError,
            RateLimitError,
            ValidationError,
        )

        # Test all error classes
        not_found = NotFoundError("proxy", "123")
        assert not_found.status_code == 404
        assert "proxy" in not_found.error_code.lower()

        validation = ValidationError("Invalid input", field="name")
        assert validation.status_code == 422
        assert validation.field == "name"

        conflict = ConflictError("Name already exists", field="name")
        assert conflict.status_code == 409

        rate_limit = RateLimitError(retry_after=30)
        assert rate_limit.status_code == 429
        assert rate_limit.retry_after == 30

        internal = InternalError()
        assert internal.status_code == 500
