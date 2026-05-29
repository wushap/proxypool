"""
Tests for proxypool.storage.connection to increase coverage.
Targets: write_connection rollback, executemany, fetchall no-params,
         commit, rollback convenience methods.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from proxypool.storage.connection import ConnectionManager


@pytest.fixture
def conn_mgr(tmp_path):
    """Yield a ConnectionManager backed by a temp SQLite file."""
    db_path = tmp_path / "test.db"
    mgr = ConnectionManager(db_path)
    mgr.execute(
        "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v TEXT)"
    )
    yield mgr
    mgr.close()


class TestWriteConnectionRollback:
    """Cover the except-rollback path in write_connection (lines 56-58)."""

    def test_exception_triggers_rollback(self, conn_mgr):
        with pytest.raises(ValueError, match="boom"):
            with conn_mgr.write_connection():
                conn_mgr.execute("INSERT INTO t (v) VALUES (?)", ("x",))
                raise ValueError("boom")
        # The insert should have been rolled back
        row = conn_mgr.fetchone("SELECT * FROM t WHERE v = ?", ("x",))
        assert row is None


class TestExecutemany:
    """Cover executemany (lines 88-89)."""

    def test_executemany_insert(self, conn_mgr):
        data = [("a",), ("b",), ("c",)]
        with conn_mgr.write_connection():
            conn_mgr.executemany("INSERT INTO t (v) VALUES (?)", data)
        rows = conn_mgr.fetchall("SELECT * FROM t ORDER BY v")
        assert [r["v"] for r in rows] == ["a", "b", "c"]


class TestFetchallNoParams:
    """Cover fetchall without params (line 103)."""

    def test_fetchall_without_params(self, conn_mgr):
        with conn_mgr.write_connection():
            conn_mgr.execute("INSERT INTO t (v) VALUES (?)", ("row1",))
            conn_mgr.execute("INSERT INTO t (v) VALUES (?)", ("row2",))
        rows = conn_mgr.fetchall("SELECT * FROM t ORDER BY v")
        assert len(rows) == 2


class TestFetchallWithParams:
    """Cover fetchall with params (line 102)."""

    def test_fetchall_with_params(self, conn_mgr):
        with conn_mgr.write_connection():
            conn_mgr.execute("INSERT INTO t (v) VALUES (?)", ("alpha",))
            conn_mgr.execute("INSERT INTO t (v) VALUES (?)", ("beta",))
        rows = conn_mgr.fetchall("SELECT * FROM t WHERE v = ?", ("alpha",))
        assert len(rows) == 1
        assert rows[0]["v"] == "alpha"


class TestCommitConvenience:
    """Cover commit() convenience method (lines 107-108)."""

    def test_commit(self, conn_mgr):
        with conn_mgr.write_connection():
            conn_mgr.execute("INSERT INTO t (v) VALUES (?)", ("committed",))
        conn_mgr.commit()
        row = conn_mgr.fetchone("SELECT * FROM t WHERE v = ?", ("committed",))
        assert row is not None


class TestRollbackConvenience:
    """Cover rollback() convenience method (lines 112-113)."""

    def test_rollback(self, conn_mgr):
        with conn_mgr.write_connection():
            conn_mgr.execute("INSERT INTO t (v) VALUES (?)", ("doomed",))
        conn_mgr.rollback()
        # Data is still committed from write_connection; rollback just
        # resets the transaction state -- the method itself should not raise.
