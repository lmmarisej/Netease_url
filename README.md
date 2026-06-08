# 网易云音乐工具箱

基于 Flask 的网易云音乐 API 服务，支持歌曲搜索、解析、下载、歌单同步，提供 Web 管理界面。

## TODO list

- [ ] 添加更多 API 端点
- [ ] 增加`我的`功能，查看当前cookie对应账号信息【可与下载用的cookie不相同】
- [ ] 可对当前账号喜欢的音乐镜像操作
- [ ] 支持多个账户cookie
- [ ] 同步功能，开启歌单完全匹配功能，开启后歌单同步删除歌曲，本地也删除

## 🚀 快速开始

```bash
pip install -r requirements.txt
# 将黑胶会员 Cookie 写入 config/cookie.txt
python main.py
# 访问 http://localhost:5000
```

Docker 部署：

```bash
docker-compose up -d
```

## 🌐 页面功能

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | 业务操作 | 歌曲搜索、单曲/歌单/专辑解析、音乐下载 |
| `/files` | 文件管理 | 本地下载文件浏览、音频播放、删除管理 |
| `/config` | 配置 | 同步配置、下载配置 & Cookie 管理 |
| `/magicpush` | 消息推送 | 推送配置管理 + 事件模板管理 |
| `/tasks` | 任务监控 | 实时下载任务进度跟踪 |
| `/api-docs` | API 接口文档 | 全部 API 端点说明与示例 |
| `/logs` | 运行日志 | 实时查看服务日志（3s 刷新） |

### 页面截图

![img.png](img.png)

## 🔌 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET/POST | `/song` | 获取歌曲信息（URL/歌词/详情） |
| GET/POST | `/search` | 搜索音乐 |
| GET/POST | `/playlist` | 获取歌单详情 |
| GET/POST | `/album` | 获取专辑详情 |
| GET/POST | `/download` | 下载音乐文件 |
| GET/POST | `/sync/config` | 定时同步配置 |
| GET | `/sync/status` | 同步状态查询 |
| POST | `/sync/now` | 立即触发同步 |
| GET | `/api/info` | API 服务信息 |
| GET | `/api/api-docs` | API 文档 JSON |
| GET | `/api/logs` | 日志内容 API |
| GET | `/api/cookie` | 获取 Cookie 配置 |
| POST | `/api/cookie` | 保存 Cookie 配置 |

> 完整文档见 Web 界面 `/api-docs`

## 🎵 音质等级

| 参数值 | 说明 | 要求 |
|--------|------|------|
| `standard` | 标准音质 | 黑胶 VIP |
| `exhigh` | 极高音质 | 黑胶 VIP |
| `lossless` | 无损音质 | 黑胶 VIP |
| `hires` | Hi-Res 音质 | 黑胶 VIP |
| `jyeffect` | 高清环绕声 | 黑胶 VIP |
| `sky` | 沉浸环绕声 | 黑胶 SVIP |
| `jymaster` | 超清母带 | 黑胶 SVIP |

## 📁 项目结构

```
├── main.py                 # 入口
├── code/                   # Python 模块
│   ├── music_api.py        # 网易云 API 封装
│   ├── music_downloader.py # 下载器
│   ├── playlist_sync.py    # 定时同步
│   ├── cookie_manager.py   # Cookie 管理
y│   ├── qr_login.py         # 扫码登录
│   ├── task_manager.py     # 任务管理器
│   ├── event_bus.py        # 事件总线（发布/订阅）
│   └── push_manager.py     # 消息推送管理
├── config/
│   ├── settings.json       # 运行配置
│   ├── api.json            # API 文档定义
│   ├── sync_config.json    # 同步配置（运行时生成）
│   ├── push_config.json    # 推送配置 + 事件模板
│   └── cookie.txt          # Cookie 配置
├── templates/              # Web 页面
│   ├── index.html          # 业务操作
│   ├── files.html          # 文件管理
│   ├── config.html         # 配置
│   ├── magicpush.html      # 消息推送
│   ├── tasks.html          # 任务监控
│   ├── logs.html           # 运行日志
│   └── api-docs.html       # API 文档
├── logs/                   # 日志文件
├── downloads/              # 下载目录
└── screenshots/            # 截图
```

## ⚠️ 注意事项

- 需要网易云音乐黑胶会员账号 Cookie 才能解析高音质
- 将 Cookie 完整内容写入 `config/cookie.txt` 文件，或在 Web 界面 `/config` → Cookie 配置中编辑
- 同步配置和 Cookie 均在 Web 界面 `/config` 中管理（页签切换）

## 📄 许可证

MIT License
