"""
Tests for proxypool.collector.fetcher targeting uncovered lines.

Covers:
- fetch_text (lines 20-61): Content-Length validation, charset extraction
- fetch_text_via_proxy_node (lines 64-131): all error paths
- _extract_charset (lines 134-139)
- _find_free_port (lines 142-145)
- _wait_port (lines 148-156)
- _stop_process (lines 159-167)
"""

from __future__ import annotations

import io
import socket
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from proxypool.collector.fetcher import (
    FetchError,
    _extract_charset,
    _find_free_port,
    _stop_process,
    _wait_port,
    fetch_text,
    fetch_text_via_proxy_node,
)


# ---------------------------------------------------------------------------
# 1. fetch_text (lines 20-61)
# ---------------------------------------------------------------------------


class TestFetchText:
    def test_content_length_exceeds_limit(self) -> None:
        """Content-Length header exceeding limit raises FetchError."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers = {"Content-Length": "999999999", "Content-Type": "text/plain"}
        mock_resp.read.return_value = b"small body"

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_resp

        with patch("proxypool.collector.fetcher.build_opener", return_value=mock_opener):
            with pytest.raises(FetchError, match="Content too large"):
                fetch_text("https://example.com", max_content_length=1024)

    def test_invalid_content_length_header_continues(self) -> None:
        """Invalid Content-Length header is ignored and reading continues."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers = {"Content-Length": "not-a-number", "Content-Type": "text/plain"}
        mock_resp.read.return_value = b"hello"

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_resp

        with patch("proxypool.collector.fetcher.build_opener", return_value=mock_opener):
            result = fetch_text("https://example.com")
            assert result == "hello"

    def test_body_exceeds_limit(self) -> None:
        """Read body exceeding limit raises FetchError."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.read.return_value = b"x" * 2000

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_resp

        with patch("proxypool.collector.fetcher.build_opener", return_value=mock_opener):
            with pytest.raises(FetchError, match="Content too large"):
                fetch_text("https://example.com", max_content_length=1000)

    def test_charset_extraction_from_content_type(self) -> None:
        """Charset in Content-Type header is used for decoding."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.read.return_value = "hello".encode("utf-8")

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_resp

        with patch("proxypool.collector.fetcher.build_opener", return_value=mock_opener):
            result = fetch_text("https://example.com")
            assert result == "hello"

    def test_garbage_content_type_falls_back_to_utf8(self) -> None:
        """Garbage Content-Type falls back to utf-8."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers = {"Content-Type": "application/octet-stream"}
        mock_resp.read.return_value = "fallback".encode("utf-8")

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_resp

        with patch("proxypool.collector.fetcher.build_opener", return_value=mock_opener):
            result = fetch_text("https://example.com")
            assert result == "fallback"

    def test_no_content_length_header(self) -> None:
        """No Content-Length header proceeds with reading."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers = {}
        mock_resp.read.return_value = b"ok"

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_resp

        with patch("proxypool.collector.fetcher.build_opener", return_value=mock_opener):
            result = fetch_text("https://example.com")
            assert result == "ok"


# ---------------------------------------------------------------------------
# 2. fetch_text_via_proxy_node (lines 64-131)
# ---------------------------------------------------------------------------


class TestFetchTextViaProxyNode:
    def test_unsupported_protocol(self) -> None:
        """Unsupported proxy protocol raises FetchError."""
        proxy_node = {"protocol": "unknown", "host": "1.2.3.4", "port": 443}

        with patch(
            "proxypool.collector.fetcher.build_singbox_outbound", return_value=None
        ):
            with pytest.raises(FetchError, match="unsupported proxy protocol"):
                fetch_text_via_proxy_node(
                    "https://example.com", proxy_node, singbox_binary="sing-box"
                )

    def test_singbox_not_found(self) -> None:
        """Missing sing-box binary raises FetchError."""
        proxy_node = {
            "protocol": "trojan",
            "host": "1.2.3.4",
            "port": 443,
            "extra": {"password": "test"},
        }

        with patch(
            "proxypool.collector.fetcher.build_singbox_outbound",
            return_value={"type": "trojan"},
        ):
            with patch("proxypool.collector.fetcher.shutil.which", return_value=None):
                with pytest.raises(FetchError, match="sing-box not found"):
                    fetch_text_via_proxy_node(
                        "https://example.com",
                        proxy_node,
                        singbox_binary="sing-box",
                    )

    def test_curl_not_found(self) -> None:
        """Missing curl binary raises FetchError."""
        proxy_node = {
            "protocol": "trojan",
            "host": "1.2.3.4",
            "port": 443,
            "extra": {"password": "test"},
        }

        def fake_which(name):
            if name == "sing-box":
                return "/usr/bin/sing-box"
            return None

        with patch(
            "proxypool.collector.fetcher.build_singbox_outbound",
            return_value={"type": "trojan"},
        ):
            with patch("proxypool.collector.fetcher.shutil.which", side_effect=fake_which):
                with pytest.raises(FetchError, match="curl not found"):
                    fetch_text_via_proxy_node(
                        "https://example.com",
                        proxy_node,
                        singbox_binary="sing-box",
                    )

    def test_free_port_oserror(self) -> None:
        """OSError when finding free port raises FetchError."""
        proxy_node = {
            "protocol": "trojan",
            "host": "1.2.3.4",
            "port": 443,
            "extra": {"password": "test"},
        }

        def fake_which(name):
            if name in ("sing-box", "curl"):
                return f"/usr/bin/{name}"
            return None

        with patch(
            "proxypool.collector.fetcher.build_singbox_outbound",
            return_value={"type": "trojan"},
        ):
            with patch("proxypool.collector.fetcher.shutil.which", side_effect=fake_which):
                with patch(
                    "proxypool.collector.fetcher._find_free_port",
                    side_effect=OSError("no free port"),
                ):
                    with pytest.raises(FetchError, match="local socket unavailable"):
                        fetch_text_via_proxy_node(
                            "https://example.com",
                            proxy_node,
                            singbox_binary="sing-box",
                        )

    def test_singbox_startup_timeout(self) -> None:
        """Timeout waiting for sing-box to start raises FetchError."""
        proxy_node = {
            "protocol": "trojan",
            "host": "1.2.3.4",
            "port": 443,
            "extra": {"password": "test"},
        }

        def fake_which(name):
            if name in ("sing-box", "curl"):
                return f"/usr/bin/{name}"
            return None

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        with patch(
            "proxypool.collector.fetcher.build_singbox_outbound",
            return_value={"type": "trojan"},
        ):
            with patch("proxypool.collector.fetcher.shutil.which", side_effect=fake_which):
                with patch(
                    "proxypool.collector.fetcher._find_free_port", return_value=19999
                ):
                    with patch(
                        "proxypool.collector.fetcher.subprocess.Popen",
                        return_value=mock_proc,
                    ):
                        with patch(
                            "proxypool.collector.fetcher._wait_port", return_value=False
                        ):
                            with pytest.raises(
                                FetchError, match="subscription proxy startup timeout"
                            ):
                                fetch_text_via_proxy_node(
                                    "https://example.com",
                                    proxy_node,
                                    singbox_binary="sing-box",
                                    timeout_sec=2.0,
                                )
                            mock_proc.terminate.assert_called()

    def test_curl_failure(self) -> None:
        """Non-zero curl exit code raises FetchError."""
        proxy_node = {
            "protocol": "trojan",
            "host": "1.2.3.4",
            "port": 443,
            "extra": {"password": "test"},
        }

        def fake_which(name):
            if name in ("sing-box", "curl"):
                return f"/usr/bin/{name}"
            return None

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        mock_completed = MagicMock()
        mock_completed.returncode = 1
        mock_completed.stderr = "curl: connection refused"

        with patch(
            "proxypool.collector.fetcher.build_singbox_outbound",
            return_value={"type": "trojan"},
        ):
            with patch("proxypool.collector.fetcher.shutil.which", side_effect=fake_which):
                with patch(
                    "proxypool.collector.fetcher._find_free_port", return_value=19999
                ):
                    with patch(
                        "proxypool.collector.fetcher.subprocess.Popen",
                        return_value=mock_proc,
                    ):
                        with patch(
                            "proxypool.collector.fetcher._wait_port", return_value=True
                        ):
                            with patch(
                                "proxypool.collector.fetcher.subprocess.run",
                                return_value=mock_completed,
                            ):
                                with pytest.raises(FetchError, match="curl"):
                                    fetch_text_via_proxy_node(
                                        "https://example.com",
                                        proxy_node,
                                        singbox_binary="sing-box",
                                    )

    def test_curl_success(self) -> None:
        """Successful curl fetch returns output."""
        proxy_node = {
            "protocol": "trojan",
            "host": "1.2.3.4",
            "port": 443,
            "extra": {"password": "test"},
        }

        def fake_which(name):
            if name in ("sing-box", "curl"):
                return f"/usr/bin/{name}"
            return None

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        mock_completed = MagicMock()
        mock_completed.returncode = 0
        mock_completed.stdout = "subscription content here"
        mock_completed.stderr = ""

        with patch(
            "proxypool.collector.fetcher.build_singbox_outbound",
            return_value={"type": "trojan"},
        ):
            with patch("proxypool.collector.fetcher.shutil.which", side_effect=fake_which):
                with patch(
                    "proxypool.collector.fetcher._find_free_port", return_value=19999
                ):
                    with patch(
                        "proxypool.collector.fetcher.subprocess.Popen",
                        return_value=mock_proc,
                    ):
                        with patch(
                            "proxypool.collector.fetcher._wait_port", return_value=True
                        ):
                            with patch(
                                "proxypool.collector.fetcher.subprocess.run",
                                return_value=mock_completed,
                            ):
                                result = fetch_text_via_proxy_node(
                                    "https://example.com",
                                    proxy_node,
                                    singbox_binary="sing-box",
                                )
                                assert result == "subscription content here"

    def test_curl_no_stderr(self) -> None:
        """Curl failure with no stderr uses exit code as error."""
        proxy_node = {
            "protocol": "trojan",
            "host": "1.2.3.4",
            "port": 443,
            "extra": {"password": "test"},
        }

        def fake_which(name):
            if name in ("sing-box", "curl"):
                return f"/usr/bin/{name}"
            return None

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        mock_completed = MagicMock()
        mock_completed.returncode = 7
        mock_completed.stdout = ""
        mock_completed.stderr = ""

        with patch(
            "proxypool.collector.fetcher.build_singbox_outbound",
            return_value={"type": "trojan"},
        ):
            with patch("proxypool.collector.fetcher.shutil.which", side_effect=fake_which):
                with patch(
                    "proxypool.collector.fetcher._find_free_port", return_value=19999
                ):
                    with patch(
                        "proxypool.collector.fetcher.subprocess.Popen",
                        return_value=mock_proc,
                    ):
                        with patch(
                            "proxypool.collector.fetcher._wait_port", return_value=True
                        ):
                            with patch(
                                "proxypool.collector.fetcher.subprocess.run",
                                return_value=mock_completed,
                            ):
                                with pytest.raises(FetchError):
                                    fetch_text_via_proxy_node(
                                        "https://example.com",
                                        proxy_node,
                                        singbox_binary="sing-box",
                                    )


# ---------------------------------------------------------------------------
# 3. _extract_charset (lines 134-139)
# ---------------------------------------------------------------------------


class TestExtractCharset:
    def test_charset_present(self) -> None:
        assert _extract_charset("text/html; charset=utf-8") == "utf-8"

    def test_charset_uppercase(self) -> None:
        assert _extract_charset("text/html; CHARSET=ISO-8859-1") == "iso-8859-1"

    def test_charset_with_semicolon_after(self) -> None:
        assert _extract_charset("text/html; charset=utf-8; boundary=xxx") == "utf-8"

    def test_no_charset(self) -> None:
        assert _extract_charset("text/html") is None

    def test_empty_string(self) -> None:
        assert _extract_charset("") is None


# ---------------------------------------------------------------------------
# 4. _find_free_port (lines 142-145)
# ---------------------------------------------------------------------------


class TestFindFreePort:
    def test_returns_valid_port(self) -> None:
        port = _find_free_port()
        assert isinstance(port, int)
        assert 1 <= port <= 65535

    def test_returns_available_port(self) -> None:
        port = _find_free_port()
        # Port should be connectable (or at least bindable)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex(("127.0.0.1", port))
            # Port should not be in use (connect should fail)
            assert result != 0


# ---------------------------------------------------------------------------
# 5. _wait_port (lines 148-156)
# ---------------------------------------------------------------------------


class TestWaitPort:
    def test_port_not_available(self) -> None:
        """Wait for a port that never opens times out."""
        result = _wait_port("127.0.0.1", 59999, timeout_sec=0.1)
        assert result is False

    def test_port_already_open(self) -> None:
        """Port that is already open returns True."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.bind(("127.0.0.1", 0))
            srv.listen(1)
            port = srv.getsockname()[1]
            result = _wait_port("127.0.0.1", port, timeout_sec=1.0)
            assert result is True


# ---------------------------------------------------------------------------
# 6. _stop_process (lines 159-167)
# ---------------------------------------------------------------------------


class TestStopProcess:
    def test_already_exited(self) -> None:
        """Process already exited is not terminated."""
        proc = MagicMock()
        proc.poll.return_value = 0
        _stop_process(proc)
        proc.terminate.assert_not_called()

    def test_normal_terminate(self) -> None:
        """Running process is terminated normally."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = None
        _stop_process(proc)
        proc.terminate.assert_called_once()

    def test_terminate_timeout_kills(self) -> None:
        """Process that doesn't terminate is killed."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=1.0),
            None,
        ]
        _stop_process(proc)
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()
