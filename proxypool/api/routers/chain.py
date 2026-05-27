"""
链式代理管理路由

提供链式代理的状态查询、启动、停止、节点管理等端点。
"""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api", tags=["chain"])


@router.get("/chain/status")
async def chain_status(
    request: Request,
) -> dict:
    """获取链式代理状态"""
    chain_service = request.app.state.chain_service
    chain_service.initialize()
    return chain_service.get_pool_status(refresh=True)


@router.get("/chain/health")
async def chain_health(
    request: Request,
) -> dict:
    """获取链式代理健康状态"""
    chain_service = request.app.state.chain_service
    return chain_service.get_health_status()


@router.post("/chain/pools/{pool_type}")
async def create_chain_pool(
    pool_type: str,
    request: Request,
    body: dict = {},
    regex_filters: list[str] = None,
) -> dict:
    """创建链池"""
    chain_service = request.app.state.chain_service
    try:
        result = chain_service.update_pool_config(pool_type=pool_type, regex_filters=regex_filters or [])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/chain/route")
async def get_chain_route(
    request: Request,
    session_id: str = "",
    pool_id: int = 0,
    target_domain: str = "",
) -> dict:
    """获取链式路由"""
    chain_service = request.app.state.chain_service
    chain_service.initialize()
    result = chain_service.route_request(session_id=session_id, pool_id=pool_id, target_domain=target_domain)
    if result is None:
        raise HTTPException(status_code=503, detail="No available nodes for routing")
    return result


@router.get("/chain/leases")
async def list_chain_leases(
    request: Request,
) -> dict:
    """获取链租约列表"""
    chain_instance_manager = request.app.state.chain_instance_manager
    return {"items": chain_instance_manager.list_all_leases()}


@router.post("/chain/leases/cleanup")
async def cleanup_chain_leases(
    request: Request,
    max_age_sec: int = Query(default=3600, ge=60),
) -> dict:
    """清理过期租约"""
    chain_instance_manager = request.app.state.chain_instance_manager
    cleaned = chain_instance_manager.cleanup_expired_leases(max_age_sec=max_age_sec)
    return {"cleaned": cleaned}


@router.post("/chain/start")
async def start_chain(
    request: Request,
) -> dict:
    """启动链式代理"""
    chain_service = request.app.state.chain_service
    try:
        chain_service.start()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "started"}


@router.post("/chain/stop")
async def stop_chain(
    request: Request,
) -> dict:
    """停止链式代理"""
    chain_service = request.app.state.chain_service
    try:
        chain_service.stop()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "stopped"}


@router.get("/chain/nodes")
async def list_chain_nodes(
    request: Request,
) -> dict:
    """获取链节点列表"""
    chain_service = request.app.state.chain_service
    return {"items": chain_service.list_nodes()}
