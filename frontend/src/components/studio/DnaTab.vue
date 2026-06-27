<template>
  <div>
    <div v-if="dnaLoading" class="skeleton-grid">
      <div class="skeleton-card skeleton-chart"><div class="shimmer" /></div>
      <div class="skeleton-card skeleton-list"><div class="shimmer" /></div>
    </div>
    <v-alert v-if="dnaError" type="error" variant="tonal" class="mb-4" closable>{{ dnaError }}</v-alert>
    <div v-else-if="dnaEmpty" class="empty-state">
      <div class="empty-icon-wrap"><v-icon size="56" color="#a78bfa">mdi-dna</v-icon></div>
      <h3 class="empty-title">暂无喜欢歌曲数据</h3>
      <p class="empty-desc">收藏歌曲后解锁专属 DNA 谱图</p>
    </div>
    <template v-else>
      <div class="dna-layout">
        <div class="dna-left">
          <div class="glass-card chart-card">
            <div class="card-header">
              <v-icon size="18" color="#a78bfa">mdi-chart-bubble</v-icon>
              <span class="card-title">10维 DNA 雷达</span>
              <v-spacer />
              <template v-if="rebuildRunning">
                <span class="rebuild-progress-text">{{ rebuildProgress }}%</span>
                <v-progress-linear
                  :model-value="rebuildProgress" color="primary" height="3"
                  style="max-width:80px;margin:0 8px" rounded
                />
                <v-btn size="small" color="error" variant="tonal" title="终止重建" @click="cancelRebuild" class="rebuild-btn">
                  <v-icon size="18" left>mdi-stop</v-icon> 终止
                </v-btn>
              </template>
              <template v-else>
                <v-btn size="default" variant="tonal" color="primary" prepend-icon="mdi-refresh"
                  :loading="rebuildLoading" :disabled="rebuildLoading" @click="triggerRebuild" class="rebuild-btn">
                  从我喜欢生成
                </v-btn>
              </template>
            </div>
            <div v-if="rebuildRunning && rebuildMessage" class="rebuild-msg">{{ rebuildMessage }}</div>
            <div class="chart-wrap">
              <v-chart :option="radarOption" autoresize style="width:100%;height:100%" />
            </div>
            <div class="legend-row">
              <div
                v-for="d in dimensions" :key="d.key"
                class="legend-item"
                :class="{ 'legend-active': hoveredDim === d.key }"
                @mouseenter="hoveredDim = d.key"
                @mouseleave="hoveredDim = null"
              >
                <div class="legend-dot" :style="{ background: d.color, boxShadow: `0 0 8px ${d.color}60` }" />
                <div class="legend-text">
                  <span class="legend-label">{{ d.label.split('\n')[0] }}</span>
                  <span class="legend-value">{{ radarData[d.key] }}</span>
                </div>
                <div class="legend-bar" :style="{ width: radarData[d.key] + '%', background: d.color }" />
              </div>
            </div>
          </div>
        </div>
        <div class="dna-right">
          <div class="glass-card" style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:200px;gap:12px">
            <v-icon size="40" color="#f59e0b">mdi-fire</v-icon>
            <span style="font-size:0.9rem;color:var(--text-2);text-align:center">
              TOP 50 共鸣单曲已迁移至<br/>「发现音乐 → ⭐ TOP 50」
            </span>
            <v-btn size="small" variant="tonal" color="warning" prepend-icon="mdi-arrow-right" @click="$emit('goDiscoverTop50')">
              立即查看
            </v-btn>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
/* ================================================================
   DnaTab.vue — 「DNA谱图」Tab
   ================================================================
   自包含：数据加载、重建任务轮询、雷达图渲染
   通过 emit 通知父组件跳转到「发现音乐 → TOP 50」
================================================================ */
import { ref, reactive, computed, onBeforeUnmount, onMounted } from 'vue'
import { useTheme } from 'vuetify'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { createAuthAxios } from '@/api/authAxios.js'

const api = createAuthAxios()
use([CanvasRenderer, RadarChart, TooltipComponent, LegendComponent])
const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)

defineEmits(['goDiscoverTop50'])

// ── 数据状态 ──
const username = computed(() => localStorage.getItem('username') || 'admin')
const dnaLoading = ref(true)
const dnaError = ref('')
const dnaEmpty = ref(false)
const trackCount = ref(0)
const hoveredDim = ref(null)

// ── 重建状态 ──
const rebuildTaskId = ref('')
const rebuildProgress = ref(0)
const rebuildMessage = ref('')
const rebuildLoading = ref(false)
const rebuildRunning = computed(() => !!rebuildTaskId.value)
let _rebuildPollTimer = null

const radarData = reactive({
  tempo: 0, energy: 0, brightness: 0, contrast: 0,
  sub_bass: 0, vocal: 0, sentiment: 0,
  ambiance: 0, instrumental: 0, cultural: 0,
})

const dimensions = [
  { key: 'tempo', label: '速度律动\nTempo', color: '#f59e0b', source: 'librosa' },
  { key: 'energy', label: '能量爆发\nEnergy', color: '#ef4444', source: 'librosa' },
  { key: 'brightness', label: '音色明亮\nBrightness', color: '#06b6d4', source: 'librosa' },
  { key: 'contrast', label: '戏剧起伏\nContrast', color: '#8b5cf6', source: 'librosa' },
  { key: 'sub_bass', label: '低音轰炸\nSub Bass', color: '#ec4899', source: 'Demucs' },
  { key: 'vocal', label: '人声主导\nVocal', color: '#10b981', source: 'Demucs' },
  { key: 'sentiment', label: '情感色彩\nSentiment', color: '#f97316', source: 'SnowNLP' },
  { key: 'ambiance', label: '空间氛围\nAmbiance', color: '#14b8a6', source: 'PANNs' },
  { key: 'instrumental', label: '纯器乐倾向\nInstrumental', color: '#a78bfa', source: 'PANNs' },
  { key: 'cultural', label: '文化共鸣\nCultural', color: '#eab308', source: 'Ollama' },
]

const radarOption = computed(() => {
  const dark = isDark.value
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: dark ? 'rgba(24,24,32,0.95)' : 'rgba(255,255,255,0.95)',
      borderColor: 'rgba(139,92,246,0.35)', borderWidth: 1,
      textStyle: { color: dark ? '#e4e4e7' : '#1a1a2e', fontSize: 12 },
      formatter: (p) => {
        if (!p?.name) return ''
        const dim = dimensions.find(d => d.label.replace(/\n/g, '') === p.name.replace(/\n/g, ''))
        return `<div style="font-weight:700;margin-bottom:4px">🎵 ${p.name.replace(/\n/g, ' · ')}</div>
          <div style="color:#a78bfa">得分: <b>${p.value}</b> / 100</div>
          ${dim ? `<div style="color:${dark ? '#71717a' : '#888'};font-size:11px">引擎: ${dim.source}</div>` : ''}`
      },
    },
    radar: {
      shape: 'polygon', center: ['50%', '48%'], radius: '62%', splitNumber: 5,
      name: {
        textStyle: { color: dark ? '#a1a1aa' : '#6b6b7b', fontSize: 10, fontWeight: 500, lineHeight: 14, backgroundColor: dark ? 'rgba(24,24,30,0.85)' : 'rgba(255,255,255,0.85)', borderRadius: 4, padding: [1, 4] },
      },
      splitArea: { areaStyle: { color: dark ? ['rgba(139,92,246,0.03)', 'rgba(139,92,246,0.06)'] : ['rgba(139,92,246,0.04)', 'rgba(139,92,246,0.08)'] } },
      axisLine: { lineStyle: { color: dark ? 'rgba(139,92,246,0.2)' : 'rgba(139,92,246,0.25)', width: 1 } },
      splitLine: { lineStyle: { color: dark ? 'rgba(139,92,246,0.12)' : 'rgba(139,92,246,0.16)', width: 1, type: 'dashed' } },
      indicator: dimensions.map(d => ({ name: d.label, max: 100 })),
    },
    series: [{
      type: 'radar', symbol: 'circle', symbolSize: 6,
      lineStyle: { color: '#a78bfa', width: 2.5, shadowBlur: 10, shadowColor: 'rgba(167,139,250,0.4)' },
      itemStyle: { color: '#a78bfa', borderColor: dark ? '#fff' : '#333', borderWidth: 1.5 },
      emphasis: { lineStyle: { width: 3, shadowBlur: 16 }, areaStyle: { color: 'rgba(167,139,250,0.3)' } },
      areaStyle: {
        color: {
          type: 'radial', x: 0.5, y: 0.5, r: 0.5,
          colorStops: [
            { offset: 0, color: 'rgba(99,102,241,0.06)' },
            { offset: 0.4, color: 'rgba(139,92,246,0.15)' },
            { offset: 0.7, color: 'rgba(167,139,250,0.28)' },
            { offset: 1, color: 'rgba(139,92,246,0.45)' },
          ],
        },
      },
      data: [{ value: dimensions.map(d => radarData[d.key]), name: '你的口味 DNA' }],
    }],
  }
})

// ── API ──
async function loadDnaData() {
  dnaLoading.value = true; dnaError.value = ''
  try {
    const u = username.value
    const radarRes = await api.get(`/api/user/${u}/taste-radar`)
    const body = radarRes?.data
    if (body?.success && body.data?.radar) {
      const d = body.data
      dimensions.forEach((dim, i) => { radarData[dim.key] = d.radar[i] ?? 50 })
      trackCount.value = d.count ?? 0
      dnaEmpty.value = trackCount.value === 0
    }
  } catch (e) {
    dnaError.value = '加载失败：' + (e.message || '网络错误')
  } finally {
    dnaLoading.value = false
  }
  await _syncActiveRebuildTask()
}

async function _syncActiveRebuildTask() {
  if (rebuildTaskId.value) return
  try {
    const res = await api.get('/api/tasks?type=dna_rebuild&status=running&limit=1')
    const tasks = res?.data?.data || res?.data || []
    if (Array.isArray(tasks) && tasks.length > 0) {
      const task = tasks[0]
      rebuildTaskId.value = task.task_id
      rebuildProgress.value = task.progress || 0
      rebuildMessage.value = task.message || ''
      _startRebuildPolling()
    }
  } catch { /* 静默 */ }
}

async function triggerRebuild() {
  if (rebuildRunning.value || rebuildLoading.value) return
  rebuildLoading.value = true
  try {
    const res = await api.post(`/api/user/${username.value}/taste-rebuild`)
    const taskId = res.data?.data?.task_id || res.data?.task_id
    if (!taskId) { rebuildLoading.value = false; return window.__snackbar?.('启动重建失败', 'error') }
    rebuildTaskId.value = taskId; rebuildProgress.value = 0; rebuildMessage.value = '启动中...'
    rebuildLoading.value = false
    window.__snackbar?.('DNA 重建任务已启动', 'success')
    _startRebuildPolling()
  } catch (e) {
    rebuildLoading.value = false
    window.__snackbar?.('启动失败: ' + (e.message || '网络错误'), 'error')
  }
}

async function cancelRebuild() {
  if (!rebuildTaskId.value || rebuildLoading.value) return
  rebuildLoading.value = true
  try {
    await api.post(`/api/tasks/${rebuildTaskId.value}/cancel`)
    window.__snackbar?.('已发送终止信号', 'info')
  } catch (e) {
    window.__snackbar?.('终止失败: ' + (e.message || '网络错误'), 'error')
  } finally { rebuildLoading.value = false }
}

function _startRebuildPolling() {
  _stopRebuildPolling()
  _rebuildPollTimer = setInterval(async () => {
    try {
      const res = await api.get(`/api/tasks/${rebuildTaskId.value}`)
      const task = res.data?.data || res.data
      if (!task) return
      rebuildProgress.value = task.progress || 0
      rebuildMessage.value = task.message || ''
      if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
        _stopRebuildPolling()
        if (task.status === 'completed') {
          window.__snackbar?.('DNA 重建完成！刷新数据...', 'success')
          rebuildTaskId.value = ''; await loadDnaData()
        } else if (task.status === 'failed') {
          window.__snackbar?.('重建失败: ' + (task.error || task.message), 'error')
          rebuildTaskId.value = ''
        } else {
          window.__snackbar?.('任务已取消', 'warning')
          rebuildTaskId.value = ''
        }
      }
    } catch { /* 静默 */ }
  }, 2000)
}

function _stopRebuildPolling() {
  if (_rebuildPollTimer) { clearInterval(_rebuildPollTimer); _rebuildPollTimer = null }
}

onMounted(loadDnaData)
onBeforeUnmount(_stopRebuildPolling)
</script>

<style scoped>
/* ── 骨骼屏 ── */
.skeleton-grid { display: grid; grid-template-columns: 1fr 300px; gap: 20px; }
.skeleton-card {
  background: rgba(var(--v-theme-surface), 0.5); border-radius: var(--aero-radius, 20px);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06); overflow: hidden; position: relative;
}
.skeleton-chart { height: 440px; }
.skeleton-list { height: 220px; }
.shimmer {
  position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent 0%, rgba(var(--v-theme-on-surface), 0.04) 50%, transparent 100%);
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }

/* ── 空状态 ── */
.empty-state { text-align: center; padding: 48px 20px; }
.empty-icon-wrap { width: 80px; height: 80px; margin: 0 auto 16px; border-radius: 50%; background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.15); display: flex; align-items: center; justify-content: center; }
.empty-title { font-size: 1.1rem; font-weight: 700; color: var(--text-1); margin-bottom: 6px; }
.empty-desc { color: var(--text-2); font-size: 0.85rem; }

/* ── 布局 ── */
.dna-layout { display: grid; grid-template-columns: 1fr 300px; gap: 20px; align-items: start; }
.chart-card { padding: 20px 16px 12px; }
.chart-wrap { width: 100%; height: 400px; }

.legend-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.legend-item {
  flex: 1; min-width: 150px; position: relative;
  background: rgba(var(--v-theme-on-surface), 0.03); border-radius: 8px;
  padding: 6px 10px; border: 1px solid transparent; transition: all 0.2s; cursor: default;
}
.legend-item:hover, .legend-active { background: rgba(139,92,246,0.1); border-color: rgba(139,92,246,0.25); }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; vertical-align: middle; margin-right: 6px; }
.legend-text { display: inline-flex; align-items: baseline; gap: 6px; }
.legend-label { font-size: 0.72rem; color: var(--text-2); }
.legend-value { font-size: 0.78rem; font-weight: 700; color: var(--text-1); font-variant-numeric: tabular-nums; }
.legend-bar { height: 2px; border-radius: 2px; margin-top: 4px; transition: width 0.5s cubic-bezier(0.4,0,0.2,1); }

.rebuild-progress-text { font-size: 0.75rem; font-weight: 600; color: #a78bfa; min-width: 32px; text-align: right; }
.rebuild-msg { font-size: 0.7rem; color: var(--text-3); padding: 0 0 8px 26px; }
.rebuild-btn { font-size: 0.85rem !important; padding: 0 16px !important; min-height: 36px !important; }

@media (max-width: 860px) {
  .dna-layout, .skeleton-grid { grid-template-columns: 1fr; }
  .chart-wrap { height: 300px; }
}
</style>
