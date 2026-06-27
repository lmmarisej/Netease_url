/**
 * API 文档页面工具函数 - HTTP 方法颜色、标识处理
 */
export const httpMethods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']

const methodColorMap = {
  GET: { text: '#10b981', bg: '#10b98115' },
  POST: { text: '#3b82f6', bg: '#3b82f615' },
  PUT: { text: '#f59e0b', bg: '#f59e0b15' },
  DELETE: { text: '#ef4444', bg: '#ef444415' },
  PATCH: { text: '#8b5cf6', bg: '#8b5cf615' },
  HEAD: { text: '#6b7280', bg: '#6b728015' },
  OPTIONS: { text: '#6b7280', bg: '#6b728015' },
}

export function methodTextColor(method) {
  return methodColorMap[(method || 'GET').toUpperCase()]?.text || '#6b7280'
}

export function methodBgColor(method) {
  return methodColorMap[(method || 'GET').toUpperCase()]?.bg || '#6b728015'
}

export function primaryMethod(method) {
  return (method || 'GET').split(',')[0].trim().toUpperCase()
}

export function getEndpointKey(ep) {
  return `${primaryMethod(ep.method)}_${ep.path}`
}
