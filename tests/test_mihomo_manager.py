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
    assert any(item.get("name") == "exit" and item.get("dialer-proxy") == "front" for item in config["proxies"])


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
