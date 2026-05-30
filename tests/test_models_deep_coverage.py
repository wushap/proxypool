"""
Deep edge-case tests for domain models: ProxyNode, CheckResult, EventLog.
Complements test_domain_models.py with boundary and variant coverage.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from proxypool.models import (
    CheckResult,
    CheckType,
    EventLog,
    EventSeverity,
    EventType,
    NodeStatus,
    ProxyNode,
    ProxyProtocol,
)


# ---- Helper ----

def _make_node(**overrides):
    defaults = dict(
        protocol="http",
        host="1.2.3.4",
        port=8080,
        raw_link="http://1.2.3.4:8080",
    )
    defaults.update(overrides)
    return ProxyNode(**defaults)


# ---- ProxyProtocol enum ----

class TestProxyProtocolEnum:
    def test_all_values_present(self):
        expected = {
            "http", "https", "socks4", "socks5", "shadowsocks",
            "vmess", "vless", "trojan", "hysteria", "hysteria2",
            "tuic", "wireguard",
        }
        assert {p.value for p in ProxyProtocol} == expected

    def test_member_is_str(self):
        assert isinstance(ProxyProtocol.HTTP, str)
        assert ProxyProtocol.HTTP == "http"


# ---- NodeStatus enum ----

class TestNodeStatusEnum:
    def test_all_values(self):
        expected = {"unknown", "available", "unavailable", "degraded", "circuit_open"}
        assert {s.value for s in NodeStatus} == expected


# ---- ProxyNode.normalized_key edge cases ----

class TestNormalizedKey:
    def test_no_identity(self):
        node = _make_node(extra={})
        key = node.normalized_key()
        assert len(key) == 40
        # same params -> same key
        assert _make_node(extra={}).normalized_key() == key

    def test_identity_via_password(self):
        a = _make_node(extra={"password": "secret"})
        b = _make_node(extra={"password": "secret"})
        assert a.normalized_key() == b.normalized_key()

    def test_identity_via_username(self):
        a = _make_node(extra={"username": "user1"})
        b = _make_node(extra={"username": "user1"})
        assert a.normalized_key() == b.normalized_key()

    def test_uuid_takes_priority(self):
        """uuid is preferred over password when both present."""
        node = _make_node(extra={"uuid": "u1", "password": "p1"})
        node_uuid_only = _make_node(extra={"uuid": "u1"})
        assert node.normalized_key() == node_uuid_only.normalized_key()

    def test_different_hosts_differ(self):
        a = _make_node(host="1.1.1.1")
        b = _make_node(host="2.2.2.2")
        assert a.normalized_key() != b.normalized_key()

    def test_different_protocols_differ(self):
        a = _make_node(protocol="http")
        b = _make_node(protocol="socks5")
        assert a.normalized_key() != b.normalized_key()

    def test_different_ports_differ(self):
        a = _make_node(port=80)
        b = _make_node(port=8080)
        assert a.normalized_key() != b.normalized_key()


# ---- ProxyNode.is_healthy edge cases ----

class TestIsHealthy:
    @pytest.mark.parametrize("status,expected", [
        (NodeStatus.UNKNOWN, False),
        (NodeStatus.AVAILABLE, True),
        (NodeStatus.UNAVAILABLE, False),
        (NodeStatus.DEGRADED, True),
        (NodeStatus.CIRCUIT_OPEN, False),
    ])
    def test_all_statuses(self, status, expected):
        assert _make_node(status=status).is_healthy() is expected


# ---- ProxyNode.to_dict edge cases ----

class TestToDict:
    def test_string_status_branch(self):
        """to_dict handles status as a plain string (not enum member)."""
        node = _make_node()
        node.status = "available"  # plain str, not NodeStatus
        data = node.to_dict()
        assert data["status"] == "available"

    def test_enum_status_branch(self):
        node = _make_node(status=NodeStatus.UNAVAILABLE)
        data = node.to_dict()
        assert data["status"] == "unavailable"

    def test_to_dict_includes_normalized_key(self):
        node = _make_node()
        data = node.to_dict()
        assert data["normalized_key"] == node.normalized_key()

    def test_datetime_serialization(self):
        now = datetime.now(UTC)
        node = _make_node(
            last_checked_at=now,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
            speed_tested_at=now,
            score_updated_at=now,
            openai_checked_at=now,
            geo_updated_at=now,
        )
        data = node.to_dict()
        # last_checked_at is serialized as isoformat
        assert data["last_checked_at"] == now.isoformat()
        assert data["last_seen_at"] == now.isoformat()
        assert data["created_at"] == now.isoformat()
        assert data["updated_at"] == now.isoformat()
        assert data["openai_checked_at"] == now.isoformat()

    def test_none_datetime_fields(self):
        node = _make_node()
        data = node.to_dict()
        assert data["last_checked_at"] is None
        assert data["openai_checked_at"] is None

    def test_extra_fields_included(self):
        node = _make_node(
            source="sub1",
            name="My Node",
            latency_ms=42,
            speed_mbps=100.5,
            fail_count=3,
            last_error="timeout",
            resolved_ip="5.5.5.5",
            country="US",
            city="NYC",
            score=0.9,
            ip_purity_score=85.0,
            ip_purity_level="clean",
            openai_unlocked=True,
            openai_status="unlocked",
            fallback_front_keys=["k1", "k2"],
        )
        data = node.to_dict()
        assert data["source"] == "sub1"
        assert data["name"] == "My Node"
        assert data["latency_ms"] == 42
        assert data["speed_mbps"] == 100.5
        assert data["fail_count"] == 3
        assert data["last_error"] == "timeout"
        assert data["resolved_ip"] == "5.5.5.5"
        assert data["country"] == "US"
        assert data["city"] == "NYC"
        assert data["score"] == 0.9
        assert data["ip_purity_score"] == 85.0
        assert data["ip_purity_level"] == "clean"
        assert data["openai_unlocked"] is True
        assert data["openai_status"] == "unlocked"
        assert data["fallback_front_keys"] == ["k1", "k2"]


# ---- ProxyNode defaults ----

class TestDefaults:
    def test_default_field_values(self):
        node = _make_node()
        assert node.status == NodeStatus.UNKNOWN
        assert node.available is False
        assert node.latency_ms is None
        assert node.speed_mbps is None
        assert node.fail_count == 0
        assert node.last_error == ""
        assert node.score == 0.0
        assert node.ip_purity_score is None
        assert node.openai_unlocked is None
        assert node.extra == {}
        assert node.fallback_front_keys == []

    def test_extra_is_independent_instances(self):
        """Each node gets its own dict/list (no shared mutable default)."""
        a = _make_node()
        b = _make_node()
        a.extra["k"] = "v"
        assert "k" not in b.extra

    def test_fallback_front_keys_independent(self):
        a = _make_node()
        b = _make_node()
        a.fallback_front_keys.append("x")
        assert b.fallback_front_keys == []


# ---- CheckResult edge cases ----

class TestCheckResult:
    def test_default_check_id_is_uuid(self):
        result = CheckResult()
        # Verify it's a valid UUID
        parsed = uuid.UUID(result.check_id)
        assert str(parsed) == result.check_id

    def test_unique_ids(self):
        a = CheckResult()
        b = CheckResult()
        assert a.check_id != b.check_id

    def test_string_check_type_branch(self):
        """to_dict handles check_type as plain string."""
        result = CheckResult(check_type="speed")
        data = result.to_dict()
        assert data["check_type"] == "speed"

    def test_enum_check_type_branch(self):
        result = CheckResult(check_type=CheckType.GEO)
        data = result.to_dict()
        assert data["check_type"] == "geo"

    def test_default_values(self):
        result = CheckResult()
        assert result.node_key == ""
        assert result.success is False
        assert result.latency_ms is None
        assert result.error == ""
        assert result.bytes_downloaded == 0
        assert result.speed_mbps is None
        assert result.speed_test_url == ""
        assert result.speed_test_timeout_sec == 30.0
        assert result.resolved_ip == ""
        assert result.country == ""
        assert result.city == ""
        assert result.openai_unlocked is None
        assert result.openai_status == ""
        assert result.checked_by == ""
        assert result.duration_ms == 0

    def test_to_dict_keys(self):
        """Ensure to_dict returns exactly the expected set of keys."""
        result = CheckResult()
        data = result.to_dict()
        expected_keys = {
            "check_id", "node_key", "check_type", "timestamp",
            "success", "latency_ms", "error", "speed_mbps",
            "country", "city", "openai_unlocked",
        }
        assert set(data.keys()) == expected_keys


# ---- EventLog edge cases ----

class TestEventLog:
    def test_default_event_id_is_uuid(self):
        event = EventLog()
        parsed = uuid.UUID(event.event_id)
        assert str(parsed) == event.event_id

    def test_unique_ids(self):
        a = EventLog()
        b = EventLog()
        assert a.event_id != b.event_id

    def test_string_event_type_branch(self):
        """to_dict handles event_type as plain string."""
        event = EventLog(event_type="custom.event")
        data = event.to_dict()
        assert data["event_type"] == "custom.event"

    def test_enum_event_type_branch(self):
        event = EventLog(event_type=EventType.TASK_FAILED)
        data = event.to_dict()
        assert data["event_type"] == "task.failed"

    def test_string_severity_branch(self):
        event = EventLog(severity="warning")
        data = event.to_dict()
        assert data["severity"] == "warning"

    def test_enum_severity_branch(self):
        event = EventLog(severity=EventSeverity.CRITICAL)
        data = event.to_dict()
        assert data["severity"] == "critical"

    def test_default_values(self):
        event = EventLog()
        assert event.event_type == "node.discovered"
        assert event.severity == "info"
        assert event.node_key == ""
        assert event.backend == ""
        assert event.task_id == ""
        assert event.subscription_id == 0
        assert event.message == ""
        assert event.details == {}
        assert event.source == ""

    def test_to_dict_keys(self):
        event = EventLog()
        data = event.to_dict()
        expected_keys = {
            "event_id", "event_type", "severity", "timestamp",
            "node_key", "backend", "task_id", "message",
            "details", "source",
        }
        assert set(data.keys()) == expected_keys

    def test_details_roundtrip(self):
        details = {"key": "val", "nested": [1, 2, 3]}
        event = EventLog(details=details)
        data = event.to_dict()
        assert data["details"] == details

    def test_all_event_types_have_values(self):
        """Verify all EventType enum members are represented."""
        for member in EventType:
            event = EventLog(event_type=member)
            data = event.to_dict()
            assert "." in data["event_type"]


# ---- Slots enforcement ----

class TestSlots:
    def test_proxy_node_slots(self):
        node = _make_node()
        with pytest.raises(AttributeError):
            node.nonexistent_attribute = True

    def test_check_result_slots(self):
        result = CheckResult()
        with pytest.raises(AttributeError):
            result.nonexistent_attribute = True

    def test_event_log_slots(self):
        event = EventLog()
        with pytest.raises(AttributeError):
            event.nonexistent_attribute = True
