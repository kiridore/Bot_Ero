# BotEro (小埃同学) 知识库索引

（BotEro = QQ 群机器人 + 单进程 FastAPI 社区站。webapp 共 11 个功能模块：timeline 社区时间线（根路径 `/` 主页，30s 实时轮询 + 逐卡未读已读）、forum 议事厅（长文/公告/单选多选多子投票/两级嵌套评论，Tiptap 富文本）、tools 工具箱（网页链接收藏卡片 + tag 云 + 点击统计）、weekly 小埃周报（每周一 08:00 自动出版）+ gallery/guestbook/profile/trpg/alarms/activities/live；全站登录门控，独立登录页 /login）
>
> 本文件是总索引，具体内容按主题拆分到 `kb/` 目录和 `specs/` 目录。
> AI 读取流程: KNOWLEDGE_BASE.md → 按需读取链接文档。

---

## 快速入口

| 需要了解 | 阅读 |
|---------|------|
| 项目身份、硬编码常量、所有指令 | [`kb/QUICK_REFERENCE.md`](kb/QUICK_REFERENCE.md) |
| 47 个插件列表、功能包、数据依赖 | [`kb/PLUGIN_CATALOG.md`](kb/PLUGIN_CATALOG.md) |
| 打卡流程、抽奖概率、商店价格、称号列表 | [`kb/GAMEPLAY.md`](kb/GAMEPLAY.md) |
| 开发规范、AI 检查清单、技术债、陷阱 | [`kb/CONVENTIONS.md`](kb/CONVENTIONS.md) |
| API 速查、部署运维、外部 API | [`kb/OPERATIONS.md`](kb/OPERATIONS.md) |
| 数据库全部 44 张表 Schema（data.db）+ message_log.db | [`kb/DATABASE.md`](kb/DATABASE.md) |

---

## Spec 文档（`specs/`）

以下内容由 `specs/` 目录覆盖，KB 不再重复：

| 文档 | 内容 |
|------|------|
| [`specs/architecture.md`](specs/architecture.md) | 系统架构、事件流、线程模型、模块依赖 |
| [`specs/plugins.md`](specs/plugins.md) | 插件开发契约、生命周期、基类说明 |
| [`specs/plugin-catalog.md`](specs/plugin-catalog.md) | 全部插件注册表 |
| [`specs/conventions.md`](specs/conventions.md) | 编码约定、隐式知识、路径、周边界 |
| [`specs/database.md`](specs/database.md) | 数据库 Schema 概述、迁移规则 |
| [`specs/onebot-protocol.md`](specs/onebot-protocol.md) | OneBot v11 协议、CQ 消息构造 |
| [`specs/web-gallery.md`](specs/web-gallery.md) | Web 应用架构（单进程 webapp：11 模块 + 共享 core + 全站登录门控）、API 路由 |
| [`specs/image-generation.md`](specs/image-generation.md) | 图片生成子系统（热度图/档案卡） |
| [`specs/timeline-protocol.md`](specs/timeline-protocol.md) | 社区时间线事件协议（Event Server / 发送方接入 / 撤回 / 占位符） |
| [`specs/llm-subsystem.md`](specs/llm-subsystem.md) | LLM 子系统（已弃用） |

---

## 目录结构

```
./
├── KNOWLEDGE_BASE.md         ← 本文件（索引）
├── main.py                    ← 启动入口
├── core/                      ← 核心库（bot 与 Web 子应用共享）
│   ├── base.py                ← Plugin/CommandPlugin/TimedHeartbeatPlugin
│   ├── context.py             ← 运行时上下文、SYSTEM_PLUGINS、plugin_key
│   ├── config.py              ← 全部 BOTERO_* 环境变量读取
│   ├── auth.py                ← make_login_key / verify_login_key（登录密钥）
│   ├── onebot_client.py       ← resolve_display_name / resolve_avatar_url
│   ├── title_defs.py          ← TITLE_DEFS 加载
│   ├── feature_packs.py       ← 功能包定义
│   ├── api.py                 ← API 封装、Echo 机制
│   ├── cq.py                  ← CQ 消息段构造器
│   ├── event.py               ← Event 包装器
│   ├── database_manager.py    ← DbManager（统一 DB_PATH + WAL + busy_timeout=5000）
│   ├── db/                    ← 各业务模块数据库管理层（checkin/points/shop/lottery/titles/alarm/immortal/quest/activity/guestbook/redeem/timeline/forum/tools/weekly/message_log）
│   ├── character_store.py     ← 角色卡 JSON 存储（server_data/trpg_chars/）
│   ├── user_settings.py       ← 个人设置 JSON 存储（server_data/user_settings/）
│   ├── trpg/                  ← 跑团规则（rules.py）与角色派生计算（character.py）
│   ├── utils.py               ← 工具函数、QUEST_DEFS
│   ├── gen_image/             ← 图片生成（热度图/档案卡）
│   ├── web/                   ← Web 共享层（auth_deps.py 登录依赖注入唯一权威副本 + static/ 共享静态）
│   ├── web/static/            ← 共享静态（auth.js 认证 token 管理 + 全局 fetch 401 拦截跳 /login + goLogin/logout/renderAuth（登录按钮/用户 chip/退出按钮），HTML 引用带 ?v= 版本号；nav.js 站点导航条（当前分区高亮）；base.css/profile.css（报纸风主题 token 全站唯一来源）；motion.css/motion.js 动效层（--motion-fast/base/slow/--spring/--ease/--reveal-dist）；lightbox.js 共享图片灯箱：点击 .tl-images a 或 img.forum-img 在当前页放大，复用 .lightbox 样式；icons.js 自托管 lucide SVG 图标）
│   ├── timeline_client.py     ← 社区时间线事件发送助手（emit_event/retract_event，best-effort）
│   └── logger.py              ← 日志
├── plugins/                   ← 47 个已注册插件
├── kb/                        ← 知识库子文档
│   ├── QUICK_REFERENCE.md
│   ├── PLUGIN_CATALOG.md
│   ├── GAMEPLAY.md
│   ├── CONVENTIONS.md
│   ├── OPERATIONS.md
│   └── DATABASE.md
├── specs/                     ← 规范文档
├── scripts/                   ← 部署脚本（botero.env 盐单一来源 / systemd unit / Caddyfile / botero-services.sh）
├── docs/                      ← 部署文档 + 归档设计文档（docs/archive/superpowers/）
├── roadmap.md                 ← 路线图（当前版本见 core/config.py::BOTERO_VERSION + CHANGELOG.md）
├── webapp/                    ← Web 单进程入口（8765；认证路由/时间线主页/static 合并目录；`python -m webapp`）
│   ├── app.py                 ← 唯一 FastAPI 入口（login_guard 全局登录门控中间件：白名单外全部路由要求登录，页面 302 → /login?next=…、API 与媒体 401；凭证 Bearer 头或 botero_key cookie 双通道；白名单 = /login、/api/auth/login、/static、/shared、/api/timeline/events*（bot 事件令牌自鉴权）；include 11 模块 router + 时间线主页 / + 登录页 /login + mount /static /shared；core/web/auth_deps.py 的依赖注入同样 cookie 兜底）
│   ├── timeline/              ← 时间线模块（Event Server：POST/DELETE /api/timeline/events + GET /api/timeline + 读状态端点 /api/timeline/poll /new /read；entries.json 侧边栏导航数据源，含「工具箱」入口；主页报头氛围动效（金线流动/标题依次浮现，timeline.css，reduced-motion 关闭）；30s 轮询「查看 N 条新事件」pill + 逐卡未读高亮（渲染即上报已读回执，每用户 rowid 水印 + 回执，见 specs/timeline-protocol.md；高亮仅为视觉提示：卡片首次进入视口后停留约 0.8s 再以约 1.5s 渐变褪回正常，动画独立于上报必定播完，reduced-motion 直接跳变））
│   ├── forum/                 ← 议事厅模块（/forum；长文/公告/投票/评论；Tiptap 富文本；投票支持单选/多选 + 单帖多子投票（表 forum_polls 子投票，forum_poll_options/votes 以 poll_id 关联；单选一人一票、多选可投多个选项且同选项不重复）；评论两级嵌套回复链（forum_comments 加列 parent_id/root_id/edited_at：顶层评论 id DESC keyset 分页、replies 串内 id ASC，回复的回复 root_id 仍指顶层、UI 标注「回复 @某人」；作者可内联编辑评论（PATCH /api/forum/comments/{id}，时间线 forum_comment:{id} 同 key 重发）；删除有存活回复的评论为软删占位（status='deleted' 占位、回复链保留），无回复则物理删；回复目标不存在/跨帖/已软删 → 400）；作者可编辑/删除自己的帖子（编辑：/forum/new?id=，类型/投票结构不可改，编辑后撤回旧时间线事件并以同 key 重发；删除：级联清评论，按 key 撤回事件）；tag 列表仅返回被引用 tag，删帖/编辑后悬空 tag 自动清理；正文图片上传 /forum/media/（POST /api/forum/images，JPG/PNG/WebP/GIF ≤10MB，落盘 server_data/forum_images/，公开读取 uuid 文件名不可枚举）；详见 docs/archive/superpowers/specs/2026-08-10-forum-design.md）
│   ├── tools/                 ← 工具箱模块（/tools 页面 + GET/POST/PUT/DELETE /api/tools + GET /api/tools/tags（全部 tag 及计数）+ GET /api/tools/icon（卡片图标兜底解析：客户端先直连 favicon.ico，失败/10s 挂起转服务端抓首页 link rel=icon，入库缓存、无图标负缓存 7 天、内网地址拒绝防 SSRF，见 webapp/tools/icon.py）+ POST /api/tools/{id}/click；仅登录可提交/编辑/删除自己的链接；提交/修改/删除推送/撤回时间线事件 source=tools（specs/timeline-protocol.md 注册）；链接收藏卡片：icon 浏览器直连 + 服务端解析兜底、关键字搜索、双维度排序（时间/热度 × 正/倒序，偏好存 localStorage）、tag 云（全部 tag + 使用数量，点击筛选）+ tag 徽标/筛选（提交时逗号分隔自由创建，create-or-get）、点击统计（眼睛图标展示，公开计数）、卡片/列表双视图、卡片展示提交者昵称头像；头部操作/编辑/删除按钮为内联 SVG 图标（自托管 lucide-static ISC，core/web/static/icons.js）；表 tools_links/tools_tags/tools_link_tags/tools_icon_cache，读写 core/db/tools.py）
│   ├── weekly/                 ← 周报模块（/weekly 报纸页面 + /api/weekly 归档 API；详见 docs/archive/superpowers/specs/2026-08-15-weekly-report-design.md）

│   ├── gallery/               ← 图库模块（/gallery；repository/thumbnails/dates）
│   ├── guestbook/             ← 留言簿模块（/guestbook）
│   ├── profile/               ← 个人中心模块（/profile）
│   ├── trpg/                  ← 跑团模块（/trpg）
│   ├── alarms/                ← 闹钟模块（/alarms）
│   ├── activities/            ← 活动归档模块（/activities）
│   ├── live/                  ← 直播间模块（/live；SRS HTTP-FLV 播放 + /api/live/status 探测 + 观众在场 heartbeat/viewers，登录显示昵称）
│   └── static/                ← 全部模块静态文件（login.html/js/css 独立登录页（next 回跳 + 会话自愈）、timeline.html/js/css、index.html、profile.html/js、trpg.html/js、guestbook.*、alarms.*、activities*.html/js、forum.*、tools.*、weekly.* 等；页面统一注入 /shared/motion.css + /shared/motion.js 动效层：View Transitions 页面过渡、data-reveal 滚动揭示批量交错（40ms/级上限 300ms，视口下方 25% 预揭示区提前进场）、按压反馈、lightbox/toast 过渡、数字滚动，prefers-reduced-motion 全关闭）
└── test/                      ← 临时测试脚本
```

---

## 关键路径图解

```
on_message()                    main.py
  │
  ├─ "echo" → api.Echo.match()
  │
  └─ resolve_event_type()
       │ "meta" / "notice" / "message"
       │
       └─ threading.Thread(plugin_pool)
            │
            └─ for plugin_cls in context.plugin_registry:
                 │ meta 事件 → 跳过检查
                 │ 非 meta: is_plugin_enabled(cls, group_id)?
                 │   系统插件 ✓ | 已启用 ✓ | 已禁用 → continue
                 │
                 plugin = plugin_cls(context)   ← 新实例
                 if plugin.match(event_type):
                     plugin.handle()
```

### 三层管理粒度

```
功能包级     /开启功能包 基础包          批量操作 shortcut
  ↓
插件级       /启用插件 checkin           精确控制单个插件
  ↓
系统级       SYSTEM_PLUGINS (7个)        始终运行，不可禁用
```
