<template>
  <div class="radar-page">
    <div class="d-flex align-center mb-5">
      <v-icon size="32" color="primary" class="mr-3">mdi-dna</v-icon>
      <h1 class="text-h4 font-weight-bold">全景音乐DNA谱图</h1>
    </div>

    <!-- loading -->
    <div v-if="loading" class="text-center py-12">
      <v-progress-circular indeterminate color="primary" size="56"/>
      <p class="text-body-2 text-medium-emphasis mt-3">正在解析你的音乐 DNA...</p>
    </div>

    <!-- error -->
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>

    <!-- empty -->
    <div v-else-if="empty" class="text-center py-12">
      <v-icon size="64" class="mb-3" color="medium-emphasis">mdi-dna</v-icon>
      <p class="text-h6 mb-2">暂无喜欢歌曲数据</p>
      <p class="text-body-2 text-medium-emphasis mb-4">去"音乐搜索"给喜欢的歌曲点个收藏，解锁你的 DNA 谱图</p>
    </div>

    <!-- content -->
    <template v-else>
      <div class="radar-layout" ref="layoutRef">
        <!-- 左列：雷达图 + 标签聚焦 -->
        <div class="left-col">
          <!-- 雷达图卡片 -->
          <div class="card-dark pa-4">
            <div class="chart-wrap" ref="chartWrap">
              <v-chart :option="radarOption" autoresize style="width:100%;height:100%"/>
            </div>
            <!-- 十维图例 -->
            <div class="legend-row mt-3">
              <div v-for="d in dimensions" :key="d.key" class="legend-item">
                <div class="legend-dot" :style="{background:d.color}"/>
                <span class="text-caption">{{ d.label.split('\n')[0] }} {{ radarData[d.key] }}</span>
              </div>
            </div>
            <div class="text-caption text-medium-emphasis mt-2 text-center">
              基于 {{ trackCount }} 首喜欢歌曲 · 10维全景DNA谱图
            </div>
          </div>

          <!-- 标签聚焦歌单面板 -->
          <v-expand-transition>
            <div v-if="activeTag" class="card-dark pa-4">
              <div class="d-flex align-center mb-3">
                <v-chip size="small" :color="activeTag.category==='llm'?'info':'success'" variant="tonal" class="mr-2">{{ activeTag.category==='llm'?'意境':'音频' }}</v-chip>
                <span class="text-subtitle-2 font-weight-bold">{{ activeTag.tag_name }}</span>
                <v-spacer/>
                <v-btn icon="mdi-close" variant="text" size="small" @click="activeTag=null"/>
              </div>
              <div v-if="tagTrackLoading" class="text-center py-4">
                <v-progress-circular indeterminate size="24"/>
              </div>
              <div v-else-if="!tagTracks.length" class="text-caption text-medium-emphasis py-2">暂无关联歌曲</div>
              <div v-for="t in tagTracks" :key="t.track_id" class="tag-track-row d-flex align-center pa-2 rounded mb-1" role="button" @click="playTrack(t)">
                <v-icon size="18" class="mr-2" color="primary">mdi-play-circle-outline</v-icon>
                <div class="flex-1-1" style="min-width:0;">
                  <div class="text-body-2 text-truncate">{{ t.title }}</div>
                  <div class="text-caption text-medium-emphasis text-truncate">{{ t.artist }}</div>
                </div>
                <v-chip v-if="t.is_favorite" size="x-small" color="error" variant="tonal">喜欢</v-chip>
              </div>
            </div>
          </v-expand-transition>
        </div>

        <!-- 右列：双表格 -->
        <div class="tables-col">
          <!-- TOP 10 共鸣单曲 -->
          <div class="card-dark pa-4">
            <div class="text-subtitle-2 font-weight-bold mb-3">🔥 TOP 10 共鸣单曲</div>
            <div v-if="!topTracks.length" class="text-caption text-medium-emphasis py-2">暂无数据</div>
            <div v-for="t in topTracks" :key="t.rank" class="top-track-row d-flex align-center py-2" style="border-bottom:1px solid #27272a;">
              <div class="rank-circle mr-3" :class="t.rank<=3?'rank-top':''">{{ t.rank }}</div>
              <div class="flex-1-1" style="min-width:0;">
                <div class="text-body-2 text-truncate">{{ t.title }}</div>
                <div class="text-caption text-medium-emphasis text-truncate">{{ t.artist }}</div>
              </div>
              <span class="text-caption font-weight-bold" :class="t.resonance>=70?'text-success':t.resonance>=50?'text-warning':'text-medium-emphasis'">{{ t.resonance }}分</span>
            </div>
          </div>

          <!-- 高频 AI 标签 -->
          <div class="card-dark pa-4 mt-4">
            <div class="text-subtitle-2 font-weight-bold mb-3">🏷 高频 AI 标签</div>
            <div v-if="!topTags.length" class="text-caption text-medium-emphasis py-2">暂无数据</div>
            <div v-for="t in topTags" :key="t.tag_name" class="tag-row d-flex align-center py-2" :class="{'tag-active': activeTag?.tag_name===t.tag_name}" style="border-bottom:1px solid #27272a;cursor:pointer;" role="button" @click="toggleTag(t)">
              <div class="flex-1-1" style="min-width:0;">
                <span class="text-body-2 tag-name">{{ t.tag_name }}</span>
                <v-chip size="x-small" :color="t.category==='llm'?'info':'success'" variant="tonal" class="ml-2">{{ t.category==='llm'?'意境':'音频' }}</v-chip>
              </div>
              <div class="text-end">
                <div class="text-caption">🔥 {{ t.freq }} 次</div>
                <div class="text-caption text-medium-emphasis">{{ t.avg_confidence }}%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, shallowRef, onMounted, nextTick } from 'vue'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { createAuthAxios } from '@/api/authAxios.js'

// 使用独立 axios 实例（复用认证拦截器）
const api = createAuthAxios()

use([CanvasRenderer, RadarChart, TooltipComponent])

const username = computed(() => localStorage.getItem('username') || 'admin')
const loading = ref(true)
const error = ref('')
const empty = ref(false)
const trackCount = ref(0)
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

const radarOption = computed(() => ({
  tooltip: {},
  radar: {
    shape: 'circle',
    center: ['50%', '50%'],
    radius: '58%',
    splitNumber: 5,
    splitArea: { show: false },
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
    axisName: {
      color: '#a1a1aa',
      fontSize: 10,
      lineHeight: 14,
      backgroundColor: 'rgba(12,12,18,0.85)',
      borderRadius: 4,
      padding: [2, 4],
    },
    indicator: dimensions.map(d => ({
      name: d.label,
      max: 100,
    })),
  },
  series: [{
    type: 'radar',
    symbol: 'circle',
    symbolSize: 4,
    lineStyle: { color: '#6366f1', width: 2 },
    itemStyle: { color: '#6366f1' },
    areaStyle: {
      color: {
        type: 'radial',
        x: 0.5, y: 0.5, r: 0.5,
        colorStops: [
          { offset: 0, color: 'rgba(99,102,241,0.08)' },
          { offset: 0.5, color: 'rgba(99,102,241,0.2)' },
          { offset: 1, color: 'rgba(99,102,241,0.55)' },
        ],
      },
    },
    data: [{
      value: dimensions.map(d => radarData[d.key]),
      name: '你的口味',
    }],
  }],
}))

const topTracks = ref([])
const topTags = ref([])
const activeTag = ref(null)
const tagTracks = ref([])
const tagTrackLoading = ref(false)

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const u = username.value
    const [radarRes, tracksRes, tagsRes] = await Promise.allSettled([
      api.get(`/api/user/${u}/taste-radar`),
      api.get(`/api/user/${u}/taste-top-tracks`),
      api.get(`/api/user/${u}/taste-top-tags`),
    ])

    // Radar
    if (radarRes.status === 'fulfilled') {
      const body = radarRes.value?.data
      if (body?.success && body.data?.radar) {
        const d = body.data
        dimensions.forEach((dim, i) => { radarData[dim.key] = d.radar[i] ?? 50 })
        trackCount.value = d.count ?? 0
        empty.value = trackCount.value === 0
      }
    }

    // TOP tracks
    if (tracksRes.status === 'fulfilled') {
      const body = tracksRes.value?.data
      topTracks.value = (body?.success && body.data) ? body.data : []
    }

    // TOP tags
    if (tagsRes.status === 'fulfilled') {
      const body = tagsRes.value?.data
      topTags.value = (body?.success && body.data) ? body.data : []
    }
  } catch (e) {
    error.value = '加载失败：' + (e.message || '网络错误')
  } finally {
    loading.value = false
  }
}

async function toggleTag(tag) {
  if (activeTag.value?.tag_name === tag.tag_name) {
    activeTag.value = null
    return
  }
  activeTag.value = tag
  tagTrackLoading.value = true
  try {
    const u = username.value
    const res = await api.get(`/api/tags/${encodeURIComponent(tag.tag_name)}/tracks`)
    const body = res?.data
    tagTracks.value = (body?.success && body.data) ? body.data : []
  } catch {
    tagTracks.value = []
  } finally {
    tagTrackLoading.value = false
  }
}

function playTrack(track) {
  if (!track?.file_path) {
    window.__snackbar?.('无法获取文件路径', 'warning')
    return
  }
  const fn = track.file_path.split('/').pop()?.split('\\').pop()
  if (!fn) {
    window.__snackbar?.('无法解析文件名', 'warning')
    return
  }
  if (window.__playAudio) {
    window.__playAudio(fn)
  } else {
    window.__snackbar?.('音频播放器未就绪', 'warning')
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.radar-page { color: #e4e4e7; }
.card-dark {
  background: #18181b;
  border: 1px solid #27272a;
  border-radius: 12px;
}
.chart-wrap { width: 100%; height: 440px; }
.radar-layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 16px;
  align-items: start;
}
.left-col { display: flex; flex-direction: column; gap: 16px; }
.tables-col { display: flex; flex-direction: column; gap: 0; }

.legend-row { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; }
.legend-item { display: flex; align-items: center; gap: 4px; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; }

.rank-circle {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: #27272a; color: #a1a1aa; font-size: 12px; font-weight: 700;
  flex-shrink: 0;
}
.rank-circle.rank-top { background: linear-gradient(135deg, #6366f1, #ec4899); color: #fff; }

.tag-name:hover { color: #818cf8; }
.tag-row:hover { background: rgba(39,39,42,0.5); }
.tag-active { background: rgba(99,102,241,0.12) !important; }
.tag-track-row { cursor: pointer; transition: background .15s; }
.tag-track-row:hover { background: rgba(39,39,42,0.6); }

@media (max-width: 860px) {
  .radar-layout { grid-template-columns: 1fr; }
  .chart-wrap { height: 320px; }
}
</style>
