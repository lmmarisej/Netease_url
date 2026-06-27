/**
 * API 文档 - 左侧边栏（接口目录树）逻辑
 */
import { ref, computed, reactive } from 'vue'

export function useApiSidebar(apiData) {
  const searchQuery = ref('')
  const expandedCategories = reactive(new Set())

  /** 根据搜索词过滤后的分类列表 */
  const filteredCategories = computed(() => {
    if (!apiData.value?.categories) return []
    const q = searchQuery.value.trim().toLowerCase()
    return apiData.value.categories
      .map(cat => ({ ...cat, endpoints: cat.endpoints || [] }))
      .filter(cat => {
        if (!q) return true
        return cat.name.toLowerCase().includes(q) ||
          cat.endpoints.some(ep =>
            ep.path.toLowerCase().includes(q) ||
            ep.method.toLowerCase().includes(q) ||
            (ep.summary || '').toLowerCase().includes(q)
          )
      })
  })

  function isCategoryExpanded(catName) {
    return expandedCategories.has(catName)
  }

  function toggleCategory(catName) {
    if (expandedCategories.has(catName)) {
      expandedCategories.delete(catName)
    } else {
      expandedCategories.add(catName)
    }
  }

  function filterEndpoints(endpoints) {
    const q = searchQuery.value.trim().toLowerCase()
    if (!q) return endpoints
    return (endpoints || []).filter(ep =>
      ep.path.toLowerCase().includes(q) ||
      ep.method.toLowerCase().includes(q) ||
      (ep.summary || '').toLowerCase().includes(q)
    )
  }

  function expandAllSidebar() {
    if (!apiData.value?.categories) return
    for (const cat of apiData.value.categories) expandedCategories.add(cat.name)
  }

  function collapseAllSidebar() {
    expandedCategories.clear()
  }

  /** 初始化：展开所有分类 */
  function initSidebar() {
    if (apiData.value?.categories) {
      for (const cat of apiData.value.categories) {
        expandedCategories.add(cat.name)
      }
    }
  }

  return {
    searchQuery,
    expandedCategories,
    filteredCategories,
    isCategoryExpanded,
    toggleCategory,
    filterEndpoints,
    expandAllSidebar,
    collapseAllSidebar,
    initSidebar,
  }
}
