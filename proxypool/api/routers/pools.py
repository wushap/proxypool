"""
代理池管理路由

提供代理池的查询、创建、更新、删除、启动、停止、验证、导出等端点。
"""

import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from proxypool.api.schemas import (
    ChainInstanceCreateRequest,
    PoolBatchCreateRequest,
    PoolBatchCreateResponse,
    PoolMetricsResponse,
    PoolSessionRuleUpsertRequest,
    ProxyPoolChainConfigRequest,
    ProxyPoolCreateRequest,
    ProxyPoolUpdateRequest,
    StickyLeaseInheritRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["代理池"])


@router.get(
    "/pools",
    summary="获取代理池列表",
    description="返回所有代理池的配置信息",
    response_description="代理池列表",
)
async def list_pools(
    request: Request,
) -> dict:
    """获取代理池列表。"""
    pool_service = request.app.state.pool_service
    return {"items": pool_service.list_pools()}


@router.post(
    "/pools",
    summary="创建代理池",
    description="创建新的代理池配置，包括名称、筛选条件、监听地址和入站类型",
    response_description="创建的代理池信息",
)
async def create_pool(
    body: ProxyPoolCreateRequest,
    request: Request,
) -> dict:
    """创建代理池。

    创建新的代理池配置，包括名称、筛选条件、监听地址和入站类型。
    """
    pool_service = request.app.state.pool_service
    try:
        logger.info(f"Creating pool: {body.name}")
        item = pool_service.create_pool(
            name=body.name,
            filters=body.filters,
            listen=body.listen,
            inbound_type=body.inbound_type,
        )
        logger.info(f"Pool created: {item.get('id')}")
    except Exception as exc:
        error_msg = str(exc)
        # Enhance common error messages
        if "name" in error_msg.lower() and "exist" in error_msg.lower():
            error_msg = f"代理池名称 '{body.name}' 已存在，请使用其他名称"
        elif "name" in error_msg.lower() and (
            "empty" in error_msg.lower() or "required" in error_msg.lower()
        ):
            error_msg = "代理池名称不能为空，请提供有效的名称"
        elif "filter" in error_msg.lower():
            error_msg = f"筛选条件格式错误: {error_msg}。请检查筛选条件是否符合要求格式"
        elif "inbound" in error_msg.lower():
            error_msg = f"入站类型 '{body.inbound_type}' 无效，支持的类型: http, socks5"
        logger.error(f"Failed to create pool: {exc}")
        raise HTTPException(status_code=400, detail=error_msg) from exc
    return {"item": item}


@router.post(
    "/pools/batch",
    summary="批量创建代理池",
    description="支持一次创建多个代理池，可配置是否在遇到错误时停止",
    response_description="批量创建结果",
    response_model=PoolBatchCreateResponse,
)
async def batch_create_pools(
    body: PoolBatchCreateRequest,
    request: Request,
) -> dict:
    """批量创建代理池。

    支持一次创建多个代理池，可配置是否在遇到错误时停止。
    """
    pool_service = request.app.state.pool_service

    created = 0
    failed = 0
    items: list[dict] = []
    errors: list[dict] = []

    logger.info(f"Batch creating {len(body.pools)} pools")

    for idx, pool_req in enumerate(body.pools):
        try:
            item = pool_service.create_pool(
                name=pool_req.name,
                filters=pool_req.filters,
                listen=pool_req.listen,
                inbound_type=pool_req.inbound_type,
            )
            created += 1
            items.append({"index": idx, "success": True, "item": item})
        except Exception as exc:
            failed += 1
            error_msg = str(exc)
            errors.append(
                {
                    "index": idx,
                    "name": pool_req.name,
                    "error": error_msg,
                }
            )
            items.append({"index": idx, "success": False, "error": error_msg})
            if body.stop_on_error:
                break

    logger.info(f"Batch create completed: {created} created, {failed} failed")

    return {
        "created": created,
        "failed": failed,
        "items": items,
        "errors": errors,
    }


@router.get("/pools/{pool_id}")
async def get_pool(
    pool_id: int,
    request: Request,
) -> dict:
    """获取代理池详情"""
    pool_service = request.app.state.pool_service
    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"代理池 #{pool_id} 不存在。请检查池ID是否正确")
    return {"item": item}


@router.put("/pools/{pool_id}")
async def update_pool(
    pool_id: int,
    body: ProxyPoolUpdateRequest,
    request: Request,
) -> dict:
    """更新代理池"""
    pool_service = request.app.state.pool_service
    # Check if pool exists first
    existing = pool_service.get_pool(pool_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"代理池 #{pool_id} 不存在，无法更新")
    try:
        update_data = body.model_dump(exclude_unset=True)
        item = pool_service.update_pool(pool_id, **update_data)
    except Exception as exc:
        error_msg = str(exc)
        if "name" in error_msg.lower() and "exist" in error_msg.lower():
            error_msg = f"代理池名称 '{body.name}' 已被其他池使用，请使用其他名称"
        elif "not found" in error_msg.lower():
            error_msg = f"代理池 #{pool_id} 不存在"
        raise HTTPException(status_code=400, detail=error_msg) from exc
    return {"item": item}


@router.delete("/pools/{pool_id}")
async def delete_pool(
    pool_id: int,
    request: Request,
) -> dict:
    """删除代理池"""
    pool_service = request.app.state.pool_service
    # Check if pool exists first
    existing = pool_service.get_pool(pool_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"代理池 #{pool_id} 不存在")

    # Check for dependencies before deleting
    storage = request.app.state.storage
    endpoints = storage.list_http_proxy_endpoints()
    for ep in endpoints:
        ep_id = int(ep.get("id") or 0)
        hops = storage.get_http_proxy_endpoint_hops(ep_id)
        hop_pool_ids = [int(h.get("pool_id") or 0) for h in hops]
        if pool_id in hop_pool_ids:
            raise HTTPException(
                status_code=409,
                detail=f"代理池 #{pool_id} 正在被HTTP代理端点 '{ep.get('name')}' (#{ep_id}) 使用，请先移除依赖后再删除",
            )

    deleted = pool_service.delete_pool(pool_id)
    return {"deleted": deleted}


@router.post("/pools/{pool_id}/sync")
async def sync_pool(
    pool_id: int,
    request: Request,
) -> dict:
    """同步代理池"""
    pool_service = request.app.state.pool_service
    # Check if pool exists
    existing = pool_service.get_pool(pool_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"代理池 #{pool_id} 不存在，无法同步")

    try:
        item = pool_service.sync_pool(pool_id)
    except Exception as exc:
        error_msg = str(exc)
        if "timeout" in error_msg.lower():
            error_msg = f"同步代理池 #{pool_id} 超时，请稍后重试或检查网络连接"
        elif "connect" in error_msg.lower():
            error_msg = f"无法连接到代理池 #{pool_id} 的源，请检查订阅源是否可用"
        else:
            error_msg = f"同步代理池 #{pool_id} 失败: {error_msg}"
        raise HTTPException(status_code=400, detail=error_msg) from exc
    return {"item": item}


@router.post("/pools/{pool_id}/start")
async def start_pool(
    pool_id: int,
    request: Request,
) -> dict:
    """启动代理池"""
    pool_service = request.app.state.pool_service
    # Check if pool exists
    existing = pool_service.get_pool(pool_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"代理池 #{pool_id} 不存在，无法启动")

    try:
        item = pool_service.start_pool(pool_id)
    except Exception as exc:
        error_msg = str(exc)
        if "port" in error_msg.lower():
            error_msg = f"启动代理池 #{pool_id} 失败: 端口配置错误。请检查监听地址和端口设置"
        elif "already running" in error_msg.lower() or "running" in error_msg.lower():
            error_msg = f"代理池 #{pool_id} 已经在运行中"
        elif "backend" in error_msg.lower():
            error_msg = f"启动代理池 #{pool_id} 失败: 后端服务未运行。请先启动后端服务"
        else:
            error_msg = f"启动代理池 #{pool_id} 失败: {error_msg}"
        raise HTTPException(status_code=400, detail=error_msg) from exc
    return {"item": item}


@router.post("/pools/{pool_id}/stop")
async def stop_pool(
    pool_id: int,
    request: Request,
) -> dict:
    """停止代理池"""
    pool_service = request.app.state.pool_service
    # Check if pool exists
    existing = pool_service.get_pool(pool_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"代理池 #{pool_id} 不存在，无法停止")

    try:
        item = pool_service.stop_pool(pool_id)
    except Exception as exc:
        error_msg = str(exc)
        if "not running" in error_msg.lower() or "stopped" in error_msg.lower():
            error_msg = f"代理池 #{pool_id} 未在运行，无需停止"
        else:
            error_msg = f"停止代理池 #{pool_id} 失败: {error_msg}"
        raise HTTPException(status_code=400, detail=error_msg) from exc
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
    body: ProxyPoolChainConfigRequest,
    request: Request,
) -> dict:
    """更新代理池链配置"""
    pool_service = request.app.state.pool_service
    try:
        update_data = body.model_dump(exclude_unset=True)
        item = pool_service.update_pool_chain_config(pool_id, **update_data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"item": item}


@router.put("/pools/{pool_id}/chain/session-rules/{url_prefix:path}")
async def upsert_pool_chain_session_rule(
    pool_id: int,
    url_prefix: str,
    body: PoolSessionRuleUpsertRequest,
    request: Request,
) -> dict:
    """更新会话规则"""
    pool_service = request.app.state.pool_service
    try:
        item = pool_service.upsert_pool_session_rule(
            pool_id, url_prefix=url_prefix, headers=body.headers
        )
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
    result = chain_service.route_request(
        session_id=session_id, pool_id=pool_id, target_domain=target_domain
    )
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
    body: ChainInstanceCreateRequest,
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
            instance_id=body.instance_id,
            pool_id=pool_id,
            front_node_key=body.front_node_key,
            exit_node_key=body.exit_node_key,
            listen=body.listen,
            port=body.port,
            inbound_type=body.inbound_type,
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
    chain_service = request.app.state.chain_service
    try:
        deleted = chain_service.delete_lease(session_id, pool_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted": deleted}


@router.post("/pools/{pool_id}/chain/leases/inherit")
async def inherit_pool_chain_lease(
    pool_id: int,
    body: StickyLeaseInheritRequest,
    request: Request,
) -> dict:
    """继承租约"""
    pool_service = request.app.state.pool_service
    chain_service = request.app.state.chain_service
    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")
    try:
        lease = chain_service.inherit_lease(
            pool_id=pool_id,
            source_session_id=body.from_session_id,
            target_session_id=body.to_session_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": lease}


@router.post("/pools/{pool_id}/preview-config")
async def preview_pool_config(
    pool_id: int,
    request: Request,
) -> dict:
    """预览代理池配置"""
    pool_service = request.app.state.pool_service
    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")

    try:
        # 生成singbox配置预览
        pool_candidates = request.app.state.storage.list_proxy_pool_candidates(pool_id)
        if not pool_candidates:
            return {
                "pool_id": pool_id,
                "pool_name": item.get("name"),
                "config": {},
                "warning": "没有可用的代理节点",
            }

        # 构建预览配置（不实际应用）
        preview_config = {
            "pool_id": pool_id,
            "pool_name": item.get("name"),
            "filters": item.get("filters"),
            "listen": item.get("listen"),
            "inbound_type": item.get("inbound_type"),
            "candidate_count": len(pool_candidates),
            "candidates": [
                {
                    "normalized_key": c.get("normalized_key"),
                    "name": c.get("name"),
                    "protocol": c.get("protocol"),
                    "host": c.get("host"),
                    "port": c.get("port"),
                    "available": c.get("available"),
                }
                for c in pool_candidates[:20]  # 只显示前20个
            ],
        }
        return preview_config
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/pools/{pool_id}/validate")
async def validate_pool_config(
    pool_id: int,
    request: Request,
) -> dict:
    """验证代理池配置。

    检查代理池配置的有效性，包括名称、筛选条件等，不实际应用更改。
    """
    import time

    pool_service = request.app.state.pool_service
    storage = request.app.state.storage

    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")

    issues: list[dict] = []
    validated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Validate pool name
    name = item.get("name", "")
    if not name:
        issues.append(
            {
                "field": "name",
                "issue_type": "error",
                "message": "代理池名称不能为空",
                "suggestion": "请设置一个有意义的名称",
            }
        )
    elif len(name) < 2:
        issues.append(
            {
                "field": "name",
                "issue_type": "warning",
                "message": "代理池名称过短，可能不便于管理",
                "suggestion": "建议使用至少2个字符的名称",
            }
        )
    elif len(name) > 50:
        issues.append(
            {
                "field": "name",
                "issue_type": "error",
                "message": "代理池名称过长",
                "suggestion": "请将名称控制在50个字符以内",
            }
        )

    # Validate filters
    filters = item.get("filters") or {}
    if filters:
        # Validate route_mode_filter
        route_mode = filters.get("route_mode_filter")
        if route_mode and route_mode not in ("direct", "chain", "unreachable"):
            issues.append(
                {
                    "field": "filters.route_mode_filter",
                    "issue_type": "error",
                    "message": f"无效的路由模式: {route_mode}",
                    "suggestion": "可选值: direct, chain, unreachable",
                }
            )

        # Validate openai_filter
        openai_filter = filters.get("openai_filter")
        if openai_filter and openai_filter not in ("unlocked", "blocked", "unchecked"):
            issues.append(
                {
                    "field": "filters.openai_filter",
                    "issue_type": "error",
                    "message": f"无效的ChatGPT筛选: {openai_filter}",
                    "suggestion": "可选值: unlocked, blocked, unchecked",
                }
            )

        # Validate ip_purity_filter
        ip_purity = filters.get("ip_purity_filter")
        if ip_purity and ip_purity not in ("residential", "non_residential", "unknown"):
            issues.append(
                {
                    "field": "filters.ip_purity_filter",
                    "issue_type": "error",
                    "message": f"无效的家宽筛选: {ip_purity}",
                    "suggestion": "可选值: residential, non_residential, unknown",
                }
            )

        # Validate latency range
        latency_min = filters.get("latency_min")
        latency_max = filters.get("latency_max")
        if latency_min is not None and latency_max is not None:
            if latency_min > latency_max:
                issues.append(
                    {
                        "field": "filters.latency_range",
                        "issue_type": "error",
                        "message": "延迟范围无效：最小值不能大于最大值",
                        "suggestion": "请调整延迟范围设置",
                    }
                )

        # Validate freshness_hours
        freshness = filters.get("freshness_hours")
        if freshness is not None and freshness < 0:
            issues.append(
                {
                    "field": "filters.freshness_hours",
                    "issue_type": "error",
                    "message": "时效时间不能为负数",
                    "suggestion": "请设置为0或正数",
                }
            )

        # Validate geo_countries
        geo_countries = filters.get("geo_countries")
        if geo_countries and not isinstance(geo_countries, list):
            issues.append(
                {
                    "field": "filters.geo_countries",
                    "issue_type": "error",
                    "message": "国家/地区筛选格式无效",
                    "suggestion": "应为字符串数组格式",
                }
            )

    # Validate inbound_type
    inbound_type = item.get("inbound_type", "http")
    if inbound_type not in ("http", "socks5"):
        issues.append(
            {
                "field": "inbound_type",
                "issue_type": "error",
                "message": f"无效的入站类型: {inbound_type}",
                "suggestion": "可选值: http, socks5",
            }
        )

    # Validate listen address
    listen = item.get("listen", "")
    if not listen:
        issues.append(
            {
                "field": "listen",
                "issue_type": "warning",
                "message": "监听地址为空",
                "suggestion": "建议设置监听地址，如 0.0.0.0 或 127.0.0.1",
            }
        )

    # Check pool chain consistency
    chain_enabled = item.get("chain_enabled")
    if chain_enabled:
        # Check if chain config exists
        chain_config = item.get("chain_config") or {}
        if not chain_config.get("session_missing_action"):
            issues.append(
                {
                    "field": "chain_config.session_missing_action",
                    "issue_type": "warning",
                    "message": "链式代理已启用但未设置会话缺失动作",
                    "suggestion": "建议设置 session_missing_action 为 RANDOM 或 REJECT",
                }
            )

    # Check candidate availability
    pool_candidates = storage.list_proxy_pool_candidates(pool_id)
    available_count = sum(1 for c in pool_candidates if c.get("available"))
    if not pool_candidates:
        issues.append(
            {
                "field": "candidates",
                "issue_type": "warning",
                "message": "代理池中没有匹配的节点",
                "suggestion": "请检查筛选条件是否过于严格，或先导入更多代理节点",
            }
        )
    elif available_count == 0:
        issues.append(
            {
                "field": "candidates",
                "issue_type": "warning",
                "message": "所有匹配节点均不可用",
                "suggestion": "请运行测试检查节点可用性",
            }
        )
    elif available_count < 3:
        issues.append(
            {
                "field": "candidates",
                "issue_type": "warning",
                "message": f"可用节点较少（{available_count}个），可能影响稳定性",
                "suggestion": "建议至少保持3个以上可用节点",
            }
        )

    # Determine if valid (no errors)
    is_valid = not any(i["issue_type"] == "error" for i in issues)

    return {
        "pool_id": pool_id,
        "pool_name": item.get("name", ""),
        "is_valid": is_valid,
        "issues": issues,
        "validated_at": validated_at,
    }


@router.get("/pools/{pool_id}/dependencies")
async def get_pool_dependencies(
    pool_id: int,
    request: Request,
) -> dict:
    """获取代理池依赖关系"""
    storage = request.app.state.storage
    pool_service = request.app.state.pool_service

    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")

    # Find dependent HTTP proxy endpoints
    dependent_endpoints: list[dict] = []
    endpoints = storage.list_http_proxy_endpoints()
    for ep in endpoints:
        ep_id = int(ep.get("id") or 0)
        hops = storage.get_http_proxy_endpoint_hops(ep_id)
        hop_pool_ids = [int(h.get("pool_id") or 0) for h in hops]
        if pool_id in hop_pool_ids:
            dependent_endpoints.append(
                {
                    "endpoint_id": ep_id,
                    "name": ep.get("name", ""),
                    "listen_host": ep.get("listen_host"),
                    "listen_port": ep.get("listen_port"),
                    "enabled": ep.get("enabled"),
                }
            )

    # Find dependent chain instances
    dependent_instances: list[dict] = []
    try:
        chain_instance_manager = request.app.state.chain_instance_manager
        instances = chain_instance_manager.list_instances(pool_id=pool_id)
        for inst in instances:
            dependent_instances.append(
                {
                    "instance_id": inst.get("instance_id"),
                    "pool_id": inst.get("pool_id"),
                    "status": inst.get("status"),
                }
            )
    except Exception:
        pass

    has_dependencies = len(dependent_endpoints) > 0 or len(dependent_instances) > 0

    return {
        "pool_id": pool_id,
        "pool_name": item.get("name", ""),
        "dependent_endpoints": dependent_endpoints,
        "dependent_instances": dependent_instances,
        "has_dependencies": has_dependencies,
    }


@router.get("/pools/{pool_id}/health-summary")
async def get_pool_health_summary(
    pool_id: int,
    request: Request,
) -> dict:
    """获取代理池健康摘要"""
    storage = request.app.state.storage
    pool_service = request.app.state.pool_service

    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="pool not found")

    # Get all candidates for this pool
    pool_candidates = storage.list_proxy_pool_candidates(pool_id)
    total_nodes = len(pool_candidates)

    # Categorize nodes by health status
    healthy_nodes = 0
    degraded_nodes = 0
    unavailable_nodes = 0
    last_test_time = None

    for candidate in pool_candidates:
        # Check availability and failure count
        available = candidate.get("available")
        failure_count = candidate.get("failure_count", 0) or 0
        last_checked = candidate.get("last_checked")

        if available:
            if failure_count > 0:
                degraded_nodes += 1
            else:
                healthy_nodes += 1
        else:
            unavailable_nodes += 1

        # Track most recent test time
        if last_checked and (last_test_time is None or last_checked > last_test_time):
            last_test_time = last_checked

    # Calculate healthy rate
    healthy_rate = (healthy_nodes / total_nodes) if total_nodes > 0 else 0.0

    # Determine overall status
    if healthy_rate >= 0.8:
        status = "healthy"
    elif healthy_rate >= 0.5:
        status = "degraded"
    else:
        status = "unhealthy"

    return {
        "pool_id": pool_id,
        "pool_name": item.get("name", ""),
        "total_nodes": total_nodes,
        "healthy_nodes": healthy_nodes,
        "degraded_nodes": degraded_nodes,
        "unavailable_nodes": unavailable_nodes,
        "healthy_rate": round(healthy_rate, 3),
        "last_test_time": last_test_time,
        "status": status,
    }


@router.get("/pools/{pool_id}/export")
async def export_pool_csv(
    pool_id: int,
    request: Request,
) -> PlainTextResponse:
    """导出代理池统计数据为CSV格式。

    返回包含代理池内所有节点信息的CSV文件，支持UTF-8 BOM以兼容Excel中文字符显示。
    """
    storage = request.app.state.storage
    pool_service = request.app.state.pool_service

    item = pool_service.get_pool(pool_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"代理池 #{pool_id} 不存在")

    # Get pool health data
    pool_candidates = storage.list_proxy_pool_candidates(pool_id, limit=10000)

    # Create CSV with UTF-8 BOM
    output = io.StringIO()
    output.write("﻿")  # UTF-8 BOM

    writer = csv.writer(output)

    # Write headers
    writer.writerow(
        [
            "地址",
            "协议",
            "状态",
            "延迟(ms)",
            "速度(Mbps)",
            "国家",
            "城市",
            "失败次数",
            "最后检查时间",
            "OpenAI解锁",
        ]
    )

    # Write data rows
    for candidate in pool_candidates:
        writer.writerow(
            [
                f"{candidate.get('host', '')}:{candidate.get('port', '')}",
                candidate.get("protocol", ""),
                "可用" if candidate.get("available") else "不可用",
                candidate.get("latency_ms", ""),
                candidate.get("speed_mbps", ""),
                candidate.get("country", ""),
                candidate.get("city", ""),
                candidate.get("failure_count", 0),
                candidate.get("last_checked", ""),
                "是"
                if candidate.get("openai_unlocked")
                else "否"
                if candidate.get("openai_unlocked") is not None
                else "未知",
            ]
        )

    # Generate filename
    pool_name = item.get("name", f"pool-{pool_id}")
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"pool-{pool_name}-{date_str}.csv"

    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )


@router.get(
    "/pools/{pool_id}/metrics",
    summary="获取代理池性能指标",
    description="返回指定代理池的性能指标，包括请求统计、代理健康状态、延迟等",
    response_description="代理池性能指标",
    response_model=PoolMetricsResponse,
)
async def get_pool_metrics(
    pool_id: int,
    request: Request,
) -> PoolMetricsResponse:
    """获取代理池性能指标

    返回指定代理池的性能指标数据，包括该池的请求统计、代理健康状态、
    延迟百分位数等信息。
    """
    storage = request.app.state.storage
    metrics_service = request.app.state.metrics_service

    # Get pool info
    pool = storage.get_proxy_pool(pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail=f"代理池 {pool_id} 不存在")

    pool_name = pool.get("name", f"pool-{pool_id}")
    metrics_data = metrics_service.get_pool_metrics(pool_id, pool_name, storage)
    return PoolMetricsResponse(**metrics_data)
