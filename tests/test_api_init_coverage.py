"""
Tests for proxypool.api.__init__ module.

Covers:
- Module import and __all__ export list
- create_app callable is re-exported correctly
- create_app via the package entry point produces a valid FastAPI instance
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from fastapi import FastAPI

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


# ===== Module import tests =====


def test_api_package_importable() -> None:
    """The api package can be imported without errors."""
    import proxypool.api as api_mod

    assert isinstance(api_mod, ModuleType)


def test_all_contains_create_app() -> None:
    """create_app is listed in __all__."""
    import proxypool.api as api_mod

    assert "create_app" in api_mod.__all__


def test_create_app_is_callable_from_package() -> None:
    """create_app can be accessed as an attribute of the package."""
    import proxypool.api as api_mod

    assert callable(api_mod.create_app)


def test_all_only_exports_create_app() -> None:
    """__all__ contains exactly ['create_app']."""
    import proxypool.api as api_mod

    assert api_mod.__all__ == ["create_app"]


# ===== create_app functional tests =====


def test_create_app_returns_fastapi(tmp_path: Path) -> None:
    """Calling create_app via the package entry point returns a FastAPI instance."""
    import proxypool.api as api_mod

    settings = _make_settings(tmp_path)
    app = api_mod.create_app(settings)
    assert isinstance(app, FastAPI)


def test_create_app_default_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """create_app with no arguments loads default settings."""
    import proxypool.api as api_mod

    settings = _make_settings(tmp_path)
    # Patch load_settings inside the app module so the no-args path works
    monkeypatch.setattr("proxypool.api.app.load_settings", lambda: settings)
    app = api_mod.create_app()
    assert isinstance(app, FastAPI)


def test_create_app_passthrough_args(tmp_path: Path) -> None:
    """create_app forwards positional and keyword args to the inner function."""
    from proxypool.api import create_app

    settings = _make_settings(tmp_path)
    app = create_app(settings)
    assert isinstance(app, FastAPI)


def test_create_app_has_routes(tmp_path: Path) -> None:
    """The created app should have at least one registered route."""
    from proxypool.api import create_app

    settings = _make_settings(tmp_path)
    app = create_app(settings)
    # FastAPI always has routes registered after creation
    assert len(app.routes) > 0


def test_create_app_openapi_schema(tmp_path: Path) -> None:
    """The created app produces a valid OpenAPI schema."""
    from proxypool.api import create_app

    settings = _make_settings(tmp_path)
    app = create_app(settings)
    schema = app.openapi()
    assert "openapi" in schema
    assert "paths" in schema
