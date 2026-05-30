"""Deep coverage tests for proxypool.storage._helpers — targeting uncovered lines."""

from __future__ import annotations

import pytest

from proxypool.storage._helpers import (
    _rewrite_share_alias,
    _rewrite_vmess_alias,
    _rewrite_url_fragment_alias,
    _safe_b64_decode_to_text,
)


# ---- _rewrite_share_alias: plain link with no protocol (line 270) ----

class TestRewriteShareAliasPlain:
    def test_plain_link_without_protocol(self) -> None:
        """A link with no '://' should be returned unchanged."""
        result = _rewrite_share_alias("some-plain-text", "alias")
        assert result == "some-plain-text"

    def test_empty_after_strip(self) -> None:
        """Empty string should be returned as-is."""
        result = _rewrite_share_alias("   ", "alias")
        assert result == ""


# ---- _rewrite_url_fragment_alias: exception path (lines 278-281) ----

class TestRewriteUrlFragmentAliasException:
    def test_exception_with_hash_in_link(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When urlsplit fails and link contains '#', the fragment is replaced."""
        def _fail_urlsplit(url: str) -> None:
            raise ValueError("broken url")

        monkeypatch.setattr("proxypool.storage._helpers.urlsplit", _fail_urlsplit)
        result = _rewrite_url_fragment_alias("https://example.com#old", "new")
        assert "new" in result
        assert "#" in result

    def test_exception_without_hash_in_link(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When urlsplit fails and link has no '#', fragment is appended."""
        def _fail_urlsplit(url: str) -> None:
            raise ValueError("broken url")

        monkeypatch.setattr("proxypool.storage._helpers.urlsplit", _fail_urlsplit)
        result = _rewrite_url_fragment_alias("https://example.com", "new")
        assert result == "https://example.com#new"


# ---- _rewrite_vmess_alias: bad JSON path (lines 291-292) ----

class TestRewriteVmessAliasBadJson:
    def test_vmess_with_non_json_payload(self) -> None:
        """vmess link whose base64 decodes to non-JSON should fall back to fragment rewrite."""
        import base64

        # "not json at all" is valid base64-encodable text but not valid JSON
        payload = base64.urlsafe_b64encode(b"not json at all").decode().rstrip("=")
        link = f"vmess://{payload}"
        result = _rewrite_vmess_alias(link, "test-alias")
        # Should fall back to url fragment alias rewrite
        assert "test-alias" in result

    def test_vmess_with_non_dict_json(self) -> None:
        """vmess link whose base64 decodes to a JSON array (not dict) should fall back."""
        import base64

        payload = base64.urlsafe_b64encode(b'[1,2,3]').decode().rstrip("=")
        link = f"vmess://{payload}"
        result = _rewrite_vmess_alias(link, "test-alias")
        assert "test-alias" in result


# ---- _safe_b64_decode_to_text: bad base64 path (lines 331-332) ----

class TestSafeB64DecodeBadInput:
    def test_invalid_base64_returns_empty(self) -> None:
        """Invalid base64 data should return empty string."""
        result = _safe_b64_decode_to_text("!!!not-base64!!!")
        assert result == ""

    def test_valid_base64_returns_text(self) -> None:
        """Valid base64 should decode correctly."""
        import base64

        encoded = base64.urlsafe_b64encode(b"hello").decode().rstrip("=")
        result = _safe_b64_decode_to_text(encoded)
        assert result == "hello"

    def test_empty_input(self) -> None:
        """Empty input should return empty string."""
        result = _safe_b64_decode_to_text("")
        assert result == ""

    def test_binary_content_returns_empty(self) -> None:
        """Base64 that decodes to non-UTF-8 bytes should return empty."""
        import base64

        # \xff\xfe is invalid UTF-8
        encoded = base64.urlsafe_b64encode(b"\xff\xfe").decode().rstrip("=")
        result = _safe_b64_decode_to_text(encoded)
        assert result == ""
