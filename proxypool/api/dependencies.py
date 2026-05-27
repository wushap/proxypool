from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from proxypool.api.security import is_request_authorized
from proxypool.settings import AppSettings, load_settings
from proxypool.storage.base import BaseStorage


# 全局单例 (仅在无 app.state 时使用)
_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """获取应用配置（单例）"""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def get_storage(request: Request) -> BaseStorage:
    """获取存储实例（从 app.state）"""
    return request.app.state.storage


def get_collector(request: Request):
    """获取采集服务（从 app.state）"""
    return request.app.state.collector


def get_tester(request: Request):
    """获取测试服务（从 app.state）"""
    return request.app.state.tester


def get_pool_service(request: Request):
    """获取代理池服务（从 app.state）"""
    return request.app.state.pool_service


def get_chain_service(request: Request):
    """获取链式代理服务（从 app.state）"""
    return request.app.state.chain_service


def get_singbox_manager(request: Request):
    """获取 SingBox 后端管理器（从 app.state）"""
    return request.app.state.singbox_manager


def get_backend_instance_manager(request: Request):
    """获取后端实例管理器（从 app.state）"""
    return request.app.state.chain_instance_manager


def get_chain_instance_manager(request: Request):
    """获取链实例管理器（从 app.state）"""
    return request.app.state.chain_instance_manager


def get_gateway_config_service(request: Request):
    """获取网关配置服务（从 app.state）"""
    return request.app.state.gateway_config_service


def get_forward_gateway(request: Request):
    """获取前向网关（从 app.state）"""
    return request.app.state.forward_gateway


def get_gateway_runtime(request: Request):
    """获取网关运行时管理器（从 app.state）"""
    return request.app.state.gateway_runtime


def get_geoip_service(request: Request):
    """获取 GeoIP 服务（从 app.state）"""
    return request.app.state.geoip


def get_task_manager(request: Request):
    """获取任务管理器（从 app.state）"""
    return request.app.state.task_manager


def get_scheduler(request: Request):
    """获取调度器（从 app.state）"""
    return request.app.state.scheduler


def get_app_state(request: Request):
    """获取应用状态（从 app.state）"""
    return request.app.state


# 类型别名
SettingsDep = Annotated[AppSettings, Depends(get_settings)]
StorageDep = Annotated[BaseStorage, Depends(get_storage)]
CollectorDep = Annotated[Any, Depends(get_collector)]
TesterDep = Annotated[Any, Depends(get_tester)]
PoolServiceDep = Annotated[Any, Depends(get_pool_service)]
ChainServiceDep = Annotated[Any, Depends(get_chain_service)]
SingboxManagerDep = Annotated[Any, Depends(get_singbox_manager)]
ChainInstanceManagerDep = Annotated[Any, Depends(get_chain_instance_manager)]
GatewayConfigServiceDep = Annotated[Any, Depends(get_gateway_config_service)]
ForwardGatewayDep = Annotated[Any, Depends(get_forward_gateway)]
GatewayRuntimeDep = Annotated[Any, Depends(get_gateway_runtime)]
GeoIPServiceDep = Annotated[Any, Depends(get_geoip_service)]
TaskManagerDep = Annotated[Any, Depends(get_task_manager)]
SchedulerDep = Annotated[Any, Depends(get_scheduler)]
AppStateDep = Annotated[Any, Depends(get_app_state)]


# 安全依赖
security = HTTPBearer(auto_error=False)


async def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: SettingsDep = Depends(),
) -> None:
    """验证 API Key"""
    api_key = credentials.credentials if credentials else None
    if not is_request_authorized(request.method, request.url.path, api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")


# 常用类型
from pydantic import BaseModel


class PaginationParams(BaseModel):
    """分页参数"""
    limit: int = 100
    offset: int = 0


class FilterParams(BaseModel):
    """过滤参数"""
    protocol: str | None = None
    available: bool | None = None
    country: str | None = None
    sort_by: str = "score"
    sort_order: str = "desc"
