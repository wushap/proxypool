from __future__ import annotations

import asyncio
import base64
import contextlib
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from proxypool.api.schemas import (
    GeoEnrichRequest,
    ImportFilesRequest,
    ImportTextsRequest,
    ImportSourcesRequest,
    ImportUrlsRequest,
    RunTestRequest,
    SetSingboxRoutesRequest,
    SubscriptionCreateRequest,
    SubscriptionRefreshRequest,
    SubscriptionUpdateProxyRequest,
    SubscriptionUpdateRequest,
)
from proxypool.api.security import is_request_authorized
from proxypool.backend.singbox_manager import SingBoxBackendManager, SingBoxRoute
from proxypool.collector.service import CollectorService
from proxypool.geoip.service import GeoIPService
from proxypool.scheduler.jobs import SchedulerService
from proxypool.settings import AppSettings, load_settings
from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.tasks.manager import TaskManager
from proxypool.tester.service import TesterService
from proxypool.tester.singbox import SingboxProber


def create_app(settings: AppSettings | None = None) -> FastAPI:
    cfg = settings or load_settings()

    storage = SQLiteProxyStorage(cfg.db_path)
    collector = CollectorService(storage, singbox_binary=cfg.singbox_binary)
    prober = SingboxProber(binary=cfg.singbox_binary, test_url=cfg.test_url)
    tester = TesterService(storage, prober=prober)
    geoip = GeoIPService(storage, proxy_json_fetcher=prober.fetch_json_via_proxy)
    scheduler = SchedulerService(collector, tester)
    task_manager = TaskManager()
    singbox_manager = SingBoxBackendManager(
        storage=storage,
        binary=cfg.singbox_binary,
        test_url=cfg.test_url,
        routes_file=cfg.singbox_routes_file,
        runtime_config_file=cfg.singbox_runtime_config_file,
        log_file=cfg.singbox_runtime_log_file,
        backend_engine=cfg.backend_engine,
        auto_restart_max=cfg.backend_auto_restart_max,
    )

    app = FastAPI(title="Proxy Pool", version="0.1.0")
    app.state.settings = cfg
    app.state.storage = storage
    app.state.collector = collector
    app.state.tester = tester
    app.state.geoip = geoip
    app.state.scheduler = scheduler
    app.state.task_manager = task_manager
    app.state.singbox_manager = singbox_manager
    app.state.backend_health_task = None

    async def _backend_health_loop() -> None:
        interval = max(5, int(cfg.backend_health_check_sec))
        while True:
            await asyncio.sleep(interval)
            try:
                singbox_manager.health_check(timeout_sec=1.5, auto_restart=True)
            except Exception:
                # health loop must not crash the API process
                continue

    @app.on_event("startup")
    async def on_startup() -> None:
        app.state.backend_health_task = asyncio.create_task(_backend_health_loop())

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        task = app.state.backend_health_task
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        app.state.backend_health_task = None

    @app.middleware("http")
    async def api_key_guard(request: Request, call_next):
        header_key = request.headers.get("X-API-Key", "")
        if not is_request_authorized(request.method, request.url.path, header_key, cfg.api_key):
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "time": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/api/stats")
    async def stats() -> dict:
        return storage.get_stats()

    @app.get("/api/tasks")
    async def list_tasks(limit: int = Query(default=30, ge=1, le=200)) -> dict:
        return {"items": task_manager.list_tasks(limit=limit)}

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str) -> dict:
        task = task_manager.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    @app.get("/api/backend/status")
    async def backend_status() -> dict:
        return singbox_manager.status()

    @app.get("/api/backend/routes")
    async def backend_routes() -> dict:
        return {"routes": singbox_manager.status()["routes"]}

    @app.get("/api/backend/latency")
    async def backend_latency(
        timeout_sec: float = Query(default=10.0, ge=1.0, le=60.0),
    ) -> dict:
        return {
            "running": singbox_manager.is_running(),
            "items": singbox_manager.measure_all_routes_latency(timeout_sec=timeout_sec),
        }

    @app.get("/api/backend/process-events")
    async def backend_process_events(limit: int = Query(default=100, ge=1, le=500)) -> dict:
        return {
            "items": storage.list_backend_process_events(limit=limit),
        }

    @app.post("/api/backend/routes")
    async def backend_set_routes(body: SetSingboxRoutesRequest) -> dict:
        routes = [
            SingBoxRoute(
                inbound_port=item.inbound_port,
                proxy_key=item.proxy_key,
                front_proxy_key=item.front_proxy_key,
                middle_proxy_key=item.middle_proxy_key,
                exit_proxy_key=item.exit_proxy_key,
                inbound_type=item.inbound_type,
                listen=item.listen,
            )
            for item in body.routes
        ]
        try:
            singbox_manager.set_routes(routes, auto_restart=body.auto_restart)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return singbox_manager.status()

    @app.post("/api/backend/start")
    async def backend_start() -> dict:
        try:
            singbox_manager.start()
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return singbox_manager.status()

    @app.post("/api/backend/stop")
    async def backend_stop() -> dict:
        singbox_manager.stop()
        return singbox_manager.status()

    @app.post("/api/backend/restart")
    async def backend_restart() -> dict:
        try:
            singbox_manager.restart()
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return singbox_manager.status()

    @app.get("/api/proxies")
    async def list_proxies(
        limit: int = Query(default=100, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
        protocol: str | None = Query(default=None),
        available: bool | None = Query(default=None),
        source: str | None = Query(default=None),
        geo_filter: str | None = Query(default=None, pattern="^(has|none)$"),
        geo_location: str | None = Query(default=None),
        openai_filter: str | None = Query(default=None, pattern="^(unlocked|blocked|unchecked)$"),
        fallback_front_filter: str | None = Query(default=None, pattern="^(has|none)$"),
        sort_by: str = Query(default="latency"),
        sort_order: str = Query(default="asc"),
    ) -> dict:
        items = storage.list_proxies_filtered(
            limit=limit,
            offset=offset,
            protocol=protocol,
            available=available,
            source_keyword=source,
            geo_filter=geo_filter,
            geo_location=geo_location,
            openai_filter=openai_filter,
            fallback_front_filter=fallback_front_filter,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return {
            "total": storage.get_stats()["total"],
            "items": items,
        }

    @app.get("/api/subscription")
    async def subscription(
        protocol: str | None = Query(default=None),
        only_available: bool = Query(default=True),
        limit: int = Query(default=5000, ge=1, le=20000),
        encode_base64: bool = Query(default=False),
    ) -> PlainTextResponse:
        links = storage.get_subscription_links(
            only_available=only_available,
            protocol=protocol,
            limit=limit,
        )
        text = "\n".join(links)
        if encode_base64:
            text = base64.b64encode(text.encode("utf-8")).decode("utf-8")
        return PlainTextResponse(text)

    @app.post("/api/collector/import-files")
    async def import_files(body: ImportFilesRequest) -> dict:
        if not body.paths:
            raise HTTPException(status_code=400, detail="paths is empty")
        paths = [Path(path).expanduser().resolve() for path in body.paths]
        missing = [str(path) for path in paths if not path.exists()]
        if missing:
            raise HTTPException(status_code=400, detail=f"missing files: {missing}")

        report = collector.collect_from_files(paths)
        return _collect_report_to_dict(report)

    @app.post("/api/collector/import-texts")
    async def import_texts(body: ImportTextsRequest) -> dict:
        if not body.items:
            raise HTTPException(status_code=400, detail="items is empty")
        items = [(item.filename, item.content) for item in body.items]
        report = collector.collect_from_text_items(items)
        return _collect_report_to_dict(report)

    @app.post("/api/collector/import-urls")
    async def import_urls(body: ImportUrlsRequest) -> dict:
        if not body.urls:
            raise HTTPException(status_code=400, detail="urls is empty")

        report = collector.collect_from_urls(urls=body.urls, timeout_sec=body.timeout_sec)
        return _collect_report_to_dict(report)

    @app.post("/api/collector/import-sources")
    async def import_sources(body: ImportSourcesRequest) -> dict:
        if not body.sources:
            raise HTTPException(status_code=400, detail="sources is empty")
        report = collector.collect_from_sources(sources=body.sources, timeout_sec=body.timeout_sec)
        return _collect_report_to_dict(report)

    @app.post("/api/collector/import-sources-file")
    async def import_sources_file() -> dict:
        sources = _read_sources_file(cfg.sources_file)
        if not sources:
            raise HTTPException(status_code=400, detail=f"no valid sources in {cfg.sources_file}")
        report = collector.collect_from_sources(sources=sources)
        return _collect_report_to_dict(report)

    @app.post("/api/collector/import-output")
    async def import_output() -> dict:
        paths: list[Path] = []
        for pattern in ("*.txt", "*.yaml", "*.yml"):
            paths.extend(sorted(cfg.output_dir.glob(pattern)))
        report = collector.collect_from_files(paths)
        return _collect_report_to_dict(report)

    @app.get("/api/subscriptions")
    async def list_subscriptions(limit: int = Query(default=200, ge=1, le=5000)) -> dict:
        return {"items": storage.list_subscriptions(limit=limit)}

    @app.post("/api/subscriptions")
    async def create_subscription(body: SubscriptionCreateRequest) -> dict:
        try:
            item = storage.create_subscription(
                name=body.name,
                url=body.url,
                enabled=body.enabled,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item}

    @app.put("/api/subscriptions/{subscription_id}")
    async def update_subscription(subscription_id: int, body: SubscriptionUpdateRequest) -> dict:
        try:
            item = storage.update_subscription(
                subscription_id=subscription_id,
                name=body.name,
                url=body.url,
                enabled=body.enabled,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item}

    @app.get("/api/subscription-update-proxy")
    async def get_subscription_update_proxy() -> dict:
        return {"update_proxy_key": storage.get_subscription_update_proxy_key()}

    @app.put("/api/subscription-update-proxy")
    async def set_subscription_update_proxy(body: SubscriptionUpdateProxyRequest) -> dict:
        key = str(body.update_proxy_key or "").strip()
        if key and storage.get_proxy_by_key(key) is None:
            raise HTTPException(status_code=400, detail="update proxy not found")
        storage.set_subscription_update_proxy_key(key)
        return {"update_proxy_key": key}

    @app.delete("/api/subscriptions/{subscription_id}")
    async def delete_subscription(subscription_id: int) -> dict:
        deleted = storage.delete_subscription(subscription_id)
        if deleted <= 0:
            raise HTTPException(status_code=404, detail="subscription not found")
        return {"deleted": deleted}

    @app.post("/api/subscriptions/delete-unavailable")
    async def delete_unavailable_subscriptions(
        include_disabled: bool = Query(default=False),
    ) -> dict:
        deleted = storage.delete_unavailable_subscriptions(include_disabled=include_disabled)
        return {"deleted": deleted}

    @app.post("/api/subscriptions/{subscription_id}/refresh")
    async def refresh_subscription(subscription_id: int, body: SubscriptionRefreshRequest) -> dict:
        sub = storage.get_subscription(subscription_id)
        if sub is None:
            raise HTTPException(status_code=404, detail="subscription not found")

        report = collector.collect_from_subscription(
            subscription_id=subscription_id,
            subscription_name=str(sub.get("name") or ""),
            subscription_url=str(sub.get("url") or ""),
            timeout_sec=body.timeout_sec,
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

    @app.post("/api/subscriptions/refresh-enabled")
    async def refresh_enabled_subscriptions(
        timeout_sec: float = Query(default=12.0, ge=1.0, le=120.0),
    ) -> dict:
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

    @app.post("/api/proxies/delete-unavailable")
    async def delete_unavailable_proxies() -> dict:
        deleted = storage.delete_unavailable()
        return {"deleted": deleted}

    @app.post("/api/geoip/enrich")
    async def enrich_geoip(body: GeoEnrichRequest) -> dict:
        return geoip.enrich_batch(limit=body.limit, concurrency=body.concurrency)

    @app.post("/api/geoip/ip-purity")
    async def enrich_ip_purity(body: GeoEnrichRequest) -> dict:
        return geoip.enrich_ip_purity_batch(
            limit=body.limit,
            concurrency=body.concurrency,
            only_unchecked=False,
        )

    @app.post("/api/tasks/geoip/start")
    async def start_geoip_task(body: GeoEnrichRequest) -> dict:
        def _runner(update):
            def _progress(payload: dict) -> None:
                update(
                    total=payload.get("total", 0),
                    completed=payload.get("completed", 0),
                    success=payload.get("updated", 0),
                    failed=payload.get("failed", 0),
                    message=f"geoip {payload.get('completed', 0)}/{payload.get('total', 0)}",
                )

            return geoip.enrich_batch(
                limit=body.limit,
                concurrency=body.concurrency,
                progress_cb=_progress,
            )

        task_id = task_manager.start_task("geoip_enrich", _runner)
        return {"task_id": task_id}

    @app.post("/api/tasks/ip-purity/start")
    async def start_ip_purity_task(body: GeoEnrichRequest) -> dict:
        def _runner(update):
            def _progress(payload: dict) -> None:
                update(
                    total=payload.get("total", 0),
                    completed=payload.get("completed", 0),
                    success=payload.get("updated", 0),
                    failed=payload.get("failed", 0),
                    message=f"purity {payload.get('completed', 0)}/{payload.get('total', 0)}",
                )

            return geoip.enrich_ip_purity_batch(
                limit=body.limit,
                concurrency=body.concurrency,
                only_unchecked=False,
                progress_cb=_progress,
            )

        task_id = task_manager.start_task("ip_purity_enrich", _runner)
        return {"task_id": task_id}

    @app.post("/api/tester/run")
    async def run_tester(body: RunTestRequest) -> dict:
        report = await tester.run_batch(
            limit=body.limit,
            concurrency=body.concurrency,
            only_unchecked=body.only_unchecked,
            only_available=body.only_available,
            protocols=body.protocols,
            fallback_front_proxy_keys=body.fallback_front_proxy_keys,
            fallback_front_max_attempts=body.fallback_front_max_attempts,
        )
        return asdict(report)

    @app.post("/api/tasks/tester/start")
    async def start_tester_task(body: RunTestRequest) -> dict:
        def _runner(update):
            def _progress(payload: dict) -> None:
                update(
                    total=payload.get("total", 0),
                    completed=payload.get("completed", 0),
                    success=payload.get("available", 0),
                    failed=payload.get("unavailable", 0),
                    message=f"tester {payload.get('completed', 0)}/{payload.get('total', 0)}",
                )

            report = asyncio.run(
                tester.run_batch(
                    limit=body.limit,
                    concurrency=body.concurrency,
                    only_unchecked=body.only_unchecked,
                    only_available=body.only_available,
                    protocols=body.protocols,
                    fallback_front_proxy_keys=body.fallback_front_proxy_keys,
                    fallback_front_max_attempts=body.fallback_front_max_attempts,
                    progress_cb=_progress,
                )
            )
            return asdict(report)

        task_id = task_manager.start_task("tester_run", _runner)
        return {"task_id": task_id}

    @app.post("/api/tasks/openai-check/start")
    async def start_openai_check_task(body: RunTestRequest) -> dict:
        def _runner(update):
            def _progress(payload: dict) -> None:
                update(
                    total=payload.get("total", 0),
                    completed=payload.get("completed", 0),
                    success=payload.get("available", 0),
                    failed=payload.get("unavailable", 0),
                    message=f"openai {payload.get('completed', 0)}/{payload.get('total', 0)}",
                )

            report = asyncio.run(
                tester.run_openai_check_batch(
                    limit=body.limit,
                    concurrency=body.concurrency,
                    only_available=True,
                    protocols=body.protocols,
                    progress_cb=_progress,
                )
            )
            return asdict(report)

        task_id = task_manager.start_task("openai_check", _runner)
        return {"task_id": task_id}

    @app.post("/api/scheduler/start")
    async def scheduler_start(
        collect_minutes: int = Query(default=60, ge=1),
        test_minutes: int = Query(default=10, ge=1),
        test_limit: int = Query(default=300, ge=1, le=5000),
        test_concurrency: int = Query(default=80, ge=1, le=500),
    ) -> dict:
        output_sources: list[str] = []
        for pattern in ("*.txt", "*.yaml", "*.yml"):
            output_sources.extend([str(path) for path in sorted(cfg.output_dir.glob(pattern))])
        output_sources.extend(_read_sources_file(cfg.sources_file))

        def _start() -> None:
            scheduler.start(
                sources=output_sources,
                collect_minutes=collect_minutes,
                test_minutes=test_minutes,
                test_limit=test_limit,
                test_concurrency=test_concurrency,
            )

        await asyncio.to_thread(_start)
        return {"status": "started"}

    @app.post("/api/scheduler/stop")
    async def scheduler_stop() -> dict:
        scheduler.stop()
        return {"status": "stopped"}

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        html_path = cfg.project_root / "proxypool" / "webui" / "index.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="WebUI not found")
        return html_path.read_text(encoding="utf-8")

    return app


def _read_sources_file(path: Path) -> list[str]:
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


def _collect_report_to_dict(report) -> dict:
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
    if report.total_parsed > 0 or report.total_inserted > 0 or report.total_updated > 0:
        return "success", ""
    if report.total_invalid > 0:
        return "failed", "empty or invalid subscription content"
    return "success", ""
