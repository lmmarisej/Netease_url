<template>
  <div class="discover-layout">
    <!-- 左侧：播放器卡片 -->
    <div class="player-col">
      <div class="glass-card player-card">
        <!-- 封面 + 歌词 左右布局 -->
        <div class="player-main">
          <!-- 左侧：CD 唱片封面 -->
          <div class="cd-wrap" :class="{ 'cd-wrap--playing': player.isPlaying.value }">
            <div class="cd-disc">
              <img
                v-if="player.currentTrack.coverUrl"
                :src="player.currentTrack.coverUrl"
                class="cd-cover"
                alt="封面"
              />
              <div v-else class="cd-placeholder">
                <v-icon size="40" color="rgba(var(--v-theme-on-surface),0.2)">mdi-music</v-icon>
              </div>
              <div class="cd-hole" />
            </div>
          </div>
          <!-- 右侧：歌词 -->
          <div class="lyrics-side">
            <div v-if="player.lyricLines.value.length" class="lyrics-scroll">
              <TransitionGroup name="lyric-fade" tag="div">
                <div
                  v-for="(line, i) in player.visibleLyricLines.value"
                  :key="line.idx"
                  class="lyric-line"
                  :class="{ 'lyric-line--active': line.idx === player.activeLyricIdx.value }"
                >{{ line.text }}</div>
              </TransitionGroup>
            </div>
            <div v-else-if="player.lyricLoading.value" class="lyric-placeholder">加载歌词中...</div>
            <div v-else class="lyric-placeholder">暂无歌词</div>
          </div>
        </div>
        <!-- 歌曲信息 -->
        <div class="player-info">
          <div class="player-title text-truncate">{{ player.currentTrack.title || '选择一首歌曲' }}</div>
          <div class="player-artist text-truncate">{{ player.currentTrack.artist || '—' }}</div>
        </div>
        <!-- 进度条 -->
        <div class="progress-row">
          <span class="progress-time">{{ player.formatTime(player.playElapsed.value) }}</span>
          <div class="progress-bar-wrap" @click="handleProgressSeek" ref="progressWrapRef">
            <div class="progress-bar-track">
              <div class="progress-bar" :style="{ width: player.progressPercent.value + '%' }" />
            </div>
          </div>
          <span class="progress-time">{{ player.formatTime(player.currentTrack.duration || 0) }}</span>
        </div>
        <!-- 控制按钮 -->
        <div class="player-controls">
          <!-- 播放模式切换：点击直接轮换 -->
          <v-btn
            :icon="player.currentPlayModeMeta.value.icon"
            variant="text"
            size="small"
            :title="player.currentPlayModeMeta.value.label"
            aria-label="切换播放模式"
            @click="cyclePlayMode"
          />

          <v-btn icon="mdi-skip-previous" variant="text" size="small" :disabled="!player.canPrev.value" @click="player.prevTrack" />
          <v-btn icon size="large" :color="player.isPlaying.value ? 'primary' : undefined" variant="flat" @click="player.togglePlay">
            <v-icon size="28">{{ player.isPlaying.value ? 'mdi-pause' : 'mdi-play' }}</v-icon>
          </v-btn>
          <v-btn icon="mdi-skip-next" variant="text" size="small" :disabled="!player.canNext.value" @click="player.nextTrack" />

          <!-- 待播放队列 -->
          <v-menu location="top" offset="10" :close-on-content-click="false" max-width="380">
            <template #activator="{ props: queueProps }">
              <v-btn
                v-bind="queueProps"
                icon="mdi-playlist-play"
                variant="text"
                size="small"
                title="待播放队列"
                aria-label="待播放队列"
              />
            </template>
            <div class="queue-popover-menu">
              <div class="queue-header">
                <span class="queue-title">待播放列表</span>
                <v-chip size="x-small" variant="flat" color="primary" label>{{ player.queueDisplayTracks.value.length }} 首</v-chip>
              </div>
              <div class="queue-scroll" v-if="player.queueDisplayTracks.value.length">
                <div
                  v-for="(t, i) in player.queueDisplayTracks.value"
                  :key="'q-' + t.track_id + '-' + i"
                  class="queue-item"
                  :class="{ 'queue-item--current': t.track_id === player.currentTrack.track_id }"
                  @click="player.playTrack(t)"
                >
                  <span class="queue-idx">{{ t._qi }}</span>
                  <img v-if="t.cover_url" :src="t.cover_url" class="queue-thumb" alt="" />
                  <div v-else class="queue-thumb-placeholder">
                    <v-icon size="12" color="rgba(var(--v-theme-on-surface),0.25)">mdi-music-note</v-icon>
                  </div>
                  <div class="queue-meta">
                    <div class="queue-name text-truncate">{{ t.title }}</div>
                    <div class="queue-artist text-truncate">{{ t.artist }}</div>
                  </div>
                  <v-chip v-if="t.track_id === player.currentTrack.track_id" size="x-small" variant="flat" color="primary" class="queue-now">播放中</v-chip>
                </div>
              </div>
              <div v-else class="queue-empty">队列为空</div>
            </div>
          </v-menu>
        </div>
      </div>

      <!-- 推荐流列表 -->
      <div class="glass-card recommend-list">
        <div class="card-header">
          <v-icon size="18" color="#a78bfa">mdi-playlist-music</v-icon>
          <span class="card-title">推荐流</span>
          <v-spacer />
          <v-btn
            icon size="x-small" variant="text"
            :color="player.sortOrder.value === 'desc' ? 'primary' : undefined"
            :title="player.sortOrder.value === 'desc' ? '偏好分从高到低' : '偏好分从低到高'"
            @click="player.sortOrder.value = player.sortOrder.value === 'desc' ? 'asc' : 'desc'; player.page.value = 1; player.fetchRecommend()"
          >
            <v-icon size="16">{{ player.sortOrder.value === 'desc' ? 'mdi-sort-descending' : 'mdi-sort-ascending' }}</v-icon>
          </v-btn>
          <span class="card-badge" v-if="player.totalTracks.value">{{ player.totalTracks.value }} 首</span>
        </div>
        <!-- 歌单源 Tab 切换 -->
        <div class="source-tabs">
          <div class="source-tab-row">
            <button
              v-for="src in player.sourceTabs"
              :key="src.value"
              class="source-tab"
              :class="{ 'source-tab--active': player.sourceType.value === src.value }"
              @click="player.switchSource(src.value)"
            >
              <span class="source-tab-icon">{{ src.icon }}</span>
              <span class="source-tab-label">{{ src.label }}</span>
            </button>
          </div>
          <!-- 喜欢歌单搜索 -->
          <div v-if="player.sourceType.value === 'liked'" class="source-tab-extra">
            <v-text-field
              v-model="player.likedSearchKeyword.value"
              label="搜索喜欢的歌曲"
              placeholder="歌名 / 歌手"
              variant="solo-filled" density="compact" hide-details clearable rounded="lg"
              class="liked-search-input"
              prepend-inner-icon="mdi-magnify"
              @click:clear="player.clearLikedSearch()"
              @keyup.enter="player.searchLikedSongs()"
            />
            <v-btn size="small" color="primary" variant="flat" :loading="player.likedSearchLoading.value" @click="player.searchLikedSongs()">搜索</v-btn>
          </div>
          <!-- 自定义歌单 ID 输入 -->
          <div v-if="player.sourceType.value === 'custom_playlist'" class="source-tab-extra">
            <v-text-field
              v-model="player.customPlaylistId.value"
              label="歌单 ID"
              placeholder="输入网易云歌单 ID"
              variant="solo-filled" density="compact" hide-details rounded="lg"
              class="playlist-id-input"
            />
            <v-btn size="small" color="primary" variant="flat" prepend-icon="mdi-refresh" :loading="player.recommendLoading.value" @click="player.fetchRecommend()">刷新</v-btn>
          </div>
        </div>
        <div v-if="player.recommendLoading.value" class="list-loading">
          <v-progress-circular indeterminate size="20" width="2" color="primary" />
          <span class="text-caption text-medium-emphasis ml-2">加载推荐...</span>
        </div>
        <div v-else-if="!player.displayTracks.value.length" class="list-empty">选择歌单源并刷新，发现新音乐</div>
        <template v-else>
        <div ref="trackScrollRef" @scroll="onTrackScroll" class="track-scroll">
        <TransitionGroup name="track-list" tag="div">
          <div
            v-for="t in player.displayTracks.value"
            :key="t.track_id"
            class="track-row"
            :class="{ 'track-row--active': player.currentTrack.track_id === t.track_id }"
            @click="player.playTrack(t)"
          >
            <img v-if="t.cover_url" :src="t.cover_url" class="track-thumb" alt="" />
            <div v-else class="track-thumb-placeholder">
              <v-icon size="14" color="rgba(var(--v-theme-on-surface),0.3)">mdi-music-note</v-icon>
            </div>
            <div class="track-meta">
              <div class="track-name text-truncate">{{ t.title }}</div>
              <div class="track-artist-name text-truncate">{{ t.artist }}</div>
            </div>
            <!-- ⊕ 加入集合 -->
            <v-menu :close-on-content-click="false" location="bottom end">
              <template #activator="{ props: menuProps }">
                <v-btn icon="mdi-playlist-plus" size="x-small" variant="text" v-bind="menuProps" @click.stop="openCollectionMenu(t)" class="track-collection-btn" />
              </template>
              <v-list density="compact" min-width="180" max-height="320" class="collection-menu" style="overflow-y:auto">
                <v-list-item
                  v-for="col in collections"
                  :key="col.id"
                  :title="col.name"
                  :subtitle="col.track_count + ' 首'"
                  @click.stop="toggleCollectionTrack(col, t)"
                >
                  <template #prepend>
                    <v-icon size="16" :color="col._hasTrack ? 'primary' : undefined">
                      {{ col._hasTrack ? 'mdi-check-circle' : 'mdi-circle-outline' }}
                    </v-icon>
                  </template>
                  <template #append>
                    <v-btn
                      icon="mdi-delete-outline"
                      size="x-small"
                      variant="text"
                      color="error"
                      @click.stop="deleteCol(col.id)"
                    />
                  </template>
                </v-list-item>
                <v-divider />
                <v-list-item @click.stop="showNewCollectionDialog = true; newCollectionName = ''; pendingTrack = t">
                  <template #prepend><v-icon size="16" color="primary">mdi-plus</v-icon></template>
                  <v-list-item-title class="text-primary">新建集合</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-menu>
            <v-chip v-if="t.preference_score > 0" size="x-small" variant="flat" :color="player.prefColor(t.preference_score)" class="track-chip track-chip--pref">{{ t.preference_score }}分</v-chip>
            <v-btn icon size="x-small" variant="text" :color="player.likedIds.value.has(Number(t.track_id)) ? 'red' : undefined" @click.stop="player.toggleLike(t)">
              <v-icon size="15">{{ player.likedIds.value.has(Number(t.track_id)) ? 'mdi-heart' : 'mdi-heart-outline' }}</v-icon>
            </v-btn>
          </div>
        </TransitionGroup>
        </div>
        <!-- 懒加载：滚动触发 + 底部状态 -->
        <div v-if="player.loadingMore.value" class="load-more-bar">
          <v-progress-circular indeterminate size="18" width="2" color="primary" />
          <span class="text-caption text-medium-emphasis ml-2">加载更多...</span>
        </div>
        <div v-else-if="player.hasMore.value" class="load-more-bar load-more-bar--btn">
          <v-btn variant="text" size="small" @click="player.loadMore()">
            加载更多（{{ player.totalTracks.value - player.recommendTracks.value.length }} 首待加载）
          </v-btn>
        </div>
        <div v-else-if="player.recommendTracks.value.length >= 20" class="load-more-bar">
          <span class="text-caption text-medium-emphasis">已加载全部 {{ player.totalTracks.value }} 首</span>
        </div>
        </template>
      </div>
    </div>

    <!-- 右侧：播放状态指示 -->
    <div class="source-col">
      <div class="glass-card status-card" v-if="player.currentTrack.track_id">
        <div class="card-header">
          <v-icon size="16" :color="player.isPlaying.value ? 'success' : 'rgba(var(--v-theme-on-surface),0.4)'">
            {{ player.isPlaying.value ? 'mdi-play-circle' : 'mdi-pause-circle' }}
          </v-icon>
          <span class="card-title">播放状态</span>
        </div>
        <div class="status-grid">
          <div class="status-item">
            <span class="status-label">累计聆听</span>
            <span class="status-value">{{ player.formatTime(player.playedAccum.value) }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">总时长</span>
            <span class="status-value">{{ player.formatTime(player.currentTrack.duration || 0) }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">位置</span>
            <span class="status-value">{{ player.progressPercent.value.toFixed(0) }}%</span>
          </div>
          <div class="status-item">
            <span class="status-label">跳过</span>
            <span class="status-value" :class="player.skipStatusClass.value">{{ player.skipStatusText.value }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建集合对话框 -->
    <v-dialog v-model="showNewCollectionDialog" max-width="360">
      <v-card>
        <v-card-title class="text-body-1">新建集合</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="newCollectionName"
            label="集合名称"
            variant="outlined"
            density="compact"
            hide-details
            autofocus
            @keyup.enter="confirmCreateCollection"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showNewCollectionDialog = false">取消</v-btn>
          <v-btn variant="flat" color="primary" :disabled="!newCollectionName.trim()" @click="confirmCreateCollection">创建并添加</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
/* ================================================================
   DiscoverTab.vue — 「发现音乐」Tab
   ================================================================
   接收 parent 传入的 player (useStudioPlayer 实例)
   通过 reactive 对象访问所有 ref，无需 .value
================================================================ */
import { ref } from 'vue'

const props = defineProps({
  /** 播放器实例（useStudioPlayer 返回值） */
  player: { type: Object, required: true },
})

const player = props.player

// 播放模式轮换：顺序 → 随机 → 加权 → 单曲循环 → 顺序
const MODE_ORDER = ['sequential', 'random', 'weighted', 'repeat-one']
function cyclePlayMode() {
  const idx = MODE_ORDER.indexOf(player.playMode.value)
  player.playMode.value = MODE_ORDER[(idx + 1) % MODE_ORDER.length]
  player.showQueue.value = false
}

// 进度条点击：本地计算比例后委托给 composable
const progressWrapRef = ref(null)
function handleProgressSeek(e) {
  if (!player.currentTrack.duration) return
  const wrap = progressWrapRef.value
  if (!wrap) return
  const rect = wrap.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  player.seekProgress(ratio)
}
defineExpose({ progressWrapRef })

// ── 滚动懒加载 ──
const trackScrollRef = ref(null)
function onTrackScroll() {
  const el = trackScrollRef.value
  if (!el || player.loadingMore.value || !player.hasMore.value) return
  // 距离底部 120px 内自动加载
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 80) {
    player.loadMore()
  }
}

// ── 集合管理 ──
import axios from 'axios'

function _authHeaders() {
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}
async function _apiGet(url) { return axios.get(url, { headers: _authHeaders() }) }
async function _apiPost(url, data) { return axios.post(url, data, { headers: _authHeaders() }) }
async function _apiDelete(url) { return axios.delete(url, { headers: _authHeaders() }) }

const collections = ref([])
const showNewCollectionDialog = ref(false)
const newCollectionName = ref('')
const pendingTrack = ref(null)

async function loadCollections() {
  try {
    const res = await _apiGet('/api/v3/collections')
    const body = res?.data
    if (body?.success && Array.isArray(body.data)) {
      collections.value = body.data
    } else {
      console.warn('loadCollections: 响应格式异常', body)
    }
  } catch (e) {
    console.error('loadCollections 失败:', e)
  }
}
loadCollections()

async function openCollectionMenu(track) {
  pendingTrack.value = track
  await loadCollections()
  for (const col of collections.value) {
    col._hasTrack = (col.track_ids || []).includes(String(track.track_id))
  }
}

async function toggleCollectionTrack(col, track) {
  try {
    if (col._hasTrack) {
      await _apiDelete(`/api/v3/collections/${col.id}/tracks/${encodeURIComponent(String(track.track_id))}`)
      col.track_count = Math.max(0, col.track_count - 1)
      col.track_ids = (col.track_ids || []).filter(id => id !== String(track.track_id))
      col._hasTrack = false
      window.__snackbar?.('已从集合移除', 'info')
    } else {
      await _apiPost(`/api/v3/collections/${col.id}/tracks`, {
        track_id: String(track.track_id), title: track.title, artist: track.artist,
      })
      col.track_count = (col.track_count || 0) + 1
      if (!col.track_ids) col.track_ids = []
      col.track_ids.push(String(track.track_id))
      col._hasTrack = true
      window.__snackbar?.(`已添加到「${col.name}」`, 'success')
    }
  } catch (e) {
    console.error('集合操作失败', e)
    window.__snackbar?.('操作失败', 'error')
  }
}

async function deleteCol(id) {
  const col = collections.value.find(c => c.id === id)
  const ok = await window.__confirm({
    title: '解散集合',
    text: `确定解散「${col?.name || '未知'}」？内含 ${col?.track_count || 0} 首歌曲将被移除。`,
    confirmText: '解散',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await _apiDelete(`/api/v3/collections/${id}`)
    collections.value = collections.value.filter(c => c.id !== id)
    window.__snackbar?.('集合已解散', 'info')
  } catch (e) {
    console.error('解散集合失败:', e)
    window.__snackbar?.('操作失败', 'error')
  }
}

async function confirmCreateCollection() {
  const name = newCollectionName.value.trim()
  if (!name) return
  // 检查重复名称
  if (collections.value.some(c => c.name === name)) {
    window.__snackbar?.('集合「' + name + '」已存在', 'warning')
    showNewCollectionDialog.value = false
    newCollectionName.value = ''
    return
  }
  showNewCollectionDialog.value = false
  newCollectionName.value = ''
  try {
    const res = await _apiPost('/api/v3/collections', { name })
    if (res?.data?.success) {
      const newCol = res.data.data
      newCol._hasTrack = false
      newCol.track_ids = []
      if (pendingTrack.value) {
        try {
          await _apiPost(`/api/v3/collections/${newCol.id}/tracks`, {
            track_id: String(pendingTrack.value.track_id),
            title: pendingTrack.value.title,
            artist: pendingTrack.value.artist,
          })
          newCol.track_count = 1
          newCol.track_ids = [String(pendingTrack.value.track_id)]
          newCol._hasTrack = true
        } catch (e) {
          console.error('添加歌曲到集合失败:', e)
        }
      }
      collections.value.unshift(newCol)
      window.__snackbar?.(`集合「${name}」已创建`, 'success')
    } else {
      window.__snackbar?.('创建失败: ' + (res?.data?.message || '未知错误'), 'error')
    }
  } catch (e) {
    console.error('创建集合异常:', e)
    window.__snackbar?.('创建失败: ' + (e?.message || '网络错误'), 'error')
  }
}
</script>

<style scoped>
/*
 * 所有 CSS 提取自 StudioHub.vue，范围限 scoped。
 * 全局变量 (--aero-bg, --aero-border, --aero-radius, --aero-shadow, --text-1/2/3)
 * 在父组件 StudioHub.vue 的 <style> 中定义。
 */

/* ── 布局 ── */
.discover-layout {
  display: grid; grid-template-columns: 1fr 280px; gap: 20px; align-items: start;
}
.player-col { display: flex; flex-direction: column; gap: 16px; }
.source-col { display: flex; flex-direction: column; gap: 16px; }

/* ── 播放器卡片 ── */
.player-card { text-align: center; overflow: visible; }
.player-main {
  display: flex !important; gap: 16px; align-items: stretch; margin-bottom: 14px;
  justify-content: center;
}

/* CD 唱片封面 */
.cd-wrap {
  flex: 0 0 auto; width: 150px; height: 150px; align-self: center;
  display: flex; align-items: center; justify-content: center;
}
.cd-disc {
  width: 140px; height: 140px; border-radius: 50%; position: relative;
  background: conic-gradient(from 0deg, rgba(255,255,255,0.06), rgba(255,255,255,0.12), rgba(0,0,0,0.08), rgba(255,255,255,0.06));
  box-shadow: 0 4px 24px rgba(0,0,0,0.2), inset 0 0 0 1px rgba(255,255,255,0.06);
  display: flex; align-items: center; justify-content: center;
}
.cd-wrap--playing .cd-disc {
  animation: cd-spin 20s linear infinite;
}
.cd-cover {
  width: 82px; height: 82px; border-radius: 50%; object-fit: cover;
  position: relative; z-index: 1;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3);
}
.cd-placeholder {
  width: 82px; height: 82px; border-radius: 50%;
  background: rgba(var(--v-theme-on-surface), 0.04);
  display: flex; align-items: center; justify-content: center; z-index: 1;
}
.cd-hole {
  position: absolute; width: 16px; height: 16px; border-radius: 50%;
  background: rgb(var(--v-theme-surface));
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.3), 0 1px 0 rgba(255,255,255,0.05);
  z-index: 2; top: 50%; left: 50%; transform: translate(-50%, -50%);
}
@keyframes cd-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* 歌词区域 */
.lyrics-side { flex: 0 1 240px; min-width: 0; height: 150px; display: flex; flex-direction: column; justify-content: center; }
.lyrics-scroll { overflow: hidden; padding: 4px 0; height: 100%; }
.lyric-line {
  padding: 4px 8px; font-size: 0.78rem; color: var(--text-3);
  border-radius: 4px; transition: all 0.35s; line-height: 1.6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.lyric-line--active { color: var(--text-1); font-weight: 600; font-size: 0.85rem; }
.lyric-placeholder { display: flex; align-items: center; justify-content: center; min-height: 100px; color: var(--text-3); font-size: 0.8rem; }

.lyric-fade-enter-active { transition: all 0.3s ease; }
.lyric-fade-leave-active { transition: all 0.2s ease; }
.lyric-fade-enter-from { opacity: 0; transform: translateY(8px); }
.lyric-fade-leave-to { opacity: 0; transform: translateY(-8px); }

.player-info { margin-bottom: 12px; }
.player-title { font-size: 1.05rem; font-weight: 700; color: var(--text-1); max-width: 260px; margin: 0 auto; }
.player-artist { font-size: 0.82rem; color: var(--text-2); margin-top: 2px; max-width: 260px; margin-left: auto; margin-right: auto; }

.progress-row { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; padding: 0 8px; }
.progress-time { font-size: 0.7rem; color: var(--text-3); font-variant-numeric: tabular-nums; min-width: 32px; }
.progress-bar-wrap { flex: 1; height: 20px; display: flex; align-items: center; cursor: pointer; position: relative; }
.progress-bar-wrap::before { content: ''; position: absolute; inset: -8px 0; z-index: 0; }
.progress-bar-track { position: relative; z-index: 1; width: 100%; height: 4px; background: rgba(var(--v-theme-on-surface), 0.08); border-radius: 2px; overflow: hidden; }
.progress-bar { height: 100%; background: rgb(var(--v-theme-primary)); border-radius: 2px; transition: width 0.25s linear; pointer-events: none; }
.player-controls { display: flex; align-items: center; justify-content: center; gap: 14px; position: relative; }

/* 队列浮窗 */
.queue-popover-menu {
  width: 360px; max-width: 92vw; max-height: 60vh;
  background: rgba(var(--v-theme-surface), 0.98);
  backdrop-filter: blur(40px) saturate(180%); -webkit-backdrop-filter: blur(40px) saturate(180%);
  border-radius: 16px;
  border: 0.5px solid rgba(var(--v-theme-on-surface), 0.15);
  box-shadow: 0 8px 32px rgba(0,0,0,0.25), 0 0 0 0.5px rgba(255,255,255,0.02) inset;
  overflow: hidden; display: flex; flex-direction: column;
}
.queue-header { display: flex; align-items: center; gap: 8px; padding: 14px 16px 10px; border-bottom: 0.5px solid rgba(var(--v-theme-on-surface), 0.10); }
.queue-title { font-size: 0.85rem; font-weight: 700; color: rgb(var(--v-theme-on-surface)); }
.queue-scroll { flex: 1; overflow-y: auto; overscroll-behavior: contain; padding: 6px 8px; }
.queue-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 12px; cursor: pointer; transition: background 0.15s; }
.queue-item:hover { background: rgba(var(--v-theme-on-surface), 0.04); }
.queue-item--current { background: rgba(var(--v-theme-primary), 0.08); }
.queue-idx { width: 22px; text-align: center; font-size: 0.7rem; font-weight: 600; color: rgba(var(--v-theme-on-surface), 0.5); font-variant-numeric: tabular-nums; flex-shrink: 0; }
.queue-item--current .queue-idx { color: rgb(var(--v-theme-primary)); }
.queue-thumb { width: 36px; height: 36px; border-radius: 8px; object-fit: cover; flex-shrink: 0; }
.queue-thumb-placeholder { width: 36px; height: 36px; border-radius: 8px; background: rgba(var(--v-theme-on-surface), 0.04); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.queue-meta { flex: 1; min-width: 0; }
.queue-name { font-size: 0.8rem; font-weight: 700; color: rgb(var(--v-theme-on-surface)); }
.queue-artist { font-size: 0.72rem; font-weight: 500; color: rgba(var(--v-theme-on-surface), 0.7); margin-top: 1px; }
.queue-now { flex-shrink: 0; }
.queue-empty { padding: 24px 0; text-align: center; font-size: 0.8rem; color: rgba(var(--v-theme-on-surface), 0.5); }

/* 推荐流列表 */
.recommend-list { flex: 1; min-height: 0; }
.track-scroll { max-height: 360px; overflow-y: auto; }
.list-loading, .list-empty { display: flex; align-items: center; justify-content: center; padding: 32px 0; color: var(--text-3); font-size: 0.85rem; }
.list-empty { text-align: center; }

.track-row {
  display: flex; align-items: center; gap: 10px; padding: 10px 8px 10px 8px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.04);
  cursor: pointer; border-radius: 10px; transition: background 0.15s;
}
.track-row:hover { background: rgba(var(--v-theme-on-surface), 0.03); }
.track-row--active { background: rgba(var(--v-theme-primary), 0.06); border-color: rgba(var(--v-theme-primary), 0.12); }
.track-thumb { width: 40px; height: 40px; border-radius: 8px; object-fit: cover; flex-shrink: 0; }
.track-thumb-placeholder { width: 40px; height: 40px; border-radius: 8px; background: rgba(var(--v-theme-on-surface), 0.04); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.track-meta { flex: 1; min-width: 0; }
.track-name { font-size: 0.82rem; font-weight: 600; color: var(--text-1); }
.track-artist-name { font-size: 0.72rem; color: var(--text-2); margin-top: 1px; }
.track-chip { flex-shrink: 0; }
.track-collection-btn { opacity: 0; transition: opacity 0.15s; }
.track-row:hover .track-collection-btn { opacity: 1; }

/* ── 毛玻璃卡片（继承父组件 CSS 变量） ── */
.glass-card {
  background: var(--aero-bg);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--aero-border);
  border-radius: var(--aero-radius);
  box-shadow: var(--aero-shadow);
  padding: 18px;
  transition: border-color 0.3s;
}
.glass-card:hover { border-color: rgba(var(--v-theme-on-surface), 0.1); }
.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.card-title { font-weight: 700; font-size: 0.9rem; color: var(--text-1); }
.card-badge {
  font-size: 0.68rem; font-weight: 600; padding: 2px 10px; border-radius: 20px;
  background: rgba(139,92,246,0.12); color: #a78bfa; border: 1px solid rgba(139,92,246,0.2);
}

/* ── 歌单源 Tab ── */
.source-tabs { padding: 0 12px 8px; border-bottom: 1px solid var(--aero-border); }
.source-tab-row { display: flex; gap: 2px; }
.source-tab {
  display: flex; align-items: center; gap: 4px; padding: 6px 14px;
  border: none; border-radius: 10px 10px 0 0; background: transparent;
  color: var(--text-3); font-size: 13px; cursor: pointer; transition: all 0.2s;
}
.source-tab:hover { color: var(--text-1); background: rgba(var(--v-theme-on-surface), 0.04); }
.source-tab--active { color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), 0.08); font-weight: 600; }
.source-tab-icon { font-size: 14px; }
.source-tab-label { white-space: nowrap; }
.source-tab-extra { display: flex; align-items: center; gap: 8px; padding: 8px 0 4px; }
.playlist-id-input { max-width: 200px; }

/* 分页 */
.load-more-bar { display: flex; align-items: center; justify-content: center; padding: 12px; border-top: 1px solid var(--aero-border); }
.load-more-bar--btn { padding: 6px 12px; }

/* 播放状态卡片 */
.status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.status-item { text-align: center; }
.status-label { display: block; font-size: 0.68rem; color: var(--text-3); margin-bottom: 2px; }
.status-value { font-size: 0.9rem; font-weight: 700; color: var(--text-1); font-variant-numeric: tabular-nums; }
.status-warn { color: #f59e0b !important; }
.status-ok { color: #4ade80 !important; }

/* 动画 */
.track-list-enter-active, .track-list-leave-active { transition: all 0.3s cubic-bezier(0.4,0,0.2,1); }
.track-list-enter-from { opacity: 0; transform: translateY(-8px); }
.track-list-leave-to { opacity: 0; transform: translateX(-12px); }

@media (max-width: 860px) {
  .discover-layout { grid-template-columns: 1fr; }
}
</style>
