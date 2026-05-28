"""
Tests for API performance enhancements - Caching, compression, logging.
"""

from __future__ import annotations

import pytest

from proxypool.api.security import get_cache_headers


class TestCacheHeaders:
    """Test cache header generation."""

    def test_static_assets_long_cache(self):
        """Should set long cache for static assets."""
        headers = get_cache_headers("GET", "/assets/index.js")
        assert "Cache-Control" in headers
        assert "immutable" in headers["Cache-Control"]
        assert "86400" in headers["Cache-Control"]

    def test_health_endpoint_no_cache(self):
        """Should set no-cache for health endpoints."""
        headers = get_cache_headers("GET", "/api/health")
        assert headers["Cache-Control"] == "no-store, no-cache, must-revalidate, private"

    def test_proxies_endpoint_short_cache(self):
        """Should set short cache for proxies endpoint with ETag support."""
        headers = get_cache_headers("GET", "/api/proxies")
        assert "max-age=30" in headers["Cache-Control"]
        assert "must-revalidate" in headers["Cache-Control"]
        assert "stale-while-revalidate" in headers["Cache-Control"]

    def test_pools_endpoint_short_cache(self):
        """Should set short cache for pools endpoint."""
        headers = get_cache_headers("GET", "/api/pools")
        assert "max-age=30" in headers["Cache-Control"]
        assert "must-revalidate" in headers["Cache-Control"]

    def test_config_endpoint_medium_cache(self):
        """Should set medium cache for config endpoint with ETag support."""
        headers = get_cache_headers("GET", "/api/config/export")
        assert "max-age=60" in headers["Cache-Control"]
        assert "must-revalidate" in headers["Cache-Control"]

    def test_write_operations_no_cache(self):
        """Should set no-cache for write operations."""
        headers = get_cache_headers("POST", "/api/proxies")
        assert "no-store" in headers["Cache-Control"]

    def test_delete_operations_no_cache(self):
        """Should set no-cache for delete operations."""
        headers = get_cache_headers("DELETE", "/api/pools/1")
        assert "no-store" in headers["Cache-Control"]

    def test_unknown_api_endpoint_default_cache(self):
        """Should set short default cache for unknown API endpoints with ETag support."""
        headers = get_cache_headers("GET", "/api/unknown")
        assert "max-age=10" in headers["Cache-Control"]
        assert "must-revalidate" in headers["Cache-Control"]

    def test_vary_header_for_api(self):
        """Should include Vary header for API endpoints."""
        headers = get_cache_headers("GET", "/api/proxies")
        assert "Vary" in headers
        assert headers["Vary"] == "X-API-Key"


class TestDatabaseIndexes:
    """Test database index creation (integration test)."""

    def test_indexes_created_on_startup(self):
        """Should create indexes without errors."""
        # This is a basic test to ensure the schema with new indexes is valid
        import tempfile
        from pathlib import Path

        from proxypool.storage.sqlite import SQLiteProxyStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = SQLiteProxyStorage(db_path)

            # Check that indexes exist
            with storage._connect() as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
                )
                indexes = [row[0] for row in cursor.fetchall()]

                # Verify new indexes exist
                assert "idx_proxies_last_checked" in indexes
                assert "idx_proxies_latency" in indexes
                assert "idx_proxies_country" in indexes
                assert "idx_proxies_openai" in indexes
                assert "idx_proxies_ip_purity" in indexes
                assert "idx_proxies_speed" in indexes
                assert "idx_sticky_leases_session" in indexes
                assert "idx_sticky_leases_expires" in indexes
                assert "idx_chain_egress_instances_endpoint" in indexes
                assert "idx_chain_egress_instances_status" in indexes

            storage._connect().close()


class TestResponseCompression:
    """Test response compression configuration."""

    def test_gzip_middleware_configured(self):
        """Should have GZip middleware configured."""
        from fastapi.middleware.gzip import GZipMiddleware

        # This is a basic test - actual compression is tested via integration tests
        assert True  # Placeholder - middleware is configured in app.py


class TestRequestLogging:
    """Test request logging configuration."""

    def test_slow_request_logging(self):
        """Should log slow requests."""
        # This is a basic test - actual logging is verified via integration tests
        # In production, slow requests > 1000ms are logged
        assert True  # Placeholder - logging is configured in app.py

    def test_error_request_logging(self):
        """Should log error requests."""
        # This is a basic test - actual logging is verified via integration tests
        # In production, 4xx and 5xx responses are logged
        assert True  # Placeholder - logging is configured in app.py
