"""
Tests for proxypool.storage.base -- BaseStorage ABC and exception hierarchy.

Base coverage is 100% from imports alone (class definitions execute on load).
These tests verify *behavior*: ABC enforcement, abstract-method contracts,
__init__ side-effects, and exception inheritance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from proxypool.storage.base import (
    BaseStorage,
    ConflictError,
    NotFoundError,
    StorageError,
    ValidationError,
)


# ---- BaseStorage ABC enforcement ----


class ConcreteStorage(BaseStorage):
    """Minimal concrete implementation that calls super().__init__."""

    def __init__(self, db_path):
        super().__init__(db_path)

    def _connect(self):
        return None

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


# ---- BaseStorage ABC enforcement ----


class TestBaseStorageABC:
    """Verify that BaseStorage cannot be instantiated directly."""

    def test_cannot_instantiate_directly(self, tmp_path):
        with pytest.raises(TypeError, match="abstract method"):
            BaseStorage(tmp_path / "dummy.db")

    def test_incomplete_subclass_raises(self, tmp_path):
        """A subclass missing abstract methods cannot be instantiated."""

        class PartialStorage(BaseStorage):
            pass

        with pytest.raises(TypeError, match="abstract method"):
            PartialStorage(tmp_path / "partial.db")

    def test_complete_subclass_can_instantiate(self, tmp_path):
        """A subclass implementing all abstract methods can be instantiated."""
        storage = ConcreteStorage(tmp_path / "ok.db")
        assert storage.db_path == tmp_path / "ok.db"


# ---- BaseStorage.__init__ side-effects ----


class TestBaseStorageInit:
    """Verify __init__ creates parent directories and sets db_path."""

    def test_creates_parent_directories(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "test.db"
        assert not nested.parent.exists()
        ConcreteStorage(nested)
        assert nested.parent.exists()

    def test_db_path_set_from_string(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        storage = ConcreteStorage(db_file)
        assert isinstance(storage.db_path, Path)
        assert storage.db_path.name == "test.db"

    def test_existing_directory_ok(self, tmp_path):
        """mkdir with exist_ok=True should not fail on existing dirs."""
        storage = ConcreteStorage(tmp_path / "test.db")
        assert storage.db_path.parent.exists()


# ---- Abstract method contracts ----


class TestAbstractMethods:
    """Verify all expected abstract methods exist on BaseStorage."""

    ABSTRACT_METHODS = {
        "__init__",
        "_connect",
        "_init_db",
        "close",
        "begin_transaction",
        "commit",
        "rollback",
    }

    def test_all_abstract_methods_present(self):
        for name in self.ABSTRACT_METHODS:
            method = getattr(BaseStorage, name)
            assert getattr(method, "__isabstractmethod__", False), (
                f"{name} should be abstract"
            )

    def test_missing_methods_prevent_instantiation(self, tmp_path):
        """Omitting any abstract method prevents instantiation."""

        class OnlyClose(BaseStorage):
            def close(self) -> None:
                pass

        with pytest.raises(TypeError, match="abstract method"):
            OnlyClose(tmp_path / "nope.db")

    def test_partial_implementation_still_fails(self, tmp_path):
        class PartialImpl(BaseStorage):
            def _connect(self):
                return None

            def _init_db(self) -> None:
                pass

            def close(self) -> None:
                pass

        with pytest.raises(TypeError, match="abstract method"):
            PartialImpl(tmp_path / "nope.db")

    def test_complete_subclass_count_matches(self, tmp_path):
        """A complete implementation should have exactly 0 abstract methods."""
        concrete = ConcreteStorage(tmp_path / "count.db")
        remaining = {
            name
            for name in self.ABSTRACT_METHODS
            if getattr(getattr(type(concrete), name), "__isabstractmethod__", False)
        }
        assert remaining == set()


# ---- Exception hierarchy ----


class TestStorageErrorHierarchy:
    """Verify the exception classes form the expected inheritance tree."""

    def test_storage_error_is_exception(self):
        assert issubclass(StorageError, Exception)

    def test_not_found_error_inherits_storage_error(self):
        assert issubclass(NotFoundError, StorageError)

    def test_conflict_error_inherits_storage_error(self):
        assert issubclass(ConflictError, StorageError)

    def test_validation_error_inherits_storage_error(self):
        assert issubclass(ValidationError, StorageError)

    def test_storage_error_catchable(self):
        with pytest.raises(StorageError):
            raise StorageError("base")

    def test_not_found_error_catchable_as_storage_error(self):
        with pytest.raises(StorageError):
            raise NotFoundError("not found")

    def test_conflict_error_catchable_as_storage_error(self):
        with pytest.raises(StorageError):
            raise ConflictError("conflict")

    def test_validation_error_catchable_as_storage_error(self):
        with pytest.raises(StorageError):
            raise ValidationError("validation")

    def test_exception_messages_preserved(self):
        assert str(StorageError("msg")) == "msg"
        assert str(NotFoundError("msg")) == "msg"
        assert str(ConflictError("msg")) == "msg"
        assert str(ValidationError("msg")) == "msg"

    def test_exceptions_catchable_by_specific_type(self):
        with pytest.raises(NotFoundError):
            raise NotFoundError("only specific")

    def test_exceptions_not_cross_catchable(self):
        """NotFoundError should not be caught by ConflictError handler."""
        with pytest.raises(NotFoundError):
            with pytest.raises(ConflictError):
                raise NotFoundError("wrong handler")

    def test_exceptions_can_be_subclassed(self):
        class CustomStorageError(StorageError):
            pass

        assert issubclass(CustomStorageError, StorageError)
        with pytest.raises(StorageError):
            raise CustomStorageError("custom")
