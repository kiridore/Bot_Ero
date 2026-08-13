# BotEro (小埃同学) 知识库索引

（社区时间线：webapp 第 8 个模块 timeline；新增第 9 个模块 forum 议事厅：长文/公告/投票/评论，所有用户消息自动入时间线，bot 发群消息；Tiptap 富文本；新增第 10 个模块 tools 工具箱：网页链接收藏卡片 /tools，icon 解析自域名、关键字搜索、双维度排序、tag 徽标/筛选、点击统计、卡片/列表双视图）
>
> 本文件是总索引，具体内容按主题拆分到 `kb/` 目录和 `specs/` 目录。
> AI 读取流程: KNOWLEDGE_BASE.md → 按需读取链接文档。

---

## 快速入口

| 需要了解 | 阅读 |
|---------|------|
| 项目身份、硬编码常量、所有指令 | [`kb/QUICK_REFERENCE.md`](kb/QUICK_REFERENCE.md) |
| 45 个插件列表、功能包、数据依赖 | [`kb/PLUGIN_CATALOG.md`](kb/PLUGIN_CATALOG.md) |
| 打卡流程、抽奖概率、商店价格、称号列表 | [`kb/GAMEPLAY.md`](kb/GAMEPLAY.md) |
| 开发规范、AI 检查清单、技术债、陷阱 | [`kb/CONVENTIONS.md`](kb/CONVENTIONS.md) |
| API 速查、部署运维、外部 API | [`kb/OPERATIONS.md`](kb/OPERATIONS.md) |
| 数据库全部 20+ 表 Schema | [`kb/DATABASE.md`](kb/DATABASE.md) |

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
| [`specs/web-gallery.md`](specs/web-gallery.md) | Web 应用架构（单进程 webapp：10 模块 + 共享 core）、API 路由 |
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
│   ├── db/                    ← 各业务模块数据库管理层（checkin/points/shop/lottery/titles/alarm/immortal/quest/activity/guestbook/redeem/timeline/forum/tools）
│   ├── character_store.py     ← 角色卡 JSON 存储（server_data/trpg_chars/）
│   ├── user_settings.py       ← 个人设置 JSON 存储（server_data/user_settings/）
│   ├── trpg/                  ← 跑团规则（rules.py）与角色派生计算（character.py）
│   ├── utils.py               ← 工具函数、QUEST_DEFS
│   ├── gen_image/             ← 图片生成（热度图/档案卡）
│   ├── web/static/            ← Web 共享静态（auth.js/gallery.css/profile.css）；Web 主题统一为报纸风（token 全站唯一来源 core/web/static/gallery.css）
│   ├── timeline_client.py     ← 社区时间线事件发送助手（emit_event/retract_event，best-effort）
│   └── logger.py              ← 日志
├── plugins/                   ← 45 个已注册插件
├── kb/                        ← 知识库子文档
│   ├── QUICK_REFERENCE.md
│   ├── PLUGIN_CATALOG.md
│   ├── GAMEPLAY.md
│   ├── CONVENTIONS.md
│   ├── OPERATIONS.md
│   └── DATABASE.md
├── specs/                     ← 规范文档
├── webapp/                    ← Web 单进程入口（8765；认证路由/时间线主页/static 合并目录；`python -m webapp`）
│   ├── app.py                 ← 唯一 FastAPI 入口（include 10 模块 router + 时间线主页 / + mount /static /shared）
│   ├── timeline/              ← 时间线模块（Event Server：POST/DELETE /api/timeline/events + GET /api/timeline；entries.json 侧边栏导航数据源，含「工具箱」入口；协议见 specs/timeline-protocol.md）
│   ├── forum/                 ← 议事厅模块（/forum；长文/公告/投票/评论；Tiptap 富文本；正文图片上传 /forum/media/（POST /api/forum/images，JPG/PNG/WebP/GIF ≤10MB，落盘 server_data/forum_images/，公开读取 uuid 文件名不可枚举）；详见 docs/superpowers/specs/2026-08-10-forum-design.md）
*82|│   ├── tools/                 ← 工具箱模块（/tools 页面 + GET/POST/DELETE /api/tools + POST /api/tools/{id}/click；仅登录可提交/删除自己的链接；提交/删除推送/撤回时间线事件 source=tools（specs/timeline-protocol.md 注册）；链接收藏卡片：icon 解析自域名、关键字搜索、双维度排序（时间/热度 × 正/倒序，偏好存 localStorage）、tag 徽标/点击筛选（提交时逗号分隔自由创建，create-or-get）、点击统计（公开计数展示在卡片）、卡片/列表双视图、卡片展示提交者昵称头像；表 tools_links/tools_tags/tools_link_tags，读写 core/db/tools.py）

│   ├── gallery/               ← 图库模块（/gallery；repository/thumbnails/dates）
│   ├── guestbook/             ← 留言簿模块（/guestbook）
│   ├── profile/               ← 个人中心模块（/profile）
│   ├── trpg/                  ← 跑团模块（/trpg）
│   ├── alarms/                ← 闹钟模块（/alarms）
│   ├── activities/            ← 活动归档模块（/activities）
│   ├── live/                  ← 直播间模块（/live；SRS HTTP-FLV 播放 + /api/live/status 探测 + 观众在场 heartbeat/viewers，登录显示昵称）
│   └── static/                ← 全部模块静态文件（timeline.html/js/css、index.html、profile.html/js、trpg.html/js、guestbook.*、alarms.*、activities*.html/js、forum.*、tools.* 等）
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
