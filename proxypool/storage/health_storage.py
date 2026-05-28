"""
Health persistence storage for probe records, scores, and circuit breaker state.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import UTC
from pathlib import Path
from typing import Any


class HealthStorage:
    """Persists health-related data (probe records, scores, circuit breakers)."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._write_lock = threading.RLock()
        self._init_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _init_tables(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS probe_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_key TEXT NOT NULL,
            timestamp REAL NOT NULL,
            probe_type TEXT NOT NULL,
            success INTEGER NOT NULL,
            latency_ms INTEGER,
            error_type TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_probe_records_node ON probe_records(node_key, timestamp DESC);

        CREATE TABLE IF NOT EXISTS node_scores (
            node_key TEXT PRIMARY KEY,
            final_score REAL NOT NULL,
            grade TEXT NOT NULL,
            raw_score REAL NOT NULL,
            confidence REAL NOT NULL,
            success_rate REAL,
            avg_latency_ms INTEGER,
            stability_score REAL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_node_scores_grade ON node_scores(grade, final_score DESC);

        CREATE TABLE IF NOT EXISTS circuit_breaker_state (
            node_key TEXT PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'closed',
            failure_count INTEGER NOT NULL DEFAULT 0,
            consecutive_successes INTEGER NOT NULL DEFAULT 0,
            last_failure_time REAL,
            last_success_time REAL,
            open_since REAL,
            backoff_until REAL,
            current_backoff_sec REAL NOT NULL DEFAULT 30.0,
            updated_at TEXT NOT NULL
        );
        """
        with self._connect() as conn:
            conn.executescript(sql)
            conn.commit()

    # ---- Probe Records ----

    def insert_probe_record(
        self,
        node_key: str,
        success: bool,
        latency_ms: int | None = None,
        probe_type: str = "active",
        error_type: str = "",
        source: str = "",
    ) -> None:
        now = time.time()
        created_at = _utc_now()
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO probe_records
                        (node_key, timestamp, probe_type, success, latency_ms, error_type, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node_key,
                        now,
                        probe_type,
                        1 if success else 0,
                        latency_ms,
                        error_type,
                        source,
                        created_at,
                    ),
                )
                conn.commit()

    def get_probe_records(
        self,
        node_key: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM probe_records
                WHERE node_key = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (node_key, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def cleanup_old_probe_records(self, max_age_hours: float = 720.0) -> int:
        cutoff = time.time() - (max_age_hours * 3600)
        with self._write_lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM probe_records WHERE timestamp < ?",
                (cutoff,),
            )
            conn.commit()
            return cursor.rowcount

    # ---- Node Scores ----

    def upsert_node_score(
        self,
        node_key: str,
        final_score: float,
        grade: str,
        raw_score: float,
        confidence: float,
        success_rate: float | None = None,
        avg_latency_ms: int | None = None,
        stability_score: float | None = None,
    ) -> None:
        now = _utc_now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                """
                    INSERT INTO node_scores
                        (node_key, final_score, grade, raw_score, confidence,
                         success_rate, avg_latency_ms, stability_score, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(node_key) DO UPDATE SET
                        final_score = excluded.final_score,
                        grade = excluded.grade,
                        raw_score = excluded.raw_score,
                        confidence = excluded.confidence,
                        success_rate = excluded.success_rate,
                        avg_latency_ms = excluded.avg_latency_ms,
                        stability_score = excluded.stability_score,
                        updated_at = excluded.updated_at
                    """,
                (
                    node_key,
                    final_score,
                    grade,
                    raw_score,
                    confidence,
                    success_rate,
                    avg_latency_ms,
                    stability_score,
                    now,
                ),
            )
            conn.commit()

    def get_node_score(self, node_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM node_scores WHERE node_key = ?",
                (node_key,),
            ).fetchone()
        return dict(row) if row else None

    def get_all_node_scores(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM node_scores ORDER BY final_score DESC").fetchall()
        return [dict(row) for row in rows]

    def delete_node_score(self, node_key: str) -> int:
        with self._write_lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM node_scores WHERE node_key = ?",
                (node_key,),
            )
            conn.commit()
            return cursor.rowcount

    # ---- Circuit Breaker State ----

    def upsert_circuit_breaker(
        self,
        node_key: str,
        state: str,
        failure_count: int,
        consecutive_successes: int = 0,
        last_failure_time: float | None = None,
        last_success_time: float | None = None,
        open_since: float | None = None,
        backoff_until: float | None = None,
        current_backoff_sec: float = 30.0,
    ) -> None:
        now = _utc_now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                """
                    INSERT INTO circuit_breaker_state
                        (node_key, state, failure_count, consecutive_successes,
                         last_failure_time, last_success_time, open_since,
                         backoff_until, current_backoff_sec, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(node_key) DO UPDATE SET
                        state = excluded.state,
                        failure_count = excluded.failure_count,
                        consecutive_successes = excluded.consecutive_successes,
                        last_failure_time = excluded.last_failure_time,
                        last_success_time = excluded.last_success_time,
                        open_since = excluded.open_since,
                        backoff_until = excluded.backoff_until,
                        current_backoff_sec = excluded.current_backoff_sec,
                        updated_at = excluded.updated_at
                    """,
                (
                    node_key,
                    state,
                    failure_count,
                    consecutive_successes,
                    last_failure_time,
                    last_success_time,
                    open_since,
                    backoff_until,
                    current_backoff_sec,
                    now,
                ),
            )
            conn.commit()

    def get_circuit_breaker(self, node_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM circuit_breaker_state WHERE node_key = ?",
                (node_key,),
            ).fetchone()
        return dict(row) if row else None

    def get_all_circuit_breakers(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM circuit_breaker_state ORDER BY node_key").fetchall()
        return [dict(row) for row in rows]

    def delete_circuit_breaker(self, node_key: str) -> int:
        with self._write_lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM circuit_breaker_state WHERE node_key = ?",
                (node_key,),
            )
            conn.commit()
            return cursor.rowcount


def _utc_now() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()
