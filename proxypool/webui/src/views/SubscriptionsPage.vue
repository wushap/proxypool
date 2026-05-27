<template>
            <section v-show="activePage === 'subscriptions'" class="card fade-in">
              <div class="card-body">
                <!-- Breadcrumb -->
                <Breadcrumb :items="breadcrumbItems" />

                <!-- Loading State -->
                <LoadingState v-if="isLoading" text="加载订阅数据中..." size="small" />
                <div class="section-header">
                  <h2 class="section-title">订阅管理</h2>
                  <div class="btn-group">
                    <button @click="onRefreshAllSubscriptions" :disabled="isActionRunning('refreshAllSubscriptions')" class="btn btn-secondary">
                      {{ buttonLabel('refreshAllSubscriptions', '刷新全部', '刷新中...') }}
                    </button>
                    <button @click="onDeleteUnavailableSubscriptions" :disabled="isActionRunning('deleteUnavailableSubscriptions')" class="btn btn-danger">
                      {{ buttonLabel('deleteUnavailableSubscriptions', '删除不可用', '删除中...') }}
                    </button>
                    <button @click="onLoadSubscriptions" :disabled="isActionRunning('loadSubscriptions')" class="btn btn-secondary">
                      {{ buttonLabel('loadSubscriptions', '刷新列表', '刷新中...') }}
                    </button>
                  </div>
                </div>

                <!-- Subscription stats -->
                <div class="status-bar" style="margin-bottom: 12px;">
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

                <!-- Add subscription form -->
                <div class="form-row-3" style="gap: 8px; margin-bottom: 12px;">
                  <input v-model.trim="subscriptionForm.name" type="text" placeholder="订阅名称" class="input" />
                  <input v-model.trim="subscriptionForm.url" type="text" placeholder="订阅链接 URL" class="input" />
                  <button @click="onCreateSubscription" :disabled="isActionRunning('createSubscription')" class="btn btn-primary">
                    {{ buttonLabel('createSubscription', '添加订阅', '添加中...') }}
                  </button>
                </div>

                <!-- Bulk import -->
                <details class="details" style="margin-bottom: 12px;">
                  <summary>批量导入订阅（每行一个 URL）</summary>
                  <textarea v-model.trim="bulkImportUrls" class="textarea input-mono" placeholder="https://example.com/sub1&#10;https://example.com/sub2&#10;..." style="margin-top: 8px; min-height: 80px;"></textarea>
                  <button @click="onBulkImportSubscriptions" :disabled="isActionRunning('bulkImportSubs')" class="btn btn-primary" style="margin-top: 6px;">
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

                <!-- Pagination -->
                <div class="pagination">
                  <div class="pagination-info">
                    <span class="text-muted">每页</span>
                    <select v-model.number="pagination.subscriptions.perPage" @change="onPaginationPageSizeChange('subscriptions')" class="select input-sm" style="width: 56px;">
                      <option v-for="n in pageSizeOptions" :key="'sub-' + n" :value="n">{{ n }}</option>
                    </select>
                    <span class="text-muted">{{ pageIndicator('subscriptions') }}</span>
                  </div>
                  <div class="pagination-nav">
                    <button @click="goPrevPage('subscriptions')" :disabled="!canPrevPage('subscriptions')" class="btn btn-xs btn-ghost">上一页</button>
                    <button @click="goNextPage('subscriptions')" :disabled="!canNextPage('subscriptions')" class="btn btn-xs btn-ghost">下一页</button>
                  </div>
                </div>

                <!-- Empty State -->
                <EmptyState v-if="!subscriptions.length" title="暂无订阅" description="点击上方添加订阅按钮创建第一个订阅源" size="normal" />

                <!-- Table -->
                <div v-else class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 50px;">ID</th>
                        <th style="width: 140px;">名称</th>
                        <th>链接</th>
                        <th style="width: 70px;">启用</th>
                        <th style="width: 80px;">状态</th>
                        <th style="width: 220px;" title="解析/新增/更新/无效/去重">统计</th>
                        <th style="width: 140px;">上次刷新</th>
                        <th style="width: 100px;">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in paginatedSubscriptions" :key="item.id">
                        <td class="mono text-muted">{{ item.id }}</td>
                        <td><input :value="item.name || ''" @change="onRenameSubscription(item, $event.target.value)" type="text" class="inline-input" /></td>
                        <td class="mono text-muted text-xs truncate" style="max-width: 280px;">{{ shortSubscriptionUrl(item.url) }}</td>
                        <td>
                          <button @click="onToggleSubscription(item)" :disabled="isActionRunning('toggleSub-' + item.id)" class="btn btn-xs" :class="item.enabled ? 'btn-success' : 'btn-ghost'">
                            {{ item.enabled ? '启用' : '停用' }}
                          </button>
                        </td>
                        <td><span class="badge" :class="item.last_status === 'success' ? 'badge-success' : item.last_status === 'failed' ? 'badge-danger' : 'badge-neutral'">{{ item.last_status || '-' }}</span></td>
                        <td>
                          <div class="subscription-stats" :title="'解析 ' + (item.last_parsed || 0) + ' / 新增 ' + (item.last_inserted || 0) + ' / 更新 ' + (item.last_updated || 0) + ' / 无效 ' + (item.last_invalid || 0) + ' / 去重 ' + (item.last_deduped || 0)">
                            <span class="stat-pill">解析 {{ item.last_parsed || 0 }}</span>
                            <span class="stat-pill stat-pill-success">新增 {{ item.last_inserted || 0 }}</span>
                            <span class="stat-pill">更新 {{ item.last_updated || 0 }}</span>
                            <span class="stat-pill" :class="(item.last_invalid || 0) > 0 ? 'stat-pill-danger' : ''">无效 {{ item.last_invalid || 0 }}</span>
                            <span class="stat-pill">去重 {{ item.last_deduped || 0 }}</span>
                          </div>
                        </td>
                        <td class="text-xs" :style="freshnessStyle(item.last_fetched_at)" :title="formatTime(item.last_fetched_at)">{{ freshnessText(item.last_fetched_at) }}</td>
                        <td>
                          <div class="btn-group">
                            <button @click="onRefreshSubscription(item.id)" :disabled="isActionRunning('refreshSub-' + item.id)" class="btn btn-xs btn-secondary">刷新</button>
                            <button @click="onDeleteSubscription(item.id)" :disabled="isActionRunning('deleteSub-' + item.id)" class="btn btn-xs btn-danger">删除</button>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
</template>

<script>
import { rootProxyMixin } from "../rootProxyMixin";
import Breadcrumb from '../components/layout/Breadcrumb.vue';
import EmptyState from '../components/common/EmptyState.vue';
import LoadingState from '../components/common/LoadingState.vue';

export default {
  name: "SubscriptionsPage",
  components: {
    Breadcrumb,
    EmptyState,
    LoadingState,
  },
  mixins: [rootProxyMixin],
  data() {
    return {
      isLoading: false,
    };
  },
  computed: {
    breadcrumbItems() {
      return [
        { label: '首页', path: '/', onClick: () => this.selectPage('dashboard') },
        { label: '订阅管理' },
      ];
    },
  },
  methods: {
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
  },
};
</script>
