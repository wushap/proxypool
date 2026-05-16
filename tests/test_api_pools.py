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
        mihomo_binary="mihomo",
        mihomo_runtime_dir=tmp_path / "runtime" / "mihomo",
    )


@pytest.mark.anyio
async def test_pool_crud_endpoints(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    proxy = ProxyNode(protocol="trojan", host="us.example.com", port=443, raw_link="trojan://us", extra={"password": "p"})
    storage.upsert_proxy(proxy)
    storage.update_test_result(proxy.normalized_key(), available=True, latency_ms=100)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create pool
        resp = await client.post("/api/pools", json={"name": "my-pool", "filters": {"available": "true"}})
        assert resp.status_code == 200
        data = resp.json()
        pool = data["item"]
        assert pool["name"] == "my-pool"
        assert pool["status"] == "stopped"
        pool_id = pool["id"]

        # List pools
        resp = await client.get("/api/pools")
        assert resp.status_code == 200
        pools = resp.json()["items"]
        assert len(pools) >= 1

        # Get pool
        resp = await client.get(f"/api/pools/{pool_id}")
        assert resp.status_code == 200
        assert resp.json()["item"]["name"] == "my-pool"

        # Update pool
        resp = await client.put(f"/api/pools/{pool_id}", json={"name": "renamed-pool"})
        assert resp.status_code == 200
        assert resp.json()["item"]["name"] == "renamed-pool"

        # Delete pool
        resp = await client.delete(f"/api/pools/{pool_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify deleted
        resp = await client.get(f"/api/pools/{pool_id}")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_pool_not_found(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/pools/999")
        assert resp.status_code == 404

        resp = await client.delete("/api/pools/999")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_pool_create_with_all_filters(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/pools", json={
            "name": "filtered-pool",
            "filters": {
                "available": "true",
                "protocol": "trojan",
                "geo_country": "US",
                "openai_filter": "unlocked",
                "ip_purity_filter": "residential",
                "latency_min": "50",
                "latency_max": "500",
                "freshness_hours": "24",
            },
        })
        assert resp.status_code == 200
        pool = resp.json()["item"]
        assert pool["filters"]["latency_min"] == "50"
        assert pool["filters"]["latency_max"] == "500"
        assert pool["filters"]["freshness_hours"] == "24"


@pytest.mark.anyio
async def test_resin_status_endpoint(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/resin/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert data["running"] is False


@pytest.mark.anyio
async def test_resin_info_when_not_running(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/resin/info")
        assert resp.status_code == 503


@pytest.mark.anyio
async def test_chain_status_uses_persisted_filters(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    app.state.storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/status")

    assert resp.status_code == 200
    assert resp.json()["front_pool"]["regex_filters"] == ["front-.*"]


@pytest.mark.anyio
async def test_chain_pool_update_accepts_empty_filters_list(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chain/pools/front")

    assert resp.status_code == 200
    assert resp.json()["front_pool"]["regex_filters"] == []


@pytest.mark.anyio
async def test_app_exposes_chain_instance_manager(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    assert hasattr(app.state, "chain_instance_manager")
    assert app.state.chain_instance_manager.backend.backend_type == "mihomo"


@pytest.mark.anyio
async def test_pool_chain_config_round_trip(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/pools", json={"name": "pool-a"})
        pool_id = create_resp.json()["item"]["id"]

        resp = await client.put(
            f"/api/pools/{pool_id}/chain",
            json={
                "chain_enabled": True,
                "sticky_ttl_sec": 7200,
                "session_missing_action": "REJECT",
                "session_header_names": ["X-ProxyPool-Session"],
                "session_query_param_names": ["session"],
                "gateway_path_prefix": "/proxy/pool-a",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["item"]["chain_enabled"] is True

        resp = await client.get(f"/api/pools/{pool_id}/chain")
        assert resp.status_code == 200
        assert resp.json()["item"]["sticky_ttl_sec"] == 7200
        assert resp.json()["item"]["gateway_path_prefix"] == "/proxy/pool-a"


@pytest.mark.anyio
async def test_pool_chain_instance_lifecycle(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    front = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1")
    exit_node = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="exit-1")
    storage.upsert_proxy(front)
    storage.upsert_proxy(exit_node)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/pools", json={"name": "pool-a"})
        pool_id = create_resp.json()["item"]["id"]

        resp = await client.post(
            f"/api/pools/{pool_id}/chain/instances",
            json={
                "instance_id": "chain-a",
                "front_node_key": front.normalized_key(),
                "exit_node_key": exit_node.normalized_key(),
                "listen": "127.0.0.1",
                "port": 18080,
                "inbound_type": "http",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["item"]["instance_id"] == "chain-a"

        resp = await client.get(f"/api/pools/{pool_id}/chain/instances")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["instance_id"] == "chain-a"
