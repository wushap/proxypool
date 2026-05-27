"""
HTTP 网关管理路由
"""

import contextlib
import hashlib
import time
import uuid
from dataclasses import asdict

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from proxypool.api.dependencies import StorageDep

router = APIRouter(prefix="/api", tags=["gateway"])


@router.get("/gateway/http-config")
async def get_http_gateway_config(request: Request) -> dict:
    """获取 HTTP 网关配置"""
    return {"item": asdict(request.app.state.gateway_config_service.get_config())}


@router.put("/gateway/http-config")
async def update_http_gateway_config(
    body: dict,
    request: Request,
    storage: StorageDep,
) -> dict:
    """更新 HTTP 网关配置"""
    gateway_config_service = request.app.state.gateway_config_service
    forward_gateway = request.app.state.forward_gateway
    gateway_runtime = request.app.state.gateway_runtime
    chain_service = request.app.state.chain_service

    item = gateway_config_service.update_config(**body)
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


@router.get("/gateway/http-status")
async def get_http_gateway_status(
    request: Request,
    endpoint_id: int = Query(default=0, ge=0),
) -> dict:
    """获取 HTTP 网关状态"""
    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime
    config = gateway_config_service.get_config()
    resolved_endpoint_id = int(endpoint_id or config.endpoint_id or 0)
    endpoint = storage.get_http_proxy_endpoint(resolved_endpoint_id) if resolved_endpoint_id > 0 else None
    return {
        "config": asdict(config),
        "endpoint": endpoint,
        "endpoint_id": resolved_endpoint_id,
        "runtime": gateway_runtime.status(),
    }


@router.post("/gateway/http-health-check")
async def run_http_gateway_health_check() -> dict:
    """运行 HTTP 网关健康检查"""
    return {"item": {"status": "not implemented"}}


@router.post("/gateway/http-test")
async def run_http_gateway_test(
    body: dict,
    request: Request,
    storage: StorageDep,
) -> dict:
    """运行 HTTP 网关测试"""
    gateway_config_service = request.app.state.gateway_config_service
    forward_gateway = request.app.state.forward_gateway

    target = str(body.get("target_url") or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="target_url is required")
    if int(body.get("endpoint_id") or 0) > 0:
        current = gateway_config_service.get_config()
        if int(current.endpoint_id or 0) != int(body["endpoint_id"]):
            updated = gateway_config_service.update_config(endpoint_id=int(body["endpoint_id"]))
            forward_gateway.config = updated
    headers = {}
    if body.get("session_id"):
        headers["X-ProxyPool-Session"] = body["session_id"]
    else:
        configured_endpoint_id = int(body.get("endpoint_id") or forward_gateway.config.endpoint_id or 0)
        endpoint_for_policy = storage.get_http_proxy_endpoint(configured_endpoint_id) if configured_endpoint_id > 0 else None
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
    proxy_host = str(endpoint.get("listen_host") or forward_gateway.config.listen_host or "127.0.0.1")
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
    request_result = await api_app._request_via_forward_proxy(target, proxy_url=proxy_url, proxy_headers=headers)
    request_ok = bool(request_result.get("request_ok"))
    status_code = int(request_result.get("status_code") or 0)
    if not request_ok:
        error_detail = str(request_result.get("error") or request_result.get("error_type") or "request failed")
        with contextlib.suppress(Exception):
            forward_gateway.report_route_failure(route, error_detail)
    else:
        with contextlib.suppress(Exception):
            forward_gateway.report_route_success(route)
    return {
        "ok": bool(request_ok and (status_code == 0 or status_code < 500)),
        "detail": "request succeeded" if request_ok else str(request_result.get("error") or "request failed"),
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
    body: dict,
    request: Request,
) -> dict:
    """更新 HTTP 代理端点服务配置"""
    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime
    forward_gateway = request.app.state.forward_gateway

    item = gateway_config_service.update_config(
        enabled=body.get("enabled"),
        endpoint_id=0,
        default_pool_id=0,
        health_check_enabled=body.get("health_check_enabled"),
        health_check_interval_sec=body.get("health_check_interval_sec"),
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
    body: dict,
    request: Request,
) -> dict:
    """创建 HTTP 代理端点"""
    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime
    try:
        item = storage.create_http_proxy_endpoint(
            name=body.get("name"),
            listen_host=body.get("listen_host", "127.0.0.1"),
            listen_port=body.get("listen_port", 8899),
            inbound_type=body.get("inbound_type", "http"),
            enabled=body.get("enabled", True),
            sticky_ttl_sec=body.get("sticky_ttl_sec", 3600),
            session_missing_action=body.get("session_missing_action", "RANDOM"),
            session_header_names=body.get("session_header_names"),
            session_query_param_names=body.get("session_query_param_names"),
            connect_session_header_names=body.get("connect_session_header_names"),
        )
        if body.get("hop_pool_ids"):
            storage.replace_http_proxy_endpoint_hops(int(item["id"]), list(body["hop_pool_ids"]))
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
    body: dict,
    request: Request,
) -> dict:
    """更新 HTTP 代理端点"""
    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime

    payload = {k: v for k, v in body.items() if v is not None}
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
        async with httpx.AsyncClient(proxy=proxy, timeout=httpx.Timeout(timeout_sec), trust_env=False) as client:
            resp = await client.get(
                target_url,
                headers={"Accept": "*/*", "User-Agent": "proxypool-gateway-test/1.0"},
            )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        preview = ""
        with contextlib.suppress(Exception):
            preview = resp.text[:2048]
        return {"request_ok": True, "status_code": int(resp.status_code), "elapsed_ms": elapsed_ms, "body_preview": preview}
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {"request_ok": False, "elapsed_ms": elapsed_ms, "error_type": exc.__class__.__name__, "error": str(exc)}
