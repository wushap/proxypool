<template>
            <section v-show="activePage === 'published-subscriptions'" class="card fade-in">
              <div class="card-body">
                <div class="section-header">
                  <h2 class="section-title">订阅发布管理</h2>
                  <button @click="onLoadPublishedSubscriptions" :disabled="isActionRunning('loadPublishedSubscriptions')" class="btn btn-secondary">
                    {{ buttonLabel('loadPublishedSubscriptions', '刷新', '刷新中...') }}
                  </button>
                </div>

                <!-- Create form -->
                <div class="settings-grid" style="margin-bottom: 12px;">
                  <div class="card" style="border: 1px dashed var(--line);">
                    <div class="card-body">
                      <h3 class="settings-title">创建发布订阅</h3>
                      <div class="settings-row">
                        <div class="form-group" style="flex: 2;">
                          <label class="form-label">名称</label>
                          <input v-model.trim="publishedSubscriptionForm.name" type="text" placeholder="发布订阅名称" class="input" />
                        </div>
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">发布格式</label>
                          <select v-model="publishedSubscriptionForm.format" class="select">
                            <option value="raw">原始链接</option>
                            <option value="clash">Clash YAML</option>
                          </select>
                        </div>
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">直连</label>
                          <select v-model="publishedSubscriptionForm.filters.available" class="select">
                            <option value="true">仅可直连</option>
                            <option value="false">仅不可直连</option>
                            <option value="">不限</option>
                          </select>
                        </div>
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">ChatGPT</label>
                          <select v-model="publishedSubscriptionForm.filters.openai_filter" class="select">
                            <option value="">不限</option>
                            <option value="unlocked">已解锁</option>
                            <option value="blocked">未解锁</option>
                            <option value="unchecked">未检测</option>
                          </select>
                        </div>
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">家宽</label>
                          <select v-model="publishedSubscriptionForm.filters.ip_purity_filter" class="select">
                            <option value="">不限</option>
                            <option value="residential">家宽</option>
                            <option value="non_residential">非家宽</option>
                            <option value="unknown">未知</option>
                          </select>
                        </div>
                        <button @click="onCreatePublishedSubscription" :disabled="isActionRunning('createPublishedSubscription')" class="btn btn-primary self-end">
                          {{ buttonLabel('createPublishedSubscription', '创建', '创建中...') }}
                        </button>
                      </div>
                      <div class="settings-row" style="margin-top: 8px;">
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">国家</label>
                          <select v-model="publishedSubscriptionForm.filters.geo_country" class="select">
                            <option value="">不限</option>
                            <option v-for="opt in geoCountryOptions" :key="'pub-c-' + opt.value" :value="opt.value">{{ opt.label }}</option>
                          </select>
                        </div>
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">城市</label>
                          <select v-model="publishedSubscriptionForm.filters.geo_location" class="select">
                            <option value="">不限</option>
                            <option v-for="opt in geoLocationFilterOptions" :key="'pub-l-' + opt.value" :value="opt.value">{{ opt.label }}</option>
                          </select>
                        </div>
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">链路</label>
                          <select v-model="publishedSubscriptionForm.filters.fallback_front_filter" class="select">
                            <option value="">不限</option>
                            <option value="none">无前置</option>
                            <option value="has">有前置</option>
                          </select>
                        </div>
                        <div class="form-group" style="flex: 2;">
                          <label class="form-label">来源</label>
                          <input v-model.trim="publishedSubscriptionForm.filters.source" type="text" placeholder="关键词" class="input" />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Pagination -->
                <div class="pagination">
                  <div class="pagination-info">
                    <span class="text-muted">每页</span>
                    <select v-model.number="pagination.publishedSubscriptions.perPage" @change="onPaginationPageSizeChange('publishedSubscriptions')" class="select input-sm" style="width: 56px;">
                      <option v-for="n in pageSizeOptions" :key="'pub-' + n" :value="n">{{ n }}</option>
                    </select>
                    <span class="text-muted">{{ pageIndicator('publishedSubscriptions') }}</span>
                  </div>
                  <div class="pagination-nav">
                    <button @click="goPrevPage('publishedSubscriptions')" :disabled="!canPrevPage('publishedSubscriptions')" class="btn btn-xs btn-ghost">上一页</button>
                    <button @click="goNextPage('publishedSubscriptions')" :disabled="!canNextPage('publishedSubscriptions')" class="btn btn-xs btn-ghost">下一页</button>
                  </div>
                </div>

                <div class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 50px;">ID</th>
                        <th style="width: 140px;">名称</th>
                        <th style="width: 90px;">格式</th>
                        <th>筛选条件</th>
                        <th style="width: 60px;">节点</th>
                        <th style="width: 70px;">启用</th>
                        <th style="width: 200px;">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in paginatedPublishedSubscriptions" :key="item.id">
                        <td class="mono text-muted">{{ item.id }}</td>
                        <td><input :value="item.name || ''" @change="onRenamePublishedSubscription(item, $event.target.value)" type="text" class="inline-input" /></td>
                        <td><span class="badge" :class="item.format === 'clash' ? 'badge-success' : 'badge-neutral'">{{ formatPublishedSubscriptionOutput(item.format) }}</span></td>
                        <td class="text-xs text-muted">{{ formatPublishedSubscriptionFilters(item.filters) }}</td>
                        <td class="mono">{{ item.match_count || 0 }}</td>
                        <td>
                          <button @click="onTogglePublishedSubscription(item)" :disabled="isActionRunning('togglePubSub-' + item.id)" class="btn btn-xs" :class="item.enabled ? 'btn-success' : 'btn-ghost'">
                            {{ item.enabled ? '启用' : '停用' }}
                          </button>
                        </td>
                        <td>
                          <div class="btn-group">
                            <button @click="onPreviewPublishedSubscription(item)" class="btn btn-xs btn-ghost">预览</button>
                            <button @click="applyPublishedSubscriptionFiltersToForm(item)" class="btn btn-xs btn-ghost">套用</button>
                            <button @click="onUpdatePublishedSubscriptionFilters(item)" :disabled="isActionRunning('updatePubSub-' + item.id)" class="btn btn-xs btn-secondary">保存</button>
                            <button @click="onCopyPublishedSubscriptionUrl(item)" :disabled="isActionRunning('copyPubSub-' + item.id)" class="btn btn-xs btn-ghost">复制</button>
                            <a :href="publishedSubscriptionExportUrl(item)" target="_blank" class="btn btn-xs btn-ghost">打开</a>
                            <button @click="onDeletePublishedSubscription(item.id)" :disabled="isActionRunning('deletePubSub-' + item.id)" class="btn btn-xs btn-danger">删除</button>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- Preview Dialog -->
                <el-dialog v-model="previewDialogVisible" title="订阅预览" width="min(800px, 95vw)" append-to-body>
                  <div v-if="previewLoading" class="empty-state">加载中...</div>
                  <div v-else-if="previewError" class="empty-state" style="color: var(--danger-text);">{{ previewError }}</div>
                  <div v-else>
                    <div style="margin-bottom: 8px;">
                      <span class="badge badge-neutral">{{ previewItem?.name }}</span>
                      <span class="badge" :class="previewItem?.format === 'clash' ? 'badge-success' : 'badge-neutral'" style="margin-left: 4px;">{{ previewItem?.format }}</span>
                      <span class="text-muted" style="font-size: 12px; margin-left: 8px;">{{ previewLineCount }} 行</span>
                    </div>
                    <textarea :value="previewContent" readonly class="textarea input-mono" style="min-height: 300px; max-height: 60vh; font-size: 12px;"></textarea>
                  </div>
                  <template #footer>
                    <button class="btn btn-secondary" @click="copyPreviewContent">复制内容</button>
                    <button class="btn btn-ghost" @click="previewDialogVisible = false">关闭</button>
                  </template>
                </el-dialog>
              </div>
            </section>
</template>

<script>
import { rootProxyMixin } from "../rootProxyMixin";

export default {
  name: "PublishedSubscriptionsPage",
  mixins: [rootProxyMixin],
  data() {
    return {
      previewDialogVisible: false,
      previewLoading: false,
      previewError: '',
      previewContent: '',
      previewItem: null,
    };
  },
  computed: {
    previewLineCount() {
      return this.previewContent ? this.previewContent.split('\n').filter(Boolean).length : 0;
    },
  },
  methods: {
    async onPreviewPublishedSubscription(item) {
      this.previewItem = item;
      this.previewContent = '';
      this.previewError = '';
      this.previewLoading = true;
      this.previewDialogVisible = true;
      try {
        const url = this.publishedSubscriptionExportUrl(item);
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        this.previewContent = await resp.text();
        if (!this.previewContent.trim()) {
          this.previewError = '订阅内容为空（可能没有匹配的节点）';
        }
      } catch (err) {
        this.previewError = '加载失败: ' + err;
      } finally {
        this.previewLoading = false;
      }
    },
    async copyPreviewContent() {
      if (!this.previewContent) return;
      try {
        await navigator.clipboard.writeText(this.previewContent);
        if (this.appState && this.appState.setMessage) {
          this.appState.setMessage('预览内容已复制到剪贴板');
        }
      } catch {
        this.appState.setMessage('复制失败', true);
      }
    },
  },
};
</script>
