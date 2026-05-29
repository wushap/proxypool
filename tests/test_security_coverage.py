"""
Tests for proxypool.security modules: rate_limiter, api_helpers, url_validator, file_validator.
Targets uncovered lines to push coverage higher.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from proxypool.security.api_helpers import (
    validate_file_path_or_raise,
    validate_sources_list_or_raise,
    validate_url_or_raise,
    validate_urls_list_or_raise,
)
from proxypool.security.file_validator import (
    PathTraversalError,
    safe_list_directory,
    safe_read_file,
    validate_file_path,
)
from proxypool.security.rate_limiter import RATE_LIMIT_CONFIG, setup_rate_limiter
from proxypool.security.url_validator import (
    URLValidationError,
    is_safe_url,
    sanitize_url_for_logging,
    validate_url,
)


# ============================================================
# rate_limiter.py  (0% -> target ~100%)
# ============================================================


class TestRateLimiterModule:
    """Tests for proxypool.security.rate_limiter."""

    def test_rate_limit_config_has_all_keys(self):
        expected_keys = {"read", "write", "bulk", "auth_failure", "dangerous"}
        assert set(RATE_LIMIT_CONFIG.keys()) == expected_keys

    def test_rate_limit_config_values_are_strings(self):
        for key, value in RATE_LIMIT_CONFIG.items():
            assert isinstance(value, str), f"{key} value should be string"
            assert "/" in value, f"{key} value should contain '/' (e.g. '60/minute')"

    def test_setup_rate_limiter_creates_limiter(self):
        app = FastAPI()
        limiter = setup_rate_limiter(app)
        assert limiter is not None
        assert app.state.limiter is limiter

    def test_setup_rate_limiter_custom_default_rate(self):
        app = FastAPI()
        limiter = setup_rate_limiter(app, default_rate="30/minute")
        assert limiter is not None

    def test_setup_rate_limiter_registers_exception_handler(self):
        app = FastAPI()
        setup_rate_limiter(app)
        # Verify the exception handler was registered (slowapi adds it)
        # Check that app.state.limiter is set as a basic smoke test
        assert hasattr(app.state, "limiter")


# ============================================================
# api_helpers.py  (22% -> target 100%)
# ============================================================


class TestApiHelpers:
    """Tests for proxypool.security.api_helpers."""

    # --- validate_url_or_raise ---

    def test_validate_url_or_raise_empty_string(self):
        """Empty string should pass (no-op)."""
        validate_url_or_raise("")

    def test_validate_url_or_raise_none_like(self):
        """Falsy string should pass (no-op)."""
        validate_url_or_raise("")

    def test_validate_url_or_raise_safe_url(self):
        """Safe public URL should not raise."""
        validate_url_or_raise("https://example.com/proxies.txt")

    def test_validate_url_or_raise_unsafe_url(self):
        """Unsafe URL should raise HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_url_or_raise("http://127.0.0.1/admin")
        assert exc_info.value.status_code == 400
        assert "URL validation failed" in exc_info.value.detail

    def test_validate_url_or_raise_custom_field_name(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_url_or_raise("http://10.0.0.1/", field_name="target_url")
        assert "target_url" in exc_info.value.detail

    # --- validate_file_path_or_raise ---

    def test_validate_file_path_or_raise_valid(self, tmp_path: Path):
        allowed = [tmp_path]
        (tmp_path / "test.txt").write_text("data")
        result = validate_file_path_or_raise(tmp_path / "test.txt", allowed)
        assert result.exists()

    def test_validate_file_path_or_raise_traversal(self, tmp_path: Path):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_file_path_or_raise("../../../etc/passwd", [tmp_path])
        assert exc_info.value.status_code == 400
        assert "Path validation failed" in exc_info.value.detail

    # --- validate_urls_list_or_raise ---

    def test_validate_urls_list_or_raise_all_safe(self):
        """All safe URLs should pass."""
        urls = ["https://example.com/a.txt", "https://example.com/b.txt"]
        validate_urls_list_or_raise(urls)

    def test_validate_urls_list_or_raise_empty_list(self):
        """Empty list should pass."""
        validate_urls_list_or_raise([])

    def test_validate_urls_list_or_raise_unsafe_url(self):
        from fastapi import HTTPException

        urls = ["https://example.com/a.txt", "http://192.168.1.1/admin"]
        with pytest.raises(HTTPException) as exc_info:
            validate_urls_list_or_raise(urls)
        assert exc_info.value.status_code == 400
        assert "urls[1]" in exc_info.value.detail

    def test_validate_urls_list_or_raise_custom_field(self):
        from fastapi import HTTPException

        urls = ["http://127.0.0.1/"]
        with pytest.raises(HTTPException) as exc_info:
            validate_urls_list_or_raise(urls, field_name="targets")
        assert "targets[0]" in exc_info.value.detail

    # --- validate_sources_list_or_raise ---

    def test_validate_sources_list_or_raise_empty(self):
        validate_sources_list_or_raise([])

    def test_validate_sources_list_or_raise_file_paths(self):
        """File paths should pass (validated at route level)."""
        validate_sources_list_or_raise(["/data/proxies.txt", "configs/sources.txt"])

    def test_validate_sources_list_or_raise_safe_urls(self):
        validate_sources_list_or_raise(["https://example.com/sources.txt"])

    def test_validate_sources_list_or_raise_unsafe_url(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_sources_list_or_raise(
                ["https://example.com/good.txt", "http://10.0.0.1/evil"]
            )
        assert exc_info.value.status_code == 400
        assert "sources[1]" in exc_info.value.detail


# ============================================================
# url_validator.py  (85% -> target 100%)
# ============================================================


class TestURLValidatorExtended:
    """Additional tests for proxypool.security.url_validator to cover missing lines."""

    def test_validate_url_not_a_string(self):
        """Non-string input should raise."""
        with pytest.raises(URLValidationError, match="empty or invalid"):
            validate_url(None)

    def test_validate_url_with_oversized_url(self):
        """URL exceeding 2048 chars should raise."""
        url = "http://example.com/" + "a" * 3000
        with pytest.raises(URLValidationError, match="length"):
            validate_url(url)

    def test_validate_url_no_hostname(self):
        """URL with no hostname should raise."""
        with pytest.raises(URLValidationError, match="no hostname"):
            validate_url("http:///path")

    def test_sanitize_url_for_logging_hides_password(self):
        url = "https://user:secret123@example.com/path"
        sanitized = sanitize_url_for_logging(url)
        assert "secret123" not in sanitized
        assert ":***@" in sanitized

    def test_sanitize_url_for_logging_no_password(self):
        url = "https://example.com/path"
        sanitized = sanitize_url_for_logging(url)
        assert sanitized == url

    def test_sanitize_url_for_logging_returns_original(self):
        """Normal URL without password is returned unchanged."""
        url = "https://example.com/path"
        result = sanitize_url_for_logging(url)
        assert result == url

    def test_sanitize_url_for_logging_with_fragment(self):
        """URL with fragment is returned unchanged (no password)."""
        url = "https://example.com/path#section"
        result = sanitize_url_for_logging(url)
        assert result == url

    def test_is_safe_url_returns_tuple(self):
        is_safe, error = is_safe_url("https://example.com")
        assert is_safe is True
        assert error is None

    def test_is_safe_url_unsafe_returns_error_string(self):
        is_safe, error = is_safe_url("http://127.0.0.1/")
        assert is_safe is False
        assert isinstance(error, str)

    @patch("proxypool.security.url_validator.socket.gethostbyname")
    def test_validate_url_dns_failure(self, mock_dns):
        """DNS resolution failure should raise URLValidationError."""
        import socket

        mock_dns.side_effect = socket.gaierror("Name resolution failed")
        with pytest.raises(URLValidationError, match="DNS resolution failed"):
            validate_url("http://nonexistent.invalid")

    @patch("proxypool.security.url_validator.socket.gethostbyname")
    def test_validate_url_private_ip_via_dns(self, mock_dns):
        """Private IP resolved via DNS should raise PrivateIPError."""
        from proxypool.security.url_validator import PrivateIPError

        mock_dns.return_value = "10.0.0.5"
        with pytest.raises(PrivateIPError):
            validate_url("http://some-hostname.internal")

    @patch("proxypool.security.url_validator.socket.gethostbyname")
    def test_validate_url_metadata_endpoint(self, mock_dns):
        """Metadata endpoint hostname should be blocked."""
        from proxypool.security.url_validator import MetadataEndpointError

        mock_dns.return_value = "169.254.169.254"
        with pytest.raises(MetadataEndpointError):
            validate_url("http://169.254.169.254/latest/meta-data/")

    @patch("proxypool.security.url_validator.socket.gethostbyname")
    def test_validate_url_allow_private_ips(self, mock_dns):
        """Private IPs should be allowed when flag is set."""
        mock_dns.return_value = "192.168.1.100"
        parsed = validate_url("http://some-host.local/", allow_private_ips=True)
        assert parsed is not None

    @patch("proxypool.security.url_validator.socket.gethostbyname")
    def test_validate_url_allow_metadata(self, mock_dns):
        """Metadata endpoints should be allowed when both flags set."""
        mock_dns.return_value = "169.254.169.254"
        parsed = validate_url(
            "http://169.254.169.254/latest/",
            allow_metadata=True,
            allow_private_ips=True,
        )
        assert parsed is not None


# ============================================================
# file_validator.py  (76% -> target higher)
# ============================================================


class TestFileValidatorExtended:
    """Additional tests for proxypool.security.file_validator to cover missing lines."""

    def test_default_allowed_directories(self):
        """validate_file_path with no allowed_directories uses project dirs."""
        # Just ensure it doesn't crash -- the file won't be in allowed dirs
        with pytest.raises(PathTraversalError, match="not within allowed"):
            validate_file_path("/some/nonexistent/path/that/is/not/in/default/dirs")

    def test_path_validation_error_on_unresolvable(self, tmp_path: Path):
        """PathValidationError for paths that cannot be resolved."""
        from proxypool.security.file_validator import PathValidationError

        # Mock Path.resolve to raise OSError to trigger PathValidationError
        with patch.object(Path, "resolve", side_effect=OSError("cannot resolve")):
            with pytest.raises(PathValidationError, match="Cannot resolve"):
                validate_file_path("/some/path", [tmp_path])

    def test_validate_file_path_empty_list_no_restriction(self, tmp_path: Path):
        """Empty allowed_directories list means no restriction."""
        (tmp_path / "open.txt").write_text("open")
        result = validate_file_path(tmp_path / "open.txt", allowed_directories=[])
        assert result.exists()

    def test_safe_read_file_not_found(self, tmp_path: Path):
        """File not found should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            safe_read_file(tmp_path / "nonexistent.txt", [tmp_path])

    def test_safe_read_file_is_directory(self, tmp_path: Path):
        """Reading a directory should raise ValueError."""
        with pytest.raises(ValueError, match="not a file"):
            safe_read_file(tmp_path, [tmp_path])

    def test_safe_list_directory_not_found(self, tmp_path: Path):
        """Listing non-existent directory should return empty list."""
        result = safe_list_directory(tmp_path / "nonexistent", [tmp_path])
        assert result == []

    def test_safe_list_directory_not_a_directory(self, tmp_path: Path):
        """Listing a file (not directory) should raise ValueError."""
        (tmp_path / "file.txt").write_text("data")
        with pytest.raises(ValueError, match="not a directory"):
            safe_list_directory(tmp_path / "file.txt", [tmp_path])

    def test_safe_list_directory_with_pattern(self, tmp_path: Path):
        """safe_list_directory should support glob patterns."""
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "a.txt").write_text("")
        (tmp_path / "data" / "b.py").write_text("")

        py_files = safe_list_directory(tmp_path / "data", [tmp_path], pattern="*.py")
        assert len(py_files) == 1
        assert py_files[0].suffix == ".py"

    def test_validate_file_path_symlink_outside_allowed(self, tmp_path: Path):
        """Symlink pointing outside allowed dir is blocked by dir check."""
        (tmp_path / "allowed").mkdir(exist_ok=True)
        (tmp_path / "secret").write_text("secret")
        (tmp_path / "allowed" / "link").symlink_to(tmp_path / "secret")

        # resolve() follows symlink -> target is outside allowed dir
        with pytest.raises(PathTraversalError):
            validate_file_path(
                tmp_path / "allowed" / "link", [tmp_path / "allowed"]
            )

    def test_validate_file_path_symlink_allowed(self, tmp_path: Path):
        """Symlink should be allowed when allow_symlinks=True."""
        (tmp_path / "allowed").mkdir(exist_ok=True)
        (tmp_path / "target").write_text("secret")
        (tmp_path / "allowed" / "link").symlink_to(tmp_path / "target")

        result = validate_file_path(
            tmp_path / "allowed" / "link", [tmp_path], allow_symlinks=True
        )
        assert result.exists()

    def test_validate_file_path_path_outside_allowed(self, tmp_path: Path):
        """Path outside allowed directories should be rejected."""
        allowed = [tmp_path / "allowed"]
        (tmp_path / "allowed").mkdir(exist_ok=True)
        (tmp_path / "outside").mkdir(exist_ok=True)
        (tmp_path / "outside" / "secret.txt").write_text("secret")

        with pytest.raises(PathTraversalError, match="not within allowed"):
            validate_file_path(tmp_path / "outside" / "secret.txt", allowed)
