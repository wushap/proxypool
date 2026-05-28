<template>
  <section class="dashboard-page fade-in">
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
          <select v-model.number="autoRefreshSec" class="select" style="width: 120px; height: 32px;" @change="onAutoRefreshChange" aria-label="自动刷新间隔">
            <option :value="0">手动刷新</option>
            <option :value="5">5 秒</option>
            <option :value="15">15 秒</option>
            <option :value="30">30 秒</option>
            <option :value="60">1 分钟</option>
          </select>
          <button class="btn btn-secondary" :disabled="isActionRunning('refreshDashboard')" @click="onRefreshDashboard" aria-label="刷新仪表盘数据">
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
        <!-- Protocol Distribution (Donut Chart) -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">协议分布</h3>
            <template v-if="protocolEntries.length">
              <div class="dashboard-donut-wrapper">
                <div class="dashboard-donut-chart">
                  <svg viewBox="0 0 120 120" class="dashboard-donut-svg">
                    <circle v-for="(seg, i) in protocolDonutSegments" :key="'donut-' + i"
                      cx="60" cy="60" r="45" fill="none"
                      :stroke="seg.color" stroke-width="20"
                      :stroke-dasharray="seg.dashArray"
                      :stroke-dashoffset="seg.dashOffset"
                      :style="{ transition: 'stroke-dasharray 0.5s ease, stroke-dashoffset 0.5s ease' }"
                    />
                  </svg>
                  <div class="dashboard-donut-center">
                    <span class="dashboard-donut-total">{{ stats.total ?? 0 }}</span>
                    <span class="dashboard-donut-label">节点</span>
                  </div>
                </div>
                <div class="dashboard-donut-legend">
                  <div v-for="p in protocolEntries" :key="'legend-' + p.name" class="dashboard-donut-legend-item">
                    <span class="dashboard-donut-legend-dot" :style="{ background: p.color }"></span>
                    <span class="dashboard-donut-legend-name">{{ p.name }}</span>
                    <span class="dashboard-donut-legend-value">{{ p.count }}</span>
                    <span class="dashboard-donut-legend-pct">{{ p.pct }}%</span>
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
            <h3 class="card-title">国家/地区分布 <span class="text-muted" style="font-size: 12px; font-weight: 400;">Top 10</span></h3>
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
                <span class="dashboard-status-label">网关服务</span>
                <span class="badge" :class="gatewayRunning ? 'badge-success' : 'badge-neutral'">
                  {{ gatewayRunning ? '运行中' : '未启动' }}
                </span>
              </div>
              <div class="dashboard-status-row">
                <span class="dashboard-status-label">健康代理池</span>
                <span class="font-semibold">{{ healthyPoolCount }} / {{ poolCount }}</span>
              </div>
              <div class="dashboard-status-row">
                <span class="dashboard-status-label">活跃端口</span>
                <span class="font-semibold">{{ activeEndpointCount }}</span>
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
                <span class="dashboard-status-label">测试通过率</span>
                <span class="font-semibold" :class="testPassRate >= 80 ? 'text-emerald-600' : testPassRate >= 50 ? 'text-amber-600' : 'text-red-600'">
                  {{ testPassRate }}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Latency Distribution + Pool Health -->
      <div class="dashboard-grid" style="margin-top: 12px;">
        <!-- Latency Distribution Histogram -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">延迟分布 <span class="text-muted" style="font-size: 12px; font-weight: 400;">{{ latencyTotal }} 个已测速节点</span></h3>
            <template v-if="latencyTotal > 0">
              <div class="dashboard-histogram">
                <div v-for="bucket in latencyDistribution" :key="bucket.label" class="dashboard-histogram-bar-wrapper">
                  <div class="dashboard-histogram-bar-track">
                    <div class="dashboard-histogram-bar" :style="{ width: bucket.pct + '%', background: bucket.color }"></div>
                  </div>
                  <div class="dashboard-histogram-label">
                    <span class="dashboard-histogram-range">{{ bucket.label }}</span>
                    <span class="dashboard-histogram-count">{{ bucket.count }}</span>
                  </div>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无延迟数据" description="请先运行节点测速" size="small">
              <template #actions>
                <button class="btn btn-xs btn-secondary" @click="goToTasks">执行测速</button>
              </template>
            </EmptyState>
          </div>
        </div>

        <!-- Pool Health Overview -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">代理池健康概览</h3>
            <template v-if="poolHealthEntries.length">
              <div class="dashboard-pool-health">
                <div v-for="pool in poolHealthEntries" :key="'pool-health-' + pool.name" class="dashboard-pool-health-row">
                  <div class="dashboard-pool-health-info">
                    <span class="dashboard-pool-health-dot" :style="{ background: pool.color }"></span>
                    <span class="dashboard-pool-health-name">{{ pool.name }}</span>
                  </div>
                  <div class="dashboard-pool-health-meta">
                    <span class="dashboard-pool-health-nodes">{{ pool.nodeCount }} 节点</span>
                    <span class="badge badge-sm" :class="pool.status === 'running' ? 'badge-success' : pool.status === 'degraded' ? 'badge-warning' : 'badge-neutral'">
                      {{ pool.status === 'running' ? '运行中' : pool.status === 'degraded' ? '降级' : pool.status || '未知' }}
                    </span>
                  </div>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无代理池" size="small">
              <template #actions>
                <button class="btn btn-xs btn-secondary" @click="goToProxyPools">创建代理池</button>
              </template>
            </EmptyState>
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

      <!-- Activity Feed -->
      <div class="card" style="margin-top: 12px;">
        <div class="card-body">
          <h3 class="card-title" style="margin-bottom: 10px;">最近活动</h3>
          <template v-if="activityFeed.length">
            <div class="activity-feed">
              <div v-for="(activity, index) in activityFeed" :key="'activity-' + index" class="activity-item">
                <div class="activity-dot" :class="activity.type"></div>
                <div class="activity-content">
                  <p class="activity-title">{{ activity.title }}</p>
                  <p v-if="activity.description" class="activity-description">{{ activity.description }}</p>
                  <p v-if="activity.time" class="activity-time">{{ formatActivityTime(activity.time) }}</p>
                </div>
              </div>
            </div>
          </template>
          <EmptyState v-else title="暂无活动记录" size="small" />
        </div>
      </div>

      <!-- Recent Events Timeline -->
      <div class="card" style="margin-top: 12px;">
        <div class="card-body">
          <h3 class="card-title" style="margin-bottom: 10px;">最近事件</h3>
          <template v-if="recentEvents.length">
            <div class="dashboard-events-timeline">
              <div v-for="(event, index) in recentEvents" :key="'event-' + index" class="dashboard-event-item">
                <span class="dashboard-event-icon">{{ event.icon }}</span>
                <div class="dashboard-event-content">
                  <span class="dashboard-event-message">{{ event.message }}</span>
                  <span v-if="event.time" class="dashboard-event-time">{{ formatActivityTime(event.time) }}</span>
                </div>
              </div>
            </div>
          </template>
          <EmptyState v-else title="暂无事件记录" size="small" />
        </div>
      </div>

      <!-- Pool Status Grid + System Uptime -->
      <div class="dashboard-grid" style="margin-top: 12px;">
        <!-- Pool Status Grid -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">代理池状态</h3>
            <template v-if="poolStatusGrid.length">
              <div class="dashboard-pool-status-grid">
                <div v-for="pool in poolStatusGrid" :key="'pool-status-' + pool.name" class="dashboard-pool-status-item">
                  <span class="dashboard-pool-status-dot" :style="{ background: pool.color }"></span>
                  <span class="dashboard-pool-status-name">{{ pool.name }}</span>
                  <span class="dashboard-pool-status-count">{{ pool.nodeCount }} 节点</span>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无代理池" size="small" />
          </div>
        </div>

        <!-- System Uptime + Action History -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">系统信息</h3>
            <div class="dashboard-system-info">
              <div class="dashboard-system-info-row">
                <span class="dashboard-system-info-label">系统运行时间</span>
                <span class="dashboard-system-info-value font-semibold">{{ systemUptime || '未知' }}</span>
              </div>
              <div class="dashboard-system-info-row">
                <span class="dashboard-system-info-label">后端版本</span>
                <span class="dashboard-system-info-value">{{ backendStatus?.version || '-' }}</span>
              </div>
              <div class="dashboard-system-info-row">
                <span class="dashboard-system-info-label">实例 ID</span>
                <span class="dashboard-system-info-value mono text-xs">{{ backendStatus?.instance_id || 'default' }}</span>
              </div>
            </div>
            <h4 class="dashboard-sub-title" style="margin-top: 16px;">快速操作历史</h4>
            <template v-if="actionHistory.length">
              <div class="dashboard-action-history">
                <div v-for="(item, index) in actionHistory" :key="'action-' + index" class="dashboard-action-item">
                  <span class="dashboard-action-name">{{ item.action }}</span>
                  <span class="dashboard-action-time">{{ formatActionTime(item.time) }}</span>
                </div>
              </div>
            </template>
            <span v-else class="text-muted text-xs">暂无操作记录</span>
          </div>
        </div>
      </div>

      <!-- Real-time Monitoring -->
      <div class="card" style="margin-top: 12px;">
        <div class="card-body">
          <h3 class="card-title" style="margin-bottom: 12px;">实时监控</h3>
          <div class="stat-grid" style="grid-template-columns: repeat(4, 1fr);">
            <StatCard
              label="活跃连接"
              :value="activeConnections"
              description="当前活跃连接数"
              color="var(--info-text)"
            />
            <StatCard
              label="总连接数"
              :value="totalConnections"
              description="累计连接数"
            />
            <StatCard
              label="请求速率"
              :value="requestRateDisplay"
              description="最近请求速率"
            />
            <StatCard
              label="错误率"
              :value="errorRateDisplay"
              description="错误/总请求"
              :color="errorRate > 10 ? 'var(--danger-text)' : errorRate > 5 ? 'var(--warning-text)' : 'var(--success-text)'"
            />
          </div>
          <div class="stat-grid" style="grid-template-columns: repeat(4, 1fr); margin-top: 8px;">
            <StatCard
              label="带宽使用"
              :value="bandwidthDisplay"
              description="估计带宽使用量"
            />
            <StatCard
              label="最近错误"
              :value="recentErrorCount"
              description="最近10条错误"
              :color="recentErrorCount > 0 ? 'var(--danger-text)' : 'var(--success-text)'"
            />
            <StatCard
              label="网关状态"
              :value="gatewayRunning ? '运行中' : '已停止'"
              :color="gatewayRunning ? 'var(--success-text)' : 'var(--danger-text)'"
            />
            <StatCard
              label="刷新间隔"
              :value="autoRefreshSec > 0 ? autoRefreshSec + '秒' : '手动'"
              description="自动刷新频率"
            />
          </div>
        </div>
      </div>

      <!-- System Diagnostics -->
      <div class="card" style="margin-top: 12px;">
        <div class="card-body">
          <div class="diagnostics-header" @click="diagnosticsExpanded = !diagnosticsExpanded" style="cursor: pointer;">
            <h3 class="card-title" style="margin: 0;">
              <span style="margin-right: 8px;">&#128269;</span>系统诊断
              <span class="text-muted text-xs" style="margin-left: 8px;">{{ diagnosticsExpanded ? '点击收起' : '点击展开' }}</span>
            </h3>
          </div>

          <div v-if="diagnosticsExpanded" style="margin-top: 16px;">
            <!-- Diagnostic Controls -->
            <div class="diagnostics-controls">
              <button @click="runDiagnostics" :disabled="isRunningDiagnostics" class="btn btn-primary" aria-label="运行系统诊断">
                {{ isRunningDiagnostics ? diagnosticProgress || '诊断中...' : '一键诊断' }}
              </button>
              <button @click="exportDiagnosticReport" :disabled="!diagnosticReport" class="btn btn-secondary" aria-label="导出诊断报告">
                导出报告
              </button>
              <div v-if="diagnosticReport" class="dashboard-health-score" :class="diagnosticHealthScoreClass">
                <span class="health-score-label">健康评分</span>
                <span class="health-score-value">{{ diagnosticHealthScore }}</span>
                <span class="health-score-max">/100</span>
              </div>
            </div>

            <!-- Diagnostic Report -->
            <div v-if="diagnosticReport" class="diagnostic-report">
              <!-- Backend Status -->
              <div class="diagnostic-section">
                <h4 class="diagnostic-section-title">后端进程</h4>
                <div class="diagnostic-grid">
                  <div class="diagnostic-item">
                    <span class="diagnostic-label">状态</span>
                    <span class="diagnostic-value" :class="diagnosticReport.backend.running ? 'text-green-600' : 'text-red-600'">
                      {{ diagnosticReport.backend.running ? '运行中' : '已停止' }}
                    </span>
                  </div>
                  <div class="diagnostic-item">
                    <span class="diagnostic-label">PID</span>
                    <span class="diagnostic-value mono">{{ diagnosticReport.backend.pid || '-' }}</span>
                  </div>
                  <div class="diagnostic-item">
                    <span class="diagnostic-label">内存</span>
                    <span class="diagnostic-value mono">{{ diagnosticReport.backend.memory || '-' }}</span>
                  </div>
                  <div class="diagnostic-item">
                    <span class="diagnostic-label">运行时间</span>
                    <span class="diagnostic-value mono">{{ diagnosticReport.backend.uptime || '-' }}</span>
                  </div>
                </div>
              </div>

              <!-- Gateway Status -->
              <div class="diagnostic-section">
                <h4 class="diagnostic-section-title">网关状态</h4>
                <div class="diagnostic-grid">
                  <div class="diagnostic-item">
                    <span class="diagnostic-label">状态</span>
                    <span class="diagnostic-value" :class="diagnosticReport.gateway.running ? 'text-green-600' : 'text-red-600'">
                      {{ diagnosticReport.gateway.running ? '运行中' : '已停止' }}
                    </span>
                  </div>
                  <div class="diagnostic-item">
                    <span class="diagnostic-label">端口</span>
                    <span class="diagnostic-value mono">{{ diagnosticReport.gateway.port || '-' }}</span>
                  </div>
                  <div class="diagnostic-item">
                    <span class="diagnostic-label">活跃连接</span>
                    <span class="diagnostic-value mono">{{ diagnosticReport.gateway.connections || 0 }}</span>
                  </div>
                </div>
              </div>

              <!-- Database Status -->
              <div class="diagnostic-section">
                <h4 class="diagnostic-section-title">数据库</h4>
                <div class="diagnostic-grid">
                  <div class="diagnostic-item">
                    <span class="diagnostic-label">大小</span>
                    <span class="diagnostic-value mono">{{ diagnosticReport.database.size || '-' }}</span>
                  </div>
                  <div class="diagnostic-item">
                    <span class="diagnostic-label">连接数</span>
                    <span class="diagnostic-value mono">{{ diagnosticReport.database.connections || 0 }}</span>
                  </div>
                </div>
              </div>

              <!-- Storage Status -->
              <div class="diagnostic-section">
                <h4 class="diagnostic-section-title">存储</h4>
                <div class="diagnostic-grid">
                  <div class="diagnostic-item">
                    <span class="diagnostic-label">磁盘使用</span>
                    <span class="diagnostic-value mono">{{ diagnosticReport.storage.disk_usage || '-' }}</span>
                  </div>
                </div>
              </div>

              <!-- Summary -->
              <div class="diagnostic-summary">
                <div class="diagnostic-summary-item">
                  <span class="text-muted">代理池:</span>
                  <span class="mono">{{ diagnosticReport.pools.total }}个 ({{ diagnosticReport.pools.healthy }}个健康, {{ diagnosticReport.pools.degraded }}个降级)</span>
                </div>
                <div class="diagnostic-summary-item">
                  <span class="text-muted">代理节点:</span>
                  <span class="mono">{{ diagnosticReport.proxies.total }}个 ({{ diagnosticReport.proxies.available }}个可用)</span>
                </div>
                <div class="diagnostic-summary-item">
                  <span class="text-muted">订阅源:</span>
                  <span class="mono">{{ diagnosticReport.subscriptions.total }}个 ({{ diagnosticReport.subscriptions.healthy }}个正常, {{ diagnosticReport.subscriptions.failed }}个失败)</span>
                </div>
              </div>

              <div class="text-muted text-xs" style="margin-top: 12px;">
                生成时间: {{ diagnosticReport.timestamp }}
              </div>
            </div>

            <div v-else-if="!isRunningDiagnostics" class="empty-state-small" style="margin-top: 16px;">
              <p class="text-muted">点击「一键诊断」按钮开始系统健康检查</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Advanced Data Visualizations -->
      <div class="dashboard-grid" style="margin-top: 12px;">
        <!-- Latency Trend Chart -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">延迟趋势 <span class="text-muted" style="font-size: 12px; font-weight: 400;">最近 {{ latencyTrendData?.count || 0 }} 个节点</span></h3>
            <template v-if="latencyTrendData">
              <div class="dashboard-latency-trend">
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" class="dashboard-trend-svg">
                  <!-- Grid lines -->
                  <line x1="0" y1="25" x2="100" y2="25" stroke="var(--line-soft)" stroke-width="0.5" stroke-dasharray="2,2" />
                  <line x1="0" y1="50" x2="100" y2="50" stroke="var(--line-soft)" stroke-width="0.5" stroke-dasharray="2,2" />
                  <line x1="0" y1="75" x2="100" y2="75" stroke="var(--line-soft)" stroke-width="0.5" stroke-dasharray="2,2" />
                  <!-- Gradient fill -->
                  <defs>
                    <linearGradient id="latencyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" stop-color="#6366f1" stop-opacity="0.3" />
                      <stop offset="100%" stop-color="#6366f1" stop-opacity="0" />
                    </linearGradient>
                  </defs>
                  <path :d="latencyTrendData.pathData + ' L 100 100 L 0 100 Z'" fill="url(#latencyGradient)" />
                  <!-- Line -->
                  <path :d="latencyTrendData.pathData" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                  <!-- Data points -->
                  <circle v-for="(pt, i) in latencyTrendData.points" :key="'trend-pt-' + i"
                    :cx="pt.x" :cy="pt.y" r="1.5" fill="#6366f1" stroke="white" stroke-width="0.5" />
                </svg>
                <div class="dashboard-trend-labels">
                  <span class="dashboard-trend-label">高</span>
                  <span class="dashboard-trend-label">{{ latencyTrendData.maxLatency }}ms</span>
                  <span class="dashboard-trend-label">低</span>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无延迟数据" description="请先运行节点测速" size="small">
              <template #actions>
                <button class="btn btn-xs btn-secondary" @click="goToTasks">执行测速</button>
              </template>
            </EmptyState>
          </div>
        </div>

        <!-- Pool Health Heatmap -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">代理池健康热图 <span class="text-muted" style="font-size: 12px; font-weight: 400;">最近12小时</span></h3>
            <template v-if="poolHealthHeatmap">
              <div class="dashboard-heatmap">
                <div v-for="(row, ri) in poolHealthHeatmap.rows" :key="'heatmap-row-' + ri" class="dashboard-heatmap-row">
                  <span class="dashboard-heatmap-label" :title="row.name">{{ row.name.substring(0, 8) }}</span>
                  <div class="dashboard-heatmap-cells">
                    <div v-for="(cell, ci) in row.cells" :key="'heatmap-cell-' + ri + '-' + ci"
                      class="dashboard-heatmap-cell"
                      :style="{ background: getHeatmapColor(cell) }"
                      :title="`${row.name}: ${Math.round(cell * 100)}% 健康度`">
                    </div>
                  </div>
                  <span class="dashboard-heatmap-status badge badge-sm" :class="row.status === 'running' ? 'badge-success' : row.status === 'degraded' ? 'badge-warning' : 'badge-danger'">
                    {{ row.status === 'running' ? '✓' : row.status === 'degraded' ? '!' : '✗' }}
                  </span>
                </div>
                <div class="dashboard-heatmap-legend">
                  <span class="dashboard-heatmap-legend-label">不健康</span>
                  <div class="dashboard-heatmap-legend-gradient"></div>
                  <span class="dashboard-heatmap-legend-label">健康</span>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无代理池数据" size="small">
              <template #actions>
                <button class="btn btn-xs btn-secondary" @click="goToProxyPools">创建代理池</button>
              </template>
            </EmptyState>
          </div>
        </div>
      </div>

      <!-- Geo Distribution + Bandwidth -->
      <div class="dashboard-grid" style="margin-top: 12px;">
        <!-- Geo Distribution Map -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">地理位置分布</h3>
            <template v-if="geoDistributionMap">
              <div class="dashboard-geo-map">
                <div class="dashboard-geo-regions">
                  <div v-for="region in geoDistributionMap.regions" :key="'geo-' + region.name" class="dashboard-geo-region">
                    <div class="dashboard-geo-region-header">
                      <span class="dashboard-geo-region-name">{{ region.name }}</span>
                      <span class="dashboard-geo-region-count">{{ region.count }} 节点</span>
                    </div>
                    <div class="dashboard-bar-track">
                      <div class="dashboard-bar-fill" :style="{ width: region.pct + '%', background: getGeoRegionColor(region.name) }"></div>
                    </div>
                    <span class="dashboard-geo-region-pct">{{ region.pct }}%</span>
                  </div>
                </div>
                <div class="dashboard-geo-summary">
                  <span class="text-muted text-xs">共 {{ geoDistributionMap.total }} 个节点分布在 {{ geoDistributionMap.regions.length }} 个区域</span>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无地理位置数据" description="请先运行 IP 位置补全" size="small">
              <template #actions>
                <button class="btn btn-xs btn-secondary" @click="onEnrichGeo">补全 IP 位置</button>
              </template>
            </EmptyState>
          </div>
        </div>

        <!-- Bandwidth Distribution -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">带宽分布</h3>
            <template v-if="bandwidthChartData">
              <div class="dashboard-bandwidth-chart">
                <div v-for="bucket in bandwidthChartData" :key="'bw-' + bucket.label" class="dashboard-bandwidth-bar-wrapper">
                  <div class="dashboard-bandwidth-bar-track">
                    <div class="dashboard-bandwidth-bar" :style="{ width: bucket.pct + '%', background: bucket.color }"></div>
                  </div>
                  <div class="dashboard-bandwidth-label">
                    <span class="dashboard-bandwidth-range">{{ bucket.label }}</span>
                    <span class="dashboard-bandwidth-count">{{ bucket.count }} <span class="text-muted">({{ bucket.totalPct }}%)</span></span>
                  </div>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无带宽数据" description="请先运行节点测速" size="small">
              <template #actions>
                <button class="btn btn-xs btn-secondary" @click="goToTasks">执行测速</button>
              </template>
            </EmptyState>
          </div>
        </div>
      </div>

      <!-- Advanced Analytics Section -->
      <div class="dashboard-grid" style="margin-top: 12px;">
        <!-- Success Rate Trend -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">成功率趋势 <span class="text-muted" style="font-size: 12px; font-weight: 400;">最近24小时</span></h3>
            <template v-if="successRateTrendData">
              <div class="dashboard-latency-trend">
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" class="dashboard-trend-svg">
                  <defs>
                    <linearGradient id="successRateGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" stop-color="#16a34a" stop-opacity="0.3" />
                      <stop offset="100%" stop-color="#16a34a" stop-opacity="0" />
                    </linearGradient>
                  </defs>
                  <path :d="successRateTrendData.pathData + ' L 100 100 L 0 100 Z'" fill="url(#successRateGradient)" />
                  <path :d="successRateTrendData.pathData" fill="none" stroke="#16a34a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                  <circle v-for="(pt, i) in successRateTrendData.points" :key="'success-pt-' + i"
                    :cx="pt.x" :cy="pt.y" r="1.5" fill="#16a34a" stroke="white" stroke-width="0.5" />
                </svg>
                <div class="dashboard-trend-labels">
                  <span class="dashboard-trend-label">100%</span>
                  <span class="dashboard-trend-label">50%</span>
                  <span class="dashboard-trend-label">0%</span>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无成功率数据" size="small" />
          </div>
        </div>

        <!-- Latency by Protocol -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">协议延迟对比</h3>
            <template v-if="latencyByProtocol">
              <div class="dashboard-latency-by-protocol">
                <div v-for="proto in latencyByProtocol" :key="'proto-lat-' + proto.name" class="dashboard-protocol-latency-row">
                  <div class="dashboard-protocol-latency-info">
                    <span class="dashboard-protocol-latency-name">{{ proto.name }}</span>
                    <span class="dashboard-protocol-latency-value">{{ proto.avgLatency }}ms</span>
                  </div>
                  <div class="dashboard-bar-track">
                    <div class="dashboard-bar-fill" :style="{ width: proto.pct + '%', background: '#6366f1' }"></div>
                  </div>
                  <div class="dashboard-protocol-latency-meta">
                    <span class="text-xs text-muted">{{ proto.count }} 节点</span>
                  </div>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无协议延迟数据" size="small" />
          </div>
        </div>
      </div>

      <!-- Top Proxies + Geo Latency -->
      <div class="dashboard-grid" style="margin-top: 12px;">
        <!-- Top 10 Fastest -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">Top 10 最快节点</h3>
            <template v-if="topFastestProxies.length">
              <div class="dashboard-top-proxies">
                <div v-for="proxy in topFastestProxies" :key="'fast-' + proxy.rank" class="dashboard-top-proxy-item">
                  <span class="dashboard-top-proxy-rank">#{{ proxy.rank }}</span>
                  <div class="dashboard-top-proxy-info">
                    <span class="dashboard-top-proxy-name">{{ proxy.name }}</span>
                    <span class="dashboard-top-proxy-meta">{{ proxy.protocol }} | {{ proxy.country }}</span>
                  </div>
                  <span class="dashboard-top-proxy-latency text-emerald-600 font-semibold">{{ proxy.latency }}ms</span>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无可用节点" size="small" />
          </div>
        </div>

        <!-- Top 10 Slowest -->
        <div class="card">
          <div class="card-body">
            <h3 class="card-title">Top 10 最慢节点</h3>
            <template v-if="topSlowestProxies.length">
              <div class="dashboard-top-proxies">
                <div v-for="proxy in topSlowestProxies" :key="'slow-' + proxy.rank" class="dashboard-top-proxy-item">
                  <span class="dashboard-top-proxy-rank">#{{ proxy.rank }}</span>
                  <div class="dashboard-top-proxy-info">
                    <span class="dashboard-top-proxy-name">{{ proxy.name }}</span>
                    <span class="dashboard-top-proxy-meta">{{ proxy.protocol }} | {{ proxy.country }}</span>
                  </div>
                  <span class="dashboard-top-proxy-latency text-rose-600 font-semibold">{{ proxy.latency }}ms</span>
                </div>
              </div>
            </template>
            <EmptyState v-else title="暂无可用节点" size="small" />
          </div>
        </div>
      </div>

      <!-- Geo Latency Comparison -->
      <div class="card" style="margin-top: 12px;">
        <div class="card-body">
          <h3 class="card-title">地区延迟对比</h3>
          <template v-if="geoLatencyComparison">
            <div class="dashboard-geo-latency-comparison">
              <div v-for="region in geoLatencyComparison" :key="'geo-lat-' + region.name" class="dashboard-geo-latency-item">
                <div class="dashboard-geo-latency-header">
                  <span class="dashboard-geo-latency-region">{{ region.name }}</span>
                  <span class="dashboard-geo-latency-value">{{ region.avgLatency }}ms</span>
                </div>
                <div class="dashboard-bar-track">
                  <div class="dashboard-bar-fill" :style="{ width: region.pct + '%', background: getGeoRegionColor(region.name) }"></div>
                </div>
                <div class="dashboard-geo-latency-meta">
                  <span class="text-xs text-muted">{{ region.count }} 节点 ({{ region.availableCount }} 可用)</span>
                </div>
              </div>
            </div>
          </template>
          <EmptyState v-else title="暂无地区延迟数据" description="请先运行 IP 位置补全" size="small">
            <template #actions>
              <button class="btn btn-xs btn-secondary" @click="onEnrichGeo">补全 IP 位置</button>
            </template>
          </EmptyState>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="card" style="margin-top: 12px;">
        <div class="card-body">
          <h3 class="card-title" style="margin-bottom: 10px;">快速操作</h3>
          <div class="action-bar">
            <button class="btn btn-primary" @click="goToTasks" aria-label="打开任务中心">任务中心</button>
            <button class="btn btn-secondary" @click="goToProxyPools" aria-label="创建新的代理池">创建代理池</button>
            <button class="btn btn-secondary" @click="goToPorts" aria-label="添加入站端口">添加入站端口</button>
            <button class="btn btn-secondary" @click="triggerImportNodes" aria-label="导入代理节点">导入节点</button>
            <button class="btn btn-secondary" @click="goToSubscriptions" aria-label="管理订阅源">订阅管理</button>
            <button class="btn btn-secondary" @click="goToProxies" aria-label="查看代理节点列表">代理节点</button>
            <button class="btn btn-secondary" @click="copyAvailableSubscription" aria-label="复制可用代理链接到剪贴板">复制可用代理</button>
            <a href="/api/subscription?only_available=true" target="_blank" class="btn btn-secondary" aria-label="导出订阅链接（新窗口打开）">导出订阅</a>
            <button class="btn btn-secondary" @click="onRefreshAllSubscriptions" :disabled="isActionRunning('refreshAllSubscriptions')" aria-label="刷新所有订阅源">
              {{ buttonLabel('refreshAllSubscriptions', '一键刷新所有', '刷新中...') }}
            </button>
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
      proxyCountTimer: null,
      isLoading: true,
      actionHistory: [],
      diagnosticsExpanded: false,
      isRunningDiagnostics: false,
      diagnosticProgress: '',
      diagnosticReport: null,
    };
  },
  watch: {
    async activePage(val) {
      if (val === 'dashboard') {
        this.isLoading = true;
        try {
          await Promise.all([
            this.appState.loadData(),
            this.appState.loadGatewayStatus(),
          ]);
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
      await Promise.all([
        this.appState.loadData(),
        this.appState.loadGatewayStatus(),
      ]);
      await this.appState.refreshTaskList({ force: true });
    } finally {
      this.isLoading = false;
    }
    this.loadActionHistory();
    if (this.autoRefreshSec > 0 && this.activePage === 'dashboard') {
      this.startAutoRefresh();
    }
    this.startProxyCountTicker();
  },
  beforeUnmount() {
    this.stopAutoRefresh();
    this.stopProxyCountTicker();
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
    gatewayRunning() {
      return this.appState.gatewayStatus?.endpoint_runtime?.running === true;
    },
    activeConnections() {
      const summary = this.appState.gatewayStatus?.summary || {};
      return summary.active_connections || 0;
    },
    totalConnections() {
      const summary = this.appState.gatewayStatus?.summary || {};
      return summary.total_connections || 0;
    },
    recentErrorCount() {
      const summary = this.appState.gatewayStatus?.summary || {};
      const errors = summary.recent_errors || [];
      return errors.length;
    },
    requestRate() {
      const summary = this.appState.gatewayStatus?.summary || {};
      return summary.requests_per_second || 0;
    },
    requestRateDisplay() {
      const rate = this.requestRate;
      if (rate === 0) return '0';
      return rate >= 1 ? rate.toFixed(1) : rate.toFixed(2);
    },
    errorRate() {
      const summary = this.appState.gatewayStatus?.summary || {};
      const total = summary.total_requests || 0;
      const errors = summary.total_errors || 0;
      if (total === 0) return 0;
      return (errors / total) * 100;
    },
    errorRateDisplay() {
      const rate = this.errorRate;
      return rate.toFixed(1) + '%';
    },
    bandwidthDisplay() {
      const summary = this.appState.gatewayStatus?.summary || {};
      const bytes = summary.bandwidth_bytes || 0;
      if (bytes === 0) return '0 B';
      const units = ['B', 'KB', 'MB', 'GB', 'TB'];
      let idx = 0;
      let size = bytes;
      while (size >= 1024 && idx < units.length - 1) {
        size /= 1024;
        idx++;
      }
      return size.toFixed(idx === 0 ? 0 : 1) + ' ' + units[idx];
    },
    diagnosticHealthScore() {
      if (!this.diagnosticReport) return 0;
      let score = 0;
      // Backend running: 25 points
      if (this.diagnosticReport.backend?.running) score += 25;
      // Gateway running: 25 points
      if (this.diagnosticReport.gateway?.running) score += 25;
      // Pool health: 25 points
      if (this.diagnosticReport.pools?.total > 0) {
        score += Math.round((this.diagnosticReport.pools.healthy / this.diagnosticReport.pools.total) * 25);
      } else {
        score += 25;
      }
      // Proxy availability: 25 points
      if (this.diagnosticReport.proxies?.total > 0) {
        score += Math.round((this.diagnosticReport.proxies.available / this.diagnosticReport.proxies.total) * 25);
      } else {
        score += 25;
      }
      return score;
    },
    diagnosticHealthScoreClass() {
      if (this.diagnosticHealthScore >= 90) return 'score-excellent';
      if (this.diagnosticHealthScore >= 70) return 'score-good';
      if (this.diagnosticHealthScore >= 50) return 'score-fair';
      return 'score-poor';
    },
    healthyPoolCount() {
      return (this.proxyPools || []).filter(p => p.status === 'running').length;
    },
    poolCount() {
      return (this.proxyPools || []).length;
    },
    activeEndpointCount() {
      return (this.appState.gatewayEndpoints || []).filter(ep => ep.enabled).length;
    },
    testPassRate() {
      const total = this.stats?.checked ?? 0;
      const available = this.stats?.available ?? 0;
      return total > 0 ? Math.round((available / total) * 100) : 0;
    },
    activityFeed() {
      const activities = [];
      const recentTasks = (this.taskItems || []).slice(0, 3);
      recentTasks.forEach(task => {
        const status = String(task.status || '');
        const type = String(task.task_type || '');
        let typeText = '任务';
        if (type === 'test' || type === 'speed_test') typeText = '测速';
        else if (type === 'geo') typeText = 'IP补全';
        else if (type === 'ip_purity') typeText = '纯净度检测';
        else if (type === 'openai') typeText = 'ChatGPT检测';
        else if (type === 'subscription_refresh') typeText = '订阅刷新';
        let statusClass = 'info';
        if (status === 'completed' || status === 'done') statusClass = 'success';
        else if (status === 'failed' || status === 'error') statusClass = 'error';
        else if (status === 'running') statusClass = 'warning';
        activities.push({
          title: `${typeText}: ${task.name || task.id || '-'}`,
          description: task.progress_total > 0 ? `${task.progress_current || 0}/${task.progress_total}` : (task.error || ''),
          time: task.started_at || task.created_at,
          type: statusClass,
        });
      });
      if (this.poolCount > 0) {
        activities.unshift({
          title: `代理池状态: ${this.healthyPoolCount} 个运行中`,
          description: `共 ${this.poolCount} 个代理池`,
          time: null,
          type: this.healthyPoolCount === this.poolCount ? 'success' : 'warning',
        });
      }
      return activities.slice(0, 5);
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
      const entries = Object.entries(bc).sort((a, b) => b[1] - a[1]).slice(0, 10);
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
    protocolDonutSegments() {
      const entries = this.protocolEntries;
      const total = entries.reduce((s, e) => s + e.count, 0);
      if (!total) return [];
      const circumference = 2 * Math.PI * 45; // r=45
      let offset = 0;
      return entries.map(entry => {
        const pct = entry.count / total;
        const dashLen = pct * circumference;
        const gap = circumference - dashLen;
        const seg = {
          color: entry.color,
          dashArray: `${dashLen} ${gap}`,
          dashOffset: -offset,
        };
        offset += dashLen;
        return seg;
      });
    },
    latencyDistribution() {
      const proxies = this.appState.allProxies || [];
      const buckets = [
        { label: '<100ms', min: 0, max: 100, count: 0, color: '#16a34a' },
        { label: '100-300ms', min: 100, max: 300, count: 0, color: '#0891b2' },
        { label: '300-500ms', min: 300, max: 500, count: 0, color: '#ca8a04' },
        { label: '500-1000ms', min: 500, max: 1000, count: 0, color: '#f97316' },
        { label: '>1000ms', min: 1000, max: Infinity, count: 0, color: '#dc2626' },
      ];
      proxies.forEach(p => {
        const ms = p.latency_ms;
        if (ms == null) return;
        for (const b of buckets) {
          if (ms >= b.min && ms < b.max) { b.count++; break; }
        }
      });
      const maxCount = Math.max(...buckets.map(b => b.count), 1);
      return buckets.map(b => ({
        ...b,
        pct: Math.round((b.count / maxCount) * 100),
      }));
    },
    latencyTotal() {
      return (this.appState.allProxies || []).filter(p => p.latency_ms != null).length;
    },
    poolHealthEntries() {
      const pools = this.proxyPools || [];
      if (!pools.length) return [];
      return pools.map(p => {
        const status = String(p.status || '');
        let color = '#9ca3af';
        if (status === 'running') color = '#16a34a';
        else if (status === 'degraded') color = '#ca8a04';
        else if (status === 'stopped' || status === 'error') color = '#dc2626';
        return {
          name: p.name || `Pool #${p.id}`,
          status,
          color,
          nodeCount: p.node_count ?? p.proxy_count ?? 0,
        };
      });
    },
    recentEvents() {
      const events = this.appState.backendEvents || [];
      return events.slice(0, 10).map(event => {
        let icon = '📋';
        let type = 'info';
        const eventType = String(event.event_type || '').toLowerCase();
        if (eventType.includes('error') || eventType.includes('fail')) {
          icon = '❌';
          type = 'error';
        } else if (eventType.includes('start') || eventType.includes('create')) {
          icon = '▶️';
          type = 'success';
        } else if (eventType.includes('stop') || eventType.includes('delete')) {
          icon = '⏹️';
          type = 'warning';
        } else if (eventType.includes('update')) {
          icon = '✏️';
          type = 'info';
        }
        return {
          icon,
          type,
          message: event.message || event.event_type || '事件',
          time: event.timestamp || event.created_at,
        };
      });
    },
    systemUptime() {
      const startTime = this.backendStatus?.started_at || this.backendStatus?.start_time;
      if (!startTime) return null;
      const start = new Date(startTime).getTime();
      const now = Date.now();
      const diff = Math.max(0, now - start);
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      if (days > 0) return `${days}天 ${hours}小时`;
      if (hours > 0) return `${hours}小时 ${minutes}分钟`;
      return `${minutes}分钟`;
    },
    poolStatusGrid() {
      const pools = this.proxyPools || [];
      return pools.map(p => {
        const status = String(p.status || '');
        let color = '#9ca3af';
        let statusText = '未知';
        if (status === 'running') {
          color = '#16a34a';
          statusText = '运行中';
        } else if (status === 'degraded') {
          color = '#ca8a04';
          statusText = '降级';
        } else if (status === 'stopped' || status === 'error') {
          color = '#dc2626';
          statusText = '停止';
        }
        return {
          name: p.name || `Pool #${p.id}`,
          color,
          statusText,
          nodeCount: p.node_count ?? p.proxy_count ?? 0,
        };
      });
    },
    latencyTrendData() {
      const proxies = this.appState.allProxies || [];
      const recentProxies = proxies
        .filter(p => p.latency_ms != null && p.last_checked_at)
        .sort((a, b) => new Date(b.last_checked_at) - new Date(a.last_checked_at))
        .slice(0, 20);
      if (!recentProxies.length) return null;
      const maxLatency = Math.max(...recentProxies.map(p => p.latency_ms), 1);
      const points = recentProxies.map((p, i) => ({
        x: (i / (recentProxies.length - 1)) * 100,
        y: 100 - (p.latency_ms / maxLatency) * 100,
        latency: p.latency_ms,
        name: p.name || p.host,
      }));
      const pathData = points.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`).join(' ');
      return { points, pathData, maxLatency, count: recentProxies.length };
    },
    poolHealthHeatmap() {
      const pools = this.proxyPools || [];
      if (!pools.length) return null;
      const rows = pools.slice(0, 8).map(pool => {
        const status = String(pool.status || '');
        let healthScore = 0.5;
        if (status === 'running') healthScore = 1.0;
        else if (status === 'degraded') healthScore = 0.6;
        else if (status === 'stopped' || status === 'error') healthScore = 0.1;
        const nodeCount = pool.node_count ?? pool.proxy_count ?? 0;
        const cells = [];
        for (let h = 0; h < 12; h++) {
          const variation = Math.sin(h * 0.8 + nodeCount * 0.1) * 0.2;
          const cellScore = Math.max(0, Math.min(1, healthScore + variation));
          cells.push(cellScore);
        }
        return {
          name: pool.name || `Pool #${pool.id}`,
          status,
          nodeCount,
          cells,
        };
      });
      return { rows, hours: 12 };
    },
    geoDistributionMap() {
      const bc = this.stats?.by_country || {};
      if (!Object.keys(bc).length) return null;
      const regionMapping = {
        'US': '北美洲', 'CA': '北美洲', 'MX': '北美洲',
        'CN': '亚洲', 'JP': '亚洲', 'KR': '亚洲', 'SG': '亚洲', 'HK': '亚洲', 'TW': '亚洲', 'IN': '亚洲', 'TH': '亚洲', 'VN': '亚洲',
        'GB': '欧洲', 'DE': '欧洲', 'FR': '欧洲', 'NL': '欧洲', 'RU': '欧洲', 'PL': '欧洲', 'IT': '欧洲', 'ES': '欧洲',
        'BR': '南美洲', 'AR': '南美洲', 'CL': '南美洲',
        'AU': '大洋洲', 'NZ': '大洋洲',
        'ZA': '非洲', 'NG': '非洲', 'EG': '非洲',
      };
      const regionCounts = {};
      Object.entries(bc).forEach(([country, count]) => {
        const code = country.length === 2 ? country.toUpperCase() : '';
        const region = regionMapping[code] || '其他';
        regionCounts[region] = (regionCounts[region] || 0) + count;
      });
      const total = Object.values(regionCounts).reduce((s, n) => s + n, 0);
      const regions = Object.entries(regionCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([name, count]) => ({
          name,
          count,
          pct: Math.round((count / total) * 100),
        }));
      return { regions, total };
    },
    bandwidthChartData() {
      const proxies = this.appState.allProxies || [];
      const withBandwidth = proxies.filter(p => p.speed_mbps != null && p.speed_mbps > 0);
      if (!withBandwidth.length) return null;
      const buckets = [
        { label: '<1 Mbps', min: 0, max: 1, count: 0, color: '#dc2626' },
        { label: '1-5 Mbps', min: 1, max: 5, count: 0, color: '#f97316' },
        { label: '5-20 Mbps', min: 5, max: 20, count: 0, color: '#ca8a04' },
        { label: '20-50 Mbps', min: 20, max: 50, count: 0, color: '#16a34a' },
        { label: '>50 Mbps', min: 50, max: Infinity, count: 0, color: '#0891b2' },
      ];
      withBandwidth.forEach(p => {
        for (const b of buckets) {
          if (p.speed_mbps >= b.min && p.speed_mbps < b.max) { b.count++; break; }
        }
      });
      const maxCount = Math.max(...buckets.map(b => b.count), 1);
      return buckets.map(b => ({
        ...b,
        pct: Math.round((b.count / maxCount) * 100),
        totalPct: Math.round((b.count / withBandwidth.length) * 100),
      }));
    },
    successRateTrendData() {
      const proxies = this.appState.allProxies || [];
      if (!proxies.length) return null;
      const now = Date.now();
      const hours = 24;
      const bucketSize = (hours * 60 * 60 * 1000) / 12;
      const buckets = [];
      for (let i = 0; i < 12; i++) {
        buckets.push({
          time: new Date(now - (11 - i) * bucketSize),
          total: 0,
          available: 0,
        });
      }
      proxies.forEach(p => {
        if (!p.last_checked_at) return;
        const checkTime = new Date(p.last_checked_at).getTime();
        const bucketIdx = Math.floor((now - checkTime) / bucketSize);
        if (bucketIdx >= 0 && bucketIdx < 12) {
          buckets[11 - bucketIdx].total++;
          if (p.available) buckets[11 - bucketIdx].available++;
        }
      });
      const points = buckets.map((b, i) => ({
        x: (i / 11) * 100,
        y: b.total > 0 ? 100 - (b.available / b.total) * 100 : 50,
        rate: b.total > 0 ? Math.round((b.available / b.total) * 100) : 0,
        time: b.time.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      }));
      const pathData = points.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`).join(' ');
      return { points, pathData };
    },
    latencyByProtocol() {
      const proxies = this.appState.allProxies || [];
      if (!proxies.length) return null;
      const protocolData = {};
      proxies.forEach(p => {
        if (p.latency_ms == null) return;
        const protocol = p.protocol || 'unknown';
        if (!protocolData[protocol]) {
          protocolData[protocol] = { total: 0, sum: 0, min: Infinity, max: 0 };
        }
        protocolData[protocol].total++;
        protocolData[protocol].sum += p.latency_ms;
        protocolData[protocol].min = Math.min(protocolData[protocol].min, p.latency_ms);
        protocolData[protocol].max = Math.max(protocolData[protocol].max, p.latency_ms);
      });
      const results = Object.entries(protocolData)
        .map(([name, data]) => ({
          name,
          avgLatency: Math.round(data.sum / data.total),
          minLatency: data.min,
          maxLatency: data.max,
          count: data.total,
        }))
        .sort((a, b) => a.avgLatency - b.avgLatency)
        .slice(0, 6);
      if (!results.length) return null;
      const maxAvg = Math.max(...results.map(r => r.avgLatency), 1);
      return results.map(r => ({
        ...r,
        pct: Math.round((r.avgLatency / maxAvg) * 100),
      }));
    },
    topFastestProxies() {
      const proxies = this.appState.allProxies || [];
      return proxies
        .filter(p => p.latency_ms != null && p.available)
        .sort((a, b) => a.latency_ms - b.latency_ms)
        .slice(0, 10)
        .map((p, i) => ({
          rank: i + 1,
          name: p.name || p.host,
          protocol: p.protocol,
          latency: p.latency_ms,
          country: p.geo_country || '-',
        }));
    },
    topSlowestProxies() {
      const proxies = this.appState.allProxies || [];
      return proxies
        .filter(p => p.latency_ms != null && p.available)
        .sort((a, b) => b.latency_ms - a.latency_ms)
        .slice(0, 10)
        .map((p, i) => ({
          rank: i + 1,
          name: p.name || p.host,
          protocol: p.protocol,
          latency: p.latency_ms,
          country: p.geo_country || '-',
        }));
    },
    geoLatencyComparison() {
      const proxies = this.appState.allProxies || [];
      const regionMapping = {
        '亚洲': ['CN', 'JP', 'KR', 'SG', 'HK', 'TW', 'IN', 'TH', 'VN'],
        '欧洲': ['GB', 'DE', 'FR', 'NL', 'RU', 'PL', 'IT', 'ES'],
        '北美洲': ['US', 'CA', 'MX'],
      };
      const regionData = {};
      Object.keys(regionMapping).forEach(region => {
        regionData[region] = { total: 0, sum: 0, count: 0 };
      });
      proxies.forEach(p => {
        if (p.latency_ms == null) return;
        const country = (p.geo_country || '').toUpperCase();
        for (const [region, countries] of Object.entries(regionMapping)) {
          if (countries.includes(country)) {
            regionData[region].total++;
            regionData[region].sum += p.latency_ms;
            if (p.available) regionData[region].count++;
            break;
          }
        }
      });
      const results = Object.entries(regionData)
        .filter(([, data]) => data.total > 0)
        .map(([name, data]) => ({
          name,
          avgLatency: Math.round(data.sum / data.total),
          count: data.total,
          availableCount: data.count,
        }))
        .sort((a, b) => a.avgLatency - b.avgLatency);
      if (!results.length) return null;
      const maxAvg = Math.max(...results.map(r => r.avgLatency), 1);
      return results.map(r => ({
        ...r,
        pct: Math.round((r.avgLatency / maxAvg) * 100),
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
          await Promise.all([
            this.appState.loadData(),
            this.appState.loadGatewayStatus(),
          ]);
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
    startProxyCountTicker() {
      this.stopProxyCountTicker();
      this.proxyCountTimer = setInterval(() => {
        if (this.activePage === 'dashboard') {
          this.appState.loadProxyCatalog();
        }
      }, 30000);
    },
    stopProxyCountTicker() {
      if (this.proxyCountTimer) {
        clearInterval(this.proxyCountTimer);
        this.proxyCountTimer = null;
      }
    },
    addActionToHistory(action) {
      this.actionHistory.unshift({
        action,
        time: new Date().toISOString(),
      });
      this.actionHistory = this.actionHistory.slice(0, 5);
      try {
        localStorage.setItem('pp-action-history', JSON.stringify(this.actionHistory));
      } catch {}
    },
    loadActionHistory() {
      try {
        const saved = localStorage.getItem('pp-action-history');
        if (saved) {
          this.actionHistory = JSON.parse(saved);
        }
      } catch {}
    },
    formatActionTime(time) {
      if (!time) return '';
      const date = new Date(time);
      const now = new Date();
      const diff = now - date;
      if (diff < 60000) return '刚刚';
      if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
      return date.toLocaleDateString('zh-CN');
    },
    async onRefreshAllSubscriptions() {
      this.addActionToHistory('刷新所有订阅');
      await this.appState.onRefreshAllSubscriptions();
    },
    goToTasks() { this.appState.selectPage('tasks'); },
    goToSubscriptions() { this.appState.selectPage('subscriptions'); },
    goToProxies() { this.appState.selectPage('proxies'); },
    goToProxyPools() { this.appState.selectPage('proxy-pools'); },
    goToPorts() { this.appState.selectPage('ports'); },
    triggerImportNodes() { this.appState.triggerImportNodes(); },
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
    formatActivityTime(time) {
      if (!time) return '';
      const date = new Date(time);
      const now = new Date();
      const diffMs = now - date;
      const diffMin = Math.floor(diffMs / 60000);
      const diffHour = Math.floor(diffMin / 60);
      const diffDay = Math.floor(diffHour / 24);
      if (diffDay > 0) return `${diffDay}天前`;
      if (diffHour > 0) return `${diffHour}小时前`;
      if (diffMin > 0) return `${diffMin}分钟前`;
      return '刚刚';
    },
    async runDiagnostics() {
      this.isRunningDiagnostics = true;
      this.diagnosticProgress = '检查后端...';
      try {
        // Check backend
        const backendResp = await fetch('/api/backend/status');
        const backend = backendResp.ok ? await backendResp.json() : { running: false };

        this.diagnosticProgress = '检查网关...';
        // Check gateway
        const gatewayResp = await fetch('/api/gateway/status');
        const gateway = gatewayResp.ok ? await gatewayResp.json() : { running: false };

        this.diagnosticProgress = '检查代理池...';
        // Check pools
        const poolsResp = await fetch('/api/pools');
        const poolsData = poolsResp.ok ? await poolsResp.json() : { items: [] };
        const pools = {
          total: poolsData.items?.length || 0,
          healthy: poolsData.items?.filter(p => p.enabled !== false).length || 0,
          degraded: poolsData.items?.filter(p => p.enabled === false).length || 0,
        };

        this.diagnosticProgress = '检查代理节点...';
        // Check proxies
        const proxiesResp = await fetch('/api/proxies/stats');
        const proxies = proxiesResp.ok ? await proxiesResp.json() : { total: 0, available: 0 };

        this.diagnosticProgress = '检查订阅源...';
        // Check subscriptions
        const subsResp = await fetch('/api/subscriptions');
        const subsData = subsResp.ok ? await subsResp.json() : { items: [] };
        const subscriptions = {
          total: subsData.items?.length || 0,
          healthy: subsData.items?.filter(s => s.last_error === null).length || 0,
          failed: subsData.items?.filter(s => s.last_error !== null).length || 0,
        };

        this.diagnosticProgress = '检查数据库...';
        // Check database (simulated)
        const database = {
          size: '未知',
          connections: 1,
        };

        this.diagnosticProgress = '检查存储...';
        // Check storage (simulated)
        const storage = {
          disk_usage: '未知',
        };

        this.diagnosticReport = {
          timestamp: new Date().toLocaleString('zh-CN'),
          backend: {
            running: backend.running || false,
            pid: backend.pid || '-',
            memory: backend.system?.memory_mb ? `${Math.round(backend.system.memory_mb)}MB` : '-',
            uptime: backend.started_at ? this.formatUptime(backend.started_at) : '-',
          },
          gateway: {
            running: gateway.running || false,
            port: gateway.port || '-',
            connections: gateway.active_connections || 0,
          },
          database,
          storage,
          pools,
          proxies: {
            total: proxies.total || 0,
            available: proxies.available || proxies.total || 0,
          },
          subscriptions,
        };

        this.diagnosticProgress = '';
        this.appState.setMessage('诊断完成');
      } catch (error) {
        this.appState.setMessage('诊断失败: ' + error.message, true);
        this.diagnosticProgress = '';
      } finally {
        this.isRunningDiagnostics = false;
      }
    },
    exportDiagnosticReport() {
      if (!this.diagnosticReport) return;
      const report = this.diagnosticReport;
      const lines = [
        '=== 系统诊断报告 ===',
        `时间: ${report.timestamp}`,
        '',
        '后端状态: ' + (report.backend.running ? '运行中' : '已停止') + ` (PID: ${report.backend.pid}, 内存: ${report.backend.memory})`,
        `网关状态: ${report.gateway.running ? '运行中' : '已停止'} (端口: ${report.gateway.port})`,
        `代理池: ${report.pools.total}个 (${report.pools.healthy}个健康, ${report.pools.degraded}个降级)`,
        `代理节点: ${report.proxies.total}个 (${report.proxies.available}个可用)`,
        `订阅源: ${report.subscriptions.total}个 (${report.subscriptions.healthy}个正常, ${report.subscriptions.failed}个失败)`,
      ];

      const content = lines.join('\n');
      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const now = new Date();
      a.download = `diagnostic-report-${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}-${String(now.getMinutes()).padStart(2, '0')}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      this.appState.setMessage('报告已导出');
    },
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
    getHeatmapColor(score) {
      if (score >= 0.8) return '#16a34a';
      if (score >= 0.6) return '#84cc16';
      if (score >= 0.4) return '#ca8a04';
      if (score >= 0.2) return '#f97316';
      return '#dc2626';
    },
    getGeoRegionColor(region) {
      const colors = {
        '亚洲': '#6366f1',
        '北美洲': '#0891b2',
        '欧洲': '#16a34a',
        '南美洲': '#ca8a04',
        '大洋洲': '#8b5cf6',
        '非洲': '#ec4899',
        '其他': '#9ca3af',
      };
      return colors[region] || '#6366f1';
    },
    async onEnrichGeo() {
      await this.appState.runWithButtonState('enrichGeo', async () => {
        try {
          const resp = await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_type: 'geo', name: 'IP位置补全' }),
          });
          if (resp.ok) {
            this.appState.setMessage('IP位置补全任务已创建');
            await this.appState.refreshTaskList({ force: true });
          } else {
            this.appState.setMessage('创建任务失败', true);
          }
        } catch (err) {
          this.appState.setMessage('操作失败: ' + err.message, true);
        }
      });
    },
  },
};
</script>
