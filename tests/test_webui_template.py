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
    assert "按地区/按ChatGPT解锁/按家宽批量填充链路列" in html
    assert "组合条件" in html
    assert "routeGeoFill.geo_location" in html
    assert "routeGeoFill.openai_status" in html
    assert "routeGeoFill.ip_purity_level" in html
    assert "proxyMatchesRouteFillFilters" in html
    assert "getRouteFillFilterLabels" in html
    assert "getProxyRefsByFillRule" in html
    assert "IP纯净度家宽" in html


def test_webui_should_skip_blank_route_defaults_when_applying() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "applyRouteDefaultValue" in html
    assert "defaultValue) return currentValue;" in html


def test_webui_should_render_single_proxy_test_action() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert 'label: "操作"' in html
    assert "onTestSingleProxy" in html
    assert "/api/tester/run-one" in html


def test_webui_should_copy_proxy_links_from_proxy_table() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "selectedProxyKeys" in html
    assert "onCopyProxyLink" in html
    assert "onCopySelectedProxyLinks" in html
    assert "proxyRawLink" in html
    assert "fallbackCopyTextToClipboard" in html
    assert "document.execCommand(\"copy\")" in html
    assert "批量复制链接" in html
    assert "复制链接" in html


def test_webui_should_use_pragmatic_element_plus_console_shell() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert 'class="ops-shell"' in html
    assert "<el-config-provider" in html
    assert "<el-aside" in html
    assert "<el-menu" in html
    assert "ops-sidebar-visibility" not in html
    assert "sectionVisibility" not in html
    assert "ops-section-switcher" not in html
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in html
    assert 'activePage = key' in html
    assert 'class="ops-command-bar"' in html
    assert "<el-button" in html
    assert "<el-tag" in html
    assert "setPropsDefaults" in html
    assert "Proxy Pool 控制台" in html


def test_webui_should_render_published_subscription_management_page() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "订阅发布管理" in html
    assert "publishedSubscriptions" in html
    assert "publishedSubscriptionForm" in html
    assert "loadPublishedSubscriptions" in html
    assert "createPublishedSubscription" in html
    assert "deletePublishedSubscription" in html
    assert "publishedSubscriptionExportUrl" in html
    assert "/api/published-subscriptions" in html


def test_webui_should_surface_backend_instances_default_listen_and_replacement() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "backendDefaultListen" in html
    assert "loadBackendDefaultListen" in html
    assert "saveBackendDefaultListen" in html
    assert "/api/backend/default-listen" in html
    assert "backendInstances" in html
    assert "backendInstanceId" in html
    assert "/api/backend/instances/${encodeURIComponent(id)}/start" in html
    assert "/api/backend/instances/${encodeURIComponent(id)}/stop" in html
    assert "/api/backend/instances/${encodeURIComponent(id)}" in html
    assert "实例管理" in html
    assert "配置管理" in html
    assert "打开配置" in html
    assert "删除实例" in html
    assert "backendConfigInstanceId" in html
    assert "onOpenBackendInstanceConfig" in html
    assert "onBackendInstanceCreate" in html
    assert "createBackendInstance" in html
    assert "创建实例" in html
    assert "保存实例配置" in html
    assert "onBackendInstanceDelete" in html
    assert "/api/backend/instances/${encodeURIComponent(id)}/routes" in html
    assert "backendActionInstanceId" in html
    assert 'typeof instanceId === "string"' in html
    assert "节点可达性检测失败时自动替换 sing-box 落地节点" in html
    assert "replace_failed_with_available" in html
    backend_section = html.split('<section v-show="activePage === \'backend\'"', 1)[1].split('<section v-show=', 1)[0]
    assert "onLoadBackendStatus" not in backend_section
    assert "onBackendStart" not in backend_section
    assert "onBackendStop" not in backend_section
    assert "onBackendRestart" not in backend_section
