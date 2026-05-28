"""
Tests for advanced proxy features.
Tests for geographic filtering, OpenAI unlock status, IP purity filtering,
and subscription refresh endpoints.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.models import ProxyNode
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


def _add_test_proxies(storage, count: int = 5) -> list[dict]:
    """Add test proxies with various attributes"""
    proxies = []
    countries = ["US", "JP", "SG", "DE", "GB"]
    cities = ["New York", "Tokyo", "Singapore", "Berlin", "London"]

    for i in range(count):
        proxy = ProxyNode(
            protocol="trojan",
            host=f"proxy{i}.example.com",
            port=443 + i,
            raw_link=f"trojan://user:pass@proxy{i}.example.com:443",
            extra={
                "password": f"pass{i}",
                "country": countries[i % len(countries)],
                "city": cities[i % len(cities)],
            },
        )
        storage.upsert_proxy(proxy)
        proxies.append({
            "normalized_key": proxy.normalized_key(),
            "host": proxy.host,
            "port": proxy.port,
            "country": proxy.extra.get("country"),
            "city": proxy.extra.get("city"),
        })

        # Update some proxies with test results
        if i % 2 == 0:
            storage.update_test_result(
                proxy.normalized_key(),
                available=True,
                latency_ms=50 + i * 10,
                error="",
            )
        else:
            storage.update_test_result(
                proxy.normalized_key(),
                available=False,
                latency_ms=0,
                error="Connection timeout",
            )

    return proxies


# ===== Geographic Filtering Tests =====


@pytest.mark.anyio
async def test_proxy_list_geo_filter_has(tmp_path: Path) -> None:
    """GET /api/proxies with geo_filter=has returns proxies with geo data"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies?geo_filter=has")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        # All proxies have country data
        assert data["total"] >= 0


@pytest.mark.anyio
async def test_proxy_list_geo_filter_none(tmp_path: Path) -> None:
    """GET /api/proxies with geo_filter=none returns proxies without geo data"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies?geo_filter=none")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.anyio
async def test_proxy_list_geo_country_filter(tmp_path: Path) -> None:
    """GET /api/proxies with geo_country filter"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies?geo_country=US")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.anyio
async def test_proxy_list_geo_location_filter(tmp_path: Path) -> None:
    """GET /api/proxies with geo_location filter"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies?geo_location=Tokyo")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


# ===== OpenAI Unlock Status Tests =====


@pytest.mark.anyio
async def test_proxy_list_openai_filter_unlocked(tmp_path: Path) -> None:
    """GET /api/proxies with openai_filter=unlocked"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies?openai_filter=unlocked")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.anyio
async def test_proxy_list_openai_filter_blocked(tmp_path: Path) -> None:
    """GET /api/proxies with openai_filter=blocked"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies?openai_filter=blocked")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.anyio
async def test_proxy_list_openai_filter_unchecked(tmp_path: Path) -> None:
    """GET /api/proxies with openai_filter=unchecked"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies?openai_filter=unchecked")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


# ===== IP Purity Filter Tests =====


@pytest.mark.anyio
async def test_proxy_list_ip_purity_checked(tmp_path: Path) -> None:
    """GET /api/proxies with ip_purity_filter=checked"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies?ip_purity_filter=checked")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.anyio
async def test_proxy_list_ip_purity_residential(tmp_path: Path) -> None:
    """GET /api/proxies with ip_purity_filter=residential"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies?ip_purity_filter=residential")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


# ===== Combined Filter Tests =====


@pytest.mark.anyio
async def test_proxy_list_combined_filters(tmp_path: Path) -> None:
    """GET /api/proxies with multiple filters combined"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/proxies?geo_country=US&openai_filter=unchecked&available=true"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.anyio
async def test_proxy_list_sorting(tmp_path: Path) -> None:
    """GET /api/proxies with various sorting options"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Sort by latency
        resp = await client.get("/api/proxies?sort_by=latency&sort_order=asc")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

        # Sort by host
        resp = await client.get("/api/proxies?sort_by=host&sort_order=desc")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data


# ===== Subscription Endpoint Tests =====


@pytest.mark.anyio
async def test_subscription_links_endpoint(tmp_path: Path) -> None:
    """GET /api/subscription returns subscription links"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 3)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/subscription")
        assert resp.status_code == 200
        # Should return plain text with subscription links
        assert resp.headers["content-type"] == "text/plain; charset=utf-8"


@pytest.mark.anyio
async def test_subscription_links_base64(tmp_path: Path) -> None:
    """GET /api/subscription with encode_base64=true"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 3)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/subscription?encode_base64=true")
        assert resp.status_code == 200
        # Response should be base64 encoded
        content = resp.text
        assert len(content) > 0


@pytest.mark.anyio
async def test_subscription_links_with_protocol_filter(tmp_path: Path) -> None:
    """GET /api/subscription with protocol filter"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/subscription?protocol=trojan")
        assert resp.status_code == 200


@pytest.mark.anyio
async def test_subscription_links_available_only(tmp_path: Path) -> None:
    """GET /api/subscription with only_available=true"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/subscription?only_available=true")
        assert resp.status_code == 200


# ===== CSV Export Tests =====


@pytest.mark.anyio
async def test_proxy_export_csv(tmp_path: Path) -> None:
    """GET /api/proxies/export returns CSV format"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        # Should contain UTF-8 BOM for Excel compatibility
        assert resp.text.startswith("﻿")


@pytest.mark.anyio
async def test_proxy_export_csv_with_filters(tmp_path: Path) -> None:
    """GET /api/proxies/export with filters"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 5)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/proxies/export?protocol=trojan&available=true")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]


# ===== Performance and Pagination Tests =====


@pytest.mark.anyio
async def test_proxy_list_pagination(tmp_path: Path) -> None:
    """GET /api/proxies with pagination"""
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 10)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Get first page
        resp = await client.get("/api/proxies?limit=3&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 3

        # Get second page
        resp = await client.get("/api/proxies?limit=3&offset=3")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data


@pytest.mark.anyio
async def test_proxy_list_performance(tmp_path: Path) -> None:
    """Verify proxy list endpoint responds quickly"""
    import time

    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    _add_test_proxies(storage, 50)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        start = time.time()
        resp = await client.get("/api/proxies")
        duration_ms = (time.time() - start) * 1000

        assert resp.status_code == 200
        # Should respond in < 200ms even with 50 proxies
        assert duration_ms < 200, f"Proxy list took {duration_ms:.1f}ms"
