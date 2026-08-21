# AGENTS.md

BotEro（小埃同学）= **QQ 群聊机器人**（OneBot v11 over WebSocket，事件驱动 + 插件架构，纯同步多线程）+ **单进程 FastAPI 社区站 `webapp`**（11 个功能模块，单一根域按路径分区，全站登录门控）。本文件是 AI 代理的第一入口：先读完本文件，再按需查阅下面的文档地图。

## 文档地图（按此顺序/需查阅）

| 需要什么 | 去哪 |
|---------|------|
| 项目概述、运行命令、架构总览 | [CLAUDE.md](CLAUDE.md) |
| 知识库总索引 → 主题子文档 | [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md) → `kb/` |
| 项目身份、硬编码常量、完整指令表 | [`kb/QUICK_REFERENCE.md`](kb/QUICK_REFERENCE.md) |
| 47 个插件注册表、功能包、数据依赖 | [`kb/PLUGIN_CATALOG.md`](kb/PLUGIN_CATALOG.md) / [`specs/plugin-catalog.md`](specs/plugin-catalog.md) |
| 打卡/经济/称号玩法数值（概率、价格、条件） | [`kb/GAMEPLAY.md`](kb/GAMEPLAY.md) |
| 数据库全部 44 张表 Schema | [`kb/DATABASE.md`](kb/DATABASE.md) / [`specs/database.md`](specs/database.md) |
| API 速查、部署运维、外部 API | [`kb/OPERATIONS.md`](kb/OPERATIONS.md) |
| 开发陷阱、AI 检查清单、技术债 | [`kb/CONVENTIONS.md`](kb/CONVENTIONS.md) |
| 编码约定（权威约束 Constraint:） | [`specs/conventions.md`](specs/conventions.md) |
| 系统架构与事件流 | [`specs/architecture.md`](specs/architecture.md) |
| Web 应用架构、API 路由、登录门控 | [`specs/web-gallery.md`](specs/web-gallery.md) |
| 时间线事件协议 | [`specs/timeline-protocol.md`](specs/timeline-protocol.md) |
| 用户可见变更历史 / 计划 | [CHANGELOG.md](CHANGELOG.md) / [roadmap.md](roadmap.md) |
| VPS 部署 | [docs/web-apps-deployment.md](docs/web-apps-deployment.md) |

## Toolchain reality

- **No build system:** 无 `pyproject.toml`/`setup.py`。两个入口：`python main.py`（bot）、`python -m webapp`（Web，默认 8765 端口）。依赖装根目录 `requirements.txt`（webapp 子集在 `webapp/requirements.txt`）。
- **No test framework, lint, or formatter.** `test/` 是 ad-hoc 脚本：Python 的用 `python test/<name>.py`（临时 DB 隔离须启动前注入 `BOTERO_DB_PATH=...` 环境变量），前端渲染测试是 `node test/test_*_render.js`（最小 DOM stub）。
- `pyrightconfig.json` 被 gitignore——不要在 CI/自动化中依赖它。
- 环境变量单一来源 `scripts/botero.env`：`main.py` 启动时 `os.environ.setdefault` 注入（必须在 import core 之前）；webapp 生产经 systemd `EnvironmentFile` 读同一文件。约 30 个 `BOTERO_*` 变量集中在 `core/config.py`。
- **Git hooks:** clone 后执行 `git config core.hooksPath .githooks` 启用 Conventional Commits 校验（commit-msg 钩子对 >12 个文件的暂存输出分块提示，警告不阻断）。
- **Commit 消息 MUST 中文** + Conventional Commits（如 `feat(任务): 新增周常全清称号`）。
- **Commits MUST 按逻辑分块**：一个 commit = 一个逻辑变更；同一逻辑变更的配套文件（代码 + 行为测试 + spec + 菜单文本 + CHANGELOG + KNOWLEDGE_BASE）进**同一个** commit，无关改动拆开（`specs/conventions.md` §Commit 提交分块）。

## Plugin auto-import magic

在 `plugins/<name>/` 建包（或裸 `.py` 文件）即完成注册——`plugins/__init__.py` 用 `pkgutil.walk_packages` 导入全部子模块，触发 `@register_plugin`（装饰器在 `core/utils.py:113`）。无需手动接线。每个插件文件夹 `__init__.py` 内放 `@register_plugin` 类。

## Two path constants — one data

| 常量 | 值 | 用途 |
|------|-----|------|
| `context.llonebot_data_path` | `/app/llonebot/server_data` | OneBot API 调用（bot 进程看到的路径） |
| `context.python_data_path` | `./server_data` | Python 文件 I/O |

**用错是静默失败**——API 调用只返回空/失败，不报错。

## Week boundary is 08:00, not 00:00

一律用 `core.utils.get_monday_to_monday()`。"一周" = 周一 08:00 → 次周一 08:00。同样适用于 `day_of_year()`、连续打卡计算、热力图逻辑。

## Threading model

每个事件起一个新线程，线程内**逐一遍历**插件、每个插件**全新实例**——不要把可变状态存 `self` 期望跨事件保留。`TimedHeartbeatPlugin._last_run_minute` 是类级 dict，跨线程共享是正确的。

**框架层已统一捕获插件异常**（`main.py` `plugin_pool()` 对 `match()`/`handle()` try/except + `logger.exception()`），异常不会静默死线程；插件自己加 try/except 只是为了给用户回友好错误消息。不要画蛇添足地包一层只 log 的 try/except。

## send_msg quirks

- 自动路由：有 `group_id` → 群聊；只有 `user_id` → 私聊；两者皆无 → fallback `DEFAULT_GROUP_ID`。
- 自动在 `@` 提及前注入称号前缀（`_inject_titles_before_at`），不要手动拼称号。

## Web 应用（webapp）要点

- 单进程承载 11 个模块（timeline 主页 `/`、gallery、guestbook、profile、trpg、alarms、activities、live、forum、tools、weekly），每模块 `app.py` 只导出 `router`，不创建 FastAPI 实例；静态合并 `webapp/static/`（文件名全局唯一）+ 共享层 `core/web/static/`（`/shared` 挂载：auth.js/nav.js/motion.css/js/lightbox.js/icons.js/gallery.css/profile.css）。
- **全站登录门控**：`webapp/app.py::login_guard` 中间件，白名单（`/login`、`/api/auth/login`、`/static`、`/shared`、`/api/timeline/events*`）外，页面 302 → `/login?next=…`、API/媒体 401；凭证 `Authorization: Bearer` 头或根域 cookie `botero_key` 任一。
- 认证依赖 `get_current_user_id`/`get_optional_user_id` 唯一权威副本在 `core/web/auth_deps.py`，模块一律从那 import，**禁止各模块复制**。
- 数据库共享 `core.database_manager.DbManager`（WAL + busy_timeout=5000）；**禁止**给 uvicorn 加 `--workers`（多 worker 重引入 SQLite 写竞争）。
- bot 侧推时间线事件用 `core/timeline_client.py` 的 `emit_event`/`retract_event`（best-effort 不阻塞主流程）。

## Hard constraints that agents miss

- **bot 进程禁止 `async`/`await`**（纯同步多线程；webapp/FastAPI 的 middleware/route 用 async 合法，别混风格）。
- **No relative imports** between plugins（已知例外：`menu/__init__.py` 的 `from .bot_menu_text`，不要复制该模式）。
- **No f-string SQL** —— 一律 `?` 参数化查询（DDL 集中在 `core/db/_base.py`，按业务拆 `core/db/<域>.py`）。
- **`match()` MUST NOT have side effects**（不发消息、不写库）。
- **Specs MUST 在同一 commit 更新**（`specs/README.md` 维护规则表）。
- **每次用户可见变更 MUST 同 commit 更新 `CHANGELOG.md` 并 bump `core/config.py::BOTERO_VERSION`**：CHANGELOG 顶部新增 `[x.y.z]` 节，与 `BOTERO_VERSION` 一致（新功能 minor / 修复 patch）。纯文档/测试/内部重构可只记 CHANGELOG `[未发布]` 节不 bump。
- **新增/改名指令 MUST 同 commit 更新 `plugins/menu/bot_menu_text.py`**（指令文本唯一来源，勿在他处硬编码）。
- **动协议代码**（`core/api.py`、`core/event.py`、`core/cq.py` 或任何插件的 OneBot 事件/消息段访问）**MUST 先查权威上游**——见 `specs/onebot-protocol.md` §权威上游文档；LLOneBot 文档索引镜像在 `specs/llms.txt`（编辑前 webfetch 对应单页）。
- LLM 子系统（`core/llm/`）**已弃用**，不要新增依赖。

## Hardcoded values (no config file)

| What | Where | Value |
|------|-------|-------|
| WS URL | `main.py:28` | `ws://127.0.0.1:3001` |
| WS token | `main.py:29` | `123456` |
| Default group | `core/context.py:16` | `296470819` |
| Super user | `core/base.py:12` | `[1057613133]` |
| Bot QQ | `core/base.py:13` | `"3915014383"` |
| Download proxy | `core/utils.py:83-85` | `127.0.0.1:7890` |

（精确 file:line 以 `kb/QUICK_REFERENCE.md` 硬编码常量表为准；路径/盐/端口类配置已 `BOTERO_*` 环境变量化。）

## API behavior

- `call_api()` 阻塞最多 30s，超时返回 `{}`。
- 多数 API 方法失败返回 `0` / `""` / `False` —— 一律检查返回值。
- 私聊消息的 `self.bot_event.group_id` 可能为 `None` —— 使用前判空。

## Knowledge base maintenance

[KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md) 是总索引，具体内容拆在 `kb/`（QUICK_REFERENCE / PLUGIN_CATALOG / GAMEPLAY / CONVENTIONS / OPERATIONS / DATABASE）与 `specs/`。

**MUST：代码变更同一 commit 更新对应文档**——新增/删除插件或指令 → `kb/PLUGIN_CATALOG.md` + `kb/QUICK_REFERENCE.md` + `specs/plugin-catalog.md` + `plugins/menu/bot_menu_text.py`；表/列变更 → `kb/DATABASE.md` + `specs/database.md`；经济数值（抽奖概率、商店价格、积分奖励）→ `kb/GAMEPLAY.md`；称号系统（TITLE_DEFS、条件称号、解锁规则）→ `kb/GAMEPLAY.md`；硬编码常量/路径/API 行为 → `kb/QUICK_REFERENCE.md`；里程碑交付 → `roadmap.md`。
