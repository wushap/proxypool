# Proxy Chain Session Egress Design

## Overview

This design turns the current proxy-chain manager from a route-selection tool into a real chained proxy egress product with two delivery phases:

1. durable chained egress instances that listen on real local ports and carry traffic through `front -> exit`
2. a unified HTTP reverse-proxy gateway that extracts `session_id`, applies sticky routing, and forwards traffic through those chained instances

The design keeps route selection, health management, and sticky leasing in Python control-plane code, while using sing-box-backed chained instances as the data plane.

This design explicitly does not make the first unified entry point a generic forward proxy with arbitrary per-request session routing. The first unified entry point is an HTTP reverse-proxy gateway.

## Goals

- Expose real, usable chained proxy endpoints instead of only returning route suggestions.
- Support sticky routing by `session_id` rather than business account.
- Reuse the existing front-pool, exit-pool, health, and chain-builder logic as much as practical.
- Preserve egress IP when possible through same-IP rotation.
- Persist instance state and sticky leases across API restarts.
- Keep HTTP request parsing at the gateway edge, not inside the route-selection core.

## Non-Goals

- Do not make the first unified entry point a full generic HTTP forward proxy with dynamic per-request chain selection.
- Do not make `header/query`-based sticky routing work for SOCKS5 clients.
- Do not overload `proxy_pools_v2` with unified gateway configuration.
- Do not couple sing-box runtime config generation to HTTP request parsing.

## Current State

The repository already contains the main building blocks, but they are not yet assembled into a true egress product:

- `ProxyChainService` selects `front` and `exit` nodes and maintains sticky routing state.
- `StickyRouter` performs in-memory sticky routing keyed by `(account, pool_id)`.
- `ChainBuilder` can build a real sing-box config for a chained route.
- `SingBoxBackendManager` already knows how to manage durable sing-box instances and multi-hop routes.
- `ProxyPoolService` and `proxy_pools` already represent the business-facing pool control plane.

The main gap is that current `/api/chain/route` returns a routing result, but not a durable, client-usable chained proxy endpoint.

## Design Principles

- Separate identity extraction from sticky routing.
- Separate control plane from data plane.
- Treat `session_id` as an opaque sticky key.
- Keep HTTP-specific logic at the unified gateway edge.
- Prefer explicit session signals over implicit extraction.
- Reuse Resin-proven behaviors where they fit this codebase.

## Architecture

### Control Plane

The control plane remains Python-based and is responsible for:

- pool configuration
- front/exit node filtering
- health and circuit state
- sticky lease lifecycle
- real chained instance orchestration
- unified gateway configuration

The control-plane core is split into these units:

- `ProxyChainService`
  - owns route selection for chained exits
  - evolves from `(account, pool_id, target_domain)` to `(session_id, pool_id, target_domain)`
- `StickyRouter`
  - owns sticky lease creation, hit, expiry, same-IP rotation, and fallback reroute
- `ChainEgressManager`
  - new component
  - creates, starts, stops, rebuilds, and restores durable chained sing-box instances
- `SessionExtractor`
  - new HTTP-facing component
  - extracts `session_id` from request metadata for the unified gateway
- `ProxyPoolService`
  - remains the business-facing pool control plane
  - becomes the place where unified gateway and sticky-session settings are stored

### Data Plane

The data plane has two layers:

- chained sing-box egress instances
  - real listening ports
  - each instance binds one `front_node + exit_node + inbound_type + listen + port`
- unified HTTP gateway
  - accepts business traffic
  - extracts `session_id`
  - resolves or creates a sticky lease
  - forwards via an existing or newly created chained instance

The gateway does not implement chain selection internally. It delegates selection to the control plane and forwards through resolved chained instances.

## Delivery Phases

### Phase 1: Durable Chained Egress Instances

Phase 1 produces real chained proxy endpoints.

Each instance:

- has a stable `instance_id`
- listens on a real local address and port
- is backed by a sing-box process
- is built from a selected `front` and `exit` node pair
- can be started, stopped, rebuilt, and restored after restart

API callers can obtain a real local proxy address that clients can connect to directly.

This phase is the mandatory foundation for all later unified-entry behavior.

### Phase 2: Unified HTTP Reverse-Proxy Gateway

Phase 2 adds a single HTTP entry point per pool or per configured path prefix.

The gateway:

- receives HTTP requests for an upstream target
- extracts `session_id`
- resolves a sticky lease for `(pool_id, session_id)`
- reuses or creates a chained egress instance
- forwards the request through that chained instance

Phase 2 intentionally starts as HTTP reverse proxy only. It does not try to provide a generic single-port forward proxy with `header/query`-based session routing.

## Session Identity Model

### Sticky Key

The sticky key becomes:

- `pool_id`
- `session_id`

`session_id` is opaque. The routing layer does not interpret it semantically.

### Session Extraction Priority

For unified HTTP gateway traffic, session extraction follows this priority:

1. explicit session header
2. explicit query parameter
3. URL-prefix-based business-header extraction rule
4. no session found

Recommended defaults:

- header: `X-ProxyPool-Session`
- query parameter: `session`

### Missing Session Behavior

Per pool, missing session behavior is configurable:

- `RANDOM`
  - do not create a sticky lease
  - route randomly through the pool
- `REJECT`
  - return an explicit error

### Why This Boundary Exists

This is intentionally limited to the HTTP gateway because:

- SOCKS5 has no request headers or query parameters
- forward-proxy `CONNECT` traffic cannot reliably expose the target application's later headers to the proxy
- the existing sing-box data plane cannot see per-request HTTP metadata once clients connect directly to a port

This design therefore keeps `header/query` session extraction only at the gateway edge.

## Resin-Derived Behaviors To Reuse

The Resin reference implementation validates several behaviors worth preserving here:

- explicit identity header has highest priority
- header-rule extraction is a fallback, not the primary mode
- sticky leases are keyed by `(platform, account)`; here this becomes `(pool_id, session_id)`
- same-egress-IP rotation is preferred when the current node dies but the egress IP can be preserved
- lease persistence and restart recovery are weakly persisted and restored on bootstrap
- lease inheritance is useful for replacing a temporary identity with a stable one

This design reuses the behavior, not the exact naming.

## Component Design

### StickyRouter

`StickyRouter` changes from an account-oriented lease table to a session-oriented lease table.

Current shape:

- key: `(account, pool_id)`
- value: exit node lease

New shape:

- key: `(session_id, pool_id)`
- value: sticky lease bound to an exit identity and optionally an active instance

The router remains responsible for:

- lease hit
- expiry
- same-IP rotation
- random fallback
- IP load accounting

The router should not parse HTTP headers or query parameters.

### ChainEgressManager

`ChainEgressManager` is a new manager responsible for real chained instance lifecycle.

Responsibilities:

- allocate or validate listen ports
- build config through `ChainBuilder`
- start and stop sing-box child processes
- persist instance metadata
- restore instances after API restart
- rebuild an instance to a new `front/exit` pair
- report liveness and last error

It should follow the style of `SingBoxBackendManager`, but manage chain instances as first-class objects rather than generic static route files.

### SessionExtractor

`SessionExtractor` is a new helper used only by the unified HTTP gateway.

Responsibilities:

- read configured session header names in order
- read configured query parameter names in order
- match URL-prefix header rules when no explicit session is present
- return `(session_id, source, extraction_failed)`

It should support host/path longest-prefix matching for header rules, mirroring the Resin approach.

### Unified HTTP Gateway

The gateway is a thin HTTP reverse-proxy layer.

Responsibilities:

- parse upstream target from the reverse-proxy path shape
- extract `session_id`
- look up pool config
- call `ProxyChainService.route_request(session_id, pool_id, target_domain)`
- resolve or create an egress instance
- forward the request through that instance
- strip internal session headers before the upstream request is sent

The gateway does not own sticky state itself.

## Data Model

### Extend `proxy_pools`

Add these fields to `proxy_pools`:

- `chain_enabled`
- `sticky_ttl_sec`
- `session_missing_action`
- `session_header_names_json`
- `session_query_param_names_json`
- `gateway_path_prefix`

Purpose:

- this is the business-facing resource that owns chain-gateway behavior
- it already has CRUD and service-layer orchestration

### New `pool_session_header_rules`

Fields:

- `pool_id`
- `url_prefix`
- `headers_json`
- `updated_at`

Primary key:

- `(pool_id, url_prefix)`

Purpose:

- longest-prefix match by `host/path`
- defines which business headers should be inspected to derive `session_id`

Examples:

- `api.example.com/v1` -> `["Authorization"]`
- v1 does not support wildcard prefixes; only exact host/path prefix matching is allowed

### Rework `sticky_leases`

Current schema uses:

- `account`
- `pool_id`

New schema uses:

- `session_id`
- `pool_id`
- `instance_id`
- `exit_node_key`
- `egress_ip`
- `expires_at`
- `last_accessed`

Primary key:

- `(pool_id, session_id)`

Purpose:

- persist sticky binding
- persist which egress instance currently serves the lease

### New `chain_egress_instances`

Fields:

- `instance_id`
- `pool_id`
- `front_node_key`
- `exit_node_key`
- `listen`
- `port`
- `inbound_type`
- `status`
- `pid`
- `config_file`
- `log_file`
- `egress_ip`
- `last_error`
- `updated_at`

Purpose:

- durable catalog of chained egress instances

## API Design

### Keep Existing Low-Level Chain APIs

Current `/api/chain/*` routes remain as low-level inspection and debugging tools for front/exit pool management and route tests.

They are not the business-facing unified gateway control plane.

### New Pool-Centric Chain Config APIs

- `GET /api/pools/{pool_id}/chain`
  - returns chain config, gateway config, instance summary, and lease summary
- `PUT /api/pools/{pool_id}/chain`
  - updates chain enablement, sticky TTL, session extraction config, and missing-session behavior

### Session Rule APIs

- `GET /api/pools/{pool_id}/chain/session-rules`
- `PUT /api/pools/{pool_id}/chain/session-rules/{url_prefix...}`
- `DELETE /api/pools/{pool_id}/chain/session-rules/{url_prefix...}`

These mirror the Resin-style longest-prefix rule model, but scoped per pool.

### Egress Instance APIs

- `GET /api/pools/{pool_id}/chain/instances`
- `POST /api/pools/{pool_id}/chain/instances`
- `POST /api/pools/{pool_id}/chain/instances/{instance_id}/start`
- `POST /api/pools/{pool_id}/chain/instances/{instance_id}/stop`
- `POST /api/pools/{pool_id}/chain/instances/{instance_id}/rebuild`

### Lease APIs

- `GET /api/pools/{pool_id}/chain/leases`
- `DELETE /api/pools/{pool_id}/chain/leases/{session_id}`
- `POST /api/pools/{pool_id}/chain/leases/inherit`

`inherit` copies the sticky binding from a temporary `session_id` to a stable `session_id`.

### Route Test API

- `GET /api/pools/{pool_id}/chain/route-test?session_id=&target_domain=`

This is for debugging only. It does not proxy real traffic.

### Unified HTTP Gateway Entry

Recommended initial path shape:

- `/proxy/{pool_name}/https/{target_host}/{path...}`
- `/proxy/{pool_name}/http/{target_host}/{path...}`

The gateway:

- identifies the target URL
- extracts `session_id`
- strips internal session headers
- forwards through the selected chained instance

## Traffic Flow

### Phase 1 Traffic Flow

1. control-plane client creates or requests a chain instance
2. `ProxyChainService` selects `front + exit`
3. `ChainEgressManager` builds config and starts sing-box
4. instance listens on a real local port
5. external clients can connect directly to that port

### Phase 2 Traffic Flow

1. client calls the unified HTTP gateway
2. gateway extracts `session_id`
3. gateway identifies `pool_id`
4. gateway calls route-selection core
5. sticky router returns an existing or new sticky binding
6. egress manager resolves or creates a real chained instance
7. gateway forwards the request through that instance
8. internal session header is stripped before upstream delivery

## Failure Handling

### Lease Invalidation Conditions

Invalidate a lease when:

- TTL has expired
- bound instance process died
- bound port is no longer healthy
- exit node is no longer healthy
- chained `front -> exit` path fails probing
- egress IP changed and same-IP replacement is unavailable
- node is no longer eligible for the pool

### Lease Reuse Decision Order

When a request arrives for an existing sticky lease:

1. if the bound instance is alive and still yields the same egress IP, reuse it
2. if the instance is dead but another valid chain can preserve the same egress IP, rebuild onto that replacement
3. if same-IP preservation is impossible, reroute and replace the lease
4. if no valid chain exists, fail explicitly

No silent direct-exit downgrade is allowed.

### Restart Recovery

On API restart:

1. restore pool chain config
2. restore instance catalog
3. restore sticky leases
4. restore desired-running state for instances
5. lazily validate restored leases on first hit
6. run background cleanup for expired or dead leases

Recovery should be lazy for stale leases. Do not full-scan and eagerly rebuild all leases at startup.

### Header Safety

Any internal session header used for routing must be stripped before the upstream request is sent.

This mirrors Resin’s behavior and avoids leaking control-plane routing metadata to origin services.

## Error Semantics

- missing session with `REJECT`: `400` or `401` depending on entrypoint auth design
- no available chain route: `503`
- route selected but instance startup failed: `502` or `503`
- session extraction rule required but extraction failed:
  - `REJECT` => explicit failure
  - `RANDOM` => non-sticky routing

## Testing Strategy

### Unit Tests

- session extraction priority
- URL-prefix header-rule matching
- sticky lease hit
- expiry
- same-IP rotation
- lease inheritance
- header stripping before upstream forwarding

### Service Tests

- `ProxyChainService` plus `ChainEgressManager` integration
- instance crash and rebuild
- restore instance catalog after restart
- restore sticky leases after restart

### API Tests

- `GET/PUT /api/pools/{pool_id}/chain`
- session-rule CRUD
- lease list/delete/inherit
- route-test behavior

### End-to-End Tests

- stable `session_id` yields stable egress IP
- missing session with `RANDOM` does not create lease
- missing session with `REJECT` fails explicitly
- broken exit node triggers same-IP rotation when possible
- internal session header does not reach upstream origin

## Implementation Boundaries

This design intentionally chooses these boundaries:

- `header/query`-based session routing only exists in the unified HTTP gateway
- `StickyRouter` never sees HTTP request objects
- `proxy_pools` is the control-plane anchor for business-facing chain gateway config
- `proxy_pools_v2` remains front/exit classification only
- Phase 2 first supports HTTP reverse proxy, not a generic dynamic forward proxy

## Recommended Implementation Order

1. introduce `chain_egress_instances` and `ChainEgressManager`
2. expose durable chained instance APIs
3. convert sticky routing from `account` to `session_id`
4. attach sticky lease persistence to runtime behavior
5. extend `proxy_pools` with session-gateway config
6. add session-rule storage and matching
7. add the unified HTTP gateway
8. add lease inheritance API
9. complete restart recovery and end-to-end verification

## Open Decisions Resolved

These decisions are fixed by this design:

- sticky key is session-based, not account-based
- unified entrypoint v1 is HTTP reverse proxy
- explicit session header is the preferred signal
- query parameter support is optional fallback, not the only mechanism
- Resin-style header-rule fallback is included
- same-IP rotation is required behavior
- control-plane config lives under `proxy_pools`

## References

- Resin README: `https://github.com/Resinat/Resin/blob/master/README.zh-CN.md`
- Resin design document: `https://github.com/Resinat/Resin/blob/master/DESIGN.md`
- RFC 1929: `https://www.rfc-editor.org/rfc/rfc1929`
- RFC 9110: `https://www.rfc-editor.org/rfc/rfc9110`
- curl man page: `https://curl.se/docs/manpage.html`
