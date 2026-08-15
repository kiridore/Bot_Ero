# 小埃周报实施计划（2026-08-15）

> 权威设计：`docs/superpowers/specs/2026-08-15-weekly-report-design.md`。

**Goal:** 每周一 08:00 自动出版一期报纸排版的群周报（webapp 展示 + 永久归档 + 群内通知链接），汇总打卡/抽奖/发言/复读/语录/热词/活跃柱状图等群内趣味数据。

**Architecture:** webapp 第 11 个模块 `webapp/weekly/`（2 API + 2 页面）+ `plugins/message_logger/` 系统插件（独立库 `message_log.db` 全群记录）+ `plugins/weekly_report/` TimedHeartbeatPlugin（周一 08:00 聚合两库写 `weekly_reports` + 群通知）。

**Tech Stack:** FastAPI + SQLite (WAL, 双库) + jieba (posseg) + 原生 JS + 现有 newspaper theme tokens + SVG/CSS 前端图表。

## Global Constraints

- 消息日志独立库 `server_data/message_log.db`（路径经 `core.config.MESSAGE_LOG_DB_PATH`，env `BOTERO_MESSAGE_LOG_DB_PATH`），仅记群消息，永久保留；系统插件不受 per-group 启用影响
- 消息日志不落 bot 自身消息（`user_id == BOT_QQ` 跳过）；`reply` 段剥离前提取 `reply_to_msg_id` 落库（供语录“被回复+1”评分）
- 抽奖流水：data.db 新增 `lottery_draw_log`，`plugins/lottery` 每次抽奖后写一行（供周报按周统计欧皇/非酋）
- jieba 懒导入，`ImportError` 降级 `re` 简易方案，热词缺失不阻塞周报
- 周界一律 `start, end = get_monday_to_monday()`；`week_key = start.split(" ")[0]`；生成幂等（week_key 已存在则跳过）+ 启动补偿 + 失败重试
- 生成器 `handle` 必须 try/except + `logger.exception()`（线程内异常静默死亡）
- 打卡群像墙：每人本周首张，排除补卡
- 无新 bot 命令 → `plugins/menu/bot_menu_text.py` 不动
- 提交消息：中文 Conventional Commits；文档与代码同 commit
- **首周测试期**：不实现群通知 + 不加入侧边栏入口，仅保留 `/weekly` 路径供开发者直连调试；群通知由 `core.config.WEEKLY_NOTIFY_ENABLED`（env `BOTERO_WEEKLY_NOTIFY`，默认关闭）控制
- Web 基址统一用 `core.config.WEB_BASE_URL`（env `BOTERO_WEB_BASE_URL`，默认 `https://littlero.tech`）

## 依赖顺序

`T1, T2 → T3 → T4 → T5`；`T6` 与实现同步；`T7` 最后。

## 任务清单

- [ ] **T1：消息日志** `core/db/message_log.py` + `plugins/message_logger/`
  - `core/config.py`：新增 `MESSAGE_LOG_DB_PATH`（env `BOTERO_MESSAGE_LOG_DB_PATH`，默认 `PROJECT_ROOT/server_data/message_log.db`）、`WEB_BASE_URL`（env `BOTERO_WEB_BASE_URL`，默认 `https://littlero.tech`）、`WEEKLY_NOTIFY_ENABLED`（env `BOTERO_WEEKLY_NOTIFY`，默认 `"0"`）
  - `core/db/message_log.py`：独立库连接（`MESSAGE_LOG_DB_PATH`，WAL + busy_timeout，仿 `DbManager`）+ `init_schema` 建 `messages` 表：
    - 列：`id` PK / `group_id` / `user_id` / `msg_id`（UNIQUE）/ `reply_to_msg_id`（可空）/ `sent_at` / `text` / `has_image`
    - 索引：`idx_messages_group_time (group_id, sent_at)`、`idx_messages_text (text)`
    - `insert`（`INSERT OR IGNORE` 防重；`sent_at` 取 `bot_event.time` Unix 秒转 `YYYY-MM-DD HH:MM:SS`，缺失回退 `datetime.now()`）+ `get_week(group_id, start, end)` 查询供生成器
  - `core/context.py`：`SYSTEM_PLUGINS` 追加 `message_logger`
  - `plugins/message_logger/__init__.py`：`Plugin`，match 所有 `message` 事件，仅群消息（`group_id` 非 None）且跳过 bot 自身（`user_id == BOT_QQ`）；文本提取（text 段拼接、图片段置 `has_image`、`@` 段剥离；`reply` 段剥离前取 `data.id` 写入 `reply_to_msg_id`）；`handle` try/except

- [ ] **T2：存储层** `core/db/weekly.py` + 抽奖流水
  - `core/db/_base.py::init_schema` 追加：
    - `weekly_reports` 表（`week_key`+`group_id` 主键 + `data_json` + `created_at`）
    - `lottery_draw_log` 表（`id` PK / `user_id` / `drawn_at` / `result_type` / `value` / `rarity` / `zero_streak_after`）+ `idx_lottery_draw_log_time (drawn_at)`
  - `core/db/weekly.py`：`WeeklyReportManager`（upsert / get / list / issue 推导 = `COUNT(*) WHERE group_id=? AND week_key <= ?`）
  - `core/db/lottery.py`：新增 `insert_draw_log`、`weekly_lucky_from_log`、`weekly_unlucky_from_log` 查询（按周界过滤 `drawn_at`）
  - `plugins/lottery/__init__.py`：`_perform_single_draw` 在结果产出后写 `lottery_draw_log` 一行（含 `result_type`/`value`/`rarity`/`zero_streak_after`）
  - `core/database_manager.py` 挂载 `self.weekly`

- [ ] **T3：生成器** `plugins/weekly_report/__init__.py`（TimedHeartbeatPlugin 周一 08:00）
  - 外壳：
    - `start, end = get_monday_to_monday()`；`week_key = start.split(" ")[0]`；`group_id = core.config.GROUP_ID`
    - 幂等：`weekly_reports` 已有 `(week_key, group_id)` 则跳过
    - 启动补偿：模块级 `_boot_checked` flag，`match` 允许启动后首次 meta 触发（参考 `startup_changelog`），`handle` 先补漏上周再执行定时生成；补漏同样幂等
    - 失败 `logger.exception()` + 下心跳重试；成功后 `api.send_msg` 群通知「第 N 期《小埃周报》已出版 + 链接」（URL 拼 `WEB_BASE_URL/weekly/<week_key>`；meta 事件无 `group_id`，`send_msg` 会 fallback 到 `DEFAULT_GROUP_ID`，默认与 `core.config.GROUP_ID` 一致）；`WEEKLY_NOTIFY_ENABLED` 开关控制，**首周测试期默认关闭，仅写库**
  - **聚合 message_log.db**（`get_week(group_id, start, end)`）：
    - 发言统计：总条数/总字数（period）、每日分布 `daily` 7 项、话痨榜 TOP5（条数 + 群占比）、深夜党（1–5 点）/早起鸟（8–12 点）、峰值时段 `peak`
    - 复读检测：同文本 ≤30 分钟 ≥3 不同用户 → 热梗 TOP3 + 复读王（忽略命令/≤2 字；bot 消息已在 T1 不落库）
    - 语录挑选：排除命令/纯图/@/链接/兑换码、8~80 字；评分（被回复+1 = `reply_to_msg_id` 指向该消息的条数 / 图片+0.5 / emoji+0.5）TOP2 + 随机 2~3；每用户限 1
    - 热词：jieba `posseg.lcut` 词性过滤（保留 n/v/a，滤 u/p/c/d/x/m）+ 补充停用词 + 去重（每用户每日每词 1 次）TOP 30；懒导入 + `ImportError` 降级
  - **聚合 data.db**：打卡（总次数/人数/日均/全勤榜/补卡/群像图=每人首张排除补卡）、抽奖（总抽数/人均/抽卡之王；欧皇/非酋按 `lottery_draw_log` 周界统计——欧皇=本周 `points 10` 或 `title_new` 且 `rarity=legendary`，非酋=本周最长连续零奖励）、仙人彩（开奖/奖池/中奖）、周常全清人数、新解锁称号（`user_titles.unlocked_at` 落周界内）、本周活动、卧底局数（读 `server_data/game_records/<group_id>/*.json` 的 `ended_at` 落周界内）
  - 花絮数据：蝉联榜/涨幅榜（对比历史 `weekly_reports.data_json` 的 TOP1/发言数）、冷知识之最（最长单条/单日最多/最多图片一天/1 分钟连发最多，随机轮换 2~3 条）、刊尾
  - 头条优先级链（仙人彩大奖→活动→传说称号→破纪录→平淡占位）+ 各板块空态 + 副题导读拼装
  - 产出 `data_json`（结构见设计文档），昵称 `resolve_display_name` 落库快照

- [ ] **T4：webapp 模块** `webapp/weekly/`
  - `webapp/weekly/app.py`：
    - 2 API：`GET /api/weekly` 列表按 week_key 倒序；`GET /api/weekly/<week_key>` 详情返回整行 `data_json`；均 `get_current_user_id` 登录，且按 `core.config.GROUP_ID` 过滤
    - 2 页面：`GET /weekly` 重定向到最新期 `/weekly/<week_key>`（无记录 404）；`GET /weekly/<week_key>` 返回 `webapp/static/weekly.html`（页面本身公开，数据走 API）
    - `webapp/weekly/__init__.py`
  - `webapp/app.py` include router（建议放在不会遮蔽已有路由的位置）
  - `webapp/timeline/entries.json` 追加 `{name:"周报",desc:"每周一自动出版的群周报",url:"/weekly"}`（**首周暂不加入**，`/weekly` 保留直连调试；开关/测试期后加入）

- [ ] **T5：前端** `webapp/static/weekly.html/js/css`
  - 报头（刊名/期号/日期区间/超大数字：总条数+总字数/副题导读）+ 5 版渲染 + 页脚期号水印
  - 柱状图 SVG：按 `daily` 渲染 7 柱，峰值柱金色高亮 + 柱顶数字；柱宽弹性自适应容器宽度
  - 词云：按 `voices.words` CSS 流式（字号分级 + TOP3 金色 + 次数角标 + 报纸分隔符 + 少量随机倾斜），词条 `textContent`
  - 打卡群像墙：`checkin.images` 卡片网格（图为主、底部昵称）
  - 归档导航：期号下拉 / 左右翻期；移动端两栏塌单栏 + 群像墙 3→2 列
  - 复用报纸风 token + 动效层；语录/热梗/榜单文本 `escapeHtml()` + `textContent`

- [ ] **T6：文档同步**（同实现 commit 收尾）
  - `CHANGELOG.md` 顶部 `[新版本]` 节 + `core/config.py::BOTERO_VERSION` bump（新功能 minor）
  - `requirements.txt` 增加 `jieba`（bot 侧新依赖）
  - `KNOWLEDGE_BASE.md` + `kb/`（PLUGIN_CATALOG 加两插件并修正插件计数、DATABASE 加三表（`messages`/`weekly_reports`/`lottery_draw_log`）、OPERATIONS 补 jieba 依赖与 `BOTERO_WEB_BASE_URL` 等新 env、QUICK_REFERENCE）
  - `specs/database.md`（`messages` + `weekly_reports` + `lottery_draw_log` 三表）、`specs/web-gallery.md`（第 11 模块 + 路由）、`specs/plugin-catalog.md`（新增插件必须登记：`message_logger`、`weekly_report`）
  - `CLAUDE.md` 模块清单与计数统一为 11 个模块
  - `docs/web-apps-deployment.md`（URL 表加 `/weekly`、模块计数、环境变量表加 `BOTERO_MESSAGE_LOG_DB_PATH`/`BOTERO_WEB_BASE_URL`/`BOTERO_WEEKLY_NOTIFY`）；`scripts/botero.env` 补新 env 注释

- [ ] **T7：验证** 见下方

## 验证清单

```bash
# 消息日志（隔离 DB 起 bot 或手动 match/handle）
- 群发 3 条 → message_log.db 3 行；私聊不出现；bot 自身消息不落库
- 同 msg_id 重复事件 → 不重复入库
- 含图消息 → has_image=1；@/reply 段不进入 text，reply 消息的 reply_to_msg_id 正确落库

# 抽奖流水（隔离 DB 手动触发一次抽奖）
- 每抽 1 次 → lottery_draw_log 新增 1 行；points 10 或 title_new(legendary) 可被周度欧皇查询命中

# 生成（手动触发一次 handle 或等待周一 08:00）
- weekly_reports 出现一行（group_id = core.config.GROUP_ID），data_json 完整（daily 7 项 = Σ 每日条数；period.total_chars = Σ text 长度）
- 首周测试期：群内**不**收到周报通知；将 BOTERO_WEEKLY_NOTIFY=1 后重启再触发 → 群内收到「第 N 期《小埃周报》已出版 + 链接」
- 重复触发 → 幂等跳过，不覆盖
- 删除上周行 → 重启 → 自动补生成

# 语录/复读/热词
- 命令、@、链接、<8 字、>80 字 → 不进语录；被回复消息的“被回复+1”体现在评分中；同文本 30 分钟内 3 人 → 计入复读
- 命令、停用词、单字、纯数字、助词/介词/连词/副词（的/了/在/和/很）→ 不出现于词云；同用户同日重复词只计 1 次
- 模拟 jieba 缺失（ImportError）→ 降级 re 方案，热词仍产出且周报不中断

# webapp（隔离 BOTERO_DB_PATH 起 webapp）
- GET /api/weekly 无 token → 401
- GET /api/weekly → 列表倒序；GET /api/weekly/<week_key> → 详情 data_json
- GET /weekly → 最新期重定向；GET /weekly/<week_key> → 200
- 打卡群像墙：每人 1 张，URL 可访问（/thumb 路由 200），补卡不计入
- 首周测试期：侧边栏**不出现**「周报」入口；entries.json 加入后重启 webapp → 侧边栏出现
- /static/weekly.{html,js,css} → 200
```

实施 commit 需同步：`specs/database.md`、`specs/web-gallery.md`、`specs/plugin-catalog.md`、`CLAUDE.md`、`KNOWLEDGE_BASE.md`、`kb/*`、`requirements.txt`、`docs/web-apps-deployment.md`、`scripts/botero.env`、`CHANGELOG.md`（新版本节 + bump）。
