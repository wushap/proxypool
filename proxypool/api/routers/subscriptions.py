"""
订阅管理路由

提供订阅源的查询、创建、更新、删除、刷新等端点。
"""

import asyncio
import base64
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from proxypool.api.schemas import SubscriptionBatchRefreshRequest

router = APIRouter(prefix="/api", tags=["订阅"])


@router.get("/subscriptions")
async def list_subscriptions(
    request: Request,
    limit: int = Query(default=200, ge=1, le=5000),
) -> dict:
    """获取订阅列表"""
    storage = request.app.state.storage
    return {"items": storage.list_subscriptions(limit=limit)}


@router.post("/subscriptions")
async def create_subscription(
    body: dict,
    request: Request,
) -> dict:
    """创建订阅"""
    storage = request.app.state.storage
    try:
        item = storage.create_subscription(
            name=body["name"],
            url=body["url"],
            enabled=body.get("enabled", True),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.put("/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: int,
    body: dict,
    request: Request,
) -> dict:
    """更新订阅"""
    storage = request.app.state.storage
    try:
        item = storage.update_subscription(
            subscription_id=subscription_id,
            name=body.get("name"),
            url=body.get("url"),
            enabled=body.get("enabled"),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.get("/subscription-update-proxy")
async def get_subscription_update_proxy(request: Request) -> dict:
    """获取订阅更新代理"""
    storage = request.app.state.storage
    return {"update_proxy_key": storage.get_subscription_update_proxy_key()}


@router.put("/subscription-update-proxy")
async def set_subscription_update_proxy(
    body: dict,
    request: Request,
) -> dict:
    """设置订阅更新代理"""
    storage = request.app.state.storage
    key = str(body.get("update_proxy_key") or "").strip()
    if key and storage.get_proxy_by_key(key) is None:
        raise HTTPException(status_code=400, detail="update proxy not found")
    storage.set_subscription_update_proxy_key(key)
    return {"update_proxy_key": key}


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: int,
    request: Request,
) -> dict:
    """删除订阅"""
    storage = request.app.state.storage
    deleted = storage.delete_subscription(subscription_id)
    if deleted <= 0:
        raise HTTPException(status_code=404, detail="subscription not found")
    return {"deleted": deleted}


@router.post("/subscriptions/delete-unavailable")
async def delete_unavailable_subscriptions(
    request: Request,
    include_disabled: bool = Query(default=False),
) -> dict:
    """删除不可用订阅"""
    storage = request.app.state.storage
    deleted = storage.delete_unavailable_subscriptions(include_disabled=include_disabled)
    return {"deleted": deleted}


@router.post("/subscriptions/batch-refresh")
async def batch_refresh_subscriptions(
    body: SubscriptionBatchRefreshRequest,
    request: Request,
) -> dict:
    """批量刷新订阅"""
    storage = request.app.state.storage
    collector = request.app.state.collector

    total = len(body.subscription_ids)
    success = 0
    failed = 0
    results: list[dict] = []

    for sub_id in body.subscription_ids:
        try:
            # Get subscription
            sub = storage.get_subscription(sub_id)
            if sub is None:
                results.append(
                    {
                        "subscription_id": sub_id,
                        "success": False,
                        "error": "subscription not found",
                    }
                )
                failed += 1
                continue

            # Refresh subscription
            if sub.get("url"):
                try:
                    await collector.refresh_subscription(
                        sub_id=sub_id,
                        timeout_sec=body.timeout_sec,
                    )
                    success += 1
                    results.append(
                        {
                            "subscription_id": sub_id,
                            "name": sub.get("name"),
                            "success": True,
                        }
                    )
                except Exception as exc:
                    failed += 1
                    results.append(
                        {
                            "subscription_id": sub_id,
                            "name": sub.get("name"),
                            "success": False,
                            "error": str(exc),
                        }
                    )
            else:
                failed += 1
                results.append(
                    {
                        "subscription_id": sub_id,
                        "name": sub.get("name"),
                        "success": False,
                        "error": "subscription URL is empty",
                    }
                )
        except Exception as exc:
            failed += 1
            results.append(
                {
                    "subscription_id": sub_id,
                    "success": False,
                    "error": str(exc),
                }
            )

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "results": results,
    }


@router.get("/published-subscriptions")
async def list_published_subscriptions(
    request: Request,
    limit: int = Query(default=200, ge=1, le=5000),
) -> dict:
    """获取已发布订阅列表"""
    storage = request.app.state.storage
    return {
        "items": [
            _published_subscription_payload(item)
            for item in storage.list_published_subscriptions(limit=limit)
        ]
    }


@router.post("/published-subscriptions")
async def create_published_subscription(
    body: dict,
    request: Request,
) -> dict:
    """创建已发布订阅"""
    storage = request.app.state.storage
    try:
        item = storage.create_published_subscription(
            name=body["name"],
            filters=body.get("filters"),
            enabled=body.get("enabled", True),
            format=body.get("format", "raw"),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": _published_subscription_payload(item)}


@router.put("/published-subscriptions/{subscription_id}")
async def update_published_subscription(
    subscription_id: int,
    body: dict,
    request: Request,
) -> dict:
    """更新已发布订阅"""
    storage = request.app.state.storage
    try:
        item = storage.update_published_subscription(
            subscription_id=subscription_id,
            name=body.get("name"),
            filters=body.get("filters"),
            enabled=body.get("enabled"),
            format=body.get("format"),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": _published_subscription_payload(item)}


@router.delete("/published-subscriptions/{subscription_id}")
async def delete_published_subscription(
    subscription_id: int,
    request: Request,
) -> dict:
    """删除已发布订阅"""
    storage = request.app.state.storage
    deleted = storage.delete_published_subscription(subscription_id)
    if deleted <= 0:
        raise HTTPException(status_code=404, detail="published subscription not found")
    return {"deleted": deleted}


@router.get("/published-subscriptions/{subscription_id}/subscription")
async def published_subscription(
    subscription_id: int,
    request: Request,
    limit: int = Query(default=5000, ge=1, le=20000),
    encode_base64: bool = Query(default=False),
) -> PlainTextResponse:
    """获取已发布订阅内容"""
    storage = request.app.state.storage
    item = storage.get_published_subscription(subscription_id)
    if item is None:
        raise HTTPException(status_code=404, detail="published subscription not found")
    if not item.get("enabled"):
        raise HTTPException(status_code=404, detail="published subscription disabled")
    output_format = str(item.get("format") or "raw").strip().lower()
    if output_format == "clash":
        text = _published_subscription_clash_yaml(
            storage.get_published_subscription_proxies(subscription_id, limit=limit)
        )
    else:
        links = storage.get_published_subscription_links(subscription_id, limit=limit)
        text = "\n".join(links)
    if encode_base64:
        text = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    return PlainTextResponse(text)


@router.post("/subscriptions/{subscription_id}/refresh")
async def refresh_subscription(
    subscription_id: int,
    body: dict,
    request: Request,
) -> dict:
    """刷新订阅"""
    storage = request.app.state.storage
    collector = request.app.state.collector
    sub = storage.get_subscription(subscription_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="subscription not found")

    def _refresh_one() -> dict:
        report = collector.collect_from_subscription(
            subscription_id=subscription_id,
            subscription_name=str(sub.get("name") or ""),
            subscription_url=str(sub.get("url") or ""),
            timeout_sec=body.get("timeout_sec"),
        )
        status, error = _subscription_status_from_report(report)
        storage.mark_subscription_result(
            subscription_id=subscription_id,
            status=status,
            error=error,
            parsed=report.total_parsed,
            inserted=report.total_inserted,
            updated=report.total_updated,
            invalid=report.total_invalid,
            deduped=report.total_deduped,
        )
        item = storage.get_subscription(subscription_id)
        return {"item": item, "report": _collect_report_to_dict(report)}

    return await asyncio.to_thread(_refresh_one)


@router.post("/subscriptions/refresh-enabled")
async def refresh_enabled_subscriptions(
    request: Request,
    timeout_sec: float = Query(default=12.0, ge=1.0, le=120.0),
) -> dict:
    """刷新所有启用的订阅"""
    storage = request.app.state.storage
    collector = request.app.state.collector

    def _refresh_enabled() -> dict:
        subscriptions = storage.list_enabled_subscriptions()
        items: list[dict] = []

        for sub in subscriptions:
            sub_id = int(sub.get("id") or 0)
            report = collector.collect_from_subscription(
                subscription_id=sub_id,
                subscription_name=str(sub.get("name") or ""),
                subscription_url=str(sub.get("url") or ""),
                timeout_sec=timeout_sec,
            )
            status, error = _subscription_status_from_report(report)
            storage.mark_subscription_result(
                subscription_id=sub_id,
                status=status,
                error=error,
                parsed=report.total_parsed,
                inserted=report.total_inserted,
                updated=report.total_updated,
                invalid=report.total_invalid,
                deduped=report.total_deduped,
            )
            items.append(
                {
                    "subscription_id": sub_id,
                    "name": sub.get("name") or "",
                    "status": status,
                    "error": error,
                    "report": _collect_report_to_dict(report),
                }
            )
        return {"count": len(items), "items": items}

    return await asyncio.to_thread(_refresh_enabled)


@router.post("/tasks/subscriptions-refresh/start")
async def start_refresh_enabled_subscriptions_task(
    request: Request,
    timeout_sec: float = Query(default=12.0, ge=1.0, le=120.0),
) -> dict:
    """启动订阅刷新任务"""
    task_manager = request.app.state.task_manager
    storage = request.app.state.storage
    collector = request.app.state.collector

    def _runner(update, should_stop):
        def _progress(payload: dict) -> None:
            update(
                total=payload.get("total", 0),
                completed=payload.get("completed", 0),
                success=payload.get("success", 0),
                failed=payload.get("failed", 0),
                message=f"refresh {payload.get('completed', 0)}/{payload.get('total', 0)}",
            )

        return refresh_enabled_subscriptions_sync(
            timeout_sec=timeout_sec,
            storage=storage,
            collector=collector,
            progress_cb=_progress,
            stop_cb=should_stop,
        )

    task_id = task_manager.start_task("subscriptions_refresh", _runner)
    task = task_manager.get_task(task_id)
    return {"task_id": task_id, "task": task}


def _published_subscription_payload(item: dict) -> dict:
    """构建已发布订阅响应"""
    out = dict(item)
    out["export_url"] = f"/api/published-subscriptions/{item['id']}/subscription"
    return out


def _collect_report_to_dict(report) -> dict:
    """将收集报告转换为字典"""
    return {
        "total_sources": report.total_sources,
        "total_parsed": report.total_parsed,
        "total_inserted": report.total_inserted,
        "total_updated": report.total_updated,
        "total_deduped": report.total_deduped,
        "total_invalid": report.total_invalid,
        "by_source": [asdict(r) for r in report.by_source],
    }


def _subscription_status_from_report(report) -> tuple[str, str]:
    """根据报告判断订阅状态"""
    if report.total_parsed > 0 or report.total_inserted > 0 or report.total_updated > 0:
        return "success", ""
    if report.total_invalid > 0:
        return "failed", "empty or invalid subscription content"
    return "success", ""


def _published_subscription_clash_yaml(proxies: list[dict]) -> str:
    """生成 Clash YAML 格式的订阅"""
    import yaml

    from proxypool.backend.mihomo_config import _build_mihomo_proxy

    proxy_items: list[dict] = []
    names: list[str] = []
    used: set[str] = set()
    for idx, proxy in enumerate(proxies, start=1):
        name = _unique_clash_proxy_name(proxy, idx=idx, used=used)
        try:
            item = _build_mihomo_proxy(proxy, name=name)
        except Exception:
            continue
        proxy_items.append(item)
        names.append(name)
    selector_names = names or ["DIRECT"]
    config = {
        "proxies": proxy_items,
        "proxy-groups": [
            {
                "name": "Proxy",
                "type": "select",
                "proxies": selector_names,
            }
        ],
        "rules": ["MATCH,Proxy"],
    }
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False)


def _unique_clash_proxy_name(proxy: dict, idx: int, used: set[str]) -> str:
    """生成唯一的 Clash 代理名称"""
    raw = str(proxy.get("name") or "").strip()
    if not raw:
        host = str(proxy.get("host") or "").strip() or "proxy"
        port = str(proxy.get("port") or "").strip()
        raw = f"{host}:{port}" if port else host
    base = raw[:80] or f"proxy-{idx}"
    name = base
    suffix = 2
    while name in used:
        name = f"{base}-{suffix}"
        suffix += 1
    used.add(name)
    return name


def refresh_enabled_subscriptions_sync(
    timeout_sec: float,
    storage,
    collector,
    progress_cb=None,
    stop_cb=None,
) -> dict:
    """同步刷新所有启用的订阅"""
    subscriptions = storage.list_enabled_subscriptions()
    items: list[dict] = []

    for idx, sub in enumerate(subscriptions):
        if stop_cb and stop_cb():
            break

        sub_id = int(sub.get("id") or 0)
        report = collector.collect_from_subscription(
            subscription_id=sub_id,
            subscription_name=str(sub.get("name") or ""),
            subscription_url=str(sub.get("url") or ""),
            timeout_sec=timeout_sec,
        )
        status, error = _subscription_status_from_report(report)
        storage.mark_subscription_result(
            subscription_id=sub_id,
            status=status,
            error=error,
            parsed=report.total_parsed,
            inserted=report.total_inserted,
            updated=report.total_updated,
            invalid=report.total_invalid,
            deduped=report.total_deduped,
        )
        items.append(
            {
                "subscription_id": sub_id,
                "name": sub.get("name") or "",
                "status": status,
                "error": error,
                "report": _collect_report_to_dict(report),
            }
        )

        if progress_cb:
            progress_cb(
                {
                    "total": len(subscriptions),
                    "completed": idx + 1,
                    "success": len([i for i in items if i["status"] == "success"]),
                    "failed": len([i for i in items if i["status"] == "failed"]),
                }
            )

    return {"count": len(items), "items": items}
