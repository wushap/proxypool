"""Shared helper functions for storage mixins and sqlite module."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlsplit, urlunsplit


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _loads_json_object(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _loads_json_array(value: Any) -> list[str]:
    try:
        parsed = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return _normalize_string_list(parsed)


def _normalize_pool_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    out = _normalize_published_subscription_filters(filters)
    raw = filters or {}
    geo_countries = _normalize_string_list(raw.get("geo_countries"), max_items=64)
    if geo_countries:
        out["geo_countries"] = geo_countries
        out.pop("geo_country", None)
    for key in ("latency_min", "latency_max", "freshness_hours"):
        value = str(raw.get(key) or "").strip()
        if value:
            try:
                num = int(float(value))
                if num >= 0:
                    out[key] = str(num)
            except (ValueError, TypeError):
                pass
    return out


def _normalize_string_list(values: Any, max_items: int = 16, max_length: int = 120) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        text = text[:max_length]
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= max_items:
            break
    return out


def _normalize_session_missing_action(value: Any) -> str:
    text = str(value or "RANDOM").strip().upper() or "RANDOM"
    if text not in {"RANDOM", "REJECT"}:
        return "RANDOM"
    return text


def _pool_filters_to_list_kwargs(filters: dict[str, Any]) -> dict[str, Any]:
    kwargs = _filters_to_proxy_list_kwargs(filters)
    for key in ("latency_min", "latency_max", "freshness_hours"):
        value = str(filters.get(key) or "").strip()
        if value:
            try:
                kwargs[key] = int(float(value))
            except (ValueError, TypeError):
                pass
    geo_countries = _normalize_string_list(filters.get("geo_countries"), max_items=64)
    if geo_countries:
        kwargs["geo_countries"] = geo_countries
        kwargs.pop("geo_country", None)
    return kwargs


def _normalize_published_subscription_filters(filters: dict[str, Any] | None) -> dict[str, str]:
    raw = filters or {}
    out: dict[str, str] = {}
    allowed = {
        "protocol",
        "available",
        "route_mode_filter",
        "source",
        "geo_filter",
        "geo_country",
        "geo_location",
        "openai_filter",
        "ip_purity_filter",
        "fallback_front_filter",
    }
    for key in allowed:
        value = str(raw.get(key) or "").strip()
        if value:
            out[key] = value[:300]
    if out.get("route_mode_filter") not in {None, "direct", "chain", "unreachable"}:
        out.pop("route_mode_filter", None)
    if out.get("available") not in {None, "true", "false"}:
        out.pop("available", None)
    if out.get("geo_filter") not in {None, "has", "none"}:
        out.pop("geo_filter", None)
    if out.get("openai_filter") not in {None, "unlocked", "blocked", "unchecked"}:
        out.pop("openai_filter", None)
    if out.get("ip_purity_filter") not in {
        None,
        "checked",
        "unchecked",
        "residential",
        "non_residential",
        "unknown",
    }:
        out.pop("ip_purity_filter", None)
    if out.get("fallback_front_filter") not in {None, "has", "none"}:
        out.pop("fallback_front_filter", None)
    if out.get("route_mode_filter"):
        out.pop("available", None)
        out.pop("fallback_front_filter", None)
    return out


def _normalize_published_subscription_format(value: Any) -> str:
    text = str(value or "raw").strip().lower() or "raw"
    if text not in {"raw", "clash"}:
        return "raw"
    return text


def _filters_to_proxy_list_kwargs(filters: dict[str, Any]) -> dict[str, Any]:
    route_mode_filter = str(filters.get("route_mode_filter") or "").strip()
    available_text = str(filters.get("available") or "").strip()
    available: bool | None
    fallback_front_filter = str(filters.get("fallback_front_filter") or "").strip() or None
    if route_mode_filter == "direct":
        available = True
        fallback_front_filter = "none"
    elif route_mode_filter == "chain":
        available = True
        fallback_front_filter = "has"
    elif route_mode_filter == "unreachable":
        available = False
        fallback_front_filter = None
    elif available_text == "true":
        available = True
    elif available_text == "false":
        available = False
    else:
        available = None
    return {
        "protocol": str(filters.get("protocol") or "").strip() or None,
        "available": available,
        "route_mode_filter": route_mode_filter or None,
        "source_keyword": str(filters.get("source") or "").strip() or None,
        "geo_filter": str(filters.get("geo_filter") or "").strip() or None,
        "geo_country": str(filters.get("geo_country") or "").strip() or None,
        "geo_location": str(filters.get("geo_location") or "").strip() or None,
        "openai_filter": str(filters.get("openai_filter") or "").strip() or None,
        "ip_purity_filter": str(filters.get("ip_purity_filter") or "").strip() or None,
        "fallback_front_filter": fallback_front_filter,
        "sort_by": "latency",
        "sort_order": "asc",
    }


def _filters_to_subscription_link_kwargs(filters: dict[str, Any]) -> dict[str, Any]:
    kwargs = _filters_to_proxy_list_kwargs(filters)
    available = kwargs.pop("available")
    kwargs["only_available"] = available is not False
    if available is not None:
        kwargs["available"] = available
    kwargs.pop("sort_by", None)
    kwargs.pop("sort_order", None)
    return kwargs


def _build_export_alias(row: dict[str, Any], serial: int, serial_map: dict[str, int]) -> str:
    country = str(row.get("country") or "").strip() or "未知"
    city = str(row.get("city") or "").strip() or "未知"
    geo = f"{country}:{city}"

    fallback_keys = _parse_fallback_keys(row.get("fallback_front_keys_json"))
    chain_serials = [str(serial_map[key]) for key in fallback_keys if key in serial_map]
    if chain_serials:
        route = f"链式({'.'.join(chain_serials)})"
    elif fallback_keys:
        route = "链式(?)"
    else:
        route = "直连"

    purity_raw = str(row.get("ip_purity_level") or "").strip()
    if purity_raw == "家宽":
        purity = "家宽"
    elif purity_raw == "非家宽":
        purity = "非家宽"
    else:
        purity = "未知"

    unlocked = row.get("openai_unlocked")
    if unlocked is None:
        gpt = "未检测GPT"
    elif bool(unlocked):
        gpt = "已解锁GPT"
    else:
        gpt = "未解锁GPT"

    imported = _format_import_time(row.get("created_at"))
    return f"{int(serial)}_{geo}_{route}_{purity}_{gpt}_{imported}"


def _parse_fallback_keys(value: Any) -> list[str]:
    text = str(value or "[]")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    keys: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _format_import_time(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "00000000000000"
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y%m%d%H%M%S")
    except Exception:
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) >= 14:
            return digits[:14]
        return "00000000000000"


def _rewrite_share_alias(raw_link: str, alias: str) -> str:
    link = str(raw_link or "").strip()
    if not link:
        return link
    if link.startswith("vmess://"):
        return _rewrite_vmess_alias(link, alias)
    if link.startswith("ssr://"):
        return _rewrite_ssr_alias(link, alias)
    if "://" in link:
        return _rewrite_url_fragment_alias(link, alias)
    return link


def _rewrite_url_fragment_alias(link: str, alias: str) -> str:
    encoded = quote(alias, safe="")
    try:
        split = urlsplit(link)
        return urlunsplit(split._replace(fragment=encoded))
    except Exception:
        if "#" in link:
            return link.split("#", 1)[0] + "#" + encoded
        return link + "#" + encoded


def _rewrite_vmess_alias(link: str, alias: str) -> str:
    payload = link[len("vmess://"):]
    text = _safe_b64_decode_to_text(payload)
    if not text:
        return _rewrite_url_fragment_alias(link, alias)
    try:
        data = json.loads(text)
    except Exception:
        return _rewrite_url_fragment_alias(link, alias)
    if not isinstance(data, dict):
        return _rewrite_url_fragment_alias(link, alias)
    data["ps"] = alias
    encoded = (
        base64.urlsafe_b64encode(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        .decode("utf-8")
        .rstrip("=")
    )
    return "vmess://" + encoded


def _rewrite_ssr_alias(link: str, alias: str) -> str:
    payload = link[len("ssr://"):]
    text = _safe_b64_decode_to_text(payload)
    if not text:
        return _rewrite_url_fragment_alias(link, alias)
    if "/?" in text:
        base, query = text.split("/?", 1)
        params = parse_qs(query, keep_blank_values=True)
    else:
        base = text
        params = {}
    remarks = base64.urlsafe_b64encode(alias.encode("utf-8")).decode("utf-8").rstrip("=")
    params["remarks"] = [remarks]
    rebuilt = f"{base}/?{urlencode(params, doseq=True)}"
    encoded = base64.urlsafe_b64encode(rebuilt.encode("utf-8")).decode("utf-8").rstrip("=")
    return "ssr://" + encoded


def _safe_b64_decode_to_text(payload: str) -> str:
    text = str(payload or "").strip()
    if not text:
        return ""
    padded = text + "=" * ((4 - len(text) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
    except Exception:
        return ""
    try:
        return raw.decode("utf-8")
    except Exception:
        return ""
