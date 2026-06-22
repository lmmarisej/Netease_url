<template>
  <div class="register-page fill-height d-flex align-center justify-center" style="background: rgb(var(--v-theme-background)); min-height: 100dvh;">
    <v-container fluid class="d-flex align-center justify-center">
      <v-row align="center" justify="center" class="w-100">
        <v-col cols="12" sm="8" md="5" lg="4" xl="3">
          <v-card class="pa-6" elevation="8" rounded="xl">
            <div class="text-center mb-6">
              <v-icon size="56" color="primary" class="mb-2">mdi-account-plus</v-icon>
              <h1 class="text-h4 font-weight-bold">
                <span class="text-primary">Music</span> Toolbox
              </h1>
              <p class="text-body-2 text-medium-emphasis mt-1">创建您的账号</p>
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

            <v-alert
              v-if="successMsg"
              type="success"
              variant="tonal"
              class="mb-4"
            >
              {{ successMsg }}
            </v-alert>

            <v-form @submit.prevent="handleRegister" :disabled="loading">
              <v-text-field
                v-model="username"
                label="用户名"
                prepend-inner-icon="mdi-account"
                placeholder="3-20 位字母、数字、下划线或中文"
                autocomplete="username"
                autofocus
                :rules="usernameRules"
                class="mb-3"
              />

              <v-text-field
                v-model="password"
                label="密码"
                prepend-inner-icon="mdi-lock"
                placeholder="至少 6 位"
                :type="showPassword ? 'text' : 'password'"
                :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
                autocomplete="new-password"
                :rules="passwordRules"
                class="mb-1"
                @click:append-inner="showPassword = !showPassword"
              />

              <v-text-field
                v-model="confirmPassword"
                label="确认密码"
                prepend-inner-icon="mdi-lock-check"
                placeholder="再次输入密码"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="new-password"
                :rules="confirmPasswordRules"
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
                注 册
              </v-btn>
            </v-form>

            <div class="text-center mt-4">
              <span class="text-body-2 text-medium-emphasis">已有账号？</span>
              <router-link to="/login" class="text-primary text-body-2 font-weight-medium text-decoration-none ml-1">
                立即登录
              </router-link>
            </div>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { register } from '@/api/index.js'

const router = useRouter()
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

const usernameRules = [
  v => !!v || '请输入用户名',
  v => /^[\w\u4e00-\u9fff]{3,20}$/.test(v) || '3-20 位字母、数字、下划线或中文',
]

const passwordRules = [
  v => !!v || '请输入密码',
  v => v.length >= 6 || '密码长度至少 6 位',
]

const confirmPasswordRules = computed(() => [
  v => !!v || '请再次输入密码',
  v => v === password.value || '两次输入的密码不一致',
])

async function handleRegister() {
  // 手动校验
  if (!username.value || !password.value || !confirmPassword.value) return
  if (!/^[\w\u4e00-\u9fff]{3,20}$/.test(username.value)) {
    errorMsg.value = '用户名需为 3-20 位字母、数字、下划线或中文'
    return
  }
  if (password.value.length < 6) {
    errorMsg.value = '密码长度至少 6 位'
    return
  }
  if (password.value !== confirmPassword.value) {
    errorMsg.value = '两次输入的密码不一致'
    return
  }

  loading.value = true
  errorMsg.value = ''
  successMsg.value = ''

  try {
    const res = await register(username.value, password.value)
    if (res?.status === 200 && res.data?.token) {
      successMsg.value = res.message || '注册成功，正在跳转...'
      localStorage.setItem('token', res.data.token)
      localStorage.setItem('username', res.data.username)
      setTimeout(() => {
        router.replace('/')
      }, 800)
    } else {
      errorMsg.value = res?.message || '注册失败'
    }
  } catch (e) {
    errorMsg.value = e.message || '注册失败，请检查网络连接'
  } finally {
    loading.value = false
  }
}
</script>
