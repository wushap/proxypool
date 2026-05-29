from __future__ import annotations

import pytest

from proxypool.gateway.config import HttpGatewayConfig, _normalize_names


class TestNormalizeNames:
    def test_none_returns_default(self) -> None:
        assert _normalize_names(None, ["a", "b"]) == ["a", "b"]

    def test_empty_list_returns_default(self) -> None:
        assert _normalize_names([], ["default"]) == ["default"]

    def test_whitespace_only_returns_default(self) -> None:
        assert _normalize_names(["  ", "  "], ["fallback"]) == ["fallback"]

    def test_strips_whitespace(self) -> None:
        assert _normalize_names(["  x  ", " y "], ["d"]) == ["x", "y"]

    def test_falsy_items_skipped(self) -> None:
        assert _normalize_names([None, 0, "", "ok"], ["d"]) == ["ok"]

    def test_preserves_valid_items(self) -> None:
        assert _normalize_names(["a", "b", "c"], ["d"]) == ["a", "b", "c"]


class TestHttpGatewayConfigDefaults:
    def test_all_defaults(self) -> None:
        cfg = HttpGatewayConfig()
        assert cfg.enabled is False
        assert cfg.listen_host == "127.0.0.1"
        assert cfg.listen_port == 8899
        assert cfg.endpoint_id == 0
        assert cfg.default_pool_id == 0
        assert cfg.sticky_ttl_sec == 3600
        assert cfg.session_missing_action == "RANDOM"
        assert cfg.http_session_header_names == ["X-ProxyPool-Session"]
        assert cfg.http_session_query_names == ["session"]
        assert cfg.connect_session_header_names == ["X-ProxyPool-Session"]
        assert cfg.health_check_enabled is True
        assert cfg.health_check_interval_sec == 30

    def test_custom_values(self) -> None:
        cfg = HttpGatewayConfig(
            enabled=True,
            listen_host="0.0.0.0",
            listen_port=9000,
            endpoint_id=5,
            default_pool_id=3,
            sticky_ttl_sec=1200,
            session_missing_action="REJECT",
            http_session_header_names=["X-Custom"],
            http_session_query_names=["sid"],
            connect_session_header_names=["X-Conn"],
            health_check_enabled=False,
            health_check_interval_sec=60,
        )
        assert cfg.enabled is True
        assert cfg.listen_host == "0.0.0.0"
        assert cfg.listen_port == 9000
        assert cfg.endpoint_id == 5
        assert cfg.default_pool_id == 3
        assert cfg.sticky_ttl_sec == 1200
        assert cfg.session_missing_action == "REJECT"
        assert cfg.http_session_header_names == ["X-Custom"]
        assert cfg.http_session_query_names == ["sid"]
        assert cfg.connect_session_header_names == ["X-Conn"]
        assert cfg.health_check_enabled is False
        assert cfg.health_check_interval_sec == 60


class TestHttpGatewayConfigValidation:
    def test_invalid_port_too_high(self) -> None:
        with pytest.raises(ValueError, match="listen_port"):
            HttpGatewayConfig(listen_port=70000)

    def test_invalid_port_zero(self) -> None:
        with pytest.raises(ValueError, match="listen_port"):
            HttpGatewayConfig(listen_port=0)

    def test_invalid_port_negative(self) -> None:
        with pytest.raises(ValueError, match="listen_port"):
            HttpGatewayConfig(listen_port=-1)

    def test_invalid_session_missing_action(self) -> None:
        with pytest.raises(ValueError, match="session_missing_action"):
            HttpGatewayConfig(session_missing_action="DROP")

    def test_empty_listen_host_defaults(self) -> None:
        cfg = HttpGatewayConfig(listen_host="")
        assert cfg.listen_host == "127.0.0.1"

    def test_whitespace_listen_host_defaults(self) -> None:
        cfg = HttpGatewayConfig(listen_host="   ")
        assert cfg.listen_host == "127.0.0.1"

    def test_empty_session_missing_action_defaults_random(self) -> None:
        cfg = HttpGatewayConfig(session_missing_action="")
        assert cfg.session_missing_action == "RANDOM"

    def test_none_listen_host_defaults(self) -> None:
        cfg = HttpGatewayConfig(listen_host=None)  # type: ignore[arg-type]
        assert cfg.listen_host == "127.0.0.1"

    def test_negative_endpoint_id_clamped_to_zero(self) -> None:
        cfg = HttpGatewayConfig(endpoint_id=-5)
        assert cfg.endpoint_id == 0

    def test_negative_default_pool_id_clamped_to_zero(self) -> None:
        cfg = HttpGatewayConfig(default_pool_id=-10)
        assert cfg.default_pool_id == 0

    def test_sticky_ttl_clamped_to_minimum(self) -> None:
        cfg = HttpGatewayConfig(sticky_ttl_sec=0)
        assert cfg.sticky_ttl_sec == 1

    def test_health_check_interval_below_minimum(self) -> None:
        cfg = HttpGatewayConfig(health_check_interval_sec=1)
        assert cfg.health_check_interval_sec == 5

    def test_health_check_interval_above_maximum(self) -> None:
        cfg = HttpGatewayConfig(health_check_interval_sec=9999)
        assert cfg.health_check_interval_sec == 3600

    def test_health_check_interval_none_defaults(self) -> None:
        cfg = HttpGatewayConfig(health_check_interval_sec=None)  # type: ignore[arg-type]
        assert cfg.health_check_interval_sec == 30

    def test_normalize_empty_session_names(self) -> None:
        cfg = HttpGatewayConfig(
            http_session_header_names=[],
            http_session_query_names=[],
            connect_session_header_names=[],
        )
        assert cfg.http_session_header_names == ["X-ProxyPool-Session"]
        assert cfg.http_session_query_names == ["session"]
        assert cfg.connect_session_header_names == ["X-ProxyPool-Session"]

    def test_case_insensitive_session_action(self) -> None:
        cfg = HttpGatewayConfig(session_missing_action="reject")
        assert cfg.session_missing_action == "REJECT"

    def test_whitespace_session_action_stripped(self) -> None:
        cfg = HttpGatewayConfig(session_missing_action="  RANDOM  ")
        assert cfg.session_missing_action == "RANDOM"


class TestHttpGatewayConfigSerialization:
    def test_dataclass_fields_accessible(self) -> None:
        cfg = HttpGatewayConfig(enabled=True, listen_port=5000)
        assert cfg.enabled is True
        assert cfg.listen_port == 5000

    def test_slots_enforced(self) -> None:
        cfg = HttpGatewayConfig()
        with pytest.raises(AttributeError):
            cfg.nonexistent_field = True  # type: ignore[attr-defined]
