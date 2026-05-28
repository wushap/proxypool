"""
Tests for ProxyPoolService API layer.

Covers: create, get, list, update, delete, name lookup, enrichment,
and the session/lease management methods.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from proxypool.pool.service import ProxyPoolService
from proxypool.storage.sqlite import SQLiteProxyStorage


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteProxyStorage:
    return SQLiteProxyStorage(tmp_path / "test.db")


@pytest.fixture
def service(storage: SQLiteProxyStorage) -> ProxyPoolService:
    return ProxyPoolService(storage)


# ---------------------------------------------------------------------------
# Creating pools
# ---------------------------------------------------------------------------


class TestCreatePool:
    def test_create_with_defaults(self, service: ProxyPoolService) -> None:
        pool = service.create_pool(name="my-pool")
        assert pool["name"] == "my-pool"
        assert pool["status"] == "stopped"
        assert pool["listen"] == "0.0.0.0"
        assert pool["inbound_type"] == "http"

    def test_create_with_custom_params(self, service: ProxyPoolService) -> None:
        pool = service.create_pool(
            name="custom",
            filters={"protocol": "trojan", "available": "true"},
            listen="127.0.0.1",
            inbound_type="socks5",
        )
        assert pool["name"] == "custom"
        assert pool["listen"] == "127.0.0.1"
        assert pool["inbound_type"] == "socks5"
        assert pool["filters"]["protocol"] == "trojan"
        assert pool["filters"]["available"] == "true"

    def test_create_with_empty_filters(self, service: ProxyPoolService) -> None:
        pool = service.create_pool(name="no-filters", filters=None)
        assert pool["name"] == "no-filters"
        assert isinstance(pool["filters"], dict)

    def test_create_returns_id(self, service: ProxyPoolService) -> None:
        pool = service.create_pool(name="id-test")
        assert "id" in pool
        assert isinstance(pool["id"], int)
        assert pool["id"] > 0


# ---------------------------------------------------------------------------
# Getting pools
# ---------------------------------------------------------------------------


class TestGetPool:
    def test_get_by_id(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="findme")
        found = service.get_pool(created["id"])
        assert found is not None
        assert found["id"] == created["id"]
        assert found["name"] == "findme"

    def test_get_nonexistent_returns_none(self, service: ProxyPoolService) -> None:
        assert service.get_pool(99999) is None

    def test_get_chain_config(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="chain-test")
        cfg = service.get_pool_chain_config(created["id"])
        assert cfg is not None
        assert cfg["name"] == "chain-test"

    def test_get_chain_config_nonexistent(self, service: ProxyPoolService) -> None:
        assert service.get_pool_chain_config(99999) is None


# ---------------------------------------------------------------------------
# Getting pools by name
# ---------------------------------------------------------------------------


class TestGetPoolByName:
    def test_find_existing(self, service: ProxyPoolService) -> None:
        service.create_pool(name="named-pool")
        found = service.get_pool_by_name("named-pool")
        assert found is not None
        assert found["name"] == "named-pool"

    def test_not_found(self, service: ProxyPoolService) -> None:
        assert service.get_pool_by_name("does-not-exist") is None

    def test_empty_name_returns_none(self, service: ProxyPoolService) -> None:
        service.create_pool(name="x")
        assert service.get_pool_by_name("") is None
        assert service.get_pool_by_name("  ") is None
        assert service.get_pool_by_name(None) is None


# ---------------------------------------------------------------------------
# Listing pools
# ---------------------------------------------------------------------------


class TestListPools:
    def test_list_empty(self, service: ProxyPoolService) -> None:
        assert service.list_pools() == []

    def test_list_returns_all(self, service: ProxyPoolService) -> None:
        service.create_pool(name="a")
        service.create_pool(name="b")
        service.create_pool(name="c")
        pools = service.list_pools()
        assert len(pools) == 3
        names = {p["name"] for p in pools}
        assert names == {"a", "b", "c"}

    def test_list_contains_enriched_fields(self, service: ProxyPoolService) -> None:
        service.create_pool(name="enriched")
        pools = service.list_pools()
        pool = pools[0]
        # Enriched pool should have match_count
        assert "match_count" in pool
        assert isinstance(pool["match_count"], int)


# ---------------------------------------------------------------------------
# Updating pools
# ---------------------------------------------------------------------------


class TestUpdatePool:
    def test_update_name(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="old")
        updated = service.update_pool(created["id"], name="new")
        assert updated["name"] == "new"

    def test_update_filters(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="f")
        updated = service.update_pool(created["id"], filters={"geo_country": "JP"})
        assert updated["filters"]["geo_country"] == "JP"

    def test_update_listen(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="listen")
        updated = service.update_pool(created["id"], listen="10.0.0.1")
        assert updated["listen"] == "10.0.0.1"

    def test_update_inbound_type(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="type")
        updated = service.update_pool(created["id"], inbound_type="socks5")
        assert updated["inbound_type"] == "socks5"

    def test_update_nonexistent_raises(self, service: ProxyPoolService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.update_pool(99999, name="x")

    def test_update_pool_chain_config(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="chain-update")
        updated = service.update_pool_chain_config(
            created["id"], filters={"protocol": "vmess"}
        )
        assert updated["filters"]["protocol"] == "vmess"

    def test_update_chain_config_nonexistent_raises(self, service: ProxyPoolService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.update_pool_chain_config(99999, name="x")


# ---------------------------------------------------------------------------
# Deleting pools
# ---------------------------------------------------------------------------


class TestDeletePool:
    def test_delete_existing(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="doomed")
        assert service.delete_pool(created["id"]) is True
        assert service.get_pool(created["id"]) is None

    def test_delete_nonexistent(self, service: ProxyPoolService) -> None:
        assert service.delete_pool(99999) is False

    def test_delete_removes_from_list(self, service: ProxyPoolService) -> None:
        p1 = service.create_pool(name="stay")
        p2 = service.create_pool(name="go")
        service.delete_pool(p2["id"])
        pools = service.list_pools()
        assert len(pools) == 1
        assert pools[0]["id"] == p1["id"]


# ---------------------------------------------------------------------------
# Pool enrichment (export_url)
# ---------------------------------------------------------------------------


class TestPoolEnrichment:
    def test_enrichment_with_published_sub(self, service: ProxyPoolService) -> None:
        """Enriched pool gets export_url when published_subscription_id is set."""
        created = service.create_pool(name="pub")
        service.update_pool(created["id"], published_subscription_id=42)
        pool = service.get_pool(created["id"])
        assert pool is not None
        assert "export_url" in pool
        assert "42" in pool["export_url"]

    def test_enrichment_without_published_sub(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="no-pub")
        pool = service.get_pool(created["id"])
        assert pool is not None
        assert "export_url" not in pool


# ---------------------------------------------------------------------------
# Start / Stop pool
# ---------------------------------------------------------------------------


class TestStartStopPool:
    def test_start_pool(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="start-me")
        result = service.start_pool(created["id"])
        assert result["status"] == "running"

    def test_stop_pool(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="stop-me")
        service.start_pool(created["id"])
        result = service.stop_pool(created["id"])
        assert result["status"] == "stopped"

    def test_start_nonexistent_raises(self, service: ProxyPoolService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.start_pool(99999)

    def test_stop_nonexistent_raises(self, service: ProxyPoolService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.stop_pool(99999)


# ---------------------------------------------------------------------------
# Session rules
# ---------------------------------------------------------------------------


class TestSessionRules:
    def test_upsert_and_list_rules(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="rules")
        pid = created["id"]
        service.upsert_pool_session_rule(pid, url_prefix="https://api.example.com")
        rules = service.list_pool_session_rules(pid)
        assert len(rules) == 1
        assert rules[0]["url_prefix"] == "https://api.example.com"

    def test_delete_session_rule(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="del-rule")
        pid = created["id"]
        service.upsert_pool_session_rule(pid, url_prefix="https://x.com")
        deleted = service.delete_pool_session_rule(pid, "https://x.com")
        assert deleted is True
        assert service.list_pool_session_rules(pid) == []

    def test_session_rules_nonexistent_pool_raises(self, service: ProxyPoolService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.upsert_pool_session_rule(99999, url_prefix="x")
        with pytest.raises(ValueError, match="not found"):
            service.list_pool_session_rules(99999)
        with pytest.raises(ValueError, match="not found"):
            service.delete_pool_session_rule(99999, "x")


# ---------------------------------------------------------------------------
# Sync pool
# ---------------------------------------------------------------------------


class TestSyncPool:
    def test_sync_creates_published_subscription(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="sync-me")
        result = service.sync_pool(created["id"])
        assert result["status"] == "running"
        assert "published_subscription_id" in result
        assert result["published_subscription_id"] is not None

    def test_sync_nonexistent_raises(self, service: ProxyPoolService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.sync_pool(99999)


# ---------------------------------------------------------------------------
# Sticky leases
# ---------------------------------------------------------------------------


class TestStickyLeases:
    def test_list_leases_empty(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="leases")
        leases = service.list_pool_chain_leases(created["id"])
        assert leases == []

    def test_list_leases_nonexistent_pool_raises(self, service: ProxyPoolService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.list_pool_chain_leases(99999)

    def test_delete_lease_nonexistent_pool_raises(self, service: ProxyPoolService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.delete_pool_chain_lease(99999, "session-1")

    def test_inherit_lease_nonexistent_pool_raises(self, service: ProxyPoolService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.inherit_pool_chain_lease(99999, "s1", "s2")

    def test_inherit_lease_missing_source_raises(self, service: ProxyPoolService) -> None:
        created = service.create_pool(name="inherit")
        with pytest.raises(ValueError, match="source sticky lease not found"):
            service.inherit_pool_chain_lease(created["id"], "missing", "new")
