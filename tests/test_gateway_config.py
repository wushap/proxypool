from pathlib import Path

from proxypool.gateway.config import HttpGatewayConfig
from proxypool.gateway.config_service import HttpGatewayConfigService
from proxypool.storage.sqlite import SQLiteProxyStorage


def test_http_gateway_config_defaults(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    service = HttpGatewayConfigService(storage)

    item = service.get_config()

    assert item.enabled is False
    assert item.listen_host == "127.0.0.1"
    assert item.listen_port == 8899
    assert item.endpoint_id == 0
    assert item.default_pool_id == 0
    assert item.session_missing_action == "RANDOM"
    assert item.http_session_header_names == ["X-ProxyPool-Session"]
    assert item.connect_session_header_names == ["X-ProxyPool-Session"]


def test_http_gateway_config_round_trip(tmp_path: Path) -> None:
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    service = HttpGatewayConfigService(storage)

    saved = service.update_config(
        enabled=True,
        listen_host="0.0.0.0",
        listen_port=18080,
        endpoint_id=11,
        default_pool_id=7,
        sticky_ttl_sec=7200,
        session_missing_action="REJECT",
        http_session_header_names=["X-ProxyPool-Session", "X-Session-Id"],
        http_session_query_names=["session", "sid"],
        connect_session_header_names=["X-ProxyPool-Session"],
    )

    assert saved.enabled is True
    assert saved.listen_host == "0.0.0.0"
    assert saved.listen_port == 18080
    assert saved.endpoint_id == 11
    assert saved.default_pool_id == 7
    assert saved.sticky_ttl_sec == 7200
    assert saved.session_missing_action == "REJECT"
    assert saved.http_session_query_names == ["session", "sid"]
    assert service.get_config().listen_port == 18080


def test_http_gateway_config_validation_rejects_bad_port() -> None:
    try:
        HttpGatewayConfig(listen_port=70000)
    except ValueError as exc:
        assert "listen_port" in str(exc)
    else:
        raise AssertionError("expected ValueError")
