# API Module

## Scope

The API module exposes the FastAPI application, request/response schemas, and optional write-operation authorization. It is the main composition layer for the project: `create_app()` wires storage, collector, tester, GeoIP, scheduler, backend managers, pool services, gateway runtime, and task management into `app.state`.

## Key Files

- `proxypool/api/app.py` builds the FastAPI app and defines all HTTP routes.
- `proxypool/api/schemas.py` defines Pydantic request models used by route handlers.
- `proxypool/api/security.py` implements optional API-key authorization.
- `proxypool/main.py` imports `create_app()` and starts uvicorn on `0.0.0.0:8080`.

## Implementation Notes

`create_app(settings)` loads `AppSettings`, creates a shared `SQLiteProxyStorage`, then instantiates service objects for collection, probing, GeoIP, scheduling, proxy pools, chain routing, sing-box/mihomo backends, and HTTP gateway endpoints. Route handlers stay mostly thin: they validate request models, call the service/storage layer, and translate errors to `HTTPException`.

The API also owns application lifecycle hooks. Startup starts gateway runtime when configured, initializes background backend health checks, and prepares auto task state. Shutdown stops schedulers, backend processes, chain services, and gateway runtime.

Authorization is implemented as HTTP middleware. Read-oriented endpoints are allowed without a key, while mutating API calls require `X-API-Key` when `PROXYPOOL_API_KEY` is configured.

## Route Groups

- Health/statistics: `/api/health`, `/api/stats`.
- Task progress and auto tasks: `/api/tasks`, `/api/tasks/{task_id}`, `/api/tasks/*/start`, `/api/tasks/auto-config`.
- Backend process and route management: `/api/backend/*`.
- Proxy listing and bulk deletion: `/api/proxies`, `/api/proxies/delete-*`.
- Collection and subscriptions: `/api/collector/*`, `/api/subscriptions/*`, `/api/published-subscriptions/*`, `/api/subscription`.
- GeoIP and IP purity: `/api/geoip/enrich`, `/api/geoip/ip-purity`, corresponding task start routes.
- Testing and speed checks: `/api/tester/*`, `/api/tasks/speed-test/start`, `/api/tasks/openai-check/start`. Speed-test requests can pass `only_direct=true` to restrict candidates to directly reachable available nodes (`fallback_front_keys_json = '[]'`), excluding nodes that only work through a fallback front proxy.
- Proxy pools and chain routes: `/api/pools/*`, `/api/chain/*`.
- HTTP gateway: `/api/gateway/*`, `/api/http-proxy-endpoints/*`, and `/api/gateway/{pool_name}/{scheme}/{target_host}/{target_path}`.

## Tests

API behavior is covered across `tests/test_api_*.py`, `tests/test_security.py`, `tests/test_webui_template.py`, `tests/test_webui_tasks.py`, `tests/test_api_pools.py`, and gateway/backend focused tests.
