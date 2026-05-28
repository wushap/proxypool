"""Tests for the unified gateway proxy route /proxy/{pool}/{protocol}/{path}."""

from __future__ import annotations

import pytest
import httpx


@pytest.fixture
def pool_with_prefix(storage, settings):
    """Create a pool with gateway_path_prefix and REJECT session policy."""
    return storage.create_proxy_pool(
        name="gw-pool",
        gateway_path_prefix="/proxy/gw-pool",
        session_missing_action="REJECT",
        session_header_names=["X-Session", "Authorization"],
        session_query_param_names=["session_id", "sid"],
    )


@pytest.fixture
def pool_random(storage, settings):
    """Create a pool with RANDOM session policy."""
    return storage.create_proxy_pool(
        name="random-pool",
        gateway_path_prefix="/proxy/random-pool",
        session_missing_action="RANDOM",
    )


async def test_unconfigured_pool_returns_404(client: httpx.AsyncClient):
    resp = await client.get("/proxy/no-such-pool/https/example.com/path")
    assert resp.status_code == 404
    assert "no pool configured" in resp.json()["detail"]


async def test_reject_without_session_returns_400(
    client: httpx.AsyncClient, pool_with_prefix
):
    resp = await client.get("/proxy/gw-pool/https/example.com/test")
    assert resp.status_code == 400
    assert "session_id is required" in resp.json()["detail"]


async def test_session_from_header(client: httpx.AsyncClient, pool_with_prefix):
    resp = await client.get(
        "/proxy/gw-pool/https/example.com/test",
        headers={"X-Session": "abc-123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["pool_name"] == "gw-pool"
    assert body["target_url"] == "https://example.com/test"


async def test_session_from_query_param(client: httpx.AsyncClient, pool_with_prefix):
    resp = await client.get(
        "/proxy/gw-pool/https/example.com/test?session_id=xyz-789",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["pool_name"] == "gw-pool"


async def test_session_from_second_header(
    client: httpx.AsyncClient, pool_with_prefix
):
    resp = await client.get(
        "/proxy/gw-pool/https/example.com/api",
        headers={"Authorization": "Bearer tok-456"},
    )
    assert resp.status_code == 200
    assert resp.json()["pool_id"] == pool_with_prefix["id"]


async def test_session_from_query_param_name(
    client: httpx.AsyncClient, pool_with_prefix
):
    # The route handler checks "session_id" query param specifically
    resp = await client.get(
        "/proxy/gw-pool/https/example.com/api?session_id=qrs-012",
    )
    assert resp.status_code == 200


async def test_random_policy_allows_no_session(
    client: httpx.AsyncClient, pool_random
):
    resp = await client.get("/proxy/random-pool/https/example.com/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pool_name"] == "random-pool"
    assert body["target_url"] == "https://example.com/test"


async def test_random_policy_with_session(
    client: httpx.AsyncClient, pool_random
):
    resp = await client.get(
        "/proxy/random-pool/https/example.com/test",
        headers={"X-Session": "has-session"},
    )
    assert resp.status_code == 200
