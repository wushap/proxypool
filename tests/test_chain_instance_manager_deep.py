from __future__ import annotations

import os
import socket
from pathlib import Path
from unittest.mock import patch

from proxypool.backend.chain_instance_manager import ChainInstanceManager
from proxypool.storage.sqlite import SQLiteProxyStorage


def _make_manager(tmp_path: Path, port_range: tuple[int, int] = (19100, 19110)):
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    storage.set_backend_default_port_range(start=port_range[0], end=port_range[1])
    return storage


def _insert_running_instance(storage: SQLiteProxyStorage, instance_id: str, port: int):
    storage.upsert_chain_egress_instance(
        instance_id=instance_id,
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key="front-1",
        exit_node_key="exit-1",
        hop_node_keys=["front-1", "exit-1"],
        route_signature="front-1>exit-1",
        listen="127.0.0.1",
        port=port,
        inbound_type="http",
        status="running",
        pid=os.getpid(),
        config_file="/tmp/test.yaml",
        log_file="/tmp/test.log",
        egress_ip="",
        last_error="",
    )


class FakeBackend:
    backend_type = "mihomo"

    def __init__(self):
        self.started: list[str] = []
        self.stopped: list[str] = []
        self.listeners: dict[str, socket.socket] = {}

    def build_config(self, spec):
        return {}

    def start(self, spec):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((spec.listen, spec.port))
        listener.listen(1)
        prev = self.listeners.pop(spec.instance_id, None)
        if prev is not None:
            prev.close()
        self.listeners[spec.instance_id] = listener
        self.started.append(spec.instance_id)
        from proxypool.backend.egress_backend import StartedInstance
        return StartedInstance(
            pid=os.getpid(),
            config_file=Path("/tmp/cim-test.yaml"),
            log_file=Path("/tmp/cim-test.log"),
        )

    def stop(self, instance_id):
        self.stopped.append(instance_id)
        listener = self.listeners.pop(instance_id, None)
        if listener is not None:
            listener.close()

    def close(self):
        for iid in list(self.listeners):
            self.stop(iid)


def test_list_running_instance_ids_skips_empty_instance_id(tmp_path):
    """Branch 70->66: instance is live but instance_id is empty, so it is not added to the set."""
    storage = _make_manager(tmp_path)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 19100))
    listener.listen(1)
    _insert_running_instance(storage, "chain-valid", 19100)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    try:
        real_item = storage.get_chain_egress_instance("chain-valid")
        empty_id_item = dict(real_item, instance_id="")

        def patched_list(pool_id=None, endpoint_id=None):
            return [real_item, empty_id_item]

        with patch.object(manager, "list_instances", side_effect=patched_list):
            ids = manager.list_running_instance_ids(pool_id=1)
            assert "chain-valid" in ids
            assert len(ids) == 1
    finally:
        listener.close()
