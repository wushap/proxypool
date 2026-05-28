"""Tests for API monitoring functionality."""

import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from proxypool.api.monitoring import (
    CorrelationIdGenerator,
    ErrorAggregator,
    ErrorRecord,
    MonitoringService,
    PerformanceBottleneck,
    PerformanceMonitor,
    RequestTrace,
)


class TestCorrelationIdGenerator:
    """Test CorrelationIdGenerator class."""

    def test_generate_unique_ids(self):
        """Test that generated IDs are unique."""
        ids = {CorrelationIdGenerator.generate() for _ in range(100)}
        assert len(ids) == 100

    def test_generate_format(self):
        """Test that ID format is correct."""
        id1 = CorrelationIdGenerator.generate()
        # Format: timestamp-counter
        parts = id1.split("-")
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert parts[1].isdigit()


class TestErrorAggregator:
    """Test ErrorAggregator class."""

    def test_record_error(self):
        """Test recording errors."""
        aggregator = ErrorAggregator()
        aggregator.record_error(
            path="/api/test",
            method="GET",
            status_code=500,
            error_type="http_500",
            error_message="Internal Server Error",
        )
        summary = aggregator.get_error_summary(last_minutes=60)
        assert summary["total_errors"] == 1
        assert "http_500" in summary["error_types"]
        assert summary["error_types"]["http_500"] == 1

    def test_error_summary_empty(self):
        """Test error summary when no errors."""
        aggregator = ErrorAggregator()
        summary = aggregator.get_error_summary(last_minutes=60)
        assert summary["total_errors"] == 0
        assert summary["error_types"] == {}
        assert summary["top_error_paths"] == []
        assert summary["error_rate_per_minute"] == 0.0

    def test_error_truncation(self):
        """Test that long error messages are truncated."""
        aggregator = ErrorAggregator()
        long_message = "x" * 1000
        aggregator.record_error(
            path="/api/test",
            method="GET",
            status_code=500,
            error_type="http_500",
            error_message=long_message,
        )
        summary = aggregator.get_error_summary(last_minutes=60)
        error_record = aggregator._errors[0]
        assert len(error_record.error_message) <= 500


class TestPerformanceMonitor:
    """Test PerformanceMonitor class."""

    def test_record_request(self):
        """Test recording request performance."""
        monitor = PerformanceMonitor()
        monitor.record_request(path="/api/test", latency_ms=50.0, status_code=200)
        metrics = monitor.get_capacity_metrics()
        assert metrics["total_requests"] == 1

    def test_detect_bottlenecks(self):
        """Test bottleneck detection."""
        monitor = PerformanceMonitor()
        # Record 20 requests with high latency (above threshold * 2 for critical)
        for _ in range(20):
            monitor.record_request(path="/api/slow", latency_ms=250.0, status_code=200)
        bottlenecks = monitor.detect_bottlenecks(threshold_ms=100.0)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].path == "/api/slow"
        assert bottlenecks[0].severity == "critical"

    def test_detect_bottlenecks_normal(self):
        """Test no bottleneck for normal latency."""
        monitor = PerformanceMonitor()
        for _ in range(20):
            monitor.record_request(path="/api/fast", latency_ms=20.0, status_code=200)
        bottlenecks = monitor.detect_bottlenecks(threshold_ms=100.0)
        assert len(bottlenecks) == 0

    def test_capacity_metrics(self):
        """Test capacity metrics calculation."""
        monitor = PerformanceMonitor()
        monitor.record_request(path="/api/test", latency_ms=50.0, status_code=200)
        monitor.record_request(path="/api/test", latency_ms=60.0, status_code=200)
        monitor.record_request(path="/api/test", latency_ms=70.0, status_code=400)
        metrics = monitor.get_capacity_metrics()
        assert metrics["total_requests"] == 3
        assert metrics["total_errors"] == 1
        assert "/api/test" in metrics["latency_stats"]


class TestMonitoringService:
    """Test MonitoringService class."""

    def test_start_end_request(self):
        """Test request tracking lifecycle."""
        service = MonitoringService()
        trace = service.start_request(
            correlation_id="test-123",
            path="/api/test",
            method="GET",
            client_ip="127.0.0.1",
        )
        assert trace.correlation_id == "test-123"
        assert trace.path == "/api/test"

        time.sleep(0.01)  # Small delay to ensure duration > 0
        ended_trace = service.end_request(
            correlation_id="test-123",
            status_code=200,
            response_size=1024,
        )
        assert ended_trace is not None
        assert ended_trace.duration_ms > 0

    def test_get_request_trace(self):
        """Test getting active request trace."""
        service = MonitoringService()
        service.start_request(
            correlation_id="test-456",
            path="/api/test",
            method="GET",
        )
        trace = service.get_request_trace("test-456")
        assert trace is not None
        assert trace.correlation_id == "test-456"

    def test_get_recent_traces(self):
        """Test getting recent traces."""
        service = MonitoringService()
        for i in range(5):
            service.start_request(
                correlation_id=f"trace-{i}",
                path=f"/api/test/{i}",
                method="GET",
            )
            service.end_request(
                correlation_id=f"trace-{i}",
                status_code=200,
            )
        traces = service.get_recent_traces(limit=10)
        assert len(traces) == 5

    def test_health_summary(self):
        """Test health summary generation."""
        service = MonitoringService()
        service.start_request(
            correlation_id="test-789",
            path="/api/test",
            method="GET",
        )
        summary = service.get_health_summary()
        assert summary["active_requests"] == 1
        assert "error_summary" in summary
        assert "bottlenecks" in summary
        assert "capacity" in summary
        assert "timestamp" in summary
