from __future__ import annotations

import abc
from pathlib import Path
from typing import Any


class BaseStorage(abc.ABC):
    """存储基类"""

    @abc.abstractmethod
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @abc.abstractmethod
    def _connect(self):
        """创建数据库连接"""
        pass

    @abc.abstractmethod
    def _init_db(self) -> None:
        """初始化数据库表"""
        pass

    @abc.abstractmethod
    def close(self) -> None:
        """关闭连接"""
        pass

    # ---- 事务支持 ----

    @abc.abstractmethod
    def begin_transaction(self):
        """开始事务"""
        pass

    @abc.abstractmethod
    def commit(self) -> None:
        """提交事务"""
        pass

    @abc.abstractmethod
    def rollback(self) -> None:
        """回滚事务"""
        pass


class StorageError(Exception):
    """存储异常基类"""
    pass


class NotFoundError(StorageError):
    """资源未找到"""
    pass


class ConflictError(StorageError):
    """资源冲突"""
    pass


class ValidationError(StorageError):
    """数据验证错误"""
    pass
