<template>
            <section v-show="activePage === 'proxy-pools'" class="card fade-in">
              <div class="card-body">
                <div class="section-header">
                  <div>
                    <h2 class="section-title">多跳代理池</h2>
                    <p class="form-hint">代理池、HTTP 代理端点、链服务和后端链路统一在本页配置；端到端入口以 HTTP 代理端点为准。</p>
                  </div>
                  <div class="btn-group">
                    <button @click="onLoadProxyPools" :disabled="isActionRunning('loadProxyPools')" class="btn btn-secondary">
                      {{ buttonLabel('loadProxyPools', '刷新', '刷新中...') }}
                    </button>
                  </div>
                </div>

                <div class="tabs workspace-tabs">
                  <button @click="proxyPoolTab = 'pools'" :class="{ active: proxyPoolTab === 'pools' }" class="tab-btn">代理池</button>
                  <button @click="proxyPoolTab = 'gateway'" :class="{ active: proxyPoolTab === 'gateway' }" class="tab-btn">HTTP 代理端点</button>
                  <button @click="proxyPoolTab = 'gateway-status'" :class="{ active: proxyPoolTab === 'gateway-status' }" class="tab-btn">网关状态</button>
                  <button @click="proxyPoolTab = 'chain'" :class="{ active: proxyPoolTab === 'chain' }" class="tab-btn">链服务</button>
                  <button @click="proxyPoolTab = 'backend'" :class="{ active: proxyPoolTab === 'backend' }" class="tab-btn">后端链路</button>
                  <button @click="proxyPoolTab = 'events'" :class="{ active: proxyPoolTab === 'events' }" class="tab-btn">进程记录</button>
                </div>

                <div v-show="proxyPoolTab === 'pools'" class="tab-panel fade-in">

                <!-- Create pool form -->
                <div class="card compact-workspace-card" style="margin-bottom: 12px;">
                  <div class="card-body">
                    <h3 class="settings-title">创建代理池</h3>
                    <div class="pool-create-grid">
                      <div class="form-group pool-field-wide">
                        <label class="form-label">名称</label>
                        <input v-model.trim="proxyPoolForm.name" type="text" placeholder="池名称" class="input" />
                      </div>
                      <div class="form-group pool-field-wide">
                        <label class="form-label">监听</label>
                        <input v-model.trim="proxyPoolForm.listen" type="text" placeholder="0.0.0.0" class="input" />
                      </div>
                      <div class="form-group">
                        <label class="form-label">类型</label>
                        <select v-model="proxyPoolForm.inbound_type" class="select">
                          <option value="http">HTTP</option>
                          <option value="socks">SOCKS</option>
                        </select>
                      </div>
                      <div class="form-group">
                        <label class="form-label">链路类型</label>
                        <select v-model="proxyPoolForm.filters.route_mode_filter" class="select"><option value="direct">直连</option><option value="chain">链式</option><option value="unreachable">不可连接</option><option value="">不限</option></select>
                      </div>
                      <div class="form-group">
                        <label class="form-label">ChatGPT</label>
                        <select v-model="proxyPoolForm.filters.openai_filter" class="select"><option value="">不限</option><option value="unlocked">已解锁</option><option value="blocked">未解锁</option><option value="unchecked">未检测</option></select>
                      </div>
                      <div class="form-group">
                        <label class="form-label">家宽</label>
                        <select v-model="proxyPoolForm.filters.ip_purity_filter" class="select"><option value="">不限</option><option value="residential">家宽</option><option value="non_residential">非家宽</option><option value="unknown">未知</option></select>
                      </div>
                      <div class="form-group pool-field-wide">
                        <label class="form-label">国家</label>
                        <el-select v-model="proxyPoolForm.filters.geo_countries" multiple collapse-tags collapse-tags-tooltip clearable placeholder="不限" size="small" style="width: 100%">
                          <el-option v-for="opt in geoCountryOptions" :key="'pool-' + opt.value" :label="opt.label" :value="opt.value"></el-option>
                        </el-select>
                      </div>
                      <div class="form-group">
                        <label class="form-label">延迟</label>
                        <div class="input-group">
                          <input v-model.number="proxyPoolForm.filters.latency_min" type="number" min="0" placeholder="最低" class="input" />
                          <span class="input-sep">-</span>
                          <input v-model.number="proxyPoolForm.filters.latency_max" type="number" min="0" placeholder="最高" class="input" />
                        </div>
                      </div>
                      <div class="form-group">
                        <label class="form-label">时效(小时)</label>
                        <input v-model.number="proxyPoolForm.filters.freshness_hours" type="number" min="0" placeholder="不限" class="input" />
                      </div>
                      <button @click="onCreateProxyPool" :disabled="isActionRunning('createProxyPool')" class="btn btn-primary pool-create-action">
                        {{ buttonLabel('createProxyPool', '创建', '创建中...') }}
                      </button>
                    </div>
                  </div>
                </div>

                <div class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th style="width: 50px;">ID</th>
                        <th style="width: 120px;">名称</th>
                        <th>筛选条件</th>
                        <th style="width: 60px;">节点</th>
                        <th style="width: 70px;">状态</th>
                        <th style="width: 210px;">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in paginatedProxyPools" :key="item.id">
                        <td class="mono text-muted">{{ item.id }}</td>
                        <td><input :value="item.name || ''" @change="onRenameProxyPool(item, $event.target.value)" type="text" class="inline-input" /></td>
                        <td class="text-xs text-muted truncate" style="max-width: 300px;" :title="formatPoolFilters(item.filters)">{{ formatPoolFilters(item.filters) }}</td>
                        <td class="mono">{{ item.match_count || 0 }}</td>
                        <td><span class="text-sm" :class="item.status === 'running' ? 'text-emerald-600' : 'text-muted'">{{ item.status || 'stopped' }}</span></td>
                        <td>
                          <div class="btn-group btn-group-nowrap">
                            <button @click="onSyncPool(item.id)" :disabled="isActionRunning('syncPool-' + item.id)" class="btn btn-xs btn-secondary">同步</button>
                            <button @click="applyPoolFiltersToForm(item)" class="btn btn-xs btn-ghost">套用</button>
                            <button @click="onUpdatePoolFilters(item)" :disabled="isActionRunning('updatePool-' + item.id)" class="btn btn-xs btn-ghost">保存</button>
                            <a v-if="item.export_url" :href="item.export_url" target="_blank" class="btn btn-xs btn-ghost">订阅源</a>
                            <button @click="onDeleteProxyPool(item.id)" :disabled="isActionRunning('deletePool-' + item.id)" class="btn btn-xs btn-danger">删除</button>
                          </div>
                        </td>
                      </tr>
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

                <div v-show="proxyPoolTab === 'chain'" class="tab-panel fade-in">
                <h3 class="section-divider">代理链服务</h3>
                <div class="card" style="margin-bottom: 12px;">
                  <div class="card-body">
                    <div class="section-header">
                      <h3 class="settings-title">前置 / 后置节点池</h3>
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
                        <label class="form-label">后置节点池正则</label>
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
};
</script>
