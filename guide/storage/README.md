# Storage Module

## Scope

The storage module owns SQLite persistence, schema initialization, query helpers, filtering, subscription export formatting, app settings, backend process state, gateway endpoints, chain health, and sticky lease records.

## Key Files

- `proxypool/storage/sqlite.py` defines `SQLiteProxyStorage` and helper functions for JSON normalization, filtering, subscription alias rewriting, and export formatting.

## Implementation Notes

`SQLiteProxyStorage` creates parent directories, opens SQLite connections with WAL mode and a busy timeout, and initializes all tables in `_init_db()`. Writes are guarded by an `RLock` where needed.

Major persisted entities include:

- `proxies` for imported proxy nodes, test status, speed metrics, GeoIP, IP purity, OpenAI status, and fallback front proxy keys.
- `subscriptions` and `published_subscriptions` for source refresh and exported subscription views.
- `proxy_pools` and `proxy_pools_v2` for user-facing pools and front/exit chain filters.
- `backend_process_events` and `backend_instances` for sing-box backend lifecycle.
- `http_proxy_endpoints` and `http_proxy_endpoint_hops` for gateway listeners and multi-hop configuration.
- `node_health`, `chain_egress_instances`, and `sticky_leases` for chain routing state.
- `app_settings` for small persisted runtime settings.

The storage layer also converts UI/API filter dictionaries into SQL query parameters, rewrites subscription aliases for export, deduplicates imported nodes by normalized key, and provides list/update methods consumed by every service layer.

## Tests

Storage behavior is covered by `tests/test_storage.py`, `tests/test_pool_storage.py`, published subscription tests, gateway config tests, backend tests, and many API tests that assert persistence side effects.
