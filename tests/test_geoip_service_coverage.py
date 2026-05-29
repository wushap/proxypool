"""Tests for proxypool.geoip.service -- pure functions, parsers, and edge-case paths."""

from __future__ import annotations

import inspect
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from proxypool.geoip.service import (
    GeoIPService,
    GeoResult,
    _clamp_score,
    _extract_bool_by_keys,
    _parse_geo_from_ifconfig,
    _parse_geo_from_ip_api,
    _parse_geo_from_ipinfo,
    _parse_geo_from_ipwhois,
    _parse_geo_from_ipsb,
    _parse_ipapi_score,
    _parse_ipinfo_db_score,
    _parse_residential_from_ip2location,
    _parse_residential_from_iplark,
    _parse_residential_from_ipinfo_network,
    _parse_residential_from_ippure,
    _residential_result_from_votes,
    _risk_from_score,
    _supports_front_proxy_arg,
    _to_bool,
    _to_float_score,
    _weighted_purity_score,
)
from proxypool.models import ProxyNode
from proxypool.storage.sqlite import SQLiteProxyStorage


# ============================================================
# GeoResult dataclass
# ============================================================


class TestGeoResult:
    def test_defaults(self) -> None:
        r = GeoResult(normalized_key="k")
        assert r.normalized_key == "k"
        assert r.resolved_ip == ""
        assert r.country == ""
        assert r.city == ""
        assert r.ip_purity_score is None
        assert r.ip_purity_level == ""
        assert r.ok is False
        assert r.error == ""

    def test_ok_result(self) -> None:
        r = GeoResult(
            normalized_key="k",
            resolved_ip="1.1.1.1",
            country="US",
            city="NYC",
            ip_purity_score=95.0,
            ip_purity_level="Very Low",
            ok=True,
        )
        assert r.ok is True
        assert r.ip_purity_score == 95.0


# ============================================================
# _clamp_score
# ============================================================


class TestClampScore:
    def test_negative(self) -> None:
        assert _clamp_score(-10) == 0.0

    def test_zero(self) -> None:
        assert _clamp_score(0) == 0.0

    def test_normal(self) -> None:
        assert _clamp_score(50.5) == 50.5

    def test_over_100(self) -> None:
        assert _clamp_score(150) == 100.0

    def test_exactly_100(self) -> None:
        assert _clamp_score(100) == 100.0


# ============================================================
# _risk_from_score
# ============================================================


class TestRiskFromScore:
    def test_very_low(self) -> None:
        assert _risk_from_score(0.5) == "Very Low"

    def test_low(self) -> None:
        assert _risk_from_score(3.0) == "Low"

    def test_elevated(self) -> None:
        assert _risk_from_score(15.0) == "Elevated"

    def test_high(self) -> None:
        assert _risk_from_score(40.0) == "High"

    def test_very_high(self) -> None:
        assert _risk_from_score(80.0) == "Very High"

    def test_boundary_1(self) -> None:
        assert _risk_from_score(1.0) == "Low"

    def test_boundary_5(self) -> None:
        assert _risk_from_score(5.0) == "Elevated"

    def test_boundary_20(self) -> None:
        assert _risk_from_score(20.0) == "High"

    def test_boundary_50(self) -> None:
        assert _risk_from_score(50.0) == "Very High"


# ============================================================
# _to_bool
# ============================================================


class TestToBool:
    def test_bool_true(self) -> None:
        assert _to_bool(True) is True

    def test_bool_false(self) -> None:
        assert _to_bool(False) is False

    def test_int_one(self) -> None:
        assert _to_bool(1) is True

    def test_int_zero(self) -> None:
        assert _to_bool(0) is False

    def test_float_nonzero(self) -> None:
        assert _to_bool(0.5) is True

    def test_float_zero(self) -> None:
        assert _to_bool(0.0) is False

    def test_string_true_variants(self) -> None:
        for val in ("1", "true", "yes", "y", "on", "True", "YES"):
            assert _to_bool(val) is True, f"expected True for {val!r}"

    def test_string_false_variants(self) -> None:
        for val in ("0", "false", "no", "n", "off", "False", "NO"):
            assert _to_bool(val) is False, f"expected False for {val!r}"

    def test_string_unknown(self) -> None:
        assert _to_bool("maybe") is None
        assert _to_bool("") is None


# ============================================================
# _to_float_score
# ============================================================


class TestToFloatScore:
    def test_valid_int(self) -> None:
        assert _to_float_score(42) == 42.0

    def test_valid_float(self) -> None:
        assert _to_float_score(3.14) == 3.14

    def test_valid_string_number(self) -> None:
        assert _to_float_score("7.5") == 7.5

    def test_invalid_string(self) -> None:
        assert _to_float_score("abc") is None

    def test_none(self) -> None:
        assert _to_float_score(None) is None

    def test_clamp_over_100(self) -> None:
        assert _to_float_score(150) == 100.0

    def test_clamp_negative(self) -> None:
        assert _to_float_score(-5) == 0.0


# ============================================================
# _normalize_geo_triplet
# ============================================================


class TestNormalizeGeoTriplet:
    def test_missing_ip(self) -> None:
        from proxypool.geoip.service import _normalize_geo_triplet as fn

        assert fn("", "US", "NYC") is None

    def test_ip_with_country_and_city(self) -> None:
        from proxypool.geoip.service import _normalize_geo_triplet as fn

        assert fn("1.1.1.1", "US", "NYC") == ("1.1.1.1", "US", "NYC")

    def test_ip_with_country_only(self) -> None:
        from proxypool.geoip.service import _normalize_geo_triplet as fn

        assert fn("1.1.1.1", "US", "") == ("1.1.1.1", "US", "")

    def test_ip_with_city_only(self) -> None:
        from proxypool.geoip.service import _normalize_geo_triplet as fn

        assert fn("1.1.1.1", "", "NYC") == ("1.1.1.1", "", "NYC")

    def test_ip_no_location(self) -> None:
        from proxypool.geoip.service import _normalize_geo_triplet as fn

        assert fn("1.1.1.1", "", "") is None


# ============================================================
# _parse_geo_from_ip_api
# ============================================================


class TestParseGeoFromIpApi:
    def test_success(self) -> None:
        data = {
            "status": "success",
            "query": "203.0.113.1",
            "country": "Japan",
            "city": "Tokyo",
        }
        result = _parse_geo_from_ip_api(data)
        assert result == ("203.0.113.1", "Japan", "Tokyo")

    def test_fail_status(self) -> None:
        data = {"status": "fail", "message": "limit"}
        assert _parse_geo_from_ip_api(data) is None

    def test_not_a_dict(self) -> None:
        assert _parse_geo_from_ip_api("string") is None
        assert _parse_geo_from_ip_api(None) is None
        assert _parse_geo_from_ip_api([1]) is None

    def test_missing_query(self) -> None:
        data = {"status": "success", "country": "US", "city": "NYC"}
        assert _parse_geo_from_ip_api(data) is None

    def test_empty_country_and_city(self) -> None:
        data = {"status": "success", "query": "1.1.1.1", "country": "", "city": ""}
        assert _parse_geo_from_ip_api(data) is None


# ============================================================
# _parse_geo_from_ipinfo
# ============================================================


class TestParseGeoFromIpinfo:
    def test_valid(self) -> None:
        data = {"ip": "8.8.8.8", "country": "US", "city": "Mountain View"}
        result = _parse_geo_from_ipinfo(data)
        assert result == ("8.8.8.8", "US", "Mountain View")

    def test_not_a_dict(self) -> None:
        assert _parse_geo_from_ipinfo(None) is None
        assert _parse_geo_from_ipinfo(42) is None

    def test_missing_ip(self) -> None:
        data = {"country": "US", "city": "NYC"}
        assert _parse_geo_from_ipinfo(data) is None

    def test_ip_only_no_location(self) -> None:
        data = {"ip": "1.1.1.1", "country": "", "city": ""}
        assert _parse_geo_from_ipinfo(data) is None


# ============================================================
# _parse_geo_from_ipwhois
# ============================================================


class TestParseGeoFromIpwhois:
    def test_valid(self) -> None:
        data = {"ip": "1.2.3.4", "country": "Germany", "city": "Berlin"}
        result = _parse_geo_from_ipwhois(data)
        assert result == ("1.2.3.4", "Germany", "Berlin")

    def test_success_false(self) -> None:
        data = {"success": False, "ip": "1.2.3.4"}
        assert _parse_geo_from_ipwhois(data) is None

    def test_not_a_dict(self) -> None:
        assert _parse_geo_from_ipwhois(None) is None

    def test_country_code_fallback(self) -> None:
        data = {"ip": "5.5.5.5", "country_code": "FR", "city": "Paris"}
        result = _parse_geo_from_ipwhois(data)
        assert result == ("5.5.5.5", "FR", "Paris")

    def test_ip_only_no_location(self) -> None:
        data = {"ip": "5.5.5.5", "country": "", "city": ""}
        assert _parse_geo_from_ipwhois(data) is None


# ============================================================
# _parse_geo_from_ifconfig
# ============================================================


class TestParseGeoFromIfconfig:
    def test_valid(self) -> None:
        data = {"ip": "9.9.9.9", "country": "Canada", "city": "Toronto"}
        result = _parse_geo_from_ifconfig(data)
        assert result == ("9.9.9.9", "Canada", "Toronto")

    def test_not_a_dict(self) -> None:
        assert _parse_geo_from_ifconfig([]) is None

    def test_country_iso_fallback(self) -> None:
        data = {"ip": "3.3.3.3", "country_iso": "GB", "city": "London"}
        result = _parse_geo_from_ifconfig(data)
        assert result == ("3.3.3.3", "GB", "London")

    def test_ip_only_no_location(self) -> None:
        data = {"ip": "3.3.3.3"}
        assert _parse_geo_from_ifconfig(data) is None


# ============================================================
# _parse_geo_from_ipsb
# ============================================================


class TestParseGeoFromIpsb:
    def test_valid(self) -> None:
        data = {"ip": "4.4.4.4", "country": "Korea", "city": "Seoul"}
        result = _parse_geo_from_ipsb(data)
        assert result == ("4.4.4.4", "Korea", "Seoul")

    def test_not_a_dict(self) -> None:
        assert _parse_geo_from_ipsb(123) is None

    def test_country_code_fallback(self) -> None:
        data = {"ip": "7.7.7.7", "country_code": "BR", "city": "Sao Paulo"}
        result = _parse_geo_from_ipsb(data)
        assert result == ("7.7.7.7", "BR", "Sao Paulo")

    def test_ip_only_no_location(self) -> None:
        data = {"ip": "7.7.7.7"}
        assert _parse_geo_from_ipsb(data) is None


# ============================================================
# _parse_ipapi_score
# ============================================================


class TestParseIpapiScore:
    def test_valid_score(self) -> None:
        data = {"company": {"abuser_score": "0.0156 (Elevated)"}}
        result = _parse_ipapi_score(data)
        assert result is not None
        assert abs(result - 1.56) < 0.01

    def test_not_a_dict(self) -> None:
        assert _parse_ipapi_score(None) is None

    def test_missing_company(self) -> None:
        assert _parse_ipapi_score({}) is None

    def test_empty_score(self) -> None:
        data = {"company": {"abuser_score": ""}}
        assert _parse_ipapi_score(data) is None

    def test_no_numeric_match(self) -> None:
        data = {"company": {"abuser_score": "N/A"}}
        assert _parse_ipapi_score(data) is None

    def test_high_score_clamped(self) -> None:
        data = {"company": {"abuser_score": "2.0"}}
        result = _parse_ipapi_score(data)
        assert result == 100.0

    def test_zero_score(self) -> None:
        data = {"company": {"abuser_score": "0.0"}}
        result = _parse_ipapi_score(data)
        assert result == 0.0


# ============================================================
# _parse_ipinfo_db_score
# ============================================================


class TestParseIpinfoDbScore:
    def test_ipqualityscore(self) -> None:
        data = {"fraud_score": 75}
        assert _parse_ipinfo_db_score(data, "ipqualityscore") == 75.0

    def test_scamalytics(self) -> None:
        data = {"scamalytics": {"scamalytics_score": 45.5}}
        assert _parse_ipinfo_db_score(data, "scamalytics") == 45.5

    def test_abuseipdb(self) -> None:
        data = {"data": {"abuseConfidenceScore": 30}}
        assert _parse_ipinfo_db_score(data, "abuseipdb") == 30.0

    def test_ip2location(self) -> None:
        data = {"fraud_score": 10}
        assert _parse_ipinfo_db_score(data, "ip2location") == 10.0

    def test_ipdata_threat(self) -> None:
        data = {"threat": {"is_threat": True}}
        assert _parse_ipinfo_db_score(data, "ipdata") == 80.0

    def test_ipdata_no_threat(self) -> None:
        data = {"threat": {}}
        assert _parse_ipinfo_db_score(data, "ipdata") == 10.0

    def test_ipdata_multiple_threat_keys(self) -> None:
        data = {"threat": {"is_proxy": True, "is_tor": False}}
        assert _parse_ipinfo_db_score(data, "ipdata") == 80.0

    def test_unknown_db(self) -> None:
        assert _parse_ipinfo_db_score({}, "unknown_db") is None

    def test_not_a_dict(self) -> None:
        assert _parse_ipinfo_db_score(None, "ipqualityscore") is None

    def test_ipqualityscore_none_value(self) -> None:
        assert _parse_ipinfo_db_score({}, "ipqualityscore") is None

    def test_scamalytics_missing_inner(self) -> None:
        assert _parse_ipinfo_db_score({}, "scamalytics") is None

    def test_abuseipdb_missing_data(self) -> None:
        assert _parse_ipinfo_db_score({}, "abuseipdb") is None


# ============================================================
# _parse_residential_from_ip2location
# ============================================================


class TestParseResidentialFromIp2location:
    def test_res(self) -> None:
        assert _parse_residential_from_ip2location({"usage_type": "RES"}) is True

    def test_isp(self) -> None:
        assert _parse_residential_from_ip2location({"usage_type": "ISP"}) is True

    def test_dch(self) -> None:
        assert _parse_residential_from_ip2location({"usage_type": "DCH"}) is False

    def test_cdn(self) -> None:
        assert _parse_residential_from_ip2location({"usage_type": "CDN"}) is False

    def test_data_usage_type(self) -> None:
        assert _parse_residential_from_ip2location({"usage_type": "SES"}) is False

    def test_com(self) -> None:
        assert _parse_residential_from_ip2location({"usage_type": "COM"}) is False

    def test_not_a_dict(self) -> None:
        assert _parse_residential_from_ip2location(None) is None

    def test_bool_key_true(self) -> None:
        assert _parse_residential_from_ip2location({"is_residential": True}) is True

    def test_bool_key_false(self) -> None:
        assert _parse_residential_from_ip2location({"hosting": True}) is False

    def test_nested_data_usage_type(self) -> None:
        assert _parse_residential_from_ip2location({"data": {"usage_type": "RES"}}) is True

    def test_no_matching_keys(self) -> None:
        assert _parse_residential_from_ip2location({"random": "value"}) is None

    def test_empty_usage_types(self) -> None:
        for ut in ("GOV", "MIL", "EDU", "LIB", "HOS"):
            assert _parse_residential_from_ip2location({"usage_type": ut}) is False


# ============================================================
# _parse_residential_from_iplark
# ============================================================


class TestParseResidentialFromIplark:
    def test_residential(self) -> None:
        assert _parse_residential_from_iplark({"is_residential": True}) is True

    def test_datacenter(self) -> None:
        assert _parse_residential_from_iplark({"is_datacenter": True}) is False

    def test_not_a_dict(self) -> None:
        assert _parse_residential_from_iplark(None) is None

    def test_is_isp(self) -> None:
        assert _parse_residential_from_iplark({"is_isp": True}) is True

    def test_hosting(self) -> None:
        assert _parse_residential_from_iplark({"hosting": True}) is False

    def test_no_match(self) -> None:
        assert _parse_residential_from_iplark({"foo": "bar"}) is None


# ============================================================
# _parse_residential_from_ippure
# ============================================================


class TestParseResidentialFromIppure:
    def test_residential(self) -> None:
        assert _parse_residential_from_ippure({"is_residential": True}) is True

    def test_home(self) -> None:
        assert _parse_residential_from_ippure({"home": True}) is True

    def test_cloud(self) -> None:
        assert _parse_residential_from_ippure({"cloud": True}) is False

    def test_not_a_dict(self) -> None:
        assert _parse_residential_from_ippure(None) is None

    def test_no_match(self) -> None:
        assert _parse_residential_from_ippure({"other": True}) is None


# ============================================================
# _parse_residential_from_ipinfo_network
# ============================================================


class TestParseResidentialFromIpinfoNetwork:
    def test_company_type_isp(self) -> None:
        data = {"company": {"type": "isp"}}
        assert _parse_residential_from_ipinfo_network(data) is True

    def test_company_type_hosting(self) -> None:
        data = {"company": {"type": "hosting"}}
        assert _parse_residential_from_ipinfo_network(data) is False

    def test_company_type_business(self) -> None:
        data = {"company": {"type": "business"}}
        assert _parse_residential_from_ipinfo_network(data) is False

    def test_company_type_residential(self) -> None:
        data = {"company": {"type": "residential"}}
        assert _parse_residential_from_ipinfo_network(data) is True

    def test_privacy_vpn(self) -> None:
        data = {"privacy": {"vpn": True}}
        assert _parse_residential_from_ipinfo_network(data) is False

    def test_privacy_tor(self) -> None:
        data = {"privacy": {"tor": True}}
        assert _parse_residential_from_ipinfo_network(data) is False

    def test_privacy_hosting(self) -> None:
        data = {"privacy": {"hosting": True}}
        assert _parse_residential_from_ipinfo_network(data) is False

    def test_privacy_proxy(self) -> None:
        data = {"privacy": {"proxy": True}}
        assert _parse_residential_from_ipinfo_network(data) is False

    def test_privacy_relay(self) -> None:
        data = {"privacy": {"relay": True}}
        assert _parse_residential_from_ipinfo_network(data) is False

    def test_org_with_isp_keyword(self) -> None:
        data = {"org": "Comcast Telecom"}
        assert _parse_residential_from_ipinfo_network(data) is True

    def test_org_with_datacenter_keyword(self) -> None:
        data = {"org": "Amazon Datacenter"}
        assert _parse_residential_from_ipinfo_network(data) is False

    def test_no_match(self) -> None:
        data = {"org": "Random Org"}
        assert _parse_residential_from_ipinfo_network(data) is None

    def test_not_a_dict(self) -> None:
        assert _parse_residential_from_ipinfo_network(None) is None

    def test_empty_data(self) -> None:
        assert _parse_residential_from_ipinfo_network({}) is None

    def test_carrier_name_isp(self) -> None:
        data = {"carrier": {"name": "Verizon Mobile"}}
        assert _parse_residential_from_ipinfo_network(data) is True

    def test_asn_datacenter(self) -> None:
        data = {"asn": "AS13335 Google Cloud"}
        assert _parse_residential_from_ipinfo_network(data) is False

    def test_company_name_only(self) -> None:
        data = {"company": {"name": "AT&T Communications"}}
        assert _parse_residential_from_ipinfo_network(data) is True


# ============================================================
# _extract_bool_by_keys
# ============================================================


class TestExtractBoolByKeys:
    def test_true_match(self) -> None:
        result = _extract_bool_by_keys(
            {"is_residential": True},
            true_keys=("is_residential",),
            false_keys=(),
        )
        assert result is True

    def test_false_match(self) -> None:
        result = _extract_bool_by_keys(
            {"hosting": True},
            true_keys=(),
            false_keys=("hosting",),
        )
        assert result is False

    def test_conflict_returns_none(self) -> None:
        result = _extract_bool_by_keys(
            {"is_residential": True, "hosting": True},
            true_keys=("is_residential",),
            false_keys=("hosting",),
        )
        assert result is None

    def test_no_match(self) -> None:
        result = _extract_bool_by_keys(
            {"other": True},
            true_keys=("is_residential",),
            false_keys=("hosting",),
        )
        assert result is None

    def test_nested_dict(self) -> None:
        data = {"outer": {"is_residential": True}}
        result = _extract_bool_by_keys(
            data,
            true_keys=("is_residential",),
            false_keys=(),
        )
        assert result is True

    def test_list_of_dicts(self) -> None:
        data = [{"hosting": True}, {"other": "val"}]
        result = _extract_bool_by_keys(
            data,
            true_keys=(),
            false_keys=("hosting",),
        )
        assert result is False

    def test_non_bool_value_ignored(self) -> None:
        result = _extract_bool_by_keys(
            {"is_residential": "notabool"},
            true_keys=("is_residential",),
            false_keys=(),
        )
        assert result is None


# ============================================================
# _residential_result_from_votes
# ============================================================


class TestResidentialResultFromVotes:
    def test_all_residential(self) -> None:
        score, level = _residential_result_from_votes({
            "ip2location": True,
            "ippure": True,
            "iplark": True,
            "ipinfo": True,
        })
        assert score == 100.0
        assert level == "家宽"

    def test_all_non_residential(self) -> None:
        score, level = _residential_result_from_votes({
            "ip2location": False,
            "ippure": False,
            "iplark": False,
            "ipinfo": False,
        })
        assert score == 0.0
        assert level == "非家宽"

    def test_mixed_majority_residential(self) -> None:
        score, level = _residential_result_from_votes({
            "ip2location": True,
            "ippure": True,
            "iplark": False,
            "ipinfo": False,
        })
        # ip2location=0.35, ippure=0.25 -> 0.60 of total 1.0 -> 60% -> "家宽"
        assert level == "家宽"

    def test_mixed_majority_non_residential(self) -> None:
        score, level = _residential_result_from_votes({
            "ip2location": False,
            "ippure": False,
            "iplark": True,
            "ipinfo": False,
        })
        # ip2location=0.35 + ippure=0.25 non-res = 0.60 of 1.0
        assert level == "非家宽"

    def test_no_votes(self) -> None:
        score, level = _residential_result_from_votes({
            "ip2location": None,
            "ippure": None,
        })
        assert score is None
        assert level == "未知"

    def test_undefined_source(self) -> None:
        score, level = _residential_result_from_votes({
            "unknown_source": True,
        })
        assert score is None
        assert level == "未知"

    def test_balanced_returns_unknown(self) -> None:
        # ip2location(True, weight=0.35) vs iplark(False, weight=0.20) + ipinfo(False, weight=0.20)
        # residential = 0.35 / 0.75 = 0.4666... -> between 0.4 and 0.6 -> "未知"
        score, level = _residential_result_from_votes({
            "ip2location": True,
            "iplark": False,
            "ipinfo": False,
        })
        assert level == "未知"
        assert score is not None


# ============================================================
# _weighted_purity_score
# ============================================================


class TestWeightedPurityScore:
    def test_all_none(self) -> None:
        score, level = _weighted_purity_score({
            "ipapi": None,
            "ipqualityscore": None,
            "scamalytics": None,
            "abuseipdb": None,
            "ip2location": None,
            "ipdata": None,
        })
        assert score is None
        assert level == ""

    def test_single_source(self) -> None:
        score, level = _weighted_purity_score({"ipapi": 50.0})
        assert score is not None
        assert score == 50.0
        assert level == "Very High"

    def test_very_low(self) -> None:
        score, level = _weighted_purity_score({"ipapi": 0.5})
        assert score is not None
        assert level == "Very Low"

    def test_low(self) -> None:
        score, level = _weighted_purity_score({"ipapi": 3.0})
        assert score is not None
        assert level == "Low"

    def test_elevated(self) -> None:
        score, level = _weighted_purity_score({"ipapi": 15.0})
        assert score is not None
        assert level == "Elevated"

    def test_very_high(self) -> None:
        score, level = _weighted_purity_score({"ipapi": 90.0})
        assert score is not None
        assert level == "Very High"

    def test_clamped_over_100(self) -> None:
        score, _ = _weighted_purity_score({"ipapi": 200.0})
        assert score == 100.0

    def test_clamped_negative(self) -> None:
        score, _ = _weighted_purity_score({"ipapi": -10.0})
        assert score == 0.0


# ============================================================
# _supports_front_proxy_arg
# ============================================================


class TestSupportsFrontProxyArg:
    def test_none_fetcher(self) -> None:
        assert _supports_front_proxy_arg(None) is False

    def test_4_params(self) -> None:
        def fetcher(a: dict, b: str, c: float, d: dict | None) -> dict:
            return {}

        assert _supports_front_proxy_arg(fetcher) is True

    def test_3_params(self) -> None:
        def fetcher(a: dict, b: str, c: float) -> dict:
            return {}

        assert _supports_front_proxy_arg(fetcher) is False

    def test_var_positional(self) -> None:
        def fetcher(*args: object) -> dict:
            return {}

        assert _supports_front_proxy_arg(fetcher) is True

    def test_lambda_no_annotation(self) -> None:
        # Lambda with 4 args
        fn = lambda a, b, c, d: {}  # noqa: E731
        assert _supports_front_proxy_arg(fn) is True

    def test_uninspectable(self) -> None:
        # Built-in that can't be inspected
        assert _supports_front_proxy_arg(print) is True


# ============================================================
# GeoIPService initialization
# ============================================================


class TestGeoIPServiceInit:
    def test_basic_init(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            assert service.storage is storage
            assert service._proxy_json_fetcher is None
            assert service._proxy_fetcher_supports_front is False

    def test_init_with_fetcher(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            def fetcher(a: dict, b: str, c: float, d: dict | None) -> dict:
                return {}

            service = GeoIPService(storage=storage, proxy_json_fetcher=fetcher)
            assert service._proxy_json_fetcher is fetcher
            assert service._proxy_fetcher_supports_front is True

    def test_init_with_3_arg_fetcher(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            def fetcher(a: dict, b: str, c: float) -> dict:
                return {}

            service = GeoIPService(storage=storage, proxy_json_fetcher=fetcher)
            assert service._proxy_fetcher_supports_front is False


# ============================================================
# GeoIPService.enrich_one edge cases
# ============================================================


class TestEnrichOne:
    def _svc(self, tmp_path: Path, **kwargs) -> tuple[GeoIPService, SQLiteProxyStorage]:
        db = tmp_path / "db.sqlite3"
        storage = SQLiteProxyStorage(db)
        service = GeoIPService(
            storage=storage,
            resolver=kwargs.get("resolver", lambda h: "1.1.1.1"),
            geo_lookup=kwargs.get("geo_lookup", lambda ip: ("US", "NYC")),
            purity_lookup=kwargs.get("purity_lookup", lambda ip: (5.0, "Low")),
            proxy_json_fetcher=kwargs.get("proxy_json_fetcher"),
        )
        return service, storage

    def test_missing_key(self, tmp_path: Path) -> None:
        service, _ = self._svc(tmp_path)
        result = service.enrich_one({"host": "example.com"})
        assert result.ok is False
        assert "missing key or host" in result.error

    def test_missing_host(self, tmp_path: Path) -> None:
        service, _ = self._svc(tmp_path)
        result = service.enrich_one({"normalized_key": "k"})
        assert result.ok is False
        assert "missing key or host" in result.error

    def test_empty_row(self, tmp_path: Path) -> None:
        service, _ = self._svc(tmp_path)
        result = service.enrich_one({})
        assert result.ok is False

    def test_direct_lookup_success(self, tmp_path: Path) -> None:
        service, storage = self._svc(tmp_path)
        node = ProxyNode(
            protocol="trojan", host="x.example.com", port=443,
            raw_link="trojan://x", extra={"password": "p"},
        )
        storage.upsert_proxy(node)
        result = service.enrich_one({
            "normalized_key": node.normalized_key(),
            "host": "x.example.com",
        })
        assert result.ok is True
        assert result.resolved_ip == "1.1.1.1"
        assert result.country == "US"
        assert result.city == "NYC"
        assert result.ip_purity_score == 5.0
        assert result.ip_purity_level == "Low"

    def test_direct_lookup_with_existing_ip(self, tmp_path: Path) -> None:
        service, _ = self._svc(tmp_path)
        result = service.enrich_one({
            "normalized_key": "k",
            "host": "x.example.com",
            "resolved_ip": "2.2.2.2",
            "country": "JP",
            "city": "Tokyo",
        })
        assert result.ok is True
        assert result.resolved_ip == "2.2.2.2"
        assert result.country == "JP"
        assert result.city == "Tokyo"

    def test_geo_lookup_exception(self, tmp_path: Path) -> None:
        def bad_geo(ip: str) -> tuple[str, str]:
            raise RuntimeError("geo lookup failed")

        service, _ = self._svc(tmp_path, geo_lookup=bad_geo)
        result = service.enrich_one({
            "normalized_key": "k",
            "host": "x.example.com",
        })
        # Should still succeed; country/city remain empty
        assert result.ok is True
        assert result.resolved_ip == "1.1.1.1"
        assert result.country == ""
        assert result.city == ""

    def test_purity_lookup_exception(self, tmp_path: Path) -> None:
        def bad_purity(ip: str):
            raise RuntimeError("purity failed")

        service, _ = self._svc(tmp_path, purity_lookup=bad_purity)
        result = service.enrich_one({
            "normalized_key": "k",
            "host": "x.example.com",
        })
        assert result.ok is True
        assert result.ip_purity_score is None
        assert result.ip_purity_level == ""

    def test_with_proxy_fetcher_success(self, tmp_path: Path) -> None:
        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            if "ip-api.com/json/" in url:
                return {"status": "success", "query": "3.3.3.3", "country": "UK", "city": "London"}
            if "ipinfo.check.place" in url and "db=ip2location" in url:
                return {"usage_type": "RES"}
            if "ipinfo.check.place" in url and "db=iplark" in url:
                return {"is_residential": True}
            if "ipinfo.check.place" in url and "db=ippure" in url:
                return {"residential": True}
            if "ipinfo.io/" in url and url.endswith("/json"):
                return {"ip": "3.3.3.3", "org": "ISP Fiber"}
            return {}

        service, _ = self._svc(tmp_path, proxy_json_fetcher=fetcher)
        result = service.enrich_one({
            "normalized_key": "k",
            "host": "x.example.com",
        })
        assert result.ok is True
        assert result.resolved_ip == "3.3.3.3"
        assert result.country == "UK"
        assert result.city == "London"

    def test_with_proxy_fetcher_geo_fails_fallback_to_direct(self, tmp_path: Path) -> None:
        call_count = 0

        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count <= 20:
                raise RuntimeError("proxy failed")
            raise RuntimeError("also fails")

        def resolver(host: str) -> str:
            return "5.5.5.5"

        service, _ = self._svc(
            tmp_path,
            resolver=resolver,
            geo_lookup=lambda ip: ("DE", "Berlin"),
            purity_lookup=lambda ip: (12.0, "Elevated"),
            proxy_json_fetcher=fetcher,
        )
        result = service.enrich_one({
            "normalized_key": "k",
            "host": "x.example.com",
        })
        assert result.ok is True
        assert result.resolved_ip == "5.5.5.5"
        assert result.country == "DE"

    def test_with_proxy_fetcher_purity_fallback_to_unknown(self, tmp_path: Path) -> None:
        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            if "ip-api.com/json/" in url:
                return {"status": "success", "query": "3.3.3.3", "country": "UK", "city": "London"}
            if "ipinfo.check.place" in url and "db=ip2location" in url:
                return {"usage_type": "RES"}
            if "ipinfo.check.place" in url and "db=iplark" in url:
                return {"is_residential": True}
            if "ipinfo.check.place" in url and "db=ippure" in url:
                return {"residential": True}
            if "ipinfo.io/" in url and url.endswith("/json"):
                return {"ip": "3.3.3.3", "org": "Random Corp"}
            raise RuntimeError("unexpected")

        def bad_purity(ip: str):
            return (None, "")

        service, _ = self._svc(tmp_path, purity_lookup=bad_purity, proxy_json_fetcher=fetcher)
        result = service.enrich_one({
            "normalized_key": "k",
            "host": "x.example.com",
        })
        assert result.ok is True


# ============================================================
# GeoIPService._enrich_ip_purity_one edge cases
# ============================================================


class TestEnrichIpPurityOne:
    def test_missing_key_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            assert service._enrich_ip_purity_one({"host": "x.com"}) is False

    def test_missing_host_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            assert service._enrich_ip_purity_one({"normalized_key": "k"}) is False

    def test_empty_row_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            assert service._enrich_ip_purity_one({}) is False

    def test_direct_path_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            node = ProxyNode(
                protocol="trojan", host="p.example.com", port=443,
                raw_link="trojan://p", extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)

            service = GeoIPService(
                storage=storage,
                resolver=lambda h: "4.4.4.4",
                geo_lookup=lambda ip: ("FR", "Paris"),
                purity_lookup=lambda ip: (3.5, "Low"),
            )
            row = storage.list_geo_candidates(limit=1, only_available=True, only_tested=True)[0]
            assert service._enrich_ip_purity_one(row) is True

    def test_with_proxy_fetcher_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            node = ProxyNode(
                protocol="trojan", host="pp.example.com", port=443,
                raw_link="trojan://pp", extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)

            def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
                if "ip-api.com/json/" in url:
                    return {"status": "success", "query": "6.6.6.6", "country": "CN", "city": "Beijing"}
                if "ipinfo.check.place" in url and "db=ip2location" in url:
                    return {"usage_type": "DCH"}
                if "ipinfo.check.place" in url and "db=iplark" in url:
                    return {"is_datacenter": True}
                if "ipinfo.check.place" in url and "db=ippure" in url:
                    return {"cloud": True}
                if "ipinfo.io/" in url and url.endswith("/json"):
                    return {"ip": "6.6.6.6", "company": {"type": "hosting"}}
                return {}

            service = GeoIPService(storage=storage, proxy_json_fetcher=fetcher)
            row = storage.list_geo_candidates(limit=1, only_available=True, only_tested=True)[0]
            assert service._enrich_ip_purity_one(row) is True

    def test_with_proxy_fetcher_exception_falls_back_to_direct(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            node = ProxyNode(
                protocol="trojan", host="pf.example.com", port=443,
                raw_link="trojan://pf", extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)

            def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
                raise RuntimeError("proxy fetch failed")

            service = GeoIPService(
                storage=storage,
                resolver=lambda h: "7.7.7.7",
                geo_lookup=lambda ip: ("KR", "Seoul"),
                purity_lookup=lambda ip: (20.0, "Elevated"),
                proxy_json_fetcher=fetcher,
            )
            row = storage.list_geo_candidates(limit=1, only_available=True, only_tested=True)[0]
            assert service._enrich_ip_purity_one(row) is True


# ============================================================
# GeoIPService._get_fallback_front_proxies
# ============================================================


class TestGetFallbackFrontProxies:
    def test_cached_list(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            cached = [{"key": "cached"}]
            row = {"_fallback_front_rows": cached}
            assert service._get_fallback_front_proxies(row) == cached

    def test_no_fallback_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            row = {"normalized_key": "k"}
            result = service._get_fallback_front_proxies(row)
            assert result == []
            assert row["_fallback_front_rows"] == []

    def test_fallback_keys_non_list(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            row = {"normalized_key": "k", "fallback_front_keys": "not-a-list"}
            result = service._get_fallback_front_proxies(row)
            assert result == []

    def test_with_valid_fallback_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            # Insert a proxy we can look up
            node = ProxyNode(
                protocol="trojan", host="front.example.com", port=443,
                raw_link="trojan://front", extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            front_key = node.normalized_key()

            service = GeoIPService(storage=storage)
            row = {
                "normalized_key": "exit-key",
                "fallback_front_keys": [front_key, "exit-key", "exit-key"],
            }
            result = service._get_fallback_front_proxies(row)
            # Should exclude current key and duplicates
            assert len(result) == 1

    def test_empty_fallback_keys_list(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            row = {"normalized_key": "k", "fallback_front_keys": []}
            result = service._get_fallback_front_proxies(row)
            assert result == []


# ============================================================
# GeoIPService._call_proxy_fetcher
# ============================================================


class TestCallProxyFetcher:
    def test_4_arg_fetcher(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            calls = []

            def fetcher(a: dict, b: str, c: float, d: dict | None) -> dict:
                calls.append((a, b, c, d))
                return {}

            service = GeoIPService(storage=storage, proxy_json_fetcher=fetcher)
            service._proxy_fetcher_supports_front = True
            result = service._call_proxy_fetcher(fetcher, {"r": 1}, "url", 5.0, None)
            assert result == {}
            assert len(calls) == 1
            assert calls[0] == ({"r": 1}, "url", 5.0, None)

    def test_3_arg_fetcher(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            calls = []

            def fetcher(a: dict, b: str, c: float) -> dict:
                calls.append((a, b, c))
                return {}

            service = GeoIPService(storage=storage)
            service._proxy_fetcher_supports_front = False
            result = service._call_proxy_fetcher(fetcher, {"r": 1}, "url", 5.0, None)
            assert result == {}
            assert len(calls) == 1


# ============================================================
# GeoIPService.enrich_batch cancellation and empty paths
# ============================================================


class TestEnrichBatchEdges:
    def test_stop_cb_immediate_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)

            from proxypool.tasks.manager import TaskCancelled
            with pytest.raises(TaskCancelled):
                service.enrich_batch(stop_cb=lambda: True)

    def test_empty_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            report = service.enrich_batch(limit=10)
            assert report["requested"] == 0
            assert report["updated"] == 0
            assert report["failed"] == 0

    def test_progress_cb_called(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(
                storage=storage,
                resolver=lambda h: "1.1.1.1",
                geo_lookup=lambda ip: ("US", "NYC"),
                purity_lookup=lambda ip: (2.0, "Low"),
            )
            progress_calls = []
            service.enrich_batch(limit=10, progress_cb=lambda d: progress_calls.append(d))
            phases = [p.get("phase") for p in progress_calls]
            assert "prepare" in phases
            assert "done" in phases

    def test_stop_during_enrichment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            for i in range(3):
                node = ProxyNode(
                    protocol="trojan", host=f"h{i}.example.com", port=443,
                    raw_link=f"trojan://h{i}", extra={"password": "p"},
                )
                storage.upsert_proxy(node)
                storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)

            from proxypool.tasks.manager import TaskCancelled

            call_count = 0

            def stop_cb() -> bool:
                nonlocal call_count
                call_count += 1
                return call_count > 1

            service = GeoIPService(
                storage=storage,
                resolver=lambda h: "1.1.1.1",
                geo_lookup=lambda ip: ("US", "NYC"),
                purity_lookup=lambda ip: (2.0, "Low"),
            )
            with pytest.raises(TaskCancelled):
                service.enrich_batch(limit=3, concurrency=1, stop_cb=stop_cb)


# ============================================================
# GeoIPService.enrich_ip_purity_batch cancellation and empty
# ============================================================


class TestEnrichIpPurityBatchEdges:
    def test_stop_cb_immediate_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)

            from proxypool.tasks.manager import TaskCancelled
            with pytest.raises(TaskCancelled):
                service.enrich_ip_purity_batch(stop_cb=lambda: True)

    def test_empty_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            report = service.enrich_ip_purity_batch(limit=10)
            assert report["requested"] == 0
            assert report["updated"] == 0
            assert report["failed"] == 0

    def test_progress_cb_called(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(
                storage=storage,
                resolver=lambda h: "1.1.1.1",
                geo_lookup=lambda ip: ("", ""),
                purity_lookup=lambda ip: (2.0, "Low"),
            )
            progress_calls = []
            service.enrich_ip_purity_batch(limit=10, progress_cb=lambda d: progress_calls.append(d))
            phases = [p.get("phase") for p in progress_calls]
            assert "prepare" in phases
            assert "done" in phases

    def test_stop_during_enrichment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            for i in range(3):
                node = ProxyNode(
                    protocol="trojan", host=f"h{i}.example.com", port=443,
                    raw_link=f"trojan://h{i}", extra={"password": "p"},
                )
                storage.upsert_proxy(node)
                storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)

            from proxypool.tasks.manager import TaskCancelled

            call_count = 0

            def stop_cb() -> bool:
                nonlocal call_count
                call_count += 1
                return call_count > 1

            service = GeoIPService(
                storage=storage,
                resolver=lambda h: "1.1.1.1",
                geo_lookup=lambda ip: ("", ""),
                purity_lookup=lambda ip: (2.0, "Low"),
            )
            with pytest.raises(TaskCancelled):
                service.enrich_ip_purity_batch(limit=3, concurrency=1, stop_cb=stop_cb)

    def test_future_exception_counted_as_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            node = ProxyNode(
                protocol="trojan", host="fail.example.com", port=443,
                raw_link="trojan://fail", extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            storage.update_test_result(node.normalized_key(), available=True, latency_ms=10)

            def bad_purity(ip: str):
                raise RuntimeError("always fails")

            service = GeoIPService(
                storage=storage,
                resolver=lambda h: "1.1.1.1",
                geo_lookup=lambda ip: ("", ""),
                purity_lookup=bad_purity,
            )
            report = service.enrich_ip_purity_batch(limit=1, concurrency=1)
            assert report["failed"] == 1
            assert report["updated"] == 0


# ============================================================
# _lookup_geo_direct paths
# ============================================================


class TestLookupGeoDirect:
    def test_uses_resolver_when_no_ip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            resolved = []
            service = GeoIPService(
                storage=storage,
                resolver=lambda h: (resolved.append(h), "1.1.1.1")[1],
                geo_lookup=lambda ip: ("US", "NYC"),
                purity_lookup=lambda ip: (1.0, "Low"),
            )
            ip, country, city = service._lookup_geo_direct({}, "example.com")
            assert ip == "1.1.1.1"
            assert country == "US"
            assert city == "NYC"
            assert "example.com" in resolved

    def test_uses_existing_ip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(
                storage=storage,
                resolver=lambda h: (_ for _ in ()).throw(AssertionError("should not call")),
                geo_lookup=lambda ip: ("US", "NYC"),
                purity_lookup=lambda ip: (1.0, "Low"),
            )
            ip, country, city = service._lookup_geo_direct(
                {"resolved_ip": "2.2.2.2"}, "example.com"
            )
            assert ip == "2.2.2.2"
            assert country == "US"
            assert city == "NYC"

    def test_uses_existing_country_and_city(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(
                storage=storage,
                resolver=lambda h: "1.1.1.1",
                geo_lookup=lambda ip: (_ for _ in ()).throw(AssertionError("should not call")),
                purity_lookup=lambda ip: (1.0, "Low"),
            )
            ip, country, city = service._lookup_geo_direct(
                {"resolved_ip": "3.3.3.3", "country": "JP", "city": "Tokyo"},
                "example.com",
            )
            assert country == "JP"
            assert city == "Tokyo"

    def test_geo_lookup_exception_silenced(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(
                storage=storage,
                resolver=lambda h: "1.1.1.1",
                geo_lookup=lambda ip: (_ for _ in ()).throw(RuntimeError("fail")),
                purity_lookup=lambda ip: (1.0, "Low"),
            )
            ip, country, city = service._lookup_geo_direct({}, "example.com")
            assert ip == "1.1.1.1"
            assert country == ""
            assert city == ""

    def test_partial_existing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(
                storage=storage,
                resolver=lambda h: "1.1.1.1",
                geo_lookup=lambda ip: ("FR", "Paris"),
                purity_lookup=lambda ip: (1.0, "Low"),
            )
            # Has country but no city
            ip, country, city = service._lookup_geo_direct(
                {"resolved_ip": "4.4.4.4", "country": "DE"},
                "example.com",
            )
            assert country == "DE"
            assert city == "Paris"


# ============================================================
# _lookup_geo_via_proxy with provider responses
# ============================================================


class TestLookupGeoViaProxy:
    def _make_service(self, fetcher):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            return GeoIPService(storage=storage, proxy_json_fetcher=fetcher)

    def test_all_providers_fail(self) -> None:
        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            return {}

        service = self._make_service(fetcher)
        with pytest.raises(RuntimeError, match="geo lookup failed"):
            service._lookup_geo_via_proxy({"host": "x.com"})

    def test_first_provider_succeeds(self) -> None:
        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            if "ip-api.com/json/" in url:
                return {"status": "success", "query": "1.1.1.1", "country": "US", "city": "NYC"}
            raise AssertionError("should not reach here")

        service = self._make_service(fetcher)
        result = service._lookup_geo_via_proxy({"host": "x.com"})
        assert result == ("1.1.1.1", "US", "NYC")

    def test_ipinfo_provider_succeeds(self) -> None:
        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            if "ip-api.com/json/" in url:
                return {}  # failed
            if "ipinfo.io/json" in url:
                return {"ip": "2.2.2.2", "country": "JP", "city": "Tokyo"}
            return {}

        service = self._make_service(fetcher)
        result = service._lookup_geo_via_proxy({"host": "x.com"})
        assert result == ("2.2.2.2", "JP", "Tokyo")

    def test_ipwhois_provider_succeeds(self) -> None:
        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            if "ipwho.is/" in url:
                return {"ip": "3.3.3.3", "country": "DE", "city": "Berlin"}
            return {}

        service = self._make_service(fetcher)
        result = service._lookup_geo_via_proxy({"host": "x.com"})
        assert result == ("3.3.3.3", "DE", "Berlin")

    def test_ifconfig_provider_succeeds(self) -> None:
        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            if "ifconfig.co/json" in url:
                return {"ip": "4.4.4.4", "country": "GB", "city": "London"}
            return {}

        service = self._make_service(fetcher)
        result = service._lookup_geo_via_proxy({"host": "x.com"})
        assert result == ("4.4.4.4", "GB", "London")

    def test_ipsb_provider_succeeds(self) -> None:
        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            if "api.ip.sb/geoip" in url:
                return {"ip": "5.5.5.5", "country": "KR", "city": "Seoul"}
            return {}

        service = self._make_service(fetcher)
        result = service._lookup_geo_via_proxy({"host": "x.com"})
        assert result == ("5.5.5.5", "KR", "Seoul")


# ============================================================
# _lookup_ip_purity_via_proxy
# ============================================================


class TestLookupIpPurityViaProxy:
    def _make_service(self, fetcher):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            return GeoIPService(storage=storage, proxy_json_fetcher=fetcher)

    def test_residential_votes_resolved(self) -> None:
        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            if "db=ip2location" in url:
                return {"usage_type": "RES"}
            if "db=iplark" in url:
                return {"is_residential": True}
            if "db=ippure" in url:
                return {"residential": True}
            if "ipinfo.io/" in url:
                return {"ip": "1.1.1.1", "company": {"type": "isp"}}
            return {}

        service = self._make_service(fetcher)
        score, level = service._lookup_ip_purity_via_proxy({"host": "x.com"}, "1.1.1.1")
        assert score is not None
        assert level == "家宽"

    def test_datacenter_votes(self) -> None:
        def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
            if "db=ip2location" in url:
                return {"usage_type": "DCH"}
            if "db=iplark" in url:
                return {"is_datacenter": True}
            if "db=ippure" in url:
                return {"cloud": True}
            if "ipinfo.io/" in url:
                return {"ip": "1.1.1.1", "company": {"type": "hosting"}}
            return {}

        service = self._make_service(fetcher)
        score, level = service._lookup_ip_purity_via_proxy({"host": "x.com"}, "1.1.1.1")
        assert score is not None
        assert level == "非家宽"


# ============================================================
# _fetch_json standalone
# ============================================================


class TestFetchJson:
    def test_invalid_json(self) -> None:
        from unittest.mock import MagicMock, patch

        from proxypool.geoip.service import _fetch_json

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("proxypool.geoip.service.urlopen", return_value=mock_resp):
            result = _fetch_json("http://example.com", timeout_sec=5.0)
            assert result is None

    def test_non_dict_json(self) -> None:
        from unittest.mock import MagicMock, patch

        from proxypool.geoip.service import _fetch_json

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'[1, 2, 3]'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("proxypool.geoip.service.urlopen", return_value=mock_resp):
            result = _fetch_json("http://example.com", timeout_sec=5.0)
            assert result is None

    def test_network_error(self) -> None:
        from unittest.mock import patch

        from proxypool.geoip.service import _fetch_json

        with patch("proxypool.geoip.service.urlopen", side_effect=RuntimeError("timeout")):
            result = _fetch_json("http://example.com", timeout_sec=5.0)
            assert result is None

    def test_valid_json(self) -> None:
        from unittest.mock import MagicMock, patch

        from proxypool.geoip.service import _fetch_json

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"key": "value"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("proxypool.geoip.service.urlopen", return_value=mock_resp):
            result = _fetch_json("http://example.com", timeout_sec=5.0)
            assert result == {"key": "value"}


# ============================================================
# _fetch_json via proxy (_fetch_json_via_proxy)
# ============================================================


class TestFetchJsonViaProxy:
    def test_no_fetcher_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            service = GeoIPService(storage=storage)
            with pytest.raises(RuntimeError, match="proxy fetcher not configured"):
                service._fetch_json_via_proxy({}, "http://url", 5.0)

    def test_fetcher_returns_non_dict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
                return "not a dict"  # type: ignore

            service = GeoIPService(storage=storage, proxy_json_fetcher=fetcher)
            with pytest.raises(RuntimeError, match="invalid json payload"):
                service._fetch_json_via_proxy({}, "http://url", 5.0)

    def test_fetcher_fails_then_fallback_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            node = ProxyNode(
                protocol="trojan", host="front.example.com", port=443,
                raw_link="trojan://front", extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            front_key = node.normalized_key()

            call_count = 0

            def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
                nonlocal call_count
                call_count += 1
                if front is not None:
                    return {"result": "ok"}
                raise RuntimeError("direct failed")

            service = GeoIPService(storage=storage, proxy_json_fetcher=fetcher)
            row = {
                "normalized_key": "exit-key",
                "fallback_front_keys": [front_key],
            }
            result = service._fetch_json_via_proxy(row, "http://url", 5.0)
            assert result == {"result": "ok"}
            assert call_count == 2  # direct + 1 fallback

    def test_all_fetches_fail_raises_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)

            def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
                raise RuntimeError("always fails")

            service = GeoIPService(storage=storage, proxy_json_fetcher=fetcher)
            with pytest.raises(RuntimeError, match="always fails"):
                service._fetch_json_via_proxy({}, "http://url", 5.0)

    def test_fallback_fetcher_returns_non_dict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite3"
            storage = SQLiteProxyStorage(db)
            node = ProxyNode(
                protocol="trojan", host="front2.example.com", port=443,
                raw_link="trojan://front2", extra={"password": "p"},
            )
            storage.upsert_proxy(node)
            front_key = node.normalized_key()

            def fetcher(proxy_row: dict, url: str, timeout: float, front: dict | None = None) -> dict:
                if front is not None:
                    return "not a dict"  # type: ignore
                raise RuntimeError("direct failed")

            service = GeoIPService(storage=storage, proxy_json_fetcher=fetcher)
            row = {
                "normalized_key": "exit-key",
                "fallback_front_keys": [front_key],
            }
            with pytest.raises(RuntimeError, match="invalid json payload"):
                service._fetch_json_via_proxy(row, "http://url", 5.0)


# ============================================================
# _resolve_ip standalone (socket mock)
# ============================================================


class TestResolveIp:
    def test_resolve(self) -> None:
        from unittest.mock import patch

        from proxypool.geoip.service import _resolve_ip

        with patch("proxypool.geoip.service.socket.gethostbyname", return_value="1.2.3.4"):
            assert _resolve_ip("example.com") == "1.2.3.4"


# ============================================================
# _lookup_ipapi_score standalone
# ============================================================


class TestLookupIpapiScore:
    def test_valid(self) -> None:
        from unittest.mock import MagicMock, patch

        from proxypool.geoip.service import _lookup_ipapi_score

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"company": {"abuser_score": "0.05 (Low)"}}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("proxypool.geoip.service.urlopen", return_value=mock_resp):
            score = _lookup_ipapi_score("1.1.1.1")
            assert score is not None
            assert abs(score - 5.0) < 0.1


# ============================================================
# _lookup_ipinfo_db_score standalone
# ============================================================


class TestLookupIpinfoDbScore:
    def test_ipqualityscore_valid(self) -> None:
        from unittest.mock import MagicMock, patch

        from proxypool.geoip.service import _lookup_ipinfo_db_score

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"fraud_score": 80}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("proxypool.geoip.service.urlopen", return_value=mock_resp):
            score = _lookup_ipinfo_db_score("1.1.1.1", "ipqualityscore")
            assert score == 80.0


# ============================================================
# _lookup_ip_purity standalone (mocked network)
# ============================================================


class TestLookupIpPurity:
    def test_all_requests_fail(self) -> None:
        from unittest.mock import patch

        from proxypool.geoip.service import _lookup_ip_purity

        with patch("proxypool.geoip.service._fetch_json", return_value=None):
            score, level = _lookup_ip_purity("1.1.1.1")
            assert score is None
            assert level == "未知"


# ============================================================
# _lookup_geo standalone (mocked network)
# ============================================================


class TestLookupGeo:
    def test_success(self) -> None:
        from unittest.mock import MagicMock, patch

        from proxypool.geoip.service import _lookup_geo

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "success", "country": "US", "city": "NYC"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("proxypool.geoip.service.urlopen", return_value=mock_resp):
            country, city = _lookup_geo("1.1.1.1")
            assert country == "US"
            assert city == "NYC"

    def test_fail_status(self) -> None:
        from unittest.mock import MagicMock, patch

        from proxypool.geoip.service import _lookup_geo

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "fail"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("proxypool.geoip.service.urlopen", return_value=mock_resp):
            country, city = _lookup_geo("1.1.1.1")
            assert country == ""
            assert city == ""
