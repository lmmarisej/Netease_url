<template>
  <div>
    <div class="d-flex align-center mb-5">
      <v-icon size="32" color="primary" class="mr-3">mdi-script-text-outline</v-icon>
      <h1 class="text-h4 font-weight-bold">歌词查询</h1>
    </div>

    <v-card class="mb-5" variant="flat" color="surface-variant">
      <v-card-text class="py-4">
        <v-btn-toggle v-model="mode" mandatory density="comfortable" class="mb-4">
          <v-btn value="name" size="small" prepend-icon="mdi-magnify">按名称</v-btn>
          <v-btn value="id" size="small" prepend-icon="mdi-pound">按歌曲ID</v-btn>
        </v-btn-toggle>

        <div v-if="mode === 'name'" class="d-flex align-center ga-3 flex-wrap">
          <v-text-field
            v-model="keyword"
            hide-details
            aria-label="歌曲名称"
            placeholder="输入歌曲中文名称，如：晴天"
            style="min-width:260px;max-width:360px;"
            @keydown.enter="doQuery"
          >
            <template #prepend-inner><v-icon size="18">mdi-music-note</v-icon></template>
          </v-text-field>
          <v-text-field
            v-model="artist"
            hide-details
            aria-label="歌手名（可选）"
            placeholder="歌手名（可选）"
            style="max-width:180px;"
            @keydown.enter="doQuery"
          />
          <v-btn color="primary" :loading="loading" @click="doQuery">查询歌词</v-btn>
        </div>

        <div v-else class="d-flex align-center ga-3 flex-wrap">
          <v-text-field
            v-model="songId"
            hide-details
            aria-label="歌曲 ID 或链接"
            placeholder="输入歌曲ID或网易云链接"
            style="min-width:260px;max-width:420px;"
            @keydown.enter="doQuery"
          >
            <template #prepend-inner><v-icon size="18">mdi-pound</v-icon></template>
          </v-text-field>
          <v-btn color="primary" :loading="loading" @click="doQuery">查询歌词</v-btn>
        </div>

        <div v-if="history.length" class="mt-3">
          <div class="text-caption text-medium-emphasis mb-1">查询历史</div>
          <div class="d-flex flex-wrap ga-1">
            <v-chip
              v-for="(h, i) in history"
              :key="i"
              size="small"
              variant="tonal"
              color="primary"
              closable
              @click="applyHistory(h)"
              @click:close="removeHistory(i)"
            >
              {{ h.label }}
            </v-chip>
          </div>
        </div>
      </v-card-text>
    </v-card>

    <v-alert v-if="error" type="error" variant="tonal" closable class="mb-4" @click:close="error = ''">
      {{ error }}
    </v-alert>

    <v-progress-linear v-if="loading" indeterminate color="primary" rounded class="mb-4" />

    <v-card v-if="result" class="mb-4">
      <v-card-item>
        <div class="d-flex ga-4 align-center">
          <v-img
            :src="result.pic || ''"
            referrerpolicy="no-referrer"
            max-width="96"
            aspect-ratio="1"
            cover
            class="rounded-lg flex-shrink-0"
          >
            <template #error>
              <v-sheet height="96" width="96" color="surface-variant" class="rounded-lg d-flex align-center justify-center">
                <v-icon color="medium-emphasis">mdi-music-note</v-icon>
              </v-sheet>
            </template>
          </v-img>
          <div style="min-width:0;">
            <div class="text-h6 font-weight-bold text-truncate">{{ result.name || '未知歌曲' }}</div>
            <div class="text-body-2 text-medium-emphasis text-truncate">{{ result.ar_name || '--' }}</div>
            <div class="text-caption text-medium-emphasis text-truncate">{{ result.al_name || '' }}</div>
            <div class="mt-2 d-flex ga-1 align-center flex-wrap">
              <v-chip size="x-small" variant="tonal" color="primary">ID: {{ result.id }}</v-chip>
              <v-chip v-if="hasTranslation" size="x-small" variant="tonal" color="success">含翻译</v-chip>
            </div>
          </div>
        </div>
      </v-card-item>

      <v-divider />

      <v-card-text>
        <div class="d-flex align-center ga-3 mb-3 flex-wrap">
          <v-switch
            v-if="hasTranslation"
            v-model="showTranslation"
            label="显示翻译"
            color="success"
            hide-details
            density="compact"
          />
          <v-spacer />
          <v-btn size="small" variant="tonal" prepend-icon="mdi-content-copy" @click="copyLyric">复制歌词</v-btn>
        </div>

        <div class="lyric-box">
          <template v-if="parsedLines.length">
            <div v-for="(line, i) in parsedLines" :key="i" class="lyric-line">
              <div class="lyric-text">{{ line.text || '\u00A0' }}</div>
              <div v-if="showTranslation && line.trans" class="lyric-trans">{{ line.trans }}</div>
            </div>
          </template>
          <div v-else class="text-center text-medium-emphasis py-6">该歌曲暂无歌词文本</div>
        </div>
      </v-card-text>
    </v-card>

    <div v-else-if="!loading" class="text-center text-medium-emphasis py-10">
      <v-icon size="48" class="mb-3">mdi-script-text-outline</v-icon>
      <p>输入歌曲名称或 ID 查询歌词</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { queryLyrics } from '@/api/index.js'

const mode = ref('name')
const keyword = ref('')
const artist = ref('')
const songId = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)
const showTranslation = ref(true)

const HISTORY_KEY = 'lyrics_query_history'
const history = ref(loadHistory())

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch (e) { return [] }
}
function saveHistory(item) {
  try {
    let all = loadHistory().filter(h => h.label !== item.label)
    all.unshift(item)
    all = all.slice(0, 15)
    localStorage.setItem(HISTORY_KEY, JSON.stringify(all))
    history.value = all
  } catch (e) { /* ignore */ }
}
function removeHistory(i) {
  const all = loadHistory()
  all.splice(i, 1)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(all))
  history.value = all
}
function applyHistory(h) {
  mode.value = h.mode
  if (h.mode === 'id') songId.value = h.value
  else { keyword.value = h.value; artist.value = h.artist || '' }
  doQuery()
}

// 解析 LRC：去时间戳，按时间合并翻译
function parseLrc(text) {
  const map = new Map()
  const order = []
  const re = /\[(\d{1,2}):(\d{2})(?:[.:]\d{1,3})?\]/g
  for (const raw of (text || '').split('\n')) {
    const tags = [...raw.matchAll(re)]
    const content = raw.replace(re, '').trim()
    if (!tags.length) continue
    for (const t of tags) {
      const key = `${t[1].padStart(2, '0')}:${t[2]}`
      if (!map.has(key)) order.push(key)
      map.set(key, content)
    }
  }
  return { map, order }
}

const parsedLines = computed(() => {
  if (!result.value) return []
  const lrc = parseLrc(result.value.lyric)
  const tlrc = parseLrc(result.value.tlyric)
  // 无有效时间轴（纯文本歌词）时直接按行展示
  if (!lrc.order.length) {
    return (result.value.lyric || '')
      .split('\n')
      .map(l => l.trim())
      .filter(Boolean)
      .map(t => ({ text: t, trans: '' }))
  }
  return lrc.order.map(k => ({ text: lrc.map.get(k), trans: tlrc.map.get(k) || '' }))
})

const hasTranslation = computed(() => !!(result.value && result.value.tlyric && result.value.tlyric.trim()))

async function doQuery() {
  let params, label
  if (mode.value === 'id') {
    const id = songId.value.trim()
    if (!id) return window.__snackbar?.('请输入歌曲ID', 'warning')
    params = { id }
    label = `ID:${id}`
  } else {
    const kw = keyword.value.trim()
    if (!kw) return window.__snackbar?.('请输入歌曲名称', 'warning')
    params = { keyword: kw, artist: artist.value.trim() }
    label = artist.value.trim() ? `${kw} - ${artist.value.trim()}` : kw
  }

  loading.value = true
  error.value = ''
  result.value = null
  try {
    const res = await queryLyrics(params)
    if (res?.status === 200 && res.data) {
      result.value = res.data
      showTranslation.value = true
      saveHistory({
        mode: mode.value,
        value: mode.value === 'id' ? songId.value.trim() : keyword.value.trim(),
        artist: artist.value.trim(),
        label,
      })
    } else {
      error.value = res?.message || '未查询到歌词'
    }
  } catch (e) {
    error.value = e.response?.data?.message || e.message || '查询失败'
  } finally {
    loading.value = false
  }
}

async function copyLyric() {
  if (!result.value) return
  const text = parsedLines.value
    .map(l => (showTranslation.value && l.trans ? `${l.text}\n${l.trans}` : l.text))
    .join('\n')
  try {
    await navigator.clipboard.writeText(text)
    window.__snackbar?.('歌词已复制', 'success')
  } catch (e) {
    window.__snackbar?.('复制失败', 'error')
  }
}
</script>

<style scoped>
.lyric-box {
  max-height: 60vh;
  overflow-y: auto;
  padding: 4px 2px;
}
.lyric-line {
  padding: 6px 0;
  text-align: center;
}
.lyric-text {
  font-size: 15px;
  line-height: 1.5;
  color: rgb(var(--v-theme-on-surface));
}
.lyric-trans {
  font-size: 13px;
  line-height: 1.4;
  margin-top: 2px;
  color: rgb(var(--v-theme-on-surface-variant));
  opacity: 0.85;
}
</style>
