from __future__ import annotations

import os
import socket
import threading
import time
from contextlib import suppress
from pathlib import Path
from unittest.mock import patch

from proxypool.backend.chain_instance_manager import ChainInstanceManager
from proxypool.backend.egress_backend import StartedInstance
from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


class FakeBackend:
    backend_type = "mihomo"

    def __init__(self):
        self.started = []
        self.stopped = []
        self.listeners: dict[str, socket.socket] = {}

    def build_config(self, spec):
        return {"listeners": [{"type": spec.inbound_type, "port": spec.port}]}

    def start(self, spec):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((spec.listen, spec.port))
        listener.listen(1)
        previous = self.listeners.pop(spec.instance_id, None)
        if previous is not None:
            previous.close()
        self.listeners[spec.instance_id] = listener
        self.started.append(spec.instance_id)
        return StartedInstance(pid=os.getpid(), config_file=Path("/tmp/test.yaml"), log_file=Path("/tmp/test.log"))

    def stop(self, instance_id):
        self.stopped.append(instance_id)
        listener = self.listeners.pop(instance_id, None)
        if listener is not None:
            listener.close()

    def close(self) -> None:
        for instance_id in list(self.listeners):
            self.stop(instance_id)


class DelayedBackend(FakeBackend):
    def __init__(self, delay_sec: float = 0.2):
        super().__init__()
        self.delay_sec = delay_sec
        self.threads: list[threading.Thread] = []

    def start(self, spec):
        def _listen() -> None:
            time.sleep(self.delay_sec)
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((spec.listen, spec.port))
            listener.listen(1)
            previous = self.listeners.pop(spec.instance_id, None)
            if previous is not None:
                previous.close()
            self.listeners[spec.instance_id] = listener

        thread = threading.Thread(target=_listen, daemon=True)
        thread.start()
        self.threads.append(thread)
        self.started.append(spec.instance_id)
        return StartedInstance(pid=os.getpid(), config_file=Path("/tmp/test.yaml"), log_file=Path("/tmp/test.log"))

    def close(self) -> None:
        for thread in self.threads:
            thread.join(timeout=1.0)
        super().close()


class ExitingBackend(FakeBackend):
    def start(self, spec):
        self.started.append(spec.instance_id)
        log_file = Path("/tmp/test-exit.log")
        log_file.write_text("fatal: parse config error\n", encoding="utf-8")
        return StartedInstance(pid=99999, config_file=Path("/tmp/test-exit.yaml"), log_file=log_file)


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
    try:
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
    finally:
        backend.close()


def test_ensure_instance_restarts_stale_running_record(tmp_path: Path):
    storage = SQLiteProxyStorage(tmp_path / "stale.db")
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
    instance_id = ChainInstanceManager(storage=storage, backend=FakeBackend()).build_instance_id(
        pool_id=1,
        hop_node_keys=[front.normalized_key(), exit_node.normalized_key()],
        inbound_type="http",
    )
    storage.upsert_chain_egress_instance(
        instance_id=instance_id,
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key=front.normalized_key(),
        exit_node_key=exit_node.normalized_key(),
        hop_node_keys=[front.normalized_key(), exit_node.normalized_key()],
        route_signature="front>exit",
        listen="127.0.0.1",
        port=18080,
        inbound_type="http",
        status="running",
        pid=99999,
        config_file="/tmp/test.yaml",
        log_file="/tmp/test.log",
        egress_ip="",
        last_error="",
    )
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    try:
        with patch("os.kill", side_effect=ProcessLookupError()):
            item = manager.ensure_instance(
                pool_id=1,
                front_node_key=front.normalized_key(),
                exit_node_key=exit_node.normalized_key(),
                inbound_type="http",
            )

        assert item["status"] == "running"
        assert item["instance_id"] == instance_id
        assert backend.started == [instance_id]
    finally:
        backend.close()


def test_allocate_port_skips_ports_already_bound_on_host(tmp_path: Path):
    storage = SQLiteProxyStorage(tmp_path / "ports.db")
    storage.set_backend_default_port_range(start=19081, end=19083)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 19081))
    sock.listen(1)
    try:
        port = manager._allocate_port()
    finally:
        sock.close()

    assert port != 19081


def test_allocate_port_ignores_failed_records_with_free_ports(tmp_path: Path):
    storage = SQLiteProxyStorage(tmp_path / "failed-ports.db")
    storage.set_backend_default_port_range(start=19081, end=19082)
    storage.upsert_chain_egress_instance(
        instance_id="failed-chain",
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key="front-1",
        exit_node_key="exit-1",
        hop_node_keys=["front-1", "exit-1"],
        route_signature="front-1>exit-1",
        listen="127.0.0.1",
        port=19081,
        inbound_type="http",
        status="failed",
        pid=-1,
        config_file="/tmp/test.yaml",
        log_file="/tmp/test.log",
        egress_ip="",
        last_error="tls failed",
    )
    manager = ChainInstanceManager(storage=storage, backend=FakeBackend())

    assert manager._allocate_port() == 19081


def test_ensure_instance_reuses_live_running_record_without_reassigning_port(tmp_path: Path):
    storage = SQLiteProxyStorage(tmp_path / "reuse.db")
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

    try:
        first = manager.ensure_instance(
            pool_id=1,
            front_node_key=front.normalized_key(),
            exit_node_key=exit_node.normalized_key(),
            inbound_type="http",
        )
        second = manager.ensure_instance(
            pool_id=1,
            front_node_key=front.normalized_key(),
            exit_node_key=exit_node.normalized_key(),
            inbound_type="http",
        )
    finally:
        backend.close()

    assert second["instance_id"] == first["instance_id"]
    assert second["port"] == first["port"]
    assert backend.started == [first["instance_id"]]


def test_list_running_instance_ids_excludes_stale_records(tmp_path: Path):
    storage = SQLiteProxyStorage(tmp_path / "stale-list.db")
    storage.upsert_chain_egress_instance(
        instance_id="chain-a",
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key="front-1",
        exit_node_key="exit-1",
        hop_node_keys=["front-1", "exit-1"],
        route_signature="front-1>exit-1",
        listen="127.0.0.1",
        port=18080,
        inbound_type="http",
        status="running",
        pid=99999,
        config_file="/tmp/test.yaml",
        log_file="/tmp/test.log",
        egress_ip="",
        last_error="",
    )
    manager = ChainInstanceManager(storage=storage, backend=FakeBackend())

    with patch("os.kill", side_effect=ProcessLookupError()):
        assert manager.list_running_instance_ids(pool_id=1) == set()

    item = manager.get_instance("chain-a")
    assert item is not None
    assert item["status"] == "stopped"


def test_ensure_instance_reassigns_port_when_stale_port_is_occupied(tmp_path: Path):
    storage = SQLiteProxyStorage(tmp_path / "reassign-port.db")
    storage.set_backend_default_port_range(start=19081, end=19083)
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
    instance_id = ChainInstanceManager(storage=storage, backend=FakeBackend()).build_instance_id(
        pool_id=1,
        hop_node_keys=[front.normalized_key(), exit_node.normalized_key()],
        inbound_type="http",
    )
    storage.upsert_chain_egress_instance(
        instance_id=instance_id,
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key=front.normalized_key(),
        exit_node_key=exit_node.normalized_key(),
        hop_node_keys=[front.normalized_key(), exit_node.normalized_key()],
        route_signature="front>exit",
        listen="127.0.0.1",
        port=19081,
        inbound_type="http",
        status="running",
        pid=99999,
        config_file="/tmp/test.yaml",
        log_file="/tmp/test.log",
        egress_ip="",
        last_error="",
    )
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 19081))
    blocker.listen(1)
    try:
        with patch("os.kill", side_effect=ProcessLookupError()):
            item = manager.ensure_instance(
                pool_id=1,
                front_node_key=front.normalized_key(),
                exit_node_key=exit_node.normalized_key(),
                inbound_type="http",
            )
    finally:
        blocker.close()
        backend.close()

    assert item["status"] == "running"
    assert item["port"] == 19082


def test_start_instance_waits_for_listener_ready(tmp_path: Path):
    storage = SQLiteProxyStorage(tmp_path / "wait-ready.db")
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
    backend = DelayedBackend(delay_sec=0.2)
    manager = ChainInstanceManager(storage=storage, backend=backend)

    try:
        manager.create_instance(
            instance_id="chain-a",
            pool_id=1,
            front_node_key=front.normalized_key(),
            exit_node_key=exit_node.normalized_key(),
            listen="127.0.0.1",
            port=19091,
            inbound_type="http",
        )
        started_at = time.monotonic()
        item = manager.start_instance("chain-a")
        elapsed = time.monotonic() - started_at
        with socket.create_connection(("127.0.0.1", int(item["port"])), timeout=1.0):
            pass
    finally:
        backend.close()

    assert elapsed >= 0.15


def test_start_instance_records_backend_log_when_process_exits_before_ready(tmp_path: Path):
    storage = SQLiteProxyStorage(tmp_path / "exit-before-ready.db")
    front = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1")
    exit_node = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="exit-1")
    storage.upsert_proxy(front)
    storage.upsert_proxy(exit_node)
    backend = ExitingBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    manager.create_instance(
        instance_id="chain-exit",
        pool_id=1,
        front_node_key=front.normalized_key(),
        exit_node_key=exit_node.normalized_key(),
        listen="127.0.0.1",
        port=19092,
        inbound_type="http",
    )

    with patch("os.kill", side_effect=ProcessLookupError()):
        try:
            manager.start_instance("chain-exit")
            raise AssertionError("expected start_instance to fail")
        except RuntimeError as exc:
            assert "fatal: parse config error" in str(exc)

    item = storage.get_chain_egress_instance("chain-exit")
    assert item is not None
    assert item["status"] == "failed"
    assert "fatal: parse config error" in item["last_error"]


def test_chain_instance_manager_supports_multi_hop_instance(tmp_path: Path):
    storage = SQLiteProxyStorage(tmp_path / "multi-hop.db")
    hop1 = ProxyNode(protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="hop-1")
    hop2 = ProxyNode(protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="hop-2")
    hop3 = ProxyNode(protocol="trojan", host="3.3.3.3", port=443, raw_link="trojan://3.3.3.3:443", name="hop-3", extra={"password": "p"})
    storage.upsert_proxy(hop1)
    storage.upsert_proxy(hop2)
    storage.upsert_proxy(hop3)

    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    try:
        item = manager.ensure_instance(
            pool_id=1,
            endpoint_id=9,
            front_node_key=hop1.normalized_key(),
            exit_node_key=hop3.normalized_key(),
            hop_node_keys=[hop1.normalized_key(), hop2.normalized_key(), hop3.normalized_key()],
            route_signature="pool1>pool3>pool2",
            inbound_type="http",
        )
    finally:
        backend.close()

    assert item["status"] == "running"
    assert item["endpoint_id"] == 9
    assert item["hop_node_keys"] == [hop1.normalized_key(), hop2.normalized_key(), hop3.normalized_key()]
    assert item["route_signature"] == "pool1>pool3>pool2"
