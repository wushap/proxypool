"""
Backend Monitoring Module - Request tracing, error aggregation, performance monitoring.
"""

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class RequestTrace:
    """Request trace with correlation ID"""

    correlation_id: str
    path: str
    method: str
    start_time: float
    end_time: float | None = None
    status_code: int = 0
    client_ip: str = ""
    error: str = ""
    response_size: int = 0

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0


@dataclass
class ErrorRecord:
    """Error record for aggregation"""

    timestamp: float
    path: str
    method: str
    status_code: int
    error_type: str
    error_message: str
    correlation_id: str = ""
    count: int = 1


@dataclass
class PerformanceBottleneck:
    """Performance bottleneck detection"""

    path: str
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    request_count: int
    error_rate: float
    severity: str = "normal"  # normal, warning, critical


class CorrelationIdGenerator:
    """Generate unique correlation IDs for request tracing"""

    _counter = 0
    _lock = threading.Lock()

    @classmethod
    def generate(cls) -> str:
        with cls._lock:
            cls._counter += 1
            timestamp = int(time.time() * 1000)
            return f"{timestamp}-{cls._counter:06d}"


class ErrorAggregator:
    """Aggregate and analyze errors"""

    def __init__(self, max_records: int = 10000):
        self._errors: deque[ErrorRecord] = deque(maxlen=max_records)
        self._error_counts: dict[str, int] = defaultdict(int)
        self._path_errors: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._lock = threading.Lock()

    def record_error(
        self,
        path: str,
        method: str,
        status_code: int,
        error_type: str,
        error_message: str,
        correlation_id: str = "",
    ) -> None:
        """Record an error"""
        record = ErrorRecord(
            timestamp=time.time(),
            path=path,
            method=method,
            status_code=status_code,
            error_type=error_type,
            error_message=error_message[:500],  # Truncate long messages
            correlation_id=correlation_id,
        )

        with self._lock:
            self._errors.append(record)
            self._error_counts[error_type] += 1
            self._path_errors[path][error_type] += 1

    def get_error_summary(self, last_minutes: int = 60) -> dict:
        """Get error summary for the last N minutes"""
        cutoff = time.time() - (last_minutes * 60)

        with self._lock:
            recent_errors = [e for e in self._errors if e.timestamp >= cutoff]

        if not recent_errors:
            return {
                "total_errors": 0,
                "error_types": {},
                "top_error_paths": [],
                "error_rate_per_minute": 0.0,
            }

        # Count by type
        error_types = defaultdict(int)
        for error in recent_errors:
            error_types[error.error_type] += 1

        # Top error paths
        path_counts = defaultdict(int)
        for error in recent_errors:
            path_counts[error.path] += 1

        top_paths = sorted(path_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Error rate
        error_rate = len(recent_errors) / last_minutes if last_minutes > 0 else 0.0

        return {
            "total_errors": len(recent_errors),
            "error_types": dict(error_types),
            "top_error_paths": [{"path": p, "count": c} for p, c in top_paths],
            "error_rate_per_minute": round(error_rate, 2),
            "last_minutes": last_minutes,
        }


class PerformanceMonitor:
    """Monitor performance and detect bottlenecks"""

    def __init__(self, max_records: int = 10000):
        self._latencies: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._path_counts: dict[str, int] = defaultdict(int)
        self._path_errors: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def record_request(
        self,
        path: str,
        latency_ms: float,
        status_code: int,
    ) -> None:
        """Record request performance"""
        with self._lock:
            self._latencies[path].append(latency_ms)
            self._path_counts[path] += 1
            if status_code >= 400:
                self._path_errors[path] += 1

    def detect_bottlenecks(self, threshold_ms: float = 100.0) -> list[PerformanceBottleneck]:
        """Detect performance bottlenecks"""
        bottlenecks = []

        with self._lock:
            for path, latencies in self._latencies.items():
                if len(latencies) < 10:  # Need minimum data points
                    continue

                sorted_latencies = sorted(latencies)
                n = len(sorted_latencies)

                avg_latency = sum(sorted_latencies) / n
                p95_index = min(int(n * 0.95), n - 1)
                p99_index = min(int(n * 0.99), n - 1)

                p95_latency = sorted_latencies[p95_index]
                p99_latency = sorted_latencies[p99_index]

                total_requests = self._path_counts.get(path, 0)
                error_count = self._path_errors.get(path, 0)
                error_rate = error_count / total_requests if total_requests > 0 else 0.0

                # Determine severity
                severity = "normal"
                if p95_latency > threshold_ms * 2 or error_rate > 0.1:
                    severity = "critical"
                elif p95_latency > threshold_ms or error_rate > 0.05:
                    severity = "warning"

                if severity != "normal":
                    bottlenecks.append(
                        PerformanceBottleneck(
                            path=path,
                            avg_latency_ms=round(avg_latency, 2),
                            p95_latency_ms=round(p95_latency, 2),
                            p99_latency_ms=round(p99_latency, 2),
                            request_count=total_requests,
                            error_rate=round(error_rate, 4),
                            severity=severity,
                        )
                    )

        return sorted(bottlenecks, key=lambda b: b.p99_latency_ms, reverse=True)

    def get_capacity_metrics(self) -> dict:
        """Get capacity planning metrics"""
        with self._lock:
            total_requests = sum(self._path_counts.values())
            total_errors = sum(self._path_errors.values())

            # Requests by path (top 20)
            top_paths = sorted(self._path_counts.items(), key=lambda x: x[1], reverse=True)[:20]

            # Average latency by path
            latency_stats = {}
            for path, latencies in self._latencies.items():
                if latencies:
                    sorted_lat = sorted(latencies)
                    n = len(sorted_lat)
                    latency_stats[path] = {
                        "avg_ms": round(sum(sorted_lat) / n, 2),
                        "p50_ms": round(sorted_lat[int(n * 0.5)], 2),
                        "p95_ms": round(sorted_lat[min(int(n * 0.95), n - 1)], 2),
                        "p99_ms": round(sorted_lat[min(int(n * 0.99), n - 1)], 2),
                        "count": n,
                    }

        return {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": round(total_errors / total_requests, 4) if total_requests > 0 else 0.0,
            "top_paths": [{"path": p, "count": c} for p, c in top_paths],
            "latency_stats": latency_stats,
            "unique_paths": len(self._path_counts),
        }


class MonitoringService:
    """Unified monitoring service"""

    def __init__(self, max_records: int = 10000):
        self.error_aggregator = ErrorAggregator(max_records)
        self.performance_monitor = PerformanceMonitor(max_records)
        self._request_traces: deque[RequestTrace] = deque(maxlen=max_records)
        self._active_requests: dict[str, RequestTrace] = {}
        self._lock = threading.Lock()

    def start_request(
        self,
        correlation_id: str,
        path: str,
        method: str,
        client_ip: str = "",
    ) -> RequestTrace:
        """Start tracking a request"""
        trace = RequestTrace(
            correlation_id=correlation_id,
            path=path,
            method=method,
            start_time=time.time(),
            client_ip=client_ip,
        )

        with self._lock:
            self._active_requests[correlation_id] = trace

        return trace

    def end_request(
        self,
        correlation_id: str,
        status_code: int,
        response_size: int = 0,
        error: str = "",
    ) -> RequestTrace | None:
        """End tracking a request"""
        with self._lock:
            trace = self._active_requests.pop(correlation_id, None)

        if trace:
            trace.end_time = time.time()
            trace.status_code = status_code
            trace.response_size = response_size
            trace.error = error

            # Record in performance monitor
            self.performance_monitor.record_request(
                path=trace.path,
                latency_ms=trace.duration_ms,
                status_code=status_code,
            )

            # Record errors
            if status_code >= 400:
                self.error_aggregator.record_error(
                    path=trace.path,
                    method=trace.method,
                    status_code=status_code,
                    error_type=f"http_{status_code}",
                    error_message=error or f"HTTP {status_code}",
                    correlation_id=correlation_id,
                )

            with self._lock:
                self._request_traces.append(trace)

        return trace

    def get_request_trace(self, correlation_id: str) -> RequestTrace | None:
        """Get trace by correlation ID"""
        with self._lock:
            return self._active_requests.get(correlation_id)

    def get_recent_traces(self, limit: int = 100) -> list[dict]:
        """Get recent request traces"""
        with self._lock:
            traces = list(self._request_traces)[-limit:]

        return [
            {
                "correlation_id": t.correlation_id,
                "path": t.path,
                "method": t.method,
                "duration_ms": round(t.duration_ms, 2),
                "status_code": t.status_code,
                "client_ip": t.client_ip,
                "error": t.error,
                "response_size": t.response_size,
                "start_time": datetime.fromtimestamp(t.start_time, UTC).isoformat(),
            }
            for t in reversed(traces)
        ]

    def get_health_summary(self) -> dict:
        """Get comprehensive health summary"""
        error_summary = self.error_aggregator.get_error_summary(last_minutes=60)
        bottlenecks = self.performance_monitor.detect_bottlenecks()
        capacity = self.performance_monitor.get_capacity_metrics()

        with self._lock:
            active_count = len(self._active_requests)

        return {
            "active_requests": active_count,
            "error_summary": error_summary,
            "bottlenecks": [
                {
                    "path": b.path,
                    "avg_latency_ms": b.avg_latency_ms,
                    "p95_latency_ms": b.p95_latency_ms,
                    "p99_latency_ms": b.p99_latency_ms,
                    "request_count": b.request_count,
                    "error_rate": b.error_rate,
                    "severity": b.severity,
                }
                for b in bottlenecks
            ],
            "capacity": capacity,
            "timestamp": datetime.now(UTC).isoformat(),
        }
