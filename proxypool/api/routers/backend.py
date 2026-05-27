"""
后端进程管理路由

提供 sing-box 后端进程的状态查询、启动、停止、配置等端点。
"""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api", tags=["backend"])


@router.get("/backend/status")
async def backend_status(
    request: Request,
) -> dict:
    """获取后端状态"""
    singbox_manager = request.app.state.singbox_manager
    return singbox_manager.status()


@router.get("/backend/routes")
async def backend_routes(
    request: Request,
) -> dict:
    """获取后端路由"""
    singbox_manager = request.app.state.singbox_manager
    return {"routes": singbox_manager.status()["routes"]}


@router.get("/backend/default-port-range")
async def backend_default_port_range(request: Request) -> dict:
    """获取默认端口范围"""
    storage = request.app.state.storage
    return storage.get_backend_default_port_range()


@router.put("/backend/default-port-range")
async def backend_set_default_port_range(
    body: dict,
    request: Request,
) -> dict:
    """设置默认端口范围"""
    storage = request.app.state.storage
    try:
        return storage.set_backend_default_port_range(start=body["start"], end=body["end"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/backend/default-listen")
async def backend_default_listen(request: Request) -> dict:
    """获取默认监听配置"""
    storage = request.app.state.storage
    return {"listen": storage.get_backend_default_listen()}


@router.put("/backend/default-listen")
async def backend_set_default_listen(
    body: dict,
    request: Request,
) -> dict:
    """设置默认监听配置"""
    storage = request.app.state.storage
    try:
        return {"listen": storage.set_backend_default_listen(body["listen"])}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/backend/instances")
async def backend_instances(
    request: Request,
) -> dict:
    """获取后端实例列表"""
    singbox_manager = request.app.state.singbox_manager
    return {"items": singbox_manager.list_instances()}


@router.post("/backend/instances")
async def backend_instance_create(
    body: dict,
    request: Request,
) -> dict:
    """创建后端实例"""
    singbox_manager = request.app.state.singbox_manager
    try:
        item = singbox_manager.create_instance(body["instance_id"])
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item, "items": singbox_manager.list_instances()}


@router.post("/backend/instances/{instance_id}/start")
async def backend_instance_start(
    instance_id: str,
    request: Request,
) -> dict:
    """启动后端实例"""
    singbox_manager = request.app.state.singbox_manager
    try:
        singbox_manager.start_instance(instance_id=instance_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return singbox_manager.status()


@router.post("/backend/instances/{instance_id}/stop")
async def backend_instance_stop(
    instance_id: str,
    request: Request,
) -> dict:
    """停止后端实例"""
    singbox_manager = request.app.state.singbox_manager
    singbox_manager.stop_instance(instance_id=instance_id)
    return singbox_manager.status()


@router.get("/backend/instances/{instance_id}/routes")
async def backend_instance_routes(
    instance_id: str,
    request: Request,
) -> dict:
    """获取实例路由"""
    singbox_manager = request.app.state.singbox_manager
    return {
        "instance_id": instance_id,
        "routes": [asdict(route) for route in singbox_manager.get_instance_routes(instance_id)],
    }


@router.post("/backend/instances/{instance_id}/routes")
async def backend_instance_set_routes(
    instance_id: str,
    body: dict,
    request: Request,
) -> dict:
    """设置实例路由"""
    singbox_manager = request.app.state.singbox_manager
    from proxypool.backend.singbox_manager import SingBoxRoute
    routes = [
        SingBoxRoute(
            inbound_port=item["inbound_port"],
            proxy_key=item["proxy_key"],
            front_proxy_key=item.get("front_proxy_key"),
            middle_proxy_key=item.get("middle_proxy_key"),
            exit_proxy_key=item.get("exit_proxy_key"),
            inbound_type=item.get("inbound_type"),
            listen=item.get("listen"),
        )
        for item in body["routes"]
    ]
    try:
        singbox_manager.set_instance_routes(instance_id, routes, auto_restart=body.get("auto_restart", False))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"instance_id": instance_id, "routes": [asdict(route) for route in singbox_manager.get_instance_routes(instance_id)]}


@router.delete("/backend/instances/{instance_id}")
async def backend_instance_delete(
    instance_id: str,
    request: Request,
) -> dict:
    """删除后端实例"""
    singbox_manager = request.app.state.singbox_manager
    return {
        "deleted": singbox_manager.delete_instance(instance_id=instance_id),
        "items": singbox_manager.list_instances(),
    }


@router.get("/backend/latency")
async def backend_latency(
    request: Request,
    timeout_sec: float = Query(default=10.0, ge=1.0, le=60.0),
) -> dict:
    """测量所有路由延迟"""
    singbox_manager = request.app.state.singbox_manager
    return {
        "running": singbox_manager.is_running(),
        "items": singbox_manager.measure_all_routes_latency(timeout_sec=timeout_sec),
    }


@router.get("/backend/process-events")
async def backend_process_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """获取后端进程事件"""
    storage = request.app.state.storage
    return {
        "items": storage.list_backend_process_events(limit=limit),
    }


@router.post("/backend/routes")
async def backend_set_routes(
    body: dict,
    request: Request,
) -> dict:
    """设置全局路由"""
    singbox_manager = request.app.state.singbox_manager
    from proxypool.backend.singbox_manager import SingBoxRoute
    routes = [
        SingBoxRoute(
            inbound_port=item["inbound_port"],
            proxy_key=item["proxy_key"],
            front_proxy_key=item.get("front_proxy_key"),
            middle_proxy_key=item.get("middle_proxy_key"),
            exit_proxy_key=item.get("exit_proxy_key"),
            inbound_type=item.get("inbound_type"),
            listen=item.get("listen"),
        )
        for item in body["routes"]
    ]
    try:
        singbox_manager.set_routes(routes, auto_restart=body.get("auto_restart", False))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"routes": [asdict(route) for route in singbox_manager.get_routes()]}


@router.post("/backend/start")
async def backend_start(
    request: Request,
) -> dict:
    """启动后端"""
    singbox_manager = request.app.state.singbox_manager
    try:
        singbox_manager.start()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return singbox_manager.status()


@router.post("/backend/stop")
async def backend_stop(
    request: Request,
) -> dict:
    """停止后端"""
    singbox_manager = request.app.state.singbox_manager
    singbox_manager.stop()
    return singbox_manager.status()


@router.post("/backend/restart")
async def backend_restart(
    request: Request,
) -> dict:
    """重启后端"""
    singbox_manager = request.app.state.singbox_manager
    try:
        singbox_manager.restart()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return singbox_manager.status()
