<template>
  <div class="api-docs-page">
    <!-- ========== 顶部标题栏 ========== -->
    <div class="api-header-bar d-flex align-center px-4">
      <v-icon size="20" color="primary" class="mr-2">mdi-api</v-icon>
      <span class="text-subtitle-2 font-weight-bold">
        API 接口调试
        <span class="text-caption text-medium-emphasis ml-2">
          工作区: {{ apiMeta.name || '网易云音乐API服务' }} v{{ apiMeta.version || '2.0.0' }}
        </span>
      </span>
      <v-spacer />
      <v-chip v-if="!loading && apiData" size="x-small" variant="tonal" color="primary">
        <v-icon start size="12">mdi-pillar</v-icon>
        {{ endpointsCount }} 接口
      </v-chip>
    </div>

    <!-- ========== 错误 / 加载状态 ========== -->
    <v-alert v-if="error" type="error" variant="tonal" class="ma-0" density="compact" closable>{{ error }}</v-alert>
    <v-progress-linear v-if="loading" indeterminate color="primary" />

    <!-- ========== 主区域：左侧列表 + 右侧控制台 ========== -->
    <div v-if="!loading && !error && apiData" class="api-body">
      <!-- ===== 左侧：接口目录树 ===== -->
      <div class="api-sidebar">
        <div class="sidebar-head pa-3">
          <v-text-field
            v-model="searchQuery"
            prepend-inner-icon="mdi-magnify"
            placeholder="搜索接口..."
            density="compact"
            hide-details
            variant="outlined"
            clearable
          />
          <div class="text-caption text-medium-emphasis mt-2 px-1 d-flex align-center">
            <span>COLLECTIONS</span>
            <v-spacer />
            <v-btn variant="text" size="x-small" icon @click="expandAllSidebar" title="全部展开">
              <v-icon size="14">mdi-expand-all</v-icon>
            </v-btn>
            <v-btn variant="text" size="x-small" icon class="ml-1" @click="collapseAllSidebar" title="全部收起">
              <v-icon size="14">mdi-collapse-all</v-icon>
            </v-btn>
          </div>
        </div>

        <div class="sidebar-tree">
          <div v-for="(cat, ci) in filteredCategories" :key="ci" class="sidebar-category">
            <div
              class="sidebar-category-header d-flex align-center pa-2 cursor-pointer"
              @click="toggleCategory(cat.name)"
            >
              <v-icon size="16" class="mr-1" color="medium-emphasis">
                {{ isCategoryExpanded(cat.name) ? 'mdi-chevron-down' : 'mdi-chevron-right' }}
              </v-icon>
              <v-icon size="16" class="mr-1" color="primary">mdi-folder-outline</v-icon>
              <span class="text-body-2 font-weight-medium flex-grow-1">{{ cat.name }}</span>
              <span class="text-caption text-medium-emphasis">({{ (filterEndpoints(cat.endpoints) || []).length }})</span>
            </div>

            <div v-show="isCategoryExpanded(cat.name)">
              <div
                v-for="(ep, ei) in filterEndpoints(cat.endpoints)"
                :key="ei"
                class="sidebar-endpoint d-flex align-center pa-2 cursor-pointer"
                :class="{ 'sidebar-endpoint-active': activeTabId === getEndpointKey(ep) }"
                @click="selectEndpoint(ep, cat)"
              >
                <span
                  class="method-badge mr-2"
                  :style="{ color: methodTextColor(ep.method), backgroundColor: methodBgColor(ep.method) }"
                >{{ primaryMethod(ep.method) }}</span>
                <span class="text-caption ep-name" :title="ep.path">{{ ep.path }}</span>
              </div>
            </div>
          </div>

          <div v-if="filteredCategories.length === 0" class="pa-4 text-center text-medium-emphasis text-caption">
            没有匹配的接口
          </div>
        </div>
      </div>

      <!-- ===== 右侧：操作控制台 ===== -->
      <div class="api-console" @click="tabMenu.show = false">
        <!-- 空状态 -->
        <div v-if="!activeTabId" class="console-empty d-flex flex-column align-center justify-center pa-8">
          <v-icon size="56" class="mb-4 text-medium-emphasis">mdi-api</v-icon>
          <p class="text-h6 font-weight-medium mb-1">选择一个接口开始调试</p>
          <p class="text-body-2 text-medium-emphasis">从左侧列表中选择一个接口</p>
        </div>

        <template v-else>
          <!-- ===== Tab 栏 ===== -->
          <div class="console-tabs d-flex align-center">
            <div
              v-for="tab in openTabs"
              :key="tab.id"
              class="console-tab d-flex align-center pa-2 cursor-pointer"
              :class="{ 'console-tab-active': tab.id === activeTabId }"
              @click="activeTabId = tab.id"
              @contextmenu.prevent="openTabMenu($event, tab)"
            >
              <span class="method-dot mr-1" :style="{ color: methodTextColor(tab.method) }">{{ primaryMethod(tab.method) }}</span>
              <span class="text-caption tab-label">{{ tab.name }}</span>
              <v-icon size="12" class="ml-1 tab-close-btn" @click.stop="closeTab(tab.id)">mdi-close</v-icon>
            </div>
          </div>

          <!-- Tab 右键菜单 -->
          <v-card
            v-if="tabMenu.show"
            class="tab-context-menu py-1"
            :style="{ position: 'fixed', left: tabMenu.x + 'px', top: tabMenu.y + 'px', zIndex: 9999 }"
            width="140"
            elevation="8"
          >
            <div class="tab-context-item pa-2 text-caption cursor-pointer" @click="closeTab(tabMenu.tab?.id); tabMenu.show = false">关闭</div>
            <div class="tab-context-item pa-2 text-caption cursor-pointer" @click="closeOtherTabs(tabMenu.tab?.id); tabMenu.show = false">关闭其他</div>
            <div class="tab-context-item pa-2 text-caption cursor-pointer" @click="closeAllTabs(); tabMenu.show = false">关闭全部</div>
          </v-card>

          <!-- ===== 请求栏 ===== -->
          <div class="console-request-bar d-flex align-center px-3 py-2" style="gap:8px;">
            <v-select
              v-model="activeEndpoint._activeMethod"
              :items="httpMethods"
              density="compact"
              hide-details
              variant="outlined"
              class="method-select"
            />
            <v-text-field
              v-model="activeEndpoint._requestUrl"
              density="compact"
              hide-details
              variant="outlined"
              placeholder="http://127.0.0.1:5000/path"
              class="url-input"
            />
            <v-btn
              color="primary"
              variant="flat"
              size="default"
              :loading="sending"
              @click="sendRequest"
              class="send-btn text-none"
            >
              <v-icon start size="16">mdi-send</v-icon>
              Send
            </v-btn>
          </div>

          <!-- ===== 参数配置区（可滚动） ===== -->
          <div class="console-config">
            <v-tabs v-model="activeEndpoint._requestTab" density="compact" color="primary">
              <v-tab value="params" size="small">Params</v-tab>
              <v-tab value="headers" size="small">Headers</v-tab>
              <v-tab value="body" size="small">Body</v-tab>
            </v-tabs>
            <v-divider />

            <div class="config-scroll">
              <!-- Params -->
              <div v-if="activeEndpoint._requestTab === 'params'">
                <template v-if="activeEndpoint._params && activeEndpoint._params.length">
                  <div class="kv-table-header d-flex align-center px-3 py-1 text-caption font-weight-bold">
                    <span style="width:32px;text-align:center;">#</span>
                    <span style="flex:1;">Key</span>
                    <span style="flex:2;">Value</span>
                    <span style="width:44px;text-align:center;">必填</span>
                    <span style="flex:1;">说明</span>
                  </div>
                  <div
                    v-for="(p, pi) in activeEndpoint._params"
                    :key="pi"
                    class="kv-row d-flex align-center px-3 py-0"
                  >
                    <span style="width:32px;text-align:center;">
                      <v-checkbox-btn v-model="p._enabled" density="compact" hide-details color="primary" />
                    </span>
                    <span style="flex:1;">
                      <code class="text-caption px-1 rounded bg-surface-variant">{{ p.name }}</code>
                    </span>
                    <span style="flex:2;">
                      <v-text-field
                        v-model="p._value"
                        :placeholder="p.default || 'Value'"
                        density="compact"
                        hide-details
                        variant="underlined"
                        class="kv-input"
                      />
                    </span>
                    <span style="width:44px;text-align:center;">
                      <span :class="p.required ? 'text-error text-caption font-weight-bold' : 'text-caption text-medium-emphasis'">{{ p.required ? '是' : '否' }}</span>
                    </span>
                    <span style="flex:1;" class="text-caption text-medium-emphasis">{{ p.description || p.note || '' }}</span>
                  </div>
                </template>

                <div class="pa-3">
                  <div v-for="(cp, cpi) in activeEndpoint._customParams" :key="cpi" class="d-flex align-center ga-2 mb-1">
                    <v-text-field v-model="cp.name" placeholder="Key" density="compact" hide-details variant="underlined" style="flex:1;" />
                    <v-text-field v-model="cp.value" placeholder="Value" density="compact" hide-details variant="underlined" style="flex:2;" />
                    <v-btn icon size="x-small" variant="text" color="error" @click="removeCustomParam(cpi)">
                      <v-icon size="14">mdi-close-circle-outline</v-icon>
                    </v-btn>
                  </div>
                  <v-btn variant="text" color="primary" size="x-small" @click="addCustomParam" class="mt-1">
                    <v-icon start size="14">mdi-plus</v-icon>添加自定义参数
                  </v-btn>
                </div>
              </div>

              <!-- Headers -->
              <div v-if="activeEndpoint._requestTab === 'headers'" class="pa-3">
                <div v-for="(h, hi) in activeEndpoint._headers" :key="hi" class="d-flex align-center ga-2 mb-1">
                  <v-text-field v-model="h.name" placeholder="Header" density="compact" hide-details variant="underlined" style="flex:1;" />
                  <v-text-field v-model="h.value" placeholder="Value" density="compact" hide-details variant="underlined" style="flex:2;" />
                  <v-btn icon size="x-small" variant="text" color="error" @click="activeEndpoint._headers.splice(hi, 1)">
                    <v-icon size="14">mdi-close-circle-outline</v-icon>
                  </v-btn>
                </div>
                <div class="d-flex align-center ga-2">
                  <v-text-field v-model="newHeaderName" placeholder="Header" density="compact" hide-details variant="underlined" style="flex:1;" @keydown.enter="addHeader" />
                  <v-text-field v-model="newHeaderValue" placeholder="Value" density="compact" hide-details variant="underlined" style="flex:2;" @keydown.enter="addHeader" />
                  <v-btn variant="text" color="primary" size="x-small" @click="addHeader">
                    <v-icon size="16">mdi-plus</v-icon>
                  </v-btn>
                </div>
              </div>

              <!-- Body -->
              <div v-if="activeEndpoint._requestTab === 'body'">
                <v-radio-group
                  v-model="activeEndpoint._bodyMode"
                  inline
                  density="compact"
                  hide-details
                  class="body-radio-group pa-3"
                >
                  <v-radio value="none" label="none" />
                  <v-radio value="form-data" label="form-data" />
                  <v-radio value="x-www-form-urlencoded" label="x-www-form-urlencoded" />
                  <v-radio value="raw" label="raw" />
                </v-radio-group>
                <v-divider />
                <div v-if="activeEndpoint._bodyMode === 'raw'" class="pa-3">
                  <v-textarea
                    v-model="activeEndpoint._bodyRawContent"
                    variant="underlined"
                    hide-details
                    rows="8"
                    class="body-textarea"
                    placeholder='{\n  "key": "value"\n}'
                  />
                </div>
                <div v-else-if="activeEndpoint._bodyMode === 'form-data' || activeEndpoint._bodyMode === 'x-www-form-urlencoded'" class="pa-3">
                  <div v-for="(fd, fdi) in activeEndpoint._formData" :key="fdi" class="d-flex align-center ga-2 mb-1">
                    <v-text-field v-model="fd.name" placeholder="Key" density="compact" hide-details variant="underlined" style="flex:1;" />
                    <v-text-field v-model="fd.value" placeholder="Value" density="compact" hide-details variant="underlined" style="flex:2;" />
                    <v-btn icon size="x-small" variant="text" color="error" @click="activeEndpoint._formData.splice(fdi, 1)">
                      <v-icon size="14">mdi-close-circle-outline</v-icon>
                    </v-btn>
                  </div>
                  <v-btn variant="text" color="primary" size="x-small" @click="activeEndpoint._formData.push({name:'',value:''})">
                    <v-icon start size="14">mdi-plus</v-icon>添加
                  </v-btn>
                </div>
                <div v-else class="text-caption text-medium-emphasis pa-8 text-center">
                  此请求不使用 body
                </div>
              </div>
            </div>
          </div>

          <!-- ===== 响应面板（固定底部） ===== -->
          <div class="console-response" v-if="responseData">
            <v-divider />
            <div class="response-status-bar d-flex align-center px-3 py-2">
              <v-icon size="14" :color="responseData.success ? 'success' : 'error'" class="mr-1">
                {{ responseData.success ? 'mdi-check-circle' : 'mdi-alert-circle' }}
              </v-icon>
              <span class="text-body-2 font-weight-bold">{{ responseData.statusText }}</span>
              <v-chip size="x-small" variant="tonal" class="ml-2">{{ responseData.duration }}ms</v-chip>
              <v-chip size="x-small" variant="tonal" class="ml-1">{{ responseData.size }}</v-chip>
              <v-spacer />
              <v-btn variant="text" size="x-small" color="medium-emphasis" @click="copyResponse">
                <v-icon start size="14">mdi-content-copy</v-icon>复制
              </v-btn>
              <v-btn variant="text" size="x-small" color="medium-emphasis" class="ml-1" @click="clearResponse">
                <v-icon start size="14">mdi-close</v-icon>清除
              </v-btn>
            </div>
            <v-tabs v-model="activeEndpoint._responseTab" density="compact" color="primary" class="response-tabs">
              <v-tab value="body" size="small">Body</v-tab>
              <v-tab value="headers" size="small">Headers</v-tab>
            </v-tabs>
            <div class="response-scroll pa-3">
              <pre class="response-pre"><code>{{ activeEndpoint._responseTab === 'body' ? responseData.body : responseData.headers }}</code></pre>
            </div>
          </div>
          <div v-else class="console-response-empty pa-3 text-center">
            <v-divider class="mb-2" />
            <span class="text-caption text-medium-emphasis">点击「Send」发送请求，响应将显示在此处</span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, computed, onMounted } from 'vue'
import { getApiDocs } from '@/api/index.js'
import { httpMethods, methodTextColor, methodBgColor, primaryMethod, getEndpointKey } from '@/composables/useApiDocsUtils.js'
import { useApiSidebar } from '@/composables/useApiSidebar.js'
import { useApiTabs } from '@/composables/useApiTabs.js'
import { useApiRequest } from '@/composables/useApiRequest.js'

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
  filteredCategories,
  isCategoryExpanded,
  toggleCategory,
  filterEndpoints,
  expandAllSidebar,
  collapseAllSidebar,
  initSidebar,
} = useApiSidebar(apiData)

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