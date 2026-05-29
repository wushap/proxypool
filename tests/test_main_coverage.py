"""
Tests for proxypool.main module.

Covers app creation at module level and the __main__ entry point
(host/port parsing from environment variables, uvicorn invocation).
"""

from __future__ import annotations

import importlib
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI


class TestAppCreation:
    """Test the module-level app object."""

    def test_app_is_fastapi_instance(self):
        """The module-level ``app`` should be a FastAPI instance."""
        from proxypool.main import app

        assert isinstance(app, FastAPI)

    def test_app_has_routes(self):
        """The created app should have registered routes."""
        from proxypool.main import app

        # The app is created via create_app() so it must have at least one route
        assert len(app.routes) > 0


class TestMainEntryPoint:
    """Test the ``if __name__ == '__main__'`` block."""

    def test_default_host_and_port(self, monkeypatch: pytest.MonkeyPatch):
        """With no env vars set, host=0.0.0.0 and port=8080."""
        monkeypatch.delenv("PROXYPOOL_WEBUI_HOST", raising=False)
        monkeypatch.delenv("PROXYPOOL_WEBUI_PORT", raising=False)

        with patch("proxypool.main.uvicorn.run") as mock_run:
            import runpy

            runpy.run_module("proxypool.main", run_name="__main__")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args.kwargs["host"] == "0.0.0.0"
        assert call_args.kwargs["port"] == 8080

    def test_custom_host_and_port(self, monkeypatch: pytest.MonkeyPatch):
        """Env vars override the defaults."""
        monkeypatch.setenv("PROXYPOOL_WEBUI_HOST", "127.0.0.1")
        monkeypatch.setenv("PROXYPOOL_WEBUI_PORT", "9090")

        with patch("proxypool.main.uvicorn.run") as mock_run:
            import runpy

            runpy.run_module("proxypool.main", run_name="__main__")

        call_args = mock_run.call_args
        assert call_args.kwargs["host"] == "127.0.0.1"
        assert call_args.kwargs["port"] == 9090

    def test_empty_host_env_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """An empty PROXYPOOL_WEBUI_HOST should fall back to 0.0.0.0."""
        monkeypatch.setenv("PROXYPOOL_WEBUI_HOST", "   ")
        monkeypatch.delenv("PROXYPOOL_WEBUI_PORT", raising=False)

        with patch("proxypool.main.uvicorn.run") as mock_run:
            import runpy

            runpy.run_module("proxypool.main", run_name="__main__")

        assert mock_run.call_args.kwargs["host"] == "0.0.0.0"

    def test_invalid_port_falls_back_to_8080(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """A non-numeric port should fall back to 8080."""
        monkeypatch.delenv("PROXYPOOL_WEBUI_HOST", raising=False)
        monkeypatch.setenv("PROXYPOOL_WEBUI_PORT", "not-a-number")

        with patch("proxypool.main.uvicorn.run") as mock_run:
            import runpy

            runpy.run_module("proxypool.main", run_name="__main__")

        assert mock_run.call_args.kwargs["port"] == 8080

    def test_port_clamped_below_minimum(self, monkeypatch: pytest.MonkeyPatch):
        """Port 0 is clamped to 1."""
        monkeypatch.delenv("PROXYPOOL_WEBUI_HOST", raising=False)
        monkeypatch.setenv("PROXYPOOL_WEBUI_PORT", "0")

        with patch("proxypool.main.uvicorn.run") as mock_run:
            import runpy

            runpy.run_module("proxypool.main", run_name="__main__")

        assert mock_run.call_args.kwargs["port"] == 1

    def test_port_clamped_above_maximum(self, monkeypatch: pytest.MonkeyPatch):
        """Port > 65535 is clamped to 65535."""
        monkeypatch.delenv("PROXYPOOL_WEBUI_HOST", raising=False)
        monkeypatch.setenv("PROXYPOOL_WEBUI_PORT", "99999")

        with patch("proxypool.main.uvicorn.run") as mock_run:
            import runpy

            runpy.run_module("proxypool.main", run_name="__main__")

        assert mock_run.call_args.kwargs["port"] == 65535

    def test_uvicorn_called_with_reload_false(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """uvicorn.run should be called with reload=False."""
        monkeypatch.delenv("PROXYPOOL_WEBUI_HOST", raising=False)
        monkeypatch.delenv("PROXYPOOL_WEBUI_PORT", raising=False)

        with patch("proxypool.main.uvicorn.run") as mock_run:
            import runpy

            runpy.run_module("proxypool.main", run_name="__main__")

        assert mock_run.call_args.kwargs["reload"] is False
