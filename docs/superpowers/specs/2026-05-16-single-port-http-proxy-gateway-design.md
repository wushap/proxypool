# Single-Port HTTP Proxy Gateway Design

## Overview

This design changes the current unified gateway from a path-based HTTP reverse gateway into a standard single-port HTTP proxy gateway.

After this change:

- administrators configure one global HTTP proxy gateway
- end users only configure `HTTP proxy = host:port` and `HTTPS proxy = host:port`
- the gateway decides routing internally
- sticky routing is session-oriented
- chained egress instances remain the data-plane foundation

The routing semantics reuse the useful parts of Resin's routing model without copying its client-facing identity protocol.

## Goals

- Replace the current `/proxy/{pool}/{scheme}/{host}/{path}` unified entry with a standard HTTP proxy entry.
- Keep a single global HTTP proxy listener as the main user-facing entry.
- Route by `session_key`, not by business account.
- Support sticky routing for normal HTTP requests and HTTPS `CONNECT` tunnels.
- Prefer stable egress IP reuse through same-IP rotation when possible.
- Reuse the current Python control plane, sticky lease storage, health checks, and chain instance runtime.
- Expose gateway configuration and testing through the web UI and control-plane API.
- Verify the full flow end to end, including configuration from the frontend.

## Non-Goals

- Do not expose Resin-style `platform.account` credentials to end users.
- Do not support multi-pool per-request routing in this phase.
- Do not make business headers visible inside an already-established `CONNECT` tunnel.
- Do not preserve the current `/proxy/...` path flow as the primary user experience.
- Do not move sticky-session logic into Mihomo itself.

## Current State

The repository already has the key control-plane pieces:

- `ProxyChainService` for route selection
- `StickyRouter` for sticky lease state
- `ChainInstanceManager` for durable chained egress instances
- `MihomoEgressBackend` for the preferred runtime backend
- `SessionExtractor` for HTTP metadata-based session extraction

The current gateway is not a standard proxy. It is a FastAPI route mounted at `/proxy/{pool_name}/{scheme}/{target_host}/{target_path:path}` and implemented by `UnifiedHttpGateway`.

That current shape has several hard limits:

- users must know an internal path protocol
- pool selection is path-bound
- the gateway is request-handler based instead of protocol-listener based
- `CONNECT` tunneling is not supported
- API middleware concerns are mixed with gateway concerns

## Confirmed Product Decisions

The following decisions were confirmed during design:

1. The user-facing entry is a single global HTTP proxy port.
2. The gateway uses one default pool in this phase.
3. Sticky routing does not distinguish business accounts; it only uses session identity.
4. For normal HTTP requests, session extraction priority is:
   - explicit proxy/session header
   - business headers or query parameters
   - configured host/path session rules
5. For `CONNECT`, business headers after tunnel establishment are unavailable, so only explicit proxy/session headers are visible before routing.
6. If a `CONNECT` request has no explicit session identity, routing falls back to connection-level stickiness.
7. Routing order is:
   - reuse a live bound instance if possible
   - reuse the existing sticky lease
   - rotate to another healthy node with the same egress IP if possible
   - create a new lease and instance

## Architecture

### Control Plane

The control plane remains Python-based and keeps ownership of:

- gateway configuration
- default pool selection
- session extraction rules
- sticky lease lifecycle
- chain route selection
- chained instance orchestration
- health and failover decisions

The relevant control-plane components are:

- `ProxyChainService`
  - owns route selection
  - remains the entry point for random vs sticky routing
- `StickyRouter`
  - owns lease hit, expiry, rotation, and new lease creation
- `ChainInstanceManager`
  - owns creation, start, stop, rebuild, and lookup of local chained instances
- `SessionExtractor`
  - remains the normal HTTP request extractor
  - is not used as-is for post-`CONNECT` inner traffic
- new `HttpGatewayConfigService`
  - owns the global HTTP gateway configuration and validation
- new `ForwardProxyGateway`
  - owns the user-facing proxy protocol listener

### Data Plane

The data plane has two layers:

- a single global HTTP proxy listener
- local chained egress instances created from `front + exit` routes

The gateway does not contain its own chain-selection algorithm. It delegates selection to the control plane and uses a chosen local chained instance for actual outbound traffic.

## Gateway Configuration Model

The current pool-scoped reverse-gateway fields are not the correct long-term control model for a standard proxy listener.

This phase introduces one global HTTP gateway configuration with at least:

- `enabled`
- `listen_host`
- `listen_port`
- `default_pool_id`
- `sticky_ttl_sec`
- `session_missing_action`
- `http_session_header_names`
- `http_session_query_names`
- `connect_session_header_names`

Optional future-facing fields may include:

- `proxy_auth_enabled`
- `proxy_auth_mode`
- `request_timeout_sec`

### Pool Model

`proxy_pools` remains the business routing and node-selection anchor, but it stops being the primary place where user entry semantics are defined.

In this phase:

- the global gateway points to one default pool
- pool session rules remain useful as fallback extractors for normal HTTP traffic
- reverse-gateway-specific entry fields such as `gateway_path_prefix` become deprecated

## Session Identity Model

### Sticky Key

The sticky key for the gateway becomes:

- `pool_id`
- `session_key`

`session_key` is opaque. The routing layer does not interpret business meaning from it.

### Normal HTTP Extraction

For normal HTTP requests, session extraction priority is:

1. explicit proxy/session headers
2. configured business headers or query parameters
3. longest-prefix host/path session rules
4. missing

If the configured action is:

- `RANDOM`, the gateway routes without creating a sticky lease
- `REJECT`, the gateway rejects the request

### CONNECT Extraction

For `CONNECT` requests, the gateway can only inspect data available before tunnel establishment.

Extraction priority is:

1. explicit proxy/session headers
2. missing

If missing:

- when action is `RANDOM`, the gateway creates a connection-scoped session key and keeps the tunnel sticky to one route
- when action is `REJECT`, the gateway rejects the tunnel request

This boundary is mandatory because the gateway cannot inspect inner HTTPS request headers after `200 Connection Established`.

## Routing Model

### Route Inputs

The routing layer should operate on a compact internal request model:

- `pool_id`
- `session_key`
- `target_host`
- `transport_kind`
- `connection_id`

`transport_kind` is either:

- `http_request`
- `connect_tunnel`

`connection_id` is used only when the gateway needs connection-level fallback stickiness.

### Random vs Sticky

The top-level branch follows Resin's useful rule:

- empty `session_key` => random route
- non-empty `session_key` => sticky route

### Instance-First Sticky Semantics

This project must go one step beyond Resin's node lease semantics because the actual data plane is a local managed chain instance.

Sticky reuse order is:

1. If the session already binds to a live local chained instance, reuse it directly.
2. Otherwise, check whether the existing sticky lease still maps to a healthy route and rebuild or reuse the expected instance.
3. Otherwise, attempt same-IP rotation to preserve egress IP.
4. Otherwise, select a fresh route and create a new lease.

This ensures the product sticks to a stable running route, not just a remembered logical node.

### Same-IP Rotation

If the original leased exit node is no longer usable, routing should prefer another healthy node with the same egress IP before creating a brand-new lease.

The stability target is the external egress IP, not a specific node identity.

## Request Flow

### Normal HTTP Flow

1. The client sends a standard HTTP proxy request to the global listener.
2. The gateway parses the absolute-form target URL.
3. The gateway resolves the default pool.
4. The gateway extracts `session_key`.
5. The gateway asks the control plane for a route.
6. The gateway reuses or creates a chained local instance.
7. The gateway forwards the HTTP request through that instance.
8. The gateway streams the upstream response back to the client.

### CONNECT Flow

1. The client sends `CONNECT host:port` to the global listener.
2. The gateway extracts `session_key` from explicit proxy headers if present.
3. If missing and allowed, the gateway creates a connection-scoped sticky key.
4. The gateway resolves the route and local chained instance.
5. The gateway opens a tunnel through that local instance to `host:port`.
6. The gateway returns `200 Connection Established`.
7. The gateway switches to bidirectional streaming until either side closes.

## Runtime Boundary

The standard HTTP proxy listener must not remain a plain FastAPI route handler.

Reasons:

- `CONNECT` requires tunnel semantics, not request/response buffering
- the current API middleware should not guard end-user proxy traffic
- standard forward proxy traffic is protocol-layer behavior, not path-routed business API behavior

The gateway should instead run as a dedicated listener owned by the application lifecycle. The FastAPI app remains the control plane.

## API Changes

The pool-scoped reverse-gateway config endpoints remain only as a temporary compatibility surface. The main control surface moves to dedicated gateway endpoints.

New or refactored endpoints should include:

- `GET /api/gateway/http-config`
- `PUT /api/gateway/http-config`
- `GET /api/gateway/http-status`
- `GET /api/gateway/http-leases`
- `GET /api/gateway/http-instances`
- `POST /api/gateway/http-test`

The status response should expose:

- listener state
- effective default pool
- active leases
- active chained instances
- recent gateway errors

## Frontend Changes

The UI changes from reverse-gateway path preview to standard proxy operations.

The new main gateway panel should show:

- enabled state
- listener host and port
- default pool
- session extraction rules
- missing-session policy
- active lease summary
- active instance summary
- health and recent failover state

The user-facing instructions should show how to configure:

- browser HTTP/HTTPS proxy
- CLI `http_proxy` and `https_proxy`
- programmatic proxy settings

The UI should also provide a real gateway test action that exercises the configured listener rather than generating a path preview.

## Migration and Compatibility

This design intentionally supersedes the earlier reverse-gateway design.

Migration rules:

- the new spec becomes the primary design reference
- reverse gateway support may remain temporarily for compatibility, but it is no longer the product direction
- existing pool session rules should be migrated or referenced by the global gateway config
- `gateway_path_prefix` should be deprecated in the UI and control plane

## Error Handling

The gateway should produce explicit failures for:

- gateway listener disabled
- default pool missing or invalid
- no healthy route available
- session required but missing
- local chained instance startup failure
- tunnel establishment failure

Operational failures should be visible through the status API and UI.

## Testing Scope

The implementation is not complete until the following are verified:

- unit tests for gateway config validation
- unit tests for normal HTTP session extraction priority
- unit tests for `CONNECT` session extraction and connection-level fallback
- unit tests for instance-first sticky reuse
- unit tests for same-IP rotation and lease replacement
- API tests for gateway config CRUD and status
- gateway integration tests for standard HTTP proxy request forwarding
- gateway integration tests for `CONNECT` tunneling
- frontend tests for the new gateway configuration panel
- a real end-to-end flow that configures the gateway from the frontend and successfully sends test traffic through it

## Risks and Constraints

- `CONNECT` support is the main protocol boundary and must be implemented as true tunneling.
- Instance liveness must be checked before trusting a persisted `instance_id`.
- Pool-scoped TTL and the current global `StickyRouter` TTL behavior need alignment.
- Existing reverse-gateway tests and UI assumptions will need controlled migration.
- End-to-end verification must include real runtime processes, not only mocked route-selection tests.

## Implementation Direction

Implementation should proceed in this order:

1. add the new gateway configuration model and API
2. add the dedicated forward-proxy listener and lifecycle management
3. adapt routing to instance-first sticky reuse
4. implement normal HTTP proxy forwarding
5. implement `CONNECT` tunneling
6. migrate frontend configuration and testing UI
7. run full end-to-end verification from the web UI

## Design Status

This design is approved and supersedes the earlier reverse-gateway-first direction for the unified entry point.
