from __future__ import annotations

import asyncio
import contextlib
import socket
from urllib.parse import urlsplit

import httpx

from proxypool.gateway.config import HttpGatewayConfig
from proxypool.gateway.forward_proxy import ForwardProxyGateway


class ForwardProxyGatewayRuntime:
    CONNECT_ROUTE_ATTEMPTS = 12
    CONNECT_PREFLIGHT_TIMEOUT_SEC = 8.0

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
        return str(host) == str(self.gateway.config.listen_host) and int(port) == int(
            self.gateway.config.listen_port
        )

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        connection_id = f"{id(writer)}"
        try:
            head = await self._read_until_headers(reader)
            if not head:
                return
            header_block, body_prefix = self._split_headers_and_body(head)
            request_line, headers = self._parse_request(header_block)
            method, target, _ = request_line.split(" ", 2)
            if method.upper() == "CONNECT":
                await self._handle_connect(
                    target, headers, body_prefix, reader, writer, connection_id
                )
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
        body_prefix: bytes,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        connection_id: str,
    ) -> None:
        route = await self._resolve_connect_route_with_preflight(target, headers, connection_id)
        upstream_reader, upstream_writer = await self._open_instance_connection(route)
        try:
            upstream_writer.write(self._build_request_bytes("CONNECT", target, {"host": target}))
            await upstream_writer.drain()
            response_head = await self._read_until_headers(upstream_reader)
            response_header, upstream_prefix = self._split_headers_and_body(response_head)
            first_line = response_header.split(b"\r\n", 1)[0]
            if b"200" not in first_line:
                raise RuntimeError("upstream CONNECT failed")
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            if upstream_prefix:
                client_writer.write(upstream_prefix)
            await client_writer.drain()
            if body_prefix:
                upstream_writer.write(body_prefix)
                await upstream_writer.drain()

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

    async def _resolve_connect_route_with_preflight(
        self,
        target: str,
        headers: dict[str, str],
        connection_id: str,
    ) -> dict:
        attempts = max(1, int(self.CONNECT_ROUTE_ATTEMPTS))
        last_error: Exception | None = None
        for _ in range(attempts):
            route = self.gateway.resolve_route_for_connect(
                target, headers=headers, connection_id=connection_id
            )
            preflight_url = self._connect_preflight_url(target)
            if not preflight_url:
                return route
            try:
                await self._preflight_instance_http_request(route, preflight_url, headers)
                self.gateway.report_route_success(route)
                return route
            except Exception as exc:
                last_error = exc
                self.gateway.report_route_failure(route, str(exc) or exc.__class__.__name__)
        if last_error is not None:
            raise RuntimeError(
                f"no healthy CONNECT route for {target}: {last_error}"
            ) from last_error
        raise RuntimeError(f"no healthy CONNECT route for {target}")

    async def _preflight_instance_http_request(
        self,
        route: dict,
        target_url: str,
        headers: dict[str, str],
    ) -> None:
        del headers
        proxy_url = f"http://{route['instance']['listen']}:{int(route['instance']['port'])}"
        proxy = httpx.Proxy(proxy_url)
        timeout = httpx.Timeout(self.CONNECT_PREFLIGHT_TIMEOUT_SEC)
        async with httpx.AsyncClient(
            proxy=proxy, timeout=timeout, follow_redirects=False, trust_env=False
        ) as client:
            await client.get(
                target_url,
                headers={
                    "Accept": "*/*",
                    "User-Agent": "proxypool-connect-preflight/1.0",
                },
            )

    async def _open_instance_connection(
        self, route: dict
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await asyncio.open_connection(
            str(route["instance"]["listen"]),
            int(route["instance"]["port"]),
        )

    def _connect_preflight_url(self, target: str) -> str:
        host, port = self._split_host_port(target)
        if not host:
            return ""
        if port == 443:
            return f"https://{host}/"
        if port == 80:
            return f"http://{host}/"
        return ""

    def _split_host_port(self, target: str) -> tuple[str, int]:
        text = str(target or "").strip()
        if not text:
            return "", 0
        if text.startswith("[") and "]" in text:
            host, _, port_text = text[1:].partition("]")
            port_text = port_text[1:] if port_text.startswith(":") else ""
        else:
            host, _, port_text = text.rpartition(":")
            if not host:
                host = text
                port_text = ""
        try:
            port = int(port_text or "443")
        except Exception:
            port = 443
        return host.strip("[]"), port

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

    async def _pump_stream(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
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


class ForwardProxyGatewayRuntimeManager:
    def __init__(
        self,
        storage,
        pool_service,
        chain_service,
        chain_instance_manager,
        config_service,
        legacy_gateway: ForwardProxyGateway,
    ) -> None:
        self.storage = storage
        self.pool_service = pool_service
        self.chain_service = chain_service
        self.chain_instance_manager = chain_instance_manager
        self.config_service = config_service
        self.legacy_gateway = legacy_gateway
        self.legacy_runtime = ForwardProxyGatewayRuntime(legacy_gateway)
        self.endpoint_runtimes: dict[int, ForwardProxyGatewayRuntime] = {}
        self.last_error = ""

    async def start(self) -> None:
        await self.sync()

    async def sync(self) -> None:
        self.last_error = ""
        config = self.config_service.get_config()
        self.legacy_gateway.config = config

        if not bool(config.enabled):
            await self.stop()
            return

        errors: list[str] = []
        active_endpoint_ids: set[int] = set()
        for endpoint in self.storage.list_http_proxy_endpoints():
            if endpoint.get("enabled") is not True:
                continue
            endpoint_id = int(endpoint.get("id") or 0)
            entry_pool_id = self._endpoint_entry_pool_id(endpoint)
            if endpoint_id <= 0 or entry_pool_id <= 0:
                continue
            active_endpoint_ids.add(endpoint_id)
            runtime = self.endpoint_runtimes.get(endpoint_id)
            if runtime is None:
                gateway = ForwardProxyGateway(
                    storage=self.storage,
                    pool_service=self.pool_service,
                    chain_service=self.chain_service,
                    chain_instance_manager=self.chain_instance_manager,
                    config=self._config_from_endpoint(endpoint),
                )
                runtime = ForwardProxyGatewayRuntime(gateway)
                self.endpoint_runtimes[endpoint_id] = runtime
            runtime.gateway.config = self._config_from_endpoint(endpoint)
            try:
                await runtime.start()
            except Exception as exc:
                runtime.last_error = str(exc)
                errors.append(f"endpoint#{endpoint_id}: {exc}")

        stale_ids = [
            endpoint_id
            for endpoint_id in self.endpoint_runtimes
            if endpoint_id not in active_endpoint_ids
        ]
        for endpoint_id in stale_ids:
            runtime = self.endpoint_runtimes.pop(endpoint_id)
            await runtime.stop()

        use_legacy_runtime = (
            int(config.endpoint_id or 0) <= 0 and int(config.default_pool_id or 0) > 0
        )
        if use_legacy_runtime:
            try:
                await self.legacy_runtime.start()
            except Exception as exc:
                self.legacy_runtime.last_error = str(exc)
                errors.append(str(exc))
        else:
            await self.legacy_runtime.stop()

        if errors:
            self.last_error = errors[-1]

    async def stop(self) -> None:
        await self.legacy_runtime.stop()
        for endpoint_id in list(self.endpoint_runtimes):
            runtime = self.endpoint_runtimes.pop(endpoint_id)
            await runtime.stop()

    def status(self) -> dict[str, object]:
        items: list[dict[str, object]] = []
        endpoint_map = {
            int(item.get("id") or 0): item for item in self.storage.list_http_proxy_endpoints()
        }
        for endpoint_id, runtime in sorted(
            self.endpoint_runtimes.items(), key=lambda item: item[0]
        ):
            endpoint = endpoint_map.get(int(endpoint_id), {})
            items.append(
                {
                    "endpoint_id": int(endpoint_id),
                    "name": str(endpoint.get("name") or ""),
                    "listen_host": str(runtime.gateway.config.listen_host),
                    "listen_port": int(runtime.gateway.config.listen_port),
                    "running": runtime.server is not None,
                    "last_error": str(runtime.last_error or ""),
                }
            )
        legacy_status = self.legacy_runtime.status()
        return {
            "running": bool(legacy_status.get("running")) or any(item["running"] for item in items),
            "last_error": str(self.last_error or legacy_status.get("last_error") or ""),
            "legacy": legacy_status,
            "items": items,
        }

    def _endpoint_entry_pool_id(self, endpoint: dict[str, object]) -> int:
        hops = list(endpoint.get("hops") or [])
        if not hops:
            return 0
        return int(hops[0].get("pool_id") or 0)

    def _config_from_endpoint(self, endpoint: dict[str, object]) -> HttpGatewayConfig:
        entry_pool_id = self._endpoint_entry_pool_id(endpoint)
        return HttpGatewayConfig(
            enabled=True,
            listen_host=str(endpoint.get("listen_host") or "127.0.0.1"),
            listen_port=int(endpoint.get("listen_port") or 8899),
            endpoint_id=int(endpoint.get("id") or 0),
            default_pool_id=entry_pool_id,
            sticky_ttl_sec=int(endpoint.get("sticky_ttl_sec") or 3600),
            session_missing_action=str(endpoint.get("session_missing_action") or "RANDOM"),
            http_session_header_names=list(endpoint.get("session_header_names") or []),
            http_session_query_names=list(endpoint.get("session_query_param_names") or []),
            connect_session_header_names=list(endpoint.get("connect_session_header_names") or []),
        )
