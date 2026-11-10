# 设计：跑团记录上网页

## 1. 已确认决策

| 编号 | 决策 | 来源 |
|---|---|---|
| D1 | 所有登录用户可查看全部记录 | 所有者 Q1:B |
| D2 | 不支持旧格式记录，列表只列新格式目录 | 所有者 Q2 |
| D3 | 独立页 `/trpg/records` 与 `/trpg/records/<群号>/<目录>`，`/trpg` 页内页签作为入口 | 所有者 Q3:A+B |
| D4 | 录制中实时可看（录制即落盘） | 所有者 Q4:C |
| D5 | 气泡展示时间戳、DM/观察者标记、角色名（昵称）、自己靠右、机器人消息区分、图片气泡+lightbox | 所有者 Q5 |
| D6 | 导出成功消息附网页链接 | 所有者 Q6:A |
| D7 | 录制中图片实时下载到记录目录 | 所有者 Q8:A |
| D8 | 录制中详情页每 5 秒增量轮询 | 所有者 Q9:A |
| D9 | 崩溃残留目录照常列出，标「录制中（可能已中断）」 | 所有者 Q10:A |
| D10 | 列表默认全部，顶部提供「只看我参加的」开关 | 所有者 Q11:A |
| D11 | 录制开始时取群名写入 `meta.json`，失败回退群号 | 所有者 Q12:A |
| D12 | 开发流程文档缺口先单独提交修正 | 所有者 Q7:A（已完成 commit f4b4f70） |
| D13 | 暗骰结果入档，网页默认不显示，详情页提供「显示暗骰」开关 | 所有者 2026-11-10 追加 |

## 2. 数据格式

### 2.1 目录布局

```
<python_data_path>/trpg_records/
└── <群号>/
    └── <YYYY-MM-DD_HH-MM-SS>/          # 录制开始时间
        ├── meta.json
        ├── messages.jsonl
        ├── imgs/
        │   └── img_0001.jpg
        └── record.md                    # 导出后才出现
```

`<python_data_path>` 取 `core.config.PYTHON_DATA_PATH`（默认 `./server_data`，按进程 CWD 解析）。bot 与 webapp 必须同 CWD 启动。

### 2.2 `meta.json`

```json
{
  "version": 2,
  "group_id": 123456789,
  "group_name": "夜航团",
  "start": "2026-11-10 20:00:00",
  "end": null,
  "roles": { "123456": "dm", "234567": "ob" },
  "participants": [
    { "user_id": "123456", "nickname": "老张", "char_name": "艾拉", "role": "dm" }
  ]
}
```

- 录制开始时写入（`end` 为 `null`，`participants` 为空数组）。
- 新参与者首次发言、`.dm`/`.ob` 设置时整体重写（tmp 文件 + `os.replace` 原子替换）。
- 录制结束时重写并写入 `end`。
- `char_name` 取该用户当前角色卡名（`core.character_store.get_current`），无卡为空串。
- 机器人首次发言时以其 QQ 与昵称加入 `participants`。

### 2.3 `messages.jsonl`

每行一个 JSON 对象，追加写入：

```json
{"time": 1762776000, "sender_type": "user", "user_id": "123456", "nickname": "老张", "char_name": "艾拉", "role": "dm", "segments": [{"type": "text", "text": "我推开酒馆的门"}]}
{"time": 1762776031, "sender_type": "bot", "user_id": "3915014383", "nickname": "小埃", "char_name": "", "role": "", "segments": [{"type": "text", "text": "老张的感知检定: D20=13=13"}]}
{"time": 1762776040, "sender_type": "bot", "user_id": "3915014383", "nickname": "小埃", "char_name": "", "role": "", "secret": true, "segments": [{"type": "text", "text": "暗骰：老张的D20=7=7"}]}
{"time": 1762776050, "sender_type": "user", "user_id": "234567", "nickname": "小王", "char_name": "", "role": "", "segments": [{"type": "image", "local": "imgs/img_0001.jpg"}]}
{"time": 1762776060, "sender_type": "user", "user_id": "234567", "nickname": "小王", "char_name": "", "role": "", "segments": [{"type": "at", "qq": "123456"}, {"type": "text", "text": "你看这里"}]}
```

行级可选字段：`secret`（缺省不写，视为 `false`）。暗骰结果写入时置 `true`，网页默认过滤不展示。

分段类型收敛为四种，其余 OneBot 段类型统一落为 `{"type": "other"}`（渲染时显示占位）：

| 段 | 字段 | 说明 |
|---|---|---|
| `text` | `text` | 纯文本 |
| `image` | `local` | 相对记录目录的图片路径；下载失败时为 `"unavailable": true` 且无 `local` |
| `at` | `qq` | 提及的 QQ 号 |
| `other` | — | 其它类型（表情、语音、回复等） |

## 3. 状态判定

状态不额外存字段，由文件推断（每次列表/详情请求时计算）：

| 状态 | 判定 | 页面表现 |
|---|---|---|
| `recording` | `meta.end` 为 `null` | 徽标「录制中」，详情页每 5 秒增量轮询 |
| `ended` | `meta.end` 有值且 `record.md` 不存在 | 徽标「已结束·未导出」 |
| `exported` | `record.md` 存在 | 徽标「已导出」 |

崩溃残留（进程退出但 `end` 未写入）无法与真实录制区分，一律按 `recording` 处理；详情页在最新一条消息时间距今超过 10 分钟时，在徽标后追加「（可能已中断）」——纯展示提示，不改数据、不自动结束。

## 4. 并发与半写

- **写入方**：bot 进程。`messages.jsonl` 追加在 `runtime_context.recording_lock` 内完成，一次 `write` 写完整行再 `flush`，保证行不与其他线程交错。
- **读取方**：webapp 进程，只读。逐行解析，`json.loads` 失败或字段缺失的行跳过（半写的最后一行即此情形）。
- **`meta.json`**：整体重写用 `<name>.tmp` + `os.replace`，读者不会读到半个 JSON；若仍读失败（文件被替换瞬间），该记录在列表中跳过并在日志记一条 warning。
- **不引入跨进程锁**：写入方唯一，读取方只读，冲突面只有半写行，已按行跳过。

## 5. 路径常量与校验（`core/trpg/records.py`）

```python
records_root() -> Path                       # PYTHON_DATA_PATH / "trpg_records"
group_dir(group_id) -> Path                  # 仅接受纯数字字符串
record_dir(group_id, start_dir) -> Path      # start_dir 需匹配 ^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$
media_file(group_id, start_dir, name) -> Path# name 需匹配 ^img_\d{4}\.(jpg|jpeg|png|gif|webp)$（忽略大小写）
start_dir_name(dt) -> str                    # strftime 包装，写入与校验共用同一格式
```

三个校验函数对非法输入抛 `ValueError`；路由层转 400，插件层不应出现（群号来自事件）。**禁止**在路由里用 `Path(请求参数)` 直接拼路径后返回文件——一律经 `record_dir` / `media_file` 校验，杜绝目录穿越。

## 6. API 契约（`webapp/trpg/app.py` 扩展）

复用现有 `get_current_user_id` 鉴权依赖，全部走全站登录门控。

### 6.1 `GET /api/trpg/records?mine=1`

```json
{
  "records": [
    {
      "group_id": "123456789",
      "group_name": "夜航团",
      "start": "2026-11-10 20:00:00",
      "start_dir": "2026-11-10_20-00-00",
      "end": "2026-11-10 23:10:00",
      "state": "exported",
      "message_count": 128,
      "last_message_at": 1762776031,
      "is_mine": true,
      "participants": [
        { "user_id": "123456", "nickname": "老张", "char_name": "艾拉", "role": "dm" }
      ]
    }
  ]
}
```

- 遍历 `records_root()/*/*/`，跳过非法目录名、缺 `meta.json`、`version != 2`、缺 `messages.jsonl` 的目录。
- 按 `start` 倒序。
- `is_mine`：当前登录用户在 `participants` 中；`mine=1` 时只返回 `is_mine` 为真的条目。
- `message_count`：逐行计数非空行（记录规模小，直接读；见 `shortcut:` 注释：记录数过千时改为把计数写进 `meta.json`）。

### 6.2 `GET /api/trpg/records/{group_id}/{start_dir}?from=<n>&reveal=<0|1>`

```json
{
  "group_id": "123456789", "group_name": "夜航团",
  "start": "...", "end": null, "state": "recording",
  "participants": [ ... ],
  "total": 128, "from": 100,
  "messages": [ { ...同 jsonl 行，图片段追加 url 字段... } ]
}
```

- `from` 缺省为 0；返回第 `from` 条（0 基）起的全部消息。
- `reveal` 缺省为 0：`secret` 为 `true` 的消息不包含在 `messages` 中，但仍计入 `total`（索引口径稳定，增量不会错位）；`reveal=1` 时一并返回并各自带 `secret: true`。
- 图片段由服务端把 `local` 转为 `url`：`/trpg/media/<群号>/<目录>/<文件名>`。
- 记录或 `messages.jsonl` 不存在 → 404；群号/目录名非法 → 400。

### 6.3 `GET /trpg/media/{group_id}/{start_dir}/{filename}`

`FileResponse`，媒体类型按扩展名。校验失败 400，文件不存在 404。

**门控**：`webapp/app.py::_UNAUTHORIZED_PREFIXES` 增加 `"/trpg/media/"`，未登录返回 401 而不是 302 重定向（否则 `<img>` 会把登录页 HTML 当图片渲染）。

## 7. 前端

### 7.1 页面文件

| 文件 | 职责 |
|---|---|
| `webapp/static/trpg_records.html` + `trpg_records.js` | 列表页 `/trpg/records`：筛选开关、记录卡片、状态徽标 |
| `webapp/static/trpg_record.html` + `trpg_record.js` | 详情页：气泡渲染、录制中增量轮询、图片 lightbox |
| `webapp/static/trpg.css` | 追加页签条与气泡样式（沿用 `:root` token，不新增硬编码颜色） |
| `webapp/static/trpg.html` | 顶部加页签条：车卡 / 跑团记录 |

两个新页面沿用现有页面骨架：`theme.js` → `base.css`/`motion.css`/`profile.css` → `trpg.css`，脚本 `auth.js`/`motion.js`/`nav.js` + 页内脚本，`motion.js` 负责滚动揭示。

### 7.2 气泡渲染规则

| 情形 | 渲染 |
|---|---|
| 自己（`user_id` == 登录用户） | `is-self`，靠右，气泡用强调底色 |
| 他人 | 靠左，左侧头像（`/api/auth/me` 同源的昵称头像解析规则；解析失败降级首字母） |
| 名字行 | `角色名（昵称）`；无角色卡时只显示昵称 |
| 角色徽标 | `role == "dm"` → DM；`"ob"` → 观察者 |
| 机器人 | `is-bot`，居中窄条，无头像 |
| 时间戳 | 每条显示 `HH:MM:SS` |
| 图片段 | `<img loading="lazy">`，点击调 `window.BoteroLightbox.open(url)`（沿用 `/shared/lightbox.js` 现有入口） |
| `unavailable` 图片 | 灰底占位「图片获取失败」 |
| 暗骰消息（`secret: true`） | 默认不渲染；打开「显示暗骰」后以虚线边框窄条插入对应时间位置，与普通机器人消息可区分 |
| `other` 段 | 占位「[暂不支持的附件]」 |
| `at` 段 | 渲染为「@昵称」文本 |

同一分钟内连续同一发送者的消息**不做合并**（保持与 QQ 时间线一致、实现简单）。

### 7.3 增量轮询

- 详情页打开且 `state == "recording"` 时，`setInterval` 每 5 秒请求 `?from=<已渲染条数>`；`state` 非 `recording` 或页面隐藏（`document.hidden`）时停止/暂停。
- 新消息追加到列表尾部；若请求前滚动条位于底部则追加后自动滚到底，否则不移动视口。

### 7.4 导航入口
- `core/web/static/nav.js`：`NAV_ITEMS` 增加 `{ label: "跑团记录", path: "/trpg/records" }`；同时把高亮判定从 `current.startsWith(it.path)` 改为**最长前缀匹配**，否则 `/trpg/records` 会同时点亮「跑团」与「跑团记录」。
- `webapp/timeline/entries.json`：新增一张卡片 `{ "name": "跑团记录", "desc": "跑团过程与聊天记录回顾", "url": "/trpg/records" }`。

### 7.5 暗骰开关

- 详情页顶部工具条提供「显示暗骰」开关，默认关闭。
- 关闭时请求不带 `reveal`（服务端不返回 `secret` 消息）；打开时整页重新从 `from=0` 拉取 `reveal=1` 并重建消息列表（记录规模小，重新拉取比维护两套游标简单）。
- 开关状态只保存在页面内存，不写 localStorage、不走服务端。

## 8. 失败路径

| 场景 | 行为 |
|---|---|
| `get_group_info` 超时/失败 | `group_name` 写空串，录制照常；网页显示群号 |
| 图片下载失败 | 该段 `unavailable: true`，消息照常入档，导出时写 `[图片: <原始文件标识>]` |
| `meta.json` 重写失败（磁盘满、权限） | 记 `logger.exception`，录制继续（消息行已写入）；网页侧该记录可能缺 `end`，表现为「录制中」 |
| `messages.jsonl` 追加失败 | 记 `logger.exception` 并在群内回一条「记录写入失败」，录制继续，不静默丢失 |
| 读取时半写行 | 跳过该行，其余正常返回 |
| 记录目录被手工删除 | 列表自动不显示；详情页 404 |
| 记录内 `record.md` 存在但 `messages.jsonl` 缺失 | 列表跳过（不属于新格式） |

## 9. 影响面（必须一并处理的调用方）

| 位置 | 改动 |
|---|---|
| `plugins/trpg_session/__init__.py` | 移除 `TRPG_RECORDS_ROOT` 常量，改用 `core.trpg.records`；开始/强制开始/结束/导出改为经记录模块落盘；`_handle_list`/`_handle_view` 改读新路径；导出消息加网页链接 |
| `plugins/trpg_dice/__init__.py` | 录制期间把群内输出交给 `core.context.record_bot_message`（新增）入档；暗骰私聊不调用 |
| `plugins/trpg_char/__init__.py` | 不变（`.dm`/`.ob` 在 `trpg_session` 内处理，其提示由 `trpg_session` 入档） |
| `core/context.py` | 录制会话增加 `dir` 与 `record_bot_message()` 辅助函数 |
| `core/trpg/records.py`（新增） | 路径、校验、追加与重写函数 |
| `webapp/trpg/app.py` | 三个 API + 两个页面路由 |
| `webapp/app.py` | `_UNAUTHORIZED_PREFIXES` 加 `/trpg/media/` |
| `core/web/static/nav.js` | 新增导航项 + 高亮最长前缀匹配 |
| `webapp/timeline/entries.json` | 新增入口卡片 |
| `test/test_trpg_session.py` | 落盘、图片、机器人消息、群名、结束/导出用例；`TRPG_RECORDS_ROOT` patch 改为指向临时数据目录 |
| `test/test_trpg.py`、`test/test_trpg_finalize.py` | 确认未受影响（不改规则计算） |

## 10. 测试清单

| 层 | 文件 | 覆盖 |
|---|---|---|
| bot 进程内 | `test/test_trpg_session.py`（扩展） | AC01–AC04：目录与 meta 结构、逐条追加、参与者同步、图片成功/失败、机器人消息、群名成功/失败、结束写 end、导出 md 与链接 |
| webapp 独立进程 | `test/scripts/check_trpg_records_api.py`（新增，`_env.write_config` 把 `bot.python_data_path` 指向临时目录） | AC05–AC07、AC10：列表排序与状态、`mine=1` 过滤、坏目录跳过、详情与 `from` 增量、`reveal` 过滤、坏行跳过、404/400、媒体正常与穿越拒绝、未登录 401 |
| 前端 DOM | `test/test_trpg_records_dom.js`（新增） | AC08、AC10：自己/他人/机器人气泡类名与位置、徽标、图片段、页签高亮、暗骰默认隐藏与开关后显示 |
| 全量 | `python -m pytest -q` | AC09：回归全绿 + `openspec validate --strict` |

## 11. 版本

新功能 minor：`BOTERO_VERSION` 1.61.0 → **1.62.0**，CHANGELOG 新增 `[1.62.0]` 节（`[未发布]` 中他人未发布条目保持原样）。
