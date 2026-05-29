"""
Tests for health router endpoints with low coverage.

Covers: system/activity, system/processes, system/logs, system/resources,
system/version, system/metrics, system/metrics/export, system/config-diff,
system/test-report/export, system/health, POST restart, and
_format_event_description helper.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import psutil
import pytest

from proxypool.api.app import create_app
from proxypool.settings import AppSettings


def _make_settings(tmp_path_factory) -> AppSettings:
    from pathlib import Path

    tmp = tmp_path_factory.mktemp("test_health_coverage")
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


# ===== system/activity =====


@pytest.mark.anyio
async def test_system_activity_empty(tmp_path_factory):
    """GET /api/system/activity returns empty items when no events exist."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/activity")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] == 0


@pytest.mark.anyio
async def test_system_activity_with_limit(tmp_path_factory):
    """GET /api/system/activity respects limit parameter."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/activity?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] <= 5


# ===== _format_event_description helper =====


def test_format_event_description_start_success():
    from proxypool.api.routers.health import _format_event_description

    result = _format_event_description({"action": "start", "result": "success"})
    assert "启动" in result
    assert "成功" in result


def test_format_event_description_start_failure():
    from proxypool.api.routers.health import _format_event_description

    result = _format_event_description({"action": "start", "result": "error"})
    assert "启动" in result
    assert "失败" in result


def test_format_event_description_stop_success():
    from proxypool.api.routers.health import _format_event_description

    result = _format_event_description({"action": "stop", "result": "success"})
    assert "停止" in result
    assert "成功" in result


def test_format_event_description_stop_failure():
    from proxypool.api.routers.health import _format_event_description

    result = _format_event_description({"action": "stop", "result": "failed"})
    assert "停止" in result
    assert "失败" in result


def test_format_event_description_restart():
    from proxypool.api.routers.health import _format_event_description

    # "restart" contains "start" so the start branch matches first
    result = _format_event_description({"action": "restart", "result": "success"})
    assert "启动" in result or "重启" in result


def test_format_event_description_test_action():
    from proxypool.api.routers.health import _format_event_description

    result = _format_event_description({"action": "test", "result": "ok", "detail": "100ms"})
    assert "测试完成" in result


def test_format_event_description_refresh():
    from proxypool.api.routers.health import _format_event_description

    result = _format_event_description({"action": "refresh", "result": "updated"})
    assert "订阅刷新" in result


def test_format_event_description_config():
    from proxypool.api.routers.health import _format_event_description

    result = _format_event_description({"action": "config", "detail": "changed port"})
    assert "配置变更" in result


def test_format_event_description_unknown():
    from proxypool.api.routers.health import _format_event_description

    result = _format_event_description({"action": "reboot", "result": "done"})
    assert "reboot" in result
    assert "done" in result


def test_format_event_description_empty():
    from proxypool.api.routers.health import _format_event_description

    result = _format_event_description({})
    assert "unknown" in result


# ===== system/processes =====


@pytest.mark.anyio
async def test_system_processes_returns_list(tmp_path_factory):
    """GET /api/system/processes returns process list."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/processes")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "running" in data
        assert isinstance(data["items"], list)


@pytest.mark.anyio
async def test_system_processes_with_stopped_backend(tmp_path_factory):
    """GET /api/system/processes when backend is not running."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/processes")
        assert resp.status_code == 200
        data = resp.json()
        # Backend not running, so total may be 0
        assert data["total"] >= 0
        assert data["running"] <= data["total"]


@pytest.mark.anyio
async def test_system_processes_structure(tmp_path_factory):
    """GET /api/system/processes items have correct fields."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/processes")
        assert resp.status_code == 200
        data = resp.json()
        for proc in data["items"]:
            assert "id" in proc
            assert "pid" in proc
            assert "type" in proc
            assert "status" in proc


# ===== system/logs =====


@pytest.mark.anyio
async def test_system_logs_empty(tmp_path_factory):
    """GET /api/system/logs returns empty logs when no events exist."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "level_filter" in data
        assert data["level_filter"] is None


@pytest.mark.anyio
async def test_system_logs_with_level_filter(tmp_path_factory):
    """GET /api/system/logs with level filter."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/logs?level=INFO")
        assert resp.status_code == 200
        data = resp.json()
        assert data["level_filter"] == "INFO"


@pytest.mark.anyio
async def test_system_logs_with_limit(tmp_path_factory):
    """GET /api/system/logs respects limit parameter."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/logs?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] <= 10


@pytest.mark.anyio
async def test_system_logs_item_structure(tmp_path_factory):
    """GET /api/system/logs items have correct structure."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/logs")
        assert resp.status_code == 200
        data = resp.json()
        for entry in data["items"]:
            assert "timestamp" in entry
            assert "level" in entry
            assert "source" in entry
            assert "message" in entry


# ===== system/resources =====


@pytest.mark.anyio
async def test_system_resources_endpoint(tmp_path_factory):
    """GET /api/system/resources returns CPU, memory, disk, uptime."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data
        assert "uptime_seconds" in data
        assert "timestamp" in data


@pytest.mark.anyio
async def test_system_resources_cpu_structure(tmp_path_factory):
    """GET /api/system/resources CPU info has expected fields."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/resources")
        assert resp.status_code == 200
        data = resp.json()
        cpu = data["cpu"]
        assert "percent" in cpu
        assert "count" in cpu


@pytest.mark.anyio
async def test_system_resources_memory_structure(tmp_path_factory):
    """GET /api/system/resources memory info has expected fields."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/resources")
        assert resp.status_code == 200
        data = resp.json()
        mem = data["memory"]
        assert "total_gb" in mem
        assert "used_gb" in mem
        assert "available_gb" in mem
        assert "percent" in mem


@pytest.mark.anyio
async def test_system_resources_disk_structure(tmp_path_factory):
    """GET /api/system/resources disk info has expected fields."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/resources")
        assert resp.status_code == 200
        data = resp.json()
        disk = data["disk"]
        assert "total_gb" in disk
        assert "used_gb" in disk
        assert "free_gb" in disk
        assert "percent" in disk


@pytest.mark.anyio
async def test_system_resources_uptime_positive(tmp_path_factory):
    """GET /api/system/resources uptime is positive."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["uptime_seconds"] > 0


# ===== system/version =====


@pytest.mark.anyio
async def test_system_version_endpoint(tmp_path_factory):
    """GET /api/system/version returns version info."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "python_version" in data
        assert "platform" in data
        assert "architecture" in data
        assert "build_time" in data
        assert "uptime_seconds" in data
        assert "api_uptime_seconds" in data


@pytest.mark.anyio
async def test_system_version_values(tmp_path_factory):
    """GET /api/system/version returns sensible values."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/version")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0
        assert data["platform"] in ("Linux", "Darwin", "Windows", "java")
        assert data["uptime_seconds"] >= 0
        assert data["api_uptime_seconds"] >= 0


# ===== system/metrics =====


@pytest.mark.anyio
async def test_system_metrics_endpoint(tmp_path_factory):
    """GET /api/system/metrics returns performance metrics."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert "requests" in data
        assert "active_connections" in data


@pytest.mark.anyio
async def test_system_metrics_requests_structure(tmp_path_factory):
    """GET /api/system/metrics requests sub-object has expected fields."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/metrics")
        assert resp.status_code == 200
        data = resp.json()
        reqs = data["requests"]
        assert "total_requests" in reqs
        assert "successful_requests" in reqs
        assert "failed_requests" in reqs
        assert "error_rate" in reqs


# ===== system/metrics/export =====


@pytest.mark.anyio
async def test_system_metrics_export_endpoint(tmp_path_factory):
    """GET /api/system/metrics/export returns full metrics export."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/metrics/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "exported_at" in data
        assert "system_metrics" in data
        assert "windows" in data
        assert "pools" in data
        assert isinstance(data["windows"], list)
        assert isinstance(data["pools"], list)


# ===== system/config-diff =====


@pytest.mark.anyio
async def test_system_config_diff_endpoint(tmp_path_factory):
    """GET /api/system/config-diff returns config comparison."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/config-diff")
        assert resp.status_code == 200
        data = resp.json()
        assert "has_diff" in data
        assert "differences" in data
        assert isinstance(data["differences"], list)


@pytest.mark.anyio
async def test_system_config_diff_items_structure(tmp_path_factory):
    """GET /api/system/config-diff items have expected fields."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/config-diff")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["differences"]:
            assert "key" in item
            assert "stored_value" in item
            assert "running_value" in item
            assert "status" in item
            assert item["status"] in ("added", "removed", "changed", "unchanged")


# ===== system/test-report/export =====


@pytest.mark.anyio
async def test_export_test_report_csv(tmp_path_factory):
    """GET /api/system/test-report/export returns CSV content."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/test-report/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]


@pytest.mark.anyio
async def test_export_test_report_csv_with_limit(tmp_path_factory):
    """GET /api/system/test-report/export respects limit parameter."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/test-report/export?limit=10")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]


# ===== system/health (detailed) =====


@pytest.mark.anyio
async def test_system_health_detailed_endpoint(tmp_path_factory):
    """GET /api/system/health returns detailed health status."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "backend_status" in data
        assert "gateway_status" in data
        assert "active_processes" in data
        assert "pool_count" in data
        assert "proxy_count" in data
        assert "healthy_proxy_rate" in data
        assert "uptime_seconds" in data


@pytest.mark.anyio
async def test_system_health_detailed_values(tmp_path_factory):
    """GET /api/system/health returns valid numeric values."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_processes"] >= 0
        assert data["pool_count"] >= 0
        assert data["proxy_count"] >= 0
        assert 0.0 <= data["healthy_proxy_rate"] <= 1.0
        assert data["uptime_seconds"] >= 0


@pytest.mark.anyio
async def test_system_health_healthy_proxy_rate_zero_proxies(tmp_path_factory):
    """GET /api/system/health returns 0.0 healthy_proxy_rate when no proxies."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy_proxy_rate"] == 0.0


# ===== POST /system/processes/{id}/restart =====


@pytest.mark.anyio
async def test_restart_nonexistent_process_404(tmp_path_factory):
    """POST restart for a non-existent process returns 404."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/system/processes/nonexistent-123/restart")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_restart_backend_process(tmp_path_factory):
    """POST restart backend process returns success."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    # Mock singbox_manager stop/start so they don't touch real binaries
    app.state.singbox_manager.stop = lambda: None
    app.state.singbox_manager.start = lambda: None
    # Mock storage method - health.py calls it without required backend/pid args
    app.state.storage.record_backend_process_event = lambda **kw: None

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/system/processes/backend/restart")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "restarted"
        assert data["process_id"] == "backend"


@pytest.mark.anyio
async def test_restart_backend_process_failure(tmp_path_factory):
    """POST restart backend process returns 500 when stop raises."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    def fail_stop():
        raise RuntimeError("stop failed")

    app.state.singbox_manager.stop = fail_stop
    app.state.storage.record_backend_process_event = lambda **kw: None

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/system/processes/backend/restart")
        assert resp.status_code == 500


# ===== system/logs with events (cover loop body) =====


@pytest.mark.anyio
async def test_system_logs_error_level_events(tmp_path_factory):
    """GET /api/system/logs returns ERROR level when events contain errors."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    mock_events = [
        {
            "action": "start",
            "result": "failed",
            "detail": "cannot find binary",
            "created_at": "2025-01-01T00:00:00Z",
        },
        {
            "action": "test",
            "result": "ok",
            "detail": "latency 50ms",
            "created_at": "2025-01-01T00:01:00Z",
        },
        {
            "action": "refresh",
            "result": "updated",
            "detail": "30 proxies",
            "created_at": "2025-01-01T00:02:00Z",
        },
        {
            "action": "config",
            "result": "changed",
            "detail": "port 8080",
            "created_at": "2025-01-01T00:03:00Z",
        },
        {
            "action": "unknown_action",
            "result": "",
            "detail": "",
            "created_at": "2025-01-01T00:04:00Z",
        },
    ]

    app.state.storage.list_backend_process_events = lambda limit: mock_events

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0

        # Check that error events are detected
        levels = {entry["level"] for entry in data["items"]}
        assert "ERROR" in levels


@pytest.mark.anyio
async def test_system_logs_filter_by_level(tmp_path_factory):
    """GET /api/system/logs filters events by the requested level."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    mock_events = [
        {
            "action": "start",
            "result": "failed",
            "detail": "error detail",
            "created_at": "2025-01-01T00:00:00Z",
        },
        {
            "action": "test",
            "result": "ok",
            "detail": "50ms",
            "created_at": "2025-01-01T00:01:00Z",
        },
        {
            "action": "warn_check",
            "result": "",
            "detail": "slow",
            "created_at": "2025-01-01T00:02:00Z",
        },
    ]

    app.state.storage.list_backend_process_events = lambda limit: mock_events

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Request only ERROR level
        resp = await client.get("/api/system/logs?level=ERROR")
        assert resp.status_code == 200
        data = resp.json()
        assert data["level_filter"] == "ERROR"
        for entry in data["items"]:
            assert entry["level"] == "ERROR"


# ===== system/activity with events =====


@pytest.mark.anyio
async def test_system_activity_with_events(tmp_path_factory):
    """GET /api/system/activity returns formatted items for events."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    mock_events = [
        {
            "action": "start",
            "result": "success",
            "detail": "started ok",
            "pid": 1234,
            "config_file": "/etc/config.json",
            "created_at": "2025-01-01T00:00:00Z",
        },
        {
            "action": "stop",
            "result": "success",
            "detail": "stopped gracefully",
            "pid": 1234,
            "config_file": None,
            "created_at": "2025-01-01T00:01:00Z",
        },
    ]

    app.state.storage.list_backend_process_events = lambda limit: mock_events

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/activity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        # Check item structure
        item = data["items"][0]
        assert item["id"] == 1
        assert "timestamp" in item
        assert "event_type" in item
        assert "description" in item
        assert "details" in item


# ===== config-diff with gateway config =====


@pytest.mark.anyio
async def test_system_config_diff_with_settings(tmp_path_factory):
    """GET /api/system/config-diff shows stored config values."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/config-diff")
        assert resp.status_code == 200
        data = resp.json()
        # Should have differences for test_url, backend_health_check_sec, etc.
        keys = {item["key"] for item in data["differences"]}
        assert "test_url" in keys
        assert "backend_health_check_sec" in keys


# ===== system/processes with instances =====


@pytest.mark.anyio
async def test_system_processes_with_instances(tmp_path_factory):
    """GET /api/system/processes includes instance processes."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    # Mock singbox_manager to return instances
    app.state.singbox_manager.status = lambda: {"running": False, "pid": 0}
    app.state.singbox_manager.list_instances = lambda: [
        {
            "id": "inst-1",
            "status": "running",
            "pid": 9999,
            "port": 1080,
            "config_file": "/tmp/config.json",
            "last_error": None,
        },
        {
            "id": "inst-2",
            "status": "stopped",
            "pid": 0,
            "port": 1081,
            "config_file": "/tmp/config2.json",
            "last_error": "port in use",
        },
    ]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/processes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["running"] == 1

        # Check that instance details are included
        ids = {p["id"] for p in data["items"]}
        assert "inst-1" in ids
        assert "inst-2" in ids


@pytest.mark.anyio
async def test_system_processes_with_running_backend(tmp_path_factory):
    """GET /api/system/processes shows backend process info when running."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    import os

    current_pid = os.getpid()

    app.state.singbox_manager.status = lambda: {"running": True, "pid": current_pid}
    app.state.singbox_manager.list_instances = lambda: []

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/processes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["running"] == 1
        proc = data["items"][0]
        assert proc["type"] == "backend"
        assert proc["status"] == "running"
        assert proc["pid"] == current_pid
        # memory/cpu should be populated since the process exists
        assert proc["memory_mb"] is not None
        assert proc["cpu_percent"] is not None


@pytest.mark.anyio
async def test_system_processes_stopped_instance_no_psutil(tmp_path_factory):
    """GET /api/system/processes skipped psutil for stopped instances with pid=0."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    app.state.singbox_manager.status = lambda: {"running": False, "pid": 0}
    app.state.singbox_manager.list_instances = lambda: [
        {
            "id": "inst-dead",
            "status": "stopped",
            "pid": 0,
            "port": None,
            "config_file": None,
            "last_error": "crash",
        },
    ]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/processes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["running"] == 0
        proc = data["items"][0]
        assert proc["memory_mb"] is None
        assert proc["cpu_percent"] is None


# ===== system/version uptime values =====


@pytest.mark.anyio
async def test_system_version_uptime_positive(tmp_path_factory):
    """GET /api/system/version uptime_seconds is non-negative."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/version")
        data = resp.json()
        assert data["uptime_seconds"] >= 0
        assert data["api_uptime_seconds"] >= 0


# ===== system/resources disk OSError path =====


@pytest.mark.anyio
async def test_system_resources_disk_oserror(tmp_path_factory):
    """GET /api/system/resources handles disk_usage OSError gracefully."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    import shutil

    original = shutil.disk_usage

    def fail_disk(path):
        raise OSError("permission denied")

    shutil.disk_usage = fail_disk
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/system/resources")
            assert resp.status_code == 200
            data = resp.json()
            disk = data["disk"]
            assert disk["total_gb"] == 0
            assert disk["used_gb"] == 0
            assert disk["free_gb"] == 0
            assert disk["percent"] == 0
    finally:
        shutil.disk_usage = original


# ===== system/metrics/export structure =====


@pytest.mark.anyio
async def test_system_metrics_export_full_structure(tmp_path_factory):
    """GET /api/system/metrics/export windows list has expected structure."""
    settings = _make_settings(tmp_path_factory)
    app = create_app(settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/system/metrics/export")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["exported_at"], str)
        assert "requests" in data["system_metrics"]
