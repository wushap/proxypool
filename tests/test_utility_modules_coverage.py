"""
Tests for utility modules to increase overall coverage:
- storage/health_storage.py
- security/api_helpers.py
- pool/protocol_compat.py
- gateway/session_extractor.py
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from proxypool.gateway.session_extractor import SessionExtractor
from proxypool.pool.protocol_compat import (
    ALL_SUPPORTED_PROTOCOLS,
    COMMON_PROTOCOLS,
    SINGBOX_PROTOCOLS,
    MIHOMO_PROTOCOLS,
    check_nodes_compatibility,
    filter_compatible_nodes,
    find_backend_for_protocol,
    get_supported_protocols,
    supports_protocol,
)
from proxypool.security.api_helpers import (
    validate_file_path_or_raise,
    validate_sources_list_or_raise,
    validate_url_or_raise,
    validate_urls_list_or_raise,
)
from proxypool.storage.health_storage import HealthStorage


# ================================================================
# health_storage.py tests
# ================================================================


def _make_health_storage(tmp_path: Path) -> HealthStorage:
    return HealthStorage(db_path=tmp_path / "health.db")


class TestHealthStorageProbeRecords:
    def test_insert_and_get(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.insert_probe_record(
            node_key="node1",
            success=True,
            latency_ms=42,
            probe_type="active",
            error_type="",
            source="test",
        )
        records = hs.get_probe_records("node1")
        assert len(records) == 1
        assert records[0]["node_key"] == "node1"
        assert records[0]["success"] == 1
        assert records[0]["latency_ms"] == 42

    def test_insert_failure(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.insert_probe_record(
            node_key="node1",
            success=False,
            latency_ms=None,
            error_type="timeout",
        )
        records = hs.get_probe_records("node1")
        assert len(records) == 1
        assert records[0]["success"] == 0
        assert records[0]["error_type"] == "timeout"

    def test_get_records_limit(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        for _ in range(5):
            hs.insert_probe_record(node_key="k1", success=True)
        records = hs.get_probe_records("k1", limit=2)
        assert len(records) == 2

    def test_get_records_nonexistent(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        assert hs.get_probe_records("no-such") == []

    def test_cleanup_old_records(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.insert_probe_record(node_key="k1", success=True)
        # cleanup with max_age_hours=0 should delete everything
        deleted = hs.cleanup_old_probe_records(max_age_hours=0)
        assert deleted == 1
        assert hs.get_probe_records("k1") == []


class TestHealthStorageNodeScores:
    def test_upsert_and_get(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.upsert_node_score(
            node_key="n1",
            final_score=85.0,
            grade="B",
            raw_score=80.0,
            confidence=0.9,
            success_rate=0.85,
            avg_latency_ms=120,
            stability_score=0.7,
        )
        score = hs.get_node_score("n1")
        assert score is not None
        assert score["final_score"] == 85.0
        assert score["grade"] == "B"

    def test_upsert_update(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.upsert_node_score(
            node_key="n1", final_score=50.0, grade="C", raw_score=45.0, confidence=0.6
        )
        hs.upsert_node_score(
            node_key="n1", final_score=90.0, grade="A", raw_score=88.0, confidence=0.95
        )
        score = hs.get_node_score("n1")
        assert score is not None
        assert score["final_score"] == 90.0

    def test_get_nonexistent(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        assert hs.get_node_score("no-such") is None

    def test_get_all(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.upsert_node_score(
            node_key="a", final_score=90.0, grade="A", raw_score=88.0, confidence=0.9
        )
        hs.upsert_node_score(
            node_key="b", final_score=60.0, grade="D", raw_score=55.0, confidence=0.5
        )
        all_scores = hs.get_all_node_scores()
        assert len(all_scores) == 2
        # Ordered by final_score DESC
        assert all_scores[0]["final_score"] >= all_scores[1]["final_score"]

    def test_delete(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.upsert_node_score(
            node_key="n1", final_score=80.0, grade="B", raw_score=75.0, confidence=0.8
        )
        deleted = hs.delete_node_score("n1")
        assert deleted == 1
        assert hs.get_node_score("n1") is None


class TestHealthStorageCircuitBreaker:
    def test_upsert_and_get(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.upsert_circuit_breaker(
            node_key="n1",
            state="open",
            failure_count=5,
            consecutive_successes=0,
            last_failure_time=1000.0,
            last_success_time=900.0,
            open_since=1000.0,
            backoff_until=1030.0,
            current_backoff_sec=30.0,
        )
        cb = hs.get_circuit_breaker("n1")
        assert cb is not None
        assert cb["state"] == "open"
        assert cb["failure_count"] == 5

    def test_upsert_update(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.upsert_circuit_breaker(
            node_key="n1", state="open", failure_count=3
        )
        hs.upsert_circuit_breaker(
            node_key="n1", state="closed", failure_count=0, consecutive_successes=5
        )
        cb = hs.get_circuit_breaker("n1")
        assert cb is not None
        assert cb["state"] == "closed"

    def test_get_nonexistent(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        assert hs.get_circuit_breaker("no-such") is None

    def test_get_all(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.upsert_circuit_breaker(node_key="a", state="open", failure_count=1)
        hs.upsert_circuit_breaker(node_key="b", state="closed", failure_count=0)
        all_cb = hs.get_all_circuit_breakers()
        assert len(all_cb) == 2

    def test_delete(self, tmp_path: Path) -> None:
        hs = _make_health_storage(tmp_path)
        hs.upsert_circuit_breaker(node_key="n1", state="open", failure_count=3)
        deleted = hs.delete_circuit_breaker("n1")
        assert deleted == 1
        assert hs.get_circuit_breaker("n1") is None


# ================================================================
# api_helpers.py tests
# ================================================================


class TestValidateUrlOrRaise:
    def test_empty_url_ok(self) -> None:
        validate_url_or_raise("")

    def test_valid_url_ok(self) -> None:
        validate_url_or_raise("https://example.com")

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_url_or_raise("ftp://unsafe.example.com", field_name="test_url")
        assert exc_info.value.status_code == 400
        assert "test_url" in exc_info.value.detail


class TestValidateFilePathOrRaise:
    def test_valid_path(self, tmp_path: Path) -> None:
        result = validate_file_path_or_raise(
            str(tmp_path / "file.txt"), allowed_directories=[tmp_path]
        )
        assert isinstance(result, Path)

    def test_traversal_path(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_file_path_or_raise("../../../etc/passwd")
        assert exc_info.value.status_code == 400


class TestValidateUrlsListOrRaise:
    def test_valid_urls(self) -> None:
        # Use localhost which resolves to 127.0.0.1 (private IP -> rejected)
        # but we test the error path here. Use empty list for clean pass.
        validate_urls_list_or_raise([])

    def test_invalid_url_in_list(self) -> None:
        # 169.254.169.254 is metadata endpoint -> rejected
        with pytest.raises(HTTPException) as exc_info:
            validate_urls_list_or_raise(
                ["http://169.254.169.254/metadata"]
            )
        assert exc_info.value.status_code == 400
        assert "urls[0]" in exc_info.value.detail

    def test_private_ip_in_list(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_urls_list_or_raise(
                ["http://127.0.0.1:8080/test"]
            )
        assert exc_info.value.status_code == 400
        assert "urls[0]" in exc_info.value.detail


class TestValidateSourcesListOrRaise:
    def test_file_path_source(self) -> None:
        # File path sources are not validated at this level
        validate_sources_list_or_raise(["/some/local/path"])

    def test_invalid_source_url(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_sources_list_or_raise(["http://169.254.169.254/metadata"])
        assert exc_info.value.status_code == 400

    def test_private_ip_source(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_sources_list_or_raise(["http://192.168.1.1/admin"])
        assert exc_info.value.status_code == 400


# ================================================================
# protocol_compat.py tests
# ================================================================


class TestProtocolCompat:
    def test_singbox_protocols(self) -> None:
        procs = get_supported_protocols("singbox")
        assert procs == SINGBOX_PROTOCOLS
        assert "snell" in procs

    def test_mihomo_protocols(self) -> None:
        procs = get_supported_protocols("mihomo")
        assert procs == MIHOMO_PROTOCOLS
        assert "snell" not in procs

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown backend type"):
            get_supported_protocols("unknown")

    def test_supports_protocol(self) -> None:
        assert supports_protocol("vmess", "singbox") is True
        assert supports_protocol("snell", "mihomo") is False
        assert supports_protocol("VMess", "singbox") is True  # case insensitive

    def test_find_backend(self) -> None:
        assert find_backend_for_protocol("vmess") == "singbox"
        assert find_backend_for_protocol("snell") == "singbox"
        assert find_backend_for_protocol("unknown") is None

    def test_check_nodes_compatibility(self) -> None:
        nodes = [
            {"protocol": "vmess", "normalized_key": "k1"},
            {"protocol": "snell", "normalized_key": "k2"},
        ]
        result = check_nodes_compatibility(nodes, "singbox")
        assert result["compatible"] is True

        result = check_nodes_compatibility(nodes, "mihomo")
        assert result["compatible"] is False
        assert len(result["incompatible_nodes"]) == 1

    def test_filter_compatible_nodes(self) -> None:
        nodes = [
            {"protocol": "vmess", "normalized_key": "k1"},
            {"protocol": "snell", "normalized_key": "k2"},
        ]
        filtered = filter_compatible_nodes(nodes, "mihomo")
        assert len(filtered) == 1
        assert filtered[0]["normalized_key"] == "k1"

    def test_sets(self) -> None:
        assert "vmess" in ALL_SUPPORTED_PROTOCOLS
        assert "vmess" in COMMON_PROTOCOLS


# ================================================================
# session_extractor.py tests
# ================================================================


class TestSessionExtractor:
    def setup_method(self) -> None:
        self.extractor = SessionExtractor()

    def test_header_session(self) -> None:
        value, source, missing = self.extractor.extract(
            headers={"X-Session-Id": "abc123"},
            query_params={},
            target_host="example.com",
            target_path="/api",
            header_names=["X-Session-Id"],
        )
        assert value == "abc123"
        assert source == "header:X-Session-Id"
        assert missing is False

    def test_query_session(self) -> None:
        value, source, missing = self.extractor.extract(
            headers={},
            query_params={"session_id": "q123"},
            target_host="example.com",
            target_path="/api",
            header_names=["X-Session-Id"],
            query_names=["session_id"],
        )
        assert value == "q123"
        assert source == "query:session_id"
        assert missing is False

    def test_missing_session(self) -> None:
        value, source, missing = self.extractor.extract(
            headers={},
            query_params={},
            target_host="example.com",
            target_path="/api",
        )
        assert value == ""
        assert source == "missing"
        assert missing is True

    def test_rule_based_session(self) -> None:
        value, source, missing = self.extractor.extract(
            headers={"Authorization": "Bearer tok123"},
            query_params={},
            target_host="api.example.com",
            target_path="/v1/data",
            rules=[
                {
                    "url_prefix": "api.example.com",
                    "headers": ["Authorization"],
                }
            ],
        )
        assert value == "Bearer tok123"
        assert "rule:" in source
        assert missing is False

    def test_normalize_target(self) -> None:
        assert self.extractor._normalize_target("host.com", "/path") == "host.com/path"
        assert self.extractor._normalize_target("host.com", "") == "host.com"

    def test_select_rule_longest_match(self) -> None:
        rules = [
            {"url_prefix": "api.example.com/v1"},
            {"url_prefix": "api.example.com"},
        ]
        match = self.extractor._select_rule("api.example.com/v1/data", rules)
        assert match is not None
        assert match["url_prefix"] == "api.example.com/v1"

    def test_select_rule_no_match(self) -> None:
        rules = [{"url_prefix": "other.com"}]
        assert self.extractor._select_rule("api.example.com", rules) is None

    def test_select_rule_empty_prefix(self) -> None:
        rules = [{"url_prefix": ""}]
        assert self.extractor._select_rule("target", rules) is None

    def test_first_value_list(self) -> None:
        assert self.extractor._first_value(["a", "b"]) == "a"
        assert self.extractor._first_value(["", "b"]) == "b"
        assert self.extractor._first_value([]) == ""

    def test_first_value_string(self) -> None:
        assert self.extractor._first_value("hello") == "hello"
