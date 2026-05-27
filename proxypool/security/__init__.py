"""
Security utilities for ProxyPool.
Provides SSRF protection, path traversal prevention, and rate limiting.
"""
from proxypool.security.url_validator import (
    SSRFProtectionError,
    PrivateIPError,
    MetadataEndpointError,
    DangerousPortError,
    URLValidationError,
    validate_url,
    is_safe_url,
    sanitize_url_for_logging,
)
from proxypool.security.file_validator import (
    PathTraversalError,
    PathValidationError,
    validate_file_path,
    safe_read_file,
    safe_list_directory,
)
from proxypool.security.api_helpers import (
    validate_url_or_raise,
    validate_file_path_or_raise,
    validate_urls_list_or_raise,
    validate_sources_list_or_raise,
)

__all__ = [
    # URL validation (SSRF protection)
    "SSRFProtectionError",
    "PrivateIPError",
    "MetadataEndpointError",
    "DangerousPortError",
    "URLValidationError",
    "validate_url",
    "is_safe_url",
    "sanitize_url_for_logging",
    # File validation (path traversal protection)
    "PathTraversalError",
    "PathValidationError",
    "validate_file_path",
    "safe_read_file",
    "safe_list_directory",
    # API helpers (FastAPI integration)
    "validate_url_or_raise",
    "validate_file_path_or_raise",
    "validate_urls_list_or_raise",
    "validate_sources_list_or_raise",
]
