# Gateway Module

## Scope

The gateway module exposes runtime HTTP forwarding through configured proxy pool chains. It handles endpoint configuration, session extraction, sticky route binding, CONNECT session tracking, and runtime start/stop of local forward proxy listeners.

## Key Files

- `proxypool/gateway/http_gateway.py` defines `UnifiedHttpGateway` for API-mounted gateway requests.
- `proxypool/gateway/forward_proxy.py` implements the local forward proxy behavior.
- `proxypool/gateway/runtime.py` manages configured gateway listener processes/servers.
- `proxypool/gateway/config.py` and `config_service.py` define persisted gateway settings.
- `proxypool/gateway/session_extractor.py` extracts session IDs from headers, query params, and rules.
- `proxypool/gateway/connect_session.py` tracks CONNECT request session metadata.

## Implementation Notes

`UnifiedHttpGateway.handle()` is used by the FastAPI route mounted under `/api/gateway/{pool_name}/{scheme}/{target_host}/{target_path}`. It finds the target pool, verifies chain mode is enabled, selects an HTTP endpoint, extracts a session ID, obtains a route from `ProxyChainService`, ensures a running chain instance via `ChainInstanceManager`, then forwards the request through the instance's local HTTP proxy.

The forward proxy runtime is separate from API-mounted forwarding. `ForwardProxyGatewayRuntimeManager` reads persisted HTTP proxy endpoint settings, starts listeners for enabled endpoints, and updates endpoint status in storage. Endpoint hops define the ordered proxy pools used for multi-hop routes.

Session behavior is controlled by endpoint and pool settings. Missing sessions can be rejected or routed randomly. Sticky leases are persisted so repeated requests with the same session can reuse the same egress route.

## Tests

Gateway behavior is covered by `tests/test_gateway_config.py`, `tests/test_http_gateway.py`, `tests/test_forward_proxy_gateway.py`, and chain/pool tests that exercise route selection and endpoint state.
