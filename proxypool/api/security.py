"""
Enhanced API Security Module - Authentication and authorization.
"""
from __future__ import annotations

import hmac
import re

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

# Task ID format validation
TASK_ID_PATTERN = re.compile(r"^[a-f0-9-]{8,64}$", re.IGNORECASE)


def normalize_path(path: str) -> str:
    """
    Normalize path (handle trailing slashes, multiple slashes, etc.)
    """
    stripped = path.strip()
    # Remove trailing slash (except for root path)
    if stripped != "/" and stripped.endswith("/"):
        stripped = stripped.rstrip("/")
    return stripped if stripped else "/"


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
    if norm_method == "GET" and (
        norm_path == "/api/tasks" or norm_path.startswith("/api/tasks/")
    ):
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
