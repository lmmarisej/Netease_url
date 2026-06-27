/**
 * usePlaybackHistory.ts — 播放历史分页 Composable
 * ===============================================
 */

import { ref } from 'vue'
import { createAuthAxios } from '@/api/authAxios.js'

export interface HistoryItem {
  id: number
  track_id: string
  title: string
  artist: string
  play_duration: number
  total_duration: number
  is_skipped: boolean
  timestamp: string
}

export function usePlaybackHistory() {
  const api = createAuthAxios()

  const items = ref<HistoryItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = 20
  const loading = ref(false)

  async function fetchHistory() {
    loading.value = true
    try {
      const res = await api.get('/api/v3/music/history', {
        params: { page: page.value, page_size: pageSize },
      })
      const body = res.data?.data
      items.value = body?.items || []
      total.value = body?.total || 0
    } catch { /* 静默 */ }
    finally { loading.value = false }
  }

  function formatDate(iso: string): string {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleString('zh-CN', {
        month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
      })
    } catch { return iso }
  }

  return { items, total, page, pageSize, loading, fetchHistory, formatDate }
}
