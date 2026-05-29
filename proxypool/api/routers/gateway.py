"""
HTTP 网关管理路由
"""

import contextlib
import time
import uuid
from dataclasses import asdict

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from proxypool.api.dependencies import StorageDep
from proxypool.api.schemas import (
    HttpGatewayConfigRequest,
    HttpGatewayTestRequest,
    HttpProxyEndpointCreateRequest,
    HttpProxyEndpointServiceConfigRequest,
    HttpProxyEndpointUpdateRequest,
)

router = APIRouter(prefix="/api", tags=["网关"])


@router.get(
    "/gateway/http-config",
    summary="获取HTTP网关配置",
    description="返回当前HTTP网关的配置信息",
    response_description="网关配置详情",
)
async def get_http_gateway_config(request: Request) -> dict:
    """获取 HTTP 网关配置"""
    return {"item": asdict(request.app.state.gateway_config_service.get_config())}


@router.put(
    "/gateway/http-config",
    summary="更新HTTP网关配置",
    description="更新HTTP网关配置并可选地重启网关服务",
    response_description="更新后的配置",
)
async def update_http_gateway_config(
    body: HttpGatewayConfigRequest,
    request: Request,
    storage: StorageDep,
) -> dict:
    """更新 HTTP 网关配置"""
    gateway_config_service = request.app.state.gateway_config_service
    forward_gateway = request.app.state.forward_gateway
    gateway_runtime = request.app.state.gateway_runtime
    chain_service = request.app.state.chain_service

    update_data = body.model_dump(exclude_unset=True)
    item = gateway_config_service.update_config(**update_data)
    forward_gateway.config = item
    endpoint = storage.get_http_proxy_endpoint(int(item.endpoint_id or 0))
    chain_service.sticky_router.sticky_ttl_sec = int(
        endpoint.get("sticky_ttl_sec") if endpoint is not None else item.sticky_ttl_sec
    )
    if item.enabled:
        with contextlib.suppress(Exception):
            await gateway_runtime.start()
    else:
        await gateway_runtime.stop()
    return {"item": asdict(item)}


@router.get(
    "/gateway/http-status",
    summary="获取HTTP网关状态",
    description="返回HTTP网关的运行状态和端点信息",
    response_description="网关状态详情",
)
async def get_http_gateway_status(
    request: Request,
    endpoint_id: int = Query(default=0, ge=0),
) -> dict:
    """获取 HTTP 网关状态"""
    from proxypool.api.gateway_helpers import build_endpoint_status_response

    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime
    config = gateway_config_service.get_config()
    resolved_endpoint_id = int(endpoint_id or config.endpoint_id or 0)
    endpoint = (
        storage.get_http_proxy_endpoint(resolved_endpoint_id) if resolved_endpoint_id > 0 else None
    )
    runtime = gateway_runtime.status()

    # Find the specific endpoint runtime from the list
    endpoint_runtime = None
    for item in list(runtime.get("items") or []):
        if int(item.get("endpoint_id") or 0) == resolved_endpoint_id:
            endpoint_runtime = item
            break

    # Build detailed status with hop pools and transitions if endpoint exists
    detail: dict = {}
    if resolved_endpoint_id > 0 and endpoint is not None:
        chain_service = request.app.state.chain_service
        chain_instance_manager = request.app.state.chain_instance_manager
        detail = build_endpoint_status_response(
            storage=storage,
            chain_service=chain_service,
            chain_instance_manager=chain_instance_manager,
            endpoint_id=resolved_endpoint_id,
        )

    return {
        "config": asdict(config),
        "endpoint": endpoint,
        "item": endpoint,
        "endpoint_id": resolved_endpoint_id,
        "endpoint_runtime": endpoint_runtime,
        "runtime": runtime,
        "leases": detail.get("leases", []),
        "instances": detail.get("instances", []),
        "active_hop_node_keys": detail.get("active_hop_node_keys", []),
        "hop_pools": detail.get("hop_pools", []),
        "transitions": detail.get("transitions", []),
        "summary": detail.get("summary", {
            "endpoint_id": resolved_endpoint_id,
            "hop_count": 0,
            "available": bool(endpoint_runtime and endpoint_runtime.get("running")),
            "degraded": False,
            "healthy_hop_pools": 0,
            "total_hop_pools": 0,
            "healthy_transitions": 0,
            "total_transitions": 0,
        }),
    }


@router.post(
    "/gateway/http-health-check",
    summary="运行HTTP网关健康检查",
    description="检查HTTP网关和所有端点的健康状态",
    response_description="健康检查结果",
)
async def run_http_gateway_health_check(request: Request) -> dict:
    """运行 HTTP 网关健康检查"""
    gateway_runtime = request.app.state.gateway_runtime
    status = gateway_runtime.status()

    # Check if gateway is running and healthy
    is_running = bool(status.get("running"))
    last_error = str(status.get("last_error") or "")

    # Check endpoint health
    endpoints = status.get("items", [])
    healthy_endpoints = sum(1 for ep in endpoints if bool(ep.get("running")))
    total_endpoints = len(endpoints)

    health_status = "healthy" if is_running and not last_error else "unhealthy"
    if is_running and healthy_endpoints < total_endpoints:
        health_status = "degraded"

    return {
        "item": {
            "status": health_status,
            "running": is_running,
            "last_error": last_error,
            "endpoints": {
                "total": total_endpoints,
                "healthy": healthy_endpoints,
            },
        }
    }


@router.post(
    "/gateway/http-test",
    summary="运行HTTP网关测试",
    description="通过网关发送测试请求到指定URL",
    response_description="测试结果详情",
)
async def run_http_gateway_test(
    body: HttpGatewayTestRequest,
    request: Request,
    storage: StorageDep,
) -> dict:
    """运行 HTTP 网关测试"""
    gateway_config_service = request.app.state.gateway_config_service
    forward_gateway = request.app.state.forward_gateway

    target = body.target_url.strip()
    if not target:
        raise HTTPException(status_code=400, detail="target_url is required")
    if body.endpoint_id > 0:
        current = gateway_config_service.get_config()
        if int(current.endpoint_id or 0) != body.endpoint_id:
            updated = gateway_config_service.update_config(endpoint_id=body.endpoint_id)
            forward_gateway.config = updated
    headers = {}
    if body.session_id:
        headers["X-ProxyPool-Session"] = body.session_id
    else:
        configured_endpoint_id = int(
            body.endpoint_id or forward_gateway.config.endpoint_id or 0
        )
        endpoint_for_policy = (
            storage.get_http_proxy_endpoint(configured_endpoint_id)
            if configured_endpoint_id > 0
            else None
        )
        missing_action = str(
            (endpoint_for_policy or {}).get("session_missing_action")
            or forward_gateway.config.session_missing_action
            or "RANDOM"
        ).upper()
        if missing_action != "REJECT":
            headers["X-ProxyPool-Session"] = f"gateway-test:{uuid.uuid4().hex}"
    try:
        route = forward_gateway.resolve_route_for_http(target, headers=headers)
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}
    endpoint = route.get("endpoint") or {}
    endpoint_id = int(endpoint.get("id") or 0)
    proxy_host = str(
        endpoint.get("listen_host") or forward_gateway.config.listen_host or "127.0.0.1"
    )
    proxy_port = int(endpoint.get("listen_port") or forward_gateway.config.listen_port or 0)
    if proxy_port <= 0:
        return {
            "ok": False,
            "detail": "gateway listen port is not configured",
            "session_id": route["session_id"],
            "endpoint_id": endpoint_id,
            "instance_id": route["instance"]["instance_id"],
            "target_host": route["target"].netloc,
            "hop_node_keys": list(route["route"].get("hop_node_keys") or []),
            "route_signature": str(route["route"].get("route_signature") or ""),
        }
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    import proxypool.api.app as api_app

    request_result = await api_app._request_via_forward_proxy(
        target, proxy_url=proxy_url, proxy_headers=headers
    )
    request_ok = bool(request_result.get("request_ok"))
    status_code = int(request_result.get("status_code") or 0)
    if not request_ok:
        error_detail = str(
            request_result.get("error") or request_result.get("error_type") or "request failed"
        )
        with contextlib.suppress(Exception):
            forward_gateway.report_route_failure(route, error_detail)
    else:
        with contextlib.suppress(Exception):
            forward_gateway.report_route_success(route)
    return {
        "ok": bool(request_ok and (status_code == 0 or status_code < 500)),
        "detail": "request succeeded"
        if request_ok
        else str(request_result.get("error") or "request failed"),
        "session_id": route["session_id"],
        "endpoint_id": endpoint_id,
        "proxy_url": proxy_url,
        "instance_id": route["instance"]["instance_id"],
        "target_host": route["target"].netloc,
        "hop_node_keys": list(route["route"].get("hop_node_keys") or []),
        "route_signature": str(route["route"].get("route_signature") or ""),
        "request": request_result,
    }


@router.get("/http-proxy-endpoints")
async def list_http_proxy_endpoints(request: Request) -> dict:
    """获取 HTTP 代理端点列表"""
    storage = request.app.state.storage
    return {"items": storage.list_http_proxy_endpoints()}


@router.get("/http-proxy-endpoints/service-config")
async def get_http_proxy_endpoint_service_config(request: Request) -> dict:
    """获取 HTTP 代理端点服务配置"""
    config = request.app.state.gateway_config_service.get_config()
    return {
        "item": {
            "enabled": bool(config.enabled),
            "health_check_enabled": bool(config.health_check_enabled),
            "health_check_interval_sec": int(config.health_check_interval_sec),
        }
    }


@router.put("/http-proxy-endpoints/service-config")
async def update_http_proxy_endpoint_service_config(
    body: HttpProxyEndpointServiceConfigRequest,
    request: Request,
) -> dict:
    """更新 HTTP 代理端点服务配置"""
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime
    forward_gateway = request.app.state.forward_gateway

    item = gateway_config_service.update_config(
        enabled=body.enabled,
        endpoint_id=0,
        default_pool_id=0,
        health_check_enabled=body.health_check_enabled,
        health_check_interval_sec=body.health_check_interval_sec,
    )
    forward_gateway.config = item
    if item.enabled:
        with contextlib.suppress(Exception):
            await gateway_runtime.start()
    else:
        await gateway_runtime.stop()
    return {
        "item": {
            "enabled": bool(item.enabled),
            "health_check_enabled": bool(item.health_check_enabled),
            "health_check_interval_sec": int(item.health_check_interval_sec),
        }
    }


@router.post("/http-proxy-endpoints")
async def create_http_proxy_endpoint(
    body: HttpProxyEndpointCreateRequest,
    request: Request,
) -> dict:
    """创建 HTTP 代理端点"""
    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime
    try:
        item = storage.create_http_proxy_endpoint(
            name=body.name,
            listen_host=body.listen_host,
            listen_port=body.listen_port,
            inbound_type=body.inbound_type,
            enabled=body.enabled,
            sticky_ttl_sec=body.sticky_ttl_sec,
            session_missing_action=body.session_missing_action,
            session_header_names=body.session_header_names,
            session_query_param_names=body.session_query_param_names,
            connect_session_header_names=body.connect_session_header_names,
        )
        if body.hop_pool_ids:
            storage.replace_http_proxy_endpoint_hops(int(item["id"]), list(body.hop_pool_ids))
            item = storage.get_http_proxy_endpoint(int(item["id"])) or item
        if gateway_config_service.get_config().enabled:
            with contextlib.suppress(Exception):
                await gateway_runtime.sync()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.get("/http-proxy-endpoints/{endpoint_id}")
async def get_http_proxy_endpoint(
    endpoint_id: int,
    request: Request,
) -> dict:
    """获取 HTTP 代理端点详情"""
    storage = request.app.state.storage
    item = storage.get_http_proxy_endpoint(endpoint_id)
    if item is None:
        raise HTTPException(status_code=404, detail="http proxy endpoint not found")
    return {"item": item}


@router.put("/http-proxy-endpoints/{endpoint_id}")
async def update_http_proxy_endpoint(
    endpoint_id: int,
    body: HttpProxyEndpointUpdateRequest,
    request: Request,
) -> dict:
    """更新 HTTP 代理端点"""
    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime

    payload = body.model_dump(exclude_unset=True)
    hop_pool_ids = payload.pop("hop_pool_ids", None)
    try:
        item = storage.update_http_proxy_endpoint(endpoint_id, **payload)
        if hop_pool_ids is not None:
            storage.replace_http_proxy_endpoint_hops(endpoint_id, list(hop_pool_ids))
            item = storage.get_http_proxy_endpoint(endpoint_id) or item
        if gateway_config_service.get_config().enabled:
            with contextlib.suppress(Exception):
                await gateway_runtime.sync()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.delete("/http-proxy-endpoints/{endpoint_id}")
async def delete_http_proxy_endpoint(
    endpoint_id: int,
    request: Request,
) -> dict:
    """删除 HTTP 代理端点"""
    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime

    deleted = storage.delete_http_proxy_endpoint(endpoint_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="http proxy endpoint not found")
    if gateway_config_service.get_config().enabled:
        with contextlib.suppress(Exception):
            await gateway_runtime.sync()
    return {"deleted": deleted}


@router.get("/http-proxy-endpoints/{endpoint_id}/route-test")
async def http_proxy_endpoint_route_test(
    endpoint_id: int,
    request: Request,
    session_id: str = "",
    target_domain: str = "",
) -> dict:
    """测试 HTTP 代理端点路由"""
    storage = request.app.state.storage
    chain_service = request.app.state.chain_service
    chain_instance_manager = request.app.state.chain_instance_manager

    item = storage.get_http_proxy_endpoint(endpoint_id)
    if item is None:
        raise HTTPException(status_code=404, detail="http proxy endpoint not found")
    hops = list(item.get("hops") or [])
    if not hops:
        raise HTTPException(status_code=400, detail="endpoint hops are empty")
    entry_pool_id = int(hops[0].get("pool_id") or 0)
    chain_service.initialize()
    result = chain_service.route_request(
        session_id=session_id,
        pool_id=entry_pool_id,
        endpoint_id=endpoint_id,
        target_domain=target_domain,
        live_instance_ids=chain_instance_manager.list_running_instance_ids(
            pool_id=entry_pool_id,
            endpoint_id=endpoint_id,
        ),
    )
    if result is None:
        raise HTTPException(status_code=503, detail="No available nodes for routing")
    return result


@router.get("/http-proxy-endpoints/{endpoint_id}/status")
async def http_proxy_endpoint_status(
    endpoint_id: int,
    request: Request,
) -> dict:
    """获取 HTTP 代理端点状态"""
    from proxypool.api.gateway_helpers import build_endpoint_status_response

    storage = request.app.state.storage
    item = storage.get_http_proxy_endpoint(endpoint_id)
    if item is None:
        raise HTTPException(status_code=404, detail="http proxy endpoint not found")
    chain_service = request.app.state.chain_service
    chain_instance_manager = request.app.state.chain_instance_manager
    return build_endpoint_status_response(
        storage=storage,
        chain_service=chain_service,
        chain_instance_manager=chain_instance_manager,
        endpoint_id=endpoint_id,
    )


@router.get("/gateway/endpoints/{endpoint_id}/health")
async def get_endpoint_health(
    endpoint_id: int,
    request: Request,
) -> dict:
    """获取网关端点详细健康状态"""
    storage = request.app.state.storage
    gateway_runtime = request.app.state.gateway_runtime

    item = storage.get_http_proxy_endpoint(endpoint_id)
    if item is None:
        raise HTTPException(status_code=404, detail="http proxy endpoint not found")

    # Get gateway runtime status
    runtime_status = gateway_runtime.status()
    endpoint_errors: list[dict] = []

    # Check if this endpoint is running in the gateway
    for ep in runtime_status.get("items", []):
        if int(ep.get("id") or 0) == endpoint_id:
            endpoint_errors = list(ep.get("recent_errors") or [])
            break

    # Get active leases for this endpoint
    chain_instance_manager = request.app.state.chain_instance_manager
    active_leases: list[dict] = []
    upstream_pool_status: dict = {}

    hops = list(item.get("hops") or [])
    if hops:
        entry_pool_id = int(hops[0].get("pool_id") or 0)
        if entry_pool_id > 0:
            # Get upstream pool info
            pool = storage.get_proxy_pool(entry_pool_id)
            if pool:
                pool_candidates = storage.list_proxy_pool_candidates(entry_pool_id)
                available_count = sum(1 for c in pool_candidates if c.get("available"))
                upstream_pool_status = {
                    "pool_id": entry_pool_id,
                    "pool_name": pool.get("name"),
                    "total_candidates": len(pool_candidates),
                    "available_candidates": available_count,
                    "status": pool.get("status", "stopped"),
                }

            # Get leases from chain instances
            instances = chain_instance_manager.list_instances(pool_id=entry_pool_id)
            for inst in instances:
                if inst.get("status") == "running":
                    leases = storage.list_sticky_leases(pool_id=entry_pool_id)
                    active_leases.extend(
                        [
                            lease
                            for lease in leases
                            if lease.get("instance_id") == inst.get("instance_id")
                        ]
                    )

    # Check port listening status
    is_listening = False
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        result = sock.connect_ex((item.get("listen_host", "127.0.0.1"), item.get("listen_port", 0)))
        is_listening = result == 0
        sock.close()
    except Exception:
        pass

    return {
        "endpoint_id": endpoint_id,
        "name": item.get("name", ""),
        "listen_host": item.get("listen_host", ""),
        "listen_port": item.get("listen_port", 0),
        "enabled": bool(item.get("enabled")),
        "is_listening": is_listening,
        "total_connections": len(active_leases),
        "active_connections": sum(
            1 for lease in active_leases if lease.get("expires_at", 0) > time.time()
        ),
        "recent_errors": endpoint_errors[-10:],
        "active_leases": active_leases[:20],
        "upstream_pool_status": upstream_pool_status,
        "last_health_check": runtime_status.get("last_health_check"),
        "health_check_enabled": bool(item.get("health_check_enabled", True)),
    }


@router.post("/gateway/endpoints/{endpoint_id}/test-connectivity")
async def test_endpoint_connectivity(
    endpoint_id: int,
    request: Request,
) -> dict:
    """测试网关端点连通性"""
    storage = request.app.state.storage

    item = storage.get_http_proxy_endpoint(endpoint_id)
    if item is None:
        raise HTTPException(status_code=404, detail="http proxy endpoint not found")

    listen_host = item.get("listen_host", "127.0.0.1")
    listen_port = item.get("listen_port", 0)
    tested_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if listen_port <= 0:
        return {
            "endpoint_id": endpoint_id,
            "listen_host": listen_host,
            "listen_port": listen_port,
            "is_reachable": False,
            "latency_ms": None,
            "error": "Port not configured",
            "tested_at": tested_at,
            "connection_test": False,
            "http_test": False,
        }

    # Test TCP connection
    connection_test = False
    latency_ms = None
    error = None
    try:
        import socket

        start_time = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect((listen_host, listen_port))
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        connection_test = True
        sock.close()
    except Exception as exc:
        error = str(exc)

    # Test HTTP connectivity if connection succeeded
    http_test = False
    if connection_test:
        try:
            proxy_url = f"http://{listen_host}:{listen_port}"
            async with httpx.AsyncClient(
                proxy=proxy_url,
                timeout=httpx.Timeout(5.0),
                trust_env=False,
            ) as client:
                await client.get(
                    "http://127.0.0.1:1",
                    headers={"User-Agent": "proxypool-connectivity-test/1.0"},
                )
                # Any response (even error) means the proxy is working
                http_test = True
        except Exception:
            # HTTP test failure is acceptable - proxy might reject the request
            http_test = connection_test

    return {
        "endpoint_id": endpoint_id,
        "listen_host": listen_host,
        "listen_port": listen_port,
        "is_reachable": connection_test,
        "latency_ms": latency_ms,
        "error": error,
        "tested_at": tested_at,
        "connection_test": connection_test,
        "http_test": http_test,
    }


@router.get("/gateway/port-conflicts")
async def check_port_conflicts(
    request: Request,
) -> dict:
    """检测端口冲突"""
    storage = request.app.state.storage
    singbox_manager = request.app.state.singbox_manager

    # Collect all port usages
    port_usages: dict[int, list[dict]] = {}

    # Check HTTP proxy endpoints
    endpoints = storage.list_http_proxy_endpoints()
    for ep in endpoints:
        port = int(ep.get("listen_port") or 0)
        if port > 0:
            if port not in port_usages:
                port_usages[port] = []
            port_usages[port].append(
                {
                    "type": "endpoint",
                    "id": ep.get("id"),
                    "name": ep.get("name"),
                    "host": ep.get("listen_host", "127.0.0.1"),
                }
            )

    # Check backend instances
    instances = singbox_manager.list_instances()
    for inst in instances:
        for port in inst.get("ports") or []:
            port = int(port)
            if port > 0:
                if port not in port_usages:
                    port_usages[port] = []
                port_usages[port].append(
                    {
                        "type": "instance",
                        "id": inst.get("instance_id"),
                        "name": inst.get("instance_id"),
                        "host": inst.get("listen", "127.0.0.1"),
                    }
                )

    # Find conflicts
    conflicts: list[dict] = []
    for port, sources in port_usages.items():
        if len(sources) > 1:
            # Check if hosts are different or same
            hosts = {s.get("host", "127.0.0.1") for s in sources}
            if len(hosts) == 1 or "0.0.0.0" in hosts:
                # Same host or wildcard - actual conflict
                conflict_type = "endpoint_endpoint"
                if any(s["type"] == "instance" for s in sources):
                    if any(s["type"] == "endpoint" for s in sources):
                        conflict_type = "endpoint_instance"
                    else:
                        conflict_type = "instance_instance"

                conflicts.append(
                    {
                        "port": port,
                        "conflicting_sources": sources,
                        "conflict_type": conflict_type,
                    }
                )

    return {
        "has_conflicts": len(conflicts) > 0,
        "conflicts": conflicts,
        "scanned_endpoints": len(endpoints),
        "scanned_instances": len(instances),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


async def _request_via_forward_proxy(
    target_url: str,
    proxy_url: str,
    proxy_headers: dict[str, str],
    timeout_sec: float = 15.0,
) -> dict:
    """通过代理发送请求"""
    started = time.perf_counter()
    try:
        proxy = httpx.Proxy(proxy_url, headers=proxy_headers or None)
        async with httpx.AsyncClient(
            proxy=proxy, timeout=httpx.Timeout(timeout_sec), trust_env=False
        ) as client:
            resp = await client.get(
                target_url,
                headers={"Accept": "*/*", "User-Agent": "proxypool-gateway-test/1.0"},
            )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        preview = ""
        with contextlib.suppress(Exception):
            preview = resp.text[:2048]
        return {
            "request_ok": True,
            "status_code": int(resp.status_code),
            "elapsed_ms": elapsed_ms,
            "body_preview": preview,
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "request_ok": False,
            "elapsed_ms": elapsed_ms,
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }
