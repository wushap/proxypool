"""
Tests for proxypool.storage._helpers utility functions to increase coverage.
"""

from __future__ import annotations

import base64
import json

from proxypool.storage._helpers import (
    _build_export_alias,
    _filters_to_proxy_list_kwargs,
    _format_import_time,
    _loads_json_array,
    _loads_json_object,
    _normalize_pool_filters,
    _normalize_published_subscription_filters,
    _normalize_published_subscription_format,
    _normalize_session_missing_action,
    _normalize_string_list,
    _parse_fallback_keys,
    _pool_filters_to_list_kwargs,
    _rewrite_share_alias,
    _rewrite_vmess_alias,
    _rewrite_ssr_alias,
    _safe_b64_decode_to_text,
)


# ---- _loads_json_object ----


def test_loads_json_object_valid():
    assert _loads_json_object('{"a": 1}') == {"a": 1}


def test_loads_json_object_empty():
    assert _loads_json_object(None) == {}
    assert _loads_json_object("") == {}


def test_loads_json_object_invalid():
    assert _loads_json_object("not json") == {}


def test_loads_json_object_not_dict():
    assert _loads_json_object("[1,2]") == {}


# ---- _loads_json_array ----


def test_loads_json_array_valid():
    assert _loads_json_array('["a", "b"]') == ["a", "b"]


def test_loads_json_array_empty():
    assert _loads_json_array(None) == []
    assert _loads_json_array("") == []


def test_loads_json_array_invalid():
    assert _loads_json_array("not json") == []


def test_loads_json_array_not_list():
    assert _loads_json_array('{"a": 1}') == []


# ---- _normalize_string_list ----


def test_normalize_string_list_basic():
    result = _normalize_string_list(["a", "b", "c"])
    assert result == ["a", "b", "c"]


def test_normalize_string_list_dedup():
    result = _normalize_string_list(["a", "a", "b"])
    assert result == ["a", "b"]


def test_normalize_string_list_max_items():
    result = _normalize_string_list(["a", "b", "c"], max_items=2)
    assert result == ["a", "b"]


def test_normalize_string_list_max_length():
    result = _normalize_string_list(["hello world"], max_length=5)
    assert result == ["hello"]


def test_normalize_string_list_not_list():
    assert _normalize_string_list(None) == []
    assert _normalize_string_list("not a list") == []


def test_normalize_string_list_empty_items():
    result = _normalize_string_list(["", "  ", "a"])
    assert result == ["a"]


# ---- _normalize_session_missing_action ----


def test_normalize_session_missing_action_random():
    assert _normalize_session_missing_action("random") == "RANDOM"


def test_normalize_session_missing_action_reject():
    assert _normalize_session_missing_action("REJECT") == "REJECT"


def test_normalize_session_missing_action_invalid():
    assert _normalize_session_missing_action("invalid") == "RANDOM"


def test_normalize_session_missing_action_empty():
    assert _normalize_session_missing_action("") == "RANDOM"


# ---- _normalize_pool_filters ----


def test_normalize_pool_filters_empty():
    result = _normalize_pool_filters(None)
    assert isinstance(result, dict)


def test_normalize_pool_filters_geo_countries():
    result = _normalize_pool_filters({"geo_countries": ["US", "JP"]})
    assert "geo_countries" in result
    assert "geo_country" not in result


def test_normalize_pool_filters_latency():
    result = _normalize_pool_filters({"latency_min": "100", "latency_max": "500"})
    assert result.get("latency_min") == "100"
    assert result.get("latency_max") == "500"


def test_normalize_pool_filters_freshness():
    result = _normalize_pool_filters({"freshness_hours": "24"})
    assert result.get("freshness_hours") == "24"


def test_normalize_pool_filters_invalid_latency():
    result = _normalize_pool_filters({"latency_min": "abc"})
    assert "latency_min" not in result


def test_normalize_pool_filters_negative_latency():
    result = _normalize_pool_filters({"latency_min": "-1"})
    assert "latency_min" not in result


# ---- _normalize_published_subscription_filters ----


def test_norm_pub_sub_filters_empty():
    result = _normalize_published_subscription_filters(None)
    assert result == {}


def test_norm_pub_sub_filters_valid():
    result = _normalize_published_subscription_filters({
        "protocol": "vmess",
        "source": "test",
        "geo_filter": "has",
        "geo_country": "US",
        "geo_location": "NYC",
        "openai_filter": "unlocked",
        "ip_purity_filter": "residential",
        "fallback_front_filter": "none",
    })
    assert result["protocol"] == "vmess"
    assert result["source"] == "test"


def test_norm_pub_sub_filters_invalid_route_mode():
    result = _normalize_published_subscription_filters(
        {"route_mode_filter": "invalid"}
    )
    assert "route_mode_filter" not in result


def test_norm_pub_sub_filters_invalid_available():
    result = _normalize_published_subscription_filters(
        {"available": "maybe"}
    )
    assert "available" not in result


def test_norm_pub_sub_filters_invalid_geo_filter():
    result = _normalize_published_subscription_filters(
        {"geo_filter": "invalid"}
    )
    assert "geo_filter" not in result


def test_norm_pub_sub_filters_invalid_openai_filter():
    result = _normalize_published_subscription_filters(
        {"openai_filter": "invalid"}
    )
    assert "openai_filter" not in result


def test_norm_pub_sub_filters_invalid_ip_purity():
    result = _normalize_published_subscription_filters(
        {"ip_purity_filter": "invalid"}
    )
    assert "ip_purity_filter" not in result


def test_norm_pub_sub_filters_invalid_fallback_front():
    result = _normalize_published_subscription_filters(
        {"fallback_front_filter": "invalid"}
    )
    assert "fallback_front_filter" not in result


def test_norm_pub_sub_filters_route_mode_cleans_available():
    result = _normalize_published_subscription_filters(
        {"route_mode_filter": "chain", "available": "true"}
    )
    assert "route_mode_filter" in result
    assert "available" not in result


# ---- _normalize_published_subscription_format ----


def test_norm_pub_sub_format_raw():
    assert _normalize_published_subscription_format("raw") == "raw"


def test_norm_pub_sub_format_clash():
    assert _normalize_published_subscription_format("clash") == "clash"


def test_norm_pub_sub_format_invalid():
    assert _normalize_published_subscription_format("yaml") == "raw"


def test_norm_pub_sub_format_empty():
    assert _normalize_published_subscription_format("") == "raw"


# ---- _filters_to_proxy_list_kwargs ----


def test_filters_to_proxy_list_direct():
    result = _filters_to_proxy_list_kwargs({"route_mode_filter": "direct"})
    assert result["available"] is True
    assert result["fallback_front_filter"] == "none"


def test_filters_to_proxy_list_chain():
    result = _filters_to_proxy_list_kwargs({"route_mode_filter": "chain"})
    assert result["available"] is True
    assert result["fallback_front_filter"] == "has"


def test_filters_to_proxy_list_unreachable():
    result = _filters_to_proxy_list_kwargs({"route_mode_filter": "unreachable"})
    assert result["available"] is False
    assert result["fallback_front_filter"] is None


def test_filters_to_proxy_list_available_true():
    result = _filters_to_proxy_list_kwargs({"available": "true"})
    assert result["available"] is True


def test_filters_to_proxy_list_available_false():
    result = _filters_to_proxy_list_kwargs({"available": "false"})
    assert result["available"] is False


def test_filters_to_proxy_list_available_none():
    result = _filters_to_proxy_list_kwargs({})
    assert result["available"] is None


def test_filters_to_proxy_list_all_fields():
    result = _filters_to_proxy_list_kwargs({
        "protocol": "vmess",
        "source": "test",
        "geo_filter": "has",
        "geo_country": "US",
        "geo_location": "NYC",
        "openai_filter": "unlocked",
        "ip_purity_filter": "residential",
        "fallback_front_filter": "none",
    })
    assert result["protocol"] == "vmess"
    assert result["source_keyword"] == "test"


# ---- _pool_filters_to_list_kwargs ----


def test_pool_filters_to_list_kwargs_latency():
    result = _pool_filters_to_list_kwargs({"latency_min": "100"})
    assert result.get("latency_min") == 100


def test_pool_filters_to_list_kwargs_geo():
    result = _pool_filters_to_list_kwargs({"geo_countries": ["US"]})
    assert "geo_countries" in result
    assert "geo_country" not in result


def test_pool_filters_to_list_kwargs_invalid_latency():
    result = _pool_filters_to_list_kwargs({"latency_min": "abc"})
    assert "latency_min" not in result


# ---- _parse_fallback_keys ----


def test_parse_fallback_keys_valid():
    result = _parse_fallback_keys('["key1", "key2"]')
    assert result == ["key1", "key2"]


def test_parse_fallback_keys_dedup():
    result = _parse_fallback_keys('["a", "a", "b"]')
    assert result == ["a", "b"]


def test_parse_fallback_keys_empty():
    assert _parse_fallback_keys(None) == []
    assert _parse_fallback_keys("[]") == []


def test_parse_fallback_keys_invalid_json():
    assert _parse_fallback_keys("not json") == []


def test_parse_fallback_keys_not_list():
    assert _parse_fallback_keys('{"key": "value"}') == []


def test_parse_fallback_keys_empty_items():
    result = _parse_fallback_keys('["", "  ", "key"]')
    assert result == ["key"]


# ---- _format_import_time ----


def test_format_import_time_empty():
    assert _format_import_time(None) == "00000000000000"
    assert _format_import_time("") == "00000000000000"


def test_format_import_time_valid():
    result = _format_import_time("2024-01-15T10:30:00+00:00")
    assert len(result) == 14


def test_format_import_time_digits_fallback():
    result = _format_import_time("20240115103000extra")
    assert result == "20240115103000"


def test_format_import_time_short_digits():
    result = _format_import_time("abc")
    assert result == "00000000000000"


# ---- _build_export_alias ----


def test_build_export_alias_basic():
    alias = _build_export_alias(
        {"country": "US", "city": "NYC"},
        serial=1,
        serial_map={},
    )
    assert "1" in alias
    assert "US" in alias
    assert "NYC" in alias
    assert "直连" in alias


def test_build_export_alias_chain():
    alias = _build_export_alias(
        {
            "country": "JP",
            "city": "Tokyo",
            "fallback_front_keys_json": '["k1"]',
        },
        serial=2,
        serial_map={"k1": 1},
    )
    assert "链式" in alias


def test_build_export_alias_chain_unknown_key():
    alias = _build_export_alias(
        {
            "fallback_front_keys_json": '["unknown_key"]',
        },
        serial=1,
        serial_map={},
    )
    assert "链式(?)" in alias


def test_build_export_alias_purity():
    alias = _build_export_alias(
        {"ip_purity_level": "家宽"},
        serial=1,
        serial_map={},
    )
    assert "家宽" in alias


def test_build_export_alias_purity_non():
    alias = _build_export_alias(
        {"ip_purity_level": "非家宽"},
        serial=1,
        serial_map={},
    )
    assert "非家宽" in alias


def test_build_export_alias_purity_unknown():
    alias = _build_export_alias(
        {"ip_purity_level": "other"},
        serial=1,
        serial_map={},
    )
    assert "未知" in alias


def test_build_export_alias_gpt_unlocked():
    alias = _build_export_alias(
        {"openai_unlocked": True},
        serial=1,
        serial_map={},
    )
    assert "已解锁GPT" in alias


def test_build_export_alias_gpt_not_unlocked():
    alias = _build_export_alias(
        {"openai_unlocked": False},
        serial=1,
        serial_map={},
    )
    assert "未解锁GPT" in alias


def test_build_export_alias_gpt_none():
    alias = _build_export_alias(
        {"openai_unlocked": None},
        serial=1,
        serial_map={},
    )
    assert "未检测GPT" in alias


# ---- _rewrite_share_alias ----


def test_rewrite_share_alias_empty():
    assert _rewrite_share_alias("", "alias") == ""


def test_rewrite_share_alias_vmess():
    # Create a valid vmess link
    data = {"ps": "old", "add": "1.2.3.4", "port": "443"}
    payload = base64.urlsafe_b64encode(
        json.dumps(data, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    link = f"vmess://{payload}"
    result = _rewrite_share_alias(link, "new_alias")
    assert result.startswith("vmess://")
    # Decode and verify alias
    decoded = _safe_b64_decode_to_text(result[len("vmess://"):])
    decoded_data = json.loads(decoded)
    assert decoded_data["ps"] == "new_alias"


def test_rewrite_share_alias_ssr():
    # Create a valid ssr link
    inner = base64.urlsafe_b64encode(b"server:port:0:0:aes-256-cfb").decode().rstrip("=")
    link = f"ssr://{inner}"
    result = _rewrite_share_alias(link, "my_alias")
    assert result.startswith("ssr://")


def test_rewrite_share_alias_url_fragment():
    result = _rewrite_share_alias("https://example.com/path#old", "new")
    assert "#new" in result or "new" in result


def test_rewrite_share_alias_unknown():
    # Any protocol with :// gets fragment rewriting
    result = _rewrite_share_alias("ftp://something", "alias")
    assert "alias" in result


# ---- _rewrite_vmess_alias ----


def test_rewrite_vmess_alias_invalid_payload():
    link = "vmess://not_valid_base64!!!"
    result = _rewrite_vmess_alias(link, "alias")
    assert "vmess://" in result


def test_rewrite_vmess_alias_non_dict():
    data = [1, 2, 3]
    payload = base64.urlsafe_b64encode(
        json.dumps(data).encode()
    ).decode().rstrip("=")
    link = f"vmess://{payload}"
    result = _rewrite_vmess_alias(link, "alias")
    assert "vmess://" in result


def test_rewrite_vmess_alias_empty_payload():
    result = _rewrite_vmess_alias("vmess://", "alias")
    assert "alias" in result


# ---- _rewrite_ssr_alias ----


def test_rewrite_ssr_alias_no_query():
    inner = base64.urlsafe_b64encode(b"server:port:0:0:aes-256-cfb").decode().rstrip("=")
    link = f"ssr://{inner}"
    result = _rewrite_ssr_alias(link, "new_name")
    assert result.startswith("ssr://")


def test_rewrite_ssr_alias_with_query():
    inner = base64.urlsafe_b64encode(
        b"server:port:0:0:aes-256-cfb/?remarks=old"
    ).decode().rstrip("=")
    link = f"ssr://{inner}"
    result = _rewrite_ssr_alias(link, "new_name")
    assert result.startswith("ssr://")


def test_rewrite_ssr_alias_empty_payload():
    result = _rewrite_ssr_alias("ssr://", "alias")
    assert "alias" in result


# ---- _safe_b64_decode_to_text ----


def test_safe_b64_decode_valid():
    text = base64.urlsafe_b64encode(b"hello").decode().rstrip("=")
    result = _safe_b64_decode_to_text(text)
    assert result == "hello"


def test_safe_b64_decode_empty():
    assert _safe_b64_decode_to_text("") == ""
    assert _safe_b64_decode_to_text(None) == ""


def test_safe_b64_decode_invalid():
    result = _safe_b64_decode_to_text("not_base64!!!")
    assert result == ""


def test_safe_b64_decode_non_utf8():
    # Binary data that can't be decoded as UTF-8
    raw = bytes([0xFF, 0xFE])
    encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    result = _safe_b64_decode_to_text(encoded)
    assert result == ""
