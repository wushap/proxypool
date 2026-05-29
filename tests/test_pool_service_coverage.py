"""
Tests for ProxyPoolService covering remaining uncovered paths.

Targets: delete_pool_chain_lease, inherit_pool_chain_lease success path,
sync_pool with existing published_subscription, cleanup exception path,
and get_pool_by_name branch with multiple pools.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from proxypool.pool.service import ProxyPoolService
from proxypool.storage.sqlite import SQLiteProxyStorage


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteProxyStorage:
    return SQLiteProxyStorage(tmp_path / "test.db")


@pytest.fixture
def service(storage: SQLiteProxyStorage) -> ProxyPoolService:
    return ProxyPoolService(storage)


def _make_lease(storage: SQLiteProxyStorage, pool_id: int, session_id: str = "s1") -> dict:
    """Insert a sticky lease directly into storage for testing."""
    return storage.upsert_sticky_lease(
        session_id=session_id,
        pool_id=pool_id,
        endpoint_id=0,
        instance_id="inst-1",
        exit_node_key="exit-abc",
        egress_ip="1.2.3.4",
        expires_at="2099-01-01T00:00:00+00:00",
        last_accessed="2026-01-01T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# delete_pool_chain_lease (lines 93-94)
# ---------------------------------------------------------------------------


class TestDeletePoolChainLease:
    def test_delete_existing_lease_returns_true(self, service: ProxyPoolService, storage: SQLiteProxyStorage) -> None:
        pool = service.create_pool(name="dl-lease")
        pid = pool["id"]
        _make_lease(storage, pid, session_id="sess-1")
        assert service.delete_pool_chain_lease(pid, "sess-1") is True

    def test_delete_nonexistent_lease_returns_false(self, service: ProxyPoolService) -> None:
        pool = service.create_pool(name="dl-no-lease")
        assert service.delete_pool_chain_lease(pool["id"], "ghost") is False


# ---------------------------------------------------------------------------
# inherit_pool_chain_lease success path (lines 105-118)
# ---------------------------------------------------------------------------


class TestInheritPoolChainLease:
    def test_inherit_existing_lease(self, service: ProxyPoolService, storage: SQLiteProxyStorage) -> None:
        pool = service.create_pool(name="inherit-ok")
        pid = pool["id"]
        _make_lease(storage, pid, session_id="src")
        inherited = service.inherit_pool_chain_lease(pid, "src", "dst")
        assert inherited["session_id"] == "dst"
        assert inherited["pool_id"] == pid
        assert inherited["exit_node_key"] == "exit-abc"
        assert inherited["egress_ip"] == "1.2.3.4"

    def test_inherit_runtime_error_when_get_returns_none(self, service: ProxyPoolService, storage: SQLiteProxyStorage) -> None:
        """Cover the defensive RuntimeError when get_sticky_lease returns None after upsert."""
        pool = service.create_pool(name="inherit-fail")
        pid = pool["id"]
        _make_lease(storage, pid, session_id="src")
        call_count = 0
        original_get = storage.get_sticky_lease

        def fake_get(session_id, pool_id, endpoint_id=0):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                return None
            return original_get(session_id, pool_id, endpoint_id)

        with patch.object(storage, "get_sticky_lease", side_effect=fake_get):
            with pytest.raises(RuntimeError, match="failed to inherit"):
                service.inherit_pool_chain_lease(pid, "src", "dst")


# ---------------------------------------------------------------------------
# sync_pool when pool already has published_subscription_id (line 155)
# ---------------------------------------------------------------------------


class TestSyncPoolExistingSubscription:
    def test_sync_with_existing_pub_sub(self, service: ProxyPoolService, storage: SQLiteProxyStorage) -> None:
        pool = service.create_pool(name="sync-existing")
        pid = pool["id"]
        # Create a published subscription first
        pub = storage.create_published_subscription(
            name=f"pool-{pid}", filters={}, enabled=True,
        )
        service.update_pool(pid, published_subscription_id=int(pub["id"]))
        result = service.sync_pool(pid)
        assert result["status"] == "running"
        assert result["published_subscription_id"] == int(pub["id"])


# ---------------------------------------------------------------------------
# _cleanup_published_subscription exception path (lines 184-186)
# ---------------------------------------------------------------------------


class TestCleanupPublishedSubscription:
    def test_delete_pool_with_broken_pub_sub(self, service: ProxyPoolService, storage: SQLiteProxyStorage) -> None:
        """Deleting a pool whose published_subscription_id is invalid should still succeed."""
        pool = service.create_pool(name="broken-pub")
        pid = pool["id"]
        service.update_pool(pid, published_subscription_id=99999)
        with patch.object(
            storage, "delete_published_subscription", side_effect=RuntimeError("db gone"),
        ):
            assert service.delete_pool(pid) is True
        assert service.get_pool(pid) is None


# ---------------------------------------------------------------------------
# get_pool_by_name branch coverage: multiple pools, first doesn't match (45->44)
# ---------------------------------------------------------------------------


class TestGetPoolByNameBranch:
    def test_name_matches_second_pool(self, service: ProxyPoolService) -> None:
        service.create_pool(name="alpha")
        service.create_pool(name="beta")
        found = service.get_pool_by_name("beta")
        assert found is not None
        assert found["name"] == "beta"

    def test_name_matches_none_of_many(self, service: ProxyPoolService) -> None:
        service.create_pool(name="a")
        service.create_pool(name="b")
        assert service.get_pool_by_name("z") is None
