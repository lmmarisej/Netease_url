<template>
  <div class="glass-card player-card">
    <!-- 封面 + 歌词 左右布局 -->
    <div class="player-main">
      <div class="cd-wrap" :class="{ 'cd-wrap--playing': isPlaying }">
        <div class="cd-disc">
          <img v-if="coverUrl" :src="coverUrl" class="cd-cover" alt="封面" />
          <div v-else class="cd-placeholder">
            <v-icon size="40" color="rgba(var(--v-theme-on-surface),0.2)">mdi-music</v-icon>
          </div>
          <div class="cd-hole" />
        </div>
      </div>
      <div class="lyrics-side">
        <div v-if="lyricLines.length" class="lyrics-scroll">
          <TransitionGroup name="lyric-fade" tag="div">
            <div
              v-for="line in lyricLines"
              :key="line.idx"
              class="lyric-line"
              :class="{ 'lyric-line--active': line.idx === activeIdx }"
            >{{ line.text }}</div>
          </TransitionGroup>
        </div>
        <div v-else-if="lyricLoading" class="lyric-placeholder">加载歌词中...</div>
        <div v-else class="lyric-placeholder">暂无歌词</div>
      </div>
    </div>

    <!-- 歌曲信息 -->
    <div class="player-info">
      <div class="player-title text-truncate">{{ title || '选择一首歌曲' }}</div>
      <div class="player-artist text-truncate">{{ artist || '—' }}</div>
    </div>

    <!-- 进度条 -->
    <div class="progress-row">
      <span class="progress-time">{{ formatTime(playElapsed) }}</span>
      <div class="progress-bar-wrap" ref="progressRef" @click="onProgressClick">
        <div class="progress-bar" :style="{ width: progressPercent + '%' }" />
      </div>
      <span class="progress-time">{{ formatTime(duration) }}</span>
    </div>

    <!-- 控制按钮 -->
    <div class="player-controls">
      <v-btn icon="mdi-skip-previous" variant="text" size="small" :disabled="!canPrev" @click="$emit('prev')" />
      <v-btn icon size="large" :color="isPlaying ? 'primary' : undefined" variant="flat" @click="$emit('toggle-play')">
        <v-icon size="28">{{ isPlaying ? 'mdi-pause' : 'mdi-play' }}</v-icon>
      </v-btn>
      <v-btn icon="mdi-skip-next" variant="text" size="small" :disabled="!canNext" @click="$emit('next')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

export interface LyricLineView {
  idx: number
  text: string
}

const props = defineProps<{
  coverUrl: string
  title: string
  artist: string
  duration: number
  isPlaying: boolean
  playElapsed: number
  progressPercent: number
  canPrev: boolean
  canNext: boolean
  lyricLines: LyricLineView[]
  activeIdx: number
  lyricLoading: boolean
  formatTime: (sec: number) => string
}>()

const emit = defineEmits<{
  (e: 'toggle-play'): void
  (e: 'prev'): void
  (e: 'next'): void
  (e: 'seek', ratio: number): void
}>()

const progressRef = ref<HTMLElement | null>(null)

function onProgressClick(e: MouseEvent) {
  if (!progressRef.value || !props.duration) return
  const rect = progressRef.value.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  emit('seek', ratio)
}
</script>

<style scoped>
.player-card { text-align: center; }
.player-main { display: flex !important; gap: 16px; align-items: stretch; margin-bottom: 14px; justify-content: center; }
.player-info { margin-bottom: 12px; }
.player-title { font-size: 1.05rem; font-weight: 700; color: rgb(var(--v-theme-on-surface)); max-width: 260px; margin: 0 auto; }
.player-artist { font-size: 0.82rem; color: rgba(var(--v-theme-on-surface), 0.6); margin-top: 2px; max-width: 260px; margin: 0 auto; }

.cd-wrap { flex: 0 0 auto; width: 150px; height: 150px; align-self: center; display: flex; align-items: center; justify-content: center; }
.cd-disc { width: 140px; height: 140px; border-radius: 50%; position: relative; background: conic-gradient(from 0deg, rgba(255,255,255,0.06), rgba(255,255,255,0.12), rgba(0,0,0,0.08), rgba(255,255,255,0.06)); box-shadow: 0 4px 24px rgba(0,0,0,0.2), inset 0 0 0 1px rgba(255,255,255,0.06); display: flex; align-items: center; justify-content: center; }
.cd-wrap--playing .cd-disc { animation: cd-spin 20s linear infinite; }
.cd-cover { width: 82px; height: 82px; border-radius: 50%; object-fit: cover; z-index: 1; box-shadow: 0 2px 12px rgba(0,0,0,0.3); }
.cd-placeholder { width: 82px; height: 82px; border-radius: 50%; background: rgba(var(--v-theme-on-surface),0.04); display: flex; align-items: center; justify-content: center; z-index: 1; }
.cd-hole { position: absolute; width: 16px; height: 16px; border-radius: 50%; background: rgb(var(--v-theme-surface)); box-shadow: inset 0 1px 2px rgba(0,0,0,0.3), 0 1px 0 rgba(255,255,255,0.05); z-index: 2; top: 50%; left: 50%; transform: translate(-50%,-50%); }
@keyframes cd-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.lyrics-side { flex: 0 1 240px; min-width: 0; height: 150px; display: flex; flex-direction: column; justify-content: center; }
.lyrics-scroll { overflow: hidden; padding: 4px 0; height: 100%; }
.lyric-line { padding: 4px 8px; font-size: 0.78rem; color: rgba(var(--v-theme-on-surface),0.38); border-radius: 4px; transition: all 0.35s; line-height: 1.6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.lyric-line--active { color: rgb(var(--v-theme-on-surface)); font-weight: 600; font-size: 0.85rem; }
.lyric-placeholder { display: flex; align-items: center; justify-content: center; min-height: 100px; color: rgba(var(--v-theme-on-surface),0.38); font-size: 0.8rem; }
.lyric-fade-enter-active { transition: all 0.3s ease; }
.lyric-fade-leave-active { transition: all 0.2s ease; }
.lyric-fade-enter-from { opacity: 0; transform: translateY(8px); }
.lyric-fade-leave-to { opacity: 0; transform: translateY(-8px); }

.progress-row { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; padding: 0 8px; }
.progress-time { font-size: 0.7rem; color: rgba(var(--v-theme-on-surface),0.38); font-variant-numeric: tabular-nums; min-width: 32px; }
.progress-bar-wrap { flex: 1; height: 4px; background: rgba(var(--v-theme-on-surface),0.08); border-radius: 2px; overflow: hidden; cursor: pointer; }
.progress-bar { height: 100%; background: rgb(var(--v-theme-primary)); border-radius: 2px; transition: width 0.25s linear; }
.player-controls { display: flex; align-items: center; justify-content: center; gap: 12px; }
</style>
