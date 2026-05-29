"""Tests to push mihomo_config.py coverage by hitting every branch."""

from __future__ import annotations

import base64

import pytest

from proxypool.backend.egress_backend import ChainInstanceSpec
from proxypool.backend.mihomo_config import (
    build_mihomo_chain_config,
    _apply_auth,
    _apply_common_tls,
    _apply_network_opts,
    _decode_auth_value,
    _safe_b64decode_text,
    _is_truthy,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _spec(**overrides) -> ChainInstanceSpec:
    defaults = dict(
        instance_id="inst-1",
        pool_id=1,
        listen="127.0.0.1",
        port=1080,
        inbound_type="http",
        hop_proxies=[],
    )
    defaults.update(overrides)
    return ChainInstanceSpec(**defaults)


def _proxy(protocol: str = "http", **extra_fields) -> dict:
    p: dict = {"name": "test", "host": "1.2.3.4", "port": 443, "protocol": protocol}
    if extra_fields:
        p["extra"] = extra_fields
    return p


# ---------------------------------------------------------------------------
# build_mihomo_chain_config — basic happy paths
# ---------------------------------------------------------------------------

class TestBuildChainConfig:
    def test_single_http_proxy(self) -> None:
        spec = _spec(hop_proxies=[_proxy("http")])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["listeners"][0]["type"] == "http"
        assert len(cfg["proxies"]) == 1
        assert cfg["proxies"][0]["type"] == "http"
        assert cfg["rules"] == ["MATCH,test"]

    def test_single_socks_proxy(self) -> None:
        spec = _spec(inbound_type="socks", hop_proxies=[_proxy("socks")])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["listeners"][0]["type"] == "socks"

    def test_mixed_inbound_type(self) -> None:
        spec = _spec(inbound_type="mixed", hop_proxies=[_proxy("http")])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["listeners"][0]["type"] == "mixed"

    def test_empty_inbound_type_defaults_to_http(self) -> None:
        spec = _spec(inbound_type="", hop_proxies=[_proxy("http")])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["listeners"][0]["type"] == "http"

    def test_whitespace_inbound_type_defaults_to_http(self) -> None:
        spec = _spec(inbound_type="  ", hop_proxies=[_proxy("http")])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["listeners"][0]["type"] == "http"

    def test_chain_with_multiple_hops(self) -> None:
        proxies = [
            {"host": "1.2.3.4", "port": 443, "protocol": "http", "name": "a"},
            {"host": "5.6.7.8", "port": 443, "protocol": "socks", "name": "b"},
        ]
        spec = _spec(hop_proxies=proxies)
        cfg = build_mihomo_chain_config(spec)
        assert len(cfg["proxies"]) == 2
        assert cfg["proxies"][1]["dialer-proxy"] == "a"
        assert cfg["rules"] == ["MATCH,b"]

    def test_auto_names_when_no_name(self) -> None:
        p = {"host": "1.2.3.4", "port": 443, "protocol": "http"}
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["name"] == "hop-1"

    def test_empty_name_falls_back_to_default(self) -> None:
        p = {"host": "1.2.3.4", "port": 443, "protocol": "http", "name": ""}
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["name"] == "hop-1"


# ---------------------------------------------------------------------------
# build_mihomo_chain_config — error paths (lines 12, 16)
# ---------------------------------------------------------------------------

class TestBuildChainConfigErrors:
    def test_unsupported_inbound_type_raises(self) -> None:
        spec = _spec(inbound_type="quic", hop_proxies=[_proxy("http")])
        with pytest.raises(RuntimeError, match="unsupported mihomo inbound_type"):
            build_mihomo_chain_config(spec)

    def test_no_hop_proxies_raises(self) -> None:
        spec = _spec(hop_proxies=[])
        with pytest.raises(RuntimeError, match="requires at least one hop proxy"):
            build_mihomo_chain_config(spec)


# ---------------------------------------------------------------------------
# _build_mihomo_proxy — invalid host/port (line 56)
# ---------------------------------------------------------------------------

class TestBuildProxyErrors:
    def test_empty_host_raises(self) -> None:
        p = {"host": "", "port": 443, "protocol": "http"}
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="invalid proxy host/port"):
            build_mihomo_chain_config(spec)

    def test_zero_port_raises(self) -> None:
        p = {"host": "1.2.3.4", "port": 0, "protocol": "http"}
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="invalid proxy host/port"):
            build_mihomo_chain_config(spec)

    def test_negative_port_raises(self) -> None:
        p = {"host": "1.2.3.4", "port": -1, "protocol": "http"}
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="invalid proxy host/port"):
            build_mihomo_chain_config(spec)

    def test_unsupported_protocol_raises(self) -> None:
        p = {"host": "1.2.3.4", "port": 443, "protocol": "wireguard"}
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="unsupported mihomo proxy protocol"):
            build_mihomo_chain_config(spec)

    def test_empty_protocol_raises(self) -> None:
        p = {"host": "1.2.3.4", "port": 443, "protocol": ""}
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="unsupported mihomo proxy protocol"):
            build_mihomo_chain_config(spec)


# ---------------------------------------------------------------------------
# _build_mihomo_proxy — auth on http/socks (line 144)
# ---------------------------------------------------------------------------

class TestApplyAuth:
    def test_http_with_username_and_password(self) -> None:
        p = _proxy("http", username="user", password="pass")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["username"] == "user"
        assert cfg["proxies"][0]["password"] == "pass"

    def test_socks_with_password_only(self) -> None:
        p = _proxy("socks", password="secret")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["password"] == "secret"
        assert "username" not in cfg["proxies"][0]

    def test_auth_missing_when_no_credentials(self) -> None:
        p = _proxy("http")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert "username" not in cfg["proxies"][0]
        assert "password" not in cfg["proxies"][0]


# ---------------------------------------------------------------------------
# _build_mihomo_proxy — vless (lines 99, 104, 111)
# ---------------------------------------------------------------------------

class TestVless:
    def test_vless_requires_uuid(self) -> None:
        p = _proxy("vless", uuid="")
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="vless proxy requires uuid"):
            build_mihomo_chain_config(spec)

    def test_vless_with_flow(self) -> None:
        p = _proxy("vless", uuid="abc-123", flow="xtls-rprx-vision")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["flow"] == "xtls-rprx-vision"

    def test_vless_without_flow(self) -> None:
        p = _proxy("vless", uuid="abc-123")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert "flow" not in cfg["proxies"][0]


# ---------------------------------------------------------------------------
# _build_mihomo_proxy — vmess (line 111)
# ---------------------------------------------------------------------------

class TestVmess:
    def test_vmess_requires_uuid(self) -> None:
        p = _proxy("vmess", uuid="")
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="vmess proxy requires uuid"):
            build_mihomo_chain_config(spec)

    def test_vmess_with_defaults(self) -> None:
        p = _proxy("vmess", uuid="abc-123")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        vmess = cfg["proxies"][0]
        assert vmess["type"] == "vmess"
        assert vmess["uuid"] == "abc-123"
        assert vmess["alterId"] == 0
        assert vmess["cipher"] == "auto"

    def test_vmess_with_alter_id_and_cipher(self) -> None:
        p = _proxy("vmess", uuid="abc-123", alterId=1, security="chacha20")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        vmess = cfg["proxies"][0]
        assert vmess["alterId"] == 1
        assert vmess["cipher"] == "chacha20"


# ---------------------------------------------------------------------------
# _build_mihomo_proxy — hysteria2 (lines 122-137)
# ---------------------------------------------------------------------------

class TestHysteria2:
    def test_hysteria2_requires_password(self) -> None:
        p = _proxy("hysteria2", password="")
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="hysteria2 proxy requires password"):
            build_mihomo_chain_config(spec)

    def test_hysteria2_basic(self) -> None:
        p = _proxy("hysteria2", password="secret")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        hy = cfg["proxies"][0]
        assert hy["type"] == "hysteria2"
        assert hy["password"] == "secret"

    def test_hysteria2_with_obfs(self) -> None:
        p = _proxy("hysteria2", password="secret", obfs="salamander",
                   **{"obfs-password": "obfspass"})
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        hy = cfg["proxies"][0]
        assert hy["obfs"] == "salamander"
        assert hy["obfs-password"] == "obfspass"

    def test_hysteria2_obfs_password_snake_case(self) -> None:
        p = _proxy("hysteria2", password="secret", obfs="salamander",
                   obfs_password="obfspass")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["obfs-password"] == "obfspass"


# ---------------------------------------------------------------------------
# _build_mihomo_proxy — common TLS (line 160-163)
# ---------------------------------------------------------------------------

class TestCommonTls:
    def test_tls_enabled_via_security(self) -> None:
        p = _proxy("http", security="tls")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["tls"] is True

    def test_tls_sni_and_fingerprint(self) -> None:
        p = _proxy("http", security="tls", sni="example.com", fp="chrome")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["sni"] == "example.com"
        assert item["servername"] == "example.com"
        assert item["client-fingerprint"] == "chrome"

    def test_tls_insecure(self) -> None:
        p = _proxy("http", allowInsecure="true")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["tls"] is True
        assert item["skip-cert-verify"] is True

    def test_tls_not_set_when_no_tls_fields(self) -> None:
        p = _proxy("http")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert "tls" not in cfg["proxies"][0]

    def test_tls_via_peer_field(self) -> None:
        p = _proxy("http", peer="sni.example.com")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["tls"] is True

    def test_tls_via_servername_field(self) -> None:
        p = _proxy("http", servername="sni.example.com")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["tls"] is True

    def test_tls_via_client_fingerprint(self) -> None:
        p = _proxy("http", client_fingerprint="firefox")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["tls"] is True

    def test_tls_insecure_via_allow_insecure(self) -> None:
        p = _proxy("http", allow_insecure="1")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["skip-cert-verify"] is True

    def test_tls_insecure_via_insecure(self) -> None:
        p = _proxy("http", insecure="yes")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["skip-cert-verify"] is True

    def test_tls_via_tls_field(self) -> None:
        p = _proxy("http", tls="tls")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["tls"] is True


# ---------------------------------------------------------------------------
# _apply_network_opts (lines 181-194)
# ---------------------------------------------------------------------------

class TestNetworkOpts:
    def test_ws_network(self) -> None:
        p = _proxy("vmess", uuid="u", type="ws", host="ws.example.com", path="/ws")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["network"] == "ws"
        assert item["ws-opts"]["path"] == "/ws"
        assert item["ws-opts"]["headers"]["Host"] == "ws.example.com"

    def test_ws_network_without_host(self) -> None:
        p = _proxy("vmess", uuid="u", type="ws", path="/ws")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert "headers" not in item["ws-opts"]

    def test_grpc_network(self) -> None:
        p = _proxy("vmess", uuid="u", type="grpc", serviceName="mygrpc")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["network"] == "grpc"
        assert item["grpc-opts"]["grpc-service-name"] == "mygrpc"

    def test_grpc_network_without_service_name(self) -> None:
        p = _proxy("vmess", uuid="u", type="grpc")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["network"] == "grpc"
        assert "grpc-opts" not in item

    def test_http_network(self) -> None:
        p = _proxy("vmess", uuid="u", type="http", host="h.example.com", path="/hp")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["network"] == "http"
        assert item["http-opts"]["path"] == ["/hp"]
        assert item["http-opts"]["host"] == ["h.example.com"]

    def test_http_network_without_host(self) -> None:
        p = _proxy("vmess", uuid="u", type="http")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert "host" not in item["http-opts"]

    def test_network_via_net_field(self) -> None:
        p = _proxy("vmess", uuid="u", net="ws", path="/n")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["network"] == "ws"

    def test_network_tcp_ignored(self) -> None:
        p = _proxy("vmess", uuid="u", type="tcp")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert "network" not in cfg["proxies"][0]

    def test_network_none_ignored(self) -> None:
        p = _proxy("vmess", uuid="u", type="none")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert "network" not in cfg["proxies"][0]

    def test_network_empty_ignored(self) -> None:
        p = _proxy("vmess", uuid="u", type="")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert "network" not in cfg["proxies"][0]


# ---------------------------------------------------------------------------
# _decode_auth_value / _safe_b64decode_text (lines 201-220)
# ---------------------------------------------------------------------------

class TestDecodeAuthValue:
    def test_empty_value_returns_empty(self) -> None:
        assert _decode_auth_value("") == ""
        assert _decode_auth_value(None) == ""

    def test_plain_text_returned_as_is(self) -> None:
        assert _decode_auth_value("simpleuser") == "simpleuser"

    def test_base64_encoded_user_pass(self) -> None:
        raw = base64.b64encode(b"myuser:mypass").decode()
        result = _decode_auth_value(raw)
        assert result == "myuser"

    def test_double_base64_encoded(self) -> None:
        inner = base64.b64encode(b"realuser:realpass").decode()
        outer = base64.b64encode(f"{inner}:".encode()).decode()
        result = _decode_auth_value(outer)
        assert result == "realuser"

    def test_base64_without_colon_returns_original(self) -> None:
        raw = base64.b64encode(b"nocolon").decode()
        result = _decode_auth_value(raw)
        assert result == raw

    def test_invalid_base64_returns_original(self) -> None:
        result = _decode_auth_value("not-valid-base64!!!")
        assert result == "not-valid-base64!!!"

    def test_url_encoded_username(self) -> None:
        raw = base64.b64encode(b"my%40user:pass").decode()
        result = _decode_auth_value(raw)
        assert result == "my@user"


class TestSafeB64Decode:
    def test_valid_base64(self) -> None:
        encoded = base64.b64encode(b"hello").decode()
        assert _safe_b64decode_text(encoded) == "hello"

    def test_invalid_base64_returns_empty(self) -> None:
        assert _safe_b64decode_text("not-b64!!!") == ""

    def test_empty_string_returns_empty(self) -> None:
        assert _safe_b64decode_text("") == ""

    def test_padding_added_automatically(self) -> None:
        encoded = base64.b64encode(b"test").decode().rstrip("=")
        result = _safe_b64decode_text(encoded)
        assert result == "test"


# ---------------------------------------------------------------------------
# _is_truthy
# ---------------------------------------------------------------------------

class TestIsTruthy:
    def test_truthy_values(self) -> None:
        for v in ("1", "true", "yes", "on", "True", "YES", "ON"):
            assert _is_truthy(v) is True

    def test_falsy_values(self) -> None:
        for v in ("0", "false", "no", "off", "", None, "anything"):
            assert _is_truthy(v) is False


# ---------------------------------------------------------------------------
# SS and Trojan error paths
# ---------------------------------------------------------------------------

class TestSSAndTrojanErrors:
    def test_ss_requires_cipher_and_password(self) -> None:
        p = _proxy("ss", cipher="", password="pass")
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="shadowsocks.*requires cipher and password"):
            build_mihomo_chain_config(spec)

    def test_ss_requires_password(self) -> None:
        p = _proxy("ss", cipher="aes-256-gcm", password="")
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="shadowsocks.*requires cipher and password"):
            build_mihomo_chain_config(spec)

    def test_ss_happy_path(self) -> None:
        p = _proxy("ss", cipher="aes-256-gcm", password="pass")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        ss = cfg["proxies"][0]
        assert ss["type"] == "ss"
        assert ss["cipher"] == "aes-256-gcm"

    def test_trojan_requires_password(self) -> None:
        p = _proxy("trojan", password="")
        spec = _spec(hop_proxies=[p])
        with pytest.raises(RuntimeError, match="trojan.*requires password"):
            build_mihomo_chain_config(spec)

    def test_trojan_happy_path(self) -> None:
        p = _proxy("trojan", password="pass")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["type"] == "trojan"
        assert cfg["proxies"][0]["password"] == "pass"


# ---------------------------------------------------------------------------
# TLS + network combined (ss/trojan/vmess/vless with network opts)
# ---------------------------------------------------------------------------

class TestTlsAndNetworkCombined:
    def test_ss_with_tls_and_network(self) -> None:
        p = _proxy("ss", cipher="aes-256-gcm", password="pass",
                   security="tls", sni="sni.example.com", type="ws", path="/ws")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["tls"] is True
        assert item["network"] == "ws"

    def test_trojan_with_tls_and_grpc(self) -> None:
        p = _proxy("trojan", password="pass",
                   security="tls", sni="sni.example.com", type="grpc", serviceName="svc")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["tls"] is True
        assert item["network"] == "grpc"

    def test_vless_with_tls_and_http_network(self) -> None:
        p = _proxy("vless", uuid="abc",
                   security="tls", sni="sni.example.com",
                   type="http", host="h.example.com", path="/p")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["tls"] is True
        assert item["network"] == "http"

    def test_vmess_with_tls_and_ws(self) -> None:
        p = _proxy("vmess", uuid="abc",
                   security="tls", fp="chrome",
                   type="ws", host="w.example.com", path="/ws")
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        item = cfg["proxies"][0]
        assert item["tls"] is True
        assert item["network"] == "ws"


# ---------------------------------------------------------------------------
# extra_json fallback
# ---------------------------------------------------------------------------

class TestExtraJsonFallback:
    def test_extra_json_used_when_extra_not_dict(self) -> None:
        p = {"host": "1.2.3.4", "port": 443, "protocol": "http",
             "extra_json": {"username": "u", "password": "p"}}
        spec = _spec(hop_proxies=[p])
        cfg = build_mihomo_chain_config(spec)
        assert cfg["proxies"][0]["username"] == "u"
        assert cfg["proxies"][0]["password"] == "p"
