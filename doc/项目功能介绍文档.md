#  网易云音乐工具箱项目功能介绍文档

> 会话日期: 2026-06-07 | 基于 Python Flask + Bootstrap 5

## 最终项目结构

```
Netease_url/
├── main.py                    # Flask 入口（根目录）
├── code/                      # Python 模块
│   ├── music_api.py           # 网易云 API 封装（加密、请求）
│   ├── music_downloader.py    # 音乐下载器（含 mutagen 标签写入）
│   ├── playlist_sync.py       # 定时歌单同步（APScheduler）
│   ├── cookie_manager.py      # Cookie 读写管理
│   ├── qr_login.py            # 二维码登录
│   └── task_manager.py        # 🆕 通用任务管理器（线程安全单例）
├── config/                    # JSON 配置文件
│   ├── settings.json          # 🆕 运行配置（替代 .env）
│   ├── api.json               # API 文档定义数据
│   ├── sync_config.json       # 运行时生成的同步配置
│   ├── cookie.txt             # 🆕 Cookie 配置（从根目录迁移）
│   └── push_config.json       # 🆕 消息推送配置
├── templates/                 # 前端页面
│   ├── index.html             # 🔄 业务操作（标签页重构）
│   ├── config.html            # 🔄 配置页（三页签重构）
│   ├── magicpush.html         # 🆕 消息推送（Magic Push）
│   ├── tasks.html             # 🆕 任务监控
│   ├── api-docs.html          # 🆕 API 文档（折叠式）
│   └── logs.html              # 🆕 运行日志查看器
├── logs/                      # 🆕 日志目录
│   ├── music_api.log          # 服务日志（RotatingFileHandler 2MB）
│   ├── playlist_sync.log      # 同步日志
│   └── operation.log          # 🆕 操作历史日志
├── downloads/                 # 下载目录
├── screenshots/               # 🆕 截图目 录
├── requirements.txt
├── Dockerfile                 # 🔄 python:3.12-slim
├── docker-compose.yml         # 🔄 精简环境变量
├── entrypoint.sh              # 🔄 简化
├── .gitignore / .dockerignore # 🔄 更新
├── LICENSE
├── README.md                  # 🔄 精简重写 + 截图
└── SESSION_SUMMARY.md         # 本文档
```

## 已删除的文件

- `quick_test.py`, `test_sync_local.py`, `test_sync.bat` — 测试文件
- `本地测试指南.md`, `使用文档.md`, `定时同步使用说明.md` — 冗余文档
- `setup_config.bat`, `setup_config.ps1` — 配置脚本
- `.env`, `.env.example` — 配置已迁移到 `config/settings.json`
- 根目录 `cookie.txt` — 已迁移到 `config/cookie.txt`

---

## 一、项目结构重组

### 1.1 代码模块移入 `code/`
- 所有 `.py` 模块（除 `main.py`）移入 `code/` 目录
- `main.py` 顶部添加 `sys.path.insert(0, 'code/')` 确保导入正常
- 内部模块间导入无需修改（同在 `code/` 目录）

### 1.2 配置 JSON 化
- **`config/settings.json`** — 运行配置，优先级最高
  ```json
  { "host": "0.0.0.0", "port": 5000, "downloads_dir": "downloads",
    "log_level": "INFO", "debug": false, ... }
  ```
- `main.py` 启动时读取顺序: `settings.json` > 环境变量 > 默认值
- `.env` 已删除，`docker-compose.yml` 移除 `env_file`

### 1.3 日志统一到 `logs/`
- `main.py` + `playlist_sync.py` 日志写入 `logs/` 目录
- 使用 `RotatingFileHandler(maxBytes=2MB, backupCount=3)`

---

## 二、新增功能

### 2.1 API 文档页面 (`/api-docs`)
- **`templates/api-docs.html`** — 从 `/api/api-docs` JSON 动态渲染
- 接口**折叠展示**：默认只显示方法+路径+描述，点击展开参数/示例
- 分类卡片 + 枚举值参考 + 统一响应格式说明
- **`/api/api-docs`** 端点 — 读取 `config/api.json` 返回 JSON

### 2.2 日志查看页面 (`/logs`)
- **`templates/logs.html`** — 实时日志查看
- 3 秒自动刷新，最近 1000 条，**倒序排列**
- 日志文件下拉切换 + 暂停/恢复 + 手动刷新
- **`/api/logs`** — 返回日志 JSON（支持 `?file=&limit=`）
- **`/api/logs/cleanup`** — 清空所有日志文件
- 工具栏「🗑️ 清空日志」按钮

### 2.3 操作日志 (`logs/operation.log`)
- 独立的 `operation_logger`（`RotatingFileHandler`）
- 记录：`[歌单解析] ID=xxx 名称=xxx`
- 记录：`[音乐下载] ID=xxx 歌名=xxx 歌手=xxx 音质=xxx`

### 2.4 任务管理系统
- **`code/task_manager.py`** — 通用任务管理器（线程安全单例）
  - 任务状态: `pending → running → completed / failed / cancelled`
  - 进度跟踪 0-100%，扩展字段，自动清理 >100 条
- **`/tasks`** 页面 — 实时任务监控（3秒刷新）
  - 状态筛选：全部/执行中/已完成/失败
  - 显示歌名、歌手、音质、进度条
- **任务 API**: `GET/POST/DELETE /api/tasks/*`
- 下载端点已接入任务系统：创建任务 → 更新进度 → 标记完成/失败

### 2.5 Toast 通知替代 alert
- 所有页面 `alert()` 替换为右上角 Toast（2秒自动消失）
- 支持 4 种类型：`success`(绿) / `error`(红) / `warning`(黄) / `info`(蓝)

### 2.6 前端历史记录
- 搜索/歌单/专辑/下载 四个标签页各有 localStorage 历史
- 最多 20 条，自动去重，点击重新执行，✕ 删除

---

## 三、页面重构

### 3.1 业务操作页 (`index.html`) — 标签页重构
**旧:** 下拉框切换模式，功能区隐藏，结果分散

**新:** 
- 4 个标签页始终可见：🔍搜索 | 📋歌单 | 💿专辑 | ⬇️下载
- 搜索：卡片网格布局，封面图+歌名+歌手，悬停动效
- 歌单/专辑：头部信息卡 + 整齐曲目列表
- 下载：输入 ID → 失焦自动查询歌名，音质按钮组选择
- 歌曲详情：**Bootstrap Modal 弹窗**（封面限制 140px），内嵌 APlayer
- Enter 键触发搜索/解析

### 3.2 配置页 (`config.html`) — 三页签重构
**旧:** 仅定时同步配置，开关式折叠

**新:**
- 页签式布局：🔄 同步配置 | ⬇️ 下载配置 | 🍪 Cookie 配置
- **同步配置**: 原定时同步全部功能（歌单标签管理 + 音质 + 调度方式）
- **下载配置**: 下载目录 + 保存到本地开关 + 浏览器同时下载选项 + 模式说明
- **Cookie 配置**: textarea 编辑 + 有效性状态 + 保存/清空

---

## 四、后端优化

### 4.1 Docker 优化
- 基础镜像: `python:3.9.22-alpine3.21` → **`python:3.12-slim`**（3.9 已 EOL）
- `COPY . .` → 分层复制（`code/`, `config/`, `templates/`）
- `pip3 config set` → `pip install -i` 直接指定镜像
- `entrypoint.sh` 精简为 `python3 main.py`

### 4.2 音质自动降级
下载时如果请求的音质不可用，自动逐级降级：
```
jymaster → sky → jyeffect → hires → lossless → exhigh → standard
```
- 文件名使用实际音质标记
- 任务消息提示降级信息
- 所有音质均不可用才返回错误

### 4.3 Cookie 配置迁移
- Cookie 存储路径从根目录 `cookie.txt` 迁移到 `config/cookie.txt`
- `cookie_manager.py`、`qr_login.py` 默认路径同步更新
- `settings.json` 中 `cookie_file` 默认值更新
- 新增 `GET/POST /api/cookie` 端点，Web 界面直接编辑

### 4.4 下载流式代理
- `/download` 端点改为流式代理：从网易云获取 URL 后，逐 chunk 同时写本地 + 发浏览器
- 浏览器无需等待后台下载完成，第一个 chunk 到达即开始下载
- 三种模式由配置驱动：仅浏览器 / 保存+浏览器 / 仅本地

### 4.5 菜单栏顺序（全部页面统一）
```
🏠 业务操作 → ⚙️ 配置 → 📨 消息推送 → 📊 任务监控 → 📋 运行日志 → 📖 API文档
```

---

## 五、关键 API 端点汇总

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/song` | 歌曲信息 |
| GET/POST | `/search` | 搜索音乐 |
| GET/POST | `/playlist` | 歌单详情 |
| GET/POST | `/album` | 专辑详情 |
| GET/POST | `/download` | 下载音乐（流式代理 + 音质降级） |
| GET | `/health` | 健康检查 |
| GET/POST | `/sync/config` | 同步配置 |
| GET | `/sync/status` | 同步状态 |
| POST | `/sync/now` | 立即同步 |
| GET/POST | `/api/cookie` | Cookie 配置 |
| GET/POST | `/api/settings` | 下载等通用配置 |
| GET/POST | `/api/push/config` | 推送配置 |
| POST | `/api/push/send` | 发送推送测试 |
| GET | `/api/info` | API 服务信息 |
| GET | `/magicpush` | 消息推送页面 |
| GET | `/api-docs` | API 文档页面 |
| GET | `/api/api-docs` | API 文档 JSON |
| GET | `/logs` | 日志页面 |
| GET | `/api/logs` | 日志内容 API |
| POST | `/api/logs/cleanup` | 清理日志 |
| GET | `/tasks` | 任务监控页面 |
| GET | `/api/tasks` | 任务列表 |
| GET | `/api/tasks/<id>` | 任务详情 |
| DELETE | `/api/tasks/<id>` | 删除任务 |
| POST | `/api/tasks/clear` | 清理已完成任务 |

---

---

## 七、新增功能（2026-06-07 下半场）

### 7.1 歌单名称展示
- 添加歌单时自动调用 `/playlist` API 获取歌单名称
- 标签显示格式：`📋 歌单名称 (ID: xxx) ✕`
- 使用 `localStorage` 缓存歌单名称，避免重复请求

### 7.2 Cookie 配置迁移
- Cookie 从根目录 `cookie.txt` 移至 `config/cookie.txt`
- `cookie_manager.py`、`qr_login.py` 默认路径同步更新
- 新增 `GET/POST /api/cookie` 端点，支持 Web 界面直接编辑
- Cookie 状态显示简化：仅显示项数，不再逐字段列举缺失

### 7.3 下载配置体系
- `settings.json` 新增 `download_save_local`、`download_browser` 字段
- 配置页新增「⬇️ 下载配置」页签：下载目录 / 保存开关 / 浏览器选项
- `/download` 端点三种模式：
  - 🌐 仅浏览器（流式代理，临时文件自动清理）
  - 💾🌐 保存 + 浏览器（同时写文件 + 流式发送）
  - 💾 仅本地（后台线程下载，JSON 通知）

### 7.4 流式下载代理
- `/download` 端点改为 `requests.get(stream=True)` + Flask `Response(stream_with_context(...))`
- 浏览器在第一个 chunk 到达时即开始下载，无需等待完整文件
- 使用 `shutil.move` 处理临时文件，`call_on_close` 自动清理

### 7.5 消息推送（Magic Push）
- 新增 `templates/magicpush.html` — 推送配置管理页面
- 每个推送配置支持多个接口地址，独立启用/禁用
- 卡片折叠/展开，Toggle 开关在卡片头部
- `GET/POST /api/push/config` — 配置持久化到 `config/push_config.json`
- `POST /api/push/send` — 测试推送（超时/连接错误有明确提示）
- 推送格式：`POST application/json → {"title":"","content":"","type":"text"}`

### 7.6 前端错误提示优化
- `doDownload()` 非 200 响应时读取 JSON 响应体显示具体错误原因
- `testPush()` 改为传 ID 而非静态 URL 值，支持实时输入

---

## 八、技术要点

- **日志滚动**: `RotatingFileHandler(maxBytes=2*1024*1024, backupCount=3)`
- **任务管理**: 线程安全单例 `TaskManager`，用于下载进度跟踪
- **配置优先级**: `settings.json` > 环境变量 > 默认值
- **前端框架**: jQuery 3.7 + Bootstrap 5.1.3 + APlayer 1.10.1
- **Toast 动画**: CSS `@keyframes toastIn` 0.3s fadeIn
- **localStorage**: 历史记录存储 + 歌单名称缓存
- **流式代理**: Flask `stream_with_context` + `requests` stream 模式
- **线程安全**: `Thread` 后台下载 + `TaskManager` 单例
