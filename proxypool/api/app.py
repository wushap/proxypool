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

    app = FastAPI(title="Proxy Pool", version="0.1.0")
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

    @app.on_event("startup")
    async def on_startup() -> None:
        app.state.backend_health_task = asyncio.create_task(_backend_health_loop())
        app.state.auto_task_runner = asyncio.create_task(_auto_task_loop())
        app.state.gateway_health_task = asyncio.create_task(_gateway_health_loop())
        if gateway_config_service.get_config().enabled:
            try:
                await gateway_runtime.start()
            except Exception:
                pass

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        for attr in ("backend_health_task", "auto_task_runner", "gateway_health_task"):
            task = getattr(app.state, attr, None)
            if task is None:
                continue
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            setattr(app.state, attr, None)

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

    @app.get("/api/tasks/auto-config")
    async def get_auto_task_config() -> dict:
        return {
            "item": dict(app.state.auto_task_config or {}),
            "last_run": dict(app.state.auto_task_last_run or {}),
            "running": app.state.auto_task_runner is not None and not app.state.auto_task_runner.done(),
        }

    @app.put("/api/tasks/auto-config")
    async def update_auto_task_config(body: AutoTaskConfigRequest) -> dict:
        payload = body.model_dump()
        url = str(payload.get("speed_test_url") or "").strip()
        if payload.get("speed_test_enabled") and not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(status_code=400, detail="speed_test_url must start with http:// or https://")
        app.state.auto_task_config = payload
        return {
            "item": dict(app.state.auto_task_config),
            "last_run": dict(app.state.auto_task_last_run or {}),
            "running": app.state.auto_task_runner is not None and not app.state.auto_task_runner.done(),
        }

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

    @app.get("/api/http-proxy-endpoints")
    async def list_http_proxy_endpoints() -> dict:
        return {"items": storage.list_http_proxy_endpoints()}

    @app.post("/api/http-proxy-endpoints")
    async def create_http_proxy_endpoint(body: HttpProxyEndpointCreateRequest) -> dict:
        try:
            item = storage.create_http_proxy_endpoint(
                name=body.name,
                listen_host=body.listen_host,
                listen_port=body.listen_port,
                inbound_type=body.inbound_type,
                enabled=body.enabled,
                sticky_ttl_sec=body.sticky_ttl_sec,
                session_missing_action=body.session_missing_action,
                session_header_names=body.session_header_names,
                session_query_param_names=body.session_query_param_names,
                connect_session_header_names=body.connect_session_header_names,
            )
            if body.hop_pool_ids:
                storage.replace_http_proxy_endpoint_hops(int(item["id"]), list(body.hop_pool_ids))
                item = storage.get_http_proxy_endpoint(int(item["id"])) or item
            if gateway_config_service.get_config().enabled:
                await gateway_runtime.sync()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item}

    @app.get("/api/http-proxy-endpoints/{endpoint_id}")
    async def get_http_proxy_endpoint(endpoint_id: int) -> dict:
        item = storage.get_http_proxy_endpoint(endpoint_id)
        if item is None:
            raise HTTPException(status_code=404, detail="http proxy endpoint not found")
        return {"item": item}

    @app.put("/api/http-proxy-endpoints/{endpoint_id}")
    async def update_http_proxy_endpoint(endpoint_id: int, body: HttpProxyEndpointUpdateRequest) -> dict:
        payload = body.model_dump(exclude_none=True)
        hop_pool_ids = payload.pop("hop_pool_ids", None)
        try:
            item = storage.update_http_proxy_endpoint(endpoint_id, **payload)
            if hop_pool_ids is not None:
                storage.replace_http_proxy_endpoint_hops(endpoint_id, list(hop_pool_ids))
                item = storage.get_http_proxy_endpoint(endpoint_id) or item
            if gateway_config_service.get_config().enabled:
                await gateway_runtime.sync()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item}

    @app.delete("/api/http-proxy-endpoints/{endpoint_id}")
    async def delete_http_proxy_endpoint(endpoint_id: int) -> dict:
        deleted = storage.delete_http_proxy_endpoint(endpoint_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="http proxy endpoint not found")
        if gateway_config_service.get_config().enabled:
            await gateway_runtime.sync()
        return {"deleted": True}

    @app.get("/api/gateway/http-config")
    async def get_http_gateway_config() -> dict:
        return {"item": asdict(gateway_config_service.get_config())}

    @app.put("/api/gateway/http-config")
    async def update_http_gateway_config(body: HttpGatewayConfigRequest) -> dict:
        item = gateway_config_service.update_config(**body.model_dump())
        app.state.forward_gateway.config = item
        endpoint = storage.get_http_proxy_endpoint(int(item.endpoint_id or 0))
        app.state.chain_service.sticky_router.sticky_ttl_sec = int(
            endpoint.get("sticky_ttl_sec") if endpoint is not None else item.sticky_ttl_sec
        )
        if item.enabled:
            try:
                await gateway_runtime.start()
            except Exception:
                pass
        else:
            await gateway_runtime.stop()
        return {"item": asdict(item)}

    @app.get("/api/gateway/http-status")
    async def get_http_gateway_status(endpoint_id: int = Query(default=0, ge=0)) -> dict:
        config = gateway_config_service.get_config()
        resolved_endpoint_id = int(endpoint_id or config.endpoint_id or 0)
        return _build_http_gateway_status(config, resolved_endpoint_id)

    @app.post("/api/gateway/http-health-check")
    async def run_http_gateway_health_check() -> dict:
        snapshot = await _run_gateway_health_once()
        return {"item": snapshot}

    @app.post("/api/gateway/http-test")
    async def run_http_gateway_test(body: HttpGatewayTestRequest) -> dict:
        target = str(body.target_url or "").strip()
        if not target:
            raise HTTPException(status_code=400, detail="target_url is required")
        if int(body.endpoint_id or 0) > 0:
            current = gateway_config_service.get_config()
            if int(current.endpoint_id or 0) != int(body.endpoint_id):
                updated = gateway_config_service.update_config(endpoint_id=int(body.endpoint_id))
                app.state.forward_gateway.config = updated
        headers = {}
        if body.session_id:
            headers["X-ProxyPool-Session"] = body.session_id
        else:
            configured_endpoint_id = int(body.endpoint_id or app.state.forward_gateway.config.endpoint_id or 0)
            endpoint_for_policy = storage.get_http_proxy_endpoint(configured_endpoint_id) if configured_endpoint_id > 0 else None
            missing_action = str(
                (endpoint_for_policy or {}).get("session_missing_action")
                or app.state.forward_gateway.config.session_missing_action
                or "RANDOM"
            ).upper()
            if missing_action != "REJECT":
                headers["X-ProxyPool-Session"] = f"gateway-test:{uuid.uuid4().hex}"
        try:
            route = app.state.forward_gateway.resolve_route_for_http(target, headers=headers)
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
        endpoint = route.get("endpoint") or {}
        endpoint_id = int(endpoint.get("id") or 0)
        proxy_host = str(endpoint.get("listen_host") or app.state.forward_gateway.config.listen_host or "127.0.0.1")
        proxy_port = int(endpoint.get("listen_port") or app.state.forward_gateway.config.listen_port or 0)
        if proxy_port <= 0:
            return {
                "ok": False,
                "detail": "gateway listen port is not configured",
                "session_id": route["session_id"],
                "endpoint_id": endpoint_id,
                "instance_id": route["instance"]["instance_id"],
                "target_host": route["target"].netloc,
                "hop_node_keys": list(route["route"].get("hop_node_keys") or []),
                "route_signature": str(route["route"].get("route_signature") or ""),
            }
        proxy_url = f"http://{proxy_host}:{proxy_port}"
        request_result = await _request_via_forward_proxy(
            target,
            proxy_url=proxy_url,
            proxy_headers=headers,
        )
        request_ok = bool(request_result.get("request_ok"))
        status_code = int(request_result.get("status_code") or 0)
        if not request_ok:
            error_detail = str(request_result.get("error") or request_result.get("error_type") or "request failed")
            with contextlib.suppress(Exception):
                app.state.forward_gateway.report_route_failure(route, error_detail)
        else:
            with contextlib.suppress(Exception):
                app.state.forward_gateway.report_route_success(route)
        return {
            "ok": bool(request_ok and (status_code == 0 or status_code < 500)),
            "detail": "request succeeded" if request_ok else str(request_result.get("error") or "request failed"),
            "session_id": route["session_id"],
            "endpoint_id": endpoint_id,
            "proxy_url": proxy_url,
            "instance_id": route["instance"]["instance_id"],
            "target_host": route["target"].netloc,
            "hop_node_keys": list(route["route"].get("hop_node_keys") or []),
            "route_signature": str(route["route"].get("route_signature") or ""),
            "request": request_result,
        }

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
        speed_min_mbps: float | None = Query(default=None, ge=0),
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
            speed_min_mbps=speed_min_mbps,
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
                format=body.format,
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
                format=body.format,
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
        output_format = str(item.get("format") or "raw").strip().lower()
        if output_format == "clash":
            text = _published_subscription_clash_yaml(storage.get_published_subscription_proxies(subscription_id, limit=limit))
        else:
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
        task_id = _start_subscription_refresh_task(timeout_sec=timeout_sec)
        task = task_manager.get_task(task_id)
        return {"task_id": task_id, "task": task}

    @app.post("/api/proxies/delete-unavailable")
    async def delete_unavailable_proxies() -> dict:
        deleted = storage.delete_unavailable()
        return {"deleted": deleted}

    @app.post("/api/proxies/delete-selected")
    async def delete_selected_proxies(body: ProxyBulkDeleteRequest) -> dict:
        keys = [str(key or "").strip() for key in body.normalized_keys if str(key or "").strip()]
        if not keys:
            raise HTTPException(status_code=400, detail="normalized_keys is empty")
        deleted = storage.delete_proxies_by_keys(keys)
        return {"deleted": deleted, "requested": len(set(keys))}

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
        task_id = _start_tester_task(body)
        return {"task_id": task_id}

    @app.post("/api/tasks/speed-test/start")
    async def start_speed_test_task(body: SpeedTestRequest) -> dict:
        try:
            task_id = _start_speed_test_task(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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

    @app.put("/api/pools/{pool_id}/chain/session-rules/{url_prefix:path}")
    async def upsert_pool_chain_session_rule(pool_id: int, url_prefix: str, body: PoolSessionRuleUpsertRequest) -> dict:
        try:
            item = pool_service.upsert_pool_session_rule(pool_id, url_prefix=url_prefix, headers=body.headers)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"item": item}

    @app.get("/api/pools/{pool_id}/chain/session-rules")
    async def list_pool_chain_session_rules(pool_id: int) -> dict:
        try:
            items = pool_service.list_pool_session_rules(pool_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"items": items}

    @app.delete("/api/pools/{pool_id}/chain/session-rules/{url_prefix:path}")
    async def delete_pool_chain_session_rule(pool_id: int, url_prefix: str) -> dict:
        try:
            deleted = pool_service.delete_pool_session_rule(pool_id, url_prefix=url_prefix)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="session rule not found")
        return {"deleted": True}

    @app.get("/api/pools/{pool_id}/chain/route-test")
    async def pool_chain_route_test(
        pool_id: int,
        session_id: str = "",
        target_domain: str = "",
    ) -> dict:
        item = pool_service.get_pool(pool_id)
        if item is None:
            raise HTTPException(status_code=404, detail="pool not found")
        chain_service.initialize()
        result = chain_service.route_request(session_id=session_id, pool_id=pool_id, target_domain=target_domain)
        if result is None:
            raise HTTPException(status_code=503, detail="No available nodes for routing")
        return result

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

    @app.post("/api/pools/{pool_id}/chain/instances/{instance_id}/start")
    async def start_pool_chain_instance(pool_id: int, instance_id: str) -> dict:
        item = pool_service.get_pool(pool_id)
        if item is None:
            raise HTTPException(status_code=404, detail="pool not found")
        instance = chain_instance_manager.get_instance(instance_id)
        if instance is None or int(instance.get("pool_id") or 0) != pool_id:
            raise HTTPException(status_code=404, detail="chain instance not found")
        try:
            started = chain_instance_manager.start_instance(instance_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": started, "items": chain_instance_manager.list_instances(pool_id=pool_id)}

    @app.post("/api/pools/{pool_id}/chain/instances/{instance_id}/stop")
    async def stop_pool_chain_instance(pool_id: int, instance_id: str) -> dict:
        item = pool_service.get_pool(pool_id)
        if item is None:
            raise HTTPException(status_code=404, detail="pool not found")
        instance = chain_instance_manager.get_instance(instance_id)
        if instance is None or int(instance.get("pool_id") or 0) != pool_id:
            raise HTTPException(status_code=404, detail="chain instance not found")
        stopped = chain_instance_manager.stop_instance(instance_id)
        return {"item": stopped, "items": chain_instance_manager.list_instances(pool_id=pool_id)}

    @app.post("/api/pools/{pool_id}/chain/instances/{instance_id}/rebuild")
    async def rebuild_pool_chain_instance(
        pool_id: int,
        instance_id: str,
        front_node_key: str | None = None,
        exit_node_key: str | None = None,
    ) -> dict:
        item = pool_service.get_pool(pool_id)
        if item is None:
            raise HTTPException(status_code=404, detail="pool not found")
        instance = chain_instance_manager.get_instance(instance_id)
        if instance is None or int(instance.get("pool_id") or 0) != pool_id:
            raise HTTPException(status_code=404, detail="chain instance not found")
        try:
            rebuilt = chain_instance_manager.rebuild_instance(
                instance_id,
                front_node_key=front_node_key,
                exit_node_key=exit_node_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": rebuilt, "items": chain_instance_manager.list_instances(pool_id=pool_id)}

    @app.get("/api/pools/{pool_id}/chain/leases")
    async def list_pool_chain_leases(pool_id: int) -> dict:
        try:
            items = pool_service.list_pool_chain_leases(pool_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"items": items}

    @app.delete("/api/pools/{pool_id}/chain/leases/{session_id}")
    async def delete_pool_chain_lease(pool_id: int, session_id: str) -> dict:
        try:
            deleted = pool_service.delete_pool_chain_lease(pool_id, session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="sticky lease not found")
        return {"deleted": True}

    @app.post("/api/pools/{pool_id}/chain/leases/inherit")
    async def inherit_pool_chain_lease(pool_id: int, body: StickyLeaseInheritRequest) -> dict:
        try:
            item = pool_service.inherit_pool_chain_lease(
                pool_id,
                from_session_id=body.from_session_id,
                to_session_id=body.to_session_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"item": item}

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

    @app.get("/api/http-proxy-endpoints/{endpoint_id}/route-test")
    async def http_proxy_endpoint_route_test(
        endpoint_id: int,
        session_id: str = "",
        target_domain: str = "",
    ) -> dict:
        endpoint = storage.get_http_proxy_endpoint(endpoint_id)
        if endpoint is None:
            raise HTTPException(status_code=404, detail="http proxy endpoint not found")
        hops = list(endpoint.get("hops") or [])
        if not hops:
            raise HTTPException(status_code=400, detail="endpoint hops are empty")
        entry_pool_id = int(hops[0].get("pool_id") or 0)
        chain_service.initialize()
        result = chain_service.route_request(
            session_id=session_id,
            pool_id=entry_pool_id,
            endpoint_id=endpoint_id,
            target_domain=target_domain,
            live_instance_ids=chain_instance_manager.list_running_instance_ids(
                pool_id=entry_pool_id,
                endpoint_id=endpoint_id,
            ),
        )
        if result is None:
            raise HTTPException(status_code=503, detail="No available nodes for routing")
        return result

    @app.get("/api/http-proxy-endpoints/{endpoint_id}/status")
    async def http_proxy_endpoint_status(endpoint_id: int) -> dict:
        endpoint = storage.get_http_proxy_endpoint(endpoint_id)
        if endpoint is None:
            raise HTTPException(status_code=404, detail="http proxy endpoint not found")
        return _build_http_gateway_status(gateway_config_service.get_config(), endpoint_id)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        dist_index = cfg.project_root / "proxypool" / "webui" / "dist" / "index.html"
        if not dist_index.exists():
            raise HTTPException(status_code=404, detail="WebUI build not found. Run `npm run build` in proxypool/webui.")
        return dist_index.read_text(encoding="utf-8")

    # Serve built Vite assets when present; fall back to legacy static assets for tests/dev.
    _webui_dir = cfg.project_root / "proxypool" / "webui"
    _webui_dist = _webui_dir / "dist"
    if (_webui_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(_webui_dist / "assets")), name="webui-assets")
    if (_webui_dir / "css").is_dir():
        app.mount("/css", StaticFiles(directory=str(_webui_dir / "css")), name="webui-css")
    if (_webui_dir / "js").is_dir():
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
        endpoint_id: int = 0,
        target_domain: str = "",
    ) -> dict:
        """Route a request through the proxy chain."""
        chain_service.initialize()
        result = chain_service.route_request(session_id, pool_id, endpoint_id, target_domain)
        if result is None:
            raise HTTPException(status_code=503, detail="No available nodes for routing")
        return result

    @app.get("/api/chain/leases")
    async def chain_leases(
        pool_id: int | None = None,
        endpoint_id: int | None = None,
    ) -> dict:
        """Get sticky leases."""
        chain_service.initialize()
        return {"leases": chain_service.get_leases(pool_id, endpoint_id)}

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

    @app.api_route(
        "/proxy/{pool_name}/{scheme}/{target_host}/{target_path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    )
    async def unified_http_gateway_route(
        pool_name: str,
        scheme: str,
        target_host: str,
        target_path: str,
        request: Request,
    ) -> Response:
        pool = pool_service.get_pool_by_name(pool_name)
        if pool is None:
            raise HTTPException(status_code=404, detail="pool not found")
        expected_prefix = str(pool.get("gateway_path_prefix") or "").strip()
        if expected_prefix != f"/proxy/{pool_name}":
            raise HTTPException(status_code=404, detail="gateway path not enabled for pool")
        try:
            response = await unified_gateway.handle(
                method=request.method,
                pool_name=pool_name,
                scheme=scheme,
                target_host=target_host,
                target_path="/" + str(target_path or "").lstrip("/"),
                headers=request.headers,
                query_params=request.query_params,
                body=await request.body(),
            )
        except GatewayError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        skip_headers = {"content-encoding", "transfer-encoding", "connection"}
        response_headers = {k: v for k, v in response.headers.items() if k.lower() not in skip_headers}
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type"),
        )

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
