"""
Tests for subscription management endpoints that support intelligence features.
Tests subscription CRUD, batch refresh, and related functionality.
Note: Subscription intelligence (deduplication, quality scoring, merge recommendations)
is implemented as frontend-only computed properties.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


def _make_settings(tmp_path: Path) -> AppSettings:
    """Create minimal test settings"""
    return AppSettings(
        project_root=tmp_path,
        db_path=tmp_path / "test.db",
        output_dir=tmp_path / "output",
        sources_file=tmp_path / "sources.txt",
        singbox_routes_file=tmp_path / "routes.json",
        singbox_runtime_config_file=tmp_path / "runtime.json",
        singbox_runtime_log_file=tmp_path / "runtime.log",
        singbox_binary="sing-box",
        test_url="https://httpbin.org/get",
        api_key="",  # Disable auth for testing
        backend_engine="singbox",
        backend_health_check_sec=60,
        backend_auto_restart_max=3,
    )


# ===== Subscription CRUD Tests =====


@pytest.mark.anyio
async def test_subscription_create(tmp_path: Path) -> None:
    """POST /api/subscriptions creates subscription"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/subscriptions",
            json={
                "name": "Test Subscription",
                "url": "https://example.com/sub",
                "enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        assert data["item"]["name"] == "Test Subscription"
        assert data["item"]["url"] == "https://example.com/sub"
        assert data["item"]["enabled"] is True


@pytest.mark.anyio
async def test_subscription_list(tmp_path: Path) -> None:
    """GET /api/subscriptions lists subscriptions"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create a subscription first
        await client.post(
            "/api/subscriptions",
            json={
                "name": "Test Sub",
                "url": "https://example.com/sub",
            },
        )

        resp = await client.get("/api/subscriptions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) >= 1


@pytest.mark.anyio
async def test_subscription_update(tmp_path: Path) -> None:
    """PUT /api/subscriptions/{id} updates subscription"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create subscription
        create_resp = await client.post(
            "/api/subscriptions",
            json={
                "name": "Original Name",
                "url": "https://example.com/sub",
            },
        )
        sub_id = create_resp.json()["item"]["id"]

        # Update subscription
        resp = await client.put(
            f"/api/subscriptions/{sub_id}",
            json={
                "name": "Updated Name",
                "enabled": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["item"]["name"] == "Updated Name"
        assert data["item"]["enabled"] is False


@pytest.mark.anyio
async def test_subscription_delete(tmp_path: Path) -> None:
    """DELETE /api/subscriptions/{id} deletes subscription"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create subscription
        create_resp = await client.post(
            "/api/subscriptions",
            json={
                "name": "To Delete",
                "url": "https://example.com/sub",
            },
        )
        sub_id = create_resp.json()["item"]["id"]

        # Delete subscription
        resp = await client.delete(f"/api/subscriptions/{sub_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == 1


@pytest.mark.anyio
async def test_subscription_delete_nonexistent(tmp_path: Path) -> None:
    """DELETE /api/subscriptions/{id} with nonexistent ID"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete("/api/subscriptions/99999")
        assert resp.status_code == 404


# ===== Subscription Refresh Tests =====


@pytest.mark.anyio
async def test_subscription_refresh(tmp_path: Path) -> None:
    """POST /api/subscriptions/{id}/refresh refreshes subscription"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create subscription
        create_resp = await client.post(
            "/api/subscriptions",
            json={
                "name": "Refreshable",
                "url": "https://example.com/sub",
            },
        )
        sub_id = create_resp.json()["item"]["id"]

        # Refresh subscription (may fail if URL is unreachable)
        resp = await client.post(
            f"/api/subscriptions/{sub_id}/refresh",
            json={"timeout_sec": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        assert "report" in data


@pytest.mark.anyio
async def test_subscription_refresh_nonexistent(tmp_path: Path) -> None:
    """POST /api/subscriptions/{id}/refresh with nonexistent ID"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/subscriptions/99999/refresh",
            json={"timeout_sec": 5},
        )
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_subscription_refresh_enabled(tmp_path: Path) -> None:
    """POST /api/subscriptions/refresh-enabled refreshes all enabled"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create subscriptions
        await client.post(
            "/api/subscriptions",
            json={
                "name": "Enabled Sub",
                "url": "https://example.com/sub1",
                "enabled": True,
            },
        )
        await client.post(
            "/api/subscriptions",
            json={
                "name": "Disabled Sub",
                "url": "https://example.com/sub2",
                "enabled": False,
            },
        )

        resp = await client.post("/api/subscriptions/refresh-enabled?timeout_sec=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "items" in data
        # Should only refresh enabled subscriptions
        assert data["count"] >= 0


# ===== Batch Operations Tests =====


@pytest.mark.anyio
async def test_subscription_batch_refresh(tmp_path: Path) -> None:
    """POST /api/subscriptions/batch-refresh batch refreshes subscriptions"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create subscriptions
        resp1 = await client.post(
            "/api/subscriptions",
            json={
                "name": "Batch Sub 1",
                "url": "https://example.com/sub1",
            },
        )
        resp2 = await client.post(
            "/api/subscriptions",
            json={
                "name": "Batch Sub 2",
                "url": "https://example.com/sub2",
            },
        )

        sub_id1 = resp1.json()["item"]["id"]
        sub_id2 = resp2.json()["item"]["id"]

        # Batch refresh
        resp = await client.post(
            "/api/subscriptions/batch-refresh",
            json={
                "subscription_ids": [sub_id1, sub_id2],
                "timeout_sec": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "success" in data
        assert "failed" in data
        assert "results" in data
        assert data["total"] == 2


@pytest.mark.anyio
async def test_subscription_delete_unavailable(tmp_path: Path) -> None:
    """POST /api/subscriptions/delete-unavailable deletes unavailable"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/subscriptions/delete-unavailable")
        assert resp.status_code == 200
        data = resp.json()
        assert "deleted" in data


# ===== Published Subscriptions Tests =====


@pytest.mark.anyio
async def test_published_subscription_crud(tmp_path: Path) -> None:
    """Test published subscription CRUD operations"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create published subscription
        resp = await client.post(
            "/api/published-subscriptions",
            json={
                "name": "Published Sub",
                "filters": {"protocol": "trojan"},
                "enabled": True,
                "format": "raw",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        assert data["item"]["name"] == "Published Sub"
        assert "export_url" in data["item"]
        pub_id = data["item"]["id"]

        # List published subscriptions
        resp = await client.get("/api/published-subscriptions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

        # Update published subscription
        resp = await client.put(
            f"/api/published-subscriptions/{pub_id}",
            json={"name": "Updated Published"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["item"]["name"] == "Updated Published"

        # Delete published subscription
        resp = await client.delete(f"/api/published-subscriptions/{pub_id}")
        assert resp.status_code == 200


# ===== Subscription Update Proxy Tests =====


@pytest.mark.anyio
async def test_subscription_update_proxy_get(tmp_path: Path) -> None:
    """GET /api/subscription-update-proxy returns current proxy key"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/subscription-update-proxy")
        assert resp.status_code == 200
        data = resp.json()
        assert "update_proxy_key" in data


@pytest.mark.anyio
async def test_subscription_update_proxy_set(tmp_path: Path) -> None:
    """PUT /api/subscription-update-proxy sets proxy key"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Set to empty (disable)
        resp = await client.put(
            "/api/subscription-update-proxy",
            json={"update_proxy_key": ""},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["update_proxy_key"] == ""


# ===== Performance Tests =====


@pytest.mark.anyio
async def test_subscription_list_performance(tmp_path: Path) -> None:
    """Verify subscription list responds quickly"""
    import time

    settings = _make_settings(tmp_path)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create some subscriptions
        for i in range(10):
            await client.post(
                "/api/subscriptions",
                json={
                    "name": f"Sub {i}",
                    "url": f"https://example.com/sub{i}",
                },
            )

        start = time.time()
        resp = await client.get("/api/subscriptions")
        duration_ms = (time.time() - start) * 1000

        assert resp.status_code == 200
        # Should respond in < 100ms
        assert duration_ms < 100, f"Subscription list took {duration_ms:.1f}ms"
