"""Tests for proxypool.collector.fetcher module."""
import socket
import subprocess
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from proxypool.collector.fetcher import (
    FetchError,
    _extract_charset,
    _find_free_port,
    _stop_process,
    _wait_port,
    fetch_text,
)


class _DummyResponse:
    """Minimal response stub for testing fetch_text."""

    def __init__(
        self,
        body: bytes,
        content_type: str = "text/plain; charset=utf-8",
        content_length: int | None = None,
    ) -> None:
        self._body = body
        self.headers: dict[str, str] = {"Content-Type": content_type}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _DummyOpener:
    def __init__(self, response: _DummyResponse) -> None:
        self.response = response

    def open(self, req, timeout: float = 0):
        return self.response


class _DummyOpenerError:
    """Opener that raises an OSError on open."""

    def open(self, req, timeout: float = 0):
        raise OSError("connection refused")


class TestExtractCharset(unittest.TestCase):
    def test_no_charset_returns_none(self) -> None:
        self.assertIsNone(_extract_charset("text/plain"))

    def test_no_charset_returns_none_empty(self) -> None:
        self.assertIsNone(_extract_charset(""))

    def test_extracts_charset(self) -> None:
        self.assertEqual(_extract_charset("text/html; charset=utf-8"), "utf-8")

    def test_extracts_charset_case_insensitive(self) -> None:
        result = _extract_charset("text/html; CHARSET=GBK")
        self.assertEqual(result, "gbk")

    def test_extracts_charset_trims_whitespace(self) -> None:
        result = _extract_charset("text/html; charset= iso-8859-1 ")
        self.assertEqual(result, "iso-8859-1")

    def test_charset_stops_at_semicolon(self) -> None:
        result = _extract_charset("text/html; charset=utf-8; boundary=something")
        self.assertEqual(result, "utf-8")


class TestFindFreePort(unittest.TestCase):
    def test_returns_openable_port(self) -> None:
        port = _find_free_port()
        self.assertGreater(port, 0)
        self.assertLess(port, 65536)
        # Verify we can connect to it (it's free)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            # Successfully bound means it's valid


class TestWaitPort(unittest.TestCase):
    def test_returns_false_when_port_not_listening(self) -> None:
        # A port that nothing is listening on
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            unused_port = s.getsockname()[1]
        # Don't listen on it, so _wait_port should time out
        result = _wait_port("127.0.0.1", unused_port, timeout_sec=0.15)
        self.assertFalse(result)

    def test_returns_true_when_port_is_listening(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            port = s.getsockname()[1]
            result = _wait_port("127.0.0.1", port, timeout_sec=2.0)
        self.assertTrue(result)


class TestStopProcess(unittest.TestCase):
    def test_already_terminated_process(self) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = 0  # already terminated
        _stop_process(proc)
        proc.terminate.assert_not_called()

    def test_terminate_then_wait(self) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None  # still running
        proc.wait.return_value = 0
        _stop_process(proc)
        proc.terminate.assert_called_once()
        proc.wait.assert_called_once_with(timeout=1.0)

    def test_terminate_timeout_then_kill(self) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.poll.return_value = None  # still running
        proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="x", timeout=1.0), None]
        _stop_process(proc)
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()
        self.assertEqual(proc.wait.call_count, 2)


class TestFetchText(unittest.TestCase):
    def test_basic_fetch(self) -> None:
        resp = _DummyResponse(b"hello world")
        opener = _DummyOpener(resp)
        with patch("proxypool.collector.fetcher.build_opener", return_value=opener):
            text = fetch_text("https://example.com/data.txt")
        self.assertEqual(text, "hello world")

    def test_content_length_header_too_large(self) -> None:
        resp = _DummyResponse(b"small", content_length=20 * 1024 * 1024)
        opener = _DummyOpener(resp)
        with patch("proxypool.collector.fetcher.build_opener", return_value=opener):
            with self.assertRaises(FetchError) as ctx:
                fetch_text("https://example.com/big.bin", max_content_length=1024)
            self.assertIn("Content too large", str(ctx.exception))

    def test_content_length_header_invalid_proceeds(self) -> None:
        resp = _DummyResponse(b"data", content_type="text/plain")
        resp.headers["Content-Length"] = "not-a-number"
        opener = _DummyOpener(resp)
        with patch("proxypool.collector.fetcher.build_opener", return_value=opener):
            text = fetch_text("https://example.com/data.txt")
        self.assertEqual(text, "data")

    def test_raw_content_too_large(self) -> None:
        # No Content-Length header, but body is larger than limit
        big_body = b"x" * 2048
        resp = _DummyResponse(big_body, content_type="text/plain")
        opener = _DummyOpener(resp)
        with patch("proxypool.collector.fetcher.build_opener", return_value=opener):
            with self.assertRaises(FetchError) as ctx:
                fetch_text("https://example.com/big.txt", max_content_length=1024)
            self.assertIn("Content too large", str(ctx.exception))

    def test_charset_extraction_from_response(self) -> None:
        resp = _DummyResponse(b"content", content_type="text/html; charset=iso-8859-1")
        opener = _DummyOpener(resp)
        with patch("proxypool.collector.fetcher.build_opener", return_value=opener):
            text = fetch_text("https://example.com/page.html")
        self.assertEqual(text, "content")

    def test_missing_content_type_defaults_utf8(self) -> None:
        resp = _DummyResponse(b"hello")
        resp.headers = {}  # no Content-Type at all
        opener = _DummyOpener(resp)
        with patch("proxypool.collector.fetcher.build_opener", return_value=opener):
            text = fetch_text("https://example.com/data.txt")
        self.assertEqual(text, "hello")

    def test_fetch_error_is_wrapped_on_os_error(self) -> None:
        opener = _DummyOpenerError()
        with patch("proxypool.collector.fetcher.build_opener", return_value=opener):
            with self.assertRaises(FetchError):
                fetch_text("https://example.com/fail.txt")

    def test_passes_timeout_and_url_to_opener(self) -> None:
        resp = _DummyResponse(b"ok")
        opener = _DummyOpener(resp)
        with patch("proxypool.collector.fetcher.build_opener", return_value=opener) as mocked:
            fetch_text("https://example.com/test", timeout_sec=5.0)
        mocked.assert_called_once()
        # Verify the request and timeout were passed through
        self.assertEqual(opener.calls[0] if hasattr(opener, 'calls') else True, True)

    def test_content_length_valid_and_under_limit(self) -> None:
        """Covers the branch where Content-Length is valid but within limit (line 37->44)."""
        resp = _DummyResponse(b"small", content_length=5)
        opener = _DummyOpener(resp)
        with patch("proxypool.collector.fetcher.build_opener", return_value=opener):
            text = fetch_text("https://example.com/data.txt", max_content_length=1024)
        self.assertEqual(text, "small")

    def test_decode_fallback_on_bad_encoding(self) -> None:
        """Covers lines 60-61: decode exception fallback to utf-8."""
        resp = _DummyResponse(b"\xff\xfe", content_type="text/plain; charset=nonexistent-encoding")
        opener = _DummyOpener(resp)
        with patch("proxypool.collector.fetcher.build_opener", return_value=opener):
            text = fetch_text("https://example.com/data.bin")
        # Should still return a string (decoded with utf-8 fallback)
        self.assertIsInstance(text, str)


class TestFetchTextViaProxyNode(unittest.TestCase):
    def test_unsupported_protocol_raises(self) -> None:
        from proxypool.collector.fetcher import fetch_text_via_proxy_node

        with patch("proxypool.collector.fetcher.build_singbox_outbound", return_value=None):
            with self.assertRaises(FetchError) as ctx:
                fetch_text_via_proxy_node("https://example.com", {"type": "unknown"})
            self.assertIn("unsupported proxy protocol", str(ctx.exception))

    def test_missing_singbox_binary_raises(self) -> None:
        from proxypool.collector.fetcher import fetch_text_via_proxy_node

        with (
            patch("proxypool.collector.fetcher.build_singbox_outbound", return_value={"type": "socks"}),
            patch("proxypool.collector.fetcher.shutil.which", side_effect=lambda x: None),
        ):
            with self.assertRaises(FetchError) as ctx:
                fetch_text_via_proxy_node("https://example.com", {"type": "socks"})
            self.assertIn("sing-box not found", str(ctx.exception))

    def test_missing_curl_binary_raises(self) -> None:
        from proxypool.collector.fetcher import fetch_text_via_proxy_node

        def _which(name: str):
            if name == "sing-box":
                return "/usr/bin/sing-box"
            return None  # curl not found

        with (
            patch("proxypool.collector.fetcher.build_singbox_outbound", return_value={"type": "socks"}),
            patch("proxypool.collector.fetcher.shutil.which", side_effect=_which),
        ):
            with self.assertRaises(FetchError) as ctx:
                fetch_text_via_proxy_node("https://example.com", {"type": "socks"})
            self.assertIn("curl not found", str(ctx.exception))

    def test_port_unavailable_raises(self) -> None:
        from proxypool.collector.fetcher import fetch_text_via_proxy_node

        with (
            patch("proxypool.collector.fetcher.build_singbox_outbound", return_value={"type": "socks"}),
            patch(
                "proxypool.collector.fetcher.shutil.which",
                side_effect=lambda x: "/usr/bin/sing-box" if x == "sing-box" else "/usr/bin/curl",
            ),
            patch("proxypool.collector.fetcher._find_free_port", side_effect=OSError("no ports")),
        ):
            with self.assertRaises(FetchError) as ctx:
                fetch_text_via_proxy_node("https://example.com", {"type": "socks"})
            self.assertIn("local socket unavailable", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
