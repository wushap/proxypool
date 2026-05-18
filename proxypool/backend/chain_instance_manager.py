from __future__ import annotations

import os
import socket
import time
from contextlib import suppress
from typing import Any

from proxypool.backend.egress_backend import ChainInstanceSpec, EgressBackend
from proxypool.storage.sqlite import SQLiteProxyStorage


class ChainInstanceManager:
    def __init__(self, storage: SQLiteProxyStorage, backend: EgressBackend) -> None:
        self.storage = storage
        self.backend = backend

    def create_instance(
        self,
        instance_id: str,
        pool_id: int,
        front_node_key: str,
        exit_node_key: str,
        listen: str,
        port: int,
        inbound_type: str,
        endpoint_id: int = 0,
        hop_node_keys: list[str] | None = None,
        route_signature: str = "",
    ) -> dict[str, Any]:
        resolved_hops = self._resolve_hop_keys(front_node_key, exit_node_key, hop_node_keys)
        self._assert_hop_keys_exist(resolved_hops)
        return self.storage.upsert_chain_egress_instance(
            instance_id=instance_id,
            pool_id=pool_id,
            endpoint_id=endpoint_id,
            backend_type=self.backend.backend_type,
            front_node_key=resolved_hops[0],
            exit_node_key=resolved_hops[-1],
            hop_node_keys=resolved_hops,
            route_signature=route_signature or ">".join(resolved_hops),
            listen=listen,
            port=port,
            inbound_type=inbound_type,
            status="stopped",
            pid=-1,
            config_file="",
            log_file="",
            egress_ip="",
            last_error="",
        )

    def list_instances(
        self,
        pool_id: int | None = None,
        endpoint_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.storage.list_chain_egress_instances(pool_id=pool_id, endpoint_id=endpoint_id)

    def list_running_instance_ids(
        self,
        pool_id: int | None = None,
        endpoint_id: int | None = None,
    ) -> set[str]:
        running_ids: set[str] = set()
        for item in self.list_instances(pool_id=pool_id, endpoint_id=endpoint_id):
            if not self._is_instance_live(item):
                continue
            instance_id = str(item.get("instance_id") or "")
            if instance_id:
                running_ids.add(instance_id)
        return running_ids

    def get_instance(self, instance_id: str) -> dict[str, Any] | None:
        return self.storage.get_chain_egress_instance(instance_id)

    def ensure_instance(
        self,
        pool_id: int,
        front_node_key: str,
        exit_node_key: str,
        inbound_type: str = "http",
        listen: str | None = None,
        endpoint_id: int = 0,
        hop_node_keys: list[str] | None = None,
        route_signature: str = "",
    ) -> dict[str, Any]:
        resolved_hops = self._resolve_hop_keys(front_node_key, exit_node_key, hop_node_keys)
        instance_id = self.build_instance_id(
            pool_id=pool_id,
            hop_node_keys=resolved_hops,
            inbound_type=inbound_type,
            endpoint_id=endpoint_id,
        )
        item = self.storage.get_chain_egress_instance(instance_id)
        if item is None:
            item = self.create_instance(
                instance_id=instance_id,
                pool_id=pool_id,
                front_node_key=resolved_hops[0],
                exit_node_key=resolved_hops[-1],
                listen=listen or self.storage.get_backend_default_listen(),
                port=self._allocate_port(),
                inbound_type=inbound_type,
                endpoint_id=endpoint_id,
                hop_node_keys=resolved_hops,
                route_signature=route_signature or ">".join(resolved_hops),
            )
        if self._is_instance_live(item):
            return item
        if not self._is_instance_port_available(item):
            item = self._update_instance_port(item, self._allocate_port(exclude_instance_id=str(item.get("instance_id") or "")))
        return self.start_instance(instance_id)

    def build_instance_id(
        self,
        pool_id: int,
        hop_node_keys: list[str],
        inbound_type: str,
        endpoint_id: int = 0,
    ) -> str:
        resolved_hops = [str(item or "").strip() for item in hop_node_keys if str(item or "").strip()]
        if not resolved_hops:
            raise ValueError("hop_node_keys is empty")
        route_part = "-".join(key[:10] for key in resolved_hops[:4])
        return f"gw-{int(endpoint_id)}-{int(pool_id)}-{route_part}-{str(inbound_type or 'http').lower()}"

    def _allocate_port(self, exclude_instance_id: str = "") -> int:
        port_range = self.storage.get_backend_default_port_range()
        listen = self.storage.get_backend_default_listen()
        used_ports = {
            int(item.get("port") or 0)
            for item in self.storage.list_chain_egress_instances()
            if int(item.get("port") or 0) > 0
            and str(item.get("instance_id") or "") != str(exclude_instance_id or "")
            and str(item.get("status") or "") == "running"
            and self._is_tcp_open(str(item.get("listen") or listen), int(item.get("port") or 0), timeout_sec=0.05)
        }
        for port in range(int(port_range["start"]), int(port_range["end"]) + 1):
            if port not in used_ports and self._is_bind_available(listen, port):
                return port
        raise RuntimeError("no available backend port")

    def start_instance(self, instance_id: str) -> dict[str, Any]:
        item = self.storage.get_chain_egress_instance(instance_id)
        if item is None:
            raise ValueError("chain instance not found")

        hop_node_keys = self._resolve_hop_keys(
            str(item.get("front_node_key") or ""),
            str(item.get("exit_node_key") or ""),
            item.get("hop_node_keys"),
        )
        hop_proxies = self._load_hop_proxies(hop_node_keys)

        spec = ChainInstanceSpec(
            instance_id=str(item["instance_id"]),
            pool_id=int(item["pool_id"]),
            endpoint_id=int(item.get("endpoint_id") or 0),
            listen=str(item["listen"]),
            port=int(item["port"]),
            inbound_type=str(item["inbound_type"]),
            hop_proxies=hop_proxies,
            route_signature=str(item.get("route_signature") or ""),
        )
        if not self._is_bind_available(spec.listen, spec.port):
            item = self._update_instance_port(item, self._allocate_port(exclude_instance_id=str(item["instance_id"])))
            spec = ChainInstanceSpec(
                instance_id=str(item["instance_id"]),
                pool_id=int(item["pool_id"]),
                endpoint_id=int(item.get("endpoint_id") or 0),
                listen=str(item["listen"]),
                port=int(item["port"]),
                inbound_type=str(item["inbound_type"]),
                hop_proxies=hop_proxies,
                route_signature=str(item.get("route_signature") or ""),
            )
        started = self.backend.start(spec)
        self._wait_until_instance_ready(spec.listen, spec.port)
        return self.storage.upsert_chain_egress_instance(
            instance_id=str(item["instance_id"]),
            pool_id=int(item["pool_id"]),
            endpoint_id=int(item.get("endpoint_id") or 0),
            backend_type=self.backend.backend_type,
            front_node_key=str(item["front_node_key"]),
            exit_node_key=str(item["exit_node_key"]),
            hop_node_keys=hop_node_keys,
            route_signature=str(item.get("route_signature") or ""),
            listen=str(item["listen"]),
            port=int(item["port"]),
            inbound_type=str(item["inbound_type"]),
            status="running",
            pid=started.pid,
            config_file=str(started.config_file),
            log_file=str(started.log_file),
            egress_ip=str(item.get("egress_ip") or ""),
            last_error="",
        )

    def stop_instance(self, instance_id: str) -> dict[str, Any]:
        item = self.storage.get_chain_egress_instance(instance_id)
        if item is None:
            raise ValueError("chain instance not found")
        self.backend.stop(instance_id)
        return self.storage.upsert_chain_egress_instance(
            instance_id=str(item["instance_id"]),
            pool_id=int(item["pool_id"]),
            endpoint_id=int(item.get("endpoint_id") or 0),
            backend_type=str(item.get("backend_type") or self.backend.backend_type),
            front_node_key=str(item["front_node_key"]),
            exit_node_key=str(item["exit_node_key"]),
            hop_node_keys=list(item.get("hop_node_keys") or []),
            route_signature=str(item.get("route_signature") or ""),
            listen=str(item["listen"]),
            port=int(item["port"]),
            inbound_type=str(item["inbound_type"]),
            status="stopped",
            pid=-1,
            config_file=str(item.get("config_file") or ""),
            log_file=str(item.get("log_file") or ""),
            egress_ip=str(item.get("egress_ip") or ""),
            last_error="",
        )

    def mark_instance_failed(self, instance_id: str, error: str = "") -> dict[str, Any] | None:
        item = self.storage.get_chain_egress_instance(instance_id)
        if item is None:
            return None
        with suppress(Exception):
            self.backend.stop(instance_id)
        return self.storage.upsert_chain_egress_instance(
            instance_id=str(item["instance_id"]),
            pool_id=int(item["pool_id"]),
            endpoint_id=int(item.get("endpoint_id") or 0),
            backend_type=str(item.get("backend_type") or self.backend.backend_type),
            front_node_key=str(item["front_node_key"]),
            exit_node_key=str(item["exit_node_key"]),
            hop_node_keys=list(item.get("hop_node_keys") or []),
            route_signature=str(item.get("route_signature") or ""),
            listen=str(item["listen"]),
            port=int(item["port"]),
            inbound_type=str(item["inbound_type"]),
            status="failed",
            pid=-1,
            config_file=str(item.get("config_file") or ""),
            log_file=str(item.get("log_file") or ""),
            egress_ip=str(item.get("egress_ip") or ""),
            last_error=str(error or "proxy route request failed")[:1000],
        )

    def rebuild_instance(
        self,
        instance_id: str,
        front_node_key: str | None = None,
        exit_node_key: str | None = None,
        hop_node_keys: list[str] | None = None,
        route_signature: str | None = None,
    ) -> dict[str, Any]:
        item = self.storage.get_chain_egress_instance(instance_id)
        if item is None:
            raise ValueError("chain instance not found")
        current_hops = list(item.get("hop_node_keys") or [])
        next_hops = hop_node_keys or self._resolve_hop_keys(
            str(front_node_key or item["front_node_key"]),
            str(exit_node_key or item["exit_node_key"]),
            current_hops,
        )
        self._assert_hop_keys_exist(next_hops)
        next_front = next_hops[0]
        next_exit = next_hops[-1]
        was_running = str(item.get("status") or "") == "running"
        if was_running:
            self.backend.stop(instance_id)
        updated = self.storage.upsert_chain_egress_instance(
            instance_id=str(item["instance_id"]),
            pool_id=int(item["pool_id"]),
            endpoint_id=int(item.get("endpoint_id") or 0),
            backend_type=str(item.get("backend_type") or self.backend.backend_type),
            front_node_key=next_front,
            exit_node_key=next_exit,
            hop_node_keys=next_hops,
            route_signature=str(route_signature or item.get("route_signature") or ">".join(next_hops)),
            listen=str(item["listen"]),
            port=int(item["port"]),
            inbound_type=str(item["inbound_type"]),
            status="stopped",
            pid=-1,
            config_file=str(item.get("config_file") or ""),
            log_file=str(item.get("log_file") or ""),
            egress_ip=str(item.get("egress_ip") or ""),
            last_error="",
        )
        if not was_running:
            return updated
        return self.start_instance(instance_id)

    def _is_instance_live(self, item: dict[str, Any] | None) -> bool:
        if item is None:
            return False
        if str(item.get("status") or "") != "running":
            return False
        pid = int(item.get("pid") or -1)
        listen = str(item.get("listen") or "")
        port = int(item.get("port") or 0)
        if self._is_process_alive(pid) and self._is_tcp_open(listen, port):
            return True
        self.storage.upsert_chain_egress_instance(
            instance_id=str(item["instance_id"]),
            pool_id=int(item["pool_id"]),
            endpoint_id=int(item.get("endpoint_id") or 0),
            backend_type=str(item.get("backend_type") or self.backend.backend_type),
            front_node_key=str(item["front_node_key"]),
            exit_node_key=str(item["exit_node_key"]),
            hop_node_keys=list(item.get("hop_node_keys") or []),
            route_signature=str(item.get("route_signature") or ""),
            listen=listen,
            port=port,
            inbound_type=str(item["inbound_type"]),
            status="stopped",
            pid=-1,
            config_file=str(item.get("config_file") or ""),
            log_file=str(item.get("log_file") or ""),
            egress_ip=str(item.get("egress_ip") or ""),
            last_error=str(item.get("last_error") or ""),
        )
        return False

    def _is_instance_port_available(self, item: dict[str, Any]) -> bool:
        return self._is_bind_available(str(item.get("listen") or ""), int(item.get("port") or 0))

    def _update_instance_port(self, item: dict[str, Any], port: int) -> dict[str, Any]:
        return self.storage.upsert_chain_egress_instance(
            instance_id=str(item["instance_id"]),
            pool_id=int(item["pool_id"]),
            endpoint_id=int(item.get("endpoint_id") or 0),
            backend_type=str(item.get("backend_type") or self.backend.backend_type),
            front_node_key=str(item["front_node_key"]),
            exit_node_key=str(item["exit_node_key"]),
            hop_node_keys=list(item.get("hop_node_keys") or []),
            route_signature=str(item.get("route_signature") or ""),
            listen=str(item["listen"]),
            port=int(port),
            inbound_type=str(item["inbound_type"]),
            status=str(item.get("status") or "stopped"),
            pid=int(item.get("pid") or -1),
            config_file=str(item.get("config_file") or ""),
            log_file=str(item.get("log_file") or ""),
            egress_ip=str(item.get("egress_ip") or ""),
            last_error=str(item.get("last_error") or ""),
        )

    def _is_process_alive(self, pid: int) -> bool:
        if int(pid) <= 0:
            return False
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False

    def _is_tcp_open(self, host: str, port: int, timeout_sec: float = 0.25) -> bool:
        probe_host = self._normalize_probe_host(host)
        try:
            with socket.create_connection((probe_host, int(port)), timeout=max(0.1, timeout_sec)):
                return True
        except OSError:
            return False

    def _is_bind_available(self, host: str, port: int) -> bool:
        bind_host = str(host or "").strip() or "127.0.0.1"
        try:
            infos = socket.getaddrinfo(bind_host, int(port), type=socket.SOCK_STREAM)
        except socket.gaierror:
            return False
        for family, socktype, proto, _canonname, sockaddr in infos:
            sock = socket.socket(family, socktype, proto)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(sockaddr)
                return True
            except OSError:
                continue
            finally:
                with suppress(OSError):
                    sock.close()
        return False

    def _normalize_probe_host(self, host: str) -> str:
        text = str(host or "").strip()
        if text in {"", "0.0.0.0", "::"}:
            return "127.0.0.1"
        return text

    def _wait_until_instance_ready(self, host: str, port: int, timeout_sec: float = 5.0) -> None:
        deadline = time.monotonic() + max(0.1, timeout_sec)
        while time.monotonic() < deadline:
            if self._is_tcp_open(host, port, timeout_sec=0.2):
                return
            time.sleep(0.05)
        raise RuntimeError(f"chain instance did not become ready on {host}:{port}")

    def _resolve_hop_keys(self, front_node_key: str, exit_node_key: str, hop_node_keys: list[str] | None) -> list[str]:
        resolved = [str(item or "").strip() for item in list(hop_node_keys or []) if str(item or "").strip()]
        if resolved:
            return resolved
        front = str(front_node_key or "").strip()
        exit_key = str(exit_node_key or "").strip()
        if not front or not exit_key:
            raise ValueError("front and exit proxy are required")
        if front == exit_key:
            return [front]
        return [front, exit_key]

    def _assert_hop_keys_exist(self, hop_node_keys: list[str]) -> None:
        for index, key in enumerate(hop_node_keys):
            if self.storage.get_proxy_by_key(key) is None:
                raise ValueError(f"hop proxy not found at index {index}: {key}")

    def _load_hop_proxies(self, hop_node_keys: list[str]) -> list[dict[str, Any]]:
        proxies: list[dict[str, Any]] = []
        for index, key in enumerate(hop_node_keys):
            proxy = self.storage.get_proxy_by_key(key)
            if proxy is None:
                raise ValueError(f"hop proxy not found at index {index}: {key}")
            proxies.append(proxy)
        return proxies
