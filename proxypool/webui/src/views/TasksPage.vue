<template>
            <section class="task-dashboard fade-in">
              <!-- Breadcrumb -->
              <Breadcrumb :items="breadcrumbItems" />

              <!-- Quick actions -->
              <div class="card task-quick-card">
                <div class="card-body">
                  <div class="task-ops-header">
                    <div>
                      <h2 class="section-title">任务操作</h2>
                      <p class="form-hint">常用任务集中启动，运行状态在下方任务列表跟踪。</p>
                    </div>
                    <span class="badge" :class="taskItems.some(t => ['queued','running'].includes(String(t.status||''))) ? 'badge-warning' : 'badge-neutral'">
                      {{ taskItems.some(t => ['queued','running'].includes(String(t.status||''))) ? '有任务运行' : '空闲' }}
                    </span>
                  </div>

                  <!-- 常用操作 -->
                  <div class="action-group" style="margin-bottom: 12px;">
                    <h4 class="action-group-title">常用操作</h4>
                    <div class="action-bar task-action-bar">
                      <el-tooltip content="导入本地代理节点文件（支持多种格式），导入后节点会自动保存到数据库" placement="top" :show-after="300">
                        <button class="btn btn-primary" :disabled="isActionRunning('importFiles')" @click="openImportFiles" aria-label="导入本地代理节点文件">
                          {{ buttonLabel('importFiles', '导入节点文件', '导入中...') }}
                        </button>
                      </el-tooltip>
                      <el-tooltip content="立即测试所有可用节点的连通性和延迟，更新节点状态" placement="top" :show-after="300">
                        <button class="btn btn-primary" :disabled="isActionRunning('runTest')" @click="onRunTest" aria-label="立即测试所有节点">
                          {{ buttonLabel('runTest', '立即测速', '测速中...') }}
                        </button>
                      </el-tooltip>
                    </div>
                  </div>

                  <!-- 一键诊断 -->
                  <div class="action-group" style="margin-bottom: 12px;">
                    <h4 class="action-group-title">一键诊断</h4>
                    <p class="form-hint" style="margin-bottom: 8px;">快速检测节点健康状态，定位问题节点</p>
                    <div class="action-bar task-action-bar">
                      <el-tooltip content="测试选中的单个节点，快速验证节点连通性" placement="top" :show-after="300">
                        <button class="btn btn-secondary" :disabled="!selectedProxyKeys.length || isActionRunning('testSingleProxy')" @click="onTestSelectedProxy" aria-label="测试选中的单个节点">
                          {{ buttonLabel('testSingleProxy', '单节点测试', '测试中...') }}
                        </button>
                      </el-tooltip>
                      <el-tooltip content="批量测试所有选中的节点，适合验证多个节点状态" placement="top" :show-after="300">
                        <button class="btn btn-secondary" :disabled="!selectedProxyKeys.length || isActionRunning('testBatchProxies')" @click="onTestSelectedProxies" :aria-label="'批量测试选中的 ' + selectedProxyKeys.length + ' 个节点'">
                          {{ buttonLabel('testBatchProxies', '批量测试 (' + selectedProxyKeys.length + ')', '测试中...') }}
                        </button>
                      </el-tooltip>
                      <el-tooltip content="检查所有代理池的健康状态，识别不健康的节点" placement="top" :show-after="300">
                        <button class="btn btn-secondary" :disabled="isActionRunning('checkPoolHealth')" @click="onCheckPoolHealth" aria-label="检查所有代理池的健康状态">
                          {{ buttonLabel('checkPoolHealth', '池健康检查', '检查中...') }}
                        </button>
                      </el-tooltip>
                      <el-tooltip content="测试代理链路的连通性，验证多跳代理是否正常工作" placement="top" :show-after="300">
                        <button class="btn btn-secondary" :disabled="isActionRunning('testChainLink')" @click="onTestChainLink" aria-label="测试代理链路的连通性">
                          {{ buttonLabel('testChainLink', '链路测试', '测试中...') }}
                        </button>
                      </el-tooltip>
                    </div>
                  </div>

                  <!-- 订阅操作 -->
                  <div class="action-group" style="margin-bottom: 12px;">
                    <h4 class="action-group-title">订阅操作</h4>
                    <div class="action-bar task-action-bar">
                      <el-tooltip content="复制所有可用节点的订阅链接到剪贴板，可直接导入到代理客户端" placement="top" :show-after="300">
                        <button class="btn btn-secondary" :disabled="isActionRunning('copySubscription')" @click="onCopySubscription">
                          {{ buttonLabel('copySubscription', '复制订阅', '复制中...') }}
                        </button>
                      </el-tooltip>
                      <el-tooltip content="在新窗口打开订阅链接，查看原始订阅内容" placement="top" :show-after="300">
                        <a href="/api/subscription?only_available=true" target="_blank" class="btn btn-secondary">导出链接</a>
                      </el-tooltip>
                    </div>
                  </div>

                  <!-- 高级操作（可折叠） -->
                  <details class="action-group action-group-collapsible" style="margin-bottom: 12px;">
                    <summary class="action-group-summary">高级操作</summary>
                    <div class="action-bar task-action-bar" style="margin-top: 8px;">
                      <el-tooltip content="测试节点的下载速度，需要较长时间，适合测试少量节点" placement="top" :show-after="300">
                        <button class="btn btn-secondary" :disabled="isActionRunning('runSpeedTest')" @click="onRunSpeedTest">
                          {{ buttonLabel('runSpeedTest', '测试网速', '测试中...') }}
                        </button>
                      </el-tooltip>
                      <el-tooltip content="检测节点是否可以解锁 ChatGPT 服务（OpenAI 访问权限）" placement="top" :show-after="300">
                        <button class="btn btn-secondary" :disabled="isActionRunning('runUnlockCheck')" @click="onRunUnlockCheck">
                          {{ buttonLabel('runUnlockCheck', '检测ChatGPT解锁', '检测中...') }}
                        </button>
                      </el-tooltip>
                      <el-tooltip content="补全节点的地理位置信息（国家、城市），用于按地区筛选节点" placement="top" :show-after="300">
                        <button class="btn btn-secondary" :disabled="isActionRunning('enrichGeo')" @click="onEnrichGeo">
                          {{ buttonLabel('enrichGeo', '补全IP位置', '补全中...') }}
                        </button>
                      </el-tooltip>
                      <el-tooltip content="检测节点 IP 的纯净度（家宽/非家宽），家宽 IP 通常更稳定" placement="top" :show-after="300">
                        <button class="btn btn-secondary" :disabled="isActionRunning('runIpPurity')" @click="onRunIpPurity">
                          {{ buttonLabel('runIpPurity', '检测IP纯净度', '检测中...') }}
                        </button>
                      </el-tooltip>
                    </div>
                  </details>

                  <!-- 维护操作 -->
                  <div class="action-group" style="margin-bottom: 12px;">
                    <h4 class="action-group-title">维护操作</h4>
                    <div class="action-bar task-action-bar">
                      <el-tooltip content="删除所有不可用的节点（状态为 DOWN），此操作不可恢复" placement="top" :show-after="300">
                        <button class="btn btn-danger" :disabled="isActionRunning('deleteUnavailable')" @click="onDeleteUnavailable">
                          {{ buttonLabel('deleteUnavailable', '删除不可用', '删除中...') }}
                        </button>
                      </el-tooltip>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Settings panels -->
              <div class="settings-grid task-settings-grid">
                <!-- Test fallback -->
                <div class="card">
                  <div class="card-body">
                    <h3 class="settings-title">测速回退配置</h3>
                    <div class="settings-row">
                      <div class="form-group" style="flex: 3;">
                        <label class="form-label">前置代理(序号)</label>
                        <input v-model.trim="testFallback.front_proxy_refs" list="proxy-key-options" type="text" placeholder="如 #1,#8,#12" class="input input-mono" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">最多尝试</label>
                        <input v-model.number="testFallback.max_attempts" type="number" min="0" max="100" class="input" />
                      </div>
                      <button @click="onSaveTestFallback" :disabled="isActionRunning('saveTestFallback')" class="btn btn-secondary self-end">
                        {{ buttonLabel('saveTestFallback', '保存', '保存中...') }}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Test filter -->
                <div class="card">
                  <div class="card-body">
                    <h3 class="settings-title">测速筛选</h3>
                    <div class="settings-row">
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">状态</label>
                        <select v-model="testRunFilter.status" class="select">
                          <option value="all">全部</option>
                          <option value="down">仅不可用</option>
                          <option value="up">仅可用</option>
                          <option value="unchecked">仅未测速</option>
                        </select>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">复测间隔(天)</label>
                        <input v-model.number="testRunFilter.min_retest_days" type="number" min="0" max="365" step="0.5" class="input" />
                      </div>
                      <label class="form-check self-end">
                        <input v-model="testRunFilter.replace_failed_with_available" type="checkbox" />
                        <span>失败时自动替换落地节点</span>
                      </label>
                      <button @click="onSaveTestRunFilter" :disabled="isActionRunning('saveTestRunFilter')" class="btn btn-secondary self-end">
                        {{ buttonLabel('saveTestRunFilter', '保存', '保存中...') }}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Detection strategy -->
                <div class="card">
                  <div class="card-body">
                    <h3 class="settings-title">检测策略</h3>
                    <div class="settings-row">
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">预设策略</label>
                        <el-select v-model="detectionStrategy.preset" clearable placeholder="选择预设策略" size="default" style="width: 100%">
                          <el-option label="快速检测（仅连通性）" value="quick"></el-option>
                          <el-option label="标准检测（连通性+延迟）" value="standard"></el-option>
                          <el-option label="完整检测（连通性+延迟+速度）" value="full"></el-option>
                          <el-option label="深度检测（连通性+延迟+速度+解锁）" value="deep"></el-option>
                        </el-select>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">超时时间(秒)</label>
                        <input v-model.number="detectionStrategy.timeout" type="number" min="3" max="120" class="input" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">并发数</label>
                        <input v-model.number="detectionStrategy.concurrency" type="number" min="1" max="200" class="input" />
                      </div>
                    </div>
                    <div class="settings-row" style="margin-top: 8px;">
                      <button @click="onSaveDetectionStrategy" :disabled="isActionRunning('saveDetectionStrategy')" class="btn btn-primary">
                        {{ buttonLabel('saveDetectionStrategy', '保存策略', '保存中...') }}
                      </button>
                      <button @click="onResetDetectionStrategy" :disabled="isActionRunning('resetDetectionStrategy')" class="btn btn-secondary">
                        {{ buttonLabel('resetDetectionStrategy', '恢复默认', '恢复中...') }}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Concurrency -->
                <div class="card">
                  <div class="card-body">
                    <h3 class="settings-title">并发设置</h3>
                    <div class="settings-row">
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">测速</label>
                        <input v-model.number="taskConcurrency.tester" type="number" min="1" max="500" class="input" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">解锁</label>
                        <input v-model.number="taskConcurrency.openai" type="number" min="1" max="500" class="input" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">Geo</label>
                        <input v-model.number="taskConcurrency.geoip" type="number" min="1" max="500" class="input" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">纯净度</label>
                        <input v-model.number="taskConcurrency.ip_purity" type="number" min="1" max="500" class="input" />
                      </div>
                      <button @click="onSaveTaskConcurrency" :disabled="isActionRunning('saveTaskConcurrency')" class="btn btn-secondary self-end">
                        {{ buttonLabel('saveTaskConcurrency', '保存', '保存中...') }}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Speed test -->
                <div class="card">
                  <div class="card-body">
                    <h3 class="settings-title">网速测试</h3>
                    <div class="settings-row">
                      <div class="form-group" style="flex: 2.2;">
                        <label class="form-label">测速文件地址</label>
                        <input v-model.trim="speedTestForm.url" type="text" placeholder="https://speed.cloudflare.com/__down?bytes=10000000" class="input mono" />
                      </div>
                      <div class="form-group" style="flex: 0.8;">
                        <label class="form-label">节点数</label>
                        <input v-model.number="speedTestForm.limit" type="number" min="0" max="20000" class="input" />
                      </div>
                      <div class="form-group" style="flex: 0.8;">
                        <label class="form-label">超时(秒)</label>
                        <input v-model.number="speedTestForm.timeout_sec" type="number" min="3" max="300" class="input" />
                      </div>
                      <label class="form-check self-end">
                        <input v-model="speedTestForm.only_direct" type="checkbox" />
                        <span>仅对可直连的节点测速</span>
                      </label>
                      <button @click="onRunSpeedTest" :disabled="isActionRunning('runSpeedTest')" class="btn btn-secondary self-end">
                        {{ buttonLabel('runSpeedTest', '开始网速测试', '测试中...') }}
                      </button>
                    </div>
                    <p class="form-hint" style="margin-top: 8px;">串行测试，适合使用固定大小下载文件；开启后只选择直连可用节点，排除依赖前置代理的链式连通节点。</p>
                  </div>
                </div>

                <!-- Auto tasks -->
                <div class="card">
                  <div class="card-body">
                    <div class="card-header">
                      <h3 class="settings-title">自动任务</h3>
                      <button @click="onLoadAutoTaskConfig" :disabled="isActionRunning('loadAutoTaskConfig')" class="btn btn-xs btn-secondary">刷新配置</button>
                    </div>
                    <div class="settings-row">
                      <label class="form-check">
                        <input v-model="autoTaskConfig.enabled" type="checkbox" />
                        <span>启用自动任务</span>
                      </label>
                      <label class="form-check">
                        <input v-model="autoTaskConfig.subscription_refresh_enabled" type="checkbox" />
                        <span>自动更新订阅</span>
                      </label>
                      <div class="form-group" style="flex: 0.8;">
                        <label class="form-label">订阅间隔(分钟)</label>
                        <input v-model.number="autoTaskConfig.subscription_refresh_minutes" type="number" min="1" max="10080" class="input" />
                      </div>
                    </div>
                    <div class="settings-row" style="margin-top: 8px;">
                      <label class="form-check">
                        <input v-model="autoTaskConfig.tester_enabled" type="checkbox" />
                        <span>自动测速</span>
                      </label>
                      <div class="form-group" style="flex: 0.8;">
                        <label class="form-label">测速间隔(分钟)</label>
                        <input v-model.number="autoTaskConfig.tester_minutes" type="number" min="1" max="10080" class="input" />
                      </div>
                      <div class="form-group" style="flex: 0.8;">
                        <label class="form-label">测速节点数</label>
                        <input v-model.number="autoTaskConfig.tester_limit" type="number" min="0" max="20000" class="input" />
                      </div>
                      <div class="form-group" style="flex: 0.8;">
                        <label class="form-label">测速并发</label>
                        <input v-model.number="autoTaskConfig.tester_concurrency" type="number" min="1" max="500" class="input" />
                      </div>
                    </div>
                    <div class="settings-row" style="margin-top: 8px;">
                      <label class="form-check">
                        <input v-model="autoTaskConfig.speed_test_enabled" type="checkbox" />
                        <span>自动网速测试</span>
                      </label>
                      <div class="form-group" style="flex: 1.8;">
                        <label class="form-label">网速测试地址</label>
                        <input v-model.trim="autoTaskConfig.speed_test_url" type="text" class="input mono" />
                      </div>
                      <div class="form-group" style="flex: 0.8;">
                        <label class="form-label">间隔(分钟)</label>
                        <input v-model.number="autoTaskConfig.speed_test_minutes" type="number" min="1" max="10080" class="input" />
                      </div>
                      <div class="form-group" style="flex: 0.8;">
                        <label class="form-label">节点数</label>
                        <input v-model.number="autoTaskConfig.speed_test_limit" type="number" min="0" max="20000" class="input" />
                      </div>
                      <div class="form-group" style="flex: 0.8;">
                        <label class="form-label">超时(秒)</label>
                        <input v-model.number="autoTaskConfig.speed_test_timeout_sec" type="number" min="3" max="300" class="input" />
                      </div>
                    </div>
                    <div class="settings-row" style="margin-top: 8px;">
                      <button @click="onSaveAutoTaskConfig" :disabled="isActionRunning('saveAutoTaskConfig')" class="btn btn-primary">
                        {{ buttonLabel('saveAutoTaskConfig', '保存自动任务', '保存中...') }}
                      </button>
                      <span class="text-xs text-muted">状态: {{ autoTaskStatus?.running ? '调度器运行中' : '调度器未运行' }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Task list -->
              <div class="card task-list-card">
                <div class="card-body">
                  <div class="card-header">
                    <h2 class="section-title">任务列表</h2>
                    <button @click="onRefreshTasks" :disabled="isActionRunning('refreshTasks')" class="btn btn-sm btn-secondary">
                      {{ buttonLabel('refreshTasks', '刷新', '刷新中...') }}
                    </button>
                  </div>
                  <EmptyState v-if="!taskItems.length" title="暂无任务" description="点击上方按钮开始执行任务" size="small" />
                  <div v-else class="task-list">
                    <div v-for="task in taskItems" :key="task.task_id" class="task-item">
                      <div class="task-row">
                        <div class="task-info">
                          <span class="task-name">{{ taskLabel(task.kind) }}</span>
                          <span class="badge badge-sm" :class="taskStatusClass(task.status)">{{ taskStatusText(task.status) }}</span>
                        </div>
                        <div class="task-actions">
                          <button v-if="isTaskStoppable(task)" @click="onStopTask(task)" :disabled="isActionRunning('stopTask-' + task.task_id)" class="btn btn-xs btn-danger">
                            {{ buttonLabel('stopTask-' + task.task_id, '停止', '...') }}
                          </button>
                          <button v-if="isTaskDeletable(task)" @click="onDeleteTaskBtn(task)" :disabled="isActionRunning('deleteTask-' + task.task_id)" class="btn btn-xs btn-secondary">
                            {{ buttonLabel('deleteTask-' + task.task_id, '删除记录', '...') }}
                          </button>
                        </div>
                      </div>
                      <TaskProgress :current="task.completed || 0" :total="task.total || 0" :status="task.status" :show-label="true" />
                      <div class="task-meta">
                        <span>任务 {{ shortTaskId(task.task_id) }}</span>
                        <span>进度 {{ task.completed || 0 }}/{{ task.total || '-' }}</span>
                        <span class="text-emerald-600">成功 {{ task.success || 0 }}</span>
                        <span class="text-rose-600">失败 {{ task.failed || 0 }}</span>
                        <span v-if="task.duration_sec" class="text-muted">耗时 {{ formatDuration(task.duration_sec) }}</span>
                        <span class="task-message" :title="taskMessageText(task)">结果 {{ taskMessageText(task) }}</span>
                        <span>更新 {{ formatTime(task.updated_at) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>
</template>

<script>
import { rootProxyMixin } from "../rootProxyMixin";
import Breadcrumb from '../components/layout/Breadcrumb.vue';
import TaskProgress from '../components/common/TaskProgress.vue';
import EmptyState from '../components/common/EmptyState.vue';

export default {
  name: "TasksPage",
  components: {
    Breadcrumb,
    TaskProgress,
    EmptyState,
  },
  mixins: [rootProxyMixin],
  data() {
    return {
      detectionStrategy: {
        preset: 'standard',
        timeout: 10,
        concurrency: 50,
      },
    };
  },
  computed: {
    breadcrumbItems() {
      return [
        { label: '首页', path: '/', onClick: () => this.selectPage('dashboard') },
        { label: '任务中心' },
      ];
    },
  },
  methods: {
    formatDuration(seconds) {
      if (!seconds || seconds <= 0) return '-';
      if (seconds < 60) return `${Math.round(seconds)}秒`;
      if (seconds < 3600) return `${Math.floor(seconds / 60)}分${Math.round(seconds % 60)}秒`;
      const hours = Math.floor(seconds / 3600);
      const mins = Math.floor((seconds % 3600) / 60);
      return `${hours}时${mins}分`;
    },

    async onTestSelectedProxy() {
      if (!this.selectedProxyKeys.length) return;
      const key = this.selectedProxyKeys[0];
      await this.runWithButtonState('testSingleProxy', async () => {
        try {
          const resp = await fetch('/api/tasks/tester/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keys: [key], limit: 1, concurrency: 1 }),
          });
          if (resp.ok) {
            this.setMessage('单节点测试已启动');
          } else {
            this.setMessage('测试启动失败');
          }
        } catch (e) {
          this.setMessage('网络错误: ' + e.message);
        }
      });
    },

    async onTestSelectedProxies() {
      if (!this.selectedProxyKeys.length) return;
      await this.runWithButtonState('testBatchProxies', async () => {
        try {
          const resp = await fetch('/api/tasks/tester/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              keys: this.selectedProxyKeys,
              limit: this.selectedProxyKeys.length,
              concurrency: 10,
            }),
          });
          if (resp.ok) {
            this.setMessage(`批量测试已启动，共 ${this.selectedProxyKeys.length} 个节点`);
          } else {
            this.setMessage('批量测试启动失败');
          }
        } catch (e) {
          this.setMessage('网络错误: ' + e.message);
        }
      });
    },

    async onCheckPoolHealth() {
      await this.runWithButtonState('checkPoolHealth', async () => {
        try {
          const resp = await fetch('/api/pools/health', { method: 'GET' });
          if (resp.ok) {
            const data = await resp.json();
            const summary = data.summary || {};
            const msg = `池健康检查完成: ${summary.total_pools || 0} 个池, ${summary.healthy_pools || 0} 个健康, ${summary.unhealthy_pools || 0} 个异常`;
            this.setMessage(msg);
          } else {
            this.setMessage('健康检查失败');
          }
        } catch (e) {
          this.setMessage('网络错误: ' + e.message);
        }
      });
    },

    async onTestChainLink() {
      await this.runWithButtonState('testChainLink', async () => {
        try {
          const resp = await fetch('/api/pools/chains/test', { method: 'POST' });
          if (resp.ok) {
            const data = await resp.json();
            const msg = `链路测试完成: ${data.success ? '链路正常' : '链路异常'}`;
            this.setMessage(msg);
          } else {
            this.setMessage('链路测试失败');
          }
        } catch (e) {
          this.setMessage('网络错误: ' + e.message);
        }
      });
    },

    async onSaveDetectionStrategy() {
      await this.runWithButtonState('saveDetectionStrategy', async () => {
        try {
          const config = {
            preset: this.detectionStrategy.preset,
            timeout: this.detectionStrategy.timeout,
            concurrency: this.detectionStrategy.concurrency,
          };
          try {
            localStorage.setItem('proxypool.detectionStrategy.v1', JSON.stringify(config));
            this.setMessage('检测策略已保存');
          } catch (e) {
            this.setMessage('保存失败: ' + e.message);
          }
        } catch (e) {
          this.setMessage('保存失败: ' + e.message);
        }
      });
    },

    async onResetDetectionStrategy() {
      await this.runWithButtonState('resetDetectionStrategy', async () => {
        this.detectionStrategy = {
          preset: 'standard',
          timeout: 10,
          concurrency: 50,
        };
        try {
          localStorage.setItem('proxypool.detectionStrategy.v1', JSON.stringify(this.detectionStrategy));
          this.setMessage('已恢复默认策略');
        } catch (e) {
          this.setMessage('恢复失败: ' + e.message);
        }
      });
    },

    loadDetectionStrategy() {
      try {
        const saved = localStorage.getItem('proxypool.detectionStrategy.v1');
        if (saved) {
          const config = JSON.parse(saved);
          this.detectionStrategy = {
            preset: config.preset || 'standard',
            timeout: config.timeout || 10,
            concurrency: config.concurrency || 50,
          };
        }
      } catch (e) {
        // ignore
      }
    },
  },
  mounted() {
    this.loadDetectionStrategy();
  },
};
</script>

<style scoped>
.action-group {
  border-bottom: 1px solid var(--line);
  padding-bottom: 8px;
}

.action-group:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.action-group-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.action-group-collapsible {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px 12px;
}

.action-group-collapsible[open] {
  padding-bottom: 12px;
}

.action-group-summary {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
  user-select: none;
}

.action-group-summary:hover {
  color: var(--ink);
}

.action-group-summary::marker {
  color: var(--muted);
}
</style>
