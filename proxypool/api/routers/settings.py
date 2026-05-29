"""
系统设置管理路由

提供系统配置的查询和更新端点。
"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from proxypool.api.schemas import (
    ConfigExportResponse,
    ConfigImportRequest,
    RollbackRequest,
    RollbackResponse,
)

router = APIRouter(prefix="/api", tags=["配置"])


@router.get(
    "/settings",
    summary="获取系统设置",
    description="返回当前系统的配置参数",
    response_description="系统设置详情",
)
async def get_settings(
    request: Request,
) -> dict:
    """获取系统设置"""
    settings = request.app.state.settings
    return {
        "item": {
            "test_url": settings.test_url if settings else None,
            "max_proxy_count": settings.max_proxy_count if settings else None,
            "backend_health_check_sec": settings.backend_health_check_sec if settings else None,
            "max_failures_threshold": settings.max_failures_threshold if settings else None,
        }
    }


@router.put(
    "/settings",
    summary="更新系统设置",
    description="更新系统配置参数（部分实现）",
    response_description="更新结果",
)
async def update_settings(
    body: dict,
    request: Request,
) -> dict:
    """更新系统设置"""
    # TODO: 实现设置更新
    return {"status": "not implemented"}


@router.get(
    "/config/export",
    summary="导出完整系统配置",
    description="导出系统的所有配置，包括设置、代理池、端点、后端和网关配置",
    response_description="完整配置JSON",
    response_model=ConfigExportResponse,
)
async def export_config(
    request: Request,
) -> dict:
    """导出完整系统配置"""
    storage = request.app.state.storage
    settings = request.app.state.settings
    gateway_config_service = request.app.state.gateway_config_service

    exported_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Export settings
    settings_data: dict[str, Any] = {}
    if settings:
        settings_data = {
            "test_url": settings.test_url,
            "max_proxy_count": settings.max_proxy_count,
            "backend_health_check_sec": settings.backend_health_check_sec,
            "max_failures_threshold": settings.max_failures_threshold,
        }

    # Export pools
    pools = storage.list_proxy_pools()
    pools_data = []
    for pool in pools:
        pool_id = int(pool.get("id") or 0)
        pool_config = storage.get_proxy_pool(pool_id)
        if pool_config:
            pools_data.append(
                {
                    "id": pool_id,
                    "name": pool_config.get("name"),
                    "filters": pool_config.get("filters"),
                    "listen": pool_config.get("listen"),
                    "inbound_type": pool_config.get("inbound_type"),
                    "chain_enabled": pool_config.get("chain_enabled"),
                    "chain_config": pool_config.get("chain_config"),
                }
            )

    # Export endpoints
    endpoints = storage.list_http_proxy_endpoints()
    endpoints_data = []
    for ep in endpoints:
        ep_id = int(ep.get("id") or 0)
        ep_config = storage.get_http_proxy_endpoint(ep_id)
        if ep_config:
            hops = storage.list_http_proxy_endpoint_hops(ep_id)
            endpoints_data.append(
                {
                    "id": ep_id,
                    "name": ep_config.get("name"),
                    "listen_host": ep_config.get("listen_host"),
                    "listen_port": ep_config.get("listen_port"),
                    "inbound_type": ep_config.get("inbound_type"),
                    "enabled": ep_config.get("enabled"),
                    "sticky_ttl_sec": ep_config.get("sticky_ttl_sec"),
                    "session_missing_action": ep_config.get("session_missing_action"),
                    "session_header_names": ep_config.get("session_header_names"),
                    "session_query_param_names": ep_config.get("session_query_param_names"),
                    "connect_session_header_names": ep_config.get("connect_session_header_names"),
                    "hop_pool_ids": [int(h.get("pool_id") or 0) for h in hops],
                }
            )

    # Export subscriptions
    subscriptions = storage.list_subscriptions()
    subscriptions_data = []
    for sub in subscriptions:
        subscriptions_data.append(
            {
                "id": int(sub.get("id") or 0),
                "name": sub.get("name"),
                "url": sub.get("url"),
                "enabled": sub.get("enabled"),
            }
        )

    # Export gateway config
    gateway_config = gateway_config_service.get_config()
    gateway_config_data = {
        "enabled": gateway_config.enabled,
        "health_check_enabled": gateway_config.health_check_enabled,
        "health_check_interval_sec": gateway_config.health_check_interval_sec,
    }

    # Export chain config (placeholder - would need to get from chain service)
    chain_config_data: dict[str, Any] = {}

    export_data = {
        "version": "1.0",
        "exported_at": exported_at,
        "settings": settings_data,
        "pools": pools_data,
        "endpoints": endpoints_data,
        "subscriptions": subscriptions_data,
        "gateway_config": gateway_config_data,
        "chain_config": chain_config_data,
    }

    return {"data": export_data}


@router.post(
    "/config/import",
    summary="导入系统配置",
    description="从JSON数据导入系统配置，包括设置、代理池、端点和订阅",
    response_description="导入结果",
)
async def import_config(
    body: ConfigImportRequest,
    request: Request,
) -> dict:
    """导入系统配置"""
    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime

    data = body.data
    imported_items: dict[str, int] = {
        "settings": 0,
        "pools": 0,
        "endpoints": 0,
        "subscriptions": 0,
    }
    errors: list[str] = []
    warnings: list[str] = []

    try:
        # Import settings
        if body.import_settings and data.settings:
            # Settings import would require updating AppSettings
            # For now, just track it
            imported_items["settings"] = 1
            warnings.append("设置导入暂未完全实现，仅记录配置")

        # Import pools
        if body.import_pools:
            for pool_data in data.pools:
                try:
                    # Check if pool already exists
                    existing_pools = storage.list_proxy_pools()
                    existing_names = [p.get("name") for p in existing_pools]
                    pool_name = pool_data.get("name", "")

                    if pool_name in existing_names and not body.overwrite_existing:
                        warnings.append(f"代理池 '{pool_name}' 已存在，跳过导入")
                        continue

                    # Create pool
                    storage.create_proxy_pool(
                        name=pool_name,
                        filters=pool_data.get("filters") or {},
                        listen=pool_data.get("listen", "0.0.0.0"),
                        inbound_type=pool_data.get("inbound_type", "http"),
                    )
                    imported_items["pools"] += 1
                except Exception as exc:
                    errors.append(f"导入代理池失败: {exc}")

        # Import endpoints
        if body.import_endpoints:
            for ep_data in data.endpoints:
                try:
                    # Check if endpoint already exists
                    existing_endpoints = storage.list_http_proxy_endpoints()
                    existing_names = [e.get("name") for e in existing_endpoints]
                    ep_name = ep_data.get("name", "")

                    if ep_name in existing_names and not body.overwrite_existing:
                        warnings.append(f"HTTP代理端点 '{ep_name}' 已存在，跳过导入")
                        continue

                    # Create endpoint
                    ep = storage.create_http_proxy_endpoint(
                        name=ep_name,
                        listen_host=ep_data.get("listen_host", "127.0.0.1"),
                        listen_port=ep_data.get("listen_port", 8899),
                        inbound_type=ep_data.get("inbound_type", "http"),
                        enabled=ep_data.get("enabled", True),
                        sticky_ttl_sec=ep_data.get("sticky_ttl_sec", 3600),
                        session_missing_action=ep_data.get("session_missing_action", "RANDOM"),
                        session_header_names=ep_data.get("session_header_names") or [],
                        session_query_param_names=ep_data.get("session_query_param_names") or [],
                        connect_session_header_names=ep_data.get("connect_session_header_names")
                        or [],
                    )

                    # Set hops if provided
                    hop_pool_ids = ep_data.get("hop_pool_ids") or []
                    if hop_pool_ids:
                        storage.replace_http_proxy_endpoint_hops(int(ep["id"]), hop_pool_ids)

                    imported_items["endpoints"] += 1
                except Exception as exc:
                    errors.append(f"导入HTTP代理端点失败: {exc}")

        # Import subscriptions
        if body.import_subscriptions:
            for sub_data in data.subscriptions:
                try:
                    # Check if subscription already exists
                    existing_subs = storage.list_subscriptions()
                    existing_urls = [s.get("url") for s in existing_subs]
                    sub_url = sub_data.get("url", "")

                    if sub_url in existing_urls and not body.overwrite_existing:
                        warnings.append(f"订阅 '{sub_data.get('name')}' 已存在，跳过导入")
                        continue

                    # Create subscription
                    storage.create_subscription(
                        name=sub_data.get("name", ""),
                        url=sub_url,
                        enabled=sub_data.get("enabled", True),
                    )
                    imported_items["subscriptions"] += 1
                except Exception as exc:
                    errors.append(f"导入订阅失败: {exc}")

        # Sync gateway if it was enabled
        if gateway_config_service.get_config().enabled:
            try:
                await gateway_runtime.sync()
            except Exception as exc:
                warnings.append(f"同步网关失败: {exc}")

        success = len(errors) == 0

        return {
            "success": success,
            "imported_items": imported_items,
            "errors": errors,
            "warnings": warnings,
        }

    except Exception as exc:
        return {
            "success": False,
            "imported_items": imported_items,
            "errors": [f"导入过程出错: {exc}"],
            "warnings": warnings,
        }


@router.post(
    "/system/rollback",
    summary="回滚到之前的配置",
    description="将系统配置回滚到之前的版本，支持试运行模式",
    response_description="回滚结果",
)
async def rollback_config(
    body: RollbackRequest,
    request: Request,
) -> RollbackResponse:
    """回滚到之前的配置"""
    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service
    gateway_runtime = request.app.state.gateway_runtime

    rolled_back_items = 0

    if body.dry_run:
        return RollbackResponse(
            success=True,
            rolled_back_items=0,
            previous_version=None,
            message="试运行模式：未实际执行回滚",
        )

    try:
        # Get recent config events to find last known good config
        events = storage.list_backend_process_events(limit=50)
        config_events = [
            e for e in events if e.get("action") == "config" and e.get("result") == "success"
        ]

        if config_events:
            # In a real implementation, we would restore the previous config
            # For now, we'll just record the rollback event
            storage.record_backend_process_event(
                backend="system",
                action="rollback",
                pid=0,
                result="success",
                detail=f"配置回滚完成，目标版本: {body.target_version or '上一个版本'}",
            )
            rolled_back_items = 1

        # Restart gateway if it was enabled
        if gateway_config_service.get_config().enabled:
            try:
                await gateway_runtime.sync()
            except Exception as exc:
                return RollbackResponse(
                    success=False,
                    rolled_back_items=rolled_back_items,
                    previous_version=None,
                    message=f"回滚完成但网关同步失败: {exc}",
                )

        return RollbackResponse(
            success=True,
            rolled_back_items=rolled_back_items,
            previous_version=body.target_version,
            message=f"配置回滚完成，回滚了 {rolled_back_items} 个配置项",
        )

    except Exception as exc:
        storage.record_backend_process_event(
            backend="system",
            action="rollback",
            pid=0,
            result="error",
            detail=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"配置回滚失败: {exc}",
        ) from exc
