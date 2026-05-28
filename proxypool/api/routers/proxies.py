"""
代理节点管理路由

提供代理节点的查询、导入、测试、删除、导出等端点。
"""

import asyncio
import base64
import csv
import io
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from proxypool.api.schemas import (
    ImportFilesRequest,
    ImportSourcesRequest,
    ImportUrlsRequest,
    ProxyBatchTestRequest,
)
from proxypool.security.api_helpers import validate_file_path_or_raise

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["代理节点"])


@router.get(
    "/proxies",
    summary="获取代理节点列表",
    description="支持多种过滤条件和排序方式的代理节点查询",
    response_description="代理节点列表",
)
async def list_proxies(
    request: Request,
    limit: int = Query(default=100, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    protocol: str | None = Query(default=None),
    available: bool | None = Query(default=None),
    source: str | None = Query(default=None),
    geo_filter: str | None = Query(default=None, pattern="^(has|none)$"),
    geo_country: str | None = Query(default=None),
    geo_location: str | None = Query(default=None),
    openai_filter: str | None = Query(default=None, pattern="^(unlocked|blocked|unchecked)$"),
    ip_purity_filter: str | None = Query(
        default=None, pattern="^(checked|unchecked|residential|non_residential|unknown)$"
    ),
    fallback_front_filter: str | None = Query(default=None, pattern="^(has|none)$"),
    speed_min_mbps: float | None = Query(default=None, ge=0),
    sort_by: str = Query(default="latency"),
    sort_order: str = Query(default="asc"),
) -> dict:
    """获取代理节点列表。

    支持多种过滤条件和排序方式。
    """
    storage = request.app.state.storage
    items = storage.list_proxies_filtered(
        limit=limit,
        offset=offset,
        protocol=protocol,
        available=available,
        source_keyword=source,
        geo_filter=geo_filter,
        geo_country=geo_country,
        geo_location=geo_location,
        openai_filter=openai_filter,
        ip_purity_filter=ip_purity_filter,
        fallback_front_filter=fallback_front_filter,
        speed_min_mbps=speed_min_mbps,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {
        "total": storage.get_stats()["total"],
        "items": items,
    }


@router.get(
    "/subscription",
    summary="获取订阅链接",
    description="返回代理节点的订阅链接，支持Base64编码",
    response_description="订阅链接文本",
)
async def subscription(
    request: Request,
    protocol: str | None = Query(default=None),
    only_available: bool = Query(default=True),
    limit: int = Query(default=5000, ge=1, le=20000),
    encode_base64: bool = Query(default=False),
) -> PlainTextResponse:
    """获取订阅链接"""
    storage = request.app.state.storage
    links = storage.get_subscription_links(
        only_available=only_available,
        protocol=protocol,
        limit=limit,
    )
    text = "\n".join(links)
    if encode_base64:
        text = base64.b64encode(text.encode()).decode()
    return PlainTextResponse(content=text)


@router.post(
    "/collector/import-files",
    summary="从文件导入代理",
    description="从本地文件或上传的文件中导入代理节点",
    response_description="导入结果",
)
async def import_files(
    body: ImportFilesRequest,
    request: Request,
) -> dict:
    """从文件导入代理"""
    collector = request.app.state.collector
    if not body.paths:
        raise HTTPException(status_code=400, detail="paths is empty")

    # Validate all paths before processing (R03 fix)
    validated_paths = []
    for path_str in body.paths:
        validated_path = validate_file_path_or_raise(path_str)
        if not validated_path.exists():
            raise HTTPException(status_code=400, detail=f"file not found: {validated_path}")
        if not validated_path.is_file():
            raise HTTPException(status_code=400, detail=f"not a file: {validated_path}")
        validated_paths.append(validated_path)

    report = await asyncio.to_thread(collector.collect_from_files, validated_paths)
    return _collect_report_to_dict(report)


@router.post("/collector/import-texts")
async def import_texts(
    body: dict,
    request: Request,
) -> dict:
    """从文本导入代理"""
    collector = request.app.state.collector
    if not body.get("items"):
        raise HTTPException(status_code=400, detail="items is empty")
    items = [(item["filename"], item["content"]) for item in body["items"]]
    report = await asyncio.to_thread(collector.collect_from_text_items, items)
    return _collect_report_to_dict(report)


@router.post("/collector/import-urls")
async def import_urls(
    body: ImportUrlsRequest,
    request: Request,
) -> dict:
    """从URL导入代理"""
    collector = request.app.state.collector
    if not body.urls:
        raise HTTPException(status_code=400, detail="urls is empty")

    report = await asyncio.to_thread(collector.collect_from_urls, body.urls, body.timeout_sec)
    return _collect_report_to_dict(report)


@router.post("/collector/import-sources")
async def import_sources(
    body: ImportSourcesRequest,
    request: Request,
) -> dict:
    """从订阅源导入代理"""
    collector = request.app.state.collector
    if not body.sources:
        raise HTTPException(status_code=400, detail="sources is empty")

    # R06 fix: Validate file path sources before passing to collector
    # URL sources are already validated by ImportSourcesRequest schema
    validated_sources = []
    for source in body.sources:
        if source.startswith(("http://", "https://", "data:", "file://")):
            validated_sources.append(source)
        else:
            # File path - validate for path traversal
            validated_path = validate_file_path_or_raise(source)
            validated_sources.append(str(validated_path))

    report = await asyncio.to_thread(
        collector.collect_from_sources, validated_sources, body.timeout_sec
    )
    return _collect_report_to_dict(report)


@router.post("/collector/import-sources-file")
async def import_sources_file(
    request: Request,
) -> dict:
    """从sources.txt文件导入代理"""
    settings = request.app.state.settings
    collector = request.app.state.collector
    sources = _read_sources_file(settings.sources_file)
    if not sources:
        raise HTTPException(status_code=400, detail=f"no valid sources in {settings.sources_file}")
    report = await asyncio.to_thread(collector.collect_from_sources, sources)
    return _collect_report_to_dict(report)


@router.post("/collector/import-output")
async def import_output(
    request: Request,
) -> dict:
    """从output目录导入代理"""
    settings = request.app.state.settings
    collector = request.app.state.collector
    paths: list[Path] = []
    for pattern in ("*.txt", "*.yaml", "*.yml"):
        paths.extend(sorted(settings.output_dir.glob(pattern)))
    report = await asyncio.to_thread(collector.collect_from_files, paths)
    return _collect_report_to_dict(report)


@router.post("/proxies/delete-unavailable")
async def delete_unavailable_proxies(request: Request) -> dict:
    """删除不可用代理"""
    storage = request.app.state.storage
    deleted = storage.delete_unavailable()
    return {"deleted": deleted}


@router.post("/proxies/delete-selected")
async def delete_selected_proxies(
    body: dict,
    request: Request,
) -> dict:
    """删除选中的代理"""
    storage = request.app.state.storage
    keys = [
        str(key or "").strip() for key in body.get("normalized_keys", []) if str(key or "").strip()
    ]
    if not keys:
        raise HTTPException(status_code=400, detail="normalized_keys is empty")
    deleted = storage.delete_proxies_by_keys(keys)
    return {"deleted": deleted, "requested": len(set(keys))}


@router.post("/geoip/enrich")
async def enrich_geoip(
    body: dict,
    request: Request,
) -> dict:
    """批量增强地理位置信息"""
    # TODO: 实现 GeoIP 增强
    return {"status": "not implemented"}


@router.post("/geoip/ip-purity")
async def enrich_ip_purity(
    body: dict,
    request: Request,
) -> dict:
    """批量增强IP纯净度"""
    # TODO: 实现 IP 纯净度增强
    return {"status": "not implemented"}


def _collect_report_to_dict(report) -> dict:
    """将收集报告转换为字典"""
    from dataclasses import asdict

    return {
        "total_sources": report.total_sources,
        "total_parsed": report.total_parsed,
        "total_inserted": report.total_inserted,
        "total_updated": report.total_updated,
        "total_deduped": report.total_deduped,
        "total_invalid": report.total_invalid,
        "by_source": [asdict(r) for r in report.by_source],
    }


def _read_sources_file(path: Path) -> list[str]:
    """读取sources.txt文件"""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    sources: list[str] = []
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        sources.append(text)


@router.post("/proxies/batch-test")
async def batch_test_proxies(
    body: ProxyBatchTestRequest,
    request: Request,
) -> dict:
    """批量测试代理节点"""
    storage = request.app.state.storage
    tester = request.app.state.tester

    total = len(body.normalized_keys)
    completed = 0
    success = 0
    failed = 0
    results: list[dict] = []

    for key in body.normalized_keys:
        try:
            # Get proxy info
            proxy = storage.get_proxy_by_key(key)
            if proxy is None:
                results.append(
                    {
                        "normalized_key": key,
                        "success": False,
                        "error": "proxy not found",
                    }
                )
                failed += 1
                completed += 1
                continue

            # Test the proxy
            report = await tester.run_one(
                normalized_key=key,
                fallback_front_proxy_keys=[],
                fallback_front_max_attempts=0,
            )

            result_ok = report.available if hasattr(report, "available") else False
            latency_ms = report.latency_ms if hasattr(report, "latency_ms") else None

            results.append(
                {
                    "normalized_key": key,
                    "success": result_ok,
                    "latency_ms": latency_ms,
                }
            )

            if result_ok:
                success += 1
            else:
                failed += 1

            completed += 1
        except Exception as exc:
            results.append(
                {
                    "normalized_key": key,
                    "success": False,
                    "error": str(exc),
                }
            )
            failed += 1
            completed += 1

    return {
        "total": total,
        "completed": completed,
        "success": success,
        "failed": failed,
        "results": results,
    }


@router.get("/proxies/export")
async def export_proxies_csv(
    request: Request,
    protocol: str | None = Query(default=None),
    available: bool | None = Query(default=None),
    source: str | None = Query(default=None),
) -> PlainTextResponse:
    """导出代理列表为CSV格式。

    返回包含代理信息的CSV文件，支持UTF-8 BOM以兼容Excel中文字符显示。
    """
    storage = request.app.state.storage

    # Get all proxies (with optional filters)
    items = storage.list_proxies_filtered(
        limit=10000,
        offset=0,
        protocol=protocol,
        available=available,
        source_keyword=source,
        sort_by="latency",
        sort_order="asc",
    )

    # Create CSV with UTF-8 BOM for Excel compatibility
    output = io.StringIO()
    output.write("﻿")  # UTF-8 BOM

    writer = csv.writer(output)

    # Write headers
    writer.writerow(
        [
            "地址",
            "协议",
            "延迟(ms)",
            "评分",
            "状态",
            "国家",
            "城市",
            "来源",
            "最后检查时间",
            "OpenAI解锁",
        ]
    )

    # Write data rows
    for item in items:
        writer.writerow(
            [
                f"{item.get('host', '')}:{item.get('port', '')}",
                item.get("protocol", ""),
                item.get("latency_ms", ""),
                item.get("score", ""),
                "可用" if item.get("available") else "不可用",
                item.get("country", ""),
                item.get("city", ""),
                item.get("source", ""),
                item.get("last_checked_at", ""),
                "是"
                if item.get("openai_unlocked")
                else "否"
                if item.get("openai_unlocked") is not None
                else "未知",
            ]
        )

    # Generate filename with date
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"proxies-export-{date_str}.csv"

    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )
