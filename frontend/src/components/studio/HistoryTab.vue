<template>
  <div class="glass-card">
    <div class="card-header">
      <v-icon size="18" color="#6b9e78">mdi-history</v-icon>
      <span class="card-title">播放历史</span>
      <v-spacer />
      <span class="card-badge" v-if="historyTotal">{{ historyTotal }} 条</span>
    </div>
    <div v-if="historyLoading" class="list-loading">
      <v-progress-circular indeterminate size="20" width="2" color="primary" />
      <span class="text-caption text-medium-emphasis ml-2">加载中...</span>
    </div>
    <div v-else-if="!historyItems.length" class="list-empty">暂无播放记录</div>
    <div v-else class="history-table-wrap">
      <div class="history-header">
        <span class="h-col col-track">歌曲</span>
        <span class="h-col col-time">播放时长</span>
        <span class="h-col col-skip">状态</span>
        <span class="h-col col-date">时间</span>
      </div>
      <div v-for="item in historyItems" :key="item.id" class="history-row">
        <div class="h-col col-track">
          <div class="ht-title text-truncate">{{ item.title || '未知歌曲' }}</div>
          <div class="ht-artist text-truncate">{{ item.artist || '—' }}</div>
        </div>
        <div class="h-col col-time">
          <span class="ht-dur">{{ formatTime(item.play_duration) }}</span>
          <span class="ht-sep">/</span>
          <span class="ht-total">{{ formatTime(item.total_duration) }}</span>
        </div>
        <div class="h-col col-skip">
          <span v-if="item.is_skipped" class="skip-tag skip-tag--yes">⏭ 跳过</span>
          <span v-else class="skip-tag skip-tag--no">✓ 完播</span>
        </div>
        <div class="h-col col-date">
          <span class="ht-date">{{ formatDate(item.timestamp) }}</span>
        </div>
      </div>
    </div>
    <!-- 分页 -->
    <div v-if="historyTotal > historyPageSize" class="pagination-row">
      <v-btn variant="text" size="small" :disabled="historyPage <= 1" prepend-icon="mdi-chevron-left" @click="historyPage--; fetchHistory()">上一页</v-btn>
      <span class="text-caption text-medium-emphasis">{{ historyPage }} / {{ Math.ceil(historyTotal / historyPageSize) }}</span>
      <v-btn variant="text" size="small" :disabled="historyPage >= Math.ceil(historyTotal / historyPageSize)" append-icon="mdi-chevron-right" @click="historyPage++; fetchHistory()">下一页</v-btn>
    </div>
  </div>
</template>

<script setup>
/* ================================================================
   HistoryTab.vue — 「播放历史」Tab
   ================================================================
   自包含：分页历史加载 + 格式化
================================================================ */
import { ref, onMounted } from 'vue'
import { createAuthAxios } from '@/api/authAxios.js'

const api = createAuthAxios()

const historyItems = ref([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = 20
const historyLoading = ref(false)

async function fetchHistory() {
  historyLoading.value = true
  try {
    const res = await api.get('/api/v3/music/history', { params: { page: historyPage.value, page_size: historyPageSize } })
    const body = res.data?.data
    historyItems.value = body?.items || []
    historyTotal.value = body?.total || 0
  } catch { /* 静默 */ }
  finally { historyLoading.value = false }
}

function formatTime(sec) {
  if (!sec || sec <= 0) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

onMounted(fetchHistory)
</script>

<style scoped>
/* ── 毛玻璃卡片 ── */
.glass-card {
  background: var(--aero-bg, rgba(var(--v-theme-surface), 0.55));
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--aero-border, rgba(var(--v-theme-on-surface), 0.06));
  border-radius: var(--aero-radius, 20px);
  box-shadow: var(--aero-shadow, 0 4px 24px rgba(0,0,0,0.06));
  padding: 18px;
  transition: border-color 0.3s;
}
.glass-card:hover { border-color: rgba(var(--v-theme-on-surface), 0.1); }
.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.card-title { font-weight: 700; font-size: 0.9rem; color: var(--text-1, rgb(var(--v-theme-on-surface))); }
.card-badge {
  font-size: 0.68rem; font-weight: 600; padding: 2px 10px; border-radius: 20px;
  background: rgba(139,92,246,0.12); color: #a78bfa; border: 1px solid rgba(139,92,246,0.2);
}

/* ── 历史表格 ── */
.history-table-wrap { overflow-x: auto; }
.history-header {
  display: flex; align-items: center; padding: 8px 12px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  font-size: 0.72rem; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.05em;
}
.history-row {
  display: flex; align-items: center; padding: 10px 12px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.03);
  transition: background 0.15s; font-size: 0.82rem;
}
.history-row:hover { background: rgba(var(--v-theme-on-surface), 0.02); }
.h-col { display: flex; align-items: center; }
.col-track { flex: 2; min-width: 0; flex-direction: column; align-items: flex-start; }
.col-time { flex: 1; justify-content: center; gap: 3px; }
.col-skip { flex: 0.7; justify-content: center; }
.col-date { flex: 0.8; justify-content: flex-end; }

.ht-title { font-weight: 600; color: var(--text-1); max-width: 100%; }
.ht-artist { font-size: 0.72rem; color: var(--text-2); max-width: 100%; }
.ht-dur { font-weight: 700; font-variant-numeric: tabular-nums; color: var(--text-1); }
.ht-sep { color: var(--text-3); }
.ht-total { color: var(--text-3); font-variant-numeric: tabular-nums; }
.ht-date { color: var(--text-3); font-size: 0.75rem; white-space: nowrap; }

.skip-tag { font-size: 0.7rem; font-weight: 600; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
.skip-tag--yes { background: rgba(245,158,11,0.1); color: #d97706; border: 1px solid rgba(245,158,11,0.2); }
.skip-tag--no { background: rgba(74,222,128,0.08); color: #4ade80; border: 1px solid rgba(74,222,128,0.15); }

.pagination-row { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 16px; }
.list-loading, .list-empty { display: flex; align-items: center; justify-content: center; padding: 32px 0; color: var(--text-3); font-size: 0.85rem; }
</style>
