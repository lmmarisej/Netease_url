<template>
  <div class="api-docs-page">
    <ApiDocsHeader
      :api-meta="apiMeta"
      :loading="loading"
      :api-data="apiData"
      :endpoints-count="endpointsCount"
    />

    <v-alert v-if="error" type="error" variant="tonal" class="ma-0" density="compact" closable>{{ error }}</v-alert>
    <v-progress-linear v-if="loading" indeterminate color="primary" />

    <div v-if="!loading && !error && apiData" class="api-body">
      <ApiDocsSidebar
        v-model:search-query="searchQuery"
        :filtered-categories="filteredCategories"
        :expanded-categories="expandedCategories"
        :active-tab-id="activeTabId"
        :sidebar-all-expanded="sidebarAllExpanded"
        @expand-all="expandAllSidebar"
        @collapse-all="collapseAllSidebar"
        @toggle-category="toggleCategory"
        @select-endpoint="selectEndpoint"
      />

      <ApiDocsConsole
        :open-tabs="openTabs"
        :active-tab-id="activeTabId"
        :active-endpoint="activeEndpoint"
        :response-data="responseData"
        :tab-menu="tabMenu"
        :http-methods="httpMethods"
        :sending="sending"
        :new-header-name="newHeaderName"
        :new-header-value="newHeaderValue"
        @update:active-tab-id="activeTabId = $event"
        @update:new-header-name="newHeaderName = $event"
        @update:new-header-value="newHeaderValue = $event"
        @click-console="tabMenu.show = false"
        @tab-menu="openTabMenu"
        @close-tab="closeTab"
        @close-others="closeOtherTabs"
        @close-all="closeAllTabs"
        @close-menu="tabMenu.show = false"
        @send-request="sendRequest"
        @add-custom-param="addCustomParam"
        @remove-custom-param="removeCustomParam"
        @add-header="addHeader"
        @copy-response="copyResponse"
        @clear-response="clearResponse"
      />
    </div>
  </div>
</template>


<script setup>
import { ref, computed, onMounted } from 'vue'
import { getApiDocs } from '@/api/index.js'
import { httpMethods } from '@/composables/useApiDocsUtils.js'
import { useApiSidebar } from '@/composables/useApiSidebar.js'
import { useApiTabs } from '@/composables/useApiTabs.js'
import { useApiRequest } from '@/composables/useApiRequest.js'
import ApiDocsHeader from '@/components/api-docs/ApiDocsHeader.vue'
import ApiDocsSidebar from '@/components/api-docs/ApiDocsSidebar.vue'
import ApiDocsConsole from '@/components/api-docs/ApiDocsConsole.vue'

// ========== 基础数据 ==========
const loading = ref(true)
const error = ref('')
const apiData = ref(null)
const sending = ref(false)
const newHeaderName = ref('')
const newHeaderValue = ref('')

const apiMeta = computed(() => apiData.value?.api || {})
const endpointsCount = computed(() => {
  let n = 0
  for (const cat of apiData.value?.categories || []) n += (cat.endpoints || []).length
  return n
})

// ========== 左侧边栏 ==========
const {
  searchQuery,
  expandedCategories,
  filteredCategories,
  toggleCategory,
  expandAllSidebar,
  collapseAllSidebar,
  initSidebar,
} = useApiSidebar(apiData)

/** 所有分类是否已全部展开 */
const sidebarAllExpanded = computed(() => {
  if (!apiData.value?.categories) return false
  return apiData.value.categories.every(cat => expandedCategories.has(cat.name))
})

// ========== Tab 管理 ==========
const {
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
} = useApiTabs(apiMeta)

// ========== 请求与响应 ==========
const {
  addCustomParam,
  removeCustomParam,
  addHeader,
  sendRequest,
  copyResponse,
  clearResponse,
} = useApiRequest(activeEndpoint, sending, newHeaderName, newHeaderValue, responseData)

// ========== 初始化 ==========
onMounted(async () => {
  try {
    loading.value = true
    const res = await getApiDocs()
    if (res?.status === 200 && res.data) apiData.value = res.data
    else if (res?.data) apiData.value = res.data
    initSidebar()
  } catch (e) {
    error.value = e.message || '加载 API 文档失败'
  } finally {
    loading.value = false
  }
})

</script>

<style scoped>
/* ========== 页面布局 ========== */
.api-docs-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
  overflow: hidden;
}

.api-header-bar {
  flex-shrink: 0;
  height: 40px;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.12);
}

/* ========== 主区域：左右布局 ========== */
.api-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ===== 左侧边栏容器 ===== */
.api-sidebar {
  width: 260px;
  min-width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(var(--v-border-color), 0.12);
  overflow: hidden;
}

.sidebar-head {
  flex-shrink: 0;
}

.sidebar-tree {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

/* ===== 右侧控制台容器 ===== */
.api-console {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* ===== 滚动条美化 ===== */
.sidebar-tree::-webkit-scrollbar,
.response-scroll::-webkit-scrollbar,
.config-scroll::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}

.sidebar-tree::-webkit-scrollbar-thumb,
.response-scroll::-webkit-scrollbar-thumb,
.config-scroll::-webkit-scrollbar-thumb {
  background: rgba(var(--v-theme-on-surface), 0.15);
  border-radius: 3px;
}
</style>