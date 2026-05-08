from __future__ import annotations

import json
import inspect
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable
from urllib.request import Request, urlopen

from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.tasks.manager import TaskCancelled


@dataclass(slots=True)
class GeoResult:
    normalized_key: str
    resolved_ip: str = ""
    country: str = ""
    city: str = ""
    ip_purity_score: float | None = None
    ip_purity_level: str = ""
    ok: bool = False
    error: str = ""


_PURITY_SOURCE_WEIGHTS: dict[str, float] = {
    # Based on IPQuality project's data-source set, with conservative weighting.
    "ipapi": 0.25,
    "ipqualityscore": 0.25,
    "scamalytics": 0.20,
    "abuseipdb": 0.15,
    "ip2location": 0.10,
    "ipdata": 0.05,
}

_RESIDENTIAL_SOURCE_WEIGHTS: dict[str, float] = {
    "ip2location": 0.35,
    "ippure": 0.25,
    "iplark": 0.20,
    "ipinfo": 0.20,
}

_DATACENTER_KEYWORDS: tuple[str, ...] = (
    "amazon",
    "aws",
    "google cloud",
    "gcp",
    "microsoft",
    "azure",
    "digitalocean",
    "vultr",
    "linode",
    "oracle cloud",
    "cloudflare",
    "akamai",
    "ovh",
    "hetzner",
    "alibaba cloud",
    "tencent cloud",
    "datacenter",
    "hosting",
    "colo",
)

_ISP_KEYWORDS: tuple[str, ...] = (
    "telecom",
    "comcast",
    "verizon",
    "at&t",
    "charter",
    "spectrum",
    "broadband",
    "isp",
    "communications",
    "fiber",
    "residential",
    "cable",
    "mobile",
)


ProxyJSONFetcher = Callable[[dict, str, float, dict | None], dict]


class GeoIPService:
    def __init__(
        self,
        storage: SQLiteProxyStorage,
        resolver: Callable[[str], str] | None = None,
        geo_lookup: Callable[[str], tuple[str, str]] | None = None,
        purity_lookup: Callable[[str], tuple[float | None, str]] | None = None,
        proxy_json_fetcher: ProxyJSONFetcher | None = None,
    ) -> None:
        self.storage = storage
        self._resolver = resolver or _resolve_ip
        self._geo_lookup = geo_lookup or _lookup_geo
        self._purity_lookup = purity_lookup or _lookup_ip_purity
        self._proxy_json_fetcher = proxy_json_fetcher
        self._proxy_fetcher_supports_front = _supports_front_proxy_arg(proxy_json_fetcher)

    def enrich_batch(
        self,
        limit: int = 200,
        concurrency: int = 20,
        progress_cb: Callable[[dict], None] | None = None,
        stop_cb: Callable[[], bool] | None = None,
    ) -> dict[str, int]:
        if stop_cb and stop_cb():
            raise TaskCancelled("cancel requested")
        candidates = self.storage.list_geo_candidates(
            limit=limit,
            only_available=True,
            only_tested=True,
        )
        updated = 0
        failed = 0
        if progress_cb:
            progress_cb({"total": len(candidates), "completed": 0, "updated": 0, "failed": 0, "phase": "prepare"})

        if candidates:
            workers = max(1, min(int(concurrency or 1), len(candidates)))
            executor = ThreadPoolExecutor(max_workers=workers)
            try:
                futures = [executor.submit(self.enrich_one, row) for row in candidates]
                for fut in as_completed(futures):
                    if stop_cb and stop_cb():
                        executor.shutdown(wait=False, cancel_futures=True)
                        raise TaskCancelled("cancel requested")
                    try:
                        result = fut.result()
                    except Exception as exc:
                        result = GeoResult(normalized_key="", ok=False, error=str(exc))
                    if result.ok:
                        updated += 1
                    else:
                        failed += 1
                    if progress_cb:
                        progress_cb(
                            {
                                "total": len(candidates),
                                "completed": updated + failed,
                                "updated": updated,
                                "failed": failed,
                                "phase": "enriching",
                            }
                        )
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        report = {
            "requested": len(candidates),
            "updated": updated,
            "failed": failed,
        }
        if progress_cb:
            progress_cb(
                {
                    "total": len(candidates),
                    "completed": len(candidates),
                    "updated": updated,
                    "failed": failed,
                    "phase": "done",
                }
            )
        return report

    def enrich_ip_purity_batch(
        self,
        limit: int = 0,
        concurrency: int = 20,
        only_unchecked: bool = False,
        progress_cb: Callable[[dict], None] | None = None,
        stop_cb: Callable[[], bool] | None = None,
    ) -> dict[str, int]:
        if stop_cb and stop_cb():
            raise TaskCancelled("cancel requested")
        candidates = self.storage.list_ip_purity_candidates(
            limit=limit,
            only_unchecked=only_unchecked,
            only_available=True,
            only_tested=True,
        )
        updated = 0
        failed = 0
        if progress_cb:
            progress_cb({"total": len(candidates), "completed": 0, "updated": 0, "failed": 0, "phase": "prepare"})

        if candidates:
            workers = max(1, min(int(concurrency or 1), len(candidates)))
            executor = ThreadPoolExecutor(max_workers=workers)
            try:
                futures = [executor.submit(self._enrich_ip_purity_one, row) for row in candidates]
                for fut in as_completed(futures):
                    if stop_cb and stop_cb():
                        executor.shutdown(wait=False, cancel_futures=True)
                        raise TaskCancelled("cancel requested")
                    try:
                        ok = bool(fut.result())
                    except Exception:
                        ok = False
                    if ok:
                        updated += 1
                    else:
                        failed += 1
                    if progress_cb:
                        progress_cb(
                            {
                                "total": len(candidates),
                                "completed": updated + failed,
                                "updated": updated,
                                "failed": failed,
                                "phase": "purity",
                            }
                        )
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        report = {"requested": len(candidates), "updated": updated, "failed": failed}
        if progress_cb:
            progress_cb(
                {
                    "total": len(candidates),
                    "completed": len(candidates),
                    "updated": updated,
                    "failed": failed,
                    "phase": "done",
                }
            )
        return report

    def _enrich_ip_purity_one(self, row: dict) -> bool:
        key = str(row.get("normalized_key") or "")
        host = str(row.get("host") or "")
        if not key or not host:
            return False
        if self._proxy_json_fetcher is not None:
            try:
                ip, country, city = self._lookup_geo_via_proxy(row)
                self.storage.update_geo(key, resolved_ip=ip, country=country, city=city)
                score, level = self._lookup_ip_purity_via_proxy(row, ip)
                if score is None or not str(level or "").strip() or str(level).strip() == "未知":
                    score, level = self._purity_lookup(ip)
            except Exception:
                ip, country, city = self._lookup_geo_direct(row, host)
                self.storage.update_geo(key, resolved_ip=ip, country=country, city=city)
                score, level = self._purity_lookup(ip)
        else:
            ip, country, city = self._lookup_geo_direct(row, host)
            self.storage.update_geo(key, resolved_ip=ip, country=country, city=city)
            score, level = self._purity_lookup(ip)
        self.storage.update_ip_purity(key, score=score, level=level)
        return True

    def enrich_one(self, proxy_row: dict) -> GeoResult:
        key = str(proxy_row.get("normalized_key") or "")
        host = str(proxy_row.get("host") or "")
        if not key or not host:
            return GeoResult(normalized_key=key, ok=False, error="missing key or host")

        try:
            if self._proxy_json_fetcher is not None:
                try:
                    ip, country, city = self._lookup_geo_via_proxy(proxy_row)
                except Exception:
                    ip, country, city = self._lookup_geo_direct(proxy_row, host)
            else:
                ip, country, city = self._lookup_geo_direct(proxy_row, host)
            self.storage.update_geo(key, resolved_ip=ip, country=country, city=city)
            purity_score: float | None = None
            purity_level = ""
            try:
                if self._proxy_json_fetcher is not None:
                    try:
                        purity_score, purity_level = self._lookup_ip_purity_via_proxy(proxy_row, ip)
                        if (
                            purity_score is None
                            or not str(purity_level or "").strip()
                            or str(purity_level).strip() == "未知"
                        ):
                            purity_score, purity_level = self._purity_lookup(ip)
                    except Exception:
                        purity_score, purity_level = self._purity_lookup(ip)
                else:
                    purity_score, purity_level = self._purity_lookup(ip)
                self.storage.update_ip_purity(key, score=purity_score, level=purity_level)
            except Exception:
                # IP purity is best-effort, geo update success should not fail as a whole.
                pass
            return GeoResult(
                normalized_key=key,
                resolved_ip=ip,
                country=country,
                city=city,
                ip_purity_score=purity_score,
                ip_purity_level=purity_level,
                ok=True,
            )
        except Exception as exc:
            # keep silent in DB for geo errors, only return status
            return GeoResult(normalized_key=key, ok=False, error=str(exc))

    def _lookup_geo_direct(self, proxy_row: dict, host: str) -> tuple[str, str, str]:
        ip = str(proxy_row.get("resolved_ip") or "").strip()
        country = str(proxy_row.get("country") or "").strip()
        city = str(proxy_row.get("city") or "").strip()
        if not ip:
            ip = self._resolver(host)
        if not country or not city:
            try:
                looked_country, looked_city = self._geo_lookup(ip)
                if not country:
                    country = str(looked_country or "")
                if not city:
                    city = str(looked_city or "")
            except Exception:
                pass
        return ip, country, city

    def _lookup_geo_via_proxy(self, proxy_row: dict) -> tuple[str, str, str]:
        providers: list[tuple[str, float, Callable[[object], tuple[str, str, str] | None]]] = [
            (
                "http://ip-api.com/json/?lang=zh-CN&fields=status,country,city,query",
                8.0,
                _parse_geo_from_ip_api,
            ),
            (
                "https://ipinfo.io/json",
                8.0,
                _parse_geo_from_ipinfo,
            ),
            (
                "https://ipwho.is/",
                8.0,
                _parse_geo_from_ipwhois,
            ),
            (
                "https://ifconfig.co/json",
                8.0,
                _parse_geo_from_ifconfig,
            ),
            (
                "https://api.ip.sb/geoip",
                8.0,
                _parse_geo_from_ipsb,
            ),
        ]
        errors: list[str] = []
        for url, timeout_sec, parser in providers:
            data = self._try_fetch_json_via_proxy(proxy_row, url, timeout_sec=timeout_sec)
            if data is None:
                errors.append(f"{url}: fetch failed")
                continue
            parsed = parser(data)
            if parsed is not None:
                return parsed
            errors.append(f"{url}: invalid payload")
        raise RuntimeError("geo lookup failed: " + "; ".join(errors[:3]))

    def _lookup_ip_purity_via_proxy(self, proxy_row: dict, ip: str) -> tuple[float | None, str]:
        residential_votes = {
            "ip2location": _parse_residential_from_ip2location(
                self._try_fetch_json_via_proxy(
                    proxy_row,
                    f"https://ipinfo.check.place/{ip}?db=ip2location",
                    timeout_sec=12.0,
                )
            ),
            "iplark": _parse_residential_from_iplark(
                self._try_fetch_json_via_proxy(
                    proxy_row,
                    f"https://ipinfo.check.place/{ip}?db=iplark",
                    timeout_sec=12.0,
                )
            ),
            "ipinfo": _parse_residential_from_ipinfo_network(
                self._try_fetch_json_via_proxy(
                    proxy_row,
                    f"https://ipinfo.io/{ip}/json",
                    timeout_sec=12.0,
                )
            ),
            "ippure": _parse_residential_from_ippure(
                self._try_fetch_json_via_proxy(
                    proxy_row,
                    f"https://ipinfo.check.place/{ip}?db=ippure",
                    timeout_sec=12.0,
                )
            ),
        }
        return _residential_result_from_votes(residential_votes)

    def _try_fetch_json_via_proxy(self, proxy_row: dict, url: str, timeout_sec: float) -> dict | None:
        try:
            return self._fetch_json_via_proxy(proxy_row, url, timeout_sec)
        except Exception:
            return None

    def _fetch_json_via_proxy(self, proxy_row: dict, url: str, timeout_sec: float) -> dict:
        fetcher = self._proxy_json_fetcher
        if fetcher is None:
            raise RuntimeError("proxy fetcher not configured")
        last_error: Exception | None = None
        try:
            data = self._call_proxy_fetcher(fetcher, proxy_row, url, timeout_sec, front_proxy=None)
            if isinstance(data, dict):
                return data
            raise RuntimeError("invalid json payload from proxy fetch")
        except Exception as exc:
            last_error = exc

        for front_proxy in self._get_fallback_front_proxies(proxy_row):
            try:
                data = self._call_proxy_fetcher(fetcher, proxy_row, url, timeout_sec, front_proxy=front_proxy)
                if isinstance(data, dict):
                    return data
                last_error = RuntimeError("invalid json payload from proxy fetch")
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            raise RuntimeError(str(last_error))
        raise RuntimeError("proxy fetch failed")

    def _call_proxy_fetcher(
        self,
        fetcher: ProxyJSONFetcher,
        proxy_row: dict,
        url: str,
        timeout_sec: float,
        front_proxy: dict | None,
    ) -> dict:
        if self._proxy_fetcher_supports_front:
            return fetcher(proxy_row, url, timeout_sec, front_proxy)
        # Backward compatibility for fetchers that accept only 3 args.
        return fetcher(proxy_row, url, timeout_sec)  # type: ignore[misc]

    def _get_fallback_front_proxies(self, proxy_row: dict) -> list[dict]:
        cached = proxy_row.get("_fallback_front_rows")
        if isinstance(cached, list):
            return cached
        raw_keys = proxy_row.get("fallback_front_keys")
        if not isinstance(raw_keys, list):
            proxy_row["_fallback_front_rows"] = []
            return []
        keys: list[str] = []
        seen: set[str] = set()
        current_key = str(proxy_row.get("normalized_key") or "")
        for item in raw_keys:
            key = str(item or "").strip()
            if not key or key == current_key or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        if not keys:
            proxy_row["_fallback_front_rows"] = []
            return []
        rows = self.storage.get_proxies_by_keys(keys)
        proxy_row["_fallback_front_rows"] = rows
        return rows


def _resolve_ip(host: str) -> str:
    return socket.gethostbyname(host)


def _lookup_geo(ip: str) -> tuple[str, str]:
    req = Request(
        f"http://ip-api.com/json/{ip}?lang=zh-CN&fields=status,country,city,query",
        headers={"User-Agent": "proxypool/0.1"},
    )
    with urlopen(req, timeout=4) as resp:  # nosec B310
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    if str(data.get("status")) != "success":
        return "", ""
    return str(data.get("country") or ""), str(data.get("city") or "")


def _lookup_ip_purity(ip: str) -> tuple[float | None, str]:
    residential_votes = {
        "ip2location": _parse_residential_from_ip2location(
            _fetch_json(
                f"https://ipinfo.check.place/{ip}?db=ip2location",
                timeout_sec=12.0,
                headers={"User-Agent": "Mozilla/5.0 proxypool/0.1"},
            )
        ),
        "iplark": _parse_residential_from_iplark(
            _fetch_json(
                f"https://ipinfo.check.place/{ip}?db=iplark",
                timeout_sec=12.0,
                headers={"User-Agent": "Mozilla/5.0 proxypool/0.1"},
            )
        ),
        "ipinfo": _parse_residential_from_ipinfo_network(
            _fetch_json(
                f"https://ipinfo.io/{ip}/json",
                timeout_sec=10.0,
                headers={"User-Agent": "proxypool/0.1"},
            )
        ),
        "ippure": _parse_residential_from_ippure(
            _fetch_json(
                f"https://ipinfo.check.place/{ip}?db=ippure",
                timeout_sec=12.0,
                headers={"User-Agent": "Mozilla/5.0 proxypool/0.1"},
            )
        ),
    }
    return _residential_result_from_votes(residential_votes)


def _lookup_ipapi_score(ip: str) -> float | None:
    data = _fetch_json(
        f"https://api.ipapi.is/?q={ip}",
        timeout_sec=6,
        headers={"User-Agent": "proxypool/0.1"},
    )
    return _parse_ipapi_score(data)


def _lookup_ipinfo_db_score(ip: str, db_name: str) -> float | None:
    data = _fetch_json(
        f"https://ipinfo.check.place/{ip}?db={db_name}",
        timeout_sec=8,
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 proxypool/0.1"},
    )
    return _parse_ipinfo_db_score(data, db_name)


def _parse_geo_from_ip_api(data: object) -> tuple[str, str, str] | None:
    if not isinstance(data, dict):
        return None
    if str(data.get("status") or "") != "success":
        return None
    ip = str(data.get("query") or "").strip()
    country = str(data.get("country") or "").strip()
    city = str(data.get("city") or "").strip()
    return _normalize_geo_triplet(ip, country, city)


def _parse_geo_from_ipinfo(data: object) -> tuple[str, str, str] | None:
    if not isinstance(data, dict):
        return None
    ip = str(data.get("ip") or "").strip()
    country = str(data.get("country") or "").strip()
    city = str(data.get("city") or "").strip()
    return _normalize_geo_triplet(ip, country, city)


def _parse_geo_from_ipwhois(data: object) -> tuple[str, str, str] | None:
    if not isinstance(data, dict):
        return None
    if "success" in data and data.get("success") is False:
        return None
    ip = str(data.get("ip") or "").strip()
    country = str(data.get("country") or data.get("country_code") or "").strip()
    city = str(data.get("city") or "").strip()
    return _normalize_geo_triplet(ip, country, city)


def _parse_geo_from_ifconfig(data: object) -> tuple[str, str, str] | None:
    if not isinstance(data, dict):
        return None
    ip = str(data.get("ip") or "").strip()
    country = str(data.get("country") or data.get("country_iso") or "").strip()
    city = str(data.get("city") or "").strip()
    return _normalize_geo_triplet(ip, country, city)


def _parse_geo_from_ipsb(data: object) -> tuple[str, str, str] | None:
    if not isinstance(data, dict):
        return None
    ip = str(data.get("ip") or "").strip()
    country = str(data.get("country") or data.get("country_code") or "").strip()
    city = str(data.get("city") or "").strip()
    return _normalize_geo_triplet(ip, country, city)


def _normalize_geo_triplet(ip: str, country: str, city: str) -> tuple[str, str, str] | None:
    if not ip:
        return None
    # Require at least one location field to count as a successful geo fill.
    if not country and not city:
        return None
    return ip, country, city


def _parse_ipapi_score(data: object) -> float | None:
    if not isinstance(data, dict):
        return None
    score_text = str(((data.get("company") or {}).get("abuser_score")) or "").strip()
    if not score_text:
        return None
    # Typical value: "0.0156 (Elevated)".
    m = re.search(r"([0-9]*\.?[0-9]+)", score_text)
    if not m:
        return None
    return _clamp_score(float(m.group(1)) * 100)


def _parse_ipinfo_db_score(data: object, db_name: str) -> float | None:
    if not isinstance(data, dict):
        return None
    if db_name == "ipqualityscore":
        return _to_float_score(data.get("fraud_score"))
    if db_name == "scamalytics":
        return _to_float_score((data.get("scamalytics") or {}).get("scamalytics_score"))
    if db_name == "abuseipdb":
        return _to_float_score((data.get("data") or {}).get("abuseConfidenceScore"))
    if db_name == "ip2location":
        return _to_float_score(data.get("fraud_score"))
    if db_name == "ipdata":
        threat = data.get("threat") or {}
        is_bad = any(
            bool(threat.get(key))
            for key in ("is_threat", "is_known_abuser", "is_known_attacker", "is_proxy", "is_tor")
        )
        return 80.0 if is_bad else 10.0
    return None


def _parse_residential_from_ip2location(data: object) -> bool | None:
    if not isinstance(data, dict):
        return None
    # Common indicator fields.
    usage_type = str(
        data.get("usage_type")
        or (data.get("data") or {}).get("usage_type")
        or ""
    ).strip().upper()
    if usage_type:
        if usage_type in {"RES", "ISP"}:
            return True
        if usage_type in {"DCH", "SES", "CDN", "COM", "ORG", "GOV", "MIL", "EDU", "LIB", "HOS"}:
            return False
    # Proxy/datacenter hints.
    return _extract_bool_by_keys(
        data,
        true_keys=("is_residential", "residential"),
        false_keys=("is_proxy", "proxy", "hosting", "datacenter"),
    )


def _parse_residential_from_iplark(data: object) -> bool | None:
    if not isinstance(data, dict):
        return None
    return _extract_bool_by_keys(
        data,
        true_keys=("is_residential", "residential", "is_isp"),
        false_keys=("is_proxy", "proxy", "hosting", "datacenter", "is_datacenter"),
    )


def _parse_residential_from_ippure(data: object) -> bool | None:
    if not isinstance(data, dict):
        return None
    return _extract_bool_by_keys(
        data,
        true_keys=("is_residential", "residential", "home"),
        false_keys=("is_proxy", "proxy", "hosting", "datacenter", "cloud"),
    )


def _parse_residential_from_ipinfo_network(data: object) -> bool | None:
    if not isinstance(data, dict):
        return None

    company = data.get("company") or {}
    if isinstance(company, dict):
        ctype = str(company.get("type") or "").strip().lower()
        if ctype in {"hosting", "business"}:
            return False
        if ctype in {"isp", "residential"}:
            return True

    privacy = data.get("privacy") or {}
    if isinstance(privacy, dict):
        for k in ("hosting", "proxy", "vpn", "tor", "relay"):
            if bool(privacy.get(k)):
                return False

    org_text = " ".join(
        str(x or "")
        for x in (
            data.get("org"),
            data.get("asn"),
            company.get("name") if isinstance(company, dict) else "",
            (data.get("carrier") or {}).get("name") if isinstance(data.get("carrier"), dict) else "",
        )
    ).strip().lower()
    if org_text:
        if any(s in org_text for s in _DATACENTER_KEYWORDS):
            return False
        if any(s in org_text for s in _ISP_KEYWORDS):
            return True
    return None


def _extract_bool_by_keys(
    data: dict,
    true_keys: tuple[str, ...],
    false_keys: tuple[str, ...],
) -> bool | None:
    def _iter_values(obj: object):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield str(k).strip().lower(), v
                yield from _iter_values(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from _iter_values(item)

    found_true = False
    found_false = False
    true_set = {k.lower() for k in true_keys}
    false_set = {k.lower() for k in false_keys}
    for key, val in _iter_values(data):
        if not isinstance(val, (bool, int, float, str)):
            continue
        norm = _to_bool(val)
        if norm is None:
            continue
        if key in true_set and norm is True:
            found_true = True
        if key in false_set and norm is True:
            found_false = True
    if found_true and not found_false:
        return True
    if found_false and not found_true:
        return False
    return None


def _to_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _residential_result_from_votes(votes: dict[str, bool | None]) -> tuple[float | None, str]:
    total_weight = 0.0
    residential_weight = 0.0
    non_residential_weight = 0.0
    for name, decision in votes.items():
        if decision is None:
            continue
        weight = float(_RESIDENTIAL_SOURCE_WEIGHTS.get(name, 0.0))
        if weight <= 0:
            continue
        total_weight += weight
        if decision:
            residential_weight += weight
        else:
            non_residential_weight += weight
    if total_weight <= 0:
        return None, "未知"
    residential_ratio = residential_weight / total_weight
    score = round(residential_ratio * 100.0, 2)
    if residential_ratio >= 0.6:
        return score, "家宽"
    if residential_ratio <= 0.4:
        return score, "非家宽"
    return score, "未知"


def _fetch_json(url: str, timeout_sec: float, headers: dict[str, str] | None = None) -> dict | None:
    req = Request(url, headers=headers or {"User-Agent": "proxypool/0.1"})
    try:
        with urlopen(req, timeout=timeout_sec) as resp:  # nosec B310
            text = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None
    try:
        data = json.loads(text)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _weighted_purity_score(scores: dict[str, float | None]) -> tuple[float | None, str]:
    weighted = 0.0
    total_weight = 0.0
    for name, weight in _PURITY_SOURCE_WEIGHTS.items():
        score = scores.get(name)
        if score is None:
            continue
        total_weight += float(weight)
        weighted += float(weight) * _clamp_score(float(score))
    if total_weight <= 0:
        return None, ""
    score = round(weighted / total_weight, 2)
    return score, _risk_from_score(score)


def _to_float_score(value: object) -> float | None:
    try:
        return _clamp_score(float(value))  # type: ignore[arg-type]
    except Exception:
        return None


def _clamp_score(score: float) -> float:
    if score < 0:
        return 0.0
    if score > 100:
        return 100.0
    return float(score)


def _risk_from_score(score: float) -> str:
    if score < 1:
        return "Very Low"
    if score < 5:
        return "Low"
    if score < 20:
        return "Elevated"
    if score < 50:
        return "High"
    return "Very High"


def _supports_front_proxy_arg(fetcher: ProxyJSONFetcher | None) -> bool:
    if fetcher is None:
        return False
    try:
        sig = inspect.signature(fetcher)
    except Exception:
        return True
    params = list(sig.parameters.values())
    if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
        return True
    return len(params) >= 4
