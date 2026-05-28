"""
Security utilities for ProxyPool.
Provides SSRF protection, path traversal prevention, and rate limiting.
"""

from proxypool.security.api_helpers import (
    validate_file_path_or_raise,
    validate_sources_list_or_raise,
    validate_url_or_raise,
    validate_urls_list_or_raise,
)
from proxypool.security.file_validator import (
    PathTraversalError,
    PathValidationError,
    safe_list_directory,
    safe_read_file,
    validate_file_path,
)
from proxypool.security.url_validator import (
    DangerousPortError,
    MetadataEndpointError,
    PrivateIPError,
    SSRFProtectionError,
    URLValidationError,
    is_safe_url,
    sanitize_url_for_logging,
    validate_url,
)

__all__ = [
    "DangerousPortError",
    "MetadataEndpointError",
    # File validation (path traversal protection)
    "PathTraversalError",
    "PathValidationError",
    "PrivateIPError",
    # URL validation (SSRF protection)
    "SSRFProtectionError",
    "URLValidationError",
    "is_safe_url",
    "safe_list_directory",
    "safe_read_file",
    "sanitize_url_for_logging",
    "validate_file_path",
    "validate_file_path_or_raise",
    "validate_sources_list_or_raise",
    "validate_url",
    # API helpers (FastAPI integration)
    "validate_url_or_raise",
    "validate_urls_list_or_raise",
]
