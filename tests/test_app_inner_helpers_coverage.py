"""
Tests for app.py inner helper functions targeting uncovered lines.

Covers:
- _probe_gateway_node (lines 561-586): both normal and exception paths
- _run_gateway_health_once (lines 613-718): endpoint probing, failure reporting
- _backend_health_loop exception path (lines 735-738)
- _auto_task_loop exception handling (lines 954-956)
- _build_http_gateway_status full path (lines 377-425)
- _proxy_status_summary with None (lines 203-206)
- Speed/tester task starters (lines 740-906)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


def _make_settings(tmp_path: Path, *, api_key: str = "") -> AppSettings:
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
        api_key=api_key,
        http_gateway_default_host="127.0.0.1",
        http_gateway_default_port=8899,
        backend_engine="singbox",
        backend_health_check_sec=30,
        backend_auto_restart_max=3,
        mihomo_binary="mihomo",
        mihomo_runtime_dir=tmp_path / "runtime" / "mihomo",
    )


def _setup_endpoint(app, storage, port, pool_name="pool", ep_name="ep"):
    """Create pool + endpoint with 1 hop, return (endpoint_id, pool_id, key)."""
    from proxypool.models import ProxyNode

    pool = storage.create_proxy_pool(
        name=pool_name, gateway_path_prefix=f"/proxy/{pool_name}"
    )
    pool_id = int(pool.get("id") or 0)

    node = ProxyNode(
        protocol="trojan", host=f"{pool_name}.example.com", port=443,
        raw_link=f"trojan://{pool_name}.example.com:443",
        extra={"password": "test", "sni": "example.com"},
        name=f"{pool_name}-proxy",
    )
    key = storage.upsert_proxy(node, source="test")

    endpoint = storage.create_http_proxy_endpoint(
        name=ep_name, listen_host="127.0.0.1", listen_port=port,
    )
    endpoint_id = int(endpoint.get("id") or 0)
    storage.replace_http_proxy_endpoint_hops(endpoint_id, [pool_id])
    return endpoint_id, pool_id, key


# ---------------------------------------------------------------------------
# 1. _probe_gateway_node via health loop (lines 561-586)
# ---------------------------------------------------------------------------


class TestProbeGatewayNode:
    @pytest.mark.anyio
    async def test_probe_node_exception_path(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        storage = app.state.storage

        _setup_endpoint(app, storage, 18099, "probe-pool", "probe-ep")

        async def fake_probe_async(node_dict, **kwargs):
            raise RuntimeError("probe failed")

        app.state.tester.prober.probe_async = fake_probe_async
        app.state.tester.prober.probe_with_front_proxy_async = fake_probe_async

        app.state.gateway_config_service.update_config(
            enabled=True, health_check_enabled=True, health_check_interval_sec=5,
        )

        async with app.router.lifespan_context(app):
            await asyncio.sleep(3)
            snapshot = app.state.gateway_health_snapshot
            for ep_data in snapshot.get("endpoints", {}).values():
                for hop in ep_data.get("hops", []):
                    for n in hop.get("nodes", []):
                        assert n.get("ok") is False
            app.state.backend_health_task.cancel()
            app.state.auto_task_runner.cancel()
            app.state.gateway_health_task.cancel()

    @pytest.mark.anyio
    async def test_probe_node_normal_success(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        storage = app.state.storage

        endpoint_id, pool_id, key = _setup_endpoint(
            app, storage, 18100, "good-pool", "good-ep"
        )

        async def fake_probe_async(node_dict, **kwargs):
            return SimpleNamespace(
                normalized_key=key, available=True, latency_ms=50,
                openai_unlocked=False, openai_status="", error="",
            )

        app.state.tester.prober.probe_async = fake_probe_async
        app.state.tester.prober.probe_with_front_proxy_async = fake_probe_async

        app.state.gateway_config_service.update_config(
            enabled=True, health_check_enabled=True, health_check_interval_sec=5,
        )

        async with app.router.lifespan_context(app):
            await asyncio.sleep(3)
            snapshot = app.state.gateway_health_snapshot
            for ep_data in snapshot.get("endpoints", {}).values():
                for hop in ep_data.get("hops", []):
                    for n in hop.get("nodes", []):
                        if n.get("normalized_key") == key:
                            assert n.get("ok") is True
            app.state.backend_health_task.cancel()
            app.state.auto_task_runner.cancel()
            app.state.gateway_health_task.cancel()


# ---------------------------------------------------------------------------
# 2. _run_gateway_health_once exception handling (lines 707-718)
# ---------------------------------------------------------------------------


class TestGatewayHealthOnceException:
    @pytest.mark.anyio
    async def test_health_once_exception_updates_snapshot(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        original_method = app.state.storage.list_http_proxy_endpoints

        def failing_list(*args, **kwargs):
            raise RuntimeError("storage broken")

        app.state.storage.list_http_proxy_endpoints = failing_list

        app.state.gateway_config_service.update_config(
            enabled=True, health_check_enabled=True, health_check_interval_sec=5,
        )

        async with app.router.lifespan_context(app):
            await asyncio.sleep(3)
            snapshot = app.state.gateway_health_snapshot
            assert snapshot.get("last_error") != "" or snapshot.get("running") is False
            app.state.backend_health_task.cancel()
            app.state.auto_task_runner.cancel()
            app.state.gateway_health_task.cancel()

        app.state.storage.list_http_proxy_endpoints = original_method


# ---------------------------------------------------------------------------
# 3. _build_http_gateway_status with endpoint data (lines 377-425)
# ---------------------------------------------------------------------------


class TestBuildHttpGatewayStatus:
    @pytest.mark.anyio
    async def test_gateway_status_with_active_endpoint(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        storage = app.state.storage

        endpoint_id, _, _ = _setup_endpoint(app, storage, 18101, "active-pool", "active-ep")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/gateway/http-status?endpoint_id={endpoint_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("endpoint") is not None
            assert data.get("hop_pools") is not None

    @pytest.mark.anyio
    async def test_gateway_status_no_hops(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        storage = app.state.storage

        endpoint = storage.create_http_proxy_endpoint(
            name="no-hop-ep", listen_host="127.0.0.1", listen_port=18102,
        )
        endpoint_id = int(endpoint.get("id") or 0)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/gateway/http-status?endpoint_id={endpoint_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("endpoint") is not None


# ---------------------------------------------------------------------------
# 4. Backend health loop exception path (lines 735-738)
# ---------------------------------------------------------------------------


class TestBackendHealthLoopException:
    @pytest.mark.anyio
    async def test_exception_suppressed(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        async def failing_health_check(**kwargs):
            raise RuntimeError("health check failed")

        app.state.singbox_manager.health_check_async = failing_health_check

        async with app.router.lifespan_context(app):
            await asyncio.sleep(7)
            assert app.state.backend_health_task is not None
            app.state.backend_health_task.cancel()
            app.state.auto_task_runner.cancel()
            app.state.gateway_health_task.cancel()


# ---------------------------------------------------------------------------
# 5. Auto task loop exception handling (lines 954-956)
# ---------------------------------------------------------------------------


class TestAutoTaskLoopException:
    @pytest.mark.anyio
    async def test_exception_suppressed(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        app.state.auto_task_config = {
            "enabled": True,
            "subscription_refresh_enabled": True,
            "subscription_refresh_minutes": 0,
            "tester_enabled": True,
            "tester_minutes": 0,
            "tester_limit": 0,
            "tester_concurrency": 50,
            "speed_test_enabled": True,
            "speed_test_minutes": 0,
            "speed_test_url": "https://speed.example.com/test",
            "speed_test_limit": 0,
            "speed_test_timeout_sec": 30.0,
        }

        def failing_collect(**kwargs):
            raise RuntimeError("collector broken")

        app.state.collector.collect_from_subscription = failing_collect

        async with app.router.lifespan_context(app):
            await asyncio.sleep(7)
            assert app.state.auto_task_runner is not None
            app.state.backend_health_task.cancel()
            app.state.auto_task_runner.cancel()
            app.state.gateway_health_task.cancel()


# ---------------------------------------------------------------------------
# 6. Gateway health loop exception (lines 727-728)
# ---------------------------------------------------------------------------


class TestGatewayHealthLoopException:
    @pytest.mark.anyio
    async def test_exception_suppressed(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        app.state.gateway_config_service.update_config(
            enabled=True, health_check_enabled=True, health_check_interval_sec=5,
        )

        original_method = app.state.storage.list_http_proxy_endpoints

        def failing_list(*args, **kwargs):
            raise RuntimeError("storage broken")

        app.state.storage.list_http_proxy_endpoints = failing_list

        async with app.router.lifespan_context(app):
            await asyncio.sleep(7)
            assert app.state.gateway_health_task is not None
            app.state.backend_health_task.cancel()
            app.state.auto_task_runner.cancel()
            app.state.gateway_health_task.cancel()

        app.state.storage.list_http_proxy_endpoints = original_method


# ---------------------------------------------------------------------------
# 7. _proxy_status_summary with None (lines 203-206)
# ---------------------------------------------------------------------------


class TestProxyStatusSummaryNone:
    @pytest.mark.anyio
    async def test_gateway_status_empty_endpoint(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/gateway/http-status")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("endpoint") is None
            assert data.get("hop_pools") == []


# ---------------------------------------------------------------------------
# 8. Subscription refresh task (lines 805-875)
# ---------------------------------------------------------------------------


class TestSubscriptionRefreshTask:
    @pytest.mark.anyio
    async def test_start_task(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)
        storage = app.state.storage

        storage.create_subscription(
            name="test-sub", url="https://example.com/sub", enabled=True
        )

        from proxypool.collector.service import CollectReport, SourceCollectReport

        def fake_collect(**kwargs):
            return CollectReport(
                total_sources=1, total_parsed=5, total_inserted=3,
                by_source=[SourceCollectReport(source="test", parsed=5, inserted=3)],
            )

        app.state.collector.collect_from_subscription = fake_collect

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/subscriptions-refresh/start",
                params={"timeout_sec": 5.0},
            )
            assert resp.status_code == 200
            assert "task_id" in resp.json()


# ---------------------------------------------------------------------------
# 9. Speed test task (lines 740-803)
# ---------------------------------------------------------------------------


class TestSpeedTestTask:
    @pytest.mark.anyio
    async def test_start_task(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/speed-test/start",
                json={"url": "https://speed.cloudflare.com/__down?bytes=1000",
                       "limit": 0, "timeout_sec": 5.0, "only_available": True},
            )
            assert resp.status_code == 200
            assert "task_id" in resp.json()

    @pytest.mark.anyio
    async def test_invalid_url(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/speed-test/start",
                json={"url": "ftp://invalid.example.com"},
            )
            assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 10. Tester task (lines 877-906)
# ---------------------------------------------------------------------------


class TestTesterTask:
    @pytest.mark.anyio
    async def test_start_task(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        app = create_app(settings)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/tester/start",
                json={"limit": 0, "concurrency": 10, "only_unchecked": False,
                      "only_available": False, "only_unavailable": False,
                      "min_last_checked_age_hours": 0},
            )
            assert resp.status_code == 200
            assert "task_id" in resp.json()
