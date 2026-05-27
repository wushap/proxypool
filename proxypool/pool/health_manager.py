"""Health management and circuit breaking for proxy chain nodes."""
from __future__ import annotations

import asyncio
import logging
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from proxypool.pool.node_pool import NodeEntry, NodePool
from proxypool.pool.scoring import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerManager,
    CircuitState,
    NodeScorerManager,
    NodeScore,
    ScoreWeights,
    SlidingWindow,
    WindowManager,
)
from proxypool.storage.health_storage import HealthStorage
from proxypool.storage.sqlite import SQLiteProxyStorage

logger = logging.getLogger(__name__)


def _log_event(level: int, msg: str, **kwargs: Any) -> None:
    """Log a structured event with extra data."""
    extra = {"extra_data": kwargs}
    logger.log(level, msg, extra=extra)


@dataclass
class HealthConfig:
    """Configuration for health management."""
    max_consecutive_failures: int = 5
    probe_interval_sec: int = 60
    probe_timeout_sec: float = 10.0
    egress_check_interval_sec: int = 300
    probe_concurrency: int = 50
    egress_trace_url: str = "https://cloudflare.com/cdn-cgi/trace"
    latency_test_url: str = "https://www.gstatic.com/generate_204"
    # Scoring
    window_max_samples: int = 20
    window_max_age_hours: float = 24.0
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    # Circuit breaker
    circuit_breaker_config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)


class HealthManager:
    """Manages health probing and circuit breaking for node pools."""

    def __init__(
        self,
        storage: SQLiteProxyStorage,
        front_pool: NodePool,
        exit_pool: NodePool,
        config: HealthConfig | None = None,
        build_chain_proxy_url: Callable[[NodeEntry, NodeEntry], str] | None = None,
        probe_chain: Callable[[NodeEntry, NodeEntry], tuple[bool, str, int | None]] | None = None,
        singbox_binary: str = "sing-box",
        health_storage: HealthStorage | None = None,
    ) -> None:
        self.storage = storage
        self.front_pool = front_pool
        self.exit_pool = exit_pool
        self.config = config or HealthConfig()
        self.build_chain_proxy_url = build_chain_proxy_url
        self.probe_chain = probe_chain
        self.singbox_binary = singbox_binary
        self.health_storage = health_storage

        # Scoring and circuit breaking
        self.window_manager = WindowManager(
            max_samples=self.config.window_max_samples,
            max_age_hours=self.config.window_max_age_hours,
        )
        self.scorer_manager = NodeScorerManager(self.config.score_weights)
        self.circuit_breaker_manager = CircuitBreakerManager(self.config.circuit_breaker_config)

        self._running = False
        self._probe_task: threading.Thread | None = None
        self._stop_event = threading.Event()
    
    def start(self) -> None:
        """Start background health probing."""
        if self._running:
            return
        self._restore_state()
        self._running = True
        self._stop_event.clear()
        self._probe_task = threading.Thread(target=self._probe_loop, daemon=True)
        self._probe_task.start()
        logger.info("HealthManager started")

    def _restore_state(self) -> None:
        """Restore health state from storage on startup."""
        if self.health_storage is None:
            return

        try:
            # Restore circuit breaker state
            for cb_data in self.health_storage.get_all_circuit_breakers():
                node_key = cb_data["node_key"]
                state_str = cb_data["state"]
                failure_count = cb_data["failure_count"]
                consecutive_successes = cb_data["consecutive_successes"]

                # Map state string to CircuitState enum
                state_map = {
                    "open": CircuitState.OPEN,
                    "half_open": CircuitState.HALF_OPEN,
                    "closed": CircuitState.CLOSED,
                }
                state = state_map.get(state_str, CircuitState.CLOSED)

                breaker = self.circuit_breaker_manager.get_breaker(node_key)
                breaker.restore_state(
                    state=state,
                    failure_count=failure_count,
                    consecutive_successes=consecutive_successes,
                    last_failure_time=cb_data.get("last_failure_time"),
                    last_success_time=cb_data.get("last_success_time"),
                    open_since=cb_data.get("open_since"),
                    backoff_until=cb_data.get("backoff_until"),
                    current_backoff_sec=cb_data.get("current_backoff_sec"),
                )

            # Restore node scores
            for score_data in self.health_storage.get_all_node_scores():
                node_key = score_data["node_key"]
                score = NodeScore(
                    node_key=node_key,
                    timestamp=time.time(),
                    final_score=score_data["final_score"],
                    grade=score_data["grade"],
                    raw_score=score_data["raw_score"],
                    confidence=score_data["confidence"],
                    success_rate=score_data.get("success_rate"),
                    avg_latency_ms=score_data.get("avg_latency_ms"),
                    stability_score=score_data.get("stability_score", 0.0),
                    availability_score=0.0,
                    latency_score=0.0,
                    purity_score=None,
                    purity_score_normalized=0.0,
                )
                self.scorer_manager.set_score(node_key, score)

            logger.info("Health state restored from storage")
        except Exception as e:
            logger.error(f"Failed to restore health state: {e}")
    
    def stop(self) -> None:
        """Stop background health probing."""
        self._running = False
        self._stop_event.set()
        if self._probe_task:
            self._probe_task.join(timeout=5.0)
        logger.info("HealthManager stopped")
    
    def _probe_loop(self) -> None:
        """Main probe loop running in background thread."""
        while not self._stop_event.is_set():
            try:
                self._probe_all_nodes()
            except Exception as e:
                logger.error(f"Probe loop error: {e}")
            self._stop_event.wait(timeout=self.config.probe_interval_sec)
    
    def _probe_all_nodes(self) -> None:
        """Probe all nodes in both pools."""
        _log_event(logging.INFO, "Starting probe cycle")

        # Probe front nodes directly
        front_nodes = self.front_pool.get_all_nodes()
        self._probe_front_nodes(front_nodes)

        # Probe exit nodes through proxy chain
        exit_nodes = self.exit_pool.get_all_nodes()
        front_healthy = self.front_pool.get_healthy_nodes()
        if front_healthy:
            self._probe_exit_nodes(exit_nodes, front_healthy)

        _log_event(logging.INFO, "Probe cycle completed", front_count=len(front_nodes), exit_count=len(exit_nodes))
    
    def _probe_front_nodes(self, nodes: list[NodeEntry]) -> None:
        """Probe front nodes directly."""
        if not nodes:
            return

        _log_event(logging.DEBUG, "Probing front nodes", count=len(nodes))

        with ThreadPoolExecutor(max_workers=self.config.probe_concurrency) as executor:
            futures = {
                executor.submit(self._probe_single_front, node): node
                for node in nodes
            }
            for future in as_completed(futures):
                node = futures[future]
                try:
                    success, latency = future.result()
                    _log_event(
                        logging.DEBUG,
                        "Front probe result",
                        node_key=node.key,
                        success=success,
                        latency_ms=latency,
                    )
                    self._update_node_health(
                        pool=self.front_pool,
                        node_key=node.key,
                        success=success,
                        latency_ms=latency,
                    )
                except Exception as e:
                    logger.error(f"Front probe error for {node.key}: {e}")
    
    def _probe_single_front(self, node: NodeEntry) -> tuple[bool, int | None]:
        """Probe a single front node using curl."""
        proxy_url = f"{node.protocol}://{node.host}:{node.port}"
        cmd = [
            "curl", "-sS", "-o", "/dev/null", "-w", "%{time_total}",
            "--max-time", str(int(self.config.probe_timeout_sec)),
            "--proxy", proxy_url,
        ]

        # Add proxy authentication if available
        proxy = self.storage.get_proxy_by_key(node.key)
        if proxy:
            extra = proxy.get("extra") or {}
            username = str(extra.get("username") or "").strip()
            password = str(extra.get("password") or "").strip()
            if username and password:
                cmd.extend(["-U", f"{username}:{password}"])

        cmd.append(self.config.latency_test_url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.config.probe_timeout_sec + 2)
            if result.returncode == 0:
                latency_sec = float(result.stdout.strip())
                return True, int(latency_sec * 1000)
            return False, None
        except Exception:
            return False, None
    
    def _probe_exit_nodes(self, exit_nodes: list[NodeEntry], front_nodes: list[NodeEntry]) -> None:
        """Probe exit nodes through proxy chain."""
        if not exit_nodes or not front_nodes:
            return

        # Use first healthy front node for probing
        front = front_nodes[0]

        _log_event(logging.DEBUG, "Probing exit nodes", count=len(exit_nodes), front_node=front.key)

        with ThreadPoolExecutor(max_workers=self.config.probe_concurrency) as executor:
            futures = {
                executor.submit(self._probe_single_exit, front, exit_node): exit_node
                for exit_node in exit_nodes
            }
            for future in as_completed(futures):
                exit_node = futures[future]
                try:
                    success, egress_ip, latency = future.result()
                    _log_event(
                        logging.DEBUG,
                        "Exit probe result",
                        node_key=exit_node.key,
                        success=success,
                        latency_ms=latency,
                        egress_ip=egress_ip,
                    )
                    self._update_node_health(
                        pool=self.exit_pool,
                        node_key=exit_node.key,
                        success=success,
                        latency_ms=latency,
                        egress_ip=egress_ip,
                    )
                except Exception as e:
                    logger.error(f"Exit probe error for {exit_node.key}: {e}")
    
    def _probe_single_exit(self, front: NodeEntry, exit_node: NodeEntry) -> tuple[bool, str, int | None]:
        """Probe exit node through proxy chain."""
        if self.probe_chain is not None:
            return self.probe_chain(front, exit_node)

        # Build chain proxy URL using the callback
        if self.build_chain_proxy_url:
            proxy_url = self.build_chain_proxy_url(front, exit_node)
        else:
            # Fallback: use direct proxy (for testing)
            proxy_url = f"{exit_node.protocol}://{exit_node.host}:{exit_node.port}"
        
        cmd = [
            "curl", "-sS", "-w", "\n%{time_total}",
            "--max-time", str(int(self.config.probe_timeout_sec)),
            "--proxy", proxy_url,
            self.config.egress_trace_url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.config.probe_timeout_sec + 2)
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    body = "\n".join(lines[:-1])
                    latency_sec = float(lines[-1])
                    egress_ip = self._parse_trace_ip(body)
                    return True, egress_ip, int(latency_sec * 1000)
            return False, "", None
        except Exception:
            return False, "", None
    
    def _parse_trace_ip(self, body: str) -> str:
        """Parse IP from cloudflare trace response."""
        for line in body.split("\n"):
            if line.startswith("ip="):
                return line.split("=", 1)[1].strip()
        return ""
    
    def _persist_health(
        self,
        node_key: str,
        success: bool,
        egress_ip: str = "",
        latency_ms: int | None = None,
    ) -> None:
        """Persist health state to storage."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            self.storage.upsert_node_health(
                node_key=node_key,
                success=success,
                egress_ip=egress_ip,
                latency_ms=latency_ms,
                timestamp=now,
                max_failures=self.config.max_consecutive_failures,
            )
        except Exception as e:
            logger.error(f"Failed to persist health for {node_key}: {e}")
    
    def record_request_result(self, front_key: str, exit_key: str, success: bool) -> None:
        """Record the result of a proxy request (passive probing)."""
        front = self.front_pool.get_node(front_key)
        exit_node = self.exit_pool.get_node(exit_key)

        if front:
            self._update_node_health(
                pool=self.front_pool,
                node_key=front_key,
                success=success,
            )

        if exit_node:
            self._update_node_health(
                pool=self.exit_pool,
                node_key=exit_key,
                success=success,
            )

    def _update_node_health(
        self,
        pool: NodePool,
        node_key: str,
        success: bool,
        latency_ms: int | None = None,
        egress_ip: str = "",
    ) -> None:
        """Update node health, sliding window, circuit breaker, and score."""
        # 1. Update sliding window
        error_type = "" if success else "probe_failed"
        self.window_manager.record(node_key, success, latency_ms, error_type)

        # 2. Update circuit breaker
        old_state = self.circuit_breaker_manager.get_state(node_key)
        if success:
            self.circuit_breaker_manager.record_success(node_key)
        else:
            self.circuit_breaker_manager.record_failure(node_key)
        new_state = self.circuit_breaker_manager.get_state(node_key)

        # Log circuit breaker state change
        if old_state != new_state:
            _log_event(
                logging.INFO,
                "Circuit breaker state changed",
                node_key=node_key,
                old_state=old_state.value if hasattr(old_state, 'value') else str(old_state),
                new_state=new_state.value if hasattr(new_state, 'value') else str(new_state),
            )

        # 3. Update node pool (legacy state for backward compat)
        pool.update_node_health(
            node_key,
            success=success,
            egress_ip=egress_ip,
            latency_ms=latency_ms,
            max_failures=self.config.max_consecutive_failures,
        )

        # 4. Update database statistics
        try:
            self.storage.update_check_result(node_key, success)
        except Exception:
            logger.warning("Failed to update check result for %s", node_key, exc_info=True)

        # 4. Update score
        window = self.window_manager.get_window(node_key)
        score = self.scorer_manager.update_score(node_key, window)

        if score is not None:
            _log_event(
                logging.DEBUG,
                "Node score updated",
                node_key=node_key,
                score=round(score.final_score, 4),
                grade=score.grade.value if hasattr(score.grade, 'value') else score.grade,
                success_rate=round(score.success_rate, 4),
            )

        # 5. Update node entry references
        node = pool.get_node(node_key)
        if node is not None:
            node.score = score
            node.circuit_breaker = self.circuit_breaker_manager.get_breaker(node_key)
            # Sync circuit_open from circuit breaker for backward compat
            node.circuit_open = self.circuit_breaker_manager.get_state(node_key) == CircuitState.OPEN

        # 6. Persist to legacy storage
        self._persist_health(node_key, success, egress_ip=egress_ip, latency_ms=latency_ms)

        # 7. Persist to HealthStorage (scoring, circuit breaker, probe records)
        if self.health_storage is not None:
            try:
                # Persist probe record
                self.health_storage.insert_probe_record(
                    node_key=node_key,
                    success=success,
                    latency_ms=latency_ms,
                    probe_type="active",
                    error_type="" if success else "probe_failed",
                    source="health_manager",
                )

                # Persist node score
                if score is not None:
                    self.health_storage.upsert_node_score(
                        node_key=node_key,
                        final_score=score.final_score,
                        grade=score.grade.value if hasattr(score.grade, 'value') else score.grade,
                        raw_score=score.raw_score,
                        confidence=score.confidence,
                        success_rate=score.success_rate,
                        avg_latency_ms=score.avg_latency_ms,
                        stability_score=score.stability_score if hasattr(score, 'stability_score') else None,
                    )

                # Persist circuit breaker state
                breaker = self.circuit_breaker_manager.get_breaker(node_key)
                state = self.circuit_breaker_manager.get_state(node_key)
                self.health_storage.upsert_circuit_breaker(
                    node_key=node_key,
                    state=state.value if hasattr(state, 'value') else state,
                    failure_count=breaker.failure_count,
                    consecutive_successes=breaker._consecutive_successes,
                    last_failure_time=breaker._last_failure_time,
                    last_success_time=breaker._last_success_time,
                    open_since=breaker._open_since,
                    backoff_until=breaker._backoff_until,
                    current_backoff_sec=breaker._current_backoff_sec,
                )

                _log_event(
                    logging.DEBUG,
                    "Health state persisted",
                    node_key=node_key,
                    success=success,
                )
            except Exception as e:
                logger.error(f"Failed to persist health to HealthStorage for {node_key}: {e}")
