// src/core/state.js
// 全局状态定义

import { reactive } from 'vue'
import {
  DEFAULT_PROXY_COLUMN_CONFIGS,
  DEFAULT_PROXY_COLUMN_ORDER,
  DEFAULT_PROXY_FILTERS
} from './constants'
import { cloneProxyColumnConfigs } from './utils'

/**
 * 创建初始状态
 * @returns {object} 响应式状态对象
 */
export function createInitialState() {
  return reactive({
    // 导航状态
    activePage: "tasks",
    proxyPoolTab: "pools",

    // 数据状态
    stats: {},
    proxies: [],
    allProxies: [],
    proxySerialMap: {},
    backendStatus: {},
    backendEvents: [],
    subscriptions: [],
    publishedSubscriptions: [],
    proxyPools: [],
    taskItems: [],

    // 网关相关
    gatewayEndpoints: [],
    gatewayStatus: null,
    gatewayConfigForm: {
      enabled: true,
      health_check_enabled: true,
      health_check_interval_sec: 30,
    },
    gatewayEndpointForm: {
      id: 0,
      name: "",
      listen_host: "127.0.0.1",
      listen_port: 18899,
      enabled: true,
      sticky_ttl_sec: 3600,
      session_missing_action: "RANDOM",
      session_header_names_text: "X-ProxyPool-Session",
      session_query_param_names_text: "session",
      connect_session_header_names_text: "X-ProxyPool-Session",
      hop_pool_ids: [],
    },
    gatewayStatusEndpointId: 0,
    gatewayTestForm: {
      target_url: "https://www.cloudflare.com/cdn-cgi/trace",
      endpoint_id: 0,
      session_id: "",
    },
    gatewayTestResult: null,

    // UI状态
    message: "",
    messageError: false,
    loading: false,

    // 筛选状态
    proxyFilters: { ...DEFAULT_PROXY_FILTERS },

    // 分页状态
    pageSizeOptions: [10, 50, 100],
    pagination: {
      subscriptions: { page: 1, perPage: 10 },
      publishedSubscriptions: { page: 1, perPage: 10 },
      proxyPools: { page: 1, perPage: 10 },
      routes: { page: 1, perPage: 10 },
      backendEvents: { page: 1, perPage: 10 },
      proxies: { page: 1, perPage: 50 },
    },

    // 按钮状态
    buttonState: {},

    // 代理列配置
    proxyColumnConfigs: cloneProxyColumnConfigs(DEFAULT_PROXY_COLUMN_CONFIGS),
    proxyColumnOrder: [...DEFAULT_PROXY_COLUMN_ORDER],

    // 路由相关
    routesJson: "[]",
    routeEntries: [],
    routeDefaults: { front_proxy_key: "", middle_proxy_key: "", exit_proxy_key: "" },
    routeGeoFill: {
      mode: "geo",
      geo_location: "",
      openai_status: "",
      ip_purity_level: "residential",
      target_column: "exit_proxy_key",
    },
    routeLatencyMap: {},

    // 后端配置
    backendPortRange: { start: 1081, end: 1180 },
    backendDefaultListen: "127.0.0.1",
    backendInstanceId: "default",
    backendConfigInstanceId: "default",

    // 测试配置
    testFallback: { front_proxy_refs: "", max_attempts: 3 },
    testRunFilter: { status: "all", min_retest_days: 0, replace_failed_with_available: false },
    taskConcurrency: { tester: 60, openai: 30, geoip: 30, ip_purity: 30 },

    // 订阅表单
    subscriptionForm: { name: "", url: "" },
    bulkImportUrls: "",
    subscriptionUpdateProxyRef: "",

    // 发布订阅表单
    publishedSubscriptionForm: {
      name: "",
      format: "raw",
      filters: {
        available: "true", geo_country: "", geo_location: "",
        openai_filter: "", ip_purity_filter: "", fallback_front_filter: "", source: "",
      },
    },

    // 代理池表单
    proxyPoolForm: {
      name: "", listen: "0.0.0.0", inbound_type: "http",
      filters: {
        route_mode_filter: "direct", geo_countries: [], geo_country: "", geo_location: "",
        openai_filter: "", ip_purity_filter: "",
        source: "", protocol: "", latency_min: "", latency_max: "", freshness_hours: "",
      },
    },

    // 池级链路配置
    selectedPoolIdForChain: 0,
    selectedPoolNameForChain: "",
    poolChainForm: {
      chain_enabled: false,
      sticky_ttl_sec: 3600,
      session_missing_action: "RANDOM",
      session_header_names_text: "X-ProxyPool-Session",
      session_query_param_names_text: "session",
    },
    poolSessionRuleForm: {
      url_prefix: "",
      headers_text: "",
    },
    poolSessionRules: [],
    poolRouteTest: {
      session_id: "",
      target_domain: "",
    },
    poolRouteTestResult: null,

    // 链服务相关
    chainStatus: {},
    chainHealth: {},
    chainLeases: [],
    chainNodeTab: 'front',
    chainPoolForm: {
      front_filters: '',
      exit_filters: '',
    },

    // 任务相关
    taskPollingTimer: null,
    taskListLoading: false,
    pendingTaskResultRefresh: false,

    // 速度测试表单
    speedTestForm: {
      url: "https://speed.cloudflare.com/__down?bytes=10000000",
      limit: 0,
      timeout_sec: 30,
      only_direct: true,
    },

    // 自动任务配置
    autoTaskConfig: {
      enabled: false,
      subscription_refresh_enabled: true,
      subscription_refresh_minutes: 60,
      tester_enabled: false,
      tester_minutes: 60,
      tester_limit: 0,
      tester_concurrency: 50,
      speed_test_enabled: false,
      speed_test_minutes: 120,
      speed_test_url: "https://speed.cloudflare.com/__down?bytes=10000000",
      speed_test_limit: 0,
      speed_test_timeout_sec: 30,
    },
    autoTaskStatus: null,

    // 代理配置对话框
    proxyConfigDialogVisible: false,
    selectedProxyKeys: [],

    // 暗色模式
    darkMode: false,
  })
}
