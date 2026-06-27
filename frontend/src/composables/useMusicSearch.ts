/**
 * useMusicSearch.ts — 音乐搜索 / 歌单解析 / 专辑解析 Composable
 * ===============================================================
 * 从 BusinessOperation.vue 剥离，管理：
 *   - 搜索：多源（网易云/QQ）交错合并
 *   - 歌单：输入 ID 解析、历史记录
 *   - 专辑：输入 ID 解析、历史记录
 *   - 本地 history localStorage 持久化
 */

import { ref, computed, type Ref } from 'vue'
import { searchMusic, getPlaylist, getAlbum } from '@/api/index.js'

const HISTORY_KEY = 'music_toolbox_history_v2'

// ═══════════════ 历史管理 ═══════════════

function loadHistory(type: string): any[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    const all = raw ? JSON.parse(raw) : {}
    return all[type] || []
  } catch { return [] }
}

function saveHistory(type: string, item: { id: string; name: string }) {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    const all = raw ? JSON.parse(raw) : {}
    if (!all[type]) all[type] = []
    all[type] = all[type].filter((h: any) => h.id !== item.id)
    all[type].unshift({ ...item, time: Date.now() })
    if (all[type].length > 20) all[type] = all[type].slice(0, 20)
    localStorage.setItem(HISTORY_KEY, JSON.stringify(all))
  } catch { /* ignore */ }
}

export function removeHistory(type: string, index: number) {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    const all = raw ? JSON.parse(raw) : {}
    if (all[type]) {
      all[type].splice(index, 1)
      localStorage.setItem(HISTORY_KEY, JSON.stringify(all))
    }
  } catch { /* ignore */ }
}

function interleave<T>(lists: T[][]): T[] {
  const out: T[] = []
  const max = Math.max(0, ...lists.map(l => l.length))
  for (let i = 0; i < max; i++) {
    for (const l of lists) { if (i < l.length) out.push(l[i]) }
  }
  return out
}

// ═══════════════ Composable ═══════════════

export function useMusicSearch() {
  // ── 搜索 ──
  const searchKeyword = ref('')
  const searchLimit = ref(30)
  const searchLoading = ref(false)
  const searchResults = ref<any[]>([])
  const searchEmptyText = ref('输入关键词搜索歌曲')
  const searchHistory = ref(loadHistory('search'))
  const searchSources = ref<string[]>(['netease'])
  const resultFilter = ref('all')

  const countBySource = computed(() => {
    const c: Record<string, number> = {}
    for (const s of searchResults.value) {
      const src = s.source || 'netease'
      c[src] = (c[src] || 0) + 1
    }
    return c
  })

  const displayedResults = computed(() => {
    if (resultFilter.value === 'all') return searchResults.value
    return searchResults.value.filter((s: any) => (s.source || 'netease') === resultFilter.value)
  })

  async function doSearch() {
    const kw = searchKeyword.value.trim()
    if (!kw) return (window as any).__snackbar?.('请输入搜索关键词', 'warning')
    const sources = searchSources.value.length ? searchSources.value : ['netease']
    saveHistory('search', { id: kw, name: kw })
    searchHistory.value = loadHistory('search')
    searchLoading.value = true
    resultFilter.value = 'all'
    try {
      const lists = await Promise.all(
        sources.map(src =>
          searchMusic({ keyword: kw, limit: searchLimit.value, source: src })
            .then((r: any) => (r?.status === 200 && Array.isArray(r.data)) ? r.data.map((s: any) => ({ ...s, source: s.source || src })) : [])
            .catch(() => [])
        )
      )
      const merged = interleave(lists)
      if (merged.length) {
        searchResults.value = merged
        searchEmptyText.value = ''
      } else {
        searchResults.value = []
        searchEmptyText.value = '未找到相关歌曲'
      }
    } catch {
      searchResults.value = []
      searchEmptyText.value = '搜索失败'
    } finally {
      searchLoading.value = false
    }
  }

  // ── 歌单 ──
  const playlistInput = ref('')
  const playlistLoading = ref(false)
  const playlistHeader = ref<any>(null)
  const playlistTracks = ref<any[]>([])
  const playlistChecked = ref<string[]>([])
  const playlistFilter = ref('')
  const playlistHistory = ref(loadHistory('playlist'))

  const filteredPlaylistTracks = computed(() => {
    if (!playlistFilter.value.trim()) return playlistTracks.value
    const kw = playlistFilter.value.toLowerCase()
    return playlistTracks.value.filter((t: any) =>
      (t.name || '').toLowerCase().includes(kw) || (t.artists || '').toLowerCase().includes(kw)
    )
  })

  async function doPlaylist() {
    let pid = playlistInput.value.trim()
    if (!pid) return (window as any).__snackbar?.('请输入歌单ID', 'warning')
    const m = pid.match(/playlist\?id=(\d+)/)
    if (m) pid = m[1]
    saveHistory('playlist', { id: pid, name: '' })
    playlistHistory.value = loadHistory('playlist')
    playlistLoading.value = true
    try {
      const r = await getPlaylist({ id: pid })
      if (r?.status === 200 && r.data?.playlist) {
        const pl = r.data.playlist
        playlistHeader.value = pl
        saveHistory('playlist', { id: pid, name: pl.name || pid })
        playlistHistory.value = loadHistory('playlist')
        playlistTracks.value = (pl.tracks || []).map((s: any, i: number) => ({ ...s, _idx: i + 1 }))
        playlistChecked.value = []
        playlistFilter.value = ''
      } else {
        playlistHeader.value = null
        playlistTracks.value = []
        ;(window as any).__snackbar?.('歌单解析失败', 'error')
      }
    } catch {
      playlistHeader.value = null
      playlistTracks.value = []
      ;(window as any).__snackbar?.('请求失败', 'error')
    } finally {
      playlistLoading.value = false
    }
  }

  // ── 专辑 ──
  const albumInput = ref('')
  const albumLoading = ref(false)
  const albumHeader = ref<any>(null)
  const albumTracks = ref<any[]>([])
  const albumChecked = ref<string[]>([])
  const albumFilter = ref('')
  const albumHistory = ref(loadHistory('album'))

  const filteredAlbumTracks = computed(() => {
    if (!albumFilter.value.trim()) return albumTracks.value
    const kw = albumFilter.value.toLowerCase()
    return albumTracks.value.filter((t: any) =>
      (t.name || '').toLowerCase().includes(kw) || (t.artists || '').toLowerCase().includes(kw)
    )
  })

  async function doAlbum() {
    let aid = albumInput.value.trim()
    if (!aid) return (window as any).__snackbar?.('请输入专辑ID', 'warning')
    const m = aid.match(/album\?id=(\d+)/)
    if (m) aid = m[1]
    saveHistory('album', { id: aid, name: '' })
    albumHistory.value = loadHistory('album')
    albumLoading.value = true
    try {
      const r = await getAlbum({ id: aid })
      if (r?.status === 200 && r.data?.album) {
        const al = r.data.album
        albumHeader.value = al
        saveHistory('album', { id: aid, name: al.name || aid })
        albumHistory.value = loadHistory('album')
        albumTracks.value = (al.songs || []).map((s: any, i: number) => ({ ...s, _idx: i + 1 }))
        albumChecked.value = []
        albumFilter.value = ''
      } else {
        albumHeader.value = null
        albumTracks.value = []
        ;(window as any).__snackbar?.('专辑解析失败', 'error')
      }
    } catch {
      albumHeader.value = null
      albumTracks.value = []
      ;(window as any).__snackbar?.('请求失败', 'error')
    } finally {
      albumLoading.value = false
    }
  }

  return {
    // 搜索
    searchKeyword, searchLimit, searchLoading, searchResults, searchEmptyText,
    searchHistory, searchSources, resultFilter, countBySource, displayedResults,
    doSearch,
    // 歌单
    playlistInput, playlistLoading, playlistHeader, playlistTracks,
    playlistChecked, playlistFilter, playlistHistory, filteredPlaylistTracks,
    doPlaylist,
    // 专辑
    albumInput, albumLoading, albumHeader, albumTracks,
    albumChecked, albumFilter, albumHistory, filteredAlbumTracks,
    doAlbum,
  }
}
