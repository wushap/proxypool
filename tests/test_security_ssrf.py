"""
SSRF Security Tests - Validates Server-Side Request Forgery protection.
"""
from __future__ import annotations

import pytest

from proxypool.security.url_validator import (
    DangerousPortError,
    MetadataEndpointError,
    PrivateIPError,
    SSRFProtectionError,
    URLValidationError,
    is_safe_url,
    validate_url,
)


class TestSSRFProtection:
    """SSRF protection test suite."""

    # ---- Allowed URLs ----

    def test_allow_public_https(self):
        url = "https://www.example.com/api/data"
        is_safe, error = is_safe_url(url)
        assert is_safe is True
        assert error is None

    def test_allow_public_http(self):
        url = "http://httpbin.org/get"
        is_safe, error = is_safe_url(url)
        assert is_safe is True

    # ---- Private IP Detection ----

    def test_block_loopback_127(self):
        url = "http://127.0.0.1/admin"
        is_safe, error = is_safe_url(url)
        assert is_safe is False
        assert "private" in error.lower()

    def test_block_loopback_localhost(self):
        url = "http://localhost/metadata"
        is_safe, error = is_safe_url(url)
        assert is_safe is False

    def test_block_private_10_x(self):
        url = "http://10.0.0.1/internal"
        is_safe, error = is_safe_url(url)
        assert is_safe is False

    def test_block_private_172_16(self):
        url = "http://172.16.0.1/api"
        is_safe, error = is_safe_url(url)
        assert is_safe is False

    def test_block_private_192_168(self):
        url = "http://192.168.1.1/admin"
        is_safe, error = is_safe_url(url)
        assert is_safe is False

    # ---- Cloud Metadata Endpoint Detection ----

    def test_block_aws_metadata(self):
        url = "http://169.254.169.254/latest/meta-data/"
        is_safe, error = is_safe_url(url)
        assert is_safe is False
        assert "metadata" in error.lower()

    def test_block_gcp_metadata(self):
        url = "http://metadata.google.internal/computeMetadata/v1/"
        is_safe, error = is_safe_url(url)
        assert is_safe is False

    # ---- Dangerous Port Detection ----

    def test_block_ssh_port(self):
        url = "http://example.com:22/"
        is_safe, error = is_safe_url(url)
        assert is_safe is False
        assert "port 22" in error.lower()

    def test_block_redis_port(self):
        url = "http://example.com:6379/"
        is_safe, error = is_safe_url(url)
        assert is_safe is False

    def test_block_mongodb_port(self):
        url = "http://example.com:27017/"
        is_safe, error = is_safe_url(url)
        assert is_safe is False

    # ---- URL Format Validation ----

    def test_block_empty_url(self):
        is_safe, error = is_safe_url("")
        assert is_safe is False
        assert "empty" in error.lower()

    def test_block_invalid_scheme(self):
        url = "ftp://example.com/file"
        is_safe, error = is_safe_url(url)
        assert is_safe is False
        assert "scheme" in error.lower()

    def test_block_file_scheme(self):
        url = "file:///etc/passwd"
        is_safe, error = is_safe_url(url)
        assert is_safe is False

    def test_block_oversized_url(self):
        url = "http://example.com/" + "a" * 3000
        is_safe, error = is_safe_url(url)
        assert is_safe is False
        assert "length" in error.lower()

    # ---- Exception Type Tests ----

    def test_validate_url_raises_private_ip(self):
        with pytest.raises(PrivateIPError):
            validate_url("http://127.0.0.1/")

    def test_validate_url_raises_metadata(self):
        with pytest.raises(MetadataEndpointError):
            validate_url("http://169.254.169.254/")

    def test_validate_url_raises_dangerous_port(self):
        with pytest.raises(DangerousPortError):
            validate_url("http://example.com:22/")

    def test_validate_url_raises_invalid_format(self):
        with pytest.raises(URLValidationError):
            validate_url("not-a-url")
