/**
 * API 文档 - 请求构建与发送逻辑
 */
import { ref } from 'vue'
import axios from 'axios'

export function useApiRequest(activeEndpoint, sending, newHeaderName, newHeaderValue, responseData) {
  // ========== 参数操作 ==========
  function addCustomParam() {
    if (activeEndpoint.value) {
      activeEndpoint.value._customParams.push({ name: '', value: '' })
    }
  }

  function removeCustomParam(idx) {
    if (activeEndpoint.value) {
      activeEndpoint.value._customParams.splice(idx, 1)
    }
  }

  function addHeader() {
    if (activeEndpoint.value && newHeaderName.value.trim()) {
      activeEndpoint.value._headers.push({
        name: newHeaderName.value.trim(),
        value: newHeaderValue.value,
      })
      newHeaderName.value = ''
      newHeaderValue.value = ''
    }
  }

  // ========== 请求构建 ==========
  function buildParams() {
    if (!activeEndpoint.value) return {}
    const ep = activeEndpoint.value
    const params = {}
    for (const p of ep._params || []) {
      if (p._enabled && p._value !== '' && p._value != null) {
        let val = p._value
        if (p.type === 'integer' || p.type === 'number') val = Number(val)
        else if (p.type === 'boolean') val = val === 'true' || val === true
        params[p.name] = val
      }
    }
    for (const cp of ep._customParams || []) {
      if (cp.name && cp.name.trim()) params[cp.name.trim()] = cp.value
    }
    return params
  }

  function buildHeaders() {
    if (!activeEndpoint.value) return {}
    const headers = { 'Content-Type': 'application/json' }
    for (const h of activeEndpoint.value._headers || []) {
      if (h.name && h.name.trim()) headers[h.name.trim()] = h.value
    }
    const token = localStorage.getItem('token')
    if (token) headers['Authorization'] = `Bearer ${token}`
    return headers
  }

  function buildBody() {
    if (!activeEndpoint.value) return undefined
    const ep = activeEndpoint.value
    if (ep._bodyMode === 'none') return undefined
    if (ep._bodyMode === 'raw') {
      try { return JSON.parse(ep._bodyRawContent || '{}') }
      catch { return ep._bodyRawContent || {} }
    }
    if (ep._bodyMode === 'form-data' || ep._bodyMode === 'x-www-form-urlencoded') {
      const data = {}
      for (const fd of ep._formData || []) {
        if (fd.name && fd.name.trim()) data[fd.name.trim()] = fd.value
      }
      return data
    }
    return undefined
  }

  // ========== 发送请求 ==========
  async function sendRequest() {
    if (!activeEndpoint.value || sending.value) return
    sending.value = true

    const ep = activeEndpoint.value
    const method = ep._activeMethod?.toLowerCase() || 'get'
    const isGet = method === 'get'
    const url = ep._requestUrl
    const params = buildParams()
    const headers = buildHeaders()
    const body = isGet ? undefined : buildBody()
    const startTime = performance.now()

    try {
      const config = {
        method,
        url,
        timeout: 30000,
        headers,
      }
      if (isGet) config.params = params
      else if (body) config.data = body

      const response = await axios(config)
      const duration = Math.round(performance.now() - startTime)
      const respData = response.data
      const bodyStr = typeof respData === 'string' ? respData : JSON.stringify(respData, null, 2)
      const size = new Blob([bodyStr]).size
      const sizeLabel = size > 1024 ? `${(size / 1024).toFixed(1)} KB` : `${size} B`

      ep._response = {
        success: true,
        status: response.status,
        statusText: `${response.status} ${response.statusText}`,
        duration,
        size: sizeLabel,
        body: bodyStr,
        headers: JSON.stringify(response.headers, null, 2),
      }
    } catch (e) {
      const duration = Math.round(performance.now() - startTime)
      const status = e.response?.status || 0
      let respBody = ''
      if (e.response?.data) {
        respBody = typeof e.response.data === 'string' ? e.response.data : JSON.stringify(e.response.data, null, 2)
      } else {
        respBody = e.message || '请求失败'
      }
      const size = new Blob([respBody]).size
      const sizeLabel = size > 1024 ? `${(size / 1024).toFixed(1)} KB` : `${size} B`

      ep._response = {
        success: status >= 200 && status < 400,
        status,
        statusText: status ? `${status} ${e.response?.statusText || 'Error'}` : 'Network Error',
        duration,
        size: sizeLabel,
        body: respBody,
        headers: e.response?.headers ? JSON.stringify(e.response.headers, null, 2) : '{}',
      }
    } finally {
      sending.value = false
      ep._responseTab = 'body'
    }
  }

  // ========== 响应操作 ==========
  function copyResponse() {
    if (!responseData?.value) return
    navigator.clipboard?.writeText(responseData.value.body)
  }

  function clearResponse() {
    if (activeEndpoint.value) activeEndpoint.value._response = null
  }

  return {
    addCustomParam,
    removeCustomParam,
    addHeader,
    sendRequest,
    copyResponse,
    clearResponse,
  }
}
