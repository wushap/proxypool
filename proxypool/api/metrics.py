"""
性能指标收集和聚合服务

提供请求计数、延迟百分位数、错误率等指标的收集和聚合功能。
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class RequestRecord:
    """请求记录"""

    timestamp: float
    latency_ms: float
    success: bool
    path: str = ""
    method: str = ""
    status_code: int = 200
    pool_id: int | None = None


@dataclass
class MetricsWindowData:
    """指标窗口数据"""

    window_name: str
    duration_seconds: int
    start_time: float
    end_time: float
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    latencies: list[float] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    @property
    def latency_percentiles(self) -> dict:
        if not self.latencies:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}

        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)

        def percentile(p: int) -> float:
            index = int(n * p / 100)
            index = min(index, n - 1)
            return sorted_latencies[index]

        return {
            "p50": percentile(50),
            "p90": percentile(90),
            "p95": percentile(95),
            "p99": percentile(99),
        }


class MetricsService:
    """性能指标服务"""

    # 时间窗口定义（秒）
    WINDOWS = {
        "1min": 60,
        "5min": 300,
        "1hour": 3600,
    }

    def __init__(self, max_records: int = 10000):
        self._records: deque[RequestRecord] = deque(maxlen=max_records)
        self._lock = threading.Lock()
        self._start_time = time.time()

    def record_request(
        self,
        path: str,
        method: str,
        status_code: int,
        latency_ms: float,
        pool_id: int | None = None,
    ) -> None:
        """记录一个请求"""
        record = RequestRecord(
            timestamp=time.time(),
            latency_ms=latency_ms,
            success=200 <= status_code < 400,
            path=path,
            method=method,
            status_code=status_code,
            pool_id=pool_id,
        )

        with self._lock:
            self._records.append(record)

    def record_response_size(self, path: str, size_bytes: int) -> None:
        """记录响应大小（用于监控）"""
        # This is a placeholder for response size monitoring
        # In a production system, you might want to track this separately
        # or aggregate it with the request records
        pass

    def _get_records_in_window(self, start_time: float, end_time: float) -> list[RequestRecord]:
        """获取时间窗口内的记录"""
        with self._lock:
            return [r for r in self._records if start_time <= r.timestamp <= end_time]

    def _calculate_metrics(self, records: list[RequestRecord]) -> dict:
        """计算指标"""
        if not records:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "error_rate": 0.0,
                "avg_latency_ms": 0.0,
                "latency_percentiles": {
                    "p50": 0.0,
                    "p90": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                },
            }

        total = len(records)
        successful = sum(1 for r in records if r.success)
        failed = total - successful
        latencies = [r.latency_ms for r in records]

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        def percentile(p: int) -> float:
            index = int(n * p / 100)
            index = min(index, n - 1)
            return sorted_latencies[index]

        return {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "error_rate": failed / total if total > 0 else 0.0,
            "avg_latency_ms": sum(latencies) / total if total > 0 else 0.0,
            "latency_percentiles": {
                "p50": percentile(50),
                "p90": percentile(90),
                "p95": percentile(95),
                "p99": percentile(99),
            },
        }

    def get_system_metrics(self, storage=None) -> dict:
        """获取系统级指标"""
        now = time.time()
        uptime = int(now - self._start_time)

        # 获取所有请求记录
        all_records = self._get_records_in_window(self._start_time, now)
        metrics = self._calculate_metrics(all_records)

        # 获取代理测试统计
        total_proxies_tested = 0
        proxy_test_success = 0
        if storage:
            try:
                stats = storage.get_stats()
                total_proxies_tested = stats.get("total", 0)
                proxy_test_success = stats.get("available", 0) or stats.get("healthy", 0)
            except Exception:
                pass

        proxy_test_success_rate = (
            proxy_test_success / total_proxies_tested if total_proxies_tested > 0 else 0.0
        )

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": uptime,
            "requests": metrics,
            "active_connections": 0,  # Placeholder - would need middleware to track
            "total_proxies_tested": total_proxies_tested,
            "proxy_test_success_rate": round(proxy_test_success_rate, 3),
        }

    def get_pool_metrics(self, pool_id: int, pool_name: str, storage=None) -> dict:
        """获取代理池级指标"""
        now = time.time()

        # 获取该池的请求记录
        pool_records = [
            r for r in self._get_records_in_window(self._start_time, now) if r.pool_id == pool_id
        ]
        metrics = self._calculate_metrics(pool_records)

        # 获取池的代理统计
        active_proxies = 0
        total_proxies = 0
        healthy_proxies = 0
        if storage:
            try:
                pool_stats = storage.get_proxy_pool_stats(pool_id)
                if pool_stats:
                    total_proxies = pool_stats.get("total", 0)
                    healthy_proxies = pool_stats.get("healthy", 0)
                    active_proxies = pool_stats.get("active", 0)
            except Exception:
                pass

        proxy_health_rate = healthy_proxies / total_proxies if total_proxies > 0 else 0.0

        return {
            "pool_id": pool_id,
            "pool_name": pool_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "requests": metrics,
            "active_proxies": active_proxies,
            "total_proxies": total_proxies,
            "healthy_proxies": healthy_proxies,
            "proxy_health_rate": round(proxy_health_rate, 3),
            "avg_latency_ms": metrics["avg_latency_ms"],
        }

    def get_metrics_windows(self) -> list[dict]:
        """获取多个时间窗口的指标"""
        now = time.time()
        windows = []

        for window_name, duration in self.WINDOWS.items():
            start_time = now - duration
            records = self._get_records_in_window(start_time, now)
            metrics = self._calculate_metrics(records)

            windows.append(
                {
                    "window": window_name,
                    "start_time": datetime.fromtimestamp(start_time, UTC).isoformat(),
                    "end_time": datetime.fromtimestamp(now, UTC).isoformat(),
                    "requests": metrics,
                }
            )

        return windows

    def get_metrics_export(self, storage=None) -> dict:
        """导出完整指标数据"""
        system_metrics = self.get_system_metrics(storage)
        windows = self.get_metrics_windows()

        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "system_metrics": system_metrics,
            "windows": windows,
            "pools": [],  # Would need pool list to populate
        }
