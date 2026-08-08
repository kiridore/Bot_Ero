# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

BotEro（小埃同学）是一个基于 **OneBot v11 协议** 的 QQ 群聊机器人，通过 WebSocket 连接到 OneBot 服务端（NapCat / Lagrange / LLOneBot），事件驱动 + 插件架构。

此外包含 **单进程 FastAPI Web 应用 `webapp`**（注册 6 个功能域模块 `webapp/gallery/`、`webapp/guestbook/`、`webapp/profile/`、`webapp/trpg/`、`webapp/alarms/`、`webapp/activities/` 的 APIRouter + 根路径导航主页），共享 `core/` 层，单一根域 `littlero.tech` 按路径分区，Caddy 全量反代到同一 8765 端口。

## 运行命令

```bash
# 启动机器人主程序
python main.py

# 启动 Web 应用（单进程承载导航主页 + 6 功能分区，默认 8765，Caddy 全量反代）
python -m webapp

# 本地调试：直接按路径访问 http://127.0.0.1:8765/<分区>
#   /          导航主页   /gallery  /guestbook  /profile(/checkin /shop /settings)
#   /trpg(/char/...)  /alarms  /activities
python -m webapp --port 8765
```

- 机器人依赖：`websocket-client`、`requests`、`Pillow`
- Web 应用依赖：见 `webapp/requirements.txt`（fastapi、uvicorn、requests、Pillow、python-multipart）
- 部署参考：`docs/web-apps-deployment.md`
- 本项目无 `pyproject.toml` 或 `setup.py`，无测试框架，无 lint 配置

## 架构

### 事件流

```
OneBot 服务端 ──WebSocket──> main.py
                              ├── echo 消息 → api.Echo.match() 匹配异步 API 响应
                              └── 事件消息 → 每个线程 new Plugin(raw_context)
                                               ├── match(event_type) → bool
                                               └── handle()
```

- `main.py` 中 `on_message` 回调收到事件后，**逐一遍历** `plugin_registry` 中的所有插件类，每个事件在新线程中实例化并执行 `match()` → `handle()`
- 支持三种事件类型：`message`（群聊/私聊消息）、`notice`（通知）、`meta`（心跳/生命周期）

### 核心模块 (`core/`)

| 模块 | 职责 |
|---|---|
| `base.py` | `Plugin` 基类（match/handle 接口 + 常用匹配方法 on_full_match/on_command 等）；`TimedHeartbeatPlugin`（基于 meta 心跳的定时触发，支持 RUN_AT / RUN_WEEKDAYS / RUN_ANNUAL_DATES） |
| `event.py` | `Event` 包装 OneBot 原始事件 dict，提供 user_id / group_id / message / is_group / is_private 等属性 |
| `api.py` | `ApiWrapper` 通过 WebSocket 调用 OneBot API（send_msg / get_image / set_essence_msg 等），使用 echo 机制实现异步请求-响应匹配；`Echo` 类维护一个 deque 队列 |
| `cq.py` | OneBot 消息段构造器：`text()`、`image()`、`at()`、`reply()`、`forward()` 等，返回 dict 格式的消息段 |
| `context.py` | 全局运行时状态：`plugin_registry`（插件类列表）、`script_start_time`、`DEFAULT_GROUP_ID`、路径配置 |
| `database_manager.py` | SQLite 数据访问层（`data.db`），管理打卡、积分、称号、抽奖、商店、闹钟、留言簿等全部持久化 |
| `utils.py` | 工具函数：日期计算、积分操作、图片下载、`register_plugin` 装饰器 |

### 插件系统

所有插件位于 `plugins/` 目录下，`plugins/__init__.py` 通过 `pkgutil.walk_packages` 自动导入所有子模块，触发 `@register_plugin` 装饰器将插件类注册到 `context.plugin_registry`。

**编写新插件的约定：**
1. 继承 `Plugin`（或 `TimedHeartbeatPlugin`）
2. 用 `@register_plugin` 装饰类
3. 实现 `match(self, event_type)` 和 `handle(self)`
4. 通过 `self.bot_event`（`Event` 实例）获取事件信息
5. 通过 `self.api`（`ApiWrapper` 实例）发送消息 / 调用 API
6. 通过 `self.dbmanager`（`DbManager` 实例）访问数据库

**定时任务：** 继承 `TimedHeartbeatPlugin`，设置类属性 `RUN_AT`（"HH:MM"），可选 `RUN_WEEKDAYS` / `RUN_ANNUAL_DATES`，重写 `handle()` 即可。

### Web 应用（单进程 `webapp`，单一 origin 路径分区）

单进程 FastAPI（端口 8765）注册 6 个模块的 APIRouter + 导航主页，单一根域 `littlero.tech` 按路径分区（`/gallery` `/guestbook` `/profile` `/trpg` `/alarms` `/activities`），Caddy 全量反代 8765。共享 `core/` 层：

- 入口 `webapp/app.py`：认证路由 `/api/auth/login` + `/api/auth/me`（**唯一一份**）、导航主页（`/` 与 `/style.css` `/app.js` `/entries.json` `/notices.json` `/quotes.json`，文件在 `webapp/homepage/`）、include 6 个模块 router、mount `/static`（`webapp/static/`）+ `/shared`（`core/web/static/`）
- 每功能域模块含 `app.py`（导出 `router = APIRouter()`，业务/页面路由，不创建 FastAPI 实例、不 mount）；页面路由带分区前缀（如 `/profile/checkin`），API 保持根路径（全局唯一）；静态统一在 `webapp/static/`（25 个文件，文件名全局唯一）
- 认证助手 `get_current_user_id` / `get_optional_user_id` 唯一权威副本在 `core/web/auth_deps.py`，模块一律从该处 import
- 密钥即登录 token（HMAC，`core/auth.py`），全站共享同一 `BOTERO_AUTH_SALT`；单 origin 下登录态 localStorage 同源共享（auth.js 保留根域 cookie 写入兼容旧缓存）
- 配置集中在 `core/config.py`（全部 `BOTERO_*` 环境变量）；数据库统一走 `core.database_manager.DbManager`（共享 SQLite，WAL + busy_timeout=5000）
- **不要**给 uvicorn 加 `--workers`（多 worker 重新引入多进程 SQLite 写竞争）

模块划分（全部位于 `webapp/` 包内）：`webapp/gallery/`（图库瀑布流 + /thumb /media + 打卡数据 API）、`webapp/guestbook/`（留言簿）、`webapp/profile/`（个人主页/打卡/商店/称号/设置 5 域聚合，依赖 `webapp.gallery.repository`）、`webapp/trpg/`（车卡）、`webapp/alarms/`（闹钟）、`webapp/activities/`（活动归档）；导航主页 `webapp/homepage/`（`entries.json` 为唯一入口维护点）。

### LLM 子系统 (`core/llm/`)

分层架构（开发中）：
- `llm.py` — OpenAI 兼容 API 传输层（默认 DeepSeek）
- `conversation_engine.py` — 对话状态机编排
- `prompt_builder.py` — 提示词组装
- `plugin_tools.py` — 插件 → LLM ToolSpec 转换
- `embedder.py` — 嵌入服务（SiliconFlow / BAAI-bge-m3）

## 详细规范文档 (SDD)

所有开发约束的**权威参考**位于 [`specs/`](specs/) 目录。修改任何模块前，请先查阅对应规范：

| 修改范围 | 必读规范 |
|---------|---------|
| 新增/修改插件 | [`specs/plugins.md`](specs/plugins.md) + [`specs/conventions.md`](specs/conventions.md) |
| 数据库变更 | [`specs/database.md`](specs/database.md) |
| 消息发送/接收 | [`specs/onebot-protocol.md`](specs/onebot-protocol.md) |
| LLM 功能 | [`specs/llm-subsystem.md`](specs/llm-subsystem.md) |
| Web 应用 | [`specs/web-gallery.md`](specs/web-gallery.md) |
| 图片生成 | [`specs/image-generation.md`](specs/image-generation.md) |
| 系统架构理解 | [`specs/architecture.md`](specs/architecture.md) |
| 查找已有插件 | [`specs/plugin-catalog.md`](specs/plugin-catalog.md) |
| 规范体系总览 | [`specs/README.md`](specs/README.md) |

**规范体系设计原则：**
- **约束优先** — 每条规则以 `Constraint:` 开头，明确 `MUST` / `MUST NOT`
- **代码示例** — 每个模式都有可工作的代码片段
- **反模式明确** — 列出常见 AI 错误及预防方法
- **同步维护** — 代码变更时**必须在同一 commit 中**更新对应规范

## 关键约定

- **`ApiWrapper.send_msg()` 会自动判断群聊/私聊**：有 `group_id` 发群聊，只有 `user_id` 发私聊，两者都无则 fallback 到 `DEFAULT_GROUP_ID`
- **`ApiWrapper.send_msg()` 会自动在 @提及前注入称号前缀**（`_inject_titles_before_at`），无需插件手动处理
- **打卡周从周一 08:00 到次周一 08:00**（见 `utils.get_monday_to_monday` 的 8 小时偏移）
- **超级用户**定义在 `base.py` 的 `SUPER_USER` 列表；**默认群号**在 `context.py` 的 `DEFAULT_GROUP_ID`
- **菜单文本**统一维护在 `plugins/menu/bot_menu_text.py` 的 `BOT_MENU_TEXT`，不要在其他地方硬编码指令说明
- 插件中 `_command_kind()` 等私有方法用于提取指令参数，`match()` 只做匹配判断，`handle()` 执行业务逻辑
- **Commit 消息使用中文描述**，格式遵循 Conventional Commits（如 `feat(任务): 新增周常任务系统`）
