# Tester Module

## Scope

The tester module probes proxy availability, latency, speed, OpenAI unlock status, and chained fallback connectivity using sing-box-backed local test processes.

## Key Files

- `proxypool/tester/service.py` defines `TesterService`, batch reports, and selection helpers.
- `proxypool/tester/singbox.py` defines `SingboxProber`, `ProbeResult`, `SpeedTestResult`, and sing-box outbound config generation.

## Implementation Notes

`TesterService.run_one()` loads a proxy by normalized key, optionally prepares fallback front proxies, probes it, and writes availability, latency, unlock status, fallback front keys, and errors back to storage.

`run_batch()` selects candidates through storage filters, limits concurrency with an asyncio semaphore when async prober methods are available, updates progress callbacks, optionally probes failed exits through fallback front proxies, and deletes stale unavailable nodes after the run. It can call `replace_failed_proxy_cb`, wired in `api.app` to `SingBoxBackendManager.replace_failed_exit_proxy()`, to replace failed backend routes with available proxies.

`SingboxProber` builds temporary sing-box configs, starts local inbound proxies, executes HTTP/curl-style probes, parses timing and speed metrics, and tears down processes. If sing-box support is unavailable in a specific path, tests and runtime guards cover fallback/error handling.

## Tests

Tester behavior is covered by `tests/test_tester.py`, `tests/test_api_tester_filters.py`, `tests/test_api_single_proxy_test.py`, and speed/openai task tests in the API suite.
