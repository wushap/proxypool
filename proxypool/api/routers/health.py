"""
健康检查和统计路由

提供系统健康检查、进程监控、资源使用、版本信息、配置对比等端点。
"""

import csv
import io
import logging
import platform
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from proxypool.api.dependencies import SingboxManagerDep
from proxypool.api.schemas import (
    BottleneckResponse,
    CapacityMetricsResponse,
    ConfigDiffItem,
    ConfigDiffResponse,
    ErrorSummaryResponse,
    HealthSummaryResponse,
    LogEntry,
    MetricsExportResponse,
    ProcessInfo,
    RequestTraceResponse,
    SystemHealthResponse,
    SystemLogsResponse,
    SystemMetricsResponse,
    SystemProcessesResponse,
    SystemResourcesResponse,
    SystemVersionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["系统"])

# Track system start time
_system_start_time = time.time()


@router.get(
    "/health",
    summary="系统健康检查",
    description="返回系统基本健康状态，包括后端运行状态和代理节点数量",
    response_description="健康状态信息",
)
async def health(
    request: Request,
    singbox_manager: SingboxManagerDep = None,
) -> dict:
    """系统健康检查

    快速检查系统是否正常运行，返回后端服务状态和代理节点统计。
    """
    storage = request.app.state.storage
    backend_ok = singbox_manager.is_running() if hasattr(singbox_manager, "is_running") else False
    return {
        "status": "ok",
        "time": datetime.now(UTC).isoformat(),
        "backend_running": backend_ok,
        "proxy_count": storage.get_stats().get("total", 0),
    }


@router.get(
    "/stats",
    summary="系统统计数据",
    description="返回系统代理节点的统计信息，包括总数、可用数、不可用数等",
    response_description="统计数据",
)
async def stats(request: Request) -> dict:
    """系统统计数据

    获取代理节点的详细统计信息，用于仪表盘显示。
    """
    storage = request.app.state.storage
    return storage.get_stats()


@router.get(
    "/system/health",
    summary="系统详细健康状态",
    description="返回系统详细的健康状态，包括后端、网关、进程、池和代理的完整状态",
    response_description="详细健康状态",
    response_model=SystemHealthResponse,
)
async def system_health(
    request: Request,
) -> dict:
    """系统详细健康状态

    获取系统完整的健康状态信息，包括后端进程、网关运行状态、代理池数量和健康率。
    """
    storage = request.app.state.storage
    singbox_manager = request.app.state.singbox_manager
    gateway_runtime = request.app.state.gateway_runtime

    # Get backend status
    backend_status = singbox_manager.status()

    # Get gateway status
    gateway_status = gateway_runtime.status()

    # Count active processes
    active_processes = 0
    if backend_status.get("running"):
        active_processes += 1
    instances = singbox_manager.list_instances()
    active_processes += sum(1 for inst in instances if inst.get("status") == "running")

    # Get pool and proxy counts
    stats = storage.get_stats()
    pool_count = len(storage.list_proxy_pools())
    proxy_count = stats.get("total", 0)

    # Calculate healthy proxy rate
    healthy_count = stats.get("available", 0) or stats.get("healthy", 0)
    healthy_proxy_rate = (healthy_count / proxy_count) if proxy_count > 0 else 0.0

    # Calculate uptime
    uptime_seconds = int(time.time() - _system_start_time)

    return {
        "backend_status": backend_status,
        "gateway_status": gateway_status,
        "active_processes": active_processes,
        "pool_count": pool_count,
        "proxy_count": proxy_count,
        "healthy_proxy_rate": round(healthy_proxy_rate, 3),
        "uptime_seconds": uptime_seconds,
    }


@router.get(
    "/system/activity",
    summary="系统活动记录",
    description="返回最近的系统活动事件，支持限制返回数量",
    response_description="活动事件列表",
)
async def system_activity(
    request: Request,
    limit: int = 20,
) -> dict:
    """系统活动记录"""
    storage = request.app.state.storage

    # Get recent events from storage
    events = storage.list_backend_process_events(limit=limit)

    # Format events as activity items
    items = []
    for idx, event in enumerate(events):
        items.append(
            {
                "id": idx + 1,
                "timestamp": event.get("created_at") or "",
                "event_type": event.get("action", "unknown"),
                "description": _format_event_description(event),
                "details": {
                    "result": event.get("result"),
                    "pid": event.get("pid"),
                    "config_file": event.get("config_file"),
                    "detail": event.get("detail"),
                },
            }
        )

    return {
        "items": items,
        "total": len(items),
    }


def _format_event_description(event: dict) -> str:
    """Format event as human-readable description"""
    action = event.get("action", "unknown")
    result = event.get("result", "")
    detail = event.get("detail", "")

    if "start" in action.lower():
        return f"后端启动 {'成功' if result == 'success' else '失败'}"
    elif "stop" in action.lower():
        return f"后端停止 {'成功' if result == 'success' else '失败'}"
    elif "restart" in action.lower():
        return f"后端重启 {'成功' if result == 'success' else '失败'}"
    elif "test" in action.lower():
        return f"测试完成: {detail[:100] if detail else result}"
    elif "refresh" in action.lower():
        return f"订阅刷新: {result}"
    elif "config" in action.lower():
        return f"配置变更: {detail[:100] if detail else result}"
    else:
        return f"{action}: {result or detail}"


@router.get(
    "/system/processes",
    summary="系统进程列表",
    description="返回所有后端和实例进程的信息，包括PID、端口、状态、内存和CPU使用率",
    response_description="进程信息列表",
)
async def system_processes(
    request: Request,
) -> SystemProcessesResponse:
    """获取系统进程列表。

    返回所有后端和实例进程的信息，包括PID、端口、状态、内存和CPU使用率。
    """
    singbox_manager = request.app.state.singbox_manager

    processes = []

    # Collect backend processes
    backend_status = singbox_manager.status()
    if backend_status.get("running"):
        pid = backend_status.get("pid", 0)
        memory_mb = None
        cpu_percent = None
        uptime_seconds = None

        if pid:
            try:
                proc = psutil.Process(pid)
                memory_info = proc.memory_info()
                memory_mb = round(memory_info.rss / 1024 / 1024, 2)
                cpu_percent = proc.cpu_percent(interval=0.1)
                uptime_seconds = int(time.time() - proc.create_time())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        processes.append(
            ProcessInfo(
                id="backend",
                pid=pid,
                type="backend",
                status="running",
                port=None,
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                uptime_seconds=uptime_seconds,
                config_file=None,
                last_error=None,
            )
        )

    # Collect instance processes
    instances = singbox_manager.list_instances()
    for inst in instances:
        inst_id = inst.get("id", "unknown")
        inst_status = inst.get("status", "unknown")
        pid = inst.get("pid", 0)
        port = inst.get("port")
        config_file = inst.get("config_file")
        last_error = inst.get("last_error")
        memory_mb = None
        cpu_percent = None
        uptime_seconds = None

        if pid and inst_status == "running":
            try:
                proc = psutil.Process(pid)
                memory_info = proc.memory_info()
                memory_mb = round(memory_info.rss / 1024 / 1024, 2)
                cpu_percent = proc.cpu_percent(interval=0.1)
                uptime_seconds = int(time.time() - proc.create_time())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        processes.append(
            ProcessInfo(
                id=inst_id,
                pid=pid,
                type="instance",
                status=inst_status,
                port=port,
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                uptime_seconds=uptime_seconds,
                config_file=config_file,
                last_error=last_error,
            )
        )

    running = sum(1 for p in processes if p.status == "running")
    return SystemProcessesResponse(items=processes, total=len(processes), running=running)


@router.get(
    "/system/logs",
    summary="系统日志",
    description="返回系统事件日志，支持按级别过滤（INFO/WARN/ERROR/DEBUG）",
    response_description="日志条目列表",
)
async def system_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000, description="返回日志条数"),
    level: str | None = Query(default=None, description="日志级别过滤：INFO/WARN/ERROR/DEBUG"),
) -> SystemLogsResponse:
    """获取系统日志。

    返回系统事件日志，支持按级别过滤。
    """
    storage = request.app.state.storage

    # Get recent events from storage
    events = storage.list_backend_process_events(limit=limit * 2)

    # Convert events to log entries
    logs = []
    for event in events:
        action = event.get("action", "unknown")
        result = event.get("result", "")
        detail = event.get("detail", "")
        created_at = event.get("created_at") or datetime.now(UTC).isoformat()

        # Determine log level based on action and result
        if "error" in action.lower() or "failed" in result.lower():
            log_level = "ERROR"
        elif "warn" in action.lower():
            log_level = "WARN"
        elif "test" in action.lower() or "start" in action.lower() or "stop" in action.lower():
            log_level = "INFO"
        else:
            log_level = "DEBUG"

        # Apply level filter
        if level and log_level.upper() != level.upper():
            continue

        # Format message
        message = _format_event_description(event)
        if detail:
            message = f"{message}: {detail[:200]}"

        logs.append(
            LogEntry(
                timestamp=created_at,
                level=log_level,
                source="storage",
                message=message,
            )
        )

        if len(logs) >= limit:
            break

    return SystemLogsResponse(items=logs, total=len(logs), level_filter=level)


@router.post(
    "/system/processes/{process_id}/restart",
    summary="重启指定进程",
    description="重启后端主进程（process_id='backend'）或指定实例进程",
    response_description="重启结果",
)
async def restart_process(
    process_id: str,
    request: Request,
) -> dict:
    """重启指定进程。

    支持重启后端主进程（process_id='backend'）或指定实例。
    重启操作会记录到系统事件日志中。
    """
    storage = request.app.state.storage
    singbox_manager = request.app.state.singbox_manager

    if process_id == "backend":
        # Restart backend
        try:
            logger.info("Restarting backend process via API")
            singbox_manager.stop()
            time.sleep(1)
            singbox_manager.start()
            storage.record_backend_process_event(
                action="restart",
                result="success",
                detail="Backend restarted via API",
            )
            logger.info("Backend process restarted successfully")
            return {"status": "restarted", "process_id": process_id}
        except Exception as exc:
            storage.record_backend_process_event(
                action="restart",
                result="error",
                detail=str(exc),
            )
            logger.error(f"Failed to restart backend: {exc}")
            raise HTTPException(status_code=500, detail=f"重启后端失败: {exc}") from exc
    else:
        # Restart instance
        instances = singbox_manager.list_instances()
        instance_ids = [inst.get("id") for inst in instances]

        if process_id not in instance_ids:
            raise HTTPException(status_code=404, detail=f"进程 {process_id} 不存在")

        try:
            logger.info(f"Restarting instance {process_id} via API")
            singbox_manager.stop_instance(process_id)
            time.sleep(1)
            singbox_manager.start_instance(process_id)
            storage.record_backend_process_event(
                action="restart",
                result="success",
                detail=f"Instance {process_id} restarted via API",
            )
            logger.info(f"Instance {process_id} restarted successfully")
            return {"status": "restarted", "process_id": process_id}
        except Exception as exc:
            storage.record_backend_process_event(
                action="restart",
                result="error",
                detail=f"Failed to restart {process_id}: {exc}",
            )
            logger.error(f"Failed to restart instance {process_id}: {exc}")
            raise HTTPException(
                status_code=500, detail=f"重启实例 {process_id} 失败: {exc}"
            ) from exc


@router.get(
    "/system/resources",
    summary="系统资源使用情况",
    description="返回CPU、内存、磁盘使用率和系统运行时间",
    response_description="资源使用详情",
)
async def system_resources(
    request: Request,
) -> SystemResourcesResponse:
    """获取系统资源使用情况。

    返回CPU、内存、磁盘使用率和系统运行时间。
    """
    # CPU info
    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    cpu_info = {
        "percent": cpu_percent,
        "count": cpu_count,
        "frequency_mhz": cpu_freq.current if cpu_freq else None,
    }

    # Memory info
    memory = psutil.virtual_memory()
    memory_info = {
        "total_gb": round(memory.total / 1024 / 1024 / 1024, 2),
        "used_gb": round(memory.used / 1024 / 1024 / 1024, 2),
        "available_gb": round(memory.available / 1024 / 1024 / 1024, 2),
        "percent": memory.percent,
    }

    # Disk info
    disk_path = Path("/")
    try:
        disk_usage = shutil.disk_usage(disk_path)
        disk_info = {
            "total_gb": round(disk_usage.total / 1024 / 1024 / 1024, 2),
            "used_gb": round(disk_usage.used / 1024 / 1024 / 1024, 2),
            "free_gb": round(disk_usage.free / 1024 / 1024 / 1024, 2),
            "percent": round(disk_usage.used / disk_usage.total * 100, 1),
        }
    except OSError:
        disk_info = {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}

    # System uptime
    uptime_seconds = int(time.time() - psutil.boot_time())

    return SystemResourcesResponse(
        cpu=cpu_info,
        memory=memory_info,
        disk=disk_info,
        uptime_seconds=uptime_seconds,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get(
    "/system/version",
    summary="系统版本信息",
    description="返回系统版本号、Python版本、运行平台、架构和运行时间",
    response_description="版本信息详情",
)
async def system_version(
    request: Request,
) -> SystemVersionResponse:
    """获取系统版本信息。

    返回系统版本号、Python版本、运行平台、架构和运行时间。
    """
    from proxypool import __version__

    return SystemVersionResponse(
        version=__version__,
        python_version=platform.python_version(),
        platform=platform.system(),
        architecture=platform.machine(),
        build_time=None,
        uptime_seconds=int(time.time() - psutil.boot_time()),
        api_uptime_seconds=int(time.time() - _system_start_time),
    )


@router.get(
    "/system/config-diff",
    summary="配置差异对比",
    description="比较当前运行配置与存储配置，列出所有差异项",
    response_description="配置差异详情",
)
async def config_diff(
    request: Request,
) -> ConfigDiffResponse:
    """获取配置差异。

    比较当前运行配置与存储配置，列出所有差异项。
    """
    storage = request.app.state.storage
    gateway_config_service = request.app.state.gateway_config_service

    differences: list[ConfigDiffItem] = []

    # Get stored config
    stored_settings = {}
    settings_obj = request.app.state.settings
    if settings_obj:
        stored_settings = {
            "test_url": getattr(settings_obj, "test_url", None),
            "max_proxy_count": getattr(settings_obj, "max_proxy_count", None),
            "backend_health_check_sec": getattr(settings_obj, "backend_health_check_sec", None),
            "max_failures_threshold": getattr(settings_obj, "max_failures_threshold", None),
        }

    # Get running config (from gateway_config_service)
    running_config = {}
    try:
        gw_config = gateway_config_service.get_config()
        running_config = {
            "gateway_enabled": gw_config.enabled,
            "health_check_enabled": gw_config.health_check_enabled,
            "health_check_interval_sec": gw_config.health_check_interval_sec,
        }
    except Exception:
        pass

    # Get pool count from storage
    try:
        pools = storage.list_proxy_pools()
        stored_settings["pool_count"] = len(pools)
    except Exception:
        stored_settings["pool_count"] = 0

    # Compare configs
    all_keys = set(stored_settings.keys()) | set(running_config.keys())

    for key in sorted(all_keys):
        stored_val = stored_settings.get(key)
        running_val = running_config.get(key)

        stored_str = str(stored_val) if stored_val is not None else None
        running_str = str(running_val) if running_val is not None else None

        if stored_str is None and running_str is not None:
            status = "added"
        elif stored_str is not None and running_str is None:
            status = "removed"
        elif stored_str != running_str:
            status = "changed"
        else:
            status = "unchanged"

        differences.append(
            ConfigDiffItem(
                key=key,
                stored_value=stored_str,
                running_value=running_str,
                status=status,
            )
        )

    has_diff = any(d.status != "unchanged" for d in differences)

    return ConfigDiffResponse(
        has_diff=has_diff,
        differences=differences,
        stored_config_hash=None,
        running_config_hash=None,
    )


@router.get(
    "/system/test-report/export",
    summary="导出测试报告",
    description="导出测试报告为CSV格式，支持UTF-8 BOM以兼容Excel中文字符显示",
    response_description="CSV格式的测试报告文件",
)
async def export_test_report_csv(
    request: Request,
    limit: int = Query(default=1000, ge=1, le=10000, description="导出数量限制"),
) -> PlainTextResponse:
    """导出测试报告为CSV格式。

    返回包含测试结果的CSV文件，支持UTF-8 BOM以兼容Excel中文字符显示。
    """
    storage = request.app.state.storage

    # Get proxies with test results
    items = storage.list_proxies_filtered(
        limit=limit,
        offset=0,
        sort_by="last_checked",
        sort_order="desc",
    )

    # Create CSV with UTF-8 BOM
    output = io.StringIO()
    output.write("﻿")  # UTF-8 BOM

    writer = csv.writer(output)

    # Write headers
    writer.writerow(
        ["地址", "协议", "测试结果", "延迟(ms)", "错误信息", "出口IP", "国家", "城市", "测试时间"]
    )

    # Write data rows
    for item in items:
        # Determine test result
        available = item.get("available")
        test_result = "成功" if available else "失败" if available is not None else "未测试"

        writer.writerow(
            [
                f"{item.get('host', '')}:{item.get('port', '')}",
                item.get("protocol", ""),
                test_result,
                item.get("latency_ms", ""),
                item.get("error", ""),
                item.get("resolved_ip", ""),
                item.get("country", ""),
                item.get("city", ""),
                item.get("last_checked_at", ""),
            ]
        )

    # Generate filename
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"test-report-{date_str}.csv"

    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )


@router.get(
    "/system/metrics",
    summary="系统性能指标",
    description="返回系统级性能指标，包括请求计数、延迟百分位数、错误率等",
    response_description="系统性能指标",
    response_model=SystemMetricsResponse,
)
async def system_metrics(
    request: Request,
) -> SystemMetricsResponse:
    """获取系统性能指标

    返回系统级的性能指标数据，包括请求统计、延迟百分位数、错误率等。
    支持1分钟、5分钟、1小时的时间窗口聚合。
    """
    metrics_service = request.app.state.metrics_service
    storage = request.app.state.storage

    metrics_data = metrics_service.get_system_metrics(storage)
    return SystemMetricsResponse(**metrics_data)


@router.get(
    "/system/metrics/export",
    summary="导出性能指标",
    description="导出完整的性能指标数据，包括系统指标、多时间窗口指标和代理池指标",
    response_description="完整指标数据",
    response_model=MetricsExportResponse,
)
async def export_metrics(
    request: Request,
) -> MetricsExportResponse:
    """导出完整性能指标

    导出系统的完整性能指标数据，包括系统级指标、多个时间窗口的历史指标，
    以及各代理池的指标数据。
    """
    metrics_service = request.app.state.metrics_service
    storage = request.app.state.storage

    metrics_data = metrics_service.get_metrics_export(storage)
    return MetricsExportResponse(**metrics_data)


@router.get(
    "/system/traces",
    summary="请求追踪列表",
    description="返回最近的请求追踪记录，包括关联ID、路径、耗时、状态码等",
    response_description="请求追踪列表",
)
async def system_traces(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000, description="返回记录数"),
) -> list[RequestTraceResponse]:
    """获取请求追踪记录。

    返回最近的请求追踪记录，支持限制返回数量。
    """
    monitoring_service = request.app.state.monitoring_service
    traces = monitoring_service.get_recent_traces(limit=limit)
    return [RequestTraceResponse(**trace) for trace in traces]


@router.get(
    "/system/errors",
    summary="错误摘要",
    description="返回指定时间范围内的错误摘要，包括错误类型统计、错误最多的路径等",
    response_description="错误摘要",
    response_model=ErrorSummaryResponse,
)
async def system_errors(
    request: Request,
    last_minutes: int = Query(default=60, ge=1, le=1440, description="统计时间范围（分钟）"),
) -> ErrorSummaryResponse:
    """获取错误摘要。

    返回指定时间范围内的错误统计信息。
    """
    monitoring_service = request.app.state.monitoring_service
    error_summary = monitoring_service.error_aggregator.get_error_summary(
        last_minutes=last_minutes
    )
    return ErrorSummaryResponse(**error_summary)


@router.get(
    "/system/bottlenecks",
    summary="性能瓶颈检测",
    description="返回检测到的性能瓶颈，包括高延迟路径、错误率等",
    response_description="性能瓶颈列表",
)
async def system_bottlenecks(
    request: Request,
    threshold_ms: float = Query(default=100.0, ge=10.0, le=1000.0, description="延迟阈值（毫秒）"),
) -> list[BottleneckResponse]:
    """检测性能瓶颈。

    返回超过延迟阈值或错误率过高的路径。
    """
    monitoring_service = request.app.state.monitoring_service
    bottlenecks = monitoring_service.performance_monitor.detect_bottlenecks(
        threshold_ms=threshold_ms
    )
    return [
        BottleneckResponse(
            path=b.path,
            avg_latency_ms=b.avg_latency_ms,
            p95_latency_ms=b.p95_latency_ms,
            p99_latency_ms=b.p99_latency_ms,
            request_count=b.request_count,
            error_rate=b.error_rate,
            severity=b.severity,
        )
        for b in bottlenecks
    ]


@router.get(
    "/system/capacity",
    summary="容量规划指标",
    description="返回容量规划指标，包括请求统计、延迟分布、唯一路径数等",
    response_description="容量指标",
    response_model=CapacityMetricsResponse,
)
async def system_capacity(
    request: Request,
) -> CapacityMetricsResponse:
    """获取容量规划指标。

    返回系统容量相关的统计数据。
    """
    monitoring_service = request.app.state.monitoring_service
    capacity = monitoring_service.performance_monitor.get_capacity_metrics()
    return CapacityMetricsResponse(**capacity)


@router.get(
    "/system/health/monitoring",
    summary="综合健康监控",
    description="返回综合健康监控数据，包括错误摘要、性能瓶颈、容量指标等",
    response_description="健康监控数据",
    response_model=HealthSummaryResponse,
)
async def system_health_monitoring(
    request: Request,
) -> HealthSummaryResponse:
    """获取综合健康监控数据。

    返回系统的全面健康状态，包括活跃请求、错误摘要、性能瓶颈和容量指标。
    """
    monitoring_service = request.app.state.monitoring_service
    health_summary = monitoring_service.get_health_summary()
    return HealthSummaryResponse(**health_summary)
