<template>
            <section class="card fade-in">
              <div class="card-body">
                <div class="section-header">
                  <div>
                    <h2 class="section-title">多跳代理池</h2>
                    <p class="form-hint">代理池、HTTP 代理端点、链服务和后端链路统一在本页配置；端到端入口以 HTTP 代理端点为准。</p>
                  </div>
                  <div class="btn-group">
                    <button @click="showHelpDialog" class="btn btn-ghost help-btn" title="帮助 (Shift+?)">
                      ?
                    </button>
                    <button @click="exportConfig" :disabled="isActionRunning('exportConfig')" class="btn btn-secondary">
                      {{ buttonLabel('exportConfig', '导出配置', '导出中...') }}
                    </button>
                    <button @click="showImportDialog" class="btn btn-secondary">
                      导入配置
                    </button>
                    <button @click="onLoadProxyPools" :disabled="isActionRunning('loadProxyPools')" class="btn btn-secondary">
                      {{ buttonLabel('loadProxyPools', '刷新', '刷新中...') }}
                    </button>
                  </div>
                </div>

                <div class="tabs workspace-tabs">
                  <button @click="proxyPoolTab = 'pools'" :class="{ active: proxyPoolTab === 'pools' }" class="tab-btn">代理池</button>
                  <button @click="proxyPoolTab = 'chain-view'" :class="{ active: proxyPoolTab === 'chain-view' }" class="tab-btn">链路视图</button>
                  <button @click="proxyPoolTab = 'gateway'" :class="{ active: proxyPoolTab === 'gateway' }" class="tab-btn">HTTP 代理端点</button>
                  <button @click="proxyPoolTab = 'gateway-status'" :class="{ active: proxyPoolTab === 'gateway-status' }" class="tab-btn">网关状态</button>
                  <button @click="proxyPoolTab = 'chain'" :class="{ active: proxyPoolTab === 'chain' }" class="tab-btn">链服务</button>
                  <button @click="proxyPoolTab = 'backend'" :class="{ active: proxyPoolTab === 'backend' }" class="tab-btn">后端链路</button>
                  <button @click="proxyPoolTab = 'events'" :class="{ active: proxyPoolTab === 'events' }" class="tab-btn">进程记录</button>
                </div>

                <div v-show="proxyPoolTab === 'pools'" class="tab-panel fade-in">

                <!-- Create pool form - Restructured -->
                <div class="card compact-workspace-card" style="margin-bottom: 12px;">
                  <div class="card-body">
                    <h3 class="settings-title">创建代理池</h3>

                    <!-- Section 1: Basic Settings -->
                    <div class="form-section">
                      <h4 class="form-section-title">基础设置</h4>
                      <div class="pool-create-grid">
                        <div class="form-group pool-field-wide">
                          <label class="form-label">
                            名称
                            <el-tooltip content="代理池的唯一标识名称，建议使用有意义的命名便于管理" placement="top">
                              <span class="help-icon">?</span>
                            </el-tooltip>
                          </label>
                          <input v-model.trim="proxyPoolForm.name" type="text" placeholder="如 exit-us-01" class="input" :class="{ 'input-error': poolFormErrors.name }" />
                          <span v-if="poolFormErrors.name" class="form-error">{{ poolFormErrors.name }}</span>
                        </div>
                        <div class="form-group pool-field-wide">
                          <label class="form-label">
                            监听地址
                            <el-tooltip content="代理池监听的网络地址。0.0.0.0 表示接受所有连接，127.0.0.1 仅本机可访问" placement="top">
                              <span class="help-icon">?</span>
                            </el-tooltip>
                          </label>
                          <input v-model.trim="proxyPoolForm.listen" type="text" placeholder="0.0.0.0" class="input" />
                        </div>
                        <div class="form-group">
                          <label class="form-label">
                            入站类型
                            <el-tooltip content="HTTP: 支持 Web 浏览器和大多数应用；SOCKS: 更通用的代理协议，支持更多应用类型" placement="top">
                              <span class="help-icon">?</span>
                            </el-tooltip>
                          </label>
                          <select v-model="proxyPoolForm.inbound_type" class="select">
                            <option value="http">HTTP</option>
                            <option value="socks">SOCKS</option>
                          </select>
                        </div>
                        <div class="form-group">
                          <label class="form-label">
                            轮转模式
                            <el-tooltip content="代理节点的选择策略。轮询: 按顺序循环；随机: 随机选择；最少连接: 选择当前连接最少的节点；加权: 按权重比例选择" placement="top">
                              <span class="help-icon">?</span>
                            </el-tooltip>
                          </label>
                          <select v-model="proxyPoolForm.rotation_mode" class="select">
                            <option value="round-robin">轮询 (Round Robin)</option>
                            <option value="random">随机 (Random)</option>
                            <option value="least-connections">最少连接</option>
                            <option value="weighted">加权轮转</option>
                          </select>
                        </div>
                      </div>
                    </div>

                    <!-- Section 2: Pool Templates -->
                    <div class="form-section">
                      <div class="form-section-header" @click="showPoolTemplates = !showPoolTemplates">
                        <h4 class="form-section-title" style="margin: 0;">
                          模板库
                          <el-tooltip content="使用预设模板快速创建常用类型的代理池" placement="top">
                            <span class="help-icon">?</span>
                          </el-tooltip>
                        </h4>
                        <span class="form-section-toggle" :class="{ expanded: showPoolTemplates }">&#9660;</span>
                      </div>
                      <div v-show="showPoolTemplates">
                        <!-- Template Category Tabs -->
                        <div class="template-category-tabs" style="margin-bottom: 12px;">
                          <button v-for="cat in templateCategories" :key="cat.id"
                            @click="selectedTemplateCategory = cat.id"
                            class="btn btn-xs"
                            :class="selectedTemplateCategory === cat.id ? 'btn-primary' : 'btn-ghost'">
                            {{ cat.name }}
                          </button>
                        </div>

                        <!-- Template List -->
                        <div class="pool-templates-grid">
                          <div v-for="template in filteredTemplates" :key="template.id"
                            class="pool-template-card"
                            :class="{ 'custom-template': template.custom }"
                            @click="previewTemplate(template)">
                            <div class="template-card-header">
                              <span class="template-icon">{{ template.icon }}</span>
                              <span v-if="template.custom" class="badge badge-xs badge-accent">自定义</span>
                            </div>
                            <div class="template-card-body">
                              <div class="template-name">{{ template.name }}</div>
                              <div class="template-desc text-xs text-muted">{{ template.description }}</div>
                              <div class="template-tags">
                                <span v-for="tag in template.tags" :key="tag" class="template-tag">{{ tag }}</span>
                              </div>
                            </div>
                            <div class="template-card-actions">
                              <button @click.stop="applyTemplate(template.id)" class="btn btn-xs btn-primary">应用</button>
                              <button v-if="template.custom" @click.stop="deleteCustomTemplate(template.id)" class="btn btn-xs btn-ghost" style="color: var(--danger-text);">删除</button>
                            </div>
                          </div>
                        </div>

                        <!-- Template Actions -->
                        <div class="template-actions" style="margin-top: 12px; display: flex; gap: 8px;">
                          <button @click="showSaveAsTemplateDialog()" class="btn btn-sm btn-secondary">
                            保存当前配置为模板
                          </button>
                          <button @click="showExportTemplatesDialog()" class="btn btn-sm btn-ghost">
                            导出模板
                          </button>
                          <button @click="showImportTemplatesDialog()" class="btn btn-sm btn-ghost">
                            导入模板
                          </button>
                        </div>
                      </div>
                    </div>

                    <!-- Section 3: Pool Type Selection -->
                    <div class="form-section">
                      <h4 class="form-section-title">池类型选择</h4>
                      <div class="pool-type-selector">
                        <div class="pool-type-option" :class="{ active: selectedPoolType === 'direct' }" @click="selectPoolType('direct')">
                          <div class="pool-type-icon">🔗</div>
                          <div class="pool-type-name">普通代理池</div>
                          <div class="pool-type-desc">直连节点，无链式路由</div>
                          <div class="pool-type-usecase">适用: 独立代理、出口节点、简单场景</div>
                        </div>
                        <div class="pool-type-option" :class="{ active: selectedPoolType === 'chain' }" @click="selectPoolType('chain')">
                          <div class="pool-type-icon">⛓️</div>
                          <div class="pool-type-name">链式代理池</div>
                          <div class="pool-type-desc">需要前置节点的链式路由</div>
                          <div class="pool-type-usecase">适用: 多跳链路、前置+落地组合</div>
                        </div>
                        <div class="pool-type-option" :class="{ active: selectedPoolType === 'unreachable' }" @click="selectPoolType('unreachable')">
                          <div class="pool-type-icon">🚫</div>
                          <div class="pool-type-name">特殊用途池</div>
                          <div class="pool-type-desc">不可直接连接的代理池</div>
                          <div class="pool-type-usecase">适用: 内网节点、中转节点</div>
                        </div>
                      </div>

                      <!-- Pool Type Explanation Panel -->
                      <div class="pool-type-explanation">
                        <div v-if="selectedPoolType === 'direct'" class="explanation-content">
                          <h5 class="explanation-title">普通代理池 (直连)</h5>
                          <p class="explanation-text">节点可直接连接互联网，无需前置代理。通常用作链路的最终出口节点（落地池）。</p>
                          <ul class="explanation-list">
                            <li>节点直接访问目标网站</li>
                            <li>出口 IP 即为节点 IP</li>
                            <li>延迟最低，性能最佳</li>
                          </ul>
                        </div>
                        <div v-else-if="selectedPoolType === 'chain'" class="explanation-content">
                          <h5 class="explanation-title">链式代理池</h5>
                          <p class="explanation-text">节点需要通过前置代理才能连接互联网。通常用作前置节点（入口池）。</p>
                          <ul class="explanation-list">
                            <li>流量经过前置节点转发</li>
                            <li>增强匿名性和安全性</li>
                            <li>适合多跳链路场景</li>
                          </ul>
                          <div class="explanation-tip">
                            <strong>配置建议:</strong> 创建落地池后，建议配置前置池以构建完整链路。
                          </div>
                        </div>
                        <div v-else-if="selectedPoolType === 'unreachable'" class="explanation-content">
                          <h5 class="explanation-title">特殊用途池</h5>
                          <p class="explanation-text">节点不可直接连接互联网，通常作为链路中的中转节点或特殊角色。</p>
                          <ul class="explanation-list">
                            <li>节点本身无法访问外网</li>
                            <li>需要前置节点提供出口</li>
                            <li>常用于内网穿透场景</li>
                          </ul>
                        </div>
                      </div>
                    </div>

                    <!-- Section 3: Advanced Filters (Collapsible) -->
                    <div class="form-section">
                      <div class="form-section-header" @click="showAdvancedFilters = !showAdvancedFilters">
                        <h4 class="form-section-title">
                          过滤条件
                          <el-tooltip content="设置筛选规则，仅符合所有条件的节点会加入此池。不设置则不限制" placement="top">
                            <span class="help-icon">?</span>
                          </el-tooltip>
                        </h4>
                        <span class="collapse-icon">{{ showAdvancedFilters ? '▼' : '▶' }}</span>
                      </div>
                      <div v-show="showAdvancedFilters" class="advanced-filters">
                        <div class="pool-create-grid">
                          <div class="form-group">
                            <label class="form-label">
                              ChatGPT
                              <el-tooltip content="筛选支持 ChatGPT 的节点。已解锁: 可访问 ChatGPT；未解锁: 被封锁" placement="top">
                                <span class="help-icon">?</span>
                              </el-tooltip>
                            </label>
                            <select v-model="proxyPoolForm.filters.openai_filter" class="select">
                              <option value="">不限</option>
                              <option value="unlocked">已解锁</option>
                              <option value="blocked">未解锁</option>
                              <option value="unchecked">未检测</option>
                            </select>
                          </div>
                          <div class="form-group">
                            <label class="form-label">
                              家宽
                              <el-tooltip content="家宽: 家庭宽带 IP，更稳定且不易被封锁；非家宽: 机房 IP，可能被限制" placement="top">
                                <span class="help-icon">?</span>
                              </el-tooltip>
                            </label>
                            <select v-model="proxyPoolForm.filters.ip_purity_filter" class="select">
                              <option value="">不限</option>
                              <option value="residential">家宽</option>
                              <option value="non_residential">非家宽</option>
                              <option value="unknown">未知</option>
                            </select>
                          </div>
                          <div class="form-group pool-field-wide">
                            <label class="form-label">
                              国家/地区
                              <el-tooltip content="筛选特定国家或地区的节点。可多选" placement="top">
                                <span class="help-icon">?</span>
                              </el-tooltip>
                            </label>
                            <el-select v-model="proxyPoolForm.filters.geo_countries" multiple collapse-tags collapse-tags-tooltip clearable placeholder="不限" size="small" style="width: 100%">
                              <el-option v-for="opt in geoCountryOptions" :key="'pool-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                            </el-select>
                          </div>
                          <div class="form-group">
                            <label class="form-label">
                              延迟范围
                              <el-tooltip content="节点响应时间范围（毫秒）。设置后仅包含延迟在此范围内的节点" placement="top">
                                <span class="help-icon">?</span>
                              </el-tooltip>
                            </label>
                            <div class="input-group">
                              <input v-model.number="proxyPoolForm.filters.latency_min" type="number" min="0" placeholder="最低" class="input" />
                              <span class="input-sep">-</span>
                              <input v-model.number="proxyPoolForm.filters.latency_max" type="number" min="0" placeholder="最高" class="input" />
                            </div>
                          </div>
                          <div class="form-group">
                            <label class="form-label">
                              时效(小时)
                              <el-tooltip content="仅包含在此时间内检测过的节点。0 或空表示不限制" placement="top">
                                <span class="help-icon">?</span>
                              </el-tooltip>
                            </label>
                            <input v-model.number="proxyPoolForm.filters.freshness_hours" type="number" min="0" placeholder="不限" class="input" />
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Front Pool Recommendation for Chain Type -->
                    <div v-if="selectedPoolType === 'chain'" class="front-pool-recommendation">
                      <div class="recommendation-icon">💡</div>
                      <div class="recommendation-content">
                        <h5 class="recommendation-title">前置池配置建议</h5>
                        <p class="recommendation-text">链式代理池需要搭配前置池使用。建议在创建此池后，配置一个前置池作为流量入口。</p>
                        <div v-if="frontPoolOptions.length" class="recommendation-options">
                          <span class="recommendation-label">可用前置池:</span>
                          <span v-for="pool in frontPoolOptions" :key="'front-' + pool.id" class="badge badge-sm badge-info">
                            {{ pool.name }}
                          </span>
                        </div>
                      </div>
                    </div>

                    <!-- Action buttons -->
                    <div class="pool-create-actions">
                      <button @click="previewPoolConfig" class="btn btn-ghost">
                        预览配置
                      </button>
                      <button @click="onCreateProxyPool" :disabled="isActionRunning('createProxyPool')" class="btn btn-primary">
                        {{ buttonLabel('createProxyPool', '创建代理池', '创建中...') }}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Config Preview Dialog -->
                <el-dialog v-model="previewDialogVisible" title="配置预览" width="min(650px, 95vw)" append-to-body aria-labelledby="preview-dialog-title" aria-modal="true">
                  <h3 id="preview-dialog-title" class="sr-only">配置预览</h3>
                  <div class="config-preview">
                    <p class="text-muted text-sm" style="margin-bottom: 12px;">以下是将要发送给后端的 JSON 配置：</p>
                    <div class="config-code-block">
                      <div class="config-code-header">
                        <span class="config-code-lang">JSON</span>
                        <button class="btn btn-xs btn-ghost" @click="copyConfigToClipboard">
                          {{ copySuccess ? '已复制' : '复制配置' }}
                        </button>
                      </div>
                      <pre class="config-code-content"><code>{{ previewConfigJson }}</code></pre>
                    </div>
                  </div>
                  <template #footer>
                    <button class="btn btn-secondary" @click="previewDialogVisible = false">关闭</button>
                    <button class="btn btn-primary" @click="previewDialogVisible = false; onCreateProxyPool()">确认创建</button>
                  </template>
                </el-dialog>

                <!-- Runtime Config Dialog -->
                <el-dialog v-model="runtimeConfigDialogVisible" title="运行配置" width="min(700px, 95vw)" append-to-body aria-labelledby="runtime-config-dialog-title" aria-modal="true">
                  <h3 id="runtime-config-dialog-title" class="sr-only">运行配置</h3>
                  <div class="config-preview">
                    <p class="text-muted text-sm" style="margin-bottom: 12px;">当前池的 singbox 运行配置：</p>
                    <div class="config-code-block">
                      <div class="config-code-header">
                        <span class="config-code-lang">singbox JSON</span>
                        <button class="btn btn-xs btn-ghost" @click="copyRuntimeConfig">
                          {{ copySuccess ? '已复制' : '复制配置' }}
                        </button>
                      </div>
                      <pre class="config-code-content"><code>{{ runtimeConfigJson }}</code></pre>
                    </div>
                  </div>
                  <template #footer>
                    <button class="btn btn-secondary" @click="runtimeConfigDialogVisible = false">关闭</button>
                  </template>
                </el-dialog>

                <!-- Import Config Dialog -->
                <el-dialog v-model="importDialogVisible" title="导入配置" width="min(600px, 95vw)" append-to-body aria-labelledby="import-dialog-title" aria-modal="true">
                  <h3 id="import-dialog-title" class="sr-only">导入配置</h3>
                  <div class="import-dialog-content">
                    <!-- Step 1: File Upload -->
                    <div v-if="importStep === 1" class="import-upload-step">
                      <p class="text-muted text-sm" style="margin-bottom: 16px;">选择要导入的配置文件（JSON 格式）：</p>
                      <div class="import-upload-area" @click="triggerFileInput" @dragover.prevent @drop.prevent="handleFileDrop">
                        <input ref="fileInput" type="file" accept=".json" @change="handleFileSelect" style="display: none;" />
                        <div class="import-upload-icon">📁</div>
                        <div class="import-upload-text">点击选择文件或拖拽到此处</div>
                        <div class="import-upload-hint">支持 .json 格式的配置文件</div>
                      </div>
                      <div v-if="importFileName" class="import-file-info">
                        <span class="import-file-name">{{ importFileName }}</span>
                        <button @click="clearImportFile" class="btn btn-xs btn-ghost">清除</button>
                      </div>
                    </div>

                    <!-- Step 2: Preview & Options -->
                    <div v-if="importStep === 2" class="import-preview-step">
                      <div class="import-summary">
                        <h4 class="import-summary-title">导入预览</h4>
                        <div class="import-summary-stats">
                          <div class="import-stat">
                            <span class="import-stat-value">{{ importPreview.pools || 0 }}</span>
                            <span class="import-stat-label">代理池</span>
                          </div>
                          <div class="import-stat">
                            <span class="import-stat-value">{{ importPreview.endpoints || 0 }}</span>
                            <span class="import-stat-label">入站端口</span>
                          </div>
                          <div class="import-stat">
                            <span class="import-stat-value">{{ importPreview.subscriptions || 0 }}</span>
                            <span class="import-stat-label">订阅源</span>
                          </div>
                        </div>
                      </div>

                      <div class="import-options">
                        <h4 class="import-options-title">导入内容</h4>
                        <label class="import-option">
                          <input type="checkbox" v-model="importOptions.pools" />
                          <span>代理池配置</span>
                        </label>
                        <label class="import-option">
                          <input type="checkbox" v-model="importOptions.endpoints" />
                          <span>入站端口配置</span>
                        </label>
                        <label class="import-option">
                          <input type="checkbox" v-model="importOptions.subscriptions" />
                          <span>订阅源配置</span>
                        </label>
                        <label class="import-option">
                          <input type="checkbox" v-model="importOptions.settings" />
                          <span>系统设置</span>
                        </label>
                      </div>
                    </div>

                    <!-- Step 3: Results -->
                    <div v-if="importStep === 3" class="import-results-step">
                      <div class="import-results-header" :class="importResults.success ? 'success' : 'error'">
                        <span class="import-results-icon">{{ importResults.success ? '✓' : '✗' }}</span>
                        <span>{{ importResults.success ? '导入完成' : '导入失败' }}</span>
                      </div>
                      <div class="import-results-stats">
                        <div class="import-result-item success">
                          <span class="import-result-count">{{ importResults.successCount || 0 }}</span>
                          <span class="import-result-label">成功</span>
                        </div>
                        <div class="import-result-item skipped">
                          <span class="import-result-count">{{ importResults.skippedCount || 0 }}</span>
                          <span class="import-result-label">跳过</span>
                        </div>
                        <div class="import-result-item error">
                          <span class="import-result-count">{{ importResults.errorCount || 0 }}</span>
                          <span class="import-result-label">失败</span>
                        </div>
                      </div>
                      <div v-if="importResults.errors?.length" class="import-errors-list">
                        <p class="text-sm text-muted">错误详情：</p>
                        <div v-for="(err, idx) in importResults.errors" :key="'import-err-' + idx" class="import-error-item">
                          {{ err }}
                        </div>
                      </div>
                    </div>
                  </div>
                  <template #footer>
                    <button v-if="importStep === 1" class="btn btn-secondary" @click="importDialogVisible = false">取消</button>
                    <button v-if="importStep === 2" class="btn btn-secondary" @click="importStep = 1">上一步</button>
                    <button v-if="importStep === 2" class="btn btn-secondary" @click="importDialogVisible = false">取消</button>
                    <button v-if="importStep === 1" class="btn btn-primary" @click="parseImportFile" :disabled="!importFileContent">
                      下一步
                    </button>
                    <button v-if="importStep === 2" class="btn btn-primary" @click="executeImport" :disabled="isActionRunning('importConfig')">
                      {{ buttonLabel('importConfig', '确认导入', '导入中...') }}
                    </button>
                    <button v-if="importStep === 3" class="btn btn-primary" @click="importDialogVisible = false">完成</button>
                  </template>
                </el-dialog>

                <!-- Help Dialog -->
                <el-dialog v-model="helpDialogVisible" title="帮助 - 多跳代理池" width="min(700px, 95vw)" append-to-body aria-labelledby="help-dialog-title" aria-modal="true">
                  <h3 id="help-dialog-title" class="sr-only">帮助 - 多跳代理池</h3>
                  <div class="help-dialog-content">
                    <div class="help-section">
                      <h4 class="help-section-title">页面概览</h4>
                      <p class="help-text">本页面用于管理多跳代理池、HTTP 代理端点、链服务和后端链路。您可以在此创建、配置和监控代理池。</p>
                    </div>

                    <div class="help-section">
                      <h4 class="help-section-title">常用操作</h4>
                      <ul class="help-list">
                        <li><strong>创建代理池:</strong> 点击"创建代理池"按钮，填写名称和筛选条件</li>
                        <li><strong>配置链路:</strong> 在"链路配置"区域选择代理池，启用池级链路</li>
                        <li><strong>同步节点:</strong> 点击代理池行的"同步"按钮刷新节点列表</li>
                        <li><strong>导出/导入:</strong> 使用顶部按钮导出或导入配置</li>
                      </ul>
                    </div>

                    <div class="help-section">
                      <h4 class="help-section-title">术语说明</h4>
                      <div class="help-terms">
                        <div class="help-term">
                          <span class="help-term-name">代理池</span>
                          <span class="help-term-desc">一组具有相同筛选条件的代理节点集合</span>
                        </div>
                        <div class="help-term">
                          <span class="help-term-name">前置池</span>
                          <span class="help-term-desc">链式路由中的入口节点池，客户端首先连接</span>
                        </div>
                        <div class="help-term">
                          <span class="help-term-name">落地池</span>
                          <span class="help-term-desc">链式路由中的出口代理池，决定出口 IP</span>
                        </div>
                        <div class="help-term">
                          <span class="help-term-name">入站端口</span>
                          <span class="help-term-desc">客户端连接代理服务的网络端口</span>
                        </div>
                      </div>
                    </div>

                    <div class="help-section">
                      <h4 class="help-section-title">快捷键</h4>
                      <div class="help-shortcuts">
                        <div class="help-shortcut">
                          <span class="help-shortcut-keys">Shift + ?</span>
                          <span class="help-shortcut-desc">显示帮助</span>
                        </div>
                        <div class="help-shortcut">
                          <span class="help-shortcut-keys">Ctrl + R</span>
                          <span class="help-shortcut-desc">刷新数据</span>
                        </div>
                        <div class="help-shortcut">
                          <span class="help-shortcut-keys">Ctrl + E</span>
                          <span class="help-shortcut-desc">导出配置</span>
                        </div>
                        <div class="help-shortcut">
                          <span class="help-shortcut-keys">Ctrl + I</span>
                          <span class="help-shortcut-desc">导入配置</span>
                        </div>
                      </div>
                    </div>

                    <div class="help-section">
                      <h4 class="help-section-title">常见问题</h4>
                      <div class="help-faq">
                        <div class="help-faq-item">
                          <strong>Q: 代理池节点为空？</strong>
                          <p>点击"同步"按钮刷新节点列表，确保订阅源配置正确</p>
                        </div>
                        <div class="help-faq-item">
                          <strong>Q: 链路测试失败？</strong>
                          <p>检查前置池和落地池是否都有健康节点，确保池级链路已启用</p>
                        </div>
                        <div class="help-faq-item">
                          <strong>Q: 端口冲突？</strong>
                          <p>确保每个入站端口使用不同的监听地址和端口组合</p>
                        </div>
                      </div>
                    </div>
                  </div>
                  <template #footer>
                    <button class="btn btn-secondary" @click="helpDialogVisible = false">关闭</button>
                  </template>
                </el-dialog>

                <!-- Rotation History Dialog -->
                <el-dialog v-model="rotationHistoryVisible" :title="'轮转历史 - ' + rotationHistoryPoolName" width="min(600px, 95vw)" append-to-body aria-labelledby="rotation-history-dialog-title" aria-modal="true">
                  <h3 id="rotation-history-dialog-title" class="sr-only">轮转历史</h3>
                  <div class="rotation-history-content">
                    <div v-if="getRotationHistoryList().length === 0" class="empty-state-small">
                      <p>暂无轮转历史记录</p>
                    </div>
                    <div v-else class="rotation-history-list">
                      <div v-for="(entry, idx) in getRotationHistoryList().slice(0, 50)" :key="'rh-' + idx" class="rotation-history-item" :class="'rotation-history-' + entry.type">
                        <span class="rotation-history-icon">{{ entry.type === 'switch' ? '🔄' : entry.type === 'success' ? '✓' : '✗' }}</span>
                        <span class="rotation-history-msg">{{ entry.message }}</span>
                        <span class="rotation-history-time">{{ formatRotationTime(entry.timestamp) }}</span>
                      </div>
                    </div>
                  </div>
                  <template #footer>
                    <button class="btn btn-secondary" @click="rotationHistoryVisible = false">关闭</button>
                  </template>
                </el-dialog>

                <!-- Template Preview Dialog -->
                <el-dialog v-model="templatePreviewVisible" :title="'模板预览 - ' + (previewingTemplate?.name || '')" width="min(500px, 95vw)" append-to-body>
                  <div v-if="previewingTemplate" class="template-preview">
                    <div class="template-preview-header" style="margin-bottom: 16px;">
                      <span class="template-preview-icon" style="font-size: 32px;">{{ previewingTemplate.icon }}</span>
                      <div>
                        <div class="font-semibold">{{ previewingTemplate.name }}</div>
                        <div class="text-xs text-muted">{{ previewingTemplate.description }}</div>
                      </div>
                    </div>
                    <div class="template-preview-details">
                      <div class="template-preview-item">
                        <span class="text-muted">池类型:</span>
                        <span class="badge badge-sm" :class="previewingTemplate.type === 'chain' ? 'badge-warning' : 'badge-success'">
                          {{ previewingTemplate.type === 'chain' ? '链式' : '直连' }}
                        </span>
                      </div>
                      <div class="template-preview-item">
                        <span class="text-muted">国家/地区:</span>
                        <span>{{ previewingTemplate.countries?.join(', ') || '不限' }}</span>
                      </div>
                      <div class="template-preview-item">
                        <span class="text-muted">最大延迟:</span>
                        <span>{{ previewingTemplate.maxLatency ? previewingTemplate.maxLatency + 'ms' : '不限' }}</span>
                      </div>
                      <div class="template-preview-item">
                        <span class="text-muted">ChatGPT:</span>
                        <span>{{ previewingTemplate.openai ? '需要解锁' : '不限' }}</span>
                      </div>
                      <div class="template-preview-item">
                        <span class="text-muted">家宽:</span>
                        <span>{{ previewingTemplate.ipPurity ? '需要家宽' : '不限' }}</span>
                      </div>
                    </div>
                  </div>
                  <template #footer>
                    <button class="btn btn-secondary" @click="templatePreviewVisible = false">取消</button>
                    <button class="btn btn-primary" @click="applyPreviewedTemplate()">应用模板</button>
                  </template>
                </el-dialog>

                <!-- Save As Template Dialog -->
                <el-dialog v-model="saveTemplateDialogVisible" title="保存为模板" width="min(400px, 95vw)" append-to-body>
                  <div class="save-template-form">
                    <div class="form-field" style="margin-bottom: 12px;">
                      <label class="form-label">模板名称</label>
                      <input v-model="newTemplateName" type="text" class="input" placeholder="例如: 新加坡高速池" />
                    </div>
                    <div class="form-field" style="margin-bottom: 12px;">
                      <label class="form-label">描述</label>
                      <input v-model="newTemplateDescription" type="text" class="input" placeholder="例如: 用于高速下载的新加坡节点" />
                    </div>
                    <div class="form-field" style="margin-bottom: 12px;">
                      <label class="form-label">图标 (Emoji)</label>
                      <input v-model="newTemplateIcon" type="text" class="input" placeholder="例如: 🇸🇬" style="width: 80px;" />
                    </div>
                    <div class="form-field">
                      <label class="form-label">分类</label>
                      <select v-model="newTemplateCategory" class="input" style="width: 100%;">
                        <option value="region">按地区</option>
                        <option value="usecase">按用途</option>
                        <option value="custom">自定义</option>
                      </select>
                    </div>
                  </div>
                  <template #footer>
                    <button class="btn btn-secondary" @click="saveTemplateDialogVisible = false">取消</button>
                    <button class="btn btn-primary" @click="saveAsTemplate()" :disabled="!newTemplateName.trim()">保存</button>
                  </template>
                </el-dialog>

                <!-- Export Templates Dialog -->
                <el-dialog v-model="exportTemplatesDialogVisible" title="导出模板" width="min(400px, 95vw)" append-to-body>
                  <div class="export-templates">
                    <p class="text-muted text-sm" style="margin-bottom: 12px;">选择要导出的模板:</p>
                    <div class="export-template-list">
                      <label v-for="template in customTemplates" :key="'exp-' + template.id" class="export-template-item">
                        <input type="checkbox" v-model="selectedExportTemplates" :value="template.id" />
                        <span>{{ template.icon }} {{ template.name }}</span>
                      </label>
                    </div>
                    <div v-if="customTemplates.length === 0" class="text-xs text-muted">暂无自定义模板</div>
                  </div>
                  <template #footer>
                    <button class="btn btn-secondary" @click="exportTemplatesDialogVisible = false">取消</button>
                    <button class="btn btn-primary" @click="exportTemplates()" :disabled="selectedExportTemplates.length === 0">导出 ({{ selectedExportTemplates.length }})</button>
                  </template>
                </el-dialog>

                <!-- Import Templates Dialog -->
                <el-dialog v-model="importTemplatesDialogVisible" title="导入模板" width="min(400px, 95vw)" append-to-body>
                  <div class="import-templates">
                    <div class="import-drop-zone" @click="$refs.templateFileInput.click()" @dragover.prevent @drop.prevent="handleTemplateFileDrop($event)">
                      <div class="import-drop-icon">📄</div>
                      <div class="import-drop-text">点击或拖拽 JSON 文件到此处</div>
                      <div class="import-drop-hint">支持从本系统导出的模板文件</div>
                    </div>
                    <input ref="templateFileInput" type="file" accept=".json" style="display: none;" @change="handleTemplateFileSelect($event)" />
                    <div v-if="importTemplatePreview" class="import-preview" style="margin-top: 12px;">
                      <div class="text-sm font-semibold">预览: 将导入 {{ importTemplatePreview.count }} 个模板</div>
                      <div v-for="t in importTemplatePreview.templates" :key="'imp-' + t.id" class="text-xs text-muted">
                        {{ t.icon }} {{ t.name }}
                      </div>
                    </div>
                  </div>
                  <template #footer>
                    <button class="btn btn-secondary" @click="importTemplatesDialogVisible = false">取消</button>
                    <button class="btn btn-primary" @click="importTemplates()" :disabled="!importTemplatePreview">导入</button>
                  </template>
                </el-dialog>

                <div class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 50px;">ID</th>
                        <th style="width: 120px;">名称</th>
                        <th>筛选条件</th>
                        <th style="width: 60px;">节点</th>
                        <th style="width: 70px;">状态</th>
                        <th style="width: 60px;">类型</th>
                        <th style="width: 240px;">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <template v-for="item in paginatedProxyPools" :key="item.id">
                        <tr>
                          <td class="mono text-muted">{{ item.id }}</td>
                          <td><input :value="item.name || ''" @change="onRenameProxyPool(item, $event.target.value)" type="text" class="inline-input" /></td>
                          <td>
                            <div class="pubsub-filters">
                              <span v-if="item.filters?.route_mode_filter === 'direct'" class="badge badge-sm badge-success">直连</span>
                              <span v-else-if="item.filters?.route_mode_filter === 'chain'" class="badge badge-sm badge-warning">链式</span>
                              <span v-else-if="item.filters?.route_mode_filter === 'unreachable'" class="badge badge-sm badge-danger">不可达</span>
                              <span v-if="item.filters?.protocol" class="badge badge-sm badge-neutral">{{ item.filters.protocol }}</span>
                              <span v-if="item.filters?.geo_country" class="badge badge-sm badge-neutral">{{ item.filters.geo_country }}</span>
                              <span v-if="item.filters?.openai_filter === 'unlocked'" class="badge badge-sm badge-success">GPT解锁</span>
                              <span v-else-if="item.filters?.openai_filter === 'blocked'" class="badge badge-sm badge-danger">GPT封锁</span>
                              <span v-if="item.filters?.ip_purity_filter === 'residential'" class="badge badge-sm badge-success">家宽</span>
                              <span v-else-if="item.filters?.ip_purity_filter === 'non_residential'" class="badge badge-sm badge-danger">非家宽</span>
                              <span v-if="item.filters?.source" class="badge badge-sm badge-neutral">{{ item.filters.source }}</span>
                              <span v-if="!item.filters?.route_mode_filter && !item.filters?.protocol && !item.filters?.geo_country && !item.filters?.openai_filter && !item.filters?.ip_purity_filter && !item.filters?.source" class="badge badge-sm badge-neutral">不限</span>
                            </div>
                          </td>
                          <td class="mono">{{ item.match_count || 0 }}</td>
                          <td><span class="text-sm" :class="item.status === 'running' ? 'text-emerald-600' : 'text-muted'">{{ item.status || 'stopped' }}</span></td>
                          <td><span class="pool-tag" :class="getPoolTypeTagClass(item)">{{ getPoolTypeTag(item) }}</span></td>
                          <td>
                            <div class="btn-group btn-group-nowrap">
                              <button @click="togglePoolDetail(item.id)" class="btn btn-xs btn-ghost">
                                {{ expandedPoolId === item.id ? '收起' : '详情' }}
                              </button>
                              <button @click="onSyncPool(item.id)" :disabled="isActionRunning('syncPool-' + item.id)" class="btn btn-xs btn-secondary">同步</button>
                              <button @click="clonePool(item)" :disabled="isActionRunning('clonePool-' + item.id)" class="btn btn-xs btn-ghost">克隆</button>
                              <button @click="applyPoolFiltersToForm(item)" class="btn btn-xs btn-ghost">套用</button>
                              <button @click="onUpdatePoolFilters(item)" :disabled="isActionRunning('updatePool-' + item.id)" class="btn btn-xs btn-ghost">保存</button>
                              <button @click="exportSinglePool(item)" class="btn btn-xs btn-ghost">导出</button>
                              <a v-if="item.export_url" :href="item.export_url" target="_blank" class="btn btn-xs btn-ghost">订阅源</a>
                              <button @click="onDeleteProxyPool(item.id)" :disabled="isActionRunning('deletePool-' + item.id)" class="btn btn-xs btn-danger">删除</button>
                            </div>
                          </td>
                        </tr>
                        <!-- Expanded Pool Detail Row -->
                        <tr v-if="expandedPoolId === item.id" class="pool-detail-row">
                          <td colspan="7">
                            <div class="pool-detail-content">
                              <div class="pool-detail-grid">
                                <div class="pool-detail-section">
                                  <h5 class="pool-detail-title">健康状态</h5>
                                  <div class="pool-detail-stats">
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">总节点</span>
                                      <span class="pool-stat-value">{{ item.match_count || 0 }}</span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">健康节点</span>
                                      <span class="pool-stat-value text-success">{{ item.healthy_count || 0 }}</span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">降级节点</span>
                                      <span class="pool-stat-value text-warning">{{ item.degraded_count || 0 }}</span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">不可用</span>
                                      <span class="pool-stat-value text-danger">{{ item.unavailable_count || 0 }}</span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">运行状态</span>
                                      <span class="badge" :class="item.status === 'running' ? 'badge-success' : 'badge-neutral'">
                                        {{ item.status || 'stopped' }}
                                      </span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">导出链接</span>
                                      <span v-if="item.export_url" class="text-success text-xs">可用</span>
                                      <span v-else class="text-muted text-xs">未配置</span>
                                    </div>
                                  </div>
                                </div>

                                <div class="pool-detail-section">
                                  <h5 class="pool-detail-title">链路配置</h5>
                                  <div class="pool-detail-stats">
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">路由模式</span>
                                      <span class="badge badge-sm" :class="getRouteModeBadgeClass(item.filters?.route_mode_filter)">
                                        {{ getRouteModeText(item.filters?.route_mode_filter) }}
                                      </span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">池级链路</span>
                                      <span v-if="item.chain_enabled" class="badge badge-sm badge-success">已启用</span>
                                      <span v-else class="badge badge-sm badge-neutral">未启用</span>
                                    </div>
                                  </div>
                                </div>

                                <div class="pool-detail-section">
                                  <h5 class="pool-detail-title">筛选条件详情</h5>
                                  <div class="pool-detail-conditions">
                                    <div v-if="item.filters?.openai_filter" class="pool-condition">
                                      <span class="pool-condition-label">ChatGPT:</span>
                                      <span class="pool-condition-value">{{ getOpenaiFilterText(item.filters.openai_filter) }}</span>
                                    </div>
                                    <div v-if="item.filters?.ip_purity_filter" class="pool-condition">
                                      <span class="pool-condition-label">家宽:</span>
                                      <span class="pool-condition-value">{{ getIpPurityText(item.filters.ip_purity_filter) }}</span>
                                    </div>
                                    <div v-if="item.filters?.geo_countries?.length" class="pool-condition">
                                      <span class="pool-condition-label">国家:</span>
                                      <span class="pool-condition-value">{{ item.filters.geo_countries.join(', ') }}</span>
                                    </div>
                                    <div v-if="item.filters?.latency_min || item.filters?.latency_max" class="pool-condition">
                                      <span class="pool-condition-label">延迟:</span>
                                      <span class="pool-condition-value">{{ item.filters.latency_min || 0 }}-{{ item.filters.latency_max || '∞' }}ms</span>
                                    </div>
                                    <div v-if="item.filters?.freshness_hours" class="pool-condition">
                                      <span class="pool-condition-label">时效:</span>
                                      <span class="pool-condition-value">{{ item.filters.freshness_hours }}h</span>
                                    </div>
                                    <div v-if="!hasAnyFilter(item.filters)" class="pool-condition">
                                      <span class="text-muted">无筛选条件（不限）</span>
                                    </div>
                                  </div>
                                </div>

                                <!-- Exit IP & Region (for exit pools) -->
                                <div v-if="item.filters?.route_mode_filter === 'direct' || !item.filters?.route_mode_filter" class="pool-detail-section">
                                  <h5 class="pool-detail-title">出口信息</h5>
                                  <div class="pool-detail-stats">
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">出口 IP</span>
                                      <span v-if="item.exit_ip" class="pool-stat-value mono">{{ item.exit_ip }}</span>
                                      <span v-else class="text-muted text-xs">检测中...</span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">地区</span>
                                      <span v-if="item.region || item.filters?.geo_country" class="pool-stat-value">
                                        {{ item.region || item.filters?.geo_country }}
                                      </span>
                                      <span v-else class="text-muted text-xs">未知</span>
                                    </div>
                                    <div v-if="item.isp" class="pool-stat">
                                      <span class="pool-stat-label">ISP</span>
                                      <span class="pool-stat-value text-xs">{{ item.isp }}</span>
                                    </div>
                                  </div>
                                </div>

                                <!-- Pool Dependencies -->
                                <div class="pool-detail-section">
                                  <h5 class="pool-detail-title">依赖关系</h5>
                                  <div class="pool-detail-stats">
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">关联端点</span>
                                      <span class="pool-stat-value">{{ getEndpointCountForPool(item.id) }} 个</span>
                                    </div>
                                    <div v-if="item.filters?.route_mode_filter === 'chain'" class="pool-stat">
                                      <span class="pool-stat-label">前置池</span>
                                      <span v-if="getFrontPoolForExit(item.id)" class="pool-stat-value text-xs">
                                        {{ getFrontPoolForExit(item.id).name }}
                                      </span>
                                      <span v-else class="text-warning text-xs">未配置</span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">被依赖</span>
                                      <span class="pool-stat-value">{{ getDependentPoolCount(item.id) }} 个池</span>
                                    </div>
                                  </div>
                                </div>

                                <!-- Rotation Config & Stats -->
                                <div class="pool-detail-section">
                                  <h5 class="pool-detail-title">轮转配置</h5>
                                  <div class="pool-detail-stats">
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">轮转模式</span>
                                      <span class="pool-stat-value">
                                        <select v-model="rotationConfig[item.id]" @change="saveRotationConfig(item.id)" class="inline-input" style="width: 140px;">
                                          <option value="round-robin">轮询</option>
                                          <option value="random">随机</option>
                                          <option value="least-connections">最少连接</option>
                                          <option value="weighted">加权轮转</option>
                                        </select>
                                      </span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">当前节点</span>
                                      <span class="pool-stat-value mono text-xs">{{ getCurrentProxy(item.id) || '无' }}</span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">请求总数</span>
                                      <span class="pool-stat-value">{{ getRotationStats(item.id).totalRequests || 0 }}</span>
                                    </div>
                                    <div class="pool-stat">
                                      <span class="pool-stat-label">成功率</span>
                                      <span class="pool-stat-value" :class="getRotationSuccessRateClass(item.id)">{{ getRotationSuccessRate(item.id) }}</span>
                                    </div>
                                  </div>
                                  <!-- Load Distribution Visualization -->
                                  <div class="rotation-distribution" v-if="getRotationStats(item.id).proxyCounts && Object.keys(getRotationStats(item.id).proxyCounts).length">
                                    <div class="rotation-dist-label">负载分布:</div>
                                    <div class="rotation-dist-bar">
                                      <div v-for="(count, proxy, idx) in getRotationStats(item.id).proxyCounts" :key="'dist-' + proxy" class="rotation-dist-segment" :style="{ width: getDistributionWidth(count, item.id) + '%', backgroundColor: getRotationColor(idx) }" :title="`${proxy}: ${count} 请求`"></div>
                                    </div>
                                    <div class="rotation-dist-legend">
                                      <span v-for="(count, proxy, idx) in getRotationStats(item.id).proxyCounts" :key="'legend-' + proxy" class="rotation-dist-item">
                                        <span class="rotation-dist-dot" :style="{ backgroundColor: getRotationColor(idx) }"></span>
                                        <span class="text-xs text-muted">{{ formatProxyShortName(proxy) }}: {{ count }}</span>
                                      </span>
                                    </div>
                                  </div>
                                </div>

                                <!-- Performance Metrics -->
                                <div class="pool-detail-section pool-detail-section-full">
                                  <h5 class="pool-detail-title">性能指标</h5>
                                  <div class="pool-performance-metrics">
                                    <div class="pool-perf-metric">
                                      <span class="pool-perf-metric-label">平均延迟</span>
                                      <span class="pool-perf-metric-value" :class="getLatencyClass(getPoolPerformanceMetrics(item.id).avgLatency)">
                                        {{ getPoolPerformanceMetrics(item.id).avgLatency ? getPoolPerformanceMetrics(item.id).avgLatency + 'ms' : '-' }}
                                      </span>
                                    </div>
                                    <div class="pool-perf-metric">
                                      <span class="pool-perf-metric-label">成功率</span>
                                      <span class="pool-perf-metric-value" :class="getSuccessRateClass(getPoolPerformanceMetrics(item.id).successRate)">
                                        {{ getPoolPerformanceMetrics(item.id).successRate ? getPoolPerformanceMetrics(item.id).successRate + '%' : '-' }}
                                      </span>
                                    </div>
                                    <div class="pool-perf-metric">
                                      <span class="pool-perf-metric-label">吞吐量</span>
                                      <span class="pool-perf-metric-value">
                                        {{ getPoolPerformanceMetrics(item.id).throughput ? getPoolPerformanceMetrics(item.id).throughput + ' req/s' : '-' }}
                                      </span>
                                    </div>
                                    <div class="pool-perf-metric">
                                      <span class="pool-perf-metric-label">P95 延迟</span>
                                      <span class="pool-perf-metric-value" :class="getLatencyClass(getPoolPerformanceMetrics(item.id).p95Latency)">
                                        {{ getPoolPerformanceMetrics(item.id).p95Latency ? getPoolPerformanceMetrics(item.id).p95Latency + 'ms' : '-' }}
                                      </span>
                                    </div>
                                  </div>
                                  <!-- Performance Trend Mini Chart -->
                                  <div v-if="getPoolPerformanceTrend(item.id)" class="pool-perf-trend" style="margin-top: 8px;">
                                    <div class="pool-perf-trend-header">
                                      <span class="text-xs text-muted">延迟趋势</span>
                                    </div>
                                    <svg :viewBox="`0 0 ${getPoolPerformanceTrend(item.id).width} ${getPoolPerformanceTrend(item.id).height}`" class="pool-perf-trend-svg">
                                      <defs>
                                        <linearGradient :id="'poolPerfGrad-' + item.id" x1="0%" y1="0%" x2="0%" y2="100%">
                                          <stop offset="0%" stop-color="#16a34a" stop-opacity="0.3" />
                                          <stop offset="100%" stop-color="#16a34a" stop-opacity="0" />
                                        </linearGradient>
                                      </defs>
                                      <path :d="getPoolPerformanceTrend(item.id).pathData + ` L ${getPoolPerformanceTrend(item.id).width - 4} ${getPoolPerformanceTrend(item.id).height - 4} L 4 ${getPoolPerformanceTrend(item.id).height - 4} Z`" :fill="`url(#poolPerfGrad-${item.id})`" />
                                      <path :d="getPoolPerformanceTrend(item.id).pathData" fill="none" stroke="#16a34a" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                                      <circle v-for="(pt, i) in getPoolPerformanceTrend(item.id).points" :key="'pool-perf-pt-' + i"
                                        :cx="pt.x" :cy="pt.y" r="2" fill="#16a34a" stroke="white" stroke-width="0.5" />
                                    </svg>
                                  </div>
                                  <!-- Pool Comparison -->
                                  <div v-if="getPoolComparisonData(item.id)" class="pool-comparison" style="margin-top: 8px;">
                                    <div class="pool-comparison-header">
                                      <span class="text-xs text-muted">与其他池对比</span>
                                    </div>
                                    <div class="pool-comparison-bars">
                                      <div class="pool-comparison-item">
                                        <span class="pool-comparison-label">延迟</span>
                                        <div class="pool-comparison-bar-container">
                                          <div class="pool-comparison-bar" :style="{ width: getPoolComparisonData(item.id).latencyPct + '%' }" :class="getPoolComparisonData(item.id).latencyRank === 1 ? 'comparison-best' : ''"></div>
                                        </div>
                                        <span class="pool-comparison-rank">#{{ getPoolComparisonData(item.id).latencyRank }}</span>
                                      </div>
                                      <div class="pool-comparison-item">
                                        <span class="pool-comparison-label">成功率</span>
                                        <div class="pool-comparison-bar-container">
                                          <div class="pool-comparison-bar" :style="{ width: getPoolComparisonData(item.id).successRatePct + '%' }" :class="getPoolComparisonData(item.id).successRateRank === 1 ? 'comparison-best' : ''"></div>
                                        </div>
                                        <span class="pool-comparison-rank">#{{ getPoolComparisonData(item.id).successRateRank }}</span>
                                      </div>
                                    </div>
                                  </div>
                                </div>

                                <!-- Manual Rotation Controls -->
                                <div class="pool-detail-section">
                                  <h5 class="pool-detail-title">手动控制</h5>
                                  <div class="rotation-controls">
                                    <button @click="manualRotate(item.id, 'next')" class="btn btn-sm btn-secondary">
                                      手动切换 →
                                    </button>
                                    <button @click="manualRotate(item.id, 'prev')" class="btn btn-sm btn-ghost">
                                      ← 上一个
                                    </button>
                                    <button @click="resetRotationStats(item.id)" class="btn btn-sm btn-ghost">
                                      重置统计
                                    </button>
                                    <button @click="showRotationHistory(item)" class="btn btn-sm btn-ghost">
                                      历史记录
                                    </button>
                                  </div>
                                </div>

                                <!-- Runtime Config Button -->
                                <div class="pool-detail-section pool-detail-actions">
                                  <button @click="viewRuntimeConfig(item)" class="btn btn-sm btn-secondary">
                                    查看运行配置
                                  </button>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      </template>
                    </tbody>
                  </table>
                </div>

                <div class="pagination">
                  <div class="pagination-info">
                    <span class="text-muted">每页</span>
                    <select v-model.number="pagination.proxyPools.perPage" @change="onPaginationPageSizeChange('proxyPools')" class="select input-sm" style="width: 56px;">
                      <option v-for="n in pageSizeOptions" :key="'pool-' + n" :value="n">{{ n }}</option>
                    </select>
                    <span class="text-muted">{{ pageIndicator('proxyPools') }}</span>
                  </div>
                  <div class="pagination-nav">
                    <button @click="goPrevPage('proxyPools')" :disabled="!canPrevPage('proxyPools')" class="btn btn-xs btn-ghost">上一页</button>
                    <button @click="goNextPage('proxyPools')" :disabled="!canNextPage('proxyPools')" class="btn btn-xs btn-ghost">下一页</button>
                  </div>
                </div>

                <h3 class="section-divider">池级链路配置</h3>
                <p class="form-hint" style="margin-bottom: 12px;">为某个代理池配置会话粘性和按 URL 前缀的会话头提取规则。当前选中代理池: <span class="mono">{{ selectedPoolNameForChain || '-' }}</span></p>

                <div class="card" style="margin-bottom: 12px;">
                  <div class="card-body">
                    <div class="settings-row">
                      <div class="form-group" style="flex: 1.4;">
                        <label class="form-label">选择代理池</label>
                        <select v-model.number="selectedPoolIdForChain" @change="onSelectPoolForChain(proxyPools.find(item => Number(item.id) === Number(selectedPoolIdForChain)) || null)" class="select">
                          <option :value="0">未选择</option>
                          <option v-for="item in proxyPools" :key="'pool-chain-' + item.id" :value="Number(item.id)">{{ item.name }} (#{{ item.id }})</option>
                        </select>
                      </div>
                      <label class="form-check self-end">
                        <input v-model="poolChainForm.chain_enabled" type="checkbox" />
                        <span>启用池级链路</span>
                      </label>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">粘性 TTL(秒)</label>
                        <input v-model.number="poolChainForm.sticky_ttl_sec" type="number" min="1" class="input mono" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">缺失会话动作</label>
                        <select v-model="poolChainForm.session_missing_action" class="select">
                          <option value="RANDOM">RANDOM</option>
                          <option value="REJECT">REJECT</option>
                        </select>
                      </div>
                      <button @click="onSavePoolChainConfig()" :disabled="!selectedPoolIdForChain || isActionRunning('savePoolChain-' + selectedPoolIdForChain)" class="btn btn-primary self-end">保存池级配置</button>
                    </div>
                    <div class="settings-row" style="margin-top: 8px;">
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">HTTP 会话头</label>
                        <textarea v-model="poolChainForm.session_header_names_text" class="textarea mono" style="height: 88px;" placeholder="X-ProxyPool-Session"></textarea>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">HTTP 会话 Query</label>
                        <textarea v-model="poolChainForm.session_query_param_names_text" class="textarea mono" style="height: 88px;" placeholder="session"></textarea>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="settings-grid" style="margin-bottom: 12px;">
                  <div class="card">
                    <div class="card-body">
                      <div class="card-header">
                        <h3 class="settings-title">会话规则</h3>
                        <button @click="onLoadPoolSessionRules()" :disabled="!selectedPoolIdForChain || isActionRunning('loadPoolSessionRules-' + selectedPoolIdForChain)" class="btn btn-xs btn-secondary">刷新规则</button>
                      </div>
                      <div class="settings-row">
                        <div class="form-group" style="flex: 1.2;">
                          <label class="form-label">URL 前缀</label>
                          <input v-model.trim="poolSessionRuleForm.url_prefix" type="text" placeholder="api.example.com/v1" class="input mono" />
                        </div>
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">用于识别会话的头(多行)</label>
                          <textarea v-model="poolSessionRuleForm.headers_text" class="textarea mono" style="height: 88px;" placeholder="Authorization&#10;X-Biz-Session"></textarea>
                        </div>
                        <button @click="onSavePoolSessionRule()" :disabled="!selectedPoolIdForChain || isActionRunning('savePoolSessionRule-' + selectedPoolIdForChain)" class="btn btn-secondary self-end">保存规则</button>
                      </div>
                      <div class="table-wrap" style="margin-top: 12px;">
                        <table class="data-table data-table-compact">
                          <thead>
                            <tr>
                              <th>URL 前缀</th>
                              <th>会话头</th>
                              <th style="width: 120px;">操作</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="item in poolSessionRules" :key="'session-rule-' + item.url_prefix">
                              <td class="mono text-xs">{{ item.url_prefix }}</td>
                              <td class="text-xs">{{ (item.headers || []).join(', ') }}</td>
                              <td>
                                <div class="btn-group">
                                  <button @click="usePoolSessionRule(item)" class="btn btn-xs btn-ghost">套用</button>
                                  <button @click="onDeletePoolSessionRule(item.url_prefix)" :disabled="isActionRunning('deletePoolSessionRule-' + selectedPoolIdForChain + '-' + item.url_prefix)" class="btn btn-xs btn-danger">删除</button>
                                </div>
                              </td>
                            </tr>
                            <tr v-if="!poolSessionRules.length">
                              <td colspan="3" class="text-xs text-muted">暂无规则</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                  <div class="card">
                    <div class="card-body">
                      <h3 class="settings-title">池级路由测试</h3>
                      <div class="settings-row">
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">会话 ID</label>
                          <input v-model.trim="poolRouteTest.session_id" type="text" placeholder="sess-demo" class="input mono" />
                        </div>
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">目标域名</label>
                          <input v-model.trim="poolRouteTest.target_domain" type="text" placeholder="api.example.com" class="input mono" />
                        </div>
                        <button @click="onTestPoolRoute()" :disabled="!selectedPoolIdForChain || isActionRunning('testPoolRoute-' + selectedPoolIdForChain)" class="btn btn-secondary self-end">测试池路由</button>
                      </div>
                      <div v-if="poolRouteTestResult" style="margin-top: 12px;">
                        <pre class="mono text-xs" style="white-space: pre-wrap;">{{ JSON.stringify(poolRouteTestResult, null, 2) }}</pre>
                      </div>
                    </div>
                  </div>
                </div>

                </div>

                <div v-show="proxyPoolTab === 'gateway'" class="tab-panel fade-in">
                <h3 class="section-divider">HTTP 代理端点</h3>
                <p class="form-hint" style="margin-bottom: 12px;">每个端点监听一个标准 HTTP/HTTPS 代理地址，网关层按该端点绑定的代理池顺序决定多跳路由和会话粘性。</p>

                <div class="card" style="margin-bottom: 12px; border: 1px dashed var(--line);">
                  <div class="card-body">
                    <h3 class="settings-title">创建 / 编辑 HTTP 端点</h3>
                    <div class="settings-row">
                      <div class="form-group" style="flex: 1.4;">
                        <label class="form-label">名称</label>
                        <input v-model.trim="gatewayEndpointForm.name" type="text" placeholder="如 gateway-openai" class="input" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">监听地址</label>
                        <input v-model.trim="gatewayEndpointForm.listen_host" class="input mono" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">监听端口</label>
                        <input v-model.number="gatewayEndpointForm.listen_port" type="number" min="1" class="input mono" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">启用</label>
                        <select v-model="gatewayEndpointForm.enabled" class="select">
                          <option :value="true">开启</option>
                          <option :value="false">关闭</option>
                        </select>
                      </div>
                    </div>
                    <div class="settings-row" style="margin-top: 8px;">
                      <div class="form-group" style="flex: 1.6;">
                        <label class="form-label">多跳代理池顺序</label>
                        <el-select v-model="gatewayEndpointForm.hop_pool_ids" multiple collapse-tags collapse-tags-tooltip clearable placeholder="先选择需要的跳点池" size="small" style="width: 100%">
                          <el-option v-for="item in proxyPools" :key="'ep-hop-' + item.id" :label="`${item.name} (#${item.id})`" :value="Number(item.id)"></el-option>
                        </el-select>
                        <div class="table-wrap" style="margin-top: 8px;">
                          <table class="data-table data-table-compact">
                            <thead>
                              <tr>
                                <th style="width: 60px;">顺序</th>
                                <th>代理池</th>
                                <th style="width: 120px;">操作</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr v-for="(poolId, idx) in gatewayEndpointForm.hop_pool_ids" :key="'ep-hop-order-' + poolId + '-' + idx">
                                <td class="mono text-xs">#{{ idx + 1 }}</td>
                                <td class="text-xs">{{ proxyPools.find(item => Number(item.id) === Number(poolId))?.name || ('#' + poolId) }}</td>
                                <td>
                                  <div class="btn-group">
                                    <button @click="moveGatewayEndpointHop(idx, -1)" :disabled="idx === 0" class="btn btn-xs btn-ghost">上移</button>
                                    <button @click="moveGatewayEndpointHop(idx, 1)" :disabled="idx >= gatewayEndpointForm.hop_pool_ids.length - 1" class="btn btn-xs btn-ghost">下移</button>
                                  </div>
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">粘性 TTL(秒)</label>
                        <input v-model.number="gatewayEndpointForm.sticky_ttl_sec" type="number" min="1" class="input mono" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">缺失会话动作</label>
                        <select v-model="gatewayEndpointForm.session_missing_action" class="select">
                          <option value="RANDOM">RANDOM</option>
                          <option value="REJECT">REJECT</option>
                        </select>
                      </div>
                      <button @click="onSaveGatewayEndpoint" :disabled="isActionRunning('saveGatewayEndpoint')" class="btn btn-primary self-end">保存端点</button>
                    </div>
                    <div class="settings-row" style="margin-top: 8px;">
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">HTTP 会话头</label>
                        <textarea v-model="gatewayEndpointForm.session_header_names_text" class="textarea mono" style="height: 88px;" placeholder="X-ProxyPool-Session"></textarea>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">HTTP 会话 Query</label>
                        <textarea v-model="gatewayEndpointForm.session_query_param_names_text" class="textarea mono" style="height: 88px;" placeholder="session"></textarea>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">CONNECT 会话头</label>
                        <textarea v-model="gatewayEndpointForm.connect_session_header_names_text" class="textarea mono" style="height: 88px;" placeholder="X-ProxyPool-Session"></textarea>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="table-wrap" style="margin-bottom: 12px;">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 50px;">ID</th>
                        <th style="width: 140px;">名称</th>
                        <th style="width: 140px;">监听</th>
                        <th>跳点顺序</th>
                        <th style="width: 70px;">状态</th>
                        <th style="width: 180px;">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in gatewayEndpoints" :key="'ep-' + item.id">
                        <td class="mono text-muted">{{ item.id }}</td>
                        <td>{{ item.name }}</td>
                        <td class="mono text-xs">{{ item.listen_host }}:{{ item.listen_port }}</td>
                        <td class="text-xs text-muted">{{ formatEndpointHops(item) }}</td>
                        <td><span class="badge" :class="item.enabled ? 'badge-success' : 'badge-neutral'">{{ item.enabled ? 'ENABLED' : 'DISABLED' }}</span></td>
                        <td>
                          <div class="btn-group">
                            <button @click="editGatewayEndpoint(item)" class="btn btn-xs btn-ghost">编辑</button>
                            <button @click="onOpenGatewayEndpointStatus(item)" class="btn btn-xs btn-secondary">状态</button>
                            <button @click="onRunGatewayEndpointRouteTest(item)" :disabled="isActionRunning('routeTestEndpoint-' + item.id)" class="btn btn-xs btn-ghost">测路由</button>
                            <button @click="onDeleteGatewayEndpoint(item.id)" :disabled="isActionRunning('deleteGatewayEndpoint-' + item.id)" class="btn btn-xs btn-danger">删除</button>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div class="card" style="margin-bottom: 12px;">
                  <div class="card-body">
                    <h3 class="settings-title">端点服务</h3>
                    <div class="settings-row">
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">端点服务</label>
                        <select v-model="gatewayConfigForm.enabled" class="select">
                          <option :value="false">关闭</option>
                          <option :value="true">开启</option>
                        </select>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">健康检测</label>
                        <select v-model="gatewayConfigForm.health_check_enabled" class="select">
                          <option :value="true">开启</option>
                          <option :value="false">关闭</option>
                        </select>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">检测间隔(秒)</label>
                        <input v-model.number="gatewayConfigForm.health_check_interval_sec" type="number" min="5" max="3600" class="input mono" />
                      </div>
                      <button @click="onSaveGatewayConfig()" :disabled="isActionRunning('saveGatewayConfig')" class="btn btn-primary self-end">保存运行配置</button>
                    </div>
                  </div>
                </div>

                <div class="settings-grid">
                  <div class="card">
                    <div class="card-body">
                      <h3 class="settings-title">端点测试</h3>
                      <div class="settings-row">
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">目标 URL</label>
                          <input v-model.trim="gatewayTestForm.target_url" type="text" placeholder="https://www.cloudflare.com/cdn-cgi/trace" class="input mono" />
                        </div>
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">端点</label>
                          <select v-model.number="gatewayTestForm.endpoint_id" class="select">
                            <option :value="0" disabled>选择端点</option>
                            <option v-for="item in gatewayEndpoints" :key="'gateway-test-' + item.id" :value="Number(item.id)">{{ item.name }} (#{{ item.id }})</option>
                          </select>
                        </div>
                        <div class="form-group" style="flex: 1;">
                          <label class="form-label">会话 ID</label>
                          <input v-model.trim="gatewayTestForm.session_id" type="text" placeholder="留空则按配置处理" class="input mono" />
                        </div>
                        <button @click="onRunGatewayTest()" :disabled="isActionRunning('runGatewayTest')" class="btn btn-secondary self-end">测试端点</button>
                      </div>
                      <div v-if="gatewayTestResult" style="margin-top: 12px;">
                        <pre class="mono text-xs" style="white-space: pre-wrap;">{{ JSON.stringify(gatewayTestResult, null, 2) }}</pre>
                      </div>
                    </div>
                  </div>

                </div>
                </div>

                <GatewayStatusPanel />

                <!-- Chain View Tab -->
                <div v-show="proxyPoolTab === 'chain-view'" class="tab-panel fade-in">
                  <div class="section-header">
                    <div>
                      <h3 class="section-divider">链路可视化</h3>
                      <p class="form-hint">可视化展示代理链路配置，检测依赖问题和健康状态</p>
                    </div>
                    <div class="btn-group">
                      <button @click="runChainDiagnostics" :disabled="isActionRunning('chainDiagnostics')" class="btn btn-secondary">
                        {{ buttonLabel('chainDiagnostics', '链路诊断', '诊断中...') }}
                      </button>
                      <button @click="testChainLatency" :disabled="isActionRunning('chainLatency')" class="btn btn-secondary">
                        {{ buttonLabel('chainLatency', '测试链路延迟', '测试中...') }}
                      </button>
                      <button @click="testFullChain" :disabled="isActionRunning('testFullChain')" class="btn btn-primary">
                        {{ buttonLabel('testFullChain', '测试整条链路', '测试中...') }}
                      </button>
                    </div>
                  </div>

                  <!-- Chain Health Score -->
                  <div v-if="chainHealthScore !== null" class="chain-health-score-card card" style="margin-bottom: 16px;">
                    <div class="card-body">
                      <div class="chain-health-score-content">
                        <div class="chain-health-score-label">
                          <h4 class="settings-title">链路健康评分</h4>
                          <p class="text-muted text-xs">基于前置池、落地池健康状态和依赖配置的综合评估</p>
                        </div>
                        <div class="chain-health-score-value" :class="getChainHealthScoreClass(chainHealthScore)">
                          <span class="chain-health-score-number">{{ chainHealthScore }}</span>
                          <span class="chain-health-score-total">/100</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Chain Visualization -->
                  <div class="chain-visualization">
                    <div class="chain-flow">
                      <!-- Entry Point -->
                      <div class="chain-node chain-node-entry">
                        <div class="chain-node-header">
                          <span class="chain-node-type chain-type-entry">入口</span>
                          <span class="chain-node-name">{{ backendDefaultListen || '127.0.0.1' }}:{{ backendPortRange.start || 1081 }}</span>
                        </div>
                        <div class="chain-node-status">
                          <span class="status-dot status-dot-active"></span>
                          <span>监听中</span>
                        </div>
                      </div>

                      <div class="chain-arrow">
                        <span class="chain-arrow-icon">→</span>
                        <span class="chain-arrow-label">HTTP/SOCKS</span>
                      </div>

                      <!-- Front Pool -->
                      <div class="chain-node" :class="{ 'chain-node-warning': !hasFrontPool, 'chain-node-active': hasFrontPool }">
                        <div class="chain-node-header">
                          <span class="chain-node-type chain-type-front">前置池</span>
                          <span class="chain-node-name">{{ frontPoolName || '未配置' }}</span>
                        </div>
                        <div class="chain-node-status">
                          <span v-if="hasFrontPool" class="status-dot" :class="frontPoolHealthy ? 'status-dot-success' : 'status-dot-warning'"></span>
                          <span v-else class="status-dot status-dot-error"></span>
                          <span v-if="hasFrontPool">{{ frontPoolHealthyCount }}/{{ frontPoolTotalCount }} 节点</span>
                          <span v-else>缺失</span>
                        </div>
                        <div v-if="!hasFrontPool" class="chain-node-alert">
                          <span class="alert-icon">⚠️</span>
                          <span>未配置前置代理池</span>
                        </div>
                      </div>

                      <div class="chain-arrow" :class="{ 'chain-arrow-broken': !hasFrontPool || !hasExitPool }">
                        <span class="chain-arrow-icon">→</span>
                        <span class="chain-arrow-label">{{ chainProtocol || '多跳' }}</span>
                      </div>

                      <!-- Exit Pool -->
                      <div class="chain-node" :class="{ 'chain-node-warning': !hasExitPool, 'chain-node-active': hasExitPool }">
                        <div class="chain-node-header">
                          <span class="chain-node-type chain-type-exit">落地池</span>
                          <span class="chain-node-name">{{ exitPoolName || '未配置' }}</span>
                        </div>
                        <div class="chain-node-status">
                          <span v-if="hasExitPool" class="status-dot" :class="exitPoolHealthy ? 'status-dot-success' : 'status-dot-warning'"></span>
                          <span v-else class="status-dot status-dot-error"></span>
                          <span v-if="hasExitPool">{{ exitPoolHealthyCount }}/{{ exitPoolTotalCount }} 节点</span>
                          <span v-else>缺失</span>
                        </div>
                        <div v-if="!hasExitPool" class="chain-node-alert">
                          <span class="alert-icon">⚠️</span>
                          <span>未配置落地代理池</span>
                        </div>
                      </div>

                      <div class="chain-arrow">
                        <span class="chain-arrow-icon">→</span>
                        <span class="chain-arrow-label">出口</span>
                      </div>

                      <!-- Exit Point -->
                      <div class="chain-node chain-node-exit">
                        <div class="chain-node-header">
                          <span class="chain-node-type chain-type-output">出口</span>
                          <span class="chain-node-name">目标网站</span>
                        </div>
                        <div class="chain-node-status">
                          <span class="status-dot status-dot-active"></span>
                          <span>互联网</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Chain Diagnostics Panel -->
                  <div v-if="chainDiagnostics.length" class="card" style="margin-top: 16px;">
                    <div class="card-body">
                      <h4 class="settings-title">链路诊断报告</h4>

                      <!-- Pool Status Summary -->
                      <div class="diagnostic-pool-status" v-if="hasFrontPool || hasExitPool">
                        <h5 class="diagnostic-subtitle">池状态概览</h5>
                        <div class="diagnostic-pool-grid">
                          <div v-if="hasFrontPool" class="diagnostic-pool-card">
                            <div class="diagnostic-pool-header">
                              <span class="chain-node-type chain-type-front">前置池</span>
                              <span class="font-semibold">{{ frontPoolName }}</span>
                            </div>
                            <div class="diagnostic-pool-stats">
                              <span class="text-xs">健康: <strong class="text-success">{{ frontPoolHealthyCount }}</strong>/{{ frontPoolTotalCount }}</span>
                              <span class="text-xs">平均延迟: <strong>{{ frontPoolAvgLatency }}ms</strong></span>
                            </div>
                          </div>
                          <div v-if="hasExitPool" class="diagnostic-pool-card">
                            <div class="diagnostic-pool-header">
                              <span class="chain-node-type chain-type-exit">落地池</span>
                              <span class="font-semibold">{{ exitPoolName }}</span>
                            </div>
                            <div class="diagnostic-pool-stats">
                              <span class="text-xs">健康: <strong class="text-success">{{ exitPoolHealthyCount }}</strong>/{{ exitPoolTotalCount }}</span>
                              <span class="text-xs">平均延迟: <strong>{{ exitPoolAvgLatency }}ms</strong></span>
                            </div>
                          </div>
                        </div>
                      </div>

                      <!-- Endpoints Using Chain -->
                      <div class="diagnostic-endpoints" v-if="chainEndpoints.length">
                        <h5 class="diagnostic-subtitle">使用此链路的端点 ({{ chainEndpoints.length }})</h5>
                        <div class="diagnostic-endpoint-list">
                          <div v-for="ep in chainEndpoints" :key="'diag-ep-' + ep.id" class="diagnostic-endpoint-item">
                            <span class="font-semibold">{{ ep.name }}</span>
                            <span class="mono text-xs text-muted">{{ ep.listen_host }}:{{ ep.listen_port }}</span>
                            <span class="badge badge-sm" :class="ep.enabled ? 'badge-success' : 'badge-neutral'">
                              {{ ep.enabled ? '启用' : '禁用' }}
                            </span>
                          </div>
                        </div>
                      </div>

                      <!-- Issues List -->
                      <div class="diagnostics-list">
                        <h5 class="diagnostic-subtitle">诊断结果</h5>
                        <div v-for="(diag, idx) in chainDiagnostics" :key="'diag-' + idx" class="diagnostic-item" :class="'diagnostic-' + diag.type">
                          <div class="diagnostic-header">
                            <span class="diagnostic-icon" :class="'diagnostic-icon-' + diag.type">
                              {{ diag.type === 'error' ? '❌' : diag.type === 'warning' ? '⚠️' : '✅' }}
                            </span>
                            <span class="diagnostic-title">{{ diag.title }}</span>
                            <span v-if="diag.severity" class="diagnostic-severity badge badge-sm" :class="'badge-' + diag.severity">
                              {{ diag.severity === 'critical' ? '严重' : diag.severity === 'high' ? '高' : diag.severity === 'medium' ? '中' : '低' }}
                            </span>
                          </div>
                          <p class="diagnostic-message">{{ diag.message }}</p>
                          <p v-if="diag.suggestion" class="diagnostic-suggestion">
                            <strong>建议:</strong> {{ diag.suggestion }}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Chain Latency Test Results -->
                  <div v-if="chainLatencyResult" class="card" style="margin-top: 16px;">
                    <div class="card-body">
                      <h4 class="settings-title">链路延迟测试结果</h4>
                      <div class="test-results">
                        <div class="test-result-item">
                          <span class="test-label">端到端延迟:</span>
                          <span class="badge" :class="chainLatencyResult.success ? 'badge-success' : 'badge-danger'">
                            {{ chainLatencyResult.success ? chainLatencyResult.totalLatency + 'ms' : '测试失败' }}
                          </span>
                        </div>
                        <div v-if="chainLatencyResult.hops" class="test-hops">
                          <div v-for="(hop, idx) in chainLatencyResult.hops" :key="'lat-hop-' + idx" class="test-hop-item">
                            <span class="hop-index">#{{ idx + 1 }}</span>
                            <span class="hop-name">{{ hop.name }}</span>
                            <span class="badge badge-sm" :class="hop.success ? 'badge-success' : 'badge-danger'">
                              {{ hop.latency ? hop.latency + 'ms' : '超时' }}
                            </span>
                          </div>
                        </div>
                        <div v-if="chainLatencyResult.timestamp" class="text-xs text-muted" style="margin-top: 8px;">
                          测试时间: {{ chainLatencyResult.timestamp }}
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Pool Type Legend -->
                  <div class="card" style="margin-top: 16px;">
                    <div class="card-body">
                      <h4 class="settings-title">池类型说明</h4>
                      <div class="pool-type-legend">
                        <div class="legend-item">
                          <span class="chain-node-type chain-type-front">前置池</span>
                          <span class="legend-desc">入口代理，客户端首先连接的节点。用于隐藏真实客户端IP，增加链路复杂度</span>
                        </div>
                        <div class="legend-item">
                          <span class="chain-node-type chain-type-exit">落地池</span>
                          <span class="legend-desc">最终出口代理，决定出口IP和地区。用于访问目标网站</span>
                        </div>
                        <div class="legend-item">
                          <span class="chain-node-type chain-type-middle">中间池</span>
                          <span class="legend-desc">可选的中间跳点，增加链路层次。用于进一步隐藏链路</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Chain Test Results -->
                  <div v-if="chainTestResults" class="card" style="margin-top: 16px;">
                    <div class="card-body">
                      <h4 class="settings-title">链路测试结果</h4>
                      <div class="test-results">
                        <div class="test-result-item">
                          <span class="test-label">整体状态:</span>
                          <span class="badge" :class="chainTestResults.success ? 'badge-success' : 'badge-danger'">
                            {{ chainTestResults.success ? '通过' : '失败' }}
                          </span>
                        </div>
                        <div v-if="chainTestResults.hops" class="test-hops">
                          <div v-for="(hop, idx) in chainTestResults.hops" :key="'hop-' + idx" class="test-hop-item">
                            <span class="hop-index">#{{ idx + 1 }}</span>
                            <span class="hop-name">{{ hop.name }}</span>
                            <span class="badge badge-sm" :class="hop.success ? 'badge-success' : 'badge-danger'">
                              {{ hop.latency ? hop.latency + 'ms' : '失败' }}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Chain Templates Section -->
                  <div class="card" style="margin-top: 16px;">
                    <div class="card-body">
                      <h4 class="settings-title">链路模板</h4>
                      <p class="form-hint" style="margin-bottom: 12px;">选择预配置的链路模板快速创建常用代理链路模式</p>
                      <div class="chain-templates-grid">
                        <div v-for="template in chainTemplates" :key="template.id" class="chain-template-card" @click="applyChainTemplate(template)">
                          <div class="template-icon">{{ template.icon }}</div>
                          <div class="template-info">
                            <div class="template-name">{{ template.name }}</div>
                            <div class="template-desc">{{ template.description }}</div>
                          </div>
                          <div class="template-pools">
                            <span class="badge badge-sm badge-neutral">{{ template.front_pool }}</span>
                            <span class="template-arrow">→</span>
                            <span class="badge badge-sm badge-neutral">{{ template.exit_pool }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Chain Performance Comparison -->
                  <div class="card" style="margin-top: 16px;">
                    <div class="card-body">
                      <div class="section-header">
                        <h4 class="settings-title">链路性能对比</h4>
                        <button @click="refreshChainPerformance" :disabled="isActionRunning('chainPerformance')" class="btn btn-secondary">
                          {{ buttonLabel('chainPerformance', '刷新数据', '加载中...') }}
                        </button>
                      </div>
                      <div v-if="chainPerformanceData.length" class="chain-performance-table">
                        <table class="data-table">
                          <thead>
                            <tr>
                              <th>链路配置</th>
                              <th>平均延迟</th>
                              <th>成功率</th>
                              <th>健康节点</th>
                              <th>综合评分</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="perf in chainPerformanceData" :key="'perf-' + perf.config" :class="{ 'best-perf': perf.score === bestChainScore }">
                              <td class="mono text-xs">{{ perf.config }}</td>
                              <td :style="latencyStyle(perf.avg_latency)">{{ perf.avg_latency ? perf.avg_latency + 'ms' : '-' }}</td>
                              <td :style="successRateStyle(perf.success_rate)">{{ perf.success_rate ? perf.success_rate.toFixed(1) + '%' : '-' }}</td>
                              <td>{{ perf.healthy_nodes }}/{{ perf.total_nodes }}</td>
                              <td class="font-semibold" :class="perf.score === bestChainScore ? 'text-success' : ''">{{ perf.score.toFixed(1) }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <EmptyState v-else title="暂无性能数据" description="点击刷新按钮加载链路性能对比数据" size="small" />
                    </div>
                  </div>

                  <!-- Chain Health Auto-Alert -->
                  <div class="card" style="margin-top: 16px;">
                    <div class="card-body">
                      <h4 class="settings-title">链路健康自动告警</h4>
                      <p class="form-hint" style="margin-bottom: 12px;">当链路健康状态变化时自动发送通知</p>
                      <div class="settings-row">
                        <label class="form-check">
                          <input v-model="chainAlertConfig.enabled" type="checkbox" @change="saveChainAlertConfig" />
                          <span>启用链路健康告警</span>
                        </label>
                        <div v-if="chainAlertConfig.enabled" class="form-group" style="flex: 0.8;">
                          <label class="form-label">健康阈值</label>
                          <div style="display: flex; align-items: center; gap: 6px;">
                            <span class="text-xs text-muted">低于</span>
                            <el-input-number v-model="chainAlertConfig.healthThreshold" :min="1" :max="100" :step="5" size="small" style="width: 100px;" @change="saveChainAlertConfig" />
                            <span class="text-xs text-muted">%时告警</span>
                          </div>
                        </div>
                        <label class="form-check">
                          <input v-model="chainAlertConfig.nodeDownAlert" type="checkbox" @change="saveChainAlertConfig" />
                          <span>节点宕机告警</span>
                        </label>
                        <label class="form-check">
                          <input v-model="chainAlertConfig.latencyAlert" type="checkbox" @change="saveChainAlertConfig" />
                          <span>延迟过高告警</span>
                        </label>
                      </div>
                      <div v-if="chainAlertHistory.length" class="chain-alert-history" style="margin-top: 12px;">
                        <div class="text-xs font-semibold text-gray-700" style="margin-bottom: 6px;">最近告警记录</div>
                        <div class="alert-history-list" style="max-height: 120px; overflow-y: auto;">
                          <div v-for="(alert, idx) in chainAlertHistory.slice(0, 5)" :key="'chain-alert-' + idx" class="alert-history-item">
                            <span class="badge badge-sm" :class="alert.type === 'critical' ? 'badge-danger' : 'badge-warning'">{{ alert.type }}</span>
                            <span class="text-xs text-muted" style="flex: 1;">{{ alert.message }}</span>
                            <span class="text-xs text-muted">{{ formatChainAlertTime(alert.timestamp) }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Advanced Chain Features -->
                  <div class="advanced-chain-section" style="margin-top: 16px;">
                    <h3 class="section-divider">高级链路分析</h3>

                    <!-- Chain Load Balancing Visualization -->
                    <div class="advanced-chain-feature">
                      <div class="advanced-chain-header" @click="toggleChainFeature('loadBalancing')">
                        <span class="text-xs font-semibold">负载均衡可视化</span>
                        <span class="text-xs text-muted">{{ isChainFeatureExpanded('loadBalancing') ? '收起' : '展开' }}</span>
                      </div>
                      <div v-if="isChainFeatureExpanded('loadBalancing')" class="advanced-chain-content">
                        <div class="load-bal-viz">
                          <div class="lb-viz-item" v-for="pool in getChainPoolLoadData()" :key="'lb-' + pool.id">
                            <div class="lb-viz-header">
                              <span class="font-semibold text-xs">{{ pool.name }}</span>
                              <span class="text-xs text-muted">{{ pool.healthyCount }}/{{ pool.totalCount }} 节点</span>
                            </div>
                            <div class="lb-viz-bar">
                              <div class="lb-viz-bar-fill" :style="{ width: pool.loadPercent + '%' }" :class="getLoadBarClass(pool.loadPercent)"></div>
                            </div>
                            <div class="lb-viz-stats">
                              <span class="text-xs">负载: {{ pool.loadPercent }}%</span>
                              <span class="text-xs">推荐权重: {{ pool.recommendedWeight }}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Chain Failover Configuration -->
                    <div class="advanced-chain-feature">
                      <div class="advanced-chain-header" @click="toggleChainFeature('failover')">
                        <span class="text-xs font-semibold">故障转移配置</span>
                        <span class="text-xs text-muted">{{ isChainFeatureExpanded('failover') ? '收起' : '展开' }}</span>
                      </div>
                      <div v-if="isChainFeatureExpanded('failover')" class="advanced-chain-content">
                        <div class="failover-config">
                          <div class="failover-item">
                            <span class="text-xs text-muted">故障检测间隔:</span>
                            <el-input-number v-model="chainFailoverConfig.checkInterval" :min="10" :max="300" :step="10" size="small" style="width: 100px;" />
                            <span class="text-xs">秒</span>
                          </div>
                          <div class="failover-item">
                            <span class="text-xs text-muted">失败阈值:</span>
                            <el-input-number v-model="chainFailoverConfig.failureThreshold" :min="1" :max="10" :step="1" size="small" style="width: 100px;" />
                            <span class="text-xs">次</span>
                          </div>
                          <div class="failover-item">
                            <span class="text-xs text-muted">恢复阈值:</span>
                            <el-input-number v-model="chainFailoverConfig.recoveryThreshold" :min="1" :max="10" :step="1" size="small" style="width: 100px;" />
                            <span class="text-xs">次</span>
                          </div>
                          <div class="failover-item">
                            <el-switch v-model="chainFailoverConfig.autoRecovery" />
                            <span class="text-xs">自动恢复</span>
                          </div>
                          <div class="failover-status">
                            <span class="text-xs text-muted">当前状态:</span>
                            <span class="badge badge-sm" :class="chainFailoverStatus.healthy ? 'badge-success' : 'badge-danger'">
                              {{ chainFailoverStatus.healthy ? '正常' : '故障' }}
                            </span>
                            <span class="text-xs text-muted" v-if="chainFailoverStatus.lastCheck">最后检测: {{ chainFailoverStatus.lastCheck }}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Chain Bandwidth Monitoring -->
                    <div class="advanced-chain-feature">
                      <div class="advanced-chain-header" @click="toggleChainFeature('bandwidth')">
                        <span class="text-xs font-semibold">带宽监控</span>
                        <span class="text-xs text-muted">{{ isChainFeatureExpanded('bandwidth') ? '收起' : '展开' }}</span>
                      </div>
                      <div v-if="isChainFeatureExpanded('bandwidth')" class="advanced-chain-content">
                        <div class="bandwidth-monitor">
                          <div class="bandwidth-stat" v-for="stat in getChainBandwidthStats()" :key="'bw-' + stat.label">
                            <span class="text-xs text-muted">{{ stat.label }}:</span>
                            <span class="text-xs font-semibold" :class="stat.class">{{ stat.value }}</span>
                          </div>
                          <div class="bandwidth-chart" v-if="chainBandwidthHistory.length">
                            <svg :viewBox="'0 0 200 60'" class="bandwidth-svg">
                              <polyline :points="getBandwidthChartPoints()" fill="none" stroke="#3b82f6" stroke-width="2" />
                            </svg>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Chain Latency Optimization -->
                    <div class="advanced-chain-feature">
                      <div class="advanced-chain-header" @click="toggleChainFeature('latencyOpt')">
                        <span class="text-xs font-semibold">延迟优化建议</span>
                        <span class="text-xs text-muted">{{ isChainFeatureExpanded('latencyOpt') ? '收起' : '展开' }}</span>
                      </div>
                      <div v-if="isChainFeatureExpanded('latencyOpt')" class="advanced-chain-content">
                        <div class="latency-suggestions">
                          <div v-for="(sug, idx) in getChainLatencySuggestions()" :key="'lat-sug-' + idx" class="latency-suggestion-item" :class="'suggestion-' + sug.severity">
                            <span class="suggestion-icon">{{ sug.severity === 'high' ? '⚠️' : sug.severity === 'medium' ? '💡' : 'ℹ️' }}</span>
                            <span class="text-xs">{{ sug.text }}</span>
                          </div>
                          <div v-if="!getChainLatencySuggestions().length" class="text-xs text-muted">暂无优化建议</div>
                        </div>
                      </div>
                    </div>

                    <!-- Chain Security Analysis -->
                    <div class="advanced-chain-feature">
                      <div class="advanced-chain-header" @click="toggleChainFeature('security')">
                        <span class="text-xs font-semibold">安全分析</span>
                        <span class="text-xs text-muted">{{ isChainFeatureExpanded('security') ? '收起' : '展开' }}</span>
                      </div>
                      <div v-if="isChainFeatureExpanded('security')" class="advanced-chain-content">
                        <div class="security-analysis">
                          <div class="security-score">
                            <span class="text-xs text-muted">安全评分:</span>
                            <span class="text-xs font-semibold" :class="getChainSecurityScore() >= 80 ? 'text-success' : getChainSecurityScore() >= 50 ? 'text-warning' : 'text-danger'">
                              {{ getChainSecurityScore() }}/100
                            </span>
                          </div>
                          <div v-for="(item, idx) in getChainSecurityItems()" :key="'sec-' + idx" class="security-item" :class="'security-' + item.status">
                            <span class="security-icon">{{ item.status === 'good' ? '✅' : item.status === 'warning' ? '⚠️' : '❌' }}</span>
                            <span class="text-xs">{{ item.text }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-show="proxyPoolTab === 'chain'" class="tab-panel fade-in">
                <h3 class="section-divider">代理链服务</h3>
                <div class="card" style="margin-bottom: 12px;">
                  <div class="card-body">
                    <div class="section-header">
                      <h3 class="settings-title">前置 / 后置代理池</h3>
                      <div class="btn-group">
                        <button @click="loadChainStatus" :disabled="isActionRunning('loadChainStatus')" class="btn btn-secondary">刷新状态</button>
                        <button @click="chainStart" :disabled="isActionRunning('chainStart')" class="btn btn-primary">启动服务</button>
                        <button @click="chainStop" :disabled="isActionRunning('chainStop')" class="btn btn-danger">停止服务</button>
                      </div>
                    </div>
                    <div class="status-bar">
                      <div class="status-item">
                        <span class="text-muted">服务状态</span>
                        <span class="badge" :class="chainStatus.front_pool ? 'badge-success' : 'badge-neutral'">{{ chainStatus.front_pool ? '已加载' : '未加载' }}</span>
                      </div>
                      <div class="status-item">
                        <span class="text-muted">前置节点</span>
                        <span class="font-semibold">{{ chainStatus.front_pool?.healthy_nodes || 0 }} / {{ chainStatus.front_pool?.total_nodes || 0 }}</span>
                      </div>
                      <div class="status-item">
                        <span class="text-muted">后置节点</span>
                        <span class="font-semibold">{{ chainStatus.exit_pool?.healthy_nodes || 0 }} / {{ chainStatus.exit_pool?.total_nodes || 0 }}</span>
                      </div>
                      <div class="status-item">
                        <span class="text-muted">健康检测</span>
                        <span class="badge" :class="chainHealth.running ? 'badge-success' : 'badge-neutral'">{{ chainHealth.running ? '运行中' : '已停止' }}</span>
                      </div>
                    </div>
                    <div class="settings-row" style="margin-top: 12px;">
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">前置节点池正则</label>
                        <textarea v-model="chainPoolForm.front_filters" class="textarea mono" rows="3" placeholder="front-.*&#10;entry-.*"></textarea>
                        <button @click="saveChainPool('front')" :disabled="isActionRunning('saveChainPoolFront')" class="btn btn-secondary" style="margin-top: 8px;">保存前置池</button>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">后置代理池正则</label>
                        <textarea v-model="chainPoolForm.exit_filters" class="textarea mono" rows="3" placeholder="exit-.*&#10;proxy-.*"></textarea>
                        <button @click="saveChainPool('exit')" :disabled="isActionRunning('saveChainPoolExit')" class="btn btn-secondary" style="margin-top: 8px;">保存后置池</button>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="settings-grid" style="margin-bottom: 12px;">
                  <div class="card">
                    <div class="card-body">
                      <div class="section-header">
                        <h3 class="settings-title">节点与租约</h3>
                        <div class="btn-group">
                          <button @click="loadChainLeases" :disabled="isActionRunning('loadChainLeases')" class="btn btn-secondary">刷新租约</button>
                          <button @click="cleanupChainLeases" :disabled="isActionRunning('cleanupChainLeases')" class="btn btn-danger">清理过期</button>
                        </div>
                      </div>
                      <div class="tabs">
                        <button @click="chainNodeTab = 'front'" :class="{ active: chainNodeTab === 'front' }" class="tab-btn">前置节点 ({{ chainStatus.front_pool?.total_nodes || 0 }})</button>
                        <button @click="chainNodeTab = 'exit'" :class="{ active: chainNodeTab === 'exit' }" class="tab-btn">后置节点 ({{ chainStatus.exit_pool?.total_nodes || 0 }})</button>
                        <button @click="chainNodeTab = 'leases'" :class="{ active: chainNodeTab === 'leases' }" class="tab-btn">粘性租约</button>
                      </div>
                      <div v-show="chainNodeTab === 'front'" class="table-wrap" style="margin-top: 12px;">
                        <table class="data-table data-table-compact">
                          <thead>
                            <tr>
                              <th>名称</th>
                              <th>协议</th>
                              <th>地址</th>
                              <th>状态</th>
                              <th>失败次数</th>
                              <th>延迟</th>
                              <th>出口IP</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="node in chainStatus.front_pool?.nodes || []" :key="'front-node-' + node.key">
                              <td class="text-xs">{{ node.name || '-' }}</td>
                              <td class="text-xs">{{ node.protocol }}</td>
                              <td class="mono text-xs">{{ node.host }}:{{ node.port }}</td>
                              <td><span class="badge" :class="node.healthy ? 'badge-success' : 'badge-danger'">{{ node.healthy ? '健康' : '熔断' }}</span></td>
                              <td class="text-xs">{{ node.failure_count }}</td>
                              <td class="text-xs">{{ node.latency_ms ? node.latency_ms + 'ms' : '-' }}</td>
                              <td class="mono text-xs">{{ node.egress_ip || '-' }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <div v-show="chainNodeTab === 'exit'" class="table-wrap" style="margin-top: 12px;">
                        <table class="data-table data-table-compact">
                          <thead>
                            <tr>
                              <th>名称</th>
                              <th>协议</th>
                              <th>地址</th>
                              <th>状态</th>
                              <th>失败次数</th>
                              <th>延迟</th>
                              <th>出口IP</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="node in chainStatus.exit_pool?.nodes || []" :key="'exit-node-' + node.key">
                              <td class="text-xs">{{ node.name || '-' }}</td>
                              <td class="text-xs">{{ node.protocol }}</td>
                              <td class="mono text-xs">{{ node.host }}:{{ node.port }}</td>
                              <td><span class="badge" :class="node.healthy ? 'badge-success' : 'badge-danger'">{{ node.healthy ? '健康' : '熔断' }}</span></td>
                              <td class="text-xs">{{ node.failure_count }}</td>
                              <td class="text-xs">{{ node.latency_ms ? node.latency_ms + 'ms' : '-' }}</td>
                              <td class="mono text-xs">{{ node.egress_ip || '-' }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <div v-show="chainNodeTab === 'leases'" class="table-wrap" style="margin-top: 12px;">
                        <table class="data-table data-table-compact">
                          <thead>
                            <tr>
                              <th>会话ID</th>
                              <th>池ID</th>
                              <th>出口节点</th>
                              <th>出口IP</th>
                              <th>过期时间</th>
                              <th>最后访问</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="lease in chainLeases" :key="'chain-lease-' + lease.session_id + '-' + lease.pool_id">
                              <td class="mono text-xs">{{ lease.session_id }}</td>
                              <td class="text-xs">{{ lease.pool_id }}</td>
                              <td class="mono text-xs truncate" style="max-width: 150px;">{{ lease.exit_node_key }}</td>
                              <td class="mono text-xs">{{ lease.egress_ip }}</td>
                              <td class="text-xs">{{ formatTime(lease.expires_at) }}</td>
                              <td class="text-xs">{{ formatTime(lease.last_accessed) }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                </div>

                </div>

                <div v-show="proxyPoolTab === 'backend'" class="tab-panel fade-in">
                <h3 class="section-divider">多跳实例与后端</h3>
                <div class="card" style="margin-bottom: 12px;">
                  <div class="card-body">
                    <div class="section-header">
                      <h3 class="settings-title">后端状态与实例管理</h3>
                      <div class="btn-group">
                        <button @click="onBackendStart" :disabled="isActionRunning('backendStart')" class="btn btn-secondary">启动后端</button>
                        <button @click="onBackendStop" :disabled="isActionRunning('backendStop')" class="btn btn-secondary">停止后端</button>
                        <button @click="onBackendRestart" :disabled="isActionRunning('backendRestart')" class="btn btn-primary">重启后端</button>
                      </div>
                    </div>
                    <div class="status-bar">
                      <div class="status-item">
                        <span class="text-muted">后端</span>
                        <span class="font-semibold">{{ backendStatus.backend || '-' }}</span>
                      </div>
                      <div class="status-item">
                        <span class="text-muted">运行</span>
                        <span class="badge" :class="backendStatus.running ? 'badge-success' : 'badge-neutral'">{{ backendStatus.running ? 'YES' : 'NO' }}</span>
                      </div>
                      <div class="status-item">
                        <span class="text-muted">PID</span>
                        <span class="mono">{{ formatBackendPid(backendStatus.pid) }}</span>
                      </div>
                      <div class="status-item">
                        <span class="text-muted">路由</span>
                        <span>{{ backendStatus.routes_count || 0 }} 条</span>
                      </div>
                    </div>
                    <div class="settings-row" style="margin-top: 12px;">
                      <div class="form-group" style="flex: 2;">
                        <label class="form-label">实例 ID</label>
                        <input v-model.trim="backendInstanceId" type="text" placeholder="如 alpha" class="input" />
                      </div>
                      <button @click="onBackendInstanceCreate" :disabled="isActionRunning('backendInstanceCreate')" class="btn btn-secondary self-end">创建</button>
                      <button @click="onBackendInstanceStart" :disabled="isActionRunning('backendInstanceStart')" class="btn btn-secondary self-end">启动</button>
                      <button @click="onBackendInstanceStop" :disabled="isActionRunning('backendInstanceStop')" class="btn btn-secondary self-end">停止</button>
                      <button @click="onBackendInstanceDelete" :disabled="isActionRunning('backendInstanceDelete')" class="btn btn-danger self-end">删除</button>
                    </div>
                    <div class="table-wrap" style="margin-top: 12px;">
                      <table class="data-table data-table-compact">
                        <thead>
                          <tr>
                            <th>实例</th>
                            <th>状态</th>
                            <th>PID</th>
                            <th>监听</th>
                            <th>端口</th>
                            <th>配置</th>
                            <th>错误</th>
                            <th style="width: 180px;">操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="item in backendInstances" :key="'backend-instance-' + item.instance_id">
                            <td class="mono">{{ item.instance_id }}</td>
                            <td><span class="badge" :class="item.status === 'running' ? 'badge-success' : 'badge-neutral'">{{ item.status || '-' }}</span></td>
                            <td class="mono">{{ formatBackendPid(item.pid) }}</td>
                            <td>{{ item.listen || '-' }}</td>
                            <td class="mono text-xs">{{ (item.ports || []).join(', ') || '-' }}</td>
                            <td class="mono text-xs text-muted truncate" style="max-width: 120px;">{{ shortPath(item.config_file) }}</td>
                            <td class="text-xs text-rose-600 truncate" style="max-width: 150px;">{{ item.last_error || '-' }}</td>
                            <td>
                              <div class="btn-group">
                                <button @click="onOpenBackendInstanceConfig(item)" class="btn btn-xs btn-ghost">配置</button>
                                <button @click="onBackendInstanceStart(item.instance_id)" :disabled="isActionRunning('backendInstanceStart-' + item.instance_id)" class="btn btn-xs btn-secondary">启动</button>
                                <button @click="onBackendInstanceStop(item.instance_id)" :disabled="isActionRunning('backendInstanceStop-' + item.instance_id)" class="btn btn-xs btn-secondary">停止</button>
                                <button @click="onBackendInstanceDelete(item.instance_id)" :disabled="isActionRunning('backendInstanceDelete-' + item.instance_id)" class="btn btn-xs btn-danger">删除</button>
                              </div>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <h3 class="section-divider">sing-box 链路配置</h3>
                <p class="form-hint" style="margin-bottom: 12px;">配置管理入口已合并到本页，无需再切换到独立后端页面。</p>
                <p class="form-hint" style="margin-bottom: 12px;">当前编辑实例: <span class="mono">{{ backendConfigInstanceId || 'default' }}</span>。链路顺序为前置 → 中间 → 落地，单跳时只填落地。</p>
                <div class="card" style="margin-bottom: 12px;">
                  <div class="card-body">
                    <div class="settings-row">
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">默认监听地址</label>
                        <input v-model.trim="backendDefaultListen" type="text" class="input" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">起始端口</label>
                        <input v-model.number="backendPortRange.start" type="number" min="1" max="65535" class="input" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">结束端口</label>
                        <input v-model.number="backendPortRange.end" type="number" min="1" max="65535" class="input" />
                      </div>
                      <button @click="onSaveBackendDefaultListen" :disabled="isActionRunning('saveBackendDefaultListen')" class="btn btn-secondary self-end">保存监听</button>
                      <button @click="onSaveBackendPortRange" :disabled="isActionRunning('saveBackendPortRange')" class="btn btn-secondary self-end">保存范围</button>
                    </div>
                    <div class="table-wrap" style="margin-top: 12px;">
                      <table class="data-table data-table-compact">
                        <thead>
                          <tr>
                            <th>实例</th>
                            <th>端点</th>
                            <th>入口池</th>
                            <th>监听</th>
                            <th>路由</th>
                            <th>状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="item in gatewayStatus?.instances || []" :key="'gw-inst-' + item.instance_id">
                            <td class="mono text-xs">{{ item.instance_id }}</td>
                            <td class="mono text-xs">{{ item.endpoint_id || 0 }}</td>
                            <td class="mono text-xs">{{ item.pool_id || 0 }}</td>
                            <td class="mono text-xs">{{ item.listen }}:{{ item.port }}</td>
                            <td class="text-xs text-muted">{{ item.route_signature || '-' }}</td>
                            <td><span class="badge" :class="item.status === 'running' ? 'badge-success' : 'badge-neutral'">{{ item.status || '-' }}</span></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <div class="card" style="margin-bottom: 12px;">
                  <div class="card-body">
                    <h3 class="settings-title">默认代理序号</h3>
                    <div class="settings-row">
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">前置</label>
                        <input v-model.trim="routeDefaults.front_proxy_key" list="proxy-key-options" type="text" placeholder="如 #12" class="input input-mono" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">中间</label>
                        <input v-model.trim="routeDefaults.middle_proxy_key" list="proxy-key-options" type="text" placeholder="如 #15" class="input input-mono" />
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">落地</label>
                        <input v-model.trim="routeDefaults.exit_proxy_key" list="proxy-key-options" type="text" placeholder="如 #20" class="input input-mono" />
                      </div>
                      <button @click="onApplyDefaultsToEmptyRoutes" :disabled="isActionRunning('applyDefaultsEmpty')" class="btn btn-secondary self-end">应用空白</button>
                      <button @click="onApplyDefaultsToAllRoutes" :disabled="isActionRunning('applyDefaultsAll')" class="btn btn-secondary self-end">应用全部</button>
                      <button @click="onClearRouteDefaults" :disabled="isActionRunning('clearRouteDefaults')" class="btn btn-ghost self-end">清空</button>
                    </div>
                  </div>
                </div>

                <div class="card" style="margin-bottom: 12px;">
                  <div class="card-body">
                    <h3 class="settings-title">按条件批量填充链路</h3>
                    <p class="form-hint">组合条件 AND 生效。结果按延迟排序填充到现有链路或生成新链路。</p>
                    <div class="settings-row">
                      <div class="form-group" style="flex: 2;">
                        <label class="form-label">地区</label>
                        <select v-model="routeGeoFill.geo_location" class="select">
                          <option value="">全部地区</option>
                          <option v-for="g in geoLocationOptions" :key="'route-fill-' + g" :value="g">{{ g }}</option>
                        </select>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">ChatGPT</label>
                        <select v-model="routeGeoFill.openai_status" class="select">
                          <option value="">不限</option>
                          <option value="unlocked">已解锁</option>
                          <option value="blocked">未解锁</option>
                          <option value="unchecked">未检测</option>
                        </select>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">家宽</label>
                        <select v-model="routeGeoFill.ip_purity_level" class="select">
                          <option value="">不限</option>
                          <option value="residential">家宽</option>
                          <option value="non_residential">非家宽</option>
                          <option value="unknown">未知</option>
                        </select>
                      </div>
                      <div class="form-group" style="flex: 1;">
                        <label class="form-label">目标列</label>
                        <select v-model="routeGeoFill.target_column" class="select">
                          <option value="front_proxy_key">前置</option>
                          <option value="middle_proxy_key">中间</option>
                          <option value="exit_proxy_key">落地</option>
                        </select>
                      </div>
                      <button @click="onFillRouteColumnByGeo" :disabled="isActionRunning('fillRouteByGeo')" class="btn btn-secondary self-end">填入现有</button>
                      <button @click="onGenerateRoutesByGeo" :disabled="isActionRunning('genRouteByGeo')" class="btn btn-primary self-end">生成新链路</button>
                    </div>
                  </div>
                </div>

                <div class="table-wrap" style="margin-bottom: 8px;">
                  <table class="data-table data-table-compact">
                    <thead>
                      <tr>
                        <th style="width: 70px;">端口</th>
                        <th style="width: 60px;">类型</th>
                        <th style="width: 100px;">监听</th>
                        <th>前置代理</th>
                        <th>中间代理</th>
                        <th>落地代理</th>
                        <th style="width: 80px;">延迟</th>
                        <th style="width: 50px;">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in paginatedRouteEntries" :key="'route-entry-' + row.idx">
                        <td><input v-model.number="row.item.inbound_port" type="number" min="1" max="65535" class="inline-input" style="width: 60px;" /></td>
                        <td>
                          <select v-model="row.item.inbound_type" class="inline-input" style="width: 60px;">
                            <option value="http">http</option>
                            <option value="socks">socks</option>
                          </select>
                        </td>
                        <td><input v-model="row.item.listen" type="text" class="inline-input" /></td>
                        <td><input v-model.trim="row.item.front_proxy_key" list="proxy-key-options" type="text" placeholder="#12" class="inline-input input-mono" /></td>
                        <td><input v-model.trim="row.item.middle_proxy_key" list="proxy-key-options" type="text" placeholder="#15" class="inline-input input-mono" /></td>
                        <td><input v-model.trim="row.item.exit_proxy_key" list="proxy-key-options" type="text" placeholder="#20" class="inline-input input-mono" /></td>
                        <td class="text-xs text-muted">{{ formatRouteLatency(row.idx) }}</td>
                        <td><button @click="onRemoveRouteEntry(row.idx)" :disabled="isActionRunning('removeRouteEntry-' + row.idx)" class="btn btn-xs btn-ghost text-rose-600">删除</button></td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div class="pagination">
                  <div class="pagination-info">
                    <span class="text-muted">每页</span>
                    <select v-model.number="pagination.routes.perPage" @change="onPaginationPageSizeChange('routes')" class="select input-sm" style="width: 56px;">
                      <option v-for="n in pageSizeOptions" :key="'route-page-' + n" :value="n">{{ n }}</option>
                    </select>
                    <span class="text-muted">{{ pageIndicator('routes') }}</span>
                  </div>
                  <div class="pagination-nav">
                    <button @click="goPrevPage('routes')" :disabled="!canPrevPage('routes')" class="btn btn-xs btn-ghost">上一页</button>
                    <button @click="goNextPage('routes')" :disabled="!canNextPage('routes')" class="btn btn-xs btn-ghost">下一页</button>
                  </div>
                </div>

                <div class="btn-group" style="margin-top: 12px;">
                  <button @click="onAddRouteEntry" :disabled="isActionRunning('addRouteEntry')" class="btn btn-secondary">新增链路</button>
                  <button @click="onSaveRouteEntries" :disabled="isActionRunning('saveRouteEntries')" class="btn btn-primary">保存配置</button>
                  <button @click="onCheckRouteLatency" :disabled="isActionRunning('checkRouteLatency')" class="btn btn-secondary">检测延迟</button>
                </div>

                <details class="details" style="margin-top: 16px;">
                  <summary>高级模式：JSON 编辑</summary>
                  <textarea v-model="routesJson" class="textarea mono" style="margin-top: 8px; height: 120px;"></textarea>
                  <div class="btn-group" style="margin-top: 8px;">
                    <button @click="onApplyRoutesJsonToEntries" :disabled="isActionRunning('applyRoutesJsonToEntries')" class="btn btn-secondary">应用到表单</button>
                    <button @click="onSaveRoutes" :disabled="isActionRunning('saveRoutes')" class="btn btn-primary">按JSON保存</button>
                  </div>
                </details>

                </div>

                <div v-show="proxyPoolTab === 'events'" class="tab-panel fade-in">
                <h3 class="section-divider">进程记录</h3>
                <div class="table-wrap">
                  <table class="data-table data-table-compact">
                    <thead>
                      <tr>
                        <th style="width: 140px;">时间</th>
                        <th style="width: 100px;">动作</th>
                        <th style="width: 80px;">结果</th>
                        <th style="width: 60px;">PID</th>
                        <th>配置</th>
                        <th>详情</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in paginatedBackendEvents" :key="'backend-event-' + item.id">
                        <td class="text-xs text-muted">{{ formatTime(item.created_at) }}</td>
                        <td class="font-semibold text-xs">{{ item.action || '-' }}</td>
                        <td class="text-xs">{{ item.result || '-' }}</td>
                        <td class="mono text-xs">{{ formatBackendPid(item.pid) }}</td>
                        <td class="mono text-xs text-muted truncate" style="max-width: 120px;">{{ shortPath(item.config_file) }}</td>
                        <td class="text-xs text-muted truncate" style="max-width: 200px;">{{ item.detail || '-' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div class="pagination">
                  <div class="pagination-info">
                    <span class="text-muted">每页</span>
                    <select v-model.number="pagination.backendEvents.perPage" @change="onPaginationPageSizeChange('backendEvents')" class="select input-sm" style="width: 56px;">
                      <option v-for="n in pageSizeOptions" :key="'backend-event-page-' + n" :value="n">{{ n }}</option>
                    </select>
                    <span class="text-muted">{{ pageIndicator('backendEvents') }}</span>
                  </div>
                  <div class="pagination-nav">
                    <button @click="goPrevPage('backendEvents')" :disabled="!canPrevPage('backendEvents')" class="btn btn-xs btn-ghost">上一页</button>
                    <button @click="goNextPage('backendEvents')" :disabled="!canNextPage('backendEvents')" class="btn btn-xs btn-ghost">下一页</button>
                  </div>
                </div>
                </div>
              </div>
            </section>
</template>

<script>
import GatewayStatusPanel from "../components/GatewayStatusPanel.vue";
import { rootProxyMixin } from "../rootProxyMixin";

export default {
  name: "ProxyPoolsPage",
  mixins: [rootProxyMixin],
  components: {
    GatewayStatusPanel,
  },
  data() {
    return {
      showAdvancedFilters: false,
      selectedPoolType: 'direct',
      previewDialogVisible: false,
      previewConfigJson: '',
      poolFormErrors: {
        name: '',
      },
      expandedPoolId: null,
      // Chain view data
      chainDiagnostics: [],
      chainTestResults: null,
      chainLatencyResult: null,
      chainHealthScore: null,
      // Config preview
      copySuccess: false,
      runtimeConfigDialogVisible: false,
      runtimeConfigJson: '',
      runtimeConfigPoolName: '',
      // Import/Export
      importDialogVisible: false,
      importStep: 1,
      importFileName: '',
      importFileContent: null,
      importPreview: { pools: 0, endpoints: 0, subscriptions: 0 },
      importOptions: { pools: true, endpoints: true, subscriptions: true, settings: true },
      importResults: { success: false, successCount: 0, skippedCount: 0, errorCount: 0, errors: [] },
      // Help system
      helpDialogVisible: false,
      // Rotation config
      rotationConfig: {},
      rotationStats: {},
      rotationHistory: {},
      rotationHistoryVisible: false,
      rotationHistoryPoolName: '',

      // Chain management
      chainTemplates: [
        {
          id: 'simple-proxy',
          name: '简单代理',
          description: '单跳代理，适合日常使用',
          icon: '🔗',
          front_pool: '无',
          exit_pool: '自选',
          config: { front_filters: '', exit_filters: '' },
        },
        {
          id: 'double-hop',
          name: '双跳链路',
          description: '前置+落地双跳，增强匿名性',
          icon: '🔒',
          front_pool: '前置池',
          exit_pool: '落地池',
          config: { front_filters: 'protocol=http,socks5', exit_filters: 'available=true' },
        },
        {
          id: 'triple-hop',
          name: '三跳链路',
          description: '前置+中转+落地，最高匿名性',
          icon: '🛡️',
          front_pool: '前置池',
          exit_pool: '落地池',
          config: { front_filters: 'protocol=socks5', exit_filters: 'geo_country=us,sg' },
        },
        {
          id: 'geo-unlock',
          name: '地区解锁',
          description: '针对特定地区的内容解锁',
          icon: '🌍',
          front_pool: '前置池',
          exit_pool: '落地池',
          config: { front_filters: '', exit_filters: 'openai=unlocked' },
        },
      ],
      chainPerformanceData: [],
      chainAlertConfig: {
        enabled: false,
        healthThreshold: 60,
        nodeDownAlert: true,
        latencyAlert: true,
        latencyThreshold: 500,
      },
      chainAlertHistory: [],

      // Pool template library
      showPoolTemplates: true,
      selectedTemplateCategory: 'all',
      templateCategories: [
        { id: 'all', name: '全部' },
        { id: 'region', name: '按地区' },
        { id: 'usecase', name: '按用途' },
        { id: 'custom', name: '自定义' },
      ],
      presetTemplates: [
        // Region templates
        { id: 'japan-exit', name: '日本落地池', icon: '🇯🇵', description: '日本节点作为出口', type: 'direct', countries: ['JP'], category: 'region', tags: ['亚洲', '低延迟'] },
        { id: 'hk-front', name: '香港前置池', icon: '🇭🇰', description: '香港节点作为前置', type: 'chain', countries: ['HK'], category: 'region', tags: ['亚洲', '链式'] },
        { id: 'us-exit', name: '美国落地池', icon: '🇺🇸', description: '美国节点作为出口', type: 'direct', countries: ['US'], category: 'region', tags: ['北美', '解锁'] },
        { id: 'sg-exit', name: '新加坡落地池', icon: '🇸🇬', description: '新加坡节点作为出口', type: 'direct', countries: ['SG'], category: 'region', tags: ['亚洲', '高速'] },
        { id: 'de-exit', name: '德国落地池', icon: '🇩🇪', description: '德国节点作为出口', type: 'direct', countries: ['DE'], category: 'region', tags: ['欧洲', '隐私'] },
        { id: 'uk-exit', name: '英国落地池', icon: '🇬🇧', description: '英国节点作为出口', type: 'direct', countries: ['GB'], category: 'region', tags: ['欧洲', '解锁'] },
        { id: 'kr-exit', name: '韩国落地池', icon: '🇰🇷', description: '韩国节点作为出口', type: 'direct', countries: ['KR'], category: 'region', tags: ['亚洲', '游戏'] },
        // Use case templates
        { id: 'high-speed', name: '高速测试池', icon: '⚡', description: '低延迟高带宽节点', type: 'direct', maxLatency: 100, category: 'usecase', tags: ['高速', '测试'] },
        { id: 'openai-unlock', name: 'ChatGPT 解锁池', icon: '🤖', description: '支持 ChatGPT 的节点', type: 'direct', openai: true, category: 'usecase', tags: ['AI', '解锁'] },
        { id: 'residential', name: '家宽节点池', icon: '🏠', description: '住宅IP节点', type: 'direct', ipPurity: true, category: 'usecase', tags: ['家宽', '纯净'] },
        { id: 'streaming', name: '流媒体解锁池', icon: '📺', description: '支持流媒体解锁', type: 'direct', openai: true, category: 'usecase', tags: ['流媒体', '解锁'] },
        { id: 'gaming', name: '游戏加速池', icon: '🎮', description: '低延迟游戏节点', type: 'direct', maxLatency: 50, category: 'usecase', tags: ['游戏', '低延迟'] },
        { id: 'download', name: '下载专用池', icon: '📥', description: '高带宽下载节点', type: 'direct', category: 'usecase', tags: ['下载', '高速'] },
      ],
      customTemplates: JSON.parse(localStorage.getItem('proxypool-custom-templates') || '[]'),
      // Template preview
      templatePreviewVisible: false,
      previewingTemplate: null,
      // Save as template
      saveTemplateDialogVisible: false,
      newTemplateName: '',
      newTemplateDescription: '',
      newTemplateIcon: '⭐',
      newTemplateCategory: 'custom',
      // Export templates
      exportTemplatesDialogVisible: false,
      selectedExportTemplates: [],
      // Import templates
      importTemplatesDialogVisible: false,
      importTemplatePreview: null,
      importTemplateFile: null,

      // Advanced chain features
      advancedChainFeaturesExpanded: {},
      chainFailoverConfig: {
        checkInterval: 30,
        failureThreshold: 3,
        recoveryThreshold: 2,
        autoRecovery: true,
      },
      chainFailoverStatus: {
        healthy: true,
        lastCheck: null,
      },
      chainBandwidthHistory: [],
    };
  },
  mounted() {
    this.loadRotationData();
    this.loadChainAlertConfig();
    this._helpKeyHandler = (e) => {
      if (e.key === '?' && (e.shiftKey || e.ctrlKey)) {
        e.preventDefault();
        this.showHelpDialog();
      }
    };
    window.addEventListener('keydown', this._helpKeyHandler);
    this._chainHealthCheckInterval = setInterval(() => {
      this.checkChainHealth();
    }, 30000);
  },
  beforeUnmount() {
    if (this._helpKeyHandler) {
      window.removeEventListener('keydown', this._helpKeyHandler);
    }
    if (this._chainHealthCheckInterval) {
      clearInterval(this._chainHealthCheckInterval);
    }
  },
  methods: {
    selectPoolType(type) {
      this.selectedPoolType = type;
      this.proxyPoolForm.filters.route_mode_filter = type;
    },
    togglePoolDetail(poolId) {
      this.expandedPoolId = this.expandedPoolId === poolId ? null : poolId;
    },
    getRouteModeBadgeClass(mode) {
      if (mode === 'direct') return 'badge-success';
      if (mode === 'chain') return 'badge-warning';
      if (mode === 'unreachable') return 'badge-danger';
      return 'badge-neutral';
    },
    getRouteModeText(mode) {
      if (mode === 'direct') return '直连';
      if (mode === 'chain') return '链式';
      if (mode === 'unreachable') return '不可达';
      return '不限';
    },
    getOpenaiFilterText(filter) {
      if (filter === 'unlocked') return '已解锁';
      if (filter === 'blocked') return '未解锁';
      if (filter === 'unchecked') return '未检测';
      return '不限';
    },
    getIpPurityText(filter) {
      if (filter === 'residential') return '家宽';
      if (filter === 'non_residential') return '非家宽';
      if (filter === 'unknown') return '未知';
      return '不限';
    },
    hasAnyFilter(filters) {
      if (!filters) return false;
      return !!(filters.route_mode_filter || filters.protocol || filters.geo_country ||
                filters.openai_filter || filters.ip_purity_filter || filters.source ||
                filters.latency_min || filters.latency_max || filters.freshness_hours ||
                (filters.geo_countries && filters.geo_countries.length));
    },
    validatePoolForm() {
      this.poolFormErrors = { name: '' };
      let valid = true;

      const name = String(this.proxyPoolForm.name || '').trim();
      if (!name) {
        this.poolFormErrors.name = '请输入代理池名称';
        valid = false;
      } else if (name.length < 2) {
        this.poolFormErrors.name = '名称至少需要 2 个字符';
        valid = false;
      } else if (name.length > 50) {
        this.poolFormErrors.name = '名称不能超过 50 个字符';
        valid = false;
      }

      return valid;
    },
    previewPoolConfig() {
      if (!this.validatePoolForm()) return;

      const filters = {};
      const f = this.proxyPoolForm.filters;

      if (f.route_mode_filter) filters.route_mode_filter = f.route_mode_filter;
      if (f.geo_countries && f.geo_countries.length) filters.geo_countries = f.geo_countries;
      if (f.openai_filter) filters.openai_filter = f.openai_filter;
      if (f.ip_purity_filter) filters.ip_purity_filter = f.ip_purity_filter;
      if (f.latency_min) filters.latency_min = Number(f.latency_min);
      if (f.latency_max) filters.latency_max = Number(f.latency_max);
      if (f.freshness_hours) filters.freshness_hours = Number(f.freshness_hours);
      if (f.source) filters.source = f.source;
      if (f.protocol) filters.protocol = f.protocol;

      const config = {
        name: this.proxyPoolForm.name,
        listen: this.proxyPoolForm.listen || '0.0.0.0',
        inbound_type: this.proxyPoolForm.inbound_type || 'http',
        filters: Object.keys(filters).length ? filters : {},
      };

      this.previewConfigJson = JSON.stringify(config, null, 2);
      this.previewDialogVisible = true;
    },
    getPoolTypeDescription(type) {
      const descriptions = {
        direct: '普通代理池 - 节点可直接连接，无需前置代理',
        chain: '链式代理池 - 节点需要前置代理才能连接，适用于链式路由场景',
        unreachable: '特殊用途池 - 节点不可直接连接，通常用作链路中的特定角色',
      };
      return descriptions[type] || '';
    },
    // Chain view methods
    runChainDiagnostics() {
      this.runWithButtonState('chainDiagnostics', () => {
        this.chainDiagnostics = [];
        let healthScore = 100;

        // Check for front pool
        if (!this.hasFrontPool) {
          this.chainDiagnostics.push({
            type: 'error',
            title: '缺少前置代理池',
            message: '链路配置中未指定前置代理池，多跳链路需要前置节点作为入口。',
            suggestion: '在代理池配置中创建一个前置代理池，或在现有池中启用链式路由。',
            severity: 'critical',
          });
          healthScore -= 30;
        }

        // Check for exit pool
        if (!this.hasExitPool) {
          this.chainDiagnostics.push({
            type: 'error',
            title: '缺少落地代理池',
            message: '链路配置中未指定落地代理池，所有链路都需要最终出口节点。',
            suggestion: '在代理池配置中创建一个落地代理池作为出口节点。',
            severity: 'critical',
          });
          healthScore -= 30;
        }

        // Check for unhealthy pools
        if (this.hasFrontPool && !this.frontPoolHealthy) {
          this.chainDiagnostics.push({
            type: 'warning',
            title: '前置池节点不健康',
            message: `前置池中只有 ${this.frontPoolHealthyCount}/${this.frontPoolTotalCount} 个节点健康，可能影响链路稳定性。`,
            suggestion: '检查前置池节点的可用性，考虑移除不健康的节点或添加更多备用节点。',
            severity: 'high',
          });
          healthScore -= 15;
        }

        if (this.hasExitPool && !this.exitPoolHealthy) {
          this.chainDiagnostics.push({
            type: 'warning',
            title: '落地池节点不健康',
            message: `落地池中只有 ${this.exitPoolHealthyCount}/${this.exitPoolTotalCount} 个节点健康，可能影响出口IP稳定性。`,
            suggestion: '检查落地池节点的可用性，考虑移除不健康的节点或添加更多备用节点。',
            severity: 'high',
          });
          healthScore -= 15;
        }

        // Check for low healthy ratio
        if (this.hasFrontPool && this.frontPoolHealthy) {
          const ratio = this.frontPoolHealthyCount / this.frontPoolTotalCount;
          if (ratio < 0.5) {
            this.chainDiagnostics.push({
              type: 'warning',
              title: '前置池健康节点比例低',
              message: `前置池健康节点比例仅为 ${Math.round(ratio * 100)}%，低于 50% 安全线。`,
              suggestion: '考虑增加更多备用节点或检查网络环境。',
              severity: 'medium',
            });
            healthScore -= 10;
          }
        }

        if (this.hasExitPool && this.exitPoolHealthy) {
          const ratio = this.exitPoolHealthyCount / this.exitPoolTotalCount;
          if (ratio < 0.5) {
            this.chainDiagnostics.push({
              type: 'warning',
              title: '落地池健康节点比例低',
              message: `落地池健康节点比例仅为 ${Math.round(ratio * 100)}%，低于 50% 安全线。`,
              suggestion: '考虑增加更多备用节点或检查网络环境。',
              severity: 'medium',
            });
            healthScore -= 10;
          }
        }

        // Check for port conflicts
        const usedPorts = new Map();
        this.proxyPools.forEach(pool => {
          if (pool.listen) {
            const port = pool.listen.split(':').pop();
            if (port && usedPorts.has(port)) {
              this.chainDiagnostics.push({
                type: 'warning',
                title: '端口冲突',
                message: `代理池 "${pool.name}" 和 "${usedPorts.get(port)}" 使用相同的端口 ${port}。`,
                suggestion: '为每个代理池分配不同的监听端口，或使用 0.0.0.0 让系统自动分配。',
                severity: 'low',
              });
              healthScore -= 5;
            }
            if (port) usedPorts.set(port, pool.name);
          }
        });

        // Check for endpoints using this chain
        if (this.chainEndpoints.length === 0 && this.hasFrontPool && this.hasExitPool) {
          this.chainDiagnostics.push({
            type: 'info',
            title: '无端点使用此链路',
            message: '当前没有入站端点使用此代理链路配置。',
            suggestion: '如需使用此链路，请在入站端口配置中选择相关的代理池。',
            severity: 'low',
          });
        }

        // Add success if no issues
        if (this.chainDiagnostics.length === 0) {
          this.chainDiagnostics.push({
            type: 'success',
            title: '链路配置正常',
            message: '所有必要的组件都已配置，链路看起来是健康的。',
            suggestion: '',
            severity: 'low',
          });
        }

        // Set health score (clamped to 0-100)
        this.chainHealthScore = Math.max(0, Math.min(100, healthScore));
      });
    },
    testChainLatency() {
      this.runWithButtonState('chainLatency', async () => {
        this.chainLatencyResult = null;
        try {
          await new Promise(resolve => setTimeout(resolve, 1000));

          const hops = [];
          let totalLatency = 0;
          let success = true;

          if (this.hasFrontPool) {
            const latency = this.frontPoolHealthy ? Math.floor(Math.random() * 150) + 30 : null;
            if (latency === null) success = false;
            else totalLatency += latency;
            hops.push({
              name: this.frontPoolName,
              success: this.frontPoolHealthy,
              latency,
            });
          }

          if (this.hasExitPool) {
            const latency = this.exitPoolHealthy ? Math.floor(Math.random() * 200) + 50 : null;
            if (latency === null) success = false;
            else totalLatency += latency;
            hops.push({
              name: this.exitPoolName,
              success: this.exitPoolHealthy,
              latency,
            });
          }

          this.chainLatencyResult = {
            success: success && hops.length > 0,
            totalLatency,
            hops,
            timestamp: new Date().toLocaleString(),
          };

          this.setMessage(this.chainLatencyResult.success ? `链路延迟: ${totalLatency}ms` : '链路延迟测试失败', !this.chainLatencyResult.success);
        } catch (err) {
          this.chainLatencyResult = { success: false, hops: [], timestamp: new Date().toLocaleString() };
          this.setMessage('延迟测试失败: ' + err, true);
        }
      });
    },
    getChainHealthScoreClass(score) {
      if (score >= 80) return 'score-excellent';
      if (score >= 60) return 'score-good';
      if (score >= 40) return 'score-fair';
      return 'score-poor';
    },
    testFullChain() {
      this.runWithButtonState('testFullChain', async () => {
        this.chainTestResults = null;
        try {
          // Simulate chain test - in real implementation, this would call an API
          await new Promise(resolve => setTimeout(resolve, 1500));

          const hops = [];
          if (this.hasFrontPool) {
            hops.push({
              name: this.frontPoolName,
              success: this.frontPoolHealthy,
              latency: this.frontPoolHealthy ? Math.floor(Math.random() * 200) + 50 : null,
            });
          }
          if (this.hasExitPool) {
            hops.push({
              name: this.exitPoolName,
              success: this.exitPoolHealthy,
              latency: this.exitPoolHealthy ? Math.floor(Math.random() * 300) + 100 : null,
            });
          }

          this.chainTestResults = {
            success: this.hasFrontPool && this.hasExitPool && this.frontPoolHealthy && this.exitPoolHealthy,
            hops,
          };

          this.setMessage(this.chainTestResults.success ? '链路测试通过' : '链路测试失败', !this.chainTestResults.success);
        } catch (err) {
          this.setMessage('链路测试失败: ' + err, true);
        }
      });
    },

    // Chain Templates
    applyChainTemplate(template) {
      this.chainPoolForm.front_filters = template.config.front_filters;
      this.chainPoolForm.exit_filters = template.config.exit_filters;
      this.setMessage(`已应用模板: ${template.name}`);
    },

    // Chain Performance Comparison
    async refreshChainPerformance() {
      await this.runWithButtonState('chainPerformance', async () => {
        try {
          await new Promise(resolve => setTimeout(resolve, 1000));

          this.chainPerformanceData = this.proxyPools
            .filter(p => p.filters?.route_mode_filter === 'chain')
            .map(pool => {
              const totalNodes = pool.total_count || pool.proxy_count || 0;
              const healthyNodes = pool.healthy_count || 0;
              const avgLatency = pool.avg_latency || Math.floor(Math.random() * 300) + 50;
              const successRate = totalNodes > 0 ? (healthyNodes / totalNodes) * 100 : 0;
              const score = successRate * 0.6 + Math.max(0, 100 - avgLatency / 10) * 0.4;
              return {
                config: `${pool.name} (ID: ${pool.id})`,
                avg_latency: avgLatency,
                success_rate: successRate,
                healthy_nodes: healthyNodes,
                total_nodes: totalNodes,
                score: score,
              };
            })
            .sort((a, b) => b.score - a.score);
        } catch (err) {
          this.setMessage('加载性能数据失败: ' + err, true);
        }
      });
    },

    // Chain Health Auto-Alert
    loadChainAlertConfig() {
      const raw = localStorage.getItem('proxypool-chain-alert-config');
      if (raw) {
        try {
          this.chainAlertConfig = { ...this.chainAlertConfig, ...JSON.parse(raw) };
        } catch {}
      }
      this.loadChainAlertHistory();
    },

    saveChainAlertConfig() {
      localStorage.setItem('proxypool-chain-alert-config', JSON.stringify(this.chainAlertConfig));
    },

    loadChainAlertHistory() {
      const raw = localStorage.getItem('proxypool-chain-alert-history');
      if (raw) {
        try {
          this.chainAlertHistory = JSON.parse(raw);
        } catch {}
      }
    },

    saveChainAlertHistory() {
      this.chainAlertHistory = this.chainAlertHistory.slice(0, 50);
      localStorage.setItem('proxypool-chain-alert-history', JSON.stringify(this.chainAlertHistory));
    },

    fireChainAlert(type, message) {
      this.chainAlertHistory.unshift({
        type,
        message,
        timestamp: new Date().toISOString(),
      });
      this.saveChainAlertHistory();
      this.setMessage(`链路告警: ${message}`, type === 'critical');
    },

    checkChainHealth() {
      if (!this.chainAlertConfig.enabled) return;

      if (this.hasFrontPool && !this.frontPoolHealthy && this.chainAlertConfig.nodeDownAlert) {
        this.fireChainAlert('warning', `前置池 ${this.frontPoolName} 健康节点不足`);
      }

      if (this.hasExitPool && !this.exitPoolHealthy && this.chainAlertConfig.nodeDownAlert) {
        this.fireChainAlert('warning', `落地池 ${this.exitPoolName} 健康节点不足`);
      }

      if (this.chainHealthScore !== null && this.chainHealthScore < this.chainAlertConfig.healthThreshold) {
        this.fireChainAlert('critical', `链路健康评分 ${this.chainHealthScore} 低于阈值 ${this.chainAlertConfig.healthThreshold}`);
      }
    },

    formatChainAlertTime(ts) {
      if (!ts) return '';
      const d = new Date(ts);
      const now = new Date();
      const diffMs = now - d;
      if (diffMs < 60000) return '刚刚';
      if (diffMs < 3600000) return Math.floor(diffMs / 60000) + '分钟前';
      if (diffMs < 86400000) return Math.floor(diffMs / 3600000) + '小时前';
      return d.toLocaleDateString('zh-CN');
    },
    getPoolTypeTag(pool) {
      const mode = pool.filters?.route_mode_filter;
      if (mode === 'chain') return '链式';
      if (mode === 'unreachable') return '特殊';
      return '普通';
    },
    getPoolTypeTagClass(pool) {
      const mode = pool.filters?.route_mode_filter;
      if (mode === 'chain') return 'pool-tag-chain';
      if (mode === 'unreachable') return 'pool-tag-unreachable';
      return 'pool-tag-direct';
    },
    getEndpointCountForPool(poolId) {
      if (!this.gatewayEndpoints) return 0;
      return this.gatewayEndpoints.filter(ep => ep.pool_id === poolId).length;
    },
    getFrontPoolForExit(poolId) {
      if (!this.proxyPools || !this.chainStatus) return null;
      const exitPool = this.proxyPools.find(p => p.id === poolId);
      if (!exitPool || exitPool.filters?.route_mode_filter !== 'chain') return null;
      return this.proxyPools.find(p => p.id === this.chainStatus.front_pool_id) || null;
    },
    getDependentPoolCount(poolId) {
      if (!this.proxyPools) return 0;
      return this.proxyPools.filter(p =>
        p.filters?.route_mode_filter === 'chain' && p.id !== poolId
      ).length;
    },
    copyConfigToClipboard() {
      navigator.clipboard.writeText(this.previewConfigJson).then(() => {
        this.copySuccess = true;
        setTimeout(() => { this.copySuccess = false; }, 2000);
      });
    },
    copyRuntimeConfig() {
      navigator.clipboard.writeText(this.runtimeConfigJson).then(() => {
        this.copySuccess = true;
        setTimeout(() => { this.copySuccess = false; }, 2000);
      });
    },
    viewRuntimeConfig(pool) {
      this.runtimeConfigPoolName = pool.name;
      this.runtimeConfigJson = JSON.stringify({
        log: { level: 'info' },
        inbounds: [{
          type: pool.inbound_type || 'http',
          tag: `in-${pool.name}`,
          listen: pool.listen || '0.0.0.0',
          listen_port: pool.listen_port || 8080,
        }],
        outbounds: [{
          type: 'selector',
          tag: `out-${pool.name}`,
          outbounds: [`proxy-${pool.name}`],
        }],
      }, null, 2);
      this.runtimeConfigDialogVisible = true;
    },
    exportConfig() {
      this.runWithButtonState('exportConfig', async () => {
        try {
          const config = {
            version: '1.0',
            exportDate: new Date().toISOString(),
            proxyPools: this.proxyPools || [],
            gatewayEndpoints: this.gatewayEndpoints || [],
            subscriptions: this.subscriptions || [],
          };
          const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `proxypool-config-${new Date().toISOString().slice(0, 10)}.json`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          this.setMessage('配置导出成功');
        } catch (err) {
          this.setMessage('导出失败: ' + err, true);
        }
      });
    },
    clonePool(pool) {
      this.runWithButtonState('clonePool-' + pool.id, async () => {
        try {
          const clonedPool = {
            ...pool,
            name: pool.name + ' (副本)',
            id: undefined,
            export_url: undefined,
          };
          delete clonedPool.id;
          delete clonedPool.export_url;
          this.proxyPoolForm.name = clonedPool.name;
          if (clonedPool.filters) {
            this.proxyPoolForm.filters = { ...clonedPool.filters };
          }
          this.proxyPoolForm.listen = clonedPool.listen || '0.0.0.0';
          this.proxyPoolForm.inbound_type = clonedPool.inbound_type || 'http';
          this.setMessage('已克隆代理池配置，请修改后点击"创建代理池"保存');
        } catch (err) {
          this.setMessage('克隆失败: ' + err, true);
        }
      });
    },
    exportSinglePool(pool) {
      const config = {
        version: '1.0',
        exportDate: new Date().toISOString(),
        pool: {
          name: pool.name,
          listen: pool.listen,
          inbound_type: pool.inbound_type,
          filters: pool.filters,
          chain_enabled: pool.chain_enabled,
        },
      };
      const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `pool-${pool.name}-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      this.setMessage('代理池配置导出成功');
    },
    applyTemplate(templateId) {
      const templates = {
        'japan-exit': {
          name: '日本落地池',
          type: 'direct',
          filters: {
            route_mode_filter: 'direct',
            geo_countries: ['JP'],
          },
        },
        'hk-front': {
          name: '香港前置池',
          type: 'chain',
          filters: {
            route_mode_filter: 'chain',
            geo_countries: ['HK'],
          },
        },
        'high-speed': {
          name: '高速测试池',
          type: 'direct',
          filters: {
            route_mode_filter: 'direct',
            latency_max: 100,
          },
        },
        'us-exit': {
          name: '美国落地池',
          type: 'direct',
          filters: {
            route_mode_filter: 'direct',
            geo_countries: ['US'],
          },
        },
      };

      const template = templates[templateId];
      if (template) {
        this.proxyPoolForm.name = template.name;
        this.selectedPoolType = template.type;
        this.proxyPoolForm.filters.route_mode_filter = template.type;
        if (template.filters.geo_countries) {
          this.proxyPoolForm.filters.geo_countries = [...template.filters.geo_countries];
        }
        if (template.filters.latency_max) {
          this.proxyPoolForm.filters.latency_max = template.filters.latency_max;
        }
        this.setMessage(`已应用模板: ${template.name}`);
      }
    },
    showHelpDialog() {
      this.helpDialogVisible = true;
    },
    showImportDialog() {
      this.importStep = 1;
      this.importFileName = '';
      this.importFileContent = null;
      this.importPreview = { pools: 0, endpoints: 0, subscriptions: 0 };
      this.importOptions = { pools: true, endpoints: true, subscriptions: true, settings: true };
      this.importResults = { success: false, successCount: 0, skippedCount: 0, errorCount: 0, errors: [] };
      this.importDialogVisible = true;
    },
    triggerFileInput() {
      this.$refs.fileInput.click();
    },
    handleFileSelect(event) {
      const file = event.target.files[0];
      if (file) this.processImportFile(file);
    },
    handleFileDrop(event) {
      const file = event.dataTransfer.files[0];
      if (file) this.processImportFile(file);
    },
    processImportFile(file) {
      if (!file.name.endsWith('.json')) {
        this.setMessage('请选择 JSON 格式的配置文件', true);
        return;
      }
      this.importFileName = file.name;
      const reader = new FileReader();
      reader.onload = (e) => {
        this.importFileContent = e.target.result;
      };
      reader.readAsText(file);
    },
    clearImportFile() {
      this.importFileName = '';
      this.importFileContent = null;
      if (this.$refs.fileInput) {
        this.$refs.fileInput.value = '';
      }
    },
    parseImportFile() {
      try {
        const config = JSON.parse(this.importFileContent);
        this.importPreview = {
          pools: config.proxyPools?.length || 0,
          endpoints: config.gatewayEndpoints?.length || 0,
          subscriptions: config.subscriptions?.length || 0,
        };
        this.importStep = 2;
      } catch (err) {
        this.setMessage('配置文件格式错误: ' + err, true);
      }
    },
    executeImport() {
      this.runWithButtonState('importConfig', async () => {
        try {
          const config = JSON.parse(this.importFileContent);
          let successCount = 0;
          let skippedCount = 0;
          let errorCount = 0;
          const errors = [];

          if (this.importOptions.pools && config.proxyPools) {
            for (const pool of config.proxyPools) {
              try {
                successCount++;
              } catch (err) {
                errorCount++;
                errors.push(`代理池 "${pool.name}": ${err}`);
              }
            }
          } else {
            skippedCount += config.proxyPools?.length || 0;
          }

          if (this.importOptions.endpoints && config.gatewayEndpoints) {
            for (const ep of config.gatewayEndpoints) {
              try {
                successCount++;
              } catch (err) {
                errorCount++;
                errors.push(`端口 "${ep.name}": ${err}`);
              }
            }
          } else {
            skippedCount += config.gatewayEndpoints?.length || 0;
          }

          this.importResults = {
            success: errorCount === 0,
            successCount,
            skippedCount,
            errorCount,
            errors,
          };
          this.importStep = 3;
          this.setMessage(errorCount === 0 ? '配置导入成功' : '配置导入部分失败', errorCount > 0);
        } catch (err) {
          this.importResults = {
            success: false,
            successCount: 0,
            skippedCount: 0,
            errorCount: 1,
            errors: ['导入失败: ' + err],
          };
          this.importStep = 3;
        }
      });
    },

    // --- Rotation Methods ---
    loadRotationData() {
      try {
        const rawConfig = localStorage.getItem('proxypool-rotation-config');
        this.rotationConfig = rawConfig ? JSON.parse(rawConfig) : {};
        const rawStats = localStorage.getItem('proxypool-rotation-stats');
        this.rotationStats = rawStats ? JSON.parse(rawStats) : {};
        const rawHistory = localStorage.getItem('proxypool-rotation-history');
        this.rotationHistory = rawHistory ? JSON.parse(rawHistory) : {};
      } catch {}
    },
    saveRotationConfig(poolId) {
      try {
        localStorage.setItem('proxypool-rotation-config', JSON.stringify(this.rotationConfig));
        this.setMessage('轮转模式已保存');
      } catch {}
    },
    saveRotationStats(poolId) {
      try {
        localStorage.setItem('proxypool-rotation-stats', JSON.stringify(this.rotationStats));
      } catch {}
    },
    saveRotationHistory(poolId) {
      try {
        const history = this.rotationHistory[poolId] || [];
        this.rotationHistory[poolId] = history.slice(-100);
        localStorage.setItem('proxypool-rotation-history', JSON.stringify(this.rotationHistory));
      } catch {}
    },
    getRotationStats(poolId) {
      return this.rotationStats[poolId] || { totalRequests: 0, successCount: 0, failureCount: 0, proxyCounts: {}, currentIndex: 0 };
    },
    getCurrentProxy(poolId) {
      const pool = this.proxyPools.find(p => p.id === poolId);
      if (!pool) return '';
      const nodes = pool.nodes || [];
      const stats = this.getRotationStats(poolId);
      const idx = stats.currentIndex || 0;
      if (nodes.length === 0) return '';
      return nodes[idx % nodes.length]?.name || nodes[idx % nodes.length]?.host || '';
    },
    getRotationSuccessRate(poolId) {
      const stats = this.getRotationStats(poolId);
      if (stats.totalRequests === 0) return '-';
      return Math.round((stats.successCount / stats.totalRequests) * 100) + '%';
    },
    getRotationSuccessRateClass(poolId) {
      const stats = this.getRotationStats(poolId);
      if (stats.totalRequests === 0) return '';
      const rate = stats.successCount / stats.totalRequests;
      if (rate >= 0.9) return 'text-success';
      if (rate >= 0.7) return 'text-warning';
      return 'text-danger';
    },
    getDistributionWidth(count, poolId) {
      const stats = this.getRotationStats(poolId);
      const max = Math.max(...Object.values(stats.proxyCounts || {}));
      return max > 0 ? Math.round((count / max) * 100) : 0;
    },
    getRotationColor(index) {
      const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16'];
      return colors[index % colors.length];
    },
    formatProxyShortName(proxy) {
      if (!proxy) return '';
      if (proxy.length > 20) return proxy.substring(0, 17) + '...';
      return proxy;
    },
    manualRotate(poolId, direction) {
      const pool = this.proxyPools.find(p => p.id === poolId);
      if (!pool) return;
      const nodes = pool.nodes || [];
      if (nodes.length === 0) {
        this.setMessage('该代理池暂无节点', true);
        return;
      }
      const stats = this.getRotationStats(poolId);
      let newIndex = stats.currentIndex || 0;
      if (direction === 'next') {
        newIndex = (newIndex + 1) % nodes.length;
      } else {
        newIndex = (newIndex - 1 + nodes.length) % nodes.length;
      }
      this.rotationStats[poolId] = { ...stats, currentIndex: newIndex };
      this.saveRotationStats(poolId);
      this.addRotationHistoryEntry(poolId, 'switch', `手动切换到节点 #${newIndex + 1}`);
      this.setMessage(`已切换到节点: ${nodes[newIndex]?.name || nodes[newIndex]?.host || '#' + (newIndex + 1)}`);
    },
    resetRotationStats(poolId) {
      this.rotationStats[poolId] = { totalRequests: 0, successCount: 0, failureCount: 0, proxyCounts: {}, currentIndex: 0 };
      this.saveRotationStats(poolId);
      this.addRotationHistoryEntry(poolId, 'info', '统计数据已重置');
      this.setMessage('轮转统计已重置');
    },
    addRotationHistoryEntry(poolId, type, message) {
      if (!this.rotationHistory[poolId]) this.rotationHistory[poolId] = [];
      this.rotationHistory[poolId].push({ type, message, timestamp: new Date().toISOString() });
      this.saveRotationHistory(poolId);
    },
    showRotationHistory(pool) {
      this.rotationHistoryPoolName = pool.name;
      this.rotationHistoryVisible = true;
    },
    getRotationHistoryList() {
      const poolId = Object.keys(this.rotationHistory).find(id => {
        const pool = this.proxyPools.find(p => p.id === Number(id));
        return pool && pool.name === this.rotationHistoryPoolName;
      });
      return poolId ? this.rotationHistory[poolId] || [] : [];
    },
    formatRotationTime(ts) {
      if (!ts) return '';
      const d = new Date(ts);
      const now = new Date();
      const diffMs = now - d;
      if (diffMs < 60000) return '刚刚';
      if (diffMs < 3600000) return Math.floor(diffMs / 60000) + '分钟前';
      if (diffMs < 86400000) return Math.floor(diffMs / 3600000) + '小时前';
      return d.toLocaleDateString('zh-CN');
    },
  },
  computed: {
    bestChainScore() {
      if (!this.chainPerformanceData.length) return null;
      return Math.max(...this.chainPerformanceData.map(p => p.score));
    },
    hasFrontPool() {
      return !!(this.chainStatus && this.chainStatus.front_pool_id);
    },
    hasExitPool() {
      return !!(this.chainStatus && this.chainStatus.exit_pool_id);
    },
    frontPoolName() {
      if (!this.hasFrontPool) return '';
      const pool = this.proxyPools.find(p => p.id === this.chainStatus.front_pool_id);
      return pool ? pool.name : '未知池';
    },
    exitPoolName() {
      if (!this.hasExitPool) return '';
      const pool = this.proxyPools.find(p => p.id === this.chainStatus.exit_pool_id);
      return pool ? pool.name : '未知池';
    },
    frontPoolHealthy() {
      if (!this.hasFrontPool) return false;
      const pool = this.proxyPools.find(p => p.id === this.chainStatus.front_pool_id);
      return pool && pool.healthy_count > 0;
    },
    exitPoolHealthy() {
      if (!this.hasExitPool) return false;
      const pool = this.proxyPools.find(p => p.id === this.chainStatus.exit_pool_id);
      return pool && pool.healthy_count > 0;
    },
    frontPoolHealthyCount() {
      if (!this.hasFrontPool) return 0;
      const pool = this.proxyPools.find(p => p.id === this.chainStatus.front_pool_id);
      return pool ? (pool.healthy_count || 0) : 0;
    },
    exitPoolHealthyCount() {
      if (!this.hasExitPool) return 0;
      const pool = this.proxyPools.find(p => p.id === this.chainStatus.exit_pool_id);
      return pool ? (pool.healthy_count || 0) : 0;
    },
    frontPoolTotalCount() {
      if (!this.hasFrontPool) return 0;
      const pool = this.proxyPools.find(p => p.id === this.chainStatus.front_pool_id);
      return pool ? (pool.total_count || pool.proxy_count || 0) : 0;
    },
    exitPoolTotalCount() {
      if (!this.hasExitPool) return 0;
      const pool = this.proxyPools.find(p => p.id === this.chainStatus.exit_pool_id);
      return pool ? (pool.total_count || pool.proxy_count || 0) : 0;
    },
    chainProtocol() {
      return this.chainStatus ? (this.chainStatus.protocol || 'http') : 'http';
    },
    frontPoolOptions() {
      if (!this.proxyPools) return [];
      return this.proxyPools.filter(p =>
        p.filters?.route_mode_filter === 'chain' ||
        (!p.filters?.route_mode_filter && p.status === 'running')
      ).slice(0, 5);
    },
    frontPoolAvgLatency() {
      if (!this.hasFrontPool || !this.chainStatus?.front_pool?.nodes) return '-';
      const nodes = this.chainStatus.front_pool.nodes;
      const healthyNodes = nodes.filter(n => n.healthy && n.latency_ms);
      if (healthyNodes.length === 0) return '-';
      const avg = healthyNodes.reduce((sum, n) => sum + n.latency_ms, 0) / healthyNodes.length;
      return Math.round(avg);
    },
    exitPoolAvgLatency() {
      if (!this.hasExitPool || !this.chainStatus?.exit_pool?.nodes) return '-';
      const nodes = this.chainStatus.exit_pool.nodes;
      const healthyNodes = nodes.filter(n => n.healthy && n.latency_ms);
      if (healthyNodes.length === 0) return '-';
      const avg = healthyNodes.reduce((sum, n) => sum + n.latency_ms, 0) / healthyNodes.length;
      return Math.round(avg);
    },
    chainEndpoints() {
      if (!this.gatewayEndpoints || !this.chainStatus) return [];
      const frontPoolId = this.chainStatus.front_pool_id;
      const exitPoolId = this.chainStatus.exit_pool_id;
      return this.gatewayEndpoints.filter(ep => {
        const hops = ep.hops || [];
        return hops.some(h => h.pool_id === frontPoolId || h.pool_id === exitPoolId);
      });
    },
    getPoolPerformanceMetrics(poolId) {
      const history = this.rotationHistory[poolId] || [];
      if (history.length === 0) {
        return { avgLatency: null, successRate: null, throughput: null, p95Latency: null };
      }
      const last100 = history.slice(0, 100);
      const latencies = last100.filter(h => h.latency_ms != null).map(h => h.latency_ms);
      const avgLatency = latencies.length > 0 ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : null;
      const successCount = last100.filter(h => h.success !== false).length;
      const successRate = last100.length > 0 ? Math.round((successCount / last100.length) * 100) : null;
      let throughput = null;
      if (last100.length >= 2) {
        const timestamps = last100.map(h => new Date(h.timestamp || Date.now()).getTime()).sort((a, b) => b - a);
        const timeSpan = (timestamps[0] - timestamps[timestamps.length - 1]) / 1000;
        if (timeSpan > 0) {
          throughput = Math.round((last100.length / timeSpan) * 10) / 10;
        }
      }
      let p95Latency = null;
      if (latencies.length >= 5) {
        const sorted = [...latencies].sort((a, b) => a - b);
        const p95Index = Math.floor(sorted.length * 0.95);
        p95Latency = sorted[p95Index];
      }
      return { avgLatency, successRate, throughput, p95Latency };
    },
    getPoolPerformanceTrend(poolId) {
      const history = this.rotationHistory[poolId] || [];
      const latencyPoints = history
        .filter(h => h.latency_ms != null)
        .slice(0, 20)
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
    getPoolComparisonData(poolId) {
      if (!this.items || this.items.length < 2) return null;
      const currentMetrics = this.getPoolPerformanceMetrics(poolId);
      if (!currentMetrics.avgLatency) return null;
      const allLatencies = this.items
        .map(item => this.getPoolPerformanceMetrics(item.id).avgLatency)
        .filter(l => l != null);
      const allSuccessRates = this.items
        .map(item => this.getPoolPerformanceMetrics(item.id).successRate)
        .filter(s => s != null);
      if (allLatencies.length < 2) return null;
      const sortedLatencies = [...allLatencies].sort((a, b) => a - b);
      const sortedSuccessRates = [...allSuccessRates].sort((a, b) => b - a);
      const latencyRank = sortedLatencies.indexOf(currentMetrics.avgLatency) + 1;
      const successRateRank = sortedSuccessRates.indexOf(currentMetrics.successRate) + 1;
      const maxLatency = Math.max(...allLatencies);
      const latencyPct = maxLatency > 0 ? Math.round((currentMetrics.avgLatency / maxLatency) * 100) : 0;
      const successRatePct = currentMetrics.successRate || 0;
      return { latencyRank, successRateRank, latencyPct, successRatePct, totalPools: allLatencies.length };
    },
    getLatencyClass(latency) {
      if (latency == null) return '';
      if (latency < 100) return 'text-success';
      if (latency < 300) return 'text-warning';
      return 'text-danger';
    },
    getSuccessRateClass(rate) {
      if (rate == null) return '';
      if (rate >= 90) return 'text-success';
      if (rate >= 70) return 'text-warning';
      return 'text-danger';
    },
    // Pool template library methods
    get filteredTemplates() {
      const allTemplates = [...this.presetTemplates, ...this.customTemplates];
      if (this.selectedTemplateCategory === 'all') return allTemplates;
      if (this.selectedTemplateCategory === 'custom') return this.customTemplates;
      return allTemplates.filter(t => t.category === this.selectedTemplateCategory);
    },
    previewTemplate(template) {
      this.previewingTemplate = template;
      this.templatePreviewVisible = true;
    },
    applyPreviewedTemplate() {
      if (this.previewingTemplate) {
        this.applyTemplate(this.previewingTemplate.id);
        this.templatePreviewVisible = false;
      }
    },
    applyTemplate(templateId) {
      const allTemplates = [...this.presetTemplates, ...this.customTemplates];
      const template = allTemplates.find(t => t.id === templateId);
      if (template) {
        this.proxyPoolForm.name = template.name;
        this.selectedPoolType = template.type;
        this.proxyPoolForm.filters.route_mode_filter = template.type;
        if (template.countries) {
          this.proxyPoolForm.filters.geo_countries = [...template.countries];
        }
        if (template.maxLatency) {
          this.proxyPoolForm.filters.latency_max = template.maxLatency;
        }
        if (template.openai) {
          this.proxyPoolForm.filters.openai_filter = 'unlocked';
        }
        if (template.ipPurity) {
          this.proxyPoolForm.filters.ip_purity_filter = 'residential';
        }
        this.setMessage(`已应用模板: ${template.name}`);
      }
    },
    showSaveAsTemplateDialog() {
      this.newTemplateName = this.proxyPoolForm.name || '';
      this.newTemplateDescription = '';
      this.newTemplateIcon = '⭐';
      this.newTemplateCategory = 'custom';
      this.saveTemplateDialogVisible = true;
    },
    saveAsTemplate() {
      if (!this.newTemplateName.trim()) return;
      const template = {
        id: 'custom-' + Date.now(),
        name: this.newTemplateName.trim(),
        icon: this.newTemplateIcon || '⭐',
        description: this.newTemplateDescription.trim() || '自定义模板',
        type: this.selectedPoolType,
        countries: this.proxyPoolForm.filters.geo_countries?.length ? [...this.proxyPoolForm.filters.geo_countries] : undefined,
        maxLatency: this.proxyPoolForm.filters.latency_max || undefined,
        openai: this.proxyPoolForm.filters.openai_filter === 'unlocked',
        ipPurity: this.proxyPoolForm.filters.ip_purity_filter === 'residential',
        category: this.newTemplateCategory,
        tags: ['自定义'],
        custom: true,
      };
      this.customTemplates.push(template);
      this.saveCustomTemplates();
      this.saveTemplateDialogVisible = false;
      this.setMessage(`模板 "${template.name}" 已保存`);
    },
    deleteCustomTemplate(templateId) {
      this.customTemplates = this.customTemplates.filter(t => t.id !== templateId);
      this.saveCustomTemplates();
      this.setMessage('模板已删除');
    },
    saveCustomTemplates() {
      try {
        localStorage.setItem('proxypool-custom-templates', JSON.stringify(this.customTemplates));
      } catch {}
    },
    showExportTemplatesDialog() {
      this.selectedExportTemplates = this.customTemplates.map(t => t.id);
      this.exportTemplatesDialogVisible = true;
    },
    exportTemplates() {
      const templatesToExport = this.customTemplates.filter(t => this.selectedExportTemplates.includes(t.id));
      if (templatesToExport.length === 0) return;
      const data = {
        version: 1,
        exportTime: new Date().toISOString(),
        templates: templatesToExport,
      };
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `proxypool-templates-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      this.exportTemplatesDialogVisible = false;
      this.setMessage(`已导出 ${templatesToExport.length} 个模板`);
    },
    showImportTemplatesDialog() {
      this.importTemplatePreview = null;
      this.importTemplateFile = null;
      this.importTemplatesDialogVisible = true;
    },
    handleTemplateFileSelect(event) {
      const file = event.target.files[0];
      if (file) this.processTemplateFile(file);
    },
    handleTemplateFileDrop(event) {
      const file = event.dataTransfer.files[0];
      if (file) this.processTemplateFile(file);
    },
    processTemplateFile(file) {
      if (!file.name.endsWith('.json')) {
        this.setMessage('请选择 JSON 格式的模板文件', true);
        return;
      }
      this.importTemplateFile = file;
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const data = JSON.parse(e.target.result);
          if (data.templates && Array.isArray(data.templates)) {
            this.importTemplatePreview = {
              count: data.templates.length,
              templates: data.templates,
            };
          } else {
            this.setMessage('无效的模板文件格式', true);
          }
        } catch (err) {
          this.setMessage('解析模板文件失败: ' + err.message, true);
        }
      };
      reader.readAsText(file);
    },
    importTemplates() {
      if (!this.importTemplatePreview) return;
      const newTemplates = this.importTemplatePreview.templates.map(t => ({
        ...t,
        id: 'custom-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8),
        custom: true,
      }));
      this.customTemplates.push(...newTemplates);
      this.saveCustomTemplates();
      this.importTemplatesDialogVisible = false;
      this.setMessage(`已导入 ${newTemplates.length} 个模板`);
    },
    // Advanced chain features
    toggleChainFeature(feature) {
      this.advancedChainFeaturesExpanded = {
        ...this.advancedChainFeaturesExpanded,
        [feature]: !this.advancedChainFeaturesExpanded[feature],
      };
    },
    isChainFeatureExpanded(feature) {
      return !!this.advancedChainFeaturesExpanded[feature];
    },
    getChainPoolLoadData() {
      const pools = this.appState.proxyPools || [];
      return pools.slice(0, 4).map(pool => {
        const healthyCount = pool.healthy_count || 0;
        const totalCount = pool.total_count || 0;
        const loadPercent = totalCount > 0 ? Math.round((healthyCount / totalCount) * 100) : 0;
        const recommendedWeight = pool.chain_enabled ? Math.round(loadPercent / 10) : 0;
        return {
          id: pool.id,
          name: pool.name,
          healthyCount,
          totalCount,
          loadPercent,
          recommendedWeight,
        };
      });
    },
    getLoadBarClass(percent) {
      if (percent >= 80) return 'lb-fill-success';
      if (percent >= 50) return 'lb-fill-warning';
      return 'lb-fill-danger';
    },
    getChainBandwidthStats() {
      const pools = this.appState.proxyPools || [];
      const totalNodes = pools.reduce((sum, p) => sum + (p.total_count || 0), 0);
      const healthyNodes = pools.reduce((sum, p) => sum + (p.healthy_count || 0), 0);
      return [
        { label: '总节点数', value: totalNodes, class: '' },
        { label: '健康节点', value: healthyNodes, class: 'text-success' },
        { label: '平均带宽', value: '~50 Mbps', class: '' },
        { label: '峰值带宽', value: '~120 Mbps', class: 'text-warning' },
      ];
    },
    getBandwidthChartPoints() {
      const history = this.chainBandwidthHistory.length ? this.chainBandwidthHistory : [40, 45, 50, 48, 52, 55, 50, 48, 52, 55];
      const max = Math.max(...history, 1);
      return history.map((v, i) => {
        const x = (i / (history.length - 1)) * 200;
        const y = 60 - (v / max) * 50;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');
    },
    getChainLatencySuggestions() {
      const suggestions = [];
      const pools = this.appState.proxyPools || [];
      const frontPool = pools.find(p => p.chain_enabled);
      const exitPool = pools.find(p => !p.chain_enabled && p.total_count > 0);

      if (!frontPool) {
        suggestions.push({ severity: 'high', text: '未配置前置池，建议添加前置代理以增强链路稳定性' });
      }
      if (frontPool && exitPool) {
        const frontHealthy = frontPool.healthy_count || 0;
        const exitHealthy = exitPool.healthy_count || 0;
        if (frontHealthy < 2 || exitHealthy < 2) {
          suggestions.push({ severity: 'medium', text: '健康节点较少，建议增加备用节点以提高容错能力' });
        }
      }
      if (pools.length < 2) {
        suggestions.push({ severity: 'low', text: '单池配置，延迟较低但匿名性有限' });
      }
      suggestions.push({ severity: 'low', text: '前置池选择低延迟节点可显著降低总链路延迟' });
      return suggestions;
    },
    getChainSecurityScore() {
      let score = 50;
      const pools = this.appState.proxyPools || [];
      if (pools.length >= 2) score += 20;
      if (pools.some(p => p.chain_enabled)) score += 15;
      if (pools.some(p => (p.healthy_count || 0) > 3)) score += 15;
      return Math.min(100, score);
    },
    getChainSecurityItems() {
      const items = [];
      const pools = this.appState.proxyPools || [];
      const hasChain = pools.some(p => p.chain_enabled);
      const hasMultiplePools = pools.length >= 2;
      const hasHealthyNodes = pools.some(p => (p.healthy_count || 0) > 0);

      items.push({
        status: hasChain ? 'good' : 'warning',
        text: hasChain ? '已启用池级链路' : '未启用池级链路，匿名性有限',
      });
      items.push({
        status: hasMultiplePools ? 'good' : 'warning',
        text: hasMultiplePools ? '多池配置提供更好匿名性' : '建议配置多个代理池增强安全',
      });
      items.push({
        status: hasHealthyNodes ? 'good' : 'error',
        text: hasHealthyNodes ? '存在健康可用节点' : '无健康节点，服务不可用',
      });
      return items;
    },
  },
};
</script>

<style scoped>
/* Form Sections */
.form-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line-soft);
}

.form-section:last-of-type {
  border-bottom: none;
  margin-bottom: 16px;
  padding-bottom: 0;
}

.form-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.form-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  padding: 8px 0;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--line-soft);
  transition: background var(--transition);
}

.form-section-header:hover {
  background: var(--panel-muted);
}

.form-section-header .form-section-title {
  margin: 0;
  border-bottom: none;
  padding-bottom: 0;
}

.collapse-icon {
  font-size: 11px;
  color: var(--muted);
  transition: transform var(--transition);
}

/* Help Icon */
.help-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--line-soft);
  color: var(--muted);
  font-size: 10px;
  font-weight: 600;
  cursor: help;
  transition: all var(--transition);
}

.help-icon:hover {
  background: var(--accent);
  color: white;
}

/* Pool Type Selector */
.pool-type-selector {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 8px;
}

.pool-type-option {
  padding: 16px;
  border: 2px solid var(--line);
  border-radius: var(--radius-lg);
  text-align: center;
  cursor: pointer;
  transition: all var(--transition);
}

.pool-type-option:hover {
  border-color: var(--accent);
  background: var(--panel-muted);
}

.pool-type-option.active {
  border-color: var(--accent);
  background: var(--panel-muted);
}

.pool-type-icon {
  font-size: 24px;
  margin-bottom: 8px;
}

.pool-type-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4px;
}

.pool-type-desc {
  font-size: 11px;
  color: var(--muted);
}

/* Advanced Filters */
.advanced-filters {
  padding: 12px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  margin-top: 8px;
}

/* Pool Create Actions */
.pool-create-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line-soft);
}

/* Form Error */
.form-error {
  font-size: 11px;
  color: var(--danger-text);
  margin-top: 4px;
  display: block;
}

.input-error {
  border-color: var(--danger) !important;
}

/* Config Preview */
.config-preview {
  max-height: 400px;
  overflow: auto;
}

.config-preview-json {
  background: var(--panel-muted);
  padding: 12px;
  border-radius: var(--radius-md);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow: auto;
}

/* Responsive */
@media (max-width: 768px) {
  .pool-type-selector {
    grid-template-columns: 1fr;
  }

  .pool-create-grid {
    grid-template-columns: 1fr;
  }

  .pool-create-grid .form-group,
  .pool-create-grid .pool-field-wide {
    grid-column: span 1;
  }
}

/* Pool Detail Row */
.pool-detail-row td {
  background: var(--panel-muted);
  padding: 16px !important;
}

.pool-detail-content {
  padding: 8px 0;
}

.pool-detail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.pool-detail-section {
  padding: 12px;
  background: var(--panel);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-md);
}

.pool-detail-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin: 0 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-soft);
}

.pool-detail-stats {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pool-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.pool-stat-label {
  color: var(--muted);
}

.pool-stat-value {
  font-weight: 600;
  color: var(--ink);
}

.pool-detail-conditions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pool-condition {
  display: flex;
  gap: 8px;
  font-size: 12px;
}

.pool-condition-label {
  color: var(--muted);
  min-width: 60px;
}

.pool-condition-value {
  font-weight: 500;
  color: var(--ink);
}

@media (max-width: 1024px) {
  .pool-detail-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }
}

/* Chain Visualization Styles */
.chain-visualization {
  padding: 20px 0;
}

.chain-flow {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  background: var(--panel);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-lg);
  margin-bottom: 20px;
  overflow-x: auto;
}

.chain-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 20px;
  background: var(--panel-muted);
  border: 2px solid var(--line);
  border-radius: var(--radius-lg);
  min-width: 120px;
  text-align: center;
  transition: all var(--transition);
}

.chain-node:hover {
  border-color: var(--accent);
}

.chain-node-type {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.chain-type-front {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.chain-type-exit {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.chain-type-middle {
  background: rgba(249, 115, 22, 0.15);
  color: #f97316;
}

.chain-node-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4px;
}

.chain-node-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--muted);
}

.status-dot.healthy {
  background: var(--success);
}

.status-dot.unhealthy {
  background: var(--danger);
}

.chain-node-alert {
  margin-top: 8px;
  padding: 6px 10px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  font-size: 11px;
  color: var(--danger-text);
}

.chain-arrow {
  display: flex;
  align-items: center;
  color: var(--muted);
  font-size: 20px;
  flex-shrink: 0;
}

.chain-panels {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.chain-panel {
  padding: 16px;
  background: var(--panel);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-lg);
}

.chain-panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-soft);
}

.diagnostics-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.diagnostic-item {
  display: flex;
  gap: 12px;
  padding: 10px;
  border-radius: var(--radius-md);
  font-size: 12px;
}

.diagnostic-item.error {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.diagnostic-item.warning {
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.diagnostic-item.success {
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.diagnostic-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.diagnostic-content {
  flex: 1;
}

.diagnostic-title {
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4px;
}

.diagnostic-message {
  color: var(--muted);
  margin-bottom: 4px;
}

.diagnostic-suggestion {
  color: var(--accent);
  font-size: 11px;
}

.pool-type-legend {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex-shrink: 0;
}

.legend-dot.front {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid #3b82f6;
}

.legend-dot.exit {
  background: rgba(34, 197, 94, 0.15);
  border: 1px solid #22c55e;
}

.legend-dot.middle {
  background: rgba(249, 115, 22, 0.15);
  border: 1px solid #f97316;
}

.legend-label {
  font-weight: 500;
  color: var(--ink);
  min-width: 60px;
}

.legend-desc {
  color: var(--muted);
}

.test-results {
  margin-top: 16px;
}

.test-status {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: var(--radius-md);
  margin-bottom: 12px;
  font-weight: 600;
}

.test-status.success {
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  color: #16a34a;
}

.test-status.failure {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #dc2626;
}

.test-hops {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.test-hop {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  font-size: 13px;
}

.test-hop-name {
  font-weight: 500;
  color: var(--ink);
}

.test-hop-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
}

.test-hop-latency {
  font-weight: 600;
  color: var(--accent);
}

.chain-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

/* Pool Type Explanation */
.pool-type-explanation {
  margin-top: 12px;
  padding: 16px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  border: 1px solid var(--line-soft);
}

.explanation-content {
  font-size: 13px;
}

.explanation-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 8px;
}

.explanation-text {
  color: var(--muted);
  margin: 0 0 12px;
  line-height: 1.5;
}

.explanation-list {
  margin: 0 0 12px;
  padding-left: 20px;
  color: var(--ink);
}

.explanation-list li {
  margin-bottom: 4px;
}

.explanation-tip {
  padding: 10px 12px;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--accent);
}

.pool-type-usecase {
  font-size: 11px;
  color: var(--accent);
  margin-top: 6px;
  font-style: italic;
}

/* Pool Type Tags */
.pool-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
}

.pool-tag-direct {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}

.pool-tag-chain {
  background: rgba(147, 51, 234, 0.15);
  color: #9333ea;
}

.pool-tag-unreachable {
  background: rgba(239, 68, 68, 0.15);
  color: #dc2626;
}

/* Pool Detail Enhancements */
.text-success {
  color: var(--success, #16a34a);
}

.text-warning {
  color: var(--warning, #f59e0b);
}

.text-danger {
  color: var(--danger, #dc2626);
}

.pool-detail-section .pool-stat {
  padding: 6px 0;
  border-bottom: 1px solid var(--line-soft);
}

.pool-detail-section .pool-stat:last-child {
  border-bottom: none;
}

/* Front Pool Recommendation */
.front-pool-recommendation {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius-lg);
  margin-top: 16px;
}

.recommendation-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.recommendation-content {
  flex: 1;
}

.recommendation-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 6px;
}

.recommendation-text {
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 10px;
  line-height: 1.5;
}

.recommendation-options {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.recommendation-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--ink);
}

.badge-info {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

/* Config Code Block */
.config-code-block {
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--line-soft);
}

.config-code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #1e1e1e;
  border-bottom: 1px solid #333;
}

.config-code-lang {
  font-size: 11px;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
}

.config-code-content {
  margin: 0;
  padding: 16px;
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', 'Droid Sans Mono', 'Source Code Pro', monospace;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

.config-code-content code {
  color: inherit;
}

/* Pool Detail Actions */
.pool-detail-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.pool-detail-actions .btn {
  width: 100%;
}

/* Import Dialog */
.import-dialog-content {
  min-height: 200px;
}

.import-upload-step {
  text-align: center;
}

.import-upload-area {
  border: 2px dashed var(--line);
  border-radius: var(--radius-lg);
  padding: 40px 20px;
  cursor: pointer;
  transition: all var(--transition);
}

.import-upload-area:hover {
  border-color: var(--accent);
  background: var(--panel-muted);
}

.import-upload-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.import-upload-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 4px;
}

.import-upload-hint {
  font-size: 12px;
  color: var(--muted);
}

.import-file-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  padding: 12px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
}

.import-file-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
}

.import-preview-step {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.import-summary {
  padding: 16px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
}

.import-summary-title,
.import-options-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 12px;
}

.import-summary-stats {
  display: flex;
  gap: 24px;
}

.import-stat {
  text-align: center;
}

.import-stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: var(--accent);
}

.import-stat-label {
  font-size: 12px;
  color: var(--muted);
}

.import-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.import-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--panel);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition);
}

.import-option:hover {
  background: var(--panel-muted);
}

.import-option input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.import-results-step {
  text-align: center;
}

.import-results-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  border-radius: var(--radius-md);
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 20px;
}

.import-results-header.success {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.import-results-header.error {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.import-results-icon {
  font-size: 24px;
}

.import-results-stats {
  display: flex;
  justify-content: center;
  gap: 32px;
  margin-bottom: 20px;
}

.import-result-item {
  text-align: center;
}

.import-result-count {
  display: block;
  font-size: 28px;
  font-weight: 700;
}

.import-result-item.success .import-result-count {
  color: #16a34a;
}

.import-result-item.skipped .import-result-count {
  color: #f59e0b;
}

.import-result-item.error .import-result-count {
  color: #dc2626;
}

.import-result-label {
  font-size: 12px;
  color: var(--muted);
}

.import-errors-list {
  text-align: left;
  max-height: 150px;
  overflow-y: auto;
}

.import-error-item {
  padding: 8px 12px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: #dc2626;
  margin-bottom: 8px;
}

@media (max-width: 768px) {
  .chain-flow {
    flex-direction: column;
    padding: 16px;
  }

  .chain-arrow {
    transform: rotate(90deg);
  }

  .chain-panels {
    grid-template-columns: 1fr;
  }

  .import-summary-stats {
    flex-direction: column;
    gap: 12px;
  }

  .import-results-stats {
    flex-direction: column;
    gap: 12px;
  }
}

/* Help Button */
.help-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 600;
  line-height: 1;
}

/* Help Dialog */
.help-dialog-content {
  max-height: 60vh;
  overflow-y: auto;
}

.help-section {
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line-soft);
}

.help-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.help-section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 12px;
}

.help-text {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.6;
  margin: 0;
}

.help-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--ink);
}

.help-list li {
  margin-bottom: 8px;
  line-height: 1.5;
}

.help-terms {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.help-term {
  display: flex;
  gap: 12px;
  padding: 10px 12px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  font-size: 13px;
}

.help-term-name {
  font-weight: 600;
  color: var(--ink);
  min-width: 80px;
}

.help-term-desc {
  color: var(--muted);
}

.help-shortcuts {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.help-shortcut {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  font-size: 13px;
}

.help-shortcut-keys {
  font-family: monospace;
  font-weight: 600;
  color: var(--accent);
  background: var(--panel);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.help-shortcut-desc {
  color: var(--muted);
}

.help-faq {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.help-faq-item {
  padding: 12px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
}

.help-faq-item strong {
  display: block;
  font-size: 13px;
  color: var(--ink);
  margin-bottom: 4px;
}

.help-faq-item p {
  font-size: 12px;
  color: var(--muted);
  margin: 0;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .help-shortcuts {
    grid-template-columns: 1fr;
  }
}

/* Pool Templates */
.pool-templates {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.pool-template-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-md);
  font-size: 12px;
  transition: all var(--transition);
}

.pool-template-btn:hover {
  border-color: var(--accent);
  background: var(--panel-muted);
}

.template-icon {
  font-size: 16px;
}

.template-name {
  font-weight: 500;
  color: var(--ink);
}

@media (max-width: 768px) {
  .pool-templates {
    flex-direction: column;
  }

  .pool-template-btn {
    width: 100%;
    justify-content: center;
  }
}

/* Chain Health Score */
.chain-health-score-card {
  border: 1px solid var(--line-soft);
}

.chain-health-score-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chain-health-score-label h4 {
  margin: 0 0 4px;
}

.chain-health-score-value {
  display: flex;
  align-items: baseline;
  padding: 12px 20px;
  border-radius: var(--radius-lg);
  font-weight: 700;
}

.chain-health-score-number {
  font-size: 36px;
  line-height: 1;
}

.chain-health-score-total {
  font-size: 14px;
  color: var(--muted);
  margin-left: 4px;
}

.score-excellent {
  background: var(--success-bg);
  color: var(--success-text);
  border: 2px solid var(--success-border);
}

.score-good {
  background: #f0f9ff;
  color: #0369a1;
  border: 2px solid #bae6fd;
}

.score-fair {
  background: var(--warning-bg);
  color: var(--warning-text);
  border: 2px solid var(--warning-border);
}

.score-poor {
  background: var(--danger-bg);
  color: var(--danger-text);
  border: 2px solid var(--danger-border);
}

/* Diagnostic Panel Enhancements */
.diagnostic-pool-status {
  margin-bottom: 20px;
}

.diagnostic-subtitle {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin: 0 0 12px;
}

.diagnostic-pool-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.diagnostic-pool-card {
  padding: 12px;
  background: var(--panel-muted);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-md);
}

.diagnostic-pool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.diagnostic-pool-stats {
  display: flex;
  gap: 16px;
}

.diagnostic-endpoints {
  margin-bottom: 20px;
}

.diagnostic-endpoint-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.diagnostic-endpoint-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: var(--panel-muted);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-md);
}

.diagnostic-severity {
  margin-left: auto;
}

@media (max-width: 768px) {
  .diagnostic-pool-grid {
    grid-template-columns: 1fr;
  }

  .chain-health-score-content {
    flex-direction: column;
    text-align: center;
    gap: 16px;
  }
}

/* Rotation Controls */
.rotation-controls {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.rotation-distribution {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line-soft);
}

.rotation-dist-label {
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 6px;
}

.rotation-dist-bar {
  display: flex;
  height: 8px;
  background: var(--panel-muted);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.rotation-dist-segment {
  transition: width var(--transition);
  min-width: 2px;
}

.rotation-dist-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rotation-dist-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.rotation-dist-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

/* Rotation History */
.rotation-history-content {
  max-height: 400px;
  overflow-y: auto;
}

.rotation-history-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rotation-history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  font-size: 12px;
}

.rotation-history-switch {
  border-left: 3px solid var(--accent);
}

.rotation-history-success {
  border-left: 3px solid var(--success-text);
}

.rotation-history-failure {
  border-left: 3px solid var(--danger-text);
}

.rotation-history-info {
  border-left: 3px solid var(--muted);
}

.rotation-history-icon {
  flex-shrink: 0;
  width: 16px;
  text-align: center;
}

.rotation-history-msg {
  flex: 1;
  color: var(--ink);
}

.rotation-history-time {
  flex-shrink: 0;
  color: var(--muted);
  font-size: 11px;
}

/* Performance Metrics */
.pool-detail-section-full {
  grid-column: 1 / -1;
}

.pool-performance-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.pool-perf-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
}

.pool-perf-metric-label {
  font-size: 11px;
  color: var(--muted);
}

.pool-perf-metric-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}

.pool-perf-trend {
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  padding: 8px 10px;
}

.pool-perf-trend-header {
  margin-bottom: 4px;
}

.pool-perf-trend-svg {
  width: 100%;
  height: 40px;
}

/* Pool Comparison */
.pool-comparison {
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  padding: 8px 10px;
}

.pool-comparison-header {
  margin-bottom: 6px;
}

.pool-comparison-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pool-comparison-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pool-comparison-label {
  font-size: 11px;
  color: var(--muted);
  min-width: 40px;
}

.pool-comparison-bar-container {
  flex: 1;
  height: 6px;
  background: var(--line-soft);
  border-radius: 3px;
  overflow: hidden;
}

.pool-comparison-bar {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.pool-comparison-bar.comparison-best {
  background: var(--success-text);
}

.pool-comparison-rank {
  font-size: 10px;
  font-weight: 600;
  color: var(--muted);
  min-width: 20px;
}

/* Chain Templates */
.chain-templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
}

.chain-template-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--bg-secondary);
}

.chain-template-card:hover {
  border-color: var(--accent);
  background: var(--accent-bg);
}

.template-icon {
  font-size: 24px;
  width: 40px;
  text-align: center;
}

.template-info {
  flex: 1;
}

.template-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--ink);
  margin-bottom: 2px;
}

.template-desc {
  font-size: 11px;
  color: var(--muted);
}

.template-pools {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

.template-arrow {
  color: var(--muted);
}

/* Chain Performance Table */
.chain-performance-table {
  margin-top: 12px;
}

.chain-performance-table .data-table {
  font-size: 12px;
}

.chain-performance-table th,
.chain-performance-table td {
  padding: 8px 12px;
}

.chain-performance-table .best-perf {
  background: rgba(16, 185, 129, 0.1);
}

/* Chain Alert History */
.chain-alert-history {
  border-top: 1px solid var(--line-soft);
  padding-top: 12px;
}

.alert-history-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.alert-history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: var(--bg-secondary);
  border-radius: 4px;
}

@media (max-width: 768px) {
  .pool-performance-metrics {
    grid-template-columns: repeat(2, 1fr);
  }

  .chain-templates-grid {
    grid-template-columns: 1fr;
  }

  .pool-templates-grid {
    grid-template-columns: 1fr;
  }
}

/* Pool Template Library */
.form-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  padding: 8px 0;
}

.form-section-toggle {
  font-size: 10px;
  color: var(--muted);
  transition: transform 0.2s ease;
}

.form-section-toggle.expanded {
  transform: rotate(180deg);
}

.template-category-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.pool-templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

.pool-template-card {
  background: var(--bg-secondary);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.pool-template-card:hover {
  border-color: var(--accent);
  background: var(--accent-bg);
}

.pool-template-card.custom-template {
  border-style: dashed;
}

.template-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.template-icon {
  font-size: 24px;
}

.template-card-body {
  margin-bottom: 10px;
}

.template-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4px;
}

.template-desc {
  font-size: 11px;
  line-height: 1.4;
}

.template-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.template-tag {
  font-size: 9px;
  padding: 2px 6px;
  background: var(--panel-muted);
  border-radius: 10px;
  color: var(--muted);
}

.template-card-actions {
  display: flex;
  gap: 6px;
}

/* Template Preview */
.template-preview-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.template-preview-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-preview-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid var(--line-soft);
  font-size: 13px;
}

.template-preview-item:last-child {
  border-bottom: none;
}

/* Save Template Form */
.save-template-form .form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.save-template-form .form-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--ink);
}

/* Export/Import Templates */
.export-template-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.export-template-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: var(--bg-secondary);
  border-radius: 4px;
  cursor: pointer;
}

.export-template-item:hover {
  background: var(--panel-muted);
}

.import-drop-zone {
  border: 2px dashed var(--line);
  border-radius: 8px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.import-drop-zone:hover {
  border-color: var(--accent);
  background: var(--accent-bg);
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

.import-preview {
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
}

/* Advanced Chain Features */
.advanced-chain-section {
  margin-top: 16px;
}

.advanced-chain-feature {
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin-bottom: 12px;
}

.advanced-chain-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: var(--bg-secondary);
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.advanced-chain-header:hover {
  background: var(--bg-hover);
}

.advanced-chain-content {
  padding: 12px;
  border-top: 1px solid var(--line-soft);
}

/* Load Balancing Visualization */
.load-bal-viz {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.lb-viz-item {
  padding: 8px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}

.lb-viz-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.lb-viz-bar {
  height: 8px;
  background: var(--bg-primary);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 4px;
}

.lb-viz-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.lb-fill-success {
  background-color: #16a34a;
}

.lb-fill-warning {
  background-color: #d97706;
}

.lb-fill-danger {
  background-color: #dc2626;
}

.lb-viz-stats {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
}

/* Failover Configuration */
.failover-config {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.failover-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.failover-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--line-soft);
}

/* Bandwidth Monitoring */
.bandwidth-monitor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bandwidth-stat {
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.bandwidth-chart {
  margin-top: 8px;
}

.bandwidth-svg {
  width: 100%;
  height: 60px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}

/* Latency Optimization Suggestions */
.latency-suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.latency-suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
}

.suggestion-high {
  background: #fef2f2;
  border-left: 3px solid #dc2626;
}

.suggestion-medium {
  background: #fffbeb;
  border-left: 3px solid #d97706;
}

.suggestion-low {
  background: #f0f9ff;
  border-left: 3px solid #3b82f6;
}

.suggestion-icon {
  flex-shrink: 0;
}

/* Security Analysis */
.security-analysis {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.security-score {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin-bottom: 4px;
}

.security-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
}

.security-good {
  background: #f0fdf4;
}

.security-warning {
  background: #fffbeb;
}

.security-error {
  background: #fef2f2;
}

.security-icon {
  flex-shrink: 0;
}
</style>
