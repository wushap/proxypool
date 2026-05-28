from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from proxypool.backend.egress_backend import ChainInstanceSpec
from proxypool.backend.mihomo_config import build_mihomo_chain_config
from proxypool.backend.mihomo_manager import MihomoEgressBackend


def test_build_mihomo_chain_config_uses_dialer_proxy(tmp_path: Path):
    spec = ChainInstanceSpec(
        instance_id="chain-a",
        pool_id=1,
        listen="127.0.0.1",
        port=19090,
        inbound_type="http",
        front_proxy={
            "protocol": "socks",
            "host": "front.example.com",
            "port": 1080,
            "raw_link": "socks://front.example.com:1080",
            "name": "front",
        },
        exit_proxy={
            "protocol": "ss",
            "host": "exit.example.com",
            "port": 443,
            "raw_link": "ss://exit.example.com:443",
            "name": "exit",
            "extra_json": {"cipher": "aes-128-gcm", "password": "secret"},
        },
    )

    config = build_mihomo_chain_config(spec)

    assert config["listeners"][0]["type"] == "http"
    assert config["listeners"][0]["port"] == 19090
    assert any(
        item.get("name") == "exit" and item.get("dialer-proxy") == "front"
        for item in config["proxies"]
    )


def test_build_mihomo_chain_config_supports_vless_ws_and_trojan_ws(tmp_path: Path):
    vless_spec = ChainInstanceSpec(
        instance_id="chain-vless",
        pool_id=1,
        listen="127.0.0.1",
        port=19091,
        inbound_type="http",
        front_proxy={
            "protocol": "socks",
            "host": "front.example.com",
            "port": 1080,
            "raw_link": "socks://front.example.com:1080",
            "name": "front",
        },
        exit_proxy={
            "protocol": "vless",
            "host": "exit.example.com",
            "port": 443,
            "raw_link": "vless://uuid@exit.example.com:443",
            "name": "exit-vless",
            "extra_json": {
                "uuid": "12345678-1234-1234-1234-123456789012",
                "security": "tls",
                "sni": "ws.example.com",
                "fp": "chrome",
                "allowInsecure": "1",
                "type": "ws",
                "host": "ws.example.com",
                "path": "/ws",
                "encryption": "none",
            },
        },
    )
    trojan_spec = ChainInstanceSpec(
        instance_id="chain-trojan",
        pool_id=1,
        listen="127.0.0.1",
        port=19092,
        inbound_type="http",
        front_proxy={
            "protocol": "http",
            "host": "front.example.com",
            "port": 8080,
            "raw_link": "http://front.example.com:8080",
            "name": "front-http",
        },
        exit_proxy={
            "protocol": "trojan",
            "host": "trojan.example.com",
            "port": 443,
            "raw_link": "trojan://password@trojan.example.com:443",
            "name": "exit-trojan",
            "extra_json": {
                "password": "secret",
                "security": "tls",
                "sni": "trojan.example.com",
                "allowInsecure": "1",
                "type": "ws",
                "host": "trojan.example.com",
                "path": "/tr",
            },
        },
    )

    vless_config = build_mihomo_chain_config(vless_spec)
    trojan_config = build_mihomo_chain_config(trojan_spec)

    vless_proxy = next(item for item in vless_config["proxies"] if item.get("name") == "exit-vless")
    trojan_proxy = next(
        item for item in trojan_config["proxies"] if item.get("name") == "exit-trojan"
    )
    assert vless_proxy["type"] == "vless"
    assert vless_proxy["uuid"] == "12345678-1234-1234-1234-123456789012"
    assert vless_proxy["network"] == "ws"
    assert vless_proxy["ws-opts"]["path"] == "/ws"
    assert vless_proxy["ws-opts"]["headers"]["Host"] == "ws.example.com"
    assert trojan_proxy["type"] == "trojan"
    assert trojan_proxy["password"] == "secret"
    assert trojan_proxy["network"] == "ws"
    assert trojan_proxy["ws-opts"]["path"] == "/tr"


def test_build_mihomo_chain_config_includes_vmess_zero_alter_id(tmp_path: Path):
    spec = ChainInstanceSpec(
        instance_id="chain-vmess",
        pool_id=1,
        listen="127.0.0.1",
        port=19093,
        inbound_type="http",
        hop_proxies=[
            {
                "protocol": "vmess",
                "host": "vmess.example.com",
                "port": 443,
                "raw_link": "vmess://example",
                "name": "exit-vmess",
                "extra_json": {
                    "uuid": "12345678-1234-1234-1234-123456789012",
                    "cipher": "auto",
                },
            }
        ],
    )

    config = build_mihomo_chain_config(spec)

    proxy = config["proxies"][0]
    assert proxy["type"] == "vmess"
    assert proxy["alterId"] == 0


def test_mihomo_backend_start_writes_config_and_returns_paths(tmp_path: Path):
    spec = ChainInstanceSpec(
        instance_id="chain-a",
        pool_id=1,
        listen="127.0.0.1",
        port=19090,
        inbound_type="http",
        front_proxy={
            "protocol": "socks",
            "host": "front.example.com",
            "port": 1080,
            "raw_link": "socks://front.example.com:1080",
            "name": "front",
        },
        exit_proxy={
            "protocol": "ss",
            "host": "exit.example.com",
            "port": 443,
            "raw_link": "ss://exit.example.com:443",
            "name": "exit",
            "extra_json": {"cipher": "aes-128-gcm", "password": "secret"},
        },
    )
    backend = MihomoEgressBackend(binary="mihomo", runtime_dir=tmp_path)

    with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
        with patch("proxypool.backend.mihomo_manager.subprocess.Popen") as popen:
            popen.return_value.pid = 4321
            started = backend.start(spec)

    assert started.pid == 4321
    assert started.config_file.exists()
    assert started.log_file.name == "chain-a.log"
    assert "dialer-proxy" in started.config_file.read_text(encoding="utf-8")


def test_mihomo_backend_start_sets_writable_home_and_config_env(tmp_path: Path):
    spec = ChainInstanceSpec(
        instance_id="chain-env",
        pool_id=1,
        listen="127.0.0.1",
        port=19091,
        inbound_type="http",
        front_proxy={
            "protocol": "socks",
            "host": "front.example.com",
            "port": 1080,
            "raw_link": "socks://front.example.com:1080",
            "name": "front",
        },
        exit_proxy={
            "protocol": "ss",
            "host": "exit.example.com",
            "port": 443,
            "raw_link": "ss://exit.example.com:443",
            "name": "exit",
            "extra_json": {"cipher": "aes-128-gcm", "password": "secret"},
        },
    )
    backend = MihomoEgressBackend(binary="mihomo", runtime_dir=tmp_path)

    with patch("proxypool.backend.mihomo_manager.shutil.which", return_value="/usr/bin/mihomo"):
        with patch("proxypool.backend.mihomo_manager.subprocess.Popen") as popen:
            popen.return_value.pid = 4321
            backend.start(spec)

    _, kwargs = popen.call_args
    env = kwargs["env"]
    assert env["HOME"] == str(tmp_path)
    assert env["XDG_CONFIG_HOME"] == str(tmp_path)
