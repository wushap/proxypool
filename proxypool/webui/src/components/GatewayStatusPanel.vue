<template>
  <div v-show="proxyPoolTab === 'gateway-status'" class="tab-panel fade-in">
    <div class="section-header">
      <div>
        <h3 class="section-divider">网关状态</h3>
        <p class="form-hint">端点按代理池顺序选择健康节点；单个节点或单条组合失败时会临时避开，直到候选组合耗尽才视为不可用。</p>
      </div>
      <div class="btn-group">
        <select v-model.number="gatewayStatusEndpointId" @change="onGatewayStatusEndpointChanged" class="select input-sm" style="min-width: 220px;">
          <option :value="0">默认端点</option>
          <option v-for="item in gatewayEndpoints" :key="'gateway-status-ep-' + item.id" :value="Number(item.id)">{{ item.name }} (#{{ item.id }})</option>
        </select>
        <button @click="onRunGatewayHealthCheck()" :disabled="isActionRunning('runGatewayHealthCheck')" class="btn btn-secondary">立即检测</button>
        <button @click="onLoadGatewayStatus()" :disabled="isActionRunning('loadGatewayStatus')" class="btn btn-secondary">刷新</button>
      </div>
    </div>

    <div class="gateway-status-strip">
      <div class="gateway-status-item">
        <span class="text-muted">端点</span>
        <strong>{{ selectedGatewayStatusEndpoint?.name || '-' }}</strong>
        <span class="mono text-xs">{{ selectedGatewayStatusEndpoint ? `${selectedGatewayStatusEndpoint.listen_host}:${selectedGatewayStatusEndpoint.listen_port}` : '-' }}</span>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">运行</span>
        <span class="badge" :class="gatewayStatusBadgeClass(gatewayStatus?.endpoint_runtime?.running)">{{ gatewayStatus?.endpoint_runtime?.running ? 'RUNNING' : 'STOPPED' }}</span>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">端点可用</span>
        <span class="badge" :class="gatewayStatusBadgeClass(gatewayStatus?.summary?.available)">{{ gatewayStatus?.summary?.available ? 'AVAILABLE' : 'UNAVAILABLE' }}</span>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">跳点池</span>
        <strong class="mono">{{ gatewayStatus?.summary?.healthy_hop_pools || 0 }}/{{ gatewayStatus?.summary?.total_hop_pools || 0 }}</strong>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">跨跳组合</span>
        <strong class="mono">{{ gatewayStatus?.summary?.healthy_transitions || 0 }}/{{ gatewayStatus?.summary?.total_transitions || 0 }}</strong>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">活跃链路</span>
        <strong class="mono">{{ (gatewayStatus?.active_hop_node_keys || []).map(key => '#' + getSerial(key)).join(' -> ') || '-' }}</strong>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">实时检测</span>
        <span class="badge" :class="gatewayStatusBadgeClass(gatewayStatus?.health_monitor?.enabled)">{{ gatewayStatus?.health_monitor?.enabled ? `${gatewayStatus?.health_monitor?.interval_sec || '-'}s` : 'OFF' }}</span>
      </div>
      <div class="gateway-status-item">
        <span class="text-muted">最后检测</span>
        <strong class="mono text-xs">{{ formatTime(gatewayStatus?.health_monitor?.last_finished_at) }}</strong>
      </div>
    </div>

    <div class="gateway-config-panel">
      <div class="gateway-panel-header">
        <div>
          <h4>选中网关配置</h4>
          <p class="form-hint">监听、会话策略和跳点池顺序来自当前端点配置。</p>
        </div>
        <span class="badge" :class="gatewayStatusBadgeClass(selectedGatewayStatusEndpoint?.enabled !== false)">{{ selectedGatewayStatusEndpoint?.enabled === false ? 'DISABLED' : 'ENABLED' }}</span>
      </div>
      <div class="gateway-config-grid">
        <div>
          <span class="text-muted">监听地址</span>
          <strong class="mono">{{ selectedGatewayStatusEndpoint ? `${selectedGatewayStatusEndpoint.listen_host}:${selectedGatewayStatusEndpoint.listen_port}` : '-' }}</strong>
        </div>
        <div>
          <span class="text-muted">会话缺失</span>
          <strong>{{ selectedGatewayStatusEndpoint?.session_missing_action || '-' }}</strong>
        </div>
        <div>
          <span class="text-muted">粘性 TTL</span>
          <strong class="mono">{{ selectedGatewayStatusEndpoint?.sticky_ttl_sec || '-' }}s</strong>
        </div>
        <div>
          <span class="text-muted">跳点顺序</span>
          <strong>{{ formatEndpointHops(selectedGatewayStatusEndpoint) }}</strong>
        </div>
      </div>
    </div>

    <div class="gateway-status-layout">
      <section v-for="pool in gatewayHopPools" :key="'gw-hop-pool-' + pool.hop_index" class="gateway-status-panel">
        <div class="gateway-panel-header">
          <div>
            <h4>{{ pool.label }} · {{ pool.pool?.name || ('#' + pool.pool_id) }}</h4>
            <p class="form-hint">{{ pool.healthy_nodes }}/{{ pool.total_nodes }} 个健康节点</p>
          </div>
          <span class="badge" :class="gatewayStatusBadgeClass(pool.available)">{{ pool.available ? 'AVAILABLE' : 'EMPTY' }}</span>
        </div>
        <div class="table-wrap">
          <table class="data-table data-table-compact">
            <thead>
              <tr>
                <th style="width: 74px;">状态</th>
                <th>节点</th>
                <th>信息</th>
                <th style="width: 80px;">延迟</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="node in pool.nodes" :key="'gw-hop-node-' + pool.hop_index + '-' + node.key" :class="{ 'gateway-active-row': node.active }">
                <td>
                  <span v-if="node.active" class="badge badge-warning">ACTIVE</span>
                  <span v-else class="badge" :class="gatewayStatusBadgeClass(node.healthy)">{{ node.healthy ? 'UP' : 'DOWN' }}</span>
                </td>
                <td>
                  <div class="font-semibold">{{ formatGatewayNode(node) }}</div>
                  <div class="mono text-xs text-muted">{{ node.host }}:{{ node.port }}</div>
                </td>
                <td class="text-xs text-muted">{{ formatGatewayNodeMeta(node) }}</td>
                <td class="mono text-xs">{{ node.latency_ms ?? '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <section v-for="transition in gatewayTransitions" :key="'gw-transition-' + transition.from_hop_index" class="gateway-transition-panel">
      <div class="gateway-panel-header">
        <div>
          <h4>{{ transition.label }}</h4>
          <p class="form-hint">{{ transition.healthy_pairs }}/{{ transition.total_pairs }} 个组合可用，显示 {{ transition.shown_pairs }} 个候选</p>
        </div>
        <span class="badge" :class="gatewayStatusBadgeClass(transition.available)">{{ transition.available ? 'ROUTEABLE' : 'BLOCKED' }}</span>
      </div>
      <div class="table-wrap">
        <table class="data-table data-table-compact">
          <thead>
            <tr>
              <th style="width: 74px;">状态</th>
              <th>起点</th>
              <th>下一跳</th>
              <th style="width: 140px;">结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pair in transition.pairs" :key="'gw-pair-' + pair.hop_node_keys.join('-')" :class="{ 'gateway-active-row': pair.active }">
              <td>
                <span v-if="pair.active" class="badge badge-warning">ACTIVE</span>
                <span v-else class="badge" :class="gatewayStatusBadgeClass(pair.healthy)">{{ pair.healthy ? 'OK' : 'FAILED' }}</span>
              </td>
              <td>{{ formatGatewayNode(pair.source) }}</td>
              <td>{{ formatGatewayNode(pair.target) }}</td>
              <td class="text-xs text-muted">
                <span v-if="pair.failed">失败冷却中</span>
                <span v-else-if="pair.known_healthy">近期成功</span>
                <span v-else>候选</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="!gatewayHopPools.length" class="empty-state">未选择端点或端点尚未配置代理池顺序。</div>
  </div>
</template>

<script>
import { rootProxyMixin } from "../rootProxyMixin";

export default {
  name: "GatewayStatusPanel",
  mixins: [rootProxyMixin],
};
</script>
