<template>
  <div class="login-page fill-height d-flex align-center justify-center" style="background: rgb(var(--v-theme-background)); min-height: 100vh;">
    <v-container fluid class="d-flex align-center justify-center">
      <v-row align="center" justify="center" class="w-100">
        <v-col cols="12" sm="8" md="5" lg="4" xl="3">
          <v-card class="pa-6" elevation="8" rounded="xl">
              <div class="text-center mb-6">
                <v-icon size="56" color="primary" class="mb-2">mdi-music-circle</v-icon>
                <h2 class="text-h4 font-weight-bold">
                  <span class="text-primary">Music</span> Toolbox
                </h2>
                <p class="text-body-2 text-medium-emphasis mt-1">请登录以继续</p>
              </div>

              <v-alert
                v-if="errorMsg"
                type="error"
                variant="tonal"
                closable
                class="mb-4"
                @click:close="errorMsg = ''"
              >
                {{ errorMsg }}
              </v-alert>

              <v-form @submit.prevent="handleLogin" :disabled="loading">
                <v-text-field
                  v-model="username"
                  label="用户名"
                  prepend-inner-icon="mdi-account"
                  placeholder="请输入用户名"
                  autocomplete="username"
                  autofocus
                  :rules="[v => !!v || '请输入用户名']"
                  class="mb-3"
                />

                <v-text-field
                  v-model="password"
                  label="密码"
                  prepend-inner-icon="mdi-lock"
                  placeholder="请输入密码"
                  type="password"
                  autocomplete="current-password"
                  :rules="[v => !!v || '请输入密码']"
                  class="mb-2"
                />

                <v-btn
                  type="submit"
                  color="primary"
                  size="large"
                  block
                  :loading="loading"
                  rounded="lg"
                  class="mt-2"
                >
                  登 录
                </v-btn>
              </v-form>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '@/api/index.js'

const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  if (!username.value || !password.value) return

  loading.value = true
  errorMsg.value = ''

  try {
    const res = await login(username.value, password.value)
    if (res?.status === 200 && res.data?.token) {
      localStorage.setItem('token', res.data.token)
      localStorage.setItem('username', res.data.username)
      router.replace('/')
    } else {
      errorMsg.value = res?.message || '登录失败'
    }
  } catch (e) {
    errorMsg.value = e.message || '登录失败，请检查网络连接'
  } finally {
    loading.value = false
  }
}
</script>
