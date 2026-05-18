# GeoIP Module

## Scope

The GeoIP module enriches tested proxy nodes with resolved IP, country/city metadata, IP purity scores, residential/datacenter classification signals, and OpenAI-style availability metadata where supported by probing code.

## Key Files

- `proxypool/geoip/service.py` defines `GeoIPService`, `GeoResult`, lookup helpers, parser helpers, and scoring logic.

## Implementation Notes

`GeoIPService.enrich_batch()` selects available and tested candidates from storage, resolves hostnames to IPs, looks up geographic metadata, and writes results back to SQLite. Work is parallelized with `ThreadPoolExecutor` and supports progress/cancellation callbacks from `TaskManager`.

`enrich_ip_purity_batch()` selects candidates for purity checks and combines multiple source-specific signals into a conservative score/level. Helper parsers normalize responses from services such as ip-api, ipinfo-style databases, IP2Location-style data, IPLark/IPPure-style flags, and generic network/ISP fields. Weighted scores are converted into coarse risk or residential classification labels before being persisted.

The service accepts injectable resolver, geo lookup, purity lookup, and proxy JSON fetcher functions. Tests use these hooks to avoid network dependence and to verify parsing/scoring behavior.

## Tests

Geo enrichment behavior is covered by `tests/test_geoip.py` and API task tests for GeoIP/IP purity task startup and progress.
