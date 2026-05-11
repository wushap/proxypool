from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any


class ResinClient:
    """HTTP client for the Resin proxy pool gateway REST API."""

    def __init__(self, base_url: str = "http://127.0.0.1:2260", admin_token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.admin_token = admin_token

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        timeout_sec: float = 10.0,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.admin_token:
            headers["Authorization"] = f"Bearer {self.admin_token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                if not raw.strip():
                    return {"status_code": resp.status}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"status_code": resp.status, "body": raw[:2000]}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            return {"status_code": exc.code, "error": raw[:1000]}
        except Exception as exc:
            return {"status_code": 0, "error": str(exc)[:500]}

    def is_ready(self) -> bool:
        result = self._request("GET", "/healthz", timeout_sec=3.0)
        return result.get("status_code") == 200

    # ---- Subscriptions ----

    def create_subscription(
        self,
        name: str,
        url: str,
        format: str = "uri-lines",
        interval_sec: int = 60,
    ) -> dict[str, Any]:
        body = {
            "name": name,
            "url": url,
            "format": format,
            "interval_sec": interval_sec,
        }
        return self._request("POST", "/api/v1/subscriptions", body)

    def delete_subscription(self, sub_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/subscriptions/{sub_id}")

    def refresh_subscription(self, sub_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/subscriptions/{sub_id}/refresh")

    def list_subscriptions(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/subscriptions")

    def get_subscription(self, sub_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/subscriptions/{sub_id}")

    # ---- Platforms ----

    def create_platform(
        self,
        name: str,
        subscription_ids: list[str] | None = None,
        regex_filters: list[str] | None = None,
        region_filters: list[str] | None = None,
        allocation_policy: str = "BALANCED",
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name}
        if subscription_ids:
            body["subscription_ids"] = subscription_ids
        if regex_filters:
            body["regex_filters"] = regex_filters
        if region_filters:
            body["region_filters"] = region_filters
        if allocation_policy:
            body["allocation_policy"] = allocation_policy
        return self._request("POST", "/api/v1/platforms", body)

    def delete_platform(self, platform_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/platforms/{platform_id}")

    def update_platform(self, platform_id: str, **kwargs: Any) -> dict[str, Any]:
        return self._request("PATCH", f"/api/v1/platforms/{platform_id}", kwargs)

    def list_platforms(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/platforms")

    def get_platform(self, platform_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/platforms/{platform_id}")

    # ---- Nodes ----

    def list_nodes(self, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/nodes?limit={limit}&offset={offset}")

    def get_node(self, node_hash: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/nodes/{node_hash}")

    # ---- System ----

    def get_system_info(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/system/info")

    def get_system_config(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/system/config")

    # ---- Leases ----

    def list_leases(self, platform_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/leases?platform_id={platform_id}")
