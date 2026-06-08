<template>
  <div>
    <div class="d-flex align-center mb-5"><v-icon size="32" color="primary" class="mr-3">mdi-bell-ring-outline</v-icon><h2 class="text-h4 font-weight-bold">消息推送</h2></div>
    <v-tabs v-model="activeTab" class="mb-6"><v-tab value="push">Magic Push</v-tab><v-tab value="tpl">消息模板</v-tab></v-tabs>
    <v-window v-model="activeTab">
      <v-window-item value="push">
        <div v-if="!pushConfig.pushes||!pushConfig.pushes.length" class="text-center text-medium-emphasis py-8"><v-icon size="48" class="mb-3">mdi-bell-ring-outline</v-icon><p>暂无推送配置</p></div>
        <v-card v-for="push in (pushConfig.pushes||[])" :key="push.id" class="mb-4">
          <v-card-title class="d-flex align-center py-3" style="background:rgb(var(--v-theme-surface-variant));">
            <v-icon size="20" class="mr-2">mdi-bell</v-icon><span class="text-subtitle-1 font-weight-bold cursor-pointer flex-1-1" @click="push._collapsed=!push._collapsed">{{ push.name||'未命名' }}</span>
            <v-switch :model-value="push.enabled!==false" label="启用" color="success" hide-details density="compact" class="mr-3" @click.stop @update:model-value="v=>updatePush(push.id,'enabled',v)"/>
            <v-btn size="small" color="error" variant="text" prepend-icon="mdi-delete" class="mr-1" @click.stop="removePush(push.id)">删除</v-btn>
            <v-icon size="small" class="cursor-pointer" @click="push._collapsed=!push._collapsed">{{ push._collapsed?'mdi-chevron-down':'mdi-chevron-up' }}</v-icon>
          </v-card-title>
          <v-expand-transition>
            <v-card-text v-if="!push._collapsed" style="border-top:1px solid rgb(var(--v-theme-surface-variant));">
              <v-row dense class="mb-2">
                <v-col cols="12" sm="6"><v-text-field label="推送名称" :model-value="push.name" hide-details @update:model-value="v=>updatePush(push.id,'name',v)"/></v-col>
                <v-col cols="12" sm="6"><v-select label="模板选择" :items="tplSelectItems" :model-value="push.event_template?.__tplId||''" hide-details clearable @update:model-value="v=>selectTemplate(push.id,v)"/></v-col>
              </v-row>
              <v-row v-if="!push.event_template?.__tplId" dense class="mb-3">
                <v-col cols="12" sm="6"><v-text-field label="标题" :model-value="push.title" hide-details @update:model-value="v=>updatePush(push.id,'title',v)"/></v-col>
                <v-col cols="12" sm="6"><v-text-field label="固定内容" :model-value="push.content" hide-details @update:model-value="v=>updatePush(push.id,'content',v)"/></v-col>
              </v-row>
              <div class="mb-3"><div class="text-caption font-weight-bold mb-1">事件选择</div>
                <div class="d-flex flex-wrap ga-1 mb-1"><v-chip v-for="evt in (push.events||[])" :key="evt" size="small" variant="tonal" color="primary" closable @click:close="toggleEvent(push.id,evt)">{{ getEventName(evt) }}</v-chip></div>
                <v-menu location="bottom start" :close-on-content-click="false"><template #activator="{props}"><v-btn size="x-small" variant="tonal" v-bind="props">+ 添加事件</v-btn></template>
                  <v-list density="compact" style="max-height:300px;overflow-y:auto;">
                    <template v-for="cat in eventCatalog" :key="cat.category"><v-list-subheader class="text-caption font-weight-bold text-medium-emphasis">{{ cat.category }}</v-list-subheader>
                      <v-list-item v-for="evt in cat.events" :key="evt.type" :title="evt.name" :subtitle="evt.type" density="compact" @click="toggleEvent(push.id,evt.type)"><template #prepend><div class="event-dot mr-2" :style="{background:getCategoryColor(cat.category)}"/></template></v-list-item>
                    </template>
                  </v-list>
                </v-menu>
              </div>
              <div class="mb-3"><div class="d-flex align-center mb-1"><span class="text-caption font-weight-bold">推送地址</span><v-spacer/><v-btn size="x-small" variant="tonal" prepend-icon="mdi-plus" @click="addUrl(push.id)">添加</v-btn></div>
                <div v-for="url in (push.urls||[])" :key="url.id" class="d-flex align-center ga-2 pa-2 mb-1 rounded bg-surface-variant">
                  <v-text-field :model-value="url.url" hide-details placeholder="Webhook URL" style="flex:1;font-family:monospace;font-size:12px;" @update:model-value="v=>updateUrl(push.id,url.id,'url',v)"/>
                  <v-switch :model-value="url.enabled!==false" color="success" hide-details density="compact" @update:model-value="v=>updateUrl(push.id,url.id,'enabled',v)"/>
                  <v-btn size="x-small" variant="tonal" color="primary" @click="testPush(push.id,url.id)">测试</v-btn>
                  <v-btn size="x-small" icon="mdi-delete" variant="text" color="error" @click="removeUrl(push.id,url.id)"/>
                </div>
              </div>
              <div class="text-caption text-medium-emphasis mt-2">可用变量：{song_name} {artist} {quality} {file_size} {error} {music_id} {playlist_name} {total_synced} {success_count} {total_count} {keyword}</div>
            </v-card-text>
          </v-expand-transition>
        </v-card>
        <div class="mt-3 d-flex ga-2"><v-btn color="primary" prepend-icon="mdi-plus" @click="addPush">新增推送</v-btn><v-btn color="success" prepend-icon="mdi-content-save" :loading="savingAll" @click="saveAllConfig">保存全部配置</v-btn></div>
      </v-window-item>
      <v-window-item value="tpl">
        <div v-if="!pushConfig.templates||!pushConfig.templates.length" class="text-center text-medium-emphasis py-8"><v-icon size="48" class="mb-3">mdi-file-document-outline</v-icon><p>暂无消息模板</p></div>
        <v-card v-for="tpl in (pushConfig.templates||[])" :key="tpl.id" class="mb-4">
          <v-card-text>
            <div class="d-flex align-center mb-2"><strong>{{ tpl.name||'未命名' }}</strong><v-spacer/><span class="text-caption text-medium-emphasis">ID: {{ tpl.id }}</span></div>
            <v-row dense>
              <v-col cols="12" sm="3"><v-text-field label="名称" :model-value="tpl.name" hide-details @update:model-value="v=>updateTpl(tpl.id,'name',v)"/></v-col>
              <v-col cols="12" sm="3"><v-text-field label="标题模板" :model-value="tpl.title" hide-details @update:model-value="v=>updateTpl(tpl.id,'title',v)"/></v-col>
              <v-col cols="12" sm="4"><v-text-field label="内容模板" :model-value="tpl.content" hide-details @update:model-value="v=>updateTpl(tpl.id,'content',v)"/></v-col>
              <v-col cols="12" sm="2"><v-select label="类型" :model-value="tpl.type||'text'" :items="['text']" hide-details @update:model-value="v=>updateTpl(tpl.id,'type',v)"/></v-col>
            </v-row>
            <div class="text-caption text-medium-emphasis mt-2">可用变量：{song_name} {artist} {quality} {file_size} {error} {music_id} {playlist_name} {total_synced} {success_count} {total_count} {keyword}</div>
            <div class="mt-2"><v-btn size="small" color="error" variant="tonal" @click="removeTemplate(tpl.id)">删除</v-btn></div>
          </v-card-text>
        </v-card>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="addTemplate" class="mt-2">新增模板</v-btn>
      </v-window-item>
    </v-window>
  </div>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getPushConfig, savePushConfig, sendPush, getEventsCatalog } from '@/api/index.js'
const activeTab=ref('push')
const pushConfig=reactive({pushes:[],templates:[]})
const eventCatalog=ref([])
const savingAll=ref(false)
const categoryColors={'服务生命周期':'#6b7280','API 操作':'#0891b2','下载事件':'#dc2626','同步事件':'#7c3aed','任务管理':'#ea580c','配置变更':'#059669','错误事件':'#b91c1c'}
let _idCounter=Date.now()
function genId(){return 'p'+(_idCounter++)+'_'+Math.random().toString(36).substr(2,6)}
function getCategoryColor(c){return categoryColors[c]||'#888'}
function getEventName(type){for(const cat of eventCatalog.value)for(const evt of cat.events)if(evt.type===type)return evt.name;return type}
const tplSelectItems=computed(()=>(pushConfig.templates||[]).map(t=>({title:t.name||t.id,value:t.id})))
async function loadConfig(){try{const[pushRes,eventRes]=await Promise.all([getPushConfig(),getEventsCatalog()]);if(pushRes?.status===200&&pushRes.data){const d=pushRes.data;pushConfig.pushes=(d.pushes||[]).map(p=>({...p,_collapsed:false,events:p.events||[],event_template:p.event_template?{...p.event_template,__tplId:''}:{}}));pushConfig.templates=d.templates||[]}if(eventRes?.status===200&&eventRes.data)eventCatalog.value=eventRes.data}catch(e){window.__snackbar?.('加载配置失败','error')}}
function addPush(){pushConfig.pushes.push({id:genId(),name:'新推送',title:'',content:'',type:'text',enabled:true,_collapsed:false,events:[],event_template:{},urls:[]})}
function removePush(id){if(!confirm('确定删除？'))return;pushConfig.pushes=pushConfig.pushes.filter(p=>p.id!==id)}
function updatePush(id,field,value){const p=pushConfig.pushes.find(x=>x.id===id);if(p)p[field]=value}
function addUrl(pushId){const p=pushConfig.pushes.find(x=>x.id===pushId);if(p){if(!p.urls)p.urls=[];p.urls.push({id:genId(),url:'',enabled:true})}}
function removeUrl(pushId,urlId){const p=pushConfig.pushes.find(x=>x.id===pushId);if(p)p.urls=(p.urls||[]).filter(u=>u.id!==urlId)}
function updateUrl(pushId,urlId,field,value){const p=pushConfig.pushes.find(x=>x.id===pushId);if(p){const u=(p.urls||[]).find(x=>x.id===urlId);if(u)u[field]=value}}
function toggleEvent(pushId,eventType){const p=pushConfig.pushes.find(x=>x.id===pushId);if(!p)return;if(!p.events)p.events=[];const idx=p.events.indexOf(eventType);if(idx>=0)p.events.splice(idx,1);else p.events.push(eventType)}
function selectTemplate(pushId,tplId){const p=pushConfig.pushes.find(x=>x.id===pushId);if(!p)return;if(!tplId)p.event_template={};else{const t=(pushConfig.templates||[]).find(x=>x.id===tplId);if(t)p.event_template={title:t.title,content:t.content,type:t.type,__tplId:tplId}}}
async function testPush(pushId,urlId){const p=pushConfig.pushes.find(x=>x.id===pushId);const u=(p?.urls||[]).find(x=>x.id===urlId);if(!u?.url)return window.__snackbar?.('请先填写推送地址','warning');try{const tpl=p.event_template||{};const r=await sendPush({url:u.url,title:tpl.title||p.title||'测试',content:tpl.content||p.content||'测试消息',type:tpl.type||p.type||'text'});window.__snackbar?.(r?.message||'推送成功',r?.success?'success':'error')}catch(e){window.__snackbar?.(e.message||'推送失败','error')}}
async function saveAllConfig(){savingAll.value=true;try{const toSave={pushes:pushConfig.pushes.map(p=>{const{_collapsed,...rest}=p;return rest}),templates:pushConfig.templates};await savePushConfig(toSave);window.__snackbar?.('配置已保存','success')}catch(e){window.__snackbar?.('保存失败','error')}finally{savingAll.value=false}}
function addTemplate(){if(!pushConfig.templates)pushConfig.templates=[];pushConfig.templates.push({id:genId(),name:'新模板',title:'',content:'',type:'text'})}
function removeTemplate(tplId){if(!confirm('确定删除？'))return;pushConfig.templates=(pushConfig.templates||[]).filter(t=>t.id!==tplId)}
function updateTpl(tplId,field,value){const t=(pushConfig.templates||[]).find(x=>x.id===tplId);if(t)t[field]=value}
onMounted(()=>loadConfig())
</script>
<style scoped>.cursor-pointer{cursor:pointer}.event-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}</style>
