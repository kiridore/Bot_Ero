# 小埃周报功能设计（2026-08-15）

> 状态：设计收敛，待实施确认。数据源：新独立库 `server_data/message_log.db`（消息日志，高频写入）+ 主库 `data.db`（周报产物与玩法数据）。webapp 新增第 11 个模块（`/weekly`）。

## 背景与目标

群内每周产生大量活动数据（打卡、抽奖、发言、复读、语录、活跃时段），分散在多个表和 bot 处理链路中，没有沉淀为可回看的集体记忆。周报把每周数据聚合为一期「报纸」，webapp 端报纸排版展示并永久归档，周一 08:00 自动出版，群内通知链接。

用户群小（< 20），周报定位是**趣味性集体记录**，不是严肃数据分析——版面以榜单、语录、热梗、对比为主，数字服务趣味。

## 决策记录（本次确认）

| # | 决策 |
|---|---|
| 1 | 消息日志独立库 `server_data/message_log.db`，系统插件全群记录，**永久保留** |
| 2 | 周报产物存 `data.db` 的 `weekly_reports` 表（一期一行 + JSON 数据列），**永久归档** |
| 3 | 生成时机：周一 08:00 `TimedHeartbeatPlugin`，与商店刷新/周常重置同刻；幂等 + 启动补偿 |
| 4 | 生成后群内发一条通知：「第 N 期《小埃周报》已出版 + 链接」 |
| 5 | 展示：webapp `/weekly` 模块，报纸排版（复用全站报纸风 token），列表归档 + 详情页 |
| 6 | 打卡图墙 = 每人本周首张打卡图**群像墙**（排除补卡，按 user 分组取最早一次），复用 gallery `/thumb` 公开路由 |
| 7 | 活跃柱状图前端 SVG 渲染（每日消息数，7 根柱），不用后端 Pillow |
| 8 | v1 单群（默认群），`group_id` 字段预留多群 |
| 9 | 期号由 `weekly_reports` 行数推导（第 N 期 = 该群 row_count），无需独立计数器 |
| 10 | 语录/热梗点名展示发言人昵称（`resolve_display_name`），规则过滤敏感内容 |
| 11 | 本周热词词云：引入 **jieba** 分词（`posseg` 词性过滤，结果更细致），前端 CSS 流式渲染（报纸标题词条风）；jieba 缺失时降级 `re` 简易方案，不阻塞周报 |
| 12 | **首周测试期限制**：暂不实现群通知与侧边栏「周报」入口，仅保留 `/weekly` 路径供开发者直连调试；群通知由开关控制（默认关闭），测试通过后启用 |
| 13 | 消息日志不落 bot 自身消息；`messages` 表增加 `reply_to_msg_id`（`reply` 段剥离前落库），供语录“被回复+1”评分 |
| 14 | 抽奖流水：data.db 新增 `lottery_draw_log`，`plugins/lottery` 每次抽奖后写一行，供周报按周统计欧皇/非酋 |

## 版面设计（本文件核心）

滚动长页 = 一份 5 版报纸 + 报头。版序按报纸惯例排主次：头版最重 → 数据 → 言论 → 观察 → 花絮收尾。每版用报纸式栏目标题（衬线标题 + 上下分隔线）区分，页脚有期号水印。

### 报头（页首，非独立版）

| 元素 | 内容 |
|---|---|
| 刊名 | 小埃周报 |
| 期号 | 第 N 期（连续计数） |
| 日期区间 | `2026.08.10 — 2026.08.17`（周一 08:00 周界，`get_monday_to_monday()`） |
| 超大数字区 | 本周消息总数 + 总字数（两个大字数字并排，报头视觉锚点） |
| 口径 | 总条数 = 全周群消息数；总字数 = 全周消息 `text` 长度之和（与总条数同口径，含命令） |
| 副题导读 | 一句话自动拼装：如「全勤 3 人 · 话痨王 XXX 蝉联 · 仙人彩 4A 滚入下期」 |

### 头版 · 本周头条

1 件本周大事：大标题 + 一段简述 + 1~2 个关键数字卡片。

**头条候选优先级链**（自上而下取第一个有数据的）：

1. 仙人彩中大奖（1 等/2 等有人中）或奖池滚存创新高
2. 群活动（接龙/匹配）本周结束且参与人数 > 0
3. 新传说称号解锁
4. 本周总消息数破历史纪录（对比 `weekly_reports` 历史 JSON）
5. 卧底战局参与人数破纪录
6. 全部无 → 「平淡的一周」幽默占位（如「本周群内风平浪静，大家都在好好生活」）

### 二版 · 群情数据（对开两栏）

**左栏 · 打卡战报**（`checkin_records`）

- 总打卡次数、参与人数、日均
- 全勤榜（7/7 名单，金色徽标）；空态：「本周无人全勤」
- 补卡次数
- **打卡图墙（群像）**：每人本周首张打卡图（排除 `content='remedy_checkin'`，按 `user_id` 分组取最早一次），卡片式网格——图为主、底部昵称，URL 复用 gallery 约定 `/thumb/{user_id}/{slug}`；空态：本周无人打卡则隐藏

**右栏 · 抽奖战报**（`user_lottery_daily_stats` / `user_lottery_profile` / `immortal_lottery_results`）

- 总抽数、人均抽数
- 抽卡之王（本周抽数最多）
- 欧皇（本周中 10 积分或出传说称号者）
- 非酋（本周最长连 0 记录）
- 仙人彩小卡：开奖号码 / 奖池 / 中奖情况

### 三版 · 群友言论

**本周语录** 3~5 条：引用块样式，点名 + 日期时间。

挑选规则（LLM 子系统已弃用，纯规则）：

- 排除：命令（`/` 开头）、纯图片、含 `@`/链接/兑换码格式、过短（< 8 字）、过长（> 80 字）
- 评分：被回复数 +1，含图片 +0.5，含 emoji +0.5；取 TOP 2 + 随机 2~3 补足
- 每用户限 1 条（避免一人刷屏）
- 空态：无候选则隐藏该块

**复读热梗 TOP3**：被复读文本 + 复读次数 + 参与人数；**复读王**（参与复读事件最多者）。

复读事件定义：同一纯文本 ≤30 分钟内 ≥3 个不同用户发送 → 计 1 次复读事件。忽略命令、过短文本（≤ 2 字）、bot 自身消息。

**本周热词**：词云 TOP 30，展示群友本周话题热度。

分词（jieba，bot 侧新依赖）：

- 依赖：`pip install jieba`（不锁版本）；生成器聚合时**懒导入**，`ImportError` 时降级为 `re` 简易方案（决策 11），热词缺失不影响其它板块
- 分词：`jieba.posseg.lcut(text)` 精确模式，保留实词词性（n/v/a），过滤虚词与噪音词性（u/p/c/d/x/m：助词/介词/连词/副词/非语素/数词）及标点
- 补充停用词表（的/了/吗/啊/嗯 等 jieba 未覆盖的语气词）
- 过滤：长度 < 2、纯数字
- **去重**：每用户每日对同一词最多计 1 次（防复读/刷屏污染热词）
- 按频率降序取 TOP 30
- 可选增强（v1 不做）：`jieba.load_userdict` 支持群专属词汇（如「板油」「小埃」）
- 空态：无候选词则隐藏该块

渲染（报纸风，前端 CSS）：flex-wrap 流式排布，不画 canvas 碰撞——报纸没有圆形词云，词条即「报纸标题词条」：字号/字重按频率分 4~5 档，墨黑为主、TOP3 金色点缀，高频词带次数角标（`[42]`），词条间报纸分隔符间隔；少量随机倾斜（0°/±3°）增加手作感。

### 四版 · 群像观察

- **活跃柱状图**：每日消息数柱状图（7 根柱，周一至周日），柱高 = 当日消息数，峰值柱金色高亮，柱顶标注数字
- **峰值摘要**：本周最活跃时段文字：「周三 21 点最活跃，一小时 214 条」
- **话痨榜 TOP5**：条数 + 群占比进度条
- **深夜党**（1-5 点发言最多者）/ **早起鸟**（8-12 点发言最多者）

### 五版 · 花絮

- **蝉联榜**：连续上榜者（话痨王连庄 N 周，比较历史期 JSON 的 TOP1 user_id）
- **涨幅榜**：比上周发言涨幅最大者
- **冷知识之最**：最长单条消息 / 单日最多消息 / 最多图片的一天 / 1 分钟内连发最多（随机轮换出 2~3 条）
- **刊尾**：「本期完 · 下期周一 08:00 自动出版」

### 空态降级总则

每个板块定义空态文案或直接隐藏，报纸不开天窗。柱状图全零（极低活跃周）仍正常渲染（矮柱）。

### 移动端适配

- 两栏对开在 <768px 塌为单栏（报纸分栏不跨行）
- 柱状图柱宽弹性自适应容器宽度，小屏不挤压
- 打卡群像墙卡片网格自适应（3 列 → 2 列）

## 架构

```
群消息
  │
  ▼
message_logger（系统插件，全群记录，不受 per-group 启用影响）
  │  INSERT（独立库单写者，无锁竞争）
  ▼
server_data/message_log.db
  │
  │ 周一 08:00 心跳（与商店刷新/周常重置同刻，无冲突）
  ▼
weekly_report_generator（TimedHeartbeatPlugin，幂等 + 启动补偿）
  │  聚合 message_log.db（发言/复读/语录/时间轴）
  │       + data.db（打卡/抽奖/仙人彩/周常/称号/活动）
  │  写 weekly_reports 一行 → 群内通知「第 N 期已出版 + 链接」
  ▼
data.db: weekly_reports（永久归档）
  │
  ▼
webapp /weekly 模块（第 11 个）
  ├─ GET /weekly 最新一期（无 week_key 时重定向）
  ├─ GET /weekly/<week_key> 详情（报纸排版渲染 data_json）
  ├─ GET /api/weekly 列表（归档目录）
  ├─ GET /api/weekly/<week_key> 详情数据
  └─ entries.json 侧边栏「周报」入口
```

- 生成器是只读聚合 + 单行写入，与同刻的商店刷新/周常重置互不冲突
- 打卡图墙不走新接口：详情 API 直接返回 `/thumb/{user_id}/{slug}` URL，前端 `<img>` 加载（gallery 路由已公开）

## 数据模型

### message_log.db（新独立库，仿 `DbManager` WAL + busy_timeout 配置）

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    msg_id INTEGER NOT NULL,        -- QQ 消息 ID，防重复入库
    reply_to_msg_id INTEGER,        -- 本消息回复的目标消息 ID（无 reply 段为空）
    sent_at TEXT NOT NULL,          -- YYYY-MM-DD HH:MM:SS
    text TEXT NOT NULL DEFAULT '',  -- 剥离 CQ 码后的纯文本（命令也存，统计时过滤）
    has_image INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_messages_group_time ON messages(group_id, sent_at);
CREATE INDEX idx_messages_text ON messages(text);   -- 复读检测 GROUP BY text
```

- 只记录群消息（`group_id` 为 None 的私聊不记），并跳过 bot 自身消息（`user_id == BOT_QQ`）
- 文本提取：遍历 message segments，text 段拼接；图片段置 `has_image=1`；`@` 段剥离；`reply` 段剥离前取 `data.id` 写入 `reply_to_msg_id`
- 永久保留（决策 1）；库文件不存在时自动建表（`init_schema` 模式）

### data.db（`core/db/_base.py::init_schema` 追加）

```sql
CREATE TABLE weekly_reports (
    week_key TEXT NOT NULL,         -- 周一日期 YYYY-MM-DD（周界起点）
    group_id INTEGER NOT NULL,      -- 预留多群，v1 恒为默认群
    data_json TEXT NOT NULL,        -- 完整版面数据
    created_at TEXT NOT NULL,
    PRIMARY KEY (week_key, group_id)
);

CREATE TABLE lottery_draw_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    drawn_at TEXT NOT NULL,         -- YYYY-MM-DD HH:MM:SS
    result_type TEXT NOT NULL,      -- points | title_new | title_duplicate | title_none
    value INTEGER,                  -- points 数值或 title_id
    rarity TEXT,                    -- title 稀有度（title_* 时）
    zero_streak_after INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_lottery_draw_log_time ON lottery_draw_log (drawn_at);
```

期号 = `SELECT COUNT(*) FROM weekly_reports WHERE group_id=? AND week_key <= ?`。

### data_json 结构草案

```json
{
  "period": {"issue": 3, "start": "2026-08-10", "end": "2026-08-17", "total_messages": 1523, "total_chars": 48210},
  "headline": {"kind": "immortal_jackpot", "title": "…", "body": "…", "stats": [{"label": "奖池", "value": 42}]},
  "checkin": {
    "total": 31, "users": 9, "daily_avg": 4.4,
    "full_week": [{"user_id": 1, "name": "…"}],
    "remedy": 2,
    "images": [{"user_id": 1, "name": "…", "url": "/thumb/1/xxx.jpg"}],   // 每人本周首张（排除补卡）
  },
  "lottery": {
    "total_draws": 120, "per_user": 13.3,
    "top": {"user_id": 1, "name": "…", "count": 40},
    "lucky": [{"user_id": 2, "name": "…", "hit": "十连" }],
    "unlucky": {"user_id": 3, "name": "…", "zero_streak": 15},
    "immortal": {"digits": "1234", "pool": 42, "winners": 1}
  },
  "voices": {
    "quotes": [{"user_id": 1, "name": "…", "text": "…", "at": "2026-08-11 21:33"}],
    "memes": [{"text": "…", "count": 5, "users": 3}],
    "meme_king": {"user_id": 2, "name": "…", "count": 8},
    "words": [{"w": "打卡", "c": 42}, {"w": "抽奖", "c": 31}]   // TOP 30，频率降序
  },
  "activity": {
    "daily": [120, 98, 214, 87, 143, 55, 31],   // 周一至周日每日消息数
    "peak": {"day": 3, "hour": 21, "count": 214},
    "talkers": [{"user_id": 1, "name": "…", "count": 412, "ratio": 0.27}],
    "night_owl": {"user_id": 2, "name": "…", "count": 33},
    "early_bird": {"user_id": 3, "name": "…", "count": 7}
  },
  "trivia": {
    "streaks": [{"user_id": 1, "name": "…", "weeks": 3, "title": "话痨王"}],
    "gains": [{"user_id": 2, "name": "…", "delta": 180}],
    "records": [{"label": "最长单条消息", "detail": "…", "user_id": 3, "name": "…"}]
  }
}
```

昵称（`name`）在生成时用 `resolve_display_name` 解析后落库——历史周报永久归档，昵称快照不随改名漂移（展示层不再实时解析）。

## API

全部需登录（`get_current_user_id`）。错误码遵循现有 web 模块惯例。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/weekly` | 归档列表：每期 issue/start/end/total_messages/headline.title，按 week_key 倒序 |
| GET | `/api/weekly/<week_key>` | 详情：整行 `data_json` 返回（含打卡图墙 URL 数组） |
| GET | `/weekly` | 页面：最新一期（无 week_key 重定向到最新） |
| GET | `/weekly/<week_key>` | 页面：指定期详情 |

## 页面与 UI

| 路径 | 内容 |
|---|---|
| `/weekly` | 最新一期报纸全文；顶部归档导航（期号下拉/左右翻期） |
| `/weekly/<week_key>` | 指定期全文；页头显示期号 + 日期区间 |

- 报纸排版复用全站 token（`core/web/static/gallery.css` 报纸风）+ 动效层（`motion.css/js` 自动注入，页面过渡/滚动揭示免费获得）
- 柱状图：前端按 `daily` 数组渲染 SVG 柱状图（7 柱），报纸风单色系，峰值柱金色高亮 + 柱顶数字
- 词云：前端按 `voices.words` 渲染 CSS 流式词云（字号分级 + TOP3 金色 + 次数角标 + 报纸分隔符），词条 `textContent` 渲染防 XSS
- 语录：引用块样式 + 左侧竖线，点名 + 时间（`textContent` 渲染，防 XSS）
- **导航**：侧栏加「周报」入口（追加至 `webapp/timeline/entries.json` 数组）；**首周暂不加入**，`/weekly` 路径保留直连调试（决策 12）：
  ```json
  {"name": "周报", "desc": "每周一自动出版的群周报", "url": "/weekly"}
  ```

## Bot 端机制

### message_logger（系统插件）

- 注册进 `SYSTEM_PLUGINS`（`core/context.py`），match 所有 message 事件，不依赖群启用状态
- 只记录群消息（`group_id` 非 None），跳过 bot 自身消息（`user_id == BOT_QQ`）
- 每条群消息一次 INSERT（自动提交；独立库单写者，无锁竞争）
- 防重复：按 `msg_id` 查重（`UNIQUE` 或插入前查）；重复事件（如重启补收）跳过
- `sent_at` 取事件 `time`（Unix 秒）转 `YYYY-MM-DD HH:MM:SS`，缺失回退 `datetime.now()`

### weekly_report_generator（TimedHeartbeatPlugin，周一 08:00）

```python
def handle(self):
    start, end = get_monday_to_monday()   # 上一周周界（周一 08:00 → 次周一 08:00）
    week_key = start.split(" ")[0]        # 周一日期 YYYY-MM-DD（周界起点）
    group_id = core.config.GROUP_ID
    if self.dbmanager.weekly.exists(week_key, group_id):
        return  # 幂等：已生成则跳过
    data = aggregate(week_key, group_id, start, end)   # 聚合两个库，产出 data_json
    self.dbmanager.weekly.upsert(week_key, group_id, data)
    if core.config.WEEKLY_NOTIFY_ENABLED:
        self.api.send_msg(text(f"📰 第 {issue} 期《小埃周报》已出版\n{core.config.WEB_BASE_URL}/weekly/{week_key}"))
```

- **启动补偿**：插件模块级 `_boot_checked` flag，`match` 允许启动后首次 meta 触发（参考 `startup_changelog`），`handle` 先补漏上周再执行定时生成——周一 08:00 bot 停机不丢期；补漏同样幂等
- **失败重试**：生成或通知异常时 `logger.exception()`，week_key 未写入则下一心跳自然重试
- 群通知 URL 用 `core.config.WEB_BASE_URL`（env `BOTERO_WEB_BASE_URL`，默认 `https://littlero.tech`）；**首周测试期暂不启用**（`core.config.WEEKLY_NOTIFY_ENABLED`，env `BOTERO_WEEKLY_NOTIFY`，默认关闭），仅保留 `/weekly` 路径供开发者直连调试（决策 12）
- 群通知经 `api.send_msg` 发送：meta 事件无 `group_id`，会 fallback 到 `context.DEFAULT_GROUP_ID`（默认与 `core.config.GROUP_ID` 一致）；若生产覆盖 `BOTERO_GROUP_ID`，需同步 `DEFAULT_GROUP_ID`

## 安全与渲染

- 语录/热梗/榜单文本前端一律 `escapeHtml()` + `textContent`（与 guestbook 同款）
- 语录过滤规则排除链接/`@`/命令，降低敏感内容曝光；点名展示的是群内公开昵称，与现状一致
- 打卡图墙 URL 复用 gallery `_file_slug` 约定（防路径穿越），路由已公开且带 resolve+guard
- 无 LLM 参与（子系统已弃用）：头条/导读/语录全部规则化生成，确定性输出

## 非目标（v1 不做）

- 多群 UI / 多群通知（schema 已预留）
- 手动生成 / `/周报` 命令 / 补发接口
- 周报互动（点赞/评论/分享统计）
- 语录人工审核、置顶、举报
- 标题/导读 AI 生成
- PDF 导出 / 打印样式
- 消息日志的搜索/浏览界面（仅周报消费）

## 实施任务清单

- [ ] **T1：消息日志** `core/config.py`（`MESSAGE_LOG_DB_PATH`/`WEB_BASE_URL`/`WEEKLY_NOTIFY_ENABLED`）；`core/db/message_log.py`（独立库连接 + 建表含 `reply_to_msg_id` 与索引 + insert/get_week 方法）；`core/context.py` 注册系统插件；`plugins/message_logger/`（文本提取、msg_id 查重、跳过 bot 自身、reply 目标落库）
- [ ] **T2：存储层** `core/db/_base.py::init_schema` 追加 `weekly_reports` 与 `lottery_draw_log`；`core/db/weekly.py` 新建 `WeeklyReportManager`（upsert/get/list/issue 推导，按 group_id 过滤）；`core/db/lottery.py` 新增抽奖流水查询；`plugins/lottery` 写流水
- [ ] **T3：生成器** `plugins/weekly_report/`（TimedHeartbeatPlugin 周一 08:00）：聚合两库（打卡/抽奖/仙人彩/周常/称号/活动 + 发言/复读/语录/热词/活跃柱状图/花絮）、jieba 分词（posseg 词性过滤 + ImportError 降级）、头条优先级链、语录/复读规则、空态处理、幂等 + 启动补偿（启动后首次 meta 检查补漏） + 失败重试、群通知（开关控制）
- [ ] **T4：webapp 模块** `webapp/weekly/app.py`（2 个 API + `/weekly` 与 `/weekly/<week_key>` 2 个页面路由）；`webapp/app.py` include；`webapp/timeline/entries.json` 加「周报」入口（首周暂不加入）
- [ ] **T5：前端** `webapp/static/weekly.html/js/css`：报头 + 5 版渲染 + 页脚期号水印、柱状图 SVG（弹性柱宽）、词云、打卡群像墙、归档导航（期号下拉/翻期）、移动端塌栏
- [ ] **T6：文档同步** `CHANGELOG.md` 顶部 `[新版本]` 节 + `core/config.py::BOTERO_VERSION` bump（新功能 minor）；`requirements.txt` 加 jieba；`KNOWLEDGE_BASE.md` + `kb/`（新插件/新表/新模块/新 env）；`specs/database.md`（`messages`/`weekly_reports`/`lottery_draw_log` 三张新表）；`specs/web-gallery.md`（第 11 模块 + 路由）；`specs/plugin-catalog.md`（新增插件登记）；`CLAUDE.md` 模块清单与计数统一为 11；`kb/OPERATIONS.md` 依赖清单补 jieba（bot 侧）；`docs/web-apps-deployment.md` 路由与 env 表；`scripts/botero.env` 补新 env 注释
- [ ] **T7：验证** 见下方

> 无新 bot 命令 → `plugins/menu/bot_menu_text.py` 不动。

## 验证清单

```bash
# 消息日志
群发 3 条消息 → message_log.db 出现 3 行，私聊消息不出现，bot 自身消息不落库
同 msg_id 重复事件 → 不重复入库
含图片消息 → has_image=1；@/reply 段不进入 text，reply 消息的 reply_to_msg_id 正确落库

# 抽奖流水
每抽 1 次 → lottery_draw_log 新增 1 行；points 10 或 title_new(legendary) 可被周度欧皇查询命中

# 生成（手动触发一次 handle 或等待周一 08:00）
→ weekly_reports 出现一行（group_id = core.config.GROUP_ID），data_json 完整（daily 7 项 = Σ 每日条数，period.total_chars = Σ text 长度）
→ 首周测试期：群内**不**收到周报通知；将 BOTERO_WEEKLY_NOTIFY=1 后重启再触发 → 群内收到「第 N 期《小埃周报》已出版 + 链接」
→ 重复触发 → 幂等跳过，不覆盖

# 启动补偿
删除上周行 → 重启 → 自动补生成

# 语录/复读规则
命令、@、链接、<8 字、>80 字 → 不进语录；被回复消息的“被回复+1”体现在评分中；同文本 30 分钟内 3 人 → 计入复读

# 热词
命令/停用词/单字/纯数字 → 不进词云；同用户同日重复词只计 1 次；TOP 30 频率降序
助词/介词/连词/副词（的/了/在/和/很）→ 不出现于词云
模拟 jieba 缺失（ImportError）→ 降级 re 方案，热词仍产出且周报不中断

# webapp
GET /api/weekly 无 token → 401
GET /weekly → 最新期；GET /weekly/<week_key> → 指定期
打卡群像墙：每人 1 张，URL 可访问（/thumb 路由 200），补卡不计入
首周测试期：侧边栏**不出现**「周报」入口；entries.json 加入后重启 webapp → 侧边栏出现
```

实施 commit 需同步：`specs/database.md`、`specs/web-gallery.md`、`specs/plugin-catalog.md`、`CLAUDE.md`（模块与路由）、`KNOWLEDGE_BASE.md`（索引）、`kb/*`（插件目录/数据库/惯例）、`requirements.txt`、`docs/web-apps-deployment.md`、`scripts/botero.env`、`CHANGELOG.md`（新版本节 + bump）。
