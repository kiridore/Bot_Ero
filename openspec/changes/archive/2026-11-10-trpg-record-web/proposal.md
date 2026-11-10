# 跑团记录上网页：按团浏览与聊天气泡回顾

## Why

所有者指令（2026-11-10）：「下一步开发记录上 web，能在 web 上查询自己参加的团，以类似聊天对话气泡的形式展示跑团过程。」

现状核实（读源码确认，非推测）：

- 录制中的消息只存在 bot 进程内存 `core/context.py::recording_sessions`，进程退出即丢失；
- 导出的记录只落 `server_data/trpg_records/<群号>/<开始时间>/` 下的 `meta.json`（开始/结束时间 + 参与人）与 `record.md`（Markdown 纯文本），**没有任何结构化消息数据**，网页端也没有任何入口——`webapp/` 现有 12 个模块全部读 SQLite，没有一个读 `server_data` 下的 bot 产物；
- 机器人自己在录制期间发出的骰子结果**完全不进记录**：`_record_user_message` 显式跳过 `BOT_QQ`，插件也只匹配 `message` 事件，因此现有记录里看不到任何掷骰过程；
- 网页端因此无法回答「我参加过哪些团」，也无法回顾过程。

## What Changes

### 1. 录制持久化（bot 侧）

- 录制开始即创建 `server_data/trpg_records/<群号>/<YYYY-MM-DD_HH-MM-SS>/`，写 `meta.json`；此后每条消息追加一行到 `messages.jsonl`（结构化：时间、发送方类型、QQ、昵称、角色名、DM/观察者角色、分段列表）。
- 录制开始时调用一次 `get_group_info` 取群名写入 `meta.json`；调用失败或超时留空，网页回退显示群号。
- 录制期间收到的图片立即下载到 `imgs/img_NNNN.ext`，`messages.jsonl` 同段记录相对路径；下载失败标记该段不可用，不阻断录制、不影响后续消息。
- 录制结束在 `meta.json` 写入 `end`；导出仍生成 `record.md`（文本格式保持不变），但改为**从 `messages.jsonl` 生成**，避免两份数据源分叉。

### 2. 机器人消息入档（bot 侧）

- 录制期间机器人自己发出的消息（骰子结果、DM/观察者设置提示）以 `sender_type: "bot"` 写入 `messages.jsonl`，网页以居中窄条样式展示。
- 暗骰（`.rh`）的结果同样入档，但标记 `secret: true`；网页默认不显示，详情页提供「显示暗骰」开关，打开后才渲染这些消息。

### 3. 网页浏览（webapp）

- 新增记录列表页 `/trpg/records`：全部记录按开始时间倒序，展示群名、开始时间、时长、消息条数、参与人、状态徽标；顶部「只看我参加的」开关（默认关闭，即显示全部）。
- 新增记录详情页 `/trpg/records/<群号>/<开始时间目录>`，聊天气泡渲染：自己的消息靠右、他人靠左带头像；名字显示「角色名（昵称）」；DM / 观察者徽标；每条显示时间；机器人消息居中窄条；图片消息渲染为图片气泡，点击打开全站 lightbox。
- 录制中的记录详情页每 5 秒增量拉取新消息并在底部追加；打开页面时若已滚到底部则自动跟随，用户上滑查看历史时不被强制拉回。
- 详情页顶部提供「显示暗骰」开关（默认关闭）：关闭时暗骰消息不出现在页面，打开后这些消息以区别于普通机器人消息的样式插入对应位置。
- `/trpg` 页面顶部新增页签「车卡 / 跑团记录」，两个页面共用同一条页签；顶部导航条 `core/web/static/nav.js` 与主页导航网格 `webapp/timeline/entries.json` 各新增一个「跑团记录」入口。
- 新增鉴权媒体路由提供记录图片，该前缀加入未登录返回 401 的列表（避免 `<img>` 收到 302 登录页把 HTML 当图片渲染）。
- 导出成功的群消息追加一行「查看：<web 地址>/trpg/records/<群号>/<目录>」，地址取 `core/config.py::WEB_BASE_URL`。

### 4. 路径常量统一

- 记录根路径从插件内硬编码相对常量 `TRPG_RECORDS_ROOT = "server_data/trpg_records"` 上移到 `core/trpg/records.py`，用 `core.config.PYTHON_DATA_PATH` 拼出；插件与 webapp 共用同一份实现，并集中提供群号、开始时间目录名、媒体文件名的合法性校验。

### 5. 文档与版本

- `specs/web-gallery.md` 更新模块表与路径分区；`kb/PLUGIN_CATALOG.md` 与 `specs/plugin-catalog.md` 更新 `trpg_session` 描述；`CHANGELOG.md` 新增 `[1.62.0]` 节并 bump `core/config.py::BOTERO_VERSION` 至 1.62.0。
- 无新增/改名 QQ 指令，`plugins/menu/bot_menu_text.py` 不需要改动（导出行文案变化不属于指令表）。

## Capabilities

### New Capabilities

- `trpg-session-recording`：录制期间的结构化落盘（目录布局、`meta.json` v2、`messages.jsonl`、`imgs/`）、机器人消息与群名入档、三种状态判定、崩溃残留处理、`record.md` 由结构化数据生成。
- `trpg-record-web`：记录列表与详情页、气泡渲染规则、录制中增量轮询、鉴权媒体路由、导航入口、可见性规则。

### Modified Capabilities

- 无（跑团此前没有任何 OpenSpec 规范文件，本变更不修改既有规范）。

## Scope and Compatibility

- **不支持旧格式记录**：所有者确认生产环境没有旧格式记录。列表只展示同时含 `meta.json`（`version: 2`）与 `messages.jsonl` 的目录；旧目录既不显示也不迁移。
- **可见性**：所有登录用户可查看全部记录（所有者选择）。不按群成员关系或参与关系限制；参与关系只用于「只看我参加的」筛选。
- **社区版与私有版一致**：本功能无版本差异，两版共用同一实现与同一套页面，不引入任何 edition 分支或开关。
- **不做的**：网页端结束或导出录制、编辑/删除记录、记录分享外链、跨群搜索与全文检索、为崩溃残留记录提供补导出入口。
- **部署影响**：无数据库变更、无新指令、无新增第三方依赖；新增的是 `server_data/trpg_records` 下的文件读写。录制期间图片实时下载，磁盘占用与现有导出规模相当。
- **文案变化**：导出成功消息新增一行网页链接，同步更新 `test/test_trpg_session.py` 相关断言。
- 运行两个进程的工作目录必须一致（bot 与 webapp 都从项目根启动，与 `core/config.py` 现有相对路径约定一致）；Docker 单容器双进程满足该前提。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 录制落盘 | `python -m pytest test/test_trpg_session.py -q` | 开始录制后目录立即存在；`meta.json` 含 `version: 2`、`group_id`、`group_name`、`start`，`end` 为 `null`；每条群消息使 `messages.jsonl` 增加一行，字段含 `time`/`sender_type`/`user_id`/`nickname`/`char_name`/`role`/`segments`；新参与者首次发言后 `meta.json.participants` 同步出现该用户 |
| AC02 图片入档与失败路径 | 同上专项（注入假 `get_image_url` 与假下载） | 图片消息在 `imgs/` 下产生文件，`segments` 记录相对路径 `imgs/img_0001.jpg`；下载失败时该段标记不可用且后续消息仍正常入档 |
| AC03 机器人消息与群名 | 同上专项 | 录制期间 `trpg_dice` 输出的骰子结果与 `.dm`/`.ob` 提示以 `sender_type: "bot"` 入档；暗骰结果入档且带 `secret: true`；`get_group_info` 成功时 `meta.json.group_name` 为群名，失败/超时时为空串且录制不中断 |
| AC04 结束与导出 | 同上专项 | 结束录制后 `meta.json.end` 有值；`record.md` 内容与 `messages.jsonl` 一一对应（时间、角色前缀、图片引用、@ 提及）；导出成功消息包含 `查看：<WEB_BASE_URL>/trpg/records/<群号>/<目录>` |
| AC05 列表 API | `python -m pytest test/test_trpg_records_web.py -q` | `GET /api/trpg/records` 返回按开始时间倒序的数组；状态判定正确（录制中 / 已结束未导出 / 已导出）；`?mine=1` 只返回自己在 `participants` 中的记录；不含 `messages.jsonl` 的目录与非法目录名被跳过且不报错 |
| AC06 详情 API 与增量 | 同上专项 | `GET /api/trpg/records/<群号>/<目录>` 返回 meta 与全部消息；`?from=<n>` 只返回第 n 条起的新消息；`messages.jsonl` 中损坏行（半写）被跳过且不抛异常；不存在的记录返回 404，非法群号/目录名返回 400 |
| AC07 媒体与鉴权 | 同上专项 + `test/scripts/check_login_guard.py` | 正常图片返回 200 与正确 content-type；`../`、绝对路径、非 `img_NNNN.<扩展名>` 文件名一律 400/404；未登录访问媒体返回 401（不是 302） |
| AC08 页面渲染 | `node test/test_trpg_records_dom.js` | 自己消息带 `is-self` 并将右对齐、他人消息靠左带头像；DM/观察者徽标渲染；机器人消息带 `is-bot`；图片消息渲染 `<img>` 且点击调用 lightbox；页签条在 `/trpg` 与 `/trpg/records` 均渲染且当前项高亮 |
| AC10 暗骰隐藏与开关 | `python -m pytest test/test_trpg_records_web.py -q` + `node test/test_trpg_records_dom.js` | 详情 API 默认不返回 `secret` 消息、`reveal=1` 时返回且各自带 `secret` 标记；页面默认不渲染暗骰气泡，「显示暗骰」开关打开后渲染并可与普通机器人消息区分，关闭后重新隐藏 |
| AC09 文档、版本与归档 | `python -m pytest -q`；`openspec validate trpg-record-web --strict`；`openspec validate trpg-session-recording --strict`；`git log -1 --stat` | 全量回归绿；两个能力规范校验通过；`CHANGELOG.md` 顶部新增 `[1.62.0]` 且与 `BOTERO_VERSION` 一致；`specs/web-gallery.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 已同步；归档、规范与实现同一 commit |

## 维护者可持续性

- 结构化数据只有一个写入点（`core/trpg/records.py` 提供的追加/重写函数），`record.md` 由该数据生成，网页与 QQ 端看到的是同一份事实，不再出现「网页与导出内容不一致」。
- 记录目录路径与校验集中在 `core/trpg/records.py`，插件与 webapp 共用，避免两处硬编码相对路径漂移。
- webapp 侧保持现有分层：路由在 `webapp/trpg/app.py`，页面在 `webapp/static/`，样式走 `trpg.css` 与 `:root` token，不引入新框架与新依赖。
- 测试分两层：bot 侧录制行为进 `test/test_trpg_session.py`，webapp 侧 API 与鉴权新建 `test/test_trpg_records_web.py`，渲染新建 `test/test_trpg_records_dom.js`，全部自动纳入统一 `pytest` 回归。
