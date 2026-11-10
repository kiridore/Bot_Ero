# 跑团记录上网页 — 验收记录

实施分支：`master`；版本 1.62.0；提案 `openspec/changes/2026-11-10-trpg-record-web/`。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 录制落盘 | `python -m pytest test/test_trpg_session.py -q` → 37 passed（含 AC01 段：目录即时创建、`meta.json` 含 `version:2`/`group_id`/`group_name`/`start` 且 `end` 为 null、逐条追加 `messages.jsonl` 且字段齐全、参与者随首次发言同步） | 通过 |
| AC02 图片入档与失败路径 | 同文件 AC02 段：注入假 `get_image_url` 与假下载后 `imgs/img_0001.jpg` 落盘、分段记 `imgs/img_0001.jpg`；URL 失败/下载异常两种降级都写 `unavailable: true` 且后续消息照常入档 | 通过 |
| AC03 机器人消息与群名 | 同文件 AC03/AC10 段：骰子结果与 `.dm` 提示以 `sender_type: "bot"` 入档；`.rh` 结果带 `secret: true`、群内只留「悄悄掷出骰子」；群名成功写入、取不到为空串且录制不中断 | 通过 |
| AC04 结束与导出 | 同文件 AC04 段：结束写 `meta.end`；`record.md` 由 `messages.jsonl` 生成（DM 前缀、图片引用、@ 提及齐全）；导出回执含 `查看：<WEB_BASE_URL>/trpg/records/<群号>/<目录>` | 通过 |
| AC05 列表 API | `python test/scripts/check_trpg_records_api.py`（47 项断言全过）：按开始时间倒序、三种状态、4 类坏目录跳过、`message_count` 不含坏行、`last_message_at`、`mine=1` 过滤 | 通过 |
| AC06 详情 API 与增量 | 同一脚本：详情 meta、`total` 口径、`from` 增量与越界、半写坏行跳过、图片段转 `url`、404（不存在）/400（非法群号或目录名） | 通过 |
| AC07 媒体与鉴权 | 同一脚本：正常图片 200 + `image/jpeg`；未登录媒体 401（不是 302）；`../`、绝对路径、非图片名、非法群号/目录名一律 400 | 通过 |
| AC08 页面渲染 | `node test/test_trpg_records_dom.js`（34 项断言全过）：`is-self` 靠右、他人靠左带头像、DM/观察者徽标、`is-bot`、图片 `img.trpg-img` 与 lightbox、页签高亮、导航最长前缀匹配 | 通过 |
| AC10 暗骰隐藏与开关 | API 侧 `reveal` 默认过滤且仍计入 `total`、`reveal=1` 返回并带 `secret`；DOM 侧默认不渲染、开关打开后渲染 5 条且带 `is-secret` 与「暗骰」徽标、关闭后重新隐藏 | 通过 |
| AC09 文档、版本与归档 | `python -m pytest -q` → **534 passed**（4:15）；`openspec validate trpg-session-recording --strict` 与 `trpg-record-web --strict` 均 valid；`CHANGELOG.md` 顶部 `[1.62.0]` 与 `BOTERO_VERSION = "1.62.0"` 一致；`specs/web-gallery.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 已同步；归档与实现同一 commit | 通过 |

## 实测与裁定

- **群名获取改走 HTTP 短超时**：实施初版用 `self.api.call_api("get_group_info")`，而 `core/api.py::call_api` 是 `q.get(timeout=30)`——后端不响应就干等 30 秒。实测同一测试文件从 **240.00s（35 用例）** 降到 **1.18s（37 用例）**。改为 `core/onebot_client.resolve_group_name()`（复用已有 HTTP 通道，超时 3 秒），测试在 `IsolationMixin` 里默认桩掉。
- **OneBot HTTP 不再跟随进程级代理**：本机设了 `HTTP_PROXY` 时，对 `127.0.0.1:<port>` 的请求会被代理劫走返回 502 / 等 2 秒连接失败。`core/onebot_client._call_onebot` 改用 `requests.Session()` 且 `trust_env = False`。影响面：昵称/头像解析同样受益（这是既有缺陷，不是本功能引入）。已在 CHANGELOG「内部」条目说明。
- **回执顺序**：录制开始时先发「跑团记录已开始」再取群名，取到后重写 `meta.json`；群名只影响展示，不让 OneBot 的响应速度阻塞回执。
- **导出格式**：`record.md` 由结构化数据生成，正文格式与旧版一致；参与人列表不再把 DM 标记重复写两遍（旧版输出 `[DM] 张三 (123) [DM]`）。
- **未改动**：`plugins/menu/bot_menu_text.py`（无新增/改名指令）；`test/test_trpg.py`、`test/test_trpg_finalize.py`（规则计算未变）。
- **未验证**：没有在真实 QQ 环境跑过一场团（本机无 OneBot 连接），录制行为均由注入假事件的进程内测试覆盖；网页只在 DOM stub 层验证，未做浏览器实测。

## 实施方式

四条串行子代理泳道（数据层 → 插件 → Web → 测试，模型 `commandcode/deepseek/deepseek-v4.1-flash`），子代理不提交，主会话统一复核、补文档、跑全量回归并归档。
