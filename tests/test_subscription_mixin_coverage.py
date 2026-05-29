"""
Tests for proxypool.storage.subscription_mixin.SubscriptionMixin to increase coverage.
"""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

import sqlite3

from proxypool.storage.subscription_mixin import SubscriptionMixin


# Minimal schema required by SubscriptionMixin methods.
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
        """Minimal stub for list_proxies_filtered used by _published_subscription_row_to_dict."""
        return []

    def get_subscription_links(self, **kwargs: Any) -> list[str]:
        """Minimal stub for get_subscription_links used by get_published_subscription_links."""
        return []


class TestSubscriptionMixinGet(unittest.TestCase):
    def test_get_subscription_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="test-sub", url="https://example.com/sub1")
            row = storage.get_subscription(sub["id"])
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "test-sub")
            self.assertEqual(row["url"], "https://example.com/sub1")
            self.assertTrue(row["enabled"])

    def test_get_subscription_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            row = storage.get_subscription(9999)
            self.assertIsNone(row)

    def test_get_subscription_by_url_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            storage.create_subscription(name="sub", url="https://example.com/feed")
            row = storage.get_subscription_by_url("https://example.com/feed")
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "sub")

    def test_get_subscription_by_url_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            row = storage.get_subscription_by_url("https://nonexistent.com")
            self.assertIsNone(row)

    def test_get_subscription_by_url_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            self.assertIsNone(storage.get_subscription_by_url(""))
            self.assertIsNone(storage.get_subscription_by_url(None))  # type: ignore[arg-type]


class TestSubscriptionMixinCreate(unittest.TestCase):
    def test_create_subscription_basic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="my-sub", url="https://example.com/s1")
            self.assertEqual(sub["name"], "my-sub")
            self.assertEqual(sub["url"], "https://example.com/s1")
            self.assertTrue(sub["enabled"])
            self.assertEqual(sub["update_proxy_key"], "")

    def test_create_subscription_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(
                name="disabled", url="https://example.com/s2", enabled=False
            )
            self.assertFalse(sub["enabled"])

    def test_create_subscription_empty_url_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            with self.assertRaises(ValueError):
                storage.create_subscription(name="bad", url="")

    def test_create_subscription_whitespace_url_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            with self.assertRaises(ValueError):
                storage.create_subscription(name="bad", url="   ")

    def test_create_subscription_empty_name_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="", url="https://example.com/s3")
            self.assertEqual(sub["name"], "subscription")

    def test_create_subscription_with_proxy_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(
                name="keyed", url="https://example.com/s4", update_proxy_key="my-key"
            )
            self.assertEqual(sub["update_proxy_key"], "my-key")


class TestSubscriptionMixinUpdate(unittest.TestCase):
    def test_update_subscription_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="old", url="https://example.com/u1")
            updated = storage.update_subscription(sub["id"], name="new")
            self.assertEqual(updated["name"], "new")

    def test_update_subscription_url(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="sub", url="https://example.com/u2")
            updated = storage.update_subscription(sub["id"], url="https://example.com/u2-new")
            self.assertEqual(updated["url"], "https://example.com/u2-new")

    def test_update_subscription_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="sub", url="https://example.com/u3")
            updated = storage.update_subscription(sub["id"], enabled=False)
            self.assertFalse(updated["enabled"])

    def test_update_subscription_proxy_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="sub", url="https://example.com/u4")
            updated = storage.update_subscription(sub["id"], update_proxy_key="new-key")
            self.assertEqual(updated["update_proxy_key"], "new-key")

    def test_update_subscription_empty_url_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="sub", url="https://example.com/u5")
            with self.assertRaises(ValueError):
                storage.update_subscription(sub["id"], url="")

    def test_update_subscription_not_found_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            with self.assertRaises(ValueError):
                storage.update_subscription(9999, name="nope")

    def test_update_subscription_empty_name_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="old", url="https://example.com/u6")
            updated = storage.update_subscription(sub["id"], name="")
            self.assertEqual(updated["name"], "subscription")


class TestSubscriptionMixinDelete(unittest.TestCase):
    def test_delete_subscription_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="del", url="https://example.com/d1")
            count = storage.delete_subscription(sub["id"])
            self.assertEqual(count, 1)
            self.assertIsNone(storage.get_subscription(sub["id"]))

    def test_delete_subscription_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            count = storage.delete_subscription(9999)
            self.assertEqual(count, 0)


class TestSubscriptionMixinList(unittest.TestCase):
    def test_list_subscriptions_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            subs = storage.list_subscriptions()
            self.assertEqual(subs, [])

    def test_list_subscriptions_multiple(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            storage.create_subscription(name="a", url="https://example.com/l1")
            storage.create_subscription(name="b", url="https://example.com/l2")
            subs = storage.list_subscriptions()
            self.assertEqual(len(subs), 2)

    def test_list_subscriptions_limit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            for i in range(5):
                storage.create_subscription(name=f"s{i}", url=f"https://example.com/lim{i}")
            subs = storage.list_subscriptions(limit=2)
            self.assertEqual(len(subs), 2)

    def test_list_enabled_subscriptions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            storage.create_subscription(name="enabled", url="https://example.com/e1", enabled=True)
            storage.create_subscription(name="disabled", url="https://example.com/e2", enabled=False)
            enabled = storage.list_enabled_subscriptions()
            self.assertEqual(len(enabled), 1)
            self.assertEqual(enabled[0]["name"], "enabled")


class TestSubscriptionMixinMarkResult(unittest.TestCase):
    def test_mark_subscription_result(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="mk", url="https://example.com/m1")
            storage.mark_subscription_result(
                sub["id"], status="ok", parsed=10, inserted=5, updated=2, invalid=1, deduped=2
            )
            row = storage.get_subscription(sub["id"])
            self.assertEqual(row["last_status"], "ok")
            self.assertEqual(row["last_parsed"], 10)
            self.assertEqual(row["last_inserted"], 5)
            self.assertEqual(row["last_updated"], 2)
            self.assertEqual(row["last_invalid"], 1)
            self.assertEqual(row["last_deduped"], 2)

    def test_mark_subscription_result_with_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="err", url="https://example.com/m2")
            storage.mark_subscription_result(sub["id"], status="failed", error="timeout")
            row = storage.get_subscription(sub["id"])
            self.assertEqual(row["last_status"], "failed")
            self.assertEqual(row["last_error"], "timeout")

    def test_mark_subscription_result_negative_clamped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="neg", url="https://example.com/m3")
            storage.mark_subscription_result(sub["id"], status="ok", parsed=-1, inserted=-5)
            row = storage.get_subscription(sub["id"])
            self.assertEqual(row["last_parsed"], 0)
            self.assertEqual(row["last_inserted"], 0)


class TestSubscriptionMixinDeleteUnavailable(unittest.TestCase):
    def test_delete_unavailable_subscriptions_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub1 = storage.create_subscription(name="s1", url="https://example.com/du1")
            sub2 = storage.create_subscription(name="s2", url="https://example.com/du2")
            storage.mark_subscription_result(sub1["id"], status="failed")
            storage.mark_subscription_result(sub2["id"], status="ok")
            deleted = storage.delete_unavailable_subscriptions()
            self.assertEqual(deleted, 1)
            self.assertIsNone(storage.get_subscription(sub1["id"]))
            self.assertIsNotNone(storage.get_subscription(sub2["id"]))

    def test_delete_unavailable_subscriptions_include_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub1 = storage.create_subscription(name="s1", url="https://example.com/du3", enabled=False)
            sub2 = storage.create_subscription(name="s2", url="https://example.com/du4", enabled=True)
            deleted = storage.delete_unavailable_subscriptions(include_disabled=True)
            self.assertEqual(deleted, 1)
            self.assertIsNone(storage.get_subscription(sub1["id"]))
            self.assertIsNotNone(storage.get_subscription(sub2["id"]))


class TestSubscriptionMixinPublished(unittest.TestCase):
    def test_create_published_subscription(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="pub1", format="clash")
            self.assertEqual(ps["name"], "pub1")
            self.assertEqual(ps["format"], "clash")
            self.assertTrue(ps["enabled"])
            self.assertIn("filters", ps)

    def test_create_published_subscription_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="pub2")
            self.assertEqual(ps["format"], "raw")
            self.assertEqual(ps["filters"], {})

    def test_create_published_subscription_empty_name_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="")
            self.assertEqual(ps["name"], "published-subscription")

    def test_get_published_subscription(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="pub3")
            row = storage.get_published_subscription(ps["id"])
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "pub3")

    def test_get_published_subscription_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            self.assertIsNone(storage.get_published_subscription(9999))

    def test_list_published_subscriptions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            storage.create_published_subscription(name="p1")
            storage.create_published_subscription(name="p2")
            rows = storage.list_published_subscriptions()
            self.assertEqual(len(rows), 2)

    def test_list_published_subscriptions_limit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            for i in range(5):
                storage.create_published_subscription(name=f"p{i}")
            rows = storage.list_published_subscriptions(limit=2)
            self.assertEqual(len(rows), 2)

    def test_update_published_subscription_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="old")
            updated = storage.update_published_subscription(ps["id"], name="new")
            self.assertEqual(updated["name"], "new")

    def test_update_published_subscription_filters(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="f")
            updated = storage.update_published_subscription(
                ps["id"], filters={"protocol": "ss", "available": "true"}
            )
            self.assertEqual(updated["filters"]["protocol"], "ss")

    def test_update_published_subscription_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="e")
            updated = storage.update_published_subscription(ps["id"], enabled=False)
            self.assertFalse(updated["enabled"])

    def test_update_published_subscription_format(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="fmt", format="raw")
            updated = storage.update_published_subscription(ps["id"], format="clash")
            self.assertEqual(updated["format"], "clash")

    def test_update_published_subscription_not_found_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            with self.assertRaises(ValueError):
                storage.update_published_subscription(9999, name="x")

    def test_update_published_subscription_empty_name_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="old")
            updated = storage.update_published_subscription(ps["id"], name="")
            self.assertEqual(updated["name"], "published-subscription")

    def test_delete_published_subscription(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="del")
            count = storage.delete_published_subscription(ps["id"])
            self.assertEqual(count, 1)
            self.assertIsNone(storage.get_published_subscription(ps["id"]))

    def test_delete_published_subscription_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            count = storage.delete_published_subscription(9999)
            self.assertEqual(count, 0)

    def test_get_published_subscription_links_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            with self.assertRaises(ValueError):
                storage.get_published_subscription_links(9999)

    def test_get_published_subscription_links_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(
                name="links", filters={"protocol": "ss"}
            )
            links = storage.get_published_subscription_links(ps["id"])
            self.assertIsInstance(links, list)

    def test_get_published_subscription_proxies_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            with self.assertRaises(ValueError):
                storage.get_published_subscription_proxies(9999)

    def test_get_published_subscription_proxies_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(
                name="proxies", filters={"available": "true"}
            )
            proxies = storage.get_published_subscription_proxies(ps["id"])
            self.assertIsInstance(proxies, list)

    def test_published_subscription_row_to_dict_invalid_filters_json(self) -> None:
        """Published sub with invalid filters_json should get empty filters dict."""
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            ps = storage.create_published_subscription(name="bad", filters={"protocol": "ss"})
            # Corrupt the filters_json directly
            with storage._connect() as conn:
                conn.execute(
                    "UPDATE published_subscriptions SET filters_json = 'not-json' WHERE id = ?",
                    (ps["id"],),
                )
                conn.commit()
            row = storage.get_published_subscription(ps["id"])
            self.assertIsNotNone(row)
            self.assertEqual(row["filters"], {})


class TestSubscriptionMixinRowToDict(unittest.TestCase):
    def test_subscription_row_to_dict_enabled_true(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="t", url="https://example.com/r1", enabled=True)
            row = storage.get_subscription(sub["id"])
            self.assertTrue(row["enabled"])

    def test_subscription_row_to_dict_enabled_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = _TestableSubscriptionMixin(Path(td) / "db.sqlite3")
            sub = storage.create_subscription(name="f", url="https://example.com/r2", enabled=False)
            row = storage.get_subscription(sub["id"])
            self.assertFalse(row["enabled"])


if __name__ == "__main__":
    unittest.main()
