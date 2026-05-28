"""
测试任务管理路由

提供代理测试、速度测试、OpenAI 检查等端点。
"""

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from proxypool.api.schemas import (
    RunTestRequest,
    SingleProxyTestRequest,
    SpeedTestRequest,
)

router = APIRouter(prefix="/api", tags=["测试"])


@router.post(
    "/tester/run",
    summary="运行批量测试",
    description="批量测试代理节点的可用性和性能",
    response_description="测试结果报告",
)
async def run_tester(
    body: RunTestRequest,
    request: Request,
) -> dict:
    """运行批量测试"""
    tester = request.app.state.tester
    report = await tester.run_batch(
        limit=body.limit,
        concurrency=body.concurrency,
        only_unchecked=body.only_unchecked,
        only_available=body.only_available,
        only_unavailable=body.only_unavailable,
        min_last_checked_age_hours=body.min_last_checked_age_hours,
        protocols=body.protocols,
        fallback_front_proxy_keys=body.fallback_front_proxy_keys,
        fallback_front_max_attempts=body.fallback_front_max_attempts,
        replace_failed_with_available=body.replace_failed_with_available,
    )
    return asdict(report)


@router.post(
    "/tester/run-one",
    summary="运行单个代理测试",
    description="测试指定代理节点的可用性和性能",
    response_description="单个代理测试结果",
)
async def run_single_proxy_test(
    body: SingleProxyTestRequest,
    request: Request,
) -> dict:
    """运行单个代理测试"""
    storage = request.app.state.storage
    tester = request.app.state.tester
    key = body.normalized_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="normalized_key is empty")
    if storage.get_proxy_by_key(key) is None:
        raise HTTPException(status_code=404, detail="proxy not found")
    report = await tester.run_one(
        normalized_key=key,
        fallback_front_proxy_keys=body.fallback_front_proxy_keys,
        fallback_front_max_attempts=body.fallback_front_max_attempts,
    )
    return asdict(report)


@router.post(
    "/tasks/tester/start",
    summary="启动测试任务",
    description="在后台启动批量代理测试任务，返回任务ID",
    response_description="任务ID",
)
async def start_tester_task(
    body: RunTestRequest,
    request: Request,
) -> dict:
    """启动测试任务"""
    task_manager = request.app.state.task_manager
    tester = request.app.state.tester

    def _runner(update, should_stop):
        def _progress(payload: dict) -> None:
            update(
                total=payload.get("total", 0),
                completed=payload.get("completed", 0),
                success=payload.get("success", 0),
                failed=payload.get("failed", 0),
                message=f"test {payload.get('completed', 0)}/{payload.get('total', 0)}",
            )

        import asyncio

        report = asyncio.run(
            tester.run_batch(
                limit=body.limit,
                concurrency=body.concurrency,
                only_unchecked=body.only_unchecked,
                only_available=body.only_available,
                only_unavailable=body.only_unavailable,
                min_last_checked_age_hours=body.min_last_checked_age_hours,
                protocols=body.protocols,
                fallback_front_proxy_keys=body.fallback_front_proxy_keys,
                fallback_front_max_attempts=body.fallback_front_max_attempts,
                replace_failed_with_available=body.replace_failed_with_available,
                progress_cb=_progress,
                stop_cb=should_stop,
            )
        )
        return asdict(report)

    task_id = task_manager.start_task("tester", _runner)
    return {"task_id": task_id}


@router.post(
    "/tasks/speed-test/start",
    summary="启动速度测试任务",
    description="在后台启动代理速度测试任务",
    response_description="任务ID",
)
async def start_speed_test_task(
    body: SpeedTestRequest,
    request: Request,
) -> dict:
    """启动速度测试任务"""
    task_manager = request.app.state.task_manager
    storage = request.app.state.storage
    tester = request.app.state.tester
    target_url = body.url.strip()
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        raise HTTPException(
            status_code=400, detail="speed test url must start with http:// or https://"
        )

    def _runner(update, should_stop):
        only_direct = body.only_available if body.only_direct is None else body.only_direct
        candidates = storage.get_candidates_for_test(
            limit=body.limit,
            only_available=body.only_available,
            only_direct=only_direct,
        )
        total = len(candidates)
        results: list[dict] = []
        success = 0
        failed = 0
        update(total=total, completed=0, success=0, failed=0, message=f"queued {total} nodes")
        for idx, node in enumerate(candidates, start=1):
            if should_stop():
                break
            key = str(node.get("normalized_key") or "")
            name = str(node.get("name") or node.get("host") or key[:8])
            update(
                total=total,
                completed=idx - 1,
                success=success,
                failed=failed,
                message=f"speed testing {idx}/{total} {name}",
            )
            result = asyncio.run(
                tester.prober.speed_test_async(
                    node,
                    target_url,
                    timeout_sec=float(body.timeout_sec),
                )
            )
            item = {
                "normalized_key": key,
                "name": name,
                "ok": result.ok,
                "elapsed_ms": result.elapsed_ms,
                "bytes": result.bytes_downloaded,
                "speed_mbps": result.speed_mbps,
                "error": result.error[:300],
            }
            results.append(item)
            storage.update_speed_test_result(key, ok=result.ok, speed_mbps=result.speed_mbps)
            if result.ok:
                success += 1
            else:
                failed += 1
            update(
                total=total,
                completed=idx,
                success=success,
                failed=failed,
                message=f"speed {idx}/{total} ok={success} failed={failed}",
                result={"items": results[-50:], "count": len(results)},
            )
        return {"count": len(results), "items": results}

    task_id = task_manager.start_task("speed_test", _runner)
    return {"task_id": task_id}


@router.post("/tasks/openai-check/start")
async def start_openai_check_task(
    body: dict,
    request: Request,
) -> dict:
    """启动 OpenAI 检查任务"""
    task_manager = request.app.state.task_manager
    tester = request.app.state.tester

    def _runner(update, should_stop):
        def _progress(payload: dict) -> None:
            update(
                total=payload.get("total", 0),
                completed=payload.get("completed", 0),
                success=payload.get("available", 0),
                failed=payload.get("unavailable", 0),
                message=f"openai {payload.get('completed', 0)}/{payload.get('total', 0)}",
            )

        import asyncio

        report = asyncio.run(
            tester.run_openai_check_batch(
                limit=body.get("limit", 100),
                concurrency=body.get("concurrency", 50),
                only_available=True,
                protocols=body.get("protocols"),
                progress_cb=_progress,
                stop_cb=should_stop,
            )
        )
        return asdict(report)

    task_id = task_manager.start_task("openai_check", _runner)
    return {"task_id": task_id}
