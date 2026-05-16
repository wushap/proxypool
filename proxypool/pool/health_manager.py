"""Health management and circuit breaking for proxy chain nodes."""
from __future__ import annotations

import asyncio
import logging
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from proxypool.pool.node_pool import NodeEntry, NodePool
from proxypool.storage.sqlite import SQLiteProxyStorage

logger = logging.getLogger(__name__)


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
    ) -> None:
        self.storage = storage
        self.front_pool = front_pool
        self.exit_pool = exit_pool
        self.config = config or HealthConfig()
        self.build_chain_proxy_url = build_chain_proxy_url
        self.probe_chain = probe_chain
        self.singbox_binary = singbox_binary
        
        self._running = False
        self._probe_task: threading.Thread | None = None
        self._stop_event = threading.Event()
    
    def start(self) -> None:
        """Start background health probing."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._probe_task = threading.Thread(target=self._probe_loop, daemon=True)
        self._probe_task.start()
        logger.info("HealthManager started")
    
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
        # Probe front nodes directly
        front_nodes = self.front_pool.get_all_nodes()
        self._probe_front_nodes(front_nodes)
        
        # Probe exit nodes through proxy chain
        exit_nodes = self.exit_pool.get_all_nodes()
        front_healthy = self.front_pool.get_healthy_nodes()
        if front_healthy:
            self._probe_exit_nodes(exit_nodes, front_healthy)
    
    def _probe_front_nodes(self, nodes: list[NodeEntry]) -> None:
        """Probe front nodes directly."""
        if not nodes:
            return
        
        with ThreadPoolExecutor(max_workers=self.config.probe_concurrency) as executor:
            futures = {
                executor.submit(self._probe_single_front, node): node
                for node in nodes
            }
            for future in as_completed(futures):
                node = futures[future]
                try:
                    success, latency = future.result()
                    self.front_pool.update_node_health(
                        node.key,
                        success=success,
                        latency_ms=latency,
                        max_failures=self.config.max_consecutive_failures,
                    )
                    self._persist_health(node.key, success, latency_ms=latency)
                except Exception as e:
                    logger.error(f"Front probe error for {node.key}: {e}")
    
    def _probe_single_front(self, node: NodeEntry) -> tuple[bool, int | None]:
        """Probe a single front node using curl."""
        proxy_url = f"{node.protocol}://{node.host}:{node.port}"
        cmd = [
            "curl", "-sS", "-o", "/dev/null", "-w", "%{time_total}",
            "--max-time", str(int(self.config.probe_timeout_sec)),
            "--proxy", proxy_url,
            self.config.latency_test_url,
        ]
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
        
        with ThreadPoolExecutor(max_workers=self.config.probe_concurrency) as executor:
            futures = {
                executor.submit(self._probe_single_exit, front, exit_node): exit_node
                for exit_node in exit_nodes
            }
            for future in as_completed(futures):
                exit_node = futures[future]
                try:
                    success, egress_ip, latency = future.result()
                    self.exit_pool.update_node_health(
                        exit_node.key,
                        success=success,
                        egress_ip=egress_ip,
                        latency_ms=latency,
                        max_failures=self.config.max_consecutive_failures,
                    )
                    self._persist_health(exit_node.key, success, egress_ip=egress_ip, latency_ms=latency)
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
            self.front_pool.update_node_health(
                front_key,
                success=success,
                max_failures=self.config.max_consecutive_failures,
            )
        
        if exit_node:
            self.exit_pool.update_node_health(
                exit_key,
                success=success,
                max_failures=self.config.max_consecutive_failures,
            )
