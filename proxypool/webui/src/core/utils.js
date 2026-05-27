// src/core/utils.js
// 工具函数

/**
 * 时间格式化
 * @param {string|null} ts - 时间戳
 * @returns {string} 格式化后的时间字符串
 */
export function formatTime(ts) {
  if (!ts) return "-"
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return String(ts)
  }
}

/**
 * 相对时间显示
 * @param {string|null} ts - 时间戳
 * @returns {string} 相对时间字符串
 */
export function formatRelativeTime(ts) {
  if (!ts) return '从未'
  const age = Date.now() - new Date(ts).getTime()
  const min = 60000
  const hour = 3600000
  const day = 86400000

  if (age < min) return '刚刚'
  if (age < hour) return Math.floor(age / min) + ' 分钟前'
  if (age < day) return Math.floor(age / hour) + ' 小时前'
  return Math.floor(age / day) + ' 天前'
}

/**
 * 格式化延迟样式
 * @param {number|null} ms - 毫秒数
 * @returns {object} CSS样式对象
 */
export function latencyStyle(ms) {
  if (!ms) return {}
  if (ms < 100) return { color: '#16a34a', fontWeight: 600 }
  if (ms < 500) return { color: '#ca8a04', fontWeight: 600 }
  return { color: '#dc2626', fontWeight: 600 }
}

/**
 * 格式化带宽样式
 * @param {number|null} mbps - 带宽Mbps
 * @returns {object} CSS样式对象
 */
export function bandwidthStyle(mbps) {
  if (!mbps || mbps <= 0) return {}
  if (mbps >= 50) return { color: '#16a34a' }
  if (mbps >= 10) return { color: '#ca8a04' }
  return { color: '#dc2626' }
}

/**
 * 格式化带宽显示
 * @param {object} item - 代理项
 * @returns {string} 格式化后的带宽字符串
 */
export function formatBandwidthMbps(item) {
  if (item?.speed_mbps === null || item?.speed_mbps === undefined) return "-"
  const value = Number(item.speed_mbps)
  if (!Number.isFinite(value) || value < 0) return "-"
  return value >= 100 ? value.toFixed(0) : value.toFixed(2)
}

/**
 * 格式化地理位置
 * @param {object} item - 代理项
 * @returns {string} 格式化后的地理位置字符串
 */
export function formatGeo(item) {
  const c = item?.country || ""
  const city = item?.city || ""
  return (!c && !city) ? "-" : `${c || "-"}:${city || "-"}`
}

/**
 * 格式化IP纯净度
 * @param {object} item - 代理项
 * @returns {string} 格式化后的IP纯净度字符串
 */
export function formatIpPurity(item) {
  const level = String(item?.ip_purity_level || "").trim()
  const score = item?.ip_purity_score
  const hasScore = Number.isFinite(Number(score))

  if (level === "家宽" || level === "非家宽" || level === "未知") return level
  if (level && hasScore) return `${level} (${Number(score).toFixed(2)}%)`
  if (level) return level
  if (hasScore) return `${Number(score).toFixed(2)}%`
  return "-"
}

/**
 * 格式化解锁状态
 * @param {object} item - 代理项
 * @returns {string} 格式化后的解锁状态字符串
 */
export function formatUnlock(item) {
  if (item?.openai_unlocked === true) return "已解锁"
  if (item?.openai_unlocked === false) return "未解锁"
  return "未检测"
}

/**
 * 格式化来源显示
 * @param {string} src - 来源字符串
 * @returns {string} 格式化后的来源字符串
 */
export function shortSource(src) {
  const text = String(src || "").trim()
  if (!text) return "-"
  if (text.startsWith("subscription#")) return text.split("|", 1)[0]
  if (text.startsWith("upload:")) return text
  return text.split("/").slice(-1)[0]
}

/**
 * 格式化订阅URL显示
 * @param {string} url - URL字符串
 * @returns {string} 格式化后的URL字符串
 */
export function shortSubscriptionUrl(url) {
  const text = String(url || "").trim()
  if (!text) return "-"
  return text.length <= 64 ? text : text.slice(0, 61) + "..."
}

/**
 * 格式化路径显示
 * @param {string} path - 路径字符串
 * @returns {string} 格式化后的路径字符串
 */
export function shortPath(path) {
  const text = String(path || "").trim()
  if (!text) return "-"
  const parts = text.split("/")
  return parts.length <= 3 ? text : "..." + parts.slice(-3).join("/")
}

/**
 * 防抖函数
 * @param {Function} fn - 要防抖的函数
 * @param {number} delay - 延迟时间（毫秒）
 * @returns {Function} 防抖后的函数
 */
export function debounce(fn, delay = 300) {
  let timer = null
  return function (...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

/**
 * 复制文本到剪贴板
 * @param {string} text - 要复制的文本
 */
export async function copyToClipboard(text) {
  const value = String(text || "")
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    await navigator.clipboard.writeText(value)
    return
  }

  // 降级方案
  const textarea = document.createElement("textarea")
  textarea.value = value
  textarea.setAttribute("readonly", "readonly")
  textarea.style.cssText = "position:fixed;left:-9999px;top:0"
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  try {
    document.execCommand("copy")
  } finally {
    document.body.removeChild(textarea)
  }
}

/**
 * 克隆代理列配置
 * @returns {object} 克隆后的代理列配置
 */
export function cloneProxyColumnConfigs(DEFAULT_PROXY_COLUMN_CONFIGS) {
  const out = {}
  for (const [key, val] of Object.entries(DEFAULT_PROXY_COLUMN_CONFIGS)) {
    out[key] = { label: String(val.label || ""), visible: val.visible !== false }
  }
  return out
}

/**
 * 获取任务状态文本
 * @param {string} status - 任务状态
 * @returns {string} 状态文本
 */
export function getTaskStatusText(status) {
  const s = String(status || '')
  if (s === 'running') return '运行中'
  if (s === 'queued') return '排队中'
  if (s === 'completed' || s === 'done') return '已完成'
  if (s === 'failed' || s === 'error') return '失败'
  return s || '未知'
}

/**
 * 获取任务状态CSS类
 * @param {string} status - 任务状态
 * @returns {string} CSS类名
 */
export function getTaskStatusClass(status) {
  const s = String(status || '')
  if (s === 'running' || s === 'queued') return 'badge-warning'
  if (s === 'completed' || s === 'done') return 'badge-success'
  if (s === 'failed' || s === 'error') return 'badge-danger'
  return 'badge-neutral'
}

/**
 * 获取任务类型文本
 * @param {string} kind - 任务类型
 * @returns {string} 类型文本
 */
export function getTaskTypeText(kind, TASK_TYPE_MAP) {
  return TASK_TYPE_MAP[kind] || kind || '任务'
}

/**
 * 格式化短任务ID
 * @param {string} taskId - 任务ID
 * @returns {string} 短任务ID
 */
export function shortTaskId(taskId) {
  if (!taskId) return '-'
  return String(taskId).slice(0, 8)
}
