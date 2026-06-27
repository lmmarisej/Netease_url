/**
 * usePushConfig.ts — 推送配置管理 Composable
 * ==========================================
 * 从 MagicPush.vue 剥离核心推送规则 CRUD 逻辑。
 */

import { ref, reactive } from 'vue'
import { getPushConfig, savePushConfig } from '@/api/index.js'

export interface PushRule {
  id: string
  name: string
  enabled: boolean
  serverId: string
  events: string[]
  event_template?: { __tplId?: string }
  _collapsed?: boolean
}

export function usePushConfig() {
  const pushConfig = reactive<{ pushes: PushRule[] }>({ pushes: [] })
  const dirty = ref(false)
  const savingAll = ref(false)
  const allCollapsed = ref(false)

  async function loadPushConfig() {
    try {
      const r = await getPushConfig()
      if (r?.data?.pushes) {
        pushConfig.pushes = r.data.pushes.map((p: PushRule) => ({ ...p, _collapsed: p._collapsed ?? true }))
      }
    } catch { /* ignore */ }
  }

  async function saveAllConfig() {
    savingAll.value = true
    try {
      await savePushConfig({ pushes: pushConfig.pushes.map(({ _collapsed, ...p }) => p) })
      dirty.value = false
      ;(window as any).__snackbar?.('推送配置已保存', 'success')
    } catch (e: any) {
      ;(window as any).__snackbar?.('保存失败: ' + (e.message || ''), 'error')
    } finally { savingAll.value = false }
  }

  function addPush() {
    const newPush: PushRule = {
      id: 'push_' + Date.now(),
      name: '新推送',
      enabled: true,
      serverId: '',
      events: [],
      _collapsed: false,
    }
    pushConfig.pushes.push(newPush)
    dirty.value = true
  }

  function toggleEnabled(pushId: string, val: boolean) {
    const p = pushConfig.pushes.find(p => p.id === pushId)
    if (p) { p.enabled = val; dirty.value = true }
  }

  function toggleCollapseAll() {
    allCollapsed.value = !allCollapsed.value
    for (const p of pushConfig.pushes) p._collapsed = allCollapsed.value
  }

  return {
    pushConfig, dirty, savingAll, allCollapsed,
    loadPushConfig, saveAllConfig, addPush, toggleEnabled, toggleCollapseAll,
  }
}
