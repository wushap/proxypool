"""
Tests for BaseStorage and storage exceptions.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from proxypool.storage.base import (
    BaseStorage,
    ConflictError,
    NotFoundError,
    StorageError,
    ValidationError,
)


class TestStorageExceptions:
    """Test storage exceptions."""

    def test_storage_error(self):
        """Test StorageError exception."""
        with pytest.raises(StorageError):
            raise StorageError("test error")

    def test_not_found_error(self):
        """Test NotFoundError exception."""
        with pytest.raises(NotFoundError):
            raise NotFoundError("not found")

    def test_conflict_error(self):
        """Test ConflictError exception."""
        with pytest.raises(ConflictError):
            raise ConflictError("conflict")

    def test_validation_error(self):
        """Test ValidationError exception."""
        with pytest.raises(ValidationError):
            raise ValidationError("validation error")

    def test_error_hierarchy(self):
        """Test exception hierarchy."""
        assert issubclass(NotFoundError, StorageError)
        assert issubclass(ConflictError, StorageError)
        assert issubclass(ValidationError, StorageError)


class ConcreteStorage(BaseStorage):
    """Concrete implementation for testing."""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__(db_path)
        self._init_db()

    def _connect(self):
        pass

    def _init_db(self) -> None:
        pass

    def close(self) -> None:
        pass

    def begin_transaction(self):
        pass

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class TestBaseStorage:
    """Test BaseStorage."""

    def test_create_concrete_storage(self):
        """Test creating concrete storage implementation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "test.db"
            storage = ConcreteStorage(db_path)
            assert storage.db_path == db_path
            # Parent directory should be created
            assert storage.db_path.parent.exists()
