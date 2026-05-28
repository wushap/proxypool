<template>
<div class="layout">
      <!-- Skip to content link for screen readers -->
      <a href="#main-content" class="skip-to-content">跳转到主要内容</a>

      <el-config-provider size="small" :button="{ autoInsertSpace: true }">
        <!-- Sidebar -->
        <aside class="sidebar" aria-label="侧边栏导航">
          <div class="sidebar-brand" aria-label="应用标题">
            <div class="sidebar-brand-header">
              <div>
                <h2>Proxy Pool</h2>
                <p>代理池管理台</p>
              </div>
              <div class="notification-bell-wrapper" @click="toggleNotificationDropdown()">
                <span class="notification-bell">🔔</span>
                <span v-if="unreadNotificationCount > 0" class="notification-badge">{{ unreadNotificationCount > 99 ? '99+' : unreadNotificationCount }}</span>
              </div>
            </div>
          </div>

          <!-- Notification Dropdown -->
          <div v-if="notificationDropdownVisible" class="notification-dropdown">
            <div class="notification-dropdown-header">
              <span class="notification-dropdown-title">通知</span>
              <div class="notification-dropdown-actions">
                <button class="btn btn-xs btn-ghost" @click="markAllNotificationsRead()">全部已读</button>
                <button class="btn btn-xs btn-ghost" @click="clearAllNotifications()">清除所有</button>
              </div>
            </div>
            <div class="notification-dropdown-list">
              <div v-if="notifications.length === 0" class="notification-dropdown-empty">
                暂无通知
              </div>
              <div v-else v-for="notification in notifications" :key="notification.id" class="notification-item" :class="['notification-item-' + notification.type, { 'notification-unread': !notification.read }]" @click="markNotificationRead(notification.id)">
                <div class="notification-item-icon">
                  <span v-if="notification.type === 'info'">ℹ️</span>
                  <span v-else-if="notification.type === 'success'">✅</span>
                  <span v-else-if="notification.type === 'warning'">⚠️</span>
                  <span v-else-if="notification.type === 'error'">❌</span>
                </div>
                <div class="notification-item-content">
                  <div class="notification-item-message">{{ notification.message }}</div>
                  <div class="notification-item-time">{{ formatNotificationTime(notification.timestamp) }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- Global Search -->
          <div class="sidebar-search">
            <div class="search-input-wrapper" @click="openGlobalSearch()">
              <span class="search-icon">🔍</span>
              <input
                type="text"
                class="search-input"
                placeholder="搜索池、节点、订阅、端口..."
                readonly
                aria-label="全局搜索"
              />
              <span class="search-shortcut">⌘K</span>
            </div>
          </div>

          <el-menu class="sidebar-menu" :default-active="activePage" @select="selectPage" role="navigation" aria-label="主导航菜单">
            <!-- 概览 -->
            <el-menu-item-group>
              <template #title><span class="sidebar-menu-group-title">概览</span></template>
              <el-menu-item index="dashboard">仪表盘</el-menu-item>
            </el-menu-item-group>
            <!-- 代理管理 -->
            <el-menu-item-group>
              <template #title><span class="sidebar-menu-group-title">代理管理</span></template>
              <el-menu-item index="proxies">代理节点</el-menu-item>
              <el-menu-item index="proxy-pools">多跳代理池</el-menu-item>
              <el-menu-item index="ports">入站端口</el-menu-item>
              <el-menu-item index="subscriptions">订阅管理</el-menu-item>
            </el-menu-item-group>
            <!-- 运维 -->
            <el-menu-item-group>
              <template #title><span class="sidebar-menu-group-title">运维</span></template>
              <el-menu-item index="tasks">任务中心</el-menu-item>
              <el-menu-item index="published-subscriptions">订阅发布</el-menu-item>
            </el-menu-item-group>
            <!-- 系统 -->
            <el-menu-item-group>
              <template #title><span class="sidebar-menu-group-title">系统</span></template>
              <el-menu-item index="docs">
                <span style="margin-right: 4px;">&#128214;</span>使用指南
              </el-menu-item>
              <el-menu-item index="config-history">
                <span style="margin-right: 4px;">&#128190;</span>配置历史
              </el-menu-item>
              <el-menu-item index="system-diagnostics">
                <span style="margin-right: 4px;">&#128269;</span>系统诊断
              </el-menu-item>
              <el-menu-item index="settings">
                <span style="margin-right: 4px;">&#9881;</span>设置
              </el-menu-item>
            </el-menu-item-group>
          </el-menu>
          <!-- Terminology tooltips -->
          <div class="sidebar-help" role="region" aria-label="术语说明">
            <div class="sidebar-help-title">术语说明</div>
            <el-tooltip content="代理链路的第一跳节点池，负责前置中转和协议转换" placement="right" :show-after="300">
              <span class="sidebar-help-item">前置代理池</span>
            </el-tooltip>
            <el-tooltip content="代理链路的最后一跳节点池，直接连接目标服务器" placement="right" :show-after="300">
              <span class="sidebar-help-item">落地代理池</span>
            </el-tooltip>
            <el-tooltip content="确保同一会话的请求始终被路由到相同的代理节点" placement="right" :show-after="300">
              <span class="sidebar-help-item">会话粘性</span>
            </el-tooltip>
            <el-tooltip content="当节点连续失败时自动暂停使用，避免无效请求浪费资源" placement="right" :show-after="300">
              <span class="sidebar-help-item">熔断</span>
            </el-tooltip>
            <el-tooltip content="通过多个代理节点依次转发请求，增加匿名性和绕过地理限制" placement="right" :show-after="300">
              <span class="sidebar-help-item">链式路由</span>
            </el-tooltip>
          </div>
          <!-- Global status footer -->
          <div class="sidebar-footer" role="region" aria-label="系统状态概览">
            <div class="sidebar-stat">
              <span class="sidebar-stat-label">节点</span>
              <span class="sidebar-stat-value">{{ stats.total ?? 0 }}</span>
            </div>
            <div class="sidebar-stat">
              <span class="sidebar-stat-label">可用</span>
              <span class="sidebar-stat-value text-emerald-400">{{ stats.available ?? 0 }}</span>
            </div>
            <div class="sidebar-stat">
              <span class="sidebar-stat-label">代理池</span>
              <span class="sidebar-stat-value">{{ proxyPools.length }}</span>
            </div>
            <div class="sidebar-stat">
              <span class="sidebar-stat-label">后端</span>
              <span class="sidebar-stat-value" :class="backendStatus.running ? 'text-emerald-400' : 'text-gray-500'">{{ backendStatus.running ? '运行中' : '已停止' }}</span>
            </div>
            <div class="sidebar-stat">
              <span class="sidebar-stat-label">连接</span>
              <span class="sidebar-stat-value">
                <span class="connection-indicator" :class="isOnline ? 'online' : 'offline'"></span>
                {{ isOnline ? '正常' : '断开' }}
              </span>
            </div>
          </div>
          <!-- Dark mode toggle -->
          <button class="sidebar-toggle" @click="toggleDarkMode" :title="darkMode ? '切换浅色模式' : '切换深色模式'" :aria-label="darkMode ? '切换浅色模式' : '切换深色模式'">
            <span v-if="darkMode" style="font-size: 16px;">&#9728;</span>
            <span v-else style="font-size: 16px;">&#9790;</span>
          </button>
          <!-- Wizard button -->
          <button class="sidebar-wizard-btn" @click="openWizardDialog()" title="配置向导" aria-label="打开配置向导">
            <span style="font-size: 16px;">🧙</span>
            <span class="wizard-btn-text">向导</span>
          </button>
        </aside>

        <!-- Main Content -->
        <div class="workspace">
          <main id="main-content" class="main" tabindex="-1" role="main" aria-label="主内容区域">
            <!-- Offline detection banner -->
            <div v-if="isOffline" class="offline-banner offline-banner-error fade-in" role="alert" aria-live="assertive">
              <span class="offline-banner-icon">⚠️</span>
              <span class="offline-banner-text">网络连接已断开，正在重试...</span>
            </div>

            <!-- Connection restored banner -->
            <div v-if="connectionRestored" class="offline-banner offline-banner-success fade-in" role="status" aria-live="polite">
              <span class="offline-banner-icon">✅</span>
              <span class="offline-banner-text">网络连接已恢复</span>
            </div>

            <!-- Global task notification bar -->
            <div v-if="activeTasks.length > 0" class="global-task-bar fade-in" role="status" aria-live="polite" aria-label="活跃任务">
              <div v-for="t in activeTasks" :key="t.task_id || t.id" class="global-task-item">
                <div class="global-task-info">
                  <span class="global-task-dot"></span>
                  <span class="global-task-name">{{ t.name || t.task_type || '任务' }}</span>
                  <span class="text-muted" style="font-size: 11px;">{{ t.progress_current || 0 }}/{{ t.progress_total || 0 }}</span>
                </div>
                <div v-if="t.progress_total > 0" class="global-task-progress">
                  <div class="global-task-progress-bar" :style="{ width: Math.round(((t.progress_current || 0) / Math.max(t.progress_total, 1)) * 100) + '%' }"></div>
                </div>
              </div>
            </div>

            <!-- Global message bar -->
            <div v-if="message" class="message fade-in" :class="messageError ? 'message-error' : 'message-success'" role="alert" aria-live="assertive">{{ message }}</div>

            <!-- Undo toast -->
            <div v-if="undoState.visible" class="undo-toast fade-in" role="alert" aria-live="assertive">
              <span class="undo-toast-message">{{ undoState.message }}</span>
              <span class="undo-toast-countdown">{{ undoState.countdown }}s</span>
              <button class="undo-toast-button" @click="undoAction()">撤销</button>
              <button class="undo-toast-close" @click="hideUndoToast()" aria-label="关闭">×</button>
            </div>

            <!-- Hidden file input -->
            <input ref="fileInput" type="file" class="hidden" multiple accept=".txt,.yaml,.yml,.conf,.json,.log" @change="onImportFilesSelected" aria-label="导入代理配置文件" />

            <!-- Proxy key datalist -->
            <datalist id="proxy-key-options">
              <option v-for="item in allProxies" :key="item.normalized_key" :value="'#' + getSerial(item.normalized_key)">
                #{{ getSerial(item.normalized_key) }} {{ item.protocol }} {{ item.host }}:{{ item.port }}
              </option>
            </datalist>

            <!-- ==================== 仪表盘 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'dashboard'" page-name="仪表盘" :key="'page-dashboard'">
                <DashboardPage />
              </ErrorBoundary>
            </Transition>

            <!-- ==================== 任务中心 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'tasks'" page-name="任务中心" :key="'page-tasks'">
                <TasksPage />
              </ErrorBoundary>
            </Transition>

            <!-- ==================== 订阅管理 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'subscriptions'" page-name="订阅管理" :key="'page-subs'">
                <SubscriptionsPage />
              </ErrorBoundary>
            </Transition>

            <!-- ==================== 订阅发布 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'published-subscriptions'" page-name="订阅发布" :key="'page-pub-subs'">
                <PublishedSubscriptionsPage />
              </ErrorBoundary>
            </Transition>

            <!-- ==================== 代理池 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'proxy-pools'" page-name="多跳代理池" :key="'page-pools'">
                <ProxyPoolsPage />
              </ErrorBoundary>
            </Transition>

            <!-- ==================== 入站端口 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'ports'" page-name="入站端口" :key="'page-ports'">
                <PortsPage />
              </ErrorBoundary>
            </Transition>

            <!-- ==================== 代理节点 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'proxies'" page-name="代理节点" :key="'page-proxies'">
                <ProxiesPage />
              </ErrorBoundary>
            </Transition>

            <!-- ==================== 设置 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'settings'" page-name="设置" :key="'page-settings'">
                <SettingsPage />
              </ErrorBoundary>
            </Transition>

            <!-- ==================== 使用指南 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'docs'" page-name="使用指南" :key="'page-docs'">
                <DocsPage />
              </ErrorBoundary>
            </Transition>

            <!-- ==================== 配置历史 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'config-history'" page-name="配置历史" :key="'page-config-history'">
                <ConfigHistoryPage />
              </ErrorBoundary>
            </Transition>

            <!-- ==================== 系统诊断 ==================== -->
            <Transition name="page" mode="out-in">
              <ErrorBoundary v-if="activePage === 'system-diagnostics'" page-name="系统诊断" :key="'page-system-diagnostics'">
                <SystemDiagnosticsPage />
              </ErrorBoundary>
            </Transition>


          </main>
        </div>
      </el-config-provider>

      <!-- Global Search Dialog -->
      <el-dialog
        v-model="globalSearchVisible"
        title=""
        width="600px"
        :show-close="false"
        class="global-search-dialog"
        @close="closeGlobalSearch()"
      >
        <div class="global-search-content">
          <div class="global-search-input-wrapper">
            <span class="search-icon">🔍</span>
            <input
              ref="globalSearchInput"
              v-model="globalSearchQuery"
              type="text"
              class="global-search-input"
              placeholder="搜索代理池、代理节点、订阅、入站端口..."
              @input="debouncedSearch(globalSearchQuery)"
              @keydown.escape="closeGlobalSearch()"
              autofocus
            />
            <span v-if="globalSearchLoading" class="search-loading">搜索中...</span>
          </div>

          <div class="global-search-results">
            <template v-if="globalSearchGrouped.length">
              <div v-for="group in globalSearchGrouped" :key="group.label" class="search-result-group">
                <div class="search-result-group-header">
                  <span class="search-result-group-icon">{{ group.icon }}</span>
                  <span class="search-result-group-label">{{ group.label }}</span>
                  <span class="search-result-group-count">{{ group.items.length }}</span>
                </div>
                <div
                  v-for="result in group.items"
                  :key="result.id"
                  class="search-result-item"
                  @click="navigateToSearchResult(result)"
                >
                  <div class="search-result-title">{{ result.title }}</div>
                  <div class="search-result-subtitle">{{ result.subtitle }}</div>
                </div>
              </div>
            </template>
            <div v-else-if="globalSearchQuery && globalSearchQuery.length >= 2 && !globalSearchLoading" class="search-no-results">
              <p>未找到匹配 "{{ globalSearchQuery }}" 的结果</p>
            </div>
            <div v-else class="search-hint">
              <p>输入至少 2 个字符开始搜索</p>
              <p class="search-hint-examples">示例: HTTP, 127.0.0.1, 订阅名称</p>
            </div>
          </div>
        </div>
      </el-dialog>

      <!-- Configuration Wizard Dialog -->
      <el-dialog
        v-model="wizardDialogVisible"
        :title="currentWizard?.title || '配置向导'"
        width="min(700px, 95vw)"
        :close-on-click-modal="false"
        class="wizard-dialog"
      >
        <div v-if="!currentWizard" class="wizard-select">
          <h3 class="wizard-select-title">选择向导类型</h3>
          <div class="wizard-select-grid">
            <div v-for="w in wizardTypes" :key="w.id" class="wizard-select-card" @click="startWizard(w.id)">
              <div class="wizard-select-icon">{{ w.icon }}</div>
              <div class="wizard-select-name">{{ w.name }}</div>
              <div class="wizard-select-desc text-xs text-muted">{{ w.description }}</div>
            </div>
          </div>
        </div>

        <div v-else class="wizard-content">
          <!-- Progress indicator -->
          <div class="wizard-progress">
            <div v-for="(step, idx) in currentWizard.steps" :key="'ws-' + idx"
              class="wizard-progress-step"
              :class="{
                'completed': idx < wizardCurrentStep,
                'active': idx === wizardCurrentStep,
                'pending': idx > wizardCurrentStep
              }">
              <div class="wizard-step-number">{{ idx < wizardCurrentStep ? '✓' : idx + 1 }}</div>
              <div class="wizard-step-label">{{ step.title }}</div>
            </div>
          </div>

          <!-- Current step content -->
          <div class="wizard-step-content">
            <h4 class="wizard-step-title">{{ currentWizard.steps[wizardCurrentStep].title }}</h4>
            <p class="wizard-step-description text-muted">{{ currentWizard.steps[wizardCurrentStep].description }}</p>

            <!-- Step 1: Subscription Import -->
            <div v-if="currentWizard.id === 'complete-setup' && wizardCurrentStep === 0" class="wizard-form">
              <div class="wizard-form-field">
                <label class="wizard-form-label">订阅链接 (每行一个)</label>
                <textarea v-model="wizardData.subscriptions" class="input textarea" placeholder="https://example.com/sub1&#10;https://example.com/sub2" rows="4"></textarea>
              </div>
              <div class="wizard-form-field">
                <label class="wizard-form-label">导入代理 (可选)</label>
                <textarea v-model="wizardData.proxies" class="input textarea" placeholder="protocol://user:pass@host:port" rows="3"></textarea>
              </div>
            </div>

            <!-- Step 2: Pool Configuration -->
            <div v-if="currentWizard.id === 'complete-setup' && wizardCurrentStep === 1" class="wizard-form">
              <div class="wizard-form-field">
                <label class="wizard-form-label">代理池名称</label>
                <input v-model="wizardData.poolName" class="input" placeholder="我的代理池" />
              </div>
              <div class="wizard-form-field">
                <label class="wizard-form-label">池类型</label>
                <div class="wizard-radio-group">
                  <label class="wizard-radio">
                    <input type="radio" v-model="wizardData.poolType" value="direct" />
                    <span>直连池</span>
                  </label>
                  <label class="wizard-radio">
                    <input type="radio" v-model="wizardData.poolType" value="chain" />
                    <span>链式池</span>
                  </label>
                </div>
              </div>
              <div class="wizard-form-field">
                <label class="wizard-form-label">筛选条件</label>
                <div class="wizard-checkbox-group">
                  <label class="wizard-checkbox">
                    <input type="checkbox" v-model="wizardData.filterOpenai" />
                    <span>ChatGPT 解锁</span>
                  </label>
                  <label class="wizard-checkbox">
                    <input type="checkbox" v-model="wizardData.filterResidential" />
                    <span>家宽节点</span>
                  </label>
                </div>
              </div>
              <div class="wizard-form-field">
                <label class="wizard-form-label">最大延迟 (ms)</label>
                <input v-model.number="wizardData.maxLatency" type="number" class="input" placeholder="不限" min="0" />
              </div>
            </div>

            <!-- Step 3: Port Configuration -->
            <div v-if="currentWizard.id === 'complete-setup' && wizardCurrentStep === 2" class="wizard-form">
              <div class="wizard-form-field">
                <label class="wizard-form-label">端口名称</label>
                <input v-model="wizardData.portName" class="input" placeholder="代理入口" />
              </div>
              <div class="wizard-form-field">
                <label class="wizard-form-label">监听端口</label>
                <input v-model.number="wizardData.listenPort" type="number" class="input" placeholder="1080" min="1" max="65535" />
              </div>
              <div class="wizard-form-field">
                <label class="wizard-form-label">会话粘性 (秒)</label>
                <input v-model.number="wizardData.stickyTtl" type="number" class="input" placeholder="0 (禁用)" min="0" />
              </div>
            </div>

            <!-- Chain Wizard Steps -->
            <div v-if="currentWizard.id === 'chain-setup' && wizardCurrentStep === 0" class="wizard-form">
              <div class="wizard-form-field">
                <label class="wizard-form-label">前置池 (第一跳)</label>
                <select v-model="wizardData.frontPoolId" class="input">
                  <option value="">选择前置池</option>
                  <option v-for="pool in proxyPools" :key="'fp-' + pool.id" :value="pool.id">
                    {{ pool.name || '池 #' + pool.id }}
                  </option>
                </select>
              </div>
              <div class="wizard-form-field">
                <label class="wizard-form-label">落地池 (最后一跳)</label>
                <select v-model="wizardData.exitPoolId" class="input">
                  <option value="">选择落地池</option>
                  <option v-for="pool in proxyPools" :key="'ep-' + pool.id" :value="pool.id">
                    {{ pool.name || '池 #' + pool.id }}
                  </option>
                </select>
              </div>
            </div>

            <!-- Subscription Import Wizard Steps -->
            <div v-if="currentWizard.id === 'sub-import' && wizardCurrentStep === 0" class="wizard-form">
              <div class="wizard-form-field">
                <label class="wizard-form-label">订阅链接 (每行一个)</label>
                <textarea v-model="wizardData.subscriptions" class="input textarea" placeholder="https://example.com/sub1&#10;https://example.com/sub2" rows="5"></textarea>
              </div>
              <div class="wizard-form-field">
                <label class="wizard-form-label">订阅格式</label>
                <div class="wizard-radio-group">
                  <label class="wizard-radio">
                    <input type="radio" v-model="wizardData.subFormat" value="auto" />
                    <span>自动检测</span>
                  </label>
                  <label class="wizard-radio">
                    <input type="radio" v-model="wizardData.subFormat" value="clash" />
                    <span>Clash</span>
                  </label>
                  <label class="wizard-radio">
                    <input type="radio" v-model="wizardData.subFormat" value="v2ray" />
                    <span>V2Ray</span>
                  </label>
                </div>
              </div>
            </div>

            <!-- Migration Wizard Steps -->
            <div v-if="currentWizard.id === 'migration' && wizardCurrentStep === 0" class="wizard-form">
              <div class="wizard-form-field">
                <label class="wizard-form-label">从其他管理器迁移</label>
                <select v-model="wizardData.migrationSource" class="input">
                  <option value="">选择来源</option>
                  <option value="clash">Clash for Windows</option>
                  <option value="v2ray">V2RayN</option>
                  <option value="shadowrocket">Shadowrocket</option>
                  <option value="surge">Surge</option>
                  <option value="quantumult">Quantumult X</option>
                  <option value="other">其他 (JSON)</option>
                </select>
              </div>
              <div class="wizard-form-field">
                <label class="wizard-form-label">配置文件</label>
                <div class="wizard-file-upload" @click="$refs.wizardFileInput.click()">
                  <div class="wizard-file-icon">📄</div>
                  <div class="wizard-file-text">点击选择配置文件</div>
                  <div class="wizard-file-hint text-xs text-muted">支持 .yaml, .json, .conf 格式</div>
                </div>
                <input ref="wizardFileInput" type="file" accept=".yaml,.yml,.json,.conf" style="display: none;" @change="handleWizardFileSelect($event)" />
              </div>
            </div>

            <!-- Summary step for all wizards -->
            <div v-if="wizardCurrentStep === currentWizard.steps.length - 1" class="wizard-summary">
              <h4 class="wizard-summary-title">配置摘要</h4>
              <div class="wizard-summary-items">
                <div class="wizard-summary-item">
                  <span class="text-muted">向导类型:</span>
                  <span>{{ currentWizard.name }}</span>
                </div>
                <div class="wizard-summary-item">
                  <span class="text-muted">完成步骤:</span>
                  <span>{{ wizardCurrentStep + 1 }} / {{ currentWizard.steps.length }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <template #footer>
          <div class="wizard-footer">
            <div class="wizard-footer-left">
              <button v-if="currentWizard && wizardCurrentStep > 0" class="btn btn-ghost" @click="wizardPrevStep()">
                上一步
              </button>
              <button v-if="wizardDraftExists" class="btn btn-ghost" @click="loadWizardDraft()">
                恢复草稿
              </button>
            </div>
            <div class="wizard-footer-right">
              <button v-if="currentWizard" class="btn btn-ghost" @click="saveWizardDraft()">
                保存草稿
              </button>
              <button v-if="currentWizard" class="btn btn-ghost" @click="cancelWizard()">
                取消
              </button>
              <button v-if="!currentWizard" class="btn btn-secondary" @click="wizardDialogVisible = false">
                关闭
              </button>
              <button v-if="currentWizard && wizardCurrentStep < currentWizard.steps.length - 1"
                class="btn btn-primary" @click="wizardNextStep()">
                下一步
              </button>
              <button v-if="currentWizard && wizardCurrentStep === currentWizard.steps.length - 1"
                class="btn btn-primary" @click="completeWizard()">
                完成
              </button>
            </div>
          </div>
        </template>
      </el-dialog>
    </div>
</template>

<script>
import { appOptions } from "./appOptions";
import { defineAsyncComponent } from "vue";
import ErrorBoundary from "./components/common/ErrorBoundary.vue";

export default {
  ...appOptions,
  name: "App",
  components: {
    ErrorBoundary,
    DashboardPage: defineAsyncComponent(() => import("./views/DashboardPage.vue")),
    TasksPage: defineAsyncComponent(() => import("./views/TasksPage.vue")),
    SubscriptionsPage: defineAsyncComponent(() => import("./views/SubscriptionsPage.vue")),
    PublishedSubscriptionsPage: defineAsyncComponent(() => import("./views/PublishedSubscriptionsPage.vue")),
    ProxyPoolsPage: defineAsyncComponent(() => import("./views/ProxyPoolsPage.vue")),
    ProxiesPage: defineAsyncComponent(() => import("./views/ProxiesPage.vue")),
    PortsPage: defineAsyncComponent(() => import("./views/PortsPage.vue")),
    SettingsPage: defineAsyncComponent(() => import("./views/SettingsPage.vue")),
    DocsPage: defineAsyncComponent(() => import("./views/DocsPage.vue")),
    ConfigHistoryPage: defineAsyncComponent(() => import("./views/ConfigHistoryPage.vue")),
    SystemDiagnosticsPage: defineAsyncComponent(() => import("./views/SystemDiagnosticsPage.vue")),
  },
  provide() {
    return { appState: this };
  },
  data() {
    return {
      isOffline: !navigator.onLine,
      connectionRestored: false,
      // 撤销功能状态
      undoState: {
        visible: false,
        message: '',
        action: null,
        countdown: 5,
        timer: null,
      },
      // 通知中心状态
      notifications: [],
      notificationDropdownVisible: false,
    };
  },
  computed: {
    isOnline() {
      return !this.isOffline;
    },
    unreadNotificationCount() {
      return this.notifications.filter(n => !n.read).length;
    },
  },
  mounted() {
    this.setupKeyboardShortcuts();
    this.setupOfflineDetection();
    this.loadNotifications();
    this.setupNotificationClickOutside();
    this.initAlertMonitoring();
  },
  beforeUnmount() {
    this.removeKeyboardShortcuts();
    this.removeOfflineDetection();
    this.removeNotificationClickOutside();
    this.stopAlertChecker();
  },
  methods: {
    setupKeyboardShortcuts() {
      this._handleKeydown = this.handleKeydown.bind(this);
      document.addEventListener('keydown', this._handleKeydown);
    },
    removeKeyboardShortcuts() {
      if (this._handleKeydown) {
        document.removeEventListener('keydown', this._handleKeydown);
      }
    },
    setupOfflineDetection() {
      // 监听在线/离线状态变化
      this._handleOnline = () => {
        const wasOffline = this.isOffline;
        this.isOffline = false;
        this.connectionRestored = wasOffline;

        // 显示"网络连接已恢复"横幅，3秒后自动隐藏
        if (wasOffline) {
          setTimeout(() => {
            this.connectionRestored = false;
          }, 3000);
        }
      };
      this._handleOffline = () => {
        this.isOffline = true;
        this.connectionRestored = false;
      };

      window.addEventListener('online', this._handleOnline);
      window.addEventListener('offline', this._handleOffline);

      // 监听 API 请求成功/失败事件
      this._handleApiSuccess = () => {
        const wasOffline = this.isOffline;
        this.isOffline = false;
        this.connectionRestored = wasOffline;

        // 显示"网络连接已恢复"横幅，3秒后自动隐藏
        if (wasOffline) {
          setTimeout(() => {
            this.connectionRestored = false;
          }, 3000);
        }
      };
      this._handleApiFailure = () => {
        // 只有在多次失败后才标记为离线
        // 这里可以添加更复杂的逻辑
      };

      window.addEventListener('api:request-success', this._handleApiSuccess);
      window.addEventListener('api:request-failure', this._handleApiFailure);
    },
    removeOfflineDetection() {
      if (this._handleOnline) {
        window.removeEventListener('online', this._handleOnline);
      }
      if (this._handleOffline) {
        window.removeEventListener('offline', this._handleOffline);
      }
      if (this._handleApiSuccess) {
        window.removeEventListener('api:request-success', this._handleApiSuccess);
      }
      if (this._handleApiFailure) {
        window.removeEventListener('api:request-failure', this._handleApiFailure);
      }
    },
    setupNotificationClickOutside() {
      this._handleNotificationClickOutside = (e) => {
        if (this.notificationDropdownVisible) {
          const bellWrapper = document.querySelector('.notification-bell-wrapper');
          const dropdown = document.querySelector('.notification-dropdown');
          if (bellWrapper && !bellWrapper.contains(e.target) && dropdown && !dropdown.contains(e.target)) {
            this.notificationDropdownVisible = false;
          }
        }
      };
      document.addEventListener('click', this._handleNotificationClickOutside);
    },
    removeNotificationClickOutside() {
      if (this._handleNotificationClickOutside) {
        document.removeEventListener('click', this._handleNotificationClickOutside);
      }
    },
    // 通知中心方法
    toggleNotificationDropdown() {
      this.notificationDropdownVisible = !this.notificationDropdownVisible;
    },
    addNotification(type, message, source = '') {
      const notification = {
        id: Date.now(),
        type,
        message,
        source,
        timestamp: new Date().toISOString(),
        read: false,
      };
      this.notifications.unshift(notification);
      // 限制通知数量为 50 条
      if (this.notifications.length > 50) {
        this.notifications = this.notifications.slice(0, 50);
      }
      this.saveNotifications();
    },
    markNotificationRead(id) {
      const notification = this.notifications.find(n => n.id === id);
      if (notification) {
        notification.read = true;
        this.saveNotifications();
      }
    },
    markAllNotificationsRead() {
      this.notifications.forEach(n => {
        n.read = true;
      });
      this.saveNotifications();
    },
    clearAllNotifications() {
      this.notifications = [];
      this.saveNotifications();
    },
    saveNotifications() {
      try {
        sessionStorage.setItem('proxypool.notifications', JSON.stringify(this.notifications));
      } catch {}
    },
    loadNotifications() {
      try {
        const raw = sessionStorage.getItem('proxypool.notifications');
        if (raw) {
          this.notifications = JSON.parse(raw) || [];
        }
      } catch {}
    },
    formatNotificationTime(timestamp) {
      if (!timestamp) return '';
      const date = new Date(timestamp);
      const now = new Date();
      const diff = now - date;
      if (diff < 60000) return '刚刚';
      if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
      return date.toLocaleDateString();
    },
    // 撤销功能方法
    showUndoToast(message, action, duration = 5) {
      // 清除之前的计时器
      if (this.undoState.timer) {
        clearInterval(this.undoState.timer);
      }

      this.undoState = {
        visible: true,
        message,
        action,
        countdown: duration,
        timer: null,
      };

      // 启动倒计时
      this.undoState.timer = setInterval(() => {
        this.undoState.countdown--;
        if (this.undoState.countdown <= 0) {
          this.hideUndoToast();
        }
      }, 1000);
    },
    hideUndoToast() {
      if (this.undoState.timer) {
        clearInterval(this.undoState.timer);
      }
      this.undoState.visible = false;
      this.undoState.action = null;
    },
    undoAction() {
      if (this.undoState.action && typeof this.undoState.action === 'function') {
        this.undoState.action();
      }
      this.hideUndoToast();
    },
    handleKeydown(e) {
      // Escape: Close dialogs
      if (e.key === 'Escape') {
        this.closeAllDialogs();
        return;
      }

      // Enter: Submit forms (when focused on form elements)
      if (e.key === 'Enter' && this.isFormElement(e.target)) {
        this.submitCurrentForm(e.target);
        return;
      }

      // Ctrl+K: Open search (if search functionality exists)
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        this.openSearch();
        return;
      }
    },
    closeAllDialogs() {
      // Close all open dialogs by clicking outside or pressing Escape
      const dialogs = document.querySelectorAll('.el-dialog__wrapper');
      dialogs.forEach(dialog => {
        const closeBtn = dialog.querySelector('.el-dialog__headerbtn');
        if (closeBtn) {
          closeBtn.click();
        }
      });
    },
    isFormElement(element) {
      const formTags = ['INPUT', 'TEXTAREA', 'SELECT'];
      return formTags.includes(element.tagName) || element.closest('form');
    },
    submitCurrentForm(element) {
      const form = element.closest('form');
      if (form) {
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
          submitBtn.click();
        }
      }
    },
    openSearch() {
      this.openGlobalSearch();
    },
    debouncedSearch(query) {
      clearTimeout(this._searchTimer);
      this._searchTimer = setTimeout(() => {
        this.performGlobalSearch(query);
      }, 300);
    },
  },
};
</script>
