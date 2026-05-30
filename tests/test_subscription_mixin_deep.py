"""
Edge-case tests for proxypool.storage.subscription_mixin covering the two
remaining untested lines (94, 274): RuntimeError paths when
last_insert_rowid() SELECT returns no row.
"""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from proxypool.storage.subscription_mixin import SubscriptionMixin


# Reuse the schema and testable subclass from the existing coverage tests.
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS proxies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    raw_link TEXT NOT NULL,
    normalized_key TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT '',
    extra_json TEXT NOT NULL DEFAULT '{}',
    available INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    speed_mbps REAL,
    speed_tested_at TEXT,
    fail_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    total_checks INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    resolved_ip TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    geo_updated_at TEXT,
    ip_purity_score REAL,
    ip_purity_level TEXT NOT NULL DEFAULT '',
    ip_purity_checked_at TEXT,
    openai_unlocked INTEGER,
    openai_status TEXT NOT NULL DEFAULT '',
    openai_checked_at TEXT,
    fallback_front_keys_json TEXT NOT NULL DEFAULT '[]',
    last_checked_at TEXT,
    last_seen_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    update_proxy_key TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    last_status TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    last_parsed INTEGER NOT NULL DEFAULT 0,
    last_inserted INTEGER NOT NULL DEFAULT 0,
    last_updated INTEGER NOT NULL DEFAULT 0,
    last_invalid INTEGER NOT NULL DEFAULT 0,
    last_deduped INTEGER NOT NULL DEFAULT 0,
    last_fetched_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS published_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    filters_json TEXT NOT NULL DEFAULT '{}',
    format TEXT NOT NULL DEFAULT 'raw',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class _TestableSubscriptionMixin(SubscriptionMixin):
    """Concrete subclass providing what SubscriptionMixin expects from its host."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._write_lock = threading.RLock()
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA_SQL)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._db_path,
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def list_proxies_filtered(self, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    def get_subscription_links(self, **kwargs: Any) -> list[str]:
        return []


class _NullAfterInsertConnection:
    """Wrapper around a real connection where the second execute().fetchone() returns None.

    This simulates the impossible case where last_insert_rowid() returns no row,
    triggering the RuntimeError paths in create_subscription / create_published_subscription.
    """

    def __init__(self, real_conn: sqlite3.Connection) -> None:
        self._conn = real_conn
        self._call_count = 0

    def execute(self, sql: str, params: Any = ()) -> Any:
        self._call_count += 1
        result = self._conn.execute(sql, params)
        # After the INSERT (which is the first execute), make the second
        # execute().fetchone() return None.
        if self._call_count == 2:
            result = MagicMock()
            result.fetchone.return_value = None
        return result

    def commit(self) -> None:
        self._conn.commit()

    def executescript(self, script: str) -> Any:
        return self._conn.executescript(script)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> _NullAfterInsertConnection:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class TestCreateSubscriptionRuntimeError(unittest.TestCase):
    """Line 94: raise RuntimeError('failed to create subscription')"""

    def test_create_subscription_raises_when_row_is_none(self) -> None:
        """Simulate last_insert_rowid() returning no row."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "db.sqlite3"
            storage = _TestableSubscriptionMixin(db_path)
            real_conn = storage._connect()
            null_conn = _NullAfterInsertConnection(real_conn)

            with patch.object(storage, "_connect", return_value=null_conn):
                with self.assertRaises(RuntimeError) as ctx:
                    storage.create_subscription(name="boom", url="https://example.com/fail")
                self.assertIn("failed to create subscription", str(ctx.exception))


class TestCreatePublishedSubscriptionRuntimeError(unittest.TestCase):
    """Line 274: raise RuntimeError('failed to create published subscription')"""

    def test_create_published_subscription_raises_when_row_is_none(self) -> None:
        """Simulate last_insert_rowid() returning no row."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "db.sqlite3"
            storage = _TestableSubscriptionMixin(db_path)
            real_conn = storage._connect()
            null_conn = _NullAfterInsertConnection(real_conn)

            with patch.object(storage, "_connect", return_value=null_conn):
                with self.assertRaises(RuntimeError) as ctx:
                    storage.create_published_subscription(name="boom-pub")
                self.assertIn("failed to create published subscription", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
