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
    ) -> dict[str, Any]:
        if self.storage.get_proxy_by_key(front_node_key) is None:
            raise ValueError("front proxy not found")
        if self.storage.get_proxy_by_key(exit_node_key) is None:
            raise ValueError("exit proxy not found")
        return self.storage.upsert_chain_egress_instance(
            instance_id=instance_id,
            pool_id=pool_id,
            backend_type=self.backend.backend_type,
            front_node_key=front_node_key,
            exit_node_key=exit_node_key,
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

    def list_instances(self, pool_id: int | None = None) -> list[dict[str, Any]]:
        return self.storage.list_chain_egress_instances(pool_id=pool_id)

    def list_running_instance_ids(self, pool_id: int | None = None) -> set[str]:
        running_ids: set[str] = set()
        for item in self.list_instances(pool_id=pool_id):
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
    ) -> dict[str, Any]:
        instance_id = self.build_instance_id(
            pool_id=pool_id,
            front_node_key=front_node_key,
            exit_node_key=exit_node_key,
            inbound_type=inbound_type,
        )
        item = self.storage.get_chain_egress_instance(instance_id)
        if item is None:
            item = self.create_instance(
                instance_id=instance_id,
                pool_id=pool_id,
                front_node_key=front_node_key,
                exit_node_key=exit_node_key,
                listen=listen or self.storage.get_backend_default_listen(),
                port=self._allocate_port(),
                inbound_type=inbound_type,
            )
        if self._is_instance_live(item):
            return item
        if not self._is_instance_port_available(item):
            item = self._update_instance_port(item, self._allocate_port(exclude_instance_id=str(item.get("instance_id") or "")))
        return self.start_instance(instance_id)

    def build_instance_id(
        self,
        pool_id: int,
        front_node_key: str,
        exit_node_key: str,
        inbound_type: str,
    ) -> str:
        return f"gw-{int(pool_id)}-{str(front_node_key)[:10]}-{str(exit_node_key)[:10]}-{str(inbound_type or 'http').lower()}"

    def _allocate_port(self, exclude_instance_id: str = "") -> int:
        port_range = self.storage.get_backend_default_port_range()
        used_ports = {
            int(item.get("port") or 0)
            for item in self.storage.list_chain_egress_instances()
            if int(item.get("port") or 0) > 0 and str(item.get("instance_id") or "") != str(exclude_instance_id or "")
        }
        listen = self.storage.get_backend_default_listen()
        for port in range(int(port_range["start"]), int(port_range["end"]) + 1):
            if port not in used_ports and self._is_bind_available(listen, port):
                return port
        raise RuntimeError("no available backend port")

    def start_instance(self, instance_id: str) -> dict[str, Any]:
        item = self.storage.get_chain_egress_instance(instance_id)
        if item is None:
            raise ValueError("chain instance not found")

        front_proxy = self.storage.get_proxy_by_key(str(item.get("front_node_key") or ""))
        exit_proxy = self.storage.get_proxy_by_key(str(item.get("exit_node_key") or ""))
        if front_proxy is None:
            raise ValueError("front proxy not found")
        if exit_proxy is None:
            raise ValueError("exit proxy not found")

        spec = ChainInstanceSpec(
            instance_id=str(item["instance_id"]),
            pool_id=int(item["pool_id"]),
            listen=str(item["listen"]),
            port=int(item["port"]),
            inbound_type=str(item["inbound_type"]),
            front_proxy=front_proxy,
            exit_proxy=exit_proxy,
        )
        if not self._is_bind_available(spec.listen, spec.port):
            item = self._update_instance_port(item, self._allocate_port(exclude_instance_id=str(item["instance_id"])))
            spec = ChainInstanceSpec(
                instance_id=str(item["instance_id"]),
                pool_id=int(item["pool_id"]),
                listen=str(item["listen"]),
                port=int(item["port"]),
                inbound_type=str(item["inbound_type"]),
                front_proxy=front_proxy,
                exit_proxy=exit_proxy,
            )
        started = self.backend.start(spec)
        self._wait_until_instance_ready(spec.listen, spec.port)
        return self.storage.upsert_chain_egress_instance(
            instance_id=str(item["instance_id"]),
            pool_id=int(item["pool_id"]),
            backend_type=self.backend.backend_type,
            front_node_key=str(item["front_node_key"]),
            exit_node_key=str(item["exit_node_key"]),
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
            backend_type=str(item.get("backend_type") or self.backend.backend_type),
            front_node_key=str(item["front_node_key"]),
            exit_node_key=str(item["exit_node_key"]),
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

    def rebuild_instance(
        self,
        instance_id: str,
        front_node_key: str | None = None,
        exit_node_key: str | None = None,
    ) -> dict[str, Any]:
        item = self.storage.get_chain_egress_instance(instance_id)
        if item is None:
            raise ValueError("chain instance not found")
        next_front = str(front_node_key or item["front_node_key"])
        next_exit = str(exit_node_key or item["exit_node_key"])
        if self.storage.get_proxy_by_key(next_front) is None:
            raise ValueError("front proxy not found")
        if self.storage.get_proxy_by_key(next_exit) is None:
            raise ValueError("exit proxy not found")
        was_running = str(item.get("status") or "") == "running"
        if was_running:
            self.backend.stop(instance_id)
        updated = self.storage.upsert_chain_egress_instance(
            instance_id=str(item["instance_id"]),
            pool_id=int(item["pool_id"]),
            backend_type=str(item.get("backend_type") or self.backend.backend_type),
            front_node_key=next_front,
            exit_node_key=next_exit,
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
            backend_type=str(item.get("backend_type") or self.backend.backend_type),
            front_node_key=str(item["front_node_key"]),
            exit_node_key=str(item["exit_node_key"]),
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
            backend_type=str(item.get("backend_type") or self.backend.backend_type),
            front_node_key=str(item["front_node_key"]),
            exit_node_key=str(item["exit_node_key"]),
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
