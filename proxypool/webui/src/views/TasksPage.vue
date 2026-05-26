<template>
            <section v-show="activePage === 'tasks'" class="task-dashboard fade-in">
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
                  <div class="action-bar task-action-bar">
                    <button class="btn btn-primary" :disabled="isActionRunning('importFiles')" @click="openImportFiles">
                      {{ buttonLabel('importFiles', '导入节点文件', '导入中...') }}
                    </button>
                    <button class="btn btn-secondary" :disabled="isActionRunning('runTest')" @click="onRunTest">
                      {{ buttonLabel('runTest', '立即测速', '测速中...') }}
                    </button>
                    <button class="btn btn-secondary" :disabled="isActionRunning('runSpeedTest')" @click="onRunSpeedTest">
                      {{ buttonLabel('runSpeedTest', '测试网速', '测试中...') }}
                    </button>
                    <button class="btn btn-secondary" :disabled="isActionRunning('runUnlockCheck')" @click="onRunUnlockCheck">
                      {{ buttonLabel('runUnlockCheck', '检测ChatGPT解锁', '检测中...') }}
                    </button>
                    <button class="btn btn-secondary" :disabled="isActionRunning('enrichGeo')" @click="onEnrichGeo">
                      {{ buttonLabel('enrichGeo', '补全IP位置', '补全中...') }}
                    </button>
                    <button class="btn btn-secondary" :disabled="isActionRunning('runIpPurity')" @click="onRunIpPurity">
                      {{ buttonLabel('runIpPurity', '检测IP纯净度', '检测中...') }}
                    </button>
                    <button class="btn btn-danger" :disabled="isActionRunning('deleteUnavailable')" @click="onDeleteUnavailable">
                      {{ buttonLabel('deleteUnavailable', '删除不可用', '删除中...') }}
                    </button>
                    <button class="btn btn-secondary" :disabled="isActionRunning('copySubscription')" @click="onCopySubscription">
                      {{ buttonLabel('copySubscription', '复制订阅', '复制中...') }}
                    </button>
                    <a href="/api/subscription?only_available=true" target="_blank" class="btn btn-secondary">导出链接</a>
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
                  <div v-if="!taskItems.length" class="empty-state">暂无任务</div>
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
                      <div class="task-progress">
                        <div class="task-progress-bar" :style="{ width: (task.progress || 0) + '%' }"></div>
                      </div>
                      <div class="task-meta">
                        <span>任务 {{ shortTaskId(task.task_id) }}</span>
                        <span>进度 {{ task.completed || 0 }}/{{ task.total || '-' }}</span>
                        <span class="text-emerald-600">成功 {{ task.success || 0 }}</span>
                        <span class="text-rose-600">失败 {{ task.failed || 0 }}</span>
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

export default {
  name: "TasksPage",
  mixins: [rootProxyMixin],
};
</script>
