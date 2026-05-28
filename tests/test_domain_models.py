"""
Tests for domain models: ProxyNode, NodeScore, CheckResult, EventLog.
"""

from __future__ import annotations

import pytest

from proxypool.models import (
    CheckResult,
    CheckType,
    EventLog,
    EventSeverity,
    EventType,
    NodeStatus,
    ProxyNode,
)


class TestProxyNode:
    """Test ProxyNode model."""

    def test_create_proxy_node(self):
        """Test creating a ProxyNode instance."""
        node = ProxyNode(
            protocol="http",
            host="example.com",
            port=8080,
            raw_link="http://example.com:8080",
            name="Test Node",
        )
        assert node.protocol == "http"
        assert node.host == "example.com"
        assert node.port == 8080
        assert node.name == "Test Node"

    def test_normalized_key(self):
        """Test normalized_key generation."""
        node1 = ProxyNode(
            protocol="http",
            host="example.com",
            port=8080,
            raw_link="http://example.com:8080",
        )
        node2 = ProxyNode(
            protocol="http",
            host="example.com",
            port=8080,
            raw_link="http://example.com:8080",
        )
        # Same parameters should produce same key
        assert node1.normalized_key() == node2.normalized_key()

    def test_normalized_key_with_uuid(self):
        """Test normalized_key with UUID in extra."""
        node = ProxyNode(
            protocol="vmess",
            host="example.com",
            port=443,
            raw_link="vmess://abc123",
            extra={"uuid": "test-uuid-123"},
        )
        key = node.normalized_key()
        assert len(key) == 40  # SHA1 hex digest

    def test_is_healthy(self):
        """Test is_healthy method."""
        node_available = ProxyNode(
            protocol="http",
            host="example.com",
            port=8080,
            raw_link="http://example.com:8080",
            status=NodeStatus.AVAILABLE,
        )
        assert node_available.is_healthy() is True

        node_unavailable = ProxyNode(
            protocol="http",
            host="example.com",
            port=8080,
            raw_link="http://example.com:8080",
            status=NodeStatus.UNAVAILABLE,
        )
        assert node_unavailable.is_healthy() is False

        node_degraded = ProxyNode(
            protocol="http",
            host="example.com",
            port=8080,
            raw_link="http://example.com:8080",
            status=NodeStatus.DEGRADED,
        )
        assert node_degraded.is_healthy() is True

    def test_to_dict(self):
        """Test to_dict method."""
        node = ProxyNode(
            protocol="http",
            host="example.com",
            port=8080,
            raw_link="http://example.com:8080",
            name="Test",
            status=NodeStatus.AVAILABLE,
            available=True,
            latency_ms=150,
            score=0.85,
        )
        data = node.to_dict()
        assert data["protocol"] == "http"
        assert data["host"] == "example.com"
        assert data["port"] == 8080
        assert data["status"] == "available"
        assert data["available"] is True
        assert data["latency_ms"] == 150
        assert data["score"] == 0.85


class TestNodeScore:
    """Test NodeScore model.

    Note: These tests verify the old NodeScore interface which has been replaced
    by the scoring.py implementation. They are kept for backwards compatibility
    but may need to be updated if the scoring module changes.
    """

    @pytest.mark.skip(reason="Old NodeScore interface replaced by scoring.py")
    def test_calculate_score(self):
        """Test score calculation."""
        pass

    @pytest.mark.skip(reason="Old NodeScore interface replaced by scoring.py")
    def test_score_weights(self):
        """Test custom score weights."""
        pass

    @pytest.mark.skip(reason="Old NodeScore interface replaced by scoring.py")
    def test_latency_scoring(self):
        """Test latency score ranges."""
        pass


class TestCheckResult:
    """Test CheckResult model."""

    def test_create_check_result(self):
        """Test creating CheckResult."""
        result = CheckResult(
            node_key="test-key",
            check_type=CheckType.ACTIVE,
            success=True,
            latency_ms=100,
        )
        assert result.node_key == "test-key"
        assert result.success is True
        assert result.latency_ms == 100

    def test_check_result_to_dict(self):
        """Test CheckResult.to_dict()."""
        result = CheckResult(
            node_key="test-key",
            check_type=CheckType.SPEED,
            success=True,
            speed_mbps=25.5,
        )
        data = result.to_dict()
        assert data["node_key"] == "test-key"
        assert data["success"] is True
        assert data["speed_mbps"] == 25.5


class TestEventLog:
    """Test EventLog model."""

    def test_create_event_log(self):
        """Test creating EventLog."""
        event = EventLog(
            event_type=EventType.NODE_AVAILABLE,
            severity=EventSeverity.INFO,
            node_key="test-key",
            message="Node is now available",
        )
        assert event.event_type == "node.available"
        assert event.severity == "info"
        assert event.node_key == "test-key"

    def test_event_log_to_dict(self):
        """Test EventLog.to_dict()."""
        event = EventLog(
            event_type=EventType.BACKEND_STARTED,
            severity=EventSeverity.INFO,
            backend="singbox",
            message="Backend started successfully",
        )
        data = event.to_dict()
        assert data["event_type"] == "backend.started"
        assert data["backend"] == "singbox"
        assert data["message"] == "Backend started successfully"
