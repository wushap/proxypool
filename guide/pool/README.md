# Pool Module

## Scope

The pool module manages logical proxy pools, chain pool selection, node health, sticky routing, and route construction. It is the core routing layer used by HTTP gateway endpoints and chain instance management.

## Key Files

- `proxypool/pool/service.py` defines `ProxyPoolService` for CRUD and published-subscription synchronization.
- `proxypool/pool/chain_service.py` defines `ProxyChainService`, the high-level chain routing orchestrator.
- `proxypool/pool/node_pool.py` stores filtered in-memory front/exit node pools.
- `proxypool/pool/chain_builder.py` builds chain proxy URLs/config inputs from storage rows.
- `proxypool/pool/sticky_router.py` implements session-to-egress lease selection.
- `proxypool/pool/health_manager.py` tracks node health, circuit state, and route probing.

## Implementation Notes

`ProxyPoolService` wraps storage operations for user-facing proxy pools. It creates, updates, lists, deletes, starts/stops, and syncs pools to published subscriptions. Chain-related settings such as sticky TTL, session rules, gateway path prefixes, and missing-session policy are stored with the pool and exposed through API routes.

`ProxyChainService` initializes in-memory front and exit `NodePool` instances from persisted `proxy_pools_v2` regex filters and all proxy rows. It applies tested availability, persisted health state, and sticky leases from SQLite. Route requests select healthy front/exit nodes, support endpoint-specific multi-hop route signatures, and bind session leases for stable egress behavior.

`HealthManager` can probe chain combinations, update health records, and open/close circuit state based on failures. `StickyRouter` keeps active leases and load counters so repeated session traffic does not churn egress IPs unnecessarily.

## Tests

Pool and chain behavior is covered by `tests/test_api_pools.py`, `tests/test_chain_service.py`, `tests/test_chain_instance_manager.py`, `tests/test_pool_storage.py`, and gateway tests.
