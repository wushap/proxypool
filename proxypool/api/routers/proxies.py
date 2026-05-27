"""
代理节点管理路由

提供代理节点的查询、导入、测试、删除等端点。
"""

import base64
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api", tags=["proxies"])


@router.get("/proxies")
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
    ip_purity_filter: str | None = Query(default=None, pattern="^(checked|unchecked|residential|non_residential|unknown)$"),
    fallback_front_filter: str | None = Query(default=None, pattern="^(has|none)$"),
    speed_min_mbps: float | None = Query(default=None, ge=0),
    sort_by: str = Query(default="latency"),
    sort_order: str = Query(default="asc"),
) -> dict:
    """获取代理节点列表"""
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


@router.get("/subscription")
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


@router.post("/collector/import-files")
async def import_files(
    body: dict,
    request: Request,
) -> dict:
    """从文件导入代理"""
    collector = request.app.state.collector
    if not body.get("paths"):
        raise HTTPException(status_code=400, detail="paths is empty")
    paths = [Path(path).expanduser().resolve() for path in body["paths"]]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing files: {missing}")

    report = collector.collect_from_files(paths)
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
    report = collector.collect_from_text_items(items)
    return _collect_report_to_dict(report)


@router.post("/collector/import-urls")
async def import_urls(
    body: dict,
    request: Request,
) -> dict:
    """从URL导入代理"""
    collector = request.app.state.collector
    if not body.get("urls"):
        raise HTTPException(status_code=400, detail="urls is empty")

    report = collector.collect_from_urls(urls=body["urls"], timeout_sec=body.get("timeout_sec"))
    return _collect_report_to_dict(report)


@router.post("/collector/import-sources")
async def import_sources(
    body: dict,
    request: Request,
) -> dict:
    """从订阅源导入代理"""
    collector = request.app.state.collector
    if not body.get("sources"):
        raise HTTPException(status_code=400, detail="sources is empty")
    report = collector.collect_from_sources(sources=body["sources"], timeout_sec=body.get("timeout_sec"))
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
    report = collector.collect_from_sources(sources=sources)
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
    report = collector.collect_from_files(paths)
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
    keys = [str(key or "").strip() for key in body.get("normalized_keys", []) if str(key or "").strip()]
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
    return sources
