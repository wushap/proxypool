// src/composables/useTaskPolling.js
// 任务轮询 composable

import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '../core/api'

/**
 * 任务轮询 composable
 * @param {number} intervalMs - 轮询间隔（毫秒）
 * @returns {object} 任务相关状态和方法
 */
export function useTaskPolling(intervalMs = 5000) {
  const tasks = ref([])
  const isLoading = ref(false)
  let pollingTimer = null

  const activeTasks = ref([])

  function updateActiveTasks() {
    activeTasks.value = tasks.value.filter(t =>
      ['queued', 'running'].includes(String(t.status || ''))
    )
  }

  async function fetchTasks(force = false) {
    if (isLoading.value && !force) return

    try {
      isLoading.value = true
      const data = await api.get('/tasks')
      tasks.value = data.items || []
      updateActiveTasks()
    } catch (error) {
      console.error('刷新任务列表失败:', error)
    } finally {
      isLoading.value = false
    }
  }

  function startPolling() {
    stopPolling()
    pollingTimer = setInterval(() => fetchTasks(), intervalMs)
  }

  function stopPolling() {
    if (pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
  }

  // 组件挂载时启动轮询
  onMounted(() => {
    fetchTasks()
    startPolling()
  })

  // 组件卸载时停止轮询
  onUnmounted(() => {
    stopPolling()
  })

  return {
    tasks,
    activeTasks,
    isLoading,
    fetchTasks,
    startPolling,
    stopPolling,
  }
}
