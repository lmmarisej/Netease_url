<template>
  <div class="radar-page">
    <div class="page-header">
      <div class="header-icon">
        <v-icon size="28" color="#a78bfa">mdi-dna</v-icon>
      </div>
      <div>
        <h1 class="page-title">全景音乐DNA谱图</h1>
        <p class="page-subtitle" v-if="!loading && !empty">基于 {{ trackCount }} 首喜欢的歌曲 * 10维声学与文化分析</p>
      </div>
    </div>
    <div v-if="loading" class="skeleton-grid">
      <div class="skeleton-card skeleton-chart"><div class="shimmer"/></div>
      <div class="skeleton-card skeleton-list"><div class="shimmer"/></div>
      <div class="skeleton-card skeleton-list"><div class="shimmer"/></div>
    </div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4" closable>{{ error }}</v-alert>
    <div v-else-if="empty" class="empty-state">
      <div class="empty-icon-wrap"><v-icon size="72" color="#a78bfa">mdi-dna</v-icon></div>
      <h2 class="empty-title">暂无喜欢歌曲数据</h2>
      <p class="empty-desc">去「音乐搜索」给喜欢的歌曲点个收藏<br/>解锁你的专属 DNA 谱图</p>
      <v-btn color="primary" variant="outlined" prepend-icon="mdi-magnify" to="/search">去发现音乐</v-btn>
    </div>
    <template v-else>
      <div class="radar-layout">
        <div class="left-col">
          <div class="glass-card chart-card">
            <div class="card-header">
              <v-icon size="20" color="#a78bfa">mdi-chart-bubble</v-icon>
              <span class="card-title">10维 DNA 雷达</span>
              <v-spacer/>
              <span class="card-badge">实时分析</span>
            </div>
            <div class="chart-wrap">
              <v-chart :option="radarOption" autoresize style="width:100%;height:100%"/>
            </div>
            <div class="legend-row">
              <div
                v-for="d in dimensions" :key="d.key"
                class="legend-item"
                :class="{ 'legend-active': hoveredDim === d.key }"
                @mouseenter="hoveredDim = d.key"
                @mouseleave="hoveredDim = null"
              >
                <div class="legend-dot" :style="{ background: d.color, boxShadow: `0 0 8px ${d.color}60` }"/>
                <div class="legend-text">
                  <span class="legend-label">{{ d.label.split('\n')[0] }}</span>
                  <span class="legend-value">{{ radarData[d.key] }}</span>
                </div>
                <div class="legend-bar" :style="{ width: radarData[d.key] + '%', background: d.color }"/>
              </div>
            </div>
          </div>
        </div>
        <div class="right-col">
          <div class="glass-card">
            <div class="card-header">
              <v-icon size="20" color="#f59e0b">mdi-fire</v-icon>
              <span class="card-title">TOP 10 共鸣单曲</span>
              <v-spacer/>
              <span class="card-badge accent">{{ topTracks.length }} 首</span>
            </div>
            <div v-if="!topTracks.length" class="card-empty">暂无数据</div>
            <TransitionGroup name="track-list" tag="div" class="track-list">
              <div v-for="t in topTracks" :key="t.rank" class="track-row">
                <div class="rank-badge" :class="t.rank <= 3 ? 'rank-gold' : ''">
                  <template v-if="t.rank === 1">🥇</template>
                  <template v-else-if="t.rank === 2">🥈</template>
                  <template v-else-if="t.rank === 3">🥉</template>
                  <template v-else>{{ t.rank }}</template>
                </div>
                <div class="track-info">
                  <div class="track-title">{{ t.title }}</div>
                  <div class="track-artist">{{ t.artist }}</div>
                </div>
                <div class="track-score" :class="scoreClass(t.resonance)">
                  <span class="score-value">{{ t.resonance }}</span>
                  <span class="score-unit">分</span>
                </div>
              </div>
            </TransitionGroup>
          </div>
          <div class="glass-card">
            <div class="card-header">
              <v-icon size="20" color="#06b6d4">mdi-tag-multiple</v-icon>
              <span class="card-title">高频 AI 标签</span>
              <v-spacer/>
              <span class="card-badge info">{{ topTags.length }} 项</span>
            </div>
            <div v-if="!topTags.length" class="card-empty">暂无数据</div>
            <TransitionGroup name="tag-list" tag="div" class="tag-list">
              <div
                v-for="t in topTags" :key="t.tag_name"
                class="tag-row"
                :class="{ 'tag-row--active': activeTag?.tag_name === t.tag_name }"
                role="button" tabindex="0"
                @click="toggleTag(t)" @keydown.enter="toggleTag(t)"
              >
                <div class="tag-main">
                  <span class="tag-name">{{ t.tag_name }}</span>
                  <v-chip size="x-small" :color="t.category === 'llm' ? 'deep-purple-lighten-1' : 'teal-lighten-1'" variant="tonal" class="tag-chip">
                    {{ t.category === 'llm' ? '意境' : '音频' }}
                  </v-chip>
                </div>
                <div class="tag-stats">
                  <span class="tag-freq">🔥 {{ t.freq }}</span>
                  <span class="tag-conf">{{ t.avg_confidence }}%</span>
                </div>
              </div>
            </TransitionGroup>
          </div>
          <Transition name="panel-slide">
            <div v-if="activeTag" class="glass-card tag-panel">
              <div class="card-header">
                <v-icon size="18" :color="activeTag.category === 'llm' ? '#b39ddb' : '#80cbc4'">
                  {{ activeTag.category === 'llm' ? 'mdi-brain' : 'mdi-waveform' }}
                </v-icon>
                <span class="card-title">{{ activeTag.tag_name }}</span>
                <v-spacer/>
                <v-btn icon="mdi-close" variant="text" size="x-small" density="compact" @click="activeTag = null"/>
              </div>
              <div v-if="tagTrackLoading" class="panel-loading">
                <v-progress-circular indeterminate size="20" width="2" color="primary"/>
                <span>加载关联歌曲...</span>
              </div>
              <div v-else-if="!tagTracks.length" class="card-empty">暂无关联歌曲</div>
              <TransitionGroup v-else name="track-list" tag="div" class="tag-track-list">
                <div
                  v-for="t in tagTracks" :key="t.track_id"
                  class="tag-track-row" role="button" tabindex="0"
                  @click="playTrack(t)" @keydown.enter="playTrack(t)"
                >
                  <v-icon size="16" color="#a78bfa" class="mr-2">mdi-play-circle-outline</v-icon>
                  <div style="min-width:0;flex:1;">
                    <div class="text-truncate text-body-2">{{ t.title }}</div>
                    <div class="text-truncate text-caption text-medium-emphasis">{{ t.artist }}</div>
                  </div>
                  <v-chip v-if="t.is_favorite" size="x-small" color="pink-lighten-1" variant="tonal" class="ml-2">❤</v-chip>
                </div>
              </TransitionGroup>
            </div>
          </Transition>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue"
import { useTheme } from "vuetify"
import { use } from "echarts/core"
import { RadarChart } from "echarts/charts"
import { TooltipComponent, LegendComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
import VChart from "vue-echarts"
import { createAuthAxios } from "@/api/authAxios.js"

const api = createAuthAxios()
use([CanvasRenderer, RadarChart, TooltipComponent, LegendComponent])

const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)

const username = computed(() => localStorage.getItem("username") || "admin")
const loading = ref(true)
const error = ref("")
const empty = ref(false)
const trackCount = ref(0)
const hoveredDim = ref(null)

const radarData = reactive({
  tempo: 0, energy: 0, brightness: 0, contrast: 0,
  sub_bass: 0, vocal: 0, sentiment: 0,
  ambiance: 0, instrumental: 0, cultural: 0,
})

const dimensions = [
  { key: "tempo", label: "速度律动\nTempo", color: "#f59e0b", source: "librosa" },
  { key: "energy", label: "能量爆发\nEnergy", color: "#ef4444", source: "librosa" },
  { key: "brightness", label: "音色明亮\nBrightness", color: "#06b6d4", source: "librosa" },
  { key: "contrast", label: "戏剧起伏\nContrast", color: "#8b5cf6", source: "librosa" },
  { key: "sub_bass", label: "低音轰炸\nSub Bass", color: "#ec4899", source: "Demucs" },
  { key: "vocal", label: "人声主导\nVocal", color: "#10b981", source: "Demucs" },
  { key: "sentiment", label: "情感色彩\nSentiment", color: "#f97316", source: "SnowNLP" },
  { key: "ambiance", label: "空间氛围\nAmbiance", color: "#14b8a6", source: "PANNs" },
  { key: "instrumental", label: "纯器乐倾向\nInstrumental", color: "#a78bfa", source: "PANNs" },
  { key: "cultural", label: "文化共鸣\nCultural", color: "#eab308", source: "Ollama" },
]

const radarOption = computed(() => {
  const dark = isDark.value
  const axisColor = dark ? "rgba(139,92,246,0.2)" : "rgba(139,92,246,0.25)"
  const splitColor = dark ? "rgba(139,92,246,0.12)" : "rgba(139,92,246,0.16)"
  const labelColor = dark ? "#a1a1aa" : "#6b6b7b"
  const labelBg = dark ? "rgba(24,24,30,0.85)" : "rgba(255,255,255,0.85)"
  const tooltipBg = dark ? "rgba(24,24,32,0.95)" : "rgba(255,255,255,0.95)"
  const tooltipText = dark ? "#e4e4e7" : "#1a1a2e"
  const tooltipBorder = dark ? "rgba(139,92,246,0.3)" : "rgba(139,92,246,0.4)"
  const splitAreaColors = dark
    ? ["rgba(139,92,246,0.03)", "rgba(139,92,246,0.06)"]
    : ["rgba(139,92,246,0.04)", "rgba(139,92,246,0.08)"]

  return {
  tooltip: {
    trigger: "item",
    backgroundColor: tooltipBg,
    borderColor: tooltipBorder,
    borderWidth: 1,
    textStyle: { color: tooltipText, fontSize: 12 },
    formatter: (p) => {
      if (!p || !p.name) return ""
      const dim = dimensions.find(d => d.label.replace(/\n/g, "") === p.name.replace(/\n/g, ""))
      return `<div style="font-weight:700;margin-bottom:4px;">🎵 ${p.name.replace(/\n/g, " · ")}</div>
        <div style="color:#a78bfa;">得分: <b>${p.value}</b> / 100</div>
        ${dim ? `<div style="color:${dark ? '#71717a' : '#888'};font-size:11px;">引擎: ${dim.source}</div>` : ""}`
    },
  },
  radar: {
    shape: "polygon",
    center: ["50%", "48%"],
    radius: "62%",
    splitNumber: 5,
    name: {
      textStyle: {
        color: labelColor, fontSize: 10, fontWeight: 500, lineHeight: 14,
        backgroundColor: labelBg, borderRadius: 4, padding: [1, 4],
      },
    },
    splitArea: { areaStyle: { color: splitAreaColors } },
    axisLine: { lineStyle: { color: axisColor, width: 1 } },
    splitLine: { lineStyle: { color: splitColor, width: 1, type: "dashed" } },
    indicator: dimensions.map(d => ({ name: d.label, max: 100 })),
  },
  series: [{
    type: "radar",
    symbol: "circle", symbolSize: 6,
    lineStyle: { color: "#a78bfa", width: 2.5, shadowBlur: 10, shadowColor: "rgba(167,139,250,0.4)" },
    itemStyle: { color: "#a78bfa", borderColor: dark ? "#fff" : "#333", borderWidth: 1.5 },
    emphasis: {
      lineStyle: { width: 3, shadowBlur: 16, shadowColor: "rgba(167,139,250,0.6)" },
      areaStyle: { color: "rgba(167,139,250,0.3)" },
    },
    areaStyle: {
      color: {
        type: "radial", x: 0.5, y: 0.5, r: 0.5,
        colorStops: [
          { offset: 0, color: "rgba(99,102,241,0.06)" },
          { offset: 0.4, color: "rgba(139,92,246,0.15)" },
          { offset: 0.7, color: "rgba(167,139,250,0.28)" },
          { offset: 1, color: "rgba(139,92,246,0.45)" },
        ],
      },
    },
    data: [{ value: dimensions.map(d => radarData[d.key]), name: "你的口味 DNA" }],
  }],
}})

const topTracks = ref([])
const topTags = ref([])
const activeTag = ref(null)
const tagTracks = ref([])
const tagTrackLoading = ref(false)

function scoreClass(val) {
  if (val >= 70) return "score-high"
  if (val >= 50) return "score-mid"
  return "score-low"
}

async function loadData() {
  loading.value = true; error.value = ""
  try {
    const u = username.value
    const [radarRes, tracksRes, tagsRes] = await Promise.allSettled([
      api.get(`/api/user/${u}/taste-radar`),
      api.get(`/api/user/${u}/taste-top-tracks`),
      api.get(`/api/user/${u}/taste-top-tags`),
    ])
    if (radarRes.status === "fulfilled") {
      const body = radarRes.value?.data
      if (body?.success && body.data?.radar) {
        const d = body.data
        dimensions.forEach((dim, i) => { radarData[dim.key] = d.radar[i] ?? 50 })
        trackCount.value = d.count ?? 0
        empty.value = trackCount.value === 0
      }
    }
    if (tracksRes.status === "fulfilled") {
      const body = tracksRes.value?.data
      topTracks.value = (body?.success && body.data) ? body.data : []
    }
    if (tagsRes.status === "fulfilled") {
      const body = tagsRes.value?.data
      topTags.value = (body?.success && body.data) ? body.data : []
    }
  } catch (e) {
    error.value = "加载失败：" + (e.message || "网络错误")
  } finally {
    loading.value = false
  }
}

async function toggleTag(tag) {
  if (activeTag.value?.tag_name === tag.tag_name) { activeTag.value = null; return }
  activeTag.value = tag; tagTrackLoading.value = true
  try {
    const res = await api.get(`/api/tags/${encodeURIComponent(tag.tag_name)}/tracks`)
    const body = res?.data
    tagTracks.value = (body?.success && body.data) ? body.data : []
  } catch { tagTracks.value = [] }
  finally { tagTrackLoading.value = false }
}

function playTrack(track) {
  if (!track?.file_path) { window.__snackbar?.("无法获取文件路径", "warning"); return }
  const fn = track.file_path.split("/").pop()?.split("\\").pop()
  if (!fn) { window.__snackbar?.("无法解析文件名", "warning"); return }
  if (window.__playAudio) window.__playAudio(fn)
  else window.__snackbar?.("音频播放器未就绪", "warning")
}

onMounted(() => loadData())
</script>

<style scoped>
.radar-page {
  --glass-bg: rgba(var(--v-theme-surface), 0.72);
  --glass-border: rgba(var(--v-theme-on-surface), 0.08);
  --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.08), 0 1px 4px rgba(0, 0, 0, 0.04);
  --radius-lg: 16px;
  --text-primary: rgb(var(--v-theme-on-surface));
  --text-secondary: rgba(var(--v-theme-on-surface), 0.6);
  --text-tertiary: rgba(var(--v-theme-on-surface), 0.42);
  --accent-purple: #8b5cf6;
  --accent-gold: #f59e0b;
  color: var(--text-primary);
  padding: 0 4px;
  position: relative;
}

/* 页面背景微光渐变 — 打破灰蒙感 */
.radar-page::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background:
    radial-gradient(ellipse 80% 60% at 20% 20%, rgba(139, 92, 246, 0.06) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 75% 50%, rgba(6, 182, 212, 0.04) 0%, transparent 60%),
    radial-gradient(ellipse 50% 40% at 50% 85%, rgba(245, 158, 11, 0.03) 0%, transparent 60%);
}

.page-header { display: flex; align-items: center; gap: 14px; margin-bottom: 24px; }
.header-icon {
  width: 48px; height: 48px; border-radius: 14px;
  background: linear-gradient(135deg, rgba(139,92,246,0.25), rgba(167,139,250,0.12));
  border: 1px solid rgba(139,92,246,0.3);
  display: flex; align-items: center; justify-content: center;
}
.page-title {
  font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em;
  background: linear-gradient(135deg, var(--text-primary), #a78bfa);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.page-subtitle { color: var(--text-secondary); font-size: 0.85rem; margin-top: 2px; }

.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--glass-shadow);
  padding: 16px;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.glass-card:hover {
  border-color: rgba(139,92,246,0.2);
  box-shadow: 0 8px 32px rgba(0,0,0,0.1), 0 0 0 1px rgba(139,92,246,0.1);
}

.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.card-title { font-weight: 700; font-size: 0.95rem; color: var(--text-primary); }
.card-badge {
  font-size: 0.7rem; font-weight: 600; padding: 2px 10px; border-radius: 20px;
  background: rgba(139,92,246,0.15); color: #a78bfa; border: 1px solid rgba(139,92,246,0.25);
}
.card-badge.accent { background: rgba(245,158,11,0.12); color: #fbbf24; border-color: rgba(245,158,11,0.25); }
.card-badge.info { background: rgba(6,182,212,0.12); color: #22d3ee; border-color: rgba(6,182,212,0.25); }
.card-empty { color: var(--text-tertiary); text-align: center; padding: 24px 0; font-size: 0.85rem; }

.radar-layout { display: grid; grid-template-columns: 1fr 340px; gap: 20px; align-items: start; }
.left-col { display: flex; flex-direction: column; }
.right-col { display: flex; flex-direction: column; gap: 16px; }

.skeleton-grid { display: grid; grid-template-columns: 1fr 340px; gap: 20px; }
.skeleton-card {
  background: rgba(var(--v-theme-surface), 0.5); border-radius: var(--radius-lg);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06); overflow: hidden; position: relative;
}
.skeleton-chart { height: 460px; }
.skeleton-list { height: 200px; }
.shimmer {
  position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent 0%, rgba(var(--v-theme-on-surface), 0.04) 50%, transparent 100%);
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }

.empty-state { text-align: center; padding: 60px 20px; }
.empty-icon-wrap {
  width: 100px; height: 100px; margin: 0 auto 20px; border-radius: 50%;
  background: linear-gradient(135deg, rgba(139,92,246,0.12), rgba(167,139,250,0.06));
  border: 1px solid rgba(139,92,246,0.15);
  display: flex; align-items: center; justify-content: center;
}
.empty-title { font-size: 1.2rem; font-weight: 700; color: var(--text-primary); margin-bottom: 8px; }
.empty-desc { color: var(--text-secondary); font-size: 0.9rem; line-height: 1.6; margin-bottom: 20px; }

.chart-card { padding: 20px 16px 12px; }
.chart-wrap { width: 100%; height: 420px; }

.legend-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.legend-item {
  flex: 1; min-width: 160px; position: relative;
  background: rgba(var(--v-theme-on-surface), 0.03); border-radius: 8px;
  padding: 6px 10px; border: 1px solid transparent;
  transition: background 0.2s, border-color 0.2s; cursor: default;
}
.legend-item:hover, .legend-active {
  background: rgba(139,92,246,0.1); border-color: rgba(139,92,246,0.25);
}
.legend-dot {
  width: 8px; height: 8px; border-radius: 50%;
  display: inline-block; vertical-align: middle; margin-right: 6px;
}
.legend-text { display: inline-flex; align-items: baseline; gap: 6px; }
.legend-label { font-size: 0.75rem; color: var(--text-secondary); }
.legend-value { font-size: 0.8rem; font-weight: 700; color: var(--text-primary); font-variant-numeric: tabular-nums; }
.legend-bar {
  height: 2px; border-radius: 2px; margin-top: 4px;
  transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.track-list { max-height: 440px; overflow-y: auto; }
.track-row {
  display: flex; align-items: center; gap: 12px; padding: 10px 8px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.05);
  transition: background 0.15s;
}
.track-row:hover { background: rgba(var(--v-theme-on-surface), 0.04); }
.rank-badge {
  width: 30px; height: 30px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(var(--v-theme-on-surface), 0.08); color: var(--text-secondary);
  font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.rank-badge.rank-gold {
  background: linear-gradient(135deg, #f59e0b, #f97316); color: #fff;
  box-shadow: 0 2px 8px rgba(245,158,11,0.3);
}
.track-info { flex: 1; min-width: 0; }
.track-title { font-size: 0.85rem; font-weight: 600; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.track-artist { font-size: 0.75rem; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.track-score { text-align: center; flex-shrink: 0; min-width: 42px; }
.score-value { font-size: 1rem; font-weight: 800; font-variant-numeric: tabular-nums; }
.score-unit { font-size: 0.65rem; color: var(--text-tertiary); margin-left: 1px; }
.score-high .score-value { color: #4ade80; }
.score-mid .score-value { color: #fbbf24; }
.score-low .score-value { color: var(--text-tertiary); }

.tag-list { max-height: 360px; overflow-y: auto; }
.tag-row {
  display: flex; align-items: center; padding: 10px 8px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.05);
  cursor: pointer; border-radius: 8px; transition: background 0.15s;
}
.tag-row:hover { background: rgba(var(--v-theme-on-surface), 0.04); }
.tag-row:focus-visible { outline: 2px solid rgba(139,92,246,0.5); outline-offset: -2px; }
.tag-row--active { background: rgba(139,92,246,0.12) !important; border-color: rgba(139,92,246,0.25); }
.tag-main { flex: 1; min-width: 0; display: flex; align-items: center; gap: 6px; }
.tag-name { font-size: 0.85rem; font-weight: 500; color: var(--text-primary); }
.tag-chip { font-size: 0.6rem !important; height: 18px !important; }
.tag-stats { text-align: right; flex-shrink: 0; }
.tag-freq { font-size: 0.75rem; color: #fbbf24; }
.tag-conf { font-size: 0.7rem; color: var(--text-tertiary); display: block; }

.tag-panel { margin-top: 0; }
.panel-loading { display: flex; align-items: center; gap: 10px; justify-content: center; padding: 20px 0; color: var(--text-secondary); font-size: 0.85rem; }
.tag-track-list { max-height: 260px; overflow-y: auto; }
.tag-track-row {
  display: flex; align-items: center; padding: 8px; border-radius: 8px;
  cursor: pointer; transition: background 0.15s;
}
.tag-track-row:hover { background: rgba(var(--v-theme-on-surface), 0.04); }
.tag-track-row:focus-visible { outline: 2px solid rgba(139,92,246,0.5); outline-offset: -2px; }

.track-list-enter-active, .track-list-leave-active,
.tag-list-enter-active, .tag-list-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.track-list-enter-from, .tag-list-enter-from { opacity: 0; transform: translateY(-8px); }
.track-list-leave-to, .tag-list-leave-to { opacity: 0; transform: translateX(-12px); }

.panel-slide-enter-active, .panel-slide-leave-active { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.panel-slide-enter-from { opacity: 0; transform: translateY(-12px) scale(0.97); }
.panel-slide-leave-to { opacity: 0; transform: translateY(-8px); }

@media (max-width: 860px) {
  .radar-layout, .skeleton-grid { grid-template-columns: 1fr; }
  .chart-wrap { height: 320px; }
  .legend-item { min-width: 140px; }
  .skeleton-chart { height: 340px; }
}
</style>
