import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/BusinessOperation.vue')
  },
  {
    path: '/files',
    name: 'Files',
    component: () => import('@/views/FileManagement.vue')
  },
  {
    path: '/config',
    name: 'Config',
    component: () => import('@/views/ConfigPage.vue')
  },
  {
    path: '/magicpush',
    name: 'MagicPush',
    component: () => import('@/views/MagicPush.vue')
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@/views/TaskMonitor.vue')
  },
  {
    path: '/logs',
    name: 'Logs',
    component: () => import('@/views/RunningLogs.vue')
  },
  {
    path: '/api-docs',
    name: 'ApiDocs',
    component: () => import('@/views/ApiDocs.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
