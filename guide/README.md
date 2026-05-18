# Proxy Pool Overall Functionality And Architecture

## What The System Does

Proxy Pool is a local proxy management system built around a complete end-to-end workflow:

1. Import proxy sources from text, files, URLs, and managed subscriptions.
2. Parse and normalize proxy nodes into a shared SQLite database.
3. Test node availability, latency, bandwidth, OpenAI unlock status, GeoIP, and IP purity.
4. Filter nodes into logical pools and front/exit chain pools.
5. Build single-hop or multi-hop egress routes using sing-box and mihomo.
6. Expose usable subscription exports, local backend ports, HTTP gateway endpoints, and a Web UI console.

The main runtime entry point is `python3 -m proxypool.main`, which starts FastAPI, serves the Web UI, initializes services, and manages configured background/runtime components.

## High-Level Architecture

The application is organized as service modules under `proxypool/`, all wired together by `proxypool/api/app.py`.

- `api` is the composition and HTTP boundary. It creates service instances, exposes JSON routes, serves the Web UI, enforces optional API-key protection, and owns startup/shutdown hooks.
- `storage` is the shared persistence layer. SQLite stores proxy nodes, subscriptions, published exports, pools, gateway endpoints, backend process state, chain instances, node health, sticky leases, and app settings.
- `collector` imports source content, parses proxy formats, deduplicates nodes, and writes import reports.
- `tester` probes proxies through sing-box, updates availability/latency/speed/unlock fields, and supports fallback front-proxy probing.
- `geoip` enriches tested proxies with resolved IP, country/city, IP purity, and residential/datacenter signals.
- `pool` manages logical proxy pools, front/exit node pools, health state, sticky routing, and route selection.
- `backend` generates and runs sing-box or mihomo configs for local proxy egress and chain instances.
- `gateway` exposes configured HTTP proxy endpoints and API-mounted forwarding routes.
- `tasks` tracks long-running background operations started from API/Web UI.
- `scheduler` runs simple interval collection and testing jobs.
- `webui` is a static Vue/Element Plus console for operating the whole system.
- `deploy` documents container deployment and runtime mount strategy.

## End-To-End Data Flow

### 1. Source Import

Users import proxy content through the Web UI, scripts, or API routes such as `/api/collector/import-texts`, `/api/collector/import-files`, `/api/collector/import-urls`, and `/api/subscriptions/{id}/refresh`.

`CollectorService` fetches or reads content, expands nested subscription source references when present, and sends raw text to `collector.parser`. The parser converts supported formats into `ProxyNode` records. Storage deduplicates by each node's `normalized_key` and records source, raw link, protocol, host, port, and protocol-specific metadata.

### 2. Persistence And Querying

`SQLiteProxyStorage` is the durable center of the application. Every major service reads from and writes to it. API filters and Web UI table filters eventually become storage queries over fields such as protocol, availability, latency, GeoIP, IP purity, OpenAI status, source, and fallback front keys.

Subscription export routes read filtered proxy rows from storage and render share links. Alias rewriting gives exported nodes stable, readable names based on serial numbers and metadata.

### 3. Testing And Enrichment

The Web UI starts long-running checks through task routes:

- `/api/tasks/tester/start` for availability and latency.
- `/api/tasks/speed-test/start` for bandwidth.
- `/api/tasks/openai-check/start` for unlock status.
- `/api/tasks/geoip/start` for IP location.
- `/api/tasks/ip-purity/start` for purity/residential classification.

`TaskManager` tracks progress and cancellation. `TesterService` and `GeoIPService` update proxy rows as checks finish. These fields then feed pool filtering, chain route quality, subscription export filters, and UI status displays.

### 4. Pool And Chain Routing

Proxy Pool has two related pool concepts:

- User-facing proxy pools in `proxy_pools`, used for published subscriptions and gateway pool configuration.
- Chain node pools in `proxy_pools_v2`, where regex filters define `front` and `exit` candidate sets.

`ProxyChainService` loads proxy rows, applies front/exit filters, overlays persisted health state, and chooses routes for gateway traffic. Sticky leases bind a session ID to an egress route so repeated requests can keep the same exit identity. Health data and circuit state help avoid repeatedly selecting failing nodes.

### 5. Backend Runtime

For local backend ports, `SingBoxBackendManager` converts configured `SingBoxRoute` objects into sing-box runtime config. Each route maps a local inbound listener to one proxy or an ordered chain of proxy keys.

For gateway chain instances, `ChainInstanceManager` asks `MihomoEgressBackend` to create a concrete local HTTP proxy instance for a selected route. The mihomo config represents the chosen front/exit or multi-hop chain and is persisted with process metadata so it can be reused, stopped, rebuilt, or inspected.

### 6. HTTP Gateway

Gateway endpoints provide an operational way to consume the pool. Endpoint settings define listen host/port, session extraction rules, sticky TTL, missing-session behavior, and ordered hop pools.

At request time, the gateway extracts a session ID from configured headers/query params/rules, asks `ProxyChainService` for a route, ensures a local chain instance exists, and forwards the target request through that instance. This turns the stored/tested proxy inventory into live HTTP proxy behavior.

### 7. Web UI Operation

The Web UI is served from `/` and talks to the FastAPI API with `fetch()`. It is the main operator console for:

- Importing nodes and refreshing subscriptions.
- Starting tests and watching task progress.
- Filtering, copying, and deleting proxy nodes.
- Creating published subscriptions and proxy pools.
- Configuring chain filters, sticky routing, and route tests.
- Managing gateway endpoints.
- Managing backend routes, instances, and process status.

The UI does not own business logic. It reflects API/storage state and calls backend services through HTTP routes.

## Runtime Ownership

FastAPI owns process lifecycle. On startup, `create_app()` initializes service objects in `app.state`, starts configured gateway runtime, and prepares health/auto-task loops. On shutdown, it stops schedulers, backend processes, chain services, and gateway listeners.

The database is the main boundary between modules. Services communicate mostly by calling each other directly through objects created in `create_app()`, while persisted state allows the Web UI, API routes, background tasks, backend managers, and gateway runtime to observe the same proxy inventory and runtime configuration.

## Typical Operator Workflow

1. Add subscriptions or import source files from the Web UI.
2. Refresh subscriptions to populate `proxies`.
3. Run availability, speed, unlock, GeoIP, and IP purity tasks.
4. Filter good nodes into published subscriptions or chain front/exit pools.
5. Configure a proxy pool and gateway endpoint.
6. Start gateway/backend runtime.
7. Send client traffic through exported subscriptions, local backend ports, or HTTP gateway endpoints.
8. Periodically refresh sources and rerun tests so routing decisions stay current.

## Deployment Guides

- [Docker deployment](deploy/docker.md)
