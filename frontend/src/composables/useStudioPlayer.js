/**
 * useStudioPlayer.js — 音乐工作室播放器状态管理
 * ===============================================
 * 从 StudioHub.vue 提取，管理：
 *   - 播放/暂停/切歌控制（4种播放模式）
 *   - 推荐流获取（5种歌单源 + 分页缓存）
 *   - 歌词 LRC 解析与当前行匹配
 *   - CD 唱片旋转 + 进度条
 *   - 喜欢/取消喜欢 + 搜索喜欢歌曲
 *   - 待播放队列计算
 *   - 播放行为埋点上报
 */

import { ref, reactive, computed } from 'vue'
import { createAuthAxios } from '@/api/authAxios.js'

export function useStudioPlayer(audioRef) {
  const api = createAuthAxios()

  // ═══════════════ 播放器核心状态 ═══════════════
  const isPlaying = ref(false)
  const playElapsed = ref(0)
  const playedAccum = ref(0)
  const hasAudioSource = ref(false)
  let playTimer = null

  const currentTrack = reactive({
    track_id: '', title: '', artist: '', album: '', coverUrl: '', duration: 0,
  })

  const progressPercent = computed(() => {
    if (!currentTrack.duration) return 0
    return Math.min((playElapsed.value / currentTrack.duration) * 100, 100)
  })

  // ═══════════════ 推荐流 ═══════════════
  const playlist = ref([])
  const playlistIndex = ref(-1)
  const recommendTracks = ref([])
  const recommendLoading = ref(false)
  const sourceType = ref('liked')
  const customPlaylistId = ref('')
  const sortOrder = ref('desc')

  const page = ref(1)
  const pageSize = ref(20)
  const totalPages = ref(1)
  const totalTracks = ref(0)
  const recommendCache = reactive(new Map())

  // ═══════════════ 播放模式 ═══════════════
  const playMode = ref('sequential')
  const playedIndices = ref(new Set())
  const playHistoryStack = ref([])
  const showQueue = ref(false)

  const playModeOptions = [
    { value: 'sequential', icon: 'mdi-arrow-right-bold', label: '顺序播放' },
    { value: 'random', icon: 'mdi-shuffle-variant', label: '随机播放' },
    { value: 'weighted', icon: 'mdi-chart-bell-curve', label: '智能推荐' },
    { value: 'repeat-one', icon: 'mdi-repeat', label: '单曲循环' },
  ]

  const currentPlayModeMeta = computed(() =>
    playModeOptions.find(m => m.value === playMode.value) || playModeOptions[0]
  )

  const canPrev = computed(() => {
    if (!playlist.value.length) return false
    if (playMode.value === 'repeat-one') return true
    if (playMode.value === 'random') return playHistoryStack.value.length > 0
    return playlistIndex.value > 0
  })

  const canNext = computed(() => {
    if (!playlist.value.length) return false
    if (playMode.value === 'repeat-one' || playMode.value === 'random' || playMode.value === 'weighted') return true
    return playlistIndex.value < playlist.value.length - 1
  })

  const queueDisplayTracks = computed(() => {
    if (!playlist.value.length) return []
    const curIdx = playlistIndex.value
    switch (playMode.value) {
      case 'sequential':
        if (curIdx < 0) return playlist.value.map((t, i) => ({ ...t, _qi: i + 1 }))
        return playlist.value.map((t, i) => ({ ...t, _qi: i + 1, _isCurrent: i === curIdx }))
      case 'random':
        return playlist.value.map((t, i) => ({ ...t, _qi: i + 1 })).filter((_, i) => !playedIndices.value.has(i))
      case 'weighted':
        return playlist.value.map((t, i) => ({ ...t, _qi: i + 1, _isCurrent: i === curIdx }))
      case 'repeat-one':
        if (curIdx >= 0) return [{ ...playlist.value[curIdx], _qi: 1, _isCurrent: true }]
        return []
    }
  })

  function _resetPlayModeState() {
    playedIndices.value = new Set()
    playHistoryStack.value = []
    showQueue.value = false
  }

  // ═══════════════ 歌词 ═══════════════
  const lyricLines = ref([])
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

  // ═══════════════ 喜欢状态 ═══════════════
  const likedIds = ref(new Set())

  // ═══════════════ 喜欢歌单搜索 ═══════════════
  const likedSearchKeyword = ref('')
  const likedSearchLoading = ref(false)
  const likedSearchResults = ref(null)
  const isLikedSearchMode = ref(false)

  const displayTracks = computed(() => {
    if (isLikedSearchMode.value && likedSearchResults.value) {
      return likedSearchResults.value.map(s => ({
        track_id: String(s.id), title: s.name, artist: s.artists,
        cover_url: s.picUrl || '', album: s.album || '',
      }))
    }
    return recommendTracks.value
  })

  const sourceTabs = [
    { icon: '❤️', label: '喜欢', value: 'liked' },
    { icon: '🔥', label: '热榜', value: 'hot_list' },
    { icon: '⭐', label: 'TOP 50', value: 'top50' },
    { icon: '💿', label: '本地', value: 'local_library' },
    { icon: '📋', label: '歌单', value: 'custom_playlist' },
  ]

  // ═══════════════ 定时器 ═══════════════
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

  // ═══════════════ 音频事件 ═══════════════
  function onTimeUpdate() {
    if (audioRef.value) {
      playElapsed.value = audioRef.value.currentTime
      currentTrack.duration = audioRef.value.duration || currentTrack.duration
    }
  }

  function onTrackEnded() {
    isPlaying.value = false
    stopPlayTimer()
    if (playMode.value === 'repeat-one') {
      seekProgress(0)
      if (audioRef.value) {
        audioRef.value.currentTime = 0
        audioRef.value.play().catch(() => {})
        isPlaying.value = true
        startPlayTimer()
      }
      return
    }
    nextTrack()
  }

  // ═══════════════ 播放控制 ═══════════════
  async function playTrack(track) {
    if (currentTrack.track_id && String(currentTrack.track_id) !== String(track.track_id)) {
      await logPlayback(true)
    }
    currentTrack.track_id = track.track_id
    currentTrack.title = track.title
    currentTrack.artist = track.artist
    currentTrack.album = track.album || ''
    currentTrack.coverUrl = track.cover_url || ''
    currentTrack.duration = 180
    playElapsed.value = 0
    playedAccum.value = 0
    hasAudioSource.value = !!track.file_path

    const idx = playlist.value.findIndex(p => String(p.track_id) === String(track.track_id))
    if (idx >= 0) playlistIndex.value = idx

    if (playMode.value === 'random' && idx >= 0) {
      if (!playedIndices.value.has(idx)) playedIndices.value = new Set([...playedIndices.value, idx])
      playHistoryStack.value.push(idx)
      if (playHistoryStack.value.length > 100) playHistoryStack.value = playHistoryStack.value.slice(-50)
    }

    const token = localStorage.getItem('token') || ''
    if (track.file_path) {
      const safePath = track.file_path.replace(/\\/g, '/')
      audioRef.value.src = `/api/files/stream/${encodeURI(safePath)}?token=${encodeURIComponent(token)}`
    } else {
      audioRef.value.src = `/api/v3/music/stream/${encodeURIComponent(track.track_id)}?token=${encodeURIComponent(token)}`
    }
    audioRef.value.load()
    try { await audioRef.value.play(); isPlaying.value = true } catch { isPlaying.value = false }
    if (isPlaying.value) startPlayTimer()
    fetchLyrics(track.track_id, track.title, track.artist)
  }

  async function togglePlay() {
    if (!currentTrack.track_id) {
      if (recommendTracks.value.length) { playTrack(recommendTracks.value[0]); playlistIndex.value = 0 }
      return
    }
    if (isPlaying.value) {
      audioRef.value?.pause(); stopPlayTimer(); isPlaying.value = false
    } else {
      isPlaying.value = true; startPlayTimer()
      try { await audioRef.value?.play() } catch { /* ignore */ }
    }
  }

  function nextTrack() {
    if (!playlist.value.length) return
    if (currentTrack.track_id) logPlayback(true)
    switch (playMode.value) {
      case 'sequential':
        if (playlistIndex.value < playlist.value.length - 1) { playlistIndex.value++; playTrack(playlist.value[playlistIndex.value]) }
        break
      case 'random': {
        const remaining = playlist.value.map((_, i) => i).filter(i => !playedIndices.value.has(i))
        if (remaining.length === 0) { playedIndices.value = new Set(); remaining.push(...playlist.value.map((_, i) => i)) }
        const randIdx = remaining[Math.floor(Math.random() * remaining.length)]
        playedIndices.value = new Set([...playedIndices.value, randIdx])
        playHistoryStack.value.push(randIdx)
        playlistIndex.value = randIdx
        playTrack(playlist.value[randIdx])
        break
      }
      case 'weighted': {
        const weights = playlist.value.map(t => Math.max(t.preference_score || 1, 1))
        const totalWeight = weights.reduce((a, b) => a + b, 0)
        let rand = Math.random() * totalWeight
        for (let i = 0; i < playlist.value.length; i++) { rand -= weights[i]; if (rand <= 0) { playlistIndex.value = i; playTrack(playlist.value[i]); break } }
        break
      }
      case 'repeat-one': seekProgress(0); if (audioRef.value) { audioRef.value.currentTime = 0; audioRef.value.play().catch(() => {}) } break
    }
  }

  function prevTrack() {
    if (!playlist.value.length) return
    if (currentTrack.track_id) logPlayback(true)
    switch (playMode.value) {
      case 'sequential': case 'weighted':
        if (playlistIndex.value > 0) { playlistIndex.value--; playTrack(playlist.value[playlistIndex.value]) } break
      case 'random':
        if (playHistoryStack.value.length > 1) {
          playHistoryStack.value.pop()
          const prevIdx = playHistoryStack.value[playHistoryStack.value.length - 1]
          playlistIndex.value = prevIdx; playTrack(playlist.value[prevIdx])
        } else if (playHistoryStack.value.length === 1) {
          playlistIndex.value = playHistoryStack.value[0]; playTrack(playlist.value[playHistoryStack.value[0]])
        }
        break
      case 'repeat-one': seekProgress(0); if (audioRef.value) { audioRef.value.currentTime = 0; audioRef.value.play().catch(() => {}) } break
    }
  }

  function seekProgress(ratio) {
    const target = ratio * currentTrack.duration
    playElapsed.value = target
    if (audioRef.value) { try { audioRef.value.currentTime = target } catch { /* ignore */ } }
  }

  // ═══════════════ 埋点 ═══════════════
  async function logPlayback(isSwitch = false) {
    if (!currentTrack.track_id) return
    const duration = playedAccum.value
    const total = currentTrack.duration || 1
    const isSkipped = isSwitch && (duration < 10 || duration / total < 0.2)
    try {
      await api.post('/api/v3/music/log', {
        track_id: currentTrack.track_id, title: currentTrack.title, artist: currentTrack.artist,
        play_duration: Math.round(duration), total_duration: Math.round(total), source_type: sourceType.value,
      })
    } catch { /* ignore */ }
  }

  // ═══════════════ 歌词 ═══════════════
  function parseLRC(lrcText) {
    const lines = []
    const regex = /\[(\d{1,3}):(\d{2})(?:[.:](\d{2,3}))?\]/g
    for (const raw of (lrcText || '').split('\n')) {
      const matches = [...raw.matchAll(regex)]
      if (!matches.length) continue
      const text = raw.replace(regex, '').trim()
      if (!text) continue
      for (const m of matches) {
        const min = parseInt(m[1]) || 0; const sec = parseInt(m[2]) || 0; const ms = parseInt(m[3]) || 0
        lines.push({ time: min * 60 + sec + ms / (m[3]?.length === 3 ? 1000 : 100), text })
      }
    }
    return lines.sort((a, b) => a.time - b.time)
  }

  async function fetchLyrics(trackId, title, artist) {
    lyricLines.value = []; activeLyricIdx.value = -1; lyricLoading.value = true
    try {
      const res = await api.get('/api/lyrics', { params: { title, artist, id: trackId }, responseType: 'text', transformResponse: [(d) => d] })
      const lrc = res.data || ''
      if (lrc && lrc.includes('[')) lyricLines.value = parseLRC(lrc)
    } catch { lyricLines.value = [] }
    finally { lyricLoading.value = false }
  }

  function updateActiveLyric() {
    if (!lyricLines.value.length) return
    const t = playElapsed.value; let idx = -1
    for (let i = 0; i < lyricLines.value.length; i++) { if (lyricLines.value[i].time <= t) idx = i; else break }
    if (idx !== activeLyricIdx.value) activeLyricIdx.value = idx
  }

  // ═══════════════ 推荐流 ═══════════════
  function _cacheKey() {
    const pid = sourceType.value === 'custom_playlist' ? customPlaylistId.value.trim() : ''
    return `${sourceType.value}|${sortOrder.value}|${pid}`
  }

  function _restoreFromCache(key) {
    const pages = recommendCache.get(key)
    if (!pages) return false
    const cached = pages.get(page.value)
    if (!cached) return false
    recommendTracks.value = cached.tracks; playlist.value = cached.tracks; playlistIndex.value = -1
    _resetPlayModeState(); totalTracks.value = cached.total; totalPages.value = cached.total_pages
    return true
  }

  async function _fetchTop50() {
    recommendLoading.value = true
    try {
      const u = localStorage.getItem('username') || 'admin'
      const res = await api.get(`/api/user/${u}/taste-top-tracks`)
      const tracks = res?.data?.data || res?.data || []
      const mapped = tracks.map(t => ({
        track_id: t.track_id, title: t.title, artist: t.artist, album: '', cover_url: '',
        file_path: t.file_path, preference_score: t.resonance, source: t.file_path ? 'local' : 'netease',
        bpm: t.file_path ? 120 : -1, rank: t.rank,
      }))
      recommendTracks.value = mapped; playlist.value = mapped; playlistIndex.value = -1
      _resetPlayModeState(); totalTracks.value = mapped.length; totalPages.value = 1; page.value = 1
      window.__snackbar?.(`TOP ${mapped.length} 共鸣单曲`, 'success')
    } catch (e) { window.__snackbar?.('TOP 50 加载失败: ' + (e.message || '网络错误'), 'error') }
    finally { recommendLoading.value = false }
  }

  async function fetchRecommend() {
    if (sourceType.value === 'custom_playlist' && !customPlaylistId.value.trim()) {
      window.__snackbar?.('请输入歌单 ID', 'warning'); return
    }
    if (sourceType.value === 'top50') { await _fetchTop50(); return }
    const key = _cacheKey()
    if (_restoreFromCache(key)) return
    recommendLoading.value = true
    try {
      const params = { source_type: sourceType.value, sort_order: sortOrder.value, page: page.value, page_size: pageSize.value }
      if (sourceType.value === 'custom_playlist') params.playlist_id = customPlaylistId.value.trim()
      const res = await api.get('/api/v3/music/recommend', { params })
      const body = res.data?.data
      if (body?.tracks) {
        recommendTracks.value = body.tracks; playlist.value = body.tracks; playlistIndex.value = -1
        _resetPlayModeState(); totalTracks.value = body.total || body.tracks.length
        totalPages.value = body.total_pages || 1; page.value = body.page || 1
        if (!recommendCache.has(key)) recommendCache.set(key, new Map())
        recommendCache.get(key).set(page.value, { tracks: body.tracks, total: body.total || body.tracks.length, total_pages: body.total_pages || 1 })
        window.__snackbar?.(`第 ${page.value}/${totalPages.value} 页，共 ${totalTracks.value} 首`, 'success')
      }
    } catch (e) { window.__snackbar?.('推荐加载失败: ' + (e.message || '网络错误'), 'error') }
    finally { recommendLoading.value = false }
  }

  function switchSource(val) {
    if (sourceType.value === val) return
    sourceType.value = val; page.value = 1; totalPages.value = 1; totalTracks.value = 0
    recommendTracks.value = []; playlist.value = []
    clearLikedSearch()
    if (!_restoreFromCache(_cacheKey())) fetchRecommend()
  }

  function goToPage(p) {
    if (p < 1 || p > totalPages.value) return
    page.value = p
    if (!_restoreFromCache(_cacheKey())) fetchRecommend()
  }

  // ═══════════════ 喜欢 ═══════════════
  async function initLikedIds() {
    try {
      const res = await api.get('/api/v3/music/liked-ids')
      const ids = res.data?.ids || res.data?.data?.ids
      if (ids?.length) likedIds.value = new Set(ids)
    } catch { /* ignore */ }
  }

  async function toggleLike(track) {
    const id = Number(track.track_id)
    if (!id) return
    const wasLiked = likedIds.value.has(id)
    const next = new Set(likedIds.value)
    if (wasLiked) next.delete(id); else next.add(id)
    likedIds.value = next
    try {
      await api.post('/api/v3/music/like', { track_id: id, like: !wasLiked })
      window.__snackbar?.(wasLiked ? '已取消喜欢' : '已加入 ❤️ 我喜欢的音乐', 'success')
    } catch (e) {
      const rollback = new Set(likedIds.value)
      if (wasLiked) rollback.add(id); else rollback.delete(id)
      likedIds.value = rollback
      window.__snackbar?.('操作失败: ' + (e.response?.data?.message || e.message), 'error')
    }
  }

  async function searchLikedSongs() {
    const keyword = likedSearchKeyword.value.trim()
    if (!keyword) { clearLikedSearch(); return }
    likedSearchLoading.value = true
    try {
      const res = await api.get('/api/v3/music/liked/songs', { params: { keyword, limit: 500 } })
      const songs = res.data?.data?.songs
      if (songs?.length) { likedSearchResults.value = songs; isLikedSearchMode.value = true; totalTracks.value = songs.length; window.__snackbar?.(`找到 ${songs.length} 首匹配歌曲`, 'success') }
      else { likedSearchResults.value = []; isLikedSearchMode.value = true; totalTracks.value = 0; window.__snackbar?.('未找到匹配的歌曲', 'warning') }
    } catch (e) { window.__snackbar?.('搜索失败: ' + (e.message || '网络错误'), 'error') }
    finally { likedSearchLoading.value = false }
  }

  function clearLikedSearch() {
    likedSearchKeyword.value = ''; likedSearchResults.value = null; isLikedSearchMode.value = false
    fetchRecommend()
  }

  // ═══════════════ 工具 ═══════════════
  function formatTime(sec) {
    if (!sec || sec <= 0) return '0:00'
    const m = Math.floor(sec / 60); const s = Math.floor(sec % 60)
    return `${m}:${String(s).padStart(2, '0')}`
  }

  function prefColor(score) {
    if (score >= 80) return 'success'; if (score >= 60) return 'primary'
    if (score >= 40) return 'warning'; return 'error'
  }

  const skipStatusText = computed(() => {
    if (!currentTrack.duration) return '—'
    if (playElapsed.value < 10 || progressPercent.value < 20) return '⚠ 即将跳过'
    return '正常'
  })

  const skipStatusClass = computed(() => {
    if (!currentTrack.duration) return ''
    if (playElapsed.value < 10 || progressPercent.value < 20) return 'status-warn'
    return 'status-ok'
  })

  return {
    // 核心状态
    isPlaying, playElapsed, playedAccum, hasAudioSource, currentTrack, progressPercent,
    playlist, playlistIndex, recommendTracks, recommendLoading,
    sourceType, customPlaylistId, sortOrder,
    page, pageSize, totalPages, totalTracks,
    // 播放模式
    playMode, playModeOptions, currentPlayModeMeta, showQueue,
    canPrev, canNext, queueDisplayTracks,
    // 歌词
    lyricLines, activeLyricIdx, lyricLoading, visibleLyricLines,
    // 喜欢
    likedIds, likedSearchKeyword, likedSearchLoading, likedSearchResults, isLikedSearchMode,
    displayTracks, sourceTabs,
    // 跳过状态
    skipStatusText, skipStatusClass,
    // 方法
    startPlayTimer, stopPlayTimer, onTimeUpdate, onTrackEnded,
    playTrack, togglePlay, nextTrack, prevTrack, seekProgress,
    logPlayback, fetchLyrics, updateActiveLyric,
    fetchRecommend, switchSource, goToPage,
    initLikedIds, toggleLike, searchLikedSongs, clearLikedSearch,
    formatTime, prefColor,
  }
}
