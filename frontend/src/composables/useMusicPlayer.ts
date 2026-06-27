/**
 * useMusicPlayer.ts — 音乐播放器状态管理 Composable
 * ====================================================
 * 剥离自 StudioHub.vue，管理：
 *   - 播放/暂停/切歌控制
 *   - setInterval 计时器（累计聆听时长 + 歌词同步）
 *   - 播放行为埋点上报（POST /api/v3/music/log）
 *   - 网易云推荐流获取（热榜 / 自定义歌单）
 *   - 歌词 LRC 解析与当前行匹配
 *   - CD 唱片旋转状态
 *
 * 纯逻辑层，无 DOM 依赖（除 audioRef 由调用方注入）。
 */

import { ref, reactive, computed, watch, nextTick, type Ref } from 'vue'
import { createAuthAxios } from '@/api/authAxios.js'

// ═══════════════ 类型定义 ═══════════════

export interface RecommendTrack {
  track_id: string
  title: string
  artist: string
  album?: string
  cover_url: string
  bpm: number
  vocal_ratio: number
  energy: number
  acousticness: number
  instrumentalness: number
  valence: number
  source_label: string
  source: string         // "local" | "netease"
  preference_score: number  // 0-100 偏好匹配分
  file_path?: string
  total_duration?: number
  danceability?: number
}

export interface LyricLine {
  time: number   // 秒
  text: string
}

export interface PlayerState {
  track_id: string
  title: string
  artist: string
  album: string
  coverUrl: string
  duration: number
}

// ═══════════════ Composable ═══════════════

export function useMusicPlayer(audioRef: Ref<HTMLAudioElement | null>) {
  const api = createAuthAxios()

  // ── 播放器核心状态 ──
  const isPlaying = ref(false)
  const playElapsed = ref(0)       // 当前播放位置（秒）
  const playedAccum = ref(0)       // 累计聆听时长（不受拖拽影响）
  const hasAudioSource = ref(false)

  const currentTrack = reactive<PlayerState>({
    track_id: '', title: '', artist: '', album: '', coverUrl: '', duration: 180,
  })

  const progressPercent = computed(() => {
    if (!currentTrack.duration) return 0
    return Math.min((playElapsed.value / currentTrack.duration) * 100, 100)
  })

  // ── 推荐流 ──
  const recommendTracks = ref<RecommendTrack[]>([])
  const recommendLoading = ref(false)
  const playlist = ref<RecommendTrack[]>([])
  const playlistIndex = ref(-1)
  const sourceType = ref('hot_list')
  const customPlaylistId = ref('')
  const sortOrder = ref('desc')

  // ── 歌词 ──
  const lyricLines = ref<LyricLine[]>([])
  const activeLyricIdx = ref(-1)
  const lyricLoading = ref(false)

  const LYRIC_WINDOW = 6
  const visibleLyricLines = computed(() => {
    if (!lyricLines.value.length) return []
    const center = Math.max(0, activeLyricIdx.value)
    const start = Math.max(0, center - Math.floor(LYRIC_WINDOW / 2))
    const end = Math.min(lyricLines.value.length, start + LYRIC_WINDOW)
    return lyricLines.value.slice(start, end).map((l, i) => ({ ...l, idx: start + i }))
  })

  // ── 定时器 ──
  let playTimer: ReturnType<typeof setInterval> | null = null

  function startPlayTimer() {
    stopPlayTimer()
    playTimer = setInterval(() => {
      if (isPlaying.value) playedAccum.value += 0.25
      updateActiveLyric()
    }, 250)
  }

  function stopPlayTimer() {
    if (playTimer) { clearInterval(playTimer); playTimer = null }
  }

  // ── seek 锁：流媒体代理不支持 Range，防止 timeupdate 覆盖手动 seek ──
  const seekLocked = ref(false)
  let _seekLockTimer: ReturnType<typeof setTimeout> | null = null

  // ── 音频事件 ──
  function onTimeUpdate() {
    if (audioRef.value && !seekLocked.value) {
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

  // ═══════════════ 播放控制 ═══════════════

  async function playTrack(track: RecommendTrack | PlayerState) {
    if (currentTrack.track_id && currentTrack.track_id !== (track as any).track_id) {
      await logPlayback(true)
    }
    const t = track as any
    currentTrack.track_id = t.track_id
    currentTrack.title = t.title
    currentTrack.artist = t.artist
    currentTrack.album = t.album || ''
    currentTrack.coverUrl = t.cover_url || t.coverUrl || ''
    currentTrack.duration = t.total_duration || 180
    playElapsed.value = 0
    playedAccum.value = 0
    hasAudioSource.value = !!t.file_path

    const token = localStorage.getItem('token') || ''
    if (t.file_path) {
      audioRef.value!.src = `/api/files/stream/${encodeURIComponent(t.file_path)}?token=${encodeURIComponent(token)}`
      audioRef.value!.load()
      try { await audioRef.value!.play(); isPlaying.value = true } catch { isPlaying.value = false }
    } else {
      audioRef.value!.src = `/api/v3/music/stream/${encodeURIComponent(t.track_id)}?token=${encodeURIComponent(token)}`
      audioRef.value!.load()
      try { await audioRef.value!.play(); isPlaying.value = true } catch { isPlaying.value = false }
    }
    if (isPlaying.value) startPlayTimer()
    fetchLyrics()
  }

  function togglePlay() {
    if (!currentTrack.track_id) {
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
      audioRef.value?.play().catch(() => {})
    }
  }

  function nextTrack() {
    if (currentTrack.track_id) logPlayback(true)
    if (playlistIndex.value < playlist.value.length - 1) {
      playlistIndex.value++
      playTrack(playlist.value[playlistIndex.value])
    }
  }

  function prevTrack() {
    if (currentTrack.track_id) logPlayback(true)
    if (playlistIndex.value > 0) {
      playlistIndex.value--
      playTrack(playlist.value[playlistIndex.value])
    }
  }

  function seekProgress(ratio: number) {
    const target = ratio * currentTrack.duration
    playElapsed.value = target
    // 锁定 onTimeUpdate，防止流媒体（不支持 Range）覆盖回来
    seekLocked.value = true
    if (_seekLockTimer) clearTimeout(_seekLockTimer)
    _seekLockTimer = setTimeout(() => { seekLocked.value = false }, 600)
    if (audioRef.value) {
      try { audioRef.value.currentTime = target } catch { /* 忽略 */ }
    }
  }

  // ═══════════════ 埋点上报 ═══════════════

  async function logPlayback(isSwitch = false) {
    if (!currentTrack.track_id) return
    const duration = playedAccum.value
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
    } catch { /* 静默 */ }
  }

  // ═══════════════ 推荐流获取 ═══════════════

  async function fetchRecommend() {
    recommendLoading.value = true
    try {
      const params: Record<string, string> = {
        source_type: sourceType.value,
        sort_order: sortOrder.value,
      }
      if (sourceType.value === 'custom_playlist') {
        if (!customPlaylistId.value.trim()) {
          (window as any).__snackbar?.('请输入歌单 ID', 'warning')
          return
        }
        params.playlist_id = customPlaylistId.value.trim()
      }
      const res = await api.get('/api/v3/music/recommend', { params })
      const body = res.data?.data
      if (body?.tracks) {
        recommendTracks.value = body.tracks
        playlist.value = body.tracks
        playlistIndex.value = -1
        ;(window as any).__snackbar?.(`已加载 ${body.tracks.length} 首推荐`, 'success')
      }
    } catch (e: any) {
      (window as any).__snackbar?.('推荐加载失败: ' + (e.message || '网络错误'), 'error')
    } finally {
      recommendLoading.value = false
    }
  }

  // ═══════════════ 歌词解析 ═══════════════

  function parseLRC(lrcText: string): LyricLine[] {
    const lines: LyricLine[] = []
    const regex = /\[(\d{1,3}):(\d{2})(?:[.:](\d{2,3}))?\]/g
    for (const raw of lrcText.split('\n')) {
      const matches = [...raw.matchAll(regex)]
      if (!matches.length) continue
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
    return lines.sort((a, b) => a.time - b.time)
  }

  async function fetchLyrics() {
    lyricLines.value = []
    activeLyricIdx.value = -1
    lyricLoading.value = true
    try {
      const res = await api.get('/api/lyrics', {
        params: { title: currentTrack.title, artist: currentTrack.artist, id: currentTrack.track_id },
        responseType: 'text',
        transformResponse: [(d: string) => d],
      })
      const lrc = res.data || ''
      if (lrc.includes('[')) lyricLines.value = parseLRC(lrc)
    } catch { /* 静默 */ }
    finally { lyricLoading.value = false }
  }

  function updateActiveLyric() {
    if (!lyricLines.value.length) return
    const t = playElapsed.value
    let idx = -1
    for (let i = 0; i < lyricLines.value.length; i++) {
      if (lyricLines.value[i].time <= t) idx = i
      else break
    }
    if (idx !== activeLyricIdx.value) activeLyricIdx.value = idx
  }

  // ═══════════════ 工具函数 ═══════════════

  function formatTime(sec: number): string {
    if (!sec || sec <= 0) return '0:00'
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m}:${String(s).padStart(2, '0')}`
  }

  // ═══════════════ 导出 ═══════════════

  return {
    // 状态
    isPlaying, playElapsed, playedAccum, hasAudioSource,
    currentTrack, progressPercent,
    recommendTracks, recommendLoading, playlist, playlistIndex,
    sourceType, customPlaylistId, sortOrder,
    lyricLines, activeLyricIdx, lyricLoading, visibleLyricLines,
    // 播放控制
    playTrack, togglePlay, nextTrack, prevTrack, seekProgress,
    // 定时器
    startPlayTimer, stopPlayTimer, onTimeUpdate, onTrackEnded,
    // 数据
    fetchRecommend, fetchLyrics,
    // 工具
    formatTime,
  }
}
