/**
 * useWeightMixer.ts — 权重调音台 Composable
 * ==========================================
 * 管理 4 时段（morning/daytime/evening/midnight）的 10 维权重 CRUD。
 *
 * 数据流：
 *   onMounted → GET /api/v3/config/weights → 合并默认值
 *   用户拖拽 → 修改 reactive allWeights
 *   保存 → POST /api/v3/config/weights → snackbar
 */

import { ref, reactive, computed } from 'vue'
import { getWeightConfig, saveWeightConfig } from '@/api/index.js'

// ═══════════════ 类型 ═══════════════

export type SlotKey = 'morning' | 'daytime' | 'evening' | 'midnight'

export interface SlotDef {
  key: SlotKey
  icon: string
  label: string
  time: string
  color: string
}

export interface MixerPanel {
  name: string
  icon: string
  iconColor: string
  chip: string
  chipColor: string
  params: MixerParam[]
}

export interface MixerParam {
  key: string
  label: string
  color: string
}

export type WeightMap = Record<string, number>
export type AllWeights = Record<SlotKey, WeightMap>

// ═══════════════ 默认权重 ═══════════════

const DEFAULT_WEIGHTS: AllWeights = {
  morning:   { tempo: 0.8, energy: 0.6, vocal_ratio: 1.0, bass_intensity: 0.5, acousticness: 1.5, electronic_score: 0.3, rock_score: 0.3, instrument_pureness: 1.3, midnight_emo: 0.2, guofeng_vibe: 1.2 },
  daytime:   { tempo: 1.2, energy: 1.0, vocal_ratio: 1.1, bass_intensity: 0.9, acousticness: 0.7, electronic_score: 1.1, rock_score: 0.8, instrument_pureness: 1.4, midnight_emo: 0.4, guofeng_vibe: 1.0 },
  evening:   { tempo: 1.5, energy: 1.6, vocal_ratio: 1.2, bass_intensity: 1.5, acousticness: 0.4, electronic_score: 1.5, rock_score: 1.2, instrument_pureness: 0.7, midnight_emo: 1.1, guofeng_vibe: 0.8 },
  midnight:  { tempo: 0.5, energy: 0.3, vocal_ratio: 1.4, bass_intensity: 0.7, acousticness: 1.3, electronic_score: 0.6, rock_score: 0.2, instrument_pureness: 1.2, midnight_emo: 1.8, guofeng_vibe: 1.1 },
}

// ═══════════════ 常量 ═══════════════

export const SLOTS: SlotDef[] = [
  { key: 'morning',  icon: '🌅', label: '元气清晨', time: '07:00-09:00', color: '#c4956a' },
  { key: 'daytime',  icon: '💻', label: '高效白昼', time: '09:00-18:00', color: '#6a9fb5' },
  { key: 'evening',  icon: '🌆', label: '多巴胺黄昏', time: '18:00-22:00', color: '#b87d8d' },
  { key: 'midnight', icon: '🌌', label: '静谧深夜', time: '22:00-07:00', color: '#8b7fba' },
]

export const MIXER_PANELS: MixerPanel[] = [
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

// ═══════════════ Composable ═══════════════

export function useWeightMixer() {
  const activeSlot = ref<SlotKey>('morning')
  const draggingKey = ref<string | null>(null)
  const saving = ref(false)

  const allWeights = reactive<AllWeights>(structuredClone(DEFAULT_WEIGHTS))

  const currentWeights = computed({
    get: () => allWeights[activeSlot.value] || {},
    set: (v) => { allWeights[activeSlot.value] = v as WeightMap },
  })

  async function loadWeights() {
    try {
      const data = await getWeightConfig()
      if (data?.slots) {
        for (const [key, slot] of Object.entries(data.slots) as [SlotKey, any][]) {
          if (allWeights[key] && slot.weights) {
            allWeights[key] = { ...DEFAULT_WEIGHTS[key], ...slot.weights }
          }
        }
      }
    } catch { /* 保留默认 */ }
  }

  async function saveWeights() {
    saving.value = true
    try {
      const payload: any = { slots: {} }
      for (const [key, weights] of Object.entries(allWeights)) {
        const def = SLOTS.find(s => s.key === key)
        payload.slots[key] = {
          label: def ? `${def.label} (${def.time})` : key,
          weights: { ...weights },
        }
      }
      await saveWeightConfig(payload)
      ;(window as any).__snackbar?.('权重配置已保存', 'success')
    } catch (e: any) {
      ;(window as any).__snackbar?.('保存失败: ' + (e.message || '未知错误'), 'error')
    } finally {
      saving.value = false
    }
  }

  return {
    activeSlot, draggingKey, saving,
    allWeights, currentWeights,
    loadWeights, saveWeights,
  }
}
