"""Tests for proxypool.storage.pool_mixin — pool CRUD coverage."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from proxypool.storage.pool_mixin import PoolMixin


# ---------------------------------------------------------------------------
# Minimal harness that gives PoolMixin the infrastructure it requires
# ---------------------------------------------------------------------------

_POOL_SCHEMA = """\
CREATE TABLE IF NOT EXISTS proxy_pools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    published_subscription_id INTEGER,
    filters_json TEXT NOT NULL DEFAULT '{}',
    listen TEXT NOT NULL DEFAULT '0.0.0.0',
    inbound_type TEXT NOT NULL DEFAULT 'http',
    chain_enabled INTEGER NOT NULL DEFAULT 0,
    sticky_ttl_sec INTEGER NOT NULL DEFAULT 3600,
    session_missing_action TEXT NOT NULL DEFAULT 'RANDOM',
    session_header_names_json TEXT NOT NULL DEFAULT '[]',
    session_query_param_names_json TEXT NOT NULL DEFAULT '[]',
    gateway_path_prefix TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'stopped',
    last_synced_at TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_proxy_pools_status ON proxy_pools(status);

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

CREATE TABLE IF NOT EXISTS proxy_pools_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    pool_type TEXT NOT NULL CHECK(pool_type IN ('front', 'exit')),
    regex_filters_json TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class _PoolMixinHarness(PoolMixin):
    """Concrete subclass that wires PoolMixin to a real SQLite DB."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._write_lock = threading.RLock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.executescript(_POOL_SCHEMA)
        conn.close()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()

    # --- proxy list helper (minimal stub) ---

    def list_proxies_filtered(
        self, *, limit: int = 100, exclude_keys: set[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM proxies LIMIT ?", (limit,)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            if exclude_keys and d.get("normalized_key") in exclude_keys:
                continue
            result.append(d)
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make(tmp_path: Path) -> _PoolMixinHarness:
    return _PoolMixinHarness(tmp_path / "pool_mixin_test.db")


# ---------------------------------------------------------------------------
# Pool CRUD tests
# ---------------------------------------------------------------------------


def test_create_proxy_pool_defaults(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="my-pool")
    assert pool["name"] == "my-pool"
    assert pool["status"] == "stopped"
    assert pool["filters"] == {}
    assert pool["listen"] == "0.0.0.0"
    assert pool["inbound_type"] == "http"
    assert pool["chain_enabled"] is False
    assert pool["sticky_ttl_sec"] == 3600
    assert pool["session_missing_action"] == "RANDOM"
    assert pool["session_header_names"] == []
    assert pool["session_query_param_names"] == []
    assert pool["gateway_path_prefix"] == ""
    assert "match_count" in pool


def test_create_proxy_pool_all_options(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(
        name="custom-pool",
        filters={"protocol": "trojan", "available": "true", "geo_countries": ["US", "JP"]},
        listen="127.0.0.1:18800",
        inbound_type="socks5",
        chain_enabled=True,
        sticky_ttl_sec=7200,
        session_missing_action="REJECT",
        session_header_names=["X-Session"],
        session_query_param_names=["sid"],
        gateway_path_prefix="/gw/pool1",
    )
    assert pool["name"] == "custom-pool"
    assert pool["listen"] == "127.0.0.1:18800"
    assert pool["inbound_type"] == "socks5"
    assert pool["chain_enabled"] is True
    assert pool["sticky_ttl_sec"] == 7200
    assert pool["session_missing_action"] == "REJECT"
    assert pool["session_header_names"] == ["X-Session"]
    assert pool["session_query_param_names"] == ["sid"]
    assert pool["gateway_path_prefix"] == "/gw/pool1"
    assert pool["filters"]["protocol"] == "trojan"


def test_create_proxy_pool_empty_name_fallback(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="")
    assert pool["name"] == "proxy-pool"


def test_create_proxy_pool_sticky_ttl_floor(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="ttl-floor", sticky_ttl_sec=0)
    assert pool["sticky_ttl_sec"] == 1


def test_get_proxy_pool(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="get-me")
    loaded = store.get_proxy_pool(pool["id"])
    assert loaded is not None
    assert loaded["name"] == "get-me"
    assert loaded["id"] == pool["id"]


def test_get_proxy_pool_not_found(tmp_path: Path) -> None:
    store = _make(tmp_path)
    assert store.get_proxy_pool(9999) is None


def test_update_proxy_pool_name_and_filters(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="old")
    updated = store.update_proxy_pool(pool["id"], name="new", filters={"geo_country": "DE"})
    assert updated["name"] == "new"
    assert updated["filters"]["geo_country"] == "DE"


def test_update_proxy_pool_no_changes_returns_current(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="no-change")
    result = store.update_proxy_pool(pool["id"])
    assert result["name"] == "no-change"


def test_update_proxy_pool_not_found(tmp_path: Path) -> None:
    store = _make(tmp_path)
    try:
        store.update_proxy_pool(9999, name="x")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_update_proxy_pool_published_subscription_id(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="sub-linked")
    updated = store.update_proxy_pool(pool["id"], published_subscription_id=42)
    assert updated["published_subscription_id"] == 42


def test_update_proxy_pool_listeners_and_chain(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="chain-pool")
    updated = store.update_proxy_pool(
        pool["id"],
        listen="0.0.0.0:9090",
        inbound_type="http",
        chain_enabled=True,
        sticky_ttl_sec=1800,
        session_missing_action="REJECT",
        session_header_names=["H1"],
        session_query_param_names=["q1"],
        gateway_path_prefix="/api",
    )
    assert updated["listen"] == "0.0.0.0:9090"
    assert updated["chain_enabled"] is True
    assert updated["sticky_ttl_sec"] == 1800
    assert updated["session_missing_action"] == "REJECT"
    assert updated["session_header_names"] == ["H1"]
    assert updated["session_query_param_names"] == ["q1"]
    assert updated["gateway_path_prefix"] == "/api"


def test_delete_proxy_pool(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="delete-me")
    deleted = store.delete_proxy_pool(pool["id"])
    assert deleted == 1
    assert store.get_proxy_pool(pool["id"]) is None


def test_delete_proxy_pool_nonexistent(tmp_path: Path) -> None:
    store = _make(tmp_path)
    deleted = store.delete_proxy_pool(9999)
    assert deleted == 0


def test_list_proxy_pools(tmp_path: Path) -> None:
    store = _make(tmp_path)
    store.create_proxy_pool(name="p1")
    store.create_proxy_pool(name="p2")
    pools = store.list_proxy_pools()
    assert len(pools) == 2
    names = {p["name"] for p in pools}
    assert names == {"p1", "p2"}


def test_list_proxy_pools_limit(tmp_path: Path) -> None:
    store = _make(tmp_path)
    for i in range(5):
        store.create_proxy_pool(name=f"pool-{i}")
    pools = store.list_proxy_pools(limit=2)
    assert len(pools) == 2


def test_get_proxy_pool_by_gateway_prefix(tmp_path: Path) -> None:
    store = _make(tmp_path)
    store.create_proxy_pool(name="gw-pool", gateway_path_prefix="/my-gateway")
    found = store.get_proxy_pool_by_gateway_prefix("/my-gateway")
    assert found is not None
    assert found["name"] == "gw-pool"


def test_get_proxy_pool_by_gateway_prefix_empty(tmp_path: Path) -> None:
    store = _make(tmp_path)
    assert store.get_proxy_pool_by_gateway_prefix("") is None
    assert store.get_proxy_pool_by_gateway_prefix("   ") is None


def test_get_proxy_pool_by_gateway_prefix_not_found(tmp_path: Path) -> None:
    store = _make(tmp_path)
    assert store.get_proxy_pool_by_gateway_prefix("/nope") is None


def test_update_proxy_pool_status(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="status-pool")
    store.update_proxy_pool_status(pool["id"], "running", last_synced_at="2026-01-01T00:00:00")
    loaded = store.get_proxy_pool(pool["id"])
    assert loaded["status"] == "running"
    assert loaded["last_synced_at"] == "2026-01-01T00:00:00"


def test_update_proxy_pool_status_without_synced_at(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="no-sync")
    store.update_proxy_pool_status(pool["id"], "stopped", last_error="boom")
    loaded = store.get_proxy_pool(pool["id"])
    assert loaded["status"] == "stopped"
    assert loaded["last_error"] == "boom"
    assert loaded["last_synced_at"] is None


def test_list_proxy_pool_candidates(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="cand")
    candidates = store.list_proxy_pool_candidates(pool["id"])
    assert isinstance(candidates, list)


def test_list_proxy_pool_candidates_not_found(tmp_path: Path) -> None:
    store = _make(tmp_path)
    try:
        store.list_proxy_pool_candidates(9999)
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# V2 pool tests
# ---------------------------------------------------------------------------


def test_upsert_proxy_pool_v2_create(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.upsert_proxy_pool_v2("front-a", "front", ["regex1", "regex2"])
    assert pool["name"] == "front-a"
    assert pool["pool_type"] == "front"
    assert pool["regex_filters"] == ["regex1", "regex2"]
    assert pool["enabled"] is True


def test_upsert_proxy_pool_v2_update(tmp_path: Path) -> None:
    store = _make(tmp_path)
    store.upsert_proxy_pool_v2("exit-x", "exit", ["old"])
    updated = store.upsert_proxy_pool_v2("exit-x", "exit", ["new-a", "new-b"])
    assert updated["regex_filters"] == ["new-a", "new-b"]


def test_get_proxy_pool_v2(tmp_path: Path) -> None:
    store = _make(tmp_path)
    store.upsert_proxy_pool_v2("f1", "front", [])
    pool = store.get_proxy_pool_v2("f1")
    assert pool is not None
    assert pool["name"] == "f1"


def test_get_proxy_pool_v2_not_found(tmp_path: Path) -> None:
    store = _make(tmp_path)
    assert store.get_proxy_pool_v2("missing") is None


def test_list_proxy_pools_v2(tmp_path: Path) -> None:
    store = _make(tmp_path)
    store.upsert_proxy_pool_v2("b-pool", "front", [])
    store.upsert_proxy_pool_v2("a-pool", "exit", [])
    pools = store.list_proxy_pools_v2()
    assert len(pools) == 2
    assert pools[0]["name"] == "a-pool"  # sorted by name
    assert pools[1]["name"] == "b-pool"


def test_delete_proxy_pool_v2(tmp_path: Path) -> None:
    store = _make(tmp_path)
    store.upsert_proxy_pool_v2("del-me", "front", [])
    deleted = store.delete_proxy_pool_v2("del-me")
    assert deleted == 1
    assert store.get_proxy_pool_v2("del-me") is None


def test_delete_proxy_pool_v2_nonexistent(tmp_path: Path) -> None:
    store = _make(tmp_path)
    assert store.delete_proxy_pool_v2("nope") == 0


def test_upsert_proxy_pool_v2_disabled(tmp_path: Path) -> None:
    store = _make(tmp_path)
    pool = store.upsert_proxy_pool_v2("dis", "front", [], enabled=False)
    assert pool["enabled"] is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_pool_row_to_dict_resilient(tmp_path: Path) -> None:
    """Ensure _pool_row_to_dict handles missing / corrupt JSON gracefully."""
    store = _make(tmp_path)
    # Manually insert a row with bad JSON to test resilience
    with store._connect() as conn:
        conn.execute(
            """INSERT INTO proxy_pools
               (name, filters_json, listen, inbound_type, chain_enabled,
                sticky_ttl_sec, session_missing_action,
                session_header_names_json, session_query_param_names_json,
                gateway_path_prefix, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'stopped', '', '')""",
            ("bad-json", "NOT_JSON{", "0.0.0.0", "http", 0,
             3600, "RANDOM", "BAD[", "NOT{", "",),
        )
        conn.commit()
    # Should not raise
    pools = store.list_proxy_pools()
    assert len(pools) == 1
    assert pools[0]["filters"] == {}


def test_create_pool_publishes_subscription_id(tmp_path: Path) -> None:
    """Verify published_subscription_id is not exposed in row_to_dict."""
    store = _make(tmp_path)
    pool = store.create_proxy_pool(name="sub-pool")
    assert "resin_subscription_id" not in pool
    assert "resin_platform_id" not in pool
