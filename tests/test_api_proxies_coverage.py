"""
Tests for proxies router endpoints with low coverage.

Covers: import-files, import-urls, import-sources, import-sources-file,
import-output, delete-unavailable, delete-selected, batch-test,
geoip enrich/ip-purity stubs, and _read_sources_file.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.collector.service import CollectReport, SourceCollectReport
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
        http_gateway_default_host="127.0.0.1",
        http_gateway_default_port=8899,
        backend_engine="singbox",
        backend_health_check_sec=30,
        backend_auto_restart_max=3,
        mihomo_binary="mihomo",
        mihomo_runtime_dir=tmp_path / "runtime" / "mihomo",
    )


def _fake_report() -> CollectReport:
    return CollectReport(
        total_sources=1,
        total_parsed=1,
        total_inserted=1,
        total_updated=0,
        total_deduped=0,
        total_invalid=0,
        by_source=[
            SourceCollectReport(
                source="test",
                parsed=1,
                inserted=1,
                updated=0,
                deduped=0,
                invalid=0,
            )
        ],
    )


# ===== import-files =====


@pytest.mark.anyio
async def test_import_files_empty_paths_returns_400(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/collector/import-files", json={"paths": []})
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_import_files_not_found_returns_400(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    # Mock validate_file_path_or_raise to bypass path restriction and return the path
    monkeypatch.setattr(
        "proxypool.api.routers.proxies.validate_file_path_or_raise",
        lambda p: Path(p).resolve(),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/collector/import-files",
            json={"paths": [str(tmp_path / "nonexistent.txt")]},
        )
        assert resp.status_code == 400
        assert "file not found" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_import_files_directory_returns_400(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    monkeypatch.setattr(
        "proxypool.api.routers.proxies.validate_file_path_or_raise",
        lambda p: Path(p).resolve(),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/collector/import-files",
            json={"paths": [str(tmp_path)]},
        )
        assert resp.status_code == 400
        assert "not a file" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_import_files_success(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("trojan://host:443\n")

    monkeypatch.setattr(
        "proxypool.api.routers.proxies.validate_file_path_or_raise",
        lambda p: Path(p).resolve(),
    )
    monkeypatch.setattr(
        app.state.collector, "collect_from_files", lambda paths: _fake_report()
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/collector/import-files",
            json={"paths": [str(proxy_file)]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_parsed"] == 1
        assert data["total_inserted"] == 1


# ===== import-urls =====


@pytest.mark.anyio
async def test_import_urls_empty_returns_400(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/collector/import-urls", json={"urls": []})
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_import_urls_success(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    def fake_collect_from_urls(urls, timeout):
        return _fake_report()

    monkeypatch.setattr(app.state.collector, "collect_from_urls", fake_collect_from_urls)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/collector/import-urls",
            json={"urls": ["https://example.com/proxies.txt"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_parsed"] == 1


# ===== import-sources =====


@pytest.mark.anyio
async def test_import_sources_empty_returns_400(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/collector/import-sources", json={"sources": []})
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_import_sources_url_success(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    def fake_collect(sources, timeout):
        return _fake_report()

    monkeypatch.setattr(app.state.collector, "collect_from_sources", fake_collect)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/collector/import-sources",
            json={"sources": ["https://example.com/sub.txt"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_parsed"] == 1


@pytest.mark.anyio
async def test_import_sources_file_path_success(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    sources_file = tmp_path / "mysources.txt"
    sources_file.write_text("trojan://host:443\n")

    monkeypatch.setattr(
        "proxypool.api.routers.proxies.validate_file_path_or_raise",
        lambda p: Path(p).resolve(),
    )

    def fake_collect(sources, timeout):
        return _fake_report()

    monkeypatch.setattr(app.state.collector, "collect_from_sources", fake_collect)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/collector/import-sources",
            json={"sources": [str(sources_file)]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_parsed"] == 1


@pytest.mark.anyio
async def test_import_sources_data_uri(tmp_path: Path, monkeypatch) -> None:
    """Test that data: URIs pass through validation."""
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    def fake_collect(sources, timeout):
        return _fake_report()

    monkeypatch.setattr(app.state.collector, "collect_from_sources", fake_collect)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/collector/import-sources",
            json={"sources": ["data:text/plain;base64,dGVzdA=="]},
        )
        assert resp.status_code == 200


# ===== import-sources-file =====


@pytest.mark.anyio
async def test_import_sources_file_no_sources_returns_400(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    # sources.txt doesn't exist
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/collector/import-sources-file")
        assert resp.status_code == 400
        assert "no valid sources" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_import_sources_file_success(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    settings.sources_file.write_text("https://example.com/sub.txt\n")

    def fake_collect(sources, timeout=None):
        return _fake_report()

    monkeypatch.setattr(app.state.collector, "collect_from_sources", fake_collect)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/collector/import-sources-file")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_parsed"] == 1


@pytest.mark.anyio
async def test_import_sources_file_skips_comments_and_blank(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    settings.sources_file.write_text("# comment\n\n  \nhttps://example.com/sub.txt\n# another\n")

    def fake_collect(sources, timeout=None):
        return _fake_report()

    monkeypatch.setattr(app.state.collector, "collect_from_sources", fake_collect)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/collector/import-sources-file")
        assert resp.status_code == 200


@pytest.mark.anyio
async def test_import_sources_file_all_comments_returns_400(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    settings.sources_file.write_text("# only comments\n# another comment\n")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/collector/import-sources-file")
        assert resp.status_code == 400


# ===== import-output =====


@pytest.mark.anyio
async def test_import_output_empty_dir(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    def fake_collect_files(paths):
        return _fake_report()

    with pytest.MonkeyPatch.context() as m:
        m.setattr(app.state.collector, "collect_from_files", fake_collect_files)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/collector/import-output")
            assert resp.status_code == 200


@pytest.mark.anyio
async def test_import_output_with_files(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "out.txt").write_text("trojan://host:443\n")

    def fake_collect_files(paths):
        return _fake_report()

    with pytest.MonkeyPatch.context() as m:
        m.setattr(app.state.collector, "collect_from_files", fake_collect_files)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/collector/import-output")
            assert resp.status_code == 200


@pytest.mark.anyio
async def test_import_output_with_yaml_files(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "out.yaml").write_text("proxies:\n  - name: test\n")

    def fake_collect_files(paths):
        return _fake_report()

    with pytest.MonkeyPatch.context() as m:
        m.setattr(app.state.collector, "collect_from_files", fake_collect_files)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/collector/import-output")
            assert resp.status_code == 200


# ===== delete-unavailable =====


@pytest.mark.anyio
async def test_delete_unavailable_proxies(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    # Add an unavailable proxy
    proxy = ProxyNode(
        protocol="trojan",
        host="bad.example.com",
        port=443,
        raw_link="trojan://bad",
        extra={"password": "p"},
    )
    storage.upsert_proxy(proxy)
    storage.update_test_result(proxy.normalized_key(), available=False, latency_ms=0)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/proxies/delete-unavailable")
        assert resp.status_code == 200
        data = resp.json()
        assert "deleted" in data
        assert isinstance(data["deleted"], int)


@pytest.mark.anyio
async def test_delete_unavailable_proxies_none_deleted(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/proxies/delete-unavailable")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 0


# ===== delete-selected =====


@pytest.mark.anyio
async def test_delete_selected_empty_keys_returns_400(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/delete-selected",
            json={"normalized_keys": []},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_delete_selected_whitespace_keys_returns_400(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/delete-selected",
            json={"normalized_keys": ["  ", ""]},
        )
        assert resp.status_code == 400


@pytest.mark.anyio
async def test_delete_selected_no_normalized_keys_returns_400(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/delete-selected",
            json={},
        )
        assert resp.status_code == 400


@pytest.mark.anyio
async def test_delete_selected_success(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    proxy = ProxyNode(
        protocol="vmess",
        host="del.example.com",
        port=443,
        raw_link="vmess://del",
        extra={},
    )
    storage.upsert_proxy(proxy)
    key = proxy.normalized_key()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/delete-selected",
            json={"normalized_keys": [key]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "deleted" in data
        assert "requested" in data
        assert data["requested"] == 1


@pytest.mark.anyio
async def test_delete_selected_deduplicates_keys(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    proxy = ProxyNode(
        protocol="ss",
        host="dup.example.com",
        port=1080,
        raw_link="ss://dup",
        extra={},
    )
    storage.upsert_proxy(proxy)
    key = proxy.normalized_key()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/delete-selected",
            json={"normalized_keys": [key, key]},
        )
        assert resp.status_code == 200
        assert resp.json()["requested"] == 1


# ===== batch-test =====


@pytest.mark.anyio
async def test_batch_test_nonexistent_key(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/batch-test",
            json={"normalized_keys": ["nonexistent-key"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["completed"] == 1
        assert data["failed"] == 1
        assert data["success"] == 0
        assert data["results"][0]["error"] == "proxy not found"


@pytest.mark.anyio
async def test_batch_test_with_real_proxy(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    proxy = ProxyNode(
        protocol="trojan",
        host="test.example.com",
        port=443,
        raw_link="trojan://test",
        extra={"password": "p"},
    )
    storage.upsert_proxy(proxy)
    key = proxy.normalized_key()

    class FakeReport:
        available = True
        latency_ms = 150

    async def fake_run_one(normalized_key, fallback_front_proxy_keys, fallback_front_max_attempts):
        return FakeReport()

    monkeypatch.setattr(app.state.tester, "run_one", fake_run_one)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/batch-test",
            json={"normalized_keys": [key]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["completed"] == 1
        assert data["success"] == 1
        assert data["failed"] == 0
        assert data["results"][0]["success"] is True
        assert data["results"][0]["latency_ms"] == 150


@pytest.mark.anyio
async def test_batch_test_unavailable_proxy(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    proxy = ProxyNode(
        protocol="ss",
        host="fail.example.com",
        port=1080,
        raw_link="ss://fail",
        extra={},
    )
    storage.upsert_proxy(proxy)
    key = proxy.normalized_key()

    class FailReport:
        available = False
        latency_ms = None

    async def fake_run_one(normalized_key, fallback_front_proxy_keys, fallback_front_max_attempts):
        return FailReport()

    monkeypatch.setattr(app.state.tester, "run_one", fake_run_one)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/batch-test",
            json={"normalized_keys": [key]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] == 0
        assert data["failed"] == 1
        assert data["results"][0]["success"] is False


@pytest.mark.anyio
async def test_batch_test_exception_during_test(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    proxy = ProxyNode(
        protocol="trojan",
        host="err.example.com",
        port=443,
        raw_link="trojan://err",
        extra={"password": "p"},
    )
    storage.upsert_proxy(proxy)
    key = proxy.normalized_key()

    async def fake_run_one(normalized_key, fallback_front_proxy_keys, fallback_front_max_attempts):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(app.state.tester, "run_one", fake_run_one)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/batch-test",
            json={"normalized_keys": [key]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["failed"] == 1
        assert "connection refused" in data["results"][0]["error"]


@pytest.mark.anyio
async def test_batch_test_mixed_keys(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    storage = app.state.storage

    proxy = ProxyNode(
        protocol="trojan",
        host="mix.example.com",
        port=443,
        raw_link="trojan://mix",
        extra={"password": "p"},
    )
    storage.upsert_proxy(proxy)
    key = proxy.normalized_key()

    class OkReport:
        available = True
        latency_ms = 80

    async def fake_run_one(normalized_key, fallback_front_proxy_keys, fallback_front_max_attempts):
        return OkReport()

    monkeypatch.setattr(app.state.tester, "run_one", fake_run_one)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/proxies/batch-test",
            json={"normalized_keys": [key, "nonexistent"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["completed"] == 2
        assert data["success"] == 1
        assert data["failed"] == 1


# ===== geoip stubs =====


@pytest.mark.anyio
async def test_geoip_enrich_stub(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/geoip/enrich", json={"keys": []})
        assert resp.status_code == 200
        assert resp.json()["status"] == "not implemented"


@pytest.mark.anyio
async def test_geoip_ip_purity_stub(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/geoip/ip-purity", json={"keys": []})
        assert resp.status_code == 200
        assert resp.json()["status"] == "not implemented"
