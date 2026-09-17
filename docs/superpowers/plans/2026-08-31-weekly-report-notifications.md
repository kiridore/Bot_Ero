# 周报出版通知实施计划（2026-08-31）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 周报出版（周一 08:00 生成）后默认发两类通知——群消息 + 社区时间线事件，时间线事件 actor 为小埃同学（bot 本体）；`BOTERO_WEEKLY_NOTIFY` 统一控制两类通知，默认值从 `0` 翻为 `1`。

**Architecture:** 复用既有 `plugins/weekly_report/_generate_week` 末尾的通知开关块：开启时先发群消息（已有），再调 `core.timeline_client.emit_event`（bot 侧既有 best-effort 通道）发一条时间线事件。不改生成逻辑、不加 web 入口、不加 bot 命令。

**Tech Stack:** 纯同步多线程 bot 插件 + FastAPI webapp 时间线（Event Server 接收）。无新依赖。

**Spec:**
- 权威设计：`docs/archive/superpowers/specs/2026-08-15-weekly-report-design.md`（决策 12 的「首周测试期」由本计划终结）
- 时间线协议：`specs/timeline-protocol.md`（新增 source MUST 在 §「已注册 source 与 dedup_key 约定」表注册，同 commit）
- 已确认的需求决策（2026-08-31 对话）：
  - Q1a：`BOTERO_WEEKLY_NOTIFY` 默认改为开启，保留 env 可关；**时间线通知与群通知受同一开关控制**
  - Q2：时间线事件 actor = bot 本体（`core.base.BOT_QQ` = `"3915014383"`）
  - Q3：时间线卡片 = title「第 N 期《小埃周报》已出版」+ description「本周 X 条消息 · Y 字」+ `target_url=/weekly/<week_key>`（站内相对路径，时间线渲染「>>详情」按钮）；**不带图片**（时间线事件 API 在登录白名单内，公开可读，打卡图墙有隐私四态设置，放进公开卡片会绕过隐私控制）
  - Q4：**不加**侧边栏入口（`entries.json` 不动）

## Global Constraints

- bot 进程禁止 `async`/`await`（纯同步）
- `emit_event` best-effort 不抛出，不加 try/except 包裹（`core/timeline_client.py` 自带）
- 生成幂等：`(week_key, group_id)` 已存在即整段跳过（含通知），重复触发不重发
- 通知块仍受 `WEEKLY_NOTIFY_ENABLED` 单一开关控制（import 自 `core.config`，plugin 命名空间常量）
- 无新 bot 命令 → `plugins/menu/bot_menu_text.py` 不动；无新表/新路由 → `specs/database.md`/`specs/web-gallery.md` 不动
- 归档目录 `docs/archive/` 下的设计文档**不修改**（历史快照）
- 文档 + CHANGELOG + `BOTERO_VERSION` bump（minor → `1.29.0`）与代码同一 commit；commit 消息中文 Conventional Commits
- 测试不得真实发起 HTTP：凡触发 `_generate_week` 的用例必须 patch `plugins.weekly_report.emit_event`（`_post` 有 5s 超时 ×2 重试，漏 patch 会拖慢回归）

## File Structure

全部为修改，无新文件（计划文档本身除外）：

| 文件 | 职责 |
|---|---|
| `core/config.py:45` | `WEEKLY_NOTIFY_ENABLED` 默认值 `"0"` → `"1"` |
| `plugins/weekly_report/__init__.py` | 通知块加 `emit_event`；import `BOT_QQ`、`emit_event` |
| `test/test_weekly_report.py` | 新增 `TestPublishNotifications` 3 用例；既有 2 个类的 setUp/tearDown 加 `emit_event` 守卫 |
| `scripts/botero.env:18` | 注释更新（默认开启，示例改为关闭用法） |
| `specs/timeline-protocol.md` | 注册 source `weekly_report` + dedup_key 约定 |
| `kb/OPERATIONS.md` / `docs/web-apps-deployment.md` | env 默认值与说明更新 |
| `kb/PLUGIN_CATALOG.md` | `weekly_report` 插件行描述更新 |
| `CHANGELOG.md` + `core/config.py::BOTERO_VERSION` | `[1.29.0]` 节 + bump |

---

### Task 1: 通知行为测试（先红）

**Files:**
- Modify: `test/test_weekly_report.py`

**Interfaces:**
- Consumes: `WeeklyReportPlugin._generate_week(start: str, end: str)`（已存在，`plugins/weekly_report/__init__.py:118`）；`test/helper.py::MockApiWrapper.sent_messages: list[tuple[str, tuple]]`（`send_msg(*message)` 把消息元组原样记录）；`core.cq.text(s) -> dict`（形如 `{"type": "text", "data": {"text": s}}`）
- Produces: `TestPublishNotifications`（Task 2 的实现必须使其中 2 个用例由红转绿，`test_disabled_sends_nothing` 在现状即绿——它锁住「关=双静默」不被本次实现破坏）

- [ ] **Step 1: 头部补 import**

在 `test/test_weekly_report.py` 的 `from core.base import TimedHeartbeatPlugin` 改为：

```python
from core.base import BOT_QQ, TimedHeartbeatPlugin
```

- [ ] **Step 2: 既有两个测试类加 emit_event 守卫**

默认值翻开后，`TestTriggerWiring`（走 `handle()`）与 `TestImmortalInReport`（直调 `_generate_week`）都会进通知块调真实 `emit_event`。两个类的 `setUp` 末尾各加：

```python
        self._emit = patch.object(weekly_report, "emit_event")
        self._emit.start()
```

两个类的 `tearDown` 开头各加：

```python
        self._emit.stop()
```

（`patch` 与 `patch.object` 均已在该文件 import。）

- [ ] **Step 3: 文件末尾追加 TestPublishNotifications**

```python
class TestPublishNotifications(unittest.TestCase):
    """周报出版通知（2026-08-31 需求）：开关开启时群消息 + 时间线事件
    （actor=bot 本体、站内相对 target_url、dedup_key=weekly_report:<week_key>）；
    关闭时双静默；幂等跳过不重发。"""

    def setUp(self):
        mlog = MessageLogManager()
        mlog.cur.execute("DELETE FROM messages")
        mlog.insert(int(GROUP_ID), 10001, 1, EARLIEST, "功能上线当晚的消息")
        mlog.insert(int(GROUP_ID), 10001, 2, "2026-08-20 12:00:00", "结算周内的消息")
        mlog.conn.commit()
        mlog.close()

        weekly_report._boot_checked = True
        self.plugin = WeeklyReportPlugin(make_group_message("meta"))
        self.plugin.api = MockApiWrapper(make_group_message("meta"))
        self.db = self.plugin.dbmanager
        self.db.cur.execute("DELETE FROM weekly_reports")
        self.db.conn.commit()

    def tearDown(self):
        self.db.cur.execute("DELETE FROM weekly_reports")
        self.db.conn.commit()
        weekly_report._boot_checked = True

    def test_enabled_notifies_group_and_timeline(self):
        with patch.object(weekly_report, "WEEKLY_NOTIFY_ENABLED", True), \
             patch.object(weekly_report, "emit_event") as m_emit:
            self.plugin._generate_week("2026-08-17 08:00:00", "2026-08-24 08:00:00")

        # 群通知：一条，含期号与链接
        self.assertEqual(len(self.plugin.api.sent_messages), 1)
        sent = self.plugin.api.sent_messages[0][1][0]["data"]["text"]
        self.assertIn("第 1 期《小埃周报》已出版", sent)
        self.assertIn("weekly/2026-08-17", sent)

        # 时间线事件：actor=bot，站内相对 target_url，每期一条 dedup_key
        m_emit.assert_called_once()
        kw = m_emit.call_args.kwargs
        self.assertEqual(kw["source"], "weekly_report")
        self.assertEqual(kw["actor_id"], BOT_QQ)
        self.assertEqual(kw["actor_qq"], BOT_QQ)
        self.assertEqual(kw["title"], "第 1 期《小埃周报》已出版")
        self.assertIn("条消息", kw["description"])
        self.assertEqual(kw["target_url"], "/weekly/2026-08-17")
        self.assertEqual(kw["dedup_key"], "weekly_report:2026-08-17")

    def test_disabled_sends_nothing(self):
        with patch.object(weekly_report, "WEEKLY_NOTIFY_ENABLED", False), \
             patch.object(weekly_report, "emit_event") as m_emit:
            self.plugin._generate_week("2026-08-17 08:00:00", "2026-08-24 08:00:00")
        self.assertEqual(self.plugin.api.sent_messages, [])
        m_emit.assert_not_called()

    def test_idempotent_skip_does_not_renotify(self):
        with patch.object(weekly_report, "WEEKLY_NOTIFY_ENABLED", True), \
             patch.object(weekly_report, "emit_event") as m_emit:
            self.plugin._generate_week("2026-08-17 08:00:00", "2026-08-24 08:00:00")
            self.plugin._generate_week("2026-08-17 08:00:00", "2026-08-24 08:00:00")
        self.assertEqual(len(self.plugin.api.sent_messages), 1)
        m_emit.assert_called_once()
```

- [ ] **Step 4: 跑测试确认预期红**

Run: `python -m pytest test/test_weekly_report.py -q`
Expected: `test_enabled_notifies_group_and_timeline` **FAIL**（`emit_event` 在 plugin 命名空间不存在 → `patch.object(weekly_report, "emit_event")` 直接 `AttributeError`）；`test_disabled_sends_nothing` PASS；`test_idempotent_skip_does_not_renotify` FAIL（同上）。其余既有用例 PASS（Step 2 守卫已生效——若守卫漏加，此处会现 10s 级卡顿，即信号）。

### Task 2: 实现（转绿）

**Files:**
- Modify: `core/config.py:45`（默认值）
- Modify: `plugins/weekly_report/__init__.py`（import + 通知块）

**Interfaces:**
- Consumes: `core.timeline_client.emit_event(source, actor_id, actor_qq=None, title="", description=None, target_url=None, target_type="url", data=None, dedup_key=None)`；`core.base.BOT_QQ = "3915014383"`（str）
- Produces: `plugins.weekly_report.emit_event` / `plugins.weekly_report.WEEKLY_NOTIFY_ENABLED`（模块级名字，供测试 patch）

- [ ] **Step 1: config 默认值翻转**

`core/config.py:45`：

```python
WEEKLY_NOTIFY_ENABLED = os.environ.get("BOTERO_WEEKLY_NOTIFY", "1") == "1"
```

- [ ] **Step 2: 插件 import**

`plugins/weekly_report/__init__.py` 第 10-15 行 import 区：

```python
from core.base import BOT_QQ, TimedHeartbeatPlugin
from core.config import GROUP_ID, WEB_BASE_URL, WEEKLY_NOTIFY_ENABLED
from core.cq import text
from core.timeline_client import emit_event
```

（其余行不动。）

- [ ] **Step 3: 通知块追加时间线事件**

`_generate_week` 末尾（现 145-148 行）整块替换为：

```python
        if WEEKLY_NOTIFY_ENABLED:
            issue = data["period"]["issue"]
            url = f"{WEB_BASE_URL}/weekly/{week_key}"
            self.api.send_msg(text(f"📰 第 {issue} 期《小埃周报》已出版\n{url}"))
            emit_event(
                source="weekly_report",
                actor_id=BOT_QQ,
                actor_qq=BOT_QQ,
                title=f"第 {issue} 期《小埃周报》已出版",
                description=(
                    f"本周 {data['period']['total_messages']} 条消息 · "
                    f"{data['period']['total_chars']} 字"
                ),
                target_url=f"/weekly/{week_key}",
                dedup_key=f"weekly_report:{week_key}",
            )
```

要点：`emit_event` best-effort 不抛出，不加 try/except；`target_url` 用站内相对路径（协议 §`target.url`：以 `/` 开头即可渲染「>>详情」）；dedup_key 每期一条，幂等跳过天然不重发，若行被删后补偿重生成，接收方按同 key 静默去重。

- [ ] **Step 4: 跑测试确认全绿**

Run: `python -m pytest test/test_weekly_report.py -q`
Expected: 全部 PASS（含 Task 1 新增 3 用例与既有全部用例，且无 10s 级卡顿）。

### Task 3: 文档同步 + 提交

**Files:**
- Modify: `scripts/botero.env:18`
- Modify: `specs/timeline-protocol.md`（§`source` 字段说明的注册列表 + §已注册 source 表）
- Modify: `kb/OPERATIONS.md:37`、`docs/web-apps-deployment.md:119`、`kb/PLUGIN_CATALOG.md:62`（`weekly_report` 行）
- Modify: `CHANGELOG.md`（`[1.29.0]` 节）、`core/config.py::BOTERO_VERSION`

**Interfaces:**
- Consumes: Task 2 的最终行为
- Produces: 无（文档收尾）

- [ ] **Step 1: botero.env 注释更新**

第 18 行 `# BOTERO_WEEKLY_NOTIFY=0` 替换为：

```bash
# 周报出版通知（群消息 + 时间线事件），默认开启；置 0 整体关闭
# BOTERO_WEEKLY_NOTIFY=0
```

（保持注释态：默认走代码里的 `1`，需要关闭时取消注释。生产 systemd `EnvironmentFile` 读本文件，无需其它动作。）

- [ ] **Step 2: timeline-protocol.md 注册 source**

两处：

① §事件结构 `source` 字段行（约 37 行）的注册列表追加：

> v1 注册：`checkin`、`forum`、`tools`、`weekly_report`；`quest`、`title` 已停用

② §「已注册 source 与 dedup_key 约定」表（约 115-118 行）追加一行：

```markdown
| `weekly_report` | `plugins/weekly_report` | 周报出版（每周一 08:00 生成后，actor=bot 本体） | `weekly_report:<week_key>`（每期一条；生成幂等不重发，行被删后补偿重生成的重复提交由接收方按 dedup_key 静默忽略） |
```

- [ ] **Step 3: 运维文档与插件目录**

- `kb/OPERATIONS.md:37`：句尾「`BOTERO_WEEKLY_NOTIFY`（`1` 开启周报群通知，默认 `0` 关闭；首周测试期保持关闭）」改为「`BOTERO_WEEKLY_NOTIFY`（周报出版通知，默认 `1` 开启，群消息 + 时间线事件同开同关；置 `0` 关闭）」
- `docs/web-apps-deployment.md:119`：`| BOTERO_WEEKLY_NOTIFY | 1 | 周报出版通知开关（群消息 + 时间线事件；置 0 关闭） |`（默认值列 `0` → `1`）
- `kb/PLUGIN_CATALOG.md:62`（#47 `weekly_report` 行）：「聚合消息日志与玩法数据，生成群周报并归档（首周通知默认关闭；仅日志覆盖到的完整周出报，启动补漏不越过日志起点）」改为「聚合消息日志与玩法数据，生成群周报并归档；出版后默认群通知 + 时间线事件（`BOTERO_WEEKLY_NOTIFY` 可关）；仅日志覆盖到的完整周出报，启动补漏不越过日志起点」

- [ ] **Step 4: CHANGELOG + 版本号**

- `core/config.py::BOTERO_VERSION`：`"1.28.1"` → `"1.29.0"`
- `CHANGELOG.md` 在 `## [未发布]` 之下、`## [1.28.1]` 之上插入：

```markdown
## [1.29.0] - 2026-08-31

### 新增

- **周报出版通知上线**：`BOTERO_WEEKLY_NOTIFY` 默认值从 `0` 改为 `1`——每周一 08:00 周报生成后，默认在群里发「第 N 期《小埃周报》已出版 + 链接」，并向社区时间线发一条新事件（actor 为小埃同学，卡片导读显示本周总消息数与总字数，「>>详情」跳转当期周报）；两类通知同开同关，置 `BOTERO_WEEKLY_NOTIFY=0` 可整体关闭
```

- [ ] **Step 5: 全量回归**

Run: `python -m pytest -q`
Expected: 全部 PASS，无 10s 级卡顿用例。

- [ ] **Step 6: 提交（代码 + 测试 + 文档同一 commit）**

```bash
git add core/config.py plugins/weekly_report/__init__.py test/test_weekly_report.py \
  scripts/botero.env specs/timeline-protocol.md kb/OPERATIONS.md \
  docs/web-apps-deployment.md kb/PLUGIN_CATALOG.md CHANGELOG.md
git commit -m "feat(周报): 出版通知默认开启并新增时间线事件"
```

## Self-Review 结论

- **需求覆盖**：①默认开启（Task 2 Step 1）②群+时间线双通知同开关（Task 2 Step 3）③actor=bot（Task 2 Step 3 / Task 1 断言）④卡片=标题+导读+站内跳转、不带图（Task 2 Step 3）⑤不加入口（Global Constraints 声明 `entries.json` 不动，无任务触碰它）✓
- **协议合规**：新 source 已注册 + dedup_key 约定 + 同 commit（Task 3 Step 2）✓
- **类型一致**：`BOT_QQ` str、`week_key` str、`emit_event` 全 kwargs 调用与 `m_emit.call_args.kwargs` 断言一致 ✓
- **风险**：既有用例漏加 `emit_event` 守卫会真实发起 HTTP（5s×2 重试）——Task 1 Step 2 强制、Task 1 Step 4 与 Task 3 Step 5 双重验证 ✓
