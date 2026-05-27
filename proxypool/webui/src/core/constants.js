// src/core/constants.js
// 常量定义

// 协议颜色映射
export const PROTOCOL_COLORS = [
  '#4b5058', '#6366f1', '#0891b2', '#16a34a', '#ca8a04',
  '#dc2626', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316',
]

// 纯净度颜色映射
export const PURITY_COLORS = {
  '家宽': '#16a34a',
  '非家宽': '#dc2626',
  '未知': '#9ca3af',
}

// 任务状态映射
export const TASK_STATUS_MAP = {
  running: { text: '运行中', class: 'badge-warning' },
  queued: { text: '排队中', class: 'badge-warning' },
  completed: { text: '已完成', class: 'badge-success' },
  done: { text: '已完成', class: 'badge-success' },
  failed: { text: '失败', class: 'badge-danger' },
  error: { text: '失败', class: 'badge-danger' },
}

// 任务类型映射
export const TASK_TYPE_MAP = {
  test: '测速任务',
  speed_test: '网速测试',
  openai_check: 'ChatGPT解锁检测',
  geoip: 'IP位置补全',
  ip_purity: 'IP纯净度检测',
  subscription_refresh: '订阅刷新',
  subscriptions_refresh: '订阅刷新',
}

// 页面配置
export const PAGE_SIZE_OPTIONS = [10, 50, 100]

// 代理列配置默认值
export const DEFAULT_PROXY_COLUMN_CONFIGS = {
  serial:         { label: "序号",       visible: true },
  protocol:       { label: "协议",       visible: true },
  address:        { label: "地址",       visible: true },
  latency:        { label: "延迟",       visible: true },
  bandwidth:      { label: "带宽 Mbps",  visible: true },
  success_rate:   { label: "成功率",     visible: true },
  fail_count:     { label: "失败次数",   visible: true },
  status:         { label: "状态",       visible: true },
  checked_at:     { label: "最后检测",   visible: true },
  geo:            { label: "IP位置",     visible: true },
  purity:         { label: "IP纯净度",   visible: true },
  unlock:         { label: "ChatGPT解锁", visible: true },
  fallback_front: { label: "可连通前置", visible: true },
  source:         { label: "来源",       visible: true },
  action:         { label: "操作",       visible: true },
}

// 代理列顺序默认值
export const DEFAULT_PROXY_COLUMN_ORDER = [
  "serial", "protocol", "address", "latency", "bandwidth", "success_rate", "fail_count",
  "status", "checked_at", "geo", "purity", "unlock", "fallback_front", "source", "action",
]

// 代理筛选默认值
export const DEFAULT_PROXY_FILTERS = {
  protocol: "",
  available: "",
  geo: "",
  geo_country: "",
  geo_location: "",
  openai: "",
  ip_purity: "",
  fallback_front: "",
  source: "",
  speed_min_mbps: "",
}
