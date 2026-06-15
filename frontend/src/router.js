import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/BusinessOperation.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/files',
    name: 'Files',
    component: () => import('@/views/FileManagement.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/lyrics',
    name: 'LyricsQuery',
    component: () => import('@/views/LyricsQuery.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/sync',
    name: 'PlaylistSync',
    component: () => import('@/views/PlaylistSync.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/config',
    name: 'Config',
    component: () => import('@/views/ConfigPage.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/magicpush',
    name: 'MagicPush',
    component: () => import('@/views/MagicPush.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@/views/TaskMonitor.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/logs',
    name: 'Logs',
    component: () => import('@/views/RunningLogs.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/api-docs',
    name: 'ApiDocs',
    component: () => import('@/views/ApiDocs.vue'),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 导航守卫：未登录时重定向到 /login
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.meta.requiresAuth !== false && !token) {
    // 需要认证但无 token，跳转登录页
    next('/login')
  } else if (to.path === '/login' && token) {
    // 已登录访问登录页，跳转首页
    next('/')
  } else {
    next()
  }
})

export default router
