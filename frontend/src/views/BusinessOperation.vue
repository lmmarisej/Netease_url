<template>
  <div>
    <div class="d-flex align-center mb-5"><v-icon size="32" color="primary" class="mr-3">mdi-magnify</v-icon><h2 class="text-h4 font-weight-bold">音乐搜索</h2></div>
    <v-tabs v-model="activeTab" class="mb-5"><v-tab value="search">搜索音乐</v-tab><v-tab value="playlist">歌单解析</v-tab><v-tab value="album">专辑解析</v-tab><v-tab value="download">音乐下载</v-tab></v-tabs>
    <v-window v-model="activeTab">
      <v-window-item value="search">
        <v-card class="mb-4" variant="flat" color="surface-variant">
          <v-card-text class="d-flex align-center ga-3 py-3">
            <v-text-field v-model="searchKeyword" hide-details placeholder="输入歌曲名、歌手名..." style="max-width:500px;" @keydown.enter="doSearch"><template #prepend-inner><v-icon size="18">mdi-magnify</v-icon></template></v-text-field>
            <v-select v-model="searchLimit" :items="[10,20,30]" hide-details style="max-width:100px;"/>
            <v-btn color="primary" :loading="searchLoading" @click="doSearch">搜索</v-btn>
          </v-card-text>
        </v-card>
        <div v-if="searchHistory.length" class="mb-3"><div class="text-caption text-medium-emphasis mb-1">搜索历史</div><div class="d-flex flex-wrap ga-1"><v-chip v-for="(h,i) in searchHistory" :key="i" size="small" variant="tonal" color="primary" closable @click="searchKeyword=h.name;doSearch()" @click:close="removeHistory('search',i)">{{ h.name }}</v-chip></div></div>
        <div v-if="searchResults.length" class="song-grid">
          <v-card v-for="song in searchResults" :key="song.id" class="song-card">
            <v-card-item class="pa-3">
              <div class="d-flex align-center ga-3">
                <v-img :src="song.picUrl||''" max-width="52" aspect-ratio="1" cover class="rounded-lg flex-shrink-0"><template #error><v-sheet max-width="52" aspect-ratio="1" color="surface-variant" class="rounded-lg d-flex align-center justify-center"><v-icon color="medium-emphasis">mdi-music-note</v-icon></v-sheet></template></v-img>
                <div class="flex-1-1" style="min-width:0;"><div class="text-body-2 font-weight-bold text-truncate" :title="song.name">{{ song.name }}</div><div class="text-caption text-medium-emphasis text-truncate">{{ song.artists||song.artist_string||'--' }}</div><div class="text-caption text-medium-emphasis text-truncate">{{ song.album||'' }}</div></div>
                <div class="d-flex ga-1 flex-shrink-0"><v-btn size="x-small" variant="tonal" color="primary" @click="showDetail(song.id)">详情</v-btn><v-btn size="x-small" color="success" @click="openDownloadModal(song.id,song.name)">下载</v-btn></div>
              </div>
            </v-card-item>
          </v-card>
        </div>
        <div v-else-if="!searchLoading" class="text-center text-medium-emphasis py-8"><v-icon size="48" class="mb-3">mdi-magnify</v-icon><p>{{ searchEmptyText }}</p></div>
      </v-window-item>
      <v-window-item value="playlist">
        <v-card class="mb-4" variant="flat" color="surface-variant"><v-card-text class="d-flex align-center ga-3 py-3"><v-text-field v-model="playlistInput" hide-details placeholder="输入歌单ID或链接" style="max-width:400px;" @keydown.enter="doPlaylist"><template #prepend-inner><v-icon size="18">mdi-playlist-music</v-icon></template></v-text-field><v-btn color="warning" :loading="playlistLoading" @click="doPlaylist">解析歌单</v-btn></v-card-text></v-card>
        <div v-if="playlistHistory.length" class="mb-3"><div class="text-caption text-medium-emphasis mb-1">歌单历史</div><div class="d-flex flex-wrap ga-1"><v-chip v-for="(h,i) in playlistHistory" :key="i" size="small" variant="tonal" color="warning" closable @click="playlistInput=h.id;doPlaylist()" @click:close="removeHistory('playlist',i)">{{ h.name||h.id }}</v-chip></div></div>
        <v-card v-if="playlistHeader" class="mb-4"><v-card-item><div class="d-flex ga-4 align-center"><v-img :src="playlistHeader.coverImgUrl||''" max-width="80" aspect-ratio="1" cover class="rounded-lg flex-shrink-0"/><div><div class="text-h6 font-weight-bold">{{ playlistHeader.name }}</div><div class="text-caption text-medium-emphasis">by {{ playlistHeader.creator||'' }} · {{ playlistHeader.trackCount||0 }} 首歌</div><div class="text-caption text-medium-emphasis mt-1">{{ (playlistHeader.description||'').substring(0,100) }}</div></div></div></v-card-item></v-card>
        <div v-if="playlistTracks.length" class="d-flex align-center ga-2 mb-2 flex-wrap"><v-btn size="x-small" variant="tonal" @click="batchSelectAll('playlist')">全选</v-btn><v-btn size="x-small" variant="tonal" @click="batchInvert('playlist')">反选</v-btn><v-text-field v-model="playlistFilter" hide-details placeholder="关键词筛选" style="max-width:140px;"/><v-btn size="x-small" color="warning" @click="batchDownload('playlist')" :disabled="!getCheckedCount('playlist')">批量下载 ({{ getCheckedCount('playlist') }})</v-btn></div>
        <div v-if="playlistTracks.length"><div v-for="track in filteredPlaylistTracks" :key="track.id" class="track-item d-flex align-center ga-3 pa-3 border-b"><v-checkbox v-model="playlistChecked" :value="track.id" hide-details density="compact" class="flex-shrink-0"/><span class="text-caption text-medium-emphasis flex-shrink-0" style="width:28px;">{{ track._idx }}</span><div class="flex-1-1" style="min-width:0;"><div class="text-body-2 font-weight-bold text-truncate">{{ track.name }}</div><div class="text-caption text-medium-emphasis text-truncate">{{ track.artists||'' }} · {{ track.album||'' }}</div></div><div class="d-flex ga-1 flex-shrink-0"><v-btn size="x-small" variant="tonal" color="primary" @click="showDetail(track.id)">详情</v-btn><v-btn size="x-small" color="success" @click="openDownloadModal(track.id,track.name)">下载</v-btn></div></div></div>
      </v-window-item>
      <v-window-item value="album">
        <v-card class="mb-4" variant="flat" color="surface-variant"><v-card-text class="d-flex align-center ga-3 py-3"><v-text-field v-model="albumInput" hide-details placeholder="输入专辑ID或链接" style="max-width:400px;" @keydown.enter="doAlbum"><template #prepend-inner><v-icon size="18">mdi-album</v-icon></template></v-text-field><v-btn color="info" :loading="albumLoading" @click="doAlbum">解析专辑</v-btn></v-card-text></v-card>
        <div v-if="albumHistory.length" class="mb-3"><div class="text-caption text-medium-emphasis mb-1">专辑历史</div><div class="d-flex flex-wrap ga-1"><v-chip v-for="(h,i) in albumHistory" :key="i" size="small" variant="tonal" color="info" closable @click="albumInput=h.id;doAlbum()" @click:close="removeHistory('album',i)">{{ h.name||h.id }}</v-chip></div></div>
        <v-card v-if="albumHeader" class="mb-4"><v-card-item><div class="d-flex ga-4 align-center"><v-img :src="albumHeader.coverImgUrl||''" max-width="80" aspect-ratio="1" cover class="rounded-lg flex-shrink-0"/><div><div class="text-h6 font-weight-bold">{{ albumHeader.name }}</div><div class="text-caption text-medium-emphasis">{{ albumHeader.artist||'' }} · {{ (albumHeader.songs||[]).length }} 首歌</div></div></div></v-card-item></v-card>
        <div v-if="albumTracks.length" class="d-flex align-center ga-2 mb-2 flex-wrap"><v-btn size="x-small" variant="tonal" @click="batchSelectAll('album')">全选</v-btn><v-btn size="x-small" variant="tonal" @click="batchInvert('album')">反选</v-btn><v-text-field v-model="albumFilter" hide-details placeholder="关键词筛选" style="max-width:140px;"/><v-btn size="x-small" color="warning" @click="batchDownload('album')" :disabled="!getCheckedCount('album')">批量下载 ({{ getCheckedCount('album') }})</v-btn></div>
        <div v-if="albumTracks.length"><div v-for="track in filteredAlbumTracks" :key="track.id" class="track-item d-flex align-center ga-3 pa-3 border-b"><v-checkbox v-model="albumChecked" :value="track.id" hide-details density="compact" class="flex-shrink-0"/><span class="text-caption text-medium-emphasis flex-shrink-0" style="width:28px;">{{ track._idx }}</span><div class="flex-1-1" style="min-width:0;"><div class="text-body-2 font-weight-bold text-truncate">{{ track.name }}</div><div class="text-caption text-medium-emphasis text-truncate">{{ track.artists||'' }} · {{ track.album||'' }}</div></div><div class="d-flex ga-1 flex-shrink-0"><v-btn size="x-small" variant="tonal" color="primary" @click="showDetail(track.id)">详情</v-btn><v-btn size="x-small" color="success" @click="openDownloadModal(track.id,track.name)">下载</v-btn></div></div></div>
      </v-window-item>
      <v-window-item value="download">
        <v-card class="mx-auto" style="max-width:500px;">
          <v-card-text class="pa-6">
            <div class="mb-4"><label class="text-subtitle-2 font-weight-bold mb-2 d-block">音乐 ID 或链接</label><v-text-field v-model="downloadInput" hide-details placeholder="输入歌曲ID或链接" @update:model-value="onDownloadInput"/><div v-if="downloadSongInfo" class="mt-2 pa-2 rounded bg-surface-variant text-caption">🎵 <strong>{{ downloadSongInfo }}</strong></div></div>
            <div class="mb-4"><label class="text-subtitle-2 font-weight-bold mb-2 d-block">音质选择</label><v-btn-toggle v-model="currentQuality" mandatory variant="outlined" divided density="compact" style="flex-wrap:wrap"><v-btn value="standard" size="small">标准</v-btn><v-btn value="exhigh" size="small">极高</v-btn><v-btn value="lossless" size="small">无损</v-btn><v-btn value="hires" size="small">Hi-Res</v-btn><v-btn value="sky" size="small">环绕声</v-btn><v-btn value="jyeffect" size="small">高清环绕</v-btn><v-btn value="jymaster" size="small">母带</v-btn></v-btn-toggle></div>
            <v-btn color="success" block :loading="downloading" prepend-icon="mdi-download" @click="doDownload">开始下载</v-btn>
            <div v-if="downloadHistory.length" class="mt-3"><div class="text-caption text-medium-emphasis mb-1">下载历史</div><div class="d-flex flex-wrap ga-1"><v-chip v-for="(h,i) in downloadHistory" :key="i" size="small" variant="tonal" color="success" closable @click="downloadInput=h.id" @click:close="removeHistory('download',i)">{{ h.name||h.id }}</v-chip></div></div>
            <v-progress-linear v-if="downloading" indeterminate color="success" class="mt-3"/>
            <small v-if="downloading" class="text-medium-emphasis d-block mt-1">正在下载并写入元信息...</small>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
    <v-dialog v-model="detailDialog" max-width="700px" scrollable>
      <v-card v-if="detailData">
        <v-card-title class="d-flex align-center">🎧 歌曲详情<v-spacer/><v-btn icon="mdi-close" variant="text" @click="closeDetail"/></v-card-title>
        <v-card-text>
          <div class="d-flex ga-4 mb-4"><v-img :src="detailData.pic||''" max-width="140" aspect-ratio="1" cover class="rounded-lg flex-shrink-0"/><div><h5 class="text-h5 mb-1">{{ detailData.name }}</h5><v-chip size="small" color="primary" variant="tonal" class="mr-1">{{ detailData.ar_name }}</v-chip><v-chip size="small" variant="tonal" class="mr-1">{{ detailData.al_name }}</v-chip><div class="mt-1"><v-chip size="x-small" color="success" variant="tonal" class="mr-1">{{ detailData.level||currentQuality }}</v-chip><v-chip size="x-small" color="warning" variant="tonal">{{ detailData.size||'--' }}</v-chip></div></div></div>
          <div class="d-flex ga-2 mb-4 flex-wrap"><v-btn size="small" color="success" prepend-icon="mdi-download" @click="downloadFromDetail">下载到本地</v-btn><v-btn v-if="detailData.url" size="small" variant="tonal" prepend-icon="mdi-link" :href="detailData.url" target="_blank">直链</v-btn><v-btn v-if="detailData.pic" size="small" variant="tonal" prepend-icon="mdi-image" @click="showBigPic(detailData.pic)">大图</v-btn></div>
          <div v-if="detailData.lyric" class="lyric-box pa-3 rounded mb-3" style="background:rgb(var(--v-theme-surface-variant));max-height:160px;overflow-y:auto;line-height:1.8;font-size:14px;" v-html="detailData.lyric.replace(/\n/g,'&lt;br&gt;')"/>
          <div v-if="detailData.url" id="aplayer-container" class="mt-3"/>
        </v-card-text>
      </v-card>
    </v-dialog>
    <v-dialog v-model="downloadDialog" max-width="420px">
      <v-card v-if="downloadTarget">
        <v-card-title class="d-flex align-center">⬇ 确认下载<v-spacer/><v-btn icon="mdi-close" variant="text" @click="downloadDialog=false"/></v-card-title>
        <v-card-text>
          <div class="mb-4 pa-3 rounded bg-surface-variant">
            <div class="text-body-2 font-weight-bold">{{ downloadTarget.name }}</div>
            <div class="text-caption text-medium-emphasis">ID: {{ downloadTarget.id }}</div>
          </div>
          <div class="mb-4"><label class="text-caption font-weight-bold mb-2 d-block">音质选择</label>
            <v-btn-toggle v-model="downloadQuality" mandatory variant="outlined" divided density="compact" style="flex-wrap:wrap">
              <v-btn value="standard" size="small">标准</v-btn><v-btn value="exhigh" size="small">极高</v-btn><v-btn value="lossless" size="small">无损</v-btn><v-btn value="hires" size="small">Hi-Res</v-btn><v-btn value="sky" size="small">环绕</v-btn><v-btn value="jyeffect" size="small">高清环绕</v-btn><v-btn value="jymaster" size="small">母带</v-btn>
            </v-btn-toggle>
          </div>
         <v-btn color="success" block :loading="downloading" prepend-icon="mdi-download" @click="confirmDownload">确认下载</v-btn>
         <small class="text-medium-emphasis d-block mt-2 text-center">下载任务将在后台执行，请前往 📊 任务管理 查看进度</small>
       </v-card-text>
     </v-card>
    </v-dialog>
    <v-dialog v-model="bigPicDialog" max-width="600px"><v-card><v-card-title class="d-flex align-center">大图预览<v-spacer/><v-btn icon="mdi-close" variant="text" @click="bigPicDialog=false"/></v-card-title><v-card-text class="text-center"><v-img :src="bigPicUrl" max-height="60vh" contain/></v-card-text></v-card></v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { searchMusic, getPlaylist, getAlbum, getSongInfo, downloadMusic } from '@/api/index.js'

const activeTab = ref('search')

// History helpers
const HISTORY_KEY = 'music_toolbox_history'
function loadHistory(type) {
  try { const r = localStorage.getItem(HISTORY_KEY); const all = r ? JSON.parse(r) : {}; return all[type] || [] } catch (e) { return [] }
}
function saveHistory(type, item) {
  try {
    const r = localStorage.getItem(HISTORY_KEY); const all = r ? JSON.parse(r) : {}
    if (!all[type]) all[type] = []
    all[type] = all[type].filter(h => h.id !== item.id)
    all[type].unshift({ ...item, time: Date.now() })
    if (all[type].length > 20) all[type] = all[type].slice(0, 20)
    localStorage.setItem(HISTORY_KEY, JSON.stringify(all))
  } catch (e) { /* ignore */ }
}
function removeHistory(type, index) {
  try { const r = localStorage.getItem(HISTORY_KEY); const all = r ? JSON.parse(r) : {}; if (all[type]) { all[type].splice(index, 1); localStorage.setItem(HISTORY_KEY, JSON.stringify(all)) } } catch (e) {}
}

// Search
const searchKeyword = ref(''), searchLimit = ref(30), searchLoading = ref(false), searchResults = ref([]), searchEmptyText = ref('输入关键词搜索歌曲'), searchHistory = ref(loadHistory('search'))
async function doSearch() {
  const kw = searchKeyword.value.trim()
  if (!kw) return window.__snackbar?.('请输入搜索关键词', 'warning')
  saveHistory('search', { id: kw, name: kw }); searchHistory.value = loadHistory('search')
  searchLoading.value = true
  try {
    const r = await searchMusic({ keyword: kw, limit: searchLimit.value })
    if (r?.status === 200 && r.data?.length) { searchResults.value = r.data; searchEmptyText.value = '' }
    else { searchResults.value = []; searchEmptyText.value = '未找到相关歌曲' }
  } catch (e) { searchResults.value = []; searchEmptyText.value = '搜索失败' }
  finally { searchLoading.value = false }
}

// Playlist
const playlistInput = ref(''), playlistLoading = ref(false), playlistHeader = ref(null), playlistTracks = ref([]), playlistChecked = ref([]), playlistFilter = ref(''), playlistHistory = ref(loadHistory('playlist'))
const filteredPlaylistTracks = computed(() => {
  if (!playlistFilter.value.trim()) return playlistTracks.value
  const kw = playlistFilter.value.toLowerCase()
  return playlistTracks.value.filter(t => (t.name || '').toLowerCase().includes(kw) || (t.artists || '').toLowerCase().includes(kw))
})
async function doPlaylist() {
  let pid = playlistInput.value.trim()
  if (!pid) return window.__snackbar?.('请输入歌单ID', 'warning')
  const m = pid.match(/playlist\?id=(\d+)/); if (m) pid = m[1]
  saveHistory('playlist', { id: pid, name: pid }); playlistHistory.value = loadHistory('playlist')
  playlistLoading.value = true
  try {
    const r = await getPlaylist({ id: pid })
    if (r?.status === 200 && r.data?.playlist) {
      const pl = r.data.playlist; playlistHeader.value = pl
      playlistTracks.value = (pl.tracks || []).map((s, i) => ({ ...s, _idx: i + 1 }))
      playlistChecked.value = []; playlistFilter.value = ''
    } else { playlistHeader.value = null; playlistTracks.value = []; window.__snackbar?.('歌单解析失败', 'error') }
  } catch (e) { playlistHeader.value = null; playlistTracks.value = []; window.__snackbar?.('请求失败', 'error') }
  finally { playlistLoading.value = false }
}

// Album
const albumInput = ref(''), albumLoading = ref(false), albumHeader = ref(null), albumTracks = ref([]), albumChecked = ref([]), albumFilter = ref(''), albumHistory = ref(loadHistory('album'))
const filteredAlbumTracks = computed(() => {
  if (!albumFilter.value.trim()) return albumTracks.value
  const kw = albumFilter.value.toLowerCase()
  return albumTracks.value.filter(t => (t.name || '').toLowerCase().includes(kw) || (t.artists || '').toLowerCase().includes(kw))
})
async function doAlbum() {
  let aid = albumInput.value.trim()
  if (!aid) return window.__snackbar?.('请输入专辑ID', 'warning')
  const m = aid.match(/album\?id=(\d+)/); if (m) aid = m[1]
  saveHistory('album', { id: aid, name: aid }); albumHistory.value = loadHistory('album')
  albumLoading.value = true
  try {
    const r = await getAlbum({ id: aid })
    if (r?.status === 200 && r.data?.album) {
      const al = r.data.album; albumHeader.value = al
      albumTracks.value = (al.songs || []).map((s, i) => ({ ...s, _idx: i + 1 }))
      albumChecked.value = []; albumFilter.value = ''
    } else { albumHeader.value = null; albumTracks.value = []; window.__snackbar?.('专辑解析失败', 'error') }
  } catch (e) { albumHeader.value = null; albumTracks.value = []; window.__snackbar?.('请求失败', 'error') }
  finally { albumLoading.value = false }
}

// Download
const downloadInput = ref(''), currentQuality = ref('lossless'), downloading = ref(false), downloadSongInfo = ref(''), downloadHistory = ref(loadHistory('download'))
const DEBOUNCE_TIMER = ref(null)
function onDownloadInput() {
  clearTimeout(DEBOUNCE_TIMER.value)
  DEBOUNCE_TIMER.value = setTimeout(async () => {
    const val = String(downloadInput.value).trim()
    if (!val) { downloadSongInfo.value = ''; return }
    let songId = val; const m = val.match(/song\?id=(\d+)/); if (m) songId = m[1]
    if (!/^\d+$/.test(songId)) { downloadSongInfo.value = ''; return }
    try {
      const r = await getSongInfo({ url: songId, type: 'name' })
      if (r?.status === 200 && r.data?.songs?.[0]) {
        const s = r.data.songs[0]; const artist = (s.ar || []).map(a => a.name).join(', ')
        downloadSongInfo.value = s.name + ' — ' + artist
      }
    } catch (e) { /* ignore */ }
  }, 500)
}
async function doDownload() {
  let musicId = String(downloadInput.value).trim()
  if (!musicId) return window.__snackbar?.('请输入音乐ID', 'warning')
  const m = musicId.match(/song\?id=(\d+)/); if (m) musicId = m[1]
  if (!/^\d+$/.test(musicId)) return window.__snackbar?.('无效的音乐ID', 'warning')
  saveHistory('download', { id: musicId, name: downloadSongInfo.value || musicId }); downloadHistory.value = loadHistory('download')
  downloading.value = true
  try {
    const response = await downloadMusic({ id: musicId, quality: currentQuality.value })
    const blob = response.data
    const ct = blob.type || ''
    // 检测响应类型：JSON（仅保存本地）或二进制（浏览器下载）
    if (ct.includes('application/json') || ct.includes('text/')) {
      // JSON 响应：仅保存到本地模式
      const text = await blob.text()
      const data = JSON.parse(text)
      window.__snackbar?.(data.message || '下载任务已开始', 'success')
    } else {
      // 二进制响应：触发浏览器下载
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const disposition = response.headers['content-disposition'] || ''
      const fnMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
      a.href = url
      a.download = fnMatch ? fnMatch[1].replace(/['"]/g, '') : (downloadSongInfo.value || musicId) + '.mp3'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      window.__snackbar?.('下载成功！', 'success')
    }
  } catch (e) { window.__snackbar?.(e.message || '下载失败', 'error') }
  finally { downloading.value = false }
}
const downloadDialog = ref(false), downloadTarget = ref(null), downloadQuality = ref('lossless')
function openDownloadModal(songId, songName) {
  downloadTarget.value = { id: songId, name: songName || songId }
  downloadQuality.value = currentQuality.value || 'lossless'
  downloadDialog.value = true
}
async function confirmDownload() {
  if (!downloadTarget.value) return
  downloading.value = true
  try {
    const r = await downloadMusic({ id: downloadTarget.value.id, quality: downloadQuality.value }, {})
    if (r?.data?.status === 200 || r?.status === 200) {
      window.__snackbar?.('下载任务已创建，请前往 📊 任务管理 查看进度', 'success')
    } else {
      window.__snackbar?.(r?.data?.message || r?.message || '任务创建成功', 'success')
    }
    downloadDialog.value = false
  } catch (e) { window.__snackbar?.(e.message || '下载失败', 'error') }
  finally { downloading.value = false }
}

// Song Detail
const detailDialog = ref(false), detailData = ref(null)
let apInstance = null
async function showDetail(songId) {
  detailDialog.value = true; detailData.value = null
  if (apInstance) { apInstance.destroy(); apInstance = null }
  try {
    const r = await getSongInfo({ url: songId, level: currentQuality.value, type: 'json' })
    if (r?.status === 200 && r.data) {
      const d = r.data; detailData.value = { ...d, id: songId, lyric: d.lyric || '' }
      await nextTick()
      if (d.url && window.APlayer) {
        setTimeout(() => {
          const c = document.getElementById('aplayer-container')
          if (c) { apInstance = new window.APlayer({ container: c, lrcType: 1, audio: [{ name: d.name, artist: d.ar_name, url: d.url, cover: d.pic, lrc: d.lyric }] }) }
        }, 300)
      }
    } else { detailData.value = { name: '获取失败', ar_name: '', al_name: '', pic: '', level: '', size: '', url: '', lyric: '' } }
  } catch (e) { detailData.value = { name: '请求失败', ar_name: '', al_name: '', pic: '', level: '', size: '', url: '', lyric: '' } }
}
function closeDetail() { if (apInstance) { apInstance.destroy(); apInstance = null }; detailDialog.value = false }
async function downloadFromDetail() {
  if (!detailData.value?.id) return window.__snackbar?.('无法获取歌曲ID', 'error')
  await quickDownload(detailData.value.id, detailData.value.name || '')
}

// Big Picture
const bigPicDialog = ref(false), bigPicUrl = ref('')
function showBigPic(url) { bigPicUrl.value = url; bigPicDialog.value = true }

// Batch operations
function getCheckedCount(type) { return type === 'playlist' ? playlistChecked.value.length : albumChecked.value.length }
function batchSelectAll(type) {
  const tracks = type === 'playlist' ? playlistTracks.value : albumTracks.value
  const checked = type === 'playlist' ? playlistChecked : albumChecked
  checked.value = tracks.map(t => t.id)
}
function batchInvert(type) {
  const tracks = type === 'playlist' ? playlistTracks.value : albumTracks.value
  const checked = type === 'playlist' ? playlistChecked : albumChecked
  const s = new Set(checked.value)
  checked.value = tracks.filter(t => !s.has(t.id)).map(t => t.id)
}
async function batchDownload(type) {
  const checked = type === 'playlist' ? playlistChecked.value : albumChecked.value
  if (!checked.length) return window.__snackbar?.('请先选择歌曲', 'warning')
  window.__snackbar?.(`开始批量下载 ${checked.length} 首...`, 'info')
  let fail = 0; let idx = 0
  for (const sid of checked) {
    try {
      idx++
      const response = await downloadMusic({ id: sid, quality: currentQuality.value })
      const blob = response.data; const ct = blob.type || ''
      if (ct.includes('application/json') || ct.includes('text/')) {
        const text = await blob.text(); JSON.parse(text) // ignore json mode
      } else {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        const disposition = response.headers['content-disposition'] || ''
        const fnMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
        a.href = url; a.download = fnMatch ? fnMatch[1].replace(/['"]/g, '') : `track_${sid}.mp3`
        document.body.appendChild(a); a.click(); document.body.removeChild(a)
        URL.revokeObjectURL(url)
      }
    } catch (e) { fail++ }
  }
  const msg = fail === 0 ? `批量下载完成！${checked.length} 首` : `${fail}/${checked.length} 首失败`
  window.__snackbar?.(msg, fail === 0 ? 'success' : 'warning')
}

watch(() => detailDialog.value, (val) => { if (!val && apInstance) { apInstance.destroy(); apInstance = null } })
</script>

<style scoped>
.song-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }
.song-card { transition: box-shadow 0.15s, transform 0.15s; }
.song-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); transform: translateY(-1px); }
.flex-1-1 { flex: 1 1 0; }
.border-b { border-bottom: 1px solid rgb(var(--v-theme-surface-variant)); }
.border-b:last-child { border-bottom: none; }
.track-item:hover { background: rgb(var(--v-theme-surface-variant)); }
</style>
