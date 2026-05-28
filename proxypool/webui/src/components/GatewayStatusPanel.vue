<template>
  <div v-show="proxyPoolTab === 'gateway-status'" class="tab-panel fade-in">
    <div class="section-header">
      <div>
        <h3 class="section-divider">网关状态</h3>
        <p class="form-hint">端点按代理池顺序选择健康节点；单个节点或单条组合失败时会临时避开，直到候选组合耗尽才视为不可用。</p>
      </div>
      <div class="btn-group">
        <select v-model.number="gatewayStatusEndpointId" @change="onGatewayStatusEndpointChanged" class="select input-sm" style="min-width: 220px;">
          <option :value="0" disabled>选择端点</option>
          <option v-for="item in gatewayEndpoints" :key="'gateway-status-ep-' + item.id" :value="Number(item.id)">{{ item.name }} (#{{ item.id }})</option>
        </select>
        <button @click="onRunGatewayHealthCheck()" :disabled="isActionRunning('runGatewayHealthCheck')" class="btn btn-secondary">立即检测</button>
        <button @click="onLoadGatewayStatus()" :disabled="isActionRunning('loadGatewayStatus')" class="btn btn-secondary">刷新</button>
      </div>
    </div>

    <div class="gateway-status-strip">
      <div class="gateway-status-item">
        <span class="text-muted">端点</span>
        <strong>{{ selectedGatewayStatusEndpoint?.name || '-' }}</strong>
        <span class="mono text-xs">{{ selectedGatewayStatusEndpoint ? `${selectedGatewayStatusEndpoint.listen_host}:${selectedGatewayStatusEndpoint.listen_port}` : '-' }}</span>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">运行</span>
        <span class="badge" :class="gatewayStatusBadgeClass(gatewayStatus?.endpoint_runtime?.running)">{{ gatewayStatus?.endpoint_runtime?.running ? '运行中' : '已停止' }}</span>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">运行时间</span>
        <strong class="mono text-xs">{{ formatUptime(gatewayStatus?.endpoint_runtime?.started_at) }}</strong>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">版本</span>
        <strong class="mono text-xs">{{ backendStatus?.version || '-' }}</strong>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">端点可用</span>
        <span class="badge" :class="gatewayStatusBadgeClass(gatewayStatus?.summary?.available)">{{ gatewayStatus?.summary?.available ? '可用' : '不可用' }}</span>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">跳点池</span>
        <strong class="mono">{{ gatewayStatus?.summary?.healthy_hop_pools || 0 }}/{{ gatewayStatus?.summary?.total_hop_pools || 0 }}</strong>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">跨跳组合</span>
        <strong class="mono">{{ gatewayStatus?.summary?.healthy_transitions || 0 }}/{{ gatewayStatus?.summary?.total_transitions || 0 }}</strong>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">活跃链路</span>
        <strong class="mono">{{ (gatewayStatus?.active_hop_node_keys || []).map(key => '#' + getSerial(key)).join(' -> ') || '-' }}</strong>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">实时检测</span>
        <span class="badge" :class="gatewayHealthMonitor?.enabled ? (gatewayHealthMonitor?.running ? 'badge-warning' : 'badge-success') : 'badge-danger'">
          {{ gatewayHealthMonitor?.enabled ? (gatewayHealthMonitor?.running ? '检测中' : `${gatewayHealthMonitor?.interval_sec || '-'}s`) : '关闭' }}
        </span>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">最后检测</span>
        <strong class="mono text-xs">{{ formatTime(gatewayHealthMonitor?.last_finished_at) }}</strong>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">检测端点</span>
        <strong class="mono">{{ Object.keys(gatewayHealthMonitor?.endpoints || {}).length }}</strong>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">检测错误</span>
        <strong class="text-xs" :class="gatewayHealthMonitor?.last_error ? 'text-rose-600' : 'text-muted'">{{ gatewayHealthMonitor?.last_error || '-' }}</strong>
      </div>
    </div>

    <div class="gateway-config-panel">
      <div class="gateway-panel-header">
        <div>
          <h4>实时健康检测</h4>
          <p class="form-hint">后台按配置间隔检测每个启用端点；活跃链路失败时会标记冷却，后续请求自动选择其它可用组合。</p>
        </div>
        <span class="badge" :class="selectedGatewayHealthEndpoint?.active_failed ? 'badge-danger' : 'badge-neutral'">
          {{ selectedGatewayHealthEndpoint?.active_failed ? '当前失败' : '当前正常' }}
        </span>
      </div>
      <div class="gateway-config-grid">
        <div>
          <span class="text-muted">当前检测端点</span>
          <strong>{{ selectedGatewayHealthEndpoint?.name || selectedGatewayStatusEndpoint?.name || '-' }}</strong>
        </div>
        <div>
          <span class="text-muted">检测时间</span>
          <strong class="mono text-xs">{{ formatTime(selectedGatewayHealthEndpoint?.checked_at) }}</strong>
        </div>
        <div>
          <span class="text-muted">活跃检测链路</span>
          <strong class="mono">{{ (selectedGatewayHealthEndpoint?.active_hop_node_keys || []).map(key => '#' + getSerial(key)).join(' -> ') || '-' }}</strong>
        </div>
        <div>
          <span class="text-muted">检测间隔</span>
          <strong class="mono">{{ gatewayHealthMonitor?.enabled ? `${gatewayHealthMonitor?.interval_sec || '-'}s` : '关闭' }}</strong>
        </div>
      </div>
    </div>

    <div class="gateway-config-panel">
      <div class="gateway-panel-header">
        <div>
          <h4>选中网关配置</h4>
          <p class="form-hint">监听、会话策略和跳点池顺序来自当前端点配置。</p>
        </div>
        <span class="badge" :class="gatewayStatusBadgeClass(selectedGatewayStatusEndpoint?.enabled !== false)">{{ selectedGatewayStatusEndpoint?.enabled === false ? '已禁用' : '已启用' }}</span>
      </div>
      <div class="gateway-config-grid">
        <div>
          <span class="text-muted">监听地址</span>
          <strong class="mono">{{ selectedGatewayStatusEndpoint ? `${selectedGatewayStatusEndpoint.listen_host}:${selectedGatewayStatusEndpoint.listen_port}` : '-' }}</strong>
        </div>
        <div>
          <span class="text-muted">会话缺失</span>
          <strong>{{ selectedGatewayStatusEndpoint?.session_missing_action || '-' }}</strong>
        </div>
        <div>
          <span class="text-muted">粘性 TTL</span>
          <strong class="mono">{{ selectedGatewayStatusEndpoint?.sticky_ttl_sec || '-' }}s</strong>
        </div>
        <div>
          <span class="text-muted">跳点顺序</span>
          <strong>{{ formatEndpointHops(selectedGatewayStatusEndpoint) }}</strong>
        </div>
      </div>
    </div>

    <div class="gateway-status-layout">
      <section v-for="pool in gatewayHopPools" :key="'gw-hop-pool-' + pool.hop_index" class="gateway-status-panel">
        <div class="gateway-panel-header">
          <div>
            <h4>{{ pool.label }} · {{ pool.pool?.name || ('#' + pool.pool_id) }}</h4>
            <p class="form-hint">{{ pool.healthy_nodes }}/{{ pool.total_nodes }} 个可路由节点；{{ gatewayHealthCheckedText(pool) }}</p>
          </div>
          <span class="badge" :class="gatewayStatusBadgeClass(pool.available)">{{ pool.available ? '可用' : '空' }}</span>
        </div>
        <div class="table-wrap">
          <table class="data-table data-table-compact">
            <thead>
              <tr>
                <th style="width: 74px;">状态</th>
                <th>节点</th>
                <th>信息</th>
                <th style="width: 140px;">检测结果</th>
                <th style="width: 70px;">经由</th>
                <th style="width: 130px;">检测时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="node in pool.nodes" :key="'gw-hop-node-' + pool.hop_index + '-' + node.key" :class="{ 'gateway-active-row': node.active }">
                <td>
                  <span v-if="node.active" class="badge badge-warning">活跃</span>
                  <span v-else class="badge" :class="gatewayStatusBadgeClass(node.healthy)">{{ node.healthy ? '正常' : '异常' }}</span>
                </td>
                <td>
                  <div class="font-semibold">{{ formatGatewayNode(node) }}</div>
                  <div class="mono text-xs text-muted">{{ node.host }}:{{ node.port }}</div>
                </td>
                <td class="text-xs text-muted">{{ formatGatewayNodeMeta(node) }}</td>
                <td class="text-xs">
                  <span class="badge badge-sm" :class="gatewayHealthBadgeClass(gatewayHealthNode(pool, node))">
                    {{ formatGatewayHealthResult(gatewayHealthNode(pool, node)) }}
                  </span>
                </td>
                <td class="mono text-xs">{{ formatGatewayHealthVia(gatewayHealthNode(pool, node)) }}</td>
                <td class="mono text-xs">{{ formatTime(gatewayHealthNode(pool, node)?.checked_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <section v-for="transition in gatewayTransitions" :key="'gw-transition-' + transition.from_hop_index" class="gateway-transition-panel">
      <div class="gateway-panel-header">
        <div>
          <h4>{{ transition.label }}</h4>
          <p class="form-hint">{{ transition.healthy_pairs }}/{{ transition.total_pairs }} 个组合可用，显示 {{ transition.shown_pairs }} 个候选</p>
        </div>
        <span class="badge" :class="gatewayStatusBadgeClass(transition.available)">{{ transition.available ? '可路由' : '阻塞' }}</span>
      </div>
      <div class="table-wrap">
        <table class="data-table data-table-compact">
          <thead>
            <tr>
              <th style="width: 74px;">状态</th>
              <th>起点</th>
              <th>下一跳</th>
              <th style="width: 140px;">结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pair in transition.pairs" :key="'gw-pair-' + pair.hop_node_keys.join('-')" :class="{ 'gateway-active-row': pair.active }">
              <td>
                <span v-if="pair.active" class="badge badge-warning">活跃</span>
                <span v-else class="badge" :class="gatewayStatusBadgeClass(pair.healthy)">{{ pair.healthy ? '正常' : '失败' }}</span>
              </td>
              <td>{{ formatGatewayNode(pair.source) }}</td>
              <td>{{ formatGatewayNode(pair.target) }}</td>
              <td class="text-xs text-muted">
                <span v-if="pair.failed">失败冷却中</span>
                <span v-else-if="pair.known_healthy">近期成功</span>
                <span v-else>候选</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="!gatewayHopPools.length" class="empty-state">未选择端点或端点尚未配置代理池顺序。</div>

    <!-- Process Management Section -->
    <div class="process-management-section">
      <div class="gateway-config-panel">
        <div class="gateway-panel-header">
          <div>
            <h4>进程管理</h4>
            <p class="form-hint">管理后端 sing-box 实例的运行状态</p>
          </div>
          <div class="btn-group">
            <button @click="loadBackendStatus()" class="btn btn-secondary btn-sm" :disabled="isActionRunning('loadBackendStatus')">
              刷新状态
            </button>
            <button v-if="!backendStatus?.running" @click="backendStart()" class="btn btn-success btn-sm" :disabled="isActionRunning('backendStart')">
              启动
            </button>
            <button v-if="backendStatus?.running" @click="backendStop()" class="btn btn-danger btn-sm" :disabled="isActionRunning('backendStop')">
              停止
            </button>
            <button v-if="backendStatus?.running" @click="backendRestart()" class="btn btn-warning btn-sm" :disabled="isActionRunning('backendRestart')">
              重启
            </button>
          </div>
        </div>

        <!-- System Resources -->
        <div class="system-resources-strip">
          <div class="resource-item">
            <span class="resource-label">CPU</span>
            <div class="resource-bar">
              <div class="resource-bar-fill" :class="getCpuUsageClass()" :style="{ width: (backendStatus?.system?.cpu_percent || 0) + '%' }"></div>
            </div>
            <span class="resource-value mono">{{ backendStatus?.system?.cpu_percent || 0 }}%</span>
          </div>
          <div class="resource-item">
            <span class="resource-label">内存</span>
            <div class="resource-bar">
              <div class="resource-bar-fill" :class="getMemoryUsageClass()" :style="{ width: (backendStatus?.system?.memory_percent || 0) + '%' }"></div>
            </div>
            <span class="resource-value mono">{{ formatMemory(backendStatus?.system?.memory_used) }} / {{ formatMemory(backendStatus?.system?.memory_total) }}</span>
          </div>
          <div class="resource-item">
            <span class="resource-label">磁盘</span>
            <div class="resource-bar">
              <div class="resource-bar-fill" :class="getDiskUsageClass()" :style="{ width: (backendStatus?.system?.disk_percent || 0) + '%' }"></div>
            </div>
            <span class="resource-value mono">{{ formatMemory(backendStatus?.system?.disk_used) }} / {{ formatMemory(backendStatus?.system?.disk_total) }}</span>
          </div>
        </div>

        <!-- Backend Instances Table -->
        <div v-if="backendInstances.length" class="table-wrap">
          <table class="data-table data-table-compact">
            <thead>
              <tr>
                <th style="width: 80px;">状态</th>
                <th>实例 ID</th>
                <th style="width: 80px;">PID</th>
                <th style="width: 100px;">端口</th>
                <th style="width: 100px;">内存</th>
                <th style="width: 120px;">启动时间</th>
                <th style="width: 100px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="instance in backendInstances" :key="'instance-' + instance.instance_id">
                <td>
                  <span class="badge" :class="getInstanceStatusClass(instance)">
                    {{ getInstanceStatusText(instance) }}
                  </span>
                </td>
                <td>
                  <strong class="font-semibold">{{ instance.instance_id }}</strong>
                  <span v-if="instance.instance_id === backendInstanceId" class="badge badge-sm badge-info" style="margin-left: 4px;">当前</span>
                </td>
                <td class="mono text-xs">{{ instance.pid || '-' }}</td>
                <td class="mono text-xs">{{ instance.port || '-' }}</td>
                <td class="mono text-xs">{{ formatMemory(instance.memory_bytes) }}</td>
                <td class="mono text-xs">{{ formatUptime(instance.started_at) }}</td>
                <td>
                  <div class="btn-group btn-group-sm">
                    <button v-if="!instance.running" @click="backendInstanceStart(instance.instance_id)" class="btn btn-success btn-xs" :disabled="isActionRunning('backendInstanceStart')">
                      启动
                    </button>
                    <button v-if="instance.running" @click="backendInstanceStop(instance.instance_id)" class="btn btn-danger btn-xs" :disabled="isActionRunning('backendInstanceStop')">
                      停止
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-state-small">
          <p class="text-muted">暂无后端实例</p>
        </div>
      </div>

      <!-- Log Viewer -->
      <div class="gateway-config-panel">
        <div class="gateway-panel-header">
          <div>
            <h4>最近日志</h4>
            <p class="form-hint">显示后端最近日志记录</p>
          </div>
          <div class="btn-group">
            <button @click="loadBackendEvents()" class="btn btn-secondary btn-sm" :disabled="isActionRunning('loadBackendEvents')">
              刷新日志
            </button>
            <button @click="exportLogs()" class="btn btn-secondary btn-sm" :disabled="!recentLogs.length">
              导出日志
            </button>
            <button @click="toggleAutoScroll()" class="btn btn-sm" :class="logAutoScroll ? 'btn-primary' : 'btn-secondary'">
              {{ logAutoScroll ? '自动滚动 ✓' : '自动滚动' }}
            </button>
          </div>
        </div>

        <!-- Log Controls -->
        <div class="log-controls">
          <input
            v-model="logSearchText"
            type="text"
            class="input input-sm"
            placeholder="搜索日志..."
            style="flex: 1; max-width: 300px;"
          />
          <select v-model="logLevelFilter" class="select input-sm">
            <option value="">全部级别</option>
            <option value="info">INFO</option>
            <option value="warning">WARNING</option>
            <option value="error">ERROR</option>
            <option value="debug">DEBUG</option>
          </select>
          <button v-if="logSearchText || logLevelFilter" @click="clearFilters()" class="btn btn-sm btn-secondary">
            清除筛选
          </button>
          <span class="text-muted text-xs">
            显示 {{ filteredLogs.length }}/{{ recentLogs.length }} 条日志
            <span v-if="logSearchText && filteredLogs.length > 0"> (找到 {{ filteredLogs.length }} 条匹配)</span>
          </span>
        </div>

        <!-- Error Alert -->
        <div v-if="showLogAlert && logStats.error > 0" class="log-alert">
          <span class="log-alert-icon">⚠️</span>
          <span>检测到 {{ logStats.error }} 条错误日志</span>
          <button @click="clearLogAlert()" class="btn btn-sm btn-secondary">关闭</button>
        </div>

        <div class="log-viewer" ref="logContainer">
          <div v-if="filteredLogs.length" class="log-content">
            <div v-for="(log, index) in filteredLogs" :key="'log-' + index" class="log-line" :class="getLogLineClass(log)">
              <span class="log-time mono text-xs">{{ formatLogTime(log.timestamp || log.time) }}</span>
              <span class="log-level badge-sm" :class="getLogLevelClass(log.level || log.type)">{{ log.level || log.type || 'info' }}</span>
              <span class="log-message">{{ log.message || log.event || '-' }}</span>
            </div>
          </div>
          <div v-else class="empty-state-small">
            <p class="text-muted">暂无日志记录</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { rootProxyMixin } from "../rootProxyMixin";

export default {
  name: "GatewayStatusPanel",
  mixins: [rootProxyMixin],
  data() {
    return {
      gatewayStatusRefreshTimer: null,
      logSearchText: '',
      debouncedSearchText: '',
      logSearchDebounceTimer: null,
      logLevelFilter: '',
      logAutoScroll: true,
      showLogAlert: true,
    };
  },
  mounted() {
    this.startGatewayStatusAutoRefresh();
  },
  beforeUnmount() {
    this.stopGatewayStatusAutoRefresh();
    if (this.logSearchDebounceTimer) {
      clearTimeout(this.logSearchDebounceTimer);
    }
  },
  watch: {
    logSearchText(value) {
      if (this.logSearchDebounceTimer) {
        clearTimeout(this.logSearchDebounceTimer);
      }
      this.logSearchDebounceTimer = setTimeout(() => {
        this.debouncedSearchText = value;
      }, 300);
    },
    proxyPoolTab(value) {
      this.startGatewayStatusAutoRefresh();
      if (value === "gateway-status") {
        this.loadGatewayStatus().catch(err => this.setMessage("刷新网关状态失败: " + err, true));
      }
    },
    "gatewayHealthMonitor.interval_sec"() {
      this.startGatewayStatusAutoRefresh();
    },
    "gatewayHealthMonitor.enabled"() {
      this.startGatewayStatusAutoRefresh();
    },
    filteredLogs: {
      handler() {
        if (this.logAutoScroll && this.$refs.logContainer) {
          this.$nextTick(() => {
            const container = this.$refs.logContainer;
            if (container) {
              container.scrollTop = container.scrollHeight;
            }
          });
        }
      },
      deep: true,
    },
  },
  computed: {
    recentLogs() {
      return (this.backendEvents || []).slice(0, 100);
    },
    filteredLogs() {
      let logs = this.recentLogs;
      if (this.debouncedSearchText) {
        const search = this.debouncedSearchText.toLowerCase();
        logs = logs.filter(log => {
          const message = (log.message || log.event || '').toLowerCase();
          return message.includes(search);
        });
      }
      if (this.logLevelFilter) {
        logs = logs.filter(log => {
          const level = (log.level || log.type || 'info').toLowerCase();
          return level === this.logLevelFilter;
        });
      }
      return logs;
    },
    logStats() {
      const logs = this.recentLogs;
      return {
        info: logs.filter(l => (l.level || l.type || '').toLowerCase() === 'info').length,
        warning: logs.filter(l => (l.level || l.type || '').toLowerCase() === 'warning' || (l.level || l.type || '').toLowerCase() === 'warn').length,
        error: logs.filter(l => (l.level || l.type || '').toLowerCase() === 'error' || (l.level || l.type || '').toLowerCase() === 'fatal').length,
        debug: logs.filter(l => (l.level || l.type || '').toLowerCase() === 'debug').length,
      };
    },
  },
  methods: {
    formatUptime(startedAt) {
      if (!startedAt) return '-';
      const start = new Date(startedAt);
      const now = new Date();
      const diffMs = now - start;
      const diffSec = Math.floor(diffMs / 1000);
      const diffMin = Math.floor(diffSec / 60);
      const diffHour = Math.floor(diffMin / 60);
      const diffDay = Math.floor(diffHour / 24);
      if (diffDay > 0) return `${diffDay}天 ${diffHour % 24}时`;
      if (diffHour > 0) return `${diffHour}时 ${diffMin % 60}分`;
      if (diffMin > 0) return `${diffMin}分 ${diffSec % 60}秒`;
      return `${diffSec}秒`;
    },
    stopGatewayStatusAutoRefresh() {
      if (this.gatewayStatusRefreshTimer) {
        clearInterval(this.gatewayStatusRefreshTimer);
        this.gatewayStatusRefreshTimer = null;
      }
    },
    startGatewayStatusAutoRefresh() {
      this.stopGatewayStatusAutoRefresh();
      if (this.proxyPoolTab !== "gateway-status") return;
      const monitor = this.gatewayHealthMonitor || {};
      const intervalSec = Number(monitor.interval_sec || 30);
      const delayMs = Math.max(5000, Math.min(300000, intervalSec * 1000));
      this.gatewayStatusRefreshTimer = setInterval(() => {
        if (this.proxyPoolTab !== "gateway-status" || this.isActionRunning("loadGatewayStatus")) return;
        this.loadGatewayStatus().catch(err => this.setMessage("刷新网关状态失败: " + err, true));
      }, delayMs);
    },
    getInstanceStatusClass(instance) {
      if (!instance.running) return 'badge-neutral';
      if (instance.health === 'unhealthy') return 'badge-danger';
      if (instance.health === 'crashed') return 'badge-danger';
      return 'badge-success';
    },
    getInstanceStatusText(instance) {
      if (!instance.running) return '已停止';
      if (instance.health === 'unhealthy') return '异常';
      if (instance.health === 'crashed') return '崩溃';
      return '运行中';
    },
    getCpuUsageClass() {
      const cpu = this.backendStatus?.system?.cpu_percent || 0;
      if (cpu > 80) return 'resource-bar-danger';
      if (cpu > 60) return 'resource-bar-warning';
      return 'resource-bar-success';
    },
    getMemoryUsageClass() {
      const mem = this.backendStatus?.system?.memory_percent || 0;
      if (mem > 80) return 'resource-bar-danger';
      if (mem > 60) return 'resource-bar-warning';
      return 'resource-bar-success';
    },
    getDiskUsageClass() {
      const disk = this.backendStatus?.system?.disk_percent || 0;
      if (disk > 90) return 'resource-bar-danger';
      if (disk > 70) return 'resource-bar-warning';
      return 'resource-bar-success';
    },
    formatMemory(bytes) {
      if (!bytes) return '-';
      const mb = bytes / (1024 * 1024);
      if (mb < 1024) return `${Math.round(mb)}MB`;
      const gb = mb / 1024;
      return `${gb.toFixed(1)}GB`;
    },
    formatLogTime(time) {
      if (!time) return '-';
      const date = new Date(time);
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${hours}:${minutes}:${seconds}`;
    },
    getLogLineClass(log) {
      const level = String(log.level || log.type || '').toLowerCase();
      if (level === 'error' || level === 'fatal') return 'log-line-error';
      if (level === 'warning' || level === 'warn') return 'log-line-warning';
      return 'log-line-info';
    },
    getLogLevelClass(level) {
      const l = String(level || '').toLowerCase();
      if (l === 'error' || l === 'fatal') return 'badge-danger';
      if (l === 'warning' || l === 'warn') return 'badge-warning';
      return 'badge-info';
    },
    exportLogs() {
      const logs = this.filteredLogs;
      if (!logs.length) return;
      const lines = logs.map(log => {
        const time = log.timestamp || log.time || '';
        const level = (log.level || log.type || 'info').toUpperCase();
        const message = log.message || log.event || '-';
        return `[${time}] [${level}] ${message}`;
      });
      const content = lines.join('\n');
      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const now = new Date();
      const filename = `logs-${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}-${String(now.getMinutes()).padStart(2, '0')}.txt`;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      this.setMessage('日志已导出');
    },
    toggleAutoScroll() {
      this.logAutoScroll = !this.logAutoScroll;
    },
    clearLogAlert() {
      this.showLogAlert = false;
    },
    clearFilters() {
      this.logSearchText = '';
      this.debouncedSearchText = '';
      this.logLevelFilter = '';
    },
  },
};
</script>
