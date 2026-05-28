// src/core/api.js
// API 请求封装

const BASE_URL = '/api'

/**
 * API 客户端类
 * 提供统一的请求封装、错误处理和拦截器支持
 */
class ApiClient {
  constructor() {
    this.baseUrl = BASE_URL
    this.interceptors = {
      request: [],
      response: [],
    }
  }

  /**
   * 添加请求拦截器
   * @param {Function} fn - 拦截器函数
   */
  addRequestInterceptor(fn) {
    this.interceptors.request.push(fn)
  }

  /**
   * 添加响应拦截器
   * @param {Function} fn - 拦截器函数
   */
  addResponseInterceptor(fn) {
    this.interceptors.response.push(fn)
  }

  /**
   * 延迟执行
   * @param {number} ms - 毫秒数
   * @returns {Promise<void>}
   */
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * 发送请求（带自动重试）
   * @param {string} url - 请求URL（相对于BASE_URL）
   * @param {object} options - 请求选项
   * @param {number} maxRetries - 最大重试次数（默认3次）
   * @param {number} timeout - 请求超时时间（毫秒，默认30秒）
   * @returns {Promise<object>} 响应数据
   */
  async request(url, options = {}, maxRetries = 3, timeout = 30000) {
    const fullUrl = `${this.baseUrl}${url}`
    let lastError

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      // 执行请求拦截器
      let config = { url: fullUrl, ...options }
      for (const interceptor of this.interceptors.request) {
        config = await interceptor(config)
      }

      try {
        // 创建超时控制器
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), timeout)

        const response = await fetch(config.url, {
          headers: {
            'Content-Type': 'application/json',
            ...config.headers,
          },
          ...config,
          signal: controller.signal,
        })

        clearTimeout(timeoutId)

        let data
        const contentType = response.headers.get('content-type')
        if (contentType && contentType.includes('application/json')) {
          data = await response.json()
        } else {
          data = await response.text()
        }

        // 执行响应拦截器
        for (const interceptor of this.interceptors.response) {
          data = await interceptor(data, response)
        }

        if (!response.ok) {
          const error = this.createApiError(data, response.status)
          throw error
        }

        // 请求成功，触发在线状态更新
        if (typeof window !== 'undefined' && window.dispatchEvent) {
          window.dispatchEvent(new CustomEvent('api:request-success'))
        }

        return data
      } catch (error) {
        lastError = error

        // 处理超时错误
        if (error.name === 'AbortError') {
          const timeoutError = new Error(`请求超时 (${timeout/1000}秒)，请检查网络或稍后重试`)
          timeoutError.isApiError = true
          timeoutError.status = 0
          timeoutError.isTimeout = true
          throw timeoutError
        }

        // 如果是 API 错误（非网络错误），不重试
        if (error.isApiError) {
          throw error
        }

        // 如果还有重试次数，等待后重试（指数退避）
        if (attempt < maxRetries) {
          const waitTime = Math.pow(2, attempt) * 1000 // 1s, 2s, 4s
          await this.delay(waitTime)
        }
      }
    }

    // 所有重试都失败了
    if (typeof window !== 'undefined' && window.dispatchEvent) {
      window.dispatchEvent(new CustomEvent('api:request-failure'))
    }
    throw new Error(`网络请求失败: ${lastError?.message || '未知错误'}`)
  }

  /**
   * 创建API错误对象
   * @param {object|string} data - 响应数据
   * @param {number} status - HTTP状态码
   * @returns {Error} 错误对象
   */
  createApiError(data, status) {
    let detail = ''
    if (typeof data === 'object' && data !== null) {
      detail = data.detail || data.message || JSON.stringify(data)
    } else {
      detail = String(data)
    }
    const error = new Error(detail || `HTTP ${status}`)
    error.isApiError = true
    error.status = status
    error.data = data
    return error
  }

  /**
   * GET 请求
   * @param {string} url - 请求URL
   * @param {object} params - 查询参数
   * @returns {Promise<object>} 响应数据
   */
  async get(url, params = {}) {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.set(key, String(value))
      }
    }
    const query = searchParams.toString() ? `?${searchParams.toString()}` : ''
    return this.request(`${url}${query}`, { method: 'GET' })
  }

  /**
   * POST 请求
   * @param {string} url - 请求URL
   * @param {object} data - 请求体数据
   * @returns {Promise<object>} 响应数据
   */
  async post(url, data = {}) {
    return this.request(url, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  /**
   * PUT 请求
   * @param {string} url - 请求URL
   * @param {object} data - 请求体数据
   * @returns {Promise<object>} 响应数据
   */
  async put(url, data = {}) {
    return this.request(url, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  /**
   * DELETE 请求
   * @param {string} url - 请求URL
   * @returns {Promise<object>} 响应数据
   */
  async delete(url) {
    return this.request(url, { method: 'DELETE' })
  }
}

// 创建单例
export const api = new ApiClient()

// 设置全局拦截器
api.addRequestInterceptor((config) => {
  // 可以在这里添加认证token
  // const token = localStorage.getItem('token')
  // if (token) {
  //   config.headers['Authorization'] = `Bearer ${token}`
  // }
  return config
})

api.addResponseInterceptor(async (data, response) => {
  // 可以在这里统一处理响应格式
  return data
})

// API 模块导出
export const proxyApi = {
  getList: (params) => api.get('/proxies', params),
  getStats: () => api.get('/stats'),
  getSubscription: (params) => api.get('/subscription', params),
  deleteUnavailable: () => api.post('/proxies/delete-unavailable'),
  deleteSelected: (keys) => api.post('/proxies/delete-selected', { normalized_keys: keys }),
  importTexts: (items) => api.post('/collector/import-texts', { items }),
}

export const subscriptionApi = {
  getList: (params) => api.get('/subscriptions', params),
  create: (data) => api.post('/subscriptions', data),
  update: (id, data) => api.put(`/subscriptions/${id}`, data),
  delete: (id) => api.delete(`/subscriptions/${id}`),
  refresh: (id, timeout) => api.post(`/subscriptions/${id}/refresh`, { timeout_sec: timeout }),
  refreshAll: (timeout) => api.post('/subscriptions/refresh-all', { timeout_sec: timeout }),
  deleteUnavailable: () => api.post('/subscriptions/delete-unavailable'),
  getUpdateProxy: () => api.get('/subscription-update-proxy'),
  setUpdateProxy: (data) => api.put('/subscription-update-proxy', data),
}

export const taskApi = {
  getList: (params) => api.get('/tasks', params),
  get: (id) => api.get(`/tasks/${id}`),
  start: (type, payload) => api.post(`/tasks/${type}/start`, payload),
  stop: (id) => api.post(`/tasks/${id}/stop`),
  delete: (id) => api.delete(`/tasks/${id}`),
  getAutoConfig: () => api.get('/tasks/auto-config'),
  updateAutoConfig: (data) => api.put('/tasks/auto-config', data),
}

export const poolApi = {
  getList: (params) => api.get('/pools', params),
  create: (data) => api.post('/pools', data),
  update: (id, data) => api.put(`/pools/${id}`, data),
  delete: (id) => api.delete(`/pools/${id}`),
  sync: (id) => api.post(`/pools/${id}/sync`),
  getChainConfig: (id) => api.get(`/pools/${id}/chain`),
  updateChainConfig: (id, data) => api.put(`/pools/${id}/chain`, data),
  getSessionRules: (id) => api.get(`/pools/${id}/chain/session-rules`),
  upsertSessionRule: (id, prefix, data) => api.put(`/pools/${id}/chain/session-rules/${encodeURIComponent(prefix)}`, data),
  deleteSessionRule: (id, prefix) => api.delete(`/pools/${id}/chain/session-rules/${encodeURIComponent(prefix)}`),
  testRoute: (id, params) => api.get(`/pools/${id}/chain/route-test`, params),
}

export const gatewayApi = {
  getEndpoints: () => api.get('/http-proxy-endpoints'),
  createEndpoint: (data) => api.post('/http-proxy-endpoints', data),
  updateEndpoint: (id, data) => api.put(`/http-proxy-endpoints/${id}`, data),
  deleteEndpoint: (id) => api.delete(`/http-proxy-endpoints/${id}`),
  getStatus: (endpointId) => api.get('/gateway/http-status', { endpoint_id: endpointId }),
  runHealthCheck: () => api.post('/gateway/http-health-check'),
  test: (data) => api.post('/gateway/http-test', data),
  testEndpointRoute: (endpointId, params) => api.get(`/http-proxy-endpoints/${endpointId}/route-test`, params),
  getServiceConfig: () => api.get('/http-proxy-endpoints/service-config'),
  updateServiceConfig: (data) => api.put('/http-proxy-endpoints/service-config', data),
}

export const backendApi = {
  getStatus: () => api.get('/backend/status'),
  start: () => api.post('/backend/start'),
  stop: () => api.post('/backend/stop'),
  restart: () => api.post('/backend/restart'),
  getEvents: (params) => api.get('/backend/process-events', params),
  getDefaultPortRange: () => api.get('/backend/default-port-range'),
  updateDefaultPortRange: (data) => api.put('/backend/default-port-range', data),
  getDefaultListen: () => api.get('/backend/default-listen'),
  updateDefaultListen: (data) => api.put('/backend/default-listen', data),
  createInstance: (data) => api.post('/backend/instances', data),
  startInstance: (id) => api.post(`/backend/instances/${encodeURIComponent(id)}/start`),
  stopInstance: (id) => api.post(`/backend/instances/${encodeURIComponent(id)}/stop`),
  deleteInstance: (id) => api.delete(`/backend/instances/${encodeURIComponent(id)}`),
  getInstanceRoutes: (id) => api.get(`/backend/instances/${encodeURIComponent(id)}/routes`),
}

export const chainApi = {
  getStatus: () => api.get('/chain/status'),
  getHealth: () => api.get('/chain/health'),
  getLeases: () => api.get('/chain/leases'),
  start: () => api.post('/chain/start'),
  stop: () => api.post('/chain/stop'),
  updatePool: (type, params) => api.post(`/chain/pools/${type}`, null, { params }),
  cleanupLeases: () => api.post('/chain/leases/cleanup'),
}

export const publishedSubscriptionApi = {
  getList: (params) => api.get('/published-subscriptions', params),
  create: (data) => api.post('/published-subscriptions', data),
  update: (id, data) => api.put(`/published-subscriptions/${id}`, data),
  delete: (id) => api.delete(`/published-subscriptions/${id}`),
  getExportUrl: (id) => `/api/published-subscriptions/${id}/subscription`,
}

export const testerApi = {
  runSingle: (data) => api.post('/tester/run-one', data),
}
