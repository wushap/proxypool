"""
任务管理路由

提供异步任务的查询、创建、停止、删除等端点。
"""

from fastapi import APIRouter, HTTPException, Query, Request

from proxypool.api.schemas import AutoTaskConfigRequest

router = APIRouter(prefix="/api", tags=["任务"])


@router.get("/tasks")
async def list_tasks(
    request: Request,
    limit: int = Query(default=30, ge=1, le=200),
) -> dict:
    """获取任务列表"""
    task_manager = request.app.state.task_manager
    return {"items": task_manager.list_tasks(limit=limit)}


@router.get("/tasks/auto-config")
async def get_auto_task_config(request: Request) -> dict:
    """获取自动任务配置"""
    app_state = request.app.state
    return {
        "item": dict(app_state.auto_task_config or {}),
        "last_run": dict(app_state.auto_task_last_run or {}),
        "running": app_state.auto_task_runner is not None and not app_state.auto_task_runner.done(),
    }


@router.put("/tasks/auto-config")
async def update_auto_task_config(body: AutoTaskConfigRequest, request: Request) -> dict:
    """更新自动任务配置"""
    app_state = request.app.state
    app_state.auto_task_config = body.model_dump()
    return {
        "item": dict(app_state.auto_task_config),
        "last_run": dict(app_state.auto_task_last_run or {}),
        "running": app_state.auto_task_runner is not None and not app_state.auto_task_runner.done(),
    }


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, request: Request) -> dict:
    """获取任务详情"""
    task_manager = request.app.state.task_manager
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str, request: Request) -> dict:
    """停止任务"""
    task_manager = request.app.state.task_manager
    stopped = task_manager.stop_task(task_id)
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {"stopped": bool(stopped), "task": task}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, request: Request) -> dict:
    """删除任务"""
    task_manager = request.app.state.task_manager
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    deleted = task_manager.delete_task(task_id)
    if deleted:
        return {"deleted": True, "task_id": task_id}
    latest = task_manager.get_task(task_id)
    return {"deleted": False, "task": latest}
