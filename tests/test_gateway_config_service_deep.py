"""Deep / edge-case tests for HttpGatewayConfigService.

Coverage is already 100 % -- these tests exercise unusual inputs,
boundary values, and round-trip integrity beyond what the existing
coverage tests check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from proxypool.gateway.config_service import HttpGatewayConfigService
from proxypool.storage.sqlite import SQLiteProxyStorage


def _svc(tmp_path: Path) -> HttpGatewayConfigService:
    return HttpGatewayConfigService(SQLiteProxyStorage(tmp_path / "test.db"))


def _inject_raw(storage: SQLiteProxyStorage, data: dict) -> None:
    storage.set_app_setting(
        HttpGatewayConfigService.STORAGE_KEY,
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    )


# ── get_config edge cases ─────────────────────────────────────────────


class TestGetConfigDeep:
    def test_empty_json_object(self, tmp_path: Path) -> None:
        """An empty stored JSON object should yield all defaults."""
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {})
        cfg = svc.get_config()
        assert cfg.endpoint_id == 0
        assert cfg.health_check_enabled is True
        assert cfg.health_check_interval_sec == 30

    def test_completely_empty_string_returns_fresh(self, tmp_path: Path) -> None:
        """No stored value at all should return a fresh config."""
        svc = _svc(tmp_path)
        cfg = svc.get_config()
        assert cfg.listen_port == 8899
        assert cfg.enabled is False

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        """Malformed JSON stored directly should cause a JSON decode error."""
        svc = _svc(tmp_path)
        svc.storage.set_app_setting(
            HttpGatewayConfigService.STORAGE_KEY, "{bad json"
        )
        with pytest.raises(json.JSONDecodeError):
            svc.get_config()

    def test_boundary_health_check_interval_low(self, tmp_path: Path) -> None:
        """health_check_interval_sec at its minimum (5)."""
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"health_check_interval_sec": 5})
        cfg = svc.get_config()
        assert cfg.health_check_interval_sec == 5

    def test_boundary_health_check_interval_high(self, tmp_path: Path) -> None:
        """health_check_interval_sec at its maximum (3600)."""
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"health_check_interval_sec": 3600})
        cfg = svc.get_config()
        assert cfg.health_check_interval_sec == 3600

    def test_health_check_interval_below_minimum_clamps(self, tmp_path: Path) -> None:
        """Values below 5 should be clamped to 5."""
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"health_check_interval_sec": 1})
        cfg = svc.get_config()
        assert cfg.health_check_interval_sec == 5

    def test_health_check_interval_above_maximum_clamps(self, tmp_path: Path) -> None:
        """Values above 3600 should be clamped to 3600."""
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"health_check_interval_sec": 9999})
        cfg = svc.get_config()
        assert cfg.health_check_interval_sec == 3600

    def test_endpoint_id_negative_clamped_to_zero(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"endpoint_id": -5})
        cfg = svc.get_config()
        assert cfg.endpoint_id == 0

    def test_default_pool_id_negative_clamped_to_zero(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"default_pool_id": -10})
        cfg = svc.get_config()
        assert cfg.default_pool_id == 0

    def test_sticky_ttl_below_minimum_clamps_to_one(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"sticky_ttl_sec": 0})
        cfg = svc.get_config()
        assert cfg.sticky_ttl_sec == 1

    def test_session_missing_action_reject_valid(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"session_missing_action": "REJECT"})
        cfg = svc.get_config()
        assert cfg.session_missing_action == "REJECT"

    def test_session_missing_action_lowercased_normalized(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"session_missing_action": "random"})
        cfg = svc.get_config()
        assert cfg.session_missing_action == "RANDOM"

    def test_session_missing_action_invalid_raises(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"session_missing_action": "DROP"})
        with pytest.raises(ValueError, match="session_missing_action"):
            svc.get_config()

    def test_listen_host_empty_falls_back(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"listen_host": ""})
        cfg = svc.get_config()
        assert cfg.listen_host == "127.0.0.1"

    def test_listen_host_whitespace_falls_back(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"listen_host": "   "})
        cfg = svc.get_config()
        assert cfg.listen_host == "127.0.0.1"

    def test_custom_listen_host_preserved(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"listen_host": "0.0.0.0"})
        cfg = svc.get_config()
        assert cfg.listen_host == "0.0.0.0"

    def test_port_boundary_min(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"listen_port": 1})
        cfg = svc.get_config()
        assert cfg.listen_port == 1

    def test_port_boundary_max(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"listen_port": 65535})
        cfg = svc.get_config()
        assert cfg.listen_port == 65535

    def test_port_zero_raises(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"listen_port": 0})
        with pytest.raises(ValueError, match="listen_port"):
            svc.get_config()

    def test_session_header_names_with_blanks(self, tmp_path: Path) -> None:
        """Blank entries in header names list should be filtered out."""
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"http_session_header_names": ["X-Foo", "", "  ", "X-Bar"]})
        cfg = svc.get_config()
        assert cfg.http_session_header_names == ["X-Foo", "X-Bar"]


# ── update_config edge cases ──────────────────────────────────────────


class TestUpdateConfigDeep:
    def test_update_all_fields_at_once(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        updated = svc.update_config(
            enabled=True,
            listen_host="0.0.0.0",
            listen_port=9090,
            endpoint_id=7,
            default_pool_id=3,
            sticky_ttl_sec=7200,
            session_missing_action="REJECT",
            health_check_enabled=False,
            health_check_interval_sec=60,
        )
        assert updated.enabled is True
        assert updated.listen_host == "0.0.0.0"
        assert updated.listen_port == 9090
        assert updated.endpoint_id == 7
        assert updated.default_pool_id == 3
        assert updated.sticky_ttl_sec == 7200
        assert updated.session_missing_action == "REJECT"
        assert updated.health_check_enabled is False
        assert updated.health_check_interval_sec == 60

        # Persisted correctly
        reloaded = svc.get_config()
        assert reloaded == updated

    def test_update_list_fields(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        updated = svc.update_config(
            http_session_header_names=["X-Custom-1", "X-Custom-2"],
            http_session_query_names=["token"],
            connect_session_header_names=["X-Connect"],
        )
        assert updated.http_session_header_names == ["X-Custom-1", "X-Custom-2"]
        assert updated.http_session_query_names == ["token"]
        assert updated.connect_session_header_names == ["X-Connect"]

    def test_round_trip_preserves_all_fields(self, tmp_path: Path) -> None:
        """Write config, read it back, update one field, re-read -- all others stay."""
        svc = _svc(tmp_path)
        svc.update_config(enabled=True, listen_port=4000, endpoint_id=10)
        svc.update_config(listen_port=5000)
        cfg = svc.get_config()
        assert cfg.enabled is True
        assert cfg.listen_port == 5000
        assert cfg.endpoint_id == 10

    def test_update_after_raw_injection(self, tmp_path: Path) -> None:
        """Raw inject + normal update should merge correctly."""
        svc = _svc(tmp_path)
        _inject_raw(svc.storage, {"listen_port": 1111, "endpoint_id": 22})
        updated = svc.update_config(listen_port=3333)
        assert updated.listen_port == 3333
        assert updated.endpoint_id == 22  # preserved from raw injection

    def test_update_health_check_interval_clamped(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        updated = svc.update_config(health_check_interval_sec=2)
        assert updated.health_check_interval_sec == 5  # clamped to min

    def test_update_negative_sticky_ttl_clamped(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        updated = svc.update_config(sticky_ttl_sec=-100)
        assert updated.sticky_ttl_sec == 1

    def test_update_negative_endpoint_id_clamped(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        updated = svc.update_config(endpoint_id=-3)
        assert updated.endpoint_id == 0

    def test_stored_json_is_compact(self, tmp_path: Path) -> None:
        """The serialized JSON stored in DB should use compact separators."""
        svc = _svc(tmp_path)
        svc.update_config(listen_port=1234)
        raw = svc.storage.get_app_setting(HttpGatewayConfigService.STORAGE_KEY, "")
        assert ", " not in raw  # no space after comma
        assert ": " not in raw  # no space after colon
        data = json.loads(raw)
        assert data["listen_port"] == 1234

    def test_unicode_in_list_fields(self, tmp_path: Path) -> None:
        svc = _svc(tmp_path)
        updated = svc.update_config(http_session_header_names=["X-中文"])
        assert updated.http_session_header_names == ["X-中文"]
        reloaded = svc.get_config()
        assert reloaded.http_session_header_names == ["X-中文"]
