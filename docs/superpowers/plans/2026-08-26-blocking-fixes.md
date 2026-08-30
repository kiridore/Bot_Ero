# BLOCKING 缺陷修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复全量审查发现的 4 个 BLOCKING 缺陷：时间线存储型 XSS、积分并发丢失、补卡无权限/未来日期作弊、谁是卧底退出崩溃。

**Architecture:** 全部为根因修复——XSS 在 `substitute()` 单点转义；积分在 `PointsManager` 层加原子 `spend()` 并让 `add_user_point` 委托已有的原子 `adjust()`（18 个调用点一次性受益）；补卡权限/日期在 `remedy_checkin.handle` 入口加守卫（与 kb/QUICK_REFERENCE.md:140 已声明的"管理员"语义对齐，属代码补齐而非行为变更）；卧底退出把转移文案移回房主分支。

**Tech Stack:** Python 3 (stdlib sqlite3/threading/unittest), 原生 JS (无框架), pytest + node 最小 DOM stub（沿用 `test/helper.py` 与 `test/test_timeline_render.js` 既有模式）。

**Spec:** 审查报告见会话记录；文档基线：AGENTS.md 硬约束、kb/GAMEPLAY.md:44-46（补卡数值/管理员语义）、kb/QUICK_REFERENCE.md:140（超级补卡=群管理员）。

## Global Constraints

- bot 进程禁止 async/await；无 f-string SQL（一律 `?` 参数化）。
- Commit 消息 MUST 中文 + Conventional Commits；一个 commit = 一个逻辑变更（代码 + 行为测试 + CHANGELOG + `core/config.py::BOTERO_VERSION` bump 同 commit）。
- 每个 commit 依次 bump patch 版本：1.24.1 → 1.24.2（Task 1）→ 1.24.3（Task 2）→ 1.24.4（Task 3）→ 1.24.5（Task 4）。CHANGELOG 顶部新增 `[x.y.z]` 节（插在 `## [未发布]` 之下），版本号与 `BOTERO_VERSION` 严格一致。
- 测试绝不触碰真实 `data.db`/`server_data`：新 Python 测试用独立 `/tmp/*.db` + `init_schema`（照抄 `test/test_lottery_bulk.py` 模式）；Python 测试导入插件前必须先 `import test.helper`（其桩掉 `core.api.WS_APP`）。
- 工作目录：`F:/Coding/Python/project/BotEro`。

---

### Task 1: 时间线标题/描述 XSS 转义（webapp/static/timeline.js）

**Files:**
- Modify: `webapp/static/timeline.js:104-111`（`substitute()`）
- Test: `test/test_timeline_render.js`（复用既有 DOM stub，不新建文件）

**Interfaces:**
- Consumes: 同文件已存在的 `esc()`（timeline.js:34-38，转义 `&<>"'`）。
- Produces: `substitute(text, users)` 行为不变（`{id:N}` 占位符仍替换为 span），但输入文本先整体转义。下游 `renderEvent` 的 `title.innerHTML` / `desc.innerHTML` 调用点无需改动。

- [ ] **Step 1: 写失败测试**

在 `test/test_timeline_render.js` 第 6 节（点击 pill 拉新事件）：把 `eNew1` 的 title 改为含 XSS 载荷，并在 prepend 断言块之后加转义断言。

找到（约 251 行）：
```js
  const eNew1 = {
    seq: 6, id: "checkin:new1", source: "checkin", received_at: "2026-08-10 15:00:00", unread: true,
    actor: { id: "123456", qq: "123456", display_name: "小明", avatar_url: "" },
    target: null, title: "新事件一", description: null, data: null,
  };
```
改为：
```js
  const eNew1 = {
    seq: 6, id: "checkin:new1", source: "checkin", received_at: "2026-08-10 15:00:00", unread: true,
    actor: { id: "123456", qq: "123456", display_name: "小明", avatar_url: "" },
    target: null,
    title: '新事件一<img src=x onerror=alert(1)>"&', description: "<b>加粗描述</b>", data: null,
  };
```
在第 6 节断言块末尾（`check("多页拉取次数", ...)` 之后）追加：
```js
  const xssCard = newFrag.children[1]; // eNew1 的卡片
  const xssTitle = xssCard.children.find((c) => c.className === "tl-title");
  const xssDesc = xssCard.children.find((c) => c.className === "tl-desc");
  check("标题 XSS 已转义", xssTitle._html.includes("&lt;img") && !xssTitle._html.includes("<img "));
  check("描述 XSS 已转义", xssDesc._html.includes("&lt;b&gt;") && !xssDesc._html.includes("<b>"));
  check("引号转义", xssTitle._html.includes("&quot;&amp;"));
```

- [ ] **Step 2: 运行测试确认失败**

Run: `node test/test_timeline_render.js`
Expected: `FAIL - 标题 XSS 已转义` 等 3 条 FAIL（载荷原样进 innerHTML），其余 ok；进程退出码非 0（文件末尾已有 `process.exit(fail ? 1 : 0)`）。

- [ ] **Step 3: 最小实现**

`webapp/static/timeline.js` `substitute()`（104-111 行），只改第一行：

```js
  // 前
  function substitute(text, users) {
    return text.replace(/\{id:(\d+)\}/g, function (_, uid) {
  // 后
  function substitute(text, users) {
    return esc(text).replace(/\{id:(\d+)\}/g, function (_, uid) {
```

原理：`esc` 只转义 `&<>"'`，`{id:123456}` 不含这些字符，故占位符正则匹配不受影响；`u.name` 原本就已单独 `esc()`。

- [ ] **Step 4: 运行测试确认通过**

Run: `node test/test_timeline_render.js && python test/test_dom_render_suites.py`
Expected: 全部 ok（含原有占位符替换、未绑定降级等用例），退出码 0。

- [ ] **Step 5: Commit（版本 1.24.2）**

1. `core/config.py:10`：`BOTERO_VERSION = "1.24.1"` → `"1.24.2"`。
2. `CHANGELOG.md` 在 `## [未发布]` 节之后插入：

```markdown
## [1.24.2] - 2026-08-26

### 修复

- **时间线 XSS 漏洞**：主页时间线卡片对标题/描述先整体 HTML 转义再替换用户占位符——此前论坛帖子标题、工具箱等含用户原文的事件文案可携带 `<img onerror>` 类脚本在全员主页执行（存储型 XSS）；补充 DOM 渲染回归用例
```

```bash
git add webapp/static/timeline.js test/test_timeline_render.js CHANGELOG.md core/config.py
git commit -m "fix(网页): 时间线标题与描述整体转义修复存储型XSS"
```

---

### Task 2: 积分变动原子化（core/db/points.py + core/utils.py + lottery + remedy_checkin 扣费点）

**Files:**
- Modify: `core/db/points.py`（新增 `spend()` 方法）
- Modify: `core/utils.py:32-35`（`add_user_point` 委托 `adjust`）
- Modify: `plugins/lottery/__init__.py:51-64`（check+扣费改 `spend`）
- Modify: `plugins/remedy_checkin/__init__.py:53-61,100-106`（同上）
- Test: 新建 `test/test_points_atomic.py`

**Interfaces:**
- Consumes: 已存在 `PointsManager.adjust(user_id, delta, commit=True)`（原子 `UPDATE points=points+?`）。
- Produces: `PointsManager.spend(user_id, cost: int, commit: bool = True) -> bool`——条件原子扣减，余额不足返回 False 且不改动；`add_user_point(db, user_id, offer)` 签名不变（18 个调用点零改动）。

- [ ] **Step 1: 写失败测试**

新建 `test/test_points_atomic.py`：

```python
"""积分原子性回归：adjust/spend 单语句原子、并发不丢更新、余额不可为负。
运行: pytest test/test_points_atomic.py
"""
import os
import sys
import sqlite3
import threading
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import test.helper  # noqa: F401  桩掉 core.api.WS_APP，必须在导入插件前执行

from core.db._base import init_schema
from core.db.points import PointsManager
from core.utils import add_user_point

DB_PATH = "/tmp/test_points_atomic.db"


class _Db:
    """add_user_point 只用 db.points，包一层即可独立于完整 DbManager。"""
    def __init__(self, pm):
        self.points = pm


class TestPointsAtomic(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.pm = PointsManager(self.conn)
        self.db = _Db(self.pm)

    def tearDown(self):
        self.conn.close()

    def test_spend_conditional(self):
        self.pm.set("10001", 3)
        self.assertTrue(self.pm.spend("10001", 2))
        self.assertFalse(self.pm.spend("10001", 2))  # 余额 1 不足
        self.assertEqual(self.pm.get("10001"), 1)    # 失败不改动

    def test_spend_missing_row_is_insufficient(self):
        self.assertFalse(self.pm.spend("99999", 1))  # 无行 = 0 分，拒绝而非报错

    def test_add_user_point_is_atomic_under_threads(self):
        # add_user_point 必须是单语句原子：20 线程各 +10×10，最终严格等于 200
        add_user_point(self.db, "10002", 0)
        conns = [sqlite3.connect(DB_PATH) for _ in range(20)]
        for c in conns:
            c.execute("PRAGMA busy_timeout=5000")
        dbs = [_Db(PointsManager(c)) for c in conns]

        def worker(db):
            for _ in range(10):
                add_user_point(db, "10002", 10)

        threads = [threading.Thread(target=worker, args=(db,)) for db in dbs]
        [t.start() for t in threads]
        [t.join() for t in threads]
        [c.close() for c in conns]
        self.assertEqual(self.pm.get("10002"), 200)

    def test_concurrent_spend_never_negative(self):
        # 并发 50 次 spend(1)，余额 10：成功次数必须恰好 10，余额 0
        add_user_point(self.db, "10003", 10)
        conns = [sqlite3.connect(DB_PATH) for _ in range(10)]
        for c in conns:
            c.execute("PRAGMA busy_timeout=5000")
        pms = [PointsManager(c) for c in conns]
        results = []

        def worker(pm):
            for _ in range(5):
                results.append(pm.spend("10003", 1))

        threads = [threading.Thread(target=worker, args=(pm,)) for pm in pms]
        [t.start() for t in threads]
        [t.join() for t in threads]
        [c.close() for c in conns]
        self.assertEqual(results.count(True), 10)
        self.assertEqual(self.pm.get("10003"), 0)


if __name__ == "__main__":
    unittest.main()
```

（spend/get 返回均为 int/bool，与源码一致，无需调整。）

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest test/test_points_atomic.py -v`
Expected: `test_spend_conditional`、`test_spend_missing_row_is_insufficient`、`test_concurrent_spend_never_negative` FAIL（`PointsManager` 无 `spend`，AttributeError）；`test_add_user_point_is_atomic_under_threads` 可能 FAIL（get+set 丢更新，最终 < 200）或因异常 FAIL。

- [ ] **Step 3: 最小实现**

`core/db/points.py` 在 `adjust()` 之后新增：

```python
    def spend(self, user_id, cost: int, commit: bool = True) -> bool:
        """条件原子扣减：余额足够则扣并返回 True，否则不动返回 False。"""
        user_id = str(user_id)
        cost = int(cost)
        self.cur.execute("""
            UPDATE user_assets SET points = points - ?
            WHERE user_id = ? AND points >= ?
        """, (cost, user_id, cost))
        if commit:
            self.conn.commit()
        return self.cur.rowcount > 0
```

`core/utils.py:32-35` 改为：

```python
def add_user_point(db:DbManager, user_id:int, offer:int):
        # 单语句原子加减，避免并发事件线程 get+set 互相覆盖
        db.points.adjust(user_id, offer)
```

`plugins/lottery/__init__.py` `_perform_single_draw`（51-64 行）：

```python
        # 前
        points = self.dbmanager.points.get(user_id)
        payment_exempt = False
        if not free_daily:
            rem = self.dbmanager.shop.waiver_remaining(user_id)
            if rem > 0:
                if random.random() < 0.3:
                    payment_exempt = True
                if not payment_exempt and points < self.COST:
                    return {"ok": False, "points": points}
                self.dbmanager.shop.pop_waiver(user_id)
            else:
                if points < self.COST:
                    return {"ok": False, "points": points}
            if not payment_exempt:
                utils.add_user_point(self.dbmanager, user_id, -self.COST)
                self.dbmanager.lottery.add_spent(user_id, self.COST)
        # 后
        payment_exempt = False
        if not free_daily:
            rem = self.dbmanager.shop.waiver_remaining(user_id)
            if rem > 0:
                if random.random() < 0.3:
                    payment_exempt = True
                if not payment_exempt and not self.dbmanager.points.spend(user_id, self.COST):
                    return {"ok": False, "points": self.dbmanager.points.get(user_id)}
                self.dbmanager.shop.pop_waiver(user_id)
            else:
                if not self.dbmanager.points.spend(user_id, self.COST):
                    return {"ok": False, "points": self.dbmanager.points.get(user_id)}
            if not payment_exempt:
                self.dbmanager.lottery.add_spent(user_id, self.COST)
```

`plugins/remedy_checkin/__init__.py` 周补卡（53-61 行）：

```python
        # 前
                points = self.dbmanager.points.get(user_id)
                if points >= cost or super_mode:
                    success_msg = "{}-{}原来没有打卡吗？真拿你没办法……\n*涂写*好了帮你补上了喵，一共消费{}点数，谢谢惠顾喵"
                    self.api.send_msg(text(success_msg.format(start.split(" ")[0], end.split(" ")[0], cost)))
                    self.dbmanager.checkin.remedy_week(user_id, start.split(" ")[0])
                    if not super_mode:
                        utils.add_user_point(self.dbmanager, user_id, cost * -1)
                        self.dbmanager.checkin.add_remedy_used(dt.year, user_id, 1)
                else:
                    self.api.send_msg(text("补卡当然不是免费的喵!\n你现在现在点数是：{}\n补卡需要{}点喵".format(points, cost)))
        # 后
                if super_mode or self.dbmanager.points.spend(user_id, cost):
                    success_msg = "{}-{}原来没有打卡吗？真拿你没办法……\n*涂写*好了帮你补上了喵，一共消费{}点数，谢谢惠顾喵"
                    self.api.send_msg(text(success_msg.format(start.split(" ")[0], end.split(" ")[0], cost)))
                    self.dbmanager.checkin.remedy_week(user_id, start.split(" ")[0])
                    if not super_mode:
                        self.dbmanager.checkin.add_remedy_used(dt.year, user_id, 1)
                else:
                    self.api.send_msg(text("补卡当然不是免费的喵!\n你现在现在点数是：{}\n补卡需要{}点喵".format(self.dbmanager.points.get(user_id), cost)))
```

同文件单日补卡（100-106 行）：

```python
        # 前
        self.dbmanager.checkin.remedy_day(user_id, self.args[0])
        utils.add_user_point(self.dbmanager, user_id, cost * -1)
        self.dbmanager.checkin.add_remedy_used(day.year, user_id, 1)
        # 后
        if not self.dbmanager.points.spend(user_id, cost):
            self.api.send_msg(text("补卡当然不是免费的喵!\n你现在点数是：{}\n单日补卡需要{}点喵".format(self.dbmanager.points.get(user_id), cost)))
            return
        self.dbmanager.checkin.remedy_day(user_id, self.args[0])
        self.dbmanager.checkin.add_remedy_used(day.year, user_id, 1)
```

（插入位置：在原 `if points < cost: ...return` 块被删除后，紧接 `_check_remedy_limit` 之后。）

- [ ] **Step 4: 运行测试确认通过（含全量回归）**

Run: `python -m pytest test/test_points_atomic.py test/test_lottery_bulk.py -v && python -m pytest`
Expected: 新用例全 PASS；全量回归无失败（lottery/remedy/shop 相关既有用例行为不变——免费首抽、豁免券、成功消息文案均未改）。

- [ ] **Step 5: Commit（版本 1.24.3）**

1. `core/config.py`：`"1.24.2"` → `"1.24.3"`。
2. `CHANGELOG.md` 插入：

```markdown
## [1.24.3] - 2026-08-26

### 修复

- **积分并发丢失更新**：`add_user_point` 改为单条原子 SQL 加减（原"读-改-写"在并发事件线程下互相覆盖，积分会凭空增多或丢失）；积分管理器新增 `spend` 条件原子扣减，抽奖与补卡付费路径改用它——余额校验与扣费一步完成，并发下不可能扣成负数；补充并发回归用例
```

```bash
git add core/db/points.py core/utils.py plugins/lottery/__init__.py plugins/remedy_checkin/__init__.py test/test_points_atomic.py CHANGELOG.md core/config.py
git commit -m "fix(经济): 积分加减与扣费原子化修复并发丢失"
```

---

### Task 3: 补卡权限与日期校验（plugins/remedy_checkin）

**Files:**
- Modify: `plugins/remedy_checkin/__init__.py`（`handle` 与 `handle_single_day_remedy` 加守卫；基于 Task 2 已应用的代码）
- Test: 新建 `test/test_remedy_checkin.py`

**Interfaces:**
- Consumes: `CommandPlugin.admin_user()`（core/base.py:105，super_user 或群 admin/owner——与 kb/QUICK_REFERENCE.md:140 "群管理员" 语义一致）；`PointsManager.spend`（Task 2）。
- Produces: 无新接口。行为契约——①`/超级补卡` 仅管理员（免扣分/免额度保留给管理员）；②`/补卡 <日期> <uid>` 指定他人仅管理员；③周补卡目标周必须已结束（`end <= now`），单日补卡目标日窗口必须已结束（`次日 08:00 <= now`）。

- [ ] **Step 1: 写失败测试**

新建 `test/test_remedy_checkin.py`：

```python
"""补卡插件权限与日期校验回归。
运行: pytest test/test_remedy_checkin.py
"""
import os
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import test.helper  # noqa: F401

from core.event import Event
from core.db._base import init_schema
from core.db.checkin import CheckinManager
from core.db.points import PointsManager
from plugins.remedy_checkin import RemedyCheckinPlugin
from test.helper import MockApiWrapper

DB_PATH = "/tmp/test_remedy_checkin.db"

PAST_MONDAY = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")   # 上上周内某天
FUTURE_DATE = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")   # 两周后


def _raw(text_body, user_id=123456, role="member"):
    return {
        "post_type": "message", "message_type": "group", "user_id": user_id,
        "group_id": 296470819,
        "message": [{"type": "text", "data": {"text": text_body}}],
        "sender": {"user_id": user_id, "nickname": "测试用户", "role": role},
        "time": 0, "message_id": -1,
    }


class _Db:
    def __init__(self, conn):
        self.checkin = CheckinManager(conn)
        self.points = PointsManager(conn)


def _last_text(plugin):
    assert plugin.api.sent_messages, "无消息发送"
    return "".join(seg["data"].get("text", "") for seg in plugin.api.sent_messages[-1][1]
                   if seg["type"] == "text")


class TestRemedyGuard(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)

    def tearDown(self):
        self.conn.close()

    def _run(self, text_body, user_id=123456, role="member"):
        plugin = RemedyCheckinPlugin.__new__(RemedyCheckinPlugin)
        plugin.bot_event = Event(_raw(text_body, user_id, role))
        plugin.api = MockApiWrapper(_raw(text_body, user_id, role))
        plugin.dbmanager = self.db
        plugin.match("message")
        plugin.handle()
        return plugin

    def test_super_remedy_denied_for_member(self):
        plugin = self._run(f"/超级补卡 {PAST_MONDAY}")
        self.assertIn("管理员", _last_text(plugin))
        self.assertEqual(self.db.checkin.search_user_range(123456, "2000-01-01 00:00:00", "2100-01-01 00:00:00"), [])

    def test_remedy_for_other_denied_for_member(self):
        self.db.points.set("123456", 10)
        plugin = self._run(f"/补卡 {PAST_MONDAY} 999999")
        self.assertIn("管理员", _last_text(plugin))
        self.assertEqual(self.db.checkin.remedy_used(datetime.now().year, "999999"), 0)

    def test_future_week_rejected(self):
        self.db.points.set("123456", 10)
        plugin = self._run(f"/补卡 {FUTURE_DATE}")
        self.assertIn("还没过完", _last_text(plugin))
        rows = self.db.checkin.search_user_range(123456, "2000-01-01 00:00:00", "2100-01-01 00:00:00")
        self.assertEqual(rows, [])

    def test_future_single_day_rejected(self):
        self.db.points.set("123456", 10)
        plugin = self._run(f"/单日补卡 {FUTURE_DATE}")
        self.assertIn("还没过完", _last_text(plugin))
        rows = self.db.checkin.search_user_range(123456, "2000-01-01 00:00:00", "2100-01-01 00:00:00")
        self.assertEqual(rows, [])

    def test_admin_super_remedy_for_other_succeeds_free(self):
        self.db.points.set("777777", 0)  # 目标用户 0 分也能被管理员免费补
        plugin = self._run(f"/超级补卡 {PAST_MONDAY} 777777", user_id=42, role="owner")
        self.assertIn("补上了喵", _last_text(plugin))
        self.assertEqual(self.db.points.get("777777"), 0)  # 免扣分
        self.assertEqual(self.db.checkin.remedy_used(datetime.now().year, "777777"), 0)  # 免额度

    def test_member_past_week_succeeds_paid(self):
        self.db.points.set("123456", 10)
        plugin = self._run(f"/补卡 {PAST_MONDAY}")
        self.assertIn("补上了喵", _last_text(plugin))
        self.assertEqual(self.db.points.get("123456"), 6)  # 10 - 4
        self.assertEqual(self.db.checkin.remedy_used(datetime.now().year, "123456"), 1)


if __name__ == "__main__":
    unittest.main()
```

（`search_user_range` / `remedy_used` 返回形态若与断言不符——如返回 list of tuple——执行时以实际 API 为准微调断言，测试意图不变：补卡未发生、额度未消耗。）

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest test/test_remedy_checkin.py -v`
Expected: 前 4 个用例 FAIL（无守卫，超级补卡/替他人/未来日期全部放行）；后 2 个 PASS（既有正常路径）。

- [ ] **Step 3: 最小实现**

`plugins/remedy_checkin/__init__.py` `handle()` 开头（基于 Task 2 后的代码）：

```python
        # 前
        super_mode = self.cmd in ("/超级补卡", "/超級補卡")

        if self.cmd in ("/单日补卡", "/單日補卡"):
        # 后
        super_mode = self.cmd in ("/超级补卡", "/超級補卡")
        if super_mode and not self.admin_user():
            self.api.send_msg(text("超级补卡是管理员指令喵！"))
            return

        if self.cmd in ("/单日补卡", "/單日補卡"):
```

指定他人处（原 46-48 行）：

```python
        # 前
            user_id = self.bot_event.user_id
            if len(self.args) > 1:
                user_id = self.args[1] # 特殊补卡指令可以给其他人补卡
        # 后
            user_id = self.bot_event.user_id
            if len(self.args) > 1:
                if not self.admin_user():
                    self.api.send_msg(text("给别人补卡是管理员指令喵！"))
                    return
                user_id = self.args[1] # 管理员可以给其他人补卡
```

周界校验（紧接 `start, end = get_monday_to_monday(dt)` 与 `rows = ...` 之间插入）：

```python
            start, end = get_monday_to_monday(dt)
            if datetime.strptime(end, "%Y-%m-%d %H:%M:%S") > datetime.now():
                self.api.send_msg(text("{}-{}这一周还没过完，只能补已经结束的一周喵".format(start.split(" ")[0], end.split(" ")[0])))
                return
            rows = self.dbmanager.checkin.search_user_range(user_id, start, end)
```

`handle_single_day_remedy()` 中（`day_end` 计算后、查库前插入）：

```python
        day_start = day.strftime("%Y-%m-%d 08:00:00")
        day_end = (day + timedelta(days=1)).strftime("%Y-%m-%d 08:00:00")
        if datetime.strptime(day_end, "%Y-%m-%d %H:%M:%S") > datetime.now():
            self.api.send_msg(text("{}这一天还没过完，不能补喵".format(self.args[0])))
            return
```

- [ ] **Step 4: 运行测试确认通过（含全量回归）**

Run: `python -m pytest test/test_remedy_checkin.py -v && python -m pytest`
Expected: 全 PASS；全量回归无失败。

- [ ] **Step 5: Commit（版本 1.24.4）**

1. `core/config.py`：`"1.24.3"` → `"1.24.4"`。
2. `CHANGELOG.md` 插入：

```markdown
## [1.24.4] - 2026-08-26

### 修复

- **补卡权限与日期漏洞**：`/超级补卡`（免积分、免年度额度）与替他人补卡此前无任何权限校验，任何群员可白嫖或消耗他人积分；现两者均要求群管理员（与菜单及文档既有声明一致）。同时补卡目标必须为已结束的周/日——此前可对当前周或未来日期补卡，`remedy_week` 会预写未来 7 天打卡记录，白嫖连续打卡与周常
```

```bash
git add plugins/remedy_checkin/__init__.py test/test_remedy_checkin.py CHANGELOG.md core/config.py
git commit -m "fix(补卡): 超级补卡与替他人补卡加管理员校验并禁止补未来日期"
```

---

### Task 4: 谁是卧底 waiting 阶段退出崩溃（plugins/who_is_spy/room.py）

**Files:**
- Modify: `plugins/who_is_spy/room.py:98-110`（`remove_player`）
- Test: 新建 `test/test_who_is_spy_room.py`

**Interfaces:**
- Consumes: `context.game_rooms` / `context.game_lock`（core/context.py:43-44）；房间 dict 结构 `{"phase", "creator_id", "players": {uid: {"alias", "alive"}}}`。
- Produces: `remove_player(room_id: str, user_id: int) -> str` 契约不变——waiting 阶段非房主退出返回 `"已退出房间 {room_id}"`（不再抛 UnboundLocalError）；房主退出仍转移并返回含 `"房主已转移给 {alias}"`。

- [ ] **Step 1: 写失败测试**

新建 `test/test_who_is_spy_room.py`：

```python
"""谁是卧底房间退出回归：waiting 阶段非房主退出不崩溃。
运行: pytest test/test_who_is_spy_room.py
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import test.helper  # noqa: F401

import core.context as context
from plugins.who_is_spy import room


def _make_room(room_id):
    context.game_rooms[room_id] = {
        "phase": "waiting",
        "creator_id": "111",
        "players": {
            "111": {"alias": "1号", "alive": True},
            "222": {"alias": "2号", "alive": True},
        },
    }


class TestRemovePlayer(unittest.TestCase):
    def tearDown(self):
        context.game_rooms.clear()

    def test_member_exit_waiting_no_crash(self):
        _make_room("T001")
        msg = room.remove_player("T001", 222)  # 修复前此处 UnboundLocalError
        self.assertEqual(msg, "已退出房间 T001")
        self.assertIn("111", context.game_rooms["T001"]["players"])

    def test_creator_exit_transfers_room(self):
        _make_room("T002")
        msg = room.remove_player("T002", 111)
        self.assertIn("房主已转移给 1号", msg)
        self.assertEqual(context.game_rooms["T002"]["creator_id"], "222")

    def test_last_player_disbands(self):
        _make_room("T003")
        room.remove_player("T003", 222)
        msg = room.remove_player("T003", 111)
        self.assertEqual(msg, "房间已解散")
        self.assertNotIn("T003", context.game_rooms)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest test/test_who_is_spy_room.py -v`
Expected: `test_member_exit_waiting_no_crash` ERROR/FAIL（UnboundLocalError: local variable 'old_alias' referenced before assignment）；其余 2 个 PASS。

- [ ] **Step 3: 最小实现**

`plugins/who_is_spy/room.py` `remove_player`（98-110 行）：

```python
        # 前
            if not room["players"]:
                context.game_rooms.pop(room_id, None)
                return "房间已解散"
            if uid == room["creator_id"]:
                new_creator = list(room["players"].keys())[0]
                old_alias = room["players"][new_creator]["alias"]
                room["creator_id"] = new_creator
            return f"已退出房间 {room_id}，房主已转移给 {old_alias}"
        # 后
            if not room["players"]:
                context.game_rooms.pop(room_id, None)
                return "房间已解散"
            if uid == room["creator_id"]:
                new_creator = list(room["players"].keys())[0]
                old_alias = room["players"][new_creator]["alias"]
                room["creator_id"] = new_creator
                return f"已退出房间 {room_id}，房主已转移给 {old_alias}"
            return f"已退出房间 {room_id}"
```

- [ ] **Step 4: 运行测试确认通过（含全量回归）**

Run: `python -m pytest test/test_who_is_spy_room.py -v && python -m pytest`
Expected: 全 PASS。

- [ ] **Step 5: Commit（版本 1.24.5）**

1. `core/config.py`：`"1.24.4"` → `"1.24.5"`。
2. `CHANGELOG.md` 插入：

```markdown
## [1.24.5] - 2026-08-26

### 修复

- **谁是卧底退出房间崩溃**：等待阶段非房主退出时引用未赋值变量直接崩溃（用户无任何回复）；转移房主文案现仅在房主退出分支返回，普通成员退出正常提示
```

```bash
git add plugins/who_is_spy/room.py test/test_who_is_spy_room.py CHANGELOG.md core/config.py
git commit -m "fix(卧底): 修复等待阶段非房主退出房间的变量未赋值崩溃"
```

---

## 收尾核验

- [ ] `python -m pytest` 全量绿 + `node test/test_timeline_render.js` 绿。
- [ ] `git log --oneline -4` 为 4 个独立 fix commit，无混杂文件。
- [ ] `core/config.py::BOTERO_VERSION == "1.24.5"`，CHANGELOG 四节版本依次 1.24.2→1.24.5。

## 明确不做（对应 IMPORTANT 级，另行计划）

`PointsManager.get()` 悬挂写事务、`Echo` 取号竞态、WS 心跳、DbManager 每事件重跑 init_schema、SSRF 重定向复检等 26 项 IMPORTANT 不在本计划内；本计划的 `spend()` 顺带消除了补卡/抽奖路径对 `get()` 缺行 INSERT 的暴露。
