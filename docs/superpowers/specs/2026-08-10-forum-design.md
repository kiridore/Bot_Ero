# 议事厅功能设计（2026-08-10）

> 状态：设计收敛，待实施确认。协议：`specs/timeline-protocol.md`（将新增 `forum` source）。仓库知识库：`kb/CONVENTIONS.md` 沉淀的开发经验适用。

## 背景与目标

用户群小（< 20），但缺少一个能发长文/公告/投票的公共空间。当前的留言簿（guestbook）是短文本+匿名+点赞，不承载长内容与决策。议事厅补齐：长文（富文本）、公告（限频）、投票（可配匿名/截止），且所有用户消息自动汇入时间线，让社区活动有统一的「共同记录」。

## 决策记录（本次确认）

| # | 决策 |
|---|---|
| 1 | 仅登录用户可访问；公告每人每天至多 1 条 |
| 2 | 投票默认单选，可配置「是否匿名」「截止时间」，一人一票（DB 唯一约束强制） |
| 3 | 评论也进时间线（群小，量可控） |
| 4 | 投票参与不进时间线；投票**创建**与**结束**进时间线 |
| 5 | 发帖后可编辑可删除，删除 = 硬删除 + 联动时间线 retract |
| 6 | 长文使用 **Tiptap**（WYSIWYG，存 JSON，客户端 `generateHTML` 渲染，编辑器即预览）；投票选项纯文本；评论纯文本 |
| 7 | 引入 tag 系统：用户自由创建，tag 选单显示使用该 tag 的帖子数 |
| 8 | 仅登录门槛，无速率限制 |
| 9 | 新帖（含公告/投票）时机器人发群消息+链接；机制：共享 SQLite `notified_at` 字段 + bot 心跳扫描 |
| A | tag 自由创建 |
| B | Bot 通知 = 共享 DB flag + 心跳扫描 |
| C | 投票结束 = 截止时间自动关 + 手动可关 |

## 架构

```
Web 端                                  Bot 端
  webapp/forum/ 模块                          plugins/forum_notify/ (TimedHeartbeatPlugin)
    POST /api/forum/posts                       每 N 秒扫描
      ├─ 写 forum_posts                              WHERE notified_at IS NULL
      ├─ 写 forum_poll_options（投票）              AND created_at >= ?
      ├─ 写 forum_post_tags                       for each new post:
      ├─ emit_event("forum", ...) ──┐                api.send_msg(group, "新帖：「xx」\n{url}")
      │                              │                UPDATE forum_posts SET notified_at = now WHERE id = ?
      └─（best-effort）              ▼
                                   timeline_events
                                      GET /api/timeline
                                         ▲
                                   /timeline 渲染
                                   （与现有 checkin/quest 同源：forum）
```

- 论坛模块只负责写库 + 调 `core/timeline_client.emit_event`（best-effort），不直读时间线
- Bot 不需要新 HTTP/端口；通过共享 SQLite（WAL 已启用）+ 心跳轮询
- 时间线协议不新增 source 类型，复用现有 `forum` 注册

## 数据模型

在 `core/db/_base.py::init_schema` 追加表：

```sql
CREATE TABLE IF NOT EXISTS forum_posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_user_id TEXT NOT NULL,
  type TEXT NOT NULL,                    -- 'post' | 'announce' | 'poll'
  title TEXT NOT NULL,
  body_json TEXT NOT NULL DEFAULT '',    -- Tiptap JSON（长文）；公告/投票为空字符串
  status TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'closed' | 'hidden' | 'deleted'
  pinned INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  notified_at TEXT,                     -- bot 群消息已发时刻（NULL=待发）
  poll_anonymous INTEGER NOT NULL DEFAULT 0,
  poll_allow_multi INTEGER NOT NULL DEFAULT 0,
  poll_deadline TEXT                    -- NULL = 无截止（仅 type='poll' 有效）
);
CREATE INDEX IF NOT EXISTS idx_forum_posts_created ON forum_posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_forum_posts_notified ON forum_posts(notified_at) WHERE notified_at IS NULL;

CREATE TABLE IF NOT EXISTS forum_poll_options (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  text TEXT NOT NULL,
  ord INTEGER NOT NULL,
  FOREIGN KEY (post_id) REFERENCES forum_posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS forum_poll_votes (
  poll_id INTEGER NOT NULL,
  option_id INTEGER NOT NULL,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(poll_id, user_id),             -- 一人一票（强制）
  FOREIGN KEY (option_id) REFERENCES forum_poll_options(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS forum_comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  author_user_id TEXT NOT NULL,
  body_text TEXT NOT NULL,               -- 评论纯文本，无 Markdown/HTML
  status TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'deleted'
  created_at TEXT NOT NULL,
  FOREIGN KEY (post_id) REFERENCES forum_posts(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_forum_comments_post ON forum_comments(post_id, created_at);

CREATE TABLE IF NOT EXISTS forum_tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,             -- 用户自由创建，名字唯一
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS forum_post_tags (
  post_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  PRIMARY KEY (post_id, tag_id),
  FOREIGN KEY (post_id) REFERENCES forum_posts(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES forum_tags(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_forum_post_tags_tag ON forum_post_tags(tag_id);
```

公告每日限额：`SELECT COUNT(*) FROM forum_posts WHERE author_user_id=? AND type='announce' AND date(created_at)=today`；创建前校验，>0 则 429。日期粒度按本地自然日（`date('now','localtime')`）。

字段命名说明：原 `body_markdown` 改为 `body_json`，因长文存 Tiptap JSON 而非 Markdown；评论仍存 `body_text`（纯文本）。

## API

全部需登录（`get_current_user_id`）。错误码遵循现有 web 模块惯例。

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/forum/posts` | 登录 | 列表；支持 `?tag=&type=&cursor=` 过滤分页；置顶优先 |
| POST | `/api/forum/posts` | 登录 | 创建；body 含 type/title/body_json/polls?/tags? |
| GET | `/api/forum/posts/{id}` | 登录 | 详情；含评论列表、投票选项、当前用户投票状态；body_json 原文返回 |
| PATCH | `/api/forum/posts/{id}` | 作者 | 编辑标题/body_json/tags；type/polls 不可改 |
| DELETE | `/api/forum/posts/{id}` | 作者 | 硬删除 + 联动 retract 时间线 |
| GET | `/api/forum/posts/{id}/comments` | 登录 | 评论分页 |
| POST | `/api/forum/posts/{id}/comments` | 登录 | 新评论（自动 emit_event + 进时间线） |
| DELETE | `/api/forum/comments/{id}` | 作者 | 删评论（retract） |
| POST | `/api/forum/posts/{id}/vote` | 登录 | 投票；校验截止、未投过、单选 |
| POST | `/api/forum/posts/{id}/close` | 作者 | 手动结束投票（仅 type='poll'） |
| GET | `/api/forum/tags` | 登录 | tag 列表（含每个 tag 的帖子数） |
| POST | `/api/forum/tags` | 登录 | 新建 tag（name 全站唯一） |

**长文渲染**：服务端不渲染——返回 `body_json` 原文，详情页加载 Tiptap 后 `generateHTML(json, extensions)` 转 HTML。删除帖时直接 DELETE 行，JSON 不需单独清理。

## 页面与 UI

| 路径 | 内容 |
|---|---|
| `/forum` | 帖子列表：置顶 → 公告（置顶+不同视觉块）→ 普通帖按时间倒序；侧栏 tag 过滤 |
| `/forum/{id}` | 帖子详情：标题/Tiptap 长文渲染（详情页加载 Tiptap）/评论列表/投票 UI；操作：编辑、删除、投票（投票帖）/发评论 |
| `/forum/new?type=post\|announce\|poll` | 发布页：type 选择器；公告有"今日剩余次数 0/1"提示；投票可添加选项（动态增删行）+ 匿名复选框 + 截止时间选择；长文加载 Tiptap 编辑器 |
| `/forum/tags` | tag 管理：列表（名称+帖子数）+ 新建输入框 |

**导航**：侧栏加"议事厅"入口（追加至 `webapp/timeline/entries.json` 数组）：
```json
{
  "name": "议事厅",
  "desc": "长文、公告与投票",
  "url": "/forum"
}
```
侧栏 tag 筛选 = 列表页顶部 tag 链接。

**富文本编辑**：长文用 **Tiptap** WYSIWYG（StarterKit：粗体/斜体/标题/列表/引用/代码块/链接/图片），编辑器即所见即所得预览，无需另设预览面板。Tiptap 通过 ESM bundle 引入（`@tiptap/core` + `@tiptap/starter-kit` + `@tiptap/pm`）；v1 用 CDN（`jsdelivr` 固定版本 + SRI），后续可本地 vendoring 到 `webapp/static/vendor/tiptap/`。仅发布页与详情页加载，列表页不依赖。评论/选项用 `<textarea>` + `textContent`（与 guestbook 一致）。

## 时间线接入

复用现有 Event Server 协议，仅在 `specs/timeline-protocol.md` §已注册 source 表追加：

| source | 描述 | dedup_key |
|---|---|---|
| `forum` | 议事厅发帖/评论/投票结束 | `forum_post:<id>` / `forum_comment:<id>` / `forum_poll_close:<id>` |

事件 title + description 模板（`display.description` 承载长文节选，`display.title` 已含作者+标题）：

| 事件 | `display.title` | `display.description` | `target.url` |
|---|---|---|---|
| 长文 post | `{id:<author>} 在议事厅发布了长文「<title>」` | 长文正文节选（从 Tiptap JSON 提取纯文本，前 ~150 字，超长截断 + "…"） | `/forum/<id>` |
| 公告 announce | `{id:<author>} 发布了公告「<title>」` | 公告正文节选（前 ~150 字，无正文则空字符串） | `/forum/<id>` |
| 投票创建 poll | `{id:<author>} 发起了投票「<title>」` | 空（标题已足够，投票选项不节选进卡片） | `/forum/<id>` |
| 投票结束 poll_close | `投票「<title>」已结束` | 空 | `/forum/<id>` |
| 评论 comment | `{id:<author>} 在「<title>」回复了` | 评论正文前 ~80 字 | `/forum/<id>` |

卡片渲染结构（已存在的 `webapp/static/timeline.js` 即可满足，**无需新增前端代码**）：
```
[头像]昵称          [时间戳]
{author} {id:<author>} 在议事厅发布了长文「title」      ← display.title
正文节选……                                  ← display.description
[» 详情] (if ev.target.url)                ← 已实现的详情按钮
```
时间线**仅展示**作者（actor chip 渲染昵称）+ 标题（title）+ 节选（description）+ »详情按钮（target.url）——完整正文留在 `/forum/<id>` 详情页，符合用户「不要显示完整文章内容」的要求。

`target.url` 用站内相对路径 `/forum/<id>`——需同步放宽 Event Server 校验（接受 `/` 开头的相对路径，详见实施任务 T4 的协议小改动）。删除帖子时 `retract_event("forum", "forum_post:<id>")`；删评论同。

## Bot 通知机制（共享 SQLite + 心跳）

新增 `plugins/forum_notify/`（继承 `TimedHeartbeatPlugin`，`RUN_AT="*%30"` 或每分钟轮询）：

```python
def handle(self):
    new_posts = self.dbmanager.conn.execute(
        "SELECT id, type, title, author_user_id FROM forum_posts "
        "WHERE notified_at IS NULL AND status != 'deleted' "
        "ORDER BY created_at ASC LIMIT 10"
    ).fetchall()
    for pid, ptype, title, _ in new_posts:
        url = f"https://littlero.tech/forum/{pid}"
        prefix = {"post": "长文", "announce": "公告", "poll": "投票"}.get(ptype, "帖子")
        self.api.send_msg(text(f"📌 议事厅新{prefix}：「{title}」\n{url}"))
        self.dbmanager.conn.execute(
            "UPDATE forum_posts SET notified_at = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pid),
        )
    # 顺手关闭过期投票
    expired = self.dbmanager.conn.execute(
        "SELECT id, title FROM forum_posts "
        "WHERE type='poll' AND status='open' AND poll_deadline IS NOT NULL "
        "AND poll_deadline <= datetime('now','localtime')"
    ).fetchall()
    for pid, title in expired:
        self.dbmanager.conn.execute(
            "UPDATE forum_posts SET status='closed' WHERE id=?", (pid,)
        )
        emit_event(
            source="forum",
            actor_id=0,
            title=f"投票「{title}」已结束",
            dedup_key=f"forum_poll_close:{pid}",
        )
    self.dbmanager.conn.commit()
```

**注意**：bot 与 webapp 共享 `data.db`（WAL 已启用）；UPDATE 在 bot 端、INSERT 在 webapp 端，互不冲突。`actor_id=0` 表示系统事件，渲染层可显示"系统"或"自动结束"。

## 投票生命周期

```
创建  →  status='open'  →  emit_event "发起了投票"
投票  →  写 forum_poll_votes，UNIQUE 强制一人一票
截止  →  bot 心跳检测 poll_deadline ≤ now → status='closed' → emit_event "已结束"
手动  →  作者 PATCH status='closed' → emit_event "已结束"（同 dedup_key 幂等）
```

匿名投票语义：`poll_anonymous=1` 时，结果页只显示**选项+票数**，不展示任何投票人昵称；服务器仍记录 user_id（用于一人一票强制），仅展示层隐藏。

## 安全与渲染

- **长文**：存 Tiptap JSON；渲染时 `generateHTML(json, starterKit)` 在客户端执行，输出 HTML 受 StarterKit schema 约束（白名单节点与属性），无任意 HTML 入口
- **评论/选项**：前端用 `escapeHtml()` + `textContent`，与现有 guestbook/char_view 同款
- **XSS 边界**：长文 JSON 由服务端存储（不可信 → 可信，schema 固定）；HTML 输出由 Tiptap schema 约束（不可信节点不会进入）；评论/选项纯文本走 `textContent`；时间线 title 用 `{id:}` 占位符 + 渲染时替换（已在时间线设计确立）

## Auth 与权限

- 全部 API 走 `get_current_user_id`（HMAC token）
- 创建：任意登录用户；公告受每日 1 次约束
- 编辑/删除帖与评论：作者本人；`SUPER_USER` 可强制（`core/base.py` 已定义）
- 投票：任意登录用户（v1 允许自投）
- 关闭投票：作者本人 + SUPER_USER

## 非目标（v1 不做）

- 评论嵌套/回复链（评论只对帖平铺）
- 评论编辑（仅可删除）
- 投票多选（仅单选，字段已留 `poll_allow_multi` 备用）
- 图片上传到长文（v1 纯富文本）
- 搜索 / 全文检索
- 通知/邮件/个人消息中心
- 帖子版本历史
- 板块/分类（用 tag 替代）

## 实施任务清单

- [ ] **T1：存储层** `core/db/forum.py` 新建 `ForumManager`（posts/comments/tags/votes 各方法 + list_with_cursor）；`core/db/_base.py` 追加 6 张表与索引；`core/database_manager.py` 挂载 `self.forum`
- [ ] **T2：协议规范同步** `specs/timeline-protocol.md` §已注册 source 表追加 `forum`；`specs/database.md` §议事厅追加表结构
- [ ] **T3：Tiptap 集成** `webapp/forum/editor.js` 封装初始化/序列化/编辑回填；`forum.html` 通过 `<script type="module">` 加载 Tiptap（v1 走 jsdelivr CDN + SRI 固定版本：`@tiptap/core@2` + `@tiptap/starter-kit@2` + `@tiptap/pm@2`）；提交时 `JSON.stringify(editor.getJSON())` 存入 `body_json`
- [ ] **T4：论坛模块** `webapp/forum/app.py` 实现 10 个 API + `_tiptap_to_plain` + `_excerpt(body_json, max_len)`（Tiptap JSON 递归提取 text 节点、空白归一、截断 + "…"）；`webapp/forum/__init__.py`；`webapp/app.py` include router；`webapp/timeline/entries.json` 加侧栏入口；**Event Server 校验放宽**：`webapp/timeline/app.py::_validate_event` 接受 `/` 开头的相对路径 + `specs/timeline-protocol.md` §发送与幂等 同步更新
- [ ] **T5：前端** `webapp/static/forum.html/js/css` 三页：列表、详情、发布；tag 侧栏筛选；详情页加载 Tiptap 渲染 `body_json`
- [ ] **T6：时间线接入** 论坛模块内创建/删除时调 `core/timeline_client.emit_event`/`retract_event`；title 模板按上文
- [ ] **T7：Bot 通知** `plugins/forum_notify/__init__.py`（TimedHeartbeatPlugin）扫描新帖发群消息 + 过期投票自动关闭 + emit 关闭事件
- [ ] **T8：文档同步** `kb/CONVENTIONS.md` 沉淀新坑（如有）；`CLAUDE.md` 模块列表 +9→10 模块；`KNOWLEDGE_BASE.md` 索引；`docs/web-apps-deployment.md` 路由表
- [ ] **T9：验证** 见下方

## 验证清单

```bash
# 权限
curl POST /api/forum/posts 无 token → 401
curl POST type=announce → 当日第二条 → 429

# 时间线接入
POST type=post → 时间线出现「在议事厅发布了长文「x」」卡
POST type=announce → 时间线卡 + bot 群消息 + notified_at 已写
POST type=poll → 时间线出现「发起了投票「x」」
DELETE post → 时间线 retract_event 触发，卡消失

# 投票
POST /vote 同 user_id 第二次 → 409
POST /vote 截止后 → 422
bot 心跳触发关闭 → 时间线出现「投票「x」已结束」（idempotent，同 dedup_key）

# 评论
POST comment → 时间线出现「回复了「x」」卡
DELETE comment → 卡消失

# Tag
POST /tags 同名 → 409
GET /tags 返回带帖子数

# 渲染
长文 Tiptap 输入 → 存 JSON；详情页 generateHTML 输出不含用户自定义 HTML
长文 JSON 含 "<script>" 字串 → 渲染后无脚本执行（Tiptap schema 限制）
评论含 HTML 标签 → textContent 显示原文

# 时间线卡片
长文事件 → 卡片 description 出现正文节选（前 ~150 字，超长截断 + "…"）
评论事件 → 卡片 description 出现评论正文前 ~80 字
长文/评论事件 → 卡片存在 »详情按钮，href = `/forum/<id>`
点 »详情 → 跳转到 `/forum/<id>` 详情页
`target.url` 为 `/forum/123`（相对路径）→ Event Server 校验通过（放宽后）

## 风险与权衡

| 风险 | 缓解 |
|---|---|
| bot 与 webapp 共享 SQLite 的 UPDATE/INSERT 互踩 | 已启用 WAL，busy_timeout=5000；写入路径短，无长事务 |
| `notified_at` 索引在 webapp 端无写竞争（bot 单写者） | 但需 bot 启动后即处理积压——首条新帖不漏 |
| 公告每日 1 次的"日"按本地自然日，非 08:00 偏移 | 与已有"周"概念不冲突；明确写在文档 |
| 投票匿名=不展示昵称，但 user_id 仍存 | 任何"匿名"系统的标准做法；文档明确语义 |
| tag 自由创建可能产生同义 | UI 显示帖子数让用户识别常用 tag；不做合并/别名 |
| Tiptap CDN 依赖（首次加载发布/详情页时拉取） | 选固定版本 + SRI；后续可 vendoring 到 `webapp/static/vendor/tiptap/` |
| Tiptap 体积（starter-kit + PM ~400KB min ESM） | 仅发布/详情页加载；列表页不依赖 |

## 文档同步义务

实施 commit 需同步：`specs/timeline-protocol.md`（source 表）、`specs/database.md`（表结构）、`CLAUDE.md`（模块与路由）、`KNOWLEDGE_BASE.md`（索引）、`docs/web-apps-deployment.md`（路由表）、`docs/superpowers/plans/<日期>-forum.md`（实施计划）。
