from __future__ import annotations

import asyncio
import base64
import contextlib
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from proxypool.api.schemas import (
    AutoTaskConfigRequest,
    BackendInstanceCreateRequest,
    BackendPortRangeRequest,
    BackendDefaultListenRequest,
    ChainInstanceCreateRequest,
    GeoEnrichRequest,
    ImportFilesRequest,
    ImportTextsRequest,
    ImportSourcesRequest,
    ImportUrlsRequest,
    HttpGatewayConfigRequest,
    HttpProxyEndpointCreateRequest,
    HttpProxyEndpointServiceConfigRequest,
    HttpProxyEndpointUpdateRequest,
    HttpGatewayTestRequest,
    ProxyBulkDeleteRequest,
    ProxyPoolChainConfigRequest,
    ProxyPoolCreateRequest,
    PoolSessionRuleUpsertRequest,
    ProxyPoolUpdateRequest,
    PublishedSubscriptionCreateRequest,
    PublishedSubscriptionUpdateRequest,
    RunTestRequest,
    SetSingboxRoutesRequest,
    SingleProxyTestRequest,
    SpeedTestRequest,
    StickyLeaseInheritRequest,
    SubscriptionCreateRequest,
    SubscriptionRefreshRequest,
    SubscriptionUpdateProxyRequest,
    SubscriptionUpdateRequest,
)
from proxypool.api.security import is_request_authorized
from proxypool.backend.chain_instance_manager import ChainInstanceManager
from proxypool.gateway.config_service import HttpGatewayConfigService
from proxypool.gateway.forward_proxy import ForwardProxyGateway
from proxypool.gateway.http_gateway import GatewayError, UnifiedHttpGateway
from proxypool.gateway.runtime import ForwardProxyGatewayRuntimeManager
from proxypool.backend.mihomo_config import _build_mihomo_proxy
from proxypool.backend.mihomo_manager import MihomoEgressBackend
from proxypool.backend.singbox_manager import SingBoxBackendManager, SingBoxRoute
from proxypool.pool.service import ProxyPoolService
from proxypool.collector.service import CollectorService
from proxypool.geoip.service import GeoIPService
from proxypool.scheduler.jobs import SchedulerService
from proxypool.settings import AppSettings, load_settings
from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.tasks.manager import TaskManager
from proxypool.tester.service import TesterService
from proxypool.tester.singbox import SingboxProber

# 导入 Router 模块
from proxypool.api.routers import register_routers
from proxypool.api.routers.gateway import _request_via_forward_proxy


async def _request_via_forward_proxy(
    target_url: str,
    proxy_url: str,
    proxy_headers: dict[str, str],
    timeout_sec: float = 15.0,
) -> dict:
    started = time.perf_counter()
    try:
        proxy = httpx.Proxy(proxy_url, headers=proxy_headers or None)
        async with httpx.AsyncClient(proxy=proxy, timeout=httpx.Timeout(timeout_sec), trust_env=False) as client:
            resp = await client.get(
                target_url,
                headers={
                    "Accept": "*/*",
                    "User-Agent": "proxypool-gateway-test/1.0",
                },
            )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        preview = ""
        with contextlib.suppress(Exception):
            preview = resp.text[:2048]
        return {
            "request_ok": True,
            "status_code": int(resp.status_code),
            "elapsed_ms": elapsed_ms,
            "body_preview": preview,
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "request_ok": False,
            "elapsed_ms": elapsed_ms,
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }


def _default_auto_task_config() -> dict:
    return {
        "enabled": False,
        "subscription_refresh_enabled": True,
        "subscription_refresh_minutes": 60,
        "tester_enabled": False,
        "tester_minutes": 60,
        "tester_limit": 0,
        "tester_concurrency": 50,
        "speed_test_enabled": False,
        "speed_test_minutes": 120,
        "speed_test_url": "https://speed.cloudflare.com/__down?bytes=10000000",
        "speed_test_limit": 0,
        "speed_test_timeout_sec": 30.0,
    }


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

    pool_service = ProxyPoolService(
        storage=storage,
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
    unified_gateway = UnifiedHttpGateway(
        storage=storage,
        pool_service=pool_service,
        chain_service=chain_service,
        chain_instance_manager=chain_instance_manager,
    )
    gateway_config_service = HttpGatewayConfigService(storage)
    forward_gateway = ForwardProxyGateway(
        storage=storage,
        pool_service=pool_service,
        chain_service=chain_service,
        chain_instance_manager=chain_instance_manager,
        config=gateway_config_service.get_config(),
    )
    gateway_runtime = ForwardProxyGatewayRuntimeManager(
        storage=storage,
        pool_service=pool_service,
        chain_service=chain_service,
        chain_instance_manager=chain_instance_manager,
        config_service=gateway_config_service,
        legacy_gateway=forward_gateway,
    )

    def _proxy_status_summary(proxy: dict | None, active_key: str = "") -> dict:
        if proxy is None:
            return {}
        key = str(proxy.get("normalized_key") or "")
        return {
            "key": key,
            "name": str(proxy.get("name") or ""),
            "protocol": str(proxy.get("protocol") or ""),
            "host": str(proxy.get("host") or ""),
            "port": int(proxy.get("port") or 0),
            "available": bool(proxy.get("available")),
            "healthy": bool(proxy.get("available")),
            "active": bool(active_key and key == active_key),
            "latency_ms": proxy.get("latency_ms"),
            "speed_mbps": proxy.get("speed_mbps"),
            "country": str(proxy.get("country") or ""),
            "city": str(proxy.get("city") or ""),
            "resolved_ip": str(proxy.get("resolved_ip") or ""),
            "openai_unlocked": proxy.get("openai_unlocked"),
            "last_checked_at": str(proxy.get("last_checked_at") or ""),
        }

    def _latest_active_hop_keys(endpoint_id: int, leases: list[dict], instances: list[dict]) -> list[str]:
        live_ids = {
            str(item.get("instance_id") or "")
            for item in instances
            if str(item.get("status") or "") == "running"
        }
        lease_candidates = [
            item for item in leases
            if list(item.get("hop_node_keys") or [])
            and (not live_ids or str(item.get("instance_id") or "") in live_ids)
        ]
        lease_candidates.sort(key=lambda item: str(item.get("last_accessed") or ""), reverse=True)
        if lease_candidates:
            return [str(key) for key in list(lease_candidates[0].get("hop_node_keys") or [])]
        instance_candidates = [
            item for item in instances
            if int(item.get("endpoint_id") or 0) == int(endpoint_id)
            and list(item.get("hop_node_keys") or [])
        ]
        instance_candidates.sort(
            key=lambda item: (str(item.get("status") or "") == "running", str(item.get("updated_at") or "")),
            reverse=True,
        )
        if instance_candidates:
            return [str(key) for key in list(instance_candidates[0].get("hop_node_keys") or [])]
        return []

    def _endpoint_route_health(endpoint_id: int, hop_node_keys: list[str]) -> dict:
        if hasattr(chain_service, "endpoint_route_health"):
            with contextlib.suppress(Exception):
                return dict(chain_service.endpoint_route_health(endpoint_id, hop_node_keys))
        return {
            "failed": False,
            "failure_expires_at": "",
            "known_healthy": False,
            "healthy_until": "",
        }

    def _build_hop_pool_status(endpoint_id: int, endpoint: dict | None, active_hop_keys: list[str]) -> list[dict]:
        hop_status: list[dict] = []
        for index, hop in enumerate(list((endpoint or {}).get("hops") or [])):
            pool_id = int(hop.get("pool_id") or 0)
            pool = storage.get_proxy_pool(pool_id) if pool_id > 0 else None
            candidates = storage.list_proxy_pool_candidates(pool_id, limit=500) if pool is not None else []
            active_key = active_hop_keys[index] if index < len(active_hop_keys) else ""
            active_proxy = storage.get_proxy_by_key(active_key) if active_key else None
            node_rows = sorted(
                [_proxy_status_summary(proxy, active_key=active_key) for proxy in candidates],
                key=lambda item: (not item.get("active"), not item.get("healthy"), item.get("latency_ms") is None, item.get("latency_ms") or 10**9),
            )
            if active_proxy is not None and not any(item.get("key") == active_key for item in node_rows):
                node_rows.insert(0, _proxy_status_summary(active_proxy, active_key=active_key))
            healthy_count = sum(1 for item in node_rows if bool(item.get("healthy")))
            hop_status.append({
                "hop_index": index,
                "label": f"第{index + 1}跳",
                "pool": pool,
                "pool_id": pool_id,
                "total_nodes": len(node_rows),
                "healthy_nodes": healthy_count,
                "available": healthy_count > 0,
                "active_node_key": active_key,
                "active_node": _proxy_status_summary(active_proxy, active_key=active_key) if active_proxy is not None else None,
                "nodes": node_rows,
            })
        return hop_status

    def _build_hop_transition_status(endpoint_id: int, hop_pools: list[dict]) -> list[dict]:
        transitions: list[dict] = []
        for index in range(max(0, len(hop_pools) - 1)):
            left = hop_pools[index]
            right = hop_pools[index + 1]
            left_nodes = [item for item in list(left.get("nodes") or []) if item.get("healthy")]
            right_nodes = [item for item in list(right.get("nodes") or []) if item.get("healthy")]
            active_pair = [str(left.get("active_node_key") or ""), str(right.get("active_node_key") or "")]
            pairs: list[dict] = []
            if active_pair[0] and active_pair[1]:
                health = _endpoint_route_health(endpoint_id, active_pair)
                pairs.append({
                    "source": left.get("active_node"),
                    "target": right.get("active_node"),
                    "hop_node_keys": active_pair,
                    "active": True,
                    "healthy": bool(not health["failed"] and (left.get("active_node") or {}).get("healthy") and (right.get("active_node") or {}).get("healthy")),
                    **health,
                })
            for source in left_nodes:
                for target in right_nodes:
                    keys = [str(source.get("key") or ""), str(target.get("key") or "")]
                    if not keys[0] or not keys[1] or keys == active_pair:
                        continue
                    health = _endpoint_route_health(endpoint_id, keys)
                    pairs.append({
                        "source": source,
                        "target": target,
                        "hop_node_keys": keys,
                        "active": False,
                        "healthy": not health["failed"],
                        **health,
                    })
                    if len(pairs) >= 80:
                        break
                if len(pairs) >= 80:
                    break
            healthy_pairs = sum(1 for item in pairs if bool(item.get("healthy")))
            transitions.append({
                "from_hop_index": index,
                "to_hop_index": index + 1,
                "label": f"第{index + 1}跳 -> 第{index + 2}跳",
                "total_pairs": max(0, len(left_nodes) * len(right_nodes)),
                "shown_pairs": len(pairs),
                "healthy_pairs": healthy_pairs,
                "available": bool(healthy_pairs > 0),
                "pairs": pairs,
            })
        return transitions

    def _build_http_gateway_status(config, endpoint_id: int = 0) -> dict:
        endpoint = storage.get_http_proxy_endpoint(int(endpoint_id or 0)) if int(endpoint_id or 0) > 0 else None
        resolved_endpoint_id = int((endpoint or {}).get("id") or 0)
        hops = list((endpoint or {}).get("hops") or [])
        entry_pool_id = int(hops[0].get("pool_id") or 0) if hops else int(config.default_pool_id or 0)
        leases = chain_service.get_leases(pool_id=entry_pool_id or None, endpoint_id=resolved_endpoint_id or None) if resolved_endpoint_id else (
            pool_service.list_pool_chain_leases(config.default_pool_id) if config.default_pool_id else []
        )
        instances = chain_instance_manager.list_instances(
            pool_id=entry_pool_id or None,
            endpoint_id=resolved_endpoint_id or None,
        ) if resolved_endpoint_id else chain_instance_manager.list_instances(pool_id=config.default_pool_id or None)
        active_hop_keys = _latest_active_hop_keys(resolved_endpoint_id, leases, instances)
        hop_pools = _build_hop_pool_status(resolved_endpoint_id, endpoint, active_hop_keys) if endpoint is not None else []
        transitions = _build_hop_transition_status(resolved_endpoint_id, hop_pools) if endpoint is not None else []
        runtime = gateway_runtime.status()
        endpoint_runtime = None
        for item in list(runtime.get("items") or []):
            if int(item.get("endpoint_id") or 0) == resolved_endpoint_id:
                endpoint_runtime = item
                break
        hop_pools_available = bool(hop_pools) and all(item.get("available") for item in hop_pools)
        transitions_available = all(item.get("available") for item in transitions)
        return {
            "config": asdict(config),
            "endpoint": endpoint,
            "item": endpoint,
            "endpoint_runtime": endpoint_runtime,
            "runtime": runtime,
            "leases": leases,
            "instances": instances,
            "health_monitor": _gateway_health_snapshot(),
            "active_hop_node_keys": active_hop_keys,
            "hop_pools": hop_pools,
            "transitions": transitions,
            "summary": {
                "endpoint_id": resolved_endpoint_id,
                "hop_count": len(hop_pools),
                "available": bool(endpoint_runtime and endpoint_runtime.get("running") and hop_pools_available and transitions_available),
                "degraded": any(item.get("available") and item.get("healthy_nodes", 0) < item.get("total_nodes", 0) for item in hop_pools) or any(not item.get("available") for item in transitions),
                "healthy_hop_pools": sum(1 for item in hop_pools if item.get("available")),
                "total_hop_pools": len(hop_pools),
                "healthy_transitions": sum(1 for item in transitions if item.get("available")),
                "total_transitions": len(transitions),
            },
        }

    @contextlib.asynccontextmanager
    async def lifespan(application: FastAPI):
        # Startup
        application.state.backend_health_task = asyncio.create_task(_backend_health_loop())
        application.state.auto_task_runner = asyncio.create_task(_auto_task_loop())
        application.state.gateway_health_task = asyncio.create_task(_gateway_health_loop())
        if gateway_config_service.get_config().enabled:
            try:
                await gateway_runtime.start()
            except Exception:
                pass
        yield
        # Shutdown
        for attr in ("backend_health_task", "auto_task_runner", "gateway_health_task"):
            task = getattr(application.state, attr, None)
            if task is None:
                continue
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            setattr(application.state, attr, None)

    app = FastAPI(title="Proxy Pool", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {type(exc).__name__}"},
        )

    app.state.settings = cfg
    app.state.storage = storage
    app.state.collector = collector
    app.state.tester = tester
    app.state.geoip = geoip
    app.state.scheduler = scheduler
    app.state.task_manager = task_manager
    app.state.singbox_manager = singbox_manager
    app.state.pool_service = pool_service
    app.state.chain_service = chain_service
    app.state.chain_instance_manager = chain_instance_manager
    app.state.unified_gateway = unified_gateway
    app.state.gateway_config_service = gateway_config_service
    app.state.forward_gateway = forward_gateway
    app.state.gateway_runtime = gateway_runtime
    app.state.backend_health_task = None
    app.state.auto_task_config = _default_auto_task_config()
    app.state.auto_task_runner = None
    app.state.auto_task_last_run = {}
    app.state.gateway_health_task = None
    app.state.gateway_health_lock = asyncio.Lock()
    app.state.gateway_health_snapshot = {
        "enabled": False,
        "interval_sec": 30,
        "running": False,
        "last_started_at": "",
        "last_finished_at": "",
        "last_error": "",
        "endpoints": {},
    }

    def _gateway_health_snapshot() -> dict:
        snapshot = getattr(app.state, "gateway_health_snapshot", {}) or {}
        return {
            "enabled": bool(snapshot.get("enabled")),
            "interval_sec": int(snapshot.get("interval_sec") or 30),
            "running": bool(snapshot.get("running")),
            "last_started_at": str(snapshot.get("last_started_at") or ""),
            "last_finished_at": str(snapshot.get("last_finished_at") or ""),
            "last_error": str(snapshot.get("last_error") or ""),
            "endpoints": dict(snapshot.get("endpoints") or {}),
        }

    async def _probe_gateway_node(node: dict, front_proxy: dict | None = None) -> dict:
        key = str(node.get("normalized_key") or "")
        started = time.perf_counter()
        try:
            if front_proxy is not None:
                result = await prober.probe_with_front_proxy_async(node, front_proxy)
            else:
                result = await prober.probe_async(node)
        except Exception as exc:
            result = SimpleNamespace(
                normalized_key=key,
                available=False,
                latency_ms=None,
                openai_unlocked=None,
                openai_status="",
                error=str(exc),
            )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        storage.update_test_result(
            normalized_key=str(result.normalized_key or key),
            available=bool(result.available),
            latency_ms=result.latency_ms,
            openai_unlocked=result.openai_unlocked,
            openai_status=result.openai_status,
            error=str(result.error or ""),
        )
        return {
            "node_key": str(result.normalized_key or key),
            "ok": bool(result.available),
            "latency_ms": result.latency_ms,
            "elapsed_ms": elapsed_ms,
            "error": str(result.error or ""),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _run_gateway_health_once() -> dict:
        async with app.state.gateway_health_lock:
            config = gateway_config_service.get_config()
            started_at = datetime.now(timezone.utc).isoformat()
            snapshot = _gateway_health_snapshot()
            snapshot.update({
                "enabled": bool(config.health_check_enabled),
                "interval_sec": int(config.health_check_interval_sec),
                "running": True,
                "last_started_at": started_at,
                "last_error": "",
            })
            app.state.gateway_health_snapshot = snapshot
            endpoints_result: dict[str, dict] = {}
            try:
                for endpoint in storage.list_http_proxy_endpoints():
                    if endpoint.get("enabled") is not True:
                        continue
                    endpoint_id = int(endpoint.get("id") or 0)
                    if endpoint_id <= 0:
                        continue
                    hops = list(endpoint.get("hops") or [])
                    hop_results: list[dict] = []
                    active_keys = _latest_active_hop_keys(
                        endpoint_id,
                        chain_service.get_leases(
                            pool_id=int(hops[0].get("pool_id") or 0) if hops else None,
                            endpoint_id=endpoint_id,
                        ),
                        chain_instance_manager.list_instances(endpoint_id=endpoint_id),
                    )
                    active_failed = False
                    first_active_proxy = storage.get_proxy_by_key(active_keys[0]) if active_keys else None
                    for index, hop in enumerate(hops):
                        pool_id = int(hop.get("pool_id") or 0)
                        candidates = [
                            item for item in storage.list_proxy_pool_candidates(pool_id, limit=500)
                            if bool(item.get("available"))
                        ] if pool_id > 0 else []
                        active_key = active_keys[index] if index < len(active_keys) else ""
                        if active_key and not any(str(item.get("normalized_key") or "") == active_key for item in candidates):
                            active_proxy = storage.get_proxy_by_key(active_key)
                            if active_proxy is not None:
                                candidates.insert(0, active_proxy)
                        nodes: list[dict] = []
                        for node in candidates:
                            node_key = str(node.get("normalized_key") or "")
                            front_proxy = None
                            if index > 0 and first_active_proxy is not None and node_key != str(first_active_proxy.get("normalized_key") or ""):
                                front_proxy = first_active_proxy
                            result = await _probe_gateway_node(node, front_proxy=front_proxy)
                            result["active"] = bool(active_key and node_key == active_key)
                            result["via_node_key"] = str((front_proxy or {}).get("normalized_key") or "")
                            if result["active"] and not result["ok"]:
                                active_failed = True
                            nodes.append(result)
                        hop_results.append({
                            "hop_index": index,
                            "pool_id": pool_id,
                            "checked_nodes": len(nodes),
                            "healthy_nodes": sum(1 for item in nodes if item.get("ok")),
                            "active_node_key": active_key,
                            "nodes": nodes,
                        })
                    if active_failed and active_keys and hops:
                        chain_service.report_endpoint_route_failure(
                            endpoint_id=endpoint_id,
                            pool_id=int(hops[0].get("pool_id") or 0),
                            hop_node_keys=active_keys,
                            cooldown_sec=max(30, int(config.health_check_interval_sec) * 2),
                        )
                    endpoints_result[str(endpoint_id)] = {
                        "endpoint_id": endpoint_id,
                        "name": str(endpoint.get("name") or ""),
                        "active_hop_node_keys": active_keys,
                        "active_failed": active_failed,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "hops": hop_results,
                    }
                snapshot = _gateway_health_snapshot()
                snapshot.update({
                    "enabled": bool(config.health_check_enabled),
                    "interval_sec": int(config.health_check_interval_sec),
                    "running": False,
                    "last_finished_at": datetime.now(timezone.utc).isoformat(),
                    "last_error": "",
                    "endpoints": endpoints_result,
                })
                app.state.gateway_health_snapshot = snapshot
                return snapshot
            except Exception as exc:
                snapshot = _gateway_health_snapshot()
                snapshot.update({
                    "running": False,
                    "last_finished_at": datetime.now(timezone.utc).isoformat(),
                    "last_error": str(exc),
                    "endpoints": endpoints_result or snapshot.get("endpoints") or {},
                })
                app.state.gateway_health_snapshot = snapshot
                raise

    async def _gateway_health_loop() -> None:
        while True:
            config = gateway_config_service.get_config()
            interval = max(5, int(config.health_check_interval_sec or 30))
            if bool(config.enabled) and bool(config.health_check_enabled):
                with contextlib.suppress(Exception):
                    await _run_gateway_health_once()
            await asyncio.sleep(interval)

    async def _backend_health_loop() -> None:
        interval = max(5, int(cfg.backend_health_check_sec))
        while True:
            await asyncio.sleep(interval)
            try:
                singbox_manager.health_check(timeout_sec=1.5, auto_restart=True)
            except Exception:
                # health loop must not crash the API process
                continue

    def _start_speed_test_task(body: SpeedTestRequest, kind: str = "speed_test") -> str:
        target_url = str(body.url or "").strip()
        if not (target_url.startswith("http://") or target_url.startswith("https://")):
            raise ValueError("speed test url must start with http:// or https://")

        def _runner(update, should_stop):
            only_direct = bool(body.only_available) if body.only_direct is None else bool(body.only_direct)
            candidates = storage.get_candidates_for_test(
                limit=int(body.limit or 0),
                only_available=bool(body.only_available),
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
                    prober.speed_test_async(
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

        return task_manager.start_task(kind, _runner)

    def _start_subscription_refresh_task(timeout_sec: float = 12.0, kind: str = "subscriptions_refresh") -> str:
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

        return task_manager.start_task(kind, runner)

    def _start_tester_task(body: RunTestRequest, kind: str = "tester_run") -> str:
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

        return task_manager.start_task(kind, _runner)

    async def _auto_task_loop() -> None:
        while True:
            await asyncio.sleep(5)
            config = dict(app.state.auto_task_config or {})
            if not bool(config.get("enabled")):
                continue
            now = time.monotonic()
            last_run: dict = app.state.auto_task_last_run

            def _due(name: str, minutes: int) -> bool:
                interval = max(60.0, float(max(1, int(minutes or 1)) * 60))
                return now - float(last_run.get(name) or 0.0) >= interval

            try:
                if bool(config.get("subscription_refresh_enabled")) and _due("subscriptions_refresh", int(config.get("subscription_refresh_minutes") or 60)):
                    last_run["subscriptions_refresh"] = now
                    _start_subscription_refresh_task(kind="auto_subscriptions_refresh")
                if bool(config.get("tester_enabled")) and _due("tester_run", int(config.get("tester_minutes") or 60)):
                    last_run["tester_run"] = now
                    _start_tester_task(
                        RunTestRequest(
                            limit=int(config.get("tester_limit") or 0),
                            concurrency=int(config.get("tester_concurrency") or 50),
                        ),
                        kind="auto_tester_run",
                    )
                if bool(config.get("speed_test_enabled")) and _due("speed_test", int(config.get("speed_test_minutes") or 120)):
                    last_run["speed_test"] = now
                    _start_speed_test_task(
                        SpeedTestRequest(
                            url=str(config.get("speed_test_url") or "https://speed.cloudflare.com/__down?bytes=10000000"),
                            limit=int(config.get("speed_test_limit") or 0),
                            timeout_sec=float(config.get("speed_test_timeout_sec") or 30.0),
                            only_available=True,
                        ),
                        kind="auto_speed_test",
                    )
            except Exception:
                continue

    @app.middleware("http")
    async def api_key_guard(request: Request, call_next):
        header_key = request.headers.get("X-API-Key", "")
        if not is_request_authorized(request.method, request.url.path, header_key, cfg.api_key):
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)

    # 注册所有 Router
    register_routers(app)

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


def _published_subscription_clash_yaml(proxies: list[dict]) -> str:
    import yaml

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


def _subscription_status_from_report(report) -> tuple[str, str]:
    if report.total_parsed > 0 or report.total_inserted > 0 or report.total_updated > 0:
        return "success", ""
    if report.total_invalid > 0:
        return "failed", "empty or invalid subscription content"
    return "success", ""
