from __future__ import annotations

import asyncio
import contextlib
import socket
from urllib.parse import urlsplit

from proxypool.gateway.forward_proxy import ForwardProxyGateway


class ForwardProxyGatewayRuntime:
    def __init__(self, gateway: ForwardProxyGateway) -> None:
        self.gateway = gateway
        self.server: asyncio.base_events.Server | None = None
        self.last_error = ""

    async def start(self) -> None:
        self.last_error = ""
        if self.server is not None:
            sockets = list(self.server.sockets or [])
            if sockets and self._matches_socket(sockets[0]):
                return
            await self.stop()
        try:
            self.server = await asyncio.start_server(
                self._handle_client,
                host=self.gateway.config.listen_host,
                port=int(self.gateway.config.listen_port),
            )
        except Exception as exc:
            self.server = None
            self.last_error = str(exc)
            raise

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    def status(self) -> dict[str, object]:
        return {
            "running": self.server is not None,
            "last_error": self.last_error,
        }

    def _matches_socket(self, sock: socket.socket) -> bool:
        host, port = sock.getsockname()[:2]
        return str(host) == str(self.gateway.config.listen_host) and int(port) == int(self.gateway.config.listen_port)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        connection_id = f"{id(writer)}"
        try:
            head = await self._read_until_headers(reader)
            if not head:
                return
            header_block, body_prefix = self._split_headers_and_body(head)
            request_line, headers = self._parse_request(header_block)
            method, target, _ = request_line.split(" ", 2)
            if method.upper() == "CONNECT":
                await self._handle_connect(target, headers, reader, writer, connection_id)
                return
            await self._handle_http_request(method, target, headers, body_prefix, reader, writer)
        except Exception as exc:
            await self._write_error(writer, exc)
        finally:
            self.gateway.connect_registry.drop(connection_id)
            if not writer.is_closing():
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()

    async def _handle_http_request(
        self,
        method: str,
        target: str,
        headers: dict[str, str],
        body_prefix: bytes,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        parsed = urlsplit(target)
        if not parsed.scheme or not parsed.netloc:
            raise RuntimeError("absolute-form proxy target is required")
        route = self.gateway.resolve_route_for_http(target, headers=headers)
        upstream_reader, upstream_writer = await asyncio.open_connection(
            str(route["instance"]["listen"]),
            int(route["instance"]["port"]),
        )
        try:
            content_length = self._content_length(headers)
            body = body_prefix
            if content_length > len(body):
                body += await reader.readexactly(content_length - len(body))

            forward_headers = self._filter_forward_headers(headers)
            forward_headers["host"] = parsed.netloc
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            upstream_writer.write(self._build_request_bytes(method, path, forward_headers) + body)
            await upstream_writer.drain()
            await self._pump_stream(upstream_reader, writer)
        finally:
            upstream_writer.close()
            with contextlib.suppress(Exception):
                await upstream_writer.wait_closed()

    async def _handle_connect(
        self,
        target: str,
        headers: dict[str, str],
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        connection_id: str,
    ) -> None:
        route = self.gateway.resolve_route_for_connect(target, headers=headers, connection_id=connection_id)
        upstream_reader, upstream_writer = await asyncio.open_connection(
            str(route["instance"]["listen"]),
            int(route["instance"]["port"]),
        )
        try:
            upstream_writer.write(self._build_request_bytes("CONNECT", target, {"host": target}))
            await upstream_writer.drain()
            response_head = await self._read_until_headers(upstream_reader)
            first_line = response_head.split(b"\r\n", 1)[0]
            if b"200" not in first_line:
                raise RuntimeError("upstream CONNECT failed")
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()

            async def pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
                while True:
                    chunk = await src.read(65536)
                    if not chunk:
                        break
                    dst.write(chunk)
                    await dst.drain()
                with contextlib.suppress(Exception):
                    dst.write_eof()

            await asyncio.gather(
                pipe(client_reader, upstream_writer),
                pipe(upstream_reader, client_writer),
            )
        finally:
            upstream_writer.close()
            with contextlib.suppress(Exception):
                await upstream_writer.wait_closed()

    async def _read_until_headers(self, reader: asyncio.StreamReader) -> bytes:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = await reader.read(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 1024 * 1024:
                raise RuntimeError("request header too large")
        return data

    def _split_headers_and_body(self, data: bytes) -> tuple[bytes, bytes]:
        header_block, _, body = data.partition(b"\r\n\r\n")
        return header_block, body

    def _parse_request(self, header_block: bytes) -> tuple[str, dict[str, str]]:
        lines = header_block.decode("latin-1").split("\r\n")
        if not lines or not lines[0]:
            raise RuntimeError("invalid request line")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
        return lines[0], headers

    def _filter_forward_headers(self, headers: dict[str, str]) -> dict[str, str]:
        stripped = {name.lower() for name in self.gateway.config.http_session_header_names}
        hop_by_hop = {"proxy-connection", "connection", "keep-alive"}
        result: dict[str, str] = {}
        for key, value in headers.items():
            if key in stripped or key in hop_by_hop:
                continue
            result[key] = value
        return result

    def _build_request_bytes(self, method: str, target: str, headers: dict[str, str]) -> bytes:
        lines = [f"{method} {target} HTTP/1.1"]
        for key, value in headers.items():
            lines.append(f"{key}: {value}")
        lines.append("")
        lines.append("")
        return "\r\n".join(lines).encode("latin-1")

    def _content_length(self, headers: dict[str, str]) -> int:
        try:
            return int(headers.get("content-length", "0") or 0)
        except Exception:
            return 0

    async def _pump_stream(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()

    async def _write_error(self, writer: asyncio.StreamWriter, exc: Exception) -> None:
        body = str(exc).encode("utf-8") or b"bad gateway"
        writer.write(
            b"HTTP/1.1 502 Bad Gateway\r\n"
            + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("latin-1")
            + body
        )
        await writer.drain()
