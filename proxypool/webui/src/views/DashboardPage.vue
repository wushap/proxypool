<template>
  <section v-show="activePage === 'dashboard'" class="dashboard-page fade-in">
    <!-- Breadcrumb -->
    <Breadcrumb :items="breadcrumbItems" />

    <!-- Header -->
    <div class="header">
      <div class="header-row">
        <div>
          <p class="header-kicker">OVERVIEW</p>
          <h1 class="header-title">仪表盘</h1>
          <p class="header-subtitle">代理池运行状态概览</p>
        </div>
        <div class="header-actions">
          <select v-model.number="autoRefreshSec" class="select" style="width: 120px; height: 32px;" @change="onAutoRefreshChange">
            <option :value="0">手动刷新</option>
            <option :value="30">30 秒</option>
            <option :value="60">1 分钟</option>
            <option :value="300">5 分钟</option>
          </select>
          <button class="btn btn-secondary" :disabled="isActionRunning('refreshDashboard')" @click="onRefreshDashboard">
            {{ buttonLabel('refreshDashboard', '刷新', '刷新中...') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <LoadingState v-if="isLoading" text="加载数据中..." size="small" />

    <template v-else>
      <!-- Stat Cards -->
      <div class="stat-grid dashboard-stat-grid">
        <StatCard
          label="节点总数"
          :value="stats.total ?? 0"
          description="已收录代理节点"
        />
        <StatCard
          label="可用节点"
          :value="stats.available ?? 0"
          description="通过可用性测试"
          color="var(--success-text)"
        />
        <StatCard
          label="可用率"
          :value="(stats.availability_rate ?? 0) + '%'"
          description="可用节点占比"
        >
          <template #description>
            <div class="dashboard-progress">
              <div class="dashboard-progress-bar" :style="{ width: (stats.availability_rate ?? 0) + '%' }"></div>
            </div>
          </template>
        </StatCard>
        <StatCard
          label="平均延迟"
          :value="stats.avg_latency_ms ? stats.avg_latency_ms + 'ms' : '-'"
          description="可用节点平均值"
        />
      </div>

      <!-- Second row: Speed + ChatGPT + Subscriptions -->
      <div class="stat-grid" style="grid-template-columns: repeat(3, 1fr); margin-bottom: 12px;">
        <StatCard
          label="平均带宽"
          :value="stats.avg_speed_mbps ? stats.avg_speed_mbps + ' Mbps' : '-'"
          description="可用节点平均下载速度"
        />
        <StatCard
          label="ChatGPT 解锁"
          :value="stats.openai_unlocked ?? 0"
          color="var(--success-text)"
        >
          <template #description>
            已解锁 / 被封锁 {{ stats.openai_blocked ?? 0 }}
            <span v-if="chatgptRate !== null" class="badge badge-sm badge-success" style="margin-left: 4px;">{{ chatgptRate }}%</span>
          </template>
        </StatCard>
        <StatCard
          label="订阅源"
          :value="stats.subscription_count ?? subscriptions.length ?? 0"
          description="已配置的订阅源"
        />
      </div>

      <!-- Middle Row: Charts -->
      <div class="dashboard-grid">
        <!-- Protocol Distribution -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">协议分布</h3>
            <template v-if="protocolEntries.length">
              <div class="dashboard-protocol-list">
                <div v-for="p in protocolEntries" :key="p.name" class="dashboard-protocol-row">
                  <div class="dashboard-protocol-info">
                    <span class="dashboard-protocol-name">{{ p.name }}</span>
                    <span class="dashboard-protocol-count">{{ p.count }} ({{ p.pct }}%)</span>
                  </div>
                  <div class="dashboard-bar-track">
                    <div class="dashboard-bar-fill" :style="{ width: p.pct + '%', background: p.color }"></div>
                  </div>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无节点数据" size="small">
              <template #actions>
                <button class="btn btn-xs btn-secondary" @click="goToTasks">导入节点</button>
              </template>
            </EmptyState>
          </div>
        </div>

        <!-- Country Distribution -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">国家/地区分布 <span class="text-muted" style="font-size: 12px; font-weight: 400;">Top 8</span></h3>
            <template v-if="countryEntries.length">
              <div class="dashboard-protocol-list">
                <div v-for="c in countryEntries" :key="c.name" class="dashboard-protocol-row">
                  <div class="dashboard-protocol-info">
                    <span class="dashboard-protocol-name">{{ c.name }}</span>
                    <span class="dashboard-protocol-count">{{ c.count }}</span>
                  </div>
                  <div class="dashboard-bar-track">
                    <div class="dashboard-bar-fill dashboard-bar-country" :style="{ width: c.pct + '%' }"></div>
                  </div>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无国家数据" description="请先运行 IP 位置补全" size="small">
              <template #actions>
                <button class="btn btn-xs btn-secondary" @click="onEnrichGeo">补全 IP 位置</button>
              </template>
            </EmptyState>
          </div>
        </div>
      </div>

      <!-- Third Row: IP Purity + System Status -->
      <div class="dashboard-grid" style="margin-top: 12px;">
        <!-- IP Purity Distribution -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">IP 纯净度分布</h3>
            <template v-if="purityEntries.length">
              <div class="dashboard-protocol-list">
                <div v-for="p in purityEntries" :key="p.name" class="dashboard-protocol-row">
                  <div class="dashboard-protocol-info">
                    <span class="dashboard-protocol-name">{{ p.name }}</span>
                    <span class="dashboard-protocol-count">{{ p.count }}</span>
                  </div>
                  <div class="dashboard-bar-track">
                    <div class="dashboard-bar-fill" :style="{ width: p.pct + '%', background: p.color }"></div>
                  </div>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无纯净度数据" description="请先运行 IP 纯净度检测" size="small">
              <template #actions>
                <button class="btn btn-xs btn-secondary" @click="onRunIpPurity">检测纯净度</button>
              </template>
            </EmptyState>
          </div>
        </div>

        <!-- System Status -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">系统状态</h3>
            <div class="dashboard-status-list">
              <div class="dashboard-status-row">
                <span class="dashboard-status-label">后端引擎</span>
                <span class="badge" :class="backendStatus.running ? 'badge-success' : 'badge-danger'">
                  {{ backendStatus.running ? '运行中' : '已停止' }}
                </span>
              </div>
              <div class="dashboard-status-row">
                <span class="dashboard-status-label">已检测节点</span>
                <span class="font-semibold">{{ stats.checked ?? 0 }} / {{ stats.total ?? 0 }}</span>
              </div>
              <div class="dashboard-status-row">
                <span class="dashboard-status-label">活跃任务</span>
                <span class="badge" :class="activeTaskCount > 0 ? 'badge-warning' : 'badge-neutral'">
                  {{ activeTaskCount > 0 ? activeTaskCount + ' 个运行中' : '空闲' }}
                </span>
              </div>
              <div class="dashboard-status-row">
                <span class="dashboard-status-label">代理池</span>
                <span class="font-semibold">{{ proxyPools.length }} 个</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Recent Tasks -->
      <div class="card" style="margin-top: 12px;">
        <div class="card-body">
          <div class="card-header" style="margin-bottom: 8px;">
            <h3 class="card-title">最近任务</h3>
            <button class="btn btn-ghost btn-sm" @click="selectPage('tasks')">查看全部</button>
          </div>
          <template v-if="recentTasks.length">
            <div class="dashboard-task-list">
              <div v-for="t in recentTasks" :key="t.id" class="dashboard-task-item">
                <div class="dashboard-task-info">
                  <span class="dashboard-task-name">{{ t.name || t.task_type || '任务' }}</span>
                  <span class="badge badge-sm" :class="taskStatusClass(t.status)">{{ taskStatusText(t.status) }}</span>
                </div>
                <div v-if="t.progress_total > 0" class="dashboard-task-progress">
                  <div class="dashboard-bar-track">
                    <div class="dashboard-bar-fill dashboard-bar-accent" :style="{ width: Math.round((t.progress_current / Math.max(t.progress_total, 1)) * 100) + '%' }"></div>
                  </div>
                  <span class="text-muted" style="font-size: 11px;">{{ t.progress_current }}/{{ t.progress_total }}</span>
                </div>
              </div>
            </div>
          </template>
          <EmptyState v-else title="暂无任务记录" size="small">
            <template #actions>
              <button class="btn btn-xs btn-secondary" @click="goToTasks">执行任务</button>
            </template>
          </EmptyState>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="card" style="margin-top: 12px;">
        <div class="card-body">
          <h3 class="card-title" style="margin-bottom: 10px;">快速操作</h3>
          <div class="action-bar">
            <button class="btn btn-primary" @click="goToTasks">任务中心</button>
            <button class="btn btn-secondary" @click="goToSubscriptions">订阅管理</button>
            <button class="btn btn-secondary" @click="goToProxies">代理节点</button>
            <button class="btn btn-secondary" @click="copyAvailableSubscription">复制可用代理</button>
            <a href="/api/subscription?only_available=true" target="_blank" class="btn btn-secondary">导出订阅</a>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<script>
import Breadcrumb from '../components/layout/Breadcrumb.vue'
import StatCard from '../components/common/StatCard.vue'
import EmptyState from '../components/common/EmptyState.vue'
import LoadingState from '../components/common/LoadingState.vue'

const PROTOCOL_COLORS = [
  '#4b5058', '#6366f1', '#0891b2', '#16a34a', '#ca8a04',
  '#dc2626', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316',
];

const PURITY_COLORS = {
  '家宽': '#16a34a',
  '非家宽': '#dc2626',
  '未知': '#9ca3af',
};

export default {
  name: 'DashboardPage',
  components: {
    Breadcrumb,
    StatCard,
    EmptyState,
    LoadingState,
  },
  inject: ['appState'],
  data() {
    let savedInterval = 0;
    try { savedInterval = Number(localStorage.getItem('pp-dashboard-refresh') || 0); } catch {}
    return {
      autoRefreshSec: savedInterval,
      autoRefreshTimer: null,
      isLoading: true,
    };
  },
  watch: {
    async activePage(val) {
      if (val === 'dashboard') {
        this.isLoading = true;
        try {
          await this.appState.loadData();
          await this.appState.refreshTaskList({ force: true });
        } finally {
          this.isLoading = false;
        }
        if (this.autoRefreshSec > 0) {
          this.startAutoRefresh();
        }
      } else {
        this.stopAutoRefresh();
      }
    },
  },
  async mounted() {
    this.isLoading = true;
    try {
      await this.appState.loadData();
      await this.appState.refreshTaskList({ force: true });
    } finally {
      this.isLoading = false;
    }
    if (this.autoRefreshSec > 0 && this.activePage === 'dashboard') {
      this.startAutoRefresh();
    }
  },
  beforeUnmount() {
    this.stopAutoRefresh();
  },
  computed: {
    breadcrumbItems() {
      return [
        { label: '首页', path: '/', onClick: () => this.selectPage('dashboard') },
        { label: '仪表盘' },
      ];
    },
    activePage() { return this.appState.activePage; },
    stats() { return this.appState.stats; },
    backendStatus() { return this.appState.backendStatus; },
    subscriptions() { return this.appState.subscriptions; },
    proxyPools() { return this.appState.proxyPools; },
    taskItems() { return this.appState.taskItems; },
    activeTaskCount() {
      return this.taskItems.filter(t => ['queued', 'running'].includes(String(t.status || ''))).length;
    },
    recentTasks() {
      return (this.taskItems || []).slice(0, 5);
    },
    chatgptRate() {
      const u = this.stats?.openai_unlocked ?? 0;
      const b = this.stats?.openai_blocked ?? 0;
      const t = u + b;
      return t > 0 ? Math.round((u / t) * 100) : null;
    },
    protocolEntries() {
      const bp = this.stats?.by_protocol || {};
      const total = Object.values(bp).reduce((s, n) => s + n, 0);
      if (!total) return [];
      return Object.entries(bp)
        .sort((a, b) => b[1] - a[1])
        .map(([name, count], idx) => ({
          name,
          count,
          pct: Math.round((count / total) * 100),
          color: PROTOCOL_COLORS[idx % PROTOCOL_COLORS.length],
        }));
    },
    countryEntries() {
      const bc = this.stats?.by_country || {};
      const entries = Object.entries(bc).sort((a, b) => b[1] - a[1]).slice(0, 8);
      const max = entries.length > 0 ? entries[0][1] : 1;
      return entries.map(([name, count]) => ({
        name,
        count,
        pct: Math.round((count / max) * 100),
      }));
    },
    purityEntries() {
      const bp = this.stats?.by_purity || {};
      const total = Object.values(bp).reduce((s, n) => s + n, 0);
      if (!total) return [];
      return Object.entries(bp)
        .sort((a, b) => b[1] - a[1])
        .map(([name, count]) => ({
          name,
          count,
          pct: Math.round((count / total) * 100),
          color: PURITY_COLORS[name] || '#6366f1',
        }));
    },
  },
  methods: {
    isActionRunning(key) { return this.appState.isActionRunning(key); },
    buttonLabel(key, idle, running) { return this.appState.buttonLabel(key, idle, running); },
    selectPage(key) { this.appState.selectPage(key); },
    async onRefreshDashboard() {
      this.isLoading = true;
      try {
        await this.appState.runWithButtonState('refreshDashboard', async () => {
          await this.appState.loadData();
          await this.appState.refreshTaskList({ force: true });
          this.appState.setMessage('仪表盘已刷新');
        });
      } finally {
        this.isLoading = false;
      }
    },
    startAutoRefresh() {
      this.stopAutoRefresh();
      if (this.autoRefreshSec > 0) {
        this.autoRefreshTimer = setInterval(() => {
          this.onRefreshDashboard();
        }, this.autoRefreshSec * 1000);
      }
    },
    stopAutoRefresh() {
      if (this.autoRefreshTimer) {
        clearInterval(this.autoRefreshTimer);
        this.autoRefreshTimer = null;
      }
    },
    onAutoRefreshChange() {
      try { localStorage.setItem('pp-dashboard-refresh', String(this.autoRefreshSec)); } catch {}
      if (this.autoRefreshSec > 0 && this.activePage === 'dashboard') {
        this.startAutoRefresh();
      } else {
        this.stopAutoRefresh();
      }
    },
    goToTasks() { this.appState.selectPage('tasks'); },
    goToSubscriptions() { this.appState.selectPage('subscriptions'); },
    goToProxies() { this.appState.selectPage('proxies'); },
    async copyAvailableSubscription() {
      try {
        const resp = await fetch('/api/subscription?only_available=true');
        const text = await resp.text();
        if (!text.trim()) { this.appState.setMessage('没有可用的代理节点', true); return; }
        await navigator.clipboard.writeText(text);
        const lines = text.split('\n').filter(Boolean).length;
        this.appState.setMessage(`已复制 ${lines} 个可用代理链接到剪贴板`);
      } catch (err) { this.appState.setMessage('复制失败: ' + err, true); }
    },
    taskStatusClass(status) {
      const s = String(status || '');
      if (s === 'running' || s === 'queued') return 'badge-warning';
      if (s === 'completed' || s === 'done') return 'badge-success';
      if (s === 'failed' || s === 'error') return 'badge-danger';
      return 'badge-neutral';
    },
    taskStatusText(status) {
      const s = String(status || '');
      if (s === 'running') return '运行中';
      if (s === 'queued') return '排队中';
      if (s === 'completed' || s === 'done') return '已完成';
      if (s === 'failed' || s === 'error') return '失败';
      return s || '未知';
    },
  },
};
</script>
