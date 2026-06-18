<template>
  <div class="api-sidebar">
    <div class="sidebar-head pa-3">
      <v-text-field
        :model-value="searchQuery"
        @update:model-value="$emit('update:searchQuery', $event)"
        prepend-inner-icon="mdi-magnify"
        placeholder="搜索接口..."
        density="compact"
        hide-details
        variant="outlined"
        clearable
      />
      <div class="text-caption text-medium-emphasis mt-2 px-1 d-flex align-center">
        <span>COLLECTIONS</span>
        <v-spacer />
        <v-btn
          variant="text"
          size="x-small"
          icon
          :title="sidebarAllExpanded ? '全部收起' : '全部展开'"
          @click="$emit(sidebarAllExpanded ? 'collapse-all' : 'expand-all')"
        >
          <v-icon size="14">{{ sidebarAllExpanded ? 'mdi-collapse-all' : 'mdi-expand-all' }}</v-icon>
        </v-btn>
      </div>
    </div>

    <div class="sidebar-tree">
      <div v-for="(cat, ci) in filteredCategories" :key="ci" class="sidebar-category">
        <div
          class="sidebar-category-header d-flex align-center pa-2 cursor-pointer"
          @click="$emit('toggle-category', cat.name)"
        >
          <v-icon size="16" class="mr-1" color="medium-emphasis">
            {{ expandedCategories.has(cat.name) ? 'mdi-chevron-down' : 'mdi-chevron-right' }}
          </v-icon>
          <v-icon size="16" class="mr-1" color="primary">mdi-folder-outline</v-icon>
          <span class="text-body-2 font-weight-medium flex-grow-1">{{ cat.name }}</span>
          <span class="text-caption text-medium-emphasis">({{ (filterEndpoints(cat.endpoints) || []).length }})</span>
        </div>

        <div v-show="expandedCategories.has(cat.name)">
          <div
            v-for="(ep, ei) in filterEndpoints(cat.endpoints)"
            :key="ei"
            class="sidebar-endpoint d-flex align-center pa-2 cursor-pointer"
            :class="{ 'sidebar-endpoint-active': activeTabId === getEndpointKey(ep) }"
            @click="$emit('select-endpoint', ep, cat)"
          >
            <span
              class="method-badge mr-2"
              :style="{ color: methodTextColor(ep.method), backgroundColor: methodBgColor(ep.method) }"
            >{{ primaryMethod(ep.method) }}</span>
            <span class="text-caption ep-name" :title="ep.path">{{ ep.path }}</span>
          </div>
        </div>
      </div>

      <div v-if="filteredCategories.length === 0" class="pa-4 text-center text-medium-emphasis text-caption">
        没有匹配的接口
      </div>
    </div>
  </div>
</template>

<script setup>
import { toRef } from 'vue'
import { methodTextColor, methodBgColor, primaryMethod, getEndpointKey } from '@/composables/useApiDocsUtils.js'

const props = defineProps({
  searchQuery: { type: String, default: '' },
  filteredCategories: { type: Array, default: () => [] },
  expandedCategories: { type: Set, default: () => new Set() },
  activeTabId: { type: [String, null], default: null },
  sidebarAllExpanded: { type: Boolean, default: false },
})

defineEmits([
  'update:searchQuery',
  'expand-all',
  'collapse-all',
  'toggle-category',
  'select-endpoint',
])

const searchQuery = toRef(props, 'searchQuery')

function filterEndpoints(endpoints) {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return endpoints || []
  return (endpoints || []).filter(ep =>
    ep.path.toLowerCase().includes(q) ||
    ep.method.toLowerCase().includes(q) ||
    (ep.summary || '').toLowerCase().includes(q)
  )
}
</script>
