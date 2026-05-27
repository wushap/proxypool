"""
系统设置管理路由

提供系统配置的查询和更新端点。
"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
async def get_settings(
    request: Request,
) -> dict:
    """获取系统设置"""
    settings = request.app.state.settings
    return {
        "item": {
            "db_path": str(settings.db_path) if settings else None,
            "singbox_binary": str(settings.singbox_binary) if settings else None,
            "test_url": settings.test_url if settings else None,
        }
    }


@router.put("/settings")
async def update_settings(
    body: dict,
    request: Request,
) -> dict:
    """更新系统设置"""
    # TODO: 实现设置更新
    return {"status": "not implemented"}
