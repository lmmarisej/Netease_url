<template>
  <div class="weight-settings">
    <!-- 背景层 -->
    <div class="weight-settings__bg" />

    <!-- 标题 -->
    <div class="d-flex align-center mb-6">
      <v-icon size="36" color="primary" class="mr-3">mdi-tune-vertical-variant</v-icon>
      <div>
        <h1 class="text-h4 font-weight-bold mb-1">权重调音台</h1>
        <p class="text-body-2 text-medium-emphasis">按时间段精细调节音乐推荐权重，打造你的专属听感配方</p>
      </div>
    </div>

    <!-- 时段切换卡片 -->
    <div class="slot-switcher mb-8">
      <div
        v-for="slot in slots"
        :key="slot.key"
        class="slot-card"
        :class="{ 'slot-card--active': activeSlot === slot.key }"
        :style="{ '--slot-color': slot.color }"
        @click="activeSlot = slot.key"
      >
        <span class="slot-card__icon">{{ slot.icon }}</span>
        <span class="slot-card__label">{{ slot.label }}</span>
        <span class="slot-card__time">{{ slot.time }}</span>
      </div>
    </div>

    <!-- 控制面板 -->
    <v-row>
      <!-- 板块一：声学与声源分离 -->
      <v-col cols="12" md="6" xl="4">
        <div class="mixer-panel">
          <div class="mixer-panel__header">
            <v-icon size="22" color="#e09953" class="mr-2">mdi-waveform</v-icon>
            <span class="text-subtitle-1 font-weight-bold">声学与声源分离</span>
            <v-chip size="x-small" variant="tonal" color="#e09953" class="ml-2">Librosa / Demucs</v-chip>
          </div>
          <div class="mixer-panel__body">
            <div
              v-for="param in panel1"
              :key="param.key"
              class="slider-row"
              :class="{ 'slider-row--dragging': draggingKey === param.key }"
            >
              <div class="slider-row__label">
                <span class="slider-row__name">{{ param.label }}</span>
                <span
                  class="slider-row__value"
                  :class="{ 'slider-row__value--active': draggingKey === param.key }"
                  :style="{ '--param-color': param.color }"
                >
                  {{ currentWeights[param.key]?.toFixed(1) }}
                </span>
              </div>
              <v-slider
                :model-value="currentWeights[param.key]"
                :min="0"
                :max="2"
                :step="0.1"
                :color="param.color"
                track-size="4"
                thumb-size="18"
                hide-details
                density="compact"
                @update:model-value="(v) => currentWeights[param.key] = v"
                @start="draggingKey = param.key"
                @end="draggingKey = null"
              />
            </div>
          </div>
        </div>
      </v-col>

      <!-- 板块二：流派与乐器 -->
      <v-col cols="12" md="6" xl="4">
        <div class="mixer-panel">
          <div class="mixer-panel__header">
            <v-icon size="22" color="#9b8ec4" class="mr-2">mdi-music-clef-treble</v-icon>
            <span class="text-subtitle-1 font-weight-bold">流派与乐器</span>
            <v-chip size="x-small" variant="tonal" color="#9b8ec4" class="ml-2">PANNs</v-chip>
          </div>
          <div class="mixer-panel__body">
            <div
              v-for="param in panel2"
              :key="param.key"
              class="slider-row"
              :class="{ 'slider-row--dragging': draggingKey === param.key }"
            >
              <div class="slider-row__label">
                <span class="slider-row__name">{{ param.label }}</span>
                <span
                  class="slider-row__value"
                  :class="{ 'slider-row__value--active': draggingKey === param.key }"
                  :style="{ '--param-color': param.color }"
                >
                  {{ currentWeights[param.key]?.toFixed(1) }}
                </span>
              </div>
              <v-slider
                :model-value="currentWeights[param.key]"
                :min="0"
                :max="2"
                :step="0.1"
                :color="param.color"
                track-size="4"
                thumb-size="18"
                hide-details
                density="compact"
                @update:model-value="(v) => currentWeights[param.key] = v"
                @start="draggingKey = param.key"
                @end="draggingKey = null"
              />
            </div>
          </div>
        </div>
      </v-col>

      <!-- 板块三：歌词高级意境 -->
      <v-col cols="12" md="6" xl="4">
        <div class="mixer-panel">
          <div class="mixer-panel__header">
            <v-icon size="22" color="#d4956b" class="mr-2">mdi-drama-masks</v-icon>
            <span class="text-subtitle-1 font-weight-bold">歌词高级意境</span>
            <v-chip size="x-small" variant="tonal" color="#d4956b" class="ml-2">Ollama LLM</v-chip>
          </div>
          <div class="mixer-panel__body">
            <div
              v-for="param in panel3"
              :key="param.key"
              class="slider-row"
              :class="{ 'slider-row--dragging': draggingKey === param.key }"
            >
              <div class="slider-row__label">
                <span class="slider-row__name">{{ param.label }}</span>
                <span
                  class="slider-row__value"
                  :class="{ 'slider-row__value--active': draggingKey === param.key }"
                  :style="{ '--param-color': param.color }"
                >
                  {{ currentWeights[param.key]?.toFixed(1) }}
                </span>
              </div>
              <v-slider
                :model-value="currentWeights[param.key]"
                :min="0"
                :max="2"
                :step="0.1"
                :color="param.color"
                track-size="4"
                thumb-size="18"
                hide-details
                density="compact"
                @update:model-value="(v) => currentWeights[param.key] = v"
                @start="draggingKey = param.key"
                @end="draggingKey = null"
              />
            </div>
          </div>
        </div>
      </v-col>
    </v-row>

    <!-- 保存按钮 -->
    <div class="save-fab">
      <v-btn
        size="large"
        color="primary"
        :loading="saving"
        prepend-icon="mdi-content-save"
        @click="saveWeights"
      >
        保存权重配置
      </v-btn>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getWeightConfig, saveWeightConfig } from '@/api/index.js'

// ==================== 时段定义 ====================
const slots = [
  { key: 'morning', icon: '🌅', label: '元气清晨', time: '07:00-09:00', color: '#c4956a' },
  { key: 'daytime', icon: '💻', label: '高效白昼', time: '09:00-18:00', color: '#6a9fb5' },
  { key: 'evening', icon: '🌆', label: '多巴胺黄昏', time: '18:00-22:00', color: '#b87d8d' },
  { key: 'midnight', icon: '🌌', label: '静谧深夜', time: '22:00-07:00', color: '#8b7fba' },
]

const activeSlot = ref('morning')
const draggingKey = ref(null)

// ==================== 三大板块参数定义 ====================
const panel1 = [
  { key: 'tempo', label: 'Tempo · 节奏速度', color: '#e09953' },
  { key: 'energy', label: 'Energy · 能量强度', color: '#cd5c5c' },
  { key: 'vocal_ratio', label: 'Vocal Ratio · 人声比例', color: '#6b9e78' },
  { key: 'bass_intensity', label: 'Bass Int. · 低音强度', color: '#b8738d' },
  { key: 'acousticness', label: 'Acousticness · 原声度', color: '#70a1b5' },
]

const panel2 = [
  { key: 'electronic_score', label: 'Electronic · 电子乐', color: '#9b8ec4' },
  { key: 'rock_score', label: 'Rock · 摇滚乐', color: '#c46b6b' },
  { key: 'instrument_pureness', label: 'Instrument Pure. · 器乐纯净度', color: '#5f9ea0' },
]

const panel3 = [
  { key: 'midnight_emo', label: 'Midnight Emo · 深夜情绪', color: '#d4956b' },
  { key: 'guofeng_vibe', label: 'Guofeng Vibe · 国风意境', color: '#c4a35a' },
]

// ==================== 权重数据 ====================
// 各时段默认权重 — 按情绪氛围精细调校
const DEFAULT_WEIGHTS = {
  morning: {
    // 🌅 元气清晨：轻柔唤醒，原声自然，拒绝刺激
    tempo: 0.8, energy: 0.6, vocal_ratio: 1.0, bass_intensity: 0.5,
    acousticness: 1.5, electronic_score: 0.3, rock_score: 0.3,
    instrument_pureness: 1.3, midnight_emo: 0.2, guofeng_vibe: 1.2,
  },
  daytime: {
    // 💻 高效白昼：律动聚焦，人声清晰，适度电子提神
    tempo: 1.2, energy: 1.0, vocal_ratio: 1.1, bass_intensity: 0.9,
    acousticness: 0.7, electronic_score: 1.1, rock_score: 0.8,
    instrument_pureness: 1.4, midnight_emo: 0.4, guofeng_vibe: 1.0,
  },
  evening: {
    // 🌆 多巴胺黄昏：高能释放，重低音轰炸，电子拉满
    tempo: 1.5, energy: 1.6, vocal_ratio: 1.2, bass_intensity: 1.5,
    acousticness: 0.4, electronic_score: 1.5, rock_score: 1.2,
    instrument_pureness: 0.7, midnight_emo: 1.1, guofeng_vibe: 0.8,
  },
  midnight: {
    // 🌌 静谧深夜：慢速沉浸，人声贴耳，情绪深邃
    tempo: 0.5, energy: 0.3, vocal_ratio: 1.4, bass_intensity: 0.7,
    acousticness: 1.3, electronic_score: 0.6, rock_score: 0.2,
    instrument_pureness: 1.2, midnight_emo: 1.8, guofeng_vibe: 1.1,
  },
}

// 存储所有时段的完整权重数据，初始化使用默认值
const allWeights = reactive(structuredClone(DEFAULT_WEIGHTS))

// 当前选中时段的权重（绑定到滑块）
const currentWeights = computed({
  get: () => allWeights[activeSlot.value] || {},
  set: (val) => { allWeights[activeSlot.value] = val },
})

// ==================== 持久化 ====================
const saving = ref(false)

async function loadWeights() {
  try {
    const data = await getWeightConfig()
    if (data && data.slots) {
      for (const [key, slot] of Object.entries(data.slots)) {
        if (allWeights[key] && slot.weights) {
          // 服务端权重覆盖默认值，缺失字段保留默认
          allWeights[key] = { ...DEFAULT_WEIGHTS[key], ...slot.weights }
        }
      }
    }
  } catch (e) {
    // 加载失败保留默认值，不影响使用
  }
}

async function saveWeights() {
  saving.value = true
  try {
    const payload = {
      slots: {},
    }
    for (const [key, weights] of Object.entries(allWeights)) {
      const slotDef = slots.find(s => s.key === key)
      payload.slots[key] = {
        label: slotDef ? `${slotDef.label} (${slotDef.time})` : key,
        weights: { ...weights },
      }
    }
    await saveWeightConfig(payload)
    window.__snackbar?.('权重配置已保存', 'success')
  } catch (e) {
    window.__snackbar?.('保存失败: ' + (e.message || '未知错误'), 'error')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadWeights()
})
</script>

<style scoped>
/* ============================================================
   权重调音台 — 暗黑调音台风格
   ============================================================ */

.weight-settings {
  position: relative;
  min-height: calc(100vh - 200px);
}

/* 背景层：暗色渐变 + 微弱噪点纹理 */
.weight-settings__bg {
  position: fixed;
  inset: 0;
  z-index: -1;
  background:
    radial-gradient(ellipse at 20% 20%, rgba(196, 149, 106, 0.06) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 50%, rgba(155, 142, 196, 0.05) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 80%, rgba(184, 125, 141, 0.04) 0%, transparent 50%),
    rgb(var(--v-theme-background));
}

/* ==================== 时段切换器 ==================== */
.slot-switcher {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.slot-card {
  --slot-color: #888;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 16px 12px 14px;
  border-radius: 16px;
  background: rgba(var(--v-theme-surface), 0.45);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition: all 0.35s cubic-bezier(0.22, 0.61, 0.36, 1);
  user-select: none;
}

.slot-card:hover {
  background: rgba(var(--v-theme-surface), 0.65);
  border-color: rgba(var(--v-theme-on-surface), 0.1);
  transform: translateY(-1px);
}

.slot-card--active {
  background: rgba(var(--v-theme-surface), 0.75);
  border-color: color-mix(in srgb, var(--slot-color) 28%, transparent);
  box-shadow:
    inset 0 1px 1px rgba(255, 255, 255, 0.06),
    0 0 24px color-mix(in srgb, var(--slot-color) 12%, transparent);
}

.slot-card__icon {
  font-size: 26px;
  line-height: 1;
}

.slot-card__label {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
  letter-spacing: 0.02em;
}

.slot-card__time {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  font-variant-numeric: tabular-nums;
}

/* 激活态微弱发光 */
.slot-card--active .slot-card__label {
  color: var(--slot-color);
}

.slot-card--active .slot-card__time {
  color: color-mix(in srgb, var(--slot-color) 70%, rgba(var(--v-theme-on-surface), 0.4));
}

/* ==================== 控制面板卡片 ==================== */
.mixer-panel {
  border-radius: 20px;
  background: rgba(var(--v-theme-surface), 0.35);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.04);
  overflow: hidden;
  height: 100%;
  transition: border-color 0.35s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.mixer-panel:hover {
  border-color: rgba(var(--v-theme-on-surface), 0.1);
}

.mixer-panel__header {
  display: flex;
  align-items: center;
  padding: 18px 20px 14px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.05);
  color: rgb(var(--v-theme-on-surface));
}

.mixer-panel__body {
  padding: 8px 20px 20px;
}

/* ==================== 滑块行 ==================== */
.slider-row {
  margin-bottom: 28px;
  transition: opacity 0.25s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.slider-row:last-child {
  margin-bottom: 4px;
}

.slider-row__label {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 4px;
}

.slider-row__name {
  font-size: 13px;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.75);
  letter-spacing: 0.01em;
}

.slider-row__value {
  font-size: 14px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: rgba(var(--v-theme-on-surface), 0.55);
  transition: color 0.25s cubic-bezier(0.22, 0.61, 0.36, 1),
              transform 0.25s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.slider-row__value--active {
  color: var(--param-color);
  transform: scale(1.18);
}

/* 拖拽时整行微亮 */
.slider-row--dragging .slider-row__name {
  color: rgba(var(--v-theme-on-surface), 0.9);
}

/* ==================== Vuetify Slider 微调 ==================== */
:deep(.v-slider-thumb) {
  transition: box-shadow 0.25s cubic-bezier(0.22, 0.61, 0.36, 1);
}

:deep(.v-slider-thumb:hover) {
  box-shadow: 0 0 0 8px rgba(var(--v-theme-primary), 0.12);
}

:deep(.v-slider-track__tick) {
  opacity: 0.2;
}

/* ==================== 保存按钮 ==================== */
.save-fab {
  position: fixed;
  bottom: 80px;
  right: 32px;
  z-index: 10;
}

.save-fab .v-btn {
  border-radius: 16px !important;
  box-shadow: 0 4px 20px rgba(var(--v-theme-primary), 0.3);
  transition: all 0.35s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.save-fab .v-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 28px rgba(var(--v-theme-primary), 0.4);
}

/* ==================== 响应式 ==================== */
@media (max-width: 600px) {
  .slot-switcher {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }

  .slot-card {
    padding: 12px 8px 10px;
  }

  .slot-card__icon {
    font-size: 22px;
  }

  .slot-card__label {
    font-size: 12px;
  }

  .save-fab {
    bottom: 76px;
    right: 16px;
  }
}
</style>
