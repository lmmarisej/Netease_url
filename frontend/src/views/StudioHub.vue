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
      <DiscoverTab :player="playerApi" />
    </div>

    <!-- ==================== Tab 2：DNA谱图 ==================== -->
    <div v-if="activeTab === 'dna'" class="tab-content">
      <DnaTab @go-discover-top-50="goDiscoverTop50" />
    </div>

    <!-- ==================== Tab 3：权重配置 ==================== -->
    <div v-if="activeTab === 'mixer'" class="tab-content">
      <MixerTab />
    </div>

    <!-- ==================== Tab 4：播放历史 ==================== -->
    <div v-if="activeTab === 'history'" class="tab-content">
      <HistoryTab />
    </div>

    <!-- 隐藏的音频元素用于播放跟踪 -->
    <audio
      ref="audioRef"
      @timeupdate="playerApi.onTimeUpdate"
      @ended="playerApi.onTrackEnded"
      @play="playerApi.isPlaying.value = true"
      @pause="playerApi.isPlaying.value = false"
    />
  </div>
</template>

<script setup>
/* ================================================================
   StudioHub.vue — 音乐工作室主页面（薄壳）
   ================================================================
   职责：分段控制器 + Tab 切换 + 音频元素 + 共享播放器状态
   各 Tab 的具体实现拆分到 components/studio/ 目录
   共享播放器逻辑拆分到 composables/useStudioPlayer.js
================================================================ */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import DiscoverTab from '@/components/studio/DiscoverTab.vue'
import DnaTab from '@/components/studio/DnaTab.vue'
import MixerTab from '@/components/studio/MixerTab.vue'
import HistoryTab from '@/components/studio/HistoryTab.vue'
import { useStudioPlayer } from '@/composables/useStudioPlayer.js'

// ── 顶部 Tab ──
const tabs = [
  { key: 'discover', icon: '🎵', label: '发现音乐' },
  { key: 'dna', icon: '🧬', label: 'DNA谱图' },
  { key: 'mixer', icon: '🎛️', label: '权重配置' },
  { key: 'history', icon: '📜', label: '播放历史' },
]
const activeTab = ref('discover')

// ── 音频元素 ──
const audioRef = ref(null)

// ── 播放器状态（共享 composable） ──
const playerApi = useStudioPlayer(audioRef)

// ── DNA → 发现音乐 跳转 ──
function goDiscoverTop50() {
  activeTab.value = 'discover'
  playerApi.sourceType.value = 'top50'
  playerApi.fetchRecommend()
}

// ── 生命周期 ──
onMounted(() => {
  playerApi.fetchRecommend()
  playerApi.initLikedIds()
})

onBeforeUnmount(() => {
  playerApi.stopPlayTimer()
  if (playerApi.currentTrack.track_id) playerApi.logPlayback(true)
})
</script>

<style scoped>
/* ══════════════════════════════════════════════
   Aero-Material 全局基调 & iOS 分段控制器
   子组件通过 CSS 变量继承主题
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

/* ── iOS 分段控制器 ── */
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

/* ── Tab 内容容器 ── */
.tab-content {
  /* 子组件自行处理内部布局 */
}

/* ── 响应式 ── */
@media (max-width: 860px) {
  .segment-btn { padding: 8px 12px; font-size: 0.78rem; }
  .segment-icon { font-size: 0.9rem; }
}
</style>
