<template>
            <section v-show="activePage === 'proxies'" class="card fade-in">
              <div class="card-body">
                <!-- Breadcrumb -->
                <Breadcrumb :items="breadcrumbItems" />
                <div class="section-header">
                  <h2 class="section-title">代理节点</h2>
                  <div class="btn-group">
                    <button @click="clearProxyFilters" class="btn btn-sm btn-ghost">清空筛选</button>
                    <button @click="resetProxyColumns" class="btn btn-sm btn-ghost">重置列</button>
                    <el-button size="small" plain @click="proxyConfigDialogVisible = true">配置列</el-button>
                  </div>
                </div>

                <!-- Status bar -->
                <div class="status-bar" style="margin-bottom: 8px;">
                  <div class="status-item">
                    <span class="text-muted">显示</span>
                    <strong>{{ proxies.length }}</strong>
                  </div>
                  <div class="status-item">
                    <span class="text-muted">总节点</span>
                    <strong>{{ allProxyCount }}</strong>
                  </div>
                  <div v-if="proxySortKey" class="status-item">
                    <span class="text-muted">排序</span>
                    <span class="badge badge-sm badge-neutral">{{ sortLabel(proxySortKey) }} {{ proxySortDir === 'asc' ? '↑' : '↓' }}</span>
                  </div>
                  <div v-if="selectedProxyKeys.length" class="status-item">
                    <span class="text-muted">选中</span>
                    <strong style="color: var(--accent);">{{ selectedProxyKeys.length }}</strong>
                  </div>
                </div>

                <!-- Pagination & actions -->
                <div class="pagination">
                  <div class="pagination-info">
                    <span class="text-muted">每页</span>
                    <select v-model.number="pagination.proxies.perPage" @change="onPaginationPageSizeChange('proxies')" class="select input-sm" style="width: 56px;">
                      <option v-for="n in pageSizeOptions" :key="'px-' + n" :value="n">{{ n }}</option>
                    </select>
                    <span class="text-muted">{{ pageIndicator('proxies') }}</span>
                  </div>
                  <div class="pagination-nav">
                    <button @click="onCopySelectedProxyLinks" :disabled="!selectedProxyKeys.length || isActionRunning('copySelectedProxyLinks')" class="btn btn-xs btn-secondary">
                      {{ buttonLabel('copySelectedProxyLinks', '复制选中(' + selectedProxyKeys.length + ')', '...') }}
                    </button>
                    <button @click="onDeleteSelectedProxies" :disabled="!selectedProxyKeys.length || isActionRunning('deleteSelectedProxies')" class="btn btn-xs btn-danger">
                      {{ buttonLabel('deleteSelectedProxies', '删除选中(' + selectedProxyKeys.length + ')', '...') }}
                    </button>
                    <button @click="onLoadDataClick" :disabled="isActionRunning('loadData')" class="btn btn-xs btn-secondary">
                      {{ buttonLabel('loadData', '刷新', '...') }}
                    </button>
                    <button @click="goPrevPage('proxies')" :disabled="!canPrevPage('proxies')" class="btn btn-xs btn-ghost">上一页</button>
                    <button @click="goNextPage('proxies')" :disabled="!canNextPage('proxies')" class="btn btn-xs btn-ghost">下一页</button>
                  </div>
                </div>

                <!-- Config dialog -->
                <el-dialog v-model="proxyConfigDialogVisible" title="表格配置（筛选 + 列管理）" width="min(1100px, 95vw)" append-to-body>
                  <div class="flex flex-wrap items-center justify-between gap-2" style="margin-bottom: 8px;">
                    <p class="text-xs font-semibold text-gray-700">筛选条件、列顺序、列显示与列名统一配置</p>
                    <div class="flex gap-2">
                      <el-button size="small" @click="clearProxyFilters">清空筛选</el-button>
                      <el-button size="small" @click="resetProxyColumns">重置列</el-button>
                    </div>
                  </div>
                  <el-table :data="proxyColumnConfigRows" size="small" border stripe max-height="56vh">
                    <el-table-column label="顺序" width="120">
                      <template #default="{ row }">
                        <div class="flex gap-1">
                          <el-button size="small" text :disabled="row.idx === 0" @click="moveProxyColumn(row.key, -1)">↑</el-button>
                          <el-button size="small" text :disabled="row.idx >= proxyColumnConfigRows.length - 1" @click="moveProxyColumn(row.key, 1)">↓</el-button>
                        </div>
                      </template>
                    </el-table-column>
                    <el-table-column prop="key" label="字段" width="100" />
                    <el-table-column label="显示" width="80">
                      <template #default="{ row }">
                        <el-switch v-model="proxyColumnConfigs[row.key].visible" @change="persistProxyColumns" />
                      </template>
                    </el-table-column>
                    <el-table-column label="列名" width="180">
                      <template #default="{ row }">
                        <el-input v-model="proxyColumnConfigs[row.key].label" size="small" @change="persistProxyColumns" />
                      </template>
                    </el-table-column>
                    <el-table-column label="筛选">
                      <template #default="{ row }">
                        <template v-if="row.key === 'protocol'">
                          <el-select v-model="proxyFilters.protocol" clearable :placeholder="`协议 (${allProxyCount})`" size="small" style="width: 180px">
                            <el-option v-for="opt in protocolFilterOptions" :key="'fp-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                          </el-select>
                        </template>
                        <template v-else-if="row.key === 'status'">
                          <el-select v-model="proxyFilters.available" clearable :placeholder="`状态 (${allProxyCount})`" size="small" style="width: 180px">
                            <el-option v-for="opt in statusFilterOptions" :key="'fs-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                          </el-select>
                        </template>
                        <template v-else-if="row.key === 'bandwidth'">
                          <el-input v-model="proxyFilters.speed_min_mbps" clearable placeholder="带宽 > Mbps" size="small" style="width: 180px" />
                        </template>
                        <template v-else-if="row.key === 'geo'">
                          <div class="flex flex-wrap gap-2">
                            <el-select v-model="proxyFilters.geo_country" clearable :placeholder="`国家 (${allProxyCount})`" size="small" style="width: 180px" @change="onGeoCountryChanged">
                              <el-option v-for="opt in geoCountryOptions" :key="'fgc-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                            </el-select>
                            <el-select v-model="proxyFilters.geo_location" clearable :placeholder="`城市 (${geoLocationFilterOptions.length})`" size="small" style="width: 220px">
                              <el-option v-for="opt in geoLocationFilterOptions" :key="'fgl-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                            </el-select>
                          </div>
                        </template>
                        <template v-else-if="row.key === 'purity'">
                          <el-select v-model="proxyFilters.ip_purity" clearable :placeholder="`纯净度 (${allProxyCount})`" size="small" style="width: 200px">
                            <el-option v-for="opt in ipPurityFilterOptions" :key="'fip-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                          </el-select>
                        </template>
                        <template v-else-if="row.key === 'unlock'">
                          <el-select v-model="proxyFilters.openai" clearable :placeholder="`ChatGPT (${allProxyCount})`" size="small" style="width: 200px">
                            <el-option v-for="opt in openaiFilterOptions" :key="'fo-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                          </el-select>
                        </template>
                        <template v-else-if="row.key === 'fallback_front'">
                          <el-select v-model="proxyFilters.fallback_front" clearable :placeholder="`前置 (${allProxyCount})`" size="small" style="width: 200px">
                            <el-option v-for="opt in fallbackFrontFilterOptions" :key="'ff-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                          </el-select>
                        </template>
                        <template v-else-if="row.key === 'source'">
                          <el-select v-model="proxyFilters.source" clearable filterable allow-create default-first-option :placeholder="`来源 (${allProxyCount})`" size="small" style="width: 280px">
                            <el-option v-for="opt in sourceFilterOptions" :key="'fsrc-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                          </el-select>
                        </template>
                        <span v-else class="text-muted">-</span>
                      </template>
                    </el-table-column>
                  </el-table>
                  <template #footer>
                    <div class="flex justify-end gap-2">
                      <el-button @click="proxyConfigDialogVisible = false">取消</el-button>
                      <el-button type="primary" :loading="isActionRunning('loadData')" @click="applyProxyConfig">应用并刷新</el-button>
                    </div>
                  </template>
                </el-dialog>

                <!-- Proxy table -->
                <div class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 36px;">
                          <input type="checkbox" :checked="areAllPaginatedProxiesSelected()" :disabled="!paginatedProxies.length" @change="toggleAllPaginatedProxies($event.target.checked)" />
                        </th>
                        <th v-for="col in visibleProxyColumns" :key="'th-' + col.key"
                          :class="{ 'sortable-th': isSortableColumn(col.key) }"
                          @click="isSortableColumn(col.key) && toggleProxySort(col.key)">
                          {{ col.label }}
                          <span v-if="isSortableColumn(col.key) && proxySortKey === col.key" class="sort-indicator">{{ proxySortDir === 'asc' ? '↑' : '↓' }}</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in paginatedProxies" :key="item.normalized_key">
                        <td><input v-model="selectedProxyKeys" type="checkbox" :value="item.normalized_key" /></td>
                        <td v-for="col in visibleProxyColumns" :key="'td-' + item.normalized_key + '-' + col.key">
                          <template v-if="col.key === 'serial'"><span class="mono text-muted">#{{ getSerial(item.normalized_key) }}</span></template>
                          <template v-else-if="col.key === 'protocol'"><span class="font-semibold">{{ item.protocol }}</span></template>
                          <template v-else-if="col.key === 'address'"><span>{{ item.host }}:{{ item.port }}</span></template>
                          <template v-else-if="col.key === 'latency'"><span :style="latencyStyle(item.latency_ms)">{{ item.latency_ms ? item.latency_ms + ' ms' : '-' }}</span></template>
                          <template v-else-if="col.key === 'bandwidth'"><span class="mono text-xs" :style="bandwidthStyle(item.speed_mbps)">{{ formatBandwidthMbps(item) }}</span></template>
                          <template v-else-if="col.key === 'status'"><span class="badge" :class="item.available ? 'badge-success' : 'badge-danger'">{{ item.available ? 'UP' : 'DOWN' }}</span></template>
                          <template v-else-if="col.key === 'checked_at'"><span class="text-xs text-muted">{{ formatTime(item.last_checked_at) }}</span></template>
                          <template v-else-if="col.key === 'geo'"><span class="text-xs text-muted">{{ formatGeo(item) }}</span></template>
                          <template v-else-if="col.key === 'purity'"><span class="text-xs text-muted" :title="item.ip_purity_level || ''">{{ formatIpPurity(item) }}</span></template>
                          <template v-else-if="col.key === 'unlock'"><span class="text-xs" :class="item.openai_unlocked === true ? 'text-emerald-600' : item.openai_unlocked === false ? 'text-rose-600' : 'text-muted'" :title="item.openai_status || ''">{{ formatUnlock(item) }}</span></template>
                          <template v-else-if="col.key === 'fallback_front'"><span class="text-xs text-muted">{{ formatFallbackFront(item) }}</span></template>
                          <template v-else-if="col.key === 'source'"><span class="text-xs text-muted truncate" style="max-width: 160px;">{{ shortSource(item.source) }}</span></template>
                          <template v-else-if="col.key === 'action'">
                            <div class="btn-group">
                              <button @click="onTestSingleProxy(item)" :disabled="isActionRunning('testProxy-' + item.normalized_key)" class="btn btn-xs btn-secondary">测试</button>
                              <button @click="onCopyProxyLink(item)" :disabled="isActionRunning('copyProxyLink-' + item.normalized_key) || !proxyRawLink(item)" class="btn btn-xs btn-ghost">复制</button>
                            </div>
                          </template>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- Selection summary bar -->
                <div v-if="selectedProxyKeys.length > 0" class="selection-bar fade-in">
                  <span class="selection-bar-info">已选中 <strong>{{ selectedProxyKeys.length }}</strong> 个节点</span>
                  <div class="btn-group">
                    <button @click="onCopySelectedProxyLinks" :disabled="isActionRunning('copySelectedProxyLinks')" class="btn btn-xs btn-secondary">
                      {{ buttonLabel('copySelectedProxyLinks', '复制链接', '...') }}
                    </button>
                    <button @click="onRetestSelectedProxies" :disabled="isActionRunning('retestSelected')" class="btn btn-xs btn-secondary">
                      {{ buttonLabel('retestSelected', '重新测试', '...') }}
                    </button>
                    <button @click="onDeleteSelectedProxies" :disabled="isActionRunning('deleteSelectedProxies')" class="btn btn-xs btn-danger">
                      {{ buttonLabel('deleteSelectedProxies', '删除', '...') }}
                    </button>
                    <button @click="selectedProxyKeys = []" class="btn btn-xs btn-ghost">取消选择</button>
                  </div>
                </div>
              </div>
            </section>
</template>

<script>
import { rootProxyMixin } from "../rootProxyMixin";
import Breadcrumb from '../components/layout/Breadcrumb.vue';

export default {
  name: "ProxiesPage",
  components: {
    Breadcrumb,
  },
  mixins: [rootProxyMixin],
  data() {
    return {
      proxySortKey: '',
      proxySortDir: 'asc',
    };
  },
  computed: {
    breadcrumbItems() {
      return [
        { label: '首页', path: '/', onClick: () => this.selectPage('dashboard') },
        { label: '代理节点' },
      ];
    },
    sortedProxies() {
      const list = this.appState.proxies || [];
      if (!this.proxySortKey) return list;
      const key = this.proxySortKey;
      const dir = this.proxySortDir === 'asc' ? 1 : -1;
      return [...list].sort((a, b) => {
        let va, vb;
        if (key === 'latency') { va = a.latency_ms ?? Infinity; vb = b.latency_ms ?? Infinity; }
        else if (key === 'bandwidth') { va = a.speed_mbps ?? -1; vb = b.speed_mbps ?? -1; }
        else if (key === 'fail_count') { va = a.fail_count ?? 0; vb = b.fail_count ?? 0; }
        else if (key === 'last_checked') {
          va = a.last_checked_at ? new Date(a.last_checked_at).getTime() : 0;
          vb = b.last_checked_at ? new Date(b.last_checked_at).getTime() : 0;
        }
        else if (key === 'success_rate') {
          // 按可用性排序（作为成功率的代理指标）
          va = (a.available ? 1 : 0) * 1000 + (100 - (a.fail_count ?? 0));
          vb = (b.available ? 1 : 0) * 1000 + (100 - (b.fail_count ?? 0));
        }
        else { return 0; }
        return (va - vb) * dir;
      });
    },
    paginatedProxies() {
      const state = this.appState.pagination?.proxies || { page: 1, perPage: 50 };
      const perPage = Number(state.perPage) || 50;
      const page = Math.max(1, Number(state.page) || 1);
      const start = (page - 1) * perPage;
      return this.sortedProxies.slice(start, start + perPage);
    },
  },
  methods: {
    isSortableColumn(key) {
      return ['latency', 'bandwidth', 'fail_count', 'last_checked', 'success_rate'].includes(key);
    },
    sortLabel(key) {
      const labels = {
        latency: '延迟',
        bandwidth: '带宽',
        fail_count: '失败次数',
        last_checked: '最后检查',
        success_rate: '成功率'
      };
      return labels[key] || key;
    },
    toggleProxySort(key) {
      if (this.proxySortKey === key) {
        this.proxySortDir = this.proxySortDir === 'asc' ? 'desc' : 'asc';
      } else {
        this.proxySortKey = key;
        this.proxySortDir = 'asc';
      }
    },
    latencyStyle(ms) {
      if (!ms) return {};
      if (ms < 100) return { color: '#16a34a', fontWeight: 600 };
      if (ms < 500) return { color: '#ca8a04', fontWeight: 600 };
      return { color: '#dc2626', fontWeight: 600 };
    },
    bandwidthStyle(mbps) {
      if (!mbps || mbps <= 0) return {};
      if (mbps >= 50) return { color: '#16a34a' };
      if (mbps >= 10) return { color: '#ca8a04' };
      return { color: '#dc2626' };
    },
  },
};
</script>
