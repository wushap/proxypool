"""
Tests for gateway router lines not covered by test_api_gateway_coverage.py.

Targets specific uncovered lines:
- 157: health_status = "degraded" path
- 191-194: http-test endpoint_id switch
- 199-213: http-test without session_id (session missing action logic)
- 225: proxy_port <= 0 return in http-test
- 348-349: create endpoint storage exception
- 385-386: update endpoint with gateway enabled sync
- 442: route-test returns None -> 503
- 487-518: endpoint health with hops/pool/leases
- 598-622: test-connectivity TCP success + HTTP test
- 686-696: port conflicts actual conflicts
"""

from __future__ import annotations

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


def _make_settings(tmp_path_factory) -> AppSettings:
    from pathlib import Path

    tmp = tmp_path_factory.mktemp("test_gateway_router_coverage")
    return AppSettings(
        project_root=tmp,
        db_path=tmp / "test.db",
        output_dir=tmp / "output",
        sources_file=tmp / "sources.txt",
        singbox_routes_file=tmp / "routes.json",
        singbox_runtime_config_file=tmp / "runtime.json",
        singbox_runtime_log_file=tmp / "runtime.log",
        singbox_binary="sing-box",
        test_url="https://httpbin.org/get",
        api_key="",
        backend_engine="singbox",
        backend_health_check_sec=60,
        backend_auto_restart_max=3,
    )


# ===== Line 157: health_status = "degraded" path =====


@pytest.mark.anyio
async def test_health_check_degraded(tmp_path_factory):
    """POST /api/gateway/http-health-check returns 'degraded' when running
    but healthy_endpoints < total_endpoints."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    mock_status = {
        "running": True,
        "last_error": "",
        "items": [
            {"running": True},
            {"running": False},  # unhealthy endpoint -> degraded
        ],
    }
    with patch.object(app.state.gateway_runtime, "status", return_value=mock_status):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/gateway/http-health-check")
            assert resp.status_code == 200
            data = resp.json()
            assert data["item"]["status"] == "degraded"
            assert data["item"]["endpoints"]["total"] == 2
            assert data["item"]["endpoints"]["healthy"] == 1


# ===== Lines 191-194: http-test endpoint_id switch =====


@pytest.mark.anyio
async def test_http_test_switches_endpoint_id(tmp_path_factory):
    """POST /api/gateway/http-test with endpoint_id different from config
    triggers endpoint update (lines 191-194)."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create an endpoint
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "switch-ep", "listen_port": 8901},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        mock_route = {
            "session_id": "sess-switch",
            "endpoint": {"id": endpoint_id, "listen_host": "127.0.0.1", "listen_port": 8901},
            "instance": {"instance_id": "inst-sw"},
            "target": MagicMock(netloc="example.com"),
            "route": {"hop_node_keys": ["k1"], "route_signature": "sig-sw"},
        }
        mock_result = {"request_ok": True, "status_code": 200, "elapsed_ms": 10, "body_preview": ""}

        with (
            patch.object(
                app.state.forward_gateway, "resolve_route_for_http", return_value=mock_route
            ),
            patch(
                "proxypool.api.app._request_via_forward_proxy",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            resp = await client.post(
                "/api/gateway/http-test",
                json={
                    "target_url": "https://example.com",
                    "endpoint_id": endpoint_id,
                    "session_id": "sess-switch",
                },
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True


# ===== Lines 199-213: http-test without session_id =====


@pytest.mark.anyio
async def test_http_test_without_session_id(tmp_path_factory):
    """POST /api/gateway/http-test without session_id enters session missing
    action logic (lines 199-213)."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    mock_route = {
        "session_id": "auto-sess",
        "endpoint": {"id": 0, "listen_host": "127.0.0.1", "listen_port": 8899},
        "instance": {"instance_id": "inst-auto"},
        "target": MagicMock(netloc="example.com"),
        "route": {"hop_node_keys": [], "route_signature": "sig-auto"},
    }
    mock_result = {
        "request_ok": False,
        "status_code": 0,
        "elapsed_ms": 5,
        "error": "expected failure",
    }

    with (
        patch.object(
            app.state.forward_gateway, "resolve_route_for_http", return_value=mock_route
        ),
        patch(
            "proxypool.api.app._request_via_forward_proxy",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/gateway/http-test",
                json={"target_url": "https://example.com"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "session_id" in data


# ===== Line 225: proxy_port <= 0 in http-test =====


@pytest.mark.anyio
async def test_http_test_proxy_port_zero(tmp_path_factory):
    """POST /api/gateway/http-test returns 'gateway listen port not configured'
    when proxy_port is 0 (line 225)."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    mock_route = {
        "session_id": "sess-zero-port",
        "endpoint": {"id": 1, "listen_host": "127.0.0.1", "listen_port": 0},
        "instance": {"instance_id": "inst-zp"},
        "target": MagicMock(netloc="example.com"),
        "route": {"hop_node_keys": ["k1"], "route_signature": "sig-zp"},
    }

    with (
        patch.object(
            app.state.forward_gateway, "resolve_route_for_http", return_value=mock_route
        ),
        patch.object(app.state.forward_gateway.config, "listen_port", 0),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/gateway/http-test",
                json={"target_url": "https://example.com", "session_id": "sess-zero-port"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is False
            assert "gateway listen port is not configured" in data["detail"]


# ===== Lines 348-349: create endpoint storage exception =====


@pytest.mark.anyio
async def test_create_endpoint_storage_error(tmp_path_factory):
    """POST /api/http-proxy-endpoints returns 400 on storage exception
    (lines 348-349)."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    with patch.object(
        app.state.storage,
        "create_http_proxy_endpoint",
        side_effect=Exception("storage write failed"),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/http-proxy-endpoints",
                json={"name": "err-create", "listen_port": 8902},
            )
            assert resp.status_code == 400


# ===== Lines 385-386: update endpoint with gateway enabled sync =====


@pytest.mark.anyio
async def test_update_endpoint_with_gateway_sync(tmp_path_factory):
    """PUT /api/http-proxy-endpoints/{id} with gateway enabled triggers
    runtime.sync() (lines 385-386)."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    # Enable gateway first
    app.state.gateway_config_service.update_config(enabled=True)

    with patch.object(app.state.gateway_runtime, "sync", new_callable=AsyncMock):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            create_resp = await client.post(
                "/api/http-proxy-endpoints",
                json={"name": "sync-update", "listen_port": 8903},
            )
            endpoint_id = create_resp.json()["item"]["id"]

            resp = await client.put(
                f"/api/http-proxy-endpoints/{endpoint_id}",
                json={"name": "synced-name"},
            )
            assert resp.status_code == 200
            assert resp.json()["item"]["name"] == "synced-name"


# ===== Line 442: route-test returns None -> 503 =====


@pytest.mark.anyio
async def test_route_test_no_available_nodes(tmp_path_factory):
    """GET /api/http-proxy-endpoints/{id}/route-test returns 503 when
    route_request returns None (line 442)."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    # Create a pool first so the endpoint can have hops
    pool = app.state.storage.create_proxy_pool(name="route-pool")
    pool_id = pool["id"]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "route-503", "listen_port": 8904, "hop_pool_ids": [pool_id]},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        with patch.object(
            app.state.chain_service, "route_request", return_value=None
        ):
            resp = await client.get(
                f"/api/http-proxy-endpoints/{endpoint_id}/route-test"
            )
            assert resp.status_code == 503
            assert "No available nodes" in resp.json()["detail"]


# ===== Lines 487-518: endpoint health with hops/pool/leases =====


@pytest.mark.anyio
async def test_endpoint_health_with_upstream_pool(tmp_path_factory):
    """GET /api/gateway/endpoints/{id}/health exercises the hops, upstream
    pool, and leases code paths (lines 487-518)."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    # Create a pool
    pool = app.state.storage.create_proxy_pool(name="health-pool")
    pool_id = pool["id"]

    # Create endpoint with hops pointing to the pool
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "health-ep", "listen_port": 8905, "hop_pool_ids": [pool_id]},
        )
        endpoint_id = create_resp.json()["item"]["id"]

    # Mock gateway_runtime.status() to return an item matching this endpoint
    mock_runtime_status = {
        "running": True,
        "items": [
            {"id": endpoint_id, "running": True, "recent_errors": ["test err"]}
        ],
    }
    # Mock chain_instance_manager.list_instances to return a running instance
    mock_instances = [
        {"instance_id": "inst-h1", "status": "running", "endpoint_id": endpoint_id}
    ]
    # Mock storage.list_sticky_leases
    mock_leases = [
        {
            "instance_id": "inst-h1",
            "hop_node_keys": ["key-a"],
            "expires_at": 9999999999,
        }
    ]

    with (
        patch.object(app.state.gateway_runtime, "status", return_value=mock_runtime_status),
        patch.object(
            app.state.chain_instance_manager,
            "list_instances",
            return_value=mock_instances,
        ),
        patch.object(
            app.state.storage,
            "list_sticky_leases",
            return_value=mock_leases,
        ),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/gateway/endpoints/{endpoint_id}/health"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["endpoint_id"] == endpoint_id
            assert data["is_listening"] is False  # port not actually open
            assert "recent_errors" in data
            assert len(data["recent_errors"]) == 1
            assert "upstream_pool_status" in data


# ===== Lines 598-622: test-connectivity TCP success + HTTP test =====


@pytest.mark.anyio
async def test_connectivity_tcp_success(tmp_path_factory):
    """POST /api/gateway/endpoints/{id}/test-connectivity exercises the TCP
    connection success path (lines 598-622)."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "tcp-success", "listen_port": 8906},
        )
        endpoint_id = create_resp.json()["item"]["id"]

    # Mock socket to simulate successful TCP connection
    mock_sock = MagicMock()
    mock_sock.connect_ex.return_value = 0

    # Use a real socket mock class that returns our mock_sock
    original_socket = socket.socket

    def mock_socket_factory(*args, **kwargs):
        return mock_sock

    with patch("socket.socket", side_effect=mock_socket_factory):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/gateway/endpoints/{endpoint_id}/test-connectivity"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["connection_test"] is True
            assert data["is_reachable"] is True
            assert data["latency_ms"] is not None
            # HTTP test will fail since no actual proxy, but code catches exception
            # and sets http_test = connection_test (True)
            assert data["http_test"] is True


# ===== Lines 686-696: port conflicts actual conflicts =====


@pytest.mark.anyio
async def test_port_conflicts_same_port(tmp_path_factory):
    """GET /api/gateway/port-conflicts detects conflict when two endpoints
    share the same port (lines 686-696)."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "conflict-a", "listen_port": 8907},
        )
        await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "conflict-b", "listen_port": 8907},
        )

        resp = await client.get("/api/gateway/port-conflicts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_conflicts"] is True
        assert len(data["conflicts"]) >= 1
        conflict = data["conflicts"][0]
        assert conflict["port"] == 8907
        assert conflict["conflict_type"] == "endpoint_endpoint"


@pytest.mark.anyio
async def test_port_conflicts_endpoint_and_instance(tmp_path_factory):
    """GET /api/gateway/port-conflicts detects endpoint_instance conflict."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    mock_instances = [
        {
            "instance_id": "inst-ep",
            "listen": "127.0.0.1",
            "ports": [8908],
        }
    ]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "ep-inst-conflict", "listen_port": 8908},
        )

        with patch.object(
            app.state.singbox_manager, "list_instances", return_value=mock_instances
        ):
            resp = await client.get("/api/gateway/port-conflicts")
            data = resp.json()
            assert data["has_conflicts"] is True
            types = [c["conflict_type"] for c in data["conflicts"]]
            assert "endpoint_instance" in types


@pytest.mark.anyio
async def test_port_conflicts_instance_instance(tmp_path_factory):
    """GET /api/gateway/port-conflicts detects instance_instance conflict."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    mock_instances = [
        {"instance_id": "inst-a", "listen": "127.0.0.1", "ports": [8909]},
        {"instance_id": "inst-b", "listen": "127.0.0.1", "ports": [8909]},
    ]

    with patch.object(
        app.state.singbox_manager, "list_instances", return_value=mock_instances
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/gateway/port-conflicts")
            data = resp.json()
            assert data["has_conflicts"] is True
            types = [c["conflict_type"] for c in data["conflicts"]]
            assert "instance_instance" in types


# ===== Lines 720-742: _request_via_forward_proxy in gateway module =====


@pytest.mark.anyio
async def test_gateway_module_request_via_forward_proxy_success():
    """The gateway module's own _request_via_forward_proxy succeeds."""
    from proxypool.api.routers.gateway import _request_via_forward_proxy

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "response body"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("proxypool.api.routers.gateway.httpx.AsyncClient", return_value=mock_client):
        with patch("proxypool.api.routers.gateway.httpx.Proxy"):
            result = await _request_via_forward_proxy(
                target_url="https://example.com",
                proxy_url="http://127.0.0.1:8899",
                proxy_headers={"X-Session": "test"},
            )
    assert result["request_ok"] is True
    assert result["status_code"] == 200


@pytest.mark.anyio
async def test_gateway_module_request_via_forward_proxy_failure():
    """The gateway module's own _request_via_forward_proxy handles errors."""
    from proxypool.api.routers.gateway import _request_via_forward_proxy

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("proxypool.api.routers.gateway.httpx.AsyncClient", return_value=mock_client):
        with patch("proxypool.api.routers.gateway.httpx.Proxy"):
            result = await _request_via_forward_proxy(
                target_url="https://example.com",
                proxy_url="http://127.0.0.1:8899",
                proxy_headers={},
            )
    assert result["request_ok"] is False
    assert "error" in result
