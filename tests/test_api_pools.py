from __future__ import annotations

import socket
from pathlib import Path
import asyncio
from urllib.parse import urlsplit

import httpx
import pytest

import proxypool.api.app as api_app
from proxypool.api.app import create_app
from proxypool.models import ProxyNode
from proxypool.settings import AppSettings


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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
        http_gateway_default_host="127.0.0.1",
        http_gateway_default_port=8899,
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
        assert "resin_subscription_id" not in pool
        assert "resin_platform_id" not in pool
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
                "route_mode_filter": "direct",
                "protocol": "trojan",
                "geo_countries": ["US", "JP"],
                "openai_filter": "unlocked",
                "ip_purity_filter": "residential",
                "latency_min": "50",
                "latency_max": "500",
                "freshness_hours": "24",
            },
        })
        assert resp.status_code == 200
        pool = resp.json()["item"]
        assert pool["filters"]["route_mode_filter"] == "direct"
        assert pool["filters"]["geo_countries"] == ["US", "JP"]
        assert pool["filters"]["latency_min"] == "50"
        assert pool["filters"]["latency_max"] == "500"
        assert pool["filters"]["freshness_hours"] == "24"


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
async def test_http_gateway_config_api_round_trip(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/pools", json={"name": "pool-a"})
        pool_id = create_resp.json()["item"]["id"]
        endpoint_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={
                "name": "pool-a",
                "listen_host": "127.0.0.1",
                "listen_port": 18899,
                "hop_pool_ids": [pool_id],
            },
        )
        endpoint_id = endpoint_resp.json()["item"]["id"]

        put_resp = await client.put(
            "/api/gateway/http-config",
            json={
                "enabled": True,
                "listen_host": "127.0.0.1",
                "listen_port": 18899,
                "endpoint_id": endpoint_id,
                "default_pool_id": pool_id,
                "sticky_ttl_sec": 7200,
                "session_missing_action": "RANDOM",
                "http_session_header_names": ["X-ProxyPool-Session"],
                "http_session_query_names": ["session"],
                "connect_session_header_names": ["X-ProxyPool-Session"],
            },
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["item"]["enabled"] is True
        assert put_resp.json()["item"]["health_check_enabled"] is True
        assert put_resp.json()["item"]["health_check_interval_sec"] == 30

        get_resp = await client.get("/api/gateway/http-config")
        assert get_resp.status_code == 200
        assert get_resp.json()["item"]["listen_port"] == 18899
        assert get_resp.json()["item"]["endpoint_id"] == endpoint_id
        assert get_resp.json()["item"]["health_check_interval_sec"] == 30


@pytest.mark.anyio
async def test_http_proxy_endpoint_service_config_api_round_trip(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        put_resp = await client.put(
            "/api/http-proxy-endpoints/service-config",
            json={
                "enabled": True,
                "health_check_enabled": False,
                "health_check_interval_sec": 45,
            },
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["item"] == {
            "enabled": True,
            "health_check_enabled": False,
            "health_check_interval_sec": 45,
        }

        get_resp = await client.get("/api/http-proxy-endpoints/service-config")
        assert get_resp.status_code == 200
        assert get_resp.json()["item"]["enabled"] is True
        assert get_resp.json()["item"]["health_check_enabled"] is False
        assert get_resp.json()["item"]["health_check_interval_sec"] == 45


@pytest.mark.anyio
async def test_http_proxy_endpoint_crud_and_route_test(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    transport = httpx.ASGITransport(app=app)

    node1 = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="hop-1")
    node2 = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="hop-2")
    storage.upsert_proxy(node1)
    storage.upsert_proxy(node2)
    storage.update_test_result(node1.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(node2.normalized_key(), available=True, latency_ms=20)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pool1 = (await client.post("/api/pools", json={"name": "pool-1", "filters": {"protocol": "http", "available": "true"}})).json()["item"]
        pool2 = (await client.post("/api/pools", json={"name": "pool-2", "filters": {"protocol": "socks", "available": "true"}})).json()["item"]

        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={
                "name": "ep-a",
                "listen_host": "127.0.0.1",
                "listen_port": 18888,
                "hop_pool_ids": [pool1["id"], pool2["id"]],
            },
        )
        assert create_resp.status_code == 200
        endpoint = create_resp.json()["item"]
        endpoint_id = endpoint["id"]
        assert [item["pool_id"] for item in endpoint["hops"]] == [pool1["id"], pool2["id"]]

        list_resp = await client.get("/api/http-proxy-endpoints")
        assert list_resp.status_code == 200
        assert any(int(item["id"]) == int(endpoint_id) for item in list_resp.json()["items"])

        route_resp = await client.get(
            f"/api/http-proxy-endpoints/{endpoint_id}/route-test",
            params={"session_id": "sess-1", "target_domain": "api.example.com"},
        )
        assert route_resp.status_code == 200
        route = route_resp.json()
        assert route["endpoint_id"] == endpoint_id
        assert len(route["hop_node_keys"]) == 2
        assert "route_signature" in route


@pytest.mark.anyio
async def test_http_proxy_endpoint_update_reorders_hops_and_status_reflects_instances(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    transport = httpx.ASGITransport(app=app)

    hop1 = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="hop-1")
    hop2 = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="hop-2")
    hop3 = ProxyNode(protocol="trojan", host="3.3.3.3", port=443, raw_link="trojan://3.3.3.3:443", name="hop-3")
    storage.upsert_proxy(hop1)
    storage.upsert_proxy(hop2)
    storage.upsert_proxy(hop3)
    storage.update_test_result(hop1.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(hop2.normalized_key(), available=True, latency_ms=20)
    storage.update_test_result(hop3.normalized_key(), available=True, latency_ms=30)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pool1 = (await client.post("/api/pools", json={"name": "pool-1x", "filters": {"protocol": "http", "available": "true"}})).json()["item"]
        pool2 = (await client.post("/api/pools", json={"name": "pool-2x", "filters": {"protocol": "socks", "available": "true"}})).json()["item"]
        pool3 = (await client.post("/api/pools", json={"name": "pool-3x", "filters": {"protocol": "trojan", "available": "true"}})).json()["item"]

        endpoint = (await client.post("/api/http-proxy-endpoints", json={
            "name": "ep-status",
            "listen_host": "127.0.0.1",
            "listen_port": _pick_free_port(),
            "hop_pool_ids": [pool1["id"], pool2["id"]],
        })).json()["item"]

        update_resp = await client.put(
            f"/api/http-proxy-endpoints/{endpoint['id']}",
            json={"hop_pool_ids": [pool1["id"], pool3["id"], pool2["id"]]},
        )
        assert update_resp.status_code == 200
        assert [item["pool_id"] for item in update_resp.json()["item"]["hops"]] == [pool1["id"], pool3["id"], pool2["id"]]

        route_resp = await client.get(
            f"/api/http-proxy-endpoints/{endpoint['id']}/route-test",
            params={"session_id": "sess-status", "target_domain": "api.example.com"},
        )
        route = route_resp.json()
        assert route_resp.status_code == 200
        assert len(route["hop_node_keys"]) == 3

        status_resp = await client.get(f"/api/http-proxy-endpoints/{endpoint['id']}/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["item"]["id"] == endpoint["id"]
        assert isinstance(status_data["leases"], list)
        assert isinstance(status_data["instances"], list)


@pytest.mark.anyio
async def test_http_proxy_endpoint_status_includes_hop_pool_and_transition_health(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    transport = httpx.ASGITransport(app=app)

    front_up = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-up")
    front_down = ProxyNode(protocol="http", host="1.1.1.2", port=8080, raw_link="http://1.1.1.2:8080", name="front-down")
    exit_up = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="exit-up")
    storage.upsert_proxy(front_up)
    storage.upsert_proxy(front_down)
    storage.upsert_proxy(exit_up)
    storage.update_test_result(front_up.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(front_down.normalized_key(), available=False, latency_ms=None)
    storage.update_test_result(exit_up.normalized_key(), available=True, latency_ms=20)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        front_pool = (await client.post("/api/pools", json={"name": "front-status", "filters": {"protocol": "http"}})).json()["item"]
        exit_pool = (await client.post("/api/pools", json={"name": "exit-status", "filters": {"protocol": "socks"}})).json()["item"]
        endpoint = (await client.post("/api/http-proxy-endpoints", json={
            "name": "ep-health",
            "listen_host": "127.0.0.1",
            "listen_port": _pick_free_port(),
            "hop_pool_ids": [front_pool["id"], exit_pool["id"]],
        })).json()["item"]
        route_resp = await client.get(
            f"/api/http-proxy-endpoints/{endpoint['id']}/route-test",
            params={"session_id": "sess-health", "target_domain": "api.example.com"},
        )
        assert route_resp.status_code == 200

        status_resp = await client.get(f"/api/http-proxy-endpoints/{endpoint['id']}/status")

    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["summary"]["total_hop_pools"] == 2
    assert data["summary"]["healthy_hop_pools"] == 2
    assert [pool["healthy_nodes"] for pool in data["hop_pools"]] == [1, 1]
    assert data["hop_pools"][0]["nodes"][0]["active"] is True
    assert data["transitions"][0]["available"] is True
    assert data["transitions"][0]["healthy_pairs"] >= 1


@pytest.mark.anyio
async def test_http_proxy_endpoint_status_marks_all_failed_transitions_unavailable(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    transport = httpx.ASGITransport(app=app)

    front = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front")
    exit_node = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="exit")
    storage.upsert_proxy(front)
    storage.upsert_proxy(exit_node)
    storage.update_test_result(front.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(exit_node.normalized_key(), available=True, latency_ms=20)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        front_pool = (await client.post("/api/pools", json={"name": "front-only", "filters": {"protocol": "http"}})).json()["item"]
        exit_pool = (await client.post("/api/pools", json={"name": "exit-only", "filters": {"protocol": "socks"}})).json()["item"]
        endpoint = (await client.post("/api/http-proxy-endpoints", json={
            "name": "ep-all-failed",
            "listen_host": "127.0.0.1",
            "listen_port": _pick_free_port(),
            "hop_pool_ids": [front_pool["id"], exit_pool["id"]],
        })).json()["item"]

        app.state.chain_service.report_endpoint_route_failure(
            endpoint_id=int(endpoint["id"]),
            pool_id=int(front_pool["id"]),
            hop_node_keys=[front.normalized_key(), exit_node.normalized_key()],
        )
        status_resp = await client.get(f"/api/http-proxy-endpoints/{endpoint['id']}/status")

    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["summary"]["healthy_hop_pools"] == 2
    assert data["transitions"][0]["available"] is False
    assert data["summary"]["available"] is False


@pytest.mark.anyio
async def test_http_gateway_health_check_marks_active_route_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    transport = httpx.ASGITransport(app=app)

    front = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front")
    exit_node = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="exit")
    storage.upsert_proxy(front)
    storage.upsert_proxy(exit_node)
    storage.update_test_result(front.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(exit_node.normalized_key(), available=True, latency_ms=20)

    class FakeProbeResult:
        def __init__(self, normalized_key: str, available: bool, error: str = "") -> None:
            self.normalized_key = normalized_key
            self.available = available
            self.latency_ms = 7 if available else None
            self.openai_unlocked = None
            self.openai_status = ""
            self.error = error

    async def fake_probe_async(node: dict) -> FakeProbeResult:
        return FakeProbeResult(str(node.get("normalized_key") or ""), True)

    async def fake_probe_with_front_proxy_async(node: dict, front_proxy: dict) -> FakeProbeResult:
        del front_proxy
        return FakeProbeResult(str(node.get("normalized_key") or ""), False, "hop failed")

    monkeypatch.setattr(app.state.tester.prober, "probe_async", fake_probe_async)
    monkeypatch.setattr(app.state.tester.prober, "probe_with_front_proxy_async", fake_probe_with_front_proxy_async)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        front_pool = (await client.post("/api/pools", json={"name": "front-health", "filters": {"protocol": "http"}})).json()["item"]
        exit_pool = (await client.post("/api/pools", json={"name": "exit-health", "filters": {"protocol": "socks"}})).json()["item"]
        endpoint = (await client.post("/api/http-proxy-endpoints", json={
            "name": "ep-health-check",
            "listen_host": "127.0.0.1",
            "listen_port": _pick_free_port(),
            "hop_pool_ids": [front_pool["id"], exit_pool["id"]],
        })).json()["item"]
        route_resp = await client.get(
            f"/api/http-proxy-endpoints/{endpoint['id']}/route-test",
            params={"session_id": "sess-active-health", "target_domain": "api.example.com"},
        )
        assert route_resp.status_code == 200
        assert route_resp.json()["hop_node_keys"] == [front.normalized_key(), exit_node.normalized_key()]

        config_resp = await client.put("/api/gateway/http-config", json={
            "enabled": True,
            "listen_host": "127.0.0.1",
            "listen_port": _pick_free_port(),
            "endpoint_id": endpoint["id"],
            "default_pool_id": front_pool["id"],
            "health_check_enabled": True,
            "health_check_interval_sec": 5,
        })
        assert config_resp.status_code == 200

        health_resp = await client.post("/api/gateway/http-health-check")
        status_resp = await client.get(f"/api/http-proxy-endpoints/{endpoint['id']}/status")

    assert health_resp.status_code == 200
    health = health_resp.json()["item"]
    endpoint_health = health["endpoints"][str(endpoint["id"])]
    assert endpoint_health["active_failed"] is True
    assert endpoint_health["hops"][1]["nodes"][0]["active"] is True
    assert endpoint_health["hops"][1]["nodes"][0]["ok"] is False
    data = status_resp.json()
    assert data["transitions"][0]["available"] is False
    assert data["health_monitor"]["last_finished_at"]


@pytest.mark.anyio
async def test_http_proxy_endpoint_can_chain_multiple_filtered_pools_in_order(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    transport = httpx.ASGITransport(app=app)

    node_us = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="us-hop")
    node_jp = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="jp-hop")
    node_sg = ProxyNode(protocol="trojan", host="3.3.3.3", port=443, raw_link="trojan://3.3.3.3:443", name="sg-hop")
    storage.upsert_proxy(node_us)
    storage.upsert_proxy(node_jp)
    storage.upsert_proxy(node_sg)
    storage.update_test_result(node_us.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(node_jp.normalized_key(), available=True, latency_ms=20)
    storage.update_test_result(node_sg.normalized_key(), available=True, latency_ms=30)
    storage.update_geo(node_us.normalized_key(), resolved_ip="1.1.1.1", country="US", city="Los Angeles")
    storage.update_geo(node_jp.normalized_key(), resolved_ip="2.2.2.2", country="JP", city="Tokyo")
    storage.update_geo(node_sg.normalized_key(), resolved_ip="3.3.3.3", country="SG", city="Singapore")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pool1 = (await client.post("/api/pools", json={
            "name": "pool-us-direct",
            "filters": {"protocol": "http", "route_mode_filter": "direct", "geo_countries": ["US"]},
        })).json()["item"]
        pool2 = (await client.post("/api/pools", json={
            "name": "pool-sg-direct",
            "filters": {"protocol": "trojan", "route_mode_filter": "direct", "geo_countries": ["SG"]},
        })).json()["item"]
        pool3 = (await client.post("/api/pools", json={
            "name": "pool-jp-chain",
            "filters": {"protocol": "socks", "route_mode_filter": "direct", "geo_countries": ["JP"]},
        })).json()["item"]

        endpoint_resp = await client.post("/api/http-proxy-endpoints", json={
            "name": "endpoint-multi-hop",
            "listen_host": "127.0.0.1",
            "listen_port": _pick_free_port(),
            "hop_pool_ids": [pool1["id"], pool3["id"], pool2["id"]],
        })
        assert endpoint_resp.status_code == 200
        endpoint = endpoint_resp.json()["item"]
        assert [item["pool_id"] for item in endpoint["hops"]] == [pool1["id"], pool3["id"], pool2["id"]]

        route_resp = await client.get(
            f"/api/http-proxy-endpoints/{endpoint['id']}/route-test",
            params={"session_id": "sess-multi-hop", "target_domain": "api.example.com"},
        )
        assert route_resp.status_code == 200
        route = route_resp.json()
        assert route["endpoint_id"] == endpoint["id"]
        assert len(route["hop_node_keys"]) == 3
        assert route["route_signature"].count(">") == 2


@pytest.mark.anyio
async def test_http_gateway_status_api_exposes_runtime_state(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/gateway/http-status")

    assert resp.status_code == 200
    assert "runtime" in resp.json()
    assert "config" in resp.json()


@pytest.mark.anyio
async def test_http_gateway_status_lists_multiple_enabled_endpoints(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    transport = httpx.ASGITransport(app=app)

    hop1 = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="hop-1")
    hop2 = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="hop-2")
    storage.upsert_proxy(hop1)
    storage.upsert_proxy(hop2)
    storage.update_test_result(hop1.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(hop2.normalized_key(), available=True, latency_ms=20)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pool1 = (await client.post("/api/pools", json={"name": "pool-a", "filters": {"protocol": "http"}})).json()["item"]
        pool2 = (await client.post("/api/pools", json={"name": "pool-b", "filters": {"protocol": "socks"}})).json()["item"]

        ep1 = (await client.post("/api/http-proxy-endpoints", json={
            "name": "ep-1",
            "listen_host": "127.0.0.1",
            "listen_port": _pick_free_port(),
            "hop_pool_ids": [pool1["id"]],
        })).json()["item"]
        ep2 = (await client.post("/api/http-proxy-endpoints", json={
            "name": "ep-2",
            "listen_host": "127.0.0.1",
            "listen_port": _pick_free_port(),
            "hop_pool_ids": [pool2["id"]],
        })).json()["item"]

        put_resp = await client.put("/api/gateway/http-config", json={
            "enabled": True,
            "listen_host": "127.0.0.1",
            "listen_port": _pick_free_port(),
            "endpoint_id": ep1["id"],
            "default_pool_id": pool1["id"],
        })
        assert put_resp.status_code == 200

        status_resp = await client.get("/api/gateway/http-status")
        assert status_resp.status_code == 200
        runtime_items = status_resp.json()["runtime"]["items"]
        assert len(runtime_items) >= 2
        assert {int(item["endpoint_id"]) for item in runtime_items} >= {int(ep1["id"]), int(ep2["id"])}


@pytest.mark.anyio
async def test_multiple_http_proxy_endpoints_can_listen_simultaneously(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    transport = httpx.ASGITransport(app=app)

    http_node = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="hop-http")
    socks_node = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="hop-socks")
    storage.upsert_proxy(http_node)
    storage.upsert_proxy(socks_node)
    storage.update_test_result(http_node.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(socks_node.normalized_key(), available=True, latency_ms=20)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pool_http = (await client.post("/api/pools", json={"name": "pool-http", "filters": {"protocol": "http"}})).json()["item"]
        pool_socks = (await client.post("/api/pools", json={"name": "pool-socks", "filters": {"protocol": "socks"}})).json()["item"]

        ep1_port = _pick_free_port()
        ep2_port = _pick_free_port()
        ep1 = (await client.post("/api/http-proxy-endpoints", json={
            "name": "ep-http",
            "listen_host": "127.0.0.1",
            "listen_port": ep1_port,
            "hop_pool_ids": [pool_http["id"]],
        })).json()["item"]
        ep2 = (await client.post("/api/http-proxy-endpoints", json={
            "name": "ep-socks",
            "listen_host": "127.0.0.1",
            "listen_port": ep2_port,
            "hop_pool_ids": [pool_socks["id"]],
        })).json()["item"]

        enable_resp = await client.put("/api/gateway/http-config", json={
            "enabled": True,
            "listen_host": "127.0.0.1",
            "listen_port": _pick_free_port(),
            "endpoint_id": ep1["id"],
            "default_pool_id": pool_http["id"],
        })
        assert enable_resp.status_code == 200

        reader1, writer1 = await asyncio.open_connection("127.0.0.1", ep1_port)
        writer1.close()
        await writer1.wait_closed()

        reader2, writer2 = await asyncio.open_connection("127.0.0.1", ep2_port)
        writer2.close()
        await writer2.wait_closed()

        status_resp = await client.get("/api/gateway/http-status")
        assert status_resp.status_code == 200
        runtime_items = status_resp.json()["runtime"]["items"]
        assert {int(item["endpoint_id"]) for item in runtime_items} >= {int(ep1["id"]), int(ep2["id"])}


@pytest.mark.anyio
async def test_http_gateway_config_update_starts_and_stops_runtime(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    transport = httpx.ASGITransport(app=app)
    listen_port = _pick_free_port()

    front = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1")
    exit_node = ProxyNode(
        protocol="socks",
        host="2.2.2.2",
        port=1080,
        raw_link="socks://2.2.2.2:1080",
        name="exit-1",
    )
    storage.upsert_proxy(front)
    storage.upsert_proxy(exit_node)
    storage.update_test_result(front.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(exit_node.normalized_key(), available=True, latency_ms=20)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/pools", json={"name": "pool-a"})
        pool_id = create_resp.json()["item"]["id"]

        put_resp = await client.put(
            "/api/gateway/http-config",
            json={
                "enabled": True,
                "listen_host": "127.0.0.1",
                "listen_port": listen_port,
                "default_pool_id": pool_id,
                "sticky_ttl_sec": 3600,
                "session_missing_action": "RANDOM",
                "http_session_header_names": ["X-ProxyPool-Session"],
                "http_session_query_names": ["session"],
                "connect_session_header_names": ["X-ProxyPool-Session"],
            },
        )
        assert put_resp.status_code == 200

        status_resp = await client.get("/api/gateway/http-status")
        assert status_resp.status_code == 200
        assert status_resp.json()["runtime"]["running"] is True

        disable_resp = await client.put(
            "/api/gateway/http-config",
            json={
                "enabled": False,
                "listen_host": "127.0.0.1",
                "listen_port": listen_port,
                "default_pool_id": pool_id,
                "sticky_ttl_sec": 3600,
                "session_missing_action": "RANDOM",
                "http_session_header_names": ["X-ProxyPool-Session"],
                "http_session_query_names": ["session"],
                "connect_session_header_names": ["X-ProxyPool-Session"],
            },
        )
        assert disable_resp.status_code == 200

        stopped_resp = await client.get("/api/gateway/http-status")
        assert stopped_resp.status_code == 200
        assert stopped_resp.json()["runtime"]["running"] is False


@pytest.mark.anyio
async def test_http_gateway_start_failure_does_not_break_control_plane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    pool = storage.create_proxy_pool(name="pool-a")
    storage.set_app_setting(
        "http_gateway_config_v1",
        '{"enabled":true,"listen_host":"127.0.0.1","listen_port":18899,"default_pool_id":'
        + str(pool["id"])
        + ',"sticky_ttl_sec":3600,"session_missing_action":"RANDOM","http_session_header_names":["X-ProxyPool-Session"],"http_session_query_names":["session"],"connect_session_header_names":["X-ProxyPool-Session"]}',
    )
    app.state.forward_gateway.config = app.state.gateway_config_service.get_config()

    async def broken_start() -> None:
        app.state.gateway_runtime.last_error = "address already in use"
        raise OSError("address already in use")

    monkeypatch.setattr(app.state.gateway_runtime, "start", broken_start)

    # Trigger startup via lifespan
    async with app.router.lifespan_context(app):
        pass

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/gateway/http-status")

    assert resp.status_code == 200
    assert resp.json()["runtime"]["running"] is False
    assert "address already in use" in resp.json()["runtime"]["last_error"]


@pytest.mark.anyio
async def test_http_gateway_test_api_returns_result_shape(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/gateway/http-test",
            json={"target_url": "https://example.com", "session_id": "sess-1"},
        )

    assert resp.status_code == 200
    assert "ok" in resp.json()
    assert "detail" in resp.json()


@pytest.mark.anyio
async def test_http_gateway_test_api_performs_proxy_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    calls: dict[str, object] = {}

    def fake_resolve_route(raw_target: str, headers: dict[str, str]) -> dict:
        calls["resolve_target"] = raw_target
        calls["resolve_headers"] = dict(headers)
        return {
            "endpoint": {"id": 9, "listen_host": "127.0.0.1", "listen_port": 18899},
            "pool": {"id": 1},
            "session_id": str(headers.get("X-ProxyPool-Session") or ""),
            "route": {"hop_node_keys": ["front", "exit"], "route_signature": "pool-1>pool-2"},
            "instance": {"instance_id": "gw-test"},
            "target": urlsplit(raw_target),
        }

    async def fake_request(
        target_url: str,
        proxy_url: str,
        proxy_headers: dict[str, str],
        timeout_sec: float = 15.0,
    ) -> dict:
        calls["request"] = {
            "target_url": target_url,
            "proxy_url": proxy_url,
            "proxy_headers": dict(proxy_headers),
            "timeout_sec": timeout_sec,
        }
        return {
            "request_ok": True,
            "status_code": 200,
            "elapsed_ms": 12,
            "body_preview": "ok",
        }

    app.state.forward_gateway.resolve_route_for_http = fake_resolve_route
    monkeypatch.setattr(api_app, "_request_via_forward_proxy", fake_request)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/gateway/http-test",
            json={"target_url": "https://ipinfo.io", "session_id": "sess-1"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["detail"] == "request succeeded"
    assert data["proxy_url"] == "http://127.0.0.1:18899"
    assert data["request"]["status_code"] == 200
    assert calls["resolve_headers"] == {"X-ProxyPool-Session": "sess-1"}
    assert calls["request"] == {
        "target_url": "https://ipinfo.io",
        "proxy_url": "http://127.0.0.1:18899",
        "proxy_headers": {"X-ProxyPool-Session": "sess-1"},
        "timeout_sec": 15.0,
    }


@pytest.mark.anyio
async def test_http_gateway_test_api_marks_failed_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    calls: dict[str, object] = {}

    def fake_resolve_route(raw_target: str, headers: dict[str, str]) -> dict:
        return {
            "endpoint": {"id": 9, "listen_host": "127.0.0.1", "listen_port": 18899},
            "pool": {"id": 1},
            "session_id": str(headers.get("X-ProxyPool-Session") or ""),
            "route": {"hop_node_keys": ["front", "exit"], "route_signature": "pool-1>pool-2"},
            "instance": {"instance_id": "gw-test"},
            "target": urlsplit(raw_target),
        }

    async def fake_request(
        target_url: str,
        proxy_url: str,
        proxy_headers: dict[str, str],
        timeout_sec: float = 15.0,
    ) -> dict:
        return {
            "request_ok": False,
            "elapsed_ms": 12,
            "error_type": "ConnectError",
            "error": "tls failed",
        }

    def fake_report_failure(**kwargs: object) -> None:
        calls["failure"] = kwargs

    def fake_mark_failed(instance_id: str, error: str = "") -> None:
        calls["mark_failed"] = {"instance_id": instance_id, "error": error}

    app.state.forward_gateway.resolve_route_for_http = fake_resolve_route
    app.state.chain_service.report_endpoint_route_failure = fake_report_failure
    app.state.chain_instance_manager.mark_instance_failed = fake_mark_failed
    monkeypatch.setattr(api_app, "_request_via_forward_proxy", fake_request)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/gateway/http-test",
            json={"target_url": "https://ipinfo.io", "session_id": "sess-1"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["detail"] == "tls failed"
    assert calls["failure"] == {
        "endpoint_id": 9,
        "pool_id": 1,
        "session_id": "sess-1",
        "hop_node_keys": ["front", "exit"],
    }
    assert calls["mark_failed"] == {"instance_id": "gw-test", "error": "tls failed"}


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


@pytest.mark.anyio
async def test_pool_chain_lease_endpoints_and_chain_route_session_id(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])
    storage.upsert_proxy_pool_v2("exit", "exit", ["exit-.*"])
    front = ProxyNode(protocol="http", host="1.1.1.1", port=80, name="front-a", raw_link="http://1.1.1.1:80")
    exit_node = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, name="exit-a", raw_link="socks://2.2.2.2:1080")
    storage.upsert_proxy(front)
    storage.upsert_proxy(exit_node)
    storage.update_test_result(front.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(exit_node.normalized_key(), available=True, latency_ms=20)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/pools", json={"name": "pool-a"})
        pool_id = create_resp.json()["item"]["id"]

        route_resp = await client.get(f"/api/chain/route?session_id=sess-1&pool_id={pool_id}")
        assert route_resp.status_code == 200
        assert route_resp.json()["lease_created"] is True

        leases_resp = await client.get(f"/api/pools/{pool_id}/chain/leases")
        assert leases_resp.status_code == 200
        assert leases_resp.json()["items"][0]["session_id"] == "sess-1"

        inherit_resp = await client.post(
            f"/api/pools/{pool_id}/chain/leases/inherit",
            json={"from_session_id": "sess-1", "to_session_id": "sess-2"},
        )
        assert inherit_resp.status_code == 200
        assert inherit_resp.json()["item"]["session_id"] == "sess-2"

        delete_resp = await client.delete(f"/api/pools/{pool_id}/chain/leases/sess-1")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted"] is True


@pytest.mark.anyio
async def test_pool_chain_session_rule_crud(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/pools", json={"name": "pool-a"})
        pool_id = create_resp.json()["item"]["id"]

        put_resp = await client.put(
            f"/api/pools/{pool_id}/chain/session-rules/api.example.com/v1",
            json={"headers": ["Authorization", "X-Biz-Session"]},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["item"]["url_prefix"] == "api.example.com/v1"

        list_resp = await client.get(f"/api/pools/{pool_id}/chain/session-rules")
        assert list_resp.status_code == 200
        assert list_resp.json()["items"][0]["headers"] == ["Authorization", "X-Biz-Session"]

        delete_resp = await client.delete(f"/api/pools/{pool_id}/chain/session-rules/api.example.com/v1")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted"] is True


@pytest.mark.anyio
async def test_pool_chain_route_test_endpoint_uses_session_id(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])
    storage.upsert_proxy_pool_v2("exit", "exit", ["exit-.*"])
    front = ProxyNode(protocol="http", host="1.1.1.1", port=80, name="front-a", raw_link="http://1.1.1.1:80")
    exit_node = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, name="exit-a", raw_link="socks://2.2.2.2:1080")
    storage.upsert_proxy(front)
    storage.upsert_proxy(exit_node)
    storage.update_test_result(front.normalized_key(), available=True, latency_ms=10)
    storage.update_test_result(exit_node.normalized_key(), available=True, latency_ms=20)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/pools", json={"name": "pool-a"})
        pool_id = create_resp.json()["item"]["id"]

        resp = await client.get(f"/api/pools/{pool_id}/chain/route-test?session_id=sess-1&target_domain=api.example.com")
        assert resp.status_code == 200
        assert resp.json()["lease_created"] is True
        assert resp.json()["front_node"]["key"] != ""


@pytest.mark.anyio
async def test_unified_gateway_rejects_missing_session_when_pool_requires_it(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])
    storage.upsert_proxy_pool_v2("exit", "exit", ["exit-.*"])
    storage.upsert_proxy(ProxyNode(protocol="http", host="1.1.1.1", port=80, name="front-a", raw_link="http://1.1.1.1:80"))
    storage.upsert_proxy(ProxyNode(protocol="socks", host="2.2.2.2", port=1080, name="exit-a", raw_link="socks://2.2.2.2:1080"))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/pools", json={"name": "pool-a"})
        pool_id = create_resp.json()["item"]["id"]
        update_resp = await client.put(
            f"/api/pools/{pool_id}/chain",
            json={
                "chain_enabled": True,
                "session_missing_action": "REJECT",
                "session_header_names": ["X-ProxyPool-Session"],
                "gateway_path_prefix": "/proxy/pool-a",
            },
        )
        assert update_resp.status_code == 200

        resp = await client.get("/proxy/pool-a/https/api.example.com/v1/chat")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "session_id is required"


@pytest.mark.anyio
async def test_unified_gateway_requires_configured_gateway_prefix(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage
    storage.upsert_proxy_pool_v2("front", "front", ["front-.*"])
    storage.upsert_proxy_pool_v2("exit", "exit", ["exit-.*"])
    storage.upsert_proxy(ProxyNode(protocol="http", host="1.1.1.1", port=80, name="front-a", raw_link="http://1.1.1.1:80"))
    storage.upsert_proxy(ProxyNode(protocol="socks", host="2.2.2.2", port=1080, name="exit-a", raw_link="socks://2.2.2.2:1080"))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/pools", json={"name": "pool-a"})
        pool_id = create_resp.json()["item"]["id"]
        update_resp = await client.put(
            f"/api/pools/{pool_id}/chain",
            json={
                "chain_enabled": True,
                "session_header_names": ["X-ProxyPool-Session"],
            },
        )
        assert update_resp.status_code == 200

        resp = await client.get(
            "/proxy/pool-a/https/api.example.com/v1/chat",
            headers={"X-ProxyPool-Session": "sess-1"},
        )
        assert resp.status_code == 404
