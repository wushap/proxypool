from pathlib import Path
import re


def test_el_option_must_not_be_self_closing_in_dom_template() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    matches = re.findall(r"<el-option\b[^>]*\/>", html, flags=re.IGNORECASE)
    assert matches == [], (
        "Found self-closing <el-option /> in DOM template. "
        "Use explicit closing tags: <el-option ...></el-option>."
    )


def test_proxy_table_config_should_use_dialog_instead_of_popover() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert 'v-model="proxyConfigDialogVisible"' in html
    assert "<el-popover" not in html


def test_proxy_filters_should_include_geo_country_and_counted_options() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "geo_country" in html
    assert "geoCountryOptions" in html
    assert "geoLocationFilterOptions" in html
    assert "statusFilterOptions" in html
    assert "protocolFilterOptions" in html
    assert "openaiFilterOptions" in html
    assert "ipPurityFilterOptions" in html
    assert "fallbackFrontFilterOptions" in html
    assert "sourceFilterOptions" in html
    assert "(${count})" in html


def test_webui_should_support_backend_default_port_range_config() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "默认入站端口范围" in html
    assert "/api/backend/default-port-range" in html


def test_webui_should_support_route_fill_by_openai_status() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "按ChatGPT解锁批量填充链路列" in html
    assert "routeGeoFill.mode" in html
    assert "routeGeoFill.openai_status" in html
    assert "getProxyRefsByOpenaiStatus" in html


def test_webui_should_skip_blank_route_defaults_when_applying() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "applyRouteDefaultValue" in html
    assert "defaultValue) return currentValue;" in html


def test_webui_should_render_single_proxy_test_action() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert 'label: "操作"' in html
    assert "onTestSingleProxy" in html
    assert "/api/tester/run-one" in html
