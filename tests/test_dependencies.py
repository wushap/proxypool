"""
Tests for FastAPI dependencies.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from proxypool.api.dependencies import (
    get_settings,
    get_storage,
    get_collector,
    get_tester,
    get_pool_service,
    get_task_manager,
)


def _make_request(**state_attrs):
    """Create a mock FastAPI Request with app.state attributes."""
    app = SimpleNamespace(state=SimpleNamespace(**state_attrs))
    return SimpleNamespace(app=app)


class TestDependencies:
    """Test FastAPI dependencies."""

    def test_get_settings(self):
        """Test get_settings returns AppSettings."""
        settings = get_settings()
        assert settings is not None
        assert hasattr(settings, "db_path")
        assert hasattr(settings, "api_key")

    def test_get_storage(self):
        """Test get_storage returns storage from app.state."""
        mock_storage = MagicMock()
        mock_storage.list_proxies = MagicMock()
        mock_storage.upsert_proxy = MagicMock()
        request = _make_request(storage=mock_storage)
        storage = get_storage(request)
        assert storage is mock_storage
        assert hasattr(storage, "list_proxies")
        assert hasattr(storage, "upsert_proxy")

    def test_get_collector(self):
        """Test get_collector returns collector from app.state."""
        mock_collector = MagicMock()
        mock_collector.collect_from_sources = MagicMock()
        request = _make_request(collector=mock_collector)
        collector = get_collector(request)
        assert collector is mock_collector
        assert hasattr(collector, "collect_from_sources")

    def test_get_tester(self):
        """Test get_tester returns tester from app.state."""
        mock_tester = MagicMock()
        mock_tester.run_batch = MagicMock()
        request = _make_request(tester=mock_tester)
        tester = get_tester(request)
        assert tester is mock_tester
        assert hasattr(tester, "run_batch")

    def test_get_pool_service(self):
        """Test get_pool_service returns pool_service from app.state."""
        mock_pool = MagicMock()
        mock_pool.get_pool = MagicMock()
        mock_pool.list_pools = MagicMock()
        request = _make_request(pool_service=mock_pool)
        pool_service = get_pool_service(request)
        assert pool_service is mock_pool
        assert hasattr(pool_service, "get_pool")
        assert hasattr(pool_service, "list_pools")

    def test_get_task_manager(self):
        """Test get_task_manager returns task_manager from app.state."""
        mock_tm = MagicMock()
        mock_tm.start_task = MagicMock()
        mock_tm.get_task = MagicMock()
        request = _make_request(task_manager=mock_tm)
        task_manager = get_task_manager(request)
        assert task_manager is mock_tm
        assert hasattr(task_manager, "start_task")
        assert hasattr(task_manager, "get_task")
