<template>
  <div class="api-console" @click="$emit('click-console')">
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
          @click="$emit('update:activeTabId', tab.id)"
          @contextmenu.prevent="$emit('tab-menu', $event, tab)"
        >
          <span class="method-dot mr-1" :style="{ color: methodTextColor(tab.method) }">{{ primaryMethod(tab.method) }}</span>
          <span class="text-caption tab-label">{{ tab.name }}</span>
          <v-icon size="12" class="ml-1 tab-close-btn" @click.stop="$emit('close-tab', tab.id)">mdi-close</v-icon>
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
        <div class="tab-context-item pa-2 text-caption cursor-pointer" @click="$emit('close-tab', tabMenu.tab?.id); $emit('close-menu')">关闭</div>
        <div class="tab-context-item pa-2 text-caption cursor-pointer" @click="$emit('close-others', tabMenu.tab?.id); $emit('close-menu')">关闭其他</div>
        <div class="tab-context-item pa-2 text-caption cursor-pointer" @click="$emit('close-all'); $emit('close-menu')">关闭全部</div>
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
          @click="$emit('send-request')"
          class="send-btn text-none"
        >
          <v-icon start size="16">mdi-send</v-icon>
          Send
        </v-btn>
      </div>

      <!-- ===== 参数配置区 ===== -->
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
              <div v-for="(p, pi) in activeEndpoint._params" :key="pi" class="kv-row d-flex align-center px-3 py-0">
                <span style="width:32px;text-align:center;">
                  <v-checkbox-btn v-model="p._enabled" density="compact" hide-details color="primary" />
                </span>
                <span style="flex:1;">
                  <code class="text-caption px-1 rounded bg-surface-variant">{{ p.name }}</code>
                </span>
                <span style="flex:2;">
                  <v-text-field v-model="p._value" :placeholder="p.default || 'Value'" density="compact" hide-details variant="underlined" class="kv-input" />
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
                <v-btn icon size="x-small" variant="text" color="error" @click="$emit('remove-custom-param', cpi)">
                  <v-icon size="14">mdi-close-circle-outline</v-icon>
                </v-btn>
              </div>
              <v-btn variant="text" color="primary" size="x-small" @click="$emit('add-custom-param')" class="mt-1">
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
              <v-text-field :model-value="newHeaderName" @update:model-value="$emit('update:newHeaderName', $event)" placeholder="Header" density="compact" hide-details variant="underlined" style="flex:1;" @keydown.enter="$emit('add-header')" />
              <v-text-field :model-value="newHeaderValue" @update:model-value="$emit('update:newHeaderValue', $event)" placeholder="Value" density="compact" hide-details variant="underlined" style="flex:2;" @keydown.enter="$emit('add-header')" />
              <v-btn variant="text" color="primary" size="x-small" @click="$emit('add-header')">
                <v-icon size="16">mdi-plus</v-icon>
              </v-btn>
            </div>
          </div>

          <!-- Body -->
          <div v-if="activeEndpoint._requestTab === 'body'">
            <v-radio-group v-model="activeEndpoint._bodyMode" inline density="compact" hide-details class="body-radio-group pa-3">
              <v-radio value="none" label="none" />
              <v-radio value="form-data" label="form-data" />
              <v-radio value="x-www-form-urlencoded" label="x-www-form-urlencoded" />
              <v-radio value="raw" label="raw" />
            </v-radio-group>
            <v-divider />
            <div v-if="activeEndpoint._bodyMode === 'raw'" class="pa-3">
              <v-textarea v-model="activeEndpoint._bodyRawContent" variant="underlined" hide-details rows="8" class="body-textarea" placeholder='{\n  "key": "value"\n}' />
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
            <div v-else class="text-caption text-medium-emphasis pa-8 text-center">此请求不使用 body</div>
          </div>
        </div>
      </div>

      <!-- ===== 响应面板 ===== -->
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
          <v-btn variant="text" size="x-small" color="medium-emphasis" @click="$emit('copy-response')">
            <v-icon start size="14">mdi-content-copy</v-icon>复制
          </v-btn>
          <v-btn variant="text" size="x-small" color="medium-emphasis" class="ml-1" @click="$emit('clear-response')">
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
</template>

<script setup>
import { methodTextColor, methodBgColor, primaryMethod } from '@/composables/useApiDocsUtils.js'

defineProps({
  openTabs: { type: Array, default: () => [] },
  activeTabId: { type: [String, null], default: null },
  activeEndpoint: { type: Object, default: null },
  responseData: { type: Object, default: null },
  tabMenu: { type: Object, default: () => ({ show: false, x: 0, y: 0, tab: null }) },
  httpMethods: { type: Array, default: () => ['GET'] },
  sending: { type: Boolean, default: false },
  newHeaderName: { type: String, default: '' },
  newHeaderValue: { type: String, default: '' },
})

defineEmits([
  'update:activeTabId', 'update:newHeaderName', 'update:newHeaderValue',
  'click-console',
  'tab-menu', 'close-tab', 'close-others', 'close-all', 'close-menu',
  'send-request',
  'add-custom-param', 'remove-custom-param', 'add-header',
  'copy-response', 'clear-response',
])
</script>

<style scoped>
.console-empty { flex: 1; }
.console-tabs { flex-shrink: 0; border-bottom: 1px solid rgba(var(--v-border-color), 0.1); overflow-x: auto; white-space: nowrap; min-height: 36px; }
.console-tab { border-right: 1px solid rgba(var(--v-border-color), 0.08); user-select: none; position: relative; }
.console-tab:hover { background: rgba(var(--v-theme-surface-variant), 0.3); }
.console-tab-active { background: rgba(var(--v-theme-primary), 0.08); border-bottom: 2px solid rgb(var(--v-theme-primary)); }
.method-dot { font-size: 10px; font-weight: 700; }
.tab-label { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tab-close-btn { opacity: 0; transition: opacity 0.15s; }
.console-tab:hover .tab-close-btn { opacity: 1; }
.tab-context-menu { position: fixed; z-index: 9999; }
.tab-context-item:hover { background: rgba(var(--v-theme-primary), 0.08); }
.console-request-bar { flex-shrink: 0; }
.method-select { max-width: 120px; }
.url-input { flex: 1; }
.send-btn { white-space: nowrap; }
.console-config { flex-shrink: 0; overflow: hidden; display: flex; flex-direction: column; max-height: 40%; }
.config-scroll { flex: 1; overflow-y: auto; }
.kv-table-header { background: rgba(var(--v-theme-surface-variant), 0.3); border-bottom: 1px solid rgba(var(--v-border-color), 0.08); }
.kv-input { font-size: 13px; font-family: 'Cascadia Code', 'Fira Code', monospace; }
.body-radio-group :deep(.v-selection-control) { margin-right: 16px; }
.body-textarea :deep(textarea) { font-size: 13px; font-family: 'Cascadia Code', 'Fira Code', monospace; }
.console-response { flex: 1; display: flex; flex-direction: column; border-top: 1px solid rgba(var(--v-border-color), 0.12); overflow: hidden; }
.console-response-empty { flex-shrink: 0; }
.response-scroll { flex: 1; overflow-y: auto; overflow-x: auto; }
.response-pre { margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 12px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace; }
.response-status-bar { flex-shrink: 0; }
.response-tabs { flex-shrink: 0; }
</style>
