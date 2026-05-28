<template>
  <section class="card fade-in">
    <div class="card-body">
      <!-- Breadcrumb -->
      <Breadcrumb :items="breadcrumbItems" />

      <div class="section-header">
        <h2 class="section-title">配置历史</h2>
        <div class="btn-group">
          <button class="btn btn-secondary" @click="saveSnapshot" :disabled="isSaving">
            {{ isSaving ? '保存中...' : '保存快照' }}
          </button>
        </div>
      </div>

      <p class="text-muted text-sm" style="margin-bottom: 16px;">
        管理配置快照，支持查看历史、对比差异和回滚操作。快照存储在本地浏览器中。
      </p>

      <!-- Empty State -->
      <EmptyState
        v-if="snapshots.length === 0"
        title="暂无配置快照"
        description="点击保存快照按钮创建第一个配置快照"
        size="small"
      />

      <!-- Snapshot List -->
      <div v-else class="config-snapshot-list">
        <div
          v-for="(snapshot, index) in snapshots"
          :key="snapshot.id"
          class="config-snapshot-item"
          :class="{ 'config-snapshot-selected': selectedSnapshot?.id === snapshot.id }"
          @click="selectSnapshot(snapshot)"
        >
          <div class="config-snapshot-header">
            <div class="config-snapshot-info">
              <span class="config-snapshot-name">{{ snapshot.name || '快照 #' + (snapshots.length - index) }}</span>
              <span class="config-snapshot-time">{{ formatTime(snapshot.timestamp) }}</span>
            </div>
            <div class="config-snapshot-actions">
              <button
                class="btn btn-xs btn-ghost"
                @click.stop="rollbackSnapshot(snapshot)"
                :disabled="isRollingBack"
              >
                回滚
              </button>
              <button
                class="btn btn-xs btn-ghost"
                @click.stop="deleteSnapshot(snapshot.id)"
                style="color: var(--danger-text);"
              >
                删除
              </button>
            </div>
          </div>
          <div v-if="snapshot.description" class="config-snapshot-description">
            {{ snapshot.description }}
          </div>
          <div class="config-snapshot-meta">
            <span class="badge badge-sm badge-neutral">{{ snapshot.configCount }} 项配置</span>
            <span v-if="index === 0" class="badge badge-sm badge-success">最新</span>
          </div>
        </div>
      </div>

      <!-- Diff View -->
      <div v-if="selectedSnapshot" class="config-diff-section" style="margin-top: 24px;">
        <div class="section-header">
          <h3 class="section-title" style="font-size: 16px;">配置对比</h3>
          <div class="btn-group">
            <button class="btn btn-xs btn-ghost" @click="selectedSnapshot = null">关闭</button>
          </div>
        </div>

        <div class="config-diff-header">
          <span class="config-diff-label">当前配置</span>
          <span class="config-diff-label">快照配置 ({{ formatTime(selectedSnapshot.timestamp) }})</span>
        </div>

        <div class="config-diff-list">
          <div
            v-for="diff in configDiffs"
            :key="diff.key"
            class="config-diff-item"
            :class="'config-diff-' + diff.status"
          >
            <div class="config-diff-key">{{ diff.key }}</div>
            <div class="config-diff-values">
              <div class="config-diff-value config-diff-current">
                <span class="config-diff-value-label">当前</span>
                <span class="config-diff-value-content">{{ diff.currentValue ?? '-' }}</span>
              </div>
              <div class="config-diff-value config-diff-snapshot">
                <span class="config-diff-value-label">快照</span>
                <span class="config-diff-value-content">{{ diff.snapshotValue ?? '-' }}</span>
              </div>
            </div>
            <span class="config-diff-status badge badge-sm" :class="'badge-' + statusColor(diff.status)">
              {{ statusText(diff.status) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import Breadcrumb from '../components/layout/Breadcrumb.vue'
import EmptyState from '../components/common/EmptyState.vue'
import { rootProxyMixin } from '../rootProxyMixin'

const STORAGE_KEY = 'proxypool-config-snapshots'

export default {
  name: 'ConfigHistoryPage',
  components: { Breadcrumb, EmptyState },
  mixins: [rootProxyMixin],
  data() {
    return {
      snapshots: [],
      selectedSnapshot: null,
      isSaving: false,
      isRollingBack: false,
    }
  },
  computed: {
    breadcrumbItems() {
      return [
        { label: '首页', path: '/', onClick: () => this.selectPage('dashboard') },
        { label: '配置历史' },
      ]
    },
    currentConfig() {
      return {
        proxyFilters: { ...this.appState.proxyFilters },
        proxyColumnConfigs: { ...this.appState.proxyColumnConfigs },
        proxyColumnOrder: [...this.appState.proxyColumnOrder],
        pagination: { ...this.appState.pagination },
        autoRefreshInterval: this.appState.autoRefreshInterval || 0,
        darkMode: this.appState.darkMode,
      }
    },
    configDiffs() {
      if (!this.selectedSnapshot) return []
      const current = this.currentConfig
      const snapshot = this.selectedSnapshot.config
      const diffs = []
      const allKeys = new Set([...Object.keys(current), ...Object.keys(snapshot)])

      for (const key of allKeys) {
        const currentVal = JSON.stringify(current[key])
        const snapshotVal = JSON.stringify(snapshot[key])

        let status = 'unchanged'
        if (currentVal === undefined) status = 'added'
        else if (snapshotVal === undefined) status = 'removed'
        else if (currentVal !== snapshotVal) status = 'changed'

        if (status !== 'unchanged') {
          diffs.push({
            key,
            currentValue: current[key],
            snapshotValue: snapshot[key],
            status,
          })
        }
      }

      return diffs
    },
  },
  mounted() {
    this.loadSnapshots()
  },
  methods: {
    loadSnapshots() {
      try {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
          this.snapshots = JSON.parse(stored)
        }
      } catch (err) {
        console.error('Failed to load snapshots:', err)
      }
    },
    saveSnapshots() {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.snapshots))
      } catch (err) {
        console.error('Failed to save snapshots:', err)
        this.appState.setMessage('保存快照失败: ' + err.message, true)
      }
    },
    async saveSnapshot() {
      this.isSaving = true
      try {
        const snapshot = {
          id: Date.now().toString(),
          name: `快照 ${new Date().toLocaleString('zh-CN')}`,
          timestamp: new Date().toISOString(),
          description: '手动保存的配置快照',
          config: this.currentConfig,
          configCount: Object.keys(this.currentConfig).length,
        }

        this.snapshots.unshift(snapshot)

        // Keep only last 20 snapshots
        if (this.snapshots.length > 20) {
          this.snapshots = this.snapshots.slice(0, 20)
        }

        this.saveSnapshots()
        this.appState.setMessage('配置快照已保存')
      } finally {
        this.isSaving = false
      }
    },
    selectSnapshot(snapshot) {
      if (this.selectedSnapshot?.id === snapshot.id) {
        this.selectedSnapshot = null
      } else {
        this.selectedSnapshot = snapshot
      }
    },
    async rollbackSnapshot(snapshot) {
      if (!confirm('确定要回滚到此快照吗？当前配置将被覆盖。')) return

      this.isRollingBack = true
      try {
        const config = snapshot.config

        // Apply config
        if (config.proxyFilters) {
          Object.assign(this.appState.proxyFilters, config.proxyFilters)
        }
        if (config.proxyColumnConfigs) {
          Object.assign(this.appState.proxyColumnConfigs, config.proxyColumnConfigs)
        }
        if (config.proxyColumnOrder) {
          this.appState.proxyColumnOrder = [...config.proxyColumnOrder]
        }
        if (config.pagination) {
          Object.assign(this.appState.pagination, config.pagination)
        }
        if (config.darkMode !== undefined) {
          this.appState.darkMode = config.darkMode
          document.documentElement.classList.toggle('dark', config.darkMode)
          localStorage.setItem('pp-dark-mode', config.darkMode ? '1' : '0')
        }

        // Save to localStorage
        this.appState.persistFilterState()
        this.appState.persistProxyColumns()

        this.appState.setMessage('配置已回滚到: ' + snapshot.name)
        this.selectedSnapshot = null
      } catch (err) {
        this.appState.setMessage('回滚失败: ' + err.message, true)
      } finally {
        this.isRollingBack = false
      }
    },
    deleteSnapshot(id) {
      if (!confirm('确定要删除此快照吗？')) return

      this.snapshots = this.snapshots.filter(s => s.id !== id)
      if (this.selectedSnapshot?.id === id) {
        this.selectedSnapshot = null
      }
      this.saveSnapshots()
      this.appState.setMessage('快照已删除')
    },
    formatTime(timestamp) {
      if (!timestamp) return ''
      const date = new Date(timestamp)
      const now = new Date()
      const diff = now - date

      if (diff < 60000) return '刚刚'
      if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
      if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
      return date.toLocaleString('zh-CN')
    },
    statusColor(status) {
      const colors = {
        added: 'success',
        removed: 'danger',
        changed: 'warning',
        unchanged: 'neutral',
      }
      return colors[status] || 'neutral'
    },
    statusText(status) {
      const texts = {
        added: '新增',
        removed: '删除',
        changed: '修改',
        unchanged: '未变',
      }
      return texts[status] || status
    },
  },
}
</script>

<style scoped>
.config-snapshot-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-snapshot-item {
  padding: 16px;
  background: var(--bg-1, #ffffff);
  border: 1px solid var(--line-soft, #e5e7eb);
  border-radius: var(--radius-md, 8px);
  cursor: pointer;
  transition: all 0.2s;
}

.config-snapshot-item:hover {
  border-color: var(--accent, #3b82f6);
}

.config-snapshot-selected {
  border-color: var(--accent, #3b82f6);
  background: var(--bg-accent-subtle, #eff6ff);
}

.config-snapshot-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.config-snapshot-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.config-snapshot-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.config-snapshot-time {
  font-size: 12px;
  color: var(--text-muted, #6b7280);
}

.config-snapshot-actions {
  display: flex;
  gap: 4px;
}

.config-snapshot-description {
  font-size: 13px;
  color: var(--text-secondary, #4b5563);
  margin-bottom: 8px;
}

.config-snapshot-meta {
  display: flex;
  gap: 8px;
}

.config-diff-section {
  padding: 16px;
  background: var(--bg-1, #ffffff);
  border: 1px solid var(--line-soft, #e5e7eb);
  border-radius: var(--radius-md, 8px);
}

.config-diff-header {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-soft, #e5e7eb);
}

.config-diff-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted, #6b7280);
}

.config-diff-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.config-diff-item {
  display: grid;
  grid-template-columns: 200px 1fr auto;
  gap: 16px;
  padding: 12px;
  background: var(--bg-muted, #f9fafb);
  border-radius: var(--radius-sm, 6px);
}

.config-diff-key {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary, #111827);
  word-break: break-all;
}

.config-diff-values {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.config-diff-value {
  font-size: 12px;
}

.config-diff-value-label {
  display: block;
  font-size: 10px;
  color: var(--text-muted, #6b7280);
  margin-bottom: 2px;
}

.config-diff-value-content {
  display: block;
  padding: 4px 8px;
  background: var(--bg-1, #ffffff);
  border: 1px solid var(--line-soft, #e5e7eb);
  border-radius: var(--radius-sm, 4px);
  word-break: break-all;
}

.config-diff-added .config-diff-value-content {
  border-color: var(--success-border, #86efac);
  background: var(--success-bg, #f0fdf4);
}

.config-diff-removed .config-diff-value-content {
  border-color: var(--danger-border, #fca5a5);
  background: var(--danger-bg, #fef2f2);
}

.config-diff-changed .config-diff-value-content {
  border-color: var(--warning-border, #fcd34d);
  background: var(--warning-bg, #fffbeb);
}

/* Dark mode */
html.dark .config-snapshot-item {
  background: #1e1e2e;
  border-color: #333;
}

html.dark .config-snapshot-selected {
  background: #2a2a4a;
}

html.dark .config-snapshot-name {
  color: #e5e7eb;
}

html.dark .config-snapshot-description {
  color: #9ca3af;
}

html.dark .config-diff-section {
  background: #1e1e2e;
  border-color: #333;
}

html.dark .config-diff-item {
  background: #16162a;
}

html.dark .config-diff-key {
  color: #e5e7eb;
}

html.dark .config-diff-value-content {
  background: #1e1e2e;
  border-color: #333;
  color: #e5e7eb;
}

/* Responsive */
@media (max-width: 768px) {
  .config-diff-item {
    grid-template-columns: 1fr;
  }

  .config-diff-values {
    grid-template-columns: 1fr;
  }
}
</style>
