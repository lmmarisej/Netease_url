<template>
  <div>
    <div class="d-flex align-center mb-5"><v-icon size="32" color="primary" class="mr-3">mdi-cog-outline</v-icon><h2 class="text-h4 font-weight-bold">配置</h2></div>
    <v-tabs v-model="activeTab" class="mb-6"><v-tab value="sync">同步配置</v-tab><v-tab value="download">下载配置</v-tab><v-tab value="cookie">Cookie 配置</v-tab></v-tabs>
    <v-window v-model="activeTab">
      <v-window-item value="sync">
        <v-alert :type="syncRunning?'success':'warning'" variant="tonal" class="mb-4" density="compact">
          <div class="d-flex align-center"><div class="status-dot mr-2" :class="syncRunning?'on':'off'"/><span>{{ syncStatusText }}</span><v-spacer/><span class="text-caption">{{ syncExtra }}</span></div>
        </v-alert>
        <v-card class="mb-4">
          <v-card-text class="d-flex align-center justify-space-between"><div><div class="text-subtitle-1 font-weight-bold">启用定时同步</div><span class="text-caption text-medium-emphasis">开启后将按设定周期自动同步歌单到本地</span></div><v-switch v-model="syncEnabled" color="success" hide-details class="flex-shrink-0"/></v-card-text>
        </v-card>
        <v-expand-transition><div v-if="syncEnabled">
          <v-card class="mb-4"><v-card-title class="text-subtitle-1 font-weight-bold">歌单管理</v-card-title>
            <v-card-text>
              <div class="d-flex ga-2 mb-3" style="max-width:500px;"><v-text-field v-model="playlistInput" hide-details placeholder="输入歌单ID或链接" @keydown.enter="addPlaylist"/><v-btn color="primary" @click="addPlaylist" :loading="playlistLoading">添加</v-btn></div>
              <div v-if="playlistIds.length===0" class="text-caption text-medium-emphasis">尚未添加歌单</div>
              <div v-else class="d-flex flex-wrap ga-2"><v-chip v-for="p in playlistIds" :key="p.id" closable variant="tonal" color="primary" @click:close="removePlaylist(p.id)">📋 {{ p.name||p.id }}<template v-if="p.name"><small class="text-medium-emphasis ml-1">({{ p.id }})</small></template></v-chip></div>
            </v-card-text>
          </v-card>
          <v-card class="mb-4"><v-card-title class="text-subtitle-1 font-weight-bold">同步音质</v-card-title>
            <v-card-text><v-btn-toggle v-model="syncQuality" mandatory variant="outlined" divided density="compact"><v-btn value="standard" size="small">标准</v-btn><v-btn value="exhigh" size="small">极高</v-btn><v-btn value="lossless" size="small">无损</v-btn><v-btn value="hires" size="small">Hi-Res</v-btn><v-btn value="sky" size="small">环绕声</v-btn><v-btn value="jyeffect" size="small">高清环绕</v-btn><v-btn value="jymaster" size="small">母带</v-btn></v-btn-toggle></v-card-text>
          </v-card>
          <v-card class="mb-4"><v-card-title class="text-subtitle-1 font-weight-bold">调度方式</v-card-title>
            <v-card-text>
              <v-btn-toggle v-model="scheduleMode" mandatory variant="outlined" divided density="compact" class="mb-3"><v-btn value="interval" size="small">固定间隔</v-btn><v-btn value="cron" size="small">Cron 表达式</v-btn></v-btn-toggle>
              <div v-if="scheduleMode==='interval'"><v-select v-model="syncInterval" :items="intervalOptions" hide-details style="max-width:300px;"/></div>
              <div v-else><v-text-field v-model="syncCron" hide-details style="max-width:300px;" placeholder="0 2 * * *" hint="分 时 日 月 周" persistent-hint/></div>
            </v-card-text>
          </v-card>
          <div class="d-flex ga-3 mb-4"><v-btn color="primary" :loading="savingSync" prepend-icon="mdi-content-save" @click="saveConfig">保存同步配置</v-btn><v-btn color="warning" :loading="syncingNow" prepend-icon="mdi-refresh" @click="syncNow">立即同步一次</v-btn></div>
        </div></v-expand-transition>
      </v-window-item>
      <v-window-item value="download">
        <v-card class="mb-4"><v-card-title class="text-subtitle-1 font-weight-bold">下载目录</v-card-title><v-card-text><v-text-field v-model="downloadDir" hide-details style="max-width:400px;" placeholder="downloads" hint="音乐文件保存的目标文件夹" persistent-hint/></v-card-text></v-card>
        <v-card class="mb-4"><v-card-text class="d-flex align-center justify-space-between"><div><div class="text-subtitle-1 font-weight-bold mb-1">保存到本地</div><span class="text-caption text-medium-emphasis">开启后音乐文件保存到服务器本地</span></div><v-switch v-model="saveLocal" color="success" hide-details/></v-card-text>
          <v-expand-transition><v-card-text v-if="saveLocal" style="border-top:1px solid rgb(var(--v-theme-surface-variant));"><v-checkbox v-model="browserDownload" label="浏览器同时下载" hide-details density="compact"/><small class="text-medium-emphasis">勾选后浏览器也会下载文件</small></v-card-text></v-expand-transition>
        </v-card>
        <v-btn color="primary" :loading="savingDownload" prepend-icon="mdi-content-save" @click="saveDownloadSettings">保存下载配置</v-btn>
      </v-window-item>
      <v-window-item value="cookie">
        <v-card><v-card-title class="text-subtitle-1 font-weight-bold">Cookie 配置</v-card-title>
          <v-card-text>
            <p class="text-caption text-medium-emphasis mb-3">粘贴网易云音乐黑胶会员 Cookie</p>
            <v-alert :type="cookieValid?'success':'warning'" variant="tonal" density="compact" class="mb-3"><template v-if="cookieValid">已检测到有效 Cookie</template><template v-else>未检测到有效 Cookie</template></v-alert>
            <v-textarea v-model="cookieContent" rows="6" placeholder="MUSIC_U=xxx; __csrf=xxx; ..." style="font-family:monospace;font-size:13px;" class="mb-2"/>
            <small class="text-medium-emphasis">Cookie 保存在 config/cookie.txt</small>
            <div class="d-flex ga-2 mt-4"><v-btn color="primary" :loading="savingCookie" prepend-icon="mdi-content-save" @click="saveCookie">保存 Cookie</v-btn><v-btn color="error" :loading="clearingCookie" prepend-icon="mdi-delete" @click="clearCookie">清空 Cookie</v-btn></div>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { getSyncConfig, saveSyncConfig, getSyncStatus, triggerSyncNow, getCookie, saveCookie as apiSaveCookie, getSettings, saveSettings } from '@/api/index.js'
const activeTab=ref('sync')
const syncEnabled=ref(false),playlistIds=ref([]),playlistInput=ref(''),playlistLoading=ref(false),syncQuality=ref('lossless'),scheduleMode=ref('interval')
const syncInterval=ref(3600),syncCron=ref(''),savingSync=ref(false),syncingNow=ref(false),syncRunning=ref(false),syncStatusText=ref('同步服务未启用'),syncExtra=ref('')
const intervalOptions=[{title:'10 分钟',value:600},{title:'30 分钟',value:1800},{title:'1 小时',value:3600},{title:'2 小时',value:7200},{title:'6 小时',value:21600},{title:'12 小时',value:43200},{title:'24 小时',value:86400}]
const downloadDir=ref('downloads'),saveLocal=ref(true),browserDownload=ref(false),savingDownload=ref(false)
const cookieContent=ref(''),cookieValid=ref(false),savingCookie=ref(false),clearingCookie=ref(false)
async function loadConfig(){try{const r=await getSyncConfig();if(r?.status===200&&r.data){const c=r.data;syncEnabled.value=c.enable_sync;if(c.playlist_ids){let raw=c.playlist_ids;if(typeof raw==='string')raw=raw.split(',').map(s=>s.trim()).filter(Boolean);playlistIds.value=(Array.isArray(raw)?raw:[]).map(id=>({id,name:''}))}syncQuality.value=c.sync_quality||'lossless';syncInterval.value=c.sync_interval||3600;if(c.cron_expression){scheduleMode.value='cron';syncCron.value=c.cron_expression}else scheduleMode.value='interval'}}catch(e){}}
async function loadStatus(){try{const r=await getSyncStatus();if(r?.status===200&&r.data){const s=r.data;syncRunning.value=true;syncStatusText.value=s.running?'同步服务运行中':'同步服务已配置';let e='';if(s.last_sync)e+='上次同步: '+s.last_sync;if(s.next_sync)e+=(e?' | ':'')+'下次同步: '+s.next_sync;syncExtra.value=e}else{syncRunning.value=false;syncStatusText.value='同步服务未启用';syncExtra.value=''}}catch(e){syncRunning.value=false}}
function addPlaylist(){const v=playlistInput.value.trim();if(!v)return window.__snackbar?.('请输入歌单ID','warning');let id=v;const m=v.match(/playlist\?id=(\d+)/);if(m)id=m[1];if(!/^\d+$/.test(id))return window.__snackbar?.('无效的歌单ID','warning');if(playlistIds.value.some(p=>p.id===id))return window.__snackbar?.('已在列表中','warning');playlistIds.value.push({id,name:''});playlistInput.value=''}
function removePlaylist(id){playlistIds.value=playlistIds.value.filter(p=>p.id!==id)}
async function saveConfig(){if(syncEnabled.value&&!playlistIds.value.length)return window.__snackbar?.('请至少添加一个歌单','warning');savingSync.value=true;try{const r=await saveSyncConfig({enable_sync:syncEnabled.value,playlist_ids:playlistIds.value.map(p=>p.id).join(','),sync_quality:syncQuality.value,sync_interval:syncInterval.value,cron_expression:scheduleMode.value==='cron'?syncCron.value.trim():''});window.__snackbar?.(r?.message||'已保存','success');await loadStatus()}catch(e){window.__snackbar?.('保存失败','error')}finally{savingSync.value=false}}
async function syncNow(){syncingNow.value=true;try{const r=await triggerSyncNow();window.__snackbar?.(r?.message||'同步已启动',r?.success?'success':'warning')}catch(e){window.__snackbar?.('同步失败','error')}finally{syncingNow.value=false}}
async function loadDownloadSettings(){try{const r=await getSettings();if(r?.status===200&&r.data){downloadDir.value=r.data.downloads_dir||r.data.download_dir||'downloads';saveLocal.value=r.data.download_save_local!==false;browserDownload.value=r.data.download_browser===true}}catch(e){}}
async function saveDownloadSettings(){savingDownload.value=true;try{await saveSettings({download_dir:downloadDir.value,download_save_local:saveLocal.value,download_browser:browserDownload.value});window.__snackbar?.('已保存','success')}catch(e){window.__snackbar?.('保存失败','error')}finally{savingDownload.value=false}}
async function loadCookieConfig(){try{const r=await getCookie();if(r?.status===200&&r.data){cookieContent.value=r.data.cookie||'';cookieValid.value=!!r.data.cookie}}catch(e){}}
async function saveCookie(){savingCookie.value=true;try{const r=await apiSaveCookie({cookie:cookieContent.value});window.__snackbar?.(r?.message||'已保存','success');cookieValid.value=!!cookieContent.value.trim()}catch(e){window.__snackbar?.('保存失败','error')}finally{savingCookie.value=false}}
async function clearCookie(){if(!confirm('确定清空Cookie？'))return;clearingCookie.value=true;try{cookieContent.value='';await apiSaveCookie({cookie:''});window.__snackbar?.('已清空','success');cookieValid.value=false}catch(e){window.__snackbar?.('清空失败','error')}finally{clearingCookie.value=false}}
onMounted(()=>{loadConfig();loadStatus();loadDownloadSettings();loadCookieConfig();setInterval(loadStatus,10000)})
</script>
<style scoped>.status-dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex-shrink:0}.status-dot.on{background:#22c55e}.status-dot.off{background:#9ca3af}</style>
