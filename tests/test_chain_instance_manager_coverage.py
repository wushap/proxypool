from __future__ import annotations

import os
import socket
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from proxypool.backend.chain_instance_manager import ChainInstanceManager
from proxypool.backend.egress_backend import StartedInstance
from proxypool.models import ProxyNode
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


# --- build_instance_id edge cases ---


def test_build_instance_id_empty_hop_keys_raises(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    with pytest.raises(ValueError, match="hop_node_keys is empty"):
        manager.build_instance_id(pool_id=1, hop_node_keys=[], inbound_type="http")


def test_build_instance_id_filters_empty_strings(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    # mix of empty and real keys
    result = manager.build_instance_id(
        pool_id=1,
        hop_node_keys=["", "  ", "key-a", "", "key-b"],
        inbound_type="socks",
        endpoint_id=5,
    )
    assert "key-a" in result
    assert "key-b" in result
    assert "socks" in result
    assert result.startswith("gw-5-1-")


# --- start_instance error paths ---


def test_start_instance_not_found_raises(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    with pytest.raises(ValueError, match="chain instance not found"):
        manager.start_instance("nonexistent-id")


def test_stop_instance_not_found_raises(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    with pytest.raises(ValueError, match="chain instance not found"):
        manager.stop_instance("nonexistent-id")


# --- mark_instance_failed ---


def test_mark_instance_failed_on_existing(tmp_path):
    storage = _make_manager(tmp_path)
    storage.upsert_chain_egress_instance(
        instance_id="chain-fail",
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key="front-1",
        exit_node_key="exit-1",
        hop_node_keys=["front-1", "exit-1"],
        route_signature="front-1>exit-1",
        listen="127.0.0.1",
        port=19105,
        inbound_type="http",
        status="running",
        pid=-1,
        config_file="",
        log_file="",
        egress_ip="",
        last_error="",
    )
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    result = manager.mark_instance_failed("chain-fail", error="connection refused")
    assert result is not None
    assert result["status"] == "failed"
    assert "connection refused" in result["last_error"]
    assert "chain-fail" in backend.stopped


def test_mark_instance_failed_not_found_returns_none(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    result = manager.mark_instance_failed("nonexistent")
    assert result is None


def test_mark_instance_failed_empty_error_uses_default(tmp_path):
    storage = _make_manager(tmp_path)
    storage.upsert_chain_egress_instance(
        instance_id="chain-fail2",
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key="front-1",
        exit_node_key="exit-1",
        hop_node_keys=["front-1", "exit-1"],
        route_signature="front-1>exit-1",
        listen="127.0.0.1",
        port=19106,
        inbound_type="http",
        status="stopped",
        pid=-1,
        config_file="",
        log_file="",
        egress_ip="",
        last_error="",
    )
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    result = manager.mark_instance_failed("chain-fail2")
    assert result is not None
    assert result["last_error"] == "proxy route request failed"


# --- rebuild_instance ---


def test_rebuild_instance_not_running(tmp_path):
    storage = _make_manager(tmp_path)
    hop1 = ProxyNode(
        protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1"
    )
    hop2 = ProxyNode(
        protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="exit-1"
    )
    hop3 = ProxyNode(
        protocol="http", host="3.3.3.3", port=9090, raw_link="http://3.3.3.3:9090", name="new-hop"
    )
    storage.upsert_proxy(hop1)
    storage.upsert_proxy(hop2)
    storage.upsert_proxy(hop3)
    storage.upsert_chain_egress_instance(
        instance_id="chain-rebuild",
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key=hop1.normalized_key(),
        exit_node_key=hop2.normalized_key(),
        hop_node_keys=[hop1.normalized_key(), hop2.normalized_key()],
        route_signature="old-route",
        listen="127.0.0.1",
        port=19102,
        inbound_type="http",
        status="stopped",
        pid=-1,
        config_file="",
        log_file="",
        egress_ip="",
        last_error="",
    )
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    result = manager.rebuild_instance(
        "chain-rebuild",
        hop_node_keys=[hop1.normalized_key(), hop3.normalized_key(), hop2.normalized_key()],
    )
    assert result["status"] == "stopped"
    assert hop3.normalized_key() in result["hop_node_keys"]
    assert len(backend.stopped) == 0


def test_rebuild_instance_was_running_restarts(tmp_path):
    storage = _make_manager(tmp_path)
    hop1 = ProxyNode(
        protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1"
    )
    hop2 = ProxyNode(
        protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="exit-1"
    )
    storage.upsert_proxy(hop1)
    storage.upsert_proxy(hop2)
    storage.upsert_chain_egress_instance(
        instance_id="chain-rebuild-run",
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key=hop1.normalized_key(),
        exit_node_key=hop2.normalized_key(),
        hop_node_keys=[hop1.normalized_key(), hop2.normalized_key()],
        route_signature="old",
        listen="127.0.0.1",
        port=19103,
        inbound_type="http",
        status="running",
        pid=-1,
        config_file="",
        log_file="",
        egress_ip="",
        last_error="",
    )
    backend = FakeBackend()
    # Simulate running: bind the port so _is_instance_live returns True via tcp check
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("127.0.0.1", 19103))
    blocker.listen(1)
    manager = ChainInstanceManager(storage=storage, backend=backend)
    try:
        result = manager.rebuild_instance("chain-rebuild-run")
    finally:
        blocker.close()
        backend.close()

    assert result["status"] == "running"
    assert "chain-rebuild-run" in backend.stopped
    assert "chain-rebuild-run" in backend.started


def test_rebuild_instance_not_found_raises(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    with pytest.raises(ValueError, match="chain instance not found"):
        manager.rebuild_instance("nonexistent")


def test_rebuild_instance_provides_route_signature(tmp_path):
    storage = _make_manager(tmp_path)
    hop1 = ProxyNode(
        protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1"
    )
    hop2 = ProxyNode(
        protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="exit-1"
    )
    storage.upsert_proxy(hop1)
    storage.upsert_proxy(hop2)
    storage.upsert_chain_egress_instance(
        instance_id="chain-rebuild-rs",
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key=hop1.normalized_key(),
        exit_node_key=hop2.normalized_key(),
        hop_node_keys=[hop1.normalized_key(), hop2.normalized_key()],
        route_signature="old-route",
        listen="127.0.0.1",
        port=19104,
        inbound_type="http",
        status="stopped",
        pid=-1,
        config_file="",
        log_file="",
        egress_ip="",
        last_error="",
    )
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    result = manager.rebuild_instance(
        "chain-rebuild-rs",
        route_signature="custom-route",
    )
    assert result["route_signature"] == "custom-route"


def test_rebuild_instance_with_front_and_exit_keys_uses_existing_hops(tmp_path):
    """When hop_node_keys already exist on the instance, _resolve_hop_keys returns them,
    so front_node_key/exit_node_key params are not used to override hops."""
    storage = _make_manager(tmp_path)
    hop1 = ProxyNode(
        protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1"
    )
    hop2 = ProxyNode(
        protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="exit-1"
    )
    storage.upsert_proxy(hop1)
    storage.upsert_proxy(hop2)
    storage.upsert_chain_egress_instance(
        instance_id="chain-rebuild-fe",
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key=hop1.normalized_key(),
        exit_node_key=hop2.normalized_key(),
        hop_node_keys=[hop1.normalized_key(), hop2.normalized_key()],
        route_signature="old",
        listen="127.0.0.1",
        port=19107,
        inbound_type="http",
        status="stopped",
        pid=-1,
        config_file="",
        log_file="",
        egress_ip="",
        last_error="",
    )
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    # When hop_node_keys is not passed, _resolve_hop_keys uses current_hops (non-empty)
    result = manager.rebuild_instance("chain-rebuild-fe")
    assert result["status"] == "stopped"
    assert result["front_node_key"] == hop1.normalized_key()


# --- _resolve_hop_keys edge cases ---


def test_resolve_hop_keys_front_equals_exit(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    result = manager._resolve_hop_keys("key-a", "key-a", None)
    assert result == ["key-a"]


def test_resolve_hop_keys_front_and_exit(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    result = manager._resolve_hop_keys("front-x", "exit-y", None)
    assert result == ["front-x", "exit-y"]


def test_resolve_hop_keys_empty_front_and_exit_raises(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    with pytest.raises(ValueError, match="front and exit proxy are required"):
        manager._resolve_hop_keys("", "", None)


def test_resolve_hop_keys_prefers_hop_node_keys(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    result = manager._resolve_hop_keys("front-x", "exit-y", ["a", "b", "c"])
    assert result == ["a", "b", "c"]


# --- _assert_hop_keys_exist ---


def test_assert_hop_keys_exist_raises_on_missing(tmp_path):
    storage = _make_manager(tmp_path)
    hop1 = ProxyNode(
        protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="existing"
    )
    storage.upsert_proxy(hop1)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    with pytest.raises(ValueError, match="hop proxy not found at index 1"):
        manager._assert_hop_keys_exist([hop1.normalized_key(), "missing-key"])


# --- _allocate_port no port available ---


def test_allocate_port_no_available_port_raises(tmp_path):
    storage = _make_manager(tmp_path, port_range=(19108, 19108))
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    # bind the only port in range
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("127.0.0.1", 19108))
    blocker.listen(1)
    try:
        with pytest.raises(RuntimeError, match="no available backend port"):
            manager._allocate_port()
    finally:
        blocker.close()


# --- _is_bind_available gaierror ---


def test_is_bind_available_gaierror_returns_false(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("no such host")):
        assert manager._is_bind_available("invalid-hostname", 19109) is False


# --- _normalize_probe_host ---


def test_normalize_probe_host_empty(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    assert manager._normalize_probe_host("") == "127.0.0.1"
    assert manager._normalize_probe_host("0.0.0.0") == "127.0.0.1"
    assert manager._normalize_probe_host("::") == "127.0.0.1"
    assert manager._normalize_probe_host("  ") == "127.0.0.1"


def test_normalize_probe_host_named(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    assert manager._normalize_probe_host("example.com") == "example.com"


# --- _is_process_alive ---


def test_is_process_alive_positive_pid(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    assert manager._is_process_alive(os.getpid()) is True


def test_is_process_alive_negative_pid(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    assert manager._is_process_alive(-1) is False
    assert manager._is_process_alive(0) is False


def test_is_process_alive_dead_pid(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    assert manager._is_process_alive(99999) is False


# --- _is_instance_live with live process ---


def test_is_instance_live_false_when_item_is_none(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    assert manager._is_instance_live(None) is False


def test_is_instance_live_true_when_process_alive_and_port_open(tmp_path):
    storage = _make_manager(tmp_path)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 19109))
    listener.listen(1)
    _insert_running_instance(storage, "chain-live", 19109)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    try:
        item = storage.get_chain_egress_instance("chain-live")
        assert manager._is_instance_live(item) is True
    finally:
        listener.close()


# --- list_running_instance_ids with live instance ---


def test_list_running_instance_ids_includes_live(tmp_path):
    storage = _make_manager(tmp_path)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 19109))
    listener.listen(1)
    _insert_running_instance(storage, "chain-live2", 19109)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    try:
        ids = manager.list_running_instance_ids(pool_id=1)
        assert "chain-live2" in ids
    finally:
        listener.close()


# --- _wait_until_instance_ready timeout ---


def test_wait_until_instance_ready_timeout_raises(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    # Use a port that nothing is listening on
    with pytest.raises(RuntimeError, match="chain instance did not become ready"):
        manager._wait_until_instance_ready("127.0.0.1", 19109, timeout_sec=0.1)


def test_wait_until_instance_ready_timeout_with_started_log(tmp_path, monkeypatch):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)

    log_file = tmp_path / "timeout.log"
    log_file.write_text("error line 1\nerror line 2\n", encoding="utf-8")
    started = StartedInstance(pid=99999, config_file=Path("/tmp/x.yaml"), log_file=log_file)

    # Make pid 99999 appear alive so _started_process_error returns ""
    monkeypatch.setattr(manager, "_is_process_alive", lambda pid: True)
    with pytest.raises(RuntimeError, match="chain instance did not become ready.*error line 2"):
        manager._wait_until_instance_ready("127.0.0.1", 19109, timeout_sec=0.1, started=started)


# --- _started_process_error ---


def test_started_process_error_dead_process_with_log(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)

    log_file = tmp_path / "exit.log"
    log_file.write_text("fatal: something broke\n", encoding="utf-8")
    started = StartedInstance(pid=99999, config_file=Path("/tmp/x.yaml"), log_file=log_file)

    with patch.object(manager, "_is_process_alive", return_value=False):
        result = manager._started_process_error(started)
        assert "fatal: something broke" in result


def test_started_process_error_dead_process_no_log(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)

    started = StartedInstance(pid=99999, config_file=Path("/tmp/x.yaml"), log_file=Path("/tmp/empty.log"))

    with patch.object(manager, "_is_process_alive", return_value=False):
        result = manager._started_process_error(started)
        assert result == "chain instance process exited before ready"


def test_started_process_error_none_started(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    assert manager._started_process_error(None) == ""


def test_started_process_error_alive_process(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    started = StartedInstance(pid=os.getpid(), config_file=Path("/tmp/x.yaml"), log_file=Path("/tmp/x.log"))
    with patch.object(manager, "_is_process_alive", return_value=True):
        assert manager._started_process_error(started) == ""


# --- _started_log_tail ---


def test_started_log_tail_reads_tail(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)

    log_file = tmp_path / "tail.log"
    log_file.write_text("line1\nline2\nline3\n", encoding="utf-8")
    started = StartedInstance(pid=1, config_file=Path("/tmp/x.yaml"), log_file=log_file)
    result = manager._started_log_tail(started)
    assert result == "line3"


def test_started_log_tail_no_log_file(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    # Use an object with log_file="" (falsy string) instead of Path("") (truthy)
    mock_started = MagicMock()
    mock_started.log_file = ""
    assert manager._started_log_tail(mock_started) == ""


def test_started_log_tail_none_started(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    assert manager._started_log_tail(None) == ""


def test_started_log_tail_missing_file(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    started = StartedInstance(pid=1, config_file=Path("/tmp/x.yaml"), log_file=Path("/nonexistent/file.log"))
    assert manager._started_log_tail(started) == ""


def test_started_log_tail_empty_lines(tmp_path):
    storage = _make_manager(tmp_path)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)

    log_file = tmp_path / "empty.log"
    log_file.write_bytes(b"\n\n\n")
    started = StartedInstance(pid=1, config_file=Path("/tmp/x.yaml"), log_file=log_file)
    result = manager._started_log_tail(started)
    assert result == ""


# --- start_instance with port reassignment ---


def test_start_instance_reassigns_port_when_bind_unavailable(tmp_path):
    storage = _make_manager(tmp_path, port_range=(19108, 19115))
    hop1 = ProxyNode(
        protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1"
    )
    hop2 = ProxyNode(
        protocol="socks", host="2.2.2.2", port=1080, raw_link="socks://2.2.2.2:1080", name="exit-1"
    )
    storage.upsert_proxy(hop1)
    storage.upsert_proxy(hop2)
    storage.upsert_chain_egress_instance(
        instance_id="chain-port-reassign",
        pool_id=1,
        endpoint_id=0,
        backend_type="mihomo",
        front_node_key=hop1.normalized_key(),
        exit_node_key=hop2.normalized_key(),
        hop_node_keys=[hop1.normalized_key(), hop2.normalized_key()],
        route_signature="r",
        listen="127.0.0.1",
        port=19108,
        inbound_type="http",
        status="stopped",
        pid=-1,
        config_file="",
        log_file="",
        egress_ip="",
        last_error="",
    )
    backend = FakeBackend()
    # Block 19108 so _is_bind_available returns False
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("127.0.0.1", 19108))
    blocker.listen(1)
    manager = ChainInstanceManager(storage=storage, backend=backend)
    try:
        result = manager.start_instance("chain-port-reassign")
    finally:
        blocker.close()
        backend.close()

    assert result["status"] == "running"
    assert result["port"] != 19108


# --- _load_hop_proxies raises on missing ---


def test_load_hop_proxies_raises_on_missing(tmp_path):
    storage = _make_manager(tmp_path)
    hop1 = ProxyNode(
        protocol="http", host="1.1.1.1", port=8080, raw_link="http://1.1.1.1:8080", name="front-1"
    )
    storage.upsert_proxy(hop1)
    backend = FakeBackend()
    manager = ChainInstanceManager(storage=storage, backend=backend)
    with pytest.raises(ValueError, match="hop proxy not found at index 1"):
        manager._load_hop_proxies([hop1.normalized_key(), "nonexistent-key"])
