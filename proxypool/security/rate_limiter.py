"""
Rate Limiting Module - Provides API rate limiting using slowapi.

This module configures rate limiting for the FastAPI application
to prevent abuse and暴力破解 attacks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

if TYPE_CHECKING:
    from fastapi import FastAPI

# Rate limit configurations
RATE_LIMIT_CONFIG = {
    # Read operations - generous
    "read": "120/minute",
    # Write operations - strict
    "write": "20/minute",
    # Bulk operations - stricter
    "bulk": "5/minute",
    # Authentication failures - very strict (anti-brute-force)
    "auth_failure": "5/minute",
    # Dangerous operations - very strict
    "dangerous": "3/minute",
}


def setup_rate_limiter(
    app: FastAPI,
    default_rate: str = "60/minute",
    storage_uri: str = "memory://",
) -> Limiter:
    """
    Configure rate limiter for FastAPI application.

    Args:
        app: FastAPI application instance
        default_rate: Default rate limit (default: 60/minute)
        storage_uri: Storage backend URI (default: memory:// for single instance)

    Returns:
        Limiter instance
    """
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[default_rate],
        storage_uri=storage_uri,
    )

    # Add exception handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    return limiter
