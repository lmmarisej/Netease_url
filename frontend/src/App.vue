<template>
  <v-app>
    <!-- 顶部应用栏 -->
    <v-app-bar flat density="compact" color="surface" elevation="1">
      <v-app-bar-nav-icon>
        <v-icon size="28" color="primary">mdi-music-circle</v-icon>
      </v-app-bar-nav-icon>
      <v-toolbar-title class="text-h6 font-weight-bold">
        <span class="text-primary">Music</span> Toolbox
      </v-toolbar-title>

      <v-spacer />

      <v-btn
        icon
        variant="text"
        @click="toggleTheme"
      >
        <v-icon>{{ isDark ? 'mdi-weather-sunny' : 'mdi-weather-night' }}</v-icon>
      </v-btn>
    </v-app-bar>

    <!-- 侧边导航栏 -->
    <v-navigation-drawer permanent width="180" color="surface">
      <v-list nav density="compact" class="pa-2 mt-2">
        <v-list-item
          v-for="item in menuItems"
          :key="item.to"
          :to="item.to"
          :prepend-icon="item.icon"
          :title="item.title"
          color="primary"
          rounded="lg"
          class="mb-1"
          exact
        />
      </v-list>

      <template #append>
        <v-divider />
        <div class="pa-3 text-center">
          <div class="text-caption text-medium-emphasis">v2.0 · Vuetify 3</div>
        </div>
      </template>
    </v-navigation-drawer>

    <!-- 主内容区 -->
    <v-main>
      <div class="pa-8">
        <router-view v-slot="{ Component }">
          <v-fade-transition mode="out-in">
            <component :is="Component" />
          </v-fade-transition>
        </router-view>
      </div>
    </v-main>

    <!-- 全局通知 -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="2500"
      location="top right"
      variant="elevated"
      rounded="lg"
    >
      {{ snackbar.text }}
      <template #actions>
        <v-btn variant="text" icon="mdi-close" @click="snackbar.show = false" />
      </template>
    </v-snackbar>
  </v-app>
</template>

<script setup>
import { reactive, computed } from 'vue'
import { useTheme } from 'vuetify'

const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)

const menuItems = [
  { to: '/', icon: 'mdi-magnify', title: '业务操作' },
  { to: '/files', icon: 'mdi-folder-multiple', title: '文件管理' },
  { to: '/config', icon: 'mdi-cog-outline', title: '配置' },
  { to: '/magicpush', icon: 'mdi-bell-ring-outline', title: '消息推送' },
  { to: '/tasks', icon: 'mdi-chart-bar', title: '任务监控' },
  { to: '/logs', icon: 'mdi-text-box-outline', title: '运行日志' },
  { to: '/api-docs', icon: 'mdi-code-json', title: 'API 文档' },
]

function toggleTheme() {
  theme.global.name.value = theme.global.current.value.dark ? 'light' : 'dark'
}

const snackbar = reactive({ show: false, text: '', color: 'info' })
function showSnackbar(text, color = 'info') {
  snackbar.text = text
  snackbar.color = color
  snackbar.show = true
}
if (typeof window !== 'undefined') {
  window.__snackbar = showSnackbar
}
</script>

<style scoped>
/* scoped empty - theme handles styling */
</style>
