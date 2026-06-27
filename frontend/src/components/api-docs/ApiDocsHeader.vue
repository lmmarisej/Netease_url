<template>
  <div class="api-header-bar d-flex align-center px-4">
    <v-icon size="20" color="primary" class="mr-2">mdi-api</v-icon>
    <span class="text-subtitle-2 font-weight-bold">
      API 接口调试
      <span class="text-caption text-medium-emphasis ml-2">
        工作区: {{ apiMeta.name || '网易云音乐API服务' }} v{{ apiMeta.version || '2.0.0' }}
      </span>
    </span>
    <v-spacer />
    <v-chip v-if="!loading && apiData" size="x-small" variant="tonal" color="primary">
      <v-icon start size="12">mdi-pillar</v-icon>
      {{ endpointsCount }} 接口
    </v-chip>
  </div>
</template>

<script setup>
defineProps({
  apiMeta: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  apiData: { type: Object, default: null },
  endpointsCount: { type: Number, default: 0 },
})
</script>
