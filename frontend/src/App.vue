<template>
  <v-app>
    <!-- 登录页：全屏无布局 -->
    <template v-if="isLoginPage">
      <v-main>
        <router-view />
      </v-main>
    </template>

    <!-- 其他页面：正常布局 -->
    <template v-else>
    <!-- 顶部应用栏 -->
    <v-app-bar flat density="compact" color="surface" elevation="1">
      <v-app-bar-nav-icon
        v-if="isCompact"
        aria-label="打开导航菜单"
        @click="drawer = !drawer"
      />
      <v-app-bar-nav-icon v-else aria-hidden="true">
        <v-icon size="28" color="primary">mdi-music-circle</v-icon>
      </v-app-bar-nav-icon>
      <v-toolbar-title class="text-h6 font-weight-bold">
        <span class="text-primary">Music</span> Toolbox
      </v-toolbar-title>

      <v-spacer />

      <!-- 用户信息 -->
      <v-chip v-if="currentUser" size="small" variant="tonal" color="primary" class="mr-2">
        <v-icon start size="16">mdi-account</v-icon>
        {{ currentUser }}
      </v-chip>

      <v-btn
        v-if="currentUser"
        icon="mdi-logout"
        variant="text"
        size="small"
        title="退出登录"
        aria-label="退出登录"
        @click="handleLogout"
        class="mr-1"
      />

      <v-btn
        icon
        variant="text"
        :aria-label="isDark ? '切换到浅色模式' : '切换到深色模式'"
        :title="isDark ? '浅色模式' : '深色模式'"
        @click="toggleTheme"
      >
        <v-icon>{{ isDark ? 'mdi-weather-sunny' : 'mdi-weather-night' }}</v-icon>
      </v-btn>
    </v-app-bar>

    <!-- 侧边导航栏：桌面/平板常驻不折叠，仅在小屏手机用抽屉式 -->
    <v-navigation-drawer v-model="drawer" :permanent="!isCompact" :temporary="isCompact" width="200" color="surface">
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
        <div class="pa-3 text-center">
          <div class="text-caption text-medium-emphasis">v2.0</div>
        </div>
      </template>
    </v-navigation-drawer>

    <!-- 主内容区 -->
    <v-main>
      <div class="pa-4 pa-sm-6 pa-md-8">
        <router-view v-slot="{ Component }">
          <v-fade-transition mode="out-in">
            <component :is="Component" />
          </v-fade-transition>
        </router-view>
      </div>
    </v-main>
    </template>

    <!-- 全局播放器底栏（v-footer + v-show，始终在 DOM 中让 Vuetify 正确计算布局） -->
    <v-footer v-show="playerFilename" app height="56" class="pa-0" style="border-top:1px solid rgb(var(--v-theme-surface-variant))">
      <div class="d-flex align-center ga-3 px-4 w-100" style="height:56px;background:rgb(var(--v-theme-surface))">
        <v-icon class="flex-shrink-0" color="primary">mdi-music-note</v-icon>
        <strong class="text-body-2 text-truncate" style="max-width:240px;">{{ playerFilename }}</strong>
        <audio ref="audioPlayer" controls autoplay style="flex:1;min-width:0;height:32px" :src="playerUrl" />
        <v-btn icon="mdi-close" size="small" variant="text" aria-label="关闭播放器" @click="stopPlayer" />
      </div>
    </v-footer>

    <!-- 全局确认弹窗 -->
    <v-dialog v-model="confirmState.show" max-width="420">
      <v-card>
        <v-card-title class="d-flex align-center ga-2">
          <v-icon :color="confirmState.confirmColor">mdi-alert-circle-outline</v-icon>{{ confirmState.title }}
        </v-card-title>
        <v-card-text class="text-body-2">{{ confirmState.text }}</v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="resolveConfirm(false)">取消</v-btn>
          <v-btn :color="confirmState.confirmColor" variant="flat" @click="resolveConfirm(true)">{{ confirmState.confirmText }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 全局通知 -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="snackbar.timeout"
      location="top right"
      variant="elevated"
      rounded="lg"
    >
      {{ snackbar.text }}
      <template #actions>
        <v-btn variant="text" icon="mdi-close" aria-label="关闭通知" @click="snackbar.show = false" />
      </template>
    </v-snackbar>
  </v-app>
</template>

<script setup>
import { reactive, computed, ref, nextTick, watch } from 'vue'
import { useTheme, useDisplay } from 'vuetify'
import { useRouter, useRoute } from 'vue-router'

const theme = useTheme()
const router = useRouter()
const route = useRoute()
// 仅在小屏手机(<960px)折叠为抽屉，其余宽度侧边栏常驻不折叠
const { smAndDown: isCompact } = useDisplay()
const isDark = computed(() => theme.global.current.value.dark)
const isLoginPage = computed(() => route.path === '/login' || route.path === '/register')
const currentUser = computed(() => localStorage.getItem('username') || '')

// 抽屉：桌面/平板默认常驻展开，小屏手机默认收起；切换断点时同步
const drawer = ref(!isCompact.value)
watch(isCompact, (compact) => { drawer.value = !compact })
// 小屏手机点击导航项后自动收起抽屉
watch(() => route.path, () => { if (isCompact.value) drawer.value = false })

function handleLogout() {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.replace('/login')
}

const menuItems = [
  { to: '/', icon: 'mdi-magnify', title: '音乐搜索' },
  { to: '/files', icon: 'mdi-folder-multiple', title: '文件管理' },
  { to: '/lyrics', icon: 'mdi-script-text-outline', title: '歌词查询' },
  { to: '/sync', icon: 'mdi-playlist-music', title: '歌单同步' },
  { to: '/studio', icon: 'mdi-view-dashboard-outline', title: '音乐工作室' },
  { to: '/magicpush', icon: 'mdi-bell-ring-outline', title: '消息推送' },
  { to: '/config', icon: 'mdi-cog-outline', title: '配置' },
  { to: '/tasks', icon: 'mdi-chart-bar', title: '任务管理' },
  { to: '/logs', icon: 'mdi-text-box-outline', title: '运行日志' },
  { to: '/api-docs', icon: 'mdi-code-json', title: 'API 文档' },
]

function toggleTheme() {
  theme.global.name.value = theme.global.current.value.dark ? 'light' : 'dark'
}

const snackbar = reactive({ show: false, text: '', color: 'info', timeout: 3000 })
function showSnackbar(text, color = 'info') {
  snackbar.text = text
  snackbar.color = color
  // 错误/警告停留更久，便于阅读
  snackbar.timeout = (color === 'error' || color === 'warning') ? 5000 : 3000
  snackbar.show = true
}
if (typeof window !== 'undefined') {
  window.__snackbar = showSnackbar
}

// 全局确认弹窗（返回 Promise<boolean>）
const confirmState = reactive({ show: false, title: '确认', text: '', confirmText: '确定', confirmColor: 'primary' })
let confirmResolve = null
function showConfirm(opts = {}) {
  if (typeof opts === 'string') opts = { text: opts }
  confirmState.title = opts.title || '确认'
  confirmState.text = opts.text || ''
  confirmState.confirmText = opts.confirmText || '确定'
  confirmState.confirmColor = opts.confirmColor || 'primary'
  confirmState.show = true
  return new Promise((resolve) => { confirmResolve = resolve })
}
function resolveConfirm(val) {
  confirmState.show = false
  if (confirmResolve) { confirmResolve(val); confirmResolve = null }
}
// 通过 ESC / 点击遮罩关闭时视为取消
watch(() => confirmState.show, (v) => {
  if (!v && confirmResolve) { confirmResolve(false); confirmResolve = null }
})
if (typeof window !== 'undefined') {
  window.__confirm = showConfirm
}

// 全局播放器
const playerFilename = ref('')
const playerUrl = ref('')
const audioPlayer = ref(null)

async function playAudio(fn) {
  playerFilename.value = fn
  const token = localStorage.getItem('token') || ''
  playerUrl.value = '/api/files/stream/' + encodeURIComponent(fn) + '?token=' + encodeURIComponent(token)
  await nextTick()
  await nextTick()
  if (audioPlayer.value) {
    audioPlayer.value.load()
    audioPlayer.value.play().catch(() => {})
  }
}
function stopPlayer() {
  if (audioPlayer.value) {
    audioPlayer.value.pause()
    audioPlayer.value.src = ''
  }
  playerFilename.value = ''
}
if (typeof window !== 'undefined') {
  window.__playAudio = playAudio
}
</script>

<style>
/* 临时抽屉遮罩层：overlay 通过 Teleport 渲染在 scoped 之外，需全局样式确保覆盖 v-footer（app z=1004） */
.v-overlay-container {
  z-index: 2400 !important;
}
.v-overlay-container .v-overlay {
  z-index: 2400 !important;
}
</style>
