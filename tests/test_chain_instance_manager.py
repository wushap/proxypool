from __future__ import annotations

from pathlib import Path

from proxypool.backend.chain_instance_manager import ChainInstanceManager
from proxypool.backend.egress_backend import StartedInstance
from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


class FakeBackend:
    backend_type = "mihomo"

    def __init__(self):
        self.started = []
        self.stopped = []

    def build_config(self, spec):
        return {"listeners": [{"type": spec.inbound_type, "port": spec.port}]}

    def start(self, spec):
        self.started.append(spec.instance_id)
        return StartedInstance(pid=999, config_file=Path("/tmp/test.yaml"), log_file=Path("/tmp/test.log"))

    def stop(self, instance_id):
        self.stopped.append(instance_id)


def test_chain_instance_manager_start_and_stop(tmp_path: Path):
    storage = SQLiteProxyStorage(tmp_path / "test.db")
    front = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1")
    exit_node = ProxyNode(
        protocol="socks",
        host="2.2.2.2",
        port=1080,
        raw_link="socks://2.2.2.2:1080",
        name="exit-1",
    )
    storage.upsert_proxy(front)
    storage.upsert_proxy(exit_node)

    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)

    manager.create_instance(
        instance_id="chain-a",
        pool_id=1,
        front_node_key=front.normalized_key(),
        exit_node_key=exit_node.normalized_key(),
        listen="127.0.0.1",
        port=18080,
        inbound_type="http",
    )
    manager.start_instance("chain-a")

    item = storage.list_chain_egress_instances(pool_id=1)[0]
    assert item["status"] == "running"
    assert item["backend_type"] == "mihomo"

    manager.stop_instance("chain-a")
    item = storage.list_chain_egress_instances(pool_id=1)[0]
    assert item["status"] == "stopped"
