// src/composables/useDarkMode.js
// 暗色模式 composable

import { ref, watch } from 'vue'

/**
 * 暗色模式 composable
 * @returns {object} 暗色模式相关状态和方法
 */
export function useDarkMode() {
  const isDark = ref(false)

  /**
   * 初始化暗色模式
   * 从localStorage读取用户偏好或系统偏好
   */
  function init() {
    try {
      const saved = localStorage.getItem('pp-dark-mode')
      if (saved === '1' || (saved === null && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        isDark.value = true
        document.documentElement.classList.add('dark')
      }
    } catch {
      // 忽略localStorage读取错误
    }
  }

  /**
   * 切换暗色模式
   */
  function toggle() {
    isDark.value = !isDark.value
    document.documentElement.classList.toggle('dark', isDark.value)
    try {
      localStorage.setItem('pp-dark-mode', isDark.value ? '1' : '0')
    } catch {
      // 忽略localStorage写入错误
    }
  }

  // 监听变化并同步到DOM
  watch(isDark, (val) => {
    document.documentElement.classList.toggle('dark', val)
  })

  return {
    isDark,
    init,
    toggle,
  }
}
