/**
 * useDownload.ts — 音乐下载 Composable
 * ====================================
 * 从 BusinessOperation.vue 剥离下载逻辑。
 */

import { ref } from 'vue'
import { downloadMusic, getSongInfo } from '@/api/index.js'

export function useDownload() {
  const downloadInput = ref('')
  const currentQuality = ref('lossless')
  const downloading = ref(false)
  const downloadSongInfo = ref('')
  const downloadDialog = ref(false)
  const downloadTarget = ref<any>(null)
  const downloadQuality = ref('lossless')

  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  function onDownloadInput() {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(async () => {
      const val = String(downloadInput.value).trim()
      if (!val) { downloadSongInfo.value = ''; return }
      let songId = val
      const m = val.match(/song\?id=(\d+)/)
      if (m) songId = m[1]
      if (!/^\d+$/.test(songId)) { downloadSongInfo.value = ''; return }
      try {
        const r = await getSongInfo({ url: songId, type: 'name' })
        if (r?.status === 200 && r.data?.songs?.[0]) {
          const s = r.data.songs[0]
          downloadSongInfo.value = s.name + ' — ' + (s.ar || []).map((a: any) => a.name).join(', ')
        }
      } catch { /* ignore */ }
    }, 500)
  }

  async function doDownload() {
    let musicId = String(downloadInput.value).trim()
    if (!musicId) return (window as any).__snackbar?.('请输入音乐ID', 'warning')
    const m = musicId.match(/song\?id=(\d+)/)
    if (m) musicId = m[1]
    if (!/^\d+$/.test(musicId)) return (window as any).__snackbar?.('无效的音乐ID', 'warning')
    downloading.value = true
    try {
      const response = await downloadMusic({ id: musicId, quality: currentQuality.value })
      const blob = response.data
      const ct = blob.type || ''
      if (ct.includes('application/json') || ct.includes('text/')) {
        const text = await blob.text()
        const data = JSON.parse(text)
        ;(window as any).__snackbar?.(data.message || '下载任务已开始', 'success')
      } else {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        const disposition = response.headers['content-disposition'] || ''
        const fnMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
        a.href = url
        a.download = fnMatch ? fnMatch[1].replace(/['"]/g, '') : (downloadSongInfo.value || musicId) + '.mp3'
        document.body.appendChild(a); a.click(); document.body.removeChild(a)
        URL.revokeObjectURL(url)
        ;(window as any).__snackbar?.('下载成功！', 'success')
      }
    } catch (e: any) {
      (window as any).__snackbar?.(e.message || '下载失败', 'error')
    } finally { downloading.value = false }
  }

  function openDownloadModal(songId: string, songName: string, source?: string) {
    downloadTarget.value = { id: songId, name: songName || songId, source: source || 'netease' }
    downloadQuality.value = currentQuality.value || 'lossless'
    downloadDialog.value = true
  }

  async function confirmDownload() {
    if (!downloadTarget.value) return
    downloading.value = true
    try {
      await downloadMusic({
        id: downloadTarget.value.id,
        quality: downloadQuality.value,
        source: downloadTarget.value.source || 'netease',
      }, {})
      ;(window as any).__snackbar?.('下载任务已创建，请前往「任务管理」查看进度', 'success')
      downloadDialog.value = false
    } catch (e: any) {
      (window as any).__snackbar?.(e.message || '下载失败', 'error')
    } finally { downloading.value = false }
  }

  return {
    downloadInput, currentQuality, downloading, downloadSongInfo,
    downloadDialog, downloadTarget, downloadQuality,
    onDownloadInput, doDownload, openDownloadModal, confirmDownload,
  }
}
