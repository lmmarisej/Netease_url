/**
 * usePlayer.js — 音频播放器组合式函数
 * 从 StudioHub.vue 提取，语义完全不变。
 */
import { ref, reactive, computed } from 'vue'

export function usePlayer(api, sourceType, audioRef, recommendTracks, playlist, playlistIndex) {
  const isPlaying = ref(false)
  const playElapsed = ref(0)
  const playedAccum = ref(0)
  const playTimer = ref(null)
  const hasAudioSource = ref(false)
  const progressWrapRef = ref(null)

  const currentTrack = reactive({
    track_id: '',
    title: '',
    artist: '',
    album: '',
    coverUrl: '',
    duration: 0,
  })

  const progressPercent = computed(() => {
    if (!currentTrack.duration) return 0
    return Math.min((playElapsed.value / currentTrack.duration) * 100, 100)
  })

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

  function startPlayTimer(updateActiveLyric) {
    stopPlayTimer()
    playTimer.value = setInterval(() => {
      if (isPlaying.value) {
        playedAccum.value += 0.25
      }
      if (updateActiveLyric) updateActiveLyric()
    }, 250)
  }

  function stopPlayTimer() {
    if (playTimer.value) { clearInterval(playTimer.value); playTimer.value = null }
  }

  function onTimeUpdate() {
    if (audioRef.value) {
      playElapsed.value = audioRef.value.currentTime
      currentTrack.duration = audioRef.value.duration || currentTrack.duration
    }
  }

  // 这些函数需要访问外部作用域，保留为占位，实际绑定在 setup 中
  let _nextTrack = null
  let _fetchLyrics = null
  let _logPlayback = null
  let _updateActiveLyric = null

  function injectDeps({ nextTrack, fetchLyrics, logPlayback, updateActiveLyric }) {
    _nextTrack = nextTrack
    _fetchLyrics = fetchLyrics
    _logPlayback = logPlayback
    _updateActiveLyric = updateActiveLyric
  }

  function onTrackEnded() {
    isPlaying.value = false
    stopPlayTimer()
    if (_nextTrack) _nextTrack()
  }

  async function playTrack(track) {
    if (currentTrack.track_id && currentTrack.track_id !== track.track_id) {
      if (_logPlayback) await _logPlayback(true)
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

    const token = localStorage.getItem('token') || ''
    if (track.file_path) {
      const safePath = track.file_path.replace(/\\/g, '/')
      audioRef.value.src = `/api/files/stream/${encodeURI(safePath)}?token=${encodeURIComponent(token)}`
      hasAudioSource.value = true
    } else {
      audioRef.value.src = `/api/v3/music/stream/${encodeURIComponent(track.track_id)}?token=${encodeURIComponent(token)}`
      hasAudioSource.value = true
    }
    audioRef.value.load()
    try { await audioRef.value.play(); isPlaying.value = true } catch { isPlaying.value = false }
    if (isPlaying.value) startPlayTimer(_updateActiveLyric)
    if (_fetchLyrics) _fetchLyrics(track.track_id, track.title, track.artist)
  }

  async function togglePlay() {
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
      startPlayTimer(_updateActiveLyric)
      try { await audioRef.value?.play() } catch { /* noop */ }
    }
  }

  async function nextTrack() {
    if (playlistIndex.value < playlist.value.length - 1) {
      playlistIndex.value++
      playTrack(playlist.value[playlistIndex.value])
    }
  }

  async function prevTrack() {
    if (playlistIndex.value > 0) {
      playlistIndex.value--
      playTrack(playlist.value[playlistIndex.value])
    }
  }

  async function logPlayback(isSwitch = false) {
    if (!currentTrack.track_id) return
    const duration = playedAccum.value
    const total = currentTrack.duration || 1
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

  function seekProgress(e) {
    if (!audioRef.value || !currentTrack.duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    audioRef.value.currentTime = ratio * currentTrack.duration
    playElapsed.value = audioRef.value.currentTime
  }

  function formatTime(seconds) {
    if (!seconds || seconds <= 0) return '0:00'
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${m}:${String(s).padStart(2, '0')}`
  }

  return {
    // state
    isPlaying, playElapsed, playedAccum, hasAudioSource, progressWrapRef,
    currentTrack, progressPercent, skipStatusText, skipStatusClass,
    // methods
    startPlayTimer, stopPlayTimer, onTimeUpdate, onTrackEnded,
    playTrack, togglePlay, nextTrack, prevTrack,
    logPlayback, seekProgress, formatTime,
    injectDeps,
  }
}
