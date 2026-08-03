# BotEro (小埃同学) 知识库索引

> Last updated: 2026-08-03 (阵营九宫格/属性生成三方式/经验等级派生同步至 specs/kb)
>
> 本文件是总索引，具体内容按主题拆分到 `kb/` 目录和 `specs/` 目录。
> AI 读取流程: KNOWLEDGE_BASE.md → 按需读取链接文档。

---

## 快速入口

| 需要了解 | 阅读 |
|---------|------|
| 项目身份、硬编码常量、所有指令 | [`kb/QUICK_REFERENCE.md`](kb/QUICK_REFERENCE.md) |
| 41 个插件列表、功能包、数据依赖 | [`kb/PLUGIN_CATALOG.md`](kb/PLUGIN_CATALOG.md) |
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
| [`specs/web-gallery.md`](specs/web-gallery.md) | Web 图库架构、API 路由 |
| [`specs/image-generation.md`](specs/image-generation.md) | 图片生成子系统（热度图/档案卡） |
| [`specs/llm-subsystem.md`](specs/llm-subsystem.md) | LLM 子系统（已弃用） |

---

## 目录结构

```
./
├── KNOWLEDGE_BASE.md         ← 本文件（索引）
├── main.py                    ← 启动入口
├── core/                      ← 核心库
│   ├── base.py                ← Plugin/CommandPlugin/TimedHeartbeatPlugin
│   ├── context.py             ← 运行时上下文、SYSTEM_PLUGINS、plugin_key
│   ├── feature_packs.py       ← 功能包定义
│   ├── api.py                 ← API 封装、Echo 机制
│   ├── cq.py                  ← CQ 消息段构造器
│   ├── event.py               ← Event 包装器
│   ├── database_manager.py    ← DbManager
│   ├── db/                    ← 各业务模块数据库管理层
│   ├── character_store.py     ← 角色卡 JSON 存储（server_data/trpg_chars/）
│   ├── user_settings.py       ← 个人设置 JSON 存储（server_data/user_settings/）
│   ├── trpg/                  ← 跑团规则（rules.py）与角色派生计算（character.py）
│   ├── utils.py               ← 工具函数、QUEST_DEFS
│   ├── gen_image/             ← 图片生成（热度图/档案卡）
│   └── logger.py              ← 日志
├── plugins/                   ← 41 个已注册插件
├── kb/                        ← 知识库子文档
│   ├── QUICK_REFERENCE.md
│   ├── PLUGIN_CATALOG.md
│   ├── GAMEPLAY.md
│   ├── CONVENTIONS.md
│   ├── OPERATIONS.md
│   └── DATABASE.md
├── specs/                     ← 规范文档
├── checkin_gallery/           ← Web 图库（独立进程）
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
