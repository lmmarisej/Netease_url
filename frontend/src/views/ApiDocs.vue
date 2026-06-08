 <template>
  <div>
    <div class="d-flex align-center mb-6">
      <v-icon size="32" color="primary" class="mr-3">mdi-book-open-variant</v-icon>
      <h2 class="text-h4 font-weight-bold">API 接口文档</h2>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" class="mb-4" closable>
      {{ error }}
    </v-alert>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" rounded />

    <template v-if="!loading && !error && apiData">
      <div class="api-hero rounded-xl pa-8 mb-8 text-white">
        <h2 class="text-h4 font-weight-bold">{{ apiData.title || 'API 文档' }}</h2>
        <div class="d-flex align-center ga-3 mt-3">
          <v-chip variant="outlined" color="white" size="small">v{{ apiData.version || '1.0' }}</v-chip>
          <span class="text-body-2" style="opacity:0.85;">{{ apiData.description || '' }}</span>
        </div>
      </div>

      <v-card v-for="(cat, ci) in (apiData.categories || [])" :key="ci" class="mb-6">
        <v-card-title
          class="d-flex align-center pa-5 cursor-pointer cat-header"
          @click="cat._open = !cat._open"
        >
          <v-icon size="24" color="primary" class="mr-3">{{ cat.icon || 'mdi-api' }}</v-icon>
          <span class="text-h6 font-weight-bold">{{ cat.name }}</span>
          <v-spacer />
          <v-chip size="small" variant="tonal" color="primary">{{ (cat.endpoints || []).length }} 接口</v-chip>
          <v-icon class="ml-2" size="20" color="medium-emphasis">{{ cat._open !== false ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
        </v-card-title>

        <v-expand-transition>
          <div v-show="cat._open !== false">
            <div v-for="(ep, ei) in (cat.endpoints || [])" :key="ei" class="endpoint-divider">
              <div class="d-flex align-center pa-4 cursor-pointer" @click="ep._open = !ep._open">
                <v-chip
                  :color="methodColor(ep.method)"
                  size="small"
                  variant="flat"
                  class="mr-3 font-weight-bold text-uppercase"
                  style="min-width:58px;justify-content:center;"
                >
                  {{ ep.method }}
                </v-chip>
                <code class="text-body-1 font-weight-bold px-3 py-1 rounded-lg ep-path">{{ ep.path }}</code>
                <v-spacer />
                <span class="text-body-2 text-medium-emphasis mr-3 d-none d-sm-inline">{{ ep.summary || '' }}</span>
                <v-icon size="18" color="medium-emphasis">{{ ep._open ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
              </div>

              <v-expand-transition>
                <div v-show="ep._open" class="px-6 pb-4">
                  <p v-if="ep.description" class="text-body-2 text-medium-emphasis mb-4">{{ ep.description }}</p>

                  <template v-if="ep.parameters && ep.parameters.length">
                    <div class="text-overline font-weight-bold text-medium-emphasis mb-2">请求参数</div>
                    <v-table density="compact">
                      <thead><tr><th>参数名</th><th>类型</th><th>必填</th><th>默认值</th><th>说明</th></tr></thead>
                      <tbody>
                        <tr v-for="(p, pi) in ep.parameters" :key="pi">
                          <td><code class="pa-1 rounded bg-surface-variant">{{ p.name }}</code></td>
                          <td><v-chip size="x-small" variant="outlined">{{ p.type || 'string' }}</v-chip></td>
                          <td><span :class="p.required ? 'text-error font-weight-bold' : 'text-medium-emphasis'">{{ p.required ? '是' : '否' }}</span></td>
                          <td><code v-if="p.default" class="pa-1 rounded text-primary">{{ p.default }}</code><span v-else class="text-medium-emphasis">--</span></td>
                          <td>{{ p.description || '' }}</td>
                        </tr>
                      </tbody>
                    </v-table>
                  </template>

                  <template v-if="ep.responses">
                    <div class="text-overline font-weight-bold text-medium-emphasis mb-2 mt-5">响应示例</div>
                    <pre class="text-caption pa-4 rounded-lg response-block">{{ JSON.stringify(ep.responses, null, 2) }}</pre>
                  </template>
                </div>
              </v-expand-transition>
            </div>
          </div>
        </v-expand-transition>
      </v-card>
    </template>

    <div v-if="!loading && !error && !apiData" class="text-center text-medium-emphasis py-12">
      <v-icon size="64" class="mb-4" color="medium-emphasis">mdi-book-open-variant</v-icon>
      <p class="text-body-1">暂无 API 文档数据</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getApiDocs } from '@/api/index.js'

const loading = ref(true)
const error = ref('')
const apiData = ref(null)

function methodColor(method) {
  const map = { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'error', PATCH: 'secondary' }
  return map[(method || '').toUpperCase()] || 'grey'
}

onMounted(async () => {
  try {
    loading.value = true
    const res = await getApiDocs()
    if (res?.status === 200 && res.data) apiData.value = res.data
    else if (res?.data) apiData.value = res.data
  } catch (e) {
    error.value = e.message || '加载 API 文档失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.api-hero { background: linear-gradient(135deg, rgb(var(--v-theme-primary)) 0%, #42A5F5 100%); }
.endpoint-divider { border-top: 1px solid rgb(var(--v-theme-surface-variant)); }
.cat-header { background: rgb(var(--v-theme-primary-lighten-1)); }
.ep-path { background: rgb(var(--v-theme-surface-variant)); }
.response-block { background: rgb(var(--v-theme-surface-variant)); overflow-x:auto; max-height:300px; }
.cursor-pointer { cursor: pointer; }
</style>
