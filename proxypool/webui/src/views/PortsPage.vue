<template>
  <div class="page-container fade-in">
    <div class="section-header">
      <div>
        <h2 class="section-title">
          入站端口
          <el-tooltip content="客户端连接代理服务的网络端口" placement="right" :show-after="300">
            <span class="section-title-hint">?</span>
          </el-tooltip>
        </h2>
        <p class="form-hint">管理 HTTP 代理网关的入站端口配置，支持多跳代理链路和会话粘性</p>
      </div>
      <div class="btn-group">
        <button @click="loadGatewayEndpoints()" class="btn btn-secondary" :disabled="isActionRunning('loadGatewayEndpoints')" aria-label="刷新入站端口列表">
          刷新
        </button>
        <button @click="openPortWizard('create')" class="btn btn-primary" aria-label="创建新的入站端口">
          创建端口
        </button>
      </div>
    </div>

    <!-- Empty State -->
    <EmptyState
      v-if="!gatewayEndpoints.length && !isActionRunning('loadGatewayEndpoints')"
      title="暂无入站端口"
      description="入站端口是客户端连接代理服务的入口。创建入站端口后，客户端可通过此端口使用代理池。"
      icon="🔌"
    >
      <template #actions>
        <button @click="openPortWizard('create')" class="btn btn-primary">
          创建第一个入站端口
        </button>
      </template>
    </EmptyState>

    <!-- Port List Table -->
    <div v-else>
      <!-- Conflict Warning Banner -->
      <div v-if="hasPortConflicts" class="port-conflict-banner">
        <div class="port-conflict-banner-icon">⚠️</div>
        <div class="port-conflict-banner-text">
          <strong>检测到端口冲突</strong>
          <p>存在多个端口使用相同的监听地址和端口号，可能会影响正常运行</p>
        </div>
      </div>

      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 30px;"></th>
              <th style="width: 70px;">状态</th>
              <th>名称</th>
              <th>
                <el-tooltip content="代理服务监听的IP地址，0.0.0.0表示所有接口" placement="top" :show-after="300">
                  <span>监听地址 <span class="text-muted">?</span></span>
                </el-tooltip>
              </th>
              <th>跳点链路</th>
              <th style="width: 100px;">会话粘性</th>
              <th style="width: 120px;">操作</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="ep in gatewayEndpoints" :key="'port-ep-' + ep.id">
              <tr @click="toggleEndpointExpand(ep.id)" class="port-row-expandable" :aria-label="'入站端口' + ep.name + '，状态：' + (ep.enabled ? '已启用' : '已禁用')">
                <td>
                  <span class="port-expand-icon" :class="{ expanded: expandedEndpoints[ep.id] }" aria-hidden="true">&#9654;</span>
                </td>
                <td>
                  <span class="badge" :class="ep.enabled ? 'badge-success' : 'badge-neutral'">
                    {{ ep.enabled ? '已启用' : '已禁用' }}
                  </span>
                </td>
                <td>
                  <div class="font-semibold">{{ ep.name }}</div>
                  <div class="text-xs text-muted">#{{ ep.id }}</div>
                </td>
                <td class="mono">
                  <el-tooltip :content="`监听地址: ${ep.listen_host}:${ep.listen_port}`" placement="top" :show-after="300">
                    <span>{{ ep.listen_host }}:{{ ep.listen_port }}</span>
                  </el-tooltip>
                </td>
                <td>
                  <el-tooltip :content="formatEndpointHops(ep)" placement="top" :show-after="300">
                    <span class="text-xs">{{ formatEndpointHopsShort(ep) }}</span>
                  </el-tooltip>
                </td>
                <td class="mono text-xs">
                  {{ ep.sticky_ttl_sec || '-' }}s
                </td>
                <td @click.stop>
                  <div class="btn-group btn-group-sm">
                    <el-tooltip content="编辑端口配置" placement="top" :show-after="300">
                      <button @click="openPortWizard('edit', ep)" class="btn btn-secondary btn-sm" :aria-label="'编辑端口' + ep.name">编辑</button>
                    </el-tooltip>
                    <el-tooltip content="查看网关运行状态" placement="top" :show-after="300">
                      <button @click="openGatewayEndpointStatus(ep)" class="btn btn-secondary btn-sm" :aria-label="'查看端口' + ep.name + '状态'">状态</button>
                    </el-tooltip>
                    <el-tooltip content="删除此端口" placement="top" :show-after="300">
                      <button @click="deleteGatewayEndpoint(ep.id)" class="btn btn-danger btn-sm" :aria-label="'删除端口' + ep.name">删除</button>
                    </el-tooltip>
                  </div>
                </td>
              </tr>
              <!-- Expanded Health Details Row -->
              <tr v-if="expandedEndpoints[ep.id]" class="port-health-row">
                <td colspan="7">
                  <div class="port-health-details">
                    <div class="port-health-grid">
                      <div class="port-health-item">
                        <span class="text-muted">会话缺失行为</span>
                        <strong>{{ ep.session_missing_action || '-' }}</strong>
                      </div>
                      <div class="port-health-item">
                        <span class="text-muted">会话 Header</span>
                        <strong class="text-xs">{{ (ep.session_header_names || []).join(', ') || '-' }}</strong>
                      </div>
                      <div class="port-health-item">
                        <span class="text-muted">会话 Query</span>
                        <strong class="text-xs">{{ (ep.session_query_param_names || []).join(', ') || '-' }}</strong>
                      </div>
                      <div class="port-health-item">
                        <span class="text-muted">端点 ID</span>
                        <strong class="mono">#{{ ep.id }}</strong>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Port Creation Wizard Dialog -->
    <el-dialog
      v-model="portWizardVisible"
      :title="portWizardMode === 'create' ? '创建入站端口' : '编辑入站端口'"
      width="600px"
      :close-on-click-modal="false"
      @close="closePortWizard"
    >
      <!-- Step Indicator -->
      <div class="port-wizard-steps">
        <div class="port-wizard-step" :class="{ active: portWizardStep >= 1, done: portWizardStep > 1 }">
          <div class="port-wizard-step-number">1</div>
          <div class="port-wizard-step-label">基础配置</div>
        </div>
        <div class="port-wizard-step-line" :class="{ active: portWizardStep > 1 }"></div>
        <div class="port-wizard-step" :class="{ active: portWizardStep >= 2, done: portWizardStep > 2 }">
          <div class="port-wizard-step-number">2</div>
          <div class="port-wizard-step-label">跳点选择</div>
        </div>
        <div class="port-wizard-step-line" :class="{ active: portWizardStep > 2 }"></div>
        <div class="port-wizard-step" :class="{ active: portWizardStep >= 3 }">
          <div class="port-wizard-step-number">3</div>
          <div class="port-wizard-step-label">会话策略</div>
        </div>
      </div>

      <!-- Step 1: Basic Config -->
      <div v-show="portWizardStep === 1" class="port-wizard-content">
        <el-form label-position="top">
          <el-form-item label="端点名称">
            <el-input v-model="portWizardForm.name" placeholder="例如: 主入口-HTTP" maxlength="50" show-word-limit />
          </el-form-item>
          <el-form-item>
            <template #label>
              <el-tooltip content="代理服务监听的IP地址，0.0.0.0表示所有接口" placement="right" :show-after="300">
                <span>监听地址 <span class="text-muted">?</span></span>
              </el-tooltip>
            </template>
            <el-input v-model="portWizardForm.listen_host" placeholder="127.0.0.1" />
          </el-form-item>
          <el-form-item>
            <template #label>
              <el-tooltip content="客户端连接代理服务的网络端口，范围 1-65535" placement="right" :show-after="300">
                <span>监听端口 <span class="text-muted">?</span></span>
              </el-tooltip>
            </template>
            <el-input-number v-model="portWizardForm.listen_port" :min="1" :max="65535" :step="1" />
          </el-form-item>
          <el-form-item label="启用状态">
            <el-switch v-model="portWizardForm.enabled" />
          </el-form-item>
        </el-form>

        <!-- Conflict Detection -->
        <div v-if="portHasConflict" class="port-conflict-warning">
          <div class="port-conflict-icon">⚠️</div>
          <div class="port-conflict-text">
            <strong>端口冲突</strong>
            <p>该地址和端口已被端点 <span class="mono">{{ portConflicts[0].endpoint.name }}</span> (#{{ portConflicts[0].endpoint.id }}) 占用</p>
          </div>
        </div>
      </div>

      <!-- Step 2: Hop Selection -->
      <div v-show="portWizardStep === 2" class="port-wizard-content">
        <div class="port-wizard-hint">
          <p>选择代理链路的跳点池，按顺序添加多跳链路</p>
        </div>

        <div class="port-wizard-pool-list">
          <el-checkbox-group v-model="portWizardForm.hop_pool_ids">
            <div v-for="pool in proxyPools" :key="'wizard-pool-' + pool.id" class="port-wizard-pool-item">
              <el-checkbox :value="Number(pool.id)">
                <span class="font-semibold">{{ pool.name }}</span>
                <span class="text-xs text-muted">(#{{ pool.id }})</span>
              </el-checkbox>
            </div>
          </el-checkbox-group>
        </div>

        <div v-if="!proxyPools.length" class="empty-state-small">
          <p>暂无可用代理池，请先创建代理池</p>
        </div>
      </div>

      <!-- Step 3: Session Strategy -->
      <div v-show="portWizardStep === 3" class="port-wizard-content">
        <el-form label-position="top">
          <el-form-item label="会话粘性 TTL (秒)">
            <el-input-number v-model="portWizardForm.sticky_ttl_sec" :min="1" :max="604800" :step="60" />
            <div class="form-hint">会话保持时长，最大 7 天 (604800 秒)</div>
          </el-form-item>
          <el-form-item label="会话缺失行为">
            <el-select v-model="portWizardForm.session_missing_action" style="width: 100%;">
              <el-option label="随机选择 (RANDOM)" value="RANDOM"></el-option>
              <el-option label="使用首个可用 (FIRST)" value="FIRST"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="会话 Header">
            <el-input v-model="portWizardForm.session_header_names_text" placeholder="X-ProxyPool-Session" />
          </el-form-item>
          <el-form-item label="会话 Query 参数">
            <el-input v-model="portWizardForm.session_query_param_names_text" placeholder="session" />
          </el-form-item>
        </el-form>
      </div>

      <!-- Wizard Actions -->
      <template #footer>
        <div class="port-wizard-actions">
          <button v-if="portWizardStep > 1" @click="prevPortWizardStep()" class="btn btn-secondary">
            上一步
          </button>
          <button @click="previewPortConfig()" class="btn btn-ghost">
            预览配置
          </button>
          <div class="port-wizard-actions-right">
            <button @click="closePortWizard()" class="btn btn-secondary">取消</button>
            <button v-if="portWizardStep < 3" @click="nextPortWizardStep()" class="btn btn-primary">
              下一步
            </button>
            <button v-else @click="submitPortWizard()" class="btn btn-primary" :disabled="portHasConflict">
              {{ portWizardMode === 'create' ? '创建' : '保存' }}
            </button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- Config Preview Dialog -->
    <el-dialog v-model="configPreviewVisible" title="配置预览" width="min(650px, 95vw)" append-to-body>
      <div class="config-preview">
        <p class="text-muted text-sm" style="margin-bottom: 12px;">生成的 singbox inbound 配置：</p>
        <div class="config-code-block">
          <div class="config-code-header">
            <span class="config-code-lang">JSON</span>
            <button class="btn btn-xs btn-ghost" @click="copyConfigToClipboard">
              {{ copySuccess ? '已复制' : '复制配置' }}
            </button>
          </div>
          <pre class="config-code-content"><code>{{ configPreviewJson }}</code></pre>
        </div>
      </div>
      <template #footer>
        <button class="btn btn-secondary" @click="configPreviewVisible = false">关闭</button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { rootProxyMixin } from "../rootProxyMixin";
import EmptyState from '../components/common/EmptyState.vue';

export default {
  name: "PortsPage",
  mixins: [rootProxyMixin],
  components: {
    EmptyState,
  },
  data() {
    return {
      expandedEndpoints: {},
      configPreviewVisible: false,
      configPreviewJson: '',
      copySuccess: false,
    };
  },
  computed: {
    hasPortConflicts() {
      const seen = new Map();
      for (const ep of (this.gatewayEndpoints || [])) {
        const key = `${ep.listen_host || '127.0.0.1'}:${ep.listen_port || 0}`;
        if (seen.has(key)) return true;
        seen.set(key, ep.id);
      }
      return false;
    },
  },
  methods: {
    formatEndpointHopsShort(item) {
      const hops = Array.isArray(item?.hops) ? item.hops : [];
      if (!hops.length) return '未配置';
      if (hops.length === 1) {
        const pool = (this.proxyPools || []).find(p => Number(p.id) === Number(hops[0].pool_id));
        return pool ? pool.name : `#${hops[0].pool_id}`;
      }
      const first = (this.proxyPools || []).find(p => Number(p.id) === Number(hops[0].pool_id));
      const last = (this.proxyPools || []).find(p => Number(p.id) === Number(hops[hops.length - 1].pool_id));
      return `${first ? first.name : `#${hops[0].pool_id}`} → ${last ? last.name : `#${hops[hops.length - 1].pool_id}`} (${hops.length}跳)`;
    },
    toggleEndpointExpand(id) {
      this.expandedEndpoints = {
        ...this.expandedEndpoints,
        [id]: !this.expandedEndpoints[id],
      };
    },
    previewPortConfig() {
      const hops = (this.portWizardForm.hop_pool_ids || []).map(poolId => {
        const pool = (this.proxyPools || []).find(p => Number(p.id) === Number(poolId));
        return {
          pool_id: Number(poolId),
          pool_name: pool ? pool.name : `#${poolId}`,
        };
      });

      this.configPreviewJson = JSON.stringify({
        inbounds: [{
          type: 'http',
          tag: `in-${this.portWizardForm.name || 'new-port'}`,
          listen: this.portWizardForm.listen_host || '0.0.0.0',
          listen_port: this.portWizardForm.listen_port || 8080,
        }],
        route: {
          rules: [{
            inbound: [`in-${this.portWizardForm.name || 'new-port'}`],
            outbound: hops.length > 0 ? `hop-${hops[0].pool_name}` : 'direct',
          }],
        },
      }, null, 2);
      this.configPreviewVisible = true;
    },
    copyConfigToClipboard() {
      navigator.clipboard.writeText(this.configPreviewJson).then(() => {
        this.copySuccess = true;
        setTimeout(() => { this.copySuccess = false; }, 2000);
      });
    },
  },
};
</script>

<style scoped>
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
</style>
