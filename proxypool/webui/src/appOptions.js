/**
 * Proxy Pool Console - Vue root options.
 */
// --- Defaults ---
export const DEFAULT_PROXY_COLUMN_CONFIGS = {
  serial:         { label: "序号",       visible: true },
  protocol:       { label: "协议",       visible: true },
  address:        { label: "地址",       visible: true },
  latency:        { label: "延迟",       visible: true },
  bandwidth:      { label: "带宽 Mbps",  visible: true },
  status:         { label: "状态",       visible: true },
  checked_at:     { label: "最后检测",   visible: true },
  geo:            { label: "IP位置",     visible: true },
  purity:         { label: "IP纯净度",   visible: true },
  unlock:         { label: "ChatGPT解锁", visible: true },
  fallback_front: { label: "可连通前置", visible: true },
  source:         { label: "来源",       visible: true },
  action:         { label: "操作",       visible: true },
};

export const DEFAULT_PROXY_COLUMN_ORDER = [
  "serial", "protocol", "address", "latency", "bandwidth", "status", "checked_at",
  "geo", "purity", "unlock", "fallback_front", "source", "action",
];

export const DEFAULT_PROXY_FILTERS = {
  protocol: "", available: "", geo: "", geo_country: "", geo_location: "",
  openai: "", ip_purity: "", fallback_front: "", source: "", speed_min_mbps: "",
};

export function cloneProxyColumnConfigs() {
  const out = {};
  for (const [key, val] of Object.entries(DEFAULT_PROXY_COLUMN_CONFIGS)) {
    out[key] = { label: String(val.label || ""), visible: val.visible !== false };
  }
  return out;
}

// --- Root Options ---
export const appOptions = {
  data() {
    return {
      activePage: "tasks",
      proxyPoolTab: "pools",
      stats: {},
      proxies: [],
      allProxies: [],
      proxySerialMap: {},
      message: "",
      messageError: false,
      proxyFilters: { ...DEFAULT_PROXY_FILTERS },
      loading: false,
      backendStatus: {},
      backendEvents: [],
      buttonState: {},
      pageSizeOptions: [10, 50, 100],
      pagination: {
        subscriptions: { page: 1, perPage: 10 },
        publishedSubscriptions: { page: 1, perPage: 10 },
        proxyPools: { page: 1, perPage: 10 },
        routes: { page: 1, perPage: 10 },
        backendEvents: { page: 1, perPage: 10 },
        proxies: { page: 1, perPage: 50 },
      },
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
      backendPortRange: { start: 1081, end: 1180 },
      backendDefaultListen: "127.0.0.1",
      backendInstanceId: "default",
      backendConfigInstanceId: "default",
      testFallback: { front_proxy_refs: "", max_attempts: 3 },
      testRunFilter: { status: "all", min_retest_days: 0, replace_failed_with_available: false },
      taskConcurrency: { tester: 60, openai: 30, geoip: 30, ip_purity: 30 },
      proxyColumnConfigs: cloneProxyColumnConfigs(),
      proxyColumnOrder: [...DEFAULT_PROXY_COLUMN_ORDER],
      proxyColumnDragIndex: -1,
      subscriptions: [],
      subscriptionForm: { name: "", url: "" },
      publishedSubscriptions: [],
      publishedSubscriptionForm: {
        name: "",
        format: "raw",
        filters: {
          available: "true", geo_country: "", geo_location: "",
          openai_filter: "", ip_purity_filter: "", fallback_front_filter: "", source: "",
        },
      },
      subscriptionUpdateProxyRef: "",
      proxyPools: [],
      proxyPoolForm: {
        name: "", listen: "0.0.0.0", inbound_type: "http",
        filters: {
          route_mode_filter: "direct", geo_countries: [], geo_country: "", geo_location: "",
          openai_filter: "", ip_purity_filter: "",
          source: "", protocol: "", latency_min: "", latency_max: "", freshness_hours: "",
        },
      },
      gatewayConfigForm: {
        enabled: false,
        listen_host: "127.0.0.1",
        listen_port: 8899,
        endpoint_id: 0,
        default_pool_id: 0,
        sticky_ttl_sec: 3600,
        session_missing_action: "RANDOM",
        http_session_header_names_text: "X-ProxyPool-Session",
        http_session_query_names_text: "session",
        connect_session_header_names_text: "X-ProxyPool-Session",
      },
      gatewayEndpoints: [],
      gatewayStatusEndpointId: 0,
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
      gatewayStatus: null,
      gatewayTestForm: {
        target_url: "https://www.cloudflare.com/cdn-cgi/trace",
        endpoint_id: 0,
        session_id: "",
      },
      gatewayTestResult: null,
      selectedPoolIdForChain: 0,
      selectedPoolNameForChain: "",
      poolChainForm: {
        chain_enabled: false,
        sticky_ttl_sec: 3600,
        session_missing_action: "RANDOM",
        session_header_names_text: "X-ProxyPool-Session",
        session_query_param_names_text: "session",
        gateway_path_prefix: "",
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
      chainStatus: {},
      chainHealth: {},
      chainLeases: [],
      chainNodeTab: 'front',
      chainPoolForm: {
        front_filters: '',
        exit_filters: '',
      },
      taskItems: [],
      taskPollingTimer: null,
      taskListLoading: false,
      pendingTaskResultRefresh: false,
      speedTestForm: {
        url: "https://speed.cloudflare.com/__down?bytes=10000000",
        limit: 0,
        timeout_sec: 30,
        only_direct: true,
      },
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
      proxyConfigDialogVisible: false,
      selectedProxyKeys: [],
    };
  },

  computed: {
    allProxyCount() { return Array.isArray(this.allProxies) ? this.allProxies.length : 0; },
    protocolFilterOptions() {
      const map = new Map();
      (this.allProxies || []).forEach(item => {
        const key = String(item?.protocol || "").trim();
        if (key) map.set(key, (map.get(key) || 0) + 1);
      });
      return Array.from(map.entries())
        .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0], "zh-CN"))
        .map(([value, count]) => ({ value, count, label: `${value} (${count})` }));
    },
    statusFilterOptions() {
      let up = 0, down = 0;
      (this.allProxies || []).forEach(item => { if (item?.available) up++; else down++; });
      return [
        { value: "true", count: up, label: `状态: 可用 (${up})` },
        { value: "false", count: down, label: `状态: 不可用 (${down})` },
      ];
    },
    geoFilterOptions() {
      let has = 0, none = 0;
      (this.allProxies || []).forEach(item => {
        if (String(item?.country || "").trim() || String(item?.city || "").trim()) has++; else none++;
      });
      return [
        { value: "has", count: has, label: `IP位置: 已补全 (${has})` },
        { value: "none", count: none, label: `IP位置: 未补全 (${none})` },
      ];
    },
    geoCountryOptions() {
      const map = new Map();
      (this.allProxies || []).forEach(item => {
        const country = String(item?.country || "").trim() || "-";
        map.set(country, (map.get(country) || 0) + 1);
      });
      return Array.from(map.entries())
        .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0], "zh-CN"))
        .map(([value, count]) => ({ value, count, label: `${value === "-" ? "未知国家" : value} (${count})` }));
    },
    geoLocationOptions() {
      const uniq = new Set();
      (this.allProxies || []).forEach(item => {
        const c = String(item.country || "").trim();
        const city = String(item.city || "").trim();
        if (c || city) uniq.add(`${c || "-"}:${city || "-"}`);
      });
      return Array.from(uniq).sort((a, b) => a.localeCompare(b, "zh-CN"));
    },
    geoLocationFilterOptions() {
      const selCountry = String(this.proxyFilters?.geo_country || "").trim();
      const map = new Map();
      (this.allProxies || []).forEach(item => {
        const c = String(item?.country || "").trim();
        const city = String(item?.city || "").trim();
        const cKey = c || "-";
        if (selCountry && selCountry !== cKey) return;
        if (!c && !city) return;
        const loc = `${c || "-"}:${city || "-"}`;
        map.set(loc, (map.get(loc) || 0) + 1);
      });
      return Array.from(map.entries())
        .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0], "zh-CN"))
        .map(([value, count]) => ({ value, count, label: `${value} (${count})` }));
    },
    openaiFilterOptions() {
      let unlocked = 0, blocked = 0, unchecked = 0;
      (this.allProxies || []).forEach(item => {
        if (item?.openai_unlocked === true) unlocked++;
        else if (item?.openai_unlocked === false) blocked++;
        else unchecked++;
      });
      return [
        { value: "unlocked", count: unlocked, label: `ChatGPT: 已解锁 (${unlocked})` },
        { value: "blocked", count: blocked, label: `ChatGPT: 未解锁 (${blocked})` },
        { value: "unchecked", count: unchecked, label: `ChatGPT: 未检测 (${unchecked})` },
      ];
    },
    ipPurityFilterOptions() {
      let checked = 0, unchecked = 0, residential = 0, nonResidential = 0, unknown = 0;
      (this.allProxies || []).forEach(item => {
        if (item?.ip_purity_checked_at) checked++; else unchecked++;
        const level = String(item?.ip_purity_level || "").trim();
        if (level === "家宽") residential++;
        else if (level === "非家宽") nonResidential++;
        else if (level === "未知") unknown++;
      });
      return [
        { value: "checked", count: checked, label: `IP纯净度: 已检测 (${checked})` },
        { value: "unchecked", count: unchecked, label: `IP纯净度: 未检测 (${unchecked})` },
        { value: "residential", count: residential, label: `IP纯净度: 家宽 (${residential})` },
        { value: "non_residential", count: nonResidential, label: `IP纯净度: 非家宽 (${nonResidential})` },
        { value: "unknown", count: unknown, label: `IP纯净度: 未知 (${unknown})` },
      ];
    },
    fallbackFrontFilterOptions() {
      let has = 0, none = 0;
      (this.allProxies || []).forEach(item => {
        const arr = Array.isArray(item?.fallback_front_keys) ? item.fallback_front_keys : [];
        if (arr.length > 0) has++; else none++;
      });
      return [
        { value: "has", count: has, label: `可连通前置: 有标记 (${has})` },
        { value: "none", count: none, label: `可连通前置: 无标记 (${none})` },
      ];
    },
    sourceFilterOptions() {
      const map = new Map();
      (this.allProxies || []).forEach(item => {
        const key = String(item?.source || "").trim() || "-";
        map.set(key, (map.get(key) || 0) + 1);
      });
      return Array.from(map.entries())
        .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0], "zh-CN"))
        .map(([value, count]) => ({ value, count, label: `${value === "-" ? "未知来源" : value} (${count})` }));
    },
    statCards() {
      return [
        { title: "Total", value: this.stats.total ?? 0, desc: "总节点" },
        { title: "Available", value: this.stats.available ?? 0, desc: "可用节点" },
        { title: "Rate", value: (this.stats.availability_rate ?? 0) + "%", desc: "可用率" },
        { title: "Avg RTT", value: this.stats.avg_latency_ms ? this.stats.avg_latency_ms + " ms" : "-", desc: "平均延迟" },
      ];
    },
    proxyColumnsOrdered() {
      return (this.proxyColumnOrder || [])
        .filter(key => this.proxyColumnConfigs[key])
        .map(key => ({
          key,
          label: String(this.proxyColumnConfigs[key].label || DEFAULT_PROXY_COLUMN_CONFIGS[key]?.label || key),
        }));
    },
    proxyColumnConfigRows() { return this.proxyColumnsOrdered.map((item, idx) => ({ ...item, idx })); },
    visibleProxyColumns() { return this.proxyColumnsOrdered.filter(item => this.proxyColumnConfigs[item.key]?.visible !== false); },
    paginatedSubscriptions() { return this.paginateItems(this.subscriptions || [], "subscriptions"); },
    paginatedPublishedSubscriptions() { return this.paginateItems(this.publishedSubscriptions || [], "publishedSubscriptions"); },
    paginatedProxyPools() { return this.paginateItems(this.proxyPools || [], "proxyPools"); },
    paginatedRouteEntries() {
      const list = this.routeEntries || [];
      const sliced = this.paginateItems(list, "routes");
      const start = this.getPageStartIndex("routes");
      return sliced.map((item, idx) => ({ item, idx: start + idx }));
    },
    paginatedBackendEvents() { return this.paginateItems(this.backendEvents || [], "backendEvents"); },
    backendInstances() { return Array.isArray(this.backendStatus?.instances) ? this.backendStatus.instances : []; },
    paginatedProxies() { return this.paginateItems(this.proxies || [], "proxies"); },
    selectedGatewayStatusEndpoint() {
      const id = Number(this.gatewayStatusEndpointId || this.gatewayStatus?.summary?.endpoint_id || this.gatewayConfigForm.endpoint_id || 0);
      return (this.gatewayEndpoints || []).find(item => Number(item.id) === id) || this.gatewayStatus?.endpoint || null;
    },
    gatewayHopPools() { return Array.isArray(this.gatewayStatus?.hop_pools) ? this.gatewayStatus.hop_pools : []; },
    gatewayTransitions() { return Array.isArray(this.gatewayStatus?.transitions) ? this.gatewayStatus.transitions : []; },
  },

  methods: {
    // --- Navigation ---
    selectPage(key) {
      this.activePage = key;
      if (key === "proxy-pools") {
        this.loadProxyPools();
        this.loadGatewayEndpoints();
        this.loadGatewayConfig();
        this.loadGatewayStatus();
        this.loadBackendPortRange();
        this.loadBackendDefaultListen();
        this.loadBackendStatus();
        this.loadChainStatus();
        this.loadChainHealth();
      }
      else if (key === "published-subscriptions") { this.loadPublishedSubscriptions(); }
    },

    // --- Button State Management ---
    isActionRunning(key) { return !!this.buttonState[String(key || "")]; },
    buttonLabel(key, idleText, runningText = "执行中...") {
      return this.isActionRunning(key) ? runningText : idleText;
    },
    async runWithButtonState(key, fn, minVisibleMs = 220) {
      const stateKey = String(key || "");
      if (!stateKey) return await fn();
      if (this.buttonState[stateKey]) return;
      this.buttonState[stateKey] = true;
      const started = Date.now();
      try { return await fn(); }
      finally {
        const left = Number(minVisibleMs || 0) - (Date.now() - started);
        if (left > 0) await new Promise(r => setTimeout(r, left));
        this.buttonState[stateKey] = false;
      }
    },

    // --- Pagination ---
    _sanitizePerPage(value) {
      const n = Number(value);
      return this.pageSizeOptions.includes(n) ? n : 10;
    },
    getPageState(section) {
      const state = this.pagination?.[section];
      if (!state) return { page: 1, perPage: 10 };
      state.page = Math.max(1, Math.trunc(Number(state.page || 1)));
      state.perPage = this._sanitizePerPage(state.perPage);
      return state;
    },
    getSectionItems(section) {
      if (section === "subscriptions") return this.subscriptions || [];
      if (section === "publishedSubscriptions") return this.publishedSubscriptions || [];
      if (section === "proxyPools") return this.proxyPools || [];
      if (section === "routes") return this.routeEntries || [];
      if (section === "backendEvents") return this.backendEvents || [];
      if (section === "proxies") return this.proxies || [];
      return [];
    },
    getTotalPages(section) {
      const total = this.getSectionItems(section).length;
      const { perPage } = this.getPageState(section);
      return Math.max(1, Math.ceil(total / Math.max(1, perPage)));
    },
    getPageStartIndex(section) {
      const { page, perPage } = this.getPageState(section);
      return (Math.max(1, page) - 1) * Math.max(1, perPage);
    },
    paginateItems(items, section) {
      const list = Array.isArray(items) ? items : [];
      const state = this.getPageState(section);
      const totalPages = Math.max(1, Math.ceil(list.length / Math.max(1, state.perPage)));
      if (state.page > totalPages) state.page = totalPages;
      const start = (state.page - 1) * state.perPage;
      return list.slice(start, start + state.perPage);
    },
    canPrevPage(section) { return this.getPageState(section).page > 1; },
    canNextPage(section) {
      const state = this.getPageState(section);
      return state.page < this.getTotalPages(section);
    },
    goPrevPage(section) {
      const state = this.getPageState(section);
      if (state.page > 1) state.page -= 1;
    },
    goNextPage(section) {
      const state = this.getPageState(section);
      if (state.page < this.getTotalPages(section)) state.page += 1;
    },
    onPaginationPageSizeChange(section) {
      const state = this.getPageState(section);
      state.perPage = this._sanitizePerPage(state.perPage);
      state.page = 1;
    },
    pageIndicator(section) {
      const state = this.getPageState(section);
      const totalPages = this.getTotalPages(section);
      const total = this.getSectionItems(section).length;
      return `${state.page}/${totalPages} (${total})`;
    },
    resetPage(section) { this.getPageState(section).page = 1; },
    clampAllPages() {
      for (const s of ["subscriptions", "publishedSubscriptions", "proxyPools", "routes", "backendEvents", "proxies"]) {
        const state = this.getPageState(s);
        const total = this.getTotalPages(s);
        if (state.page > total) state.page = total;
      }
    },

    // --- Proxy Selection ---
    pruneSelectedProxyKeys() {
      const available = new Set((this.allProxies || []).map(item => String(item.normalized_key || "")));
      this.selectedProxyKeys = (this.selectedProxyKeys || []).filter(key => available.has(String(key || "")));
    },
    areAllPaginatedProxiesSelected() {
      const keys = (this.paginatedProxies || []).map(item => String(item.normalized_key || "")).filter(Boolean);
      if (!keys.length) return false;
      const selected = new Set(this.selectedProxyKeys || []);
      return keys.every(key => selected.has(key));
    },
    toggleAllPaginatedProxies(checked) {
      const current = new Set((this.selectedProxyKeys || []).map(k => String(k || "")).filter(Boolean));
      const keys = (this.paginatedProxies || []).map(item => String(item.normalized_key || "")).filter(Boolean);
      keys.forEach(key => { checked ? current.add(key) : current.delete(key); });
      this.selectedProxyKeys = Array.from(current);
    },
    selectedProxyItems() {
      const selected = new Set((this.selectedProxyKeys || []).map(k => String(k || "")));
      return (this.allProxies || []).filter(item => selected.has(String(item.normalized_key || "")));
    },

    // --- Proxy Column Config ---
    loadProxyColumns() {
      try {
        const raw = localStorage.getItem("proxypool.proxyColumns.v1");
        if (!raw) return;
        const data = JSON.parse(raw);
        if (!data || typeof data !== "object") return;
        const cfg = data.configs || {};
        const order = Array.isArray(data.order) ? data.order : [];
        for (const key of Object.keys(this.proxyColumnConfigs)) {
          if (cfg[key] && typeof cfg[key] === "object") {
            this.proxyColumnConfigs[key].visible = cfg[key].visible !== false;
            if (typeof cfg[key].label === "string" && cfg[key].label.trim()) {
              this.proxyColumnConfigs[key].label = cfg[key].label.trim().slice(0, 32);
            }
          }
        }
        const filteredOrder = order.filter(key => this.proxyColumnConfigs[key]);
        const missing = Object.keys(this.proxyColumnConfigs).filter(key => !filteredOrder.includes(key));
        this.proxyColumnOrder = [...filteredOrder, ...missing];
      } catch {}
    },
    persistProxyColumns() {
      try {
        const configs = {};
        for (const [key, val] of Object.entries(this.proxyColumnConfigs || {})) {
          const label = String(val?.label || "").trim();
          configs[key] = {
            visible: val?.visible !== false,
            label: label || String(DEFAULT_PROXY_COLUMN_CONFIGS[key]?.label || key),
          };
        }
        localStorage.setItem("proxypool.proxyColumns.v1", JSON.stringify({
          order: this.proxyColumnOrder,
          configs,
        }));
      } catch {}
    },
    resetProxyColumns() {
      this.proxyColumnConfigs = cloneProxyColumnConfigs();
      this.proxyColumnOrder = [...DEFAULT_PROXY_COLUMN_ORDER];
      this.persistProxyColumns();
      this.setMessage("列配置已重置");
    },
    clearProxyFilters() {
      this.proxyFilters = { ...DEFAULT_PROXY_FILTERS };
      this.setMessage("筛选条件已清空");
    },
    onGeoCountryChanged() {
      const country = String(this.proxyFilters.geo_country || "").trim();
      const location = String(this.proxyFilters.geo_location || "").trim();
      if (!country || !location) return;
      if (location.split(":", 1)[0] !== country) this.proxyFilters.geo_location = "";
    },
    moveProxyColumn(key, delta) {
      const from = this.proxyColumnOrder.indexOf(String(key || ""));
      if (from < 0) return;
      const to = from + Number(delta || 0);
      if (to < 0 || to >= this.proxyColumnOrder.length) return;
      const order = [...this.proxyColumnOrder];
      const [moved] = order.splice(from, 1);
      order.splice(to, 0, moved);
      this.proxyColumnOrder = order;
      this.persistProxyColumns();
    },

    // --- Messages ---
    setMessage(text, isError = false) {
      this.message = text;
      this.messageError = isError;
    },

    // --- File Import ---
    openImportFiles() {
      const el = this.$refs.fileInput;
      if (!el) throw new Error("文件输入控件不可用");
      el.value = "";
      el.click();
    },
    async onImportFilesSelected(event) {
      const files = Array.from(event?.target?.files || []);
      if (!files.length) return;
      await this.runWithButtonState("importFiles", () => this.importFiles(files));
    },
    async importFiles(files) {
      try {
        const items = [];
        for (const file of files) {
          const content = await file.text();
          items.push({ filename: file.name || "upload.txt", content: content || "" });
        }
        const resp = await fetch("/api/collector/import-texts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ items }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "导入失败");
        this.setMessage(`文件导入完成: parsed=${data.total_parsed}, inserted=${data.total_inserted}, updated=${data.total_updated}, deduped=${data.total_deduped}, invalid=${data.total_invalid}`);
        await this.loadData();
        await this.loadProxyCatalog();
      } catch (err) {
        this.setMessage("文件导入失败: " + err, true);
      }
    },

    // --- Data Loading ---
    normalizeFilterValue(value) {
      if (value === null || value === undefined) return "";
      return String(value).trim();
    },
    async loadData() {
      try {
        const statsResp = await fetch("/api/stats");
        this.stats = await statsResp.json();
        const params = new URLSearchParams({ limit: "5000" });
        const filters = this.proxyFilters;
        const protocol = this.normalizeFilterValue(filters.protocol);
        const available = this.normalizeFilterValue(filters.available);
        const geo = this.normalizeFilterValue(filters.geo);
        const geoCountry = this.normalizeFilterValue(filters.geo_country);
        const geoLocation = this.normalizeFilterValue(filters.geo_location);
        const openai = this.normalizeFilterValue(filters.openai);
        const ipPurity = this.normalizeFilterValue(filters.ip_purity);
        const fallbackFront = this.normalizeFilterValue(filters.fallback_front);
        const source = this.normalizeFilterValue(filters.source);
        const speedMinText = this.normalizeFilterValue(filters.speed_min_mbps);
        const speedMinMbps = Number(speedMinText);

        if (protocol) params.set("protocol", protocol);
        if (available === "true" || available === "false") params.set("available", available);
        if (geoCountry) params.set("geo_country", geoCountry);
        if (geoLocation) { params.set("geo_filter", "has"); params.set("geo_location", geoLocation); }
        else if (geo === "has" || geo === "none") params.set("geo_filter", geo);
        if (["unlocked", "blocked", "unchecked"].includes(openai)) params.set("openai_filter", openai);
        if (["checked", "unchecked", "residential", "non_residential", "unknown"].includes(ipPurity)) params.set("ip_purity_filter", ipPurity);
        if (fallbackFront === "has" || fallbackFront === "none") params.set("fallback_front_filter", fallbackFront);
        if (speedMinText && Number.isFinite(speedMinMbps) && speedMinMbps >= 0) params.set("speed_min_mbps", String(speedMinMbps));
        if (source) params.set("source", source);
        params.set("sort_by", "latency");
        params.set("sort_order", "asc");

        const proxyResp = await fetch("/api/proxies?" + params.toString());
        const proxyData = await proxyResp.json();
        this.proxies = proxyData.items || [];
        this.resetPage("proxies");
      } catch (err) {
        this.setMessage("加载数据失败: " + err, true);
      }
    },
    async loadProxyCatalog() {
      try {
        const resp = await fetch("/api/proxies?limit=5000&sort_by=latency&sort_order=asc");
        const data = await resp.json();
        const items = data.items || [];
        this.allProxies = items;
        const stableMap = {};
        this.allProxies.forEach((item, idx) => { stableMap[item.normalized_key] = idx + 1; });
        this.proxySerialMap = stableMap;
        if ((this.routeEntries || []).length > 0) {
          this.routeEntries = this.routeEntries.map(item => this.normalizeRouteItem(item));
        }
        this.pruneSelectedProxyKeys();
      } catch (err) {
        this.setMessage("加载代理序号映射失败: " + err, true);
      }
    },
    async loadDataClick() { await this.runWithButtonState("loadData", () => this.loadData()); },
    async onLoadDataClick() { await this.loadDataClick(); },

    // --- Subscriptions ---
    async loadSubscriptions() {
      try {
        const resp = await fetch("/api/subscriptions?limit=1000");
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "加载订阅失败");
        this.subscriptions = data.items || [];
        this.resetPage("subscriptions");
      } catch (err) { this.setMessage("加载订阅失败: " + err, true); }
    },
    async createSubscription() {
      const name = String(this.subscriptionForm.name || "").trim();
      const url = String(this.subscriptionForm.url || "").trim();
      if (!url) { this.setMessage("订阅链接不能为空", true); return; }
      try {
        const resp = await fetch("/api/subscriptions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name || "subscription", url, enabled: true }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "保存失败");
        this.subscriptionForm.name = "";
        this.subscriptionForm.url = "";
        this.setMessage("订阅已保存");
        await this.loadSubscriptions();
      } catch (err) { this.setMessage("保存订阅失败: " + err, true); }
    },
    async onToggleSubscription(item) {
      await this.runWithButtonState(`toggleSub-${item.id}`, async () => {
        try {
          const resp = await fetch(`/api/subscriptions/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: !item.enabled }),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "更新失败");
          this.setMessage(`订阅 ${data.item.enabled ? "已启用" : "已停用"}`);
          await this.loadSubscriptions();
        } catch (err) { this.setMessage("切换订阅状态失败: " + err, true); }
      });
    },
    async onRenameSubscription(item, nextName) {
      const name = String(nextName || "").trim();
      if (!name || name === String(item.name || "").trim()) return;
      await this.runWithButtonState(`renameSub-${item.id}`, async () => {
        try {
          const resp = await fetch(`/api/subscriptions/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "更新失败");
          this.setMessage("订阅名称已更新");
          await this.loadSubscriptions();
        } catch (err) { this.setMessage("更新订阅名称失败: " + err, true); }
      });
    },
    async onRefreshSubscription(subscriptionId) {
      await this.runWithButtonState(`refreshSub-${subscriptionId}`, async () => {
        try {
          const resp = await fetch(`/api/subscriptions/${subscriptionId}/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ timeout_sec: 12 }),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "刷新失败");
          const rpt = data.report || {};
          this.setMessage(`订阅刷新完成: parsed=${rpt.total_parsed || 0}, inserted=${rpt.total_inserted || 0}, updated=${rpt.total_updated || 0}, invalid=${rpt.total_invalid || 0}`);
          await this.loadSubscriptions();
          await this.loadData();
          await this.loadProxyCatalog();
        } catch (err) { this.setMessage("刷新订阅失败: " + err, true); }
      });
    },
    async refreshAllSubscriptions() {
      try {
        await this.startProgressTask("/api/tasks/subscriptions-refresh/start?timeout_sec=12", {}, "订阅刷新任务");
        await this.loadSubscriptions();
      } catch (err) { this.setMessage("批量刷新订阅失败: " + err, true); }
    },
    async deleteUnavailableSubscriptions() {
      try {
        const resp = await fetch("/api/subscriptions/delete-unavailable", { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "删除失败");
        this.setMessage(`已删除不可用订阅: ${data.deleted || 0}`);
        await this.loadSubscriptions();
      } catch (err) { this.setMessage("删除不可用订阅失败: " + err, true); }
    },
    async onDeleteSubscription(subscriptionId) {
      await this.runWithButtonState(`deleteSub-${subscriptionId}`, async () => {
        try {
          const resp = await fetch(`/api/subscriptions/${subscriptionId}`, { method: "DELETE" });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "删除失败");
          this.setMessage(`已删除订阅: ${data.deleted || 0}`);
          await this.loadSubscriptions();
        } catch (err) { this.setMessage("删除订阅失败: " + err, true); }
      });
    },
    async onLoadSubscriptions() { await this.runWithButtonState("loadSubscriptions", () => this.loadSubscriptions()); },
    async onCreateSubscription() { await this.runWithButtonState("createSubscription", () => this.createSubscription()); },
    async onRefreshAllSubscriptions() { await this.runWithButtonState("refreshAllSubscriptions", () => this.refreshAllSubscriptions()); },
    async onDeleteUnavailableSubscriptions() { await this.runWithButtonState("deleteUnavailableSubscriptions", () => this.deleteUnavailableSubscriptions()); },

    // --- Subscription Update Proxy ---
    async loadSubscriptionUpdateProxy() {
      try {
        const resp = await fetch("/api/subscription-update-proxy");
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "加载全局更新代理失败");
        this.subscriptionUpdateProxyRef = this.toDisplayProxyRef(data.update_proxy_key || "");
      } catch (err) { this.setMessage("加载全局更新代理失败: " + err, true); }
    },
    async saveSubscriptionUpdateProxy() {
      try {
        const raw = String(this.subscriptionUpdateProxyRef || "").trim();
        const key = raw ? this.resolveProxyRef(raw) : "";
        const resp = await fetch("/api/subscription-update-proxy", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ update_proxy_key: key }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "保存失败");
        this.subscriptionUpdateProxyRef = this.toDisplayProxyRef(data.update_proxy_key || "");
        this.setMessage("全局订阅更新代理已保存");
      } catch (err) { this.setMessage("保存全局更新代理失败: " + err, true); }
    },
    async onSaveSubscriptionUpdateProxy() { await this.runWithButtonState("saveSubUpdateProxy", () => this.saveSubscriptionUpdateProxy()); },

    // --- Published Subscriptions ---
    normalizePublishedSubscriptionFilters(filters) {
      const raw = filters || {};
      const clean = {};
      for (const key of ["available", "geo_country", "geo_location", "openai_filter", "ip_purity_filter", "fallback_front_filter", "source"]) {
        const value = String(raw[key] || "").trim();
        if (value) clean[key] = value;
      }
      return clean;
    },
    async loadPublishedSubscriptions() {
      try {
        const resp = await fetch("/api/published-subscriptions?limit=1000");
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "加载发布订阅失败");
        this.publishedSubscriptions = data.items || [];
        this.resetPage("publishedSubscriptions");
      } catch (err) { this.setMessage("加载发布订阅失败: " + err, true); }
    },
    publishedSubscriptionExportUrl(item) {
      return String(item?.export_url || `/api/published-subscriptions/${item?.id}/subscription`);
    },
    formatPublishedSubscriptionFilters(filters) {
      const f = filters || {};
      const parts = [];
      if (f.available === "true") parts.push("仅可直连");
      else if (f.available === "false") parts.push("仅不可直连");
      if (f.geo_location) parts.push(`位置 ${f.geo_location}`);
      else if (f.geo_country) parts.push(`国家 ${f.geo_country}`);
      if (f.openai_filter === "unlocked") parts.push("ChatGPT已解锁");
      else if (f.openai_filter === "blocked") parts.push("ChatGPT未解锁");
      else if (f.openai_filter === "unchecked") parts.push("ChatGPT未检测");
      if (f.ip_purity_filter === "residential") parts.push("家宽");
      else if (f.ip_purity_filter === "non_residential") parts.push("非家宽");
      else if (f.ip_purity_filter === "unknown") parts.push("纯净度未知");
      if (f.fallback_front_filter === "has") parts.push("有可连通前置");
      else if (f.fallback_front_filter === "none") parts.push("无前置链路");
      if (f.source) parts.push(`来源 ${f.source}`);
      return parts.length ? parts.join(" / ") : "不限";
    },
    applyPublishedSubscriptionFiltersToForm(item) {
      this.publishedSubscriptionForm.name = String(item?.name || "");
      this.publishedSubscriptionForm.format = this.normalizePublishedSubscriptionFormat(item?.format);
      this.publishedSubscriptionForm.filters = {
        available: "", geo_country: "", geo_location: "",
        openai_filter: "", ip_purity_filter: "", fallback_front_filter: "", source: "",
        ...(item?.filters || {}),
      };
      this.setMessage("已套用发布订阅筛选,可修改后保存当前筛选");
    },
    normalizePublishedSubscriptionFormat(value) {
      const text = String(value || "raw").trim().toLowerCase();
      return text === "clash" ? "clash" : "raw";
    },
    formatPublishedSubscriptionOutput(value) {
      return this.normalizePublishedSubscriptionFormat(value) === "clash" ? "Clash" : "原始链接";
    },
    async createPublishedSubscription() {
      const name = String(this.publishedSubscriptionForm.name || "").trim();
      try {
        const resp = await fetch("/api/published-subscriptions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: name || "published-subscription",
            enabled: true,
            format: this.normalizePublishedSubscriptionFormat(this.publishedSubscriptionForm.format),
            filters: this.normalizePublishedSubscriptionFilters(this.publishedSubscriptionForm.filters),
          }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "创建失败");
        this.publishedSubscriptionForm.name = "";
        this.setMessage("发布订阅已创建");
        await this.loadPublishedSubscriptions();
      } catch (err) { this.setMessage("创建发布订阅失败: " + err, true); }
    },
    async onRenamePublishedSubscription(item, nextName) {
      const name = String(nextName || "").trim();
      if (!name || name === String(item.name || "").trim()) return;
      await this.runWithButtonState(`renamePubSub-${item.id}`, async () => {
        try {
          const resp = await fetch(`/api/published-subscriptions/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "更新失败");
          this.setMessage("发布订阅名称已更新");
          await this.loadPublishedSubscriptions();
        } catch (err) { this.setMessage("更新发布订阅名称失败: " + err, true); }
      });
    },
    async onTogglePublishedSubscription(item) {
      await this.runWithButtonState(`togglePubSub-${item.id}`, async () => {
        try {
          const resp = await fetch(`/api/published-subscriptions/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: !item.enabled }),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "更新失败");
          this.setMessage(`发布订阅 ${data.item.enabled ? "已启用" : "已停用"}`);
          await this.loadPublishedSubscriptions();
        } catch (err) { this.setMessage("切换发布订阅状态失败: " + err, true); }
      });
    },
    async onUpdatePublishedSubscriptionFilters(item) {
      await this.runWithButtonState(`updatePubSub-${item.id}`, async () => {
        try {
          const resp = await fetch(`/api/published-subscriptions/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              format: this.normalizePublishedSubscriptionFormat(this.publishedSubscriptionForm.format),
              filters: this.normalizePublishedSubscriptionFilters(this.publishedSubscriptionForm.filters),
            }),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "保存失败");
          this.setMessage(`发布订阅筛选已保存: ${data.item.match_count || 0} 个节点`);
          await this.loadPublishedSubscriptions();
        } catch (err) { this.setMessage("保存发布订阅筛选失败: " + err, true); }
      });
    },
    async onCopyPublishedSubscriptionUrl(item) {
      await this.runWithButtonState(`copyPubSub-${item.id}`, async () => {
        try {
          await this.copyTextToClipboard(new URL(this.publishedSubscriptionExportUrl(item), window.location.href).toString());
          this.setMessage("发布订阅链接已复制");
        } catch (err) { this.setMessage("复制发布订阅链接失败: " + err, true); }
      });
    },
    async onDeletePublishedSubscription(subscriptionId) {
      await this.runWithButtonState(`deletePubSub-${subscriptionId}`, async () => {
        try {
          const resp = await fetch(`/api/published-subscriptions/${subscriptionId}`, { method: "DELETE" });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "删除失败");
          this.setMessage(`已删除发布订阅: ${data.deleted || 0}`);
          await this.loadPublishedSubscriptions();
        } catch (err) { this.setMessage("删除发布订阅失败: " + err, true); }
      });
    },
    async onLoadPublishedSubscriptions() { await this.runWithButtonState("loadPublishedSubscriptions", () => this.loadPublishedSubscriptions()); },
    async onCreatePublishedSubscription() { await this.runWithButtonState("createPublishedSubscription", () => this.createPublishedSubscription()); },

    // --- Proxy Pools ---
    async loadProxyPools() {
      try {
        const resp = await fetch("/api/pools?limit=1000");
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "加载代理池失败");
        this.proxyPools = data.items || [];
        if (!this.selectedPoolIdForChain && this.proxyPools.length) {
          this.selectPoolForChain(this.proxyPools[0]);
        } else if (this.selectedPoolIdForChain) {
          const selected = this.proxyPools.find(item => Number(item.id) === Number(this.selectedPoolIdForChain));
          if (selected) this.selectPoolForChain(selected);
          else this.selectPoolForChain(null);
        } else {
          this.resetSelectedPoolForChainState();
        }
        this.resetPage("proxyPools");
      } catch (err) { this.setMessage("加载代理池失败: " + err, true); }
    },
    normalizePoolFilters(filters) {
      const out = {};
      for (const [k, v] of Object.entries(filters || {})) {
        if (k === "geo_countries") {
          const countries = Array.isArray(v) ? v.map(item => String(item || "").trim()).filter(Boolean) : [];
          if (countries.length) out[k] = countries;
          continue;
        }
        const s = String(v ?? "").trim();
        if (s) out[k] = s;
      }
      return out;
    },
    routeModeFilterFromLegacyFilters(filters) {
      const f = filters || {};
      const routeMode = String(f.route_mode_filter || "").trim();
      if (["direct", "chain", "unreachable"].includes(routeMode)) return routeMode;
      const available = String(f.available || "").trim();
      const fallbackFront = String(f.fallback_front_filter || "").trim();
      if (available === "false") return "unreachable";
      if (available === "true" && fallbackFront === "has") return "chain";
      if (available === "true" && fallbackFront === "none") return "direct";
      return "";
    },
    formatPoolFilters(filters) {
      const f = filters || {};
      const parts = [];
      const routeMode = this.routeModeFilterFromLegacyFilters(f);
      if (routeMode === "direct") parts.push("直连");
      else if (routeMode === "chain") parts.push("链式");
      else if (routeMode === "unreachable") parts.push("不可连接");
      else if (f.available === "true") parts.push("可用");
      else if (f.available === "false") parts.push("不可用");
      if (f.protocol) parts.push(f.protocol);
      const geoCountries = Array.isArray(f.geo_countries) ? f.geo_countries : [];
      if (geoCountries.length) parts.push(`国家:${geoCountries.join(",")}`);
      else if (f.geo_country) parts.push(f.geo_country);
      if (f.openai_filter === "unlocked") parts.push("GPT解锁");
      else if (f.openai_filter === "blocked") parts.push("GPT未解锁");
      if (f.ip_purity_filter === "residential") parts.push("家宽");
      else if (f.ip_purity_filter === "non_residential") parts.push("非家宽");
      if (f.latency_min || f.latency_max) parts.push(`延迟${f.latency_min||0}-${f.latency_max||'∞'}ms`);
      if (f.freshness_hours) parts.push(`${f.freshness_hours}h内`);
      if (f.source) parts.push(`来源:${f.source}`);
      return parts.length ? parts.join(" / ") : "不限";
    },
    applyPoolFiltersToForm(item) {
      this.proxyPoolForm.name = String(item?.name || "");
      this.proxyPoolForm.listen = String(item?.listen || "0.0.0.0");
      this.proxyPoolForm.inbound_type = String(item?.inbound_type || "http");
      const itemFilters = { ...(item?.filters || {}) };
      const routeMode = this.routeModeFilterFromLegacyFilters(itemFilters);
      const geoCountries = Array.isArray(itemFilters.geo_countries)
        ? itemFilters.geo_countries.map(item => String(item || "").trim()).filter(Boolean)
        : [];
      this.proxyPoolForm.filters = {
        route_mode_filter: routeMode, geo_countries: geoCountries, geo_country: "", geo_location: "",
        openai_filter: "", ip_purity_filter: "",
        source: "", protocol: "", latency_min: "", latency_max: "", freshness_hours: "",
        ...itemFilters,
      };
      for (const key of ["available", "fallback_front_filter", "geo_country"]) delete this.proxyPoolForm.filters[key];
      this.setMessage("已套用代理池筛选,可修改后保存");
    },
    listTextToMultiline(value) {
      return Array.isArray(value) ? value.map(item => String(item || "").trim()).filter(Boolean).join("\n") : "";
    },
    parseMultilineList(value) {
      return String(value || "").split(/[\n,]+/g).map(item => item.trim()).filter(Boolean);
    },
    poolSessionRulesApiBase(poolId) {
      return `/api/pools/${poolId}/chain/session-rules`;
    },
    poolRouteTestApiUrl(poolId, params = "") {
      return `/api/pools/${poolId}/chain/route-test${params ? `?${params}` : ""}`;
    },
    gatewayApiBase() {
      return "/api/gateway";
    },
    gatewayEndpointsApiBase() {
      return "/api/http-proxy-endpoints";
    },
    resetGatewayEndpointForm() {
      this.gatewayEndpointForm = {
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
      };
    },
    formatEndpointHops(item) {
      const hops = Array.isArray(item?.hops) ? item.hops : [];
      if (!hops.length) return "未配置";
      return hops.map(hop => {
        const pool = (this.proxyPools || []).find(candidate => Number(candidate.id) === Number(hop.pool_id));
        return pool ? `${pool.name} (#${pool.id})` : `#${hop.pool_id}`;
      }).join(" -> ");
    },
    moveGatewayEndpointHop(index, delta) {
      const hops = Array.isArray(this.gatewayEndpointForm.hop_pool_ids) ? [...this.gatewayEndpointForm.hop_pool_ids] : [];
      const from = Number(index);
      const to = from + Number(delta || 0);
      if (from < 0 || from >= hops.length || to < 0 || to >= hops.length) return;
      const [item] = hops.splice(from, 1);
      hops.splice(to, 0, item);
      this.gatewayEndpointForm.hop_pool_ids = hops;
    },
    editGatewayEndpoint(item) {
      this.gatewayEndpointForm = {
        id: Number(item?.id || 0),
        name: String(item?.name || ""),
        listen_host: String(item?.listen_host || "127.0.0.1"),
        listen_port: Number(item?.listen_port || 18899),
        enabled: item?.enabled !== false,
        sticky_ttl_sec: Number(item?.sticky_ttl_sec || 3600),
        session_missing_action: String(item?.session_missing_action || "RANDOM"),
        session_header_names_text: this.listTextToMultiline(item?.session_header_names),
        session_query_param_names_text: this.listTextToMultiline(item?.session_query_param_names),
        connect_session_header_names_text: this.listTextToMultiline(item?.connect_session_header_names),
        hop_pool_ids: (item?.hops || []).map(hop => Number(hop.pool_id || 0)).filter(Boolean),
      };
    },
    onGatewayStatusEndpointChanged() {
      this.loadGatewayStatus();
    },
    async loadGatewayEndpoints() {
      const resp = await fetch(this.gatewayEndpointsApiBase());
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "加载 HTTP 端点失败");
      this.gatewayEndpoints = data.items || [];
      const preferredStatusId = Number(this.gatewayStatusEndpointId || this.gatewayConfigForm.endpoint_id || 0);
      if (!preferredStatusId && this.gatewayEndpoints.length) this.gatewayStatusEndpointId = Number(this.gatewayEndpoints[0].id || 0);
      if (!this.gatewayEndpointForm.id && this.gatewayEndpoints.length) {
        const preferred = this.gatewayEndpoints.find(item => Number(item.id) === Number(this.gatewayConfigForm.endpoint_id || 0));
        if (preferred) this.editGatewayEndpoint(preferred);
        else this.editGatewayEndpoint(this.gatewayEndpoints[0]);
      }
    },
    gatewayEndpointPayload() {
      return {
        name: String(this.gatewayEndpointForm.name || "").trim(),
        listen_host: String(this.gatewayEndpointForm.listen_host || "").trim() || "127.0.0.1",
        listen_port: Math.max(1, Number(this.gatewayEndpointForm.listen_port || 18899)),
        enabled: this.gatewayEndpointForm.enabled === true,
        sticky_ttl_sec: Math.max(1, Number(this.gatewayEndpointForm.sticky_ttl_sec || 3600)),
        session_missing_action: String(this.gatewayEndpointForm.session_missing_action || "RANDOM").trim() || "RANDOM",
        session_header_names: this.parseMultilineList(this.gatewayEndpointForm.session_header_names_text),
        session_query_param_names: this.parseMultilineList(this.gatewayEndpointForm.session_query_param_names_text),
        connect_session_header_names: this.parseMultilineList(this.gatewayEndpointForm.connect_session_header_names_text),
        hop_pool_ids: (this.gatewayEndpointForm.hop_pool_ids || []).map(item => Number(item || 0)).filter(Boolean),
      };
    },
    async saveGatewayEndpoint() {
      const payload = this.gatewayEndpointPayload();
      if (!payload.name) throw new Error("请输入端点名称");
      if (!payload.hop_pool_ids.length) throw new Error("请至少选择一个代理池跳点");
      const endpointId = Number(this.gatewayEndpointForm.id || 0);
      const url = endpointId ? `${this.gatewayEndpointsApiBase()}/${endpointId}` : this.gatewayEndpointsApiBase();
      const method = endpointId ? "PUT" : "POST";
      const resp = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "保存 HTTP 端点失败");
      await this.loadGatewayEndpoints();
      this.editGatewayEndpoint(data.item || {});
      this.gatewayStatusEndpointId = Number(data.item?.id || this.gatewayStatusEndpointId || 0);
      await this.loadGatewayStatus();
      this.setMessage(`HTTP 端点已保存: ${data.item?.name || payload.name}`);
    },
    async deleteGatewayEndpoint(endpointId) {
      const resp = await fetch(`${this.gatewayEndpointsApiBase()}/${Number(endpointId)}`, { method: "DELETE" });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "删除 HTTP 端点失败");
      await this.loadGatewayEndpoints();
      if (Number(this.gatewayConfigForm.endpoint_id || 0) === Number(endpointId)) {
        this.gatewayConfigForm.endpoint_id = 0;
      }
      if (Number(this.gatewayStatusEndpointId || 0) === Number(endpointId)) {
        this.gatewayStatusEndpointId = this.gatewayEndpoints.length ? Number(this.gatewayEndpoints[0].id || 0) : 0;
      }
      this.resetGatewayEndpointForm();
      await this.loadGatewayStatus();
      this.setMessage("HTTP 端点已删除");
    },
    async selectGatewayEndpoint(item) {
      this.gatewayConfigForm.endpoint_id = Number(item?.id || 0);
      this.gatewayStatusEndpointId = Number(item?.id || 0);
      await this.saveGatewayConfig();
      this.setMessage(`默认端点已切换: ${item?.name || item?.id}`);
    },
    async runGatewayEndpointRouteTest(item) {
      const endpointId = Number(item?.id || 0);
      if (!endpointId) throw new Error("端点不存在");
      const params = new URLSearchParams();
      params.set("session_id", String(this.gatewayTestForm.session_id || "").trim() || "endpoint-demo");
      params.set("target_domain", "api.example.com");
      const resp = await fetch(`${this.gatewayEndpointsApiBase()}/${endpointId}/route-test?${params.toString()}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "端点路由测试失败");
      this.gatewayTestResult = data;
      this.setMessage(`端点路由测试成功: ${item?.name || endpointId}`);
    },
    gatewayPoolPath(poolName) {
      return `/proxy/${encodeURIComponent(poolName)}`;
    },
    resetSelectedPoolForChainState() {
      this.selectedPoolIdForChain = 0;
      this.selectedPoolNameForChain = "";
      this.poolChainForm = {
        chain_enabled: false,
        sticky_ttl_sec: 3600,
        session_missing_action: "RANDOM",
        session_header_names_text: "X-ProxyPool-Session",
        session_query_param_names_text: "session",
        gateway_path_prefix: "",
      };
      this.poolSessionRuleForm = { url_prefix: "", headers_text: "" };
      this.poolSessionRules = [];
      this.poolRouteTest = {
        session_id: "",
        target_domain: "",
      };
      this.poolRouteTestResult = null;
    },
    selectPoolForChain(item) {
      if (!item) {
        this.resetSelectedPoolForChainState();
        return;
      }
      const poolId = Number(item?.id || 0);
      this.selectedPoolIdForChain = poolId;
      this.selectedPoolNameForChain = String(item?.name || "").trim();
      this.poolChainForm = {
        chain_enabled: item?.chain_enabled === true,
        sticky_ttl_sec: Number(item?.sticky_ttl_sec || 3600),
        session_missing_action: String(item?.session_missing_action || "RANDOM"),
        session_header_names_text: this.listTextToMultiline(item?.session_header_names),
        session_query_param_names_text: this.listTextToMultiline(item?.session_query_param_names),
        gateway_path_prefix: String(item?.gateway_path_prefix || ""),
      };
      this.poolRouteTestResult = null;
      this.poolSessionRuleForm = { url_prefix: "", headers_text: "" };
      if (poolId > 0) this.loadPoolSessionRules(poolId);
      else this.poolSessionRules = [];
    },
    async loadPoolSessionRules(poolId = this.selectedPoolIdForChain) {
      const id = Number(poolId || 0);
      if (!id) {
        this.poolSessionRules = [];
        return;
      }
      const resp = await fetch(this.poolSessionRulesApiBase(id));
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "加载会话规则失败");
      this.poolSessionRules = data.items || [];
    },
    async savePoolChainConfig(poolId = this.selectedPoolIdForChain) {
      const id = Number(poolId || 0);
      if (!id) throw new Error("请先选择代理池");
      const payload = {
        chain_enabled: this.poolChainForm.chain_enabled === true,
        sticky_ttl_sec: Math.max(1, Number(this.poolChainForm.sticky_ttl_sec || 3600)),
        session_missing_action: String(this.poolChainForm.session_missing_action || "RANDOM").trim() || "RANDOM",
        session_header_names: this.parseMultilineList(this.poolChainForm.session_header_names_text),
        session_query_param_names: this.parseMultilineList(this.poolChainForm.session_query_param_names_text),
        gateway_path_prefix: String(this.poolChainForm.gateway_path_prefix || "").trim(),
      };
      const resp = await fetch(`/api/pools/${id}/chain`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "保存链路配置失败");
      this.selectPoolForChain(data.item || {});
      await this.loadProxyPools();
      this.setMessage("池级链路配置已保存");
    },
    async loadGatewayConfig() {
      const resp = await fetch(`${this.gatewayApiBase()}/http-config`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "加载网关配置失败");
      const item = data.item || {};
      this.gatewayConfigForm = {
        enabled: item.enabled === true,
        listen_host: String(item.listen_host || "127.0.0.1"),
        listen_port: Number(item.listen_port || 8899),
        endpoint_id: Number(item.endpoint_id || 0),
        default_pool_id: Number(item.default_pool_id || 0),
        sticky_ttl_sec: Number(item.sticky_ttl_sec || 3600),
        session_missing_action: String(item.session_missing_action || "RANDOM"),
        http_session_header_names_text: this.listTextToMultiline(item.http_session_header_names),
        http_session_query_names_text: this.listTextToMultiline(item.http_session_query_names),
        connect_session_header_names_text: this.listTextToMultiline(item.connect_session_header_names),
      };
    },
    async saveGatewayConfig() {
      const payload = {
        enabled: this.gatewayConfigForm.enabled === true,
        listen_host: String(this.gatewayConfigForm.listen_host || "").trim() || "127.0.0.1",
        listen_port: Math.max(1, Number(this.gatewayConfigForm.listen_port || 8899)),
        endpoint_id: Math.max(0, Number(this.gatewayConfigForm.endpoint_id || 0)),
        default_pool_id: Math.max(0, Number(this.gatewayConfigForm.default_pool_id || 0)),
        sticky_ttl_sec: Math.max(1, Number(this.gatewayConfigForm.sticky_ttl_sec || 3600)),
        session_missing_action: String(this.gatewayConfigForm.session_missing_action || "RANDOM").trim() || "RANDOM",
        http_session_header_names: this.parseMultilineList(this.gatewayConfigForm.http_session_header_names_text),
        http_session_query_names: this.parseMultilineList(this.gatewayConfigForm.http_session_query_names_text),
        connect_session_header_names: this.parseMultilineList(this.gatewayConfigForm.connect_session_header_names_text),
      };
      const resp = await fetch(`${this.gatewayApiBase()}/http-config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "保存网关配置失败");
      await this.loadGatewayConfig();
      await this.loadGatewayStatus();
      this.setMessage("HTTP 网关配置已保存");
    },
    async loadGatewayStatus() {
      const endpointId = Number(this.gatewayStatusEndpointId || this.gatewayConfigForm.endpoint_id || 0);
      const suffix = endpointId > 0 ? `?endpoint_id=${encodeURIComponent(endpointId)}` : "";
      const resp = await fetch(`${this.gatewayApiBase()}/http-status${suffix}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "加载网关状态失败");
      this.gatewayStatus = data;
      if (Number(data?.summary?.endpoint_id || 0) > 0) this.gatewayStatusEndpointId = Number(data.summary.endpoint_id);
    },
    async runGatewayTest() {
      const resp = await fetch(`${this.gatewayApiBase()}/http-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_url: String(this.gatewayTestForm.target_url || "").trim(),
          endpoint_id: Math.max(0, Number(this.gatewayTestForm.endpoint_id || 0)),
          session_id: String(this.gatewayTestForm.session_id || "").trim(),
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "执行网关测试失败");
      this.gatewayTestResult = data;
      await this.loadGatewayStatus();
      if (data.ok) this.setMessage("HTTP 网关测试成功");
      else this.setMessage(data.detail || "HTTP 网关测试失败", true);
    },
    async savePoolSessionRule(poolId = this.selectedPoolIdForChain) {
      const id = Number(poolId || 0);
      if (!id) throw new Error("请先选择代理池");
      const urlPrefix = String(this.poolSessionRuleForm.url_prefix || "").trim();
      if (!urlPrefix) throw new Error("请输入 URL 前缀");
      const headers = this.parseMultilineList(this.poolSessionRuleForm.headers_text);
      const resp = await fetch(`${this.poolSessionRulesApiBase(id)}/${encodeURIComponent(urlPrefix)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ headers }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "保存会话规则失败");
      this.poolSessionRuleForm = { url_prefix: "", headers_text: "" };
      await this.loadPoolSessionRules(id);
      this.setMessage(`会话规则已保存: ${data.item?.url_prefix || urlPrefix}`);
    },
    async deletePoolSessionRule(urlPrefix, poolId = this.selectedPoolIdForChain) {
      const id = Number(poolId || 0);
      if (!id) throw new Error("请先选择代理池");
      const resp = await fetch(`${this.poolSessionRulesApiBase(id)}/${encodeURIComponent(String(urlPrefix || "").trim())}`, {
        method: "DELETE",
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "删除会话规则失败");
      await this.loadPoolSessionRules(id);
      this.setMessage("会话规则已删除");
    },
    usePoolSessionRule(item) {
      this.poolSessionRuleForm = {
        url_prefix: String(item?.url_prefix || ""),
        headers_text: this.listTextToMultiline(item?.headers),
      };
    },
    async testPoolRoute(poolId = this.selectedPoolIdForChain) {
      const id = Number(poolId || 0);
      if (!id) throw new Error("请先选择代理池");
      const params = new URLSearchParams();
      if (this.poolRouteTest.session_id) params.set("session_id", this.poolRouteTest.session_id);
      if (this.poolRouteTest.target_domain) params.set("target_domain", this.poolRouteTest.target_domain);
      const resp = await fetch(this.poolRouteTestApiUrl(id, params.toString()));
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "池级路由测试失败");
      this.poolRouteTestResult = data;
      this.setMessage("池级路由测试成功");
    },
    async createProxyPool() {
      const name = String(this.proxyPoolForm.name || "").trim();
      if (!name) { this.setMessage("请输入池名称", true); return; }
      try {
        const resp = await fetch("/api/pools", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            listen: this.proxyPoolForm.listen || "0.0.0.0",
            inbound_type: this.proxyPoolForm.inbound_type || "http",
            filters: this.normalizePoolFilters(this.proxyPoolForm.filters),
          }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "创建失败");
        this.proxyPoolForm.name = "";
        this.setMessage("代理池已创建");
        await this.loadProxyPools();
      } catch (err) { this.setMessage("创建代理池失败: " + err, true); }
    },
    async syncPool(poolId) {
      try {
        const resp = await fetch(`/api/pools/${poolId}/sync`, { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "同步失败");
        this.setMessage("代理池已同步");
        await this.loadProxyPools();
      } catch (err) { this.setMessage("同步代理池失败: " + err, true); }
    },
    async onRenameProxyPool(item, nextName) {
      const name = String(nextName || "").trim();
      if (!name || name === String(item.name || "").trim()) return;
      await this.runWithButtonState(`renamePool-${item.id}`, async () => {
        try {
          const resp = await fetch(`/api/pools/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
          });
          if (!resp.ok) { const d = await resp.json(); throw new Error(d.detail || "更新失败"); }
          this.setMessage("代理池名称已更新");
          await this.loadProxyPools();
        } catch (err) { this.setMessage("更新代理池名称失败: " + err, true); }
      });
    },
    async onUpdatePoolFilters(item) {
      await this.runWithButtonState(`updatePool-${item.id}`, async () => {
        try {
          const resp = await fetch(`/api/pools/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filters: this.normalizePoolFilters(this.proxyPoolForm.filters) }),
          });
          if (!resp.ok) { const d = await resp.json(); throw new Error(d.detail || "保存失败"); }
          this.setMessage("代理池筛选已保存");
          await this.loadProxyPools();
        } catch (err) { this.setMessage("保存代理池筛选失败: " + err, true); }
      });
    },
    async onDeleteProxyPool(poolId) {
      await this.runWithButtonState(`deletePool-${poolId}`, async () => {
        try {
          const resp = await fetch(`/api/pools/${poolId}`, { method: "DELETE" });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "删除失败");
          this.setMessage("代理池已删除");
          await this.loadProxyPools();
        } catch (err) { this.setMessage("删除代理池失败: " + err, true); }
      });
    },
    async onCreateProxyPool() { await this.runWithButtonState("createProxyPool", () => this.createProxyPool()); },
    async onLoadProxyPools() { await this.runWithButtonState("loadProxyPools", () => this.loadProxyPools()); },
    async onSyncPool(poolId) { await this.runWithButtonState(`syncPool-${poolId}`, () => this.syncPool(poolId)); },
    async onSelectPoolForChain(item) { this.selectPoolForChain(item); },
    async onSavePoolChainConfig(poolId) { await this.runWithButtonState(`savePoolChain-${poolId || this.selectedPoolIdForChain}`, () => this.savePoolChainConfig(poolId)); },
    async onLoadPoolSessionRules(poolId) { await this.runWithButtonState(`loadPoolSessionRules-${poolId || this.selectedPoolIdForChain}`, () => this.loadPoolSessionRules(poolId)); },
    async onSavePoolSessionRule(poolId) { await this.runWithButtonState(`savePoolSessionRule-${poolId || this.selectedPoolIdForChain}`, () => this.savePoolSessionRule(poolId)); },
    async onDeletePoolSessionRule(urlPrefix, poolId) { await this.runWithButtonState(`deletePoolSessionRule-${poolId || this.selectedPoolIdForChain}-${urlPrefix}`, () => this.deletePoolSessionRule(urlPrefix, poolId)); },
    async onTestPoolRoute(poolId) { await this.runWithButtonState(`testPoolRoute-${poolId || this.selectedPoolIdForChain}`, () => this.testPoolRoute(poolId)); },
    async onSaveGatewayConfig() { await this.runWithButtonState("saveGatewayConfig", () => this.saveGatewayConfig()); },
    async onLoadGatewayConfig() { await this.runWithButtonState("loadGatewayConfig", () => this.loadGatewayConfig()); },
    async onLoadGatewayStatus() { await this.runWithButtonState("loadGatewayStatus", () => this.loadGatewayStatus()); },
    async onRunGatewayTest() { await this.runWithButtonState("runGatewayTest", () => this.runGatewayTest()); },
    async onLoadGatewayEndpoints() { await this.runWithButtonState("loadGatewayEndpoints", () => this.loadGatewayEndpoints()); },
    async onSaveGatewayEndpoint() { await this.runWithButtonState("saveGatewayEndpoint", () => this.saveGatewayEndpoint()); },
    async onDeleteGatewayEndpoint(endpointId) { await this.runWithButtonState(`deleteGatewayEndpoint-${endpointId}`, () => this.deleteGatewayEndpoint(endpointId)); },
    async onSelectGatewayEndpoint(item) { await this.runWithButtonState(`selectGatewayEndpoint-${item?.id || 0}`, () => this.selectGatewayEndpoint(item)); },
    async onRunGatewayEndpointRouteTest(item) { await this.runWithButtonState(`routeTestEndpoint-${item?.id || 0}`, () => this.runGatewayEndpointRouteTest(item)); },

    // --- Chain Service ---
    async loadChainStatus() {
      try {
        const resp = await fetch("/api/chain/status");
        const data = await resp.json();
        this.chainStatus = data;
        this.chainPoolForm.front_filters = (data.front_pool?.regex_filters || []).join('\n');
        this.chainPoolForm.exit_filters = (data.exit_pool?.regex_filters || []).join('\n');
      } catch (err) { this.setMessage("加载代理链状态失败: " + err, true); }
    },
    async loadChainHealth() {
      try {
        const resp = await fetch("/api/chain/health");
        const data = await resp.json();
        this.chainHealth = data;
      } catch (err) { /* ignore */ }
    },
    async loadChainLeases() {
      await this.runWithButtonState("loadChainLeases", async () => {
        const resp = await fetch("/api/chain/leases");
        const data = await resp.json();
        this.chainLeases = data.leases || [];
      });
    },
    async saveChainPool(poolType) {
      const actionKey = `saveChainPool${poolType === 'front' ? 'Front' : 'Exit'}`;
      await this.runWithButtonState(actionKey, async () => {
        const filtersText = poolType === 'front' ? this.chainPoolForm.front_filters : this.chainPoolForm.exit_filters;
        const filters = filtersText.split('\n').map(s => s.trim()).filter(Boolean);
        const resp = await fetch(`/api/chain/pools/${poolType}?${filters.map(f => `regex_filters=${encodeURIComponent(f)}`).join('&')}`, { method: 'POST' });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || '保存失败');
        this.chainStatus = data;
        this.setMessage(`${poolType === 'front' ? '前置' : '后置'}节点池配置已保存`);
      });
    },
    async chainStart() {
      await this.runWithButtonState("chainStart", async () => {
        const resp = await fetch("/api/chain/start", { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || '启动失败');
        this.setMessage("代理链服务已启动");
        await this.loadChainStatus();
        await this.loadChainHealth();
      });
    },
    async chainStop() {
      await this.runWithButtonState("chainStop", async () => {
        const resp = await fetch("/api/chain/stop", { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || '停止失败');
        this.setMessage("代理链服务已停止");
        await this.loadChainStatus();
        await this.loadChainHealth();
      });
    },
    async cleanupChainLeases() {
      await this.runWithButtonState("cleanupChainLeases", async () => {
        const resp = await fetch("/api/chain/leases/cleanup", { method: "POST" });
        const data = await resp.json();
        this.setMessage(`已清理 ${data.removed || 0} 个过期租约`);
        await this.loadChainLeases();
      });
    },
    // --- Backend ---
    async loadBackendStatus() {
      try {
        const resp = await fetch("/api/backend/status");
        const data = await resp.json();
        this.backendStatus = data;
        this.routesJson = JSON.stringify(data.routes || [], null, 2);
        this.routeEntries = (data.routes || []).map(item => this.normalizeRouteItem(item));
        this.resetPage("routes");
        this.routeLatencyMap = {};
        if (data.running && (data.routes_count || 0) > 0) await this.checkRouteLatency();
        await this.loadBackendEvents();
      } catch (err) { this.setMessage("加载后端状态失败: " + err, true); }
    },
    async loadBackendEvents() {
      try {
        const resp = await fetch("/api/backend/process-events?limit=500");
        const data = await resp.json();
        this.backendEvents = data.items || [];
        this.resetPage("backendEvents");
      } catch (err) { this.setMessage("加载进程记录失败: " + err, true); }
    },
    async backendStart() {
      try {
        const resp = await fetch("/api/backend/start", { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "启动失败");
        this.backendStatus = data;
        this.setMessage("sing-box 后端已启动");
        await this.checkRouteLatency();
        await this.loadBackendEvents();
      } catch (err) { this.setMessage("启动失败: " + err, true); }
    },
    async backendStop() {
      try {
        const resp = await fetch("/api/backend/stop", { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "停止失败");
        this.backendStatus = data;
        this.setMessage("sing-box 后端已停止");
        await this.loadBackendEvents();
      } catch (err) { this.setMessage("停止失败: " + err, true); }
    },
    async backendRestart() {
      try {
        const resp = await fetch("/api/backend/restart", { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "重启失败");
        this.backendStatus = data;
        this.setMessage("sing-box 后端已重启");
        await this.checkRouteLatency();
        await this.loadBackendEvents();
      } catch (err) { this.setMessage("重启失败: " + err, true); }
    },
    backendActionInstanceId(instanceId = "") {
      return String(typeof instanceId === "string" ? instanceId : this.backendInstanceId || "default").trim() || "default";
    },
    async createBackendInstance(instanceId) {
      try {
        const id = String(instanceId || "default").trim() || "default";
        const resp = await fetch("/api/backend/instances", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ instance_id: id }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "创建实例失败");
        this.backendStatus = { ...this.backendStatus, instances: data.items || [] };
        this.backendInstanceId = id;
        this.backendConfigInstanceId = id;
        await this.openBackendInstanceConfig({ instance_id: id });
        this.setMessage(`sing-box 实例已创建: ${id}`);
        await this.loadBackendEvents();
      } catch (err) { this.setMessage("创建实例失败: " + err, true); }
    },
    async backendInstanceStart(instanceId) {
      try {
        const id = String(instanceId || "default").trim() || "default";
        const resp = await fetch(`/api/backend/instances/${encodeURIComponent(id)}/start`, { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "启动实例失败");
        this.backendStatus = data;
        this.backendInstanceId = id;
        this.setMessage(`sing-box 实例已启动: ${id}`);
        await this.loadBackendEvents();
      } catch (err) { this.setMessage("启动实例失败: " + err, true); }
    },
    async backendInstanceStop(instanceId) {
      try {
        const id = String(instanceId || "default").trim() || "default";
        const resp = await fetch(`/api/backend/instances/${encodeURIComponent(id)}/stop`, { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "停止实例失败");
        this.backendStatus = data;
        this.backendInstanceId = id;
        this.setMessage(`sing-box 实例已停止: ${id}`);
        await this.loadBackendEvents();
      } catch (err) { this.setMessage("停止实例失败: " + err, true); }
    },
    async backendInstanceDelete(instanceId) {
      try {
        const id = String(instanceId || "default").trim() || "default";
        const resp = await fetch(`/api/backend/instances/${encodeURIComponent(id)}`, { method: "DELETE" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "删除实例失败");
        this.backendStatus = { ...this.backendStatus, instances: data.items || [] };
        if (this.backendInstanceId === id) this.backendInstanceId = "default";
        if (this.backendConfigInstanceId === id) this.backendConfigInstanceId = "default";
        this.setMessage(data.deleted ? `sing-box 实例已删除: ${id}` : `sing-box 实例不存在: ${id}`);
        await this.loadBackendEvents();
      } catch (err) { this.setMessage("删除实例失败: " + err, true); }
    },
    async onBackendInstanceCreate(instanceId = "") {
      const id = this.backendActionInstanceId(instanceId);
      await this.runWithButtonState(`backendInstanceCreate${typeof instanceId === "string" && instanceId ? `-${id}` : ""}`, () => this.createBackendInstance(id));
    },
    async onBackendInstanceStart(instanceId = "") {
      const id = this.backendActionInstanceId(instanceId);
      await this.runWithButtonState(`backendInstanceStart${typeof instanceId === "string" && instanceId ? `-${id}` : ""}`, () => this.backendInstanceStart(id));
    },
    async onBackendInstanceStop(instanceId = "") {
      const id = this.backendActionInstanceId(instanceId);
      await this.runWithButtonState(`backendInstanceStop${typeof instanceId === "string" && instanceId ? `-${id}` : ""}`, () => this.backendInstanceStop(id));
    },
    async onBackendInstanceDelete(instanceId = "") {
      const id = this.backendActionInstanceId(instanceId);
      await this.runWithButtonState(`backendInstanceDelete${typeof instanceId === "string" && instanceId ? `-${id}` : ""}`, () => this.backendInstanceDelete(id));
    },
    async onBackendStart() {
      await this.runWithButtonState("backendStart", () => this.backendStart());
    },
    async onBackendStop() {
      await this.runWithButtonState("backendStop", () => this.backendStop());
    },
    async onBackendRestart() {
      await this.runWithButtonState("backendRestart", () => this.backendRestart());
    },
    async onOpenBackendInstanceConfig(item) {
      const id = String(item?.instance_id || this.backendInstanceId || "default").trim() || "default";
      await this.runWithButtonState(`openBackendInstanceConfig-${id}`, () => this.openBackendInstanceConfig(item));
    },
    async openBackendInstanceConfig(item) {
      try {
        const id = String(item?.instance_id || this.backendInstanceId || "default").trim() || "default";
        const resp = await fetch(`/api/backend/instances/${encodeURIComponent(id)}/routes`);
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "加载实例配置失败");
        this.backendConfigInstanceId = id;
        this.backendInstanceId = id;
        this.routesJson = JSON.stringify(data.routes || [], null, 2);
        this.routeEntries = (data.routes || []).map(route => this.normalizeRouteItem(route));
        this.resetPage("routes");
        this.routeLatencyMap = {};
        this.setMessage(`已打开实例配置: ${id}`);
      } catch (err) { this.setMessage("打开实例配置失败: " + err, true); }
    },

    // --- Routes ---
    normalizeBackendPortRange(data = {}) {
      let start = Number.isFinite(Number(data.start)) ? Math.trunc(Number(data.start)) : 1081;
      let end = Number.isFinite(Number(data.end)) ? Math.trunc(Number(data.end)) : 1180;
      start = Math.max(1, Math.min(65535, start));
      end = Math.max(1, Math.min(65535, end));
      if (start > end) { const tmp = start; start = end; end = tmp; }
      return { start, end };
    },
    async loadBackendPortRange() {
      try {
        const resp = await fetch("/api/backend/default-port-range");
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "加载默认端口范围失败");
        this.backendPortRange = this.normalizeBackendPortRange(data || {});
      } catch (err) {
        this.backendPortRange = this.normalizeBackendPortRange(this.backendPortRange || {});
        this.setMessage("加载默认端口范围失败: " + err, true);
      }
    },
    async loadBackendDefaultListen() {
      try {
        const resp = await fetch("/api/backend/default-listen");
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "加载默认监听地址失败");
        this.backendDefaultListen = String(data.listen || "127.0.0.1").trim() || "127.0.0.1";
      } catch (err) {
        this.backendDefaultListen = this.backendDefaultListen || "127.0.0.1";
        this.setMessage("加载默认监听地址失败: " + err, true);
      }
    },
    async saveBackendDefaultListen() {
      try {
        const listen = String(this.backendDefaultListen || "").trim() || "127.0.0.1";
        const resp = await fetch("/api/backend/default-listen", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ listen }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "保存默认监听地址失败");
        this.backendDefaultListen = String(data.listen || listen).trim() || "127.0.0.1";
        this.setMessage(`默认监听地址已保存: ${this.backendDefaultListen}`);
      } catch (err) { this.setMessage("保存默认监听地址失败: " + err, true); }
    },
    async saveBackendPortRange() {
      try {
        const payload = this.normalizeBackendPortRange(this.backendPortRange || {});
        const resp = await fetch("/api/backend/default-port-range", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "保存默认端口范围失败");
        this.backendPortRange = this.normalizeBackendPortRange(data || payload);
        this.setMessage(`默认端口范围已保存: ${this.backendPortRange.start}-${this.backendPortRange.end}`);
      } catch (err) { this.setMessage("保存默认端口范围失败: " + err, true); }
    },
    async onSaveBackendDefaultListen() { await this.runWithButtonState("saveBackendDefaultListen", () => this.saveBackendDefaultListen()); },
    async onSaveBackendPortRange() { await this.runWithButtonState("saveBackendPortRange", () => this.saveBackendPortRange()); },
    nextAvailableInboundPort() {
      const range = this.normalizeBackendPortRange(this.backendPortRange || {});
      this.backendPortRange = range;
      const used = new Set((this.routeEntries || []).map(r => Number(r.inbound_port || 0)).filter(p => Number.isInteger(p) && p > 0));
      for (let port = range.start; port <= range.end; port++) {
        if (!used.has(port)) return port;
      }
      throw new Error(`默认端口范围已耗尽(${range.start}-${range.end}),请扩大范围或删除已有链路`);
    },
    normalizeRouteItem(item = {}) {
      const defaultPort = this.normalizeBackendPortRange(this.backendPortRange || {}).start;
      return {
        inbound_port: Number(item.inbound_port || defaultPort),
        inbound_type: item.inbound_type || "http",
        listen: item.listen || this.backendDefaultListen || "127.0.0.1",
        front_proxy_key: this.toDisplayProxyRef(item.front_proxy_key || ""),
        middle_proxy_key: this.toDisplayProxyRef(item.middle_proxy_key || ""),
        exit_proxy_key: this.toDisplayProxyRef(item.exit_proxy_key || item.proxy_key || ""),
      };
    },
    toDisplayProxyRef(raw) {
      const text = String(raw || "").trim();
      if (!text) return "";
      const m = text.match(/^#?(\d+)$/);
      if (m) return `#${Number(m[1])}`;
      const serial = this.getSerial(text);
      return serial !== "-" ? `#${serial}` : "";
    },
    resolveProxyRef(raw) {
      const text = String(raw || "").trim();
      if (!text) return "";
      const m = text.match(/^#?(\d+)$/);
      if (!m) return text;
      const serial = Number(m[1]);
      if (!Number.isInteger(serial) || serial <= 0 || serial > this.allProxies.length) throw new Error(`无效代理序号: ${text}`);
      const key = this.allProxies[serial - 1]?.normalized_key;
      if (!key) throw new Error(`序号未找到代理: ${text}`);
      return String(key);
    },
    normalizeSerialRef(raw) {
      const text = String(raw || "").trim();
      if (!text) return "";
      const m = text.match(/^#?(\d+)$/);
      return m ? `#${Number(m[1])}` : text;
    },
    persistRouteDefaults() {
      try {
        const payload = {
          front_proxy_key: this.normalizeSerialRef(this.routeDefaults.front_proxy_key),
          middle_proxy_key: this.normalizeSerialRef(this.routeDefaults.middle_proxy_key),
          exit_proxy_key: this.normalizeSerialRef(this.routeDefaults.exit_proxy_key),
        };
        this.routeDefaults = payload;
        localStorage.setItem("proxypool.routeDefaults.v1", JSON.stringify(payload));
      } catch {}
    },
    loadRouteDefaults() {
      try {
        const raw = localStorage.getItem("proxypool.routeDefaults.v1");
        if (!raw) return;
        const data = JSON.parse(raw);
        this.routeDefaults = {
          front_proxy_key: this.normalizeSerialRef(data?.front_proxy_key),
          middle_proxy_key: this.normalizeSerialRef(data?.middle_proxy_key),
          exit_proxy_key: this.normalizeSerialRef(data?.exit_proxy_key),
        };
      } catch {}
    },
    routePayloadFromEntries() {
      this.persistRouteDefaults();
      return (this.routeEntries || []).map(item => {
        const n = this.normalizeRouteItem(item);
        const frontKey = this.resolveProxyRef(n.front_proxy_key || this.routeDefaults.front_proxy_key || "");
        const middleKey = this.resolveProxyRef(n.middle_proxy_key || this.routeDefaults.middle_proxy_key || "");
        const exitKey = this.resolveProxyRef(n.exit_proxy_key || this.routeDefaults.exit_proxy_key || "");
        return {
          inbound_port: Number(n.inbound_port || 0),
          inbound_type: n.inbound_type || "http",
          listen: n.listen || "127.0.0.1",
          front_proxy_key: frontKey,
          middle_proxy_key: middleKey,
          exit_proxy_key: exitKey,
          proxy_key: exitKey,
        };
      });
    },
    addRouteEntry() {
      try {
        this.persistRouteDefaults();
        const port = this.nextAvailableInboundPort();
        this.routeEntries.push({
          inbound_port: port,
          inbound_type: "http",
          listen: this.backendDefaultListen || "127.0.0.1",
          front_proxy_key: this.routeDefaults.front_proxy_key || "",
          middle_proxy_key: this.routeDefaults.middle_proxy_key || "",
          exit_proxy_key: this.routeDefaults.exit_proxy_key || "",
        });
        this.routesJson = JSON.stringify(this.routePayloadFromEntries(), null, 2);
        this.clampAllPages();
      } catch (err) { this.setMessage("新增链路失败: " + err, true); }
    },
    removeRouteEntry(idx) {
      this.routeEntries.splice(idx, 1);
      this.routesJson = JSON.stringify(this.routePayloadFromEntries(), null, 2);
      this.clampAllPages();
    },
    async saveRouteEntries() {
      try {
        const routes = this.routePayloadFromEntries();
        const id = String(this.backendConfigInstanceId || "default").trim() || "default";
        const url = id === "default" ? "/api/backend/routes" : `/api/backend/instances/${encodeURIComponent(id)}/routes`;
        const resp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ routes, auto_restart: true }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "保存失败");
        if (id === "default") this.backendStatus = data;
        else await this.loadBackendStatus();
        this.routeEntries = (data.routes || []).map(item => this.normalizeRouteItem(item));
        this.resetPage("routes");
        this.routesJson = JSON.stringify(data.routes || [], null, 2);
        this.setMessage(`实例配置已保存: ${id}`);
        await this.checkRouteLatency();
      } catch (err) { this.setMessage("保存链式路由失败: " + err, true); }
    },
    async saveRoutes() {
      try {
        const routes = JSON.parse(this.routesJson || "[]");
        if (!Array.isArray(routes)) throw new Error("routes 必须是数组");
        const normalizedRoutes = routes.map(item => ({
          ...item,
          front_proxy_key: this.resolveProxyRef(item.front_proxy_key || ""),
          middle_proxy_key: this.resolveProxyRef(item.middle_proxy_key || ""),
          exit_proxy_key: this.resolveProxyRef(item.exit_proxy_key || item.proxy_key || ""),
          proxy_key: this.resolveProxyRef(item.exit_proxy_key || item.proxy_key || ""),
        }));
        const id = String(this.backendConfigInstanceId || "default").trim() || "default";
        const url = id === "default" ? "/api/backend/routes" : `/api/backend/instances/${encodeURIComponent(id)}/routes`;
        const resp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ routes: normalizedRoutes, auto_restart: true }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "保存失败");
        if (id === "default") this.backendStatus = data;
        this.routeEntries = (data.routes || []).map(item => this.normalizeRouteItem(item));
        this.resetPage("routes");
        this.setMessage(`路由已保存: ${id}`);
        await this.checkRouteLatency();
      } catch (err) { this.setMessage("保存路由失败: " + err, true); }
    },
    applyRoutesJsonToEntries() {
      try {
        const routes = JSON.parse(this.routesJson || "[]");
        if (!Array.isArray(routes)) throw new Error("JSON 顶层必须是数组");
        this.routeEntries = routes.map(item => this.normalizeRouteItem(item));
        this.resetPage("routes");
        this.setMessage("JSON 已应用到链路表单");
      } catch (err) { this.setMessage("应用JSON失败: " + err, true); }
    },
    formatRouteLatency(routeIndex) {
      const item = this.routeLatencyMap[String(routeIndex)];
      if (!item) return "-";
      if (item.available && Number.isFinite(item.latency_ms)) return `${item.latency_ms} ms`;
      if (item.error) return `DOWN (${item.error})`;
      return "DOWN";
    },
    async checkRouteLatency() {
      try {
        const resp = await fetch("/api/backend/latency?timeout_sec=12");
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "检测失败");
        const map = {};
        (data.items || []).forEach(item => {
          const idx = Number(item.route_index);
          if (Number.isFinite(idx) && idx >= 0) map[String(idx)] = item;
        });
        this.routeLatencyMap = map;
        this.setMessage("链路延迟检测完成");
      } catch (err) { this.setMessage("链路延迟检测失败: " + err, true); }
    },
    async onAddRouteEntry() { await this.runWithButtonState("addRouteEntry", () => this.addRouteEntry()); },
    async onRemoveRouteEntry(idx) { await this.runWithButtonState(`removeRouteEntry-${idx}`, () => this.removeRouteEntry(idx)); },
    async onSaveRouteEntries() { await this.runWithButtonState("saveRouteEntries", () => this.saveRouteEntries()); },
    async onCheckRouteLatency() { await this.runWithButtonState("checkRouteLatency", () => this.checkRouteLatency()); },
    async onApplyRoutesJsonToEntries() { await this.runWithButtonState("applyRoutesJsonToEntries", () => this.applyRoutesJsonToEntries()); },
    async onSaveRoutes() { await this.runWithButtonState("saveRoutes", () => this.saveRoutes()); },

    // --- Route Defaults & Geo Fill ---
    loadTestFallback() {
      try {
        const raw = localStorage.getItem("proxypool.testFallback.v1");
        if (!raw) return;
        const data = JSON.parse(raw) || {};
        this.testFallback = {
          front_proxy_refs: String(data.front_proxy_refs || "").trim(),
          max_attempts: Math.max(0, Math.min(100, Math.trunc(Number(data.max_attempts || 0)))),
        };
      } catch {}
    },
    loadTestRunFilter() {
      try {
        const raw = localStorage.getItem("proxypool.testRunFilter.v1");
        this.testRunFilter = raw ? this.normalizeTestRunFilter(JSON.parse(raw) || {}) : this.normalizeTestRunFilter(this.testRunFilter);
      } catch { this.testRunFilter = this.normalizeTestRunFilter(this.testRunFilter); }
    },
    normalizeTestRunFilter(data = {}) {
      const statusRaw = String(data.status || "all").trim();
      const status = ["all", "down", "up", "unchecked"].includes(statusRaw) ? statusRaw : "all";
      const n = Number(data.min_retest_days);
      return {
        status,
        min_retest_days: Number.isFinite(n) ? Math.max(0, Math.min(365, Math.round(n * 10) / 10)) : 0,
        replace_failed_with_available: data.replace_failed_with_available === true,
      };
    },
    async saveTestRunFilter() {
      const payload = this.normalizeTestRunFilter(this.testRunFilter);
      this.testRunFilter = payload;
      try { localStorage.setItem("proxypool.testRunFilter.v1", JSON.stringify(payload)); } catch {}
      const statusLabelMap = { all: "全部", down: "仅不可用", up: "仅可用", unchecked: "仅未测速" };
      this.setMessage(`测速筛选已保存: 状态=${statusLabelMap[payload.status] || "全部"}, 复测间隔>=${payload.min_retest_days}天, 失败替换=${payload.replace_failed_with_available ? "开启" : "关闭"}`);
    },
    sanitizeTaskConcurrencyValue(value, fallback = 30) {
      const n = Number(value);
      return Number.isFinite(n) ? Math.max(1, Math.min(500, Math.trunc(n))) : Math.max(1, Math.min(500, Math.trunc(Number(fallback) || 30)));
    },
    normalizeTaskConcurrency(data = {}) {
      return {
        tester: this.sanitizeTaskConcurrencyValue(data.tester, 60),
        openai: this.sanitizeTaskConcurrencyValue(data.openai, 30),
        geoip: this.sanitizeTaskConcurrencyValue(data.geoip, 30),
        ip_purity: this.sanitizeTaskConcurrencyValue(data.ip_purity, 30),
      };
    },
    loadTaskConcurrency() {
      try {
        const raw = localStorage.getItem("proxypool.taskConcurrency.v1");
        this.taskConcurrency = raw ? this.normalizeTaskConcurrency(JSON.parse(raw) || {}) : this.normalizeTaskConcurrency(this.taskConcurrency);
      } catch { this.taskConcurrency = this.normalizeTaskConcurrency(this.taskConcurrency); }
    },
    async saveTaskConcurrency() {
      const payload = this.normalizeTaskConcurrency(this.taskConcurrency);
      this.taskConcurrency = payload;
      try { localStorage.setItem("proxypool.taskConcurrency.v1", JSON.stringify(payload)); } catch {}
      this.setMessage(`并发设置已保存: 测速${payload.tester}, 解锁${payload.openai}, Geo${payload.geoip}, 纯净度${payload.ip_purity}`);
    },
    async saveTestFallback() {
      try {
        const payload = {
          front_proxy_refs: String(this.testFallback.front_proxy_refs || "").trim(),
          max_attempts: Math.max(0, Math.min(100, Math.trunc(Number(this.testFallback.max_attempts || 0)))),
        };
        const refs = this.resolveFallbackFrontProxyKeys(payload.front_proxy_refs);
        this.testFallback = payload;
        try { localStorage.setItem("proxypool.testFallback.v1", JSON.stringify(payload)); } catch {}
        this.setMessage(`测速回退配置已保存: 前置代理${refs.length}个, 最多尝试${payload.max_attempts}次`);
      } catch (err) { this.setMessage("保存测速回退配置失败: " + err, true); }
    },
    resolveFallbackFrontProxyKeys(rawText) {
      const text = String(rawText || "").trim();
      if (!text) return [];
      const parts = text.split(/[,\s\n\r;|]+/g).map(item => item.trim()).filter(Boolean);
      const keys = [];
      const seen = new Set();
      for (const token of parts) {
        const key = this.resolveProxyRef(token);
        if (!key || seen.has(key)) continue;
        seen.add(key);
        keys.push(key);
      }
      return keys;
    },
    applyRouteDefaultValue(currentValue, defaultValue, applyAll = false) {
      if (!defaultValue) return currentValue;
      return applyAll ? defaultValue : (currentValue ? currentValue : defaultValue);
    },
    applyDefaultsToRoutes(applyAll = false) {
      this.persistRouteDefaults();
      const defaults = { ...this.routeDefaults };
      this.routeEntries = (this.routeEntries || []).map(item => {
        const n = this.normalizeRouteItem(item);
        return {
          ...n,
          front_proxy_key: this.applyRouteDefaultValue(n.front_proxy_key, defaults.front_proxy_key, applyAll),
          middle_proxy_key: this.applyRouteDefaultValue(n.middle_proxy_key, defaults.middle_proxy_key, applyAll),
          exit_proxy_key: this.applyRouteDefaultValue(n.exit_proxy_key, defaults.exit_proxy_key, applyAll),
        };
      });
      this.routesJson = JSON.stringify(this.routePayloadFromEntries(), null, 2);
      this.clampAllPages();
      this.setMessage(applyAll ? "默认代理已应用到全部链路" : "默认代理已应用到空白链路");
    },
    clearRouteDefaults() {
      this.routeDefaults = { front_proxy_key: "", middle_proxy_key: "", exit_proxy_key: "" };
      try { localStorage.removeItem("proxypool.routeDefaults.v1"); } catch {}
      this.setMessage("默认代理已清空");
    },
    async onApplyDefaultsToEmptyRoutes() { await this.runWithButtonState("applyDefaultsEmpty", () => this.applyDefaultsToRoutes(false)); },
    async onApplyDefaultsToAllRoutes() { await this.runWithButtonState("applyDefaultsAll", () => this.applyDefaultsToRoutes(true)); },
    async onClearRouteDefaults() { await this.runWithButtonState("clearRouteDefaults", () => this.clearRouteDefaults()); },
    async onSaveTestFallback() { await this.runWithButtonState("saveTestFallback", () => this.saveTestFallback()); },
    async onSaveTestRunFilter() { await this.runWithButtonState("saveTestRunFilter", () => this.saveTestRunFilter()); },
    async onSaveTaskConcurrency() { await this.runWithButtonState("saveTaskConcurrency", () => this.saveTaskConcurrency()); },

    // --- Geo Fill ---
    getProxyRefsByGeoLocation(geoLocation) {
      const target = String(geoLocation || "").trim();
      if (!target) return [];
      const refs = [];
      for (const item of this.allProxies || []) {
        if (this.formatGeo(item) !== target) continue;
        const serial = this.getSerial(item.normalized_key);
        if (serial !== "-") refs.push(`#${serial}`);
      }
      return refs;
    },
    getProxyRefsByOpenaiStatus(openaiStatus) {
      const target = String(openaiStatus || "").trim();
      if (!target) return [];
      const refs = [];
      for (const item of this.allProxies || []) {
        const unlocked = item?.openai_unlocked;
        const matched = (target === "unlocked" && unlocked === true) ||
          (target === "blocked" && unlocked === false) ||
          (target === "unchecked" && (unlocked === null || unlocked === undefined));
        if (matched) {
          const serial = this.getSerial(item.normalized_key);
          if (serial !== "-") refs.push(`#${serial}`);
        }
      }
      return refs;
    },
    getProxyRefsByIpPurityLevel(ipPurityLevel) {
      const target = String(ipPurityLevel || "").trim();
      if (!target) return [];
      const levelMap = { residential: "家宽", non_residential: "非家宽", unknown: "未知" };
      const targetLevel = levelMap[target] || target;
      const refs = [];
      for (const item of this.allProxies || []) {
        if (String(item?.ip_purity_level || "").trim() !== targetLevel) continue;
        const serial = this.getSerial(item.normalized_key);
        if (serial !== "-") refs.push(`#${serial}`);
      }
      return refs;
    },
    proxyMatchesRouteFillFilters(item) {
      const geoLocation = String(this.routeGeoFill.geo_location || "").trim();
      const openaiStatus = String(this.routeGeoFill.openai_status || "").trim();
      const ipPurityLevel = String(this.routeGeoFill.ip_purity_level || "").trim();
      if (geoLocation && this.formatGeo(item) !== geoLocation) return false;
      if (openaiStatus) {
        const unlocked = item?.openai_unlocked;
        const matched = (openaiStatus === "unlocked" && unlocked === true) ||
          (openaiStatus === "blocked" && unlocked === false) ||
          (openaiStatus === "unchecked" && (unlocked === null || unlocked === undefined));
        if (!matched) return false;
      }
      if (ipPurityLevel) {
        const levelMap = { residential: "家宽", non_residential: "非家宽", unknown: "未知" };
        const targetLevel = levelMap[ipPurityLevel] || ipPurityLevel;
        if (String(item?.ip_purity_level || "").trim() !== targetLevel) return false;
      }
      return Boolean(geoLocation || openaiStatus || ipPurityLevel);
    },
    getRouteFillFilterLabels() {
      const labels = [];
      const geoLocation = String(this.routeGeoFill.geo_location || "").trim();
      const openaiStatus = String(this.routeGeoFill.openai_status || "").trim();
      const ipPurityLevel = String(this.routeGeoFill.ip_purity_level || "").trim();
      if (geoLocation) labels.push(geoLocation);
      if (openaiStatus === "unlocked") labels.push("ChatGPT已解锁");
      if (openaiStatus === "blocked") labels.push("ChatGPT未解锁");
      if (openaiStatus === "unchecked") labels.push("ChatGPT未检测");
      if (ipPurityLevel === "residential") labels.push("IP纯净度家宽");
      if (ipPurityLevel === "non_residential") labels.push("IP纯净度非家宽");
      if (ipPurityLevel === "unknown") labels.push("IP纯净度未知");
      return labels;
    },
    getProxyRefsByFillRule() {
      const refs = [];
      for (const item of this.allProxies || []) {
        if (!this.proxyMatchesRouteFillFilters(item)) continue;
        const serial = this.getSerial(item.normalized_key);
        if (serial !== "-") refs.push(`#${serial}`);
      }
      return refs;
    },
    getRouteFillRuleLabel() { return this.getRouteFillFilterLabels().join(" + "); },
    routeColumnLabel(field) {
      if (field === "front_proxy_key") return "前置代理列";
      if (field === "middle_proxy_key") return "中间代理列";
      return "后置(落地)列";
    },
    fillRouteColumnByGeo() {
      const label = this.getRouteFillRuleLabel();
      const field = String(this.routeGeoFill.target_column || "").trim();
      if (!label) { this.setMessage("请先选择填充条件", true); return; }
      if (!["front_proxy_key", "middle_proxy_key", "exit_proxy_key"].includes(field)) { this.setMessage("目标链路列无效", true); return; }
      const refs = this.getProxyRefsByFillRule();
      if (!refs.length) { this.setMessage(`未找到满足条件 ${label} 的代理`, true); return; }
      if (!(this.routeEntries || []).length) { this.setMessage('当前没有链路，请先新增链路或使用「按地区生成新链路」', true); return; }
      let applied = 0;
      this.routeEntries = (this.routeEntries || []).map((item, idx) => {
        const n = this.normalizeRouteItem(item);
        if (idx >= refs.length) return n;
        applied++;
        return { ...n, [field]: refs[idx] };
      });
      this.routesJson = JSON.stringify(this.routePayloadFromEntries(), null, 2);
      this.clampAllPages();
      this.setMessage(`已按条件 ${label} 顺序填充 ${applied} 条到${this.routeColumnLabel(field)}`);
    },
    generateRoutesByGeo() {
      const label = this.getRouteFillRuleLabel();
      const field = String(this.routeGeoFill.target_column || "").trim();
      if (!label) { this.setMessage("请先选择填充条件", true); return; }
      if (!["front_proxy_key", "middle_proxy_key", "exit_proxy_key"].includes(field)) { this.setMessage("目标链路列无效", true); return; }
      const refs = this.getProxyRefsByFillRule();
      if (!refs.length) { this.setMessage(`未找到满足条件 ${label} 的代理`, true); return; }
      this.persistRouteDefaults();
      let created = 0;
      for (const ref of refs) {
        let inboundPort = 0;
        try { inboundPort = this.nextAvailableInboundPort(); }
        catch (err) {
          this.routesJson = JSON.stringify(this.routePayloadFromEntries(), null, 2);
          this.clampAllPages();
          this.setMessage(created > 0 ? `已生成 ${created} 条链路,后续失败: ${err}` : String(err), true);
          return;
        }
        const entry = {
          inbound_port: inboundPort,
          inbound_type: "http",
          listen: this.backendDefaultListen || "127.0.0.1",
          front_proxy_key: this.routeDefaults.front_proxy_key || "",
          middle_proxy_key: this.routeDefaults.middle_proxy_key || "",
          exit_proxy_key: this.routeDefaults.exit_proxy_key || "",
        };
        entry[field] = ref;
        this.routeEntries.push(entry);
        created++;
      }
      this.routesJson = JSON.stringify(this.routePayloadFromEntries(), null, 2);
      this.clampAllPages();
      this.setMessage(`已按条件 ${label} 生成 ${created} 条新链路到${this.routeColumnLabel(field)}`);
    },
    async onFillRouteColumnByGeo() { await this.runWithButtonState("fillRouteByGeo", () => this.fillRouteColumnByGeo()); },
    async onGenerateRoutesByGeo() { await this.runWithButtonState("genRouteByGeo", () => this.generateRoutesByGeo()); },

    // --- Tasks ---
    async onRefreshTasks() { await this.runWithButtonState("refreshTasks", () => this.refreshTaskList({ force: true })); },
    shortTaskId(taskId) {
      const text = String(taskId || "");
      return text ? text.slice(0, 8) : "-";
    },
    taskLabel(kind) {
      const map = {
        tester_run: "测速任务", geoip_enrich: "IP位置补全",
        ip_purity_enrich: "IP纯净度检测", openai_check: "ChatGPT解锁检测",
        subscriptions_refresh: "订阅刷新任务", auto_subscriptions_refresh: "自动订阅刷新",
        speed_test: "网速测试", auto_speed_test: "自动网速测试",
        auto_tester_run: "自动测速任务",
      };
      return map[String(kind || "")] || kind || "任务";
    },
    taskStatusText(status) {
      const map = { queued: "排队中", running: "运行中", success: "成功", failed: "失败", cancelled: "已停止" };
      return map[String(status || "")] || status || "-";
    },
    taskMessageText(task) {
      const message = String(task?.message || "").trim();
      const error = String(task?.error || "").trim();
      const map = {
        queued: "等待执行",
        running: "执行中",
        success: "完成",
        failed: "失败",
        cancelled: "已停止",
        "cancel requested": "正在停止",
      };
      if (message && map[message]) return map[message];
      if (message && message !== String(task?.status || "")) return message;
      if (error) return error.split("\n")[0].slice(0, 120);
      return map[String(task?.status || "")] || "-";
    },
    taskStatusClass(status) {
      const map = {
        success: "badge-success", failed: "badge-danger", cancelled: "badge-warning",
        running: "badge-neutral", queued: "badge-warning",
      };
      return map[String(status || "")] || "badge-neutral";
    },
    isTaskStoppable(task) { return ["queued", "running"].includes(String(task?.status || "")); },
    isTaskDeletable(task) { return ["success", "failed", "cancelled"].includes(String(task?.status || "")); },
    async stopTask(task) {
      const taskId = String(task?.task_id || "");
      if (!taskId) return;
      try {
        const resp = await fetch(`/api/tasks/${taskId}/stop`, { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "停止任务失败");
        this.setMessage(data.stopped ? `任务已请求停止: ${this.shortTaskId(taskId)}` : `任务已结束或不可停止: ${this.shortTaskId(taskId)}`);
        await this.refreshTaskList({ force: true });
      } catch (err) { this.setMessage("停止任务失败: " + err, true); }
    },
    async onDeleteTask(task) {
      const taskId = String(task?.task_id || "");
      if (!taskId) return;
      try {
        const resp = await fetch(`/api/tasks/${taskId}`, { method: "DELETE" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "删除任务失败");
        this.setMessage(data.deleted ? `任务已删除: ${this.shortTaskId(taskId)}` : `任务未删除(仅可删除已完成任务): ${this.shortTaskId(taskId)}`, !data.deleted);
        await this.refreshTaskList({ force: true });
      } catch (err) { this.setMessage("删除任务失败: " + err, true); }
    },
    async onStopTask(task) { await this.runWithButtonState(`stopTask-${task.task_id}`, () => this.stopTask(task)); },
    async onDeleteTaskBtn(task) { await this.runWithButtonState(`deleteTask-${task.task_id}`, () => this.onDeleteTask(task)); },
    normalizeAutoTaskConfig(data = {}) {
      return {
        enabled: data.enabled === true,
        subscription_refresh_enabled: data.subscription_refresh_enabled !== false,
        subscription_refresh_minutes: Math.max(1, Math.min(10080, Math.trunc(Number(data.subscription_refresh_minutes || 60)))),
        tester_enabled: data.tester_enabled === true,
        tester_minutes: Math.max(1, Math.min(10080, Math.trunc(Number(data.tester_minutes || 60)))),
        tester_limit: Math.max(0, Math.min(20000, Math.trunc(Number(data.tester_limit || 0)))),
        tester_concurrency: this.sanitizeTaskConcurrencyValue(data.tester_concurrency, 50),
        speed_test_enabled: data.speed_test_enabled === true,
        speed_test_minutes: Math.max(1, Math.min(10080, Math.trunc(Number(data.speed_test_minutes || 120)))),
        speed_test_url: String(data.speed_test_url || "https://speed.cloudflare.com/__down?bytes=10000000").trim(),
        speed_test_limit: Math.max(0, Math.min(20000, Math.trunc(Number(data.speed_test_limit || 0)))),
        speed_test_timeout_sec: Math.max(3, Math.min(300, Number(data.speed_test_timeout_sec || 30))),
      };
    },
    async loadAutoTaskConfig() {
      const resp = await fetch("/api/tasks/auto-config");
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "加载自动任务配置失败");
      this.autoTaskConfig = this.normalizeAutoTaskConfig(data.item || {});
      this.autoTaskStatus = data;
    },
    async saveAutoTaskConfig() {
      const payload = this.normalizeAutoTaskConfig(this.autoTaskConfig);
      if (payload.speed_test_enabled && !/^https?:\/\//.test(payload.speed_test_url)) throw new Error("网速测试 URL 必须以 http:// 或 https:// 开头");
      const resp = await fetch("/api/tasks/auto-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "保存自动任务配置失败");
      this.autoTaskConfig = this.normalizeAutoTaskConfig(data.item || {});
      this.autoTaskStatus = data;
      this.setMessage(this.autoTaskConfig.enabled ? "自动任务已启用" : "自动任务已停用");
    },
    async onLoadAutoTaskConfig() { await this.runWithButtonState("loadAutoTaskConfig", () => this.loadAutoTaskConfig()); },
    async onSaveAutoTaskConfig() { await this.runWithButtonState("saveAutoTaskConfig", () => this.saveAutoTaskConfig()); },
    async refreshTaskList({ force = false } = {}) {
      if (this.taskListLoading && !force) return;
      this.taskListLoading = true;
      try {
        const prevHasRunning = (this.taskItems || []).some(t => ["queued", "running"].includes(String(t.status || "")));
        const resp = await fetch("/api/tasks?limit=80");
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "任务列表加载失败");
        const items = Array.isArray(data.items) ? data.items : [];
        this.taskItems = items;
        const hasRunning = items.some(t => ["queued", "running"].includes(String(t.status || "")));
        if ((this.pendingTaskResultRefresh || prevHasRunning) && !hasRunning) {
          this.pendingTaskResultRefresh = false;
          await this.loadData();
          await this.loadProxyCatalog();
          await this.loadSubscriptions();
        }
      } catch (err) { if (force) this.setMessage("刷新任务失败: " + err, true); }
      finally { this.taskListLoading = false; }
    },
    startTaskPolling() {
      if (this.taskPollingTimer) return;
      this.taskPollingTimer = setInterval(() => { this.refreshTaskList(); }, 1200);
    },
    stopTaskPolling() {
      if (!this.taskPollingTimer) return;
      clearInterval(this.taskPollingTimer);
      this.taskPollingTimer = null;
    },
    async startProgressTask(url, payload, label) {
      try {
        const startResp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const startData = await startResp.json();
        if (!startResp.ok) throw new Error(startData.detail || "任务创建失败");
        this.pendingTaskResultRefresh = true;
        this.setMessage(`${label}已启动: ${this.shortTaskId(startData.task_id)}`);
        await this.refreshTaskList({ force: true });
      } catch (err) { throw err; }
    },

    // --- Proxy Actions ---
    async onRunTest() { await this.runWithButtonState("runTest", () => this.runTest()); },
    async runTest() {
      try {
        const fallbackKeys = this.resolveFallbackFrontProxyKeys(this.testFallback.front_proxy_refs);
        const maxAttempts = Math.max(0, Math.min(100, Math.trunc(Number(this.testFallback.max_attempts || 0))));
        const concurrency = this.sanitizeTaskConcurrencyValue(this.taskConcurrency.tester, 60);
        const testFilter = this.normalizeTestRunFilter(this.testRunFilter);
        this.testRunFilter = testFilter;
        try { localStorage.setItem("proxypool.testRunFilter.v1", JSON.stringify(testFilter)); } catch {}
        const onlyAvailable = testFilter.status === "up";
        const onlyUnavailable = testFilter.status === "down";
        const onlyUnchecked = testFilter.status === "unchecked";
        const minLastCheckedAgeHours = Math.max(0, Math.trunc(Number(testFilter.min_retest_days || 0) * 24));
        await this.startProgressTask("/api/tasks/tester/start", {
          limit: 0, concurrency, only_unchecked: onlyUnchecked,
          only_available: onlyAvailable, only_unavailable: onlyUnavailable,
          min_last_checked_age_hours: minLastCheckedAgeHours,
          fallback_front_proxy_keys: fallbackKeys,
          fallback_front_max_attempts: maxAttempts,
          replace_failed_with_available: testFilter.replace_failed_with_available === true,
        }, "测速任务");
      } catch (err) { this.setMessage("测速失败: " + err, true); }
    },
    async onRunSpeedTest() { await this.runWithButtonState("runSpeedTest", () => this.runSpeedTest()); },
    async runSpeedTest() {
      try {
        const payload = {
          url: String(this.speedTestForm.url || "").trim(),
          limit: Math.max(0, Math.min(20000, Math.trunc(Number(this.speedTestForm.limit || 0)))),
          timeout_sec: Math.max(3, Math.min(300, Number(this.speedTestForm.timeout_sec || 30))),
          only_available: this.speedTestForm.only_direct === true,
          only_direct: this.speedTestForm.only_direct === true,
        };
        if (!/^https?:\/\//.test(payload.url)) throw new Error("测速文件地址必须以 http:// 或 https:// 开头");
        this.speedTestForm = payload;
        await this.startProgressTask("/api/tasks/speed-test/start", payload, "网速测试任务");
      } catch (err) { this.setMessage("网速测试失败: " + err, true); }
    },
    async onTestSingleProxy(item) {
      await this.runWithButtonState(`testProxy-${item.normalized_key}`, async () => {
        try {
          const normalizedKey = String(item?.normalized_key || "").trim();
          if (!normalizedKey) throw new Error("节点标识缺失");
          const fallbackKeys = this.resolveFallbackFrontProxyKeys(this.testFallback.front_proxy_refs);
          const maxAttempts = Math.max(0, Math.min(100, Math.trunc(Number(this.testFallback.max_attempts || 0))));
          const resp = await fetch("/api/tester/run-one", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              normalized_key: normalizedKey,
              fallback_front_proxy_keys: fallbackKeys,
              fallback_front_max_attempts: maxAttempts,
            }),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "单节点测试失败");
          const latency = Number.isFinite(Number(data.latency_ms)) ? `${Number(data.latency_ms)} ms` : "-";
          this.setMessage(`单节点测试完成: #${this.getSerial(normalizedKey)} ${data.available ? "UP" : "DOWN"} ${latency}`);
          await this.loadData();
          await this.loadProxyCatalog();
        } catch (err) { this.setMessage("单节点测试失败: " + err, true); }
      });
    },
    async onRunUnlockCheck() { await this.runWithButtonState("runUnlockCheck", () => this.runUnlockCheck()); },
    async runUnlockCheck() {
      try {
        const concurrency = this.sanitizeTaskConcurrencyValue(this.taskConcurrency.openai, 30);
        await this.startProgressTask("/api/tasks/openai-check/start", {
          limit: 0, concurrency, only_unchecked: false, only_available: true,
        }, "ChatGPT解锁检测任务");
      } catch (err) { this.setMessage("检测失败: " + err, true); }
    },
    async onEnrichGeo() { await this.runWithButtonState("enrichGeo", () => this.enrichGeo()); },
    async enrichGeo() {
      try {
        const concurrency = this.sanitizeTaskConcurrencyValue(this.taskConcurrency.geoip, 30);
        await this.startProgressTask("/api/tasks/geoip/start", { limit: 0, concurrency }, "IP位置补全任务");
      } catch (err) { this.setMessage("补全失败: " + err, true); }
    },
    async onRunIpPurity() { await this.runWithButtonState("runIpPurity", () => this.runIpPurity()); },
    async runIpPurity() {
      try {
        const concurrency = this.sanitizeTaskConcurrencyValue(this.taskConcurrency.ip_purity, 30);
        await this.startProgressTask("/api/tasks/ip-purity/start", { limit: 0, concurrency }, "IP纯净度检测任务");
      } catch (err) { this.setMessage("IP纯净度检测失败: " + err, true); }
    },
    async onDeleteUnavailable() { await this.runWithButtonState("deleteUnavailable", () => this.deleteUnavailable()); },
    async deleteUnavailable() {
      try {
        const resp = await fetch("/api/proxies/delete-unavailable", { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "删除失败");
        this.setMessage(`删除不可用节点完成: deleted=${data.deleted || 0}`);
        await this.loadData();
        await this.loadProxyCatalog();
      } catch (err) { this.setMessage("删除不可用节点失败: " + err, true); }
    },
    async onCopySubscription() { await this.runWithButtonState("copySubscription", () => this.copySubscription()); },
    async copySubscription() {
      try {
        const text = await (await fetch("/api/subscription?only_available=true")).text();
        await this.copyTextToClipboard(text);
        this.setMessage("订阅已复制到剪贴板");
      } catch (err) { this.setMessage("复制失败: " + err, true); }
    },

    // --- Clipboard ---
    async copyTextToClipboard(text) {
      const value = String(text || "");
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        await navigator.clipboard.writeText(value);
        return;
      }
      this.fallbackCopyTextToClipboard(value);
    },
    fallbackCopyTextToClipboard(text) {
      const textarea = document.createElement("textarea");
      textarea.value = String(text || "");
      textarea.setAttribute("readonly", "readonly");
      textarea.style.cssText = "position:fixed;left:-9999px;top:0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      try { document.execCommand("copy"); }
      finally { document.body.removeChild(textarea); }
    },
    proxyRawLink(item) { return String(item?.raw_link || "").trim(); },
    async copyProxyLink(item) {
      try {
        const link = this.proxyRawLink(item);
        if (!link) throw new Error("节点链接为空");
        await this.copyTextToClipboard(link);
        this.setMessage(`节点链接已复制: #${this.getSerial(item.normalized_key)}`);
      } catch (err) { this.setMessage("复制节点链接失败: " + err, true); }
    },
    async onCopyProxyLink(item) {
      await this.runWithButtonState(`copyProxyLink-${item.normalized_key}`, () => this.copyProxyLink(item));
    },
    async copySelectedProxyLinks() {
      try {
        const items = this.selectedProxyItems();
        const links = items.map(item => this.proxyRawLink(item)).filter(Boolean);
        if (!links.length) throw new Error("未选择可复制链接的节点");
        await this.copyTextToClipboard(links.join("\n"));
        this.setMessage(`已复制 ${links.length} 条节点链接`);
      } catch (err) { this.setMessage("批量复制节点链接失败: " + err, true); }
    },
    async onCopySelectedProxyLinks() {
      await this.runWithButtonState("copySelectedProxyLinks", () => this.copySelectedProxyLinks());
    },
    async deleteSelectedProxies() {
      try {
        const keys = (this.selectedProxyKeys || []).map(key => String(key || "").trim()).filter(Boolean);
        if (!keys.length) throw new Error("未选择节点");
        const resp = await fetch("/api/proxies/delete-selected", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ normalized_keys: keys }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "删除选中节点失败");
        this.selectedProxyKeys = [];
        this.setMessage(`已删除 ${data.deleted || 0} 个选中节点`);
        await this.loadData();
        await this.loadProxyCatalog();
      } catch (err) { this.setMessage("删除选中节点失败: " + err, true); }
    },
    async onDeleteSelectedProxies() {
      await this.runWithButtonState("deleteSelectedProxies", () => this.deleteSelectedProxies());
    },

    // --- Formatting Helpers ---
    formatTime(ts) {
      if (!ts) return "-";
      try { return new Date(ts).toLocaleString(); }
      catch { return ts; }
    },
    formatBackendPid(pid) {
      const n = Number(pid);
      if (!Number.isFinite(n) || n <= -1) return "-1";
      return String(Math.trunc(n));
    },
    shortPath(path) {
      const text = String(path || "").trim();
      if (!text) return "-";
      const parts = text.split("/");
      return parts.length <= 3 ? text : "..." + parts.slice(-3).join("/");
    },
    shortSubscriptionUrl(url) {
      const text = String(url || "").trim();
      if (!text) return "-";
      return text.length <= 64 ? text : text.slice(0, 61) + "...";
    },
    shortSource(src) {
      const text = String(src || "").trim();
      if (!text) return "-";
      if (text.startsWith("subscription#")) return text.split("|", 1)[0];
      if (text.startsWith("upload:")) return text;
      return text.split("/").slice(-1)[0];
    },
    formatGeo(item) {
      const c = item.country || "";
      const city = item.city || "";
      return (!c && !city) ? "-" : `${c || "-"}:${city || "-"}`;
    },
    formatIpPurity(item) {
      const level = String(item.ip_purity_level || "").trim();
      const score = item.ip_purity_score;
      const hasScore = Number.isFinite(Number(score));
      if (level === "家宽" || level === "非家宽" || level === "未知") return level;
      if (level && hasScore) return `${level} (${Number(score).toFixed(2)}%)`;
      if (level) return level;
      if (hasScore) return `${Number(score).toFixed(2)}%`;
      return "-";
    },
    formatUnlock(item) {
      if (item.openai_unlocked === true) return "已解锁";
      if (item.openai_unlocked === false) return "未解锁";
      return "未检测";
    },
    formatBandwidthMbps(item) {
      if (item?.speed_mbps === null || item?.speed_mbps === undefined || item?.speed_mbps === "") return "-";
      const value = Number(item.speed_mbps);
      if (!Number.isFinite(value) || value < 0) return "-";
      return value >= 100 ? value.toFixed(0) : value.toFixed(2);
    },
    formatFallbackFront(item) {
      const arr = Array.isArray(item?.fallback_front_keys) ? item.fallback_front_keys : [];
      if (!arr.length) return "-";
      const labels = [];
      for (const key of arr) {
        const serial = this.getSerial(key);
        if (serial !== "-") labels.push(`#${serial}`);
      }
      return labels.length ? labels.join(",") : "-";
    },
    formatGatewayNode(node) {
      if (!node) return "-";
      const name = String(node.name || "").trim() || `${node.host || "-"}:${node.port || "-"}`;
      const serial = this.getSerial(node.key);
      return serial !== "-" ? `#${serial} ${name}` : name;
    },
    formatGatewayNodeMeta(node) {
      if (!node) return "-";
      const parts = [];
      if (node.protocol) parts.push(String(node.protocol).toUpperCase());
      if (node.country || node.city) parts.push(`${node.country || "-"}:${node.city || "-"}`);
      if (node.latency_ms !== null && node.latency_ms !== undefined) parts.push(`${node.latency_ms} ms`);
      if (node.resolved_ip) parts.push(node.resolved_ip);
      return parts.length ? parts.join(" / ") : "-";
    },
    gatewayStatusBadgeClass(ok) {
      return ok ? "badge-success" : "badge-danger";
    },
    getSerial(normalizedKey) {
      return this.proxySerialMap[String(normalizedKey || "")] || "-";
    },

    // --- Proxy Config Dialog ---
    async applyProxyConfig() {
      await this.onLoadDataClick();
      this.proxyConfigDialogVisible = false;
    },
  },

  async mounted() {
    this.loadProxyColumns();
    this.loadRouteDefaults();
    this.loadTestFallback();
    this.loadTestRunFilter();
    this.loadTaskConcurrency();
    await this.loadAutoTaskConfig();
    await this.loadBackendPortRange();
    await this.loadBackendDefaultListen();
    await this.refreshTaskList({ force: true });
    this.startTaskPolling();
    await this.loadData();
    await this.loadProxyCatalog();
    await this.loadSubscriptions();
    await this.loadPublishedSubscriptions();
    await this.loadSubscriptionUpdateProxy();
    await this.loadProxyPools();
    await this.loadGatewayEndpoints();
    await this.loadBackendStatus();
    await this.loadGatewayConfig();
    await this.loadGatewayStatus();
  },

  unmounted() { this.stopTaskPolling(); },
};
