// src/composables/useButtonState.js
// 按钮状态管理 composable

import { ref } from 'vue'

/**
 * 按钮状态管理 composable
 * 管理按钮的loading状态，防止重复点击
 * @returns {object} 按钮状态相关方法
 */
export function useButtonState() {
  const buttonStates = ref({})

  /**
   * 检查按钮是否正在执行
   * @param {string} key - 按钮唯一标识
   * @returns {boolean} 是否正在执行
   */
  function isRunning(key) {
    return !!buttonStates.value[String(key || "")]
  }

  /**
   * 获取按钮显示文本
   * @param {string} key - 按钮唯一标识
   * @param {string} idleText - 空闲状态文本
   * @param {string} runningText - 执行中状态文本
   * @returns {string} 按钮文本
   */
  function getLabel(key, idleText, runningText = "执行中...") {
    return isRunning(key) ? runningText : idleText
  }

  /**
   * 执行带状态管理的操作
   * @param {string} key - 按钮唯一标识
   * @param {Function} fn - 要执行的异步函数
   * @param {number} minVisibleMs - 最小显示时间（毫秒）
   * @returns {Promise<*>} 函数执行结果
   */
  async function runWithState(key, fn, minVisibleMs = 220) {
    const stateKey = String(key || "")
    if (!stateKey) return await fn()
    if (buttonStates.value[stateKey]) return

    buttonStates.value[stateKey] = true
    const started = Date.now()

    try {
      return await fn()
    } finally {
      const elapsed = Date.now() - started
      const remaining = minVisibleMs - elapsed
      if (remaining > 0) {
        await new Promise(r => setTimeout(r, remaining))
      }
      buttonStates.value[stateKey] = false
    }
  }

  return {
    buttonStates,
    isRunning,
    getLabel,
    runWithState,
  }
}
