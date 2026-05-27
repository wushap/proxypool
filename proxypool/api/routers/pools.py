"""
代理池管理路由

提供代理池的查询、创建、更新、删除、启动、停止等端点。
"""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api", tags=["pools"])


@router.get("/pools")
async def list_pools(
    request: Request,
) -> dict:
    """获取代理池列表"""
    pool_service = request.app.state.pool_service
    return {"items": pool_service.list_pools()}


@router.post("/pools")
async def create_pool(
    body: dict,
    request: Request,
) -> dict:
    """创建代理池"""
    pool_service = request.app.state.pool_service
    try:
        item = pool_service.create_pool(
            name=body["name"],
            filters=body.get("filters"),
            listen=body.get("listen"),
            inbound_type=body.get("inbound_type"),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.get("/pools/{pool_id}")
async def get_pool(
    pool_id: int,
    request: Request,
) -> dict:
    """获取代理池详情"""
    pool_service = request.app.state.pool_service
    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")
    return {"item": item}


@router.put("/pools/{pool_id}")
async def update_pool(
    pool_id: int,
    body: dict,
    request: Request,
) -> dict:
    """更新代理池"""
    pool_service = request.app.state.pool_service
    try:
        item = pool_service.update_pool(pool_id, **{k: v for k, v in body.items() if v is not None})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.delete("/pools/{pool_id}")
async def delete_pool(
    pool_id: int,
    request: Request,
) -> dict:
    """删除代理池"""
    pool_service = request.app.state.pool_service
    deleted = pool_service.delete_pool(pool_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="pool not found")
    return {"deleted": deleted}


@router.post("/pools/{pool_id}/sync")
async def sync_pool(
    pool_id: int,
    request: Request,
) -> dict:
    """同步代理池"""
    pool_service = request.app.state.pool_service
    try:
        item = pool_service.sync_pool(pool_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.post("/pools/{pool_id}/start")
async def start_pool(
    pool_id: int,
    request: Request,
) -> dict:
    """启动代理池"""
    pool_service = request.app.state.pool_service
    try:
        item = pool_service.start_pool(pool_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.post("/pools/{pool_id}/stop")
async def stop_pool(
    pool_id: int,
    request: Request,
) -> dict:
    """停止代理池"""
    pool_service = request.app.state.pool_service
    try:
        item = pool_service.stop_pool(pool_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.get("/pools/{pool_id}/chain")
async def get_pool_chain(
    pool_id: int,
    request: Request,
) -> dict:
    """获取代理池链配置"""
    pool_service = request.app.state.pool_service
    item = pool_service.get_pool_chain_config(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")
    return {"item": item}


@router.put("/pools/{pool_id}/chain")
async def update_pool_chain(
    pool_id: int,
    body: dict,
    request: Request,
) -> dict:
    """更新代理池链配置"""
    pool_service = request.app.state.pool_service
    try:
        item = pool_service.update_pool_chain_config(pool_id, **{k: v for k, v in body.items() if v is not None})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"item": item}


@router.put("/pools/{pool_id}/chain/session-rules/{url_prefix:path}")
async def upsert_pool_chain_session_rule(
    pool_id: int,
    url_prefix: str,
    body: dict,
    request: Request,
) -> dict:
    """更新会话规则"""
    pool_service = request.app.state.pool_service
    try:
        item = pool_service.upsert_pool_session_rule(pool_id, url_prefix=url_prefix, headers=body.get("headers"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"item": item}


@router.get("/pools/{pool_id}/chain/session-rules")
async def list_pool_chain_session_rules(
    pool_id: int,
    request: Request,
) -> dict:
    """获取会话规则列表"""
    pool_service = request.app.state.pool_service
    try:
        items = pool_service.list_pool_session_rules(pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"items": items}


@router.delete("/pools/{pool_id}/chain/session-rules/{url_prefix:path}")
async def delete_pool_chain_session_rule(
    pool_id: int,
    url_prefix: str,
    request: Request,
) -> dict:
    """删除会话规则"""
    pool_service = request.app.state.pool_service
    try:
        deleted = pool_service.delete_pool_session_rule(pool_id, url_prefix=url_prefix)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="session rule not found")
    return {"deleted": True}


@router.get("/pools/{pool_id}/chain/route-test")
async def pool_chain_route_test(
    pool_id: int,
    request: Request,
    session_id: str = "",
    target_domain: str = "",
) -> dict:
    """测试链式路由"""
    pool_service = request.app.state.pool_service
    chain_service = request.app.state.chain_service
    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")
    chain_service.initialize()
    result = chain_service.route_request(session_id=session_id, pool_id=pool_id, target_domain=target_domain)
    if result is None:
        raise HTTPException(status_code=503, detail="No available nodes for routing")
    return result


@router.get("/pools/{pool_id}/chain/instances")
async def list_pool_chain_instances(
    pool_id: int,
    request: Request,
) -> dict:
    """获取链实例列表"""
    pool_service = request.app.state.pool_service
    chain_instance_manager = request.app.state.chain_instance_manager
    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")
    return {"items": chain_instance_manager.list_instances(pool_id=pool_id)}


@router.post("/pools/{pool_id}/chain/instances")
async def create_pool_chain_instance(
    pool_id: int,
    body: dict,
    request: Request,
) -> dict:
    """创建链实例"""
    pool_service = request.app.state.pool_service
    chain_instance_manager = request.app.state.chain_instance_manager
    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")
    try:
        instance = chain_instance_manager.create_instance(
            instance_id=body["instance_id"],
            pool_id=pool_id,
            front_node_key=body["front_node_key"],
            exit_node_key=body["exit_node_key"],
            listen=body.get("listen", "127.0.0.1"),
            port=body.get("port", 0),
            inbound_type=body.get("inbound_type", "http"),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": instance}


@router.post("/pools/{pool_id}/chain/instances/{instance_id}/start")
async def start_pool_chain_instance(
    pool_id: int,
    instance_id: str,
    request: Request,
) -> dict:
    """启动链实例"""
    chain_instance_manager = request.app.state.chain_instance_manager
    try:
        chain_instance_manager.start_instance(instance_id=instance_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "started"}


@router.post("/pools/{pool_id}/chain/instances/{instance_id}/stop")
async def stop_pool_chain_instance(
    pool_id: int,
    instance_id: str,
    request: Request,
) -> dict:
    """停止链实例"""
    chain_instance_manager = request.app.state.chain_instance_manager
    try:
        chain_instance_manager.stop_instance(instance_id=instance_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "stopped"}


@router.post("/pools/{pool_id}/chain/instances/{instance_id}/rebuild")
async def rebuild_pool_chain_instance(
    pool_id: int,
    instance_id: str,
    request: Request,
) -> dict:
    """重建链实例"""
    chain_instance_manager = request.app.state.chain_instance_manager
    try:
        chain_instance_manager.rebuild_instance(instance_id=instance_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "rebuilt"}


@router.get("/pools/{pool_id}/chain/leases")
async def list_pool_chain_leases(
    pool_id: int,
    request: Request,
) -> dict:
    """获取租约列表"""
    storage = request.app.state.storage
    pool_service = request.app.state.pool_service
    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")
    return {"items": storage.list_sticky_leases(pool_id=pool_id)}


@router.delete("/pools/{pool_id}/chain/leases/{session_id}")
async def delete_pool_chain_lease(
    pool_id: int,
    session_id: str,
    request: Request,
) -> dict:
    """删除租约"""
    chain_instance_manager = request.app.state.chain_instance_manager
    try:
        deleted = chain_instance_manager.delete_lease(session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted": deleted}


@router.post("/pools/{pool_id}/chain/leases/inherit")
async def inherit_pool_chain_lease(
    pool_id: int,
    body: dict,
    request: Request,
) -> dict:
    """继承租约"""
    pool_service = request.app.state.pool_service
    chain_instance_manager = request.app.state.chain_instance_manager
    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")
    try:
        lease = chain_instance_manager.inherit_lease(
            pool_id=pool_id,
            source_session_id=body.get("from_session_id"),
            target_session_id=body.get("to_session_id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": lease}
