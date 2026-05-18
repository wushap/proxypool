# Guide Maintenance Instructions

This directory documents the implementation and behavior of each major Proxy Pool submodule. Keep it synchronized with code changes that alter module responsibilities, public APIs, persistence layout, runtime behavior, or the Web UI.

## When To Update

Update the relevant guide page in the same change set when you modify:

- FastAPI routes, request/response schemas, authorization, app startup, or mounted static assets.
- Proxy collection, subscription fetching, parser support, or import reporting.
- Proxy probing, speed tests, OpenAI unlock checks, or sing-box probing behavior.
- Backend process management, generated sing-box or mihomo configs, route files, or instance lifecycle.
- HTTP gateway endpoints, session extraction, forward proxy runtime, or request routing.
- Chain pool selection, sticky leases, node health, or multi-hop route construction.
- SQLite tables, migrations performed in `_init_db`, storage methods, or exported subscription formatting.
- Background task lifecycle, cancellation, progress fields, or auto task scheduling.
- GeoIP, IP purity, residential/datacenter heuristics, or proxy-based metadata lookups.
- Web UI pages, API calls, state keys, controls, or static asset layout.
- Settings, environment variables, entry points, or cross-module wiring that changes how modules are instantiated.

## Directory Layout

- `api/` documents `proxypool/api/` and the FastAPI application assembly in `proxypool/api/app.py`.
- `README.md` documents the overall architecture and end-to-end product workflow.
- `backend/` documents process/config managers under `proxypool/backend/`.
- `collector/` documents source fetching, parsing, and import services under `proxypool/collector/`.
- `gateway/` documents HTTP gateway and forward proxy runtime code under `proxypool/gateway/`.
- `geoip/` documents IP resolution, geo enrichment, and IP purity code under `proxypool/geoip/`.
- `pool/` documents proxy pool, chain, sticky routing, and health code under `proxypool/pool/`.
- `scheduler/` documents scheduled collector/tester jobs under `proxypool/scheduler/`.
- `storage/` documents SQLite schema and persistence APIs under `proxypool/storage/`.
- `tasks/` documents in-memory task tracking under `proxypool/tasks/`.
- `tester/` documents probing, speed tests, and unlock checks under `proxypool/tester/`.
- `webui/` documents the static Vue console under `proxypool/webui/`.

## Style

Write concise implementation notes, not marketing copy. Include the module's responsibilities, key files/classes, runtime dependencies, important data flows, and tests that cover the behavior. Prefer exact file names and route names over vague descriptions.

When adding a new top-level submodule under `proxypool/`, add a matching subdirectory here with a `README.md`. If the module is intentionally undocumented, state the reason in this file.
