<template>
  <div class="page-container fade-in">
    <div class="section-header">
      <div>
        <h2 class="section-title">
          设置
          <el-tooltip content="自定义应用外观和行为" placement="right" :show-after="300">
            <span class="section-title-hint">?</span>
          </el-tooltip>
        </h2>
        <p class="form-hint">管理应用偏好设置，所有设置保存在本地浏览器中</p>
      </div>
    </div>

    <div class="settings-grid">
      <!-- Theme Settings -->
      <div class="card settings-card">
        <div class="card-body">
          <h3 class="settings-title">外观设置</h3>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">主题模式</span>
              <span class="setting-desc">选择应用的外观主题</span>
            </div>
            <div class="setting-control">
              <el-radio-group v-model="preferences.theme" @change="savePreferences" aria-label="主题模式选择">
                <el-radio-button value="light">浅色</el-radio-button>
                <el-radio-button value="dark">深色</el-radio-button>
                <el-radio-button value="auto">跟随系统</el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">表格密度</span>
              <span class="setting-desc">控制表格行的高度和间距</span>
            </div>
            <div class="setting-control">
              <el-radio-group v-model="preferences.tableDensity" @change="savePreferences" aria-label="表格密度选择">
                <el-radio-button value="compact">紧凑</el-radio-button>
                <el-radio-button value="normal">标准</el-radio-button>
                <el-radio-button value="comfortable">宽松</el-radio-button>
              </el-radio-group>
            </div>
          </div>
        </div>
      </div>

      <!-- Data Settings -->
      <div class="card settings-card">
        <div class="card-body">
          <h3 class="settings-title">数据设置</h3>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">自动刷新间隔</span>
              <span class="setting-desc">自动刷新数据的频率</span>
            </div>
            <div class="setting-control">
              <el-select v-model="preferences.autoRefreshInterval" @change="savePreferences" style="width: 120px;" aria-label="自动刷新间隔">
                <el-option label="30 秒" :value="30000"></el-option>
                <el-option label="1 分钟" :value="60000"></el-option>
                <el-option label="5 分钟" :value="300000"></el-option>
                <el-option label="关闭" :value="0"></el-option>
              </el-select>
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">默认启动页面</span>
              <span class="setting-desc">应用启动时显示的页面</span>
            </div>
            <div class="setting-control">
              <el-select v-model="preferences.defaultPage" @change="savePreferences" style="width: 150px;" aria-label="默认启动页面">
                <el-option label="仪表盘" value="dashboard"></el-option>
                <el-option label="代理节点" value="proxies"></el-option>
                <el-option label="代理池" value="proxy-pools"></el-option>
                <el-option label="任务中心" value="tasks"></el-option>
              </el-select>
            </div>
          </div>
        </div>
      </div>

      <!-- Language Settings -->
      <div class="card settings-card">
        <div class="card-body">
          <h3 class="settings-title">语言设置</h3>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">界面语言</span>
              <span class="setting-desc">选择应用显示语言</span>
            </div>
            <div class="setting-control">
              <el-select v-model="preferences.language" @change="savePreferences" style="width: 120px;" disabled aria-label="界面语言选择">
                <el-option label="中文" value="zh-CN"></el-option>
                <el-option label="English (即将推出)" value="en" disabled></el-option>
              </el-select>
            </div>
          </div>

          <div class="setting-info">
            <span class="info-icon">ℹ️</span>
            <span>目前仅支持中文，多语言支持将在后续版本中添加</span>
          </div>
        </div>
      </div>

      <!-- Alert Settings -->
      <div class="card settings-card">
        <div class="card-body">
          <h3 class="settings-title">告警设置</h3>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">浏览器通知</span>
              <span class="setting-desc">启用浏览器桌面通知推送告警</span>
            </div>
            <div class="setting-control">
              <el-switch v-model="alertConfig.browserNotifications" @change="saveAlertConfig" aria-label="启用浏览器桌面通知" />
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">代理池健康告警</span>
              <span class="setting-desc">代理池健康率低于阈值时告警</span>
            </div>
            <div class="setting-control">
              <div class="alert-threshold-row">
                <el-switch v-model="alertConfig.poolHealthEnabled" @change="saveAlertConfig" aria-label="启用代理池健康告警" />
                <div v-if="alertConfig.poolHealthEnabled" class="alert-threshold-input">
                  <span class="text-muted text-xs">低于</span>
                  <el-input-number v-model="alertConfig.poolHealthThreshold" :min="1" :max="100" :step="5" size="small" style="width: 100px;" @change="saveAlertConfig" aria-label="代理池健康率告警阈值" />
                  <span class="text-muted text-xs">%时告警</span>
                </div>
              </div>
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">可用代理数量告警</span>
              <span class="setting-desc">可用代理数低于阈值时告警</span>
            </div>
            <div class="setting-control">
              <div class="alert-threshold-row">
                <el-switch v-model="alertConfig.proxyCountEnabled" @change="saveAlertConfig" aria-label="启用可用代理数量告警" />
                <div v-if="alertConfig.proxyCountEnabled" class="alert-threshold-input">
                  <span class="text-muted text-xs">少于</span>
                  <el-input-number v-model="alertConfig.proxyCountThreshold" :min="1" :max="10000" :step="10" size="small" style="width: 100px;" @change="saveAlertConfig" aria-label="可用代理数量告警阈值" />
                  <span class="text-muted text-xs">个时告警</span>
                </div>
              </div>
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">后端进程崩溃检测</span>
              <span class="setting-desc">后端进程异常停止时自动告警</span>
            </div>
            <div class="setting-control">
              <el-switch v-model="alertConfig.backendCrashEnabled" @change="saveAlertConfig" aria-label="启用后端进程崩溃检测" />
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">订阅刷新失败告警</span>
              <span class="setting-desc">订阅源刷新失败时自动告警</span>
            </div>
            <div class="setting-control">
              <el-switch v-model="alertConfig.subRefreshFailEnabled" @change="saveAlertConfig" aria-label="启用订阅刷新失败告警" />
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-label">
              <span class="setting-name">告警静默期</span>
              <span class="setting-desc">同类告警的最小间隔时间</span>
            </div>
            <div class="setting-control">
              <el-select v-model="alertConfig.silenceMinutes" @change="saveAlertConfig" style="width: 120px;" aria-label="告警静默期">
                <el-option label="5 分钟" :value="5"></el-option>
                <el-option label="15 分钟" :value="15"></el-option>
                <el-option label="30 分钟" :value="30"></el-option>
                <el-option label="1 小时" :value="60"></el-option>
                <el-option label="不静默" :value="0"></el-option>
              </el-select>
            </div>
          </div>

          <div v-if="alertHistory.length" class="alert-history-section">
            <div class="alert-history-header">
              <span class="text-muted text-xs">最近告警记录</span>
              <button @click="clearAlertHistory" class="btn btn-xs btn-ghost" aria-label="清空告警历史记录">清空</button>
            </div>
            <div class="alert-history-list">
              <div v-for="(alert, idx) in alertHistory.slice(0, 5)" :key="'alert-h-' + idx" class="alert-history-item">
                <span class="alert-history-icon" :class="'alert-level-' + alert.level">{{ alert.level === 'warning' ? '⚠' : 'ℹ' }}</span>
                <span class="alert-history-msg">{{ alert.message }}</span>
                <span class="alert-history-time">{{ formatAlertTime(alert.timestamp) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Keyboard Shortcuts -->
      <div class="card settings-card">
        <div class="card-body">
          <h3 class="settings-title">快捷键</h3>

          <div class="shortcuts-list">
            <div class="shortcut-item">
              <span class="shortcut-keys">Ctrl + K</span>
              <span class="shortcut-desc">打开全局搜索</span>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-keys">Ctrl + R</span>
              <span class="shortcut-desc">刷新当前页面数据</span>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-keys">Ctrl + E</span>
              <span class="shortcut-desc">导出配置</span>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-keys">Ctrl + I</span>
              <span class="shortcut-desc">导入配置</span>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-keys">Shift + ?</span>
              <span class="shortcut-desc">显示帮助</span>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-keys">Escape</span>
              <span class="shortcut-desc">关闭对话框</span>
            </div>
          </div>
        </div>
      </div>

      <!-- About -->
      <div class="card settings-card">
        <div class="card-body">
          <h3 class="settings-title">关于</h3>

          <div class="about-info">
            <div class="about-item">
              <span class="about-label">应用名称</span>
              <span class="about-value">Proxy Pool</span>
            </div>
            <div class="about-item">
              <span class="about-label">版本</span>
              <span class="about-value">0.2.0</span>
            </div>
            <div class="about-item">
              <span class="about-label">描述</span>
              <span class="about-value">高性能代理池管理器，支持健康检查、链式路由和 WebUI</span>
            </div>
          </div>

          <div class="setting-actions" style="margin-top: 16px;">
            <button @click="resetPreferences" class="btn btn-secondary" aria-label="重置所有设置为默认值">
              重置为默认设置
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { rootProxyMixin } from "../rootProxyMixin";

const STORAGE_KEY = 'proxypool-preferences';

const DEFAULT_PREFERENCES = {
  theme: 'auto',
  tableDensity: 'normal',
  autoRefreshInterval: 60000,
  defaultPage: 'dashboard',
  language: 'zh-CN',
};

export default {
  name: "SettingsPage",
  mixins: [rootProxyMixin],
  data() {
    return {
      preferences: { ...DEFAULT_PREFERENCES },
    };
  },
  mounted() {
    this.loadPreferences();
    this.applyPreferences();
    this.loadAlertConfig();
    this.loadAlertHistory();
  },
  methods: {
    loadPreferences() {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored);
          this.preferences = { ...DEFAULT_PREFERENCES, ...parsed };
        }
      } catch (err) {
        console.error('Failed to load preferences:', err);
      }
    },
    savePreferences() {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.preferences));
        this.applyPreferences();
        this.setMessage('设置已保存');
      } catch (err) {
        console.error('Failed to save preferences:', err);
        this.setMessage('保存设置失败', true);
      }
    },
    applyPreferences() {
      // Apply theme
      this.applyTheme(this.preferences.theme);

      // Apply table density
      document.documentElement.style.setProperty('--table-density', this.preferences.tableDensity);

      // Apply auto-refresh (this would need to be integrated with the parent component)
      // For now, just store the preference
    },
    applyTheme(theme) {
      const html = document.documentElement;
      if (theme === 'auto') {
        // Follow system preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        html.classList.toggle('dark', prefersDark);
        html.classList.toggle('light', !prefersDark);
      } else if (theme === 'dark') {
        html.classList.add('dark');
        html.classList.remove('light');
      } else {
        html.classList.add('light');
        html.classList.remove('dark');
      }
    },
    resetPreferences() {
      this.preferences = { ...DEFAULT_PREFERENCES };
      this.savePreferences();
    },
    formatAlertTime(ts) {
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
};
</script>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 16px;
}

.settings-card {
  height: fit-content;
}

.settings-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line-soft);
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--line-soft);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setting-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
}

.setting-desc {
  font-size: 12px;
  color: var(--muted);
}

.setting-control {
  flex-shrink: 0;
}

.setting-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--muted);
  margin-top: 12px;
}

.info-icon {
  font-size: 14px;
}

.shortcuts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.shortcut-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  font-size: 13px;
}

.shortcut-keys {
  font-family: monospace;
  font-weight: 600;
  color: var(--accent);
  background: var(--panel);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.shortcut-desc {
  color: var(--muted);
}

.about-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.about-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 8px 0;
  font-size: 13px;
}

.about-label {
  color: var(--muted);
  min-width: 80px;
}

.about-value {
  color: var(--ink);
  text-align: right;
}

.setting-actions {
  padding-top: 16px;
  border-top: 1px solid var(--line-soft);
}

.alert-threshold-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.alert-threshold-input {
  display: flex;
  align-items: center;
  gap: 6px;
}

.alert-history-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--line-soft);
}

.alert-history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.alert-history-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 160px;
  overflow-y: auto;
}

.alert-history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--panel-muted);
  border-radius: var(--radius-md);
  font-size: 12px;
}

.alert-history-icon {
  flex-shrink: 0;
  width: 18px;
  text-align: center;
}

.alert-level-warning {
  color: var(--warning-text, #e6a23c);
}

.alert-level-info {
  color: var(--muted);
}

.alert-history-msg {
  flex: 1;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-history-time {
  flex-shrink: 0;
  color: var(--muted);
  font-size: 11px;
}

@media (max-width: 768px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .setting-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .setting-control {
    width: 100%;
  }
}
</style>
