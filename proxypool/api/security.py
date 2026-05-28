"""
Enhanced API Security Module - Authentication, authorization, and rate limiting.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass, field

# Read-only endpoints that don't require authentication
READ_ONLY_ALLOWLIST = {
    ("GET", "/"),
    ("GET", "/api/health"),
    ("GET", "/api/stats"),
    ("GET", "/api/proxies"),
    ("GET", "/api/subscription"),
    ("GET", "/api/backend/status"),
    ("GET", "/api/backend/routes"),
    ("GET", "/api/backend/default-port-range"),
    ("GET", "/api/backend/latency"),
    ("GET", "/api/backend/process-events"),
    ("GET", "/api/subscriptions"),
    ("GET", "/api/subscription-update-proxy"),
}

# High-risk endpoints that MUST require authentication (even if listed elsewhere)
MUST_AUTHENTICATE_ENDPOINTS = {
    # Delete operations
    ("POST", "/api/proxies/delete-unavailable"),
    ("POST", "/api/proxies/delete-selected"),
    ("DELETE", "/api/subscriptions/{subscription_id}"),
    ("DELETE", "/api/published-subscriptions/{subscription_id}"),
    ("DELETE", "/api/pools/{pool_id}"),
    ("DELETE", "/api/http-proxy-endpoints/{endpoint_id}"),
    # Backend control (high-risk operations)
    ("POST", "/api/backend/start"),
    ("POST", "/api/backend/stop"),
    ("POST", "/api/backend/restart"),
    ("POST", "/api/backend/routes"),
    # Proxy import (SSRF risk)
    ("POST", "/api/collector/import-urls"),
    ("POST", "/api/collector/import-files"),
    ("POST", "/api/collector/import-sources"),
    # Gateway test (SSRF risk)
    ("POST", "/api/gateway/http-test"),
    ("POST", "/api/gateway/http-health-check"),
}

# Batch operation endpoints that require throttling
BATCH_OPERATION_ENDPOINTS = {
    "POST": {
        "/api/proxies/batch-delete",
        "/api/proxies/batch-test",
        "/api/pools/batch",
        "/api/subscriptions/batch-refresh",
        "/api/collector/import-urls",
        "/api/collector/import-files",
        "/api/collector/import-sources",
    }
}

# Task ID format validation
TASK_ID_PATTERN = re.compile(r"^[a-f0-9-]{8,64}$", re.IGNORECASE)

# Rate limiting configuration
RATE_LIMIT_DEFAULT = "60/minute"
RATE_LIMIT_BATCH = "10/minute"
RATE_LIMIT_WRITE = "30/minute"

# Request size limits (in bytes)
MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_BATCH_REQUEST_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_URL_LENGTH = 2048  # 2KB URL length limit

# Concurrent request limits for batch operations
CONCURRENT_BATCH_LIMITS = {
    "/api/pools/batch": 10,
    "/api/proxies/batch-test": 5,
    "/api/subscriptions/batch-refresh": 5,
}


@dataclass
class RateLimitEntry:
    """Track rate limiting state for a key."""

    timestamps: list[float] = field(default_factory=list)

    def is_limited(self, window_sec: float, max_requests: int) -> bool:
        """Check if rate limit is exceeded."""
        now = time.time()
        # Remove old entries outside the window
        self.timestamps = [ts for ts in self.timestamps if now - ts < window_sec]
        return len(self.timestamps) >= max_requests

    def record(self) -> None:
        """Record a new request."""
        self.timestamps.append(time.time())


class RateLimiter:
    """In-memory rate limiter for API endpoints."""

    def __init__(self) -> None:
        self._limits: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._last_cleanup = time.time()
        self._cleanup_interval = 60.0  # Cleanup every minute

    def _cleanup_old_entries(self) -> None:
        """Periodically cleanup old entries to prevent memory leaks."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        # Remove entries older than 1 hour
        cutoff = now - 3600
        keys_to_remove = []
        for key, entry in self._limits.items():
            entry.timestamps = [ts for ts in entry.timestamps if ts > cutoff]
            if not entry.timestamps:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self._limits[key]

    def is_limited(self, key: str, limit_str: str) -> tuple[bool, int, int]:
        """
        Check if a request should be rate limited.

        Args:
            key: Rate limit key (e.g., IP, path)
            limit_str: Rate limit string (e.g., "60/minute")

        Returns:
            Tuple of (is_limited, remaining, retry_after_sec)
        """
        self._cleanup_old_entries()

        # Parse limit string (e.g., "60/minute", "10/hour")
        try:
            count_str, period = limit_str.split("/")
            max_requests = int(count_str)
        except (ValueError, AttributeError):
            max_requests = 60
            period = "minute"

        # Calculate window in seconds
        window_map = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
        window_sec = window_map.get(period, 60)

        entry = self._limits[key]
        if entry.is_limited(window_sec, max_requests):
            # Calculate retry after time
            if entry.timestamps:
                oldest = min(entry.timestamps)
                retry_after = int(window_sec - (time.time() - oldest)) + 1
            else:
                retry_after = 1
            remaining = max(0, max_requests - len(entry.timestamps))
            return True, remaining, retry_after

        entry.record()
        remaining = max(0, max_requests - len(entry.timestamps))
        return False, remaining, 0

    def get_rate_limit_headers(self, key: str, limit_str: str, remaining: int) -> dict[str, str]:
        """Generate rate limit headers for the response."""
        try:
            count_str, _ = limit_str.split("/")
            max_requests = int(count_str)
        except (ValueError, AttributeError):
            max_requests = 60

        return {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Policy": limit_str,
        }


class APIKeyManager:
    """Manage API keys with rotation support."""

    def __init__(self) -> None:
        self._keys: dict[str, dict] = {}  # key_hash -> {key, created_at, expires_at, rotated_at}
        self._rotation_history: list[dict] = []

    def generate_key(self, prefix: str = "pp") -> str:
        """Generate a new API key with optional prefix."""
        random_part = secrets.token_urlsafe(32)
        return f"{prefix}_{random_part}"

    def hash_key(self, api_key: str) -> str:
        """Hash an API key for secure storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def register_key(self, api_key: str, expires_in_days: int = 90, description: str = "") -> dict:
        """Register a new API key."""
        key_hash = self.hash_key(api_key)
        now = time.time()
        self._keys[key_hash] = {
            "key_hash": key_hash,
            "created_at": now,
            "expires_at": now + (expires_in_days * 86400) if expires_in_days > 0 else 0,
            "rotated_at": None,
            "description": description,
            "active": True,
        }
        return self._keys[key_hash]

    def validate_key(self, api_key: str) -> bool:
        """Validate an API key is active and not expired."""
        key_hash = self.hash_key(api_key)
        key_info = self._keys.get(key_hash)
        if not key_info:
            return False
        if not key_info.get("active", False):
            return False
        expires_at = key_info.get("expires_at", 0)
        if expires_at > 0 and time.time() > expires_at:
            return False
        return True

    def rotate_key(self, old_api_key: str, new_expires_in_days: int = 90) -> tuple[str, dict]:
        """
        Rotate an API key - deactivate old, return new key info.

        Returns:
            Tuple of (new_api_key, key_info)
        """
        old_hash = self.hash_key(old_api_key)

        # Generate new key
        new_key = self.generate_key()
        new_info = self.register_key(new_key, new_expires_in_days, "rotated")

        # Deactivate old key
        if old_hash in self._keys:
            self._keys[old_hash]["active"] = False
            self._keys[old_hash]["rotated_at"] = time.time()

        # Record rotation history
        self._rotation_history.append(
            {
                "old_key_hash": old_hash[:16] + "...",  # Partial hash for audit
                "new_key_hash": new_info["key_hash"][:16] + "...",
                "rotated_at": time.time(),
            }
        )

        return new_key, new_info

    def revoke_key(self, api_key: str) -> bool:
        """Revoke an API key."""
        key_hash = self.hash_key(api_key)
        if key_hash in self._keys:
            self._keys[key_hash]["active"] = False
            return True
        return False

    def list_keys(self, include_inactive: bool = False) -> list[dict]:
        """List all registered keys (with hashes partially masked)."""
        result = []
        for key_hash, info in self._keys.items():
            if not include_inactive and not info.get("active", False):
                continue
            result.append(
                {
                    "key_prefix": key_hash[:8] + "...",
                    "created_at": info.get("created_at"),
                    "expires_at": info.get("expires_at"),
                    "active": info.get("active", False),
                    "description": info.get("description", ""),
                }
            )
        return result


def normalize_path(path: str) -> str:
    """
    Normalize path (handle trailing slashes, multiple slashes, etc.)
    """
    stripped = path.strip()
    # Remove trailing slash (except for root path)
    if stripped != "/" and stripped.endswith("/"):
        stripped = stripped.rstrip("/")
    return stripped if stripped else "/"


def is_batch_operation(method: str, path: str) -> bool:
    """
    Check if an endpoint is a batch operation that requires throttling.

    Args:
        method: HTTP method
        path: Request path

    Returns:
        True if it's a batch operation, False otherwise
    """
    norm_method = method.upper()
    norm_path = normalize_path(path)
    return norm_path in BATCH_OPERATION_ENDPOINTS.get(norm_method, set())


def get_rate_limit_for_endpoint(method: str, path: str) -> str:
    """
    Get the appropriate rate limit for an endpoint.

    Args:
        method: HTTP method
        path: Request path

    Returns:
        Rate limit string (e.g., "60/minute")
    """
    if is_batch_operation(method, path):
        return RATE_LIMIT_BATCH

    norm_method = method.upper()
    if norm_method in ("POST", "PUT", "DELETE", "PATCH"):
        return RATE_LIMIT_WRITE

    return RATE_LIMIT_DEFAULT


def is_api_key_required(method: str, path: str) -> bool:
    """
    Determine if endpoint requires API key authentication.

    Priority:
    1. MUST_AUTHENTICATE_ENDPOINTS (highest - always requires auth)
    2. READ_ONLY_ALLOWLIST (no auth required)
    3. Task list queries (GET /api/tasks, GET /api/tasks/{id})
    4. All other operations require auth
    """
    norm_method = method.upper()
    norm_path = normalize_path(path)
    key = (norm_method, norm_path)

    # 1. High-risk endpoints (highest priority)
    if key in MUST_AUTHENTICATE_ENDPOINTS:
        return True

    # 2. Read-only whitelist
    if key in READ_ONLY_ALLOWLIST:
        return False

    # 3. Task list queries (GET /api/tasks) don't require auth
    # But stop/delete tasks require auth
    if norm_method == "GET" and (norm_path == "/api/tasks" or norm_path.startswith("/api/tasks/")):
        # But stop/delete tasks require auth
        if "/stop" in norm_path or norm_method in ("DELETE", "PUT", "PATCH"):
            return True
        return False

    # 4. All other operations require auth
    return True


def is_request_authorized(
    method: str,
    path: str,
    request_api_key: str | None,
    expected_api_key: str | None,
) -> bool:
    """
    Verify request is authorized.

    Args:
        method: HTTP method
        path: Request path
        request_api_key: API key from request
        expected_api_key: Expected API key from config

    Returns:
        True if authorized, False otherwise
    """
    expected = (expected_api_key or "").strip()

    # If no API key configured, allow all requests
    if not expected:
        return True

    # Check if endpoint requires authentication
    if not is_api_key_required(method, path):
        return True

    # Timing-safe comparison
    provided = (request_api_key or "").strip()
    if not provided:
        return False

    return hmac.compare_digest(provided, expected)


def validate_task_id(task_id: str) -> bool:
    """
    Validate task ID format.

    Task IDs are UUIDs in hex format: 8-64 hex characters with optional dashes.

    Args:
        task_id: Task ID to validate

    Returns:
        True if valid format, False otherwise
    """
    if not task_id or not isinstance(task_id, str):
        return False
    return bool(TASK_ID_PATTERN.match(task_id.strip()))


# ===== CORS Configuration =====


def get_cors_settings(allowed_origins: list[str] | None = None) -> dict:
    """
    Get CORS middleware settings.

    Args:
        allowed_origins: List of allowed origins. If None, uses default development origins.

    Returns:
        Dict of CORS middleware settings
    """
    if allowed_origins is None:
        # Default development origins
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:5173",  # Vite dev server
            "http://localhost:5174",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ]

    return {
        "allow_origins": allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "allow_headers": [
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "Accept",
            "Origin",
            "User-Agent",
            "X-Requested-With",
        ],
        "expose_headers": [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Policy",
        ],
        "max_age": 600,  # Cache preflight requests for 10 minutes
    }


def validate_request_size(content_length: int | None, is_batch: bool = False) -> tuple[bool, str]:
    """
    Validate request body size against limits.

    Args:
        content_length: Content-Length header value
        is_batch: Whether this is a batch operation request

    Returns:
        Tuple of (is_valid, error_message)
    """
    if content_length is None:
        return True, ""

    max_size = MAX_BATCH_REQUEST_SIZE if is_batch else MAX_REQUEST_BODY_SIZE
    if content_length > max_size:
        max_mb = max_size / (1024 * 1024)
        current_mb = content_length / (1024 * 1024)
        return False, f"Request body too large: {current_mb:.1f}MB exceeds limit of {max_mb:.0f}MB"

    return True, ""


def get_client_ip(request) -> str:
    """
    Extract client IP from request, considering proxy headers.

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address
    """
    # Check for X-Forwarded-For header (common with reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (original client)
        return forwarded_for.split(",")[0].strip()

    # Check for X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


def create_security_headers() -> dict[str, str]:
    """
    Create security headers for API responses.

    Returns:
        Dict of security headers
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Pragma": "no-cache",
    }


def get_cache_headers(method: str, path: str) -> dict[str, str]:
    """
    Get appropriate caching headers based on endpoint type.

    Args:
        method: HTTP method
        path: Request path

    Returns:
        Dict of cache headers
    """
    # Static assets - long cache with immutable
    if path.startswith("/assets") or path.endswith((".js", ".css", ".png", ".jpg", ".ico", ".svg")):
        return {
            "Cache-Control": "public, max-age=86400, immutable",
            "ETag": None,
        }

    # Health check and status endpoints - no cache
    if path in ("/api/health", "/api/system/health", "/api/backend/status"):
        return {
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "Pragma": "no-cache",
        }

    # GET requests for read-only data - cache with must-revalidate for ETag support
    if method == "GET" and path.startswith("/api/"):
        # Proxies, pools, subscriptions lists - short cache with ETag support
        if any(
            endpoint in path for endpoint in ["/api/proxies", "/api/pools", "/api/subscriptions"]
        ):
            return {
                "Cache-Control": "private, max-age=30, must-revalidate, stale-while-revalidate=10",
                "Vary": "X-API-Key",
            }

        # Config, settings - medium cache with ETag support
        if any(endpoint in path for endpoint in ["/api/config", "/api/settings"]):
            return {
                "Cache-Control": "private, max-age=60, must-revalidate",
                "Vary": "X-API-Key",
            }

        # Default API cache with ETag support
        return {
            "Cache-Control": "private, max-age=10, must-revalidate",
            "Vary": "X-API-Key",
        }

    # Write operations - no cache
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
        "Pragma": "no-cache",
    }


def validate_url_length(url: str) -> tuple[bool, str]:
    """
    Validate URL length against limits.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(url) > MAX_URL_LENGTH:
        return False, f"URL too long: {len(url)} characters exceeds limit of {MAX_URL_LENGTH}"
    return True, ""


class ConcurrentRequestLimiter:
    """Track and limit concurrent requests for specific endpoints."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)

    def acquire(self, path: str, max_concurrent: int) -> tuple[bool, str]:
        """
        Try to acquire a slot for a concurrent request.

        Args:
            path: Request path
            max_concurrent: Maximum concurrent requests allowed

        Returns:
            Tuple of (acquired, error_message)
        """
        if self._counts[path] >= max_concurrent:
            return False, f"Too many concurrent requests to {path}. Maximum: {max_concurrent}"
        self._counts[path] += 1
        return True, ""

    def release(self, path: str) -> None:
        """
        Release a slot after request completes.

        Args:
            path: Request path
        """
        if self._counts[path] > 0:
            self._counts[path] -= 1

    def get_concurrent_count(self, path: str) -> int:
        """Get current concurrent request count for a path."""
        return self._counts[path]
