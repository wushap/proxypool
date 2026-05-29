"""Tests for proxypool.collector.service – fill coverage gaps."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from proxypool.collector.fetcher import FetchError
from proxypool.collector.service import (
    CollectorService,
    CollectReport,
    SourceCollectReport,
    _auto_subscription_name,
    _collect_status_and_error,
    _extract_subscription_source_refs,
    _is_subscription_source_ref,
    _merge_collect_report,
    _merge_collect_reports,
    _source_report_has_success,
)
from proxypool.security.file_validator import PathTraversalError
from proxypool.storage.sqlite import SQLiteProxyStorage


# ---------------------------------------------------------------------------
# Helper to build a minimal CollectorService backed by a real SQLite DB
# ---------------------------------------------------------------------------
def _make_service(tmp: Path, **kwargs) -> tuple[CollectorService, SQLiteProxyStorage]:
    db = tmp / "db.sqlite3"
    storage = SQLiteProxyStorage(db)
    service = CollectorService(storage, **kwargs)
    return service, storage


class TestCollectReportDataclasses(unittest.TestCase):
    """Cover CollectReport / SourceCollectReport defaults and merge helpers."""

    def test_collect_report_defaults(self) -> None:
        r = CollectReport()
        self.assertEqual(r.total_sources, 0)
        self.assertEqual(r.total_parsed, 0)
        self.assertEqual(r.by_source, [])

    def test_source_collect_report_defaults(self) -> None:
        r = SourceCollectReport(source="x")
        self.assertEqual(r.source, "x")
        self.assertEqual(r.parsed, 0)

    def test_merge_collect_report(self) -> None:
        report = CollectReport()
        sub = SourceCollectReport(source="a", parsed=3, inserted=2, updated=1, deduped=1, invalid=1)
        _merge_collect_report(report, sub)
        self.assertEqual(report.total_parsed, 3)
        self.assertEqual(report.total_inserted, 2)
        self.assertEqual(report.total_updated, 1)
        self.assertEqual(report.total_deduped, 1)
        self.assertEqual(report.total_invalid, 1)
        self.assertIn(sub, report.by_source)

    def test_merge_collect_reports(self) -> None:
        target = CollectReport(total_sources=1)
        src = CollectReport(
            total_sources=2,
            total_parsed=5,
            total_inserted=3,
            total_updated=2,
            total_deduped=1,
            total_invalid=1,
        )
        src.by_source.append(SourceCollectReport(source="b"))
        _merge_collect_reports(target, src)
        self.assertEqual(target.total_sources, 3)
        self.assertEqual(target.total_parsed, 5)
        self.assertEqual(len(target.by_source), 1)


class TestSourceReportHasSuccess(unittest.TestCase):
    def test_no_success(self) -> None:
        r = SourceCollectReport(source="x", parsed=0, inserted=0, updated=0)
        self.assertFalse(_source_report_has_success(r))

    def test_parsed_positive(self) -> None:
        r = SourceCollectReport(source="x", parsed=1)
        self.assertTrue(_source_report_has_success(r))

    def test_inserted_positive(self) -> None:
        r = SourceCollectReport(source="x", inserted=1)
        self.assertTrue(_source_report_has_success(r))

    def test_updated_positive(self) -> None:
        r = SourceCollectReport(source="x", updated=1)
        self.assertTrue(_source_report_has_success(r))


class TestCollectStatusAndError(unittest.TestCase):
    def test_success_when_parsed(self) -> None:
        r = CollectReport(total_parsed=1)
        self.assertEqual(_collect_status_and_error(r), ("success", ""))

    def test_success_when_inserted(self) -> None:
        r = CollectReport(total_inserted=1)
        self.assertEqual(_collect_status_and_error(r), ("success", ""))

    def test_success_when_updated(self) -> None:
        r = CollectReport(total_updated=1)
        self.assertEqual(_collect_status_and_error(r), ("success", ""))

    def test_failed_when_invalid(self) -> None:
        r = CollectReport(total_invalid=1)
        status, error = _collect_status_and_error(r)
        self.assertEqual(status, "failed")
        self.assertIn("invalid", error)

    def test_success_when_empty(self) -> None:
        r = CollectReport()
        self.assertEqual(_collect_status_and_error(r), ("success", ""))


class TestIsSubscriptionSourceRef(unittest.TestCase):
    def test_empty_string(self) -> None:
        self.assertFalse(_is_subscription_source_ref(""))

    def test_whitespace_only(self) -> None:
        self.assertFalse(_is_subscription_source_ref("   "))

    def test_line_with_spaces(self) -> None:
        self.assertFalse(_is_subscription_source_ref("hello world"))

    def test_data_url(self) -> None:
        self.assertTrue(_is_subscription_source_ref("data:text/plain,abc"))

    def test_file_ref(self) -> None:
        self.assertTrue(_is_subscription_source_ref("file:///tmp/nodes.txt"))

    def test_non_http_scheme(self) -> None:
        self.assertFalse(_is_subscription_source_ref("ftp://example.com/file"))

    def test_http_no_netloc(self) -> None:
        self.assertFalse(_is_subscription_source_ref("http://"))

    def test_http_with_at_in_netloc(self) -> None:
        # Classic proxy share: http://user:pass@ip:port#name
        self.assertFalse(_is_subscription_source_ref("http://u:p@1.2.3.4:8080#name"))

    def test_http_with_fragment(self) -> None:
        self.assertFalse(_is_subscription_source_ref("http://example.com/path#frag"))

    def test_http_bare_host_no_path(self) -> None:
        self.assertFalse(_is_subscription_source_ref("http://example.com"))

    def test_http_with_path(self) -> None:
        self.assertTrue(_is_subscription_source_ref("https://example.com/sub/list"))

    def test_http_with_query(self) -> None:
        self.assertTrue(_is_subscription_source_ref("https://example.com/sub?token=abc"))

    def test_data_ref_with_spaces_returns_false(self) -> None:
        # "data: ..." has a space, so should be False
        self.assertFalse(_is_subscription_source_ref("data: text/html"))


class TestExtractSubscriptionSourceRefs(unittest.TestCase):
    def test_extracts_http_refs(self) -> None:
        text = "https://example.com/sub?tok=1\nplain line\nhttps://example.com/sub?tok=2"
        refs, remaining = _extract_subscription_source_refs(text)
        self.assertEqual(len(refs), 2)
        self.assertEqual(remaining.strip(), "plain line")

    def test_deduplicates_refs(self) -> None:
        text = "https://example.com/a?x=1\nhttps://example.com/a?x=1"
        refs, remaining = _extract_subscription_source_refs(text)
        self.assertEqual(len(refs), 1)
        self.assertEqual(remaining.strip(), "")

    def test_data_and_file_refs(self) -> None:
        text = "data:text/plain,hello\nfile:///tmp/nodes.txt\nplain"
        refs, remaining = _extract_subscription_source_refs(text)
        self.assertEqual(len(refs), 2)
        self.assertIn("plain", remaining)

    def test_strips_bom(self) -> None:
        text = "﻿https://example.com/a?x=1"
        refs, _ = _extract_subscription_source_refs(text)
        self.assertEqual(len(refs), 1)

    def test_empty_text(self) -> None:
        refs, remaining = _extract_subscription_source_refs("")
        self.assertEqual(refs, [])
        self.assertEqual(remaining, "")


class TestAutoSubscriptionName(unittest.TestCase):
    def test_basic(self) -> None:
        name = _auto_subscription_name("https://example.com/path/sub.txt", "upload.txt", 1)
        self.assertIn("example.com", name)
        self.assertIn("sub.txt", name)
        self.assertIn("auto:", name)
        self.assertIn("upload.txt", name)

    def test_no_path(self) -> None:
        name = _auto_subscription_name("https://example.com/", "src", 2)
        self.assertIn("example.com", name)
        self.assertIn("src", name)

    def test_empty_url(self) -> None:
        name = _auto_subscription_name("", "src", 1)
        self.assertIn("subscription", name)

    def test_empty_source_name(self) -> None:
        name = _auto_subscription_name("https://example.com/sub?x=1", "", 3)
        self.assertIn("upload", name)


class TestCollectFromUrlsErrorHandling(unittest.TestCase):
    """Lines 83-86: FetchError in collect_from_urls."""

    def test_fetch_error_marks_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            with patch(
                "proxypool.collector.service.fetch_text",
                side_effect=FetchError("network error"),
            ):
                report = service.collect_from_urls(["https://example.com/fail"])
            self.assertEqual(report.total_sources, 1)
            self.assertEqual(report.total_invalid, 1)
            self.assertEqual(report.total_parsed, 0)


class TestCollectFromSourcesPathErrors(unittest.TestCase):
    """Lines 158-177: path traversal and file-not-found in collect_from_sources."""

    def test_path_traversal_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            with patch(
                "proxypool.collector.service.validate_file_path",
                side_effect=PathTraversalError("traversal detected"),
            ):
                report = service.collect_from_sources(["../../etc/passwd"])
            self.assertEqual(report.total_sources, 1)
            self.assertEqual(report.total_invalid, 1)
            self.assertEqual(len(report.by_source), 1)

    def test_file_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            report = service.collect_from_sources(["/nonexistent/file.txt"])
            self.assertEqual(report.total_sources, 1)
            self.assertEqual(report.total_invalid, 1)


class TestCollectFromSubscriptionDirectFetch(unittest.TestCase):
    """Lines 131-141: subscription with no proxy key → direct fetch."""

    def test_no_proxy_key_direct_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, storage = _make_service(Path(td))
            # get_subscription_update_proxy_key returns "" → no proxy
            with patch(
                "proxypool.collector.service.fetch_text",
                return_value="trojan://pwd@host.com:443#direct",
            ):
                report = service.collect_from_subscription(
                    subscription_id=11,
                    subscription_name="direct-sub",
                    subscription_url="https://example.com/sub.txt",
                )
            self.assertEqual(report.total_inserted, 1)

    def test_direct_fetch_fails_no_results(self) -> None:
        """Lines 135-136: proxy_source_report is not None in except block."""
        with tempfile.TemporaryDirectory() as td:
            service, storage = _make_service(Path(td))
            from proxypool.models import ProxyNode

            node = ProxyNode(
                protocol="trojan",
                host="proxy.example.com",
                port=443,
                raw_link="trojan://p@proxy.example.com:443",
                extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            storage.set_subscription_update_proxy_key(node.normalized_key())

            # Proxy fetch succeeds but returns garbage, then direct fetch also fails
            with (
                patch(
                    "proxypool.collector.service.fetch_text_via_proxy_node",
                    return_value="garbage",
                ),
                patch(
                    "proxypool.collector.service.fetch_text",
                    side_effect=FetchError("direct failed"),
                ),
            ):
                report = service.collect_from_subscription(
                    subscription_id=12,
                    subscription_name="proxy-then-fail",
                    subscription_url="https://example.com/sub.txt",
                )
            # proxy_source_report exists but has no success, text is empty, then FetchError
            # so proxy_source_report is merged, and we return
            self.assertEqual(report.total_sources, 1)


class TestCollectFromTextItems(unittest.TestCase):
    """Test collect_from_text_items basic paths."""

    def test_collect_from_text_items_basic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            report = service.collect_from_text_items(
                [("upload.txt", "trojan://pwd@host.com:443#t1")]
            )
            self.assertEqual(report.total_inserted, 1)
            self.assertEqual(report.total_sources, 1)

    def test_collect_from_text_items_empty_filename(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            report = service.collect_from_text_items([("", "trojan://pwd@h.com:443#t1")])
            self.assertEqual(report.total_inserted, 1)

    def test_collect_from_text_items_with_subscription_refs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, storage = _make_service(Path(td))
            # Text has a data: ref and a plain proxy line
            text = "data:text/plain,trojan://pwd@ref.com:443#ref1\ntrojan://pwd@direct.com:443#d1"
            report = service.collect_from_text_items([("upload.txt", text)])
            self.assertEqual(report.total_inserted, 2)


class TestCollectFromSubscriptionEnsuresSubscription(unittest.TestCase):
    """Lines 253, 258-262: _ensure_subscription_for_url paths."""

    def test_existing_subscription_reused(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, storage = _make_service(Path(td))
            # Create a subscription first
            storage.create_subscription(name="existing", url="https://example.com/exist", enabled=True)
            with patch(
                "proxypool.collector.service.fetch_text",
                return_value="trojan://pwd@host.com:443#t1",
            ):
                report = service.collect_from_subscription(
                    subscription_id=20,
                    subscription_name="existing",
                    subscription_url="https://example.com/exist",
                )
            self.assertEqual(report.total_inserted, 1)
            subs = storage.list_subscriptions()
            # Should reuse existing, not create duplicate
            matching = [s for s in subs if s["url"] == "https://example.com/exist"]
            self.assertEqual(len(matching), 1)

    def test_create_subscription_retry_on_conflict(self) -> None:
        """Lines 258-262: create_subscription raises, retry finds it."""
        with tempfile.TemporaryDirectory() as td:
            service, storage = _make_service(Path(td))
            call_count = 0

            def fake_create(name: str, url: str, enabled: bool = True) -> dict:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("unique constraint")
                # On retry, return the one from get_subscription_by_url
                return storage.create_subscription.__wrapped__(  # type: ignore[attr-defined]
                    storage, name=name, url=url, enabled=enabled
                )

            # Use the real storage method but wrapped to simulate the first call failing
            original_create = storage.create_subscription
            first_call = True

            def patched_create(name: str, url: str, enabled: bool = True) -> dict:
                nonlocal first_call
                if first_call:
                    first_call = False
                    raise Exception("unique constraint")
                return original_create(name=name, url=url, enabled=enabled)

            storage.create_subscription = patched_create  # type: ignore[assignment]

            with patch(
                "proxypool.collector.service.fetch_text",
                return_value="trojan://pwd@host.com:443#t1",
            ):
                report = service.collect_from_subscription(
                    subscription_id=21,
                    subscription_name="retry-sub",
                    subscription_url="https://example.com/retry",
                )
            self.assertEqual(report.total_inserted, 1)


class TestMaxProxyCount(unittest.TestCase):
    """Lines 284-285: max_proxy_count exceeded → node marked invalid."""

    def test_max_proxy_count_reached(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td), max_proxy_count=2)
            # Insert 2 proxies to hit the limit
            text = "\n".join([
                "trojan://pwd@a.com:443#a",
                "trojan://pwd@b.com:443#b",
            ])
            service.collect_from_text_items([("f.txt", text)])
            # Now add more – should be marked invalid
            report = service.collect_from_text_items([("f2.txt", "trojan://pwd@c.com:443#c")])
            self.assertEqual(report.total_invalid, 1)
            self.assertEqual(report.total_inserted, 0)


class TestUpsertUpdatedPath(unittest.TestCase):
    """Line 292: upsert_proxy returns 'updated'."""

    def test_duplicate_proxy_is_updated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, storage = _make_service(Path(td))
            # Insert once
            report1 = service.collect_from_text_items([("f.txt", "trojan://pwd@host.com:443#t")])
            self.assertEqual(report1.total_inserted, 1)
            # Insert again – should update, not insert
            report2 = service.collect_from_text_items([("f.txt", "trojan://pwd@host.com:443#t")])
            self.assertEqual(report2.total_updated, 1)
            self.assertEqual(report2.total_inserted, 0)


class TestCollectFromSourcesUrls(unittest.TestCase):
    """Test collect_from_sources with URL sources."""

    def test_url_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            with patch(
                "proxypool.collector.service.fetch_text",
                return_value="trojan://pwd@host.com:443#t1",
            ):
                report = service.collect_from_sources(["https://example.com/sub?x=1"])
            self.assertEqual(report.total_inserted, 1)
            self.assertEqual(report.total_sources, 1)

    def test_http_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            with patch(
                "proxypool.collector.service.fetch_text",
                return_value="",
            ):
                report = service.collect_from_sources(["http://example.com/sub"])
            self.assertEqual(report.total_sources, 1)

    def test_data_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            with patch(
                "proxypool.collector.service.fetch_text",
                return_value="trojan://pwd@host.com:443#t",
            ):
                report = service.collect_from_sources(["data:text/plain,proxy-data"])
            self.assertEqual(report.total_inserted, 1)


class TestCollectSubscriptionRefs(unittest.TestCase):
    """Lines 245-246: data:/file:// source refs in _collect_subscription_refs."""

    def test_data_ref_in_text_items(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            text = "data:text/plain,trojan://pwd@ref.com:443#data-ref"
            report = service.collect_from_text_items([("upload.txt", text)])
            self.assertEqual(report.total_inserted, 1)

    def test_file_ref_in_text_items(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            service, _ = _make_service(tmp)
            data_file = tmp / "proxies.txt"
            data_file.write_text("trojan://pwd@file.com:443#file-ref", encoding="utf-8")
            text = f"file://{data_file}"
            report = service.collect_from_text_items([("upload.txt", text)])
            self.assertEqual(report.total_inserted, 1)


class TestCollectFromSubscriptionAllPaths(unittest.TestCase):
    """Comprehensive subscription collection paths."""

    def test_subscription_name_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            with patch(
                "proxypool.collector.service.fetch_text",
                return_value="trojan://pwd@host.com:443#t",
            ):
                report = service.collect_from_subscription(
                    subscription_id=30,
                    subscription_name="",  # empty name → 'subscription' fallback
                    subscription_url="https://example.com/sub.txt",
                )
            self.assertEqual(report.total_inserted, 1)

    def test_subscription_fetch_error_no_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service, _ = _make_service(Path(td))
            with patch(
                "proxypool.collector.service.fetch_text",
                side_effect=FetchError("network down"),
            ):
                report = service.collect_from_subscription(
                    subscription_id=31,
                    subscription_name="fail-sub",
                    subscription_url="https://example.com/fail",
                )
            self.assertEqual(report.total_invalid, 1)


if __name__ == "__main__":
    unittest.main()
