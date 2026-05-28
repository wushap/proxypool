"""
API Router 模块

将 app.py 中的路由按功能域拆分为独立的 Router 文件。
"""

from fastapi import Request

from .backend import router as backend_router
from .chain import router as chain_router
from .gateway import router as gateway_router

# 导入所有 Router
from .health import router as health_router
from .pools import router as pools_router
from .proxies import router as proxies_router
from .settings import router as settings_router
from .subscriptions import router as subscriptions_router
from .tasks import router as tasks_router
from .tester import router as tester_router

__all__ = [
    "backend_router",
    "chain_router",
    "gateway_router",
    "health_router",
    "pools_router",
    "proxies_router",
    "register_routers",
    "settings_router",
    "subscriptions_router",
    "tasks_router",
    "tester_router",
]

# API version for versioning support
API_VERSION = "v1"


def register_routers(app) -> None:
    """注册所有 Router 到 FastAPI 应用

    支持 API 版本化，通过路由别名提供版本化访问。
    所有路由都支持 /api/v1/ 前缀访问，同时保留 /api/ 前缀以保持向后兼容。
    """
    # Register all routers (they already have /api prefix)
    app.include_router(health_router)
    app.include_router(proxies_router)
    app.include_router(subscriptions_router)
    app.include_router(pools_router)
    app.include_router(backend_router)
    app.include_router(tester_router)
    app.include_router(chain_router)
    app.include_router(gateway_router)
    app.include_router(tasks_router)
    app.include_router(settings_router)

    # Add version aliases for key endpoints
    @app.get(f"/api/{API_VERSION}/health", include_in_schema=False)
    async def health_v1(request: Request):
        """Versioned health endpoint"""
        from .health import health

        return await health(request)

    @app.get(f"/api/{API_VERSION}/stats", include_in_schema=False)
    async def stats_v1(request: Request):
        """Versioned stats endpoint"""
        from .health import stats

        return await stats(request)
