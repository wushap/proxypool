from __future__ import annotations

import json
from pathlib import Path

from proxypool.gateway.config_service import HttpGatewayConfigService
from proxypool.storage.sqlite import SQLiteProxyStorage


def _service(tmp_path: Path) -> HttpGatewayConfigService:
    return HttpGatewayConfigService(SQLiteProxyStorage(tmp_path / "test.db"))


def _inject_raw(storage: SQLiteProxyStorage, data: dict) -> None:
    """Write raw JSON directly into storage, bypassing the service."""
    storage.set_app_setting(
        HttpGatewayConfigService.STORAGE_KEY,
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    )


class TestGetConfigBranches:
    """Cover the three fallback branches in get_config when stored JSON
    is missing optional keys (endpoint_id, health_check_enabled,
    health_check_interval_sec)."""

    def test_missing_endpoint_id_gets_default(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        # JSON without endpoint_id
        _inject_raw(svc.storage, {"listen_port": 9000})
        cfg = svc.get_config()
        assert cfg.endpoint_id == 0
        assert cfg.listen_port == 9000

    def test_missing_health_check_enabled_gets_default(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        _inject_raw(svc.storage, {"listen_port": 9000, "endpoint_id": 3})
        cfg = svc.get_config()
        assert cfg.health_check_enabled is True
        assert cfg.endpoint_id == 3

    def test_missing_health_check_interval_gets_default(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        _inject_raw(
            svc.storage,
            {"listen_port": 9000, "endpoint_id": 3, "health_check_enabled": False},
        )
        cfg = svc.get_config()
        assert cfg.health_check_interval_sec == 30
        assert cfg.health_check_enabled is False

    def test_all_three_keys_missing(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        _inject_raw(svc.storage, {"listen_port": 7777})
        cfg = svc.get_config()
        assert cfg.endpoint_id == 0
        assert cfg.health_check_enabled is True
        assert cfg.health_check_interval_sec == 30

    def test_all_keys_present_no_overwrite(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        _inject_raw(
            svc.storage,
            {
                "endpoint_id": 5,
                "health_check_enabled": False,
                "health_check_interval_sec": 120,
                "listen_port": 5555,
            },
        )
        cfg = svc.get_config()
        assert cfg.endpoint_id == 5
        assert cfg.health_check_enabled is False
        assert cfg.health_check_interval_sec == 120


class TestUpdateConfigEdgeCases:
    def test_update_no_kwargs_returns_current(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        original = svc.get_config()
        saved = svc.update_config()
        assert saved.enabled == original.enabled
        assert saved.listen_port == original.listen_port
        # Read back to confirm persistence
        reloaded = svc.get_config()
        assert reloaded.listen_port == original.listen_port

    def test_update_partial_kwargs_merges(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        saved = svc.update_config(listen_port=3000)
        assert saved.listen_port == 3000
        assert saved.enabled is False  # unchanged default
        cfg = svc.get_config()
        assert cfg.listen_port == 3000
        assert cfg.enabled is False

    def test_consecutive_updates(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        svc.update_config(listen_port=1000)
        svc.update_config(listen_port=2000)
        cfg = svc.get_config()
        assert cfg.listen_port == 2000

    def test_update_validates_bad_port(self, tmp_path: Path) -> None:
        import pytest

        svc = _service(tmp_path)
        with pytest.raises(ValueError, match="listen_port"):
            svc.update_config(listen_port=99999)

    def test_update_validates_bad_session_action(self, tmp_path: Path) -> None:
        import pytest

        svc = _service(tmp_path)
        with pytest.raises(ValueError, match="session_missing_action"):
            svc.update_config(session_missing_action="DROP")

    def test_service_initialization_stores_key(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        assert svc.STORAGE_KEY == "http_gateway_config_v1"

    def test_empty_storage_returns_fresh_config(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        cfg = svc.get_config()
        # Verify all defaults
        assert cfg.enabled is False
        assert cfg.listen_host == "127.0.0.1"
        assert cfg.listen_port == 8899
        assert cfg.endpoint_id == 0
        assert cfg.default_pool_id == 0
        assert cfg.sticky_ttl_sec == 3600
        assert cfg.session_missing_action == "RANDOM"
        assert cfg.health_check_enabled is True
        assert cfg.health_check_interval_sec == 30
