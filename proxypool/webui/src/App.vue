<template>
<div class="layout">
      <el-config-provider size="small" :button="{ autoInsertSpace: true }">
        <!-- Sidebar -->
        <aside class="sidebar">
          <div class="sidebar-brand">
            <h2>Proxy Pool</h2>
            <p>代理池管理台</p>
          </div>
          <el-menu class="sidebar-menu" :default-active="activePage" @select="selectPage">
            <el-menu-item index="dashboard">仪表盘</el-menu-item>
            <el-menu-item index="tasks">任务中心</el-menu-item>
            <el-menu-item index="subscriptions">订阅管理</el-menu-item>
            <el-menu-item index="published-subscriptions">订阅发布</el-menu-item>
            <el-menu-item index="proxy-pools">多跳代理池</el-menu-item>
            <el-menu-item index="proxies">代理节点</el-menu-item>
          </el-menu>
          <!-- Global status footer -->
          <div class="sidebar-footer">
            <div class="sidebar-stat">
              <span class="sidebar-stat-label">节点</span>
              <span class="sidebar-stat-value">{{ stats.total ?? 0 }}</span>
            </div>
            <div class="sidebar-stat">
              <span class="sidebar-stat-label">可用</span>
              <span class="sidebar-stat-value text-emerald-400">{{ stats.available ?? 0 }}</span>
            </div>
            <div class="sidebar-stat">
              <span class="sidebar-stat-label">后端</span>
              <span class="sidebar-stat-value" :class="backendStatus.running ? 'text-emerald-400' : 'text-gray-500'">{{ backendStatus.running ? 'ON' : 'OFF' }}</span>
            </div>
            <div class="sidebar-stat">
              <span class="sidebar-stat-label">任务</span>
              <span class="sidebar-stat-value" :class="taskItems.some(t => ['queued','running'].includes(String(t.status||''))) ? 'text-amber-400' : ''">{{ taskItems.length }}</span>
            </div>
          </div>
          <!-- Dark mode toggle -->
          <div class="sidebar-toggle" @click="toggleDarkMode" :title="darkMode ? '切换浅色模式' : '切换深色模式'">
            <span v-if="darkMode" style="font-size: 16px;">&#9728;</span>
            <span v-else style="font-size: 16px;">&#9790;</span>
          </div>
        </aside>

        <!-- Main Content -->
        <div class="workspace">
          <main class="main">
            <!-- Global task notification bar -->
            <div v-if="activeTasks.length > 0" class="global-task-bar fade-in">
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
            <div v-if="message" class="message fade-in" :class="messageError ? 'message-error' : 'message-success'">{{ message }}</div>

            <!-- Hidden file input -->
            <input ref="fileInput" type="file" class="hidden" multiple accept=".txt,.yaml,.yml,.conf,.json,.log" @change="onImportFilesSelected" />

            <!-- Proxy key datalist -->
            <datalist id="proxy-key-options">
              <option v-for="item in allProxies" :key="item.normalized_key" :value="'#' + getSerial(item.normalized_key)">
                #{{ getSerial(item.normalized_key) }} {{ item.protocol }} {{ item.host }}:{{ item.port }}
              </option>
            </datalist>

            <!-- ==================== 仪表盘 ==================== -->
            <DashboardPage />

            <!-- ==================== 任务中心 ==================== -->
            <TasksPage />

            <!-- ==================== 订阅管理 ==================== -->
            <SubscriptionsPage />

            <!-- ==================== 订阅发布 ==================== -->
            <PublishedSubscriptionsPage />

            <!-- ==================== 代理池 ==================== -->
            <ProxyPoolsPage />

            <!-- ==================== 代理节点 ==================== -->
            <ProxiesPage />


          </main>
        </div>
      </el-config-provider>
    </div>
</template>

<script>
import { appOptions } from "./appOptions";
import DashboardPage from "./views/DashboardPage.vue";
import TasksPage from "./views/TasksPage.vue";
import SubscriptionsPage from "./views/SubscriptionsPage.vue";
import PublishedSubscriptionsPage from "./views/PublishedSubscriptionsPage.vue";
import ProxyPoolsPage from "./views/ProxyPoolsPage.vue";
import ProxiesPage from "./views/ProxiesPage.vue";

export default {
  ...appOptions,
  name: "App",
  components: {
    DashboardPage,
    TasksPage,
    SubscriptionsPage,
    PublishedSubscriptionsPage,
    ProxyPoolsPage,
    ProxiesPage,
  },
  provide() {
    return { appState: this };
  },
};
</script>
