from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


class ConnectionManager:
    """SQLite 连接管理器"""

    def __init__(
        self,
        db_path: str | Path,
        timeout: float = 30.0,
    ) -> None:
        self.db_path = Path(db_path)
        self.timeout = timeout
        self._local = threading.local()
        self._write_lock = threading.RLock()

    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=self.timeout,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA foreign_keys = ON")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def read_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """获取读连接"""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            pass  # 保持连接复用

    @contextmanager
    def write_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """获取写连接（带锁）"""
        with self._write_lock:
            conn = self._get_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """事务上下文"""
        with self._write_lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def close(self) -> None:
        """关闭连接"""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def execute(self, sql: str, params: tuple | None = None) -> sqlite3.Cursor:
        """执行 SQL"""
        conn = self._get_connection()
        if params:
            return conn.execute(sql, params)
        return conn.execute(sql)

    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """批量执行 SQL"""
        conn = self._get_connection()
        return conn.executemany(sql, params_list)

    def fetchone(self, sql: str, params: tuple | None = None) -> sqlite3.Row | None:
        """查询单行"""
        conn = self._get_connection()
        if params:
            return conn.execute(sql, params).fetchone()
        return conn.execute(sql).fetchone()

    def fetchall(self, sql: str, params: tuple | None = None) -> list[sqlite3.Row]:
        """查询多行"""
        conn = self._get_connection()
        if params:
            return conn.execute(sql, params).fetchall()
        return conn.execute(sql).fetchall()

    def commit(self) -> None:
        """提交当前事务"""
        conn = self._get_connection()
        conn.commit()

    def rollback(self) -> None:
        """回滚当前事务"""
        conn = self._get_connection()
        conn.rollback()
