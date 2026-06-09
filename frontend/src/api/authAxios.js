import axios from 'axios'

/**
 * 请求拦截器：自动从 localStorage 读取 token 并附加到 Authorization header
 */
function authRequestInterceptor(config) {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}

/**
 * 响应错误拦截器：401 时自动清除登录态并跳转登录页
 */
function authResponseError(error) {
  if (error.response?.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
  }
  const message = error.response?.data?.message || error.message || '请求失败'
  return Promise.reject(new Error(message))
}

/**
 * 创建带认证拦截器的 axios 实例
 *
 * 自动附加 Authorization: Bearer <token> 请求头，
 * 并在收到 401 响应时清除登录态、跳转登录页。
 *
 * @param {object} config - axios 配置（会合并到默认配置）
 * @returns {axios.AxiosInstance}
 */
export function createAuthAxios(config = {}) {
  const instance = axios.create({
    baseURL: '/',
    timeout: 120000,
    headers: { 'Content-Type': 'application/json' },
    ...config,
  })
  instance.interceptors.request.use(authRequestInterceptor, error => Promise.reject(error))
  instance.interceptors.response.use(response => response, authResponseError)
  return instance
}
