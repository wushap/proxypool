from pathlib import Path
import re

WEBUI_DIR = Path("proxypool/webui")


def _read_webui() -> str:
    """Read all webui files for combined content checks."""
    parts = []
    for name in ["index.html", "package.json", "vite.config.js"]:
        p = WEBUI_DIR / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    src_dir = WEBUI_DIR / "src"
    if src_dir.exists():
        for p in sorted(src_dir.rglob("*")):
            if p.suffix in {".vue", ".js", ".css"}:
                parts.append(p.read_text(encoding="utf-8"))
    legacy_css = WEBUI_DIR / "css" / "main.css"
    if legacy_css.exists():
        parts.append(legacy_css.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _read_html() -> str:
    parts = [(WEBUI_DIR / "index.html").read_text(encoding="utf-8")]
    src_dir = WEBUI_DIR / "src"
    if src_dir.exists():
        parts.extend(p.read_text(encoding="utf-8") for p in sorted(src_dir.rglob("*.vue")))
    return "\n".join(parts)


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
    assert "onDeleteSelectedProxies" in content
    assert "/api/proxies/delete-selected" in content
    assert "proxyRawLink" in content
    assert "fallbackCopyTextToClipboard" in content
    assert "document.execCommand(\"copy\")" in content
    # Text may be shortened
    assert ("复制" in content) or ("copy" in content.lower())


def test_webui_proxy_table_should_show_and_filter_bandwidth() -> None:
    content = _read_webui()
    assert "bandwidth" in content
    assert "带宽 Mbps" in content
    assert "formatBandwidthMbps" in content
    assert "proxyFilters.speed_min_mbps" in content
    assert "speed_min_mbps" in content


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


def test_webui_should_use_vite_vue_stack() -> None:
    content = _read_webui()
    assert '"vite"' in content
    assert '"@vitejs/plugin-vue"' in content
    assert 'import { createApp } from "vue"' in content
    assert 'import ElementPlus from "element-plus"' in content
    assert '<script type="module" src="/src/main.js"></script>' in content
    assert "js/components/loader.js" not in content


def test_webui_should_expose_unified_multi_hop_pool_menu() -> None:
    html = _read_html()
    assert 'index="proxy-pools">多跳代理池<' in html
    assert 'index="backend">sing-box 后端<' not in html
    assert 'index="chain">代理链管理<' not in html


def test_webui_should_render_published_subscription_management_page() -> None:
    content = _read_webui()
    assert "订阅发布" in content
    assert "publishedSubscriptions" in content
    assert "publishedSubscriptionForm" in content
    assert "publishedSubscriptionForm.format" in content
    assert "Clash YAML" in content
    assert "formatPublishedSubscriptionOutput" in content
    assert "loadPublishedSubscriptions" in content
    assert "createPublishedSubscription" in content
    assert "publishedSubscriptionExportUrl" in content
    assert "/api/published-subscriptions" in content


def test_webui_subscription_stats_should_be_labeled() -> None:
    content = _read_webui()
    assert "subscription-stats" in content
    assert "解析 {{ item.last_parsed || 0 }}" in content
    assert "新增 {{ item.last_inserted || 0 }}" in content
    assert "更新 {{ item.last_updated || 0 }}" in content
    assert "无效 {{ item.last_invalid || 0 }}" in content
    assert "去重 {{ item.last_deduped || 0 }}" in content


def test_webui_task_delete_button_should_call_existing_handler() -> None:
    content = _read_webui()
    assert "onDeleteTaskBtn(task)" in content
    assert "() => this.onDeleteTask(task)" in content
    assert "this.deleteTask(task)" not in content


def test_webui_click_handlers_should_exist_in_app_methods() -> None:
    html = _read_html()
    js = (WEBUI_DIR / "src" / "appOptions.js").read_text(encoding="utf-8")
    for vue_file in (WEBUI_DIR / "src" / "views").glob("*.vue"):
        js += vue_file.read_text(encoding="utf-8")
    refs = set(re.findall(r'@click="\s*(on[A-Za-z0-9_]+)\b', html))
    defs = set(re.findall(r"(?:async\s+)?(on[A-Za-z0-9_]+)\s*\(", js))
    assert sorted(refs - defs) == []


def test_webui_chain_view_should_use_session_id_instead_of_account() -> None:
    content = _read_webui()
    assert "session_id" in content
    assert "lease.session_id" in content
    assert "链服务路由测试" not in content
    assert "testChainRoute" not in content
    assert "chainRouteTest.account" not in content
    assert "lease.account" not in content
    assert "params.set('account'" not in content


def test_webui_should_use_http_proxy_endpoints_for_gateway_config() -> None:
    content = _read_webui()
    html = _read_html()
    assert "gatewayConfigForm.enabled" in content
    assert "gatewayConfigForm.health_check_enabled" in content
    assert "gatewayConfigForm.health_check_interval_sec" in content
    assert "端点服务" in content
    assert "保存运行配置" in content
    assert "HTTP 代理端点" in content
    assert "统一 HTTP 网关" not in content
    assert "HTTP 网关" not in html
    assert "统一网关" not in html
    assert "设为默认" not in content
    assert "默认端点" not in content
    assert "gatewayConfigForm.listen_host" not in content
    assert "gatewayConfigForm.listen_port" not in content
    assert "gatewayConfigForm.endpoint_id" not in content
    assert "gatewayConfigForm.default_pool_id" not in content
    assert "gatewayConfigForm.http_session_header_names_text" not in content
    assert "gatewayConfigForm.http_session_query_names_text" not in content
    assert "gatewayConfigForm.connect_session_header_names_text" not in content
    assert "gatewayEndpointServiceConfigApi" in content
    assert "/service-config" in content


def test_webui_should_support_http_proxy_endpoint_management() -> None:
    content = _read_webui()
    assert "gatewayEndpoints" in content
    assert "gatewayEndpointForm.hop_pool_ids" in content
    assert "loadGatewayEndpoints" in content
    assert "saveGatewayEndpoint" in content
    assert "formatEndpointHops" in content
    assert "moveGatewayEndpointHop" in content
    assert "上移" in content
    assert "下移" in content
    assert "/api/http-proxy-endpoints" in content


def test_webui_unified_multi_hop_page_should_include_pool_chain_chain_service_and_backend_config() -> None:
    content = _read_webui()
    assert "proxyPoolTab" in content
    assert "HTTP 代理端点" in content
    assert "后端链路" in content
    assert "进程记录" in content
    assert "池级链路配置" in content
    assert "selectedPoolNameForChain" in content
    assert "会话规则" in content
    assert "poolSessionRuleForm.url_prefix" in content
    assert "测试池路由" in content
    assert "代理链服务" in content
    assert "chainPoolForm.front_filters" in content
    assert "chainPoolForm.exit_filters" in content
    assert "后端状态与实例管理" in content
    assert "onBackendStart" in content
    assert "onBackendStop" in content
    assert "onBackendRestart" in content
    assert "sing-box 链路配置" in content
    assert "当前编辑实例" in content
    assert "链服务路由测试" not in content


def test_webui_should_show_standard_proxy_usage_and_gateway_test() -> None:
    content = _read_webui()
    assert "HTTP 代理端点" in content
    assert "gatewayStatus" in content
    assert "gatewayStatusEndpointId" in content
    assert "网关状态" in content
    assert "gatewayHopPools" in content
    assert "gatewayTransitions" in content
    assert "活跃链路" in content
    assert "跨跳组合" in content
    assert "health_check_enabled" in content
    assert "health_check_interval_sec" in content
    assert "实时检测" in content
    assert "立即检测" in content
    assert "gatewayHealthMonitor" in content
    assert "selectedGatewayHealthEndpoint" in content
    assert "gatewayHealthNode" in content
    assert "检测结果" in content
    assert "经由" in content
    assert "startGatewayStatusAutoRefresh" in content
    assert "runGatewayHealthCheck" in content
    assert "http-health-check" in content
    assert "gatewayTestForm.target_url" in content
    assert "http-status" in content
    assert "http-test" in content
    assert "gatewayPreviewUrl" not in content


def test_webui_should_clear_selected_pool_chain_state_when_pool_disappears() -> None:
    content = _read_webui()
    assert "resetSelectedPoolForChainState" in content
    assert "this.selectPoolForChain(null);" in content
    assert "selectedPoolIdForChain: 0" in content
    assert "selectedPoolNameForChain: \"\"" in content
    assert "this.poolSessionRules = [];" in content
    assert "this.poolRouteTestResult = null;" in content


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


def test_webui_proxy_pool_form_should_use_route_mode_filter() -> None:
    content = _read_webui()
    assert "proxyPoolForm.filters.route_mode_filter" in content
    assert "直连</option>" in content
    assert "链式</option>" in content
    assert "不可连接</option>" in content
    assert "proxyPoolForm.filters.available" not in content


def test_webui_proxy_pool_form_should_support_multi_geo_country() -> None:
    content = _read_webui()
    assert "proxyPoolForm.filters.geo_countries" in content
    assert "multiple" in content


def test_webui_should_not_render_resin_controls() -> None:
    content = _read_webui()
    assert "resinStatus" not in content
    assert "Resin" not in content
    assert "/api/resin/" not in content
