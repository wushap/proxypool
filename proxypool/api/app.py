from __future__ import annotations

import asyncio
import base64
import contextlib
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from proxypool.api.schemas import (
    BackendInstanceCreateRequest,
    BackendPortRangeRequest,
    BackendDefaultListenRequest,
    ChainInstanceCreateRequest,
    GeoEnrichRequest,
    ImportFilesRequest,
    ImportTextsRequest,
    ImportSourcesRequest,
    ImportUrlsRequest,
    ProxyPoolChainConfigRequest,
    ProxyPoolCreateRequest,
    ProxyPoolUpdateRequest,
    PublishedSubscriptionCreateRequest,
    PublishedSubscriptionUpdateRequest,
    RunTestRequest,
    SetSingboxRoutesRequest,
    SingleProxyTestRequest,
    SubscriptionCreateRequest,
    SubscriptionRefreshRequest,
    SubscriptionUpdateProxyRequest,
    SubscriptionUpdateRequest,
)
from proxypool.api.security import is_request_authorized
from proxypool.backend.chain_instance_manager import ChainInstanceManager
from proxypool.backend.mihomo_manager import MihomoEgressBackend
from proxypool.backend.singbox_manager import SingBoxBackendManager, SingBoxRoute
from proxypool.backend.resin_manager import ResinBackendManager
from proxypool.backend.resin_client import ResinClient
from proxypool.pool.service import ProxyPoolService
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
    tester.replace_failed_proxy_cb = singbox_manager.replace_failed_exit_proxy

    resin_manager = ResinBackendManager(
        binary=cfg.resin_binary,
        port=cfg.resin_port,
        admin_token=cfg.resin_admin_token,
        proxy_token=cfg.resin_proxy_token,
        auth_version=cfg.resin_auth_version,
        data_dir=cfg.resin_data_dir,
        log_file=Path(str(cfg.singbox_runtime_log_file).replace("singbox", "resin")),
        runtime_dir=cfg.singbox_runtime_config_file.parent,
    )
    resin_base_url = f"http://127.0.0.1:{cfg.resin_port}"
    resin_client = ResinClient(base_url=resin_base_url, admin_token=cfg.resin_admin_token)
    pool_service = ProxyPoolService(
        storage=storage,
        resin_manager=resin_manager,
        resin_client=resin_client,
    )

    # Initialize ProxyChainService
    from proxypool.pool.chain_service import ProxyChainService
    from proxypool.pool.health_manager import HealthConfig
    chain_service = ProxyChainService(
        storage=storage,
        singbox_binary=cfg.singbox_binary,
        test_url=cfg.test_url,
        health_config=HealthConfig(),
    )
    chain_backend = MihomoEgressBackend(
        binary=cfg.mihomo_binary,
        runtime_dir=cfg.mihomo_runtime_dir,
    )
    chain_instance_manager = ChainInstanceManager(storage=storage, backend=chain_backend)

    app = FastAPI(title="Proxy Pool", version="0.1.0")
    app.state.settings = cfg
    app.state.storage = storage
    app.state.collector = collector
    app.state.tester = tester
    app.state.geoip = geoip
    app.state.scheduler = scheduler
    app.state.task_manager = task_manager
    app.state.singbox_manager = singbox_manager
    app.state.resin_manager = resin_manager
    app.state.resin_client = resin_client
    app.state.pool_service = pool_service
    app.state.chain_service = chain_service
    app.state.chain_instance_manager = chain_instance_manager
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
        # Start Resin if it was running before (persisted) or resin_auto_start is set.
        if resin_manager.get_desired_running() or cfg.resin_auto_start:
            if not resin_manager.is_running():
                try:
                    resin_manager.start()
                except Exception:
                    pass

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

    @app.post("/api/tasks/{task_id}/stop")
    async def stop_task(task_id: str) -> dict:
        stopped = task_manager.stop_task(task_id)
        task = task_manager.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return {"stopped": bool(stopped), "task": task}

    @app.delete("/api/tasks/{task_id}")
    async def delete_task(task_id: str) -> dict:
        task = task_manager.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        deleted = task_manager.delete_task(task_id)
        if deleted:
            return {"deleted": True, "task_id": task_id}
        latest = task_manager.get_task(task_id)
        return {"deleted": False, "task": latest}

    @app.get("/api/backend/status")
    async def backend_status() -> dict:
        return singbox_manager.status()

    @app.get("/api/backend/routes")
    async def backend_routes() -> dict:
        return {"routes": singbox_manager.status()["routes"]}

    @app.get("/api/backend/default-port-range")
    async def backend_default_port_range() -> dict:
        return storage.get_backend_default_port_range()

    @app.put("/api/backend/default-port-range")
    async def backend_set_default_port_range(body: BackendPortRangeRequest) -> dict:
        try:
            return storage.set_backend_default_port_range(start=body.start, end=body.end)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/backend/default-listen")
    async def backend_default_listen() -> dict:
        return {"listen": storage.get_backend_default_listen()}

    @app.put("/api/backend/default-listen")
    async def backend_set_default_listen(body: BackendDefaultListenRequest) -> dict:
        try:
            return {"listen": storage.set_backend_default_listen(body.listen)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/backend/instances")
    async def backend_instances() -> dict:
        return {"items": singbox_manager.list_instances()}

    @app.post("/api/backend/instances")
    async def backend_instance_create(body: BackendInstanceCreateRequest) -> dict:
        try:
            item = singbox_manager.create_instance(body.instance_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item, "items": singbox_manager.list_instances()}

    @app.post("/api/backend/instances/{instance_id}/start")
    async def backend_instance_start(instance_id: str) -> dict:
        try:
            singbox_manager.start_instance(instance_id=instance_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return singbox_manager.status()

    @app.post("/api/backend/instances/{instance_id}/stop")
    async def backend_instance_stop(instance_id: str) -> dict:
        singbox_manager.stop_instance(instance_id=instance_id)
        return singbox_manager.status()

    @app.get("/api/backend/instances/{instance_id}/routes")
    async def backend_instance_routes(instance_id: str) -> dict:
        return {
            "instance_id": instance_id,
            "routes": [asdict(route) for route in singbox_manager.get_instance_routes(instance_id)],
        }

    @app.post("/api/backend/instances/{instance_id}/routes")
    async def backend_instance_set_routes(instance_id: str, body: SetSingboxRoutesRequest) -> dict:
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
            singbox_manager.set_instance_routes(instance_id, routes, auto_restart=body.auto_restart)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"instance_id": instance_id, "routes": [asdict(route) for route in singbox_manager.get_instance_routes(instance_id)]}

    @app.delete("/api/backend/instances/{instance_id}")
    async def backend_instance_delete(instance_id: str) -> dict:
        return {
            "deleted": singbox_manager.delete_instance(instance_id=instance_id),
            "items": singbox_manager.list_instances(),
        }

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
        geo_country: str | None = Query(default=None),
        geo_location: str | None = Query(default=None),
        openai_filter: str | None = Query(default=None, pattern="^(unlocked|blocked|unchecked)$"),
        ip_purity_filter: str | None = Query(default=None, pattern="^(checked|unchecked|residential|non_residential|unknown)$"),
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
            geo_country=geo_country,
            geo_location=geo_location,
            openai_filter=openai_filter,
            ip_purity_filter=ip_purity_filter,
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

    def _published_subscription_payload(item: dict) -> dict:
        out = dict(item)
        out["export_url"] = f"/api/published-subscriptions/{item['id']}/subscription"
        return out

    @app.get("/api/published-subscriptions")
    async def list_published_subscriptions(limit: int = Query(default=200, ge=1, le=5000)) -> dict:
        return {
            "items": [
                _published_subscription_payload(item)
                for item in storage.list_published_subscriptions(limit=limit)
            ]
        }

    @app.post("/api/published-subscriptions")
    async def create_published_subscription(body: PublishedSubscriptionCreateRequest) -> dict:
        try:
            item = storage.create_published_subscription(
                name=body.name,
                filters=body.filters,
                enabled=body.enabled,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": _published_subscription_payload(item)}

    @app.put("/api/published-subscriptions/{subscription_id}")
    async def update_published_subscription(subscription_id: int, body: PublishedSubscriptionUpdateRequest) -> dict:
        try:
            item = storage.update_published_subscription(
                subscription_id=subscription_id,
                name=body.name,
                filters=body.filters,
                enabled=body.enabled,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": _published_subscription_payload(item)}

    @app.delete("/api/published-subscriptions/{subscription_id}")
    async def delete_published_subscription(subscription_id: int) -> dict:
        deleted = storage.delete_published_subscription(subscription_id)
        if deleted <= 0:
            raise HTTPException(status_code=404, detail="published subscription not found")
        return {"deleted": deleted}

    @app.get("/api/published-subscriptions/{subscription_id}/subscription")
    async def published_subscription(
        subscription_id: int,
        limit: int = Query(default=5000, ge=1, le=20000),
        encode_base64: bool = Query(default=False),
    ) -> PlainTextResponse:
        item = storage.get_published_subscription(subscription_id)
        if item is None:
            raise HTTPException(status_code=404, detail="published subscription not found")
        if not item.get("enabled"):
            raise HTTPException(status_code=404, detail="published subscription disabled")
        links = storage.get_published_subscription_links(subscription_id, limit=limit)
        text = "\n".join(links)
        if encode_base64:
            text = base64.b64encode(text.encode("utf-8")).decode("utf-8")
        return PlainTextResponse(text)

    @app.post("/api/subscriptions/{subscription_id}/refresh")
    async def refresh_subscription(subscription_id: int, body: SubscriptionRefreshRequest) -> dict:
        sub = storage.get_subscription(subscription_id)
        if sub is None:
            raise HTTPException(status_code=404, detail="subscription not found")

        def _refresh_one() -> dict:
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

        return await asyncio.to_thread(_refresh_one)

    @app.post("/api/subscriptions/refresh-enabled")
    async def refresh_enabled_subscriptions(
        timeout_sec: float = Query(default=12.0, ge=1.0, le=120.0),
    ) -> dict:
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

    @app.post("/api/tasks/subscriptions-refresh/start")
    async def start_refresh_enabled_subscriptions_task(
        timeout_sec: float = Query(default=12.0, ge=1.0, le=120.0),
    ) -> dict:
        def runner(update, should_stop) -> dict:
            subscriptions = storage.list_enabled_subscriptions()
            total = len(subscriptions)
            items: list[dict] = []
            success = 0
            failed = 0
            update(total=total, completed=0, success=0, failed=0, message=f"queued {total} subscriptions")

            for idx, sub in enumerate(subscriptions, start=1):
                if should_stop():
                    break
                sub_id = int(sub.get("id") or 0)
                sub_name = str(sub.get("name") or "")
                update(
                    total=total,
                    completed=idx - 1,
                    success=success,
                    failed=failed,
                    message=f"refreshing {sub_name or sub_id} ({idx}/{total})",
                )
                report = collector.collect_from_subscription(
                    subscription_id=sub_id,
                    subscription_name=sub_name,
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
                        "name": sub_name,
                        "status": status,
                        "error": error,
                        "report": _collect_report_to_dict(report),
                    }
                )
                if status == "success":
                    success += 1
                else:
                    failed += 1
                update(
                    total=total,
                    completed=idx,
                    success=success,
                    failed=failed,
                    message=f"finished {sub_name or sub_id} ({idx}/{total})",
                    result={"count": len(items), "items": items},
                )

            return {"count": len(items), "items": items}

        task_id = task_manager.start_task("subscriptions_refresh", runner)
        task = task_manager.get_task(task_id)
        return {"task_id": task_id, "task": task}

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
        def _runner(update, should_stop):
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
                stop_cb=should_stop,
            )

        task_id = task_manager.start_task("geoip_enrich", _runner)
        return {"task_id": task_id}

    @app.post("/api/tasks/ip-purity/start")
    async def start_ip_purity_task(body: GeoEnrichRequest) -> dict:
        def _runner(update, should_stop):
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
                stop_cb=should_stop,
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
            only_unavailable=body.only_unavailable,
            min_last_checked_age_hours=body.min_last_checked_age_hours,
            protocols=body.protocols,
            fallback_front_proxy_keys=body.fallback_front_proxy_keys,
            fallback_front_max_attempts=body.fallback_front_max_attempts,
            replace_failed_with_available=body.replace_failed_with_available,
        )
        return asdict(report)

    @app.post("/api/tester/run-one")
    async def run_single_proxy_test(body: SingleProxyTestRequest) -> dict:
        key = str(body.normalized_key or "").strip()
        if not key:
            raise HTTPException(status_code=400, detail="normalized_key is empty")
        if storage.get_proxy_by_key(key) is None:
            raise HTTPException(status_code=404, detail="proxy not found")
        try:
            result = await tester.run_one(
                normalized_key=key,
                fallback_front_proxy_keys=body.fallback_front_proxy_keys,
                fallback_front_max_attempts=body.fallback_front_max_attempts,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return asdict(result)

    @app.post("/api/tasks/tester/start")
    async def start_tester_task(body: RunTestRequest) -> dict:
        def _runner(update, should_stop):
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

        task_id = task_manager.start_task("tester_run", _runner)
        return {"task_id": task_id}

    @app.post("/api/tasks/openai-check/start")
    async def start_openai_check_task(body: RunTestRequest) -> dict:
        def _runner(update, should_stop):
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
                    stop_cb=should_stop,
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

    # ---- Proxy Pool endpoints ----

    @app.get("/api/pools")
    async def list_pools() -> dict:
        return {"items": pool_service.list_pools()}

    @app.post("/api/pools")
    async def create_pool(body: ProxyPoolCreateRequest) -> dict:
        try:
            item = pool_service.create_pool(
                name=body.name,
                filters=body.filters,
                listen=body.listen,
                inbound_type=body.inbound_type,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item}

    @app.get("/api/pools/{pool_id}")
    async def get_pool(pool_id: int) -> dict:
        item = pool_service.get_pool(pool_id)
        if item is None:
            raise HTTPException(status_code=404, detail="pool not found")
        return {"item": item}

    @app.put("/api/pools/{pool_id}")
    async def update_pool(pool_id: int, body: ProxyPoolUpdateRequest) -> dict:
        try:
            item = pool_service.update_pool(pool_id, **body.model_dump(exclude_none=True))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item}

    @app.get("/api/pools/{pool_id}/chain")
    async def get_pool_chain(pool_id: int) -> dict:
        item = pool_service.get_pool_chain_config(pool_id)
        if item is None:
            raise HTTPException(status_code=404, detail="pool not found")
        return {"item": item}

    @app.put("/api/pools/{pool_id}/chain")
    async def update_pool_chain(pool_id: int, body: ProxyPoolChainConfigRequest) -> dict:
        try:
            item = pool_service.update_pool_chain_config(pool_id, **body.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"item": item}

    @app.get("/api/pools/{pool_id}/chain/instances")
    async def list_pool_chain_instances(pool_id: int) -> dict:
        item = pool_service.get_pool(pool_id)
        if item is None:
            raise HTTPException(status_code=404, detail="pool not found")
        return {"items": chain_instance_manager.list_instances(pool_id=pool_id)}

    @app.post("/api/pools/{pool_id}/chain/instances")
    async def create_pool_chain_instance(pool_id: int, body: ChainInstanceCreateRequest) -> dict:
        item = pool_service.get_pool(pool_id)
        if item is None:
            raise HTTPException(status_code=404, detail="pool not found")
        created = chain_instance_manager.create_instance(
            instance_id=body.instance_id,
            pool_id=pool_id,
            front_node_key=body.front_node_key,
            exit_node_key=body.exit_node_key,
            listen=body.listen,
            port=body.port,
            inbound_type=body.inbound_type,
        )
        return {"item": created, "items": chain_instance_manager.list_instances(pool_id=pool_id)}

    @app.delete("/api/pools/{pool_id}")
    async def delete_pool(pool_id: int) -> dict:
        deleted = pool_service.delete_pool(pool_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="pool not found")
        return {"deleted": True}

    @app.post("/api/pools/{pool_id}/sync")
    async def sync_pool(pool_id: int) -> dict:
        try:
            item = pool_service.sync_pool(pool_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item}

    @app.post("/api/pools/{pool_id}/start")
    async def start_pool(pool_id: int) -> dict:
        try:
            item = pool_service.start_pool(pool_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item}

    @app.post("/api/pools/{pool_id}/stop")
    async def stop_pool(pool_id: int) -> dict:
        try:
            item = pool_service.stop_pool(pool_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item}

    # ---- Resin backend management endpoints ----

    @app.get("/api/resin/status")
    async def resin_status() -> dict:
        return resin_manager.status()

    @app.post("/api/resin/start")
    async def resin_start() -> dict:
        try:
            resin_manager.start()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return resin_manager.status()

    @app.post("/api/resin/stop")
    async def resin_stop() -> dict:
        resin_manager.stop()
        return resin_manager.status()

    @app.post("/api/resin/restart")
    async def resin_restart() -> dict:
        try:
            resin_manager.restart()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return resin_manager.status()

    @app.get("/api/resin/info")
    async def resin_info() -> dict:
        if not resin_manager.is_running():
            raise HTTPException(status_code=503, detail="resin not running")
        return resin_client.get_system_info()

    @app.get("/api/resin/nodes")
    async def resin_nodes(
        limit: int = Query(default=200, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
    ) -> dict:
        if not resin_manager.is_running():
            raise HTTPException(status_code=503, detail="resin not running")
        return resin_client.list_nodes(limit=limit, offset=offset)

    # ---- Resin reverse proxy ----
    # The Resin UI is a Vite SPA with base="/ui/".  Its compiled JS
    # checks ``window.location.pathname`` at startup and refuses to
    # render unless the path begins with "/ui/".  We therefore
    # expose the Resin UI at ``/ui/`` (not ``/resin/ui/``) and
    # redirect ``/resin`` → ``/ui/`` for convenience.
    #
    # API calls from the SPA (``fetch("/api/v1/...")``) are routed
    # to the Resin backend via a dedicated ``/api/v1/{path}`` route.
    # The Proxy Pool's own API lives at ``/api/...`` (no ``v1``)
    # so there is no conflict.

    @app.get("/resin")
    async def resin_root_redirect():
        return RedirectResponse(url="/ui/")

    @app.get("/resin/")
    async def resin_slash_redirect():
        return RedirectResponse(url="/ui/")

    _RESIN_PROXY_SKIP_HEADERS = frozenset({"host", "transfer-encoding", "connection", "keep-alive"})

    async def _resin_proxy_rewrite(prefix: str, path: str, request: Request) -> Response:
        """Forward *request* to ``http://127.0.0.1:{port}/{prefix}/{path}``."""
        full_path = f"{prefix}/{path}" if prefix else path
        target = f"http://127.0.0.1:{cfg.resin_port}/{full_path}"
        qs = str(request.url.query)
        if qs:
            target += f"?{qs}"
        headers = {k: v for k, v in request.headers.items() if k.lower() not in _RESIN_PROXY_SKIP_HEADERS}
        body = await request.body()
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method=request.method,
                url=target,
                headers=headers,
                content=body,
                follow_redirects=True,
            )
        resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in _RESIN_PROXY_SKIP_HEADERS}
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=resp_headers,
            media_type=resp.headers.get("content-type"),
        )

    @app.api_route("/resin/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    async def resin_api_proxy(path: str, request: Request) -> Response:
        return await _resin_proxy_rewrite("api", path, request)

    @app.api_route("/resin/healthz", methods=["GET", "HEAD"])
    async def resin_healthz_proxy(request: Request) -> Response:
        return await _resin_proxy_rewrite("", "healthz", request)

    @app.api_route("/ui/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    async def resin_ui_proxy(path: str, request: Request) -> Response:
        """Proxy Resin Web UI.  Must live at ``/ui/...`` so that the
        Vite SPA's pathname check passes."""
        return await _proxy_to_resin(f"ui/{path}", request)

    @app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    async def resin_api_v1_proxy(path: str, request: Request) -> Response:
        """Proxy Resin REST API (``/api/v1/...``) so that the Resin
        SPA can fetch data when loaded at ``/ui/..."."""
        return await _proxy_to_resin(f"api/v1/{path}", request)

    async def _proxy_to_resin(path: str, request: Request) -> Response:
        target = f"http://127.0.0.1:{cfg.resin_port}/{path}"
        qs = str(request.url.query)
        if qs:
            target += f"?{qs}"
        headers = {k: v for k, v in request.headers.items() if k.lower() not in _RESIN_PROXY_SKIP_HEADERS}
        body = await request.body()
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method=request.method,
                url=target,
                headers=headers,
                content=body,
                follow_redirects=True,
            )
        resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in _RESIN_PROXY_SKIP_HEADERS}
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=resp_headers,
            media_type=resp.headers.get("content-type"),
        )

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        html_path = cfg.project_root / "proxypool" / "webui" / "index.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="WebUI not found")
        return html_path.read_text(encoding="utf-8")

    # Serve webui static assets (css/, js/)
    _webui_dir = cfg.project_root / "proxypool" / "webui"
    if _webui_dir.is_dir():
        app.mount("/css", StaticFiles(directory=str(_webui_dir / "css")), name="webui-css")
        app.mount("/js", StaticFiles(directory=str(_webui_dir / "js")), name="webui-js")

    # ------------------------------------------------------------------
    # Proxy Chain API Routes
    # ------------------------------------------------------------------

    @app.get("/api/chain/status")
    async def chain_status() -> dict:
        """Get proxy chain service status."""
        chain_service.initialize()
        return chain_service.get_pool_status(refresh=True)

    @app.get("/api/chain/health")
    async def chain_health() -> dict:
        """Get health manager status."""
        return chain_service.get_health_status()

    @app.post("/api/chain/pools/{pool_type}")
    async def update_chain_pool(
        pool_type: str,
        regex_filters: list[str] | None = Query(default=None, description="Regex filters for pool"),
    ) -> dict:
        """Update proxy chain pool configuration."""
        if pool_type not in ("front", "exit"):
            raise HTTPException(status_code=400, detail="pool_type must be 'front' or 'exit'")
        chain_service.initialize()
        return chain_service.update_pool_config(pool_type, list(regex_filters or []))

    @app.get("/api/chain/route")
    async def chain_route(
        session_id: str = "",
        pool_id: int = 0,
        target_domain: str = "",
    ) -> dict:
        """Route a request through the proxy chain."""
        chain_service.initialize()
        result = chain_service.route_request(session_id, pool_id, target_domain)
        if result is None:
            raise HTTPException(status_code=503, detail="No available nodes for routing")
        return result

    @app.get("/api/chain/leases")
    async def chain_leases(
        pool_id: int | None = None,
    ) -> dict:
        """Get sticky leases."""
        chain_service.initialize()
        return {"leases": chain_service.get_leases(pool_id)}

    @app.post("/api/chain/leases/cleanup")
    async def chain_leases_cleanup() -> dict:
        """Cleanup expired sticky leases."""
        chain_service.initialize()
        removed = chain_service.cleanup_leases()
        return {"removed": removed}

    @app.post("/api/chain/start")
    async def chain_start() -> dict:
        """Start the proxy chain service."""
        chain_service.start()
        return {"status": "started"}

    @app.post("/api/chain/stop")
    async def chain_stop() -> dict:
        """Stop the proxy chain service."""
        chain_service.stop()
        return {"status": "stopped"}

    @app.get("/api/chain/nodes")
    async def chain_nodes(
        pool_type: str = "all",
        healthy_only: bool = False,
    ) -> dict:
        """Get nodes from pools."""
        chain_service.initialize()
        status = chain_service.get_pool_status(refresh=True)

        if pool_type == "front":
            nodes = status["front_pool"]["nodes"]
        elif pool_type == "exit":
            nodes = status["exit_pool"]["nodes"]
        else:
            nodes = status["front_pool"]["nodes"] + status["exit_pool"]["nodes"]

        if healthy_only:
            nodes = [n for n in nodes if n["healthy"]]

        return {"nodes": nodes, "total": len(nodes)}

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
