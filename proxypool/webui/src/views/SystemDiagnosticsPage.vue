<template>
  <div class="page-container fade-in">
    <div class="section-header">
      <div>
        <h2 class="section-title">系统诊断</h2>
        <p class="form-hint">全面检查系统健康状态，生成诊断报告</p>
      </div>
      <div class="btn-group">
        <button @click="runDiagnostics" :disabled="isRunning" class="btn btn-primary">
          {{ isRunning ? '诊断中...' : '一键诊断' }}
        </button>
        <button @click="exportReport" :disabled="!report" class="btn btn-secondary">
          导出报告
        </button>
      </div>
    </div>

    <!-- System Health Summary -->
    <div class="card" style="margin-bottom: 16px;">
      <div class="card-body">
        <div class="health-header">
          <h3 class="settings-title">系统健康概览</h3>
          <div v-if="report" class="health-score-badge" :class="healthScoreClass">
            <span class="health-score-label">健康评分</span>
            <span class="health-score-value">{{ healthScore }}</span>
            <span class="health-score-max">/100</span>
          </div>
        </div>
        <div class="health-summary-grid">
          <div class="health-item">
            <span class="health-label">后端进程</span>
            <span class="health-status" :class="getStatusClass(report?.backend?.running)">
              {{ report?.backend?.running ? '运行中' : '已停止' }}
            </span>
          </div>
          <div class="health-item">
            <span class="health-label">网关服务</span>
            <span class="health-status" :class="getStatusClass(report?.gateway?.running)">
              {{ report?.gateway?.running ? '运行中' : '已停止' }}
            </span>
          </div>
          <div class="health-item">
            <span class="health-label">代理池</span>
            <span class="health-status badge-info">
              {{ report?.pools?.healthy || 0 }}/{{ report?.pools?.total || 0 }} 健康
            </span>
          </div>
          <div class="health-item">
            <span class="health-label">代理节点</span>
            <span class="health-status badge-info">
              {{ report?.proxies?.available || 0 }}/{{ report?.proxies?.total || 0 }} 可用
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Detailed Report -->
    <div v-if="report" class="card" style="margin-bottom: 16px;">
      <div class="card-body">
        <h3 class="settings-title">诊断详情</h3>

        <!-- Backend Status -->
        <div class="diagnostic-section">
          <h4 class="diagnostic-section-title">后端进程状态</h4>
          <div class="diagnostic-grid">
            <div class="diagnostic-item">
              <span class="diagnostic-label">运行状态</span>
              <span class="diagnostic-value" :class="getStatusClass(report.backend.running)">
                {{ report.backend.running ? '运行中' : '已停止' }}
              </span>
            </div>
            <div class="diagnostic-item">
              <span class="diagnostic-label">版本</span>
              <span class="diagnostic-value">{{ report.backend.version || '-' }}</span>
            </div>
            <div class="diagnostic-item">
              <span class="diagnostic-label">CPU 使用率</span>
              <span class="diagnostic-value">{{ report.backend.cpu || 0 }}%</span>
            </div>
            <div class="diagnostic-item">
              <span class="diagnostic-label">内存使用</span>
              <span class="diagnostic-value">{{ report.backend.memory || '-' }}</span>
            </div>
          </div>
        </div>

        <!-- Gateway Status -->
        <div class="diagnostic-section">
          <h4 class="diagnostic-section-title">网关服务状态</h4>
          <div class="diagnostic-grid">
            <div class="diagnostic-item">
              <span class="diagnostic-label">运行状态</span>
              <span class="diagnostic-value" :class="getStatusClass(report.gateway.running)">
                {{ report.gateway.running ? '运行中' : '已停止' }}
              </span>
            </div>
            <div class="diagnostic-item">
              <span class="diagnostic-label">端点数量</span>
              <span class="diagnostic-value">{{ report.gateway.endpoints || 0 }}</span>
            </div>
            <div class="diagnostic-item">
              <span class="diagnostic-label">健康检查</span>
              <span class="diagnostic-value" :class="getStatusClass(report.gateway.healthy)">
                {{ report.gateway.healthy ? '正常' : '异常' }}
              </span>
            </div>
          </div>
        </div>

        <!-- Pool Health -->
        <div class="diagnostic-section">
          <h4 class="diagnostic-section-title">代理池健康</h4>
          <div class="diagnostic-grid">
            <div class="diagnostic-item">
              <span class="diagnostic-label">总池数</span>
              <span class="diagnostic-value">{{ report.pools.total || 0 }}</span>
            </div>
            <div class="diagnostic-item">
              <span class="diagnostic-label">健康池数</span>
              <span class="diagnostic-value" :class="getStatusClass(report.pools.healthy > 0)">
                {{ report.pools.healthy || 0 }}
              </span>
            </div>
            <div class="diagnostic-item">
              <span class="diagnostic-label">异常池数</span>
              <span class="diagnostic-value" :class="getWarningClass(report.pools.unhealthy > 0)">
                {{ report.pools.unhealthy || 0 }}
              </span>
            </div>
          </div>
        </div>

        <!-- Proxy Statistics -->
        <div class="diagnostic-section">
          <h4 class="diagnostic-section-title">代理节点统计</h4>
          <div class="diagnostic-grid">
            <div class="diagnostic-item">
              <span class="diagnostic-label">总节点数</span>
              <span class="diagnostic-value">{{ report.proxies.total || 0 }}</span>
            </div>
            <div class="diagnostic-item">
              <span class="diagnostic-label">可用节点</span>
              <span class="diagnostic-value" :class="getStatusClass(report.proxies.available > 0)">
                {{ report.proxies.available || 0 }}
              </span>
            </div>
            <div class="diagnostic-item">
              <span class="diagnostic-label">不可用节点</span>
              <span class="diagnostic-value" :class="getWarningClass(report.proxies.unavailable > 0)">
                {{ report.proxies.unavailable || 0 }}
              </span>
            </div>
          </div>
        </div>

        <!-- Issues Found -->
        <div v-if="report.issues && report.issues.length" class="diagnostic-section">
          <h4 class="diagnostic-section-title text-rose-600">发现的问题</h4>
          <div class="issues-list">
            <div v-for="(issue, idx) in report.issues" :key="'issue-' + idx" class="issue-item">
              <span class="issue-icon">⚠️</span>
              <span class="issue-message">{{ issue }}</span>
            </div>
          </div>
        </div>

        <!-- Report Timestamp -->
        <div class="report-meta">
          <span class="text-muted text-xs">生成时间: {{ formatTime(report.timestamp) }}</span>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="card">
      <div class="card-body empty-state">
        <p class="text-muted">点击「一键诊断」按钮开始系统健康检查</p>
      </div>
    </div>

    <!-- Health Trend Chart -->
    <div v-if="healthHistory.length > 1" class="card" style="margin-bottom: 16px;">
      <div class="card-body">
        <h3 class="settings-title">健康趋势 (最近 24 小时)</h3>
        <div class="health-trend-chart">
          <svg viewBox="0 0 600 100" class="trend-svg">
            <!-- Grid lines -->
            <line x1="0" y1="25" x2="600" y2="25" stroke="var(--line-soft)" stroke-width="1" stroke-dasharray="4"/>
            <line x1="0" y1="50" x2="600" y2="50" stroke="var(--line-soft)" stroke-width="1" stroke-dasharray="4"/>
            <line x1="0" y1="75" x2="600" y2="75" stroke="var(--line-soft)" stroke-width="1" stroke-dasharray="4"/>

            <!-- Health trend line -->
            <polyline
              :points="trendPoints"
              fill="none"
              :stroke="trendColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />

            <!-- Data points -->
            <circle
              v-for="(point, idx) in trendDataPoints"
              :key="'point-' + idx"
              :cx="point.x"
              :cy="point.y"
              r="3"
              :fill="point.healthy ? 'var(--success)' : 'var(--danger)'"
            />
          </svg>
          <div class="trend-labels">
            <span class="text-muted text-xs">24h 前</span>
            <span class="text-muted text-xs">12h 前</span>
            <span class="text-muted text-xs">现在</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Health Comparison -->
    <div v-if="healthHistory.length > 0" class="card" style="margin-bottom: 16px;">
      <div class="card-body">
        <h3 class="settings-title">健康对比</h3>
        <div class="health-comparison-grid">
          <div class="comparison-item">
            <span class="comparison-label">本次诊断</span>
            <span class="comparison-value" :class="getStatusClass(report?.issues?.length === 0)">
              {{ report?.issues?.length === 0 ? '健康' : `${report?.issues?.length || 0} 个问题` }}
            </span>
            <span class="comparison-score" :class="healthScoreClass">{{ healthScore }}分</span>
          </div>
          <div class="comparison-item">
            <span class="comparison-label">24小时平均</span>
            <span class="comparison-value" :class="getStatusClass(avgHealthScore >= 80)">
              {{ avgHealthScore >= 80 ? '健康' : avgHealthScore >= 60 ? '一般' : '异常' }}
            </span>
            <span class="comparison-score">{{ avgHealthScore }}分</span>
          </div>
          <div class="comparison-item">
            <span class="comparison-label">本周平均</span>
            <span class="comparison-value" :class="getStatusClass(weeklyAvgScore >= 80)">
              {{ weeklyAvgScore >= 80 ? '健康' : weeklyAvgScore >= 60 ? '一般' : '异常' }}
            </span>
            <span class="comparison-score">{{ weeklyAvgScore }}分</span>
          </div>
          <div class="comparison-item">
            <span class="comparison-label">趋势</span>
            <span class="comparison-value" :class="trendDirection >= 0 ? 'text-green-600' : 'text-red-600'">
              {{ trendDirection >= 0 ? '改善中' : '下降中' }}
            </span>
            <span class="comparison-score" :class="trendDirection >= 0 ? 'text-green-600' : 'text-red-600'">
              {{ trendDirection >= 0 ? '+' : '' }}{{ trendDirection }}分
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Health Alerting Rules -->
    <div class="card" style="margin-bottom: 16px;">
      <div class="card-body">
        <h3 class="settings-title">健康告警规则</h3>
        <div class="alerting-rules-list">
          <div class="alerting-rule-item" v-for="(rule, idx) in alertingRules" :key="'rule-' + idx">
            <div class="rule-header">
              <span class="rule-name">{{ rule.name }}</span>
              <label class="toggle-switch">
                <input type="checkbox" v-model="rule.enabled" @change="saveAlertingRules">
                <span class="toggle-slider"></span>
              </label>
            </div>
            <div class="rule-description">{{ rule.description }}</div>
            <div class="rule-condition">
              <span class="text-muted text-xs">触发条件: </span>
              <span class="rule-threshold">{{ rule.condition }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Health History -->
    <div class="card">
      <div class="card-body">
        <h3 class="settings-title">健康历史 (最近 24 小时)</h3>
        <div v-if="healthHistory.length" class="health-history">
          <div v-for="(snapshot, idx) in healthHistory" :key="'history-' + idx" class="history-item">
            <span class="history-time mono text-xs">{{ formatTime(snapshot.timestamp) }}</span>
            <span class="history-status" :class="getStatusClass(snapshot.healthy)">
              {{ snapshot.healthy ? '健康' : '异常' }}
            </span>
            <span class="history-summary text-xs text-muted">{{ snapshot.summary }}</span>
          </div>
        </div>
        <div v-else class="empty-state-small">
          <p class="text-muted">暂无历史记录</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "SystemDiagnosticsPage",
  inject: ['appState'],
  data() {
    return {
      report: null,
      isRunning: false,
      healthHistory: [],
      alertingRules: [
        { name: '后端进程停止', description: '当后端进程停止运行时告警', condition: '后端状态 = 已停止', enabled: true },
        { name: '网关服务停止', description: '当网关服务停止运行时告警', condition: '网关状态 = 已停止', enabled: true },
        { name: '健康评分过低', description: '当系统健康评分低于60分时告警', condition: '健康评分 < 60', enabled: true },
        { name: '代理池异常', description: '当存在异常代理池时告警', condition: '异常池数 > 0', enabled: true },
        { name: '代理节点不可用', description: '当不可用节点比例超过20%时告警', condition: '不可用比例 > 20%', enabled: false },
      ],
    };
  },
  computed: {
    healthScore() {
      if (!this.report) return 0;
      let score = 0;
      // Backend running: 25 points
      if (this.report.backend?.running) score += 25;
      // Gateway running: 25 points
      if (this.report.gateway?.running) score += 25;
      // Pool health: 25 points (healthy/total * 25)
      if (this.report.pools?.total > 0) {
        score += Math.round((this.report.pools.healthy / this.report.pools.total) * 25);
      } else {
        score += 25; // No pools, consider as healthy
      }
      // Proxy availability: 25 points (available/total * 25)
      if (this.report.proxies?.total > 0) {
        score += Math.round((this.report.proxies.available / this.report.proxies.total) * 25);
      } else {
        score += 25; // No proxies, consider as healthy
      }
      return score;
    },
    healthScoreClass() {
      if (this.healthScore >= 90) return 'score-excellent';
      if (this.healthScore >= 70) return 'score-good';
      if (this.healthScore >= 50) return 'score-fair';
      return 'score-poor';
    },
    avgHealthScore() {
      if (this.healthHistory.length === 0) return 0;
      // Calculate average from health history
      let totalScore = 0;
      this.healthHistory.forEach(snapshot => {
        totalScore += snapshot.score || (snapshot.healthy ? 100 : 0);
      });
      return Math.round(totalScore / this.healthHistory.length);
    },
    weeklyAvgScore() {
      // For demo purposes, use the same as avgHealthScore
      // In production, this would compare with last week's data
      return this.avgHealthScore;
    },
    trendDirection() {
      if (this.healthHistory.length < 2) return 0;
      const recent = this.healthHistory.slice(0, 5);
      const older = this.healthHistory.slice(5, 10);
      if (older.length === 0) return 0;
      const recentAvg = recent.reduce((sum, h) => sum + (h.score || (h.healthy ? 100 : 0)), 0) / recent.length;
      const olderAvg = older.reduce((sum, h) => sum + (h.score || (h.healthy ? 100 : 0)), 0) / older.length;
      return Math.round(recentAvg - olderAvg);
    },
    trendPoints() {
      if (this.healthHistory.length < 2) return '';
      const width = 600;
      const height = 100;
      const points = this.healthHistory.slice(0, 24).reverse().map((snapshot, idx) => {
        const x = (idx / (this.healthHistory.length - 1)) * width;
        const score = snapshot.score || (snapshot.healthy ? 100 : 0);
        const y = height - (score / 100) * height;
        return `${x},${y}`;
      });
      return points.join(' ');
    },
    trendColor() {
      if (this.trendDirection >= 0) return 'var(--success)';
      return 'var(--danger)';
    },
    trendDataPoints() {
      if (this.healthHistory.length < 2) return [];
      const width = 600;
      const height = 100;
      return this.healthHistory.slice(0, 24).reverse().map((snapshot, idx) => {
        const x = (idx / (this.healthHistory.length - 1)) * width;
        const score = snapshot.score || (snapshot.healthy ? 100 : 0);
        const y = height - (score / 100) * height;
        return { x, y, healthy: snapshot.healthy };
      });
    },
  },
  mounted() {
    this.loadHealthHistory();
    this.loadAlertingRules();
  },
  methods: {
    getStatusClass(isGood) {
      return isGood ? 'badge-success' : 'badge-danger';
    },
    getWarningClass(hasWarning) {
      return hasWarning ? 'badge-warning' : 'badge-success';
    },
    formatTime(time) {
      if (!time) return '-';
      return new Date(time).toLocaleString('zh-CN');
    },
    async runDiagnostics() {
      this.isRunning = true;
      try {
        // Fetch backend status
        const backendResp = await fetch('/api/backend/status');
        const backend = backendResp.ok ? await backendResp.json() : { running: false };

        // Fetch proxy stats
        const proxiesResp = await fetch('/api/proxies/stats');
        const proxies = proxiesResp.ok ? await proxiesResp.json() : { total: 0, available: 0 };

        // Fetch pool stats
        const poolsResp = await fetch('/api/pools');
        const poolsData = poolsResp.ok ? await poolsResp.json() : { items: [] };
        const pools = {
          total: poolsData.items?.length || 0,
          healthy: poolsData.items?.filter(p => p.enabled !== false).length || 0,
          unhealthy: poolsData.items?.filter(p => p.enabled === false).length || 0,
        };

        // Fetch gateway status
        const gatewayResp = await fetch('/api/gateway/status');
        const gateway = gatewayResp.ok ? await gatewayResp.json() : { running: false };

        // Generate issues list
        const issues = [];
        if (!backend.running) issues.push('后端进程未运行');
        if (!gateway.running) issues.push('网关服务未运行');
        if (pools.unhealthy > 0) issues.push(`${pools.unhealthy} 个代理池异常`);
        if (proxies.unavailable > 0) issues.push(`${proxies.unavailable} 个代理节点不可用`);

        this.report = {
          timestamp: new Date().toISOString(),
          backend: {
            running: backend.running || false,
            version: backend.version || '-',
            cpu: backend.system?.cpu_percent || 0,
            memory: backend.system?.memory_mb ? `${Math.round(backend.system.memory_mb)}MB` : '-',
          },
          gateway: {
            running: gateway.running || false,
            endpoints: gateway.endpoints?.length || 0,
            healthy: gateway.running || false,
          },
          pools,
          proxies: {
            total: proxies.total || 0,
            available: proxies.available || proxies.total || 0,
            unavailable: proxies.total - (proxies.available || proxies.total) || 0,
          },
          issues,
        };

        // Save to history
        this.saveToHistory(this.report);
        this.appState.setMessage('诊断完成');
      } catch (error) {
        this.appState.setMessage('诊断失败: ' + error.message, true);
      } finally {
        this.isRunning = false;
      }
    },
    exportReport() {
      if (!this.report) return;
      const lines = [
        '=== Proxy Pool 系统诊断报告 ===',
        `生成时间: ${this.formatTime(this.report.timestamp)}`,
        `健康评分: ${this.healthScore}/100`,
        '',
        '--- 后端进程 ---',
        `运行状态: ${this.report.backend.running ? '运行中' : '已停止'}`,
        `版本: ${this.report.backend.version}`,
        `CPU: ${this.report.backend.cpu}%`,
        `内存: ${this.report.backend.memory}`,
        '',
        '--- 网关服务 ---',
        `运行状态: ${this.report.gateway.running ? '运行中' : '已停止'}`,
        `端点数量: ${this.report.gateway.endpoints}`,
        '',
        '--- 代理池 ---',
        `总数: ${this.report.pools.total}`,
        `健康: ${this.report.pools.healthy}`,
        `异常: ${this.report.pools.unhealthy}`,
        '',
        '--- 代理节点 ---',
        `总数: ${this.report.proxies.total}`,
        `可用: ${this.report.proxies.available}`,
        `不可用: ${this.report.proxies.unavailable}`,
        '',
        '--- 健康对比 ---',
        `24小时平均: ${this.avgHealthScore}分`,
        `本周平均: ${this.weeklyAvgScore}分`,
        `趋势: ${this.trendDirection >= 0 ? '改善中' : '下降中'} (${this.trendDirection >= 0 ? '+' : ''}${this.trendDirection}分)`,
        '',
      ];

      if (this.report.issues.length) {
        lines.push('--- 发现的问题 ---');
        this.report.issues.forEach((issue, idx) => {
          lines.push(`${idx + 1}. ${issue}`);
        });
        lines.push('');
      }

      const content = lines.join('\n');
      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const now = new Date();
      a.download = `diagnosis-${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}-${String(now.getMinutes()).padStart(2, '0')}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      this.appState.setMessage('报告已导出');
    },
    saveToHistory(report) {
      const snapshot = {
        timestamp: report.timestamp,
        healthy: report.issues.length === 0,
        score: this.healthScore,
        summary: report.issues.length === 0 ? '全部正常' : report.issues[0],
      };
      this.healthHistory.unshift(snapshot);
      this.healthHistory = this.healthHistory.slice(0, 24);
      try {
        localStorage.setItem('pp-health-history', JSON.stringify(this.healthHistory));
      } catch {}
    },
    loadHealthHistory() {
      try {
        const saved = localStorage.getItem('pp-health-history');
        if (saved) {
          this.healthHistory = JSON.parse(saved);
        }
      } catch {}
    },
    saveAlertingRules() {
      try {
        localStorage.setItem('pp-alerting-rules', JSON.stringify(this.alertingRules));
      } catch {}
    },
    loadAlertingRules() {
      try {
        const saved = localStorage.getItem('pp-alerting-rules');
        if (saved) {
          this.alertingRules = JSON.parse(saved);
        }
      } catch {}
    },
  },
};
</script>

<style scoped>
.health-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.health-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  border: 1px solid var(--line-soft);
}

.health-label {
  font-size: 12px;
  color: var(--muted);
}

.health-status {
  font-size: 16px;
  font-weight: 600;
}

.diagnostic-section {
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--line-soft);
}

.diagnostic-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.diagnostic-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 12px;
}

.diagnostic-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.diagnostic-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--panel-muted);
  border-radius: var(--radius-sm);
}

.diagnostic-label {
  font-size: 13px;
  color: var(--muted);
}

.diagnostic-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.issues-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.issue-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-sm);
  color: #ef4444;
  font-size: 13px;
}

.issue-icon {
  font-size: 14px;
}

.report-meta {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line-soft);
  text-align: right;
}

.health-history {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: var(--panel-muted);
  border-radius: var(--radius-sm);
}

.history-time {
  min-width: 140px;
}

.history-status {
  min-width: 50px;
  font-weight: 600;
  font-size: 12px;
}

.history-summary {
  flex: 1;
}

.health-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.health-score-badge {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  background: var(--panel-muted);
  border: 2px solid var(--line-soft);
}

.health-score-label {
  font-size: 12px;
  color: var(--muted);
}

.health-score-value {
  font-size: 24px;
  font-weight: 700;
}

.health-score-max {
  font-size: 12px;
  color: var(--muted);
}

.score-excellent {
  border-color: var(--success);
  color: var(--success);
}

.score-good {
  border-color: var(--success-text);
  color: var(--success-text);
}

.score-fair {
  border-color: var(--warning-text);
  color: var(--warning-text);
}

.score-poor {
  border-color: var(--danger);
  color: var(--danger);
}

.health-trend-chart {
  padding: 16px 0;
}

.trend-svg {
  width: 100%;
  height: 100px;
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-sm);
  background: var(--panel-muted);
}

.trend-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
}

.health-comparison-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.comparison-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  border: 1px solid var(--line-soft);
}

.comparison-label {
  font-size: 12px;
  color: var(--muted);
}

.comparison-value {
  font-size: 14px;
  font-weight: 600;
}

.comparison-score {
  font-size: 18px;
  font-weight: 700;
}

.alerting-rules-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alerting-rule-item {
  padding: 16px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  border: 1px solid var(--line-soft);
}

.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.rule-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}

.rule-description {
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 8px;
}

.rule-condition {
  font-size: 12px;
  color: var(--muted);
  background: var(--panel-bg);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
}

.rule-threshold {
  font-weight: 500;
  color: var(--ink);
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--panel-bg);
  transition: .4s;
  border-radius: 24px;
  border: 1px solid var(--line-soft);
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 2px;
  bottom: 2px;
  background-color: var(--muted);
  transition: .4s;
  border-radius: 50%;
}

input:checked + .toggle-slider {
  background-color: var(--success);
  border-color: var(--success);
}

input:checked + .toggle-slider:before {
  transform: translateX(20px);
  background-color: white;
}

.text-green-600 {
  color: #16a34a;
}

.text-red-600 {
  color: #dc2626;
}

@media (max-width: 768px) {
  .health-summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .health-comparison-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .diagnostic-grid {
    grid-template-columns: 1fr;
  }
}
</style>
