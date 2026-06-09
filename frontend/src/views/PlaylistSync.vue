<template>
  <div>
    <div class="d-flex align-center mb-5">
      <v-icon size="32" color="primary" class="mr-3">mdi-playlist-music</v-icon>
      <h2 class="text-h4 font-weight-bold">歌单同步</h2>
    </div>

    <v-alert :type="syncRunning ? 'success' : 'warning'" variant="tonal" class="mb-4" density="compact">
      <div class="d-flex align-center">
        <div class="status-dot mr-2" :class="syncRunning ? 'on' : 'off'" />
        <span>{{ syncStatusText }}</span>
        <v-spacer />
        <span class="text-caption">{{ syncExtra }}</span>
      </div>
    </v-alert>

    <v-card class="mb-4">
      <v-card-text class="d-flex align-center justify-space-between">
        <div>
          <div class="text-subtitle-1 font-weight-bold">启用定时同步</div>
          <span class="text-caption text-medium-emphasis">开启后将按设定周期自动同步歌单到本地</span>
        </div>
        <v-switch v-model="syncEnabled" color="success" hide-details class="flex-shrink-0" />
      </v-card-text>
    </v-card>

    <v-expand-transition>
      <div v-if="syncEnabled">
        <v-card class="mb-4">
          <v-card-title class="text-subtitle-1 font-weight-bold">歌单管理</v-card-title>
          <v-card-text>
            <div class="d-flex ga-2 mb-3" style="max-width:500px;">
              <v-text-field v-model="playlistInput" hide-details placeholder="输入歌单ID或链接" @keydown.enter="addPlaylist" />
              <v-btn color="primary" @click="addPlaylist" :loading="playlistLoading">添加</v-btn>
            </div>
            <div v-if="playlistIds.length === 0" class="text-caption text-medium-emphasis">尚未添加歌单</div>
            <div v-else class="d-flex flex-wrap ga-2">
              <v-chip v-for="p in playlistIds" :key="p.id" closable variant="tonal" color="primary" @click:close="removePlaylist(p.id)">
                📋 {{ p.name || p.id }}
                <template v-if="p.name"><small class="text-medium-emphasis ml-1">({{ p.id }})</small></template>
              </v-chip>
            </div>
          </v-card-text>
        </v-card>

        <v-card class="mb-4">
          <v-card-title class="text-subtitle-1 font-weight-bold">同步音质</v-card-title>
          <v-card-text>
            <v-btn-toggle v-model="syncQuality" mandatory variant="outlined" divided density="compact">
              <v-btn value="standard" size="small">标准</v-btn>
              <v-btn value="exhigh" size="small">极高</v-btn>
              <v-btn value="lossless" size="small">无损</v-btn>
              <v-btn value="hires" size="small">Hi-Res</v-btn>
              <v-btn value="sky" size="small">环绕声</v-btn>
              <v-btn value="jyeffect" size="small">高清环绕</v-btn>
              <v-btn value="jymaster" size="small">母带</v-btn>
            </v-btn-toggle>
          </v-card-text>
        </v-card>

        <v-card class="mb-4">
          <v-card-title class="text-subtitle-1 font-weight-bold">调度方式</v-card-title>
          <v-card-text>
            <v-btn-toggle v-model="scheduleMode" mandatory variant="outlined" divided density="compact" class="mb-3">
              <v-btn value="interval" size="small">固定间隔</v-btn>
              <v-btn value="cron" size="small">Cron 表达式</v-btn>
            </v-btn-toggle>
            <div v-if="scheduleMode === 'interval'">
              <v-select v-model="syncInterval" :items="intervalOptions" hide-details style="max-width:300px;" />
            </div>
            <div v-else>
              <v-text-field v-model="syncCron" hide-details style="max-width:300px;" placeholder="0 2 * * *" hint="分 时 日 月 周" persistent-hint />
            </div>
          </v-card-text>
        </v-card>

        <div class="d-flex ga-3 mb-4">
          <v-btn color="primary" :loading="savingSync" prepend-icon="mdi-content-save" @click="saveConfig">保存同步配置</v-btn>
          <v-btn color="warning" :loading="syncingNow" prepend-icon="mdi-refresh" @click="syncNow">立即同步一次</v-btn>
        </div>
      </div>
    </v-expand-transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getSyncConfig, saveSyncConfig, getSyncStatus, triggerSyncNow } from '@/api/index.js'

const syncEnabled = ref(false)
const playlistIds = ref([])
const playlistInput = ref('')
const playlistLoading = ref(false)
const syncQuality = ref('lossless')
const scheduleMode = ref('interval')
const syncInterval = ref(3600)
const syncCron = ref('')
const savingSync = ref(false)
const syncingNow = ref(false)
const syncRunning = ref(false)
const syncStatusText = ref('同步服务未启用')
const syncExtra = ref('')

const intervalOptions = [
  { title: '10 分钟', value: 600 },
  { title: '30 分钟', value: 1800 },
  { title: '1 小时', value: 3600 },
  { title: '2 小时', value: 7200 },
  { title: '6 小时', value: 21600 },
  { title: '12 小时', value: 43200 },
  { title: '24 小时', value: 86400 },
]

async function loadConfig() {
  try {
    const r = await getSyncConfig()
    if (r?.status === 200 && r.data) {
      const c = r.data
      syncEnabled.value = c.enable_sync
      if (c.playlist_ids) {
        let raw = c.playlist_ids
        if (typeof raw === 'string') raw = raw.split(',').map(s => s.trim()).filter(Boolean)
        playlistIds.value = (Array.isArray(raw) ? raw : []).map(id => ({ id, name: '' }))
      }
      syncQuality.value = c.sync_quality || 'lossless'
      syncInterval.value = c.sync_interval || 3600
      if (c.cron_expression) {
        scheduleMode.value = 'cron'
        syncCron.value = c.cron_expression
      } else {
        scheduleMode.value = 'interval'
      }
    }
  } catch (e) {}
}

async function loadStatus() {
  try {
    const r = await getSyncStatus()
    if (r?.status === 200 && r.data) {
      const s = r.data
      syncRunning.value = true
      syncStatusText.value = s.running ? '同步服务运行中' : '同步服务已配置'
      let e = ''
      if (s.last_sync) e += '上次同步: ' + s.last_sync
      if (s.next_sync) e += (e ? ' | ' : '') + '下次同步: ' + s.next_sync
      syncExtra.value = e
    } else {
      syncRunning.value = false
      syncStatusText.value = '同步服务未启用'
      syncExtra.value = ''
    }
  } catch (e) {
    syncRunning.value = false
  }
}

function addPlaylist() {
  const v = playlistInput.value.trim()
  if (!v) return window.__snackbar?.('请输入歌单ID', 'warning')
  let id = v
  const m = v.match(/playlist\?id=(\d+)/)
  if (m) id = m[1]
  if (!/^\d+$/.test(id)) return window.__snackbar?.('无效的歌单ID', 'warning')
  if (playlistIds.value.some(p => p.id === id)) return window.__snackbar?.('已在列表中', 'warning')
  playlistIds.value.push({ id, name: '' })
  playlistInput.value = ''
}

function removePlaylist(id) {
  playlistIds.value = playlistIds.value.filter(p => p.id !== id)
}

async function saveConfig() {
  if (syncEnabled.value && !playlistIds.value.length) return window.__snackbar?.('请至少添加一个歌单', 'warning')
  savingSync.value = true
  try {
    const r = await saveSyncConfig({
      enable_sync: syncEnabled.value,
      playlist_ids: playlistIds.value.map(p => p.id).join(','),
      sync_quality: syncQuality.value,
      sync_interval: syncInterval.value,
      cron_expression: scheduleMode.value === 'cron' ? syncCron.value.trim() : '',
    })
    window.__snackbar?.(r?.message || '已保存', 'success')
    await loadStatus()
  } catch (e) {
    window.__snackbar?.('保存失败', 'error')
  } finally {
    savingSync.value = false
  }
}

async function syncNow() {
  syncingNow.value = true
  try {
    const r = await triggerSyncNow()
    if (r?.status === 200 && r.data) {
      const d = r.data
      if (d.errors && d.errors.length > 0) {
        const errMsgs = d.errors.map(e => `歌单 ${e.playlist_id}: ${e.error}`).join('；')
        window.__snackbar?.(`${d.message || '同步完成'}；错误: ${errMsgs}`, 'warning')
      } else {
        window.__snackbar?.(d.message || '同步已启动', 'success')
      }
    } else {
      window.__snackbar?.(r?.message || '同步失败', 'error')
    }
  } catch (e) {
    window.__snackbar?.('同步失败', 'error')
  } finally {
    syncingNow.value = false
    await loadStatus()
  }
}

onMounted(() => {
  loadConfig()
  loadStatus()
  setInterval(loadStatus, 10000)
})
</script>

<style scoped>
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
.status-dot.on { background: #22c55e; }
.status-dot.off { background: #9ca3af; }
</style>
