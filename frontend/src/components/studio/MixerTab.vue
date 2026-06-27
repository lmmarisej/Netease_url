<template>
  <div>
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
</template>

<script setup>
/* ================================================================
   MixerTab.vue — 「权重配置」Tab
   ================================================================
   自包含：4 个时间段槽位 + 3 组参数面板 + 保存/加载
================================================================ */
import { ref, reactive, computed, onMounted } from 'vue'
import { getWeightConfig, saveWeightConfig } from '@/api/index.js'

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

onMounted(loadWeights)
</script>

<style scoped>
/* ── 毛玻璃卡片 ── */
.glass-card {
  background: var(--aero-bg, rgba(var(--v-theme-surface), 0.55));
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--aero-border, rgba(var(--v-theme-on-surface), 0.06));
  border-radius: var(--aero-radius, 20px);
  box-shadow: var(--aero-shadow, 0 4px 24px rgba(0,0,0,0.06));
  padding: 18px;
  transition: border-color 0.3s;
}
.glass-card:hover { border-color: rgba(var(--v-theme-on-surface), 0.1); }
.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.card-title { font-weight: 700; font-size: 0.9rem; color: var(--text-1, rgb(var(--v-theme-on-surface))); }

/* ── 时段切换器 ── */
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

@media (max-width: 860px) {
  .slot-switcher { grid-template-columns: repeat(2, 1fr); }
}
</style>
