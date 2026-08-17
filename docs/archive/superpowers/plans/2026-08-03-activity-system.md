# 群活动系统（接龙 / 匹配下家）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增群活动系统：接龙（作品链逐人接力、每人独立计时超时跳过）与匹配下家（圆桌单环、匿名保密、全局截止）两类活动；私聊提交作品自动流转；结束后归档到 `server_data/activity_archive/` 并在 `checkin_gallery` 新增活动归档页。

**Architecture:** 数据全量落 `data.db` 两张新表（活动跨数天、`/更新` 重启进程，内存态会丢活动）；纯逻辑（环生成/链导航/超时判定）放 `plugins/activity/logic.py` 便于单测；插件包 `plugins/activity/` 内含指令插件（群聊指令 + 私聊提交）与心跳插件（meta 事件 60s 节流扫描超时/截止）；模块级辅助函数统一以 `(api, db, ...)` 传参（who_is_spy 的 `broadcast(self.api, ...)` 同款模式），两个插件类共用。归档写盘复用 trpg_session 的 `get_image_url` + `download_image` 模式，转发复用原样消息段。Web 端复用现有 FastAPI 应用的路由/静态页模式。

**Tech Stack:** Python stdlib（sqlite3 / random / json）、FastAPI（`checkin_gallery/app.py`）、vanilla JS（`checkin_gallery/static/`）。

## Global Constraints

- **无 async/await**；同步 + threading。
- **无 f-string SQL**——一律 `?` 参数化（`core/db/_base.py` 管理建表）。
- `handle()` 必须 try/except + `logger.exception()`；`match()` 不得有副作用。
- 插件间无相对导入（插件包内部 `from .logic import ...` 是包内导入，允许，参照 `who_is_spy/`）。
- 时间一律字符串 `"%Y-%m-%d %H:%M:%S"`（与 `group_alarms.fire_at` 一致）。
- 转发作品用**原样消息段**（`bot_event.message` 去命令段），不重新编码（trpg_session 合并转发同款）。
- 图片落盘命名 `img_<seq>_<n><ext>`（seq=链序/环序，n=该成员第几张图）。
- 测试：`unittest` + `test/helper.py`（MockApiWrapper / make_group_message / make_private_message），`plugin.bot_event` 必须包 `Event(raw)`（dict 无属性访问），运行 `python test/test_<name>.py`。
- 中文 Conventional Commits（`feat(活动): ...`）；git hooks 在 `.githooks`。
- 同步维护（同 commit）：`specs/plugin-catalog.md`、`specs/database.md`、`specs/web-gallery.md`、`plugins/bot_menu_text.py`、`KNOWLEDGE_BASE.md`。

---

### Task 1: 建表 + 数据访问层（ActivityManager）

**Files:**
- Modify: `core/db/_base.py`（init_schema 末尾追加两张表）
- Create: `core/db/activity.py`
- Modify: `core/database_manager.py`（注册 ActivityManager）
- Test: `test/test_activity_db.py`

**Interfaces:**
- Produces: `core/db/activity.py` 的 `ActivityManager`，构造 `ActivityManager(conn)`，方法见下。行返回 **dict**（`sqlite3.Row` → `dict`）。

**表结构（与设计文档一致）：**

```sql
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    type TEXT NOT NULL,                -- 'relay' | 'match'
    title TEXT NOT NULL,
    theme TEXT,
    status TEXT NOT NULL DEFAULT 'open',  -- open | running | finished | cancelled
    created_by TEXT NOT NULL,
    deadline TEXT,                     -- match: 'YYYY-MM-DD HH:MM:SS'
    hours_per_user REAL,               -- relay: 每人时限小时
    created_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS activity_members (
    activity_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    nickname TEXT NOT NULL,
    seq INTEGER NOT NULL DEFAULT 0,    -- relay 链序 / match 环序
    next_user_id TEXT,                 -- match: 下家
    status TEXT NOT NULL DEFAULT 'pending', -- pending|done|skipped|missed|left
    received_at TEXT,                  -- relay: 作品转交时刻（第一棒=开始通知时刻）
    submitted_at TEXT,
    content TEXT,
    images TEXT,                       -- JSON 数组
    PRIMARY KEY (activity_id, user_id)
);
```

- [ ] **Step 1: 在 `core/db/_base.py` 的 `init_schema()` 末尾（`conn.commit()` 之前）追加建表语句**（上面两段 SQL 原样插入）。

- [ ] **Step 2: 写失败测试 `test/test_activity_db.py`**

```python
"""测试活动数据访问层。
运行: python test/test_activity_db.py
"""
import os
import sys
import sqlite3
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.db.activity import ActivityManager

DB_PATH = "/tmp/test_activity.db"


class TestActivityDb(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        from core.db._base import init_schema
        init_schema(self.conn, self.conn.cursor())
        self.m = ActivityManager(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_create_and_get(self):
        aid = self.m.create_activity(296470819, "relay", "端午接龙", "粽子", "1", hours_per_user=48.0)
        act = self.m.get_activity(aid)
        self.assertEqual(act["type"], "relay")
        self.assertEqual(act["status"], "open")

    def test_active_activity(self):
        aid = self.m.create_activity(1, "match", "中秋", None, "1", deadline="2026-09-15 20:00:00")
        got = self.m.get_active_activity(1)
        self.assertEqual(got["id"], aid)
        self.assertIsNone(self.m.get_active_activity(2))
        self.m.update_activity(aid, status="finished", finished_at="2026-09-01 00:00:00")
        self.assertIsNone(self.m.get_active_activity(1))

    def test_member_flow(self):
        aid = self.m.create_activity(1, "relay", "t", None, "1", hours_per_user=24.0)
        self.assertTrue(self.m.add_member(aid, "100", "A"))
        self.assertFalse(self.m.add_member(aid, "100", "A"))  # 重复加入
        self.m.add_member(aid, "200", "B")
        self.assertEqual(self.m.count_members(aid), 2)
        self.m.remove_member(aid, "200")
        self.assertEqual(self.m.count_members(aid), 1)

    def test_ring_and_updates(self):
        aid = self.m.create_activity(1, "match", "t", None, "1", deadline="2026-09-15 20:00:00")
        for uid, nick in (("100", "A"), ("200", "B"), ("300", "C")):
            self.m.add_member(aid, uid, nick)
        self.m.set_ring(aid, [("100", "200", 1), ("200", "300", 2), ("300", "100", 3)])
        members = self.m.get_members(aid)
        by_uid = {m["user_id"]: m for m in members}
        self.assertEqual(by_uid["100"]["next_user_id"], "200")
        self.assertEqual(by_uid["100"]["seq"], 1)
        self.m.update_member(aid, "100", status="done", content="作品", submitted_at="2026-09-01 00:00:00")
        got = self.m.get_member(aid, "100")
        self.assertEqual(got["status"], "done")
        self.assertEqual(got["content"], "作品")

    def test_user_activities(self):
        aid = self.m.create_activity(1, "relay", "t", None, "1", hours_per_user=24.0)
        self.m.add_member(aid, "100", "A")
        self.m.update_activity(aid, status="running")
        acts = self.m.get_running_activities_for_user("100")
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0]["id"], aid)
        self.assertEqual(self.m.get_running_activity_for_user_and_id("100", aid)["id"], aid)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 运行确认失败**

Run: `python test/test_activity_db.py`
Expected: `ModuleNotFoundError: No module named 'core.db.activity'`

- [ ] **Step 4: 创建 `core/db/activity.py`**

```python
import sqlite3
from datetime import datetime


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ActivityManager:
    def __init__(self, conn):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row  # dict(row) 依赖 Row 工厂
        self.cur = conn.cursor()

    def _rows(self, sql, params=()):
        self.cur.execute(sql, params)
        return [dict(r) for r in self.cur.fetchall()]

    def _row(self, sql, params=()):
        self.cur.execute(sql, params)
        r = self.cur.fetchone()
        return dict(r) if r else None

    # ── activities ──
    def create_activity(self, group_id, type_, title, theme, created_by,
                        hours_per_user=None, deadline=None) -> int:
        self.cur.execute(
            "INSERT INTO activities (group_id, type, title, theme, status, created_by,"
            " deadline, hours_per_user, created_at) VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?)",
            (int(group_id), type_, title, theme, str(created_by), deadline,
             hours_per_user, _now()),
        )
        self.conn.commit()
        return self.cur.lastrowid

    def get_activity(self, activity_id) -> dict | None:
        return self._row("SELECT * FROM activities WHERE id = ?", (int(activity_id),))

    def get_active_activity(self, group_id) -> dict | None:
        return self._row(
            "SELECT * FROM activities WHERE group_id = ? AND status IN ('open', 'running')"
            " ORDER BY id DESC LIMIT 1",
            (int(group_id),),
        )

    def get_running_activities(self) -> list[dict]:
        return self._rows("SELECT * FROM activities WHERE status = 'running'")

    def update_activity(self, activity_id, **fields):
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.cur.execute(
            f"UPDATE activities SET {sets} WHERE id = ?",
            (*fields.values(), int(activity_id)),
        )
        self.conn.commit()

    # ── members ──
    def add_member(self, activity_id, user_id, nickname) -> bool:
        self.cur.execute(
            "INSERT OR IGNORE INTO activity_members (activity_id, user_id, nickname)"
            " VALUES (?, ?, ?)",
            (int(activity_id), str(user_id), nickname),
        )
        self.conn.commit()
        return self.cur.rowcount > 0

    def count_members(self, activity_id) -> int:
        self.cur.execute(
            "SELECT COUNT(*) FROM activity_members WHERE activity_id = ?", (int(activity_id),)
        )
        return self.cur.fetchone()[0]

    def get_member(self, activity_id, user_id) -> dict | None:
        return self._row(
            "SELECT * FROM activity_members WHERE activity_id = ? AND user_id = ?",
            (int(activity_id), str(user_id)),
        )

    def get_members(self, activity_id) -> list[dict]:
        return self._rows(
            "SELECT * FROM activity_members WHERE activity_id = ? ORDER BY seq ASC",
            (int(activity_id),),
        )

    def remove_member(self, activity_id, user_id):
        self.cur.execute(
            "DELETE FROM activity_members WHERE activity_id = ? AND user_id = ?",
            (int(activity_id), str(user_id)),
        )
        self.conn.commit()

    def update_member(self, activity_id, user_id, **fields):
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.cur.execute(
            f"UPDATE activity_members SET {sets} WHERE activity_id = ? AND user_id = ?",
            (*fields.values(), int(activity_id), str(user_id)),
        )
        self.conn.commit()

    def set_ring(self, activity_id, assignments: list[tuple[str, str, int]]):
        """assignments: [(user_id, next_user_id, seq), ...] — 匹配环 / 接龙链一次写入。"""
        for uid, next_uid, seq in assignments:
            self.cur.execute(
                "UPDATE activity_members SET seq = ?, next_user_id = ?"
                " WHERE activity_id = ? AND user_id = ?",
                (int(seq), next_uid, int(activity_id), str(uid)),
            )
        self.conn.commit()

    def get_running_activities_for_user(self, user_id) -> list[dict]:
        return self._rows(
            "SELECT a.* FROM activities a JOIN activity_members m ON m.activity_id = a.id"
            " WHERE m.user_id = ? AND a.status = 'running' ORDER BY a.id DESC",
            (str(user_id),),
        )

    def get_running_activity_for_user_and_id(self, user_id, activity_id) -> dict | None:
        return self._row(
            "SELECT a.* FROM activities a JOIN activity_members m ON m.activity_id = a.id"
            " WHERE m.user_id = ? AND a.status = 'running' AND a.id = ?",
            (str(user_id), int(activity_id)),
        )
```

- [ ] **Step 5: 在 `core/database_manager.py` 注册**

```python
from core.db.activity import ActivityManager
# __init__ 中新增一行：
self.activity = ActivityManager(self.conn)
```

- [ ] **Step 6: 运行确认通过**

Run: `python test/test_activity_db.py`
Expected: `OK`（5 个测试全过）

- [ ] **Step 7: 提交**

```bash
git add core/db/_base.py core/db/activity.py core/database_manager.py test/test_activity_db.py
git commit -m "feat(活动): 新增活动与成员数据表及访问层"
```

---

### Task 2: 纯逻辑模块（环生成 / 链导航 / 超时判定）

**Files:**
- Create: `plugins/activity/logic.py`
- Test: `test/test_activity_logic.py`

**Interfaces:**
- Consumes: Task 1 的 `activity_members` 行 dict（`seq` / `next_user_id` / `status` / `received_at`）
- Produces:
  - `build_ring(users: list[str], rng=random) -> list[tuple[str, str]]` — 单环 (uid, next_uid)，无自匹配；`len(users) < 2` 抛 `ValueError`
  - `relay_assignments(users: list[str], rng=random) -> list[tuple[str, str, int]]` — 接龙链 (uid, next_uid=链下一人, seq)，末位 next_uid=None
  - `current_turn(members: list[dict]) -> dict | None` — 按 seq 升序第一个 status == 'pending'
  - `next_pending(members: list[dict], after_seq: int) -> dict | None` — seq > after_seq 的第一个 pending
  - `last_done(members: list[dict], before_seq: int) -> dict | None` — seq < before_seq 的最后一个 done（超时跳过时取上家作品）
  - `is_timeout(received_at: str | None, now: datetime, hours: float) -> bool` — 无 received_at 返回 False；`(now - parsed) > timedelta(hours=hours)`
  - `relay_done(members: list[dict]) -> bool` — 无 pending 成员（全 done/skipped/left）

- [ ] **Step 1: 写失败测试 `test/test_activity_logic.py`**

```python
"""测试活动纯逻辑（环/链/超时）。
运行: python test/test_activity_logic.py
"""
import sys
import random
import unittest
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.activity.logic import (
    build_ring, relay_assignments, current_turn, next_pending,
    last_done, is_timeout, relay_done,
)


def _member(uid, seq, status="pending", received_at=None):
    return {"user_id": uid, "seq": seq, "status": status, "received_at": received_at}


class TestRing(unittest.TestCase):
    def test_single_cycle_no_self(self):
        users = ["1", "2", "3", "4", "5"]
        ring = build_ring(users, rng=random.Random(42))
        self.assertEqual(len(ring), 5)
        nxt = {u: n for u, n in ring}
        self.assertEqual(set(nxt), set(users))          # 人人有下家
        for u, n in ring:
            self.assertNotEqual(u, n)                   # 无自匹配
        # 单环闭合：从任一点沿 next 走 5 步回到原点
        cur = ring[0][0]
        for _ in range(5):
            cur = nxt[cur]
        self.assertEqual(cur, ring[0][0])

    def test_ring_needs_two(self):
        with self.assertRaises(ValueError):
            build_ring(["1"])


class TestRelayChain(unittest.TestCase):
    def test_assignments(self):
        users = ["1", "2", "3"]
        assigns = relay_assignments(users, rng=random.Random(1))
        self.assertEqual([a[2] for a in assigns], [1, 2, 3])   # seq 连续
        self.assertEqual({a[0] for a in assigns}, set(users))
        self.assertEqual(assigns[0][1], users[users.index(assigns[0][0]) + 1]
                         if assigns[0][1] is not None else None)
        self.assertIsNone(assigns[-1][1])                       # 末位无下家


class TestChainNav(unittest.TestCase):
    def setUp(self):
        self.members = [_member("1", 1), _member("2", 2), _member("3", 3)]

    def test_current_turn(self):
        self.assertEqual(current_turn(self.members)["user_id"], "1")
        self.members[0]["status"] = "done"
        self.assertEqual(current_turn(self.members)["user_id"], "2")
        for m in self.members:
            m["status"] = "skipped"
        self.assertIsNone(current_turn(self.members))

    def test_next_pending_skips_left(self):
        self.members[1]["status"] = "left"
        self.assertEqual(next_pending(self.members, after_seq=1)["user_id"], "3")
        self.assertIsNone(next_pending(self.members, after_seq=3))

    def test_last_done(self):
        self.members[0]["status"] = "done"
        self.members[1]["status"] = "done"
        got = last_done(self.members, before_seq=3)
        self.assertEqual(got["user_id"], "2")
        # 边界：before_seq 不包含自身（seq==2 的 done 不计入 before_seq=2）
        self.assertIsNone(last_done(
            [_member("1", 1), _member("2", 2, status="done")], before_seq=2))

    def test_relay_done(self):
        self.assertFalse(relay_done(self.members))
        for m in self.members:
            m["status"] = "done"
        self.assertTrue(relay_done(self.members))


class TestTimeout(unittest.TestCase):
    def test_timeout(self):
        now = datetime(2026, 9, 1, 12, 0, 0)
        self.assertTrue(is_timeout("2026-09-01 00:00:00", now, 10.0))
        self.assertFalse(is_timeout("2026-09-01 09:00:00", now, 10.0))
        self.assertFalse(is_timeout(None, now, 10.0))       # 尚未开始计时

    def test_boundary(self):
        now = datetime(2026, 9, 1, 10, 0, 1)
        self.assertTrue(is_timeout("2026-09-01 00:00:00", now, 10.0))
        self.assertFalse(is_timeout("2026-09-01 00:00:01", now, 10.0))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python test/test_activity_logic.py`
Expected: `ModuleNotFoundError: No module named 'plugins.activity.logic'`

- [ ] **Step 3: 创建 `plugins/activity/logic.py`**

```python
import random
from datetime import datetime, timedelta


def build_ring(users: list[str], rng=random) -> list[tuple[str, str]]:
    """shuffle 后错位成单环，返回 [(uid, next_uid), ...]，无自匹配。"""
    if len(users) < 2:
        raise ValueError("匹配活动至少需要 2 人")
    shuffled = list(users)
    rng.shuffle(shuffled)
    return [(shuffled[i], shuffled[(i + 1) % len(shuffled)]) for i in range(len(shuffled))]


def relay_assignments(users: list[str], rng=random) -> list[tuple[str, str, int]]:
    """接龙链 [(uid, next_uid, seq), ...]，末位 next_uid=None。"""
    if not users:
        raise ValueError("接龙活动至少需要 1 人")
    shuffled = list(users)
    rng.shuffle(shuffled)
    out = []
    for i, uid in enumerate(shuffled):
        nxt = shuffled[i + 1] if i + 1 < len(shuffled) else None
        out.append((uid, nxt, i + 1))
    return out


def current_turn(members: list[dict]) -> dict | None:
    for m in sorted(members, key=lambda x: x["seq"]):
        if m["status"] == "pending":
            return m
    return None


def next_pending(members: list[dict], after_seq: int) -> dict | None:
    for m in sorted(members, key=lambda x: x["seq"]):
        if m["seq"] > after_seq and m["status"] == "pending":
            return m
    return None


def last_done(members: list[dict], before_seq: int) -> dict | None:
    done = [m for m in members if m["status"] == "done" and m["seq"] < before_seq]
    return max(done, key=lambda x: x["seq"], default=None)


def is_timeout(received_at: str | None, now: datetime, hours: float) -> bool:
    if not received_at:
        return False
    try:
        start = datetime.strptime(received_at, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return now - start > timedelta(hours=hours)


def relay_done(members: list[dict]) -> bool:
    return all(m["status"] != "pending" for m in members)
```

- [ ] **Step 4: 运行确认通过**

Run: `python test/test_activity_logic.py`
Expected: `OK`

- [ ] **Step 5: 提交**

```bash
git add plugins/activity/logic.py test/test_activity_logic.py
git commit -m "feat(活动): 新增环生成/链导航/超时判定纯逻辑"
```

---

### Task 3: 归档写盘（meta.json / relay.md / match.md / imgs）

**Files:**
- Create: `plugins/activity/archive.py`
- Test: `test/test_activity_archive.py`

**Interfaces:**
- Consumes: Task 1 的 `activities` / `activity_members` 行 dict；图片已由提交流程下载到 `server_data/activity_archive/<id>/imgs/img_<seq>_<n><ext>`
- Produces:
  - `archive_dir(activity_id: int) -> str` — `server_data/activity_archive/<id>`（用 `core.context.python_data_path`）
  - `image_path(activity_id: int, seq: int, n: int, ext: str) -> str` — 提交时图片落盘路径
  - `archive_activity(activity: dict, members: list[dict]) -> None` — 写 meta.json + relay.md / match.md

- [ ] **Step 1: 写失败测试 `test/test_activity_archive.py`**

```python
"""测试活动归档。
运行: python test/test_activity_archive.py
"""
import os
import sys
import json
import shutil
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.context as context
from plugins.activity import archive

TEST_ROOT = "/tmp/test_activity_archive"


def _member(uid, nick, seq, status="done", content=None, images=None):
    return {
        "user_id": uid, "nickname": nick, "seq": seq, "status": status,
        "next_user_id": None, "received_at": "2026-09-01 00:00:00",
        "submitted_at": "2026-09-02 00:00:00", "content": content, "images": images,
    }


class TestArchive(unittest.TestCase):
    def setUp(self):
        context.python_data_path = TEST_ROOT
        if os.path.exists(TEST_ROOT):
            shutil.rmtree(TEST_ROOT)

    def test_archive_relay(self):
        act = {"id": 1, "type": "relay", "title": "端午接龙", "theme": "粽子",
               "group_id": 296470819, "created_at": "2026-09-01 00:00:00",
               "finished_at": "2026-09-03 00:00:00", "status": "finished"}
        members = [
            _member("1", "A", 1, content="第一章", images='["img_1_1.jpg"]'),
            _member("2", "B", 2, content="第二章", images=None),
        ]
        archive.archive_activity(act, members)
        d = archive.archive_dir(1)
        self.assertTrue(os.path.isfile(f"{d}/meta.json"))
        self.assertTrue(os.path.isfile(f"{d}/relay.md"))
        md = open(f"{d}/relay.md", encoding="utf-8").read()
        self.assertIn("端午接龙", md)
        self.assertIn("A", md)
        self.assertIn("第一章", md)
        self.assertIn("imgs/img_1_1.jpg", md)
        self.assertFalse(os.path.exists(f"{d}/match.md"))
        meta = json.load(open(f"{d}/meta.json", encoding="utf-8"))
        self.assertEqual(meta["id"], 1)
        self.assertEqual(meta["members"][1]["nickname"], "B")

    def test_archive_match_marks_missed(self):
        act = {"id": 2, "type": "match", "title": "中秋", "theme": None,
               "group_id": 1, "created_at": "2026-09-01 00:00:00",
               "finished_at": "2026-09-10 00:00:00", "status": "finished"}
        members = [
            _member("1", "A", 1, content="给下家的礼物", images=None),
            _member("2", "B", 2, status="missed", content=None, images=None),
        ]
        archive.archive_activity(act, members)
        md = open(f"{archive.archive_dir(2)}/match.md", encoding="utf-8").read()
        self.assertIn("给下家的礼物", md)
        self.assertIn("B", md)
        self.assertIn("未提交", md)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python test/test_activity_archive.py`
Expected: `ModuleNotFoundError: No module named 'plugins.activity'`（包尚未创建）

- [ ] **Step 3: 创建 `plugins/activity/archive.py`**

```python
import os
import json

import core.context as context

STATUS_LABEL = {
    "done": "已完成",
    "skipped": "超时跳过",
    "missed": "未提交",
    "left": "已退出",
    "pending": "未完成",
}


def archive_dir(activity_id: int) -> str:
    return f"{context.python_data_path}/activity_archive/{activity_id}"


def image_path(activity_id: int, seq: int, n: int, ext: str) -> str:
    return f"{archive_dir(activity_id)}/imgs/img_{seq}_{n}{ext}"


def _member_block(m) -> list[str]:
    lines = [f"## {m['nickname']}（{m['user_id']}）"]
    if m["submitted_at"]:
        lines.append(f"- 提交时间：{m['submitted_at']}")
    lines.append(f"- 状态：{STATUS_LABEL.get(m['status'], m['status'])}")
    if m["status"] == "done":
        if m["content"]:
            lines.append("")
            lines.append(m["content"])
        try:
            imgs = json.loads(m["images"]) if m["images"] else []
        except (TypeError, ValueError):
            imgs = []
        for name in imgs:
            lines.append("")
            lines.append(f"![图片](imgs/{name})")
    lines.append("")
    return lines


def archive_activity(activity: dict, members: list[dict]):
    """写 meta.json + relay.md/match.md。图片已在提交时落盘，此处仅引用。"""
    d = archive_dir(activity["id"])
    os.makedirs(f"{d}/imgs", exist_ok=True)

    meta = {
        "id": activity["id"],
        "group_id": activity["group_id"],
        "type": activity["type"],
        "title": activity["title"],
        "theme": activity.get("theme"),
        "created_at": activity["created_at"],
        "finished_at": activity.get("finished_at"),
        "members": [
            {
                "user_id": m["user_id"],
                "nickname": m["nickname"],
                "seq": m["seq"],
                "status": m["status"],
                "submitted_at": m.get("submitted_at"),
            }
            for m in sorted(members, key=lambda x: x["seq"])
        ],
    }
    with open(f"{d}/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    is_match = activity["type"] == "match"
    lines = ["# 活动归档", ""]
    lines.append(f"- 标题：{activity['title']}")
    lines.append(f"- 类型：{'匹配下家' if is_match else '接龙'}")
    if activity.get("theme"):
        lines.append(f"- 主题：{activity['theme']}")
    lines.append(f"- 开始：{activity['created_at']}")
    lines.append(f"- 结束：{activity.get('finished_at')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    title = "作品" if is_match else "接力"
    for i, m in enumerate(sorted(members, key=lambda x: x["seq"]), 1):
        lines.append(f"## {title} {i}")
        lines += _member_block(m)

    md_name = "match.md" if is_match else "relay.md"
    with open(f"{d}/{md_name}", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
```

- [ ] **Step 4: 运行确认通过**

Run: `python test/test_activity_archive.py`
Expected: `OK`

- [ ] **Step 5: 提交**

```bash
git add plugins/activity/archive.py test/test_activity_archive.py
git commit -m "feat(活动): 新增归档写盘（meta/接龙/匹配 markdown）"
```

---

### Task 4: 群聊指令插件（创建 / 加入 / 退出 / 开始 / 状态 / 结束）

**Files:**
- Create: `plugins/activity/__init__.py`
- Test: `test/test_activity_commands.py`

**Interfaces:**
- Consumes: `ActivityManager`（Task 1）、`logic.build_ring / relay_assignments`（Task 2）、`archive.image_path`（Task 3）
- Produces:
  - `ActivityPlugin(Plugin)`，`name = "activity"`，`description = "群活动：接龙与匹配下家"`；私有方法 `_first_text() / _sender_nickname() / _send_private(user_id, *message) / _announce_group(group_id, text_body) / _extract_submission() / _download_images(activity_id, seq, image_files) / _work_segments(member)`（`_work_segments` 为模块级函数，见 Task 5）
  - 模块级辅助函数（Task 5 定义，Task 4 先行引用）：
    - `_send_private(api, user_id, *message)` — `call_api("send_private_msg", ...)`
    - `_announce_group(api, group_id, text_body)` — `call_api("send_group_msg", ...)`
    - `_work_segments(member) -> list[dict]` — 从成员行拼 content + 图片消息段
    - `_relay_advance(api, db, act, members, from_seq) -> bool` — 把 from_seq 之后的作品传给下一个 pending；False=无人可传
    - `_match_reconnect(api, db, act, left_uid, members)` — 环闭合
    - `_finish_activity(api, db, act)` — 置 finished + 归档 + 群公告

**指令契约：**

| 指令 | 前置 | 行为 |
|------|------|------|
| `/活动 创建 接龙 <标题> [小时数]` | 群聊、群内无 open/running 活动 | 默认 48 小时 |
| `/活动 创建 匹配 <标题> <截止 YYYY-MM-DD HH:MM>` | 同上 | |
| `/活动 加入` | 群聊、存在 open 活动、未加入 | |
| `/活动 退出` | 群聊、已加入 | open：删除行（创建人退出转移；无人则取消）；running：走 `_handle_leave_running` |
| `/活动 开始` | 群聊、创建人、open、relay≥1 人 / match≥2 人 | 置 running、写 seq/next、逐一私聊通知 |
| `/活动 状态` | 群聊 | 显示进度 |
| `/活动 结束` | 群聊、创建人 | open → cancelled；running → finished + 归档 |

- [ ] **Step 1: 写失败测试 `test/test_activity_commands.py`**

```python
"""测试活动群聊指令。
运行: python test/test_activity_commands.py
"""
import os
import sys
import sqlite3
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.context as context
from core.event import Event
from core.db._base import init_schema
from core.db.activity import ActivityManager
from plugins.activity import ActivityPlugin
from test.helper import MockApiWrapper, make_group_message

DB_PATH = "/tmp/test_activity_cmd.db"
GID = 296470819


class _Db:
    """测试用：仅挂 activity 管理器，跳过真实 DbManager 的全局库。"""
    def __init__(self, conn):
        self.activity = ActivityManager(conn)


def _sent_text(plugin):
    assert plugin.api.sent_messages, "无消息发送"
    return plugin.api.sent_messages[-1][1][0]["data"]["text"]


class TestCommands(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)
        self.old_python_data_path = context.python_data_path
        context.python_data_path = "/tmp/test_activity_archive_cmd"

    def tearDown(self):
        self.conn.close()

    def _run(self, text, user_id=123456):
        raw = make_group_message(text, user_id=user_id, group_id=GID)
        plugin = ActivityPlugin.__new__(ActivityPlugin)
        plugin.bot_event = Event(raw)
        plugin.api = MockApiWrapper(raw)
        plugin.dbmanager = self.db
        return plugin

    def test_create_relay(self):
        p = self._run("/活动 创建 接龙 端午接龙")
        p.handle()
        self.assertIn("端午接龙", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertIsNotNone(act)
        self.assertEqual(act["type"], "relay")
        self.assertEqual(act["hours_per_user"], 48.0)

    def test_create_match_deadline(self):
        p = self._run("/活动 创建 匹配 中秋 2026-09-15 20:00")
        p.handle()
        self.assertIn("中秋", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["type"], "match")
        self.assertEqual(act["deadline"], "2026-09-15 20:00:00")

    def test_join_and_start_relay(self):
        self._run("/活动 创建 接龙 端午接龙").handle()
        for uid in (123456, 234567):
            p = self._run("/活动 加入", user_id=uid)
            p.handle()
            self.assertIn("已加入", _sent_text(p))
        p = self._run("/活动 开始", user_id=123456)
        p.handle()
        self.assertIn("开始", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["status"], "running")
        members = self.db.activity.get_members(act["id"])
        self.assertEqual([m["seq"] for m in members], [1, 2])
        self.assertEqual(members[0]["next_user_id"], members[1]["user_id"])
        self.assertIsNone(members[1]["next_user_id"])
        self.assertIsNotNone(members[0]["received_at"])  # 第一棒已开始计时

    def test_start_only_creator(self):
        self._run("/活动 创建 接龙 t").handle()
        self._run("/活动 加入", user_id=123456).handle()
        p = self._run("/活动 开始", user_id=999999)
        p.handle()
        self.assertIn("创建人", _sent_text(p))

    def test_match_needs_two(self):
        self._run("/活动 创建 匹配 中秋 2026-09-15 20:00").handle()
        self._run("/活动 加入", user_id=123456).handle()
        p = self._run("/活动 开始", user_id=123456)
        p.handle()
        self.assertIn("至少", _sent_text(p))

    def test_leave_open_transfers_creator(self):
        self._run("/活动 创建 接龙 t").handle()
        self._run("/活动 加入", user_id=123456).handle()
        self._run("/活动 加入", user_id=234567).handle()
        p = self._run("/活动 退出", user_id=123456)
        p.handle()
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["created_by"], "234567")
        self.assertIn("转移", _sent_text(p))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python test/test_activity_commands.py`
Expected: `ImportError`（`plugins.activity` 无 `ActivityPlugin`）

- [ ] **Step 3: 创建 `plugins/activity/__init__.py`（群聊指令部分；提交/心跳在 Task 5/6 追加）**

```python
import json
import os
from datetime import datetime

from core.base import Plugin
from core.cq import text
from core.logger import logger
from core.utils import register_plugin

from .logic import build_ring, relay_assignments, current_turn
from . import archive as archive_mod


def _parse_deadline(raw: str) -> str | None:
    """接受 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD HH:MM:SS'，返回完整格式；非法返回 None。"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── 模块级辅助（插件类共用，Task 5 完整实现） ──

def _send_private(api, user_id: int, *message):
    api.call_api("send_private_msg", {"user_id": int(user_id), "message": list(message)})


def _announce_group(api, group_id: int, text_body: str):
    api.call_api("send_group_msg", {"group_id": int(group_id), "message": [text(text_body)]})


@register_plugin
class ActivityPlugin(Plugin):
    name = "activity"
    description = "群活动：接龙与匹配下家"

    def _first_text(self) -> str:
        for seg in self.bot_event.message:
            if seg.get("type") == "text":
                return seg.get("data", {}).get("text", "").strip()
        return ""

    def _sender_nickname(self) -> str:
        sender = self.bot_event.sender
        if sender and isinstance(sender, dict):
            return sender.get("card") or sender.get("nickname") or f"用户{self.bot_event.user_id}"
        return f"用户{self.bot_event.user_id}"

    def _send_private(self, user_id: int, *message):
        _send_private(self.api, user_id, *message)

    def _announce_group(self, group_id: int, text_body: str):
        _announce_group(self.api, group_id, text_body)

    def match(self, event_type="message") -> bool:
        if event_type != "message":
            return False
        body = self._first_text()
        if not body:
            return False
        parts = body.split()
        if parts[0] == "/活动" and self.bot_event.group_id is not None:
            return True
        if parts[0] == "/提交" and self.bot_event.is_private:
            return True
        return False

    def handle(self):
        try:
            parts = self._first_text().split()
            if parts[0] == "/活动":
                self._route_group_command(parts[1:])
            else:
                self._handle_submit(parts[1:])
        except Exception:
            logger.exception("Activity 处理异常")

    # ── 群聊指令路由 ──────────────────────────────────

    def _route_group_command(self, args: list[str]):
        gid = self.bot_event.group_id
        uid = str(self.bot_event.user_id)
        if not args:
            self._show_usage()
            return
        sub = args[0]
        if sub == "创建":
            self._handle_create(args[1:])
        elif sub == "加入":
            self._handle_join(gid, uid)
        elif sub == "退出":
            self._handle_leave(gid, uid)
        elif sub == "开始":
            self._handle_start(gid, uid)
        elif sub == "状态":
            self._handle_status(gid)
        elif sub == "结束":
            self._handle_end(gid, uid)
        else:
            self._show_usage()

    def _show_usage(self):
        self.api.send_msg(text(
            "活动指令：\n"
            "/活动 创建 接龙 <标题> [每人小时数]\n"
            "/活动 创建 匹配 <标题> <截止 YYYY-MM-DD HH:MM>\n"
            "/活动 加入 / 退出\n"
            "/活动 开始（创建人）\n"
            "/活动 状态 / 结束（创建人）"
        ))

    def _handle_create(self, args: list[str]):
        gid = self.bot_event.group_id
        uid = str(self.bot_event.user_id)
        if not args or args[0] not in ("接龙", "匹配"):
            self.api.send_msg(text("用法：/活动 创建 接龙|匹配 <标题> [参数]"))
            return
        if self.dbmanager.activity.get_active_activity(gid):
            self.api.send_msg(text("本群已有进行中的活动"))
            return
        kind = args[0]
        rest = args[1:]
        if kind == "接龙":
            if not rest:
                self.api.send_msg(text("用法：/活动 创建 接龙 <标题> [每人小时数]"))
                return
            title = rest[0]
            hours = 48.0
            if len(rest) > 1:
                try:
                    hours = float(rest[1])
                    if hours <= 0:
                        raise ValueError
                except ValueError:
                    self.api.send_msg(text("每人小时数必须为正数"))
                    return
            aid = self.dbmanager.activity.create_activity(
                gid, "relay", title, None, uid, hours_per_user=hours)
            self.api.send_msg(text(
                f"接龙活动「{title}」已创建（#{aid}）\n"
                f"每人限时 {hours:g} 小时\n"
                f"回复 /活动 加入 报名，报名完成后由创建人 /活动 开始"
            ))
        else:
            if len(rest) < 2:
                self.api.send_msg(text("用法：/活动 创建 匹配 <标题> <截止 YYYY-MM-DD HH:MM>"))
                return
            title = rest[0]
            deadline = _parse_deadline(rest[1])
            if not deadline:
                self.api.send_msg(text("截止时间格式错误，示例：2026-09-15 20:00"))
                return
            aid = self.dbmanager.activity.create_activity(
                gid, "match", title, None, uid, deadline=deadline)
            self.api.send_msg(text(
                f"匹配活动「{title}」已创建（#{aid}）\n"
                f"截止时间 {deadline}\n"
                f"回复 /活动 加入 报名，报名完成后由创建人 /活动 开始"
            ))

    def _handle_join(self, gid: int, uid: str):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act or act["status"] != "open":
            self.api.send_msg(text("本群当前没有报名中的活动"))
            return
        if self.dbmanager.activity.get_member(act["id"], uid):
            self.api.send_msg(text("你已加入该活动"))
            return
        self.dbmanager.activity.add_member(act["id"], uid, self._sender_nickname())
        n = self.dbmanager.activity.count_members(act["id"])
        self.api.send_msg(text(f"已加入「{act['title']}」（当前 {n} 人）"))

    def _handle_leave(self, gid: int, uid: str):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act:
            self.api.send_msg(text("本群没有进行中的活动"))
            return
        member = self.dbmanager.activity.get_member(act["id"], uid)
        if not member:
            self.api.send_msg(text("你不在该活动中"))
            return
        if act["status"] == "open":
            self.dbmanager.activity.remove_member(act["id"], uid)
            if self.dbmanager.activity.count_members(act["id"]) == 0:
                self.dbmanager.activity.update_activity(act["id"], status="cancelled")
                self.api.send_msg(text("已退出，活动无人参加已取消"))
                return
            if str(act["created_by"]) == uid:
                first = self.dbmanager.activity.get_members(act["id"])[0]
                self.dbmanager.activity.update_activity(act["id"], created_by=first["user_id"])
                self.api.send_msg(text(f"已退出，创建人已转移给 {first['nickname']}"))
                return
            self.api.send_msg(text("已退出报名"))
        else:
            self._handle_leave_running(act, member)

    def _handle_leave_running(self, act: dict, member: dict):
        """进行中退出：接龙摘链（仅当轮到 TA 时顺延），匹配闭合环。"""
        self.dbmanager.activity.update_member(act["id"], member["user_id"], status="left")
        members = self.dbmanager.activity.get_members(act["id"])
        self._announce_group(act["group_id"], f"{member['nickname']} 已退出活动")
        if act["type"] == "relay":
            cur = current_turn(members)
            if cur and cur["user_id"] == member["user_id"]:
                if not _relay_advance(self.api, self.dbmanager, act, members, member["seq"]):
                    _finish_activity(self.api, self.dbmanager, act)
        else:
            _match_reconnect(self.api, self.dbmanager, act, member["user_id"], members)
            fresh = self.dbmanager.activity.get_members(act["id"])
            if all(m["status"] == "done" for m in fresh):
                _finish_activity(self.api, self.dbmanager, act)

    def _handle_start(self, gid: int, uid: str):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act:
            self.api.send_msg(text("本群没有活动"))
            return
        if act["status"] != "open":
            self.api.send_msg(text("活动已开始"))
            return
        if str(act["created_by"]) != uid and not self.super_user():
            self.api.send_msg(text("只有创建人才能开始活动"))
            return
        members = self.dbmanager.activity.get_members(act["id"])
        users = [m["user_id"] for m in members]
        nick_map = {m["user_id"]: m["nickname"] for m in members}
        if act["type"] == "relay":
            if not users:
                self.api.send_msg(text("接龙活动至少需要 1 人"))
                return
            assigns = relay_assignments(users)
        else:
            if len(users) < 2:
                self.api.send_msg(text("匹配活动至少需要 2 人"))
                return
            ring = build_ring(users)
            assigns = [(u, n, i + 1) for i, (u, n) in enumerate(ring)]
        self.dbmanager.activity.set_ring(act["id"], assigns)
        self.dbmanager.activity.update_activity(act["id"], status="running")
        now = _now()
        if act["type"] == "relay":
            first = assigns[0]
            self.dbmanager.activity.update_member(act["id"], first[0], received_at=now)
            self._send_private(
                int(first[0]),
                text(f"接龙活动「{act['title']}」开始！你是第 1 棒。\n"
                     f"请创作并私聊发送 /提交 附上作品，限时 {act['hours_per_user']:g} 小时。"),
            )
            self._announce_group(gid, f"接龙活动「{act['title']}」开始，{nick_map[first[0]]} 先来！")
        else:
            for uid_, next_uid, _seq in assigns:
                self._send_private(
                    int(uid_),
                    text(f"匹配活动「{act['title']}」开始！\n"
                         f"你的下家是：{nick_map[next_uid]}\n"
                         f"请为 TA 创作并私聊发送 /提交 附上作品，截止 {act['deadline']}。"),
                )
            self._announce_group(gid, f"匹配活动「{act['title']}」开始，请查看私聊！")

    def _handle_status(self, gid: int):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act:
            self.api.send_msg(text("本群没有进行中的活动"))
            return
        members = self.dbmanager.activity.get_members(act["id"])
        lines = [f"「{act['title']}」（{'匹配下家' if act['type'] == 'match' else '接龙'} #{act['id']}）"]
        status_map = {"done": "✓", "skipped": "跳过", "missed": "未交", "left": "退出", "pending": "…"}
        for m in members:
            lines.append(f"  {m['seq']}. {m['nickname']} {status_map.get(m['status'], m['status'])}")
        if act["type"] == "relay":
            cur = current_turn(members)
            if cur:
                lines.append(f"当前轮到：{cur['nickname']}")
            else:
                lines.append("接龙已完成")
        else:
            done = sum(1 for m in members if m["status"] == "done")
            lines.append(f"进度：{done}/{len(members)}")
            lines.append(f"截止：{act['deadline']}")
        self.api.send_msg(text("\n".join(lines)))

    def _handle_end(self, gid: int, uid: str):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act:
            self.api.send_msg(text("本群没有活动"))
            return
        if str(act["created_by"]) != uid and not self.super_user():
            self.api.send_msg(text("只有创建人才能结束活动"))
            return
        if act["status"] == "open":
            self.dbmanager.activity.update_activity(act["id"], status="cancelled")
            self.api.send_msg(text(f"活动「{act['title']}」已取消"))
        else:
            _finish_activity(self.api, self.dbmanager, act)
```

- [ ] **Step 4: 运行测试确认群聊指令部分**

Run: `python test/test_activity_commands.py`
Expected: `OK`（`_relay_advance` 等引用在运行时才解析，本任务无调用路径触发缺失）

- [ ] **Step 5: 提交**

```bash
git add plugins/activity/__init__.py test/test_activity_commands.py
git commit -m "feat(活动): 新增群聊指令（创建/加入/退出/开始/状态/结束）"
```

---

### Task 5: 私聊提交 + 作品流转 + 收尾辅助函数

**Files:**
- Modify: `plugins/activity/__init__.py`
- Test: `test/test_activity_submit.py`

**Interfaces:**
- Consumes: Task 2 的 `current_turn / next_pending / last_done`；Task 3 的 `archive.image_path`；Task 4 已定义的 `ActivityPlugin`
- Produces（模块级辅助函数，补全 Task 4 的引用）：
  - `_work_segments(member) -> list[dict]` — content + 图片消息段（纯函数）
  - `_relay_advance(api, db, act, members, from_seq) -> bool`
  - `_match_reconnect(api, db, act, left_uid, members)`
  - `_finish_activity(api, db, act)`
  - `ActivityPlugin._handle_submit(args)` 与 `_extract_submission() / _download_images(activity_id, seq, image_files) / _forward_work(act, members, member)`

**流转规则：**
- 提交者必须处于唯一 running 活动（多活动需 `/提交 <id>`）、status 为 pending、relay 时必须是当前轮次。
- relay：提交 → 标记 done + 存 content/images → 若有 next_pending：转发作品 + 设 received_at + 群公告；否则 finish。
- match：提交 → 匿名转发给 next_user_id（不带作者名）→ 全员 done → finish。
- 图片：消息段里 `type == "image"` 的 `data.file` 用 `api.get_image_url(file)` + `download_image` 落盘 `imgs/img_<seq>_<n><ext>`；任一失败则整体失败提示重试。
- 转发作品消息 = `[text(提示)] + [text(content)] + 图片消息段`（图片段 `{"type": "image", "data": {"file": 文件名}}`，trpg_session 同款）。
- `_finish_activity`：`update_activity(status="finished", finished_at=now)` + `archive_activity` + 群公告"活动结束，已归档"。
- `_relay_advance`：目标 = `next_pending(members, from_seq)`；若无 → False；若 `last_done(members, target.seq)` 有作品则转发；设 `received_at`；群公告轮到谁。
- `_match_reconnect`：前驱 = `next_user_id == left_uid` 的成员；更新前驱 `next_user_id = left 的后继`；前驱 pending 未提交 → 私聊通知"你的下家已变更"。

- [ ] **Step 1: 写失败测试 `test/test_activity_submit.py`**

```python
"""测试活动私聊提交与流转。
运行: python test/test_activity_submit.py
"""
import os
import sys
import sqlite3
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.context as context
from core.event import Event
from core.db._base import init_schema
from core.db.activity import ActivityManager
from plugins.activity import ActivityPlugin
from test.helper import MockApiWrapper, make_private_message

DB_PATH = "/tmp/test_activity_submit.db"
GID = 296470819


class _Db:
    def __init__(self, conn):
        self.activity = ActivityManager(conn)


def _setup_activity(db, type_):
    aid = db.activity.create_activity(
        GID, type_, "t", None, "1",
        hours_per_user=24.0 if type_ == "relay" else None,
        deadline=None if type_ == "relay" else "2026-09-15 20:00:00",
    )
    for uid, nick in (("100", "A"), ("200", "B"), ("300", "C")):
        db.activity.add_member(aid, uid, nick)
    db.activity.update_activity(aid, status="running")
    if type_ == "relay":
        db.activity.set_ring(aid, [("100", "200", 1), ("200", "300", 2), ("300", None, 3)])
    else:
        db.activity.set_ring(aid, [("100", "200", 1), ("200", "300", 2), ("300", "100", 3)])
    return aid


class TestSubmit(unittest.TestCase):
    def setUp(self):
        for p in (DB_PATH, "/tmp/test_activity_archive_submit"):
            if os.path.exists(p):
                if os.path.isdir(p):
                    import shutil; shutil.rmtree(p)
                else:
                    os.remove(p)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)
        context.python_data_path = "/tmp/test_activity_archive_submit"

    def tearDown(self):
        self.conn.close()

    def _submit(self, user_id, text_body="", arg=""):
        full = f"/提交 {arg}".strip() + (f" {text_body}" if text_body else "")
        raw = make_private_message("", user_id=user_id)
        raw["message"] = [{"type": "text", "data": {"text": full}}]
        plugin = ActivityPlugin.__new__(ActivityPlugin)
        plugin.bot_event = Event(raw)
        plugin.api = MockApiWrapper(raw)
        plugin.dbmanager = self.db
        return plugin

    def test_relay_flow(self):
        aid = _setup_activity(self.db, "relay")
        p = self._submit(100, "第一章作品")
        p.handle()
        m = self.db.activity.get_member(aid, "100")
        self.assertEqual(m["status"], "done")
        self.assertEqual(m["content"], "第一章作品")
        b = self.db.activity.get_member(aid, "200")
        self.assertIsNotNone(b["received_at"])          # 顺延并开始计时
        # B 收到了接力作品（私聊转发）
        fwd = [c for a, c in p.api.api_calls if a == "send_private_msg"]
        self.assertTrue(any(c["user_id"] == 200 for c in fwd))

    def test_submit_wrong_turn(self):
        aid = _setup_activity(self.db, "relay")
        self._submit(200, "抢先").handle()
        self.assertEqual(self.db.activity.get_member(aid, "200")["status"], "pending")

    def test_match_anonymous_forward(self):
        aid = _setup_activity(self.db, "match")
        p = self._submit(100, "给B的礼物")
        p.handle()
        m = self.db.activity.get_member(aid, "100")
        self.assertEqual(m["status"], "done")
        fwd = [c for a, c in p.api.api_calls if a == "send_private_msg"]
        to_b = [c for c in fwd if c["user_id"] == 200]
        self.assertTrue(to_b, "应匿名私聊转发给下家 B")
        texts = "".join(s["data"]["text"] for s in to_b[0]["message"] if s["type"] == "text")
        self.assertIn("给B的礼物", texts)
        self.assertNotIn("A", texts)                    # 匿名：不泄露发送者昵称 A

    def test_duplicate_submit(self):
        aid = _setup_activity(self.db, "relay")
        self._submit(100, "第一版").handle()
        self._submit(100, "第二版").handle()
        m = self.db.activity.get_member(aid, "100")
        self.assertEqual(m["content"], "第一版")        # 不覆盖

    def test_submit_finishes_relay(self):
        aid = _setup_activity(self.db, "relay")
        for uid, content in ((100, "一"), (200, "二"), (300, "三")):
            self._submit(uid, content).handle()
        act = self.db.activity.get_activity(aid)
        self.assertEqual(act["status"], "finished")
        d = f"/tmp/test_activity_archive_submit/activity_archive/{aid}"
        self.assertTrue(os.path.isfile(f"{d}/relay.md"))

    def test_submit_finishes_match(self):
        aid = _setup_activity(self.db, "match")
        for uid, content in ((100, "一"), (200, "二"), (300, "三")):
            self._submit(uid, content).handle()
        act = self.db.activity.get_activity(aid)
        self.assertEqual(act["status"], "finished")
        d = f"/tmp/test_activity_archive_submit/activity_archive/{aid}"
        self.assertTrue(os.path.isfile(f"{d}/match.md"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python test/test_activity_submit.py`
Expected: 失败（`_handle_submit` 未实现）

- [ ] **Step 3: 在 `plugins/activity/__init__.py` 追加提交处理与辅助函数**

`ActivityPlugin` 内追加（替换 Task 4 中 `handle()` 里的占位调用，`_handle_submit` 为新方法）：

```python
    # ── 私聊提交 ──────────────────────────────────

    def _handle_submit(self, args: list[str]):
        uid = str(self.bot_event.user_id)
        if self.bot_event.user_id is None:
            return
        act = None
        if args:
            try:
                act = self.dbmanager.activity.get_running_activity_for_user_and_id(
                    uid, int(args[0]))
            except ValueError:
                self.api.send_msg(text("活动编号无效"))
                return
        else:
            acts = self.dbmanager.activity.get_running_activities_for_user(uid)
            if len(acts) == 1:
                act = acts[0]
            elif len(acts) > 1:
                ids = "、".join(str(a["id"]) for a in acts)
                self.api.send_msg(text(f"你参与了多个活动，请使用 /提交 <活动id>（{ids}）"))
                return
        if not act:
            self.api.send_msg(text("你不在任何进行中的活动中"))
            return
        member = self.dbmanager.activity.get_member(act["id"], uid)
        if not member or member["status"] != "pending":
            self.api.send_msg(text("你已提交过作品或不在活动中"))
            return
        if act["type"] == "relay":
            cur = current_turn(self.dbmanager.activity.get_members(act["id"]))
            if not cur or cur["user_id"] != uid:
                self.api.send_msg(text("还没轮到你提交"))
                return
        content, image_files = self._extract_submission()
        if not content and not image_files:
            self.api.send_msg(text("请随 /提交 附上作品（文字或图片）"))
            return
        saved = self._download_images(act["id"], member["seq"], image_files)
        if len(saved) != len(image_files):
            self.api.send_msg(text("作品图片下载失败，请重试"))
            return
        now = _now()
        self.dbmanager.activity.update_member(
            act["id"], uid, status="done", content=content or None,
            images=json.dumps(saved) if saved else None, submitted_at=now)
        self.api.send_msg(text("提交成功！"))
        members = self.dbmanager.activity.get_members(act["id"])
        if act["type"] == "relay":
            self._announce_group(act["group_id"],
                                 f"第 {member['seq']} 棒 {member['nickname']} 完成接力")
            if not _relay_advance(self.api, self.dbmanager, act, members, member["seq"]):
                _finish_activity(self.api, self.dbmanager, act)
        else:
            self._announce_group(act["group_id"], f"{member['nickname']} 提交了作品")
            if all(m["status"] == "done" for m in members):
                _finish_activity(self.api, self.dbmanager, act)
            else:
                self._forward_work(act, members, member)

    def _extract_submission(self) -> tuple[str, list[str]]:
        """从消息段提取正文与图片文件（命令文本之后的部分为正文）。"""
        text_parts, images = [], []
        for seg in self.bot_event.message:
            if seg.get("type") == "image":
                images.append(seg.get("data", {}).get("file", ""))
            elif seg.get("type") == "text":
                text_parts.append(seg.get("data", {}).get("text", "").strip())
        body = " ".join(text_parts).strip()
        if body.startswith("/提交"):
            body = body[len("/提交"):].strip()
        sp = body.split(" ", 1)
        if len(sp) == 2 and sp[0].isdigit():
            body = sp[1].strip()
        return body, [f for f in images if f]

    def _download_images(self, activity_id: int, seq: int, image_files: list[str]) -> list[str]:
        from core.utils import download_image
        saved = []
        for n, f in enumerate(image_files, 1):
            ext = os.path.splitext(f)[1] or ".jpg"
            local = archive_mod.image_path(activity_id, seq, n, ext)
            url = self.api.get_image_url(f)
            if not url:
                return []
            ok, _ = download_image(url, local)
            if not ok:
                return []
            saved.append(os.path.basename(local))
        return saved

    def _forward_work(self, act: dict, members: list[dict], member: dict):
        """match：把 member 的作品匿名转发给其下家。"""
        recipient = self.dbmanager.activity.get_member(act["id"], member["next_user_id"])
        if not recipient or recipient["status"] != "pending":
            return
        self._send_private(
            int(member["next_user_id"]),
            text(f"你收到了一份作品（活动「{act['title']}」）："),
            *self._work_segments(member),
        )
```

`ActivityPlugin` 内新增 `_work_segments` 实例方法（内部转发用），模块级同名函数供 `_relay_advance` 用：

```python
    def _work_segments(self, member: dict) -> list[dict]:
        return _work_segments(member)
```

模块级辅助函数（追加到文件末尾）：

```python
def _work_segments(member: dict) -> list[dict]:
    segs = []
    if member.get("content"):
        segs.append(text(member["content"]))
    try:
        names = json.loads(member["images"]) if member.get("images") else []
    except (TypeError, ValueError):
        names = []
    for name in names:
        segs.append({"type": "image", "data": {"file": name}})
    return segs


def _relay_advance(api, db, act: dict, members: list[dict], from_seq: int) -> bool:
    """把作品顺延给 from_seq 之后第一个 pending 成员。返回 False 表示链已走完。"""
    from .logic import next_pending, last_done
    target = next_pending(members, from_seq)
    if not target:
        return False
    prev = last_done(members, target["seq"])
    if prev and (prev["content"] or prev.get("images")):
        _send_private(
            api, int(target["user_id"]),
            text(f"接力作品（活动「{act['title']}」）："),
            *_work_segments(prev),
        )
    db.update_member(act["id"], target["user_id"], received_at=_now())
    _announce_group(
        api, act["group_id"],
        f"轮到 {target['nickname']} 接力！请于 {act['hours_per_user']:g} 小时内完成，私聊 /提交 作品。",
    )
    return True


def _match_reconnect(api, db, act: dict, left_uid: str, members: list[dict]):
    """匹配环闭合：left_uid 的前驱 next 改为其后继（Y→X→D 退出 X 后变 Y→D）。"""
    pred = next((m for m in members if m["next_user_id"] == left_uid), None)
    if not pred:
        return
    left = next((m for m in members if m["user_id"] == left_uid), None)
    new_next = left["next_user_id"] if left else None
    db.update_member(act["id"], pred["user_id"], next_user_id=new_next)
    if pred["status"] == "pending":
        _send_private(
            api, int(pred["user_id"]),
            text("你的下家已退出，请继续创作，活动截止时间不变。"),
        )


def _finish_activity(api, db, act: dict):
    now = _now()
    db.update_activity(act["id"], status="finished", finished_at=now)
    fresh = db.get_activity(act["id"])
    members = db.get_members(act["id"])
    archive_mod.archive_activity(fresh, members)
    _announce_group(api, act["group_id"], f"活动「{act['title']}」结束，已归档！")
```

- [ ] **Step 4: 运行确认通过**

Run: `python test/test_activity_submit.py && python test/test_activity_commands.py`
Expected: 两者均 `OK`

- [ ] **Step 5: 提交**

```bash
git add plugins/activity/__init__.py test/test_activity_submit.py
git commit -m "feat(活动): 新增私聊提交与作品流转（接力顺延/匿名转发/收尾归档）"
```

---

### Task 6: 心跳插件（接龙超时跳过 / 匹配截止结束）

**Files:**
- Modify: `plugins/activity/__init__.py`
- Test: `test/test_activity_timer.py`

**Interfaces:**
- Consumes: `logic.is_timeout / current_turn`、`_relay_advance / _finish_activity / _announce_group`（Task 5）
- Produces: `ActivityTimerPlugin(Plugin)`，`name = "activity_timer"`。`match(event_type)`：`event_type == "meta"` 且 60 秒节流通过（类级 dict `_last_scan`，键为类名，值为上次扫描时间戳）；`handle()` 扫描全部 running 活动。

- [ ] **Step 1: 写失败测试 `test/test_activity_timer.py`**

```python
"""测试活动心跳（超时跳过/截止结束）。
运行: python test/test_activity_timer.py
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

from core.db._base import init_schema
from core.db.activity import ActivityManager
from core.event import Event
from plugins.activity import ActivityTimerPlugin
from test.helper import MockApiWrapper
import core.context as context

DB_PATH = "/tmp/test_activity_timer.db"
GID = 296470819


class _Db:
    def __init__(self, conn):
        self.activity = ActivityManager(conn)


def _setup(db, type_):
    aid = db.activity.create_activity(
        GID, type_, "t", None, "1",
        hours_per_user=24.0 if type_ == "relay" else None,
        deadline=None if type_ == "relay" else "2026-09-15 20:00:00",
    )
    for uid, nick in (("100", "A"), ("200", "B")):
        db.activity.add_member(aid, uid, nick)
    db.activity.update_activity(aid, status="running")
    if type_ == "relay":
        db.activity.set_ring(aid, [("100", "200", 1), ("200", None, 2)])
    else:
        db.activity.set_ring(aid, [("100", "200", 1), ("200", "100", 2)])
    return aid


class TestTimer(unittest.TestCase):
    def setUp(self):
        for p in (DB_PATH, "/tmp/test_activity_archive_timer"):
            if os.path.exists(p):
                if os.path.isdir(p):
                    import shutil; shutil.rmtree(p)
                else:
                    os.remove(p)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)
        context.python_data_path = "/tmp/test_activity_archive_timer"
        ActivityTimerPlugin._last_scan = {}

    def tearDown(self):
        self.conn.close()

    def _plugin(self):
        raw = {"post_type": "meta", "meta_event_type": "heartbeat",
               "time": 0, "message_type": "meta_event"}
        p = ActivityTimerPlugin.__new__(ActivityTimerPlugin)
        p.bot_event = Event(raw)
        p.api = MockApiWrapper(raw)
        p.dbmanager = self.db
        return p

    def test_relay_timeout_skips(self):
        aid = _setup(self.db, "relay")
        old = (datetime.now() - timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S")
        self.db.activity.update_member(aid, "100", received_at=old)
        self._plugin().handle()
        self.assertEqual(self.db.activity.get_member(aid, "100")["status"], "skipped")
        b = self.db.activity.get_member(aid, "200")
        self.assertIsNotNone(b["received_at"])          # 顺延并开始计时

    def test_relay_no_timeout(self):
        aid = _setup(self.db, "relay")
        future = (datetime.now() + timedelta(seconds=2)).strftime("%Y-%m-%d %H:%M:%S")
        self.db.activity.update_member(aid, "100", received_at=future)
        self._plugin().handle()
        self.assertEqual(self.db.activity.get_member(aid, "100")["status"], "pending")

    def test_match_deadline_finishes(self):
        aid = _setup(self.db, "match")
        self.db.activity.update_activity(aid, deadline="2000-01-01 00:00:00")
        self._plugin().handle()
        act = self.db.activity.get_activity(aid)
        self.assertEqual(act["status"], "finished")
        self.assertEqual(self.db.activity.get_member(aid, "100")["status"], "missed")
        self.assertEqual(self.db.activity.get_member(aid, "200")["status"], "missed")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败（Task 6）**

Run: `python test/test_activity_timer.py`
Expected: 失败（`ActivityTimerPlugin` 未定义）

- [ ] **Step 3: 在 `plugins/activity/__init__.py` 追加心跳插件**

```python
@register_plugin
class ActivityTimerPlugin(Plugin):
    name = "activity_timer"
    description = "活动计时：接龙超时跳过、匹配截止结束"

    _last_scan = {}

    def match(self, event_type="meta") -> bool:
        if event_type != "meta":
            return False
        now = datetime.now()
        last = self._last_scan.get(type(self).__name__, 0)
        if now.timestamp() - last < 60:
            return False
        self._last_scan[type(self).__name__] = now.timestamp()
        return True

    def handle(self):
        try:
            self._scan()
        except Exception:
            logger.exception("ActivityTimer 处理异常")

    def _announce_group(self, group_id: int, text_body: str):
        _announce_group(self.api, group_id, text_body)

    def _scan(self):
        from .logic import is_timeout, current_turn
        now = datetime.now()
        for act in self.dbmanager.activity.get_running_activities():
            members = self.dbmanager.activity.get_members(act["id"])
            if act["type"] == "relay":
                cur = current_turn(members)
                if cur and is_timeout(cur.get("received_at"), now, act.get("hours_per_user") or 0):
                    self.dbmanager.activity.update_member(
                        act["id"], cur["user_id"], status="skipped")
                    self._announce_group(act["group_id"], f"{cur['nickname']} 超时未完成，跳过")
                    members = self.dbmanager.activity.get_members(act["id"])
                    if not _relay_advance(self.api, self.dbmanager, act, members, cur["seq"]):
                        _finish_activity(self.api, self.dbmanager, act)
            else:
                deadline = act.get("deadline")
                try:
                    due = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    continue
                if now >= due:
                    for m in members:
                        if m["status"] == "pending":
                            self.dbmanager.activity.update_member(
                                act["id"], m["user_id"], status="missed")
                    _finish_activity(self.api, self.dbmanager, act)
```

- [ ] **Step 4: 运行确认通过**

Run: `python test/test_activity_timer.py`
Expected: `OK`

- [ ] **Step 5: 提交**

```bash
git add plugins/activity/__init__.py test/test_activity_timer.py
git commit -m "feat(活动): 新增心跳计时（接龙超时跳过、匹配截止结束）"
```

---

### Task 7: Web 端归档页（checkin_gallery）

**Files:**
- Modify: `checkin_gallery/config.py`
- Create: `checkin_gallery/activity_service.py`
- Modify: `checkin_gallery/app.py`
- Create: `checkin_gallery/static/activities.html`, `checkin_gallery/static/activities.js`
- Modify: `checkin_gallery/static/profile.html`（导航加"活动"入口，参照现有 `profile/trpg` 链接写法）

**Interfaces:**
- Consumes: Task 1 的表结构与 `activity_archive/` 目录（机器人写入，web 只读）
- Produces:
  - `config.ACTIVITY_ROOT`（`_path_from_env("BOTERO_ACTIVITY_ROOT", PROJECT_ROOT / "server_data" / "activity_archive")`）
  - `activity_service.list_activities() -> list[dict]`：`id / title / type / group_id / created_at / finished_at / member_count / done_count`
  - `activity_service.get_activity(activity_id) -> dict | None`：活动 + `members`（按 seq，含 content / images 文件名）
  - 路由：`GET /api/activities`、`GET /api/activities/{id}`、`GET /archive/{id}/media/{filename}`（FileResponse，路径守卫仿 `_assert_under_root`）、`GET /archive`（静态页）

- [ ] **Step 1: `checkin_gallery/config.py` 追加 ACTIVITY_ROOT**

```python
ACTIVITY_ROOT = _path_from_env(
    "BOTERO_ACTIVITY_ROOT", PROJECT_ROOT / "server_data" / "activity_archive"
)
```

- [ ] **Step 2: 创建 `checkin_gallery/activity_service.py`**

```python
"""活动归档读取（bot 写入，web 只读）。"""
import json
import sqlite3

from checkin_gallery import config

DB_PATH = config.DB_PATH


def _rows(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def list_activities() -> list[dict]:
    return _rows(
        "SELECT a.id, a.type, a.title, a.group_id, a.created_at, a.finished_at,"
        " (SELECT COUNT(*) FROM activity_members m WHERE m.activity_id = a.id) AS member_count,"
        " (SELECT COUNT(*) FROM activity_members m WHERE m.activity_id = a.id AND m.status = 'done') AS done_count"
        " FROM activities a WHERE a.status = 'finished' ORDER BY a.id DESC"
    )


def get_activity(activity_id: int) -> dict | None:
    rows = _rows("SELECT * FROM activities WHERE id = ?", (activity_id,))
    if not rows:
        return None
    act = rows[0]
    act["members"] = _rows(
        "SELECT user_id, nickname, seq, status, submitted_at, content, images"
        " FROM activity_members WHERE activity_id = ? ORDER BY seq ASC",
        (activity_id,),
    )
    for m in act["members"]:
        try:
            m["images"] = json.loads(m["images"]) if m.get("images") else []
        except (TypeError, ValueError):
            m["images"] = []
    return act
```

- [ ] **Step 3: `checkin_gallery/app.py` 追加路由与导入（`serve_media` 守卫模式同款；导入加在文件顶部 import 区）**

```python
from checkin_gallery.activity_service import list_activities, get_activity


@app.get("/api/activities")
def api_activities():
    return {"items": list_activities()}


@app.get("/api/activities/{activity_id}")
def api_activity_detail(activity_id: int):
    act = get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    for m in act["members"]:
        m["images"] = [
            f"/archive/{activity_id}/media/{name}" for name in m.get("images", [])
        ]
    return act


def _assert_under_activity_root(path: Path) -> None:
    try:
        path.resolve().relative_to(config.ACTIVITY_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="禁止访问") from exc


@app.get("/archive/{activity_id}/media/{filename}")
def serve_activity_media(activity_id: int, filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法路径")
    path = config.ACTIVITY_ROOT / str(activity_id) / "imgs" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    _assert_under_activity_root(path)
    return FileResponse(path)


@app.get("/archive")
def archive_page():
    page = STATIC_DIR / "activities.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少活动归档页")
    return FileResponse(page)
```

- [ ] **Step 4: 创建 `static/activities.html`（骨架，样式复用 gallery.css）**

```html
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>活动归档 - 小埃同学</title>
<link rel="stylesheet" href="/static/gallery.css">
</head>
<body>
<nav><a href="/">图库</a> <a href="/profile">个人主页</a> <span>活动归档</span></nav>
<main>
  <h1>活动归档</h1>
  <div id="activity-list"></div>
  <div id="activity-detail" hidden></div>
</main>
<script src="/static/activities.js"></script>
</body>
</html>
```

- [ ] **Step 5: 创建 `static/activities.js`（列表 + 详情渲染）**

```js
const listEl = document.getElementById("activity-list");
const detailEl = document.getElementById("activity-detail");
const TYPE_LABEL = { relay: "接龙", match: "匹配下家" };
const STATUS_LABEL = { done: "已完成", skipped: "超时跳过", missed: "未提交", left: "已退出" };

async function loadList() {
  const res = await fetch("/api/activities");
  const { items } = await res.json();
  listEl.innerHTML = items.map(a => `
    <div class="activity-card" onclick="showDetail(${a.id})">
      <strong>${a.title}</strong>（${TYPE_LABEL[a.type] || a.type}）
      <span>${a.done_count}/${a.member_count} 人完成</span>
      <div class="muted">${a.created_at} ~ ${a.finished_at}</div>
    </div>`).join("") || "<p>暂无归档活动</p>";
}

async function showDetail(id) {
  const res = await fetch(`/api/activities/${id}`);
  const act = await res.json();
  detailEl.hidden = false;
  detailEl.innerHTML = `
    <h2>${act.title}</h2>
    <div class="muted">${TYPE_LABEL[act.type]} · ${act.created_at} ~ ${act.finished_at}</div>
    ${act.theme ? `<p>主题：${act.theme}</p>` : ""}
    ${act.members.map(m => `
      <section class="work-block">
        <h3>${m.nickname}（${m.user_id}）· ${STATUS_LABEL[m.status] || m.status}</h3>
        ${m.submitted_at ? `<div class="muted">${m.submitted_at}</div>` : ""}
        ${m.content ? `<p class="work-content">${m.content.replace(/\n/g, "<br>")}</p>` : ""}
        ${m.images.map(u => `<img class="work-img" src="${u}">`).join("")}
      </section>`).join("")}
    <button onclick="closeDetail()">返回列表</button>`;
}

function closeDetail() { detailEl.hidden = true; }

loadList();
```

- [ ] **Step 6: `profile.html` 导航加入口（仿现有链接行）**

```html
<a href="/archive">活动</a>
```

- [ ] **Step 7: 运行验证**

Run: `python -m checkin_gallery --port 8877`（后台起服务）
Expected: 访问 `http://127.0.0.1:8877/archive` 显示归档页；`/api/activities` 返回 JSON 数组（可为空）；已有归档时图片可访问

- [ ] **Step 8: 提交**

```bash
git add checkin_gallery/config.py checkin_gallery/activity_service.py checkin_gallery/app.py checkin_gallery/static/activities.html checkin_gallery/static/activities.js checkin_gallery/static/profile.html
git commit -m "feat(网页): 新增活动归档页与接口"
```

---

### Task 8: 菜单与文档同步

**Files:**
- Modify: `plugins/bot_menu_text.py`
- Modify: `specs/plugin-catalog.md`
- Modify: `specs/database.md`
- Modify: `specs/web-gallery.md`
- Modify: `KNOWLEDGE_BASE.md` / `kb/QUICK_REFERENCE.md`

- [ ] **Step 1: `plugins/bot_menu_text.py` 新增指令说明**

在 `BOT_MENU_TEXT` 追加：

```
/活动 创建 接龙 <标题> [每人小时数]    发布接龙活动
/活动 创建 匹配 <标题> <截止时间>      发布匹配活动（圆桌下家）
/活动 加入 / 退出                     报名 / 退出活动
/活动 开始                            开始活动（创建人）
/活动 状态 / 结束                     查看进度 / 结束活动
/提交 [活动id]                        （私聊）提交作品
```

- [ ] **Step 2: `specs/plugin-catalog.md` 新增条目**

消息插件表追加：
`plugins/activity/` | `ActivityPlugin` | `activity` | CommandPlugin | `/活动 …` | 群活动：接龙（每人限时）与匹配下家（圆桌单环、匿名转发）
`plugins/activity/` | `ActivityTimerPlugin` | `activity_timer` | 自定义 meta | (meta 心跳) | 活动计时：接龙超时跳过、匹配截止结束

- [ ] **Step 3: `specs/database.md` 新增两表**

`activities` 与 `activity_members` 的表结构与说明（复制 Task 1 的 DDL 与列注释）。

- [ ] **Step 4: `specs/web-gallery.md` 新增归档页**

`/archive` 页面、`/api/activities`、`/api/activities/{id}`、`/archive/{id}/media/{file}` 路由与 `ACTIVITY_ROOT` 配置说明。

- [ ] **Step 5: `KNOWLEDGE_BASE.md` 与 `kb/QUICK_REFERENCE.md` 同步**

- 指令表加 `/活动`、`/提交`
- 插件目录加 `activity`、`activity_timer`
- 数据库章节加两张新表
- 目录结构注释中提及 `server_data/activity_archive/`

- [ ] **Step 6: 提交**

```bash
git add plugins/bot_menu_text.py specs/plugin-catalog.md specs/database.md specs/web-gallery.md KNOWLEDGE_BASE.md kb/QUICK_REFERENCE.md
git commit -m "docs(活动): 同步菜单、specs 与知识库"
```

---

## 最终验收

- [ ] `python test/test_activity_db.py && python test/test_activity_logic.py && python test/test_activity_archive.py && python test/test_activity_commands.py && python test/test_activity_submit.py && python test/test_activity_timer.py` 全部 `OK`
- [ ] `python main.py` 启动无异常，`/活动 创建 接龙 测试` 群内可用
- [ ] 私聊 `/提交` 全流程：接龙顺延 / 匹配匿名转发 / 全员完成自动归档
- [ ] 心跳跳过与截止结束（可临时把 hours_per_user/deadline 调成 0 验证）
- [ ] `python -m checkin_gallery` 的 `/archive` 页展示已归档活动与图片
