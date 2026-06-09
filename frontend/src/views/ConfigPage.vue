<template>
  <div>
    <div class="d-flex align-center mb-5"><v-icon size="32" color="primary" class="mr-3">mdi-cog-outline</v-icon><h2 class="text-h4 font-weight-bold">配置</h2></div>
    <v-tabs v-model="activeTab" class="mb-6"><v-tab value="download">下载配置</v-tab><v-tab value="cookie">Cookie 配置</v-tab></v-tabs>
    <v-window v-model="activeTab">
      <v-window-item value="download">
        <v-card class="mb-4"><v-card-title class="text-subtitle-1 font-weight-bold">下载目录</v-card-title><v-card-text><v-text-field v-model="downloadDir" hide-details style="max-width:400px;" placeholder="downloads" hint="音乐文件保存的目标文件夹" persistent-hint/></v-card-text></v-card>
        <v-card class="mb-4"><v-card-title class="text-subtitle-1 font-weight-bold">默认音质</v-card-title>
          <v-card-text>
            <span class="text-caption text-medium-emphasis d-block mb-2">设置下载时的默认音质，避免每次手动选择</span>
            <v-btn-toggle v-model="defaultQuality" mandatory variant="outlined" divided density="compact" style="flex-wrap:wrap"><v-btn value="standard" size="small">标准</v-btn><v-btn value="exhigh" size="small">极高</v-btn><v-btn value="lossless" size="small">无损</v-btn><v-btn value="hires" size="small">Hi-Res</v-btn><v-btn value="sky" size="small">环绕声</v-btn><v-btn value="jyeffect" size="small">高清环绕</v-btn><v-btn value="jymaster" size="small">母带</v-btn></v-btn-toggle>
          </v-card-text>
        </v-card>
        <v-card class="mb-4"><v-card-text class="d-flex align-center justify-space-between"><div><div class="text-subtitle-1 font-weight-bold mb-1">音质写入文件名</div><span class="text-caption text-medium-emphasis">下载文件命名时附带音质标识，如"歌名 [极高].mp3"</span></div><v-switch v-model="qualityInFilename" color="success" hide-details/></v-card-text></v-card>
        <v-card class="mb-4"><v-card-text class="d-flex align-center justify-space-between"><div><div class="text-subtitle-1 font-weight-bold mb-1">同时下载歌词</div><span class="text-caption text-medium-emphasis">开启后将歌词 .lrc 文件保存到歌曲目录</span></div><v-switch v-model="lyricSaveLrc" color="success" hide-details/></v-card-text></v-card>
        <v-card class="mb-4"><v-card-text class="d-flex align-center justify-space-between"><div><div class="text-subtitle-1 font-weight-bold mb-1">保存到本地</div><span class="text-caption text-medium-emphasis">开启后音乐文件保存到服务器本地</span></div><v-switch v-model="saveLocal" color="success" hide-details/></v-card-text>
          <v-expand-transition><v-card-text v-if="saveLocal" style="border-top:1px solid rgb(var(--v-theme-surface-variant));"><v-checkbox v-model="browserDownload" label="浏览器同时下载" hide-details density="compact"/><small class="text-medium-emphasis">勾选后浏览器也会下载文件</small></v-card-text></v-expand-transition>
        </v-card>
        <v-btn color="primary" :loading="savingDownload" prepend-icon="mdi-content-save" @click="saveDownloadSettings">保存下载配置</v-btn>
      </v-window-item>
      <v-window-item value="cookie">
        <v-card class="mb-4"><v-card-title class="d-flex align-center text-subtitle-1 font-weight-bold">Cookie 管理<v-spacer/><v-btn size="small" color="primary" prepend-icon="mdi-plus" @click="addCookieRow">新增</v-btn></v-card-title>
          <v-card-text>
            <p class="text-caption text-medium-emphasis mb-3">第一行为默认 Cookie，系统将使用默认 Cookie 进行 API 请求</p>
            <div v-if="cookieList.length===0" class="text-caption text-medium-emphasis mb-3">暂无 Cookie，点击"新增"添加</div>
            <v-row v-for="(c,i) in cookieList" :key="i" dense class="mb-1 align-center">
              <v-col cols="2" class="d-flex align-center">
                <v-icon :color="i===0?'success':'medium-emphasis'" size="16" class="mr-1">{{ i===0?'mdi-star':'mdi-circle-outline' }}</v-icon>
                <span class="text-caption">{{ i===0?'默认':'' }}</span>
              </v-col>
              <v-col cols="2"><v-text-field v-model="c.name" label="名称" hide-details density="compact"/></v-col>
              <v-col><v-text-field v-model="c.content" label="Cookie" placeholder="MUSIC_U=xxx;" hide-details density="compact" style="font-family:monospace;font-size:12px;"/></v-col>
              <v-col cols="1"><v-btn size="x-small" icon="mdi-delete" variant="text" color="error" @click="doDeleteCookie(i)"/></v-col>
            </v-row>
            <div class="d-flex ga-2 mt-3"><v-btn color="primary" :loading="savingCookie" prepend-icon="mdi-content-save" @click="saveAllCookies">保存全部</v-btn></div>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { getCookie, saveCookie as apiSaveCookie, activateCookie, deleteCookie, getSettings, saveSettings } from '@/api/index.js'
const activeTab=ref('download')
const downloadDir=ref('downloads'),defaultQuality=ref('lossless'),qualityInFilename=ref(true),saveLocal=ref(true),browserDownload=ref(false),lyricSaveLrc=ref(true),savingDownload=ref(false)
const cookieList=ref([]),savingCookie=ref(false)
async function loadDownloadSettings(){try{const r=await getSettings();if(r?.status===200&&r.data){downloadDir.value=r.data.downloads_dir||r.data.download_dir||'downloads';saveLocal.value=r.data.download_save_local!==false;browserDownload.value=r.data.download_browser===true;defaultQuality.value=r.data.download_default_quality||'lossless';qualityInFilename.value=r.data.download_quality_in_filename!==false;lyricSaveLrc.value=r.data.download_lyric_save_lrc!==false}}catch(e){}}
async function saveDownloadSettings(){savingDownload.value=true;try{await saveSettings({download_dir:downloadDir.value,download_save_local:saveLocal.value,download_browser:browserDownload.value,download_default_quality:defaultQuality.value,download_quality_in_filename:qualityInFilename.value,download_lyric_save_lrc:lyricSaveLrc.value});window.__snackbar?.('已保存','success')}catch(e){window.__snackbar?.('保存失败','error')}finally{savingDownload.value=false}}
async function loadCookieConfig(){try{const r=await getCookie();if(r?.status===200&&r.data){cookieList.value=r.data.cookies||[]}}catch(e){}}
function addCookieRow(){cookieList.value.push({name:'',content:''})}
function doDeleteCookie(i){cookieList.value.splice(i,1)}
async function saveAllCookies(){savingCookie.value=true;try{for(const c of cookieList.value){if(!c.name.trim()||!c.content.trim())continue;await apiSaveCookie({name:c.name.trim(),cookie:c.content.trim()})}if(cookieList.value.length>0&&cookieList.value[0].name){await activateCookie(cookieList.value[0].name)}window.__snackbar?.('已保存','success');await loadCookieConfig()}catch(e){window.__snackbar?.('保存失败','error')}finally{savingCookie.value=false}}
onMounted(()=>{loadDownloadSettings();loadCookieConfig()})
</script>
<style scoped>.status-dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex-shrink:0}.status-dot.on{background:#22c55e}.status-dot.off{background:#9ca3af}</style>
