<template>
  <div>
    <div class="d-flex align-center mb-5">
      <v-icon size="32" color="primary" class="mr-3">mdi-folder-multiple</v-icon>
      <h2 class="text-h4 font-weight-bold">文件管理</h2>
    </div>
    <v-slide-y-transition>
      <v-card v-if="playerFilename" class="mb-4" variant="tonal" color="primary">
        <v-card-text class="d-flex align-center ga-3 py-2">
          <v-icon class="flex-shrink-0">mdi-music-note</v-icon>
          <strong class="text-body-2 text-truncate" style="max-width:280px;">{{ playerFilename }}</strong>
          <audio ref="audioPlayer" controls style="flex:1;min-width:0;" :src="playerUrl" />
          <v-btn icon="mdi-close" size="small" variant="text" @click="stopPlayer" />
        </v-card-text>
      </v-card>
    </v-slide-y-transition>
    <v-card class="mb-4" variant="flat" color="surface-variant">
      <v-card-text class="d-flex align-center flex-wrap ga-4 py-3">
        <span class="text-body-2 text-medium-emphasis">{{ dirInfo }}</span>
        <v-switch v-model="audioOnly" label="仅音频" hide-details color="primary" />
        <v-text-field v-model="extFilter" label="扩展名过滤" hide-details style="max-width:160px;" placeholder="如 yml" clearable />
        <v-checkbox v-model="ignoreCase" label="忽略大小写" hide-details />
        <v-btn variant="tonal" prepend-icon="mdi-refresh" @click="loadFiles">刷新</v-btn>
        <v-spacer />
        <v-btn color="error" variant="tonal" prepend-icon="mdi-delete" @click="deleteSelected" :disabled="selectedFiles.length === 0">
          批量删除{{ selectedFiles.length > 0 ? ` (${selectedFiles.length})` : '' }}
        </v-btn>
      </v-card-text>
    </v-card>
    <v-card>
      <v-data-table
        v-model="selectedFiles" :items="filteredFiles" :headers="headers" show-select
        item-value="name" :loading="loading" hover density="compact" no-data-text="暂无匹配文件"
      >
        <template #item.name="{ item }">
          <span :title="item.name">
            <v-icon v-if="isAudio(item.name)" size="small" class="mr-1">mdi-music-note</v-icon>
            <v-icon v-else size="small" class="mr-1">mdi-file-document</v-icon>
            {{ item.name }}
          </span>
        </template>
        <template #item.size="{ item }">{{ formatSize(item.size) }}</template>
        <template #item.modified="{ item }"><span class="text-caption text-medium-emphasis">{{ item.modified || '--' }}</span></template>
        <template #item.actions="{ item }">
          <div class="d-flex ga-1">
            <v-btn v-if="isAudio(item.name)" size="x-small" variant="tonal" color="primary" icon="mdi-play" @click="playAudio(item.name)" />
            <v-btn v-if="isTextFile(item.name)" size="x-small" variant="tonal" color="info" icon="mdi-pencil" @click="editFile(item.name)" />
            <v-btn size="x-small" variant="tonal" icon="mdi-download" @click="downloadFile(item.name)" />
            <v-btn size="x-small" variant="tonal" color="error" icon="mdi-delete" @click="deleteFile(item.name)" />
          </div>
        </template>
      </v-data-table>
    </v-card>
    <v-dialog v-model="editDialog" max-width="800px">
      <v-card>
        <v-card-title class="d-flex align-center">✏ 编辑：{{ editingFilename }}<v-spacer /><v-btn icon="mdi-close" variant="text" @click="editDialog = false" /></v-card-title>
        <v-card-text><v-textarea v-model="editContent" rows="20" style="font-family:monospace;font-size:13px;" auto-grow /></v-card-text>
        <v-card-actions class="pa-4"><v-spacer /><v-btn @click="editDialog = false">取消</v-btn><v-btn color="primary" :loading="saving" prepend-icon="mdi-content-save" @click="saveEdit">保存</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="confirmDelete" max-width="420px">
      <v-card>
        <v-card-title>确认删除</v-card-title>
        <v-card-text>
          <template v-if="deleteTargets.length === 1">确定删除文件 "{{ deleteTargets[0] }}"？</template>
          <template v-else>确定删除 {{ deleteTargets.length }} 个文件？</template>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="confirmDelete = false">取消</v-btn><v-btn color="error" :loading="deleting" @click="doDelete">确认删除</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { getFileList, deleteFiles, readFile, saveFile } from '@/api/index.js'
const files=ref([]),selectedFiles=ref([]),loading=ref(false),audioOnly=ref(false),extFilter=ref(''),ignoreCase=ref(true),saving=ref(false),deleting=ref(false)
const playerFilename=ref(''),playerUrl=ref(''),audioPlayer=ref(null)
const editDialog=ref(false),editingFilename=ref(''),editContent=ref('')
const confirmDelete=ref(false),deleteTargets=ref([])
const headers=[{title:'文件名',key:'name',sortable:true},{title:'大小',key:'size',sortable:true},{title:'修改时间',key:'modified',sortable:true},{title:'操作',key:'actions',sortable:false,width:200}]
const dirInfo=computed(()=>`📂 downloads/ (${filteredFiles.value.length}/${files.value.length} 个文件)`)
const filteredFiles=computed(()=>{let r=files.value;if(audioOnly.value)r=r.filter(f=>/\.(mp3|flac|m4a|wav|ogg|wma)$/i.test(f.name));if(extFilter.value.trim()){const e=extFilter.value.trim().replace(/[.*+?^${}()|[\]\\]/g,'\\$&');r=r.filter(f=>new RegExp('\\.'+e+'$',ignoreCase.value?'i':'').test(f.name))}return r})
function formatSize(b){return b?(b/1048576).toFixed(2)+' MB':'0.00 MB'}
function isAudio(n){return /\.(mp3|flac|m4a|wav|ogg|wma)$/i.test(n)}
function isTextFile(n){return !isAudio(n)&&!/\.(png|jpg|jpeg|gif|bmp|ico|svg|mp4|mkv|avi|mov|zip|rar|7z|gz|tar|exe|dll|so|bin)$/i.test(n)}
async function loadFiles(){loading.value=true;try{const r=await getFileList();if(r?.status===200)files.value=r.data?.files||[]}catch(e){window.__snackbar?.('加载失败','error')}finally{loading.value=false}}
function playAudio(fn){playerFilename.value=fn;playerUrl.value='/api/files/stream/'+encodeURIComponent(fn)}
function stopPlayer(){if(audioPlayer.value){audioPlayer.value.pause();audioPlayer.value.src=''}playerFilename.value=''}
function downloadFile(fn){window.open('/api/files/stream/'+encodeURIComponent(fn)+'?download=1','_blank')}
function deleteFile(fn){deleteTargets.value=[fn];confirmDelete.value=true}
function deleteSelected(){if(!selectedFiles.value.length)return window.__snackbar?.('请先选择文件','warning');deleteTargets.value=[...selectedFiles.value];confirmDelete.value=true}
async function doDelete(){deleting.value=true;let d=0;for(const fn of deleteTargets.value){try{await deleteFiles({filename:fn});d++}catch(e){}}window.__snackbar?.(`已删除 ${d} 个文件`,'success');confirmDelete.value=false;selectedFiles.value=[];await loadFiles();deleting.value=false}
async function editFile(fn){try{editingFilename.value=fn;const r=await readFile(fn);if(r?.status===200){editContent.value=r.data.content;editDialog.value=true}else window.__snackbar?.(r?.message||'读取失败','error')}catch(e){window.__snackbar?.('读取失败','error')}}
async function saveEdit(){saving.value=true;try{const r=await saveFile({filename:editingFilename.value,content:editContent.value});window.__snackbar?.(r?.message||'已保存','success');editDialog.value=false}catch(e){window.__snackbar?.('保存失败','error')}finally{saving.value=false}}
onMounted(()=>loadFiles())
</script>
