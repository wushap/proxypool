from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha1
from typing import Any


class ProxyProtocol(str, Enum):
    """代理协议枚举"""

    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"
    SHADOWSOCKS = "shadowsocks"
    VMESS = "vmess"
    VLESS = "vless"
    TROJAN = "trojan"
    HYSTERIA = "hysteria"
    HYSTERIA2 = "hysteria2"
    TUIC = "tuic"
    WIREGUARD = "wireguard"


class NodeStatus(str, Enum):
    """节点状态枚举"""

    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    CIRCUIT_OPEN = "circuit_open"


@dataclass(slots=True)
class ProxyNode:
    """代理节点核心数据模型"""

    # 基础信息
    protocol: str
    host: str
    port: int
    raw_link: str
    name: str = ""
    source: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    # 状态信息
    status: str = NodeStatus.UNKNOWN
    available: bool = False

    # 性能指标
    latency_ms: int | None = None
    speed_mbps: float | None = None
    speed_tested_at: datetime | None = None

    # 健康信息
    fail_count: int = 0
    last_error: str = ""
    last_checked_at: datetime | None = None
    last_seen_at: datetime = field(default_factory=datetime.utcnow)

    # 地理位置
    resolved_ip: str = ""
    country: str = ""
    city: str = ""
    geo_updated_at: datetime | None = None

    # 评分信息
    score: float = 0.0
    score_updated_at: datetime | None = None

    # IP 纯净度
    ip_purity_score: float | None = None
    ip_purity_level: str = ""
    ip_purity_checked_at: datetime | None = None

    # 服务解锁状态
    openai_unlocked: bool | None = None
    openai_status: str = ""
    openai_checked_at: datetime | None = None

    # 链式代理
    fallback_front_keys: list[str] = field(default_factory=list)

    # 元数据
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def normalized_key(self) -> str:
        """生成节点唯一标识"""
        identity = (
            self.extra.get("uuid") or self.extra.get("password") or self.extra.get("username") or ""
        )
        base = f"{self.protocol}|{self.host}|{self.port}|{identity}"
        return sha1(base.encode("utf-8")).hexdigest()

    def is_healthy(self) -> bool:
        """判断节点是否健康"""
        return self.status in (NodeStatus.AVAILABLE, NodeStatus.DEGRADED)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "normalized_key": self.normalized_key(),
            "protocol": self.protocol,
            "host": self.host,
            "port": self.port,
            "name": self.name,
            "source": self.source,
            "extra": self.extra,
            "status": self.status if isinstance(self.status, str) else self.status.value,
            "available": self.available,
            "latency_ms": self.latency_ms,
            "speed_mbps": self.speed_mbps,
            "fail_count": self.fail_count,
            "last_error": self.last_error,
            "resolved_ip": self.resolved_ip,
            "country": self.country,
            "city": self.city,
            "score": self.score,
            "ip_purity_score": self.ip_purity_score,
            "ip_purity_level": self.ip_purity_level,
            "openai_unlocked": self.openai_unlocked,
            "openai_status": self.openai_status,
            "openai_checked_at": self.openai_checked_at.isoformat()
            if self.openai_checked_at
            else None,
            "fallback_front_keys": self.fallback_front_keys,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "last_seen_at": self.last_seen_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# Note: ScoreWeights and NodeScore are defined in proxypool.pool.scoring
# Import from there if needed: from proxypool.pool.scoring import ScoreWeights, NodeScore


# ---- 检查结果模型 ----


class CheckType(str, Enum):
    """检查类型"""

    ACTIVE = "active"
    PASSIVE = "passive"
    SPEED = "speed"
    GEO = "geo"
    PURITY = "purity"
    OPENAI = "openai"


@dataclass(slots=True)
class CheckResult:
    """检查结果"""

    check_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_key: str = ""
    check_type: str = CheckType.ACTIVE
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # 结果
    success: bool = False
    latency_ms: int | None = None
    error: str = ""

    # 速度测试特有
    bytes_downloaded: int = 0
    speed_mbps: float | None = None
    speed_test_url: str = ""
    speed_test_timeout_sec: float = 30.0

    # 地理位置特有
    resolved_ip: str = ""
    country: str = ""
    city: str = ""

    # OpenAI 特有
    openai_unlocked: bool | None = None
    openai_status: str = ""

    # 元数据
    checked_by: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "node_key": self.node_key,
            "check_type": self.check_type
            if isinstance(self.check_type, str)
            else self.check_type.value,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "speed_mbps": self.speed_mbps,
            "country": self.country,
            "city": self.city,
            "openai_unlocked": self.openai_unlocked,
        }


# ---- 事件日志模型 ----


class EventType(str, Enum):
    """事件类型"""

    NODE_DISCOVERED = "node.discovered"
    NODE_AVAILABLE = "node.available"
    NODE_UNAVAILABLE = "node.unavailable"
    NODE_DELETED = "node.deleted"
    HEALTH_CHECK_SUCCESS = "health.check.success"
    HEALTH_CHECK_FAILURE = "health.check.failure"
    CIRCUIT_OPENED = "health.circuit.opened"
    CIRCUIT_CLOSED = "health.circuit.closed"
    BACKEND_STARTED = "backend.started"
    BACKEND_STOPPED = "backend.stopped"
    BACKEND_ERROR = "backend.error"
    SUBSCRIPTION_FETCHED = "subscription.fetched"
    SUBSCRIPTION_FAILED = "subscription.failed"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"


class EventSeverity(str, Enum):
    """事件严重程度"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(slots=True)
class EventLog:
    """事件日志"""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = EventType.NODE_DISCOVERED
    severity: str = EventSeverity.INFO
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # 关联对象
    node_key: str = ""
    backend: str = ""
    task_id: str = ""
    subscription_id: int = 0

    # 事件内容
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    # 来源
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type
            if isinstance(self.event_type, str)
            else self.event_type.value,
            "severity": self.severity if isinstance(self.severity, str) else self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "node_key": self.node_key,
            "backend": self.backend,
            "task_id": self.task_id,
            "message": self.message,
            "details": self.details,
            "source": self.source,
        }
