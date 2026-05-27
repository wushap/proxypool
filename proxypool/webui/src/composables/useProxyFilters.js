// src/composables/useProxyFilters.js
// 代理筛选逻辑 composable

import { ref, computed } from 'vue'
import { DEFAULT_PROXY_FILTERS } from '../core/constants'
import { api } from '../core/api'

/**
 * 代理筛选 composable
 * @returns {object} 筛选相关状态和方法
 */
export function useProxyFilters() {
  const filters = ref({ ...DEFAULT_PROXY_FILTERS })
  const allProxies = ref([])

  // 计算筛选选项
  const protocolFilterOptions = computed(() => {
    const map = new Map()
    allProxies.value.forEach(item => {
      const key = String(item?.protocol || "").trim()
      if (key) map.set(key, (map.get(key) || 0) + 1)
    })
    return Array.from(map.entries())
      .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0], "zh-CN"))
      .map(([value, count]) => ({ value, count, label: `${value} (${count})` }))
  })

  const statusFilterOptions = computed(() => {
    let up = 0, down = 0
    allProxies.value.forEach(item => {
      if (item?.available) up++; else down++
    })
    return [
      { value: "true", count: up, label: `状态: 可用 (${up})` },
      { value: "false", count: down, label: `状态: 不可用 (${down})` },
    ]
  })

  const geoCountryOptions = computed(() => {
    const map = new Map()
    allProxies.value.forEach(item => {
      const country = String(item?.country || "").trim() || "-"
      map.set(country, (map.get(country) || 0) + 1)
    })
    return Array.from(map.entries())
      .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0], "zh-CN"))
      .map(([value, count]) => ({
        value,
        count,
        label: `${value === "-" ? "未知国家" : value} (${count})`
      }))
  })

  const geoLocationFilterOptions = computed(() => {
    const selCountry = String(filters.value?.geo_country || "").trim()
    const map = new Map()
    allProxies.value.forEach(item => {
      const c = String(item?.country || "").trim()
      const city = String(item?.city || "").trim()
      const cKey = c || "-"
      if (selCountry && selCountry !== cKey) return
      if (!c && !city) return
      const loc = `${c || "-"}:${city || "-"}`
      map.set(loc, (map.get(loc) || 0) + 1)
    })
    return Array.from(map.entries())
      .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0], "zh-CN"))
      .map(([value, count]) => ({ value, count, label: `${value} (${count})` }))
  })

  const openaiFilterOptions = computed(() => {
    let unlocked = 0, blocked = 0, unchecked = 0
    allProxies.value.forEach(item => {
      if (item?.openai_unlocked === true) unlocked++
      else if (item?.openai_unlocked === false) blocked++
      else unchecked++
    })
    return [
      { value: "unlocked", count: unlocked, label: `ChatGPT: 已解锁 (${unlocked})` },
      { value: "blocked", count: blocked, label: `ChatGPT: 未解锁 (${blocked})` },
      { value: "unchecked", count: unchecked, label: `ChatGPT: 未检测 (${unchecked})` },
    ]
  })

  const ipPurityFilterOptions = computed(() => {
    let checked = 0, unchecked = 0, residential = 0, nonResidential = 0, unknown = 0
    allProxies.value.forEach(item => {
      if (item?.ip_purity_checked_at) checked++; else unchecked++
      const level = String(item?.ip_purity_level || "").trim()
      if (level === "家宽") residential++
      else if (level === "非家宽") nonResidential++
      else if (level === "未知") unknown++
    })
    return [
      { value: "checked", count: checked, label: `IP纯净度: 已检测 (${checked})` },
      { value: "unchecked", count: unchecked, label: `IP纯净度: 未检测 (${unchecked})` },
      { value: "residential", count: residential, label: `IP纯净度: 家宽 (${residential})` },
      { value: "non_residential", count: nonResidential, label: `IP纯净度: 非家宽 (${nonResidential})` },
      { value: "unknown", count: unknown, label: `IP纯净度: 未知 (${unknown})` },
    ]
  })

  const sourceFilterOptions = computed(() => {
    const map = new Map()
    allProxies.value.forEach(item => {
      const key = String(item?.source || "").trim() || "-"
      map.set(key, (map.get(key) || 0) + 1)
    })
    return Array.from(map.entries())
      .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0], "zh-CN"))
      .map(([value, count]) => ({
        value,
        count,
        label: `${value === "-" ? "未知来源" : value} (${count})`
      }))
  })

  // 加载所有代理用于筛选
  async function loadAllProxies() {
    try {
      const data = await api.get('/proxies', { limit: 5000, sort_by: 'latency', sort_order: 'asc' })
      allProxies.value = data.items || []
    } catch (error) {
      console.error('加载代理列表失败:', error)
    }
  }

  // 清空筛选
  function clearFilters() {
    filters.value = { ...DEFAULT_PROXY_FILTERS }
  }

  // 构建API查询参数
  function buildQueryParams() {
    const params = { limit: 5000 }
    const f = filters.value

    if (f.protocol) params.protocol = f.protocol
    if (f.available === "true" || f.available === "false") params.available = f.available
    if (f.geo_country) params.geo_country = f.geo_country
    if (f.geo_location) {
      params.geo_filter = "has"
      params.geo_location = f.geo_location
    } else if (f.geo === "has" || f.geo === "none") {
      params.geo_filter = f.geo
    }
    if (["unlocked", "blocked", "unchecked"].includes(f.openai)) {
      params.openai_filter = f.openai
    }
    if (["checked", "unchecked", "residential", "non_residential", "unknown"].includes(f.ip_purity)) {
      params.ip_purity_filter = f.ip_purity
    }
    if (f.fallback_front === "has" || f.fallback_front === "none") {
      params.fallback_front_filter = f.fallback_front
    }
    if (f.source) params.source = f.source
    if (f.speed_min_mbps) params.speed_min_mbps = f.speed_min_mbps

    params.sort_by = "latency"
    params.sort_order = "asc"

    return params
  }

  return {
    filters,
    allProxies,
    protocolFilterOptions,
    statusFilterOptions,
    geoCountryOptions,
    geoLocationFilterOptions,
    openaiFilterOptions,
    ipPurityFilterOptions,
    sourceFilterOptions,
    loadAllProxies,
    clearFilters,
    buildQueryParams,
  }
}
