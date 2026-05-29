from __future__ import annotations

import pytest

from proxypool.gateway.config import HttpGatewayConfig
from proxypool.gateway.connect_session import ConnectSessionRegistry
from proxypool.gateway.forward_proxy import ForwardProxyGateway


class FakePoolService:
    def __init__(self, pools: dict[int, dict] | None = None, pool: dict | None = None):
        if pool is not None:
            self._pools = {int(pool["id"]): pool}
        else:
            self._pools = dict(pools or {})

    def get_pool(self, pool_id: int):
        return self._pools.get(int(pool_id))


class FakeChainService:
    def __init__(self):
        self.calls: list = []
        self.failures: list = []

    def route_request(self, session_id="", pool_id=0, endpoint_id=0, target_domain="", live_instance_ids=None):
        self.calls.append((session_id, pool_id, endpoint_id, target_domain, live_instance_ids))
        return {
            "front_node": {"key": "front-1"},
            "exit_node": {"key": "exit-1"},
            "route_signature": "front-1>exit-1",
            "lease_created": bool(session_id),
        }

    def bind_instance_to_session(
        self, session_id: str, pool_id: int, instance_id: str, endpoint_id: int = 0
    ):
        return {"session_id": session_id, "pool_id": pool_id, "instance_id": instance_id, "endpoint_id": endpoint_id}

    def report_endpoint_route_failure(self, **kwargs):
        self.failures.append(kwargs)

    def report_endpoint_route_success(self, **kwargs):
        self.calls.append(("report_success", kwargs))


class FakeInstanceManager:
    def list_running_instance_ids(self, pool_id=None, endpoint_id=None):
        return set()

    def ensure_instance(self, pool_id, front_node_key, exit_node_key, inbound_type="http",
                        listen=None, endpoint_id=0, hop_node_keys=None, route_signature=""):
        return {"instance_id": "inst-1", "listen": "127.0.0.1", "port": 18080, "status": "running"}

    def mark_instance_failed(self, instance_id, error=""):
        pass


class FakeStorage:
    def __init__(self, candidates=None, endpoints=None, rules=None):
        self._candidates = candidates or []
        self._endpoints = endpoints or {}
        self._rules = rules or []

    def get_http_proxy_endpoint(self, endpoint_id):
        return self._endpoints.get(endpoint_id)

    def list_proxy_pool_candidates(self, pool_id, limit=500):
        return self._candidates

    def list_pool_session_rules(self, pool_id):
        return self._rules


def _gateway(pool_id=7, endpoint_id=0, storage=None, missing_action="RANDOM", pool_service=None):
    return ForwardProxyGateway(
        storage=storage or FakeStorage(),
        pool_service=pool_service or FakePoolService(pool={"id": pool_id}),
        chain_service=FakeChainService(),
        chain_instance_manager=FakeInstanceManager(),
        config=HttpGatewayConfig(enabled=True, default_pool_id=pool_id, endpoint_id=endpoint_id,
                                 session_missing_action=missing_action),
    )


# --- extract_connect_session_key ---

def test_extract_connect_session_key_returns_header_value():
    gw = _gateway()
    result = gw.extract_connect_session_key(
        headers={"X-ProxyPool-Session": "my-session"},
        connection_id="conn-1",
    )
    assert result == "my-session"


def test_extract_connect_session_key_reject_when_missing():
    gw = _gateway(missing_action="REJECT")
    result = gw.extract_connect_session_key(headers={}, connection_id="conn-1")
    assert result == ""


def test_extract_connect_session_key_fallback_to_registry():
    gw = _gateway(missing_action="RANDOM")
    result = gw.extract_connect_session_key(headers={}, connection_id="conn-2")
    assert result.startswith("connect:")


# --- _default_pool ---

def test_default_pool_raises_when_not_found():
    gw = _gateway(pool_id=999, pool_service=FakePoolService(pools={}))  # empty pools
    with pytest.raises(ValueError, match="default pool not found"):
        gw._default_pool()


# --- _route_instance_attempts ---

def test_route_instance_attempts_none_endpoint():
    gw = _gateway()
    assert gw._route_instance_attempts(None) == 1


def test_route_instance_attempts_hop_with_zero_pool_id():
    gw = _gateway()
    endpoint = {"hops": [{"pool_id": 0}]}
    assert gw._route_instance_attempts(endpoint) == 1


def test_route_instance_attempts_storage_exception():
    class ErrorStorage(FakeStorage):
        def list_proxy_pool_candidates(self, pool_id, limit=500):
            raise RuntimeError("db error")

    gw = _gateway(storage=ErrorStorage())
    endpoint = {"hops": [{"pool_id": 1}]}
    assert gw._route_instance_attempts(endpoint) == 1


def test_route_instance_attempts_no_candidates():
    gw = _gateway(storage=FakeStorage(candidates=[]))
    endpoint = {"hops": [{"pool_id": 1}]}
    assert gw._route_instance_attempts(endpoint) == 1


def test_route_instance_attempts_hits_cap():
    candidates = [{"available": True}] * 60
    gw = _gateway(storage=FakeStorage(candidates=candidates))
    endpoint = {"hops": [{"pool_id": 1}]}
    assert gw._route_instance_attempts(endpoint) == 50


def test_route_instance_attempts_multi_hop():
    # 3 candidates * 4 = 12 total
    candidates_3 = [{"available": True}] * 3
    candidates_4 = [{"available": True}] * 4

    class MultiHopStorage(FakeStorage):
        def list_proxy_pool_candidates(self, pool_id, limit=500):
            return candidates_3 if pool_id == 1 else candidates_4

    gw = _gateway(storage=MultiHopStorage())
    endpoint = {"hops": [{"pool_id": 1}, {"pool_id": 2}]}
    assert gw._route_instance_attempts(endpoint) == 12


def test_route_instance_attempts_empty_hops():
    gw = _gateway()
    endpoint = {"hops": []}
    assert gw._route_instance_attempts(endpoint) == 1


# --- _resolve_route_with_instance ---

def test_resolve_route_route_none_breaks():
    class NoRouteChainService(FakeChainService):
        def route_request(self, **kwargs):
            self.calls.append(kwargs)
            return None

    gw = _gateway()
    gw.chain_service = NoRouteChainService()
    with pytest.raises(RuntimeError, match="no available chain route"):
        gw._resolve_route_with_instance(
            pool={"id": 7}, endpoint=None, session_id="s1", target_domain="example.com",
        )


def test_resolve_route_skips_duplicate_route_signature():
    class RetryChainService(FakeChainService):
        def __init__(self):
            self._call_count = 0

        def route_request(self, **kwargs):
            self._call_count += 1
            if self._call_count <= 2:
                # First two calls return same signature
                return {
                    "front_node": {"key": "front-x"},
                    "exit_node": {"key": "exit-x"},
                    "route_signature": "dup-sig",
                }
            # Third call returns a new signature
            return {
                "front_node": {"key": "front-y"},
                "exit_node": {"key": "exit-y"},
                "route_signature": "new-sig",
            }

    class FailOnceInstanceManager(FakeInstanceManager):
        def __init__(self):
            self.calls = []

        def ensure_instance(self, **kwargs):
            self.calls.append(kwargs.get("front_node_key"))
            if kwargs.get("front_node_key") == "front-x":
                raise RuntimeError("first attempt failed")
            return {"instance_id": "inst-ok", "listen": "127.0.0.1", "port": 18080, "status": "running"}

    gw = _gateway()
    gw.chain_service = RetryChainService()
    gw.chain_instance_manager = FailOnceInstanceManager()
    gw._route_instance_attempts = lambda ep: 3

    route, instance = gw._resolve_route_with_instance(
        pool={"id": 7}, endpoint=None, session_id="s1", target_domain="example.com",
    )
    assert instance["instance_id"] == "inst-ok"
    # Call 1: failed (front-x), Call 2: skipped (dup-sig), Call 3: succeeded (front-y)
    assert gw.chain_instance_manager.calls == ["front-x", "front-y"]


def test_resolve_route_all_fail_raises_runtime_error():
    class AlwaysFailManager(FakeInstanceManager):
        def ensure_instance(self, **kwargs):
            raise RuntimeError("always fails")

    gw = _gateway()
    gw.chain_instance_manager = AlwaysFailManager()
    gw._route_instance_attempts = lambda ep: 2

    with pytest.raises(RuntimeError, match="no available chain route"):
        gw._resolve_route_with_instance(
            pool={"id": 7}, endpoint=None, session_id="s1", target_domain="example.com",
        )


# --- _default_endpoint ---

def test_default_endpoint_raises_when_endpoint_id_zero():
    gw = _gateway(endpoint_id=0)
    with pytest.raises(ValueError, match="default endpoint not found"):
        gw._default_endpoint()


def test_default_endpoint_raises_when_not_found():
    gw = _gateway(endpoint_id=42)  # not in FakeStorage
    with pytest.raises(ValueError, match="default endpoint not found"):
        gw._default_endpoint()


# --- resolve_route_for_http ---

def test_resolve_route_http_rejects_missing_session():
    gw = _gateway(missing_action="REJECT")
    with pytest.raises(ValueError, match="session_id is required"):
        gw.resolve_route_for_http(raw_target="https://example.com/path", headers={})


def test_resolve_route_http_no_session_binds_when_empty():
    gw = _gateway(missing_action="RANDOM")
    route = gw.resolve_route_for_http(
        raw_target="https://example.com/path",
        headers={},
    )
    assert route["session_id"] == ""


def test_resolve_route_http_with_endpoint_no_hops_raises():
    endpoint = {"id": 10, "hops": []}
    storage = FakeStorage(endpoints={10: endpoint})
    gw = _gateway(pool_id=5, endpoint_id=10, storage=storage,
                  pool_service=FakePoolService(pool={"id": 5}))
    with pytest.raises(ValueError, match="endpoint hops are not configured"):
        gw.resolve_route_for_http(raw_target="https://example.com/path", headers={})


def test_resolve_route_http_with_endpoint_pool_not_found():
    endpoint = {"id": 10, "hops": [{"pool_id": 55}]}
    storage = FakeStorage(endpoints={10: endpoint})
    gw = _gateway(pool_id=5, endpoint_id=10, storage=storage)
    with pytest.raises(ValueError, match="entry pool not found"):
        gw.resolve_route_for_http(raw_target="https://example.com/path", headers={})


def test_resolve_route_http_with_endpoint_success():
    endpoint = {"id": 10, "hops": [{"pool_id": 7}]}
    storage = FakeStorage(endpoints={10: endpoint})
    gw = _gateway(pool_id=7, endpoint_id=10, storage=storage,
                  pool_service=FakePoolService(pool={"id": 7}))
    route = gw.resolve_route_for_http(
        raw_target="https://example.com/path",
        headers={"X-ProxyPool-Session": "sess-1"},
    )
    assert route["instance"]["instance_id"] == "inst-1"
    assert route["endpoint"] == endpoint


# --- resolve_route_for_connect ---

def test_resolve_route_connect_rejects_missing_session():
    gw = _gateway(missing_action="REJECT")
    with pytest.raises(ValueError, match="session_id is required"):
        gw.resolve_route_for_connect(target_host="example.com:443", headers={}, connection_id="conn-x")


def test_resolve_route_connect_with_endpoint_no_hops():
    endpoint = {"id": 20, "hops": []}
    storage = FakeStorage(endpoints={20: endpoint})
    gw = _gateway(pool_id=7, endpoint_id=20, storage=storage,
                  pool_service=FakePoolService(pool={"id": 7}))
    with pytest.raises(ValueError, match="endpoint hops are not configured"):
        gw.resolve_route_for_connect(target_host="example.com:443", headers={}, connection_id="conn-1")


def test_resolve_route_connect_with_endpoint_pool_not_found():
    endpoint = {"id": 20, "hops": [{"pool_id": 55}]}
    storage = FakeStorage(endpoints={20: endpoint})
    gw = _gateway(pool_id=7, endpoint_id=20, storage=storage)
    with pytest.raises(ValueError, match="entry pool not found"):
        gw.resolve_route_for_connect(target_host="example.com:443", headers={}, connection_id="conn-1")


def test_resolve_route_connect_with_endpoint_success():
    endpoint = {"id": 20, "hops": [{"pool_id": 7}]}
    storage = FakeStorage(endpoints={20: endpoint})
    gw = _gateway(pool_id=7, endpoint_id=20, storage=storage,
                  pool_service=FakePoolService(pool={"id": 7}))
    route = gw.resolve_route_for_connect(
        target_host="example.com:443",
        headers={"X-ProxyPool-Session": "sess-c"},
        connection_id="conn-1",
    )
    assert route["instance"]["instance_id"] == "inst-1"


# --- report_route_success ---

def test_report_route_success_with_endpoint():
    gw = _gateway()
    gw.report_route_success({
        "endpoint": {"id": 10},
        "route": {"hop_node_keys": ["a", "b"]},
    })
    # Should not raise; report_endpoint_route_success was called


def test_report_route_success_without_endpoint():
    gw = _gateway()
    gw.report_route_success({"endpoint": None, "route": {}})
    # Should not raise


# --- report_route_failure ---

def test_report_route_failure_with_instance():
    gw = _gateway()
    gw.chain_instance_manager.mark_instance_failed = lambda iid, err: None
    gw.report_route_failure({
        "endpoint": {"id": 10},
        "pool": {"id": 7},
        "session_id": "s1",
        "route": {"hop_node_keys": ["x"]},
        "instance": {"instance_id": "inst-99"},
    }, error="boom")


def test_report_route_failure_without_endpoint():
    gw = _gateway()
    gw.report_route_failure({"route": {"pool_id": 7}}, error="fail")
