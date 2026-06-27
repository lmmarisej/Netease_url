/**
 * API 文档 - Tab 管理（打开/关闭接口标签页）
 */
import { ref, computed, reactive, nextTick } from 'vue'
import { primaryMethod, getEndpointKey } from './useApiDocsUtils.js'

export function useApiTabs(apiMeta) {
  const openTabs = ref([])
  const activeTabId = ref(null)

  /** 当前激活的端点 */
  const activeEndpoint = computed(() => {
    if (!activeTabId.value) return null
    return openTabs.value.find(t => t.id === activeTabId.value) || null
  })

  /** 当前激活端点的响应数据 */
  const responseData = computed(() => {
    if (!activeEndpoint.value) return null
    return activeEndpoint.value._response
  })

  /** 打开/选中一个端点 */
  function selectEndpoint(ep, cat) {
    const key = getEndpointKey(ep)
    const existing = openTabs.value.find(t => t.id === key)
    if (existing) {
      activeTabId.value = key
      return
    }

    const baseUrl = apiMeta.value?.base_url || window.location.origin
    const defaultUrl = `${baseUrl}${ep.path}`

    const params = (ep.parameters || []).map(p => ({
      ...p,
      _enabled: p.required !== false,
      _value: p.default || '',
    }))

    const tab = reactive({
      id: key,
      method: ep.method,
      name: ep.path.length > 30 ? ep.path.substring(0, 28) + '..' : ep.path,
      path: ep.path,
      originalMethod: ep.method,
      _activeMethod: primaryMethod(ep.method),
      _requestUrl: defaultUrl,
      _requestTab: 'params',
      _responseTab: 'body',
      _bodyMode: 'none',
      _bodyRawContent: '',
      _params: params,
      _customParams: [],
      _headers: [],
      _formData: [],
      _response: null,
      _categoryName: cat?.name || '',
    })

    openTabs.value.push(tab)
    activeTabId.value = key
  }

  function closeTab(id) {
    const idx = openTabs.value.findIndex(t => t.id === id)
    if (idx === -1) return
    openTabs.value.splice(idx, 1)
    if (activeTabId.value === id) {
      if (openTabs.value.length > 0) {
        activeTabId.value = openTabs.value[Math.min(idx, openTabs.value.length - 1)].id
      } else {
        activeTabId.value = null
      }
    }
  }

  function closeOtherTabs(id) {
    const keep = openTabs.value.find(t => t.id === id)
    openTabs.value = keep ? [keep] : []
    activeTabId.value = id
  }

  function closeAllTabs() {
    openTabs.value = []
    activeTabId.value = null
  }

  // ========== Tab 右键菜单 ==========
  const tabMenu = reactive({ show: false, x: 0, y: 0, tab: null })

  function openTabMenu(event, tab) {
    tabMenu.show = false
    nextTick(() => {
      tabMenu.x = event.clientX
      tabMenu.y = event.clientY
      tabMenu.tab = tab
      tabMenu.show = true
    })
  }

  return {
    openTabs,
    activeTabId,
    activeEndpoint,
    responseData,
    selectEndpoint,
    closeTab,
    closeOtherTabs,
    closeAllTabs,
    tabMenu,
    openTabMenu,
  }
}
