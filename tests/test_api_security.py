"""
Tests for API security enhancements - Rate limiting, API key rotation, CORS, request size validation.
"""

from __future__ import annotations

import time

import pytest

from proxypool.api.security import (
    APIKeyManager,
    ConcurrentRequestLimiter,
    RateLimiter,
    create_security_headers,
    get_client_ip,
    get_cors_settings,
    get_rate_limit_for_endpoint,
    is_batch_operation,
    validate_request_size,
    validate_url_length,
)


class TestRateLimiter:
    """Test RateLimiter functionality."""

    def test_rate_limiter_not_limited_within_window(self):
        """Should not be limited when under the limit."""
        limiter = RateLimiter()
        # Default is 60/minute, make 5 requests
        for _ in range(5):
            is_limited, remaining, retry_after = limiter.is_limited("test_key", "60/minute")
            assert is_limited is False
            assert retry_after == 0

    def test_rate_limiter_limited_at_limit(self):
        """Should be limited when reaching the limit."""
        limiter = RateLimiter()
        # Use 2/second limit for fast testing
        for _ in range(2):
            is_limited, remaining, retry_after = limiter.is_limited("test_key", "2/second")
            assert is_limited is False

        # Third request should be limited
        is_limited, remaining, retry_after = limiter.is_limited("test_key", "2/second")
        assert is_limited is True
        assert remaining == 0

    def test_rate_limiter_different_keys(self):
        """Should track different keys independently."""
        limiter = RateLimiter()
        # Use 1/second limit
        is_limited1, _, _ = limiter.is_limited("key1", "1/second")
        is_limited2, _, _ = limiter.is_limited("key2", "1/second")

        assert is_limited1 is False
        assert is_limited2 is False

        # Both should be limited now
        is_limited1, _, _ = limiter.is_limited("key1", "1/second")
        is_limited2, _, _ = limiter.is_limited("key2", "1/second")
        assert is_limited1 is True
        assert is_limited2 is True

    def test_rate_limiter_headers(self):
        """Should generate correct rate limit headers."""
        limiter = RateLimiter()
        headers = limiter.get_rate_limit_headers("key", "60/minute", 55)

        assert headers["X-RateLimit-Limit"] == "60"
        assert headers["X-RateLimit-Remaining"] == "55"
        assert headers["X-RateLimit-Policy"] == "60/minute"


class TestAPIKeyManager:
    """Test APIKeyManager functionality."""

    def test_generate_key(self):
        """Should generate a valid API key."""
        manager = APIKeyManager()
        key = manager.generate_key()
        assert key.startswith("pp_")
        assert len(key) > 10

    def test_generate_key_with_prefix(self):
        """Should generate a key with custom prefix."""
        manager = APIKeyManager()
        key = manager.generate_key(prefix="test")
        assert key.startswith("test_")

    def test_register_and_validate_key(self):
        """Should register and validate API keys."""
        manager = APIKeyManager()
        key = manager.generate_key()
        info = manager.register_key(key, expires_in_days=30)

        assert manager.validate_key(key) is True
        assert info["active"] is True

    def test_revoke_key(self):
        """Should revoke API keys."""
        manager = APIKeyManager()
        key = manager.generate_key()
        manager.register_key(key)

        assert manager.revoke_key(key) is True
        assert manager.validate_key(key) is False

    def test_rotate_key(self):
        """Should rotate API keys correctly."""
        manager = APIKeyManager()
        old_key = manager.generate_key()
        manager.register_key(old_key)

        new_key, new_info = manager.rotate_key(old_key)

        # Old key should be invalid
        assert manager.validate_key(old_key) is False
        # New key should be valid
        assert manager.validate_key(new_key) is True
        # New key should be different
        assert new_key != old_key

    def test_list_keys(self):
        """Should list registered keys."""
        manager = APIKeyManager()
        key1 = manager.generate_key()
        key2 = manager.generate_key()
        manager.register_key(key1)
        manager.register_key(key2)
        manager.revoke_key(key2)

        # List active keys
        active_keys = manager.list_keys(include_inactive=False)
        assert len(active_keys) == 1

        # List all keys
        all_keys = manager.list_keys(include_inactive=True)
        assert len(all_keys) == 2


class TestBatchOperationDetection:
    """Test batch operation detection."""

    def test_batch_operations_detected(self):
        """Should detect batch operation endpoints."""
        assert is_batch_operation("POST", "/api/pools/batch") is True
        assert is_batch_operation("POST", "/api/proxies/batch-delete") is True
        assert is_batch_operation("POST", "/api/subscriptions/batch-refresh") is True

    def test_non_batch_operations_not_detected(self):
        """Should not detect non-batch endpoints as batch."""
        assert is_batch_operation("GET", "/api/proxies") is False
        assert is_batch_operation("POST", "/api/pools") is False
        assert is_batch_operation("DELETE", "/api/pools/1") is False


class TestRateLimitForEndpoint:
    """Test rate limit selection for endpoints."""

    def test_read_endpoints_get_default_limit(self):
        """Read endpoints should get default rate limit."""
        limit = get_rate_limit_for_endpoint("GET", "/api/proxies")
        assert limit == "60/minute"

    def test_write_endpoints_get_write_limit(self):
        """Write endpoints should get write rate limit."""
        limit = get_rate_limit_for_endpoint("POST", "/api/proxies")
        assert limit == "30/minute"

    def test_batch_endpoints_get_batch_limit(self):
        """Batch endpoints should get stricter rate limit."""
        limit = get_rate_limit_for_endpoint("POST", "/api/pools/batch")
        assert limit == "10/minute"


class TestRequestSizeValidation:
    """Test request size validation."""

    def test_valid_request_size(self):
        """Should allow valid request sizes."""
        is_valid, error = validate_request_size(1024, is_batch=False)
        assert is_valid is True
        assert error == ""

    def test_large_request_rejected(self):
        """Should reject oversized requests."""
        # 20MB request on non-batch endpoint (limit is 10MB)
        is_valid, error = validate_request_size(20 * 1024 * 1024, is_batch=False)
        assert is_valid is False
        assert "exceeds limit" in error

    def test_batch_request_larger_limit(self):
        """Should allow larger sizes for batch operations."""
        # 20MB request on batch endpoint (limit is 50MB)
        is_valid, error = validate_request_size(20 * 1024 * 1024, is_batch=True)
        assert is_valid is True

    def test_no_content_length(self):
        """Should allow requests without Content-Length."""
        is_valid, error = validate_request_size(None, is_batch=False)
        assert is_valid is True
        assert error == ""


class TestCORSConfiguration:
    """Test CORS configuration."""

    def test_default_cors_settings(self):
        """Should have default CORS settings."""
        settings = get_cors_settings()

        assert "allow_origins" in settings
        assert "allow_credentials" in settings
        assert settings["allow_credentials"] is True
        assert "allow_methods" in settings
        assert "GET" in settings["allow_methods"]
        assert "POST" in settings["allow_methods"]

    def test_custom_origins(self):
        """Should support custom origins."""
        custom_origins = ["https://example.com"]
        settings = get_cors_settings(allowed_origins=custom_origins)

        assert settings["allow_origins"] == custom_origins


class TestSecurityHeaders:
    """Test security header generation."""

    def test_security_headers_present(self):
        """Should have all required security headers."""
        headers = create_security_headers()

        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "X-XSS-Protection" in headers

    def test_security_headers_values(self):
        """Should have correct security header values."""
        headers = create_security_headers()

        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"


class TestClientIPExtraction:
    """Test client IP extraction from requests."""

    def test_client_ip_from_direct_connection(self):
        """Should extract IP from direct connection."""

        class MockRequest:
            headers = {}
            client = type("Client", (), {"host": "192.168.1.100"})()

        ip = get_client_ip(MockRequest())
        assert ip == "192.168.1.100"

    def test_client_ip_from_forwarded_for(self):
        """Should extract IP from X-Forwarded-For header."""

        class MockRequest:
            headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
            client = type("Client", (), {"host": "127.0.0.1"})()

        ip = get_client_ip(MockRequest())
        assert ip == "10.0.0.1"

    def test_client_ip_from_real_ip(self):
        """Should extract IP from X-Real-IP header."""

        class MockRequest:
            headers = {"X-Real-IP": "10.0.0.2"}
            client = type("Client", (), {"host": "127.0.0.1"})()

        ip = get_client_ip(MockRequest())
        assert ip == "10.0.0.2"


class TestURLLengthValidation:
    """Test URL length validation."""

    def test_valid_url_length(self):
        """Should allow valid URL lengths."""
        is_valid, error = validate_url_length("https://example.com/api/test")
        assert is_valid is True
        assert error == ""

    def test_url_too_long(self):
        """Should reject URLs that are too long."""
        long_url = "https://example.com/" + "a" * 2100
        is_valid, error = validate_url_length(long_url)
        assert is_valid is False
        assert "too long" in error.lower()

    def test_max_url_length(self):
        """Should allow URLs at exactly 2048 characters."""
        url = "https://example.com/" + "a" * (2048 - len("https://example.com/"))
        is_valid, error = validate_url_length(url)
        assert is_valid is True


class TestConcurrentRequestLimiter:
    """Test concurrent request limiting."""

    def test_acquire_within_limit(self):
        """Should acquire when under the limit."""
        limiter = ConcurrentRequestLimiter()
        acquired, error = limiter.acquire("/api/pools/batch", 10)
        assert acquired is True
        assert error == ""

    def test_acquire_at_limit(self):
        """Should reject when at the limit."""
        limiter = ConcurrentRequestLimiter()
        # Fill up to the limit
        for _ in range(5):
            acquired, _ = limiter.acquire("/api/proxies/batch-test", 5)
            assert acquired is True

        # Should reject now
        acquired, error = limiter.acquire("/api/proxies/batch-test", 5)
        assert acquired is False
        assert "too many" in error.lower()

    def test_release_allows_new_requests(self):
        """Should allow new requests after releasing."""
        limiter = ConcurrentRequestLimiter()
        # Fill up to the limit
        for _ in range(5):
            limiter.acquire("/api/subscriptions/batch-refresh", 5)

        # Release one
        limiter.release("/api/subscriptions/batch-refresh")

        # Should be able to acquire again
        acquired, _ = limiter.acquire("/api/subscriptions/batch-refresh", 5)
        assert acquired is True

    def test_different_paths_independent(self):
        """Should track different paths independently."""
        limiter = ConcurrentRequestLimiter()
        # Fill up one path
        for _ in range(10):
            limiter.acquire("/api/pools/batch", 10)

        # Different path should still work
        acquired, _ = limiter.acquire("/api/proxies/batch-test", 5)
        assert acquired is True

    def test_get_concurrent_count(self):
        """Should return correct concurrent count."""
        limiter = ConcurrentRequestLimiter()
        assert limiter.get_concurrent_count("/api/pools/batch") == 0

        limiter.acquire("/api/pools/batch", 10)
        assert limiter.get_concurrent_count("/api/pools/batch") == 1

        limiter.release("/api/pools/batch")
        assert limiter.get_concurrent_count("/api/pools/batch") == 0


class TestSecurityIntegration:
    """Integration tests for security features."""

    def test_rate_limiter_memory_cleanup(self):
        """Rate limiter should cleanup old entries."""
        limiter = RateLimiter()
        # Force cleanup interval to be very short for testing
        limiter._cleanup_interval = 0
        limiter._last_cleanup = 0  # Force immediate cleanup

        # Add entries with old timestamps (simulate old entries)
        for i in range(5):
            entry = limiter._limits[f"old_key_{i}"]
            entry.timestamps = [time.time() - 7200]  # 2 hours ago

        # Add a recent entry
        limiter.is_limited("recent_key", "60/minute")

        # Trigger cleanup
        limiter._cleanup_old_entries()

        # Old entries should be cleaned up, recent should remain
        assert "recent_key" in limiter._limits
        assert "old_key_0" not in limiter._limits
