"""
链式代理管理路由

提供链式代理的状态查询、启动、停止、节点管理等端点。
"""

from fastapi import APIRouter, HTTPException, Query, Request

from proxypool.api.schemas import ChainDiagnosticsResponse

router = APIRouter(prefix="/api", tags=["链路"])


@router.get(
    "/chain/status",
    summary="获取链式代理状态",
    description="返回链式代理的池状态和健康信息",
    response_description="链式代理状态",
)
async def chain_status(
    request: Request,
) -> dict:
    """获取链式代理状态"""
    chain_service = request.app.state.chain_service
    chain_service.initialize()
    return chain_service.get_pool_status(refresh=True)


@router.get(
    "/chain/health",
    summary="获取链式代理健康状态",
    description="返回链式代理的健康检查结果",
    response_description="健康状态详情",
)
async def chain_health(
    request: Request,
) -> dict:
    """获取链式代理健康状态"""
    chain_service = request.app.state.chain_service
    return chain_service.get_health_status()


@router.post(
    "/chain/pools/{pool_type}",
    summary="创建或更新链池",
    description="创建或更新指定类型的链池配置",
    response_description="链池配置结果",
)
async def create_chain_pool(
    pool_type: str,
    request: Request,
    body: dict | None = None,
    regex_filters: list[str] | None = None,
) -> dict:
    """创建链池"""
    if body is None:
        body = {}
    chain_service = request.app.state.chain_service
    try:
        result = chain_service.update_pool_config(
            pool_type=pool_type, regex_filters=regex_filters or []
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get(
    "/chain/route",
    summary="获取链式路由",
    description="根据会话ID、池ID和目标域名获取链式代理路由",
    response_description="路由信息",
)
async def get_chain_route(
    request: Request,
    session_id: str = "",
    pool_id: int = 0,
    target_domain: str = "",
) -> dict:
    """获取链式路由"""
    chain_service = request.app.state.chain_service
    chain_service.initialize()
    result = chain_service.route_request(
        session_id=session_id, pool_id=pool_id, target_domain=target_domain
    )
    if result is None:
        raise HTTPException(status_code=503, detail="No available nodes for routing")
    return result


@router.get(
    "/chain/leases",
    summary="获取链租约列表",
    description="返回所有链式代理的租约信息",
    response_description="租约列表",
)
async def list_chain_leases(
    request: Request,
) -> dict:
    """获取链租约列表"""
    chain_instance_manager = request.app.state.chain_instance_manager
    return {"items": chain_instance_manager.list_all_leases()}


@router.post(
    "/chain/leases/cleanup",
    summary="清理过期租约",
    description="清理超过指定时间的过期链式代理租约",
    response_description="清理结果",
)
async def cleanup_chain_leases(
    request: Request,
    max_age_sec: int = Query(default=3600, ge=60),
) -> dict:
    """清理过期租约"""
    chain_instance_manager = request.app.state.chain_instance_manager
    cleaned = chain_instance_manager.cleanup_expired_leases(max_age_sec=max_age_sec)
    return {"cleaned": cleaned}


@router.post(
    "/chain/start",
    summary="启动链式代理",
    description="启动链式代理服务",
    response_description="启动结果",
)
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


@router.post(
    "/chain/stop",
    summary="停止链式代理",
    description="停止链式代理服务",
    response_description="停止结果",
)
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


@router.get(
    "/chain/nodes",
    summary="获取链节点列表",
    description="返回链式代理的所有节点信息",
    response_description="节点列表",
)
async def list_chain_nodes(
    request: Request,
) -> dict:
    """获取链节点列表"""
    chain_service = request.app.state.chain_service
    return {"items": chain_service.list_nodes()}


@router.get(
    "/chain/diagnostics",
    summary="获取链式代理诊断信息",
    description="返回链式代理的完整诊断信息，包括池状态、健康检查和租约信息",
    response_description="诊断信息详情",
)
async def chain_diagnostics(
    request: Request,
) -> ChainDiagnosticsResponse:
    """获取链式代理诊断信息"""
    chain_service = request.app.state.chain_service
    chain_instance_manager = request.app.state.chain_instance_manager

    # Get pool status
    try:
        pool_status = chain_service.get_pool_status(refresh=False)
    except Exception:
        pool_status = {}

    # Get health status
    try:
        health_status = chain_service.get_health_status()
    except Exception:
        health_status = {}

    # Get leases
    try:
        leases = chain_instance_manager.list_all_leases()
        active_leases = len([lease for lease in leases if lease.get("active", True)])
    except Exception:
        active_leases = 0

    # Determine overall status
    overall_status = "healthy"
    recent_errors = []

    # Check pool health
    front_pool = pool_status.get("front", {})
    exit_pool = pool_status.get("exit", {})

    if not front_pool.get("healthy", False):
        overall_status = "degraded"
        recent_errors.append("Front pool is unhealthy")

    if not exit_pool.get("healthy", False):
        overall_status = "degraded"
        recent_errors.append("Exit pool is unhealthy")

    # Collect recent errors from health status
    if health_status.get("errors"):
        recent_errors.extend(health_status["errors"][:5])

    return ChainDiagnosticsResponse(
        status=overall_status,
        front_pool=front_pool,
        exit_pool=exit_pool,
        health_check=health_status,
        active_leases=active_leases,
        circuit_breakers={},
        routing_stats={
            "total_routes": pool_status.get("total_routes", 0),
            "active_routes": pool_status.get("active_routes", 0),
        },
        recent_errors=recent_errors,
    )
