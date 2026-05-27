"""
Tests for ConnectionManager.
"""
from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest

from proxypool.storage.connection import ConnectionManager


class TestConnectionManager:
    """Test ConnectionManager."""

    def test_create_connection_manager(self):
        """Test creating ConnectionManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn_mgr = ConnectionManager(db_path)
            assert conn_mgr.db_path == db_path
            conn_mgr.close()

    def test_execute_sql(self):
        """Test executing SQL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn_mgr = ConnectionManager(db_path)

            # Create table
            conn_mgr.execute("""
                CREATE TABLE IF NOT EXISTS test (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)

            # Insert data
            with conn_mgr.write_connection():
                conn_mgr.execute("INSERT INTO test (name) VALUES (?)", ("hello",))
                conn_mgr.execute("INSERT INTO test (name) VALUES (?)", ("world",))

            # Query data
            with conn_mgr.read_connection():
                rows = conn_mgr.fetchall("SELECT * FROM test")
                assert len(rows) == 2
                assert rows[0]["name"] == "hello"
                assert rows[1]["name"] == "world"

            conn_mgr.close()

    def test_transaction_commit(self):
        """Test transaction commit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn_mgr = ConnectionManager(db_path)

            conn_mgr.execute("""
                CREATE TABLE IF NOT EXISTS test (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)

            # Commit transaction
            with conn_mgr.transaction():
                conn_mgr.execute("INSERT INTO test (name) VALUES (?)", ("committed",))

            # Verify commit
            with conn_mgr.read_connection():
                row = conn_mgr.fetchone("SELECT * FROM test WHERE name = ?", ("committed",))
                assert row is not None

            conn_mgr.close()

    def test_transaction_rollback(self):
        """Test transaction rollback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn_mgr = ConnectionManager(db_path)

            conn_mgr.execute("""
                CREATE TABLE IF NOT EXISTS test (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)

            # Try to rollback
            try:
                with conn_mgr.transaction():
                    conn_mgr.execute("INSERT INTO test (name) VALUES (?)", ("rollback",))
                    raise ValueError("Force rollback")
            except ValueError:
                pass

            # Verify rollback
            with conn_mgr.read_connection():
                row = conn_mgr.fetchone("SELECT * FROM test WHERE name = ?", ("rollback",))
                assert row is None

            conn_mgr.close()

    def test_thread_safety(self):
        """Test thread safety."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn_mgr = ConnectionManager(db_path)

            conn_mgr.execute("""
                CREATE TABLE IF NOT EXISTS test (
                    id INTEGER PRIMARY KEY,
                    thread_id INTEGER NOT NULL
                )
            """)

            def insert_records(thread_id: int):
                for _ in range(10):
                    with conn_mgr.write_connection():
                        conn_mgr.execute(
                            "INSERT INTO test (thread_id) VALUES (?)",
                            (thread_id,)
                        )

            # Create threads
            threads = []
            for i in range(5):
                t = threading.Thread(target=insert_records, args=(i,))
                threads.append(t)
                t.start()

            # Wait for all threads
            for t in threads:
                t.join()

            # Verify all records inserted
            with conn_mgr.read_connection():
                row = conn_mgr.fetchone("SELECT COUNT(*) as cnt FROM test")
                assert row["cnt"] == 50  # 5 threads * 10 records

            conn_mgr.close()
