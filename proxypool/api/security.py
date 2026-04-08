from __future__ import annotations

READ_ONLY_ALLOWLIST = {
    ("GET", "/"),
    ("GET", "/api/health"),
    ("GET", "/api/stats"),
    ("GET", "/api/proxies"),
    ("GET", "/api/subscription"),
    ("GET", "/api/backend/status"),
    ("GET", "/api/backend/routes"),
    ("GET", "/api/backend/latency"),
    ("GET", "/api/backend/process-events"),
    ("GET", "/api/subscriptions"),
    ("GET", "/api/subscription-update-proxy"),
}


def is_api_key_required(method: str, path: str) -> bool:
    norm_method = method.upper()
    norm_path = _normalize_path(path)
    key = (norm_method, norm_path)
    if key in READ_ONLY_ALLOWLIST:
        return False
    if norm_method == "GET" and (norm_path == "/api/tasks" or norm_path.startswith("/api/tasks/")):
        return False
    return True


def is_request_authorized(method: str, path: str, request_api_key: str | None, expected_api_key: str | None) -> bool:
    expected = (expected_api_key or "").strip()
    if not expected:
        return True

    if not is_api_key_required(method, path):
        return True

    return (request_api_key or "").strip() == expected


def _normalize_path(path: str) -> str:
    stripped = path.strip()
    return stripped if stripped else "/"
