"""
Tests for proxypool.storage.base -- abstract class contracts and exception hierarchy.

Covers:
- BaseStorage cannot be instantiated directly
- Incomplete subclasses are rejected
- Complete subclasses work and __init__ side-effects execute
- Exception inheritance tree and catch behavior
"""

from __future__ import annotations

import abc
from pathlib import Path

import pytest

from proxypool.storage.base import (
    BaseStorage,
    ConflictError,
    NotFoundError,
    StorageError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Concrete helper that satisfies every abstract method
# ---------------------------------------------------------------------------


class _FullImpl(BaseStorage):
    """Minimal concrete subclass that calls super().__init__."""

    def __init__(self, db_path: str | Path) -> None:
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


# ---------------------------------------------------------------------------
# ABC enforcement
# ---------------------------------------------------------------------------


class TestBaseStorageCannotBeInstantiatedDirectly:
    def test_raises_type_error(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            BaseStorage(tmp_path / "x.db")


class TestIncompleteSubclassRejected:
    """Any subclass missing at least one abstract method must fail."""

    def test_no_methods_implemented(self, tmp_path: Path) -> None:
        class Empty(BaseStorage):
            pass

        with pytest.raises(TypeError, match="abstract method"):
            Empty(tmp_path / "empty.db")

    def test_only_close_implemented(self, tmp_path: Path) -> None:
        class OnlyClose(BaseStorage):
            def close(self) -> None:
                pass

        with pytest.raises(TypeError, match="abstract method"):
            OnlyClose(tmp_path / "close.db")

    def test_missing_transaction_methods(self, tmp_path: Path) -> None:
        class NoTransaction(BaseStorage):
            def __init__(self, db_path):
                super().__init__(db_path)

            def _connect(self):
                return None

            def _init_db(self) -> None:
                pass

            def close(self) -> None:
                pass

            # begin_transaction, commit, rollback omitted

        with pytest.raises(TypeError, match="abstract method"):
            NoTransaction(tmp_path / "notx.db")


class TestCompleteSubclassAccepted:
    def test_can_instantiate(self, tmp_path: Path) -> None:
        s = _FullImpl(tmp_path / "ok.db")
        assert s.db_path == tmp_path / "ok.db"

    def test_db_path_is_path_object(self, tmp_path: Path) -> None:
        s = _FullImpl(str(tmp_path / "str.db"))
        assert isinstance(s.db_path, Path)

    def test_no_remaining_abstract_methods(self, tmp_path: Path) -> None:
        s = _FullImpl(tmp_path / "count.db")
        remaining = [
            n
            for n in ("__init__", "_connect", "_init_db", "close",
                       "begin_transaction", "commit", "rollback")
            if getattr(getattr(type(s), n), "__isabstractmethod__", False)
        ]
        assert remaining == []


# ---------------------------------------------------------------------------
# __init__ side-effects
# ---------------------------------------------------------------------------


class TestBaseStorageInitSideEffects:
    def test_creates_deeply_nested_parent(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c" / "test.db"
        assert not deep.parent.exists()
        _FullImpl(deep)
        assert deep.parent.is_dir()

    def test_existing_parent_idempotent(self, tmp_path: Path) -> None:
        _FullImpl(tmp_path / "first.db")
        _FullImpl(tmp_path / "second.db")  # parent already exists


# ---------------------------------------------------------------------------
# Abstract method declarations
# ---------------------------------------------------------------------------


class TestAbstractMethodDeclarations:
    EXPECTED = frozenset({
        "__init__", "_connect", "_init_db", "close",
        "begin_transaction", "commit", "rollback",
    })

    def test_expected_methods_are_abstract(self) -> None:
        for name in self.EXPECTED:
            assert getattr(getattr(BaseStorage, name), "__isabstractmethod__", False)

    def test_no_unexpected_abstract_methods(self) -> None:
        actual = {
            n for n in dir(BaseStorage)
            if getattr(getattr(BaseStorage, n), "__isabstractmethod__", False)
        }
        assert actual == self.EXPECTED


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    def test_storage_error_is_exception(self) -> None:
        assert issubclass(StorageError, Exception)

    @pytest.mark.parametrize(
        "exc_cls",
        [NotFoundError, ConflictError, ValidationError],
    )
    def test_subclass_inherits_storage_error(self, exc_cls: type) -> None:
        assert issubclass(exc_cls, StorageError)

    @pytest.mark.parametrize(
        "exc_cls",
        [NotFoundError, ConflictError, ValidationError],
    )
    def test_subclass_not_siblings(self, exc_cls: type) -> None:
        siblings = {NotFoundError, ConflictError, ValidationError} - {exc_cls}
        for sib in siblings:
            assert not issubclass(exc_cls, sib)

    def test_message_preserved(self) -> None:
        assert str(StorageError("hello")) == "hello"
        assert str(NotFoundError("nf")) == "nf"
        assert str(ConflictError("cf")) == "cf"
        assert str(ValidationError("vf")) == "vf"

    def test_catch_as_storage_error(self) -> None:
        for exc in (NotFoundError("a"), ConflictError("b"), ValidationError("c")):
            with pytest.raises(StorageError):
                raise exc

    def test_custom_subclass(self) -> None:
        class MyErr(StorageError):
            pass

        assert issubclass(MyErr, StorageError)
        with pytest.raises(StorageError):
            raise MyErr("custom")
