<template>
  <div>
    <div class="d-flex align-center mb-5"><v-icon size="32" color="primary" class="mr-3">mdi-bell-ring-outline</v-icon><h1 class="text-h4 font-weight-bold">消息推送</h1></div>
    <v-tabs v-model="activeTab" class="mb-6"><v-tab value="push">推送规则</v-tab><v-tab value="tpl">消息模板</v-tab><v-tab value="server">推送服务器</v-tab></v-tabs>
    <v-window v-model="activeTab">
      <!-- ==================== 推送规则 ==================== -->
      <v-window-item value="push">
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
          <div
            class="d-flex align-center pa-4 push-header" role="button" tabindex="0"
            :aria-expanded="!push._collapsed" :aria-label="(push._collapsed?'展开':'收起')+'推送：'+(push.name||'未命名')"
            @click="push._collapsed=!push._collapsed"
            @keydown.enter.prevent="push._collapsed=!push._collapsed"
            @keydown.space.prevent="push._collapsed=!push._collapsed"
          >
            <v-icon :color="push.enabled!==false?'success':'medium-emphasis'" class="mr-3 flex-shrink-0">{{ push.enabled!==false?'mdi-bell-ring':'mdi-bell-off-outline' }}</v-icon>
            <div class="flex-1-1" style="min-width:0;">
              <div class="d-flex align-center ga-2">
                <span class="text-subtitle-1 font-weight-bold text-truncate">{{ push.name||'未命名' }}</span>
                <v-chip size="small" variant="tonal" :color="push.enabled!==false?'success':'secondary'">{{ push.enabled!==false?'启用':'停用' }}</v-chip>
                <v-chip v-if="push.serverId" size="small" variant="tonal" color="info">{{ getServerName(push.serverId) }}</v-chip>
                <v-chip v-if="push.event_template?.__tplId" size="small" variant="tonal" color="accent">{{ getTplName(push.event_template.__tplId) }}</v-chip>
              </div>
              <div class="d-flex align-center ga-1 mt-1 flex-wrap">
                <template v-if="push.events&&push.events.length">
                  <v-chip v-for="evt in push.events" :key="evt" size="small" variant="tonal" color="primary">{{ getEventName(evt) }}</v-chip>
                </template>
                <span v-else class="text-caption text-error font-weight-bold">未绑定事件</span>
              </div>
            </div>
            <v-switch
              :model-value="push.enabled!==false" color="success" hide-details density="compact" class="mr-2 flex-shrink-0"
              :aria-label="'启用推送：'+(push.name||'未命名')"
              @click.stop @update:model-value="v=>toggleEnabled(push.id,v)"
            />
            <v-icon class="text-medium-emphasis flex-shrink-0" :aria-label="push._collapsed?'展开':'收起'">{{ push._collapsed?'mdi-chevron-down':'mdi-chevron-up' }}</v-icon>
          </div>

          <v-expand-transition>
            <div v-if="!push._collapsed">
              <v-divider/>
              <v-card-text class="pt-4">
                <v-row dense class="mb-2">
                  <v-col cols="12" sm="6"><v-text-field label="推送名称" :model-value="push.name" hide-details @update:model-value="v=>updatePush(push.id,'name',v)"/></v-col>
                  <v-col cols="12" sm="6">
                    <v-select label="消息模板" :items="tplSelectItems" :model-value="push.event_template?.__tplId||''" hide-details placeholder="请选择消息模板" @update:model-value="v=>selectTemplate(push.id,v)"/>
                  </v-col>
                </v-row>

                <v-row dense class="mb-3">
                  <v-col cols="12" sm="6">
                    <v-select label="推送服务器" :items="serverSelectItems" :model-value="push.serverId||''" hide-details placeholder="请选择推送服务器" @update:model-value="v=>updatePush(push.id,'serverId',v||undefined)"/>
                  </v-col>
                  <v-col v-if="push.serverId" cols="12" sm="6">
                    <v-alert variant="tonal" density="compact" class="text-caption mb-0" icon="mdi-server">
                      <template v-if="getServerInfo(push.serverId)">
                        <div class="font-weight-bold">{{ getServerInfo(push.serverId).name }}</div>
                        <div class="text-medium-emphasis">URL: {{ getServerInfo(push.serverId).url || '(空)' }}</div>
                        <div class="text-medium-emphasis">映射: {{ (getServerInfo(push.serverId).mapping||[]).map(m=>m.from+'→'+m.to).join(', ') || '(默认)' }}</div>
                      </template>
                    </v-alert>
                  </v-col>
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

                <div class="d-flex ga-2"><v-spacer/><v-btn variant="tonal" color="primary" :loading="isTesting(push.id)" @click="testPushServer(push.id)">测试推送</v-btn><v-btn color="error" variant="text" prepend-icon="mdi-delete" @click="removePush(push.id)">删除此推送</v-btn></div>
              </v-card-text>
            </div>
          </v-expand-transition>
        </v-card>
      </v-window-item>

      <!-- ==================== 消息模板 ==================== -->
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
            <v-text-field label="标题模板" class="mb-1" :model-value="tpl.title" hide-details placeholder="如：下载完成 - {song_name}" @focus="activeInput=$event.target" @update:model-value="v=>updateTpl(tpl.id,'title',v)"/>
            <v-textarea label="内容模板" :model-value="tpl.content" rows="3" auto-grow hide-details placeholder="支持多行，使用 {变量名} 占位" @focus="activeInput=$event.target" @update:model-value="v=>updateTpl(tpl.id,'content',v)"/>

            <div class="preview-box mt-3 pa-3 rounded">
              <div class="d-flex align-center mb-1">
                <span class="text-caption text-medium-emphasis">预览（示例值）</span>
                <v-spacer/>
                <v-btn size="small" variant="text" prepend-icon="mdi-refresh" @click="regenSample">换一批示例</v-btn>
              </div>
              <div class="text-body-2 font-weight-bold">{{ renderTpl(tpl.title)||'（无标题）' }}</div>
              <div class="text-body-2 mt-1" style="white-space:pre-wrap;">{{ renderTpl(tpl.content)||'（无内容）' }}</div>
            </div>

            <div class="mt-3">
              <div class="text-caption font-weight-bold mb-1">可用变量（点击插入到光标位置）</div>
              <div class="d-flex flex-wrap ga-2">
                <v-chip v-for="v in templateVars" :key="v" size="small" variant="tonal" color="primary" link :aria-label="'插入变量 '+v" @click.prevent="insertVar(v)">{{ v }}</v-chip>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- ==================== 推送服务器 ==================== -->
      <v-window-item value="server">
        <div class="d-flex align-center ga-2 mb-4 flex-wrap">
          <span class="text-body-2 text-medium-emphasis">共 {{ servers.length }} 个服务器</span>
          <v-spacer/>
          <v-btn v-if="servers.length" variant="text" :prepend-icon="allSrvCollapsed?'mdi-unfold-more-horizontal':'mdi-unfold-less-horizontal'" @click="toggleSrvCollapseAll">{{ allSrvCollapsed?'全部展开':'全部折叠' }}</v-btn>
          <v-btn color="primary" prepend-icon="mdi-plus" @click="addServer">新增服务器</v-btn>
          <v-btn color="success" prepend-icon="mdi-content-save" :loading="savingSrvs" @click="saveServers">保存</v-btn>
        </div>

        <div v-if="!servers.length" class="text-center text-medium-emphasis py-12">
          <v-icon size="56" class="mb-3">mdi-server</v-icon>
          <p class="mb-4">暂无推送服务器</p>
          <v-btn color="primary" variant="tonal" prepend-icon="mdi-plus" @click="addServer">新增服务器</v-btn>
        </div>

        <v-card v-for="srv in servers" :key="srv.id" class="mb-3">
          <div
            class="d-flex align-center pa-4 push-header" role="button" tabindex="0"
            :aria-expanded="!srv._collapsed" :aria-label="(srv._collapsed?'展开':'收起')+'服务器：'+(srv.name||'未命名')"
            @click="srv._collapsed=!srv._collapsed"
            @keydown.enter.prevent="srv._collapsed=!srv._collapsed"
            @keydown.space.prevent="srv._collapsed=!srv._collapsed"
          >
            <v-icon color="primary" class="mr-3 flex-shrink-0">mdi-server</v-icon>
            <div class="flex-1-1" style="min-width:0;">
              <div class="d-flex align-center ga-2">
                <span class="text-subtitle-1 font-weight-bold text-truncate">{{ srv.name||'未命名' }}</span>
                <v-chip size="small" variant="tonal" :color="getPresetColor(srv.type)">{{ getPresetName(srv.type) }}</v-chip>
              </div>
              <div class="text-caption text-medium-emphasis text-truncate mt-1">{{ srv.baseUrl||'(未配置URL)' }}</div>
            </div>
            <v-icon class="text-medium-emphasis flex-shrink-0" :aria-label="srv._collapsed?'展开':'收起'">{{ srv._collapsed?'mdi-chevron-down':'mdi-chevron-up' }}</v-icon>
          </div>

          <v-expand-transition>
            <div v-if="!srv._collapsed">
              <v-divider/>
              <v-card-text class="pt-4">
                <v-row dense class="mb-2">
                  <v-col cols="12" sm="6"><v-text-field label="服务器名称" :model-value="srv.name" hide-details @update:model-value="v=>{srv.name=v;markServerDirty()}"/></v-col>
                  <v-col cols="12" sm="6">
                    <v-select label="预设类型" :items="presetTypeItems" :model-value="srv.type||'custom'" hide-details @update:model-value="v=>applyServerPreset(srv.id,v)"/>
                  </v-col>
                </v-row>
                <v-text-field label="基础 URL" class="mb-3" :model-value="srv.baseUrl" hide-details placeholder="如 https://api.day.app/{token}" @update:model-value="v=>{srv.baseUrl=v;markServerDirty()}"/>

                <div class="mb-3">
                  <div class="d-flex align-center mb-2"><span class="text-caption font-weight-bold">固定参数</span><v-spacer/><v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="addFixedParam(srv.id)">添加</v-btn></div>
                  <div v-if="!srv.fixedParams||!Object.keys(srv.fixedParams).length" class="text-caption text-medium-emphasis mb-2">无固定参数</div>
                  <div v-for="(val,key,idx) in (srv.fixedParams||{})" :key="idx" class="d-flex align-center ga-2 mb-2">
                    <v-text-field :model-value="key" label="键" hide-details density="compact" style="width:140px" @update:model-value="v=>renameFixedParam(srv,key,v)"/>
                    <v-text-field :model-value="val" label="值" hide-details density="compact" style="flex:1" @update:model-value="v=>{srv.fixedParams[key]=v;markServerDirty()}"/>
                    <v-btn icon="mdi-delete" variant="text" color="error" size="small" @click="removeFixedParam(srv,key)"/>
                  </div>
                </div>

                <div class="mb-3">
                  <div class="d-flex align-center mb-2"><span class="text-caption font-weight-bold">参数映射规则</span><v-spacer/><v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="addMapping(srv)">添加</v-btn></div>
                  <div v-if="!srv.paramMapping||!srv.paramMapping.length" class="text-caption text-medium-emphasis mb-2">无映射规则（使用默认字段名）</div>
                  <div v-for="(m,idx) in (srv.paramMapping||[])" :key="idx" class="d-flex align-center ga-2 mb-2">
                    <v-select :model-value="m.from" :items="getAvailableFromFields(srv,idx)" hide-details density="compact" style="width:100px" @update:model-value="v=>{m.from=v;markServerDirty()}"/>
                    <v-icon size="20" class="text-medium-emphasis">mdi-arrow-right</v-icon>
                    <v-text-field :model-value="m.to" label="目标字段" hide-details density="compact" style="flex:1" @update:model-value="v=>{m.to=v;markServerDirty()}"/>
                    <v-btn icon="mdi-delete" variant="text" color="error" size="small" @click="removeMapping(srv,idx)"/>
                  </div>
                </div>

                <div class="preview-box pa-3 rounded mb-2">
                  <div class="text-caption font-weight-bold mb-1">请求预览</div>
                  <div class="text-caption text-medium-emphasis mb-1">POST {{ previewUrl(srv) }}</div>
                  <div class="text-caption" style="white-space:pre-wrap;font-family:monospace;">{{ JSON.stringify(previewPayload(srv),null,2) }}</div>
                </div>

                <div class="d-flex"><v-spacer/><v-btn color="error" variant="text" prepend-icon="mdi-delete" @click="removeServer(srv.id)">删除此服务器</v-btn></div>
              </v-card-text>
            </div>
          </v-expand-transition>
        </v-card>
      </v-window-item>
    </v-window>
  </div>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { getPushConfig, savePushConfig, sendPush, getEventsCatalog, getPushServers, savePushServers, getServerPresets } from '@/api/index.js'

const activeTab=ref('push')
const pushConfig=reactive({pushes:[],templates:[]})
const servers=ref([])
const serverPresets=ref({})
const eventCatalog=ref([])
const savingAll=ref(false)
const savingSrvs=ref(false)
const dirty=ref(false)
const activeInput=ref(null)
const testing=reactive({})
function markDirty(){dirty.value=true}
function isTesting(pushId){return !!testing[pushId]}

const categoryColors={'服务生命周期':'#6b7280','API 操作':'#0891b2','下载事件':'#dc2626','同步事件':'#7c3aed','任务管理':'#ea580c','配置变更':'#059669','错误事件':'#b91c1c'}
const presetColors={magicpush:'primary',bark:'success',serverchan:'warning',pushplus:'info',custom:'secondary'}
let _idCounter=Date.now()
function genId(){return 'p'+(_idCounter++)+'_'+Math.random().toString(36).substr(2,6)}
function srvGenId(){return 'srv_'+(_idCounter++)}
function getCategoryColor(c){return categoryColors[c]||'#888'}
function getEventName(type){for(const cat of eventCatalog.value)for(const evt of cat.events)if(evt.type===type)return evt.name;return type}
const templateVars=['{song_name}','{artist}','{quality}','{file_size}','{error}','{music_id}','{playlist_name}','{total_synced}','{success_count}','{total_count}','{keyword}','{now}','{当前时间}']
const fromFields=['title','content','type']

const tplSelectItems=computed(()=>(pushConfig.templates||[]).map(t=>({title:t.name||t.id,value:t.id})))
const serverSelectItems=computed(()=>servers.value.map(s=>({title:s.name||s.id,value:s.id})))
const presetTypeItems=computed(()=>Object.keys(serverPresets.value).map(k=>({title:serverPresets.value[k]?.name||k,value:k})))

function getServerName(id){const s=servers.value.find(x=>x.id===id);return s?.name||id}
function getTplName(id){const t=(pushConfig.templates||[]).find(x=>x.id===id);return t?.name||id}
function getServerInfo(id){const s=servers.value.find(x=>x.id===id);if(!s)return null;const url=resolveServerUrl(s);const mapping=s.paramMapping||[];return{name:s.name,url,mapping}}
function getPresetName(type){return serverPresets.value[type]?.name||type}
function getPresetColor(type){return presetColors[type]||'secondary'}

function insertVar(v){
  if(!activeInput.value){copyVarFallback(v);return}
  const el=activeInput.value
  const start=el.selectionStart??el.value.length
  const end=el.selectionEnd??start
  const before=el.value.substring(0,start)
  const after=el.value.substring(end)
  el.value=before+v+after
  const pos=start+v.length
  el.setSelectionRange(pos,pos)
  el.dispatchEvent(new Event('input',{bubbles:true}))
  el.focus()
}
async function copyVarFallback(v){try{await navigator.clipboard.writeText(v);window.__snackbar?.(`已复制 ${v}`,'success')}catch(e){window.__snackbar?.('复制失败','error')}}

const _pick=arr=>arr[Math.floor(Math.random()*arr.length)]
function genSampleVars(){
  const songs=['晴天','稻香','七里香','夜曲','告白气球','演员','光年之外','起风了','成都','平凡之路']
  const artists=['周杰伦','林俊杰','邓紫棋','李荣浩','陈奕迅','毛不易','薛之谦','五月天']
  const qualities=['标准','极高','无损','Hi-Res','母带']
  const playlists=['华语经典','深夜电台','通勤必备','私人雷达','怀旧金曲']
  const errors=['网络连接超时','版权限制无法下载','当前音质不支持','Cookie 已失效，请重新登录']
  const artist=_pick(artists);const total=10+Math.floor(Math.random()*40);const success=Math.max(0,total-Math.floor(Math.random()*4))
  return {song_name:_pick(songs),artist,quality:_pick(qualities),file_size:(8+Math.random()*42).toFixed(1)+' MB',error:_pick(errors),music_id:String(100000+Math.floor(Math.random()*899900000)),playlist_name:_pick(playlists),total_synced:String(success),success_count:String(success),total_count:String(total),keyword:artist}
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
async function loadConfig(){try{const[pushRes,eventRes,svrRes,preRes]=await Promise.all([getPushConfig(),getEventsCatalog(),getPushServers(),getServerPresets()]);if(pushRes?.status===200&&pushRes.data){const d=pushRes.data;pushConfig.pushes=(d.pushes||[]).map(p=>({...p,_collapsed:true,events:p.events||[],event_template:p.event_template?{...p.event_template,__tplId:''}:{}}));pushConfig.templates=d.templates||[]}if(eventRes?.status===200&&eventRes.data)eventCatalog.value=eventRes.data;if(svrRes?.status===200&&svrRes.data)servers.value=(svrRes.data||[]).map(s=>({...s,_collapsed:true}));if(preRes?.status===200&&preRes.data)serverPresets.value=preRes.data}catch(e){window.__snackbar?.('加载配置失败','error')}}
function addPush(){(pushConfig.pushes||[]).forEach(p=>p._collapsed=true);pushConfig.pushes.push({id:genId(),name:'新推送',enabled:true,_collapsed:false,events:[],event_template:{}});markDirty()}
async function removePush(id){if(!(await window.__confirm({title:'删除推送',text:'确定删除此推送？',confirmText:'删除',confirmColor:'error'})))return;pushConfig.pushes=pushConfig.pushes.filter(p=>p.id!==id);markDirty()}
function updatePush(id,field,value){const p=pushConfig.pushes.find(x=>x.id===id);if(p){p[field]=value;markDirty()}}
async function toggleEnabled(id,v){const p=pushConfig.pushes.find(x=>x.id===id);if(!p)return;p.enabled=v;p._collapsed=true;await saveAllConfig(true);window.__snackbar?.(v?'已启用并保存':'已停用并保存','success')}
function toggleEvent(pushId,eventType){const p=pushConfig.pushes.find(x=>x.id===pushId);if(!p)return;if(!p.events)p.events=[];const idx=p.events.indexOf(eventType);if(idx>=0)p.events.splice(idx,1);else p.events.push(eventType);markDirty()}
function selectTemplate(pushId,tplId){const p=pushConfig.pushes.find(x=>x.id===pushId);if(!p)return;if(!tplId){p.event_template={};markDirty();return}const t=(pushConfig.templates||[]).find(x=>x.id===tplId);if(t)p.event_template={title:t.title,content:t.content,type:t.type,__tplId:tplId};markDirty()}
async function testPushServer(pushId){const p=pushConfig.pushes.find(x=>x.id===pushId);if(!p)return;if(!p.serverId)return window.__snackbar?.('请先选择推送服务器','warning');testing[pushId]=true;try{const tpl=p.event_template||{};const title=renderTpl(tpl.title)||'测试标题';const content=renderTpl(tpl.content)||'测试内容';const r=await sendPush({serverId:p.serverId,title,content,type:tpl.type||'text'});window.__snackbar?.(r?.message||'推送成功',r?.success?'success':'error')}catch(e){window.__snackbar?.(e.message||'推送失败','error')}finally{testing[pushId]=false}}
async function saveAllConfig(silent=false){savingAll.value=true;try{const toSave={pushes:pushConfig.pushes.map(p=>{const{_collapsed,...rest}=p;return rest}),templates:pushConfig.templates};await savePushConfig(toSave);dirty.value=false;if(!silent)window.__snackbar?.('配置已保存','success')}catch(e){window.__snackbar?.('保存失败','error')}finally{savingAll.value=false}}
function addTemplate(){if(!pushConfig.templates)pushConfig.templates=[];pushConfig.templates.push({id:genId(),name:'新模板',title:'',content:'',type:'text'});markDirty()}
async function removeTemplate(tplId){if(!(await window.__confirm({title:'删除模板',text:'确定删除此模板？',confirmText:'删除',confirmColor:'error'})))return;pushConfig.templates=(pushConfig.templates||[]).filter(t=>t.id!==tplId);markDirty()}
function updateTpl(tplId,field,value){const t=(pushConfig.templates||[]).find(x=>x.id===tplId);if(t){t[field]=value;markDirty()}}

const allSrvCollapsed=computed(()=>servers.value.every(s=>s._collapsed))
function toggleSrvCollapseAll(){const target=!allSrvCollapsed.value;servers.value.forEach(s=>s._collapsed=target)}
function markServerDirty(){}
function addServer(){servers.value.forEach(s=>s._collapsed=true);servers.value.push({id:srvGenId(),name:'新服务器',type:'custom',baseUrl:'',fixedParams:{},paramMapping:[],expectedStatus:200,_collapsed:false})}
async function removeServer(srvId){if(!(await window.__confirm({title:'删除服务器',text:'确定删除此推送服务器？',confirmText:'删除',confirmColor:'error'})))return;servers.value=servers.value.filter(s=>s.id!==srvId)}
function applyServerPreset(srvId,type){const s=servers.value.find(x=>x.id===srvId);if(!s)return;const preset=serverPresets.value[type];s.type=type;s.paramMapping=preset?.paramMapping?JSON.parse(JSON.stringify(preset.paramMapping)):[];s.baseUrl=preset?.urlTemplate||s.baseUrl;s.expectedStatus=preset?.expectedStatus??200;markServerDirty()}
function addFixedParam(srvId){const s=servers.value.find(x=>x.id===srvId);if(!s)return;if(!s.fixedParams)s.fixedParams={};const key='key'+(Object.keys(s.fixedParams).length+1);s.fixedParams[key]='';markServerDirty()}
function removeFixedParam(srv,key){delete srv.fixedParams[key];markServerDirty()}
function renameFixedParam(srv,oldKey,newKey){if(oldKey===newKey||!newKey)return;const val=srv.fixedParams[oldKey];delete srv.fixedParams[oldKey];srv.fixedParams[newKey]=val;markServerDirty()}
function addMapping(srv){if(!srv.paramMapping)srv.paramMapping=[];const used=srv.paramMapping.map(m=>m.from);const next=fromFields.find(f=>!used.includes(f))||'title';srv.paramMapping.push({from:next,to:''});markServerDirty()}
function removeMapping(srv,idx){srv.paramMapping.splice(idx,1);markServerDirty()}
function getAvailableFromFields(srv,currentIdx){const used=new Set(srv.paramMapping.filter((_,i)=>i!==currentIdx).map(m=>m.from));return fromFields.map(f=>({title:f,value:f,disabled:used.has(f)}))}
function resolveServerUrl(srv){if(!srv?.baseUrl)return'';let url=srv.baseUrl;for(const[key,val]of Object.entries(srv.fixedParams||{}))url=url.replace('{'+key+'}',val||'');return url}
function previewUrl(srv){return resolveServerUrl(srv)||'(未配置)'}
function previewPayload(srv){const mapping=srv.paramMapping||[];const fixed=srv.fixedParams||{};const p={...fixed};const sample={title:'测试标题',content:'测试内容',type:'text'};for(const m of mapping){if(m.from&&m.to&&sample[m.from])p[m.to]=sample[m.from]}return Object.keys(p).length?p:{message:'无映射规则，将发送原始字段'}}
async function saveServers(){savingSrvs.value=true;try{await savePushServers(servers.value.map(s=>{const{_collapsed,...rest}=s;return rest}));window.__snackbar?.('服务器配置已保存','success')}catch(e){window.__snackbar?.('保存失败','error')}finally{savingSrvs.value=false}}

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
.url-input :deep(input){font-size:16px}
.push-header:focus-visible{outline:2px solid rgb(var(--v-theme-primary));outline-offset:-2px;border-radius:inherit}
@media (max-width:600px){.url-row .url-input{flex:1 1 100%}}
</style>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { getPushConfig, savePushConfig, sendPush, getEventsCatalog, getPushServers, savePushServers, getServerPresets } from '@/api/index.js'

const activeTab=ref('push')
const pushConfig=reactive({pushes:[],templates:[]})
const servers=ref([])
const serverPresets=ref({})
const eventCatalog=ref([])
const savingAll=ref(false)
const savingSrvs=ref(false)
const dirty=ref(false)
const activeInput=ref(null)
const testing=reactive({})
function markDirty(){dirty.value=true}
function isTesting(pushId){return !!testing[pushId]}

const categoryColors={'服务生命周期':'#6b7280','API 操作':'#0891b2','下载事件':'#dc2626','同步事件':'#7c3aed','任务管理':'#ea580c','配置变更':'#059669','错误事件':'#b91c1c'}
const presetColors={magicpush:'primary',bark:'success',serverchan:'warning',pushplus:'info',custom:'secondary'}
let _idCounter=Date.now()
function genId(){return 'p'+(_idCounter++)+'_'+Math.random().toString(36).substr(2,6)}
function srvGenId(){return 'srv_'+(_idCounter++)}
function getCategoryColor(c){return categoryColors[c]||'#888'}
function getEventName(type){for(const cat of eventCatalog.value)for(const evt of cat.events)if(evt.type===type)return evt.name;return type}
const templateVars=['{song_name}','{artist}','{quality}','{file_size}','{error}','{music_id}','{playlist_name}','{total_synced}','{success_count}','{total_count}','{keyword}','{now}','{当前时间}']
const fromFields=['title','content','type']

const tplSelectItems=computed(()=>(pushConfig.templates||[]).map(t=>({title:t.name||t.id,value:t.id})))
const serverSelectItems=computed(()=>servers.value.map(s=>({title:s.name||s.id,value:s.id})))
const presetTypeItems=computed(()=>Object.keys(serverPresets.value).map(k=>({title:serverPresets.value[k]?.name||k,value:k})))

function getServerName(id){const s=servers.value.find(x=>x.id===id);return s?.name||id}
function getTplName(id){const t=(pushConfig.templates||[]).find(x=>x.id===id);return t?.name||id}
function getServerInfo(id){const s=servers.value.find(x=>x.id===id);if(!s)return null;const url=resolveServerUrl(s);const mapping=s.paramMapping||[];return{name:s.name,url,mapping}}
function getPresetName(type){return serverPresets.value[type]?.name||type}
function getPresetColor(type){return presetColors[type]||'secondary'}

function insertVar(v){
  if(!activeInput.value){copyVarFallback(v);return}
  const el=activeInput.value
  const start=el.selectionStart??el.value.length
  const end=el.selectionEnd??start
  const before=el.value.substring(0,start)
  const after=el.value.substring(end)
  el.value=before+v+after
  const pos=start+v.length
  el.setSelectionRange(pos,pos)
  el.dispatchEvent(new Event('input',{bubbles:true}))
  el.focus()
}
async function copyVarFallback(v){try{await navigator.clipboard.writeText(v);window.__snackbar?.(`已复制 ${v}`,'success')}catch(e){window.__snackbar?.('复制失败','error')}}

const _pick=arr=>arr[Math.floor(Math.random()*arr.length)]
function genSampleVars(){
  const songs=['晴天','稻香','七里香','夜曲','告白气球','演员','光年之外','起风了','成都','平凡之路']
  const artists=['周杰伦','林俊杰','邓紫棋','李荣浩','陈奕迅','毛不易','薛之谦','五月天']
  const qualities=['标准','极高','无损','Hi-Res','母带']
  const playlists=['华语经典','深夜电台','通勤必备','私人雷达','怀旧金曲']
  const errors=['网络连接超时','版权限制无法下载','当前音质不支持','Cookie 已失效，请重新登录']
  const artist=_pick(artists);const total=10+Math.floor(Math.random()*40);const success=Math.max(0,total-Math.floor(Math.random()*4))
  return {song_name:_pick(songs),artist,quality:_pick(qualities),file_size:(8+Math.random()*42).toFixed(1)+' MB',error:_pick(errors),music_id:String(100000+Math.floor(Math.random()*899900000)),playlist_name:_pick(playlists),total_synced:String(success),success_count:String(success),total_count:String(total),keyword:artist}
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
async function loadConfig(){try{const[pushRes,eventRes,svrRes,preRes]=await Promise.all([getPushConfig(),getEventsCatalog(),getPushServers(),getServerPresets()]);if(pushRes?.status===200&&pushRes.data){const d=pushRes.data;pushConfig.pushes=(d.pushes||[]).map(p=>({...p,_collapsed:true,events:p.events||[],event_template:p.event_template?{...p.event_template,__tplId:''}:{}}));pushConfig.templates=d.templates||[]}if(eventRes?.status===200&&eventRes.data)eventCatalog.value=eventRes.data;if(svrRes?.status===200&&svrRes.data)servers.value=(svrRes.data||[]).map(s=>({...s,_collapsed:true}));if(preRes?.status===200&&preRes.data)serverPresets.value=preRes.data}catch(e){window.__snackbar?.('加载配置失败','error')}}
function addPush(){(pushConfig.pushes||[]).forEach(p=>p._collapsed=true);pushConfig.pushes.push({id:genId(),name:'新推送',enabled:true,_collapsed:false,events:[],event_template:{}});markDirty()}
async function removePush(id){if(!(await window.__confirm({title:'删除推送',text:'确定删除此推送？',confirmText:'删除',confirmColor:'error'})))return;pushConfig.pushes=pushConfig.pushes.filter(p=>p.id!==id);markDirty()}
function updatePush(id,field,value){const p=pushConfig.pushes.find(x=>x.id===id);if(p){p[field]=value;markDirty()}}
async function toggleEnabled(id,v){const p=pushConfig.pushes.find(x=>x.id===id);if(!p)return;p.enabled=v;p._collapsed=true;await saveAllConfig(true);window.__snackbar?.(v?'已启用并保存':'已停用并保存','success')}
function toggleEvent(pushId,eventType){const p=pushConfig.pushes.find(x=>x.id===pushId);if(!p)return;if(!p.events)p.events=[];const idx=p.events.indexOf(eventType);if(idx>=0)p.events.splice(idx,1);else p.events.push(eventType);markDirty()}
function selectTemplate(pushId,tplId){const p=pushConfig.pushes.find(x=>x.id===pushId);if(!p)return;if(!tplId){p.event_template={};markDirty();return}const t=(pushConfig.templates||[]).find(x=>x.id===tplId);if(t)p.event_template={title:t.title,content:t.content,type:t.type,__tplId:tplId};markDirty()}
async function testPushServer(pushId){const p=pushConfig.pushes.find(x=>x.id===pushId);if(!p)return;if(!p.serverId)return window.__snackbar?.('请先选择推送服务器','warning');testing[pushId]=true;try{const tpl=p.event_template||{};const title=renderTpl(tpl.title)||'测试标题';const content=renderTpl(tpl.content)||'测试内容';const r=await sendPush({serverId:p.serverId,title,content,type:tpl.type||'text'});window.__snackbar?.(r?.message||'推送成功',r?.success?'success':'error')}catch(e){window.__snackbar?.(e.message||'推送失败','error')}finally{testing[pushId]=false}}
async function saveAllConfig(silent=false){savingAll.value=true;try{const toSave={pushes:pushConfig.pushes.map(p=>{const{_collapsed,...rest}=p;return rest}),templates:pushConfig.templates};await savePushConfig(toSave);dirty.value=false;if(!silent)window.__snackbar?.('配置已保存','success')}catch(e){window.__snackbar?.('保存失败','error')}finally{savingAll.value=false}}
function addTemplate(){if(!pushConfig.templates)pushConfig.templates=[];pushConfig.templates.push({id:genId(),name:'新模板',title:'',content:'',type:'text'});markDirty()}
async function removeTemplate(tplId){if(!(await window.__confirm({title:'删除模板',text:'确定删除此模板？',confirmText:'删除',confirmColor:'error'})))return;pushConfig.templates=(pushConfig.templates||[]).filter(t=>t.id!==tplId);markDirty()}
function updateTpl(tplId,field,value){const t=(pushConfig.templates||[]).find(x=>x.id===tplId);if(t){t[field]=value;markDirty()}}

const allSrvCollapsed=computed(()=>servers.value.every(s=>s._collapsed))
function toggleSrvCollapseAll(){const target=!allSrvCollapsed.value;servers.value.forEach(s=>s._collapsed=target)}
function markServerDirty(){}
function addServer(){servers.value.forEach(s=>s._collapsed=true);servers.value.push({id:srvGenId(),name:'新服务器',type:'custom',baseUrl:'',fixedParams:{},paramMapping:[],expectedStatus:200,_collapsed:false})}
async function removeServer(srvId){if(!(await window.__confirm({title:'删除服务器',text:'确定删除此推送服务器？',confirmText:'删除',confirmColor:'error'})))return;servers.value=servers.value.filter(s=>s.id!==srvId)}
function applyServerPreset(srvId,type){const s=servers.value.find(x=>x.id===srvId);if(!s)return;const preset=serverPresets.value[type];s.type=type;s.paramMapping=preset?.paramMapping?JSON.parse(JSON.stringify(preset.paramMapping)):[];s.baseUrl=preset?.urlTemplate||s.baseUrl;s.expectedStatus=preset?.expectedStatus??200;markServerDirty()}
function addFixedParam(srvId){const s=servers.value.find(x=>x.id===srvId);if(!s)return;if(!s.fixedParams)s.fixedParams={};const key='key'+(Object.keys(s.fixedParams).length+1);s.fixedParams[key]='';markServerDirty()}
function removeFixedParam(srv,key){delete srv.fixedParams[key];markServerDirty()}
function renameFixedParam(srv,oldKey,newKey){if(oldKey===newKey||!newKey)return;const val=srv.fixedParams[oldKey];delete srv.fixedParams[oldKey];srv.fixedParams[newKey]=val;markServerDirty()}
function addMapping(srv){if(!srv.paramMapping)srv.paramMapping=[];const used=srv.paramMapping.map(m=>m.from);const next=fromFields.find(f=>!used.includes(f))||'title';srv.paramMapping.push({from:next,to:''});markServerDirty()}
function removeMapping(srv,idx){srv.paramMapping.splice(idx,1);markServerDirty()}
function getAvailableFromFields(srv,currentIdx){const used=new Set(srv.paramMapping.filter((_,i)=>i!==currentIdx).map(m=>m.from));return fromFields.map(f=>({title:f,value:f,disabled:used.has(f)}))}
function resolveServerUrl(srv){if(!srv?.baseUrl)return'';let url=srv.baseUrl;for(const[key,val]of Object.entries(srv.fixedParams||{}))url=url.replace('{'+key+'}',val||'');return url}
function previewUrl(srv){return resolveServerUrl(srv)||'(未配置)'}
function previewPayload(srv){const mapping=srv.paramMapping||[];const fixed=srv.fixedParams||{};const p={...fixed};const sample={title:'测试标题',content:'测试内容',type:'text'};for(const m of mapping){if(m.from&&m.to&&sample[m.from])p[m.to]=sample[m.from]}return Object.keys(p).length?p:{message:'无映射规则，将发送原始字段'}}
async function saveServers(){savingSrvs.value=true;try{await savePushServers(servers.value.map(s=>{const{_collapsed,...rest}=s;return rest}));window.__snackbar?.('服务器配置已保存','success')}catch(e){window.__snackbar?.('保存失败','error')}finally{savingSrvs.value=false}}

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
.url-input :deep(input){font-size:16px}
.push-header:focus-visible{outline:2px solid rgb(var(--v-theme-primary));outline-offset:-2px;border-radius:inherit}
@media (max-width:600px){.url-row .url-input{flex:1 1 100%}}
</style>
