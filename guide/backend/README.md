# Backend Module

## Scope

The backend module manages local egress proxy engines and generated runtime configuration. It supports the legacy/default sing-box process model and mihomo-backed chain egress instances.

## Key Files

- `proxypool/backend/singbox_manager.py` defines `SingBoxRoute` and `SingBoxBackendManager`.
- `proxypool/backend/chain_instance_manager.py` coordinates persisted chain egress instances.
- `proxypool/backend/egress_backend.py` defines backend protocol dataclasses used by chain instance management.
- `proxypool/backend/mihomo_manager.py` starts/stops mihomo processes for chain instances.
- `proxypool/backend/mihomo_config.py` builds mihomo YAML proxy chains.

## Implementation Notes

`SingBoxBackendManager` owns route files, generated sing-box runtime config, process lifecycle, health checks, process-event recording, and named backend instances. A `SingBoxRoute` maps one local inbound port/listen address to either a single `proxy_key` or an ordered front/middle/exit chain. Runtime config generation reads proxy rows from storage and converts them into sing-box outbound definitions via `tester.singbox.build_singbox_outbound()`.

Named sing-box instances persist metadata in the `backend_instances` table and use per-instance route/config/log files. The manager validates port/listen settings, starts subprocesses, stops them gracefully, and records lifecycle events in storage.

For chain egress, `ChainInstanceManager` uses an `EgressBackend` implementation. The current concrete implementation is `MihomoEgressBackend`, which writes one YAML config per chain instance and starts `mihomo -f <config>`. Config construction in `mihomo_config.py` handles protocol-specific proxy fields, TLS/network options, and chained dialer settings.

## External Dependencies

The module depends on installed `sing-box` and/or `mihomo` binaries. Paths are configured by `PROXYPOOL_SINGBOX_BINARY` and `PROXYPOOL_MIHOMO_BINARY`, with defaults resolved in `proxypool/settings.py`.

## Tests

Relevant coverage includes `tests/test_backend_manager.py`, `tests/test_backend_port_range.py`, `tests/test_mihomo_manager.py`, `tests/test_chain_instance_manager.py`, and gateway/chain integration tests.
