<template>
  <div>
    <div class="d-flex align-center mb-5"><v-icon size="32" color="primary" class="mr-3">mdi-bell-ring-outline</v-icon><h1 class="text-h4 font-weight-bold">消息推送</h1></div>
    <v-tabs v-model="activeTab" class="mb-6"><v-tab value="push">推送规则</v-tab><v-tab value="tpl">消息模板</v-tab></v-tabs>
    <v-window v-model="activeTab">
      <v-window-item value="push">
        <!-- 顶部工具条 -->
        <div class="d-flex align-center ga-2 mb-4 flex-wrap">
          <span class="text-body-2 text-medium-emphasis">共 {{ (pushConfig.pushes||[]).length }} 条推送</span>
          <v-chip v-if="dirty" size="small" color="warning" variant="tonal" prepend-icon="mdi-circle-medium">未保存</v-chip>
          <v-spacer/>
          <v-btn v-if="(pushConfig.pushes||[]).length" variant="text" :prepend-icon="allCollapsed?'mdi-unfold-more-horizontal':'mdi-unfold-less-horizontal'" @click="toggleCollapseAll">{{ allCollapsed?'全部展开':'全部折叠' }}</v-btn>
          <v-btn color="primary" prepend-icon="mdi-plus" @click="addPush">新增推送</v-btn>
          <v-btn color="success" prepend-icon="mdi-content-save" :loading="savingAll" @click="saveAllConfig">保存</v-btn>
        </div>

        <div v-if="!pushConfig.pushes||!pushConfig.pushes.length" class="text-center text-medium-emphasis py-12">
          <v-icon size="56" class="mb-3">mdi-bell-ring-outline</v-icon>
          <p class="mb-4">暂无推送配置</p>
          <v-btn color="primary" variant="tonal" prepend-icon="mdi-plus" @click="addPush">新增推送</v-btn>
        </div>

        <v-card v-for="push in (pushConfig.pushes||[])" :key="push.id" class="mb-3" :class="{'push-disabled':push.enabled===false}">
          <!-- 折叠态摘要行 -->
          <div
            class="d-flex align-center pa-4 push-header"
            role="button"
            tabindex="0"
            :aria-expanded="!push._collapsed"
            :aria-label="(push._collapsed?'展开':'收起')+'推送：'+(push.name||'未命名')"
            @click="push._collapsed=!push._collapsed"
            @keydown.enter.prevent="push._collapsed=!push._collapsed"
            @keydown.space.prevent="push._collapsed=!push._collapsed"
          >
            <v-icon :color="push.enabled!==false?'success':'medium-emphasis'" class="mr-3 flex-shrink-0">{{ push.enabled!==false?'mdi-bell-ring':'mdi-bell-off-outline' }}</v-icon>
            <div class="flex-1-1" style="min-width:0;">
              <div class="d-flex align-center ga-2">
                <span class="text-subtitle-1 font-weight-bold text-truncate">{{ push.name||'未命名' }}</span>
                <v-chip size="small" variant="tonal" :color="push.enabled!==false?'success':'secondary'">{{ push.enabled!==false?'启用':'停用' }}</v-chip>
              </div>
              <div class="d-flex align-center ga-1 mt-1 flex-wrap">
                <template v-if="push.events&&push.events.length">
                  <v-chip v-for="evt in push.events" :key="evt" size="small" variant="tonal" color="primary">{{ getEventName(evt) }}</v-chip>
                </template>
                <span v-else class="text-caption text-error font-weight-bold">未绑定事件</span>
                <span class="text-caption text-medium-emphasis ml-1">· {{ (push.urls||[]).length }} 个地址</span>
              </div>
            </div>
            <v-switch
              :model-value="push.enabled!==false"
              color="success"
              hide-details
              density="compact"
              class="mr-2 flex-shrink-0"
              :aria-label="'启用推送：'+(push.name||'未命名')"
              @click.stop
              @update:model-value="v=>toggleEnabled(push.id,v)"
            />
            <v-icon class="text-medium-emphasis flex-shrink-0" :aria-label="push._collapsed?'展开':'收起'">{{ push._collapsed?'mdi-chevron-down':'mdi-chevron-up' }}</v-icon>
          </div>

          <v-expand-transition>
            <div v-if="!push._collapsed">
              <v-divider/>
              <v-card-text class="pt-4">
                <v-row dense class="mb-2">
                  <v-col cols="12" sm="6"><v-text-field label="推送名称" :model-value="push.name" hide-details @update:model-value="v=>updatePush(push.id,'name',v)"/></v-col>
                  <v-col cols="12" sm="6"><v-select label="消息模板" :items="tplSelectItems" :model-value="push.event_template?.__tplId||''" hide-details clearable placeholder="不使用模板（用固定内容）" @update:model-value="v=>selectTemplate(push.id,v)"/></v-col>
                </v-row>
                <v-row v-if="!push.event_template?.__tplId" dense class="mb-3">
                  <v-col cols="12" sm="6"><v-text-field label="标题" :model-value="push.title" hide-details @update:model-value="v=>updatePush(push.id,'title',v)"/></v-col>
                  <v-col cols="12" sm="6"><v-text-field label="固定内容" :model-value="push.content" hide-details @update:model-value="v=>updatePush(push.id,'content',v)"/></v-col>
                </v-row>

                <div class="mb-4">
                  <div class="text-caption font-weight-bold mb-2">触发事件</div>
                  <div class="d-flex flex-wrap ga-2 align-center">
                    <v-chip v-for="evt in (push.events||[])" :key="evt" variant="tonal" color="primary" closable :aria-label="'移除事件 '+getEventName(evt)" @click:close="toggleEvent(push.id,evt)">{{ getEventName(evt) }}</v-chip>
                    <v-menu location="bottom start" :close-on-content-click="false">
                      <template #activator="{props}"><v-btn variant="tonal" prepend-icon="mdi-plus" v-bind="props">添加事件</v-btn></template>
                      <v-list density="comfortable" style="max-height:320px;overflow-y:auto;">
                        <template v-for="cat in eventCatalog" :key="cat.category">
                          <v-list-subheader class="text-caption font-weight-bold text-medium-emphasis">{{ cat.category }}</v-list-subheader>
                          <v-list-item v-for="evt in cat.events" :key="evt.type" :title="evt.name" :subtitle="evt.type" @click="toggleEvent(push.id,evt.type)">
                            <template #prepend><div class="event-dot mr-2" :style="{background:getCategoryColor(cat.category)}"/></template>
                            <template #append><v-icon v-if="(push.events||[]).includes(evt.type)" size="18" color="success">mdi-check</v-icon></template>
                          </v-list-item>
                        </template>
                      </v-list>
                    </v-menu>
                  </div>
                </div>

                <div class="mb-3">
                  <div class="d-flex align-center mb-2"><span class="text-caption font-weight-bold">推送地址</span><v-spacer/><v-btn variant="tonal" prepend-icon="mdi-plus" @click="addUrl(push.id)">添加地址</v-btn></div>
                  <div v-if="!(push.urls&&push.urls.length)" class="text-caption text-medium-emphasis py-2">尚未添加推送地址</div>
                  <div v-for="url in (push.urls||[])" :key="url.id" class="d-flex align-center ga-2 pa-2 mb-2 rounded bg-surface-variant url-row flex-wrap">
                    <v-text-field
                      :model-value="url.url"
                      :error="!!url.url && !isValidUrl(url.url)"
                      :error-messages="(!!url.url && !isValidUrl(url.url)) ? '请输入以 http:// 或 https:// 开头的有效地址' : ''"
                      placeholder="Webhook URL"
                      class="url-input"
                      style="flex:1 1 240px;min-width:200px;font-family:monospace;"
                      @update:model-value="v=>updateUrl(push.id,url.id,'url',v)"
                    />
                    <div class="d-flex align-center ga-1 flex-shrink-0">
                      <v-switch :model-value="url.enabled!==false" color="success" hide-details density="compact" :aria-label="'启用此地址'" @update:model-value="v=>toggleUrlEnabled(push.id,url.id,v)"/>
                      <v-btn variant="tonal" color="primary" :loading="isTesting(push.id,url.id)" @click="testPush(push.id,url.id)">测试</v-btn>
                      <v-btn icon="mdi-delete" variant="text" color="error" aria-label="删除此地址" @click="removeUrl(push.id,url.id)"/>
                    </div>
                  </div>
                </div>

                <v-alert variant="tonal" density="compact" class="text-caption mb-3" icon="mdi-information-outline">
                  事件变量：{song_name} {artist} {quality} {file_size} {error} {music_id} {playlist_name} {total_synced} {success_count} {total_count} {keyword}｜内置：{now} {当前时间}
                </v-alert>

                <div class="d-flex"><v-spacer/><v-btn color="error" variant="text" prepend-icon="mdi-delete" @click="removePush(push.id)">删除此推送</v-btn></div>
              </v-card-text>
            </div>
          </v-expand-transition>
        </v-card>
      </v-window-item>
      <v-window-item value="tpl">
        <div class="d-flex align-center ga-2 mb-4 flex-wrap">
          <span class="text-body-2 text-medium-emphasis">共 {{ (pushConfig.templates||[]).length }} 个模板</span>
          <v-chip v-if="dirty" size="small" color="warning" variant="tonal" prepend-icon="mdi-circle-medium">未保存</v-chip>
          <v-spacer/>
          <v-btn color="primary" prepend-icon="mdi-plus" @click="addTemplate">新增模板</v-btn>
          <v-btn color="success" prepend-icon="mdi-content-save" :loading="savingAll" @click="saveAllConfig">保存</v-btn>
        </div>

        <div v-if="!pushConfig.templates||!pushConfig.templates.length" class="text-center text-medium-emphasis py-12">
          <v-icon size="56" class="mb-3">mdi-file-document-outline</v-icon>
          <p class="mb-4">暂无消息模板</p>
          <v-btn color="primary" variant="tonal" prepend-icon="mdi-plus" @click="addTemplate">新增模板</v-btn>
        </div>

        <v-card v-for="tpl in (pushConfig.templates||[])" :key="tpl.id" class="mb-3">
          <v-card-text class="pt-4">
            <div class="d-flex align-center mb-3">
              <v-icon color="primary" class="mr-2">mdi-file-document-outline</v-icon>
              <span class="text-subtitle-1 font-weight-bold text-truncate">{{ tpl.name||'未命名模板' }}</span>
              <v-spacer/>
              <v-btn icon="mdi-delete" variant="text" color="error" aria-label="删除此模板" @click="removeTemplate(tpl.id)"/>
            </div>

            <v-row dense class="mb-1">
              <v-col cols="12" sm="8"><v-text-field label="模板名称" :model-value="tpl.name" hide-details @update:model-value="v=>updateTpl(tpl.id,'name',v)"/></v-col>
              <v-col cols="12" sm="4"><v-select label="类型" :model-value="tpl.type||'text'" :items="['text']" hide-details @update:model-value="v=>updateTpl(tpl.id,'type',v)"/></v-col>
            </v-row>
            <v-text-field label="标题模板" class="mb-1" :model-value="tpl.title" hide-details placeholder="如：下载完成 - {song_name}" @update:model-value="v=>updateTpl(tpl.id,'title',v)"/>
            <v-textarea label="内容模板" :model-value="tpl.content" rows="3" auto-grow hide-details placeholder="支持多行，使用 {变量名} 占位" @update:model-value="v=>updateTpl(tpl.id,'content',v)"/>

            <!-- 实时预览（使用示例值替换变量） -->
            <div class="preview-box mt-3 pa-3 rounded">
              <div class="d-flex align-center mb-1">
                <span class="text-caption text-medium-emphasis">预览（示例值）</span>
                <v-spacer/>
                <v-btn size="small" variant="text" prepend-icon="mdi-refresh" @click="regenSample">换一批示例</v-btn>
              </div>
              <div class="text-body-2 font-weight-bold">{{ renderTpl(tpl.title)||'（无标题）' }}</div>
              <div class="text-body-2 mt-1" style="white-space:pre-wrap;">{{ renderTpl(tpl.content)||'（无内容）' }}</div>
            </div>

            <!-- 变量快捷插入 -->
            <div class="mt-3">
              <div class="text-caption font-weight-bold mb-1">可用变量（点击复制）</div>
              <div class="d-flex flex-wrap ga-2">
                <v-chip v-for="v in templateVars" :key="v" size="small" variant="tonal" color="primary" link :aria-label="'复制变量 '+v" @click="copyVar(v)">{{ v }}</v-chip>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
  </div>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { getPushConfig, savePushConfig, sendPush, getEventsCatalog } from '@/api/index.js'
const activeTab=ref('push')
const pushConfig=reactive({pushes:[],templates:[]})
const eventCatalog=ref([])
const savingAll=ref(false)
const dirty=ref(false)
const testing=reactive({})
function markDirty(){dirty.value=true}
function isValidUrl(u){return /^https?:\/\/.+/i.test((u||'').trim())}
function isTesting(pushId,urlId){return !!testing[pushId+':'+urlId]}
const categoryColors={'服务生命周期':'#6b7280','API 操作':'#0891b2','下载事件':'#dc2626','同步事件':'#7c3aed','任务管理':'#ea580c','配置变更':'#059669','错误事件':'#b91c1c'}
let _idCounter=Date.now()
function genId(){return 'p'+(_idCounter++)+'_'+Math.random().toString(36).substr(2,6)}
function getCategoryColor(c){return categoryColors[c]||'#888'}
function getEventName(type){for(const cat of eventCatalog.value)for(const evt of cat.events)if(evt.type===type)return evt.name;return type}
const tplSelectItems=computed(()=>(pushConfig.templates||[]).map(t=>({title:t.name||t.id,value:t.id})))
const templateVars=['{song_name}','{artist}','{quality}','{file_size}','{error}','{music_id}','{playlist_name}','{total_synced}','{success_count}','{total_count}','{keyword}','{now}','{当前时间}']
async function copyVar(v){try{await navigator.clipboard.writeText(v);window.__snackbar?.(`已复制 ${v}`,'success')}catch(e){window.__snackbar?.('复制失败','error')}}

// 预览示例值（合理随机，非乱码符号）
const _pick=arr=>arr[Math.floor(Math.random()*arr.length)]
function genSampleVars(){
  const songs=['晴天','稻香','七里香','夜曲','告白气球','演员','光年之外','起风了','成都','平凡之路']
  const artists=['周杰伦','林俊杰','邓紫棋','李荣浩','陈奕迅','毛不易','薛之谦','五月天']
  const qualities=['标准','极高','无损','Hi-Res','母带']
  const playlists=['华语经典','深夜电台','通勤必备','私人雷达','怀旧金曲']
  const errors=['网络连接超时','版权限制无法下载','当前音质不支持','Cookie 已失效，请重新登录']
  const artist=_pick(artists)
  const total=10+Math.floor(Math.random()*40)
  const success=Math.max(0,total-Math.floor(Math.random()*4))
  return {
    song_name:_pick(songs),
    artist,
    quality:_pick(qualities),
    file_size:(8+Math.random()*42).toFixed(1)+' MB',
    error:_pick(errors),
    music_id:String(100000+Math.floor(Math.random()*899900000)),
    playlist_name:_pick(playlists),
    total_synced:String(success),
    success_count:String(success),
    total_count:String(total),
    keyword:artist,
  }
}
const sampleVars=ref(genSampleVars())
function regenSample(){sampleVars.value=genSampleVars();window.__snackbar?.('已生成新的示例值','info')}
function renderTpl(text){
  if(!text)return ''
  const now=new Date().toLocaleString('zh-CN',{hour12:false})
  const map={...sampleVars.value,now,'当前时间':now}
  return text.replace(/\{([\w\u4e00-\u9fff]+)\}/g,(m,k)=>k in map?map[k]:m)
}
const allCollapsed=computed(()=>(pushConfig.pushes||[]).every(p=>p._collapsed))
function toggleCollapseAll(){const target=!allCollapsed.value;(pushConfig.pushes||[]).forEach(p=>p._collapsed=target)}
async function loadConfig(){try{const[pushRes,eventRes]=await Promise.all([getPushConfig(),getEventsCatalog()]);if(pushRes?.status===200&&pushRes.data){const d=pushRes.data;pushConfig.pushes=(d.pushes||[]).map(p=>({...p,_collapsed:true,events:p.events||[],event_template:p.event_template?{...p.event_template,__tplId:''}:{}}));pushConfig.templates=d.templates||[]}if(eventRes?.status===200&&eventRes.data)eventCatalog.value=eventRes.data}catch(e){window.__snackbar?.('加载配置失败','error')}}
function addPush(){(pushConfig.pushes||[]).forEach(p=>p._collapsed=true);pushConfig.pushes.push({id:genId(),name:'新推送',title:'',content:'',type:'text',enabled:true,_collapsed:false,events:[],event_template:{},urls:[]});markDirty()}
async function removePush(id){if(!(await window.__confirm({title:'删除推送',text:'确定删除此推送？',confirmText:'删除',confirmColor:'error'})))return;pushConfig.pushes=pushConfig.pushes.filter(p=>p.id!==id);markDirty()}
function updatePush(id,field,value){const p=pushConfig.pushes.find(x=>x.id===id);if(p){p[field]=value;markDirty()}}
// 启用开关：即时持久化（开关语义=立即生效）
async function toggleEnabled(id,v){const p=pushConfig.pushes.find(x=>x.id===id);if(!p)return;p.enabled=v;p._collapsed=true;await saveAllConfig(true);window.__snackbar?.(v?'已启用并保存':'已停用并保存','success')}
function addUrl(pushId){const p=pushConfig.pushes.find(x=>x.id===pushId);if(p){if(!p.urls)p.urls=[];p.urls.push({id:genId(),url:'',enabled:true});markDirty()}}
function removeUrl(pushId,urlId){const p=pushConfig.pushes.find(x=>x.id===pushId);if(p){p.urls=(p.urls||[]).filter(u=>u.id!==urlId);markDirty()}}
function updateUrl(pushId,urlId,field,value){const p=pushConfig.pushes.find(x=>x.id===pushId);if(p){const u=(p.urls||[]).find(x=>x.id===urlId);if(u){u[field]=value;markDirty()}}}
async function toggleUrlEnabled(pushId,urlId,v){const p=pushConfig.pushes.find(x=>x.id===pushId);const u=(p?.urls||[]).find(x=>x.id===urlId);if(!u)return;u.enabled=v;await saveAllConfig(true)}
function toggleEvent(pushId,eventType){const p=pushConfig.pushes.find(x=>x.id===pushId);if(!p)return;if(!p.events)p.events=[];const idx=p.events.indexOf(eventType);if(idx>=0)p.events.splice(idx,1);else p.events.push(eventType);markDirty()}
function selectTemplate(pushId,tplId){const p=pushConfig.pushes.find(x=>x.id===pushId);if(!p)return;if(!tplId)p.event_template={};else{const t=(pushConfig.templates||[]).find(x=>x.id===tplId);if(t)p.event_template={title:t.title,content:t.content,type:t.type,__tplId:tplId}}markDirty()}
async function testPush(pushId,urlId){const p=pushConfig.pushes.find(x=>x.id===pushId);const u=(p?.urls||[]).find(x=>x.id===urlId);if(!u?.url)return window.__snackbar?.('请先填写推送地址','warning');if(!isValidUrl(u.url))return window.__snackbar?.('推送地址格式无效','warning');const key=pushId+':'+urlId;testing[key]=true;try{const tpl=p.event_template||{};const r=await sendPush({url:u.url,title:tpl.title||p.title||'测试',content:tpl.content||p.content||'测试消息',type:tpl.type||p.type||'text'});window.__snackbar?.(r?.message||'推送成功',r?.success?'success':'error')}catch(e){window.__snackbar?.(e.message||'推送失败','error')}finally{testing[key]=false}}
async function saveAllConfig(silent=false){savingAll.value=true;try{const toSave={pushes:pushConfig.pushes.map(p=>{const{_collapsed,...rest}=p;return rest}),templates:pushConfig.templates};await savePushConfig(toSave);dirty.value=false;if(!silent)window.__snackbar?.('配置已保存','success')}catch(e){window.__snackbar?.('保存失败','error')}finally{savingAll.value=false}}
function addTemplate(){if(!pushConfig.templates)pushConfig.templates=[];pushConfig.templates.push({id:genId(),name:'新模板',title:'',content:'',type:'text'});markDirty()}
async function removeTemplate(tplId){if(!(await window.__confirm({title:'删除模板',text:'确定删除此模板？',confirmText:'删除',confirmColor:'error'})))return;pushConfig.templates=(pushConfig.templates||[]).filter(t=>t.id!==tplId);markDirty()}
function updateTpl(tplId,field,value){const t=(pushConfig.templates||[]).find(x=>x.id===tplId);if(t){t[field]=value;markDirty()}}
onBeforeRouteLeave(async()=>{if(dirty.value&&!(await window.__confirm({title:'放弃未保存的修改？',text:'有未保存的修改，离开后修改将丢失。',confirmText:'离开',confirmColor:'error'})))return false;return true})
onMounted(()=>loadConfig())
</script>
<style scoped>
.cursor-pointer{cursor:pointer}
.event-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.push-header{cursor:pointer;transition:background-color .18s ease;border-radius:inherit}
.push-header:hover{background:rgba(120,120,128,.08)}
.push-disabled{opacity:.62}
.push-disabled .push-header:hover{opacity:1}
.preview-box{background:rgba(120,120,128,.1);border:1px dashed rgba(120,120,128,.3)}
/* URL 输入字号 ≥16px，避免移动端聚焦自动缩放 */
.url-input :deep(input){font-size:16px}
.push-header:focus-visible{outline:2px solid rgb(var(--v-theme-primary));outline-offset:-2px;border-radius:inherit}
@media (max-width:600px){
  .url-row .url-input{flex:1 1 100%}
}
</style>
