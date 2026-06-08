import axios from 'axios'

const api = axios.create({
  baseURL: '/',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Response interceptor
api.interceptors.response.use(
  response => response.data,
  error => {
    const message = error.response?.data?.message || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

// ==================== 音乐相关 ====================

export function getSongInfo(params) {
  return api.post('/api/song', params)
}

export function searchMusic(params) {
  return api.post('/api/search', params)
}

export function getPlaylist(params) {
  return api.post('/api/playlist', params)
}

export function getAlbum(params) {
  return api.post('/api/album', params)
}

export function downloadMusic(params, options = {}) {
  // 对于二进制下载，使用原始 axios 实例避免拦截器提取 .data
  const instance = axios.create({ baseURL: '/', timeout: 120000 })
  return instance.post('/api/download', params, { responseType: 'blob', ...options })
}

// ==================== 同步配置 ====================

export function getSyncConfig() {
  return api.get('/api/sync/config')
}

export function saveSyncConfig(data) {
  return api.post('/api/sync/config', data)
}

export function getSyncStatus() {
  return api.get('/api/sync/status')
}

export function triggerSyncNow() {
  return api.post('/api/sync/now')
}

// ==================== Cookie ====================

export function getCookie() {
  return api.get('/api/cookie')
}

export function saveCookie(data) {
  return api.post('/api/cookie', data)
}

// ==================== 设置 ====================

export function getSettings() {
  return api.get('/api/settings')
}

export function saveSettings(data) {
  return api.post('/api/settings', data)
}

// ==================== 文件管理 ====================

export function getFileList() {
  return api.get('/api/files/list')
}

export function deleteFiles(data) {
  return api.post('/api/files/delete', data)
}

export function readFile(filename) {
  return api.get(`/api/files/read/${encodeURIComponent(filename)}`)
}

export function saveFile(data) {
  return api.post('/api/files/save', data)
}

export function getFileStreamUrl(filename, download = false) {
  return `/api/files/stream/${encodeURIComponent(filename)}${download ? '?download=1' : ''}`
}

// ==================== 任务管理 ====================

export function getTasks() {
  return api.get('/api/tasks')
}

export function deleteTask(taskId) {
  return api.delete(`/api/tasks/${taskId}`)
}

export function clearTasks() {
  return api.post('/api/tasks/clear')
}

// ==================== 日志 ====================

export function getLogs(params) {
  return api.get('/api/logs', { params })
}

export function cleanupLogs() {
  return api.post('/api/logs/cleanup')
}

// ==================== 推送 ====================

export function getPushConfig() {
  return api.get('/api/push/config')
}

export function savePushConfig(data) {
  return api.post('/api/push/config', data)
}

export function sendPush(data) {
  return api.post('/api/push/send', data)
}

export function getEventsCatalog() {
  return api.get('/api/events/catalog')
}

export function getEventsHistory(params) {
  return api.get('/api/events/history', { params })
}

// ==================== API 文档 ====================

export function getApiDocs() {
  return api.get('/api/api-docs')
}

// ==================== 健康检查 ====================

export function healthCheck() {
  return api.get('/api/health')
}
