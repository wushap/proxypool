<template>
            <section class="card fade-in">
              <div class="card-body">
                <!-- Breadcrumb -->
                <Breadcrumb :items="breadcrumbItems" />
                <div class="section-header">
                  <h2 class="section-title">代理节点</h2>
                  <div class="btn-group">
                    <button @click="openImportDialog" class="btn btn-sm btn-primary">导入代理</button>
                    <button @click="openExportDialog('all')" class="btn btn-sm btn-secondary">导出代理</button>
                    <button @click="clearProxyFilters" class="btn btn-sm btn-ghost">清空筛选</button>
                    <button @click="resetProxyColumns" class="btn btn-sm btn-ghost">重置列</button>
                    <el-button size="small" plain @click="proxyConfigDialogVisible = true">配置列</el-button>
                  </div>
                </div>

                <!-- Advanced Filter Panel -->
                <div class="filter-panel">
                  <button class="filter-panel-toggle" @click="advancedFilterOpen = !advancedFilterOpen" :aria-expanded="advancedFilterOpen" aria-label="切换高级筛选面板">
                    <span style="display: flex; align-items: center; gap: 6px;">
                      <span class="filter-panel-toggle-icon" :class="{ expanded: advancedFilterOpen }">&#9654;</span>
                      高级筛选
                    </span>
                    <div class="filter-panel-active-chips">
                      <span v-for="chip in activeFilterChips" :key="chip.key" class="filter-chip">
                        {{ chip.label }}: {{ chip.value }}
                        <button class="filter-chip-remove" @click.stop="removeFilterChip(chip.key)" :aria-label="'移除筛选条件: ' + chip.label">&times;</button>
                      </span>
                    </div>
                  </button>
                  <div v-show="advancedFilterOpen" class="filter-panel-body">
                    <div class="filter-panel-field">
                      <label>协议</label>
                      <el-select v-model="proxyFilters.protocol" clearable placeholder="全部协议" size="small" style="width: 100%">
                        <el-option v-for="opt in protocolFilterOptions" :key="'afp-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                      </el-select>
                    </div>
                    <div class="filter-panel-field">
                      <label>状态</label>
                      <el-select v-model="proxyFilters.available" clearable placeholder="全部状态" size="small" style="width: 100%">
                        <el-option v-for="opt in statusFilterOptions" :key="'afs-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                      </el-select>
                    </div>
                    <div class="filter-panel-field">
                      <label>最低分数 (0-100)</label>
                      <div style="display: flex; align-items: center; gap: 8px;">
                        <el-slider v-model="scoreMinValue" :min="0" :max="100" :step="5" style="flex: 1;" :show-tooltip="true" />
                        <span class="text-xs text-muted" style="min-width: 28px; text-align: right;">{{ scoreMinValue || '-' }}</span>
                      </div>
                    </div>
                    <div class="filter-panel-field">
                      <label>最大延迟 (ms)</label>
                      <div style="display: flex; align-items: center; gap: 8px;">
                        <el-slider v-model="latencyMaxValue" :min="0" :max="5000" :step="100" style="flex: 1;" :show-tooltip="true" />
                        <span class="text-xs text-muted" style="min-width: 42px; text-align: right;">{{ latencyMaxValue ? latencyMaxValue + 'ms' : '-' }}</span>
                      </div>
                    </div>
                    <div class="filter-panel-field">
                      <label>带宽 &gt; Mbps</label>
                      <el-input v-model="proxyFilters.speed_min_mbps" clearable placeholder="最小带宽" size="small" />
                    </div>
                    <div class="filter-panel-field">
                      <label>国家/地区</label>
                      <el-select v-model="proxyFilters.geo_country" clearable placeholder="全部国家" size="small" style="width: 100%" @change="onGeoCountryChanged">
                        <el-option v-for="opt in geoCountryOptions" :key="'afgc-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                      </el-select>
                    </div>
                    <div class="filter-panel-field">
                      <label>IP 纯净度</label>
                      <el-select v-model="proxyFilters.ip_purity" clearable placeholder="全部" size="small" style="width: 100%">
                        <el-option v-for="opt in ipPurityFilterOptions" :key="'afip-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                      </el-select>
                    </div>
                    <div class="filter-panel-field">
                      <label>ChatGPT</label>
                      <el-select v-model="proxyFilters.openai" clearable placeholder="全部" size="small" style="width: 100%">
                        <el-option v-for="opt in openaiFilterOptions" :key="'afo-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                      </el-select>
                    </div>
                    <div class="filter-panel-field">
                      <label>前置可用</label>
                      <el-select v-model="proxyFilters.fallback_front" clearable placeholder="全部" size="small" style="width: 100%">
                        <el-option v-for="opt in fallbackFrontFilterOptions" :key="'aff-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                      </el-select>
                    </div>
                    <div class="filter-panel-field">
                      <label>来源</label>
                      <el-select v-model="proxyFilters.source" clearable filterable allow-create default-first-option placeholder="全部来源" size="small" style="width: 100%">
                        <el-option v-for="opt in sourceFilterOptions" :key="'afsrc-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                      </el-select>
                    </div>
                    <div class="filter-panel-actions">
                      <div style="display: flex; align-items: center; gap: 6px; margin-right: auto;">
                        <el-input v-model="filterPresetName" size="small" placeholder="预设名称" style="width: 120px;" aria-label="筛选预设名称" />
                        <button @click="saveCurrentFilterPreset()" class="btn btn-xs btn-secondary" aria-label="保存当前筛选条件">保存筛选</button>
                        <el-select v-if="savedFilterPresets.length" v-model="activeFilterPreset" size="small" placeholder="加载预设" clearable style="width: 120px;" @change="onFilterPresetChange" aria-label="加载筛选预设">
                          <el-option v-for="p in savedFilterPresets" :key="'fp-' + p.name" :label="p.name" :value="p.name"></el-option>
                        </el-select>
                        <button v-if="activeFilterPreset" @click="deleteCurrentFilterPreset()" class="btn btn-xs btn-ghost" style="color: #ef4444;" :aria-label="'删除筛选预设: ' + activeFilterPreset">删除预设</button>
                      </div>
                      <button @click="clearProxyFilters" class="btn btn-xs btn-ghost" aria-label="清空所有筛选条件">清空</button>
                      <button @click="updateUrlWithFilters()" class="btn btn-xs btn-secondary" aria-label="应用筛选条件并刷新">应用</button>
                    </div>
                  </div>
                </div>

                <!-- Status bar -->
                <div class="status-bar" style="margin-bottom: 8px;" role="status" aria-live="polite" aria-atomic="true">
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
                    <select v-model.number="pagination.proxies.perPage" @change="onPaginationPageSizeChange('proxies')" class="select input-sm" style="width: 56px;" aria-label="每页显示数量">
                      <option v-for="n in pageSizeOptions" :key="'px-' + n" :value="n">{{ n }}</option>
                    </select>
                    <span class="text-muted">{{ pageIndicator('proxies') }}</span>
                  </div>
                  <div class="pagination-nav">
                    <button @click="onCopySelectedProxyLinks" :disabled="!selectedProxyKeys.length || isActionRunning('copySelectedProxyLinks')" class="btn btn-xs btn-secondary" :aria-label="'复制选中的 ' + selectedProxyKeys.length + ' 个代理链接'">
                      {{ buttonLabel('copySelectedProxyLinks', '复制选中(' + selectedProxyKeys.length + ')', '...') }}
                    </button>
                    <button @click="onDeleteSelectedProxies" :disabled="!selectedProxyKeys.length || isActionRunning('deleteSelectedProxies')" class="btn btn-xs btn-danger" :aria-label="'删除选中的 ' + selectedProxyKeys.length + ' 个代理'">
                      {{ buttonLabel('deleteSelectedProxies', '删除选中(' + selectedProxyKeys.length + ')', '...') }}
                    </button>
                    <button @click="onLoadDataClick" :disabled="isActionRunning('loadData')" class="btn btn-xs btn-secondary" aria-label="刷新代理数据">
                      {{ buttonLabel('loadData', '刷新', '...') }}
                    </button>
                    <button @click="goPrevPage('proxies')" :disabled="!canPrevPage('proxies')" class="btn btn-xs btn-ghost" aria-label="上一页">上一页</button>
                    <button @click="goNextPage('proxies')" :disabled="!canNextPage('proxies')" class="btn btn-xs btn-ghost" aria-label="下一页">下一页</button>
                  </div>
                </div>

                <!-- Config dialog -->
                <el-dialog v-model="proxyConfigDialogVisible" title="表格配置（筛选 + 列管理）" width="min(1100px, 95vw)" append-to-body aria-labelledby="config-dialog-title" aria-modal="true">
                  <h3 id="config-dialog-title" class="sr-only">表格配置（筛选 + 列管理）</h3>
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
                <div aria-live="polite" aria-atomic="true" class="sr-only">
                  <span v-if="isLoading">正在加载代理数据</span>
                  <span v-else-if="loadError">加载失败: {{ loadError }}</span>
                  <span v-else-if="!isLoading && proxies">已加载 {{ proxies.length }} 个代理节点</span>
                </div>
                <ErrorState v-if="loadError" :title="'加载失败'" :message="loadError" :retryable="true" @retry="handleLoadData" />
                <LoadingState v-else-if="isLoading" text="加载代理数据中..." size="small" />
                <!-- Skeleton loading -->
                <div v-else-if="isLoadingSkeleton" class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 36px;"></th>
                        <th style="width: 30px;"></th>
                        <th style="width: 36px;"></th>
                        <th v-for="col in visibleProxyColumns" :key="'th-skeleton-' + col.key">{{ col.label }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="i in 5" :key="'skeleton-' + i">
                        <td><div class="skeleton skeleton-checkbox"></div></td>
                        <td><div class="skeleton skeleton-checkbox"></div></td>
                        <td><div class="skeleton skeleton-checkbox"></div></td>
                        <td v-for="col in visibleProxyColumns" :key="'td-skeleton-' + i + '-' + col.key">
                          <div class="skeleton skeleton-text" :style="{ width: col.key === 'action' ? '60px' : col.key === 'serial' ? '30px' : '100px' }"></div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 36px;">
                          <input type="checkbox" :checked="areAllPaginatedProxiesSelected()" :disabled="!paginatedProxies.length" @change="toggleAllPaginatedProxies($event.target.checked)" aria-label="选择所有代理" />
                        </th>
                        <th style="width: 30px;" title="收藏" aria-label="收藏"></th>
                        <th style="width: 36px;"></th>
                        <th v-for="col in visibleProxyColumns" :key="'th-' + col.key"
                          :class="{ 'sortable-th': isSortableColumn(col.key) }"
                          @click="isSortableColumn(col.key) && toggleProxySort(col.key)"
                          :aria-label="isSortableColumn(col.key) ? '点击排序: ' + col.label : col.label"
                          :aria-sort="proxySortKey === col.key ? (proxySortDir === 'asc' ? 'ascending' : 'descending') : 'none'">
                          <el-tooltip v-if="getColumnTooltip(col.key)" :content="getColumnTooltip(col.key)" placement="top" :show-after="300">
                            <span>{{ col.label }}<span class="help-icon">?</span></span>
                          </el-tooltip>
                          <span v-else>{{ col.label }}</span>
                          <span v-if="isSortableColumn(col.key) && proxySortKey === col.key" class="sort-indicator">{{ proxySortDir === 'asc' ? '↑' : '↓' }}</span>
                        </th>
                        <th style="width: 80px;">操作</th>
                      </tr>
                    </thead>
                    <tbody :style="virtualScrollEnabled ? { height: virtualScrollTotalHeight + 'px', position: 'relative' } : {}">
                      <template v-for="item in (virtualScrollEnabled ? getVirtualScrollItems() : paginatedProxies)" :key="item.normalized_key">
                        <tr>
                          <td><input v-model="selectedProxyKeys" type="checkbox" :value="item.normalized_key" :aria-label="'选择代理 ' + item.host" /></td>
                          <td>
                            <button @click="toggleFavorite(item.normalized_key)" class="btn btn-xs btn-ghost favorite-btn-row" :title="isFavorite(item.normalized_key) ? '取消收藏' : '收藏'" :aria-label="isFavorite(item.normalized_key) ? '取消收藏此代理' : '收藏此代理'">
                              {{ isFavorite(item.normalized_key) ? '★' : '☆' }}
                            </button>
                          </td>
                          <td>
                            <button @click="toggleExpandProxy(item.normalized_key)" class="btn btn-xs btn-ghost" style="padding: 2px 4px;" :aria-label="isProxyExpanded(item.normalized_key) ? '收起代理详情' : '展开代理详情'" :aria-expanded="isProxyExpanded(item.normalized_key)">
                              <span :style="{ transform: isProxyExpanded(item.normalized_key) ? 'rotate(90deg)' : '', display: 'inline-block', transition: 'transform 0.2s' }">▶</span>
                            </button>
                          </td>
                        <td v-for="col in visibleProxyColumns" :key="'td-' + item.normalized_key + '-' + col.key">
                          <template v-if="col.key === 'serial'"><span class="mono text-muted">#{{ getSerial(item.normalized_key) }}</span></template>
                          <template v-else-if="col.key === 'protocol'"><span class="font-semibold">{{ item.protocol }}</span></template>
                          <template v-else-if="col.key === 'address'"><span>{{ item.host }}:{{ item.port }}</span></template>
                          <template v-else-if="col.key === 'latency'"><span :style="latencyStyle(item.latency_ms)">{{ item.latency_ms ? item.latency_ms + ' ms' : '-' }}</span></template>
                          <template v-else-if="col.key === 'bandwidth'"><span class="mono text-xs" :style="bandwidthStyle(item.speed_mbps)">{{ formatBandwidthMbps(item) }}</span></template>
                          <template v-else-if="col.key === 'success_rate'"><span class="mono text-xs" :style="successRateStyle(item.success_rate)">{{ formatSuccessRate(item) }}</span></template>
                          <template v-else-if="col.key === 'fail_count'"><span class="mono text-xs" :style="failCountStyle(item.fail_count)">{{ item.fail_count ?? 0 }}</span></template>
                          <template v-else-if="col.key === 'last_error'">
                            <el-tooltip v-if="item.last_error" placement="top" :show-after="300">
                              <template #content>
                                <div style="max-width: 300px;">
                                  <div style="font-weight: 600; margin-bottom: 4px;">错误信息</div>
                                  <div style="margin-bottom: 8px;">{{ item.last_error }}</div>
                                  <div v-if="formatFailStage(item.last_error)" style="margin-bottom: 4px;">
                                    <span style="font-weight: 600;">失败阶段：</span>{{ formatFailStage(item.last_error) }}
                                  </div>
                                  <div v-if="getFailAdvice(item.last_error)" style="color: #90cdf4; font-size: 12px;">
                                    {{ getFailAdvice(item.last_error) }}
                                  </div>
                                </div>
                              </template>
                              <span class="text-xs text-rose-600 truncate" style="max-width: 120px; display: inline-block;">{{ formatFailStage(item.last_error) || item.last_error }}</span>
                            </el-tooltip>
                            <span v-else class="text-xs text-muted">-</span>
                          </template>
                          <template v-else-if="col.key === 'status'"><span class="badge" :class="item.available ? 'badge-success' : 'badge-danger'">{{ item.available ? 'UP' : 'DOWN' }}</span></template>
                          <template v-else-if="col.key === 'checked_at'">
                            <el-tooltip :content="formatTime(item.last_checked_at)" placement="top" :show-after="300">
                              <span class="text-xs text-muted">{{ formatRelativeTime(item.last_checked_at) }}</span>
                            </el-tooltip>
                          </template>
                          <template v-else-if="col.key === 'geo'"><span class="text-xs text-muted">{{ formatGeo(item) }}</span></template>
                          <template v-else-if="col.key === 'purity'"><span class="text-xs text-muted" :title="item.ip_purity_level || ''">{{ formatIpPurity(item) }}</span></template>
                          <template v-else-if="col.key === 'unlock'"><span class="text-xs" :class="item.openai_unlocked === true ? 'text-emerald-600' : item.openai_unlocked === false ? 'text-rose-600' : 'text-muted'" :title="item.openai_status || ''">{{ formatUnlock(item) }}</span></template>
                          <template v-else-if="col.key === 'fallback_front'"><span class="text-xs text-muted">{{ formatFallbackFront(item) }}</span></template>
                          <template v-else-if="col.key === 'source'"><span class="text-xs text-muted truncate" style="max-width: 160px;">{{ shortSource(item.source) }}</span></template>
                          <template v-else-if="col.key === 'action'">
                            <div class="btn-group">
                              <button @click="quickTestProxy(item)" :disabled="isActionRunning('quickTest-' + item.normalized_key)" class="btn btn-xs btn-ghost quick-test-btn" :title="inlineTestResults[item.normalized_key] ? `延迟: ${inlineTestResults[item.normalized_key].latency_ms ?? '-'}ms, 状态: ${inlineTestResults[item.normalized_key].available ? 'UP' : 'DOWN'}` : '快速测试'" :aria-label="'快速测试代理 ' + item.host">
                                {{ isActionRunning('quickTest-' + item.normalized_key) ? '⏳' : '⚡' }}
                              </button>
                              <button @click="onTestSingleProxy(item)" :disabled="isActionRunning('testProxy-' + item.normalized_key)" class="btn btn-xs btn-secondary" :aria-label="'完整测试代理 ' + item.host">
                                {{ isActionRunning('testProxy-' + item.normalized_key) ? '...' : '测试' }}
                              </button>
                              <button @click="onCopyProxyLink(item)" :disabled="isActionRunning('copyProxyLink-' + item.normalized_key) || !proxyRawLink(item)" class="btn btn-xs btn-ghost" :aria-label="'复制代理 ' + item.host + ' 的链接'">复制</button>
                            </div>
                            <div v-if="inlineTestResults[item.normalized_key]" class="inline-test-result" :class="inlineTestResults[item.normalized_key].available ? 'inline-test-up' : 'inline-test-down'">
                              <span class="inline-test-latency">{{ inlineTestResults[item.normalized_key].latency_ms ?? '-' }}ms</span>
                              <span class="inline-test-status">{{ inlineTestResults[item.normalized_key].available ? 'UP' : 'DOWN' }}</span>
                            </div>
                          </template>
                        </td>
                        </tr>
                        <tr v-if="isProxyExpanded(item.normalized_key)" class="proxy-detail-row">
                          <td :colspan="visibleProxyColumns.length + 3" style="padding: 12px; background: var(--bg-secondary);">
                            <div class="proxy-detail-grid">
                              <div class="proxy-detail-section">
                                <h4 class="proxy-detail-title">基础信息</h4>
                                <div class="proxy-detail-item"><span class="text-muted">协议：</span>{{ item.protocol }}</div>
                                <div class="proxy-detail-item"><span class="text-muted">地址：</span>{{ item.host }}:{{ item.port }}</div>
                                <div class="proxy-detail-item"><span class="text-muted">名称：</span>{{ item.name || '-' }}</div>
                                <div class="proxy-detail-item"><span class="text-muted">来源：</span>{{ item.source || '-' }}</div>
                              </div>
                              <div class="proxy-detail-section">
                                <h4 class="proxy-detail-title">健康状态</h4>
                                <div class="proxy-detail-item"><span class="text-muted">状态：</span><span class="badge badge-sm" :class="item.available ? 'badge-success' : 'badge-danger'">{{ item.available ? '可用' : '不可用' }}</span></div>
                                <div class="proxy-detail-item"><span class="text-muted">延迟：</span><span :style="latencyStyle(item.latency_ms)">{{ item.latency_ms ? item.latency_ms + ' ms' : '-' }}</span></div>
                                <div class="proxy-detail-item"><span class="text-muted">带宽：</span><span :style="bandwidthStyle(item.speed_mbps)">{{ formatBandwidthMbps(item) }}</span></div>
                                <div class="proxy-detail-item"><span class="text-muted">失败次数：</span><span :style="failCountStyle(item.fail_count)">{{ item.fail_count ?? 0 }}</span></div>
                                <div class="proxy-detail-item"><span class="text-muted">成功率：</span><span :style="successRateStyle(item.success_rate)">{{ formatSuccessRate(item) }}</span></div>
                              </div>
                              <div class="proxy-detail-section">
                                <h4 class="proxy-detail-title">时间信息</h4>
                                <div class="proxy-detail-item"><span class="text-muted">最后检测：</span>{{ formatRelativeTime(item.last_checked_at) }}</div>
                                <div class="proxy-detail-item"><span class="text-muted">最后可见：</span>{{ formatRelativeTime(item.last_seen_at) }}</div>
                                <div class="proxy-detail-item"><span class="text-muted">上次错误：</span>{{ item.last_error || '-' }}</div>
                              </div>
                              <div class="proxy-detail-section">
                                <h4 class="proxy-detail-title">附加信息</h4>
                                <div class="proxy-detail-item"><span class="text-muted">地理位置：</span>{{ formatGeo(item) || '-' }}</div>
                                <div class="proxy-detail-item"><span class="text-muted">IP纯净度：</span>{{ formatIpPurity(item) || '-' }}</div>
                                <div class="proxy-detail-item"><span class="text-muted">ChatGPT：</span>{{ formatUnlock(item) }}</div>
                                <div class="proxy-detail-item"><span class="text-muted">链式代理：</span>{{ formatFallbackFront(item) || '直连' }}</div>
                              </div>
                              <div class="proxy-detail-section">
                                <h4 class="proxy-detail-title">标签与收藏</h4>
                                <div class="proxy-detail-item">
                                  <span class="text-muted">收藏：</span>
                                  <button @click="toggleFavorite(item.normalized_key)" class="btn btn-xs btn-ghost favorite-btn" :aria-label="isFavorite(item.normalized_key) ? '取消收藏此代理' : '收藏此代理'">
                                    {{ isFavorite(item.normalized_key) ? '★ 已收藏' : '☆ 收藏' }}
                                  </button>
                                </div>
                                <div class="proxy-detail-item">
                                  <span class="text-muted">标签：</span>
                                  <div class="proxy-tags">
                                    <span v-for="tag in getProxyTags(item.normalized_key)" :key="'tag-' + tag" class="proxy-tag">
                                      {{ tag }}
                                      <button @click="removeProxyTag(item.normalized_key, tag)" class="tag-remove" :aria-label="'移除标签: ' + tag">&times;</button>
                                    </span>
                                    <button @click="showAddTagDialog(item.normalized_key)" class="btn btn-xs btn-ghost" :aria-label="'为代理添加标签'">+ 添加</button>
                                  </div>
                                </div>
                              </div>
                              <div class="proxy-detail-section proxy-detail-section-full">
                                <h4 class="proxy-detail-title">检测历史</h4>
                                <!-- Latency Trend Chart -->
                                <div v-if="getProxyLatencyTrend(item.normalized_key)" class="proxy-latency-trend" style="margin-bottom: 12px;">
                                  <div class="proxy-latency-trend-header">
                                    <span class="text-xs text-muted">延迟趋势（最近10次）</span>
                                    <span class="text-xs font-semibold">{{ getProxyLatencyTrend(item.normalized_key).maxLatency }}ms</span>
                                  </div>
                                  <svg :viewBox="`0 0 ${getProxyLatencyTrend(item.normalized_key).width} ${getProxyLatencyTrend(item.normalized_key).height}`" class="proxy-trend-svg">
                                    <defs>
                                      <linearGradient :id="'proxyTrendGrad-' + item.normalized_key" x1="0%" y1="0%" x2="0%" y2="100%">
                                        <stop offset="0%" stop-color="#16a34a" stop-opacity="0.3" />
                                        <stop offset="100%" stop-color="#16a34a" stop-opacity="0" />
                                      </linearGradient>
                                    </defs>
                                    <path :d="getProxyLatencyTrend(item.normalized_key).pathData + ` L ${getProxyLatencyTrend(item.normalized_key).width - 4} ${getProxyLatencyTrend(item.normalized_key).height - 4} L 4 ${getProxyLatencyTrend(item.normalized_key).height - 4} Z`" :fill="`url(#proxyTrendGrad-${item.normalized_key})`" />
                                    <path :d="getProxyLatencyTrend(item.normalized_key).pathData" fill="=" stroke="#16a34a" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                                    <circle v-for="(pt, i) in getProxyLatencyTrend(item.normalized_key).points" :key="'proxy-trend-pt-' + i"
                                      :cx="pt.x" :cy="pt.y" r="2" fill="#16a34a" stroke="white" stroke-width="0.5" />
                                  </svg>
                                </div>

                                <!-- Success Rate Dots -->
                                <div v-if="getProxySuccessTrend(item.normalized_key)" class="proxy-success-trend" style="margin-bottom: 12px;">
                                  <div class="proxy-success-trend-header">
                                    <span class="text-xs text-muted">成功率（最近10次）</span>
                                    <span class="text-xs font-semibold" :class="getProxySuccessTrend(item.normalized_key).trend === 'up' ? 'text-emerald-600' : getProxySuccessTrend(item.normalized_key).trend === 'down' ? 'text-rose-600' : 'text-gray-600'">
                                      {{ getProxySuccessTrend(item.normalized_key).rate }}%
                                      <span v-if="getProxySuccessTrend(item.normalized_key).trend === 'up'">↑</span>
                                      <span v-else-if="getProxySuccessTrend(item.normalized_key).trend === 'down'">↓</span>
                                      <span v-else>→</span>
                                    </span>
                                  </div>
                                  <div class="proxy-success-dots">
                                    <span v-for="(dot, i) in getProxySuccessTrend(item.normalized_key).dots" :key="'success-dot-' + i"
                                      class="proxy-success-dot"
                                      :class="dot ? 'proxy-success-dot-pass' : 'proxy-success-dot-fail'"
                                      :title="dot ? '通过' : '失败'">
                                    </span>
                                  </div>
                                </div>

                                <!-- Reliability Score -->
                                <div v-if="getProxyReliabilityScore(item.normalized_key) !== null" class="proxy-reliability" style="margin-bottom: 12px;">
                                  <div class="proxy-reliability-header">
                                    <span class="text-xs text-muted">可靠性</span>
                                    <span class="text-xs font-semibold" :class="getProxyReliabilityScore(item.normalized_key) >= 90 ? 'text-emerald-600' : getProxyReliabilityScore(item.normalized_key) >= 70 ? 'text-amber-600' : 'text-rose-600'">
                                      {{ getProxyReliabilityScore(item.normalized_key) }}%
                                    </span>
                                  </div>
                                  <div class="proxy-reliability-bar">
                                    <div class="proxy-reliability-bar-fill"
                                      :class="getProxyReliabilityScore(item.normalized_key) >= 90 ? 'reliability-high' : getProxyReliabilityScore(item.normalized_key) >= 70 ? 'reliability-medium' : 'reliability-low'"
                                      :style="{ width: getProxyReliabilityScore(item.normalized_key) + '%' }">
                                    </div>
                                  </div>
                                </div>
                                <!-- Test History List -->
                                <div v-if="getProxyTestHistory(item.normalized_key).length" class="test-history-list">
                                  <div v-for="(entry, hIdx) in getProxyTestHistory(item.normalized_key)" :key="'th-' + hIdx" class="test-history-item" :class="entry.available ? 'test-history-up' : 'test-history-down'">
                                    <span class="test-history-time">{{ formatRelativeTime(entry.timestamp) }}</span>
                                    <span class="test-history-status" :class="entry.available ? 'text-emerald-600' : 'text-rose-600'">{{ entry.available ? 'UP' : 'DOWN' }}</span>
                                    <span class="test-history-latency">{{ entry.latency_ms != null ? entry.latency_ms + 'ms' : '-' }}</span>
                                    <span v-if="entry.error" class="test-history-error text-rose-600" :title="entry.error">{{ entry.error.length > 40 ? entry.error.substring(0, 37) + '...' : entry.error }}</span>
                                  </div>
                                </div>
                                <div v-else class="text-xs text-muted">暂无检测记录</div>
                              </div>

                              <!-- Advanced Features Section -->
                              <div class="proxy-detail-section proxy-detail-section-full" style="border-top: 1px solid var(--line-soft); margin-top: 12px; padding-top: 12px;">
                                <h4 class="proxy-detail-title">高级分析</h4>

                                <!-- Health History Timeline -->
                                <div class="advanced-feature" style="margin-bottom: 16px;">
                                  <div class="advanced-feature-header" @click="toggleAdvancedFeature(item.normalized_key, 'healthTimeline')">
                                    <span class="text-xs font-semibold">健康历史时间线</span>
                                    <span class="text-xs text-muted">{{ isAdvancedFeatureExpanded(item.normalized_key, 'healthTimeline') ? '收起' : '展开' }}</span>
                                  </div>
                                  <div v-if="isAdvancedFeatureExpanded(item.normalized_key, 'healthTimeline')" class="advanced-feature-content">
                                    <div v-if="getProxyHealthTimeline(item.normalized_key).length" class="health-timeline">
                                      <div v-for="(entry, idx) in getProxyHealthTimeline(item.normalized_key).slice(0, 10)" :key="'ht-' + idx" class="timeline-item">
                                        <div class="timeline-dot" :class="entry.status === 'up' ? 'timeline-dot-success' : 'timeline-dot-danger'"></div>
                                        <div class="timeline-content">
                                          <div class="timeline-time">{{ formatRelativeTime(entry.timestamp) }}</div>
                                          <div class="timeline-status">
                                            <span class="badge badge-sm" :class="entry.status === 'up' ? 'badge-success' : 'badge-danger'">{{ entry.status.toUpperCase() }}</span>
                                            <span class="text-xs text-muted" v-if="entry.latency">延迟 {{ entry.latency }}ms</span>
                                          </div>
                                        </div>
                                      </div>
                                    </div>
                                    <div v-else class="text-xs text-muted">暂无健康历史数据</div>
                                  </div>
                                </div>

                                <!-- Performance Benchmarks -->
                                <div class="advanced-feature" style="margin-bottom: 16px;">
                                  <div class="advanced-feature-header" @click="toggleAdvancedFeature(item.normalized_key, 'benchmarks')">
                                    <span class="text-xs font-semibold">性能基准测试</span>
                                    <span class="text-xs text-muted">{{ isAdvancedFeatureExpanded(item.normalized_key, 'benchmarks') ? '收起' : '展开' }}</span>
                                  </div>
                                  <div v-if="isAdvancedFeatureExpanded(item.normalized_key, 'benchmarks')" class="advanced-feature-content">
                                    <div class="benchmark-grid">
                                      <div class="benchmark-item">
                                        <span class="benchmark-label">延迟评分</span>
                                        <span class="benchmark-value" :class="getProxyBenchmarkScore(item, 'latency') >= 80 ? 'text-success' : getProxyBenchmarkScore(item, 'latency') >= 50 ? 'text-warning' : 'text-danger'">
                                          {{ getProxyBenchmarkScore(item, 'latency') }}/100
                                        </span>
                                      </div>
                                      <div class="benchmark-item">
                                        <span class="benchmark-label">带宽评分</span>
                                        <span class="benchmark-value" :class="getProxyBenchmarkScore(item, 'bandwidth') >= 80 ? 'text-success' : getProxyBenchmarkScore(item, 'bandwidth') >= 50 ? 'text-warning' : 'text-danger'">
                                          {{ getProxyBenchmarkScore(item, 'bandwidth') }}/100
                                        </span>
                                      </div>
                                      <div class="benchmark-item">
                                        <span class="benchmark-label">稳定性评分</span>
                                        <span class="benchmark-value" :class="getProxyBenchmarkScore(item, 'stability') >= 80 ? 'text-success' : getProxyBenchmarkScore(item, 'stability') >= 50 ? 'text-warning' : 'text-danger'">
                                          {{ getProxyBenchmarkScore(item, 'stability') }}/100
                                        </span>
                                      </div>
                                      <div class="benchmark-item">
                                        <span class="benchmark-label">综合评分</span>
                                        <span class="benchmark-value font-semibold" :class="getProxyBenchmarkScore(item, 'overall') >= 80 ? 'text-success' : getProxyBenchmarkScore(item, 'overall') >= 50 ? 'text-warning' : 'text-danger'">
                                          {{ getProxyBenchmarkScore(item, 'overall') }}/100
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                </div>

                                <!-- Geographic Routing Visualization -->
                                <div class="advanced-feature" style="margin-bottom: 16px;">
                                  <div class="advanced-feature-header" @click="toggleAdvancedFeature(item.normalized_key, 'geoRouting')">
                                    <span class="text-xs font-semibold">地理路由可视化</span>
                                    <span class="text-xs text-muted">{{ isAdvancedFeatureExpanded(item.normalized_key, 'geoRouting') ? '收起' : '展开' }}</span>
                                  </div>
                                  <div v-if="isAdvancedFeatureExpanded(item.normalized_key, 'geoRouting')" class="advanced-feature-content">
                                    <div class="geo-routing-info">
                                      <div class="geo-route-item">
                                        <span class="text-xs text-muted">当前位置：</span>
                                        <span class="text-xs font-semibold">{{ formatGeo(item) || '未知' }}</span>
                                      </div>
                                      <div class="geo-route-item">
                                        <span class="text-xs text-muted">路由建议：</span>
                                        <span class="text-xs">{{ getGeoRoutingSuggestion(item) }}</span>
                                      </div>
                                      <div class="geo-route-item">
                                        <span class="text-xs text-muted">延迟距离：</span>
                                        <span class="text-xs">{{ getGeoLatencyDistance(item) }}</span>
                                      </div>
                                    </div>
                                  </div>
                                </div>

                                <!-- Protocol Optimization Suggestions -->
                                <div class="advanced-feature" style="margin-bottom: 16px;">
                                  <div class="advanced-feature-header" @click="toggleAdvancedFeature(item.normalized_key, 'protocolOpt')">
                                    <span class="text-xs font-semibold">协议优化建议</span>
                                    <span class="text-xs text-muted">{{ isAdvancedFeatureExpanded(item.normalized_key, 'protocolOpt') ? '收起' : '展开' }}</span>
                                  </div>
                                  <div v-if="isAdvancedFeatureExpanded(item.normalized_key, 'protocolOpt')" class="advanced-feature-content">
                                    <div v-if="getProtocolOptimizations(item).length" class="optimization-list">
                                      <div v-for="(opt, idx) in getProtocolOptimizations(item)" :key="'opt-' + idx" class="optimization-item" :class="'optimization-' + opt.severity">
                                        <span class="optimization-icon">{{ opt.severity === 'high' ? '⚠️' : opt.severity === 'medium' ? '💡' : 'ℹ️' }}</span>
                                        <span class="text-xs">{{ opt.suggestion }}</span>
                                      </div>
                                    </div>
                                    <div v-else class="text-xs text-muted">暂无优化建议</div>
                                  </div>
                                </div>

                                <!-- Load Balancing Recommendations -->
                                <div class="advanced-feature">
                                  <div class="advanced-feature-header" @click="toggleAdvancedFeature(item.normalized_key, 'loadBalancing')">
                                    <span class="text-xs font-semibold">负载均衡建议</span>
                                    <span class="text-xs text-muted">{{ isAdvancedFeatureExpanded(item.normalized_key, 'loadBalancing') ? '收起' : '展开' }}</span>
                                  </div>
                                  <div v-if="isAdvancedFeatureExpanded(item.normalized_key, 'loadBalancing')" class="advanced-feature-content">
                                    <div class="load-balancing-info">
                                      <div class="lb-metric">
                                        <span class="text-xs text-muted">当前负载：</span>
                                        <div class="lb-bar">
                                          <div class="lb-bar-fill" :style="{ width: getProxyLoad(item) + '%' }" :class="getProxyLoad(item) > 80 ? 'lb-bar-danger' : getProxyLoad(item) > 50 ? 'lb-bar-warning' : 'lb-bar-success'"></div>
                                        </div>
                                        <span class="text-xs font-semibold">{{ getProxyLoad(item) }}%</span>
                                      </div>
                                      <div class="lb-metric">
                                        <span class="text-xs text-muted">推荐权重：</span>
                                        <span class="text-xs font-semibold">{{ getProxyRecommendedWeight(item) }}</span>
                                      </div>
                                      <div class="lb-metric">
                                        <span class="text-xs text-muted">适合场景：</span>
                                        <span class="text-xs">{{ getProxyUseCase(item) }}</span>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      </template>
                    </tbody>
                  </table>
                </div>

                <!-- Protocol Distribution Pie Chart -->
                <div v-if="protocolDistributionData" class="protocol-distribution-card" style="margin-top: 16px;">
                  <div class="card">
                    <div class="card-body">
                      <h3 class="card-title">协议分布</h3>
                      <div class="protocol-distribution-wrapper">
                        <div class="protocol-donut-chart">
                          <svg viewBox="0 0 120 120" class="protocol-donut-svg">
                            <circle v-for="(seg, i) in protocolDonutSegments" :key="'proxy-donut-' + i"
                              cx="60" cy="60" r="45" fill="none"
                              :stroke="seg.color" stroke-width="20"
                              :stroke-dasharray="seg.dashArray"
                              :stroke-dashoffset="seg.dashOffset"
                              :style="{ transition: 'stroke-dasharray 0.5s ease, stroke-dashoffset 0.5s ease' }"
                            />
                          </svg>
                          <div class="protocol-donut-center">
                            <span class="protocol-donut-total">{{ allProxyCount }}</span>
                            <span class="protocol-donut-label">节点</span>
                          </div>
                        </div>
                        <div class="protocol-donut-legend">
                          <div v-for="p in protocolDistributionData" :key="'proxy-legend-' + p.name" class="protocol-donut-legend-item">
                            <span class="protocol-donut-legend-dot" :style="{ background: p.color }"></span>
                            <span class="protocol-donut-legend-name">{{ p.name }}</span>
                            <span class="protocol-donut-legend-value">{{ p.count }}</span>
                            <span class="protocol-donut-legend-pct">{{ p.pct }}%</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Selection summary bar -->
                <div v-if="selectedProxyKeys.length > 0" class="selection-bar fade-in" role="status" aria-live="polite">
                  <span class="selection-bar-info">已选中 <strong>{{ selectedProxyKeys.length }}</strong> 个节点</span>
                  <div class="btn-group">
                    <button @click="openExportDialog('selected')" class="btn btn-xs btn-secondary" aria-label="导出选中的代理">
                      导出选中
                    </button>
                    <button @click="onCopySelectedProxyLinks" :disabled="isActionRunning('copySelectedProxyLinks')" class="btn btn-xs btn-secondary" :aria-label="'复制选中的 ' + selectedProxyKeys.length + ' 个代理链接'">
                      {{ buttonLabel('copySelectedProxyLinks', '复制链接', '...') }}
                    </button>
                    <button @click="onRetestSelectedProxies" :disabled="isActionRunning('retestSelected')" class="btn btn-xs btn-secondary" :aria-label="'重新测试选中的 ' + selectedProxyKeys.length + ' 个代理'">
                      {{ buttonLabel('retestSelected', '重新测试', '...') }}
                    </button>
                    <button v-if="selectedProxyKeys.length >= 2 && selectedProxyKeys.length <= 3" @click="showComparisonView" class="btn btn-xs btn-secondary" aria-label="对比选中的代理">
                      对比选中
                    </button>
                    <button @click="onDeleteSelectedProxies" :disabled="isActionRunning('deleteSelectedProxies')" class="btn btn-xs btn-danger" :aria-label="'删除选中的 ' + selectedProxyKeys.length + ' 个代理'">
                      {{ buttonLabel('deleteSelectedProxies', '删除', '...') }}
                    </button>
                    <button @click="selectedProxyKeys = []" class="btn btn-xs btn-ghost">取消选择</button>
                  </div>
                </div>
              </div>
            </section>

            <!-- Add Tag Dialog -->
            <el-dialog v-model="addTagDialogVisible" title="添加标签" width="400px" append-to-body>
              <div class="tag-dialog-content">
                <p class="text-muted text-sm" style="margin-bottom: 12px;">为代理节点添加标签以便分类管理：</p>
                <el-input v-model="newTagName" placeholder="输入标签名称" @keyup.enter="addProxyTag" />
                <div class="tag-suggestions" v-if="commonTags.length">
                  <span class="text-xs text-muted">常用标签：</span>
                  <button v-for="tag in commonTags" :key="'suggest-' + tag" @click="newTagName = tag" class="btn btn-xs btn-ghost">
                    {{ tag }}
                  </button>
                </div>
              </div>
              <template #footer>
                <button class="btn btn-secondary" @click="addTagDialogVisible = false">取消</button>
                <button class="btn btn-primary" @click="addProxyTag" :disabled="!newTagName.trim()">添加</button>
              </template>
            </el-dialog>

            <!-- Comparison View Dialog -->
            <el-dialog v-model="comparisonDialogVisible" title="代理对比" width="min(900px, 95vw)" append-to-body @opened="drawRadarChart">
              <div class="comparison-content">
                <!-- Radar Chart -->
                <div class="radar-chart-container" style="margin-bottom: 16px; text-align: center;">
                  <canvas ref="radarChart" width="400" height="300" style="max-width: 100%;"></canvas>
                  <div class="radar-legend" style="margin-top: 8px;">
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'legend-' + idx" class="radar-legend-item">
                      <span class="radar-legend-dot" :style="{ background: radarColors[idx] }"></span>
                      #{{ getSerial(proxy.normalized_key) }} {{ proxy.protocol }}://{{ proxy.host }}
                    </span>
                  </div>
                </div>

                <!-- Comparison Table -->
                <div class="comparison-grid">
                  <div class="comparison-header">
                    <span class="comparison-label">属性</span>
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'comp-h-' + idx" class="comparison-value">
                      #{{ getSerial(proxy.normalized_key) }} {{ proxy.protocol }}
                    </span>
                  </div>
                  <div class="comparison-row">
                    <span class="comparison-label">地址</span>
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'comp-addr-' + idx" class="comparison-value mono">
                      {{ proxy.host }}:{{ proxy.port }}
                    </span>
                  </div>
                  <div class="comparison-row">
                    <span class="comparison-label">状态</span>
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'comp-status-' + idx" class="comparison-value" :class="{ 'best-value': isBestAvailable(proxy) }">
                      <span class="badge badge-sm" :class="proxy.available ? 'badge-success' : 'badge-danger'">
                        {{ proxy.available ? '可用' : '不可用' }}
                      </span>
                    </span>
                  </div>
                  <div class="comparison-row">
                    <span class="comparison-label">延迟</span>
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'comp-latency-' + idx" class="comparison-value" :class="{ 'best-value': isBestLatency(proxy) }" :style="latencyStyle(proxy.latency_ms)">
                      {{ proxy.latency_ms ? proxy.latency_ms + ' ms' : '-' }}
                    </span>
                  </div>
                  <div class="comparison-row">
                    <span class="comparison-label">带宽</span>
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'comp-bw-' + idx" class="comparison-value" :class="{ 'best-value': isBestBandwidth(proxy) }" :style="bandwidthStyle(proxy.speed_mbps)">
                      {{ formatBandwidthMbps(proxy) }}
                    </span>
                  </div>
                  <div class="comparison-row">
                    <span class="comparison-label">成功率</span>
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'comp-sr-' + idx" class="comparison-value" :class="{ 'best-value': isBestSuccessRate(proxy) }" :style="successRateStyle(proxy.success_rate)">
                      {{ formatSuccessRate(proxy) }}
                    </span>
                  </div>
                  <div class="comparison-row">
                    <span class="comparison-label">地理位置</span>
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'comp-geo-' + idx" class="comparison-value">
                      {{ formatGeo(proxy) || '-' }}
                    </span>
                  </div>
                  <div class="comparison-row">
                    <span class="comparison-label">IP纯净度</span>
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'comp-purity-' + idx" class="comparison-value">
                      {{ formatIpPurity(proxy) || '-' }}
                    </span>
                  </div>
                  <div class="comparison-row">
                    <span class="comparison-label">ChatGPT</span>
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'comp-unlock-' + idx" class="comparison-value" :class="{ 'best-value': isBestUnlock(proxy) }">
                      {{ formatUnlock(proxy) }}
                    </span>
                  </div>
                  <!-- Composite Score Row -->
                  <div class="comparison-row" style="border-top: 2px solid var(--line-soft); margin-top: 8px; padding-top: 8px;">
                    <span class="comparison-label" style="font-weight: 600;">综合评分</span>
                    <span v-for="(proxy, idx) in comparisonProxies" :key="'comp-score-' + idx" class="comparison-value" :class="{ 'best-value': isBestCompositeScore(proxy) }" style="font-weight: 600; font-size: 14px;">
                      {{ computeCompositeScore(proxy).toFixed(1) }}
                    </span>
                  </div>
                </div>
              </div>
              <template #footer>
                <div class="flex justify-between items-center">
                  <button class="btn btn-primary" :disabled="!comparisonProxies.length" @click="selectBestProxy">
                    选择最优
                  </button>
                  <button class="btn btn-secondary" @click="comparisonDialogVisible = false">关闭</button>
                </div>
              </template>
            </el-dialog>

            <!-- Import Dialog -->
            <el-dialog v-model="importDialogVisible" title="导入代理" width="min(800px, 95vw)" append-to-body @close="importDialogVisible = false">
              <div class="import-dialog">
                <!-- Input Mode Tabs -->
                <div class="import-tabs" style="margin-bottom: 12px;">
                  <button class="btn btn-sm" :class="importInputMode === 'file' ? 'btn-primary' : 'btn-ghost'" @click="importInputMode = 'file'">文件导入</button>
                  <button class="btn btn-sm" :class="importInputMode === 'text' ? 'btn-primary' : 'btn-ghost'" @click="importInputMode = 'text'">文本粘贴</button>
                </div>

                <!-- File Drop Zone -->
                <div v-if="importInputMode === 'file'" class="import-drop-zone" :class="{ 'drag-over': importIsDragOver, processing: importIsProcessing }"
                  @dragover="onImportDragOver" @dragleave="onImportDragLeave" @drop="onImportDrop">
                  <div class="import-drop-icon">&#128194;</div>
                  <div class="import-drop-text">
                    <span v-if="importIsProcessing">处理中...</span>
                    <span v-else>拖拽文件到这里，或 <label class="import-file-label" for="import-file-input">点击选择文件</label></span>
                  </div>
                  <div class="import-drop-hint">支持 .txt, .yaml, .yml, .conf, .json, .log 格式</div>
                  <input ref="importFileInput" id="import-file-input" type="file" class="hidden" multiple accept=".txt,.yaml,.yml,.conf,.json,.log" @change="onImportFileSelect" />
                </div>

                <!-- Text Input -->
                <div v-if="importInputMode === 'text'" class="import-text-area">
                  <div class="import-text-header">
                    <span class="text-muted text-xs">每行一个代理，支持 vmess://, ss://, trojan://, http://, socks5:// 等格式</span>
                    <button class="btn btn-xs btn-secondary" :disabled="importIsProcessing" @click="onImportPasteFromClipboard">
                      {{ importIsProcessing ? '处理中...' : '从剪贴板粘贴' }}
                    </button>
                  </div>
                  <textarea v-model="importTextInput" class="textarea import-textarea" placeholder="vmess://xxx&#10;ss://xxx&#10;trojan://xxx&#10;http://host:port" rows="8" @input="previewImportText(importTextInput)"></textarea>
                </div>

                <!-- Format Detection -->
                <div v-if="importPreviewFormat" class="import-format-badge" style="margin-bottom: 12px;">
                  <span class="badge badge-sm" :class="importPreviewFormat === 'text' ? 'badge-success' : importPreviewFormat === 'base64' ? 'badge-warning' : 'badge-info'">
                    {{ importPreviewFormat === 'base64' ? 'Base64 编码' : importPreviewFormat === 'url' ? '订阅链接' : '明文文本' }}
                  </span>
                  <span class="text-muted text-xs" style="margin-left: 8px;">自动检测格式</span>
                </div>

                <!-- Preview Stats -->
                <div v-if="importPreviewStats.total > 0" class="import-stats" style="margin-bottom: 12px;">
                  <div class="status-bar" style="margin: 0; background: var(--bg-secondary); border-radius: 6px; padding: 8px 12px;">
                    <div class="status-item">
                      <span class="text-muted">总计</span>
                      <strong>{{ importPreviewStats.total }}</strong>
                    </div>
                    <div class="status-item">
                      <span class="text-muted">有效</span>
                      <strong style="color: var(--success-text);">{{ importPreviewStats.new }}</strong>
                    </div>
                    <div class="status-item">
                      <span class="text-muted">无效</span>
                      <strong :style="{ color: importPreviewStats.invalid > 0 ? 'var(--danger-text)' : '' }">{{ importPreviewStats.invalid }}</strong>
                    </div>
                  </div>
                </div>

                <!-- Preview Table -->
                <div v-if="importPreviewData.length > 0" class="import-preview" style="margin-bottom: 12px;">
                  <div class="text-xs font-semibold text-gray-700" style="margin-bottom: 6px;">预览（前 {{ Math.min(100, importPreviewData.length) }} 条）</div>
                  <div class="table-wrap" style="max-height: 200px; overflow-y: auto;">
                    <table class="data-table data-table-sm">
                      <thead>
                        <tr>
                          <th style="width: 60px;">状态</th>
                          <th>代理内容</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(item, idx) in importPreviewData" :key="'preview-' + idx" :class="{ 'row-invalid': !item.valid && !item.isMore }">
                          <td>
                            <span v-if="item.isMore" class="text-muted text-xs">...</span>
                            <span v-else-if="item.valid" class="badge badge-sm badge-success">&#10003;</span>
                            <span v-else class="badge badge-sm badge-danger">&#10007;</span>
                          </td>
                          <td class="mono text-xs text-muted">{{ item.line }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <template #footer>
                <div class="flex justify-between">
                  <button class="btn btn-ghost" @click="importDialogVisible = false">取消</button>
                  <div class="flex gap-2">
                    <button class="btn btn-secondary" :disabled="!importPreviewStats.total || importIsProcessing" @click="previewImportText(importTextInput)">
                      刷新预览
                    </button>
                    <button class="btn btn-primary" :disabled="!importPreviewStats.total || importIsProcessing" @click="executeImport">
                      {{ importIsProcessing ? '导入中...' : '确认导入' }}
                    </button>
                  </div>
                </div>
              </template>
            </el-dialog>

            <!-- Export Dialog -->
            <el-dialog v-model="exportDialogVisible" title="导出代理" width="min(700px, 95vw)" append-to-body @close="exportDialogVisible = false">
              <div class="export-dialog">
                <!-- Export Scope -->
                <div class="form-group" style="margin-bottom: 16px;">
                  <label class="form-label">导出范围</label>
                  <div class="flex gap-2">
                    <button class="btn btn-sm" :class="exportScope === 'all' ? 'btn-primary' : 'btn-ghost'" @click="exportScope = 'all'; refreshExportPreview()">
                      全部代理 ({{ allProxyCount }})
                    </button>
                    <button class="btn btn-sm" :class="exportScope === 'selected' ? 'btn-primary' : 'btn-ghost'" @click="exportScope = 'selected'; refreshExportPreview()">
                      选中代理 ({{ selectedProxyKeys.length }})
                    </button>
                  </div>
                </div>

                <!-- Filter Options -->
                <div class="form-group" style="margin-bottom: 16px;">
                  <label class="form-check">
                    <input v-model="exportApplyFilters" type="checkbox" @change="refreshExportPreview" />
                    <span>仅导出当前筛选结果</span>
                  </label>
                  <span class="text-xs text-muted" style="margin-left: 24px;">
                    {{ exportApplyFilters ? '导出 ' + proxies.length + ' 个符合筛选条件的代理' : '导出所有代理' }}
                  </span>
                </div>

                <!-- Export Format -->
                <div class="form-group" style="margin-bottom: 16px;">
                  <label class="form-label">导出格式</label>
                  <div class="flex gap-2">
                    <button class="btn btn-sm" :class="exportFormat === 'csv' ? 'btn-primary' : 'btn-ghost'" @click="exportFormat = 'csv'">
                      CSV 表格
                    </button>
                    <button class="btn btn-sm" :class="exportFormat === 'json' ? 'btn-primary' : 'btn-ghost'" @click="exportFormat = 'json'">
                      JSON 数据
                    </button>
                    <button class="btn btn-sm" :class="exportFormat === 'links' ? 'btn-primary' : 'btn-ghost'" @click="exportFormat = 'links'">
                      代理链接
                    </button>
                  </div>
                </div>

                <!-- Format Description -->
                <div class="export-format-desc" style="margin-bottom: 16px; padding: 12px; background: var(--bg-secondary); border-radius: 6px;">
                  <div v-if="exportFormat === 'csv'" class="text-xs text-muted">
                    <strong>CSV 格式:</strong> 包含所有字段的表格格式，可用 Excel 打开。字段: Protocol, Host, Port, Available, Latency, Speed, Success Rate, Country, City, IP Purity, ChatGPT, Source, Last Checked
                  </div>
                  <div v-else-if="exportFormat === 'json'" class="text-xs text-muted">
                    <strong>JSON 格式:</strong> 结构化数据格式，适合程序处理。包含所有代理属性的 JSON 数组。
                  </div>
                  <div v-else class="text-xs text-muted">
                    <strong>链接格式:</strong> 纯文本代理链接，每行一个。格式: protocol://host:port
                  </div>
                </div>

                <!-- Preview Stats -->
                <div class="export-stats" style="margin-bottom: 16px;">
                  <div class="status-bar" style="margin: 0; background: var(--bg-secondary); border-radius: 6px; padding: 8px 12px;">
                    <div class="status-item">
                      <span class="text-muted">将导出</span>
                      <strong style="color: var(--accent);">{{ exportPreviewStats.total }}</strong>
                      <span class="text-muted">个代理</span>
                    </div>
                  </div>
                </div>

                <!-- Preview Table -->
                <div v-if="exportPreviewData.length > 0" class="export-preview">
                  <div class="text-xs font-semibold text-gray-700" style="margin-bottom: 6px;">预览（前 {{ Math.min(10, exportPreviewData.length) }} 条）</div>
                  <div class="table-wrap" style="max-height: 200px; overflow-y: auto;">
                    <table class="data-table data-table-sm">
                      <thead>
                        <tr>
                          <th>协议</th>
                          <th>地址</th>
                          <th>状态</th>
                          <th v-if="exportFormat === 'csv'">延迟</th>
                          <th v-if="exportFormat === 'csv'">成功率</th>
                          <th v-if="exportFormat === 'csv'">国家</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(proxy, idx) in exportPreviewData" :key="'export-preview-' + idx">
                          <td class="mono text-xs">{{ proxy.protocol }}</td>
                          <td class="mono text-xs">{{ proxy.host }}:{{ proxy.port }}</td>
                          <td>
                            <span class="badge badge-sm" :class="proxy.available ? 'badge-success' : 'badge-danger'">
                              {{ proxy.available ? 'UP' : 'DOWN' }}
                            </span>
                          </td>
                          <td v-if="exportFormat === 'csv'" class="text-xs">{{ proxy.latency_ms ? proxy.latency_ms + 'ms' : '-' }}</td>
                          <td v-if="exportFormat === 'csv'" class="text-xs">{{ proxy.success_rate != null ? proxy.success_rate.toFixed(1) + '%' : '-' }}</td>
                          <td v-if="exportFormat === 'csv'" class="text-xs">{{ proxy.country || '-' }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <template #footer>
                <div class="flex justify-between">
                  <button class="btn btn-ghost" @click="exportDialogVisible = false">取消</button>
                  <div class="flex gap-2">
                    <button class="btn btn-secondary" :disabled="!exportPreviewStats.total || exportIsProcessing" @click="refreshExportPreview">
                      刷新预览
                    </button>
                    <button class="btn btn-primary" :disabled="!exportPreviewStats.total || exportIsProcessing" @click="executeExport">
                      {{ exportIsProcessing ? '导出中...' : '导出文件' }}
                    </button>
                  </div>
                </div>
              </template>
            </el-dialog>
</template>

<script>
import { rootProxyMixin } from "../rootProxyMixin";
import Breadcrumb from '../components/layout/Breadcrumb.vue';
import LoadingState from '../components/common/LoadingState.vue';
import ErrorState from '../components/common/ErrorState.vue';

export default {
  name: "ProxiesPage",
  components: {
    Breadcrumb,
    LoadingState,
    ErrorState,
  },
  mixins: [rootProxyMixin],
  data() {
    return {
      proxySortKey: '',
      proxySortDir: 'asc',
      expandedProxyKeys: [],
      loadError: null,
      isLoading: false,
      isLoadingSkeleton: false,
      advancedFilterOpen: false,
      filterPresetName: '',
      // Tags & Favorites
      proxyTags: JSON.parse(localStorage.getItem('proxypool-proxy-tags') || '{}'),
      proxyFavorites: JSON.parse(localStorage.getItem('proxypool-proxy-favorites') || '[]'),
      addTagDialogVisible: false,
      addTagTargetKey: '',
      newTagName: '',
      commonTags: ['重要', '高速', '稳定', '备用', '测试', '日本', '美国', '香港'],
      // Comparison
      comparisonDialogVisible: false,
      comparisonProxies: [],
      radarColors: ['#3b82f6', '#ef4444', '#10b981', '#f59e0b'],
      // Quick test inline results
      inlineTestResults: {},
      // Test history
      testHistory: JSON.parse(localStorage.getItem('proxypool-proxy-test-history') || '{}'),
      // Advanced features expanded state
      advancedFeaturesExpanded: {},
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
      let list = this.appState.proxies || [];
      // Client-side filtering for latency_max and score_min
      const f = this.appState.proxyFilters || {};
      const latencyMax = Number(f.latency_max);
      if (latencyMax > 0) {
        list = list.filter(p => p.latency_ms != null && p.latency_ms <= latencyMax);
      }
      const scoreMin = Number(f.score_min);
      if (scoreMin > 0) {
        list = list.filter(p => (p.final_score ?? p.score ?? 0) >= scoreMin);
      }
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
    activeFilterChips() {
      const f = this.appState.proxyFilters || {};
      const chips = [];
      if (f.protocol) chips.push({ key: 'protocol', label: '协议', value: f.protocol });
      if (f.available) chips.push({ key: 'available', label: '状态', value: f.available === 'true' ? '可用' : '不可用' });
      if (f.score_min) chips.push({ key: 'score_min', label: '最低分数', value: `${f.score_min}` });
      if (f.latency_max) chips.push({ key: 'latency_max', label: '最大延迟', value: `${f.latency_max}ms` });
      if (f.speed_min_mbps) chips.push({ key: 'speed_min_mbps', label: '带宽', value: `> ${f.speed_min_mbps} Mbps` });
      if (f.geo_country) chips.push({ key: 'geo_country', label: '国家', value: f.geo_country });
      if (f.geo_location) chips.push({ key: 'geo_location', label: '城市', value: f.geo_location });
      if (f.ip_purity) chips.push({ key: 'ip_purity', label: '纯净度', value: f.ip_purity });
      if (f.openai) chips.push({ key: 'openai', label: 'ChatGPT', value: f.openai });
      if (f.fallback_front) chips.push({ key: 'fallback_front', label: '前置', value: f.fallback_front });
      if (f.source) chips.push({ key: 'source', label: '来源', value: f.source });
      return chips;
    },
    scoreMinValue: {
      get() { return Number(this.appState.proxyFilters?.score_min) || 0; },
      set(v) { this.appState.proxyFilters.score_min = v > 0 ? String(v) : ''; },
    },
    latencyMaxValue: {
      get() { return Number(this.appState.proxyFilters?.latency_max) || 0; },
      set(v) { this.appState.proxyFilters.latency_max = v > 0 ? String(v) : ''; },
    },
    protocolDistributionData() {
      const proxies = this.appState.proxies || [];
      if (!proxies.length) return null;
      const protocolCounts = {};
      proxies.forEach(p => {
        const protocol = p.protocol || 'unknown';
        protocolCounts[protocol] = (protocolCounts[protocol] || 0) + 1;
      });
      const total = proxies.length;
      const colors = ['#4b5058', '#6366f1', '#0891b2', '#16a34a', '#ca8a04', '#dc2626', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];
      return Object.entries(protocolCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([name, count], idx) => ({
          name,
          count,
          pct: Math.round((count / total) * 100),
          color: colors[idx % colors.length],
        }));
    },
    protocolDonutSegments() {
      const entries = this.protocolDistributionData || [];
      const total = entries.reduce((s, e) => s + e.count, 0);
      if (!total) return [];
      const circumference = 2 * Math.PI * 45;
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
  },
  methods: {
    async handleLoadData() {
      this.loadError = null;
      this.isLoadingSkeleton = true;
      this.isLoading = true;
      try {
        await this.loadData();
      } catch (e) {
        this.loadError = e.message || '加载代理数据失败';
      } finally {
        this.isLoading = false;
        setTimeout(() => {
          this.isLoadingSkeleton = false;
        }, 300);
      }
    },
    // Debounced filter method for text inputs
    debounceFilter(key, value, delay = 300) {
      if (this._debounceTimers && this._debounceTimers[key]) {
        clearTimeout(this._debounceTimers[key]);
      }
      if (!this._debounceTimers) this._debounceTimers = {};
      this._debounceTimers[key] = setTimeout(() => {
        this.appState.proxyFilters[key] = value;
      }, delay);
    },
    toggleExpandProxy(key) {
      const idx = this.expandedProxyKeys.indexOf(key);
      if (idx >= 0) {
        this.expandedProxyKeys.splice(idx, 1);
      } else {
        this.expandedProxyKeys.push(key);
      }
    },
    isProxyExpanded(key) {
      return this.expandedProxyKeys.includes(key);
    },
    getColumnTooltip(key) {
      const tooltips = {
        latency: '节点响应延迟，单位毫秒（ms），越低越好',
        bandwidth: '节点下载带宽，单位 Mbps，仅对直连节点有效',
        success_rate: '节点连接成功率，基于历史测试数据统计',
        fail_count: '连续失败次数。超过阈值（默认5次）节点将被标记为不可用。熔断器状态：关闭=正常，打开=隔离中，半开=恢复测试中',
        geo: '节点出口 IP 的地理位置，通过 IP 地理位置数据库查询',
        purity: 'IP 纯净度，家宽 IP 通常更稳定，非家宽 IP 可能是机房或代理',
        unlock: 'ChatGPT 解锁状态，表示节点是否可以访问 OpenAI 服务',
        fallback_front: '节点是否需要前置代理才能连通（链式代理）',
        source: '节点来源，通常为订阅链接名称',
        last_error: '最近一次测试失败的错误信息，可用于定位问题',
        score: '综合评分 = 成功率(40%) + 延迟(30%) + 纯净度(20%) + 稳定性(10%)',
      };
      return tooltips[key] || '';
    },
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
      if (ms < 200) return { color: '#16a34a', fontWeight: 600 };
      if (ms < 500) return { color: '#ca8a04', fontWeight: 600 };
      return { color: '#dc2626', fontWeight: 600 };
    },
    bandwidthStyle(mbps) {
      if (!mbps || mbps <= 0) return {};
      if (mbps >= 50) return { color: '#16a34a' };
      if (mbps >= 10) return { color: '#ca8a04' };
      return { color: '#dc2626' };
    },
    formatSuccessRate(item) {
      const rate = item.success_rate;
      if (rate === null || rate === undefined) return '-';
      return rate.toFixed(1) + '%';
    },
    successRateStyle(rate) {
      if (rate === null || rate === undefined) return {};
      if (rate >= 80) return { color: '#16a34a', fontWeight: 600 };
      if (rate >= 50) return { color: '#ca8a04', fontWeight: 600 };
      return { color: '#dc2626', fontWeight: 600 };
    },
    failCountStyle(count) {
      const num = count ?? 0;
      if (num === 0) return { color: '#16a34a' };
      if (num < 3) return { color: '#ca8a04' };
      return { color: '#dc2626' };
    },
    formatRelativeTime(ts) {
      if (!ts) return '未检测';
      try {
        const date = new Date(ts);
        const now = new Date();
        const diffMs = now - date;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);

        if (diffMin < 1) return '刚刚';
        if (diffMin < 60) return `${diffMin}分钟前`;
        if (diffHour < 24) return `${diffHour}小时前`;
        if (diffDay < 7) return `${diffDay}天前`;
        return this.formatTime(ts);
      } catch {
        return this.formatTime(ts);
      }
    },
    formatFailStage(error) {
      if (!error) return '';
      const lower = error.toLowerCase();
      if (lower.includes('dns') || lower.includes('resolve')) return 'DNS解析失败';
      if (lower.includes('tcp') || lower.includes('connect') || lower.includes('timeout')) return 'TCP连接失败';
      if (lower.includes('tls') || lower.includes('ssl') || lower.includes('certificate')) return 'TLS握手失败';
      if (lower.includes('401') || lower.includes('403') || lower.includes('auth')) return '认证失败';
      if (lower.includes('refused') || lower.includes('reset')) return '连接被拒绝';
      return '';
    },
    getFailAdvice(error) {
      if (!error) return '';
      const lower = error.toLowerCase();
      if (lower.includes('dns') || lower.includes('resolve')) return '建议：检查DNS配置或使用公共DNS（8.8.8.8）';
      if (lower.includes('timeout')) return '建议：代理服务器可能不可达，检查服务器状态或增加超时时间';
      if (lower.includes('tls') || lower.includes('ssl') || lower.includes('certificate')) return '建议：证书问题，可能是SNI不匹配或证书已过期';
      if (lower.includes('401') || lower.includes('403') || lower.includes('auth')) return '建议：检查用户名和密码配置是否正确';
      if (lower.includes('refused') || lower.includes('reset')) return '建议：代理服务未启动或端口被防火墙阻止';
      return '';
    },
    removeFilterChip(key) {
      this.appState.proxyFilters[key] = '';
      this.appState.updateUrlWithFilters();
    },
    saveCurrentFilterPreset() {
      const name = (this.filterPresetName || '').trim();
      if (!name) return;
      this.appState.saveFilterPreset(name);
      this.filterPresetName = '';
    },
    onFilterPresetChange(name) {
      if (name) {
        this.appState.loadFilterPreset(name);
      }
    },
    deleteCurrentFilterPreset() {
      if (this.appState.activeFilterPreset) {
        this.appState.deleteFilterPreset(this.appState.activeFilterPreset);
      }
    },
    // Favorites
    isFavorite(key) {
      return this.proxyFavorites.includes(key);
    },
    toggleFavorite(key) {
      const idx = this.proxyFavorites.indexOf(key);
      if (idx >= 0) {
        this.proxyFavorites.splice(idx, 1);
      } else {
        this.proxyFavorites.push(key);
      }
      localStorage.setItem('proxypool-proxy-favorites', JSON.stringify(this.proxyFavorites));
    },
    // Tags
    getProxyTags(key) {
      return this.proxyTags[key] || [];
    },
    showAddTagDialog(key) {
      this.addTagTargetKey = key;
      this.newTagName = '';
      this.addTagDialogVisible = true;
    },
    addProxyTag() {
      const tag = this.newTagName.trim();
      if (!tag || !this.addTagTargetKey) return;
      if (!this.proxyTags[this.addTagTargetKey]) {
        this.proxyTags[this.addTagTargetKey] = [];
      }
      if (!this.proxyTags[this.addTagTargetKey].includes(tag)) {
        this.proxyTags[this.addTagTargetKey].push(tag);
        localStorage.setItem('proxypool-proxy-tags', JSON.stringify(this.proxyTags));
      }
      this.addTagDialogVisible = false;
      this.newTagName = '';
    },
    removeProxyTag(key, tag) {
      if (this.proxyTags[key]) {
        this.proxyTags[key] = this.proxyTags[key].filter(t => t !== tag);
        if (this.proxyTags[key].length === 0) {
          delete this.proxyTags[key];
        }
        localStorage.setItem('proxypool-proxy-tags', JSON.stringify(this.proxyTags));
      }
    },
    // Comparison
    showComparisonView() {
      const allProxies = this.appState.proxies || [];
      this.comparisonProxies = this.selectedProxyKeys
        .map(key => allProxies.find(p => p.normalized_key === key))
        .filter(Boolean)
        .slice(0, 3);
      this.comparisonDialogVisible = true;
    },

    // Comparison - Best value detection
    computeCompositeScore(proxy) {
      const available = proxy.available ? 1 : 0;
      const latency = proxy.latency_ms || 9999;
      const latencyScore = latency < 100 ? 100 : latency < 300 ? 70 : latency < 500 ? 40 : 10;
      const bandwidth = proxy.speed_mbps || 0;
      const bandwidthScore = bandwidth >= 100 ? 100 : bandwidth >= 50 ? 80 : bandwidth >= 10 ? 50 : 10;
      const successRate = proxy.success_rate || 0;
      const successScore = successRate >= 90 ? 100 : successRate >= 70 ? 70 : successRate >= 50 ? 40 : 10;
      const unlockScore = proxy.openai_unlocked === true ? 100 : 0;
      return available * 30 + latencyScore * 0.25 + bandwidthScore * 0.2 + successScore * 0.15 + unlockScore * 0.1;
    },

    isBestLatency(proxy) {
      if (!this.comparisonProxies.length) return false;
      const best = Math.min(...this.comparisonProxies.map(p => p.latency_ms || 9999));
      return proxy.latency_ms === best && proxy.latency_ms;
    },

    isBestBandwidth(proxy) {
      if (!this.comparisonProxies.length) return false;
      const best = Math.max(...this.comparisonProxies.map(p => p.speed_mbps || 0));
      return proxy.speed_mbps === best && proxy.speed_mbps > 0;
    },

    isBestSuccessRate(proxy) {
      if (!this.comparisonProxies.length) return false;
      const best = Math.max(...this.comparisonProxies.map(p => p.success_rate || 0));
      return proxy.success_rate === best && proxy.success_rate > 0;
    },

    isBestAvailable(proxy) {
      return proxy.available && this.comparisonProxies.some(p => !p.available);
    },

    isBestUnlock(proxy) {
      return proxy.openai_unlocked === true && this.comparisonProxies.some(p => p.openai_unlocked !== true);
    },

    isBestCompositeScore(proxy) {
      if (!this.comparisonProxies.length) return false;
      const best = Math.max(...this.comparisonProxies.map(p => this.computeCompositeScore(p)));
      return this.computeCompositeScore(proxy) === best;
    },

    selectBestProxy() {
      if (!this.comparisonProxies.length) return;
      const scored = this.comparisonProxies.map(p => ({
        proxy: p,
        score: this.computeCompositeScore(p),
      }));
      scored.sort((a, b) => b.score - a.score);
      const best = scored[0].proxy;
      this.selectedProxyKeys = [best.normalized_key];
      this.comparisonDialogVisible = false;
      this.setMessage(`已选择最优代理: #${this.getSerial(best.normalized_key)} ${best.protocol}://${best.host}:${best.port}`);
    },

    drawRadarChart() {
      this.$nextTick(() => {
        const canvas = this.$refs.radarChart;
        if (!canvas || !this.comparisonProxies.length) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) * 0.35;

        ctx.clearRect(0, 0, width, height);

        const dimensions = ['延迟', '带宽', '成功率', '状态', 'ChatGPT'];
        const numAxes = dimensions.length;
        const angleStep = (Math.PI * 2) / numAxes;
        const startAngle = -Math.PI / 2;

        // Draw grid
        ctx.strokeStyle = '#e5e7eb';
        ctx.lineWidth = 1;
        for (let level = 1; level <= 4; level++) {
          const r = (radius * level) / 4;
          ctx.beginPath();
          for (let i = 0; i <= numAxes; i++) {
            const angle = startAngle + i * angleStep;
            const x = centerX + r * Math.cos(angle);
            const y = centerY + r * Math.sin(angle);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.stroke();
        }

        // Draw axes and labels
        ctx.fillStyle = '#374151';
        ctx.font = '11px system-ui';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        for (let i = 0; i < numAxes; i++) {
          const angle = startAngle + i * angleStep;
          const x = centerX + radius * Math.cos(angle);
          const y = centerY + radius * Math.sin(angle);
          ctx.beginPath();
          ctx.moveTo(centerX, centerY);
          ctx.lineTo(x, y);
          ctx.stroke();

          const labelX = centerX + (radius + 20) * Math.cos(angle);
          const labelY = centerY + (radius + 20) * Math.sin(angle);
          ctx.fillText(dimensions[i], labelX, labelY);
        }

        // Draw data for each proxy
        this.comparisonProxies.forEach((proxy, idx) => {
          const color = this.radarColors[idx];
          ctx.strokeStyle = color;
          ctx.fillStyle = color + '33';
          ctx.lineWidth = 2;

          const values = [
            proxy.latency_ms ? Math.max(0, 100 - proxy.latency_ms / 10) : 50,
            proxy.speed_mbps ? Math.min(100, proxy.speed_mbps) : 0,
            proxy.success_rate || 0,
            proxy.available ? 100 : 0,
            proxy.openai_unlocked ? 100 : 0,
          ];

          ctx.beginPath();
          values.forEach((value, i) => {
            const angle = startAngle + i * angleStep;
            const r = (radius * value) / 100;
            const x = centerX + r * Math.cos(angle);
            const y = centerY + r * Math.sin(angle);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.closePath();
          ctx.fill();
          ctx.stroke();

          // Draw data points
          values.forEach((value, i) => {
            const angle = startAngle + i * angleStep;
            const r = (radius * value) / 100;
            const x = centerX + r * Math.cos(angle);
            const y = centerY + r * Math.sin(angle);
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
          });
        });
      });
    },
    // Quick test with inline result
    async quickTestProxy(item) {
      const key = item.normalized_key;
      await this.runWithButtonState(`quickTest-${key}`, async () => {
        try {
          const normalizedKey = String(key || '').trim();
          if (!normalizedKey) throw new Error('节点标识缺失');
          const fallbackKeys = this.resolveFallbackFrontProxyKeys(this.testFallback.front_proxy_refs);
          const maxAttempts = Math.max(0, Math.min(100, Math.trunc(Number(this.testFallback.max_attempts || 0))));
          const resp = await fetch('/api/tester/run-one', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              normalized_key: normalizedKey,
              fallback_front_proxy_keys: fallbackKeys,
              fallback_front_max_attempts: maxAttempts,
            }),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || '测试失败');
          const result = {
            available: !!data.available,
            latency_ms: Number.isFinite(Number(data.latency_ms)) ? Number(data.latency_ms) : null,
            timestamp: new Date().toISOString(),
          };
          this.inlineTestResults = { ...this.inlineTestResults, [key]: result };
          this.saveProxyTestHistory(key, result);
          await this.loadData();
          await this.loadProxyCatalog();
        } catch (err) {
          const failResult = {
            available: false,
            latency_ms: null,
            timestamp: new Date().toISOString(),
            error: String(err?.message || err || '测试失败'),
          };
          this.inlineTestResults = { ...this.inlineTestResults, [key]: failResult };
          this.saveProxyTestHistory(key, failResult);
          this.setMessage('快速测试失败: ' + err, true);
        }
      });
    },
    // Test history
    getProxyTestHistory(key) {
      return (this.testHistory[key] || []).slice(0, 10);
    },
    saveProxyTestHistory(key, result) {
      const history = Array.isArray(this.testHistory[key]) ? [...this.testHistory[key]] : [];
      history.unshift({
        available: result.available,
        latency_ms: result.latency_ms,
        timestamp: result.timestamp,
        error: result.error || null,
      });
      this.testHistory[key] = history.slice(0, 10);
      try {
        localStorage.setItem('proxypool-proxy-test-history', JSON.stringify(this.testHistory));
      } catch {}
    },
    getProxyLatencyTrend(key) {
      const history = this.testHistory[key] || [];
      const latencyPoints = history
        .filter(h => h.latency_ms != null)
        .slice(0, 10)
        .reverse();
      if (latencyPoints.length < 2) return null;
      const maxLatency = Math.max(...latencyPoints.map(p => p.latency_ms), 1);
      const width = 120;
      const height = 40;
      const padding = 4;
      const points = latencyPoints.map((p, i) => ({
        x: padding + (i / (latencyPoints.length - 1)) * (width - 2 * padding),
        y: padding + (1 - p.latency_ms / maxLatency) * (height - 2 * padding),
        latency: p.latency_ms,
      }));
      const pathData = points.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`).join(' ');
      return { pathData, points, maxLatency, width, height };
    },
    getProxySuccessTrend(key) {
      const history = this.testHistory[key] || [];
      if (history.length === 0) return null;
      const recent = history.slice(0, 10);
      const dots = recent.map(h => h.available);
      const passCount = dots.filter(d => d).length;
      const rate = Math.round((passCount / dots.length) * 100);
      let trend = 'stable';
      if (dots.length >= 4) {
        const half = Math.floor(dots.length / 2);
        const firstHalf = dots.slice(0, half);
        const secondHalf = dots.slice(half);
        const firstPassRate = firstHalf.filter(d => d).length / firstHalf.length;
        const secondPassRate = secondHalf.filter(d => d).length / secondHalf.length;
        if (secondPassRate > firstPassRate + 0.1) trend = 'up';
        else if (secondPassRate < firstPassRate - 0.1) trend = 'down';
      }
      return { dots, rate, trend };
    },
    getProxyReliabilityScore(key) {
      const history = this.testHistory[key] || [];
      if (history.length === 0) return null;
      const last20 = history.slice(0, 20);
      const passCount = last20.filter(h => h.available).length;
      return Math.round((passCount / last20.length) * 100);
    },
    // Advanced features
    toggleAdvancedFeature(key, feature) {
      const featureKey = `${key}--${feature}`;
      this.advancedFeaturesExpanded = {
        ...this.advancedFeaturesExpanded,
        [featureKey]: !this.advancedFeaturesExpanded[featureKey],
      };
    },
    isAdvancedFeatureExpanded(key, feature) {
      return !!this.advancedFeaturesExpanded[`${key}--${feature}`];
    },
    getProxyHealthTimeline(key) {
      const history = this.testHistory[key] || [];
      return history.slice(0, 10).map(h => ({
        timestamp: h.timestamp,
        status: h.available ? 'up' : 'down',
        latency: h.latency_ms,
      }));
    },
    getProxyBenchmarkScore(item, type) {
      if (type === 'latency') {
        const ms = item.latency_ms || 9999;
        if (ms < 50) return 100;
        if (ms < 100) return 90;
        if (ms < 200) return 75;
        if (ms < 500) return 50;
        if (ms < 1000) return 25;
        return 10;
      }
      if (type === 'bandwidth') {
        const mbps = item.speed_mbps || 0;
        if (mbps >= 100) return 100;
        if (mbps >= 50) return 85;
        if (mbps >= 20) return 70;
        if (mbps >= 10) return 50;
        if (mbps >= 1) return 25;
        return 10;
      }
      if (type === 'stability') {
        const score = this.getProxyReliabilityScore(item.normalized_key);
        return score != null ? score : 50;
      }
      if (type === 'overall') {
        const lat = this.getProxyBenchmarkScore(item, 'latency');
        const bw = this.getProxyBenchmarkScore(item, 'bandwidth');
        const stab = this.getProxyBenchmarkScore(item, 'stability');
        return Math.round(lat * 0.35 + bw * 0.25 + stab * 0.4);
      }
      return 50;
    },
    getGeoRoutingSuggestion(item) {
      const country = item.geo_country || '';
      const latency = item.latency_ms || 0;
      if (latency < 100) return '本地直连，延迟极低，适合实时应用';
      if (latency < 300) {
        if (['US', 'JP', 'HK', 'SG', 'TW'].includes(country)) {
          return '跨区域连接，适合一般网页浏览';
        }
        return '中等延迟，适合非实时数据传输';
      }
      if (latency < 500) return '高延迟连接，建议选择更近的节点';
      return '延迟过高，建议切换区域或检查网络';
    },
    getGeoLatencyDistance(item) {
      const latency = item.latency_ms || 0;
      if (latency < 50) return '同区域 (<50ms)';
      if (latency < 100) return '近区域 (50-100ms)';
      if (latency < 200) return '跨区域 (100-200ms)';
      if (latency < 500) return '跨国连接 (200-500ms)';
      return '远距离 (>500ms)';
    },
    getProtocolOptimizations(item) {
      const suggestions = [];
      const protocol = (item.protocol || '').toLowerCase();
      const latency = item.latency_ms || 0;
      const mbps = item.speed_mbps || 0;
      if (protocol === 'vmess' && latency > 300) {
        suggestions.push({ severity: 'high', suggestion: 'VMess 协议延迟较高，考虑切换到 VLESS 或 Trojan 以获得更低延迟' });
      }
      if (protocol === 'ss' && mbps < 10) {
        suggestions.push({ severity: 'medium', suggestion: 'Shadowsocks 带宽较低，建议检查服务端配置或切换协议' });
      }
      if (protocol === 'http' || protocol === 'https') {
        suggestions.push({ severity: 'low', suggestion: 'HTTP(S) 代理不支持 UDP，如需完整网络功能建议使用 SOCKS5 或 VMess' });
      }
      if (!item.openai_unlocked && item.geo_country === 'US') {
        suggestions.push({ severity: 'medium', suggestion: '美国节点未解锁 ChatGPT，可能是数据中心 IP 被封锁' });
      }
      if (item.fail_count > 2) {
        suggestions.push({ severity: 'high', suggestion: `连续失败 ${item.fail_count} 次，建议检查节点状态或将其标记为不可用` });
      }
      return suggestions;
    },
    getProxyLoad(item) {
      const failCount = item.fail_count || 0;
      const latency = item.latency_ms || 0;
      const load = Math.min(100, Math.round(failCount * 15 + latency / 50));
      return Math.max(5, load);
    },
    getProxyRecommendedWeight(item) {
      if (!item.available) return 0;
      const score = this.getProxyBenchmarkScore(item, 'overall');
      return Math.round(score / 10);
    },
    getProxyUseCase(item) {
      const latency = item.latency_ms || 0;
      const mbps = item.speed_mbps || 0;
      const unlock = item.openai_unlocked;
      if (latency < 50 && mbps >= 50) return '游戏/视频/下载 (全场景)';
      if (latency < 100) return '网页浏览/流媒体';
      if (latency < 300 && mbps >= 20) return '大文件下载/在线视频';
      if (unlock) return 'AI 服务/内容解锁';
      if (latency < 500) return '轻量浏览/邮件收发';
      return '备用/低频访问';
    },
  },
  mounted() {
    // Initialize virtual scrolling if needed
    if (this.virtualScrollEnabled) {
      this.$nextTick(() => {
        const tableWrap = this.$el.querySelector('.table-wrap');
        if (tableWrap) {
          this.initVirtualScroll(tableWrap);
        }
      });
    }
    // Setup lazy loading for images
    this.setupLazyLoading();
  },
  unmounted() {
    this.destroyVirtualScroll();
  },
  watch: {
    virtualScrollEnabled(newVal) {
      if (newVal) {
        this.$nextTick(() => {
          const tableWrap = this.$el.querySelector('.table-wrap');
          if (tableWrap) {
            this.initVirtualScroll(tableWrap);
          }
        });
      } else {
        this.destroyVirtualScroll();
      }
    },
  },
};
</script>

<style scoped>
.help-icon {
  display: inline-block;
  width: 12px;
  height: 12px;
  line-height: 12px;
  text-align: center;
  font-size: 10px;
  font-weight: 600;
  color: var(--muted);
  background: var(--bg-secondary);
  border-radius: 50%;
  margin-left: 4px;
  cursor: help;
}

.help-icon:hover {
  background: var(--accent);
  color: white;
}

.proxy-detail-row td {
  border-top: 1px solid var(--line);
}

.proxy-detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.proxy-detail-section {
  background: var(--bg-primary);
  padding: 12px;
  border-radius: 6px;
  border: 1px solid var(--line);
}

.proxy-detail-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--line);
}

.proxy-detail-item {
  font-size: 12px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.proxy-detail-item .text-muted {
  color: var(--muted);
}

/* Tags & Favorites */
.favorite-btn {
  color: var(--warning, #f59e0b);
}

.favorite-btn:hover {
  color: var(--warning-hover, #d97706);
}

.favorite-btn-row {
  font-size: 14px;
  line-height: 1;
  padding: 2px 4px;
  color: var(--muted);
  transition: color 0.15s;
}

.favorite-btn-row:hover {
  color: var(--warning, #f59e0b);
}

/* Quick test */
.quick-test-btn {
  font-size: 13px;
  padding: 2px 5px;
}

.inline-test-result {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 3px;
  font-size: 10px;
  font-weight: 600;
}

.inline-test-up {
  color: #16a34a;
}

.inline-test-down {
  color: #dc2626;
}

.inline-test-latency {
  font-family: monospace;
}

.inline-test-status {
  font-weight: 700;
}

/* Test history */
.proxy-detail-section-full {
  grid-column: 1 / -1;
}

.test-history-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.test-history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.test-history-up {
  background: rgba(22, 163, 74, 0.06);
}

.test-history-down {
  background: rgba(220, 38, 38, 0.06);
}

.test-history-time {
  color: var(--muted);
  min-width: 80px;
}

.test-history-status {
  font-weight: 700;
  min-width: 36px;
}

.test-history-latency {
  font-family: monospace;
  color: var(--text-secondary);
  min-width: 56px;
}

.test-history-error {
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.proxy-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.proxy-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--accent-light, rgba(59, 130, 246, 0.1));
  color: var(--accent, #3b82f6);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.tag-remove {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  padding: 0;
  font-size: 12px;
  line-height: 1;
}

.tag-remove:hover {
  color: var(--danger, #dc2626);
}

/* Tag Dialog */
.tag-dialog-content {
  padding: 8px 0;
}

.tag-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
  align-items: center;
}

/* Comparison View */
.comparison-content {
  overflow-x: auto;
}

.comparison-grid {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: hidden;
}

.comparison-header,
.comparison-row {
  display: grid;
  grid-template-columns: 120px repeat(3, 1fr);
  gap: 1px;
  background: var(--bg-primary);
}

.comparison-header {
  background: var(--bg-secondary);
  font-weight: 600;
}

.comparison-label {
  padding: 10px 12px;
  font-size: 12px;
  color: var(--muted);
  background: var(--bg-secondary);
}

.comparison-value {
  padding: 10px 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.comparison-header .comparison-value {
  font-weight: 600;
  color: var(--ink);
}

.comparison-value.best-value {
  background: rgba(16, 185, 129, 0.15);
  border-left: 3px solid #10b981;
}

.radar-chart-container {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 16px;
}

.radar-legend {
  display: flex;
  gap: 16px;
  justify-content: center;
  flex-wrap: wrap;
}

.radar-legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.radar-legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

@media (max-width: 768px) {
  .comparison-header,
  .comparison-row {
    grid-template-columns: 80px repeat(3, 1fr);
  }

  .comparison-label,
  .comparison-value {
    padding: 8px;
    font-size: 11px;
  }
}

/* Import Dialog Styles */
.import-dialog {
  min-height: 200px;
}

.import-tabs {
  display: flex;
  gap: 4px;
}

.import-drop-zone {
  border: 2px dashed var(--line-soft);
  border-radius: 8px;
  padding: 32px;
  text-align: center;
  transition: all 0.2s ease;
  background: var(--bg-secondary);
  cursor: pointer;
}

.import-drop-zone:hover,
.import-drop-zone.drag-over {
  border-color: var(--accent);
  background: var(--accent-bg);
}

.import-drop-zone.processing {
  opacity: 0.6;
  pointer-events: none;
}

.import-drop-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.import-drop-text {
  font-size: 14px;
  color: var(--ink);
  margin-bottom: 4px;
}

.import-drop-hint {
  font-size: 12px;
  color: var(--muted);
}

.import-file-label {
  color: var(--accent);
  cursor: pointer;
  text-decoration: underline;
}

.import-text-area {
  margin-bottom: 12px;
}

.import-text-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.import-textarea {
  width: 100%;
  min-height: 120px;
  font-family: var(--font-mono);
  font-size: 12px;
}

.import-format-badge {
  display: flex;
  align-items: center;
}

.import-stats .status-bar {
  display: flex;
  gap: 16px;
}

.import-preview {
  margin-top: 12px;
}

.row-invalid {
  background: var(--danger-bg);
}

.row-invalid:hover {
  background: var(--danger-hover-bg);
}

/* Export Dialog Styles */
.export-dialog {
  min-height: 200px;
}

.export-format-desc {
  font-size: 12px;
  line-height: 1.5;
}

.export-stats .status-bar {
  display: flex;
  gap: 16px;
}

.export-preview {
  margin-top: 12px;
}

.hidden {
  display: none;
}

/* Success Rate Dots */
.proxy-success-trend {
  background: var(--bg-secondary);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px 10px;
}

.proxy-success-trend-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.proxy-success-dots {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.proxy-success-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.proxy-success-dot-pass {
  background-color: #16a34a;
}

.proxy-success-dot-fail {
  background-color: #dc2626;
}

/* Reliability Score */
.proxy-reliability {
  background: var(--bg-secondary);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px 10px;
}

.proxy-reliability-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.proxy-reliability-bar {
  width: 100%;
  height: 6px;
  background: var(--line-soft);
  border-radius: 3px;
  overflow: hidden;
}

.proxy-reliability-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.reliability-high {
  background-color: #16a34a;
}

.reliability-medium {
  background-color: #d97706;
}

.reliability-low {
  background-color: #dc2626;
}

/* Advanced Features */
.advanced-feature {
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.advanced-feature-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: var(--bg-secondary);
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.advanced-feature-header:hover {
  background: var(--bg-hover);
}

.advanced-feature-content {
  padding: 12px;
  border-top: 1px solid var(--line-soft);
}

/* Health Timeline */
.health-timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.timeline-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 4px;
  flex-shrink: 0;
}

.timeline-dot-success {
  background-color: #16a34a;
}

.timeline-dot-danger {
  background-color: #dc2626;
}

.timeline-content {
  flex: 1;
  min-width: 0;
}

.timeline-time {
  font-size: 11px;
  color: var(--muted);
}

.timeline-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

/* Benchmark Grid */
.benchmark-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.benchmark-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}

.benchmark-label {
  font-size: 12px;
  color: var(--muted);
}

.benchmark-value {
  font-size: 13px;
  font-weight: 600;
}

.text-success {
  color: #16a34a;
}

.text-warning {
  color: #d97706;
}

.text-danger {
  color: #dc2626;
}

/* Geo Routing */
.geo-routing-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.geo-route-item {
  display: flex;
  gap: 8px;
  align-items: baseline;
}

/* Protocol Optimization */
.optimization-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.optimization-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
}

.optimization-high {
  background: #fef2f2;
  border-left: 3px solid #dc2626;
}

.optimization-medium {
  background: #fffbeb;
  border-left: 3px solid #d97706;
}

.optimization-low {
  background: #f0f9ff;
  border-left: 3px solid #3b82f6;
}

.optimization-icon {
  flex-shrink: 0;
}

/* Load Balancing */
.load-balancing-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.lb-metric {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lb-bar {
  flex: 1;
  height: 8px;
  background: var(--bg-secondary);
  border-radius: 4px;
  overflow: hidden;
}

.lb-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.lb-bar-success {
  background-color: #16a34a;
}

.lb-bar-warning {
  background-color: #d97706;
}

.lb-bar-danger {
  background-color: #dc2626;
}
</style>
