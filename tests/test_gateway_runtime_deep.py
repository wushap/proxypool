"""Deep edge-case tests for proxypool.gateway.runtime to push coverage to 100%."""

from __future__ import annotations

import asyncio
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
# Lines 153-154: pipe() inner function reads non-empty data
# ===========================================================================


class TestConnectPipeDataTransfer:
    """Test that the inner pipe() function in _handle_connect forwards data."""

    @pytest.mark.asyncio
    async def test_upstream_data_forwarded_to_client(self) -> None:
        """Lines 153-154: pipe reads non-empty chunk and writes to dst."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}

        with patch.object(
            rt, "_resolve_connect_route_with_preflight",
            new_callable=AsyncMock, return_value=route,
        ):
            # upstream_reader: first read returns headers (consumed by
            # _read_until_headers), second read returns data (consumed by
            # pipe()), third read returns empty to terminate the loop.
            upstream_reader = AsyncMock()
            upstream_reader.read = AsyncMock(side_effect=[
                b"HTTP/1.1 200 Connection Established\r\n\r\n",
                b"tunnel-data",
                b"",
            ])
            upstream_writer = AsyncMock()
            upstream_writer.is_closing.return_value = False

            with patch(
                "asyncio.open_connection",
                new_callable=AsyncMock,
                return_value=(upstream_reader, upstream_writer),
            ):
                # client_reader: pipe(client_reader, upstream_writer) reads
                # empty immediately so that pipe finishes first.
                client_reader = AsyncMock()
                client_reader.read = AsyncMock(return_value=b"")
                client_writer = AsyncMock()
                client_writer.is_closing.return_value = False

                await rt._handle_connect(
                    "example.com:443", {}, b"",
                    client_reader, client_writer, "cid-pipe",
                )

        # client_writer should have received the tunneled data
        all_writes = [c[0][0] for c in client_writer.write.call_args_list]
        assert any(b"tunnel-data" in w for w in all_writes)

    @pytest.mark.asyncio
    async def test_client_data_forwarded_to_upstream(self) -> None:
        """pipe(client_reader, upstream_writer) also exercises lines 153-154."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}

        with patch.object(
            rt, "_resolve_connect_route_with_preflight",
            new_callable=AsyncMock, return_value=route,
        ):
            # upstream_reader: returns headers, then empty (upstream pipe
            # finishes immediately).
            upstream_reader = AsyncMock()
            upstream_reader.read = AsyncMock(side_effect=[
                b"HTTP/1.1 200 Connection Established\r\n\r\n",
                b"",
            ])
            upstream_writer = AsyncMock()
            upstream_writer.is_closing.return_value = False

            with patch(
                "asyncio.open_connection",
                new_callable=AsyncMock,
                return_value=(upstream_reader, upstream_writer),
            ):
                # client_reader: returns data first, then empty.
                client_reader = AsyncMock()
                client_reader.read = AsyncMock(side_effect=[
                    b"client-payload",
                    b"",
                ])
                client_writer = AsyncMock()
                client_writer.is_closing.return_value = False

                await rt._handle_connect(
                    "example.com:443", {}, b"",
                    client_reader, client_writer, "cid-pipe2",
                )

        # upstream_writer should have received client data
        all_writes = [c[0][0] for c in upstream_writer.write.call_args_list]
        assert any(b"client-payload" in w for w in all_writes)


# ===========================================================================
# Line 193: unreachable defensive raise (last_error is None after loop)
# ===========================================================================


class TestResolveConnectRouteDeadBranch:
    """Line 193 is defensive dead code - the loop always either returns
    a route or sets last_error. This test confirms the method raises
    RuntimeError when all attempts fail (line 190-192), which is the
    practical path through the error handling."""
    # NOTE: Line 193 (the else branch where last_error is None) is
    # unreachable by design. Every iteration either returns early or
    # sets last_error, so the `if last_error is not None` check on
    # line 189 is always True when the loop completes. We cannot
    # cover line 193 without modifying production code.

    @pytest.mark.asyncio
    async def test_all_attempts_fail_with_last_error(self) -> None:
        """Verifies line 190-192 path (last_error IS set)."""
        rt = _make_runtime()
        route = {"instance": {"listen": "127.0.0.1", "port": 19999}}
        rt.gateway.resolve_route_for_connect = MagicMock(return_value=route)
        rt.gateway.report_route_failure = MagicMock()
        with patch.object(rt, "_connect_preflight_url", return_value="https://example.com/"):
            with patch.object(
                rt, "_preflight_instance_http_request",
                new_callable=AsyncMock,
                side_effect=RuntimeError("conn refused"),
            ):
                with pytest.raises(RuntimeError, match="no healthy CONNECT route"):
                    await rt._resolve_connect_route_with_preflight(
                        "example.com:443", {}, "cid-dead"
                    )
