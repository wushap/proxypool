from __future__ import annotations

import httpx
import pytest

from proxypool.api.app import create_app
from proxypool.collector.service import CollectReport, SourceCollectReport
from proxypool.settings import AppSettings


def _make_settings(tmp_path) -> AppSettings:
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
async def test_import_texts_with_valid_proxy_links(tmp_path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    fake_report = CollectReport(
        total_sources=1,
        total_parsed=2,
        total_inserted=2,
        total_updated=0,
        total_deduped=0,
        total_invalid=0,
        by_source=[
            SourceCollectReport(
                source="text:test.txt",
                parsed=2,
                inserted=2,
                updated=0,
                deduped=0,
                invalid=0,
            )
        ],
    )

    def fake_collect_from_text_items(items):
        return fake_report

    monkeypatch.setattr(app.state.collector, "collect_from_text_items", fake_collect_from_text_items)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/collector/import-texts",
            json={
                "items": [
                    {
                        "filename": "test.txt",
                        "content": "trojan://pass@host:443\nvmess://base64data",
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sources"] == 1
        assert data["total_parsed"] == 2
        assert data["total_inserted"] == 2
        assert len(data["by_source"]) == 1


@pytest.mark.anyio
async def test_import_texts_returns_error_for_empty_items(tmp_path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/collector/import-texts",
            json={"items": []},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "empty" in data["detail"].lower()


@pytest.mark.anyio
async def test_import_urls_returns_error_for_ssrf_url(tmp_path) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/collector/import-urls",
            json={"urls": ["http://127.0.0.1:6379/internal"]},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data


@pytest.mark.anyio
async def test_export_proxies_csv(tmp_path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    fake_items = [
        {
            "host": "proxy1.example.com",
            "port": 443,
            "protocol": "trojan",
            "latency_ms": 120,
            "score": 8.5,
            "available": True,
            "country": "US",
            "city": "New York",
            "source": "test",
            "last_checked_at": "2026-05-28T12:00:00",
            "openai_unlocked": True,
        },
        {
            "host": "proxy2.example.com",
            "port": 8080,
            "protocol": "vmess",
            "latency_ms": 250,
            "score": 6.0,
            "available": False,
            "country": "JP",
            "city": "Tokyo",
            "source": "test",
            "last_checked_at": "2026-05-28T11:00:00",
            "openai_unlocked": None,
        },
    ]

    monkeypatch.setattr(
        app.state.storage, "list_proxies_filtered", lambda **kwargs: fake_items
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/proxies/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        assert "Content-Disposition" in resp.headers

        body = resp.text
        assert "地址" in body
        assert "proxy1.example.com:443" in body
        assert "proxy2.example.com:8080" in body
        assert "可用" in body
        assert "不可用" in body
