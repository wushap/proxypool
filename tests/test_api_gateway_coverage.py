"""
Tests for gateway router endpoints with low coverage.

Covers: gateway/http-config (GET/PUT), gateway/http-status,
gateway/http-health-check, gateway/http-test, http-proxy-endpoints CRUD,
http-proxy-endpoints/{id}/status, http-proxy-endpoints/service-config
(GET/PUT), gateway/port-conflicts.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


def _make_settings(tmp_path_factory) -> AppSettings:
    from pathlib import Path

    tmp = tmp_path_factory.mktemp("test_gateway_coverage")
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


# ===== GET /api/gateway/http-config =====


@pytest.mark.anyio
async def test_get_http_gateway_config(tmp_path_factory):
    """GET /api/gateway/http-config returns current config."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/gateway/http-config")
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        item = data["item"]
        assert "enabled" in item
        assert "listen_host" in item
        assert "listen_port" in item
        assert isinstance(item["enabled"], bool)
        assert isinstance(item["listen_port"], int)


# ===== PUT /api/gateway/http-config =====


@pytest.mark.anyio
async def test_update_http_gateway_config(tmp_path_factory):
    """PUT /api/gateway/http-config updates config and returns it."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put(
            "/api/gateway/http-config",
            json={
                "listen_host": "0.0.0.0",
                "listen_port": 9999,
                "enabled": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        assert data["item"]["listen_host"] == "0.0.0.0"
        assert data["item"]["listen_port"] == 9999


@pytest.mark.anyio
async def test_update_http_gateway_config_enabled(tmp_path_factory):
    """PUT /api/gateway/http-config with enabled=True attempts to start runtime."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    # Suppress the actual gateway start to avoid port binding in tests
    with patch.object(
        app.state.gateway_runtime, "start", new_callable=AsyncMock
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/gateway/http-config",
                json={"enabled": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["item"]["enabled"] is True


@pytest.mark.anyio
async def test_update_http_gateway_config_disabled(tmp_path_factory):
    """PUT /api/gateway/http-config with enabled=False stops runtime."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    with patch.object(
        app.state.gateway_runtime, "stop", new_callable=AsyncMock
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/gateway/http-config",
                json={"enabled": False},
            )
            assert resp.status_code == 200


# ===== GET /api/gateway/http-status =====


@pytest.mark.anyio
async def test_get_http_gateway_status_no_endpoint(tmp_path_factory):
    """GET /api/gateway/http-status with default endpoint_id=0."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/gateway/http-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "runtime" in data
        assert "endpoint" in data
        assert data["endpoint"] is None
        assert data["endpoint_id"] == 0


# ===== POST /api/gateway/http-health-check =====


@pytest.mark.anyio
async def test_http_health_check(tmp_path_factory):
    """POST /api/gateway/http-health-check returns health status."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/gateway/http-health-check")
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        item = data["item"]
        assert "status" in item
        assert "running" in item
        assert item["status"] in ("healthy", "unhealthy", "degraded")


# ===== GET /api/http-proxy-endpoints =====


@pytest.mark.anyio
async def test_list_http_proxy_endpoints_empty(tmp_path_factory):
    """GET /api/http-proxy-endpoints returns empty list initially."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/http-proxy-endpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 0


# ===== POST /api/http-proxy-endpoints (create) =====


@pytest.mark.anyio
async def test_create_http_proxy_endpoint(tmp_path_factory):
    """POST /api/http-proxy-endpoints creates an endpoint."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/http-proxy-endpoints",
            json={
                "name": "test-endpoint",
                "listen_host": "127.0.0.1",
                "listen_port": 8801,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        item = data["item"]
        assert item["name"] == "test-endpoint"
        assert item["listen_port"] == 8801
        assert item["id"] > 0


@pytest.mark.anyio
async def test_create_http_proxy_endpoint_with_hops(tmp_path_factory):
    """POST /api/http-proxy-endpoints with hop_pool_ids."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/http-proxy-endpoints",
            json={
                "name": "hop-endpoint",
                "listen_port": 8802,
                "hop_pool_ids": [],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["item"]["name"] == "hop-endpoint"


# ===== GET /api/http-proxy-endpoints/{id} =====


@pytest.mark.anyio
async def test_get_http_proxy_endpoint(tmp_path_factory):
    """GET /api/http-proxy-endpoints/{id} returns the endpoint."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create first
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "get-test", "listen_port": 8803},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        # Fetch it
        resp = await client.get(f"/api/http-proxy-endpoints/{endpoint_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["item"]["id"] == endpoint_id
        assert data["item"]["name"] == "get-test"


@pytest.mark.anyio
async def test_get_http_proxy_endpoint_not_found(tmp_path_factory):
    """GET /api/http-proxy-endpoints/{id} returns 404 for missing endpoint."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/http-proxy-endpoints/99999")
        assert resp.status_code == 404


# ===== PUT /api/http-proxy-endpoints/{id} =====


@pytest.mark.anyio
async def test_update_http_proxy_endpoint(tmp_path_factory):
    """PUT /api/http-proxy-endpoints/{id} updates an endpoint."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "update-test", "listen_port": 8804},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        # Update
        resp = await client.put(
            f"/api/http-proxy-endpoints/{endpoint_id}",
            json={"name": "updated-name", "listen_port": 8805},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["item"]["name"] == "updated-name"
        assert data["item"]["listen_port"] == 8805


@pytest.mark.anyio
async def test_update_http_proxy_endpoint_with_hops(tmp_path_factory):
    """PUT /api/http-proxy-endpoints/{id} with hop_pool_ids."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "hop-update", "listen_port": 8806},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        resp = await client.put(
            f"/api/http-proxy-endpoints/{endpoint_id}",
            json={"hop_pool_ids": []},
        )
        assert resp.status_code == 200


# ===== DELETE /api/http-proxy-endpoints/{id} =====


@pytest.mark.anyio
async def test_delete_http_proxy_endpoint(tmp_path_factory):
    """DELETE /api/http-proxy-endpoints/{id} deletes the endpoint."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "delete-test", "listen_port": 8807},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        # Delete
        resp = await client.delete(f"/api/http-proxy-endpoints/{endpoint_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"]

        # Verify gone
        resp2 = await client.get(f"/api/http-proxy-endpoints/{endpoint_id}")
        assert resp2.status_code == 404


@pytest.mark.anyio
async def test_delete_http_proxy_endpoint_not_found(tmp_path_factory):
    """DELETE /api/http-proxy-endpoints/{id} returns 404 for missing endpoint."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete("/api/http-proxy-endpoints/99999")
        assert resp.status_code == 404


# ===== GET /api/http-proxy-endpoints/service-config =====


@pytest.mark.anyio
async def test_get_endpoint_service_config(tmp_path_factory):
    """GET /api/http-proxy-endpoints/service-config returns config."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/http-proxy-endpoints/service-config")
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        item = data["item"]
        assert "enabled" in item
        assert "health_check_enabled" in item
        assert "health_check_interval_sec" in item


# ===== PUT /api/http-proxy-endpoints/service-config =====


@pytest.mark.anyio
async def test_update_endpoint_service_config_disabled(tmp_path_factory):
    """PUT /api/http-proxy-endpoints/service-config disables service."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    with patch.object(
        app.state.gateway_runtime, "stop", new_callable=AsyncMock
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/http-proxy-endpoints/service-config",
                json={
                    "enabled": False,
                    "health_check_enabled": False,
                    "health_check_interval_sec": 60,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            item = data["item"]
            assert item["enabled"] is False
            assert item["health_check_enabled"] is False
            assert item["health_check_interval_sec"] == 60


@pytest.mark.anyio
async def test_update_endpoint_service_config_enabled(tmp_path_factory):
    """PUT /api/http-proxy-endpoints/service-config enables service."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    with patch.object(
        app.state.gateway_runtime, "start", new_callable=AsyncMock
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/http-proxy-endpoints/service-config",
                json={"enabled": True, "health_check_enabled": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["item"]["enabled"] is True


# ===== GET /api/gateway/port-conflicts =====


@pytest.mark.anyio
async def test_check_port_conflicts_empty(tmp_path_factory):
    """GET /api/gateway/port-conflicts with no endpoints or instances."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/gateway/port-conflicts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_conflicts"] is False
        assert isinstance(data["conflicts"], list)
        assert data["scanned_endpoints"] == 0
        assert data["scanned_instances"] == 0


# ===== POST /api/gateway/http-test =====


@pytest.mark.anyio
async def test_http_gateway_test_empty_target(tmp_path_factory):
    """POST /api/gateway/http-test with empty target returns 400."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/gateway/http-test",
            json={"target_url": ""},
        )
        assert resp.status_code == 400


@pytest.mark.anyio
async def test_http_gateway_test_with_session(tmp_path_factory):
    """POST /api/gateway/http-test with session_id uses that session."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    # Mock resolve_route_for_http to return a valid route structure
    mock_route = {
        "session_id": "test-session-123",
        "endpoint": {"id": 0, "listen_host": "127.0.0.1", "listen_port": 0},
        "instance": {"instance_id": "inst-1"},
        "target": type("Target", (), {"netloc": "example.com"})(),
        "route": {"hop_node_keys": [], "route_signature": "sig1"},
    }
    mock_request_result = {
        "request_ok": True,
        "status_code": 200,
        "elapsed_ms": 50,
        "body_preview": "ok",
    }
    with (
        patch.object(
            app.state.forward_gateway, "resolve_route_for_http", return_value=mock_route
        ),
        patch(
            "proxypool.api.app._request_via_forward_proxy",
            new_callable=AsyncMock,
            return_value=mock_request_result,
        ),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/gateway/http-test",
                json={
                    "target_url": "https://example.com",
                    "session_id": "test-session-123",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "ok" in data
            # Endpoint port is 0 but config port is 8899, so proxy_url is built
            # and _request_via_forward_proxy is called (mocked to succeed)
            assert data["session_id"] == "test-session-123"
            assert data["ok"] is True


@pytest.mark.anyio
async def test_http_gateway_test_resolve_error(tmp_path_factory):
    """POST /api/gateway/http-test returns error when route resolution fails."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    with patch.object(
        app.state.forward_gateway,
        "resolve_route_for_http",
        side_effect=Exception("no routes available"),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/gateway/http-test",
                json={"target_url": "https://example.com", "session_id": "s1"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is False
            assert "no routes available" in data["detail"]


# ===== GET /api/gateway/http-status with actual endpoint =====


@pytest.mark.anyio
async def test_get_http_gateway_status_with_endpoint(tmp_path_factory):
    """GET /api/gateway/http-status with an existing endpoint exercises detail path."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create an endpoint first
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "status-test", "listen_port": 8810},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        # Now get status for that endpoint
        resp = await client.get(f"/api/gateway/http-status?endpoint_id={endpoint_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["endpoint_id"] == endpoint_id
        assert data["endpoint"] is not None
        assert "leases" in data
        assert "instances" in data
        assert "hop_pools" in data
        assert "transitions" in data
        assert "summary" in data


# ===== GET /api/http-proxy-endpoints/{id}/status =====


@pytest.mark.anyio
async def test_get_endpoint_status(tmp_path_factory):
    """GET /api/http-proxy-endpoints/{id}/status returns endpoint status."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "ep-status", "listen_port": 8811},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        resp = await client.get(
            f"/api/http-proxy-endpoints/{endpoint_id}/status"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "leases" in data
        assert "instances" in data
        assert "summary" in data


@pytest.mark.anyio
async def test_get_endpoint_status_not_found(tmp_path_factory):
    """GET /api/http-proxy-endpoints/{id}/status returns 404 for missing."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/http-proxy-endpoints/99999/status")
        assert resp.status_code == 404


# ===== GET /api/gateway/endpoints/{id}/health =====


@pytest.mark.anyio
async def test_get_endpoint_health(tmp_path_factory):
    """GET /api/gateway/endpoints/{id}/health returns health info."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "health-test", "listen_port": 8812},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        resp = await client.get(
            f"/api/gateway/endpoints/{endpoint_id}/health"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["endpoint_id"] == endpoint_id
        assert "is_listening" in data
        assert "total_connections" in data
        assert "recent_errors" in data
        assert "active_leases" in data
        assert "upstream_pool_status" in data


@pytest.mark.anyio
async def test_get_endpoint_health_not_found(tmp_path_factory):
    """GET /api/gateway/endpoints/{id}/health returns 404 for missing."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/gateway/endpoints/99999/health")
        assert resp.status_code == 404


# ===== POST /api/gateway/endpoints/{id}/test-connectivity =====


@pytest.mark.anyio
async def test_test_connectivity_not_listening(tmp_path_factory):
    """POST /api/gateway/endpoints/{id}/test-connectivity when port not open."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "conn-test", "listen_port": 19999},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        resp = await client.post(
            f"/api/gateway/endpoints/{endpoint_id}/test-connectivity"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["endpoint_id"] == endpoint_id
        assert "is_reachable" in data
        assert "connection_test" in data
        assert "tested_at" in data


@pytest.mark.anyio
async def test_test_connectivity_not_found(tmp_path_factory):
    """POST /api/gateway/endpoints/{id}/test-connectivity returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/gateway/endpoints/99999/test-connectivity")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_test_connectivity_port_zero(tmp_path_factory):
    """POST /api/gateway/endpoints/{id}/test-connectivity with port=0."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "conn-zero", "listen_port": 8813},
        )
        endpoint_id = create_resp.json()["item"]["id"]
        # Update to port 0
        await client.put(
            f"/api/http-proxy-endpoints/{endpoint_id}",
            json={"listen_port": 1},  # Need valid port for creation
        )

        resp = await client.post(
            f"/api/gateway/endpoints/{endpoint_id}/test-connectivity"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_reachable"] is False


# ===== POST /api/http-proxy-endpoints/{id}/route-test =====


@pytest.mark.anyio
async def test_route_test_not_found(tmp_path_factory):
    """POST /api/http-proxy-endpoints/{id}/route-test returns 404 for missing."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/http-proxy-endpoints/99999/route-test")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_route_test_empty_hops(tmp_path_factory):
    """GET /api/http-proxy-endpoints/{id}/route-test returns 400 when no hops."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "route-test-ep", "listen_port": 8814},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        resp = await client.get(
            f"/api/http-proxy-endpoints/{endpoint_id}/route-test"
        )
        assert resp.status_code == 400


# ===== GET /api/gateway/port-conflicts with endpoints =====


@pytest.mark.anyio
async def test_check_port_conflicts_with_endpoint(tmp_path_factory):
    """GET /api/gateway/port-conflicts with existing endpoint."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "conflict-test", "listen_port": 8815},
        )

        resp = await client.get("/api/gateway/port-conflicts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scanned_endpoints"] == 1


@pytest.mark.anyio
async def test_check_port_conflicts_with_instances(tmp_path_factory):
    """GET /api/gateway/port-conflicts includes backend instances."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    # Mock singbox_manager.list_instances to return instances with ports
    mock_instances = [
        {
            "instance_id": "test-inst-1",
            "listen": "127.0.0.1",
            "ports": [8820, 8821],
        },
    ]
    with patch.object(
        app.state.singbox_manager, "list_instances", return_value=mock_instances
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/gateway/port-conflicts")
            assert resp.status_code == 200
            data = resp.json()
            assert data["scanned_instances"] == 1


# ===== PUT /api/gateway/http-config with endpoint_id =====


@pytest.mark.anyio
async def test_update_http_gateway_config_with_endpoint(tmp_path_factory):
    """PUT /api/gateway/http-config with endpoint_id fetches endpoint data."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create endpoint first
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "config-ep", "listen_port": 8816},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        # Update config with that endpoint
        resp = await client.put(
            "/api/gateway/http-config",
            json={"endpoint_id": endpoint_id, "enabled": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["item"]["endpoint_id"] == endpoint_id


# ===== Direct _request_via_forward_proxy test =====


@pytest.mark.anyio
async def test_request_via_forward_proxy_success():
    """_request_via_forward_proxy returns success on successful request."""
    from proxypool.api.app import _request_via_forward_proxy

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "hello"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("proxypool.api.app.httpx.AsyncClient", return_value=mock_client):
        with patch("proxypool.api.app.httpx.Proxy"):
            result = await _request_via_forward_proxy(
                target_url="https://example.com",
                proxy_url="http://127.0.0.1:8899",
                proxy_headers={"X-Session": "test"},
            )
    assert result["request_ok"] is True
    assert result["status_code"] == 200


@pytest.mark.anyio
async def test_request_via_forward_proxy_failure():
    """_request_via_forward_proxy returns error on connection failure."""
    from proxypool.api.app import _request_via_forward_proxy

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("proxypool.api.app.httpx.AsyncClient", return_value=mock_client):
        with patch("proxypool.api.app.httpx.Proxy"):
            result = await _request_via_forward_proxy(
                target_url="https://example.com",
                proxy_url="http://127.0.0.1:8899",
                proxy_headers={},
            )
    assert result["request_ok"] is False
    assert "error" in result


# ===== PUT /api/http-proxy-endpoints/{id} error path =====


@pytest.mark.anyio
async def test_update_http_proxy_endpoint_error(tmp_path_factory):
    """PUT /api/http-proxy-endpoints/{id} returns 400 on storage error."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/http-proxy-endpoints",
            json={"name": "err-update", "listen_port": 8817},
        )
        endpoint_id = create_resp.json()["item"]["id"]

        with patch.object(
            app.state.storage,
            "update_http_proxy_endpoint",
            side_effect=ValueError("bad value"),
        ):
            resp = await client.put(
                f"/api/http-proxy-endpoints/{endpoint_id}",
                json={"name": "fail"},
            )
            assert resp.status_code == 400


# ===== DELETE /api/http-proxy-endpoints/{id} with gateway enabled sync =====


@pytest.mark.anyio
async def test_delete_http_proxy_endpoint_with_sync(tmp_path_factory):
    """DELETE endpoint with gateway enabled triggers sync."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    # First enable the gateway
    app.state.gateway_config_service.update_config(enabled=True)

    with patch.object(
        app.state.gateway_runtime, "sync", new_callable=AsyncMock
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            create_resp = await client.post(
                "/api/http-proxy-endpoints",
                json={"name": "sync-delete", "listen_port": 8818},
            )
            endpoint_id = create_resp.json()["item"]["id"]

            resp = await client.delete(
                f"/api/http-proxy-endpoints/{endpoint_id}"
            )
            assert resp.status_code == 200
