from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.models import ProxyNode
from proxypool.settings import AppSettings


def _make_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=tmp_path,
        db_path=tmp_path / "proxies.db",
        output_dir=tmp_path / "output",
        sources_file=tmp_path / "sources.txt",
        singbox_routes_file=tmp_path / "singbox-routes.json",
        singbox_runtime_config_file=tmp_path / "singbox-runtime.json",
        singbox_runtime_log_file=tmp_path / "singbox-runtime.log",
        singbox_binary="sing-box",
        test_url="https://www.cloudflare.com/cdn-cgi/trace",
        api_key="",
        backend_engine="singbox",
        backend_health_check_sec=30,
        backend_auto_restart_max=3,
    )


@pytest.mark.anyio
async def test_published_subscription_crud_and_filtered_export(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    us = ProxyNode(protocol="trojan", host="us.example.com", port=443, raw_link="trojan://us", extra={"password": "p"})
    jp = ProxyNode(protocol="trojan", host="jp.example.com", port=443, raw_link="trojan://jp", extra={"password": "p"})
    storage.upsert_proxy(us)
    storage.upsert_proxy(jp)
    storage.update_test_result(us.normalized_key(), available=True, latency_ms=100, openai_unlocked=True)
    storage.update_test_result(jp.normalized_key(), available=True, latency_ms=120, openai_unlocked=False)
    storage.update_geo(us.normalized_key(), resolved_ip="1.1.1.1", country="US", city="LA")
    storage.update_geo(jp.normalized_key(), resolved_ip="2.2.2.2", country="JP", city="Tokyo")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/published-subscriptions",
            json={
                "name": "US GPT",
                "enabled": True,
                "filters": {"available": "true", "geo_location": "US:LA", "openai_filter": "unlocked"},
            },
        )
        assert create_resp.status_code == 200
        item = create_resp.json()["item"]
        assert item["match_count"] == 1
        assert item["export_url"].endswith(f"/api/published-subscriptions/{item['id']}/subscription")

        export_resp = await client.get(f"/api/published-subscriptions/{item['id']}/subscription")
        assert export_resp.status_code == 200
        assert "trojan://us" in export_resp.text
        assert "trojan://jp" not in export_resp.text

        update_resp = await client.put(
            f"/api/published-subscriptions/{item['id']}",
            json={"filters": {"geo_country": "JP", "openai_filter": "blocked"}},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["item"]["match_count"] == 1

        delete_resp = await client.delete(f"/api/published-subscriptions/{item['id']}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted"] == 1


@pytest.mark.anyio
async def test_published_subscription_can_export_clash_yaml(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    node = ProxyNode(
        protocol="trojan",
        host="us.example.com",
        port=443,
        name="us-node",
        raw_link="trojan://secret@us.example.com:443#us-node",
        extra={"password": "secret", "security": "tls", "sni": "us.example.com"},
    )
    storage.upsert_proxy(node)
    storage.update_test_result(node.normalized_key(), available=True, latency_ms=100, openai_unlocked=True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/published-subscriptions",
            json={
                "name": "Clash",
                "enabled": True,
                "format": "clash",
                "filters": {"available": "true"},
            },
        )
        assert create_resp.status_code == 200
        item = create_resp.json()["item"]
        assert item["format"] == "clash"

        export_resp = await client.get(f"/api/published-subscriptions/{item['id']}/subscription")
        assert export_resp.status_code == 200
        assert "proxies:" in export_resp.text
        assert "proxy-groups:" in export_resp.text
        assert "type: trojan" in export_resp.text
        assert "server: us.example.com" in export_resp.text
        assert "password: secret" in export_resp.text
        assert "MATCH,Proxy" in export_resp.text
