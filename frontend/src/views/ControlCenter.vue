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
        <div class="player-col">
          <PlayerCard
            :cover-url="currentTrack.coverUrl"
            :title="currentTrack.title"
            :artist="currentTrack.artist"
            :duration="currentTrack.duration"
            :is-playing="isPlaying"
            :play-elapsed="playElapsed"
            :progress-percent="progressPercent"
            :can-prev="playlistIndex > 0"
            :can-next="playlistIndex < playlist.length - 1"
            :lyric-lines="visibleLyricLines"
            :active-idx="activeLyricIdx"
            :lyric-loading="lyricLoading"
            :format-time="formatTime"
            @toggle-play="togglePlay"
            @prev="prevTrack"
            @next="nextTrack"
            @seek="seekProgress"
          />

          <div class="glass-card recommend-list">
            <div class="card-header">
              <v-icon size="18" color="#a78bfa">mdi-playlist-music</v-icon>
              <span class="card-title">推荐流</span>
              <v-spacer />
              <span class="card-badge" v-if="recommendTracks.length">{{ recommendTracks.length }} 首</span>
            </div>
            <div v-if="recommendLoading" class="list-loading">
              <v-progress-circular indeterminate size="20" width="2" color="primary" />
              <span class="text-caption text-medium-emphasis ml-2">加载推荐...</span>
            </div>
            <div v-else-if="!recommendTracks.length" class="list-empty">选择歌单源并刷新，发现新音乐</div>
            <TransitionGroup v-else name="track-list" tag="div" class="track-scroll">
              <div
                v-for="t in recommendTracks" :key="t.track_id"
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
                <v-chip size="x-small" variant="tonal" :color="t.bpm < 0 ? 'warning' : 'success'" class="track-chip">
                  {{ t.bpm < 0 ? '待扫描' : '已分析' }}
                </v-chip>
              </div>
            </TransitionGroup>
          </div>
        </div>

        <div class="source-col">
          <div class="glass-card source-card">
            <div class="card-header">
              <v-icon size="18" color="#f59e0b">mdi-music-circle</v-icon>
              <span class="card-title">歌单源</span>
            </div>
            <div class="source-body">
              <v-select
                v-model="sourceType" :items="sourceOptions"
                label="推荐来源" variant="solo-filled" density="comfortable"
                hide-details rounded="lg" class="mb-4"
              />
              <v-text-field
                v-if="sourceType === 'custom_playlist'" v-model="customPlaylistId"
                label="歌单 ID" placeholder="输入网易云歌单 ID"
                variant="solo-filled" density="comfortable" hide-details rounded="lg" class="mb-4"
              />
              <v-btn block color="primary" variant="flat" prepend-icon="mdi-refresh" :loading="recommendLoading" @click="fetchRecommend">
                刷新推荐流
              </v-btn>
            </div>
          </div>

          <div class="glass-card status-card" v-if="currentTrack.track_id">
            <div class="card-header">
              <v-icon size="16" :color="isPlaying ? 'success' : 'rgba(var(--v-theme-on-surface),0.4)'">
                {{ isPlaying ? 'mdi-play-circle' : 'mdi-pause-circle' }}
              </v-icon>
              <span class="card-title">播放状态</span>
            </div>
            <div class="status-grid">
              <div class="status-item"><span class="status-label">累计聆听</span><span class="status-value">{{ formatTime(playedAccum) }}</span></div>
              <div class="status-item"><span class="status-label">总时长</span><span class="status-value">{{ formatTime(currentTrack.duration) }}</span></div>
              <div class="status-item"><span class="status-label">位置</span><span class="status-value">{{ progressPercent.toFixed(0) }}%</span></div>
              <div class="status-item">
                <span class="status-label">跳过</span>
                <span class="status-value" :class="skipClass">{{ skipText }}</span>
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
                <v-spacer /><span class="card-badge">实时分析</span>
              </div>
              <div class="chart-wrap">
                <v-chart :option="radarOption" autoresize style="width:100%;height:100%" />
              </div>
            </div>
          </div>
          <div class="dna-right">
            <div class="glass-card">
              <div class="card-header">
                <v-icon size="18" color="#f59e0b">mdi-fire</v-icon>
                <span class="card-title">TOP 10 共鸣单曲</span>
                <v-spacer /><span class="card-badge accent">{{ topTracks.length }} 首</span>
              </div>
              <div class="track-scroll">
                <div v-for="t in topTracks" :key="t.rank" class="track-row">
                  <div class="rank-badge" :class="t.rank <= 3 ? 'rank-gold' : ''">
                    {{ t.rank === 1 ? '🥇' : t.rank === 2 ? '🥈' : t.rank === 3 ? '🥉' : t.rank }}
                  </div>
                  <div class="track-meta">
                    <div class="track-name text-truncate">{{ t.title }}</div>
                    <div class="track-artist-name text-truncate">{{ t.artist }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- ==================== Tab 3：权重配置 ==================== -->
    <div v-if="activeTab === 'mixer'" class="tab-content">
      <MixerConsole
        :slots="SLOTS"
        :panels="MIXER_PANELS"
        :active-slot="mixer.activeSlot.value"
        :weights="mixer.currentWeights.value"
        :dragging-key="mixer.draggingKey.value"
        :saving="mixer.saving.value"
        @update:active-slot="mixer.activeSlot.value = $event"
        @update:weight="(k, v) => mixer.currentWeights.value[k] = v"
        @drag-start="mixer.draggingKey.value = $event"
        @drag-end="mixer.draggingKey.value = null"
        @save="mixer.saveWeights()"
      />
    </div>

    <!-- ==================== Tab 4：播放历史 ==================== -->
    <div v-if="activeTab === 'history'" class="tab-content">
      <div class="glass-card">
        <div class="card-header">
          <v-icon size="18" color="#6b9e78">mdi-history</v-icon>
          <span class="card-title">播放历史</span>
          <v-spacer />
          <span class="card-badge" v-if="history.total.value">{{ history.total.value }} 条</span>
        </div>
        <div v-if="history.loading.value" class="list-loading">
          <v-progress-circular indeterminate size="20" width="2" color="primary" />
        </div>
        <div v-else-if="!history.items.value.length" class="list-empty">暂无播放记录</div>
        <div v-else class="history-table-wrap">
          <div class="history-header">
            <span class="h-col col-track">歌曲</span>
            <span class="h-col col-time">播放时长</span>
            <span class="h-col col-skip">状态</span>
            <span class="h-col col-date">时间</span>
          </div>
          <div v-for="item in history.items.value" :key="item.id" class="history-row">
            <div class="h-col col-track">
              <div class="ht-title text-truncate">{{ item.title }}</div>
              <div class="ht-artist text-truncate">{{ item.artist }}</div>
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
            <div class="h-col col-date"><span class="ht-date">{{ history.formatDate(item.timestamp) }}</span></div>
          </div>
        </div>
        <div v-if="history.total.value > history.pageSize" class="pagination-row">
          <v-btn variant="text" size="small" :disabled="history.page.value <= 1" @click="history.page.value--; history.fetchHistory()">上一页</v-btn>
          <span class="text-caption">{{ history.page.value }} / {{ Math.ceil(history.total.value / history.pageSize) }}</span>
          <v-btn variant="text" size="small" :disabled="history.page.value >= Math.ceil(history.total.value / history.pageSize)" @click="history.page.value++; history.fetchHistory()">下一页</v-btn>
        </div>
      </div>
    </div>

    <audio ref="audioRef" @timeupdate="onTimeUpdate" @ended="onTrackEnded" @play="isPlaying = true" @pause="isPlaying = false" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useTheme } from 'vuetify'

// ── Composables ──
import { useMusicPlayer } from '@/composables/useMusicPlayer.js'
import { useWeightMixer, SLOTS, MIXER_PANELS } from '@/composables/useWeightMixer.js'
import { useDnaRadar } from '@/composables/useDnaRadar.js'
import { usePlaybackHistory } from '@/composables/usePlaybackHistory.js'

// ── 子组件 ──
import PlayerCard from '@/components/PlayerCard.vue'
import MixerConsole from '@/components/MixerConsole.vue'

// ── 工具 ──
import { buildRadarOption } from '@/utils/radarConfig.js'

// ── ECharts ──
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
use([CanvasRenderer, RadarChart, TooltipComponent, LegendComponent])

// ═══════════════ 主题 ═══════════════
const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)

// ═══════════════ Tab ═══════════════
const tabs = [
  { key: 'discover', icon: '🎵', label: '发现音乐' },
  { key: 'dna', icon: '🧬', label: 'DNA谱图' },
  { key: 'mixer', icon: '🎛️', label: '权重配置' },
  { key: 'history', icon: '📜', label: '播放历史' },
]
const activeTab = ref('discover')

// ═══════════════ 音频元素 ═══════════════
const audioRef = ref<HTMLAudioElement | null>(null)

// ═══════════════ Composable 实例 ═══════════════
const player = useMusicPlayer(audioRef)
const mixer = useWeightMixer()
const dna = useDnaRadar()
const history = usePlaybackHistory()

// 解构（保持模板中可直接使用）
const {
  isPlaying, playElapsed, playedAccum, currentTrack, progressPercent,
  recommendTracks, recommendLoading, playlist, playlistIndex,
  sourceType, customPlaylistId,
  lyricLines: _lyricLines, activeLyricIdx, lyricLoading, visibleLyricLines,
  playTrack, togglePlay, nextTrack, prevTrack, seekProgress,
  onTimeUpdate, onTrackEnded, fetchRecommend, formatTime,
} = player

const { dnaLoading: _dnaLoading, dnaError, dnaEmpty, trackCount: _tc, radarData, topTracks } = dna

// ── 跳过状态 ──
const skipText = computed(() => {
  if (!currentTrack.duration) return '—'
  if (playElapsed.value < 10 || progressPercent.value < 20) return '⚠ 即将跳过'
  return '正常'
})
const skipClass = computed(() => !currentTrack.duration ? '' : (playElapsed.value < 10 || progressPercent.value < 20) ? 'status-warn' : 'status-ok')

// ── ECharts 雷达图 ──
const radarOption = computed(() => buildRadarOption(radarData, isDark.value))

// ── 歌单源下拉选项 ──
const sourceOptions = [
  { title: '🔥 网易云热榜', value: 'hot_list' },
  { title: '📋 自定义歌单', value: 'custom_playlist' },
]

// ═══════════════ Tab 切换懒加载 ═══════════════
watch(activeTab, (tab) => {
  if (tab === 'dna') dna.loadData()
  if (tab === 'mixer') mixer.loadWeights()
  if (tab === 'history') history.fetchHistory()
})

// ═══════════════ 生命周期 ═══════════════
onMounted(() => { fetchRecommend() })
onBeforeUnmount(() => { })
</script>

<style scoped>
/*
 *  样式继承自 StudioHub.vue 的 Aero-Material 设计系统。
 *  子组件 PlayerCard.vue / MixerConsole.vue 各自携带 scoped 样式，
 *  全局卡片/布局/历史表格样式在此处定义。
 */

/* ═══════════════ 全局基调 ═══════════════ */
.studio-hub {
  --aero-bg: rgba(var(--v-theme-surface), 0.55);
  --aero-border: rgba(var(--v-theme-on-surface), 0.06);
  --aero-radius: 20px;
  --aero-shadow: 0 4px 24px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.04);
  --text-1: rgb(var(--v-theme-on-surface));
  --text-2: rgba(var(--v-theme-on-surface), 0.6);
  --text-3: rgba(var(--v-theme-on-surface), 0.38);
  color: var(--text-1);
}
</style>
