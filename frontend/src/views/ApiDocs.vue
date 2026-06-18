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

/* ===== 左侧边栏 ===== */
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

/* ===== 右侧控制台 ===== */
.api-console {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* 空状态 */
.console-empty {
  flex: 1;
}

/* Tab 栏 */
.console-tabs {
  flex-shrink: 0;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.1);
  overflow-x: auto;
  white-space: nowrap;
  min-height: 36px;
}

/* 请求栏 */
.console-request-bar {
  flex-shrink: 0;
}

/* 参数配置区 */
.console-config {
  flex-shrink: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 40%;
}

.config-scroll {
  flex: 1;
  overflow-y: auto;
}

/* 响应面板 */
.console-response {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-top: 1px solid rgba(var(--v-border-color), 0.12);
  overflow: hidden;
}

.console-response-empty {
  flex-shrink: 0;
}

.response-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: auto;
}

.response-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
}

.response-status-bar {
  flex-shrink: 0;
}

.response-tabs {
  flex-shrink: 0;
}

/* ===== 侧边栏样式 ===== */
.sidebar-category-header {
  user-select: none;
}

.sidebar-category-header:hover {
  background: rgba(var(--v-theme-surface-variant), 0.4);
}

.sidebar-endpoint {
  padding-left: 44px !important;
  user-select: none;
  transition: background 0.15s;
}

.sidebar-endpoint:hover {
  background: rgba(var(--v-theme-surface-variant), 0.4);
}

.sidebar-endpoint-active {
  background: rgba(var(--v-theme-primary), 0.08);
  border-left: 2px solid rgb(var(--v-theme-primary));
}

.method-badge {
  font-size: 10px;
  font-weight: 700;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
  min-width: 36px;
  text-align: center;
}

.ep-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== Tab 栏样式 ===== */
.console-tab {
  border-right: 1px solid rgba(var(--v-border-color), 0.08);
  user-select: none;
  position: relative;
}

.console-tab:hover {
  background: rgba(var(--v-theme-surface-variant), 0.3);
}

.console-tab-active {
  background: rgba(var(--v-theme-primary), 0.08);
  border-bottom: 2px solid rgb(var(--v-theme-primary));
}

.method-dot {
  font-size: 10px;
  font-weight: 700;
}

.tab-label {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tab-close-btn {
  opacity: 0;
  transition: opacity 0.15s;
}

.console-tab:hover .tab-close-btn {
  opacity: 1;
}

/* ===== 右键菜单 ===== */
.tab-context-menu {
  position: fixed;
  z-index: 9999;
}

.tab-context-item:hover {
  background: rgba(var(--v-theme-primary), 0.08);
}

/* ===== 请求栏 ===== */
.method-select {
  max-width: 120px;
}

.url-input {
  flex: 1;
}

.send-btn {
  white-space: nowrap;
}

/* ===== 参数/Header/Body ===== */
.kv-table-header {
  background: rgba(var(--v-theme-surface-variant), 0.3);
  border-bottom: 1px solid rgba(var(--v-border-color), 0.08);
}

.kv-input {
  font-size: 13px;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
}

.body-radio-group :deep(.v-selection-control) {
  margin-right: 16px;
}

.body-textarea :deep(textarea) {
  font-size: 13px;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
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