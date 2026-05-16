from __future__ import annotations

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

    def get_instance(self, instance_id: str) -> dict[str, Any] | None:
        return self.storage.get_chain_egress_instance(instance_id)

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
        started = self.backend.start(spec)
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
