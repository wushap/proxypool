<template>
            <section class="card fade-in">
              <div class="card-body">
                <!-- Breadcrumb -->
                <Breadcrumb :items="breadcrumbItems" />

                <!-- Loading State -->
                <div aria-live="polite" aria-atomic="true" class="sr-only">
                  <span v-if="isLoading">正在加载订阅数据</span>
                  <span v-else-if="loadError">加载失败: {{ loadError }}</span>
                  <span v-else-if="!isLoading && subscriptions">已加载 {{ subscriptions.length }} 个订阅</span>
                </div>
                <LoadingState v-if="isLoading" text="加载订阅数据中..." size="small" />
                <ErrorState v-else-if="loadError" :title="'加载失败'" :message="loadError" :retryable="true" @retry="onLoadSubscriptions" />
                <!-- Skeleton loading -->
                <div v-else-if="isLoadingSkeleton" class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 36px;"></th>
                        <th style="width: 30px;">序</th>
                        <th style="width: 50px;">ID</th>
                        <th style="width: 140px;">名称</th>
                        <th>链接</th>
                        <th style="width: 60px;">格式</th>
                        <th style="width: 60px;">分组</th>
                        <th style="width: 70px;">刷新</th>
                        <th style="width: 70px;">启用</th>
                        <th style="width: 80px;">状态</th>
                        <th style="width: 220px;">统计</th>
                        <th style="width: 140px;">上次刷新</th>
                        <th style="width: 100px;">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="i in 5" :key="'skeleton-' + i">
                        <td><div class="skeleton skeleton-checkbox"></div></td>
                        <td><div class="skeleton skeleton-text" style="width: 20px;"></div></td>
                        <td><div class="skeleton skeleton-text" style="width: 30px;"></div></td>
                        <td><div class="skeleton skeleton-text" style="width: 80px;"></div></td>
                        <td><div class="skeleton skeleton-text" style="width: 200px;"></div></td>
                        <td><div class="skeleton skeleton-badge"></div></td>
                        <td><div class="skeleton skeleton-badge"></div></td>
                        <td><div class="skeleton skeleton-badge"></div></td>
                        <td><div class="skeleton skeleton-button"></div></td>
                        <td><div class="skeleton skeleton-badge"></div></td>
                        <td><div class="skeleton skeleton-text" style="width: 180px;"></div></td>
                        <td><div class="skeleton skeleton-text" style="width: 60px;"></div></td>
                        <td><div class="skeleton skeleton-text" style="width: 80px;"></div></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div class="section-header">
                  <h2 class="section-title">订阅管理</h2>
                  <div class="btn-group">
                    <button @click="onRefreshAllSubscriptions" :disabled="isActionRunning('refreshAllSubscriptions')" class="btn btn-secondary" aria-label="刷新所有订阅">
                      {{ buttonLabel('refreshAllSubscriptions', '刷新全部', '刷新中...') }}
                    </button>
                    <el-tooltip content="删除所有最近一次刷新失败的订阅，此操作不可恢复" placement="top" :show-after="300">
                      <button @click="onDeleteUnavailableSubscriptions" :disabled="isActionRunning('deleteUnavailableSubscriptions') || unavailableCount === 0" class="btn btn-danger" :aria-label="'删除不可用订阅，共' + unavailableCount + '个'">
                        {{ buttonLabel('deleteUnavailableSubscriptions', '删除不可用' + (unavailableCount > 0 ? ` (${unavailableCount})` : ''), '删除中...') }}
                      </button>
                    </el-tooltip>
                    <button @click="onLoadSubscriptions" :disabled="isActionRunning('loadSubscriptions')" class="btn btn-secondary" aria-label="刷新订阅列表">
                      {{ buttonLabel('loadSubscriptions', '刷新列表', '刷新中...') }}
                    </button>
                  </div>
                </div>

                <!-- Bulk operations bar -->
                <div v-if="selectedSubscriptionIds.length > 0" class="selection-bar fade-in" style="margin-bottom: 12px;" role="status" aria-live="polite">
                  <span>已选中 <strong>{{ selectedSubscriptionIds.length }}</strong> 个订阅</span>
                  <div class="btn-group">
                    <button @click="onBatchEnableSubscriptions" :disabled="isActionRunning('batchEnable')" class="btn btn-xs btn-success" :aria-label="'批量启用' + selectedSubscriptionIds.length + '个订阅'">
                      {{ buttonLabel('batchEnable', '批量启用', '启用中...') }}
                    </button>
                    <button @click="onBatchDisableSubscriptions" :disabled="isActionRunning('batchDisable')" class="btn btn-xs btn-secondary" :aria-label="'批量停用' + selectedSubscriptionIds.length + '个订阅'">
                      {{ buttonLabel('batchDisable', '批量停用', '停用中...') }}
                    </button>
                    <button @click="onBatchDeleteSubscriptions" :disabled="isActionRunning('batchDelete')" class="btn btn-xs btn-danger" :aria-label="'批量删除' + selectedSubscriptionIds.length + '个订阅'">
                      {{ buttonLabel('batchDelete', '批量删除', '删除中...') }}
                    </button>
                    <span style="border-left: 1px solid var(--line); margin: 0 4px;" aria-hidden="true"></span>
                    <button v-if="subGroups.length" @click="batchAssignGroup" class="btn btn-xs btn-secondary" aria-label="分配选中订阅到分组">分配到分组</button>
                    <button @click="selectedSubscriptionIds = []" class="btn btn-xs btn-ghost" aria-label="取消选择">取消选择</button>
                  </div>
                </div>

                <!-- Subscription stats -->
                <div class="status-bar" style="margin-bottom: 12px;" role="status" aria-live="polite" aria-atomic="true">
                  <div class="status-item">
                    <span class="text-muted">总数</span>
                    <strong>{{ subscriptions.length }}</strong>
                  </div>
                  <div class="status-item">
                    <span class="text-muted">已启用</span>
                    <strong style="color: var(--success-text);">{{ subscriptions.filter(s => s.enabled).length }}</strong>
                  </div>
                  <div class="status-item">
                    <span class="text-muted">已停用</span>
                    <strong>{{ subscriptions.filter(s => !s.enabled).length }}</strong>
                  </div>
                  <div class="status-item">
                    <span class="text-muted">最近成功</span>
                    <strong style="color: var(--success-text);">{{ subscriptions.filter(s => s.last_status === 'success').length }}</strong>
                  </div>
                  <div class="status-item">
                    <span class="text-muted">最近失败</span>
                    <strong :style="{ color: subscriptions.filter(s => s.last_status === 'failed').length > 0 ? 'var(--danger-text)' : '' }">{{ subscriptions.filter(s => s.last_status === 'failed').length }}</strong>
                  </div>
                </div>

                <!-- Subscription Intelligence Section -->
                <div v-if="subscriptions.length > 0" class="subscription-intelligence" style="margin-bottom: 16px; padding: 16px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--line-soft);">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h3 style="font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
                      <span style="font-size: 16px;">🔍</span> 订阅智能分析
                    </h3>
                    <button @click="intelligenceExpanded = !intelligenceExpanded" class="btn btn-xs btn-ghost" :aria-expanded="intelligenceExpanded">
                      {{ intelligenceExpanded ? '收起' : '展开' }}
                    </button>
                  </div>

                  <div v-show="intelligenceExpanded">
                    <!-- Deduplication Analysis -->
                    <div class="intelligence-card" style="margin-bottom: 12px; padding: 12px; background: white; border-radius: 6px; border: 1px solid var(--line);">
                      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <h4 style="font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
                          <span style="color: var(--warning);">⚠️</span> 重复节点分析
                        </h4>
                        <span v-if="deduplicationStats.duplicateCount > 0" class="badge badge-warning" style="font-size: 11px;">
                          {{ deduplicationStats.duplicateCount }} 个重复
                        </span>
                        <span v-else class="badge badge-success" style="font-size: 11px;">无重复</span>
                      </div>
                      <div v-if="deduplicationStats.duplicateCount > 0" style="font-size: 12px; color: var(--muted); margin-bottom: 8px;">
                        <p>发现 {{ deduplicationStats.duplicateCount }} 个重复节点，来自 {{ deduplicationStats.duplicateSources.length }} 个订阅源</p>
                        <p>建议：合并重复订阅或删除低质量源</p>
                      </div>
                      <div v-if="deduplicationStats.topDuplicates.length > 0" style="margin-top: 8px;">
                        <div v-for="dup in deduplicationStats.topDuplicates.slice(0, 3)" :key="'dup-' + dup.key" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; background: var(--bg-secondary); border-radius: 4px; margin-bottom: 4px; font-size: 12px;">
                          <span style="color: var(--ink);">{{ dup.protocol }}://{{ dup.host }}:{{ dup.port }}</span>
                          <span style="color: var(--muted);">{{ dup.count }} 次出现</span>
                        </div>
                      </div>
                    </div>

                    <!-- Quality Scoring -->
                    <div class="intelligence-card" style="margin-bottom: 12px; padding: 12px; background: white; border-radius: 6px; border: 1px solid var(--line);">
                      <h4 style="font-size: 13px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                        <span style="color: var(--success);">📊</span> 订阅质量评分
                      </h4>
                      <div class="quality-scores" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px;">
                        <div v-for="sub in qualityScores.slice(0, 6)" :key="'qs-' + sub.id" style="padding: 8px; background: var(--bg-secondary); border-radius: 4px; text-align: center;">
                          <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ sub.name || '#' + sub.id }}</div>
                          <div style="font-size: 18px; font-weight: 700;" :style="{ color: sub.score >= 80 ? 'var(--success)' : sub.score >= 50 ? 'var(--warning)' : 'var(--danger)' }">
                            {{ sub.score }}
                          </div>
                          <div style="font-size: 10px; color: var(--muted);">{{ sub.nodeCount }} 节点 / {{ sub.reliability }}% 可靠</div>
                        </div>
                      </div>
                    </div>

                    <!-- Merge Recommendations -->
                    <div v-if="mergeRecommendations.length > 0" class="intelligence-card" style="margin-bottom: 12px; padding: 12px; background: white; border-radius: 6px; border: 1px solid var(--line);">
                      <h4 style="font-size: 13px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                        <span style="color: var(--info, #3b82f6);">🔗</span> 合并建议
                      </h4>
                      <div v-for="rec in mergeRecommendations.slice(0, 3)" :key="'merge-' + rec.id" style="padding: 8px; background: var(--bg-secondary); border-radius: 4px; margin-bottom: 6px; font-size: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                          <span style="font-weight: 500; color: var(--ink);">{{ rec.reason }}</span>
                          <span class="badge badge-info" style="font-size: 10px;">建议</span>
                        </div>
                        <div style="color: var(--muted);">{{ rec.description }}</div>
                        <div style="margin-top: 6px; display: flex; gap: 4px;">
                          <button @click="applyMergeRecommendation(rec)" class="btn btn-xs btn-primary" style="font-size: 11px;">应用</button>
                          <button @click="dismissMergeRecommendation(rec)" class="btn btn-xs btn-ghost" style="font-size: 11px;">忽略</button>
                        </div>
                      </div>
                    </div>

                    <!-- Health Monitoring -->
                    <div class="intelligence-card" style="margin-bottom: 12px; padding: 12px; background: white; border-radius: 6px; border: 1px solid var(--line);">
                      <h4 style="font-size: 13px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                        <span style="color: var(--danger);">💓</span> 健康监控
                      </h4>
                      <div class="health-metrics" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;">
                        <div style="text-align: center; padding: 8px; background: var(--bg-secondary); border-radius: 4px;">
                          <div style="font-size: 20px; font-weight: 700; color: var(--success);">{{ healthMetrics.healthyCount }}</div>
                          <div style="font-size: 11px; color: var(--muted);">健康</div>
                        </div>
                        <div style="text-align: center; padding: 8px; background: var(--bg-secondary); border-radius: 4px;">
                          <div style="font-size: 20px; font-weight: 700; color: var(--warning);">{{ healthMetrics.warningCount }}</div>
                          <div style="font-size: 11px; color: var(--muted);">警告</div>
                        </div>
                        <div style="text-align: center; padding: 8px; background: var(--bg-secondary); border-radius: 4px;">
                          <div style="font-size: 20px; font-weight: 700; color: var(--danger);">{{ healthMetrics.criticalCount }}</div>
                          <div style="font-size: 11px; color: var(--muted);">严重</div>
                        </div>
                      </div>
                      <div v-if="healthMetrics.issues.length > 0" style="margin-top: 8px;">
                        <div v-for="(issue, idx) in healthMetrics.issues.slice(0, 3)" :key="'issue-' + idx" style="padding: 6px 8px; background: var(--danger-bg); border-radius: 4px; margin-bottom: 4px; font-size: 12px; color: var(--danger-text);">
                          {{ issue }}
                        </div>
                      </div>
                    </div>

                    <!-- Auto-optimization Suggestions -->
                    <div v-if="optimizationSuggestions.length > 0" class="intelligence-card" style="padding: 12px; background: white; border-radius: 6px; border: 1px solid var(--line);">
                      <h4 style="font-size: 13px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                        <span style="color: var(--accent);">⚡</span> 优化建议
                      </h4>
                      <div v-for="(suggestion, idx) in optimizationSuggestions.slice(0, 4)" :key="'opt-' + idx" style="padding: 8px; background: var(--bg-secondary); border-radius: 4px; margin-bottom: 6px; font-size: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                          <span style="font-weight: 500; color: var(--ink);">{{ suggestion.title }}</span>
                          <span class="badge" :class="suggestion.priority === 'high' ? 'badge-danger' : suggestion.priority === 'medium' ? 'badge-warning' : 'badge-neutral'" style="font-size: 10px;">
                            {{ suggestion.priority === 'high' ? '高' : suggestion.priority === 'medium' ? '中' : '低' }}
                          </span>
                        </div>
                        <div style="color: var(--muted);">{{ suggestion.description }}</div>
                        <div style="margin-top: 6px;">
                          <button @click="applyOptimization(suggestion)" class="btn btn-xs btn-secondary" style="font-size: 11px;">查看详情</button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Add subscription form -->
                <div class="form-row-4" style="gap: 8px; margin-bottom: 12px;">
                  <input v-model.trim="subscriptionForm.name" type="text" placeholder="订阅名称" class="input" style="flex: 1;" aria-label="订阅名称" />
                  <input ref="subscriptionUrlInput" v-model.trim="subscriptionForm.url" type="text" placeholder="订阅链接 URL" class="input" style="flex: 2;" aria-label="订阅链接URL" />
                  <button @click="onTestSubscriptionUrl" :disabled="isActionRunning('testSubUrl') || !subscriptionForm.url" class="btn btn-secondary" style="flex: 0 0 auto;" aria-label="测试订阅URL是否可访问">
                    {{ buttonLabel('testSubUrl', '测试URL', '测试中...') }}
                  </button>
                  <button @click="onCreateSubscription" :disabled="isActionRunning('createSubscription')" class="btn btn-primary" style="flex: 0 0 auto;" aria-label="添加新订阅">
                    {{ buttonLabel('createSubscription', '添加订阅', '添加中...') }}
                  </button>
                </div>
                <div v-if="subscriptionTestResult" class="subscription-test-result" :class="subscriptionTestResult.success ? 'test-success' : 'test-fail'" style="margin-bottom: 12px; padding: 8px 12px; border-radius: 6px; font-size: 12px;">
                  <span v-if="subscriptionTestResult.success" style="color: var(--success-text);">✓ URL 可访问，解析到 {{ subscriptionTestResult.proxyCount || 0 }} 个代理节点</span>
                  <span v-else style="color: var(--danger-text);">✗ {{ subscriptionTestResult.error || 'URL 无法访问' }}</span>
                </div>

                <!-- Bulk import -->
                <details class="details" style="margin-bottom: 12px;">
                  <summary>批量导入订阅（每行一个 URL）</summary>
                  <textarea v-model.trim="bulkImportUrls" class="textarea input-mono" placeholder="https://example.com/sub1&#10;https://example.com/sub2&#10;..." style="margin-top: 8px; min-height: 80px;" aria-label="批量导入订阅链接，每行一个URL"></textarea>
                  <button @click="onBulkImportSubscriptions" :disabled="isActionRunning('bulkImportSubs')" class="btn btn-primary" style="margin-top: 6px;" aria-label="批量导入订阅链接">
                    {{ buttonLabel('bulkImportSubs', '批量导入', '导入中...') }}
                  </button>
                </details>

                <!-- Global update proxy -->
                <div class="form-row-4" style="gap: 8px; margin-bottom: 12px;">
                  <input v-model.trim="subscriptionUpdateProxyRef" list="proxy-key-options" type="text" placeholder="全局更新代理序号(可选 如 #12)" class="input input-mono" style="grid-column: span 3;" />
                  <button @click="onSaveSubscriptionUpdateProxy" :disabled="isActionRunning('saveSubUpdateProxy')" class="btn btn-secondary">
                    {{ buttonLabel('saveSubUpdateProxy', '保存', '保存中...') }}
                  </button>
                </div>

                <p class="form-hint" style="margin-bottom: 12px;">节点来源将自动标记为 `subscription#ID:名称|URL`，可在节点表来源列过滤。</p>

                <!-- Format help -->
                <div style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                  <el-tooltip placement="right" :show-after="200" width="360">
                    <template #content>
                      <div style="max-width: 340px; line-height: 1.6;">
                        <div style="font-weight: 600; margin-bottom: 6px;">支持的订阅格式</div>
                        <div style="font-size: 12px; margin-bottom: 4px;"><strong>Clash</strong> — YAML 格式，包含 proxies 字段的配置文件</div>
                        <div style="font-size: 12px; margin-bottom: 4px;"><strong>V2Ray</strong> — Base64 编码的节点列表或 JSON 格式</div>
                        <div style="font-size: 12px; margin-bottom: 4px;"><strong>Shadowsocks</strong> — ss:// 或 ssr:// 协议链接</div>
                        <div style="font-size: 12px; margin-bottom: 8px;"><strong>自动</strong> — 系统将自动检测格式</div>
                        <div style="font-size: 11px; color: #9ca3af;">格式通过 URL 特征自动识别，如无法识别则标记为"未知"或"自动"</div>
                      </div>
                    </template>
                    <button @click="formatHelpVisible = true" class="btn btn-xs btn-ghost" style="font-size: 12px;">
                      格式帮助 <span style="font-size: 10px; opacity: 0.6;">?</span>
                    </button>
                  </el-tooltip>
                </div>

                <!-- Pagination -->
                <div class="pagination" role="navigation" aria-label="订阅列表分页">
                  <div class="pagination-info">
                    <span class="text-muted">每页</span>
                    <select v-model.number="pagination.subscriptions.perPage" @change="onPaginationPageSizeChange('subscriptions')" class="select input-sm" style="width: 56px;" aria-label="每页显示数量">
                      <option v-for="n in pageSizeOptions" :key="'sub-' + n" :value="n">{{ n }}</option>
                    </select>
                    <span class="text-muted">{{ pageIndicator('subscriptions') }}</span>
                  </div>
                  <div class="pagination-nav">
                    <button @click="goPrevPage('subscriptions')" :disabled="!canPrevPage('subscriptions')" class="btn btn-xs btn-ghost" aria-label="上一页">上一页</button>
                    <button @click="goNextPage('subscriptions')" :disabled="!canNextPage('subscriptions')" class="btn btn-xs btn-ghost" aria-label="下一页">下一页</button>
                  </div>
                </div>

                <!-- Empty State -->
                <EmptyState v-if="!subscriptions.length" title="暂无订阅" description="订阅是一种自动获取代理节点的方式，系统会定期从订阅链接获取最新的节点列表" size="normal">
                  <template #actions>
                    <button class="btn btn-xs btn-primary" @click="focusSubscriptionUrlInput">添加订阅</button>
                  </template>
                </EmptyState>
                <div v-if="!subscriptions.length" class="subscription-examples" style="margin-top: 16px; padding: 12px; background: var(--bg-secondary); border-radius: 6px;">
                  <p style="font-size: 12px; color: var(--muted); margin-bottom: 8px;">示例订阅链接格式：</p>
                  <div style="font-size: 11px; font-family: monospace; color: var(--text-secondary); line-height: 1.6;">
                    <div>https://example.com/sub?token=xxx</div>
                    <div>https://example.com/clash/config.yaml</div>
                    <div>https://example.com/v2ray/subscribe?user=xxx</div>
                  </div>
                  <p style="font-size: 11px; color: var(--muted); margin-top: 8px;">支持 V2Ray、Clash、Shadowsocks 等主流订阅格式</p>
                </div>

                <!-- Table -->
                <div v-if="!isLoading && !loadError && !isLoadingSkeleton" class="table-wrap">
                  <!-- Group tabs -->
                  <div class="sub-group-tabs" style="margin-bottom: 12px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap;" role="tablist" aria-label="订阅分组筛选">
                    <button v-for="g in groupOptions" :key="'gtab-' + (g.id || 'all')"
                      @click="selectedGroupId = g.id"
                      class="btn btn-xs"
                      :class="selectedGroupId === g.id ? 'btn-primary' : 'btn-ghost'"
                      role="tab"
                      :aria-selected="selectedGroupId === g.id"
                      :aria-label="g.name + '分组，共' + g.count + '个订阅'">
                      {{ g.name }} <span class="text-muted" style="font-size: 10px;">({{ g.count }})</span>
                    </button>
                    <button @click="openGroupDialog('create')" class="btn btn-xs btn-ghost" style="margin-left: 4px;" aria-label="新建订阅分组">+ 新建分组</button>
                    <button v-if="selectedGroupId" @click="openGroupDialog('edit', selectedGroupId)" class="btn btn-xs btn-ghost" aria-label="编辑当前分组">编辑分组</button>
                    <button v-if="selectedGroupId" @click="deleteGroup(selectedGroupId)" class="btn btn-xs btn-ghost" style="color: var(--danger-text);" aria-label="删除当前分组">删除分组</button>
                  </div>

                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 36px;">
                          <input type="checkbox" :checked="areAllPaginatedSubscriptionsSelected()" :disabled="!filteredSubscriptions.length" @change="toggleAllPaginatedSubscriptions($event.target.checked)" aria-label="选择所有订阅" />
                        </th>
                        <th style="width: 30px;" title="优先级">序</th>
                        <th style="width: 50px;">ID</th>
                        <th style="width: 140px;">名称</th>
                        <th>链接</th>
                        <th style="width: 60px;">格式</th>
                        <th style="width: 60px;">分组</th>
                        <th style="width: 70px;">刷新</th>
                        <th style="width: 70px;">启用</th>
                        <th style="width: 80px;">状态</th>
                        <th style="width: 220px;" title="解析/新增/更新/无效/去重">统计</th>
                        <th style="width: 140px;">上次刷新</th>
                        <th style="width: 100px;">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(item, rowIdx) in filteredSubscriptions" :key="item.id">
                        <td><input v-model="selectedSubscriptionIds" type="checkbox" :value="item.id" :aria-label="'选择订阅' + (item.name || item.id)" /></td>
                        <td>
                          <div class="btn-group btn-group-xs" style="flex-direction: column; gap: 0;">
                            <button @click="moveSubPriority(item.id, -1)" :disabled="rowIdx === 0" class="btn btn-xs btn-ghost priority-btn" :aria-label="'提升' + (item.name || item.id) + '优先级'">&#9650;</button>
                            <button @click="moveSubPriority(item.id, 1)" :disabled="rowIdx === filteredSubscriptions.length - 1" class="btn btn-xs btn-ghost priority-btn" :aria-label="'降低' + (item.name || item.id) + '优先级'">&#9660;</button>
                          </div>
                        </td>
                        <td class="mono text-muted">{{ item.id }}</td>
                        <td><input :value="item.name || ''" @change="onRenameSubscription(item, $event.target.value)" type="text" class="inline-input" :aria-label="'订阅名称，当前为' + (item.name || '未命名')" /></td>
                        <td class="mono text-muted text-xs truncate" style="max-width: 200px;" :title="item.url">{{ shortSubscriptionUrl(item.url) }}</td>
                        <td>
                          <span class="badge badge-sm" :class="getFormatBadgeClass(detectSubscriptionFormat(item))">
                            {{ detectSubscriptionFormat(item) }}
                          </span>
                        </td>
                        <td>
                          <select :value="getSubGroup(item.id)" @change="setSubGroup(item.id, $event.target.value)" class="select input-sm" style="width: 60px; font-size: 10px; padding: 1px 2px;" :aria-label="'订阅分组，当前为' + (getSubGroup(item.id) || '无')">
                            <option value="">无</option>
                            <option v-for="g in subGroups" :key="'gopt-' + g.id" :value="g.id">{{ g.name }}</option>
                          </select>
                        </td>
                        <td>
                          <select :value="getSubFrequency(item.id)" @change="setSubFrequency(item.id, $event.target.value)" class="select input-sm" style="width: 60px; font-size: 10px; padding: 1px 2px;" :aria-label="'刷新频率，当前为' + getSubFrequency(item.id)">
                            <option value="manual">手动</option>
                            <option value="hourly">1小时</option>
                            <option value="6h">6小时</option>
                            <option value="12h">12小时</option>
                            <option value="daily">每天</option>
                          </select>
                        </td>
                        <td>
                          <button @click="onToggleSubscription(item)" :disabled="isActionRunning('toggleSub-' + item.id)" class="btn btn-xs" :class="item.enabled ? 'btn-success' : 'btn-ghost'" :aria-label="(item.enabled ? '停用' : '启用') + '订阅' + (item.name || item.id)">
                            {{ item.enabled ? '启用' : '停用' }}
                          </button>
                        </td>
                        <td><span class="badge" :class="item.last_status === 'success' ? 'badge-success' : item.last_status === 'failed' ? 'badge-danger' : 'badge-neutral'" :aria-label="'状态：' + (item.last_status || '未知')">{{ item.last_status || '-' }}</span></td>
                        <td>
                          <div class="subscription-stats" :title="'解析 ' + (item.last_parsed || 0) + ' / 新增 ' + (item.last_inserted || 0) + ' / 更新 ' + (item.last_updated || 0) + ' / 无效 ' + (item.last_invalid || 0) + ' / 去重 ' + (item.last_deduped || 0)" :aria-label="'统计信息：解析' + (item.last_parsed || 0) + '个，新增' + (item.last_inserted || 0) + '个，更新' + (item.last_updated || 0) + '个，无效' + (item.last_invalid || 0) + '个，去重' + (item.last_deduped || 0) + '个'">
                            <span class="stat-pill">解析 {{ item.last_parsed || 0 }}</span>
                            <span v-if="getNodeCountTrend(item)" class="stat-pill" :class="getNodeCountTrend(item) === 'increasing' ? 'stat-pill-success' : getNodeCountTrend(item) === 'decreasing' ? 'stat-pill-danger' : ''">
                              {{ getNodeCountTrendLabel(item) }}
                            </span>
                            <span class="stat-pill stat-pill-success">新增 {{ item.last_inserted || 0 }}</span>
                            <span class="stat-pill">更新 {{ item.last_updated || 0 }}</span>
                            <span class="stat-pill" :class="(item.last_invalid || 0) > 0 ? 'stat-pill-danger' : ''">无效 {{ item.last_invalid || 0 }}</span>
                            <span class="stat-pill">去重 {{ item.last_deduped || 0 }}</span>
                          </div>
                        </td>
                        <td class="text-xs" :style="freshnessStyle(item.last_fetched_at)" :title="formatTime(item.last_fetched_at)">{{ freshnessText(item.last_fetched_at) }}</td>
                        <td>
                          <div class="btn-group">
                            <button @click="showPreview(item)" class="btn btn-xs btn-ghost" :aria-label="'预览订阅' + (item.name || item.id) + '的节点'">预览</button>
                            <button @click="onRefreshSubscription(item.id)" :disabled="isActionRunning('refreshSub-' + item.id)" class="btn btn-xs btn-secondary" :aria-label="'刷新订阅' + (item.name || item.id)">刷新</button>
                            <button @click="onDeleteSubscription(item.id)" :disabled="isActionRunning('deleteSub-' + item.id)" class="btn btn-xs btn-danger" :aria-label="'删除订阅' + (item.name || item.id)">删除</button>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- Subscription Analytics Section -->
                <div v-if="subscriptions.length > 0" class="subscription-analytics" style="margin-top: 24px;">
                  <h3 class="section-title" style="margin-bottom: 16px;">订阅分析</h3>

                  <!-- Best Subscription Sources -->
                  <div class="analytics-card" style="margin-bottom: 16px;">
                    <div class="analytics-card-header">
                      <span class="analytics-card-title">最佳订阅源</span>
                      <span class="text-xs text-muted">按节点数和可靠性排名</span>
                    </div>
                    <div class="analytics-card-body">
                      <div v-if="bestSubscriptions.length > 0" class="best-subs-list">
                        <div v-for="(sub, idx) in bestSubscriptions" :key="'best-' + sub.id" class="best-sub-item">
                          <span class="best-sub-rank" :class="idx === 0 ? 'rank-gold' : idx === 1 ? 'rank-silver' : idx === 2 ? 'rank-bronze' : ''">
                            #{{ idx + 1 }}
                          </span>
                          <div class="best-sub-info">
                            <span class="best-sub-name">{{ sub.name || '订阅 #' + sub.id }}</span>
                            <span class="best-sub-meta text-xs text-muted">
                              {{ sub.nodeCount }} 节点 · 可靠性 {{ sub.reliability }}%
                            </span>
                          </div>
                          <div class="best-sub-bar">
                            <div class="best-sub-bar-fill" :style="{ width: sub.score + '%' }"></div>
                          </div>
                        </div>
                      </div>
                      <div v-else class="text-xs text-muted">暂无数据</div>
                    </div>
                  </div>

                  <!-- Refresh Trends -->
                  <div class="analytics-card" style="margin-bottom: 16px;">
                    <div class="analytics-card-header">
                      <span class="analytics-card-title">刷新趋势</span>
                      <span class="text-xs text-muted">最近10次刷新结果</span>
                    </div>
                    <div class="analytics-card-body">
                      <div v-if="refreshTrendData" class="refresh-trend">
                        <div class="refresh-trend-stats">
                          <div class="refresh-stat">
                            <span class="refresh-stat-value text-success">{{ refreshTrendData.successCount }}</span>
                            <span class="refresh-stat-label">成功</span>
                          </div>
                          <div class="refresh-stat">
                            <span class="refresh-stat-value text-danger">{{ refreshTrendData.failCount }}</span>
                            <span class="refresh-stat-label">失败</span>
                          </div>
                          <div class="refresh-stat">
                            <span class="refresh-stat-value">{{ refreshTrendData.successRate }}%</span>
                            <span class="refresh-stat-label">成功率</span>
                          </div>
                        </div>
                        <div class="refresh-trend-dots">
                          <span v-for="(result, i) in refreshTrendData.results" :key="'rt-' + i"
                            class="refresh-dot"
                            :class="result ? 'refresh-dot-success' : 'refresh-dot-fail'"
                            :title="result ? '成功' : '失败'">
                          </span>
                        </div>
                      </div>
                      <div v-else class="text-xs text-muted">暂无刷新记录</div>
                    </div>
                  </div>

                  <!-- Geographic Coverage -->
                  <div class="analytics-card">
                    <div class="analytics-card-header">
                      <span class="analytics-card-title">地理覆盖</span>
                      <span class="text-xs text-muted">按国家/地区统计节点分布</span>
                    </div>
                    <div class="analytics-card-body">
                      <div v-if="geoCoverageData.length > 0" class="geo-coverage">
                        <div v-for="geo in geoCoverageData.slice(0, 8)" :key="'geo-' + geo.country" class="geo-coverage-item">
                          <span class="geo-coverage-country">{{ geo.country || '未知' }}</span>
                          <div class="geo-coverage-bar-container">
                            <div class="geo-coverage-bar" :style="{ width: geo.percentage + '%' }"></div>
                          </div>
                          <span class="geo-coverage-count text-xs">{{ geo.count }}</span>
                        </div>
                      </div>
                      <div v-else class="text-xs text-muted">暂无地理数据</div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <!-- Format Help Dialog -->
            <el-dialog v-model="formatHelpVisible" title="订阅格式说明" width="min(500px, 95vw)" append-to-body aria-labelledby="format-help-dialog-title" aria-modal="true">
              <h3 id="format-help-dialog-title" class="sr-only">订阅格式说明</h3>
              <div class="format-help-content">
                <p class="text-muted text-sm" style="margin-bottom: 16px;">系统支持以下主流代理订阅格式，格式通过 URL 特征自动识别：</p>
                <div class="format-help-grid">
                  <div class="format-help-card">
                    <div class="format-help-card-header">
                      <span class="badge badge-sm badge-clash">Clash</span>
                    </div>
                    <div class="format-help-card-body">
                      <div class="text-xs">YAML 格式配置文件，包含 <code>proxies</code> 字段</div>
                      <div class="text-xs text-muted" style="margin-top: 4px;">URL 特征：含 /clash、.yaml、.yml</div>
                    </div>
                  </div>
                  <div class="format-help-card">
                    <div class="format-help-card-header">
                      <span class="badge badge-sm badge-v2ray">V2Ray</span>
                    </div>
                    <div class="format-help-card-body">
                      <div class="text-xs">Base64 编码的节点列表或 JSON 格式</div>
                      <div class="text-xs text-muted" style="margin-top: 4px;">URL 特征：含 subscribe、v2ray、token=</div>
                    </div>
                  </div>
                  <div class="format-help-card">
                    <div class="format-help-card-header">
                      <span class="badge badge-sm badge-ss">SS</span>
                    </div>
                    <div class="format-help-card-body">
                      <div class="text-xs">Shadowsocks/ShadowsocksR 协议链接</div>
                      <div class="text-xs text-muted" style="margin-top: 4px;">URL 特征：含 /ss、shadowsocks、/ssr</div>
                    </div>
                  </div>
                  <div class="format-help-card">
                    <div class="format-help-card-header">
                      <span class="badge badge-sm badge-neutral">自动</span>
                    </div>
                    <div class="format-help-card-body">
                      <div class="text-xs">无法通过 URL 识别格式时，系统将自动检测</div>
                      <div class="text-xs text-muted" style="margin-top: 4px;">解析成功后可能显示为"未知"</div>
                    </div>
                  </div>
                </div>
                <div style="margin-top: 16px; padding: 10px; background: var(--bg-secondary); border-radius: 6px; font-size: 11px; color: var(--muted);">
                  <strong>节点数趋势</strong>：统计列中的箭头图标表示节点数量变化趋势。绿色上箭头表示节点增加，红色下箭头表示减少，等号表示稳定。趋势数据保存在本地浏览器中。
                </div>
              </div>
              <template #footer>
                <button class="btn btn-secondary" @click="formatHelpVisible = false">关闭</button>
              </template>
            </el-dialog>

            <!-- Subscription Content Preview Dialog -->
            <el-dialog v-model="previewDialogVisible" :title="'订阅节点预览 — ' + previewSubscriptionName" width="min(700px, 95vw)" append-to-body aria-labelledby="preview-dialog-title" aria-modal="true">
              <h3 id="preview-dialog-title" class="sr-only">订阅节点预览</h3>
              <LoadingState v-if="previewLoading" text="加载节点数据中..." size="small" />
              <div v-else-if="previewProxies.length" class="preview-content">
                <p class="text-muted text-sm" style="margin-bottom: 12px;">该订阅关联的最近节点（最多显示 20 个）：</p>
                <div class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 40px;">#</th>
                        <th>协议</th>
                        <th>名称</th>
                        <th>地址</th>
                        <th style="width: 70px;">状态</th>
                        <th style="width: 80px;">延迟</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(proxy, idx) in previewProxies" :key="'preview-' + idx">
                        <td class="text-muted text-xs">{{ idx + 1 }}</td>
                        <td><span class="font-semibold text-xs">{{ proxy.protocol }}</span></td>
                        <td class="text-xs">{{ proxy.name || '-' }}</td>
                        <td class="mono text-xs text-muted">{{ proxy.host }}:{{ proxy.port }}</td>
                        <td>
                          <span class="badge badge-sm" :class="proxy.available ? 'badge-success' : 'badge-danger'">
                            {{ proxy.available ? 'UP' : 'DOWN' }}
                          </span>
                        </td>
                        <td class="text-xs">{{ proxy.latency_ms ? proxy.latency_ms + 'ms' : '-' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <EmptyState v-else title="暂无节点数据" description="该订阅尚未解析出节点，或节点已被删除" size="small" />
              <template #footer>
                <button class="btn btn-secondary" @click="previewDialogVisible = false">关闭</button>
              </template>
            </el-dialog>

            <!-- Group Dialog -->
            <el-dialog v-model="groupDialogVisible" :title="groupFormMode === 'create' ? '新建订阅分组' : '编辑订阅分组'" width="min(400px, 95vw)" append-to-body aria-labelledby="group-dialog-title" aria-modal="true">
              <h3 id="group-dialog-title" class="sr-only">{{ groupFormMode === 'create' ? '新建订阅分组' : '编辑订阅分组' }}</h3>
              <el-form label-position="top">
                <el-form-item label="分组名称">
                  <el-input v-model="groupFormName" placeholder="例如: 亚洲节点、欧美节点" maxlength="30" show-word-limit @keyup.enter="submitGroupForm" />
                </el-form-item>
              </el-form>
              <template #footer>
                <button class="btn btn-secondary" @click="groupDialogVisible = false">取消</button>
                <button class="btn btn-primary" @click="submitGroupForm" :disabled="!groupFormName.trim()">{{ groupFormMode === 'create' ? '创建' : '保存' }}</button>
              </template>
            </el-dialog>

            <!-- Batch Assign Group Dialog -->
            <el-dialog v-model="batchGroupDialogVisible" title="分配到分组" width="min(350px, 95vw)" append-to-body aria-labelledby="batch-group-dialog-title" aria-modal="true">
              <h3 id="batch-group-dialog-title" class="sr-only">分配到分组</h3>
              <p class="text-muted text-sm" style="margin-bottom: 12px;">将选中的 {{ batchGroupCount }} 个订阅分配到分组：</p>
              <el-select v-model="batchGroupTarget" placeholder="选择分组" style="width: 100%;">
                <el-option v-for="g in subGroups" :key="'bg-' + g.id" :label="g.name" :value="g.id"></el-option>
                <el-option label="移除分组" value="__remove__"></el-option>
              </el-select>
              <template #footer>
                <button class="btn btn-secondary" @click="batchGroupDialogVisible = false">取消</button>
                <button class="btn btn-primary" @click="confirmBatchAssignGroup" :disabled="!batchGroupTarget">确认</button>
              </template>
            </el-dialog>
</template>

<script>
import { rootProxyMixin } from "../rootProxyMixin";
import Breadcrumb from '../components/layout/Breadcrumb.vue';
import EmptyState from '../components/common/EmptyState.vue';
import LoadingState from '../components/common/LoadingState.vue';
import ErrorState from '../components/common/ErrorState.vue';

export default {
  name: "SubscriptionsPage",
  components: {
    Breadcrumb,
    EmptyState,
    LoadingState,
    ErrorState,
  },
  mixins: [rootProxyMixin],
  data() {
    return {
      isLoading: false,
      isLoadingSkeleton: false,
      selectedSubscriptionIds: [],
      subscriptionTestResult: null,
      loadError: null,
      formatHelpVisible: false,
      nodeCountHistory: JSON.parse(localStorage.getItem('proxypool-sub-node-counts') || '{}'),
      previewDialogVisible: false,
      previewSubscriptionName: '',
      previewProxies: [],
      previewLoading: false,
      // Groups & scheduling
      subGroups: JSON.parse(localStorage.getItem('proxypool-sub-groups') || '[]'),
      subMeta: JSON.parse(localStorage.getItem('proxypool-sub-meta') || '{}'),
      selectedGroupId: null,
      groupDialogVisible: false,
      groupFormName: '',
      groupFormMode: 'create',
      editingGroupId: null,
      batchGroupDialogVisible: false,
      batchGroupTarget: '',
      batchGroupCount: 0,
      // Analytics data
      refreshHistory: JSON.parse(localStorage.getItem('proxypool-sub-refresh-history') || '{}'),
      subscriptionProxies: {},
      // Intelligence features
      intelligenceExpanded: true,
      dismissedRecommendations: JSON.parse(localStorage.getItem('proxypool-sub-dismissed-recs') || '[]'),
    };
  },
  computed: {
    breadcrumbItems() {
      return [
        { label: '首页', path: '/', onClick: () => this.selectPage('dashboard') },
        { label: '订阅管理' },
      ];
    },
    unavailableCount() {
      return this.subscriptions.filter(s => s.last_status === 'failed').length;
    },
    filteredSubscriptions() {
      if (!this.selectedGroupId) return this.paginatedSubscriptions;
      return this.paginatedSubscriptions.filter(s => this.getSubGroup(s.id) === this.selectedGroupId);
    },
    groupOptions() {
      return [
        { id: null, name: '全部', count: this.subscriptions.length },
        ...this.subGroups.map(g => ({
          id: g.id,
          name: g.name,
          count: this.subscriptions.filter(s => this.getSubGroup(s.id) === g.id).length,
        })),
      ];
    },

    // Intelligence computed properties
    deduplicationStats() {
      const nodeMap = new Map();
      const sourceMap = new Map();

      for (const sub of this.subscriptions) {
        const proxies = this.subscriptionProxies[sub.id] || [];
        for (const proxy of proxies) {
          const key = `${proxy.protocol}://${proxy.host}:${proxy.port}`;
          if (!nodeMap.has(key)) {
            nodeMap.set(key, { count: 0, sources: new Set(), protocol: proxy.protocol, host: proxy.host, port: proxy.port });
          }
          const node = nodeMap.get(key);
          node.count++;
          node.sources.add(sub.id);
          sourceMap.set(key, node);
        }
      }

      const duplicates = Array.from(sourceMap.values()).filter(n => n.count > 1);
      const duplicateCount = duplicates.reduce((sum, n) => sum + (n.count - 1), 0);
      const duplicateSources = [...new Set(duplicates.flatMap(n => [...n.sources]))];

      return {
        duplicateCount,
        duplicateSources,
        topDuplicates: duplicates.sort((a, b) => b.count - a.count).slice(0, 5),
      };
    },

    qualityScores() {
      return this.subscriptions
        .filter(s => s.enabled)
        .map(s => {
          const nodeCount = this.getSubscriptionNodeCount(s);
          const reliability = this.getSubscriptionReliability(s);
          const freshness = this.getSubscriptionFreshness(s);
          const score = Math.round((nodeCount * 0.4) + (reliability * 0.4) + (freshness * 0.2));
          return {
            id: s.id,
            name: s.name || `#${s.id}`,
            nodeCount,
            reliability,
            freshness,
            score: Math.min(100, score),
          };
        })
        .sort((a, b) => b.score - a.score);
    },

    mergeRecommendations() {
      const recommendations = [];

      // Check for subscriptions with similar names
      const nameGroups = new Map();
      for (const sub of this.subscriptions) {
        const normalizedName = (sub.name || '').toLowerCase().replace(/[^a-z0-9一-龥]/g, '');
        if (normalizedName.length > 3) {
          if (!nameGroups.has(normalizedName)) nameGroups.set(normalizedName, []);
          nameGroups.get(normalizedName).push(sub);
        }
      }

      for (const [name, subs] of nameGroups) {
        if (subs.length > 1) {
          recommendations.push({
            id: `name-${name}`,
            type: 'merge_similar_names',
            reason: '相似名称订阅',
            description: `${subs.length} 个订阅名称相似，可能提供相同的节点`,
            subscriptions: subs.map(s => s.id),
          });
        }
      }

      // Check for subscriptions with very few nodes
      const lowNodeSubs = this.subscriptions.filter(s => s.enabled && this.getSubscriptionNodeCount(s) < 5 && s.last_status === 'success');
      if (lowNodeSubs.length > 1) {
        recommendations.push({
          id: 'low-nodes',
          type: 'merge_low_nodes',
          reason: '低节点数订阅',
          description: `${lowNodeSubs.length} 个订阅节点数少于 5 个，建议合并或删除`,
          subscriptions: lowNodeSubs.map(s => s.id),
        });
      }

      return recommendations.filter(r => !this.dismissedRecommendations.includes(r.id));
    },

    healthMetrics() {
      let healthyCount = 0;
      let warningCount = 0;
      let criticalCount = 0;
      const issues = [];

      for (const sub of this.subscriptions) {
        if (!sub.enabled) continue;

        const reliability = this.getSubscriptionReliability(sub);
        const nodeCount = this.getSubscriptionNodeCount(sub);
        const lastStatus = sub.last_status;

        if (lastStatus === 'failed' || reliability < 50) {
          criticalCount++;
          issues.push(`${sub.name || '#' + sub.id}: 刷新失败或可靠率低于 50%`);
        } else if (reliability < 80 || nodeCount < 10) {
          warningCount++;
          if (nodeCount < 10) {
            issues.push(`${sub.name || '#' + sub.id}: 节点数较少 (${nodeCount})`);
          }
        } else {
          healthyCount++;
        }
      }

      return { healthyCount, warningCount, criticalCount, issues };
    },

    optimizationSuggestions() {
      const suggestions = [];

      // Suggestion: Enable auto-refresh for manual subscriptions
      const manualSubs = this.subscriptions.filter(s => s.enabled && this.getSubFrequency(s.id) === 'manual');
      if (manualSubs.length > 2) {
        suggestions.push({
          id: 'enable-auto-refresh',
          title: '启用自动刷新',
          description: `${manualSubs.length} 个订阅设置为手动刷新，建议启用自动刷新以保持节点最新`,
          priority: 'medium',
          action: 'enable_auto_refresh',
          subscriptions: manualSubs.map(s => s.id),
        });
      }

      // Suggestion: Delete failed subscriptions
      const failedSubs = this.subscriptions.filter(s => s.last_status === 'failed' && s.enabled);
      if (failedSubs.length > 0) {
        suggestions.push({
          id: 'delete-failed',
          title: '删除失败订阅',
          description: `${failedSubs.length} 个订阅最近刷新失败，建议检查或删除`,
          priority: 'high',
          action: 'delete_failed',
          subscriptions: failedSubs.map(s => s.id),
        });
      }

      // Suggestion: Consolidate duplicate nodes
      if (this.deduplicationStats.duplicateCount > 10) {
        suggestions.push({
          id: 'consolidate-duplicates',
          title: '合并重复节点',
          description: `发现 ${this.deduplicationStats.duplicateCount} 个重复节点，建议合并订阅源`,
          priority: 'medium',
          action: 'consolidate_duplicates',
        });
      }

      return suggestions;
    },
  },
  methods: {
    focusSubscriptionUrlInput() {
      this.$nextTick(() => {
        this.$refs.subscriptionUrlInput?.focus();
      });
    },
    async onLoadSubscriptions() {
      this.loadError = null;
      this.isLoadingSkeleton = true;
      this.isLoading = true;
      try {
        await this.loadSubscriptions();
      } catch (e) {
        this.loadError = e.message || '加载订阅数据失败';
      } finally {
        this.isLoading = false;
        setTimeout(() => {
          this.isLoadingSkeleton = false;
        }, 300);
      }
    },
    areAllPaginatedSubscriptionsSelected() {
      if (!this.filteredSubscriptions.length) return false;
      return this.filteredSubscriptions.every(s => this.selectedSubscriptionIds.includes(s.id));
    },
    toggleAllPaginatedSubscriptions(checked) {
      if (checked) {
        const newIds = this.filteredSubscriptions.map(s => s.id);
        this.selectedSubscriptionIds = [...new Set([...this.selectedSubscriptionIds, ...newIds])];
      } else {
        const pageIds = new Set(this.filteredSubscriptions.map(s => s.id));
        this.selectedSubscriptionIds = this.selectedSubscriptionIds.filter(id => !pageIds.has(id));
      }
    },
    async onBatchEnableSubscriptions() {
      if (!this.selectedSubscriptionIds.length) return;
      await this.runWithButtonState('batchEnable', async () => {
        try {
          const ids = [...this.selectedSubscriptionIds];
          for (const id of ids) {
            await fetch(`/api/subscriptions/${id}/toggle`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: true }) });
          }
          this.selectedSubscriptionIds = [];
          this.setMessage(`已启用 ${ids.length} 个订阅`);
          await this.onLoadSubscriptions();
        } catch (e) {
          this.setMessage('批量启用失败: ' + e.message);
        }
      });
    },
    async onBatchDisableSubscriptions() {
      if (!this.selectedSubscriptionIds.length) return;
      await this.runWithButtonState('batchDisable', async () => {
        try {
          const ids = [...this.selectedSubscriptionIds];
          for (const id of ids) {
            await fetch(`/api/subscriptions/${id}/toggle`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: false }) });
          }
          this.selectedSubscriptionIds = [];
          this.setMessage(`已停用 ${ids.length} 个订阅`);
          await this.onLoadSubscriptions();
        } catch (e) {
          this.setMessage('批量停用失败: ' + e.message);
        }
      });
    },
    async onBatchDeleteSubscriptions() {
      if (!this.selectedSubscriptionIds.length) return;
      const count = this.selectedSubscriptionIds.length;
      if (!confirm(`确定要删除选中的 ${count} 个订阅吗？此操作不可恢复。`)) return;

      await this.runWithButtonState('batchDelete', async () => {
        try {
          const ids = [...this.selectedSubscriptionIds];
          for (const id of ids) {
            await fetch(`/api/subscriptions/${id}`, { method: 'DELETE' });
          }
          this.selectedSubscriptionIds = [];
          this.setMessage(`已删除 ${ids.length} 个订阅`);
          await this.onLoadSubscriptions();
        } catch (e) {
          this.setMessage('批量删除失败: ' + e.message);
        }
      });
    },
    async onTestSubscriptionUrl() {
      if (!this.subscriptionForm.url) return;
      this.subscriptionTestResult = null;
      await this.runWithButtonState('testSubUrl', async () => {
        try {
          const resp = await fetch('/api/collector/import-sources', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sources: [this.subscriptionForm.url], dry_run: true }),
          });
          if (resp.ok) {
            const data = await resp.json();
            this.subscriptionTestResult = {
              success: true,
              proxyCount: data.imported || data.total || 0,
            };
          } else {
            const err = await resp.json().catch(() => ({}));
            this.subscriptionTestResult = {
              success: false,
              error: err.detail || `HTTP ${resp.status}: 无法访问该 URL`,
            };
          }
        } catch (e) {
          this.subscriptionTestResult = {
            success: false,
            error: '网络错误: ' + e.message,
          };
        }
      });
    },
    freshnessStyle(ts) {
      if (!ts) return { color: 'var(--muted)' };
      const age = Date.now() - new Date(ts).getTime();
      const hour = 3600000;
      if (age < hour) return { color: 'var(--success-text)', fontWeight: 600 };
      if (age < 24 * hour) return { color: 'var(--ink)' };
      return { color: 'var(--danger-text)' };
    },
    freshnessText(ts) {
      if (!ts) return '从未刷新';
      const age = Date.now() - new Date(ts).getTime();
      const min = 60000, hour = 3600000, day = 86400000;
      if (age < min) return '刚刚';
      if (age < hour) return Math.floor(age / min) + ' 分钟前';
      if (age < day) return Math.floor(age / hour) + ' 小时前';
      return Math.floor(age / day) + ' 天前';
    },
    // Format auto-detection
    detectSubscriptionFormat(item) {
      const url = String(item?.url || '').toLowerCase();
      // URL pattern detection
      if (url.includes('/clash') || url.endsWith('.yaml') || url.endsWith('.yml')) return 'Clash';
      if (url.includes('sub?') || url.includes('subscribe') || url.includes('/v2ray') || url.includes('sub=') || url.includes('token=')) return 'V2Ray';
      if (url.includes('/ss') || url.includes('shadowsocks') || url.includes('/ssr')) return 'SS';
      // Fallback: check last_parsed count — if > 0, it was successfully parsed (unknown format)
      if ((item?.last_parsed || 0) > 0) return '未知';
      return '自动';
    },
    getFormatBadgeClass(format) {
      const map = { Clash: 'badge-clash', V2Ray: 'badge-v2ray', SS: 'badge-ss', '未知': 'badge-neutral', '自动': 'badge-neutral' };
      return map[format] || 'badge-neutral';
    },
    // Node count trend
    getNodeCountTrend(item) {
      const key = String(item?.id || '');
      const current = item?.last_parsed || 0;
      if (current === 0) return null;
      const prev = this.nodeCountHistory[key];
      if (prev === undefined || prev === null) return null;
      if (current > prev) return 'increasing';
      if (current < prev) return 'decreasing';
      return 'stable';
    },
    getTrendLabel(trend) {
      const map = { increasing: '节点增加', decreasing: '节点减少', stable: '节点稳定' };
      return map[trend] || '';
    },
    getNodeCountTrendLabel(item) {
      const key = String(item?.id || '');
      const current = item?.last_parsed || 0;
      const prev = this.nodeCountHistory[key];
      if (prev === undefined || prev === null || current === 0) return '';
      const diff = current - prev;
      if (diff > 0) return `↑ +${diff}`;
      if (diff < 0) return `↓ ${diff}`;
      return '→ 稳定';
    },

    // --- Intelligence Methods ---
    getSubscriptionFreshness(sub) {
      if (!sub.last_fetched_at) return 0;
      const age = Date.now() - new Date(sub.last_fetched_at).getTime();
      const day = 86400000;
      if (age < day) return 100;
      if (age < 7 * day) return 70;
      if (age < 30 * day) return 40;
      return 10;
    },

    applyMergeRecommendation(rec) {
      this.setMessage(`已应用合并建议: ${rec.reason}`);
      // In a real implementation, this would perform the merge action
    },

    dismissMergeRecommendation(rec) {
      this.dismissedRecommendations.push(rec.id);
      try {
        localStorage.setItem('proxypool-sub-dismissed-recs', JSON.stringify(this.dismissedRecommendations));
      } catch {}
    },

    applyOptimization(suggestion) {
      if (suggestion.action === 'enable_auto_refresh') {
        for (const subId of suggestion.subscriptions) {
          this.setSubFrequency(subId, 'daily');
        }
        this.setMessage(`已为 ${suggestion.subscriptions.length} 个订阅启用每日自动刷新`);
      } else if (suggestion.action === 'delete_failed') {
        this.selectedSubscriptionIds = suggestion.subscriptions;
        this.onBatchDeleteSubscriptions();
      } else {
        this.setMessage(suggestion.description);
      }
    },

    updateNodeCountHistory() {
      const history = { ...this.nodeCountHistory };
      for (const sub of (this.subscriptions || [])) {
        const key = String(sub.id || '');
        const current = sub.last_parsed || 0;
        if (current > 0) history[key] = current;
      }
      this.nodeCountHistory = history;
      try {
        localStorage.setItem('proxypool-sub-node-counts', JSON.stringify(history));
      } catch {}
    },
    // Subscription content preview
    async showPreview(item) {
      this.previewSubscriptionName = item.name || `#${item.id}`;
      this.previewProxies = [];
      this.previewLoading = true;
      this.previewDialogVisible = true;
      try {
        const sourcePrefix = `subscription#${item.id}:`;
        const params = new URLSearchParams({ limit: '20', source: sourcePrefix, sort_by: 'latency', sort_order: 'asc' });
        const resp = await fetch(`/api/proxies?${params.toString()}`);
        const data = await resp.json();
        this.previewProxies = (data.items || []).map(p => ({
          protocol: p.protocol,
          name: p.name || '-',
          host: p.host,
          port: p.port,
          available: p.available,
          latency_ms: p.latency_ms,
        }));
      } catch {
        this.previewProxies = [];
      } finally {
        this.previewLoading = false;
      }
    },
    // --- Groups ---
    persistSubMeta() {
      try { localStorage.setItem('proxypool-sub-meta', JSON.stringify(this.subMeta)); } catch {}
    },
    persistSubGroups() {
      try { localStorage.setItem('proxypool-sub-groups', JSON.stringify(this.subGroups)); } catch {}
    },
    getSubGroup(subId) {
      return this.subMeta[String(subId)]?.group || '';
    },
    setSubGroup(subId, groupId) {
      const key = String(subId);
      if (!this.subMeta[key]) this.subMeta[key] = {};
      this.subMeta[key].group = groupId;
      this.persistSubMeta();
    },
    getSubFrequency(subId) {
      return this.subMeta[String(subId)]?.frequency || 'manual';
    },
    setSubFrequency(subId, freq) {
      const key = String(subId);
      if (!this.subMeta[key]) this.subMeta[key] = {};
      this.subMeta[key].frequency = freq;
      this.persistSubMeta();
    },
    openGroupDialog(mode, groupId) {
      this.groupFormMode = mode;
      if (mode === 'edit' && groupId) {
        const group = this.subGroups.find(g => g.id === groupId);
        this.groupFormName = group ? group.name : '';
        this.editingGroupId = groupId;
      } else {
        this.groupFormName = '';
        this.editingGroupId = null;
      }
      this.groupDialogVisible = true;
    },
    submitGroupForm() {
      const name = this.groupFormName.trim();
      if (!name) return;
      if (this.groupFormMode === 'edit' && this.editingGroupId) {
        const idx = this.subGroups.findIndex(g => g.id === this.editingGroupId);
        if (idx >= 0) this.subGroups[idx].name = name;
      } else {
        this.subGroups.push({ id: 'g' + Date.now(), name });
      }
      this.persistSubGroups();
      this.groupDialogVisible = false;
      this.groupFormName = '';
    },
    deleteGroup(groupId) {
      if (!confirm('确定删除此分组？分组内的订阅不会被删除，仅移除分组标记。')) return;
      this.subGroups = this.subGroups.filter(g => g.id !== groupId);
      for (const key of Object.keys(this.subMeta)) {
        if (this.subMeta[key]?.group === groupId) this.subMeta[key].group = '';
      }
      this.persistSubGroups();
      this.persistSubMeta();
      if (this.selectedGroupId === groupId) this.selectedGroupId = null;
    },
    batchAssignGroup() {
      this.batchGroupTarget = '';
      this.batchGroupCount = this.selectedSubscriptionIds.length;
      this.batchGroupDialogVisible = true;
    },
    confirmBatchAssignGroup() {
      for (const id of this.selectedSubscriptionIds) {
        if (this.batchGroupTarget === '__remove__') {
          this.setSubGroup(id, '');
        } else {
          this.setSubGroup(id, this.batchGroupTarget);
        }
      }
      this.batchGroupDialogVisible = false;
      this.selectedSubscriptionIds = [];
    },
    // --- Priority ---
    moveSubPriority(subId, delta) {
      const ids = this.subscriptions.map(s => s.id);
      const fromIdx = ids.indexOf(subId);
      if (fromIdx < 0) return;
      const toIdx = fromIdx + delta;
      if (toIdx < 0 || toIdx >= ids.length) return;
      [ids[fromIdx], ids[toIdx]] = [ids[toIdx], ids[fromIdx]];
      // Reorder subscriptions array
      const map = new Map(this.subscriptions.map(s => [s.id, s]));
      this.subscriptions = ids.map(id => map.get(id)).filter(Boolean);
    },
    // --- Schedule display ---
    getNextRefreshText(item) {
      const freq = this.getSubFrequency(item.id);
      if (freq === 'manual') return '手动';
      const lastFetched = item.last_fetched_at ? new Date(item.last_fetched_at).getTime() : 0;
      if (!lastFetched) return '待刷新';
      const intervals = { hourly: 3600000, '6h': 21600000, '12h': 43200000, daily: 86400000 };
      const interval = intervals[freq] || 0;
      if (!interval) return '手动';
      const nextAt = lastFetched + interval;
      const now = Date.now();
      if (now >= nextAt) return '即将刷新';
      const remaining = nextAt - now;
      const hours = Math.floor(remaining / 3600000);
      const mins = Math.floor((remaining % 3600000) / 60000);
      if (hours > 0) return `${hours}h${mins > 0 ? mins + 'm' : ''}后`;
      return `${mins}m后`;
    },
    getSubscriptionReliability(sub) {
      const history = this.refreshHistory[sub.id] || [];
      if (history.length === 0) return 50;
      const successCount = history.filter(h => h.success).length;
      return Math.round((successCount / history.length) * 100);
    },
    getSubscriptionNodeCount(sub) {
      return sub.last_parsed || 0;
    },
    getSubscriptionScore(sub) {
      const nodeCount = this.getSubscriptionNodeCount(sub);
      const reliability = this.getSubscriptionReliability(sub);
      return Math.round((nodeCount * 0.6) + (reliability * 0.4));
    },
    get bestSubscriptions() {
      return this.subscriptions
        .filter(s => s.enabled)
        .map(s => ({
          ...s,
          nodeCount: this.getSubscriptionNodeCount(s),
          reliability: this.getSubscriptionReliability(s),
          score: this.getSubscriptionScore(s),
        }))
        .sort((a, b) => b.score - a.score)
        .slice(0, 5);
    },
    get refreshTrendData() {
      const allHistory = [];
      for (const sub of this.subscriptions) {
        const history = this.refreshHistory[sub.id] || [];
        allHistory.push(...history);
      }
      if (allHistory.length === 0) return null;
      const sorted = allHistory.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      const recent = sorted.slice(0, 10);
      const successCount = recent.filter(h => h.success).length;
      const failCount = recent.length - successCount;
      return {
        results: recent.map(h => h.success),
        successCount,
        failCount,
        successRate: Math.round((successCount / recent.length) * 100),
      };
    },
    get geoCoverageData() {
      const geoCounts = {};
      for (const sub of this.subscriptions) {
        const proxies = this.subscriptionProxies[sub.id] || [];
        for (const proxy of proxies) {
          const country = proxy.geo_country || '未知';
          geoCounts[country] = (geoCounts[country] || 0) + 1;
        }
      }
      const total = Object.values(geoCounts).reduce((a, b) => a + b, 0);
      if (total === 0) return [];
      return Object.entries(geoCounts)
        .map(([country, count]) => ({
          country,
          count,
          percentage: Math.round((count / total) * 100),
        }))
        .sort((a, b) => b.count - a.count);
    },
  },
  watch: {
    subscriptions: {
      handler() { this.updateNodeCountHistory(); },
      immediate: false,
    },
  },
};
</script>

<style scoped>
.skeleton {
  background: linear-gradient(90deg, var(--bg-secondary) 25%, var(--line-soft) 50%, var(--bg-secondary) 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 4px;
}

@keyframes skeleton-loading {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.skeleton-text {
  height: 14px;
}

.skeleton-checkbox {
  width: 16px;
  height: 16px;
  border-radius: 3px;
}

.skeleton-button {
  width: 50px;
  height: 24px;
  border-radius: 4px;
}

.skeleton-badge {
  width: 40px;
  height: 20px;
  border-radius: 10px;
}

/* Format badges */
.badge-clash {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.badge-v2ray {
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
  border: 1px solid rgba(139, 92, 246, 0.2);
}

.badge-ss {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.2);
}

/* Format help dialog */
.format-help-content {
  padding: 4px 0;
}

.format-help-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.format-help-card {
  background: var(--bg-secondary);
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: hidden;
}

.format-help-card-header {
  padding: 8px 12px 4px;
}

.format-help-card-body {
  padding: 4px 12px 10px;
}

@media (max-width: 640px) {
  .format-help-grid {
    grid-template-columns: 1fr;
  }
}

/* Preview dialog */
.preview-content .data-table {
  font-size: 12px;
}

/* Priority buttons */
.priority-btn {
  font-size: 8px;
  line-height: 1;
  padding: 0 2px;
  min-height: 12px;
}

/* Group tabs */
.sub-group-tabs .btn {
  white-space: nowrap;
}

/* Subscription Analytics */
.subscription-analytics {
  border-top: 1px solid var(--line);
  padding-top: 20px;
}

.analytics-card {
  background: var(--bg-secondary);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}

.analytics-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
}

.analytics-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.analytics-card-body {
  padding: 12px 14px;
}

/* Best Subscriptions */
.best-subs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.best-sub-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.best-sub-rank {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  min-width: 28px;
}

.best-sub-rank.rank-gold {
  color: #f59e0b;
}

.best-sub-rank.rank-silver {
  color: #9ca3af;
}

.best-sub-rank.rank-bronze {
  color: #d97706;
}

.best-sub-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.best-sub-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--ink);
}

.best-sub-meta {
  font-size: 11px;
}

.best-sub-bar {
  width: 60px;
  height: 6px;
  background: var(--line);
  border-radius: 3px;
  overflow: hidden;
}

.best-sub-bar-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
}

/* Refresh Trend */
.refresh-trend {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.refresh-trend-stats {
  display: flex;
  gap: 16px;
}

.refresh-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.refresh-stat-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
}

.refresh-stat-label {
  font-size: 10px;
  color: var(--muted);
}

.refresh-trend-dots {
  display: flex;
  gap: 4px;
}

.refresh-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.refresh-dot-success {
  background-color: #16a34a;
}

.refresh-dot-fail {
  background-color: #dc2626;
}

/* Geographic Coverage */
.geo-coverage {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.geo-coverage-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.geo-coverage-country {
  font-size: 12px;
  color: var(--ink);
  min-width: 60px;
}

.geo-coverage-bar-container {
  flex: 1;
  height: 8px;
  background: var(--line);
  border-radius: 4px;
  overflow: hidden;
}

.geo-coverage-bar {
  height: 100%;
  background: var(--accent);
  border-radius: 4px;
}

.geo-coverage-count {
  min-width: 30px;
  text-align: right;
  color: var(--muted);
}
</style>
