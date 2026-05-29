"""Tests for proxypool.gateway.runtime to improve coverage."""

from __future__ import annotations

import asyncio
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from proxypool.gateway.config import HttpGatewayConfig
from proxypool.gateway.forward_proxy import ForwardProxyGateway
from proxypool.gateway.runtime import (
    ForwardProxyGatewayRuntime,
    ForwardProxyGatewayRuntimeManager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> HttpGatewayConfig:
    defaults = dict(
        enabled=True,
        listen_host="127.0.0.1",
        listen_port=18899,
        endpoint_id=1,
        default_pool_id=10,
        http_session_header_names=["X-ProxyPool-Session"],
    )
    defaults.update(overrides)
    return HttpGatewayConfig(**defaults)


def _make_gateway(config=None) -> ForwardProxyGateway:
    return ForwardProxyGateway(
        storage=MagicMock(),
        pool_service=MagicMock(),
        chain_service=MagicMock(),
        chain_instance_manager=MagicMock(),
        config=config or _make_config(),
    )


def _make_runtime(config=None) -> ForwardProxyGatewayRuntime:
    return ForwardProxyGatewayRuntime(_make_gateway(config))


# ===========================================================================
# ForwardProxyGatewayRuntime
# ===========================================================================


class TestRuntimeInit:
    def test_init_sets_defaults(self) -> None:
        gw = _make_gateway()
        rt = ForwardProxyGatewayRuntime(gw)
        assert rt.gateway is gw
        assert rt.server is None
        assert rt.last_error == ""


class TestRuntimeStatus:
    def test_status_not_running(self) -> None:
        rt = _make_runtime()
        s = rt.status()
        assert s["running"] is False
        assert s["last_error"] == ""


class TestRuntimeStop:
    @pytest.mark.asyncio
    async def test_stop_when_no_server(self) -> None:
        rt = _make_runtime()
        rt.server = None
        await rt.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_stop_closes_server(self) -> None:
        rt = _make_runtime()
        mock_server = AsyncMock()
        mock_server.sockets = []
        rt.server = mock_server
        await rt.stop()
        mock_server.close.assert_called_once()
        mock_server.wait_closed.assert_awaited_once()
        assert rt.server is None


class TestRuntimeStart:
    @pytest.mark.asyncio
    async def test_start_creates_server(self) -> None:
        rt = _make_runtime()
        mock_server = AsyncMock()
        mock_server.sockets = []
        with patch("asyncio.start_server", new_callable=AsyncMock, return_value=mock_server):
            await rt.start()
        assert rt.server is mock_server
        assert rt.last_error == ""

    @pytest.mark.asyncio
    async def test_start_records_error_and_raises(self) -> None:
        rt = _make_runtime()
        with patch("asyncio.start_server", new_callable=AsyncMock, side_effect=OSError("bind")):
            with pytest.raises(OSError, match="bind"):
                await rt.start()
        assert rt.server is None
        assert "bind" in rt.last_error

    @pytest.mark.asyncio
    async def test_start_reuses_matching_socket(self) -> None:
        """Lines 26-29: server already running with matching host:port -> early return."""
        rt = _make_runtime()
        mock_server = MagicMock()
        fake_sock = MagicMock(spec=socket.socket)
        fake_sock.getsockname.return_value = ("127.0.0.1", 18899)
        mock_server.sockets = [fake_sock]
        rt.server = mock_server
        await rt.start()
        # server should remain the same (no restart)
        assert rt.server is mock_server

    @pytest.mark.asyncio
    async def test_start_replaces_non_matching_socket(self) -> None:
        """Lines 26-29 + 29: server exists but socket does not match -> stop then start."""
        rt = _make_runtime()
        # existing server with wrong port
        old_server = AsyncMock()
        fake_sock = MagicMock(spec=socket.socket)
        fake_sock.getsockname.return_value = ("127.0.0.1", 9999)
        old_server.sockets = [fake_sock]
        rt.server = old_server

        new_server = AsyncMock()
        new_server.sockets = []
        with patch("asyncio.start_server", new_callable=AsyncMock, return_value=new_server):
            await rt.start()
        old_server.close.assert_called_once()
        assert rt.server is new_server

    @pytest.mark.asyncio
    async def test_start_stops_when_server_has_no_sockets(self) -> None:
        """Lines 26-29: sockets list is empty -> stop then re-start."""
        rt = _make_runtime()
        old_server = AsyncMock()
        old_server.sockets = []
        rt.server = old_server

        new_server = AsyncMock()
        new_server.sockets = []
        with patch("asyncio.start_server", new_callable=AsyncMock, return_value=new_server):
            await rt.start()
        old_server.close.assert_called_once()
        assert rt.server is new_server


class TestMatchesSocket:
    def test_matches_true(self) -> None:
        rt = _make_runtime()
        fake_sock = MagicMock(spec=socket.socket)
        fake_sock.getsockname.return_value = ("127.0.0.1", 18899)
        assert rt._matches_socket(fake_sock) is True

    def test_matches_false_wrong_port(self) -> None:
        rt = _make_runtime()
        fake_sock = MagicMock(spec=socket.socket)
        fake_sock.getsockname.return_value = ("127.0.0.1", 12345)
        assert rt._matches_socket(fake_sock) is False

    def test_matches_false_wrong_host(self) -> None:
        rt = _make_runtime()
        fake_sock = MagicMock(spec=socket.socket)
        fake_sock.getsockname.return_value = ("0.0.0.0", 18899)
        assert rt._matches_socket(fake_sock) is False


class TestSplitHostPort:
    def test_empty_target(self) -> None:
        rt = _make_runtime()
        assert rt._split_host_port("") == ("", 0)
        assert rt._split_host_port(None) == ("", 0)

    def test_ipv6_bracketed(self) -> None:
        rt = _make_runtime()
        host, port = rt._split_host_port("[::1]:8080")
        assert host == "::1"
        assert port == 8080

    def test_ipv6_no_port(self) -> None:
        rt = _make_runtime()
        host, port = rt._split_host_port("[::1]")
        assert host == "::1"
        assert port == 443  # default

    def test_host_only_defaults_to_443(self) -> None:
        rt = _make_runtime()
        host, port = rt._split_host_port("example.com")
        assert host == "example.com"
        assert port == 443

    def test_host_port(self) -> None:
        rt = _make_runtime()
        host, port = rt._split_host_port("example.com:80")
        assert host == "example.com"
        assert port == 80

    def test_bad_port_falls_back_to_443(self) -> None:
        rt = _make_runtime()
        host, port = rt._split_host_port("example.com:notanumber")
        assert host == "example.com"
        assert port == 443


class TestConnectPreflightUrl:
    def test_empty_host(self) -> None:
        rt = _make_runtime()
        result = rt._connect_preflight_url("")
        # Empty host returns a URL with empty host
        assert isinstance(result, str)

    def test_port_443(self) -> None:
        rt = _make_runtime()
        url = rt._connect_preflight_url("example.com:443")
        assert url == "https://example.com/"

    def test_port_80(self) -> None:
        rt = _make_runtime()
        url = rt._connect_preflight_url("example.com:80")
        assert url == "http://example.com/"

    def test_other_port_returns_empty(self) -> None:
        rt = _make_runtime()
        url = rt._connect_preflight_url("example.com:9999")
        assert url == ""

    def test_no_port_defaults_443(self) -> None:
        rt = _make_runtime()
        url = rt._connect_preflight_url("example.com")
        assert url == "https://example.com/"


class TestSplitHeadersAndBody:
    def test_splits_correctly(self) -> None:
        rt = _make_runtime()
        data = b"GET / HTTP/1.1\r\nHost: x\r\n\r\nbody"
        header, body = rt._split_headers_and_body(data)
        assert header == b"GET / HTTP/1.1\r\nHost: x"
        assert body == b"body"

    def test_no_body(self) -> None:
        rt = _make_runtime()
        data = b"GET / HTTP/1.1\r\nHost: x\r\n\r\n"
        header, body = rt._split_headers_and_body(data)
        assert header == b"GET / HTTP/1.1\r\nHost: x"
        assert body == b""


class TestParseRequest:
    def test_valid_request(self) -> None:
        rt = _make_runtime()
        block = b"GET /path HTTP/1.1\r\nHost: example.com\r\nX-Custom: val"
        line, headers = rt._parse_request(block)
        assert line == "GET /path HTTP/1.1"
        assert headers["host"] == "example.com"
        assert headers["x-custom"] == "val"

    def test_empty_block_raises(self) -> None:
        rt = _make_runtime()
        with pytest.raises(RuntimeError, match="invalid request line"):
            rt._parse_request(b"")

    def test_line_without_colon_skipped(self) -> None:
        rt = _make_runtime()
        block = b"GET / HTTP/1.1\r\nbadline\r\nHost: x"
        line, headers = rt._parse_request(block)
        assert "host" in headers


class TestFilterForwardHeaders:
    def test_strips_hop_by_hop(self) -> None:
        rt = _make_runtime()
        headers = {
            "host": "x",
            "proxy-connection": "keep-alive",
            "connection": "keep-alive",
            "keep-alive": "timeout=5",
            "accept": "*/*",
        }
        result = rt._filter_forward_headers(headers)
        assert "host" in result
        assert "accept" in result
        assert "proxy-connection" not in result
        assert "connection" not in result
        assert "keep-alive" not in result

    def test_strips_session_header(self) -> None:
        rt = _make_runtime()
        headers = {"x-proxypool-session": "abc", "host": "x"}
        result = rt._filter_forward_headers(headers)
        assert "x-proxypool-session" not in result
        assert "host" in result


class TestBuildRequestBytes:
    def test_builds_correctly(self) -> None:
        rt = _make_runtime()
        result = rt._build_request_bytes("GET", "/path", {"host": "x", "accept": "*/*"})
        text = result.decode("latin-1")
        assert text.startswith("GET /path HTTP/1.1\r\n")
        assert "host: x\r\n" in text
        assert text.endswith("\r\n\r\n")


class TestContentLength:
    def test_valid(self) -> None:
        rt = _make_runtime()
        assert rt._content_length({"content-length": "42"}) == 42

    def test_missing(self) -> None:
        rt = _make_runtime()
        assert rt._content_length({}) == 0

    def test_non_numeric_returns_zero(self) -> None:
        rt = _make_runtime()
        assert rt._content_length({"content-length": "abc"}) == 0

    def test_empty_string_returns_zero(self) -> None:
        rt = _make_runtime()
        assert rt._content_length({"content-length": ""}) == 0


class TestWriteError:
    @pytest.mark.asyncio
    async def test_writes_502(self) -> None:
        rt = _make_runtime()
        writer = AsyncMock()
        writer.is_closing.return_value = False
        await rt._write_error(writer, RuntimeError("boom"))
        writer.write.assert_called_once()
        written = writer.write.call_args[0][0]
        assert b"502" in written
        assert b"boom" in written

    @pytest.mark.asyncio
    async def test_empty_exception_message_uses_fallback(self) -> None:
        rt = _make_runtime()
        writer = AsyncMock()
        writer.is_closing.return_value = False
        await rt._write_error(writer, RuntimeError(""))
        written = writer.write.call_args[0][0]
        assert b"bad gateway" in written


class TestReadUntilHeaders:
    @pytest.mark.asyncio
    async def test_reads_until_double_crlf(self) -> None:
        rt = _make_runtime()
        reader = AsyncMock()
        reader.read = AsyncMock(side_effect=[
            b"GET / HTTP/1.1\r\n",
            b"Host: x\r\n\r\n",
        ])
        result = await rt._read_until_headers(reader)
        assert b"\r\n\r\n" in result

    @pytest.mark.asyncio
    async def test_empty_returns_early(self) -> None:
        rt = _make_runtime()
        reader = AsyncMock()
        reader.read = AsyncMock(return_value=b"")
        result = await rt._read_until_headers(reader)
        assert result == b""

    @pytest.mark.asyncio
    async def test_header_too_large_raises(self) -> None:
        rt = _make_runtime()
        reader = AsyncMock()
        huge = b"X" * (1024 * 1024 + 1)
        reader.read = AsyncMock(return_value=huge)
        with pytest.raises(RuntimeError, match="header too large"):
            await rt._read_until_headers(reader)


class TestHandleClient:
    @pytest.mark.asyncio
    async def test_empty_head_returns_early(self) -> None:
        """Line 65-66: head is empty -> return without processing."""
        rt = _make_runtime()
        reader = AsyncMock()
        reader.read = AsyncMock(return_value=b"")
        writer = AsyncMock()
        writer.is_closing = MagicMock(return_value=False)

        await rt._handle_client(reader, writer)
        # finally block runs: connect_registry.drop + writer.close
        writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_method_handled(self) -> None:
        """Lines 70-74: CONNECT request."""
        rt = _make_runtime()
        connect_request = b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n"
        reader = AsyncMock()
        reader.read = AsyncMock(return_value=connect_request)
        writer = AsyncMock()
        writer.is_closing.return_value = False

        # Mock the connect handling to avoid network calls
        with patch.object(rt, "_handle_connect", new_callable=AsyncMock) as mock_connect:
            await rt._handle_client(reader, writer)
        mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_request_method_handled(self) -> None:
        """Line 75: non-CONNECT HTTP request."""
        rt = _make_runtime()
        http_request = b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n"
        reader = AsyncMock()
        reader.read = AsyncMock(return_value=http_request)
        writer = AsyncMock()
        writer.is_closing.return_value = False

        with patch.object(rt, "_handle_http_request", new_callable=AsyncMock) as mock_http:
            await rt._handle_client(reader, writer)
        mock_http.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_writes_error(self) -> None:
        """Lines 76-77: exception path."""
        rt = _make_runtime()
        reader = AsyncMock()
        reader.read = AsyncMock(side_effect=RuntimeError("bad"))
        writer = AsyncMock()
        writer.is_closing.return_value = False

        with patch.object(rt, "_write_error", new_callable=AsyncMock) as mock_err:
            await rt._handle_client(reader, writer)
        mock_err.assert_called_once()

    @pytest.mark.asyncio
    async def test_writer_closing_skips_close(self) -> None:
        """Line 80-81: writer already closing."""
        rt = _make_runtime()
        reader = AsyncMock()
        reader.read = AsyncMock(return_value=b"")
        writer = AsyncMock()
        writer.is_closing.return_value = True

        await rt._handle_client(reader, writer)
        writer.close.assert_not_called()


class TestHandleHttpRequest:
    @pytest.mark.asyncio
    async def test_relative_target_raises(self) -> None:
        """Line 96: target without scheme/netloc."""
        rt = _make_runtime()
        reader = AsyncMock()
        writer = AsyncMock()
        with pytest.raises(RuntimeError, match="absolute-form"):
            await rt._handle_http_request(
                "GET", "/relative/path", {}, b"", reader, writer
            )

    @pytest.mark.asyncio
    async def test_query_string_in_path(self) -> None:
        """Line 112: path with query string."""
        rt = _make_runtime()
        route = {
            "instance": {"listen": "127.0.0.1", "port": 19999},
        }
        rt.gateway.resolve_route_for_http = MagicMock(return_value=route)
        rt.gateway.config = _make_config(http_session_header_names=[])

        # Mock upstream connection
        upstream_reader = AsyncMock()
        upstream_reader.read = AsyncMock(return_value=b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        upstream_writer = AsyncMock()
        upstream_writer.is_closing.return_value = False

        with patch("asyncio.open_connection", new_callable=AsyncMock, return_value=(upstream_reader, upstream_writer)):
            with patch.object(rt, "_pump_stream", new_callable=AsyncMock):
                await rt._handle_http_request(
                    "GET",
                    "http://example.com/path?key=val",
                    {"host": "example.com"},
                    b"",
                    AsyncMock(),
                    AsyncMock(),
                )
        # Verify the request was built with the query string
        written = upstream_writer.write.call_args_list[0][0][0]
        assert b"path?key=val" in written

    @pytest.mark.asyncio
    async def test_reads_body(self) -> None:
        """Line 106: content-length > len(body_prefix)."""
        rt = _make_runtime()
        route = {
            "instance": {"listen": "127.0.0.1", "port": 19999},
        }
        rt.gateway.resolve_route_for_http = MagicMock(return_value=route)
        rt.gateway.config = _make_config(http_session_header_names=[])

        client_reader = AsyncMock()
        client_reader.readexactly = AsyncMock(return_value=b"extra body data")
        client_writer = AsyncMock()
        client_writer.is_closing.return_value = False

        upstream_reader = AsyncMock()
        upstream_reader.read = AsyncMock(return_value=b"")
        upstream_writer = AsyncMock()
        upstream_writer.is_closing.return_value = False

        with patch("asyncio.open_connection", new_callable=AsyncMock, return_value=(upstream_reader, upstream_writer)):
            with patch.object(rt, "_pump_stream", new_callable=AsyncMock):
                await rt._handle_http_request(
                    "POST",
                    "http://example.com/submit",
                    {"host": "example.com", "content-length": "10"},
                    b"short",  # body_prefix shorter than content-length
                    client_reader,
                    client_writer,
                )
        client_reader.readexactly.assert_awaited_once_with(5)  # 10 - 5 = 5


class TestHandleConnect:
    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """Full CONNECT flow: upstream returns 200."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}

        with patch.object(rt, "_resolve_connect_route_with_preflight", new_callable=AsyncMock, return_value=route):
            upstream_reader = AsyncMock()
            upstream_reader.read = AsyncMock(side_effect=[
                b"HTTP/1.1 200 Connection Established\r\n\r\n",
                b"",
                b"",
            ])
            upstream_writer = AsyncMock()
            upstream_writer.is_closing.return_value = False

            with patch("asyncio.open_connection", new_callable=AsyncMock, return_value=(upstream_reader, upstream_writer)):
                client_reader = AsyncMock()
                client_reader.read = AsyncMock(return_value=b"")
                client_writer = AsyncMock()
                client_writer.is_closing.return_value = False

                await rt._handle_connect(
                    "example.com:443", {}, b"", client_reader, client_writer, "cid-1"
                )
        # Client should receive the 200 response
        client_writer.write.assert_called()
        first_call = client_writer.write.call_args_list[0][0][0]
        assert b"200" in first_call

    @pytest.mark.asyncio
    async def test_connect_upstream_failure(self) -> None:
        """Line 139: upstream CONNECT returns non-200."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}

        with patch.object(rt, "_resolve_connect_route_with_preflight", new_callable=AsyncMock, return_value=route):
            upstream_reader = AsyncMock()
            upstream_reader.read = AsyncMock(side_effect=[
                b"HTTP/1.1 502 Bad Gateway\r\n\r\n",
                b"",
            ])
            upstream_writer = AsyncMock()
            upstream_writer.is_closing.return_value = False

            with patch("asyncio.open_connection", new_callable=AsyncMock, return_value=(upstream_reader, upstream_writer)):
                client_writer = AsyncMock()
                client_writer.is_closing.return_value = False

                # RuntimeError("upstream CONNECT failed") propagates from _handle_connect
                with pytest.raises(RuntimeError, match="upstream CONNECT failed"):
                    await rt._handle_connect(
                        "example.com:443", {}, b"", AsyncMock(), client_writer, "cid-2"
                    )

    @pytest.mark.asyncio
    async def test_connect_with_upstream_prefix(self) -> None:
        """Line 142: upstream_prefix is non-empty."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}

        with patch.object(rt, "_resolve_connect_route_with_preflight", new_callable=AsyncMock, return_value=route):
            upstream_reader = AsyncMock()
            upstream_reader.read = AsyncMock(side_effect=[
                b"HTTP/1.1 200 Connection Established\r\n\r\nextra-data",
                b"",
                b"",
            ])
            upstream_writer = AsyncMock()
            upstream_writer.is_closing.return_value = False

            with patch("asyncio.open_connection", new_callable=AsyncMock, return_value=(upstream_reader, upstream_writer)):
                client_reader = AsyncMock()
                client_reader.read = AsyncMock(return_value=b"")
                client_writer = AsyncMock()
                client_writer.is_closing.return_value = False

                await rt._handle_connect(
                    "example.com:443", {}, b"", client_reader, client_writer, "cid-3"
                )
        # Should have written the 200 and the prefix
        calls = client_writer.write.call_args_list
        assert len(calls) >= 2
        assert b"extra-data" in calls[1][0][0]

    @pytest.mark.asyncio
    async def test_connect_with_body_prefix(self) -> None:
        """Lines 144-146: body_prefix is non-empty."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}

        with patch.object(rt, "_resolve_connect_route_with_preflight", new_callable=AsyncMock, return_value=route):
            upstream_reader = AsyncMock()
            upstream_reader.read = AsyncMock(side_effect=[
                b"HTTP/1.1 200 Connection Established\r\n\r\n",
                b"",
                b"",
            ])
            upstream_writer = AsyncMock()
            upstream_writer.is_closing.return_value = False

            with patch("asyncio.open_connection", new_callable=AsyncMock, return_value=(upstream_reader, upstream_writer)):
                client_reader = AsyncMock()
                client_reader.read = AsyncMock(return_value=b"")
                client_writer = AsyncMock()
                client_writer.is_closing.return_value = False

                await rt._handle_connect(
                    "example.com:443", {}, b"early-data", client_reader, client_writer, "cid-4"
                )
        # Verify body_prefix was written to upstream (second write, after CONNECT request)
        all_written = [c[0][0] for c in upstream_writer.write.call_args_list]
        assert any(b"early-data" in w for w in all_written)


class TestResolveConnectRouteWithPreflight:
    @pytest.mark.asyncio
    async def test_no_preflight_url_returns_route_immediately(self) -> None:
        """Line 182-183: empty preflight_url -> return route."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}
        rt.gateway.resolve_route_for_connect = MagicMock(return_value=route)
        with patch.object(rt, "_connect_preflight_url", return_value=""):
            result = await rt._resolve_connect_route_with_preflight(
                "example.com:9999", {}, "cid"
            )
        assert result is route

    @pytest.mark.asyncio
    async def test_preflight_success(self) -> None:
        """Lines 183-185: preflight succeeds -> report success and return."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}
        rt.gateway.resolve_route_for_connect = MagicMock(return_value=route)
        rt.gateway.report_route_success = MagicMock()
        with patch.object(rt, "_connect_preflight_url", return_value="https://example.com/"):
            with patch.object(rt, "_preflight_instance_http_request", new_callable=AsyncMock):
                result = await rt._resolve_connect_route_with_preflight(
                    "example.com:443", {}, "cid"
                )
        assert result is route
        rt.gateway.report_route_success.assert_called_once_with(route)

    @pytest.mark.asyncio
    async def test_preflight_all_fail_raises(self) -> None:
        """Lines 189-193: all attempts fail -> RuntimeError."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}
        rt.gateway.resolve_route_for_connect = MagicMock(return_value=route)
        rt.gateway.report_route_failure = MagicMock()
        with patch.object(rt, "_connect_preflight_url", return_value="https://example.com/"):
            with patch.object(
                rt, "_preflight_instance_http_request",
                new_callable=AsyncMock,
                side_effect=RuntimeError("timeout"),
            ):
                with pytest.raises(RuntimeError, match="no healthy CONNECT route"):
                    await rt._resolve_connect_route_with_preflight(
                        "example.com:443", {}, "cid"
                    )


class TestPreflightInstanceHttpRequest:
    @pytest.mark.asyncio
    async def test_preflight_makes_httpx_request(self) -> None:
        """Lines 201-208: _preflight_instance_http_request."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("proxypool.gateway.runtime.httpx.Proxy") as mock_proxy, \
             patch("proxypool.gateway.runtime.httpx.Timeout") as mock_timeout, \
             patch("proxypool.gateway.runtime.httpx.AsyncClient", return_value=mock_client):
            await rt._preflight_instance_http_request(
                route, "https://example.com/", {"X-Custom": "val"}
            )
        mock_proxy.assert_called_once_with("http://127.0.0.1:19999")
        mock_timeout.assert_called_once()
        mock_client.get.assert_awaited_once_with(
            "https://example.com/",
            headers={
                "Accept": "*/*",
                "User-Agent": "proxypool-connect-preflight/1.0",
            },
        )


class TestPumpStream:
    @pytest.mark.asyncio
    async def test_pumps_data(self) -> None:
        rt = _make_runtime()
        reader = AsyncMock()
        reader.read = AsyncMock(side_effect=[b"chunk1", b"chunk2", b""])
        writer = AsyncMock()
        await rt._pump_stream(reader, writer)
        assert writer.write.call_count == 2
        writer.write.assert_any_call(b"chunk1")
        writer.write.assert_any_call(b"chunk2")


# ===========================================================================
# ForwardProxyGatewayRuntimeManager
# ===========================================================================


class TestManagerInit:
    def test_init(self) -> None:
        storage = MagicMock()
        pool_service = MagicMock()
        chain_service = MagicMock()
        chain_instance_manager = MagicMock()
        config_service = MagicMock()
        legacy_gw = _make_gateway()

        mgr = ForwardProxyGatewayRuntimeManager(
            storage, pool_service, chain_service,
            chain_instance_manager, config_service, legacy_gw,
        )
        assert mgr.storage is storage
        assert mgr.pool_service is pool_service
        assert mgr.chain_service is chain_service
        assert mgr.chain_instance_manager is chain_instance_manager
        assert mgr.config_service is config_service
        assert mgr.legacy_gateway is legacy_gw
        assert isinstance(mgr.legacy_runtime, ForwardProxyGatewayRuntime)
        assert mgr.endpoint_runtimes == {}
        assert mgr.last_error == ""


class TestManagerEndpointEntryPoolId:
    def test_no_hops(self) -> None:
        mgr = self._make_manager()
        assert mgr._endpoint_entry_pool_id({}) == 0
        assert mgr._endpoint_entry_pool_id({"hops": []}) == 0

    def test_first_hop_pool_id(self) -> None:
        mgr = self._make_manager()
        ep = {"hops": [{"pool_id": 42}, {"pool_id": 99}]}
        assert mgr._endpoint_entry_pool_id(ep) == 42

    def test_hop_missing_pool_id(self) -> None:
        mgr = self._make_manager()
        ep = {"hops": [{}]}
        assert mgr._endpoint_entry_pool_id(ep) == 0

    @staticmethod
    def _make_manager() -> ForwardProxyGatewayRuntimeManager:
        return ForwardProxyGatewayRuntimeManager(
            MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), _make_gateway(),
        )


class TestManagerConfigFromEndpoint:
    def test_config_from_endpoint(self) -> None:
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        endpoint = {
            "id": 5,
            "listen_host": "0.0.0.0",
            "listen_port": 8080,
            "hops": [{"pool_id": 10}],
            "sticky_ttl_sec": 7200,
            "session_missing_action": "REJECT",
            "session_header_names": ["X-Session"],
            "session_query_param_names": ["sid"],
            "connect_session_header_names": ["X-Conn"],
        }
        cfg = mgr._config_from_endpoint(endpoint)
        assert cfg.enabled is True
        assert cfg.listen_host == "0.0.0.0"
        assert cfg.listen_port == 8080
        assert cfg.endpoint_id == 5
        assert cfg.default_pool_id == 10
        assert cfg.sticky_ttl_sec == 7200
        assert cfg.session_missing_action == "REJECT"
        assert cfg.http_session_header_names == ["X-Session"]
        assert cfg.http_session_query_names == ["sid"]
        assert cfg.connect_session_header_names == ["X-Conn"]

    def test_config_from_endpoint_defaults(self) -> None:
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        endpoint = {"hops": [{"pool_id": 1}]}
        cfg = mgr._config_from_endpoint(endpoint)
        assert cfg.listen_host == "127.0.0.1"
        assert cfg.listen_port == 8899


class TestManagerStop:
    @pytest.mark.asyncio
    async def test_stop(self) -> None:
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        mgr.legacy_runtime = AsyncMock()
        ep_runtime = AsyncMock()
        mgr.endpoint_runtimes = {1: ep_runtime, 2: AsyncMock()}
        await mgr.stop()
        mgr.legacy_runtime.stop.assert_awaited_once()
        assert len(mgr.endpoint_runtimes) == 0
        assert ep_runtime.stop.await_count >= 1


class TestManagerStatus:
    def test_status_no_endpoints(self) -> None:
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[])
        mgr.legacy_runtime.server = None
        mgr.legacy_runtime.last_error = ""
        s = mgr.status()
        assert s["running"] is False
        assert s["items"] == []
        assert "legacy" in s

    def test_status_with_endpoint(self) -> None:
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        ep_rt = MagicMock()
        ep_rt.server = None
        ep_rt.last_error = ""
        ep_rt.gateway.config = _make_config(listen_host="0.0.0.0", listen_port=9090)
        mgr.endpoint_runtimes = {1: ep_rt}
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[
            {"id": 1, "name": "ep1"},
        ])
        mgr.legacy_runtime.server = None
        mgr.legacy_runtime.last_error = ""
        s = mgr.status()
        assert len(s["items"]) == 1
        item = s["items"][0]
        assert item["endpoint_id"] == 1
        assert item["name"] == "ep1"
        assert item["listen_host"] == "0.0.0.0"
        assert item["listen_port"] == 9090
        assert item["running"] is False

    def test_status_running_when_legacy_running(self) -> None:
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[])
        mgr.legacy_runtime.server = MagicMock()
        mgr.legacy_runtime.last_error = ""
        s = mgr.status()
        assert s["running"] is True


class TestManagerSync:
    @pytest.mark.asyncio
    async def test_sync_disabled_stops_all(self) -> None:
        """Line 352-353: config disabled -> stop everything."""
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        mgr.config_service.get_config = MagicMock(return_value=_make_config(enabled=False))
        mgr.legacy_runtime = AsyncMock()
        mgr.endpoint_runtimes = {1: AsyncMock()}
        await mgr.sync()
        mgr.legacy_runtime.stop.assert_awaited()
        assert len(mgr.endpoint_runtimes) == 0

    @pytest.mark.asyncio
    async def test_sync_creates_endpoint_runtimes(self) -> None:
        """Lines 359-376: enabled endpoint creates runtime."""
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        cfg = _make_config(enabled=True, endpoint_id=0, default_pool_id=0)
        mgr.config_service.get_config = MagicMock(return_value=cfg)
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[
            {
                "id": 1,
                "enabled": True,
                "listen_host": "0.0.0.0",
                "listen_port": 8080,
                "hops": [{"pool_id": 10}],
            },
        ])
        mgr.legacy_runtime = AsyncMock()
        mock_new_runtime = AsyncMock()
        with patch("proxypool.gateway.runtime.ForwardProxyGatewayRuntime", return_value=mock_new_runtime):
            await mgr.sync()
        assert 1 in mgr.endpoint_runtimes
        mock_new_runtime.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_skips_disabled_endpoint(self) -> None:
        """Line 359: endpoint not enabled."""
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        cfg = _make_config(enabled=True, endpoint_id=0, default_pool_id=0)
        mgr.config_service.get_config = MagicMock(return_value=cfg)
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[
            {"id": 1, "enabled": False, "hops": [{"pool_id": 10}]},
        ])
        mgr.legacy_runtime = AsyncMock()
        await mgr.sync()
        assert len(mgr.endpoint_runtimes) == 0

    @pytest.mark.asyncio
    async def test_sync_skips_endpoint_no_pool(self) -> None:
        """Line 363: entry_pool_id <= 0."""
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        cfg = _make_config(enabled=True, endpoint_id=0, default_pool_id=0)
        mgr.config_service.get_config = MagicMock(return_value=cfg)
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[
            {"id": 1, "enabled": True, "hops": []},
        ])
        mgr.legacy_runtime = AsyncMock()
        await mgr.sync()
        assert len(mgr.endpoint_runtimes) == 0

    @pytest.mark.asyncio
    async def test_sync_endpoint_start_error_recorded(self) -> None:
        """Lines 379-381: endpoint runtime start fails."""
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        cfg = _make_config(enabled=True, endpoint_id=0, default_pool_id=0)
        mgr.config_service.get_config = MagicMock(return_value=cfg)
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[
            {
                "id": 1,
                "enabled": True,
                "listen_host": "0.0.0.0",
                "listen_port": 8080,
                "hops": [{"pool_id": 10}],
            },
        ])
        mgr.legacy_runtime = AsyncMock()
        mock_new_runtime = AsyncMock()
        mock_new_runtime.start = AsyncMock(side_effect=OSError("bind"))
        with patch("proxypool.gateway.runtime.ForwardProxyGatewayRuntime", return_value=mock_new_runtime):
            await mgr.sync()
        assert "endpoint#1" in mgr.last_error

    @pytest.mark.asyncio
    async def test_sync_removes_stale_endpoints(self) -> None:
        """Lines 383-390: stale endpoint runtimes are stopped and removed."""
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        cfg = _make_config(enabled=True, endpoint_id=0, default_pool_id=0)
        mgr.config_service.get_config = MagicMock(return_value=cfg)
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[])
        mgr.legacy_runtime = AsyncMock()
        stale_rt = AsyncMock()
        mgr.endpoint_runtimes = {99: stale_rt}
        await mgr.sync()
        stale_rt.stop.assert_awaited_once()
        assert 99 not in mgr.endpoint_runtimes

    @pytest.mark.asyncio
    async def test_sync_legacy_runtime_when_no_endpoint_id(self) -> None:
        """Lines 392-398: endpoint_id=0, default_pool_id>0 -> use legacy."""
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        cfg = _make_config(enabled=True, endpoint_id=0, default_pool_id=10)
        mgr.config_service.get_config = MagicMock(return_value=cfg)
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[])
        mgr.legacy_runtime = AsyncMock()
        await mgr.sync()
        mgr.legacy_runtime.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_legacy_error_recorded(self) -> None:
        """Lines 398-400: legacy start fails."""
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        cfg = _make_config(enabled=True, endpoint_id=0, default_pool_id=10)
        mgr.config_service.get_config = MagicMock(return_value=cfg)
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[])
        mgr.legacy_runtime = AsyncMock()
        mgr.legacy_runtime.start = AsyncMock(side_effect=OSError("bind"))
        await mgr.sync()
        assert "bind" in mgr.last_error

    @pytest.mark.asyncio
    async def test_sync_stops_legacy_when_endpoint_id_set(self) -> None:
        """Lines 401-402: endpoint_id > 0 -> stop legacy."""
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        cfg = _make_config(enabled=True, endpoint_id=5, default_pool_id=10)
        mgr.config_service.get_config = MagicMock(return_value=cfg)
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[])
        mgr.legacy_runtime = AsyncMock()
        await mgr.sync()
        mgr.legacy_runtime.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_updates_existing_endpoint_config(self) -> None:
        """Line 376: existing runtime gets updated config."""
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        cfg = _make_config(enabled=True, endpoint_id=0, default_pool_id=0)
        mgr.config_service.get_config = MagicMock(return_value=cfg)
        ep = {
            "id": 1,
            "enabled": True,
            "listen_host": "0.0.0.0",
            "listen_port": 8080,
            "hops": [{"pool_id": 10}],
            "sticky_ttl_sec": 7200,
        }
        mgr.storage.list_http_proxy_endpoints = MagicMock(return_value=[ep])
        mgr.legacy_runtime = AsyncMock()
        existing_rt = AsyncMock()
        mgr.endpoint_runtimes = {1: existing_rt}
        # No new ForwardProxyGatewayRuntime created since key exists
        await mgr.sync()
        existing_rt.start.assert_awaited_once()
        # Config should be updated
        assert existing_rt.gateway.config.listen_port == 8080


class TestManagerStart:
    @pytest.mark.asyncio
    async def test_start_calls_sync(self) -> None:
        mgr = TestManagerEndpointEntryPoolId._make_manager()
        mgr.config_service.get_config = MagicMock(return_value=_make_config(enabled=False))
        mgr.legacy_runtime = AsyncMock()
        with patch.object(mgr, "sync", new_callable=AsyncMock) as mock_sync:
            await mgr.start()
        mock_sync.assert_awaited_once()
