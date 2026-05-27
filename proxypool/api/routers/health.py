"""
健康检查和统计路由
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request

from proxypool.api.dependencies import SingboxManagerDep, StorageDep

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(
    request: Request,
    singbox_manager: SingboxManagerDep = None,
) -> dict:
    """系统健康检查"""
    storage = request.app.state.storage
    backend_ok = singbox_manager.is_running() if hasattr(singbox_manager, 'is_running') else False
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "backend_running": backend_ok,
        "proxy_count": storage.get_stats().get("total", 0),
    }


@router.get("/stats")
async def stats(request: Request) -> dict:
    """系统统计数据"""
    storage = request.app.state.storage
    return storage.get_stats()
