<template>
  <div>
    <!-- 时段切换 -->
    <div class="slot-switcher">
      <div
        v-for="slot in slots"
        :key="slot.key"
        class="slot-card"
        :class="{ 'slot-card--active': activeSlot === slot.key }"
        :style="{ '--slot-color': slot.color }"
        @click="$emit('update:activeSlot', slot.key)"
      >
        <span class="slot-emoji">{{ slot.icon }}</span>
        <span class="slot-label">{{ slot.label }}</span>
        <span class="slot-time">{{ slot.time }}</span>
      </div>
    </div>

    <!-- 三大面板 -->
    <v-row class="mt-6">
      <v-col v-for="panel in panels" :key="panel.name" cols="12" md="6" xl="4">
        <div class="glass-card mixer-panel">
          <div class="card-header">
            <v-icon size="18" :color="panel.iconColor" class="mr-2">{{ panel.icon }}</v-icon>
            <span class="card-title">{{ panel.name }}</span>
            <v-chip size="x-small" variant="tonal" :color="panel.chipColor" class="ml-2">{{ panel.chip }}</v-chip>
          </div>
          <div class="mixer-body">
            <div
              v-for="param in panel.params"
              :key="param.key"
              class="slider-row"
            >
              <div class="slider-label">
                <span class="slider-name">{{ param.label }}</span>
                <span
                  class="slider-value"
                  :class="{ 'slider-value--active': draggingKey === param.key }"
                  :style="{ '--param-color': param.color }"
                >{{ (weights[param.key] ?? 1.0).toFixed(1) }}</span>
              </div>
              <v-slider
                :model-value="weights[param.key] ?? 1.0"
                :min="0" :max="2" :step="0.1"
                :color="param.color"
                track-size="4" thumb-size="16"
                hide-details density="compact"
                @update:model-value="(v: number) => $emit('update:weight', param.key, v)"
                @start="$emit('drag-start', param.key)"
                @end="$emit('drag-end')"
              />
            </div>
          </div>
        </div>
      </v-col>
    </v-row>

    <div class="save-bar">
      <v-btn color="primary" size="large" :loading="saving" prepend-icon="mdi-content-save" @click="$emit('save')">
        保存权重配置
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SlotDef, MixerPanel, SlotKey } from '@/composables/useWeightMixer.js'

defineProps<{
  slots: SlotDef[]
  panels: MixerPanel[]
  activeSlot: SlotKey
  weights: Record<string, number>
  draggingKey: string | null
  saving: boolean
}>()

defineEmits<{
  (e: 'update:activeSlot', key: SlotKey): void
  (e: 'update:weight', key: string, value: number): void
  (e: 'drag-start', key: string): void
  (e: 'drag-end'): void
  (e: 'save'): void
}>()
</script>

<style scoped>
.slot-switcher { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.slot-card {
  --slot-color: #888;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 14px 10px 12px; border-radius: 14px;
  background: rgba(var(--v-theme-surface), 0.45); backdrop-filter: blur(8px);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.03);
  cursor: pointer; transition: all 0.3s cubic-bezier(0.22,0.61,0.36,1); user-select: none;
}
.slot-card:hover { background: rgba(var(--v-theme-surface), 0.65); transform: translateY(-1px); }
.slot-card--active {
  background: rgba(var(--v-theme-surface), 0.72);
  border-color: color-mix(in srgb, var(--slot-color) 28%, transparent);
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.05), 0 0 20px color-mix(in srgb, var(--slot-color) 12%, transparent);
}
.slot-emoji { font-size: 24px; }
.slot-label { font-size: 12px; font-weight: 600; color: rgb(var(--v-theme-on-surface)); }
.slot-time { font-size: 10px; color: rgba(var(--v-theme-on-surface), 0.38); }
.slot-card--active .slot-label { color: var(--slot-color); }

.mixer-panel { height: 100%; }
.card-header { display: flex; align-items: center; margin-bottom: 14px; }
.card-title { font-weight: 700; font-size: 0.9rem; color: rgb(var(--v-theme-on-surface)); }
.mixer-body { padding: 4px 0; }
.slider-row { margin-bottom: 26px; transition: opacity 0.25s; }
.slider-row:last-child { margin-bottom: 4px; }
.slider-label { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 4px; }
.slider-name { font-size: 12px; font-weight: 500; color: rgba(var(--v-theme-on-surface), 0.6); }
.slider-value { font-size: 14px; font-weight: 700; color: rgba(var(--v-theme-on-surface), 0.38); transition: all 0.25s; }
.slider-value--active { color: var(--param-color); transform: scale(1.18); }
.save-bar { margin-top: 24px; text-align: right; }

@media (max-width: 600px) { .slot-switcher { grid-template-columns: repeat(2, 1fr); } }
</style>
