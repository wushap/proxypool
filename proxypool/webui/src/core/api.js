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
   * 发送请求
   * @param {string} url - 请求URL（相对于BASE_URL）
   * @param {object} options - 请求选项
   * @returns {Promise<object>} 响应数据
   */
  async request(url, options = {}) {
    const fullUrl = `${this.baseUrl}${url}`

    // 执行请求拦截器
    let config = { url: fullUrl, ...options }
    for (const interceptor of this.interceptors.request) {
      config = await interceptor(config)
    }

    try {
      const response = await fetch(config.url, {
        headers: {
          'Content-Type': 'application/json',
          ...config.headers,
        },
        ...config,
      })

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

      return data
    } catch (error) {
      if (error.isApiError) throw error
      throw new Error(`网络请求失败: ${error.message}`)
    }
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
  deleteUnavailable: () => api.post('/proxies/delete-unavailable'),
  deleteSelected: (keys) => api.post('/proxies/delete-selected', { normalized_keys: keys }),
}

export const subscriptionApi = {
  getList: () => api.get('/subscriptions'),
  create: (data) => api.post('/subscriptions', data),
  update: (id, data) => api.put(`/subscriptions/${id}`, data),
  delete: (id) => api.delete(`/subscriptions/${id}`),
  refresh: (id, timeout) => api.post(`/subscriptions/${id}/refresh`, { timeout_sec: timeout }),
}

export const taskApi = {
  getList: () => api.get('/tasks'),
  start: (type, payload) => api.post(`/tasks/${type}/start`, payload),
  stop: (id) => api.post(`/tasks/${id}/stop`),
  delete: (id) => api.delete(`/tasks/${id}`),
}

export const poolApi = {
  getList: () => api.get('/pools'),
  create: (data) => api.post('/pools', data),
  update: (id, data) => api.put(`/pools/${id}`, data),
  delete: (id) => api.delete(`/pools/${id}`),
  sync: (id) => api.post(`/pools/${id}/sync`),
}

export const gatewayApi = {
  getEndpoints: () => api.get('/http-proxy-endpoints'),
  createEndpoint: (data) => api.post('/http-proxy-endpoints', data),
  updateEndpoint: (id, data) => api.put(`/http-proxy-endpoints/${id}`, data),
  deleteEndpoint: (id) => api.delete(`/http-proxy-endpoints/${id}`),
  getStatus: (endpointId) => api.get('/gateway/http-status', { endpoint_id: endpointId }),
  runHealthCheck: () => api.post('/gateway/http-health-check'),
}

export const backendApi = {
  getStatus: () => api.get('/backend/status'),
  start: () => api.post('/backend/start'),
  stop: () => api.post('/backend/stop'),
  restart: () => api.post('/backend/restart'),
}
