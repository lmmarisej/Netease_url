
<template>
  <div>
    <div class="d-flex align-center mb-6">
      <v-icon size="32" color="primary" class="mr-3">mdi-chart-bar</v-icon>
      <h2 class="text-h4 font-weight-bold">任务监控</h2>
    </div>

    <v-card class="mb-6" variant="flat" color="surface-variant">
      <v-card-text class="d-flex align-center flex-wrap ga-4 py-3">
        <div class="d-flex align-center">
          <div class="status-dot live mr-2" />
          <span class="text-body-2 text-medium-emphasis">自动刷新 (3s)</span>
        </div>

        <v-btn-toggle v-model="currentFilter" mandatory density="compact" variant="outlined" divided color="primary">
          <v-btn value="">全部</v-btn>
          <v-btn value="running">执行中</v-btn>
          <v-btn value="completed">已完成</v-btn>
          <v-btn value="failed">失败</v-btn>
        </v-btn-toggle>

        <v-spacer />

        <v-btn color="error" variant="tonal" prepend-icon="mdi-delete-sweep" :loading="clearing" @click="handleClearTasks">
          清理已完成
        </v-btn>
      </v-card-text>
    </v-card>

    <div v-if="tasks.length === 0" class="text-center text-medium-emphasis py-12">
      <v-icon size="64" class="mb-4" color="medium-emphasis">mdi-chart-bar</v-icon>
      <p class="text-body-1">暂无任务记录</p>
      <p class="text-body-2">下载音乐后任务记录会出现在这里</p>
    </div>

    <v-card v-for="task in tasks" :key="task.task_id" class="mb-3">
      <v-card-text class="d-flex align-center ga-4 py-3">
        <v-avatar :color="statusColor(task.status)" size="44" class="flex-shrink-0">
          <v-icon color="white">{{ statusIcon(task.status) }}</v-icon>
        </v-avatar>

        <div class="flex-1-1" style="min-width:0;">
          <div class="text-body-1 font-weight-bold text-truncate">{{ task.name }}</div>
          <div class="text-body-2 text-medium-emphasis">
            <template v-if="task.extra">
              {{ [task.extra.artist, task.extra.album, task.extra.quality].filter(Boolean).join(' · ') }}
              <span v-if="task.created_at"> | {{ formatTime(task.created_at) }}</span>
            </template>
            <template v-else-if="task.created_at">
              {{ formatTime(task.created_at) }}
            </template>
          </div>
          <div v-if="task.error" class="text-body-2 text-error mt-1">错误: {{ task.error }}</div>
          <div v-if="task.message" class="text-body-2 text-medium-emphasis">{{ task.message }}</div>
        </div>

        <div v-if="task.status === 'running'" class="flex-shrink-0" style="width:90px;">
          <v-progress-linear :model-value="task.progress || 0" color="primary" height="6" rounded striped />
          <div class="text-caption text-center text-medium-emphasis mt-1">{{ task.progress || 0 }}%</div>
        </div>

        <v-chip :color="statusColor(task.status)" size="small" variant="tonal" class="flex-shrink-0">
          {{ statusLabel(task.status) }}
        </v-chip>

        <v-btn icon="mdi-close" size="small" variant="text" color="medium-emphasis" @click="handleDeleteTask(task.task_id)" />
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { getTasks, clearTasks, deleteTask } from '@/api/index.js'

const tasks = ref([])
const currentFilter = ref('')
const clearing = ref(false)
let timer = null

const statusIcon = (s) => {
  const map = { pending: 'mdi-clock-outline', running: 'mdi-loading mdi-spin', completed: 'mdi-check-circle', failed: 'mdi-alert-circle', cancelled: 'mdi-cancel' }
  return map[s] || 'mdi-help-circle'
}
const statusColor = (s) => {
  const map = { pending: 'warning', running: 'primary', completed: 'success', failed: 'error', cancelled: 'grey' }
  return map[s] || 'grey'
}
const statusLabel = (s) => {
  const map = { pending: '等待', running: '执行中', completed: '完成', failed: '失败', cancelled: '取消' }
  return map[s] || s
}

function formatTime(ts) { return new Date(ts * 1000).toLocaleString('zh-CN') }

async function fetchTasks() {
  try {
    const params = { limit: 50 }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await getTasks(params)
    if (res?.success) tasks.value = res.data || []
  } catch (e) { /* ignore */ }
}

async function handleDeleteTask(taskId) {
  try { await deleteTask(taskId); await fetchTasks() } catch (e) { /* ignore */ }
}

async function handleClearTasks() {
  if (!confirm('确定要清理所有已完成/失败的任务记录吗？')) return
  clearing.value = true
  try { await clearTasks(); await fetchTasks() } finally { clearing.value = false }
}

watch(currentFilter, () => { fetchTasks() })

onMounted(() => { fetchTasks(); timer = setInterval(fetchTasks, 3000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.status-dot.live { background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.4;} }
.flex-1-1 { flex: 1 1 0; }
</style>
