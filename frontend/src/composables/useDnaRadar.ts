/**
 * useDnaRadar.ts — DNA 雷达图数据加载 Composable
 * ===============================================
 * 从 /api/user/{u}/taste-radar 和 /api/user/{u}/taste-top-tracks 加载数据。
 */

import { ref, reactive, computed } from 'vue'
import { createAuthAxios } from '@/api/authAxios.js'

export interface TopTrack {
  rank: number
  title: string
  artist: string
  resonance: number
  file_path?: string
}

export function useDnaRadar() {
  const api = createAuthAxios()
  const username = computed(() => localStorage.getItem('username') || 'admin')

  const loading = ref(true)
  const error = ref('')
  const empty = ref(false)
  const trackCount = ref(0)

  const radarData = reactive<Record<string, number>>({
    tempo: 0, energy: 0, brightness: 0, contrast: 0,
    sub_bass: 0, vocal: 0, sentiment: 0,
    ambiance: 0, instrumental: 0, cultural: 0,
  })

  const topTracks = ref<TopTrack[]>([])

  const DIM_KEYS = ['tempo', 'energy', 'brightness', 'contrast', 'sub_bass', 'vocal', 'sentiment', 'ambiance', 'instrumental', 'cultural']

  async function loadData() {
    loading.value = true; error.value = ''
    try {
      const u = username.value
      const [radarRes, tracksRes] = await Promise.allSettled([
        api.get(`/api/user/${u}/taste-radar`),
        api.get(`/api/user/${u}/taste-top-tracks`),
      ])
      if (radarRes.status === 'fulfilled') {
        const body = (radarRes.value as any)?.data
        if (body?.success && body.data?.radar) {
          const d = body.data
          DIM_KEYS.forEach((key, i) => { radarData[key] = d.radar[i] ?? 50 })
          trackCount.value = d.count ?? 0
          empty.value = trackCount.value === 0
        }
      }
      if (tracksRes.status === 'fulfilled') {
        const body = (tracksRes.value as any)?.data
        topTracks.value = (body?.success && body.data) ? body.data : []
      }
    } catch (e: any) {
      error.value = '加载失败：' + (e.message || '网络错误')
    } finally {
      loading.value = false
    }
  }

  return { loading, error, empty, trackCount, radarData, topTracks, loadData, DIM_KEYS }
}
