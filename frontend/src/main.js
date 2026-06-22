import { createApp } from 'vue'
import { createVuetify } from 'vuetify'
import { zhHans } from 'vuetify/locale'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import App from './App.vue'
import router from './router'
import './styles/apple-theme.css'

const appleFont = '"PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", "HarmonyOS Sans SC", -apple-system, BlinkMacSystemFont, sans-serif'

const vuetify = createVuetify({
  locale: {
    locale: 'zhHans',
    messages: { zhHans },
  },
  components,
  directives,
  defaults: {
    global: {
      style: { fontFamily: appleFont },
    },
    VCard: {
      rounded: 'xl',
      elevation: 0,
      flat: true,
    },
    VBtn: {
      rounded: 'xl',
      flat: true,
      class: 'text-none',
    },
    VChip: {
      rounded: 'lg',
    },
    VTextField: {
      variant: 'solo-filled',
      flat: true,
      density: 'comfortable',
      rounded: 'lg',
      hideDetails: 'auto',
    },
    VSelect: {
      variant: 'solo-filled',
      flat: true,
      density: 'comfortable',
      rounded: 'lg',
      hideDetails: 'auto',
    },
    VTextarea: {
      variant: 'solo-filled',
      flat: true,
      density: 'comfortable',
      rounded: 'lg',
    },
    VSwitch: {
      color: 'success',
      density: 'comfortable',
      inset: true,
      hideDetails: 'auto',
    },
    VTabs: {
      color: 'primary',
      density: 'comfortable',
    },
    VAlert: {
      rounded: 'lg',
    },
    VDialog: {
      VCard: { rounded: 'xl' },
    },
  },
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        dark: false,
        colors: {
          background: '#F2F2F7',
          surface: '#FFFFFF',
          'surface-bright': '#FFFFFF',
          'surface-light': '#F2F2F7',
          'surface-variant': '#E5E5EA',
          'on-surface-variant': '#3C3C43',
          primary: '#007AFF',
          'primary-darken-1': '#0066D6',
          secondary: '#8E8E93',
          accent: '#5856D6',
          error: '#FF3B30',
          info: '#5AC8FA',
          success: '#34C759',
          warning: '#FF9500',
        }
      },
      dark: {
        dark: true,
        colors: {
          background: '#000000',
          surface: '#1C1C1E',
          'surface-bright': '#2C2C2E',
          'surface-light': '#2C2C2E',
          'surface-variant': '#2C2C2E',
          'on-surface-variant': '#EBEBF5',
          primary: '#0A84FF',
          'primary-darken-1': '#409CFF',
          secondary: '#8E8E93',
          accent: '#5E5CE6',
          error: '#FF453A',
          info: '#64D2FF',
          success: '#30D158',
          warning: '#FF9F0A',
        }
      }
    }
  }
})

const app = createApp(App)
app.use(vuetify)
app.use(router)
app.mount('#app')
