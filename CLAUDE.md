# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

BotEro（小埃同学）是一个基于 **OneBot v11 协议** 的 QQ 群聊机器人，通过 WebSocket 连接到 OneBot 服务端（NapCat / Lagrange / LLOneBot），事件驱动 + 插件架构。

此外包含一个独立的 **FastAPI Web 应用**（`checkin_gallery/`），提供打卡图片浏览画廊。

## 运行命令

```bash
# 启动机器人主程序
python main.py

# 启动打卡画廊 Web 应用（默认 http://0.0.0.0:8765，局域网可访问）
python -m checkin_gallery

# 自定义端口
python -m checkin_gallery --port 8080 --db /path/to/data.db --images /path/to/record_images
```

- 机器人依赖：`websocket-client`、`requests`、`Pillow`
- Web 应用依赖：见 `checkin_gallery/requirements.txt`（fastapi、uvicorn、requests、Pillow、python-multipart）
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

### Web 应用 (`checkin_gallery/`)

FastAPI 应用，独立于机器人主进程运行：
- `app.py` — FastAPI 实例 + 路由
- `config.py` — 环境变量配置（`BOTERO_DB_PATH`、`BOTERO_IMAGE_ROOT`、`BOTERO_ONEBOT_HTTP` 等）
- `static/` — 前端 HTML/CSS/JS
- `__main__.py` — uvicorn 启动入口
- 通过 OneBot HTTP API 拉取 QQ 昵称；通过 HMAC 签名实现图库登录认证

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
- **菜单文本**统一维护在 `plugins/bot_menu_text.py` 的 `BOT_MENU_TEXT`，不要在其他地方硬编码指令说明
- 插件中 `_command_kind()` 等私有方法用于提取指令参数，`match()` 只做匹配判断，`handle()` 执行业务逻辑
- **Commit 消息使用中文描述**，格式遵循 Conventional Commits（如 `feat(任务): 新增周常任务系统`）
