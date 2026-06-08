<template>
  <div>
    <div class="d-flex align-center mb-5">
      <v-icon size="32" color="primary" class="mr-3">mdi-text-box-outline</v-icon>
      <h2 class="text-h4 font-weight-bold">运行日志</h2>
    </div>

    <v-card class="mb-4" variant="flat" color="surface-variant">
      <v-card-text class="d-flex align-center flex-wrap ga-3 py-3">
        <div class="d-flex align-center">
          <div class="status-dot mr-2" :class="isPaused ? 'paused' : 'live'" />
          <span class="text-body-2 text-medium-emphasis">{{ isPaused ? '已暂停' : '实时监控中 (3s)' }}</span>
        </div>

        <v-select
          v-model="selectedFile"
          :items="logFiles"
          hide-details
          style="min-width:220px;max-width:300px;"
          placeholder="选择日志文件"
        />

        <v-btn :prepend-icon="isPaused ? 'mdi-play' : 'mdi-pause'" variant="tonal" @click="togglePause">
          {{ isPaused ? '恢复' : '暂停' }}
        </v-btn>
        <v-btn prepend-icon="mdi-refresh" variant="tonal" @click="fetchLogs">刷新</v-btn>
        <v-btn color="error" variant="tonal" prepend-icon="mdi-delete-sweep" :loading="cleaning" @click="handleCleanup">清空日志</v-btn>

        <v-spacer />
        <v-chip size="small" variant="tonal" color="medium-emphasis">{{ lineCountText }}</v-chip>
      </v-card-text>
    </v-card>

    <v-card class="log-container">
      <div class="log-header d-flex align-center justify-space-between pa-3 px-5">
        <span class="text-body-2 font-weight-bold text-white">{{ currentFileName }}</span>
        <span class="text-caption" style="color:#64748b;">倒序排列 · 最近 1000 条</span>
      </div>
      <div class="log-lines" ref="logContainer">
        <div v-if="lines.length === 0" class="text-center py-12" style="color:#94a3b8;">
          <v-icon size="48" class="mb-3" color="grey">mdi-text-box-outline</v-icon>
          <p>{{ logError || '暂无日志内容' }}</p>
        </div>
        <div v-for="(line, i) in lines" :key="i" class="log-line">
          <span class="line-number">{{ line._idx }}</span>
          <span :class="logLevelClass(line.text)">{{ line.text }}</span>
        </div>
      </div>
    </v-card>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { getLogs, cleanupLogs } from '@/api/index.js'

const lines = ref([])
const logFiles = ref([])
const selectedFile = ref('')
const currentFileName = ref('--')
const lineCountText = ref('--')
const isPaused = ref(false)
const cleaning = ref(false)
const logError = ref('')
const logContainer = ref(null)
let timer = null

function logLevelClass(text) {
  if (/ERROR|error/.test(text)) return 'lvl-error'
  if (/WARNING|warning/.test(text)) return 'lvl-warning'
  if (/DEBUG/.test(text)) return 'lvl-debug'
  if (/INFO/.test(text)) return 'lvl-info'
  return ''
}

async function fetchLogs() {
  try {
    const params = { limit: 1000 }
    if (selectedFile.value) params.file = selectedFile.value
    const res = await getLogs(params)
    if (res && res.success && res.data) {
      const data = res.data
      logFiles.value = data.files || []
      currentFileName.value = data.current_file || '--'

      const rawLines = data.lines || []
      lines.value = rawLines.map((text, i) => ({ text, _idx: rawLines.length - i }))
      lineCountText.value = `显示 ${rawLines.length} / 共 ${data.total_lines} 行`
      logError.value = ''
    }
  } catch (e) {
    logError.value = '获取日志失败，请检查服务运行状态'
  }
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = 0
  }
}

function togglePause() {
  isPaused.value = !isPaused.value
  if (isPaused.value) {
    if (timer) { clearInterval(timer); timer = null }
  } else {
    timer = setInterval(fetchLogs, 3000)
  }
}

async function handleCleanup() {
  if (!confirm('确定要清空所有日志文件吗？此操作不可恢复。')) return
  cleaning.value = true
  try {
    const res = await cleanupLogs()
    if (res && res.success) {
      const cleaned = res.data?.cleaned || []
      window.__snackbar?.(`已清空 ${cleaned.length} 个日志文件`, 'success')
      await fetchLogs()
    }
  } catch (e) {
    window.__snackbar?.('清理日志失败', 'error')
  } finally {
    cleaning.value = false
  }
}

watch(selectedFile, () => { fetchLogs() })

onMounted(() => {
  fetchLogs()
  timer = setInterval(fetchLogs, 3000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.status-dot {
  width: 8px; height: 8px; border-radius: 50%; display: inline-block;
}
.status-dot.live { background: #22c55e; animation: pulse 2s infinite; }
.status-dot.paused { background: #f59e0b; }
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.4;} }

.log-container { background: #1e293b; border-radius: 12px; overflow: hidden; }
.log-lines {
  max-height: 70vh; overflow-y: auto; padding: 0;
  font-family: 'SF Mono','Fira Code','Consolas','Microsoft YaHei',monospace;
  font-size: 13px; line-height: 1.5; color: #e2e8f0;
  counter-reset: log-line;
}
.log-line {
  padding: 2px 16px 2px 60px; position: relative;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  white-space: pre-wrap; word-break: break-all;
}
.log-line:hover { background: rgba(255,255,255,0.04); }
.line-number {
  position: absolute; left: 12px; width: 40px; text-align: right;
  color: #475569; font-size: 11px; user-select: none;
}
.lvl-error { color: #f87171; font-weight: 600; }
.lvl-warning { color: #fbbf24; }
.lvl-info { color: #60a5fa; }
.lvl-debug { color: #a78bfa; }
.empty-state { color: #94a3b8; }
</style>
