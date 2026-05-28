"""Tests for get_proxy_pool_by_gateway_prefix() storage method."""

from __future__ import annotations

import pytest

from proxypool.storage.sqlite import SQLiteProxyStorage


def test_valid_prefix(storage: SQLiteProxyStorage):
    storage.create_proxy_pool(
        name="prefix-pool",
        gateway_path_prefix="/proxy/my-pool",
    )
    result = storage.get_proxy_pool_by_gateway_prefix("/proxy/my-pool")
    assert result is not None
    assert result["name"] == "prefix-pool"
    assert result["gateway_path_prefix"] == "/proxy/my-pool"


def test_invalid_prefix_returns_none(storage: SQLiteProxyStorage):
    storage.create_proxy_pool(
        name="other-pool",
        gateway_path_prefix="/proxy/other",
    )
    result = storage.get_proxy_pool_by_gateway_prefix("/proxy/nonexistent")
    assert result is None


def test_empty_prefix_returns_none(storage: SQLiteProxyStorage):
    storage.create_proxy_pool(name="no-prefix-pool")
    assert storage.get_proxy_pool_by_gateway_prefix("") is None
    assert storage.get_proxy_pool_by_gateway_prefix(None) is None


def test_exact_match_not_prefix(storage: SQLiteProxyStorage):
    storage.create_proxy_pool(
        name="exact-pool",
        gateway_path_prefix="/proxy/exact",
    )
    # "/proxy/exact-extra" should NOT match "/proxy/exact"
    result = storage.get_proxy_pool_by_gateway_prefix("/proxy/exact-extra")
    assert result is None


def test_multiple_pools_returns_correct_one(storage: SQLiteProxyStorage):
    storage.create_proxy_pool(name="pool-a", gateway_path_prefix="/proxy/pool-a")
    storage.create_proxy_pool(name="pool-b", gateway_path_prefix="/proxy/pool-b")
    storage.create_proxy_pool(name="pool-c", gateway_path_prefix="/proxy/pool-c")

    result_b = storage.get_proxy_pool_by_gateway_prefix("/proxy/pool-b")
    assert result_b is not None
    assert result_b["name"] == "pool-b"

    result_a = storage.get_proxy_pool_by_gateway_prefix("/proxy/pool-a")
    assert result_a is not None
    assert result_a["name"] == "pool-a"
