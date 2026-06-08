import { createApp } from 'vue'
import { createVuetify } from 'vuetify'
import { zhHans } from 'vuetify/locale'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import App from './App.vue'
import router from './router'

const vuetify = createVuetify({
  locale: {
    locale: 'zhHans',
    messages: { zhHans },
  },
  components,
  directives,
  defaults: {
    VCard: {
      rounded: 'xl',
      elevation: 2,
    },
    VBtn: {
      rounded: 'lg',
    },
    VChip: {
      rounded: 'lg',
    },
    VTextField: {
      variant: 'outlined',
      density: 'comfortable',
      rounded: 'lg',
      hideDetails: 'auto',
    },
    VSelect: {
      variant: 'outlined',
      density: 'comfortable',
      rounded: 'lg',
      hideDetails: 'auto',
    },
    VTextarea: {
      variant: 'outlined',
      density: 'comfortable',
      rounded: 'lg',
    },
    VSwitch: {
      color: 'primary',
      density: 'comfortable',
      hideDetails: 'auto',
    },
    VTabs: {
      color: 'primary',
      density: 'comfortable',
    },
    VAlert: {
      rounded: 'lg',
    },
  },
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        dark: false,
        colors: {
          background: '#F5F5F5',
          surface: '#FFFFFF',
          'surface-bright': '#FFFFFF',
          'surface-variant': '#E8EAED',
          'on-surface-variant': '#3C4043',
          primary: '#1976D2',
          'primary-darken-1': '#1565C0',
          secondary: '#5F6368',
          accent: '#1976D2',
          error: '#D93025',
          info: '#1967D2',
          success: '#188038',
          warning: '#F9AB00',
        }
      },
      dark: {
        dark: true,
        colors: {
          background: '#121212',
          surface: '#1E1E1E',
          'surface-bright': '#2C2C2C',
          'surface-variant': '#2C2C2C',
          'on-surface-variant': '#9AA0A6',
          primary: '#8AB4F8',
          'primary-darken-1': '#A8C7FA',
          secondary: '#9AA0A6',
          accent: '#8AB4F8',
          error: '#F28B82',
          info: '#8AB4F8',
          success: '#81C995',
          warning: '#FDD663',
        }
      }
    }
  }
})

const app = createApp(App)
app.use(vuetify)
app.use(router)
app.mount('#app')
