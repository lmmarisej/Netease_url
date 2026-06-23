<template>
  <div class="studio-hub">
    <!-- ==================== iOS 风格分段控制器 ==================== -->
    <div class="segment-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="segment-btn"
        :class="{ 'segment-btn--active': activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <span class="segment-icon">{{ tab.icon }}</span>
        <span class="segment-label">{{ tab.label }}</span>
      </button>
    </div>

    <!-- ==================== Tab 1：发现音乐 ==================== -->
    <div v-if="activeTab === 'discover'" class="tab-content">
      <div class="discover-layout">
        <!-- 左侧：播放器卡片 -->
        <div class="player-col">
          <div class="glass-card player-card">
            <!-- 封面 + 歌词 左右布局 -->
            <div class="player-main">
              <!-- 左侧：CD 唱片封面 -->
              <div class="cd-wrap" :class="{ 'cd-wrap--playing': isPlaying }">
                <div class="cd-disc">
                  <img
                    v-if="currentTrack.coverUrl"
                    :src="currentTrack.coverUrl"
                    class="cd-cover"
                    alt="封面"
                  />
                  <div v-else class="cd-placeholder">
                    <v-icon size="40" color="rgba(var(--v-theme-on-surface),0.2)">mdi-music</v-icon>
                  </div>
                  <div class="cd-hole" />
                </div>
              </div>
              <!-- 右侧：歌词 -->
              <div class="lyrics-side">
                <div v-if="lyricLines.length" class="lyrics-scroll">
                  <TransitionGroup name="lyric-fade" tag="div">
                    <div
                      v-for="(line, i) in visibleLyricLines"
                      :key="line.idx"
                      class="lyric-line"
                      :class="{ 'lyric-line--active': line.idx === activeLyricIdx }"
                    >{{ line.text }}</div>
                  </TransitionGroup>
                </div>
                <div v-else-if="lyricLoading" class="lyric-placeholder">加载歌词中...</div>
                <div v-else class="lyric-placeholder">暂无歌词</div>
              </div>
            </div>
            <!-- 歌曲信息 -->
            <div class="player-info">
              <div class="player-title text-truncate">{{ currentTrack.title || '选择一首歌曲' }}</div>
              <div class="player-artist text-truncate">{{ currentTrack.artist || '—' }}</div>
            </div>
            <!-- 进度条 -->
            <div class="progress-row">
              <span class="progress-time">{{ formatTime(playElapsed) }}</span>
              <div class="progress-bar-wrap" @click="seekProgress" ref="progressWrapRef">
                <div class="progress-bar" :style="{ width: progressPercent + '%' }" />
              </div>
              <span class="progress-time">{{ formatTime(currentTrack.duration || 0) }}</span>
            </div>
            <!-- 控制按钮 -->
            <div class="player-controls">
              <v-btn icon="mdi-skip-previous" variant="text" size="small" :disabled="playlistIndex <= 0" @click="prevTrack" />
              <v-btn
                icon
                size="large"
                :color="isPlaying ? 'primary' : undefined"
                variant="flat"
                @click="togglePlay"
              >
                <v-icon size="28">{{ isPlaying ? 'mdi-pause' : 'mdi-play' }}</v-icon>
              </v-btn>
              <v-btn icon="mdi-skip-next" variant="text" size="small" :disabled="playlistIndex >= playlist.length - 1" @click="nextTrack" />
            </div>
          </div>

          <!-- 推荐流列表 -->
          <div class="glass-card recommend-list">
            <div class="card-header">
              <v-icon size="18" color="#a78bfa">mdi-playlist-music</v-icon>
              <span class="card-title">推荐流</span>
              <v-spacer />
              <!-- 排序切换 -->
              <v-btn
                icon
                size="x-small"
                variant="text"
                :color="sortOrder === 'desc' ? 'primary' : undefined"
                :title="sortOrder === 'desc' ? '偏好分从高到低' : '偏好分从低到高'"
                @click="sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'; page = 1; fetchRecommend()"
              >
                <v-icon size="16">{{ sortOrder === 'desc' ? 'mdi-sort-descending' : 'mdi-sort-ascending' }}</v-icon>
              </v-btn>
              <span class="card-badge" v-if="recommendTracks.length">{{ recommendTracks.length }} 首</span>
            </div>
            <!-- 歌单源 Tab 切换 -->
            <div class="source-tabs">
              <div class="source-tab-row">
                <button
                  v-for="src in sourceTabs"
                  :key="src.value"
                  class="source-tab"
                  :class="{ 'source-tab--active': sourceType === src.value }"
                  @click="switchSource(src.value)"
                >
                  <span class="source-tab-icon">{{ src.icon }}</span>
                  <span class="source-tab-label">{{ src.label }}</span>
                </button>
              </div>
              <!-- 自定义歌单 ID 输入 -->
              <div v-if="sourceType === 'custom_playlist'" class="source-tab-extra">
                <v-text-field
                  v-model="customPlaylistId"
                  label="歌单 ID"
                  placeholder="输入网易云歌单 ID"
                  variant="solo-filled"
                  density="compact"
                  hide-details
                  rounded="lg"
                  class="playlist-id-input"
                />
                <v-btn
                  size="small"
                  color="primary"
                  variant="flat"
                  prepend-icon="mdi-refresh"
                  :loading="recommendLoading"
                  @click="fetchRecommend"
                >刷新</v-btn>
              </div>
            </div>
            <div v-if="recommendLoading" class="list-loading">
              <v-progress-circular indeterminate size="20" width="2" color="primary" />
              <span class="text-caption text-medium-emphasis ml-2">加载推荐...</span>
            </div>
            <div v-else-if="!recommendTracks.length" class="list-empty">
              选择歌单源并刷新，发现新音乐
            </div>
            <TransitionGroup v-else name="track-list" tag="div" class="track-scroll">
              <div
                v-for="t in recommendTracks"
                :key="t.track_id"
                class="track-row"
                :class="{ 'track-row--active': currentTrack.track_id === t.track_id }"
                @click="playTrack(t)"
              >
                <img v-if="t.cover_url" :src="t.cover_url" class="track-thumb" alt="" />
                <div v-else class="track-thumb-placeholder">
                  <v-icon size="14" color="rgba(var(--v-theme-on-surface),0.3)">mdi-music-note</v-icon>
                </div>
                <div class="track-meta">
                  <div class="track-name text-truncate">{{ t.title }}</div>
                  <div class="track-artist-name text-truncate">{{ t.artist }}</div>
                </div>
                <!-- 偏好匹配分 -->
                <v-chip
                  v-if="t.preference_score > 0"
                  size="x-small"
                  variant="flat"
                  :color="prefColor(t.preference_score)"
                  class="track-chip track-chip--pref"
                >{{ t.preference_score }}分</v-chip>
                <!-- 来源标签 -->
                <v-chip
                  v-if="t.source === 'local'"
                  size="x-small"
                  variant="tonal"
                  color="success"
                  class="track-chip"
                >本地</v-chip>
                <v-chip
                  v-else-if="t.source === 'netease'"
                  size="x-small"
                  variant="tonal"
                  :color="t.bpm < 0 ? 'warning' : 'success'"
                  class="track-chip"
                >{{ t.bpm < 0 ? '待扫描' : '已分析' }}</v-chip>
                <!-- 爱心按钮 -->
                <v-btn
                  icon
                  size="x-small"
                  variant="text"
                  :color="likedIds.has(Number(t.track_id)) ? 'red' : undefined"
                  @click.stop="toggleLike(t)"
                >
                  <v-icon size="15">
                    {{ likedIds.has(Number(t.track_id)) ? 'mdi-heart' : 'mdi-heart-outline' }}
                  </v-icon>
                </v-btn>
              </div>
            </TransitionGroup>
            <!-- 分页控件 -->
            <div class="pagination-bar" v-if="totalPages > 1">
              <v-btn
                icon="mdi-chevron-left"
                size="small"
                variant="text"
                :disabled="page <= 1"
                @click="goToPage(page - 1)"
              />
              <span class="pagination-info">{{ page }} / {{ totalPages }} 页（共 {{ totalTracks }} 首）</span>
              <v-btn
                icon="mdi-chevron-right"
                size="small"
                variant="text"
                :disabled="page >= totalPages"
                @click="goToPage(page + 1)"
              />
            </div>
          </div>
        </div>

        <!-- 右侧：播放状态指示 -->
        <div class="source-col">
          <div class="glass-card status-card" v-if="currentTrack.track_id">
            <div class="card-header">
              <v-icon size="16" :color="isPlaying ? 'success' : 'rgba(var(--v-theme-on-surface),0.4)'">
                {{ isPlaying ? 'mdi-play-circle' : 'mdi-pause-circle' }}
              </v-icon>
              <span class="card-title">播放状态</span>
            </div>
            <div class="status-grid">
              <div class="status-item">
                <span class="status-label">累计聆听</span>
                <span class="status-value">{{ formatTime(playedAccum) }}</span>
              </div>
              <div class="status-item">
                <span class="status-label">总时长</span>
                <span class="status-value">{{ formatTime(currentTrack.duration || 0) }}</span>
              </div>
              <div class="status-item">
                <span class="status-label">位置</span>
                <span class="status-value">{{ progressPercent.toFixed(0) }}%</span>
              </div>
              <div class="status-item">
                <span class="status-label">跳过</span>
                <span class="status-value" :class="skipStatusClass">{{ skipStatusText }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== Tab 2：DNA谱图 ==================== -->
    <div v-if="activeTab === 'dna'" class="tab-content">
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
                <span class="card-badge">实时分析</span>
              </div>
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
            <div class="glass-card">
              <div class="card-header">
                <v-icon size="18" color="#f59e0b">mdi-fire</v-icon>
                <span class="card-title">TOP 10 共鸣单曲</span>
                <v-spacer />
                <span class="card-badge accent">{{ topTracks.length }} 首</span>
              </div>
              <TransitionGroup name="track-list" tag="div" class="track-scroll">
                <div v-for="t in topTracks" :key="t.rank" class="track-row">
                  <div class="rank-badge" :class="t.rank <= 3 ? 'rank-gold' : ''">
                    <template v-if="t.rank === 1">🥇</template>
                    <template v-else-if="t.rank === 2">🥈</template>
                    <template v-else-if="t.rank === 3">🥉</template>
                    <template v-else>{{ t.rank }}</template>
                  </div>
                  <div class="track-meta">
                    <div class="track-name text-truncate">{{ t.title }}</div>
                    <div class="track-artist-name text-truncate">{{ t.artist }}</div>
                  </div>
                  <div class="track-score" :class="scoreClass(t.resonance)">
                    <span class="score-value">{{ t.resonance }}</span>
                    <span class="score-unit">分</span>
                  </div>
                </div>
              </TransitionGroup>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- ==================== Tab 3：权重配置 ==================== -->
    <div v-if="activeTab === 'mixer'" class="tab-content">
      <div class="slot-switcher">
        <div
          v-for="slot in slots"
          :key="slot.key"
          class="slot-card"
          :class="{ 'slot-card--active': activeSlot === slot.key }"
          :style="{ '--slot-color': slot.color }"
          @click="activeSlot = slot.key"
        >
          <span class="slot-emoji">{{ slot.icon }}</span>
          <span class="slot-label">{{ slot.label }}</span>
          <span class="slot-time">{{ slot.time }}</span>
        </div>
      </div>
      <v-row class="mt-6">
        <v-col v-for="panel in mixerPanels" :key="panel.name" cols="12" md="6" xl="4">
          <div class="glass-card mixer-panel">
            <div class="card-header">
              <v-icon size="18" :color="panel.iconColor" class="mr-2">{{ panel.icon }}</v-icon>
              <span class="card-title">{{ panel.name }}</span>
              <v-chip size="x-small" variant="tonal" :color="panel.chipColor" class="ml-2">{{ panel.chip }}</v-chip>
            </div>
            <div class="mixer-body">
              <div
                v-for="param in panel.params"
                :key="param.key"
                class="slider-row"
                :class="{ 'slider-row--dragging': draggingKey === param.key }"
              >
                <div class="slider-label">
                  <span class="slider-name">{{ param.label }}</span>
                  <span
                    class="slider-value"
                    :class="{ 'slider-value--active': draggingKey === param.key }"
                    :style="{ '--param-color': param.color }"
                  >{{ currentWeights[param.key]?.toFixed(1) }}</span>
                </div>
                <v-slider
                  :model-value="currentWeights[param.key]"
                  :min="0" :max="2" :step="0.1"
                  :color="param.color"
                  track-size="4" thumb-size="16"
                  hide-details density="compact"
                  @update:model-value="(v) => currentWeights[param.key] = v"
                  @start="draggingKey = param.key"
                  @end="draggingKey = null"
                />
              </div>
            </div>
          </div>
        </v-col>
      </v-row>
      <div class="save-bar">
        <v-btn color="primary" size="large" :loading="mixerSaving" prepend-icon="mdi-content-save" @click="saveWeights">
          保存权重配置
        </v-btn>
      </div>
    </div>

    <!-- ==================== Tab 4：播放历史 ==================== -->
    <div v-if="activeTab === 'history'" class="tab-content">
      <div class="glass-card">
        <div class="card-header">
          <v-icon size="18" color="#6b9e78">mdi-history</v-icon>
          <span class="card-title">播放历史</span>
          <v-spacer />
          <span class="card-badge" v-if="historyTotal">{{ historyTotal }} 条</span>
        </div>
        <div v-if="historyLoading" class="list-loading">
          <v-progress-circular indeterminate size="20" width="2" color="primary" />
          <span class="text-caption text-medium-emphasis ml-2">加载中...</span>
        </div>
        <div v-else-if="!historyItems.length" class="list-empty">暂无播放记录</div>
        <div v-else class="history-table-wrap">
          <div class="history-header">
            <span class="h-col col-track">歌曲</span>
            <span class="h-col col-time">播放时长</span>
            <span class="h-col col-skip">状态</span>
            <span class="h-col col-date">时间</span>
          </div>
          <div v-for="item in historyItems" :key="item.id" class="history-row">
            <div class="h-col col-track">
              <div class="ht-title text-truncate">{{ item.title || '未知歌曲' }}</div>
              <div class="ht-artist text-truncate">{{ item.artist || '—' }}</div>
            </div>
            <div class="h-col col-time">
              <span class="ht-dur">{{ formatTime(item.play_duration) }}</span>
              <span class="ht-sep">/</span>
              <span class="ht-total">{{ formatTime(item.total_duration) }}</span>
            </div>
            <div class="h-col col-skip">
              <span v-if="item.is_skipped" class="skip-tag skip-tag--yes">⏭ 跳过</span>
              <span v-else class="skip-tag skip-tag--no">✓ 完播</span>
            </div>
            <div class="h-col col-date">
              <span class="ht-date">{{ formatDate(item.timestamp) }}</span>
            </div>
          </div>
        </div>
        <!-- 分页 -->
        <div v-if="historyTotal > historyPageSize" class="pagination-row">
          <v-btn
            variant="text" size="small" :disabled="historyPage <= 1"
            prepend-icon="mdi-chevron-left" @click="historyPage--; fetchHistory()"
          >上一页</v-btn>
          <span class="text-caption text-medium-emphasis">{{ historyPage }} / {{ Math.ceil(historyTotal / historyPageSize) }}</span>
          <v-btn
            variant="text" size="small" :disabled="historyPage >= Math.ceil(historyTotal / historyPageSize)"
            append-icon="mdi-chevron-right" @click="historyPage++; fetchHistory()"
          >下一页</v-btn>
        </div>
      </div>
    </div>

    <!-- 隐藏的音频元素用于播放跟踪 -->
    <audio ref="audioRef" @timeupdate="onTimeUpdate" @ended="onTrackEnded" @play="isPlaying = true" @pause="isPlaying = false" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useTheme } from 'vuetify'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { createAuthAxios } from '@/api/authAxios.js'
import { getWeightConfig, saveWeightConfig } from '@/api/index.js'

const api = createAuthAxios()
use([CanvasRenderer, RadarChart, TooltipComponent, LegendComponent])
const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)

// ══════════════════════════════════════════════
//  顶部 Tab
// ══════════════════════════════════════════════
const tabs = [
  { key: 'discover', icon: '🎵', label: '发现音乐' },
  { key: 'dna', icon: '🧬', label: 'DNA谱图' },
  { key: 'mixer', icon: '🎛️', label: '权重配置' },
  { key: 'history', icon: '📜', label: '播放历史' },
]
const activeTab = ref('discover')

// ══════════════════════════════════════════════
//  Tab 1：发现音乐 — 播放器 + 推荐
// ══════════════════════════════════════════════
const audioRef = ref(null)
const progressWrapRef = ref(null)
const isPlaying = ref(false)
const playElapsed = ref(0)       // 当前播放位置（秒），用于进度条
const playedAccum = ref(0)       // 实际累计播放时长（秒），不受拖拽影响
const playStartTime = ref(0)
const playTimer = ref(null)
const playlist = ref([])
const playlistIndex = ref(-1)
const recommendTracks = ref([])
const recommendLoading = ref(false)
const sourceType = ref('liked')
const customPlaylistId = ref('')
const sortOrder = ref('desc')
const page = ref(1)
const pageSize = ref(20)
const totalPages = ref(1)
const totalTracks = ref(0)
const hasAudioSource = ref(false)

// ── 喜欢状态 ──
const likedIds = ref(new Set())

// ── 分页数据缓存：key = `${sourceType}|${sortOrder}|${playlistId}` ──
//    每个 key 下存多页数据：Map<pageNumber, { tracks, total, total_pages }>
const recommendCache = reactive(new Map())

// ── 歌词状态 ──
const lyricLines = ref([])          // [{ time: 秒, text: '' }]
const activeLyricIdx = ref(-1)
const lyricLoading = ref(false)
const lyricsExpanded = ref(false)

// 歌词视窗：仅展示当前行前后各 3 行
const LYRIC_WINDOW = 6
const visibleLyricLines = computed(() => {
  if (!lyricLines.value.length) return []
  const center = Math.max(0, activeLyricIdx.value)
  const start = Math.max(0, center - Math.floor(LYRIC_WINDOW / 2))
  const end = Math.min(lyricLines.value.length, start + LYRIC_WINDOW)
  return lyricLines.value.slice(start, end).map((l, i) => ({ ...l, idx: start + i }))
})

const sourceOptions = [
  { title: '🔥 网易云热榜', value: 'hot_list' },
  { title: '📋 自定义歌单', value: 'custom_playlist' },
  { title: '💿 本地音乐', value: 'local_library' },
]

const sourceTabs = [
  { icon: '❤️', label: '喜欢', value: 'liked' },
  { icon: '🔥', label: '热榜', value: 'hot_list' },
  { icon: '💿', label: '本地', value: 'local_library' },
  { icon: '📋', label: '歌单', value: 'custom_playlist' },
]

const currentTrack = reactive({
  track_id: '',
  title: '',
  artist: '',
  album: '',
  coverUrl: '',
  duration: 0,
})

const progressPercent = computed(() => {
  if (!currentTrack.duration) return 0
  return Math.min((playElapsed.value / currentTrack.duration) * 100, 100)
})

const skipStatusText = computed(() => {
  if (!currentTrack.duration) return '—'
  if (playElapsed.value < 10 || progressPercent.value < 20) return '⚠ 即将跳过'
  return '正常'
})

const skipStatusClass = computed(() => {
  if (!currentTrack.duration) return ''
  if (playElapsed.value < 10 || progressPercent.value < 20) return 'status-warn'
  return 'status-ok'
})

function startPlayTimer() {
  stopPlayTimer()
  playTimer.value = setInterval(() => {
    // 播放位置以 audio.currentTime 为准（onTimeUpdate 已更新 playElapsed）
    // 累计播放时长仅在播放状态下递增
    if (isPlaying.value) {
      playedAccum.value += 0.25
    }
    // 同步歌词高亮
    updateActiveLyric()
  }, 250)
}

function stopPlayTimer() {
  if (playTimer.value) { clearInterval(playTimer.value); playTimer.value = null }
}

function onTimeUpdate() {
  if (audioRef.value) {
    playElapsed.value = audioRef.value.currentTime
    currentTrack.duration = audioRef.value.duration || currentTrack.duration
  }
}

function onTrackEnded() {
  isPlaying.value = false
  stopPlayTimer()
  logPlayback(false)
  nextTrack()
}

async function playTrack(track) {
  // 切换前上报上一首
  if (currentTrack.track_id && currentTrack.track_id !== track.track_id) {
    await logPlayback(true)
  }
  // 设置新曲目
  currentTrack.track_id = track.track_id
  currentTrack.title = track.title
  currentTrack.artist = track.artist
  currentTrack.album = track.album || ''
  currentTrack.coverUrl = track.cover_url || ''
  currentTrack.duration = 180  // 默认 3 分钟，无本地文件时用于模拟进度
  playElapsed.value = 0
  playedAccum.value = 0
  hasAudioSource.value = !!track.file_path

  // 尝试加载音频源：优先本地文件流，否则用网易云流媒体代理
  const token = localStorage.getItem('token') || ''
  if (track.file_path) {
    // Windows 路径转 URL 友好格式：反斜杠 → 正斜杠
    const safePath = track.file_path.replace(/\\/g, '/')
    audioRef.value.src = `/api/files/stream/${encodeURI(safePath)}?token=${encodeURIComponent(token)}`
    hasAudioSource.value = true
  } else {
    audioRef.value.src = `/api/v3/music/stream/${encodeURIComponent(track.track_id)}?token=${encodeURIComponent(token)}`
    hasAudioSource.value = true
  }
  audioRef.value.load()
  try { await audioRef.value.play(); isPlaying.value = true } catch { isPlaying.value = false }
  if (isPlaying.value) startPlayTimer()
  // 异步加载歌词
  fetchLyrics(track.track_id, track.title, track.artist)
}

async function togglePlay() {
  if (!currentTrack.track_id) {
    // 无选中曲目：自动播放推荐流第一首
    if (recommendTracks.value.length) {
      playTrack(recommendTracks.value[0])
      playlistIndex.value = 0
    }
    return
  }
  if (isPlaying.value) {
    audioRef.value?.pause()
    stopPlayTimer()
    isPlaying.value = false
  } else {
    isPlaying.value = true
    startPlayTimer()
    try { await audioRef.value?.play() } catch { /* 无音频源，仅视觉播放 */ }
  }
}

async function nextTrack() {
  if (currentTrack.track_id) await logPlayback(true)
  if (playlistIndex.value < playlist.value.length - 1) {
    playlistIndex.value++
    playTrack(playlist.value[playlistIndex.value])
  }
}

async function prevTrack() {
  if (currentTrack.track_id) await logPlayback(true)
  if (playlistIndex.value > 0) {
    playlistIndex.value--
    playTrack(playlist.value[playlistIndex.value])
  }
}

async function logPlayback(isSwitch = false) {
  if (!currentTrack.track_id) return
  const duration = playedAccum.value  // 实际累计聆听时长
  const total = currentTrack.duration || 1
  const isSkipped = isSwitch && (duration < 10 || duration / total < 0.2)
  try {
    await api.post('/api/v3/music/log', {
      track_id: currentTrack.track_id,
      title: currentTrack.title,
      artist: currentTrack.artist,
      play_duration: Math.round(duration),
      total_duration: Math.round(total),
      source_type: sourceType.value,
    })
  } catch {
    // 静默失败，不影响用户体验
  }
}

// ══════════════════════════════════════════════
//  歌词解析与展示
// ══════════════════════════════════════════════

function parseLRC(lrcText) {
  // 解析 LRC 格式：[mm:ss.xx]歌词文本
  const lines = []
  const regex = /\[(\d{1,3}):(\d{2})(?:[.:](\d{2,3}))?\]/g
  const rawLines = lrcText.split('\n')
  for (const raw of rawLines) {
    const matches = [...raw.matchAll(regex)]
    if (matches.length === 0) continue
    const text = raw.replace(regex, '').trim()
    if (!text) continue
    for (const m of matches) {
      const min = parseInt(m[1]) || 0
      const sec = parseInt(m[2]) || 0
      const ms = parseInt(m[3]) || 0
      const time = min * 60 + sec + ms / (m[3]?.length === 3 ? 1000 : 100)
      lines.push({ time, text })
    }
  }
  lines.sort((a, b) => a.time - b.time)
  return lines
}

async function fetchLyrics(trackId, title, artist) {
  lyricLines.value = []
  activeLyricIdx.value = -1
  lyricLoading.value = true
  try {
    const res = await api.get('/api/lyrics', {
      params: { title, artist, id: trackId },
      responseType: 'text',
      transformResponse: [(d) => d],
    })
    const lrc = res.data || ''
    if (lrc && lrc.includes('[')) {
      lyricLines.value = parseLRC(lrc)
    }
  } catch {
    lyricLines.value = []
  } finally {
    lyricLoading.value = false
  }
}

function updateActiveLyric() {
  if (!lyricLines.value.length) return
  const t = playElapsed.value
  let idx = -1
  for (let i = 0; i < lyricLines.value.length; i++) {
    if (lyricLines.value[i].time <= t) idx = i
    else break
  }
  if (idx !== activeLyricIdx.value) {
    activeLyricIdx.value = idx
  }
}

function _cacheKey() {
  const pid = sourceType.value === 'custom_playlist' ? customPlaylistId.value.trim() : ''
  return `${sourceType.value}|${sortOrder.value}|${pid}`
}

function _restoreFromCache(key) {
  const pages = recommendCache.get(key)
  if (!pages) return false
  const cached = pages.get(page.value)
  if (!cached) return false
  recommendTracks.value = cached.tracks
  playlist.value = cached.tracks
  playlistIndex.value = -1
  totalTracks.value = cached.total
  totalPages.value = cached.total_pages
  return true
}

async function fetchRecommend() {
  if (sourceType.value === 'custom_playlist' && !customPlaylistId.value.trim()) {
    window.__snackbar?.('请输入歌单 ID', 'warning')
    return
  }

  const key = _cacheKey()
  // 命中缓存则直接恢复，不请求网易云
  if (_restoreFromCache(key)) return

  recommendLoading.value = true
  try {
    const params = {
      source_type: sourceType.value,
      sort_order: sortOrder.value,
      page: page.value,
      page_size: pageSize.value,
    }
    if (sourceType.value === 'custom_playlist') {
      params.playlist_id = customPlaylistId.value.trim()
    }
    const res = await api.get('/api/v3/music/recommend', { params })
    const body = res.data?.data
    if (body?.tracks) {
      recommendTracks.value = body.tracks
      playlist.value = body.tracks
      playlistIndex.value = -1
      totalTracks.value = body.total || body.tracks.length
      totalPages.value = body.total_pages || 1
      page.value = body.page || 1

      // 写入缓存
      if (!recommendCache.has(key)) recommendCache.set(key, new Map())
      recommendCache.get(key).set(page.value, {
        tracks: body.tracks,
        total: body.total || body.tracks.length,
        total_pages: body.total_pages || 1,
      })

      window.__snackbar?.(`第 ${page.value}/${totalPages.value} 页，共 ${totalTracks.value} 首`, 'success')
    }
  } catch (e) {
    window.__snackbar?.('推荐加载失败: ' + (e.message || '网络错误'), 'error')
  } finally {
    recommendLoading.value = false
  }
}

async function initLikedIds() {
  try {
    const res = await api.get('/api/v3/music/liked-ids')
    const ids = res.data?.ids || res.data?.data?.ids
    if (ids?.length) {
      likedIds.value = new Set(ids)
    }
  } catch {
    // 静默失败，不影响主流程
  }
}

async function toggleLike(track) {
  const id = Number(track.track_id)
  if (!id) return
  const wasLiked = likedIds.value.has(id)
  // 乐观更新
  const next = new Set(likedIds.value)
  if (wasLiked) next.delete(id)
  else next.add(id)
  likedIds.value = next

  try {
    await api.post('/api/v3/music/like', { track_id: id, like: !wasLiked })
    window.__snackbar?.(wasLiked ? '已取消喜欢' : '已加入 ❤️ 我喜欢的音乐', 'success')
  } catch (e) {
    // 回滚
    const rollback = new Set(likedIds.value)
    if (wasLiked) rollback.add(id)
    else rollback.delete(id)
    likedIds.value = rollback
    window.__snackbar?.('操作失败: ' + (e.response?.data?.message || e.message), 'error')
  }
}

function formatTime(sec) {
  if (!sec || sec <= 0) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function prefColor(score) {
  if (score >= 80) return 'success'
  if (score >= 60) return 'primary'
  if (score >= 40) return 'warning'
  return 'error'
}

function seekProgress(e) {
  if (!currentTrack.duration) return
  const wrap = progressWrapRef.value
  if (!wrap) return
  const rect = wrap.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  const target = ratio * currentTrack.duration
  playElapsed.value = target
  if (audioRef.value?.src) {
    audioRef.value.currentTime = target
  }
}

// ══════════════════════════════════════════════
//  Tab 2：DNA谱图
// ══════════════════════════════════════════════
const username = computed(() => localStorage.getItem('username') || 'admin')
const dnaLoading = ref(true)
const dnaError = ref('')
const dnaEmpty = ref(false)
const trackCount = ref(0)
const hoveredDim = ref(null)

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
      borderColor: 'rgba(139,92,246,0.35)',
      borderWidth: 1,
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
        textStyle: {
          color: dark ? '#a1a1aa' : '#6b6b7b', fontSize: 10, fontWeight: 500, lineHeight: 14,
          backgroundColor: dark ? 'rgba(24,24,30,0.85)' : 'rgba(255,255,255,0.85)', borderRadius: 4, padding: [1, 4],
        },
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

const topTracks = ref([])

function scoreClass(val) {
  if (val >= 70) return 'score-high'
  if (val >= 50) return 'score-mid'
  return 'score-low'
}

async function loadDnaData() {
  dnaLoading.value = true; dnaError.value = ''
  try {
    const u = username.value
    const [radarRes, tracksRes] = await Promise.allSettled([
      api.get(`/api/user/${u}/taste-radar`),
      api.get(`/api/user/${u}/taste-top-tracks`),
    ])
    if (radarRes.status === 'fulfilled') {
      const body = radarRes.value?.data
      if (body?.success && body.data?.radar) {
        const d = body.data
        dimensions.forEach((dim, i) => { radarData[dim.key] = d.radar[i] ?? 50 })
        trackCount.value = d.count ?? 0
        dnaEmpty.value = trackCount.value === 0
      }
    }
    if (tracksRes.status === 'fulfilled') {
      const body = tracksRes.value?.data
      topTracks.value = (body?.success && body.data) ? body.data : []
    }
  } catch (e) {
    dnaError.value = '加载失败：' + (e.message || '网络错误')
  } finally {
    dnaLoading.value = false
  }
}

// ══════════════════════════════════════════════
//  Tab 3：权重配置
// ══════════════════════════════════════════════
const slots = [
  { key: 'morning', icon: '🌅', label: '元气清晨', time: '07:00-09:00', color: '#c4956a' },
  { key: 'daytime', icon: '💻', label: '高效白昼', time: '09:00-18:00', color: '#6a9fb5' },
  { key: 'evening', icon: '🌆', label: '多巴胺黄昏', time: '18:00-22:00', color: '#b87d8d' },
  { key: 'midnight', icon: '🌌', label: '静谧深夜', time: '22:00-07:00', color: '#8b7fba' },
]
const activeSlot = ref('morning')
const draggingKey = ref(null)

const mixerPanels = [
  {
    name: '声学与声源分离', icon: 'mdi-waveform', iconColor: '#e09953', chip: 'Librosa / Demucs', chipColor: '#e09953',
    params: [
      { key: 'tempo', label: 'Tempo · 节奏速度', color: '#e09953' },
      { key: 'energy', label: 'Energy · 能量强度', color: '#cd5c5c' },
      { key: 'vocal_ratio', label: 'Vocal Ratio · 人声比例', color: '#6b9e78' },
      { key: 'bass_intensity', label: 'Bass Int. · 低音强度', color: '#b8738d' },
      { key: 'acousticness', label: 'Acousticness · 原声度', color: '#70a1b5' },
    ],
  },
  {
    name: '流派与乐器', icon: 'mdi-music-clef-treble', iconColor: '#9b8ec4', chip: 'PANNs', chipColor: '#9b8ec4',
    params: [
      { key: 'electronic_score', label: 'Electronic · 电子乐', color: '#9b8ec4' },
      { key: 'rock_score', label: 'Rock · 摇滚乐', color: '#c46b6b' },
      { key: 'instrument_pureness', label: 'Instrument Pure. · 器乐纯净度', color: '#5f9ea0' },
    ],
  },
  {
    name: '歌词高级意境', icon: 'mdi-drama-masks', iconColor: '#d4956b', chip: 'Ollama LLM', chipColor: '#d4956b',
    params: [
      { key: 'midnight_emo', label: 'Midnight Emo · 深夜情绪', color: '#d4956b' },
      { key: 'guofeng_vibe', label: 'Guofeng Vibe · 国风意境', color: '#c4a35a' },
    ],
  },
]

const DEFAULT_WEIGHTS = {
  morning: { tempo: 0.8, energy: 0.6, vocal_ratio: 1.0, bass_intensity: 0.5, acousticness: 1.5, electronic_score: 0.3, rock_score: 0.3, instrument_pureness: 1.3, midnight_emo: 0.2, guofeng_vibe: 1.2 },
  daytime: { tempo: 1.2, energy: 1.0, vocal_ratio: 1.1, bass_intensity: 0.9, acousticness: 0.7, electronic_score: 1.1, rock_score: 0.8, instrument_pureness: 1.4, midnight_emo: 0.4, guofeng_vibe: 1.0 },
  evening: { tempo: 1.5, energy: 1.6, vocal_ratio: 1.2, bass_intensity: 1.5, acousticness: 0.4, electronic_score: 1.5, rock_score: 1.2, instrument_pureness: 0.7, midnight_emo: 1.1, guofeng_vibe: 0.8 },
  midnight: { tempo: 0.5, energy: 0.3, vocal_ratio: 1.4, bass_intensity: 0.7, acousticness: 1.3, electronic_score: 0.6, rock_score: 0.2, instrument_pureness: 1.2, midnight_emo: 1.8, guofeng_vibe: 1.1 },
}

const allWeights = reactive(structuredClone(DEFAULT_WEIGHTS))
const currentWeights = computed({
  get: () => allWeights[activeSlot.value] || {},
  set: (v) => { allWeights[activeSlot.value] = v },
})
const mixerSaving = ref(false)

async function loadWeights() {
  try {
    const data = await getWeightConfig()
    if (data?.slots) {
      for (const [key, slot] of Object.entries(data.slots)) {
        if (allWeights[key] && slot.weights) allWeights[key] = { ...DEFAULT_WEIGHTS[key], ...slot.weights }
      }
    }
  } catch { /* 保留默认 */ }
}

async function saveWeights() {
  mixerSaving.value = true
  try {
    const payload = { slots: {} }
    for (const [key, weights] of Object.entries(allWeights)) {
      const def = slots.find(s => s.key === key)
      payload.slots[key] = { label: def ? `${def.label} (${def.time})` : key, weights: { ...weights } }
    }
    await saveWeightConfig(payload)
    window.__snackbar?.('权重配置已保存', 'success')
  } catch (e) {
    window.__snackbar?.('保存失败: ' + (e.message || '未知错误'), 'error')
  } finally { mixerSaving.value = false }
}

// ══════════════════════════════════════════════
//  Tab 4：播放历史
// ══════════════════════════════════════════════
const historyItems = ref([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = 20
const historyLoading = ref(false)

async function fetchHistory() {
  historyLoading.value = true
  try {
    const res = await api.get('/api/v3/music/history', { params: { page: historyPage.value, page_size: historyPageSize } })
    const body = res.data?.data
    historyItems.value = body?.items || []
    historyTotal.value = body?.total || 0
  } catch { /* 静默 */ }
  finally { historyLoading.value = false }
}

function formatDate(iso) {
  if (!iso) return ''
  try { return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
  catch { return iso }
}

// ══════════════════════════════════════════════
//  生命周期
// ══════════════════════════════════════════════
watch(activeTab, (tab) => {
  if (tab === 'dna') loadDnaData()
  if (tab === 'mixer') loadWeights()
  if (tab === 'history') fetchHistory()
})


function switchSource(val) {
  if (sourceType.value === val) return
  sourceType.value = val
  page.value = 1
  totalPages.value = 1
  totalTracks.value = 0
  recommendTracks.value = []
  playlist.value = []
  // 优先从缓存恢复当前 source 的第 1 页
  if (!_restoreFromCache(_cacheKey())) {
    fetchRecommend()
  }
}

function goToPage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  // 优先从缓存恢复，无缓存才拉取
  if (!_restoreFromCache(_cacheKey())) {
    fetchRecommend()
  }
}

onMounted(() => {
  fetchRecommend()
  initLikedIds()
})

onBeforeUnmount(() => {
  stopPlayTimer()
  if (currentTrack.track_id) logPlayback(true)
})
</script>

<style scoped>
/* ══════════════════════════════════════════════
   Aero-Material 全局基调
   ══════════════════════════════════════════════ */
.studio-hub {
  --aero-bg: rgba(var(--v-theme-surface), 0.55);
  --aero-border: rgba(var(--v-theme-on-surface), 0.06);
  --aero-radius: 20px;
  --aero-shadow: 0 4px 24px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.04);
  --text-1: rgb(var(--v-theme-on-surface));
  --text-2: rgba(var(--v-theme-on-surface), 0.6);
  --text-3: rgba(var(--v-theme-on-surface), 0.38);
  color: var(--text-1);
  position: relative;
}

/* 分页栏 */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--aero-border);
}
.pagination-info {
  font-size: 13px;
  color: var(--text-2);
  min-width: 140px;
  text-align: center;
}

/* 歌单源 Tab 栏 */
.source-tabs {
  padding: 0 12px 8px;
  border-bottom: 1px solid var(--aero-border);
}
.source-tab-row {
  display: flex;
  gap: 2px;
}
.source-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border: none;
  border-radius: 10px 10px 0 0;
  background: transparent;
  color: var(--text-3);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.source-tab:hover {
  color: var(--text-1);
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.source-tab--active {
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
  font-weight: 600;
}
.source-tab-icon {
  font-size: 14px;
}
.source-tab-label {
  white-space: nowrap;
}
.source-tab-extra {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0 4px;
}
.playlist-id-input {
  max-width: 200px;
}

/* ══════════════════════════════════════════════
   iOS 分段控制器
   ══════════════════════════════════════════════ */
.segment-bar {
  display: inline-flex;
  background: rgba(var(--v-theme-on-surface), 0.045);
  border-radius: 14px;
  padding: 4px;
  margin-bottom: 24px;
  backdrop-filter: blur(8px);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.05);
}
.segment-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 18px; border: none; border-radius: 11px;
  background: transparent; cursor: pointer;
  font-size: 0.85rem; font-weight: 500; font-family: inherit;
  color: var(--text-2);
  transition: all 0.25s cubic-bezier(0.22, 0.61, 0.36, 1);
  white-space: nowrap;
}
.segment-btn:hover { color: var(--text-1); }
.segment-btn--active {
  background: var(--aero-bg);
  color: var(--text-1);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 0 rgba(255,255,255,0.04);
  font-weight: 600;
}
.segment-icon { font-size: 1rem; line-height: 1; }

/* ══════════════════════════════════════════════
   通用毛玻璃卡片
   ══════════════════════════════════════════════ */
.glass-card {
  background: var(--aero-bg);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--aero-border);
  border-radius: var(--aero-radius);
  box-shadow: var(--aero-shadow);
  padding: 18px;
  transition: border-color 0.3s;
}
.glass-card:hover { border-color: rgba(var(--v-theme-on-surface), 0.1); }
.card-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 14px;
}
.card-title { font-weight: 700; font-size: 0.9rem; color: var(--text-1); }
.card-badge {
  font-size: 0.68rem; font-weight: 600; padding: 2px 10px; border-radius: 20px;
  background: rgba(139,92,246,0.12); color: #a78bfa; border: 1px solid rgba(139,92,246,0.2);
}
.card-badge.accent { background: rgba(245,158,11,0.1); color: #fbbf24; border-color: rgba(245,158,11,0.2); }

/* ══════════════════════════════════════════════
   Tab 1：发现音乐 布局
   ══════════════════════════════════════════════ */
.discover-layout {
  display: grid; grid-template-columns: 1fr 280px; gap: 20px; align-items: start;
}
.player-col { display: flex; flex-direction: column; gap: 16px; }
.source-col { display: flex; flex-direction: column; gap: 16px; }

/* 播放器卡片 */
.player-card { text-align: center; }
.player-main {
  display: flex !important; gap: 16px; align-items: stretch; margin-bottom: 14px;
  justify-content: center;
}

/* CD 唱片封面 */
.cd-wrap {
  flex: 0 0 auto; width: 150px; height: 150px; align-self: center;
  display: flex; align-items: center; justify-content: center;
}
.cd-disc {
  width: 140px; height: 140px; border-radius: 50%; position: relative;
  background: conic-gradient(from 0deg, rgba(255,255,255,0.06), rgba(255,255,255,0.12), rgba(0,0,0,0.08), rgba(255,255,255,0.06));
  box-shadow: 0 4px 24px rgba(0,0,0,0.2), inset 0 0 0 1px rgba(255,255,255,0.06);
  display: flex; align-items: center; justify-content: center;
}
.cd-wrap--playing .cd-disc {
  animation: cd-spin 20s linear infinite;
}
.cd-cover {
  width: 82px; height: 82px; border-radius: 50%; object-fit: cover;
  position: relative; z-index: 1;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3);
}
.cd-placeholder {
  width: 82px; height: 82px; border-radius: 50%;
  background: rgba(var(--v-theme-on-surface), 0.04);
  display: flex; align-items: center; justify-content: center; z-index: 1;
}
.cd-hole {
  position: absolute; width: 16px; height: 16px; border-radius: 50%;
  background: rgb(var(--v-theme-surface));
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.3), 0 1px 0 rgba(255,255,255,0.05);
  z-index: 2; top: 50%; left: 50%; transform: translate(-50%, -50%);
}
@keyframes cd-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* 歌词区域（封面右侧，占 2/3） */
.lyrics-side {
  flex: 0 1 240px; min-width: 0; height: 150px;
  display: flex; flex-direction: column; justify-content: center;
}
.lyrics-scroll {
  overflow: hidden; padding: 4px 0; height: 100%;
}
.lyric-line {
  padding: 4px 8px; font-size: 0.78rem; color: var(--text-3);
  border-radius: 4px; transition: all 0.35s; line-height: 1.6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.lyric-line--active {
  color: var(--text-1); font-weight: 600; font-size: 0.85rem;
}
.lyric-placeholder {
  display: flex; align-items: center; justify-content: center;
  min-height: 100px; color: var(--text-3); font-size: 0.8rem;
}

/* 歌词渐入动画 */
.lyric-fade-enter-active { transition: all 0.3s ease; }
.lyric-fade-leave-active { transition: all 0.2s ease; }
.lyric-fade-enter-from { opacity: 0; transform: translateY(8px); }
.lyric-fade-leave-to { opacity: 0; transform: translateY(-8px); }

.player-info { margin-bottom: 12px; }
.player-title { font-size: 1.05rem; font-weight: 700; color: var(--text-1); max-width: 260px; margin: 0 auto; }
.player-artist { font-size: 0.82rem; color: var(--text-2); margin-top: 2px; max-width: 260px; margin-left: auto; margin-right: auto; }
.player-mode-tag {
  font-size: 0.68rem; color: #f59e0b; margin-top: 6px;
  padding: 2px 10px; border-radius: 10px;
  background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.15);
  display: inline-block;
}

.progress-row {
  display: flex; align-items: center; gap: 8px; margin-bottom: 14px; padding: 0 8px;
}
.progress-time { font-size: 0.7rem; color: var(--text-3); font-variant-numeric: tabular-nums; min-width: 32px; }
.progress-bar-wrap {
  flex: 1; height: 4px; background: rgba(var(--v-theme-on-surface), 0.08); border-radius: 2px; overflow: hidden;
}
.progress-bar {
  height: 100%; background: rgb(var(--v-theme-primary)); border-radius: 2px;
  transition: width 0.25s linear;
}
.player-controls { display: flex; align-items: center; justify-content: center; gap: 12px; }

/* 推荐流列表 */
.recommend-list { flex: 1; min-height: 0; }
.track-scroll { max-height: 440px; overflow-y: auto; }
.list-loading, .list-empty {
  display: flex; align-items: center; justify-content: center;
  padding: 32px 0; color: var(--text-3); font-size: 0.85rem;
}
.list-empty { text-align: center; }

.track-row {
  display: flex; align-items: center; gap: 10px; padding: 10px 8px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.04);
  cursor: pointer; border-radius: 10px; transition: background 0.15s;
}
.track-row:hover { background: rgba(var(--v-theme-on-surface), 0.03); }
.track-row--active { background: rgba(var(--v-theme-primary), 0.06); border-color: rgba(var(--v-theme-primary), 0.12); }
.track-thumb { width: 40px; height: 40px; border-radius: 8px; object-fit: cover; flex-shrink: 0; }
.track-thumb-placeholder {
  width: 40px; height: 40px; border-radius: 8px; background: rgba(var(--v-theme-on-surface), 0.04);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.track-meta { flex: 1; min-width: 0; }
.track-name { font-size: 0.82rem; font-weight: 600; color: var(--text-1); }
.track-artist-name { font-size: 0.72rem; color: var(--text-2); margin-top: 1px; }
.track-chip { flex-shrink: 0; }

/* 歌单源卡片 */
.source-body { padding: 4px 0; }

/* 播放状态卡片 */
.status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.status-item { text-align: center; }
.status-label { display: block; font-size: 0.68rem; color: var(--text-3); margin-bottom: 2px; }
.status-value { font-size: 0.9rem; font-weight: 700; color: var(--text-1); font-variant-numeric: tabular-nums; }
.status-warn { color: #f59e0b !important; }
.status-ok { color: #4ade80 !important; }

/* ══════════════════════════════════════════════
   Tab 2：DNA谱图 布局
   ══════════════════════════════════════════════ */
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

.rank-badge {
  width: 30px; height: 30px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
  background: rgba(var(--v-theme-on-surface), 0.08); color: var(--text-2);
  font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.rank-badge.rank-gold { background: linear-gradient(135deg, #f59e0b, #f97316); color: #fff; box-shadow: 0 2px 8px rgba(245,158,11,0.3); }
.track-score { text-align: center; flex-shrink: 0; min-width: 42px; }
.score-value { font-size: 1rem; font-weight: 800; font-variant-numeric: tabular-nums; }
.score-unit { font-size: 0.65rem; color: var(--text-3); margin-left: 1px; }
.score-high .score-value { color: #4ade80; }
.score-mid .score-value { color: #fbbf24; }
.score-low .score-value { color: var(--text-3); }

.skeleton-grid { display: grid; grid-template-columns: 1fr 300px; gap: 20px; }
.skeleton-card {
  background: rgba(var(--v-theme-surface), 0.5); border-radius: var(--aero-radius);
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

.empty-state { text-align: center; padding: 48px 20px; }
.empty-icon-wrap {
  width: 80px; height: 80px; margin: 0 auto 16px; border-radius: 50%;
  background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.15);
  display: flex; align-items: center; justify-content: center;
}
.empty-title { font-size: 1.1rem; font-weight: 700; color: var(--text-1); margin-bottom: 6px; }
.empty-desc { color: var(--text-2); font-size: 0.85rem; }

/* ══════════════════════════════════════════════
   Tab 3：权重配置
   ══════════════════════════════════════════════ */
.slot-switcher { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.slot-card {
  --slot-color: #888;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 14px 10px 12px; border-radius: 14px;
  background: rgba(var(--v-theme-surface), 0.45);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.03);
  cursor: pointer; transition: all 0.3s cubic-bezier(0.22,0.61,0.36,1); user-select: none;
}
.slot-card:hover { background: rgba(var(--v-theme-surface), 0.65); transform: translateY(-1px); }
.slot-card--active {
  background: rgba(var(--v-theme-surface), 0.72);
  border-color: color-mix(in srgb, var(--slot-color) 28%, transparent);
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.05), 0 0 20px color-mix(in srgb, var(--slot-color) 12%, transparent);
}
.slot-emoji { font-size: 24px; }
.slot-label { font-size: 12px; font-weight: 600; color: var(--text-1); }
.slot-time { font-size: 10px; color: var(--text-3); }
.slot-card--active .slot-label { color: var(--slot-color); }

.mixer-panel { height: 100%; }
.mixer-body { padding: 4px 0; }
.slider-row { margin-bottom: 26px; transition: opacity 0.25s; }
.slider-row:last-child { margin-bottom: 4px; }
.slider-label { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 4px; }
.slider-name { font-size: 12px; font-weight: 500; color: var(--text-2); }
.slider-value { font-size: 14px; font-weight: 700; color: var(--text-3); transition: all 0.25s; }
.slider-value--active { color: var(--param-color); transform: scale(1.18); }
.slider-row--dragging .slider-name { color: var(--text-1); }
.save-bar { margin-top: 24px; text-align: right; }

/* ══════════════════════════════════════════════
   Tab 4：播放历史
   ══════════════════════════════════════════════ */
.history-table-wrap { overflow-x: auto; }
.history-header {
  display: flex; align-items: center; padding: 8px 12px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  font-size: 0.72rem; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.05em;
}
.history-row {
  display: flex; align-items: center; padding: 10px 12px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.03);
  transition: background 0.15s; font-size: 0.82rem;
}
.history-row:hover { background: rgba(var(--v-theme-on-surface), 0.02); }
.h-col { display: flex; align-items: center; }
.col-track { flex: 2; min-width: 0; flex-direction: column; align-items: flex-start; }
.col-time { flex: 1; justify-content: center; gap: 3px; }
.col-skip { flex: 0.7; justify-content: center; }
.col-date { flex: 0.8; justify-content: flex-end; }

.ht-title { font-weight: 600; color: var(--text-1); max-width: 100%; }
.ht-artist { font-size: 0.72rem; color: var(--text-2); max-width: 100%; }
.ht-dur { font-weight: 700; font-variant-numeric: tabular-nums; color: var(--text-1); }
.ht-sep { color: var(--text-3); }
.ht-total { color: var(--text-3); font-variant-numeric: tabular-nums; }
.ht-date { color: var(--text-3); font-size: 0.75rem; white-space: nowrap; }

.skip-tag {
  font-size: 0.7rem; font-weight: 600; padding: 2px 8px; border-radius: 10px; white-space: nowrap;
}
.skip-tag--yes { background: rgba(245,158,11,0.1); color: #d97706; border: 1px solid rgba(245,158,11,0.2); }
.skip-tag--no { background: rgba(74,222,128,0.08); color: #4ade80; border: 1px solid rgba(74,222,128,0.15); }

.pagination-row { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 16px; }

/* ══════════════════════════════════════════════
   动画
   ══════════════════════════════════════════════ */
.track-list-enter-active, .track-list-leave-active { transition: all 0.3s cubic-bezier(0.4,0,0.2,1); }
.track-list-enter-from { opacity: 0; transform: translateY(-8px); }
.track-list-leave-to { opacity: 0; transform: translateX(-12px); }

/* ══════════════════════════════════════════════
   响应式
   ══════════════════════════════════════════════ */
@media (max-width: 860px) {
  .discover-layout, .dna-layout, .skeleton-grid { grid-template-columns: 1fr; }
  .slot-switcher { grid-template-columns: repeat(2, 1fr); }
  .segment-btn { padding: 8px 12px; font-size: 0.78rem; }
  .segment-icon { font-size: 0.9rem; }
  .chart-wrap { height: 300px; }
}
</style>
