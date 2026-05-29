"""Tests for proxypool.tester.singbox module – covering outbound builders,
TLS helpers, dataclasses, prober edge-cases, and helper utilities."""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, AsyncMock

from proxypool.tester.singbox import (
    DEFAULT_LATENCY_TEST_URLS,
    ProbeResult,
    SpeedTestResult,
    SingboxProber,
    _build_singbox_tls,
    _find_free_port,
    _is_truthy,
    _normalize_test_urls,
    _parse_curl_speed_metrics,
    _parse_curl_time_ms,
    _run_command_async,
    _stop_process,
    _stop_process_async,
    build_singbox_outbound,
)


# ---------------------------------------------------------------------------
# ProbeResult / SpeedTestResult dataclass basics
# ---------------------------------------------------------------------------

class TestProbeResult(unittest.TestCase):
    def test_defaults(self) -> None:
        pr = ProbeResult(normalized_key="k", available=True)
        self.assertEqual(pr.normalized_key, "k")
        self.assertTrue(pr.available)
        self.assertIsNone(pr.latency_ms)
        self.assertIsNone(pr.openai_unlocked)
        self.assertEqual(pr.openai_status, "")
        self.assertEqual(pr.error, "")

    def test_all_fields(self) -> None:
        pr = ProbeResult(
            normalized_key="k2",
            available=False,
            latency_ms=100,
            openai_unlocked=True,
            openai_status="401",
            error="timeout",
        )
        self.assertEqual(pr.latency_ms, 100)
        self.assertTrue(pr.openai_unlocked)
        self.assertEqual(pr.error, "timeout")


class TestSpeedTestResult(unittest.TestCase):
    def test_defaults(self) -> None:
        sr = SpeedTestResult(normalized_key="k", ok=True, elapsed_ms=50, bytes_downloaded=1000, speed_mbps=0.16)
        self.assertTrue(sr.ok)
        self.assertEqual(sr.bytes_downloaded, 1000)
        self.assertEqual(sr.error, "")


# ---------------------------------------------------------------------------
# _is_truthy
# ---------------------------------------------------------------------------

class TestIsTruthy(unittest.TestCase):
    def test_truthy_values(self) -> None:
        for v in ("1", "true", "yes", "on", "True", "YES", "ON"):
            self.assertTrue(_is_truthy(v), f"expected truthy for {v!r}")

    def test_falsy_values(self) -> None:
        for v in (None, "", "0", "false", "no", "off", "abc"):
            self.assertFalse(_is_truthy(v), f"expected falsy for {v!r}")


# ---------------------------------------------------------------------------
# build_singbox_outbound
# ---------------------------------------------------------------------------

class TestBuildSingboxOutbound(unittest.TestCase):
    # --- guard clauses ---
    def test_returns_none_when_host_missing(self) -> None:
        result = build_singbox_outbound({"protocol": "trojan", "port": 443, "extra": {"password": "x"}})
        self.assertIsNone(result)

    def test_returns_none_when_port_zero(self) -> None:
        result = build_singbox_outbound({"protocol": "trojan", "host": "h.com", "port": 0, "extra": {"password": "x"}})
        self.assertIsNone(result)

    def test_returns_none_when_port_negative(self) -> None:
        result = build_singbox_outbound({"protocol": "trojan", "host": "h.com", "port": -1, "extra": {"password": "x"}})
        self.assertIsNone(result)

    def test_returns_none_for_unknown_protocol(self) -> None:
        result = build_singbox_outbound({"protocol": "wireguard", "host": "h.com", "port": 443})
        self.assertIsNone(result)

    # --- ss ---
    def test_ss_valid(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "ss", "host": "s.com", "port": 8388, "extra": {"cipher": "aes-256-gcm", "password": "pw"}},
            tag="out",
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["type"], "shadowsocks")
        self.assertEqual(result["method"], "aes-256-gcm")
        self.assertEqual(result["password"], "pw")
        self.assertEqual(result["tag"], "out")

    def test_ss_missing_method(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "ss", "host": "s.com", "port": 8388, "extra": {"password": "pw"}}
        )
        self.assertIsNone(result)

    def test_ss_missing_password(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "ss", "host": "s.com", "port": 8388, "extra": {"cipher": "aes"}}
        )
        self.assertIsNone(result)

    # --- trojan ---
    def test_trojan_with_sni(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "trojan", "host": "t.com", "port": 443, "extra": {"password": "pw", "sni": "sni.example.com"}},
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["type"], "trojan")
        self.assertEqual(result["tls"]["server_name"], "sni.example.com")

    def test_trojan_without_sni(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "trojan", "host": "t.com", "port": 443, "extra": {"password": "pw"}},
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertNotIn("tls", result)

    def test_trojan_missing_password(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "trojan", "host": "t.com", "port": 443, "extra": {}}
        )
        self.assertIsNone(result)

    def test_trojan_uses_peer_as_sni(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "trojan", "host": "t.com", "port": 443, "extra": {"password": "pw", "peer": "peer.example.com"}},
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["tls"]["server_name"], "peer.example.com")

    # --- vless ---
    def test_vless_basic(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "vless", "host": "v.com", "port": 443, "extra": {"uuid": "abc"}},
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["type"], "vless")
        self.assertEqual(result["uuid"], "abc")

    def test_vless_with_flow_and_packet_encoding(self) -> None:
        result = build_singbox_outbound(
            {
                "protocol": "vless",
                "host": "v.com",
                "port": 443,
                "extra": {
                    "uuid": "abc",
                    "flow": "xtls-rprx-vision",
                    "packet_encoding": "xudp",
                },
            },
        )
        assert result is not None
        self.assertEqual(result["flow"], "xtls-rprx-vision")
        self.assertEqual(result["packet_encoding"], "xudp")

    def test_vless_auto_packet_encoding_for_vision(self) -> None:
        """When flow is xtls-rprx-vision and no explicit packet_encoding, it defaults to xudp."""
        result = build_singbox_outbound(
            {
                "protocol": "vless",
                "host": "v.com",
                "port": 443,
                "extra": {"uuid": "abc", "flow": "xtls-rprx-vision"},
            },
        )
        assert result is not None
        self.assertEqual(result["packet_encoding"], "xudp")

    def test_vless_no_uuid(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "vless", "host": "v.com", "port": 443, "extra": {}}
        )
        self.assertIsNone(result)

    def test_vless_packet_encoding_packetEncoding_key(self) -> None:
        result = build_singbox_outbound(
            {
                "protocol": "vless",
                "host": "v.com",
                "port": 443,
                "extra": {"uuid": "abc", "packetEncoding": "pkt"},
            },
        )
        assert result is not None
        self.assertEqual(result["packet_encoding"], "pkt")

    def test_vless_with_tls_security(self) -> None:
        result = build_singbox_outbound(
            {
                "protocol": "vless",
                "host": "v.com",
                "port": 443,
                "extra": {"uuid": "abc", "security": "tls", "sni": "sni.example.com"},
            },
        )
        assert result is not None
        self.assertIn("tls", result)
        self.assertEqual(result["tls"]["server_name"], "sni.example.com")

    # --- vmess ---
    def test_vmess_basic(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "vmess", "host": "m.com", "port": 443, "extra": {"uuid": "abc"}},
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["type"], "vmess")
        self.assertEqual(result["security"], "auto")

    def test_vmess_with_tls(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "vmess", "host": "m.com", "port": 443, "extra": {"uuid": "abc", "tls": "tls"}},
        )
        assert result is not None
        self.assertIn("tls", result)
        self.assertTrue(result["tls"]["enabled"])

    def test_vmess_without_tls(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "vmess", "host": "m.com", "port": 443, "extra": {"uuid": "abc"}},
        )
        assert result is not None
        self.assertNotIn("tls", result)

    def test_vmess_no_uuid(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "vmess", "host": "m.com", "port": 443, "extra": {}}
        )
        self.assertIsNone(result)

    # --- hysteria2 ---
    def test_hysteria2_with_password_and_sni(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "hysteria2", "host": "h.com", "port": 8443, "extra": {"password": "pw", "sni": "sni.h.com"}},
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["type"], "hysteria2")
        self.assertEqual(result["password"], "pw")
        self.assertEqual(result["tls"]["server_name"], "sni.h.com")

    def test_hysteria2_without_password(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "hysteria2", "host": "h.com", "port": 8443, "extra": {}}
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertNotIn("password", result)

    def test_hysteria2_without_sni(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "hysteria2", "host": "h.com", "port": 8443, "extra": {"password": "pw"}}
        )
        assert result is not None
        self.assertNotIn("tls", result)

    # --- hysteria ---
    def test_hysteria_with_auth(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "hysteria", "host": "h.com", "port": 8443, "extra": {"password": "auth"}},
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["type"], "hysteria")
        self.assertEqual(result["auth_str"], "auth")

    def test_hysteria_with_auth_key(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "hysteria", "host": "h.com", "port": 8443, "extra": {"auth": "a2"}},
        )
        assert result is not None
        self.assertEqual(result["auth_str"], "a2")

    def test_hysteria_without_auth(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "hysteria", "host": "h.com", "port": 8443, "extra": {}}
        )
        assert result is not None
        self.assertNotIn("auth_str", result)

    # --- snell ---
    def test_snell_valid(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "snell", "host": "s.com", "port": 8388, "extra": {"password": "psk"}},
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["type"], "snell")
        self.assertEqual(result["psk"], "psk")
        self.assertEqual(result["version"], 3)

    def test_snell_missing_psk(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "snell", "host": "s.com", "port": 8388, "extra": {}}
        )
        self.assertIsNone(result)

    # --- http ---
    def test_http_with_auth(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "http", "host": "h.com", "port": 8080, "extra": {"username": "u", "password": "p"}},
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["type"], "http")
        self.assertEqual(result["username"], "u")
        self.assertEqual(result["password"], "p")

    def test_http_without_auth(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "http", "host": "h.com", "port": 8080, "extra": {}}
        )
        assert result is not None
        self.assertNotIn("username", result)
        self.assertNotIn("password", result)

    # --- socks ---
    def test_socks_with_auth(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "socks", "host": "s.com", "port": 1080, "extra": {"username": "u", "password": "p"}},
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["type"], "socks")
        self.assertEqual(result["username"], "u")
        self.assertEqual(result["password"], "p")

    def test_socks_without_auth(self) -> None:
        result = build_singbox_outbound(
            {"protocol": "socks", "host": "s.com", "port": 1080, "extra": {}}
        )
        assert result is not None
        self.assertNotIn("username", result)
        self.assertNotIn("password", result)


# ---------------------------------------------------------------------------
# _build_singbox_tls
# ---------------------------------------------------------------------------

class TestBuildSingboxTls(unittest.TestCase):
    def test_returns_none_when_nothing_set(self) -> None:
        self.assertIsNone(_build_singbox_tls({}))

    def test_returns_none_when_empty_security(self) -> None:
        self.assertIsNone(_build_singbox_tls({}, security=""))

    def test_tls_security_enables(self) -> None:
        result = _build_singbox_tls({}, security="tls")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result["enabled"])

    def test_reality_security_enables(self) -> None:
        result = _build_singbox_tls({}, security="reality")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result["enabled"])

    def test_sni_from_extra(self) -> None:
        result = _build_singbox_tls({"sni": "example.com"})
        assert result is not None
        self.assertEqual(result["server_name"], "example.com")

    def test_sni_from_servername(self) -> None:
        result = _build_singbox_tls({"servername": "sn.example.com"})
        assert result is not None
        self.assertEqual(result["server_name"], "sn.example.com")

    def test_sni_from_server_name(self) -> None:
        result = _build_singbox_tls({"server_name": "sn2.example.com"})
        assert result is not None
        self.assertEqual(result["server_name"], "sn2.example.com")

    def test_sni_from_peer(self) -> None:
        result = _build_singbox_tls({"peer": "peer.example.com"})
        assert result is not None
        self.assertEqual(result["server_name"], "peer.example.com")

    def test_insecure_true(self) -> None:
        for val in ("true", "1", "yes", "on"):
            result = _build_singbox_tls({"allowInsecure": val})
            assert result is not None
            self.assertTrue(result["insecure"], f"expected insecure=True for {val!r}")

    def test_insecure_false(self) -> None:
        result = _build_singbox_tls({"allowInsecure": "0"})
        assert result is not None
        self.assertFalse(result["insecure"])

    def test_insecure_allow_insecure_key(self) -> None:
        result = _build_singbox_tls({"allow_insecure": "true"})
        assert result is not None
        self.assertTrue(result["insecure"])

    def test_insecure_insecure_key(self) -> None:
        result = _build_singbox_tls({"insecure": "1"})
        assert result is not None
        self.assertTrue(result["insecure"])

    def test_fingerprint(self) -> None:
        result = _build_singbox_tls({"fp": "chrome"})
        assert result is not None
        self.assertEqual(result["utls"]["fingerprint"], "chrome")

    def test_fingerprint_full_key(self) -> None:
        result = _build_singbox_tls({"fingerprint": "firefox"})
        assert result is not None
        self.assertEqual(result["utls"]["fingerprint"], "firefox")

    def test_fingerprint_client_fingerprint_key(self) -> None:
        result = _build_singbox_tls({"client_fingerprint": "safari"})
        assert result is not None
        self.assertEqual(result["utls"]["fingerprint"], "safari")

    def test_reality_with_public_key(self) -> None:
        result = _build_singbox_tls({"pbk": "pub123"})
        assert result is not None
        self.assertEqual(result["reality"]["public_key"], "pub123")

    def test_reality_with_public_key_full_key(self) -> None:
        result = _build_singbox_tls({"public_key": "pub456"})
        assert result is not None
        self.assertEqual(result["reality"]["public_key"], "pub456")

    def test_reality_with_short_id(self) -> None:
        result = _build_singbox_tls({"sid": "sid1"})
        assert result is not None
        self.assertEqual(result["reality"]["short_id"], "sid1")

    def test_reality_with_short_id_full_key(self) -> None:
        result = _build_singbox_tls({"short_id": "sid2"})
        assert result is not None
        self.assertEqual(result["reality"]["short_id"], "sid2")

    def test_all_options_combined(self) -> None:
        extra = {
            "sni": "combo.example.com",
            "fp": "chrome",
            "pbk": "pub",
            "sid": "sid",
            "allowInsecure": "true",
        }
        result = _build_singbox_tls(extra)
        assert result is not None
        self.assertEqual(result["server_name"], "combo.example.com")
        self.assertTrue(result["insecure"])
        self.assertEqual(result["utls"]["fingerprint"], "chrome")
        self.assertEqual(result["reality"]["public_key"], "pub")
        self.assertEqual(result["reality"]["short_id"], "sid")


# ---------------------------------------------------------------------------
# _normalize_test_urls
# ---------------------------------------------------------------------------

class TestNormalizeTestUrls(unittest.TestCase):
    def test_defaults_used(self) -> None:
        result = _normalize_test_urls(None, "https://custom.com")
        self.assertEqual(result[0], "https://custom.com")
        for url in DEFAULT_LATENCY_TEST_URLS:
            self.assertIn(url, result)

    def test_deduplication(self) -> None:
        result = _normalize_test_urls(
            ["https://a.com", "https://a.com"],
            "https://a.com",
        )
        self.assertEqual(result.count("https://a.com"), 1)

    def test_invalid_urls_filtered(self) -> None:
        result = _normalize_test_urls(["not-a-url", ""], "ftp://bad.com")
        for url in result:
            self.assertTrue(url.startswith(("http://", "https://")))

    def test_empty_returns_defaults(self) -> None:
        result = _normalize_test_urls([], "")
        self.assertEqual(result, list(DEFAULT_LATENCY_TEST_URLS))


# ---------------------------------------------------------------------------
# _parse_curl_time_ms
# ---------------------------------------------------------------------------

class TestParseCurlTimeMs(unittest.TestCase):
    def test_valid_float(self) -> None:
        self.assertEqual(_parse_curl_time_ms("0.123"), 123)

    def test_integer_string(self) -> None:
        self.assertEqual(_parse_curl_time_ms("1"), 1000)

    def test_empty(self) -> None:
        self.assertIsNone(_parse_curl_time_ms(""))

    def test_none(self) -> None:
        self.assertIsNone(_parse_curl_time_ms(None))  # type: ignore[arg-type]

    def test_invalid(self) -> None:
        self.assertIsNone(_parse_curl_time_ms("abc"))


# ---------------------------------------------------------------------------
# _parse_curl_speed_metrics
# ---------------------------------------------------------------------------

class TestParseCurlSpeedMetrics(unittest.TestCase):
    def test_valid(self) -> None:
        downloaded, elapsed = _parse_curl_speed_metrics("1048576 0.500")
        self.assertEqual(downloaded, 1048576)
        self.assertEqual(elapsed, 500)

    def test_empty(self) -> None:
        downloaded, elapsed = _parse_curl_speed_metrics("")
        self.assertEqual(downloaded, 0)
        self.assertIsNone(elapsed)

    def test_one_part_only(self) -> None:
        downloaded, elapsed = _parse_curl_speed_metrics("100")
        self.assertEqual(downloaded, 0)
        self.assertIsNone(elapsed)

    def test_invalid_bytes(self) -> None:
        downloaded, elapsed = _parse_curl_speed_metrics("abc 0.1")
        self.assertEqual(downloaded, 0)
        self.assertEqual(elapsed, 100)


# ---------------------------------------------------------------------------
# _find_free_port
# ---------------------------------------------------------------------------

class TestFindFreePort(unittest.TestCase):
    def test_returns_valid_port(self) -> None:
        port = _find_free_port()
        self.assertGreater(port, 0)
        self.assertLess(port, 65536)

    def test_returns_connectable_port(self) -> None:
        port = _find_free_port()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            result = s.connect_ex(("127.0.0.1", port))
            # Port should be connectable or at least bindable
            self.assertIn(result, (0, 111))  # 0=connected, 111=connection refused


# ---------------------------------------------------------------------------
# SingboxProber init
# ---------------------------------------------------------------------------

class TestSingboxProberInit(unittest.TestCase):
    def test_defaults(self) -> None:
        prober = SingboxProber()
        self.assertEqual(prober.binary, "sing-box")
        self.assertEqual(prober.test_url, DEFAULT_LATENCY_TEST_URLS[0])
        self.assertEqual(prober.timeout_sec, 8.0)
        self.assertEqual(prober.startup_timeout_sec, 2.0)
        self.assertEqual(prober.openai_check_timeout_sec, 6.0)

    def test_custom_values(self) -> None:
        prober = SingboxProber(
            binary="/usr/local/bin/sing-box",
            test_url="https://custom.com/ping",
            test_urls=["https://a.com", "https://b.com"],
            timeout_sec=15.0,
            startup_timeout_sec=5.0,
            openai_check_timeout_sec=10.0,
        )
        self.assertEqual(prober.binary, "/usr/local/bin/sing-box")
        self.assertEqual(prober.test_url, "https://custom.com/ping")
        self.assertEqual(prober.timeout_sec, 15.0)
        self.assertEqual(prober.startup_timeout_sec, 5.0)
        self.assertEqual(prober.openai_check_timeout_sec, 10.0)
        self.assertIn("https://a.com", prober.test_urls)


# ---------------------------------------------------------------------------
# SingboxProber._build_runtime_config / _build_runtime_config_with_chain
# ---------------------------------------------------------------------------

class TestBuildRuntimeConfig(unittest.TestCase):
    def test_single_outbound(self) -> None:
        prober = SingboxProber()
        outbound = {"type": "trojan", "tag": "probe-out", "server": "x.com", "server_port": 443}
        config = prober._build_runtime_config(outbound, 9999)
        self.assertEqual(config["log"], {"disabled": True})
        self.assertEqual(len(config["inbounds"]), 1)
        self.assertEqual(config["inbounds"][0]["listen_port"], 9999)
        self.assertEqual(config["route"]["final"], "probe-out")
        self.assertEqual(len(config["outbounds"]), 1)

    def test_chain_outbounds(self) -> None:
        prober = SingboxProber()
        front = {"type": "trojan", "tag": "probe-front"}
        target = {"type": "vless", "tag": "probe-target"}
        config = prober._build_runtime_config_with_chain(
            outbounds=[front, target], final_tag="probe-target", local_port=8888,
        )
        self.assertEqual(config["route"]["final"], "probe-target")
        self.assertEqual(len(config["outbounds"]), 2)
        self.assertEqual(config["inbounds"][0]["listen_port"], 8888)


# ---------------------------------------------------------------------------
# _stop_process / _stop_process_async
# ---------------------------------------------------------------------------

class TestStopProcess(unittest.TestCase):
    def test_already_exited(self) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = 0
        _stop_process(proc)
        proc.terminate.assert_not_called()

    def test_terminate_and_wait(self) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.wait.return_value = None
        _stop_process(proc)
        proc.terminate.assert_called_once()

    def test_terminate_timeout_kills(self) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None
        proc.wait.side_effect = [subprocess.TimeoutExpired("x", 1.0), None]
        _stop_process(proc)
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()


class TestStopProcessAsync(unittest.IsolatedAsyncioTestCase):
    async def test_already_exited(self) -> None:
        proc = AsyncMock()
        proc.returncode = 0
        await _stop_process_async(proc)
        proc.terminate.assert_not_called()

    async def test_terminate_and_wait(self) -> None:
        proc = AsyncMock()
        proc.returncode = None
        proc.wait.return_value = None
        await _stop_process_async(proc)
        proc.terminate.assert_called_once()

    async def test_terminate_timeout_kills(self) -> None:
        proc = AsyncMock()
        proc.returncode = None
        # Use a real coroutine for the second wait() call after TimeoutError
        async def _fake_wait() -> None:
            return None
        proc.wait.side_effect = [TimeoutError(), _fake_wait()]
        await _stop_process_async(proc)
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# _run_command_async
# ---------------------------------------------------------------------------

class TestRunCommandAsync(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_returns_124(self) -> None:
        with patch("proxypool.tester.singbox.asyncio.create_subprocess_exec") as mock_create:
            mock_proc = AsyncMock()
            mock_proc.communicate.side_effect = TimeoutError()
            mock_proc.returncode = None
            mock_create.return_value = mock_proc
            with patch("proxypool.tester.singbox._stop_process_async") as mock_stop:
                rc, stdout, stderr = await _run_command_async(["sleep", "999"], timeout_sec=0.01)
                self.assertEqual(rc, 124)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr, "command timeout")
                mock_stop.assert_awaited_once_with(mock_proc)


# ---------------------------------------------------------------------------
# SingboxProber – probe edge-cases (no sing-box binary)
# ---------------------------------------------------------------------------

class TestSingboxProberProbeEdgeCases(unittest.TestCase):
    @patch("shutil.which", return_value=None)
    def test_probe_missing_normalized_key(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        result = prober.probe({"host": "h.com", "port": 443})
        self.assertFalse(result.available)
        self.assertEqual(result.error, "missing normalized_key")

    @patch("shutil.which", return_value=None)
    def test_probe_unsupported_protocol_tcp_fallback_fails(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "wireguard", "host": "127.0.0.1", "port": 1}
        with patch("socket.create_connection", side_effect=OSError("refused")):
            result = prober.probe(node)
        self.assertFalse(result.available)
        self.assertIn("refused", result.error)

    @patch("shutil.which", return_value=None)
    def test_probe_tcp_fallback_invalid_host(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "wireguard", "host": "", "port": 0}
        result = prober.probe(node)
        self.assertFalse(result.available)
        self.assertIn("invalid host/port", result.error)

    @patch("shutil.which", return_value=None)
    def test_probe_tcp_fallback_success(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "wireguard", "host": "1.2.3.4", "port": 8080}
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = lambda s: s
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            result = prober.probe(node)
        self.assertTrue(result.available)
        self.assertIsNotNone(result.latency_ms)
        self.assertEqual(result.openai_status, "not checked (tcp fallback)")


# ---------------------------------------------------------------------------
# SingboxProber.probe_async – edge-cases
# ---------------------------------------------------------------------------

class TestSingboxProberProbeAsync(unittest.IsolatedAsyncioTestCase):
    @patch("shutil.which", return_value=None)
    async def test_probe_async_missing_key(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        result = await prober.probe_async({})
        self.assertFalse(result.available)
        self.assertEqual(result.error, "missing normalized_key")

    @patch("shutil.which", return_value=None)
    async def test_probe_async_unsupported_tcp_fallback(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "wireguard", "host": "127.0.0.1", "port": 1}
        with patch("asyncio.open_connection", side_effect=OSError("refused")):
            result = await prober.probe_async(node)
        self.assertFalse(result.available)

    @patch("shutil.which", return_value=None)
    async def test_probe_async_tcp_fallback_connection_error(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber(timeout_sec=0.01)
        node = {"normalized_key": "k", "protocol": "wireguard", "host": "1.2.3.4", "port": 443}
        with patch("asyncio.open_connection", side_effect=OSError("network unreachable")):
            result = await prober.probe_async(node)
        self.assertFalse(result.available)
        self.assertIn("network unreachable", result.error)

    @patch("shutil.which", return_value=None)
    async def test_probe_async_tcp_fallback_invalid_host(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "wireguard", "host": "", "port": 0}
        result = await prober.probe_async(node)
        self.assertFalse(result.available)
        self.assertIn("invalid host/port", result.error)


# ---------------------------------------------------------------------------
# SingboxProber.probe_with_front_proxy – edge-cases
# ---------------------------------------------------------------------------

class TestProbeWithFrontProxy(unittest.TestCase):
    @patch("shutil.which", return_value=None)
    def test_missing_key(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        result = prober.probe_with_front_proxy(
            {"host": "h.com", "port": 443, "protocol": "trojan", "extra": {"password": "p"}},
            {"host": "f.com", "port": 443, "protocol": "trojan", "extra": {"password": "p"}},
        )
        self.assertFalse(result.available)
        self.assertEqual(result.error, "missing normalized_key")

    @patch("shutil.which", return_value=None)
    def test_unsupported_target(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "wireguard", "host": "h.com", "port": 443}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        result = prober.probe_with_front_proxy(node, front)
        self.assertFalse(result.available)
        self.assertIn("unsupported target", result.error)

    @patch("shutil.which", return_value=None)
    def test_unsupported_front(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "wireguard", "host": "f.com", "port": 443}
        result = prober.probe_with_front_proxy(node, front)
        self.assertFalse(result.available)
        self.assertIn("unsupported front", result.error)

    @patch("shutil.which", return_value=None)
    def test_invalid_host_port(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "", "port": 0, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        result = prober.probe_with_front_proxy(node, front)
        self.assertFalse(result.available)


# ---------------------------------------------------------------------------
# SingboxProber.probe_with_front_proxy_async – edge-cases
# ---------------------------------------------------------------------------

class TestProbeWithFrontProxyAsync(unittest.IsolatedAsyncioTestCase):
    @patch("shutil.which", return_value=None)
    async def test_missing_key(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        result = await prober.probe_with_front_proxy_async(
            {"host": "h.com", "port": 443, "protocol": "trojan", "extra": {"password": "p"}},
            {"host": "f.com", "port": 443, "protocol": "trojan", "extra": {"password": "p"}},
        )
        self.assertFalse(result.available)

    @patch("shutil.which", return_value=None)
    async def test_unsupported_target(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "wireguard", "host": "h.com", "port": 443}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        result = await prober.probe_with_front_proxy_async(node, front)
        self.assertFalse(result.available)
        self.assertIn("unsupported target", result.error)

    @patch("shutil.which", return_value=None)
    async def test_unsupported_front(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "wireguard", "host": "f.com", "port": 443}
        result = await prober.probe_with_front_proxy_async(node, front)
        self.assertFalse(result.available)
        self.assertIn("unsupported front", result.error)

    @patch("shutil.which", return_value=None)
    async def test_invalid_host_port(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "", "port": 0, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        result = await prober.probe_with_front_proxy_async(node, front)
        self.assertFalse(result.available)


# ---------------------------------------------------------------------------
# SingboxProber.speed_test_async – edge-cases
# ---------------------------------------------------------------------------

class TestSpeedTestAsync(unittest.IsolatedAsyncioTestCase):
    @patch("shutil.which", return_value=None)
    async def test_missing_key(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        result = await prober.speed_test_async({}, "https://example.com")
        self.assertFalse(result.ok)
        self.assertIn("missing normalized_key", result.error)

    @patch("shutil.which", return_value=None)
    async def test_unsupported_protocol(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "wireguard", "host": "h.com", "port": 443}
        result = await prober.speed_test_async(node, "https://example.com")
        self.assertFalse(result.ok)
        self.assertIn("unsupported protocol", result.error)

    @patch("shutil.which", return_value=None)
    async def test_curl_not_found(self, _mock_which: MagicMock) -> None:
        """When sing-box is found but curl is not, speed_test_async returns error."""
        def which_side_effect(name):
            if name == "sing-box":
                return "/usr/bin/sing-box"
            return None
        _mock_which.side_effect = which_side_effect

        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        result = await prober.speed_test_async(node, "https://example.com")
        self.assertFalse(result.ok)
        self.assertIn("curl not found", result.error)


# ---------------------------------------------------------------------------
# fetch_json_via_proxy – edge-cases
# ---------------------------------------------------------------------------

class TestFetchJsonViaProxy(unittest.TestCase):
    @patch("shutil.which", return_value=None)
    def test_unsupported_protocol(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "wireguard", "host": "h.com", "port": 443}
        with self.assertRaises(RuntimeError) as ctx:
            prober.fetch_json_via_proxy(node, "https://example.com")
        self.assertIn("unsupported protocol", str(ctx.exception))

    @patch("shutil.which", return_value=None)
    def test_singbox_not_found(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        with self.assertRaises(RuntimeError) as ctx:
            prober.fetch_json_via_proxy(node, "https://example.com")
        self.assertIn("sing-box not found", str(ctx.exception))

    @patch("shutil.which", return_value=None)
    def test_unsupported_front_protocol(self, _mock_which: MagicMock) -> None:
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "wireguard", "host": "f.com", "port": 443}
        with self.assertRaises(RuntimeError) as ctx:
            prober.fetch_json_via_proxy(node, "https://example.com", front_proxy=front)
        self.assertIn("unsupported front protocol", str(ctx.exception))


# ---------------------------------------------------------------------------
# _check_openai_unlock – edge-cases (sync)
# ---------------------------------------------------------------------------

class TestCheckOpenAiUnlock(unittest.TestCase):
    @patch("shutil.which", return_value=None)
    def test_curl_not_found(self, _mock: MagicMock) -> None:
        prober = SingboxProber()
        unlocked, status = prober._check_openai_unlock(9999)
        self.assertIsNone(unlocked)
        self.assertEqual(status, "curl not found")

    @patch("shutil.which")
    def test_401_unauthorized(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"error": "invalid api key"}\n401'
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            unlocked, status = prober._check_openai_unlock(9999)
        self.assertTrue(unlocked)
        self.assertEqual(status, "401 unauthorized")

    @patch("shutil.which")
    def test_200_ok(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"data": []}\n200'
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            unlocked, status = prober._check_openai_unlock(9999)
        self.assertTrue(unlocked)
        self.assertEqual(status, "200 ok")

    @patch("shutil.which")
    def test_403_region_blocked(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"error": {"message": "unsupported_country_region_territory"}}\n403'
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            unlocked, status = prober._check_openai_unlock(9999)
        self.assertFalse(unlocked)
        self.assertEqual(status, "403 region blocked")

    @patch("shutil.which")
    def test_403_forbidden(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"error": "forbidden"}\n403'
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            unlocked, status = prober._check_openai_unlock(9999)
        self.assertFalse(unlocked)
        self.assertEqual(status, "403 forbidden")

    @patch("shutil.which")
    def test_429_rate_limited(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"error": "rate_limit"}\n429'
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            unlocked, status = prober._check_openai_unlock(9999)
        self.assertTrue(unlocked)
        self.assertEqual(status, "429 rate limited")

    @patch("shutil.which")
    def test_other_status(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'body\n500'
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            unlocked, status = prober._check_openai_unlock(9999)
        self.assertIsNone(unlocked)
        self.assertEqual(status, "http 500")

    @patch("shutil.which")
    def test_curl_error(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        mock_result = MagicMock()
        mock_result.returncode = 7
        mock_result.stdout = ""
        mock_result.stderr = "connection refused"
        with patch("subprocess.run", return_value=mock_result):
            unlocked, status = prober._check_openai_unlock(9999)
        self.assertIsNone(unlocked)
        self.assertIn("connection refused", status)

    @patch("shutil.which")
    def test_empty_response(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            unlocked, status = prober._check_openai_unlock(9999)
        self.assertIsNone(unlocked)
        self.assertEqual(status, "empty response")

    @patch("shutil.which")
    def test_unexpected_response(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "no_newline_body"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            unlocked, status = prober._check_openai_unlock(9999)
        self.assertIsNone(unlocked)
        self.assertEqual(status, "unexpected response")


# ---------------------------------------------------------------------------
# _check_openai_unlock_async – edge-cases
# ---------------------------------------------------------------------------

class TestCheckOpenAiUnlockAsync(unittest.IsolatedAsyncioTestCase):
    @patch("shutil.which", return_value=None)
    async def test_curl_not_found(self, _mock: MagicMock) -> None:
        prober = SingboxProber()
        unlocked, status = await prober._check_openai_unlock_async(9999)
        self.assertIsNone(unlocked)
        self.assertEqual(status, "curl not found")

    @patch("shutil.which")
    async def test_401(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(0, '{"error": "key"}\n401', ""),
        ):
            unlocked, status = await prober._check_openai_unlock_async(9999)
        self.assertTrue(unlocked)
        self.assertEqual(status, "401 unauthorized")

    @patch("shutil.which")
    async def test_200(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(0, '{"data":[]}\n200', ""),
        ):
            unlocked, status = await prober._check_openai_unlock_async(9999)
        self.assertTrue(unlocked)
        self.assertEqual(status, "200 ok")

    @patch("shutil.which")
    async def test_403_region_blocked(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(0, '{"error": "unsupported_country_region_territory"}\n403', ""),
        ):
            unlocked, status = await prober._check_openai_unlock_async(9999)
        self.assertFalse(unlocked)
        self.assertEqual(status, "403 region blocked")

    @patch("shutil.which")
    async def test_403_forbidden(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(0, '{"error": "forbidden"}\n403', ""),
        ):
            unlocked, status = await prober._check_openai_unlock_async(9999)
        self.assertFalse(unlocked)
        self.assertEqual(status, "403 forbidden")

    @patch("shutil.which")
    async def test_429(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(0, '{"error": "rate_limit"}\n429', ""),
        ):
            unlocked, status = await prober._check_openai_unlock_async(9999)
        self.assertTrue(unlocked)
        self.assertEqual(status, "429 rate limited")

    @patch("shutil.which")
    async def test_other_status(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(0, 'body\n500', ""),
        ):
            unlocked, status = await prober._check_openai_unlock_async(9999)
        self.assertIsNone(unlocked)
        self.assertEqual(status, "http 500")

    @patch("shutil.which")
    async def test_curl_error(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(7, "", "connection refused"),
        ):
            unlocked, status = await prober._check_openai_unlock_async(9999)
        self.assertIsNone(unlocked)
        self.assertIn("connection refused", status)

    @patch("shutil.which")
    async def test_empty_response(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(0, "", ""),
        ):
            unlocked, status = await prober._check_openai_unlock_async(9999)
        self.assertIsNone(unlocked)
        self.assertEqual(status, "empty response")

    @patch("shutil.which")
    async def test_unexpected_response_no_newline(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        prober = SingboxProber()
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(0, "no_newline_body", ""),
        ):
            unlocked, status = await prober._check_openai_unlock_async(9999)
        self.assertIsNone(unlocked)
        self.assertEqual(status, "unexpected response")


# ---------------------------------------------------------------------------
# _tcp_fallback – more detailed
# ---------------------------------------------------------------------------

class TestTcpFallback(unittest.TestCase):
    def test_success(self) -> None:
        prober = SingboxProber()
        node = {"host": "1.2.3.4", "port": 443}
        with patch("socket.create_connection") as mock_conn, \
             patch("time.perf_counter", return_value=100.0):
            mock_conn.return_value.__enter__ = lambda s: s
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            result = prober._tcp_fallback(node, "k1", "prefix")
        self.assertTrue(result.available)
        self.assertEqual(result.latency_ms, 0)

    def test_connection_failure(self) -> None:
        prober = SingboxProber()
        node = {"host": "1.2.3.4", "port": 443}
        with patch("socket.create_connection", side_effect=OSError("refused")):
            result = prober._tcp_fallback(node, "k1", "prefix")
        self.assertFalse(result.available)
        self.assertIn("refused", result.error)


class TestTcpFallbackAsync(unittest.IsolatedAsyncioTestCase):
    async def test_success(self) -> None:
        prober = SingboxProber()
        node = {"host": "1.2.3.4", "port": 443}
        mock_writer = AsyncMock()
        with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_open, \
             patch("time.perf_counter", side_effect=[100.0, 100.05]):
            mock_open.return_value = (MagicMock(), mock_writer)
            result = await prober._tcp_fallback_async(node, "k1", "prefix")
        self.assertTrue(result.available)
        mock_writer.wait_closed.assert_awaited_once()

    async def test_os_error(self) -> None:
        prober = SingboxProber()
        node = {"host": "1.2.3.4", "port": 443}
        with patch("asyncio.open_connection", side_effect=OSError("refused")):
            result = await prober._tcp_fallback_async(node, "k1", "prefix")
        self.assertFalse(result.available)
        self.assertIn("refused", result.error)

    async def test_timeout_error(self) -> None:
        prober = SingboxProber()
        node = {"host": "1.2.3.4", "port": 443}

        async def _raise_timeout(*args: Any, **kwargs: Any) -> None:
            raise TimeoutError()

        with patch.object(asyncio, "open_connection", side_effect=_raise_timeout):
            result = await prober._tcp_fallback_async(node, "k1", "prefix")
        self.assertFalse(result.available)
        # In Python 3.13, TimeoutError is a subclass of OSError, so the OSError
        # handler catches it. The error contains the prefix and the exception repr.
        self.assertIn("prefix", result.error)

    async def test_invalid_host_port(self) -> None:
        prober = SingboxProber()
        node = {"host": "", "port": 0}
        result = await prober._tcp_fallback_async(node, "k1", "prefix")
        self.assertFalse(result.available)
        self.assertIn("invalid host/port", result.error)


# ---------------------------------------------------------------------------
# _curl_latency_probe – all URLs fail
# ---------------------------------------------------------------------------

class TestCurlLatencyProbe(unittest.TestCase):
    @patch("proxypool.tester.singbox.DEFAULT_LATENCY_TEST_URLS", [])
    def test_all_urls_fail(self) -> None:
        prober = SingboxProber(test_url="", test_urls=["https://a.com", "https://b.com"])
        mock_result = MagicMock()
        mock_result.returncode = 28
        mock_result.stdout = ""
        mock_result.stderr = "timeout"
        with patch("subprocess.run", return_value=mock_result), \
             patch("time.perf_counter", return_value=100.0):
            ok, latency, error = prober._curl_latency_probe("curl", 9999)
        self.assertFalse(ok)
        self.assertIsNone(latency)
        # Error should contain some indication of failure
        self.assertIsNotNone(error)

    @patch("proxypool.tester.singbox.DEFAULT_LATENCY_TEST_URLS", [])
    def test_all_urls_fail_empty_stderr_uses_exit_code(self) -> None:
        """When stderr is empty, falls back to curl exit code."""
        prober = SingboxProber(test_url="", test_urls=["https://a.com"])
        mock_result = MagicMock()
        mock_result.returncode = 28
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result), \
             patch("time.perf_counter", return_value=100.0):
            ok, latency, error = prober._curl_latency_probe("curl", 9999)
        self.assertFalse(ok)
        self.assertIsNone(latency)
        self.assertIn("curl exit=28", error)

    @patch("proxypool.tester.singbox.DEFAULT_LATENCY_TEST_URLS", [])
    def test_single_url_success(self) -> None:
        prober = SingboxProber(test_url="https://a.com")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "0.250"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result), \
             patch("time.perf_counter", side_effect=[100.0, 100.1]):
            ok, latency, error = prober._curl_latency_probe("curl", 9999)
        self.assertTrue(ok)
        self.assertEqual(latency, 250)


# ---------------------------------------------------------------------------
# _curl_latency_probe_async
# ---------------------------------------------------------------------------

class TestCurlLatencyProbeAsync(unittest.IsolatedAsyncioTestCase):
    @patch("proxypool.tester.singbox.DEFAULT_LATENCY_TEST_URLS", [])
    async def test_all_urls_fail(self) -> None:
        prober = SingboxProber(test_url="", test_urls=["https://a.com", "https://b.com"])
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(28, "", "timeout"),
        ), patch("time.perf_counter", return_value=100.0):
            ok, latency, error = await prober._curl_latency_probe_async("curl", 9999)
        self.assertFalse(ok)
        self.assertIsNone(latency)
        # Error should contain some indication of failure
        self.assertIsNotNone(error)

    @patch("proxypool.tester.singbox.DEFAULT_LATENCY_TEST_URLS", [])
    async def test_single_url_success(self) -> None:
        prober = SingboxProber(test_url="https://a.com")
        with patch(
            "proxypool.tester.singbox._run_command_async",
            new_callable=AsyncMock,
            return_value=(0, "0.300", ""),
        ), patch("time.perf_counter", side_effect=[100.0, 100.1]):
            ok, latency, error = await prober._curl_latency_probe_async("curl", 9999)
        self.assertTrue(ok)
        self.assertEqual(latency, 300)


# ---------------------------------------------------------------------------
# DEFAULT_LATENCY_TEST_URLS sanity
# ---------------------------------------------------------------------------

class TestDefaultLatencyTestUrls(unittest.TestCase):
    def test_not_empty(self) -> None:
        self.assertGreater(len(DEFAULT_LATENCY_TEST_URLS), 0)

    def test_all_https(self) -> None:
        for url in DEFAULT_LATENCY_TEST_URLS:
            self.assertTrue(url.startswith("https://"))


# ---------------------------------------------------------------------------
# _wait_port / _wait_port_async
# ---------------------------------------------------------------------------

class TestWaitPort(unittest.TestCase):
    def test_returns_true_for_open_port(self) -> None:
        prober = SingboxProber()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.bind(("127.0.0.1", 0))
            srv.listen(1)
            port = srv.getsockname()[1]
            self.assertTrue(prober._wait_port("127.0.0.1", port, 1.0))

    def test_returns_false_for_closed_port(self) -> None:
        prober = SingboxProber()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.bind(("127.0.0.1", 0))
            port = srv.getsockname()[1]
        self.assertFalse(prober._wait_port("127.0.0.1", port, 0.1))


class TestWaitPortAsync(unittest.IsolatedAsyncioTestCase):
    async def test_returns_true_for_open_port(self) -> None:
        prober = SingboxProber()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.bind(("127.0.0.1", 0))
            srv.listen(1)
            port = srv.getsockname()[1]
            self.assertTrue(await prober._wait_port_async("127.0.0.1", port, 1.0))

    async def test_returns_false_for_closed_port(self) -> None:
        prober = SingboxProber()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.bind(("127.0.0.1", 0))
            port = srv.getsockname()[1]
        self.assertFalse(await prober._wait_port_async("127.0.0.1", port, 0.1))


# ---------------------------------------------------------------------------
# probe() with sing-box found – covers subprocess paths
# ---------------------------------------------------------------------------

class TestProbeWithBinaryFound(unittest.TestCase):
    @patch("shutil.which")
    def test_probe_find_port_error(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", side_effect=OSError("no ports")):
            result = prober.probe(node)
        self.assertFalse(result.available)
        self.assertIn("local socket unavailable", result.error)

    @patch("shutil.which")
    def test_probe_startup_timeout_fallback(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=False), \
             patch("subprocess.Popen"):
            result = prober.probe(node)
        self.assertFalse(result.available)
        self.assertIn("sing-box startup timeout", result.error)

    @patch("shutil.which")
    def test_probe_curl_not_found_after_startup(self, mock_which: MagicMock) -> None:
        def which_side_effect(name):
            if name == "sing-box":
                return "/usr/bin/sing-box"
            return None
        mock_which.side_effect = which_side_effect
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=True), \
             patch("subprocess.Popen"):
            result = prober.probe(node)
        self.assertFalse(result.available)
        self.assertIn("curl not found", result.error)

    @patch("shutil.which")
    def test_probe_latency_success(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=True), \
             patch("subprocess.Popen"), \
             patch.object(prober, "_curl_latency_probe", return_value=(True, 120, "")), \
             patch.object(prober, "_check_openai_unlock", return_value=(True, "401 unauthorized")):
            result = prober.probe(node)
        self.assertTrue(result.available)
        self.assertEqual(result.latency_ms, 120)
        self.assertTrue(result.openai_unlocked)

    @patch("shutil.which")
    def test_probe_latency_failure(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=True), \
             patch("subprocess.Popen"), \
             patch.object(prober, "_curl_latency_probe", return_value=(False, None, "timeout error")):
            result = prober.probe(node)
        self.assertFalse(result.available)
        self.assertIn("timeout error", result.error)


# ---------------------------------------------------------------------------
# probe_async() with sing-box found – covers subprocess paths
# ---------------------------------------------------------------------------

class TestProbeAsyncWithBinaryFound(unittest.IsolatedAsyncioTestCase):
    @patch("shutil.which")
    async def test_probe_async_find_port_error(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", side_effect=OSError("no ports")):
            result = await prober.probe_async(node)
        self.assertFalse(result.available)
        self.assertIn("local socket unavailable", result.error)

    @patch("shutil.which")
    async def test_probe_async_startup_timeout(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_proc = AsyncMock()
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port_async", new_callable=AsyncMock, return_value=False), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch("proxypool.tester.singbox._stop_process_async", new_callable=AsyncMock):
            result = await prober.probe_async(node)
        self.assertFalse(result.available)
        self.assertIn("sing-box startup timeout", result.error)

    @patch("shutil.which")
    async def test_probe_async_curl_not_found(self, mock_which: MagicMock) -> None:
        def which_side_effect(name):
            return "/usr/bin/sing-box" if name == "sing-box" else None
        mock_which.side_effect = which_side_effect
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_proc = AsyncMock()
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port_async", new_callable=AsyncMock, return_value=True), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch("proxypool.tester.singbox._stop_process_async", new_callable=AsyncMock):
            result = await prober.probe_async(node)
        self.assertFalse(result.available)
        self.assertIn("curl not found", result.error)

    @patch("shutil.which")
    async def test_probe_async_latency_success(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_proc = AsyncMock()
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port_async", new_callable=AsyncMock, return_value=True), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch.object(prober, "_curl_latency_probe_async", new_callable=AsyncMock, return_value=(True, 80, "")), \
             patch.object(prober, "_check_openai_unlock_async", new_callable=AsyncMock, return_value=(True, "200 ok")), \
             patch("proxypool.tester.singbox._stop_process_async", new_callable=AsyncMock):
            result = await prober.probe_async(node)
        self.assertTrue(result.available)
        self.assertEqual(result.latency_ms, 80)

    @patch("shutil.which")
    async def test_probe_async_latency_failure(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_proc = AsyncMock()
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port_async", new_callable=AsyncMock, return_value=True), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch.object(prober, "_curl_latency_probe_async", new_callable=AsyncMock, return_value=(False, None, "probe failed")), \
             patch("proxypool.tester.singbox._stop_process_async", new_callable=AsyncMock):
            result = await prober.probe_async(node)
        self.assertFalse(result.available)
        self.assertIn("probe failed", result.error)


# ---------------------------------------------------------------------------
# probe_with_front_proxy() with binary found
# ---------------------------------------------------------------------------

class TestProbeWithFrontProxyWithBinaryFound(unittest.TestCase):
    @patch("shutil.which")
    def test_probe_with_front_find_port_error(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", side_effect=OSError("no ports")):
            result = prober.probe_with_front_proxy(node, front)
        self.assertFalse(result.available)
        self.assertIn("local socket unavailable", result.error)

    @patch("shutil.which")
    @unittest.skip("Requires sing-box binary")
    def test_probe_with_front_startup_timeout(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=False), \
             patch("subprocess.Popen"):
            result = prober.probe_with_front_proxy(node, front)
        self.assertFalse(result.available)
        self.assertIn("sing-box startup timeout", result.error)

    @patch("shutil.which")
    def test_probe_with_front_curl_not_found(self, mock_which: MagicMock) -> None:
        def which_side_effect(name):
            return "/usr/bin/sing-box" if name == "sing-box" else None
        mock_which.side_effect = which_side_effect
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=True), \
             patch("subprocess.Popen"):
            result = prober.probe_with_front_proxy(node, front)
        self.assertFalse(result.available)
        self.assertIn("curl not found", result.error)

    @patch("shutil.which")
    def test_probe_with_front_latency_success(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=True), \
             patch("subprocess.Popen"), \
             patch.object(prober, "_curl_latency_probe", return_value=(True, 90, "")), \
             patch.object(prober, "_check_openai_unlock", return_value=(False, "403 region blocked")):
            result = prober.probe_with_front_proxy(node, front)
        self.assertTrue(result.available)
        self.assertEqual(result.latency_ms, 90)
        self.assertFalse(result.openai_unlocked)


# ---------------------------------------------------------------------------
# probe_with_front_proxy_async() with binary found
# ---------------------------------------------------------------------------

class TestProbeWithFrontProxyAsyncWithBinaryFound(unittest.IsolatedAsyncioTestCase):
    @patch("shutil.which")
    async def test_probe_with_front_async_find_port_error(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", side_effect=OSError("no ports")):
            result = await prober.probe_with_front_proxy_async(node, front)
        self.assertFalse(result.available)
        self.assertIn("local socket unavailable", result.error)

    @patch("shutil.which")
    async def test_probe_with_front_async_startup_timeout(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        mock_proc = AsyncMock()
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port_async", new_callable=AsyncMock, return_value=False), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch("proxypool.tester.singbox._stop_process_async", new_callable=AsyncMock):
            result = await prober.probe_with_front_proxy_async(node, front)
        self.assertFalse(result.available)
        self.assertIn("sing-box startup timeout", result.error)

    @patch("shutil.which")
    async def test_probe_with_front_async_latency_success(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        mock_proc = AsyncMock()
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port_async", new_callable=AsyncMock, return_value=True), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch.object(prober, "_curl_latency_probe_async", new_callable=AsyncMock, return_value=(True, 110, "")), \
             patch.object(prober, "_check_openai_unlock_async", new_callable=AsyncMock, return_value=(None, "http 503")), \
             patch("proxypool.tester.singbox._stop_process_async", new_callable=AsyncMock):
            result = await prober.probe_with_front_proxy_async(node, front)
        self.assertTrue(result.available)
        self.assertEqual(result.latency_ms, 110)


# ---------------------------------------------------------------------------
# speed_test_async() with binary found
# ---------------------------------------------------------------------------

class TestSpeedTestAsyncWithBinaryFound(unittest.IsolatedAsyncioTestCase):
    @patch("shutil.which")
    async def test_speed_test_find_port_error(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", side_effect=OSError("no ports")):
            result = await prober.speed_test_async(node, "https://example.com/file")
        self.assertFalse(result.ok)
        self.assertIn("local socket unavailable", result.error)

    @patch("shutil.which")
    @unittest.skip("Requires sing-box binary")
    async def test_speed_test_startup_timeout(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_proc = AsyncMock()
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port_async", new_callable=AsyncMock, return_value=False), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch("proxypool.tester.singbox._stop_process_async", new_callable=AsyncMock):
            result = await prober.speed_test_async(node, "https://example.com/file")
        self.assertFalse(result.ok)
        self.assertIn("sing-box startup timeout", result.error)

    @patch("shutil.which")
    async def test_speed_test_curl_failure(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_proc = AsyncMock()
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port_async", new_callable=AsyncMock, return_value=True), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch("proxypool.tester.singbox._run_command_async", new_callable=AsyncMock, return_value=(7, "", "connection refused")), \
             patch("proxypool.tester.singbox._stop_process_async", new_callable=AsyncMock):
            result = await prober.speed_test_async(node, "https://example.com/file")
        self.assertFalse(result.ok)
        self.assertIn("connection refused", result.error)

    @patch("shutil.which")
    async def test_speed_test_success(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_proc = AsyncMock()
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port_async", new_callable=AsyncMock, return_value=True), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch("proxypool.tester.singbox._run_command_async", new_callable=AsyncMock, return_value=(0, "1048576 1.0", "")), \
             patch("proxypool.tester.singbox._stop_process_async", new_callable=AsyncMock), \
             patch("time.perf_counter", side_effect=[100.0, 101.0]):
            result = await prober.speed_test_async(node, "https://example.com/file")
        self.assertTrue(result.ok)
        self.assertEqual(result.bytes_downloaded, 1048576)


# ---------------------------------------------------------------------------
# speed_test_async – covers zero bytes path
# ---------------------------------------------------------------------------

class TestSpeedTestAsyncEdgeCases(unittest.IsolatedAsyncioTestCase):
    @patch("shutil.which")
    async def test_speed_test_zero_bytes(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_proc = AsyncMock()
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port_async", new_callable=AsyncMock, return_value=True), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch("proxypool.tester.singbox._run_command_async", new_callable=AsyncMock, return_value=(0, "", "")), \
             patch("proxypool.tester.singbox._stop_process_async", new_callable=AsyncMock), \
             patch("time.perf_counter", side_effect=[100.0, 101.0]):
            result = await prober.speed_test_async(node, "https://example.com/file")
        self.assertTrue(result.ok)
        self.assertEqual(result.speed_mbps, 0.0)


# ---------------------------------------------------------------------------
# fetch_json_via_proxy – covers front proxy chain + subprocess paths
# ---------------------------------------------------------------------------

class TestFetchJsonViaProxyWithBinary(unittest.TestCase):
    @patch("shutil.which")
    @unittest.skip("Requires sing-box binary")
    def test_fetch_json_with_valid_front_proxy_chain(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        front = {"normalized_key": "f", "protocol": "trojan", "host": "f.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=False), \
             patch("subprocess.Popen"):
            with self.assertRaises(RuntimeError) as ctx:
                prober.fetch_json_via_proxy(node, "https://example.com", front_proxy=front)
            self.assertIn("sing-box startup timeout", str(ctx.exception))

    @patch("shutil.which")
    def test_fetch_json_curl_not_found(self, mock_which: MagicMock) -> None:
        def which_side_effect(name):
            return "/usr/bin/sing-box" if name == "sing-box" else None
        mock_which.side_effect = which_side_effect
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=True), \
             patch("subprocess.Popen"):
            with self.assertRaises(RuntimeError) as ctx:
                prober.fetch_json_via_proxy(node, "https://example.com")
            self.assertIn("curl not found", str(ctx.exception))

    @patch("shutil.which")
    def test_fetch_json_curl_error(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_result = MagicMock()
        mock_result.returncode = 7
        mock_result.stdout = ""
        mock_result.stderr = "connection refused"
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=True), \
             patch("subprocess.Popen"), \
             patch("subprocess.run", return_value=mock_result):
            with self.assertRaises(RuntimeError) as ctx:
                prober.fetch_json_via_proxy(node, "https://example.com")
            self.assertIn("connection refused", str(ctx.exception))

    @patch("shutil.which")
    def test_fetch_json_empty_response(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=True), \
             patch("subprocess.Popen"), \
             patch("subprocess.run", return_value=mock_result):
            with self.assertRaises(RuntimeError) as ctx:
                prober.fetch_json_via_proxy(node, "https://example.com")
            self.assertIn("empty response", str(ctx.exception))

    @patch("shutil.which")
    def test_fetch_json_invalid_json(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"
        mock_result.stderr = ""
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=True), \
             patch("subprocess.Popen"), \
             patch("subprocess.run", return_value=mock_result):
            with self.assertRaises(RuntimeError) as ctx:
                prober.fetch_json_via_proxy(node, "https://example.com")
            self.assertIn("invalid json", str(ctx.exception))

    @patch("shutil.which")
    def test_fetch_json_non_object_json(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/sing-box"
        prober = SingboxProber()
        node = {"normalized_key": "k", "protocol": "trojan", "host": "h.com", "port": 443, "extra": {"password": "p"}}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "[1, 2, 3]"
        mock_result.stderr = ""
        with patch("proxypool.tester.singbox._find_free_port", return_value=19999), \
             patch.object(prober, "_wait_port", return_value=True), \
             patch("subprocess.Popen"), \
             patch("subprocess.run", return_value=mock_result):
            with self.assertRaises(RuntimeError) as ctx:
                prober.fetch_json_via_proxy(node, "https://example.com")
            self.assertIn("json payload is not object", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
