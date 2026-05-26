<template>
            <section v-show="activePage === 'proxies'" class="card fade-in">
              <div class="card-body">
                <div class="section-header">
                  <h2 class="section-title">代理节点</h2>
                  <div class="btn-group">
                    <button @click="clearProxyFilters" class="btn btn-sm btn-ghost">清空筛选</button>
                    <button @click="resetProxyColumns" class="btn btn-sm btn-ghost">重置列</button>
                    <el-button size="small" plain @click="proxyConfigDialogVisible = true">配置列</el-button>
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
                        <th v-for="col in visibleProxyColumns" :key="'th-' + col.key">{{ col.label }}</th>
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
                          <template v-else-if="col.key === 'purity'"><span class="text-xs text-muted">{{ formatIpPurity(item) }}</span></template>
                          <template v-else-if="col.key === 'unlock'"><span class="text-xs text-muted">{{ formatUnlock(item) }}</span></template>
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

export default {
  name: "ProxiesPage",
  mixins: [rootProxyMixin],
  methods: {
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
