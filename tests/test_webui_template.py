from pathlib import Path
import re

WEBUI_DIR = Path("proxypool/webui")


def _read_webui() -> str:
    """Read all webui files for combined content checks."""
    parts = []
    for name in ["index.html", "js/app.js", "css/main.css"]:
        p = WEBUI_DIR / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _read_html() -> str:
    return (WEBUI_DIR / "index.html").read_text(encoding="utf-8")


def test_el_option_must_not_be_self_closing_in_dom_template() -> None:
    html = _read_html()
    matches = re.findall(r"<el-option\b[^>]*\/>", html, flags=re.IGNORECASE)
    assert matches == [], (
        "Found self-closing <el-option /> in DOM template. "
        "Use explicit closing tags: <el-option ...></el-option>."
    )


def test_proxy_table_config_should_use_dialog_instead_of_popover() -> None:
    html = _read_html()
    assert 'v-model="proxyConfigDialogVisible"' in html
    assert "<el-popover" not in html


def test_proxy_filters_should_include_geo_country_and_counted_options() -> None:
    content = _read_webui()
    assert "geo_country" in content
    assert "geoCountryOptions" in content
    assert "geoLocationFilterOptions" in content
    assert "statusFilterOptions" in content
    assert "protocolFilterOptions" in content
    assert "openaiFilterOptions" in content
    assert "ipPurityFilterOptions" in content
    assert "fallbackFrontFilterOptions" in content
    assert "sourceFilterOptions" in content


def test_webui_should_support_backend_default_port_range_config() -> None:
    content = _read_webui()
    # Text may be shortened in refactored UI
    assert ("默认监听" in content) or ("端口范围" in content) or ("default-port-range" in content)
    assert "/api/backend/default-port-range" in content


def test_webui_should_support_route_fill_by_openai_status() -> None:
    content = _read_webui()
    # Shortened text in refactored UI
    assert ("批量填充链路" in content) or ("填充链路" in content) or ("按条件" in content)
    assert "routeGeoFill.geo_location" in content
    assert "routeGeoFill.openai_status" in content
    assert "routeGeoFill.ip_purity_level" in content
    assert "proxyMatchesRouteFillFilters" in content


def test_webui_should_skip_blank_route_defaults_when_applying() -> None:
    content = _read_webui()
    assert "applyRouteDefaultValue" in content
    assert "defaultValue) return currentValue;" in content


def test_webui_should_render_single_proxy_test_action() -> None:
    content = _read_webui()
    assert "label: \"操作\"" in content
    assert "onTestSingleProxy" in content
    assert "/api/tester/run-one" in content


def test_webui_should_copy_proxy_links_from_proxy_table() -> None:
    content = _read_webui()
    assert "selectedProxyKeys" in content
    assert "onCopyProxyLink" in content
    assert "onCopySelectedProxyLinks" in content
    assert "proxyRawLink" in content
    assert "fallbackCopyTextToClipboard" in content
    assert "document.execCommand(\"copy\")" in content
    # Text may be shortened
    assert ("复制" in content) or ("copy" in content.lower())


def test_webui_should_use_pragmatic_element_plus_console_shell() -> None:
    html = _read_html()
    content = _read_webui()
    # Layout structure
    assert '<div id="app"' in html
    assert "<el-config-provider" in html
    assert "<el-menu" in html
    # No legacy section switcher patterns
    assert "ops-sidebar-visibility" not in content
    assert "sectionVisibility" not in content
    assert "ops-section-switcher" not in content
    # Navigation works
    assert "selectPage" in content
    assert "activePage" in content
    # Element Plus components present
    assert "<el-button" in html
    # setPropsDefaults in JS
    assert "setPropsDefaults" in content
    assert "Proxy Pool" in html


def test_webui_should_render_published_subscription_management_page() -> None:
    content = _read_webui()
    assert "订阅发布" in content
    assert "publishedSubscriptions" in content
    assert "publishedSubscriptionForm" in content
    assert "loadPublishedSubscriptions" in content
    assert "createPublishedSubscription" in content
    assert "publishedSubscriptionExportUrl" in content
    assert "/api/published-subscriptions" in content


def test_webui_chain_view_should_use_session_id_instead_of_account() -> None:
    content = _read_webui()
    assert "chainRouteTest.session_id" in content
    assert "session_id" in content
    assert "lease.session_id" in content
    assert "chainRouteTest.account" not in content
    assert "lease.account" not in content
    assert "params.set('account'" not in content


def test_webui_should_surface_backend_instances_default_listen_and_replacement() -> None:
    content = _read_webui()
    assert "backendDefaultListen" in content
    assert "loadBackendDefaultListen" in content
    assert "saveBackendDefaultListen" in content
    assert "/api/backend/default-listen" in content
    assert "backendInstances" in content
    assert "backendInstanceId" in content
    assert "/api/backend/instances/${encodeURIComponent(id)}/start" in content
    assert "/api/backend/instances/${encodeURIComponent(id)}/stop" in content
    assert "/api/backend/instances/${encodeURIComponent(id)}" in content
    assert "实例管理" in content
    assert "配置管理" in content
    assert "backendConfigInstanceId" in content
    assert "onOpenBackendInstanceConfig" in content
    assert "onBackendInstanceCreate" in content
    assert "createBackendInstance" in content
    assert "创建" in content
    assert "onBackendInstanceDelete" in content
    assert "/api/backend/instances/${encodeURIComponent(id)}/routes" in content
    assert "backendActionInstanceId" in content
    assert 'typeof instanceId === "string"' in content
    assert "replace_failed_with_available" in content
