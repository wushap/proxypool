from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from proxypool.collector.fetcher import FetchError, fetch_text, fetch_text_via_proxy_node
from proxypool.collector.parser import parse_source_content
from proxypool.storage.sqlite import SQLiteProxyStorage


@dataclass(slots=True)
class SourceCollectReport:
    source: str
    parsed: int = 0
    inserted: int = 0
    updated: int = 0
    deduped: int = 0
    invalid: int = 0


@dataclass(slots=True)
class CollectReport:
    total_sources: int = 0
    total_parsed: int = 0
    total_inserted: int = 0
    total_updated: int = 0
    total_deduped: int = 0
    total_invalid: int = 0
    by_source: list[SourceCollectReport] = field(default_factory=list)


class CollectorService:
    def __init__(self, storage: SQLiteProxyStorage, singbox_binary: str = "sing-box") -> None:
        self.storage = storage
        self.singbox_binary = singbox_binary

    def collect_from_text_items(self, items: list[tuple[str, str]], timeout_sec: float = 12.0) -> CollectReport:
        report = CollectReport(total_sources=0)
        for filename, text in items:
            safe_name = str(filename or "upload.txt")
            source = f"upload:{safe_name}"
            sub = self._collect_one_text_source_with_subscription_sources(
                text=text,
                source=source,
                source_name=safe_name,
                timeout_sec=timeout_sec,
            )
            _merge_collect_reports(report, sub)
        return report

    def collect_from_files(self, paths: list[Path], timeout_sec: float = 12.0) -> CollectReport:
        report = CollectReport(total_sources=0)

        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore")
            sub = self._collect_one_text_source_with_subscription_sources(
                text=text,
                source=str(path),
                source_name=path.name,
                timeout_sec=timeout_sec,
            )
            _merge_collect_reports(report, sub)

        return report

    def collect_from_urls(self, urls: list[str], timeout_sec: float = 12.0) -> CollectReport:
        report = CollectReport(total_sources=len(urls))

        for url in urls:
            source_report = SourceCollectReport(source=url)
            try:
                text = fetch_text(url, timeout_sec=timeout_sec)
            except FetchError:
                source_report.invalid = 1
                _merge_collect_report(report, source_report)
                continue

            parsed_report = self._collect_one_text_source(text=text, source=url, source_name=url)
            _merge_collect_report(report, parsed_report)

        return report

    def collect_from_subscription(
        self,
        subscription_id: int,
        subscription_name: str,
        subscription_url: str,
        timeout_sec: float = 12.0,
    ) -> CollectReport:
        report = CollectReport(total_sources=1)
        tag = f"subscription#{int(subscription_id)}:{(subscription_name or 'subscription').strip()}|{subscription_url}"
        source_report = SourceCollectReport(source=tag)
        source_name = f"subscription-{int(subscription_id)}"
        proxy_source_report: SourceCollectReport | None = None
        try:
            proxy_key = str(self.storage.get_subscription_update_proxy_key() or "").strip()
            text = ""
            if proxy_key:
                proxy = self.storage.get_proxy_by_key(proxy_key)
                if proxy is not None:
                    try:
                        text = fetch_text_via_proxy_node(
                            subscription_url,
                            proxy_node=proxy,
                            timeout_sec=timeout_sec,
                            singbox_binary=self.singbox_binary,
                        )
                    except FetchError:
                        # Fallback to direct fetch when update proxy is temporarily unavailable.
                        text = ""
                if text:
                    proxy_source_report = self._collect_one_text_source(
                        text=text,
                        source=tag,
                        source_name=source_name,
                    )
                    if _source_report_has_success(proxy_source_report):
                        _merge_collect_report(report, proxy_source_report)
                        return report
                    text = ""
            if not text:
                text = fetch_text(subscription_url, timeout_sec=timeout_sec)
        except FetchError:
            if proxy_source_report is not None:
                _merge_collect_report(report, proxy_source_report)
                return report
            source_report.invalid = 1
            _merge_collect_report(report, source_report)
            return report

        parsed_report = self._collect_one_text_source(
            text=text,
            source=tag,
            source_name=source_name,
        )
        _merge_collect_report(report, parsed_report)
        return report

    def collect_from_sources(self, sources: list[str], timeout_sec: float = 12.0) -> CollectReport:
        report = CollectReport(total_sources=len(sources))
        for source in sources:
            if source.startswith(("http://", "https://", "data:", "file://")):
                sub = self.collect_from_urls([source], timeout_sec=timeout_sec)
            else:
                path = Path(source).expanduser().resolve()
                if path.exists():
                    sub = self.collect_from_files([path], timeout_sec=timeout_sec)
                else:
                    invalid = CollectReport(total_sources=1)
                    invalid.by_source.append(SourceCollectReport(source=source, invalid=1))
                    invalid.total_invalid = 1
                    sub = invalid

            report.total_parsed += sub.total_parsed
            report.total_inserted += sub.total_inserted
            report.total_updated += sub.total_updated
            report.total_deduped += sub.total_deduped
            report.total_invalid += sub.total_invalid
            report.by_source.extend(sub.by_source)

        return report

    def _collect_one_text_source_with_subscription_sources(
        self,
        text: str,
        source: str,
        source_name: str,
        timeout_sec: float = 12.0,
    ) -> CollectReport:
        report = CollectReport(total_sources=1)
        source_refs, remaining_text = _extract_subscription_source_refs(text)
        source_report = self._collect_one_text_source(
            text=remaining_text,
            source=source,
            source_name=source_name,
        )
        _merge_collect_report(report, source_report)

        if source_refs:
            nested = self._collect_subscription_refs(source_refs, source_name=source_name, timeout_sec=timeout_sec)
            _merge_collect_reports(report, nested)

        return report

    def _collect_subscription_refs(
        self,
        refs: list[str],
        source_name: str,
        timeout_sec: float = 12.0,
    ) -> CollectReport:
        report = CollectReport(total_sources=0)
        for idx, ref in enumerate(refs, start=1):
            if str(ref).startswith(("http://", "https://")):
                subscription = self._ensure_subscription_for_url(ref, source_name=source_name, index=idx)
                sub_report = self.collect_from_subscription(
                    subscription_id=int(subscription["id"]),
                    subscription_name=str(subscription.get("name") or ""),
                    subscription_url=str(subscription.get("url") or ""),
                    timeout_sec=timeout_sec,
                )
                status, error = _collect_status_and_error(sub_report)
                self.storage.mark_subscription_result(
                    subscription_id=int(subscription["id"]),
                    status=status,
                    error=error,
                    parsed=sub_report.total_parsed,
                    inserted=sub_report.total_inserted,
                    updated=sub_report.total_updated,
                    invalid=sub_report.total_invalid,
                    deduped=sub_report.total_deduped,
                )
                _merge_collect_reports(report, sub_report)
                continue

            # data:/file:// source refs are still imported, but not persisted as managed subscriptions.
            sub = self.collect_from_sources([ref], timeout_sec=timeout_sec)
            _merge_collect_reports(report, sub)

        return report

    def _ensure_subscription_for_url(self, url: str, source_name: str, index: int) -> dict:
        existed = self.storage.get_subscription_by_url(url)
        if existed is not None:
            return existed

        name = _auto_subscription_name(url, source_name=source_name, index=index)
        try:
            return self.storage.create_subscription(name=name, url=url, enabled=True)
        except Exception:
            retry = self.storage.get_subscription_by_url(url)
            if retry is not None:
                return retry
            raise

    def _collect_one_text_source(self, text: str, source: str, source_name: str) -> SourceCollectReport:
        source_report = SourceCollectReport(source=source)

        nodes, invalid = parse_source_content(text, source_name=source_name)
        source_report.parsed = len(nodes)
        source_report.invalid = len(invalid)
        seen_keys: set[str] = set()

        for node in nodes:
            key = node.normalized_key()
            if key in seen_keys:
                source_report.deduped += 1
                continue
            seen_keys.add(key)
            status = self.storage.upsert_proxy(node, source=source)
            if status == "inserted":
                source_report.inserted += 1
            else:
                source_report.updated += 1

        return source_report


def _merge_collect_report(report: CollectReport, source_report: SourceCollectReport) -> None:
    report.by_source.append(source_report)
    report.total_parsed += source_report.parsed
    report.total_inserted += source_report.inserted
    report.total_updated += source_report.updated
    report.total_deduped += source_report.deduped
    report.total_invalid += source_report.invalid


def _merge_collect_reports(target: CollectReport, source: CollectReport) -> None:
    target.total_sources += source.total_sources
    target.total_parsed += source.total_parsed
    target.total_inserted += source.total_inserted
    target.total_updated += source.total_updated
    target.total_deduped += source.total_deduped
    target.total_invalid += source.total_invalid
    target.by_source.extend(source.by_source)


def _extract_subscription_source_refs(text: str) -> tuple[list[str], str]:
    refs: list[str] = []
    seen: set[str] = set()
    kept_lines: list[str] = []
    for line in text.replace("\ufeff", "").splitlines():
        stripped = line.strip()
        if _is_subscription_source_ref(stripped):
            if stripped not in seen:
                seen.add(stripped)
                refs.append(stripped)
            continue
        kept_lines.append(line)
    return refs, "\n".join(kept_lines)


def _is_subscription_source_ref(line: str) -> bool:
    text = str(line or "").strip()
    if not text:
        return False
    if any(ch.isspace() for ch in text):
        return False
    if text.startswith(("data:", "file://")):
        return True
    if not text.startswith(("http://", "https://")):
        return False

    split = urlsplit(text)
    if not split.netloc:
        return False
    # Exclude classic HTTP proxy shares like http://user:pass@ip:port#name
    if "@" in split.netloc or split.fragment:
        return False
    has_path = str(split.path or "").strip() not in {"", "/"}
    has_query = bool(split.query)
    if not has_path and not has_query:
        return False
    return True


def _auto_subscription_name(url: str, source_name: str, index: int) -> str:
    split = urlsplit(str(url or ""))
    host = (split.netloc or "").strip() or "subscription"
    path = str(split.path or "").strip("/")
    tail = path.split("/")[-1] if path else ""
    core = f"{host}/{tail}" if tail else host
    safe_source = str(source_name or "upload").strip() or "upload"
    return f"auto:{safe_source}:{index}:{core}"


def _collect_status_and_error(report: CollectReport) -> tuple[str, str]:
    if report.total_parsed > 0 or report.total_inserted > 0 or report.total_updated > 0:
        return "success", ""
    if report.total_invalid > 0:
        return "failed", "empty or invalid subscription content"
    return "success", ""


def _source_report_has_success(source_report: SourceCollectReport) -> bool:
    return source_report.parsed > 0 or source_report.inserted > 0 or source_report.updated > 0
