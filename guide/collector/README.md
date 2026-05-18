# Collector Module

## Scope

The collector module imports proxy nodes from pasted text, uploaded/local files, URLs, managed subscriptions, and mixed source lists. It parses source formats, deduplicates nodes, and writes import results to SQLite.

## Key Files

- `proxypool/collector/service.py` defines `CollectorService`, `CollectReport`, and per-source reporting.
- `proxypool/collector/parser.py` parses raw proxy links, base64 subscriptions, and Clash YAML.
- `proxypool/collector/fetcher.py` fetches remote content directly or through a proxy node.

## Implementation Notes

`CollectorService` is the orchestration layer. It accepts text items, filesystem paths, URLs, source references, and stored subscriptions, then delegates content parsing to `parse_source_content()`. Parsed `ProxyNode` objects are upserted through `SQLiteProxyStorage`; duplicate and invalid entries are counted in `CollectReport`.

Uploaded text and local files can contain subscription source references. `_extract_subscription_source_refs()` splits those references from inline proxy content, persists HTTP references as managed subscriptions, and recursively refreshes them. Managed subscription refresh supports an optional update proxy key stored in app settings; when configured, `fetch_text_via_proxy_node()` tries to fetch the subscription through that proxy and falls back to direct fetch if needed.

`parser.py` supports common share link formats such as vmess, ss, ssr, trojan/vless-like URL schemes, base64 encoded subscription blocks, and Clash YAML `proxies` sections. Parsed nodes are normalized into `ProxyNode` dataclasses with `protocol`, host/port, raw link, source, name, and protocol-specific `extra` fields.

## Tests

Collector behavior is covered by `tests/test_collector.py`, `tests/test_collector_sources.py`, `tests/test_parser.py`, and `tests/test_fetcher.py`.
