"""
API Router 模块

将 app.py 中的路由按功能域拆分为独立的 Router 文件。
"""

from fastapi import APIRouter

# 导入所有 Router
from .health import router as health_router
from .proxies import router as proxies_router
from .subscriptions import router as subscriptions_router
from .pools import router as pools_router
from .backend import router as backend_router
from .tester import router as tester_router
from .chain import router as chain_router
from .gateway import router as gateway_router
from .tasks import router as tasks_router
from .settings import router as settings_router

__all__ = [
    "health_router",
    "proxies_router",
    "subscriptions_router",
    "pools_router",
    "backend_router",
    "tester_router",
    "chain_router",
    "gateway_router",
    "tasks_router",
    "settings_router",
    "register_routers",
]


def register_routers(app) -> None:
    """注册所有 Router 到 FastAPI 应用"""
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
