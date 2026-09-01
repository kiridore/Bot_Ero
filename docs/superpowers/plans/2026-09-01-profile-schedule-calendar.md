# 个人主页日程日历 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 个人主页新增日历式日程页 `/profile/schedule`（展示自己+全群闹钟、循环自动展开、点选添加/编辑/取消），替代旧 `/alarms` 页。

**Architecture:** 服务端复用 `plugins/group_alarm/parser.py` 的循环推进权威逻辑按月展开（前端零重复实现）；`webapp/alarms` 模块原地扩展（新增 calendar API、scope 字段、PUT 编辑），不搬家；前端手写月历网格（无框架、无构建），表单/列表从旧 alarms.js 移植改造。

**Tech Stack:** FastAPI 同步路由 + SQLite（`core.database_manager.DbManager`）+ 原生 JS/CSS 静态页；测试 = 进程内 unittest + `test/scripts/check_*.py` 脚本式 TestClient + `test/test_*.js` node DOM stub（三类均被现有回归自动发现）。

**Spec:** `docs/superpowers/specs/2026-09-01-profile-schedule-calendar-design.md`（决策 D1–D6 与边界情况以此为准）

## Global Constraints

- bot 进程禁 `async`/`await`；webapp 路由用同步 `def`（本计划全部同步）
- SQL 一律 `?` 参数化，禁止 f-string SQL
- Commit 消息中文 + Conventional Commits，按逻辑分块（本计划 4 个 commit）
- Task 4（用户可见切换）commit 内 MUST 同步 `CHANGELOG.md` 新增 `[1.32.0]` 节 + `core/config.py::BOTERO_VERSION = "1.32.0"`
- `specs/web-gallery.md` 随 Task 1/2/4 分别更新对应小节
- 群闹钟 group 一律用 `core.config.GROUP_ID`（env `BOTERO_GROUP_ID`，默认 296470819），**不是** `core.context.DEFAULT_GROUP_ID`
- 测试统一入口 `pytest`（conftest 已把 `BOTERO_*` 数据路径重定向到临时目录，绝不触碰真实 `data.db`）；脚本式套件另需 `python test/scripts/check_alarm_calendar_api.py` 可独立运行
- 前端静态文件名全局唯一（`webapp/static/` 平铺合并），新文件：`schedule.html` / `schedule.js` / `schedule.css`

---

### Task 1: 服务端月历展开 + `GET /api/me/calendar`

**Files:**
- Modify: `webapp/alarms/alarm_service.py`（新增 `calendar_month`）
- Modify: `webapp/alarms/app.py`（新增 calendar 路由）
- Modify: `core/onebot_client.py`（`resolve_display_name` 加 `@lru_cache`）
- Create: `test/test_alarm_calendar.py`（进程内，展开逻辑）
- Create: `test/scripts/check_alarm_calendar_api.py`（脚本式，HTTP 层）
- Modify: `specs/web-gallery.md`（API 表）

**Interfaces:**
- Consumes: `plugins/group_alarm/parser.py` 的 `_next_recurring_fire(prev, now, kind, a, b, c)`、`_format_recur_desc(k, a, b, c)`（经 `_load_group_alarm()` 按路径加载，现有机制）；`core.database_manager.DbManager`；`core.onebot_client.resolve_display_name(user_id: str) -> str`
- Produces: `calendar_month(user_id: str, month: str) -> dict`，返回 `{"month": "YYYY-MM", "days": {"YYYY-MM-DD": [{id, time, content, date, is_mine, scope, is_recurring, recur_kind, recur_a, recur_b, recur_desc, creator_name}]}, "min_lead_minutes: 5}`；`GET /api/me/calendar?month=YYYY-MM`（登录必需，month 不合法 400）

- [ ] **Step 1: 写失败测试（进程内展开逻辑）**

创建 `test/test_alarm_calendar.py`：

```python
"""日历展开逻辑（webapp.alarms.alarm_service.calendar_month）进程内测试。

conftest 已将 BOTERO_DB_PATH 重定向到会话临时库；resolve_display_name 打桩避免真实 HTTP。
"""

import unittest
from datetime import datetime, timedelta
from calendar import monthrange

from core.database_manager import DbManager
import webapp.alarms.alarm_service as alarm_service

alarm_service.resolve_display_name = lambda uid: f"用户{uid}"


def _month_of(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


class CalendarExpandTest(unittest.TestCase):
    def setUp(self):
        db = DbManager()
        db.cur.execute("DELETE FROM group_alarms")
        db.conn.commit()
        self.me, self.other = "10001", "10002"

    def _add(self, uid, fire, content, recur=None, is_private=True, group_id=None):
        db = DbManager()
        return db.alarm.add(int(uid), fire, content, group_id=group_id, is_private=is_private, recur=recur)

    def test_single_shot_lands_on_day(self):
        fire = datetime.now() + timedelta(minutes=30)
        self._add(self.me, fire, "单次")
        data = alarm_service.calendar_month(self.me, _month_of(fire))
        key = fire.strftime("%Y-%m-%d")
        self.assertIn(key, data["days"])
        item = data["days"][key][0]
        self.assertEqual(item["time"], fire.strftime("%H:%M"))
        self.assertTrue(item["is_mine"])
        self.assertEqual(item["scope"], "private")
        self.assertFalse(item["is_recurring"])

    def test_daily_recurring_no_history(self):
        fire = (datetime.now() + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        self._add(self.me, fire, "吃药", recur=(1, 1, 0, 0))
        data = alarm_service.calendar_month(self.me, _month_of(fire))
        tomorrow = fire.strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertIn(tomorrow, data["days"])  # 从 fire_at 向前展开
        self.assertNotIn(today, data["days"])  # 历史不回溯
        if (fire + timedelta(days=1)).month == fire.month:
            self.assertIn((fire + timedelta(days=1)).strftime("%Y-%m-%d"), data["days"])

    def test_weekly_steps_seven_days(self):
        now = datetime.now()
        delta = (2 - now.weekday()) % 7 or 7  # 下一个周三，至少明天
        fire = (now + timedelta(days=delta)).replace(hour=9, minute=30, second=0, microsecond=0)
        self._add(self.me, fire, "周会", recur=(2, 3, 0, 0))
        data = alarm_service.calendar_month(self.me, _month_of(fire))
        self.assertIn(fire.strftime("%Y-%m-%d"), data["days"])
        nxt = fire + timedelta(days=7)
        if nxt.month == fire.month:
            self.assertIn(nxt.strftime("%Y-%m-%d"), data["days"])

    def test_monthly_clamps_short_next_month(self):
        # 找一个「31 天月且下月不足 31 天」的未来月份
        y, m = datetime.now().year, datetime.now().month
        for _ in range(24):
            if monthrange(y, m)[1] == 31 and monthrange(y + (m == 12), m % 12 + 1)[1] < 31:
                break
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        fire = datetime(y, m, 31, 12, 0)
        if fire <= datetime.now():  # 保险：再推一年
            fire = datetime(y + 1, m, 31, 12, 0)
            y += 1
        self._add(self.me, fire, "月末", recur=(4, 31, 0, 0))
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        data = alarm_service.calendar_month(self.me, f"{ny:04d}-{nm:02d}")
        clamped = f"{ny:04d}-{nm:02d}-{monthrange(ny, nm)[1]:02d}"
        self.assertIn(clamped, data["days"])  # 31 → 下月末钳位

    def test_yearly_clamps_feb29(self):
        y = datetime.now().year + 1
        while not (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)):
            y += 1
        fire = datetime(y, 2, 29, 12, 0)
        self._add(self.me, fire, "四年一度", recur=(3, 2, 29, 0))
        data = alarm_service.calendar_month(self.me, f"{y + 1}-02")
        self.assertIn(f"{y + 1}-02-28", data["days"])  # 2/29 → 次年 2/28 钳位

    def test_fire_next_month_leaves_current_empty(self):
        now = datetime.now()
        ny, nm = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
        fire = datetime(ny, nm, 15, 10, 0)
        self._add(self.me, fire, "每天", recur=(1, 1, 0, 0))
        data = alarm_service.calendar_month(self.me, now.strftime("%Y-%m"))
        self.assertEqual(data["days"], {})  # fire_at 在下月 → 本月无条目

    def test_privacy_others_private_hidden(self):
        fire = datetime.now() + timedelta(hours=2)
        key = fire.strftime("%Y-%m-%d")
        self._add(self.other, fire, "别人的私聊", recur=None, is_private=True)
        self._add(self.other, fire.replace(minute=30), "别人的群", recur=None, is_private=False, group_id=123)
        data = alarm_service.calendar_month(self.me, _month_of(fire))
        contents = [it["content"] for it in data["days"].get(key, [])]
        self.assertNotIn("别人的私聊", contents)  # 他人私聊永不下发
        self.assertIn("别人的群", contents)
        other_item = next(it for it in data["days"][key] if it["content"] == "别人的群")
        self.assertFalse(other_item["is_mine"])
        self.assertEqual(other_item["scope"], "group")
        self.assertEqual(other_item["creator_name"], f"用户{self.other}")

    def test_sorted_by_time(self):
        fire = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        self._add(self.me, fire.replace(hour=20), "晚")
        self._add(self.me, fire.replace(hour=8), "早")
        data = alarm_service.calendar_month(self.me, _month_of(fire))
        items = data["days"][fire.strftime("%Y-%m-%d")]
        self.assertEqual([i["content"] for i in items], ["早", "晚"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest test/test_alarm_calendar.py -v`
Expected: FAIL/ERROR — `calendar_month` 不存在（AttributeError）

- [ ] **Step 3: 实现 `calendar_month` + 路由 + lru_cache**

`webapp/alarms/alarm_service.py` 头部 import 区改为（新增 `calendar`、`datetime`、`GROUP_ID`、`resolve_display_name`）：

```python
import calendar as _cal
from datetime import datetime
```

```python
from core.config import GROUP_ID
from core.onebot_client import resolve_display_name
```

文件末尾追加：

```python
def calendar_month(user_id: str, month: str) -> dict:
    """按月展开闹钟（服务端权威展开，前端零重复实现）。

    只向前展开：单次看 fire_at 是否落月内；循环从 fire_at 推进到月末。
    # ponytail: fire_at 落后于 now（bot 停机）时显示其迟到的待触发项，与列表视图一致
    """
    ga = _load_group_alarm()
    uid = int(user_id)
    y, m = int(month[:4]), int(month[5:7])
    month_start = datetime(y, m, 1)
    month_end = datetime(y, m, _cal.monthrange(y, m)[1], 23, 59, 59)
    now = datetime.now()

    db = DbManager()
    db.cur.execute(
        """
        SELECT id, creator_user_id, fire_at, content, is_private,
               is_recurring, recur_kind, recur_a, recur_b, recur_c
        FROM group_alarms
        WHERE fired = 0 AND (creator_user_id = ? OR is_private = 0)
        """,
        (uid,),
    )
    rows = db.cur.fetchall()
    days: dict[str, list[dict]] = {}

    def place(id_, creator, fire_s, content, is_priv, is_rec, rk, ra, rb, rc, occ: datetime):
        is_recurring = int(is_rec or 0) and int(rk or 0) > 0
        days.setdefault(occ.strftime("%Y-%m-%d"), []).append({
            "id": int(id_),
            "time": occ.strftime("%H:%M"),
            "content": content,
            "date": occ.strftime("%Y-%m-%d"),
            "is_mine": int(creator) == uid,
            "scope": "private" if int(is_priv or 0) else "group",
            "is_recurring": is_recurring,
            "recur_kind": int(rk or 0),
            "recur_a": int(ra or 0),
            "recur_b": int(rb or 0),
            "recur_desc": ga._format_recur_desc(int(rk), int(ra or 0), int(rb or 0), int(rc or 0)) if is_recurring else None,
            "creator_name": resolve_display_name(str(creator)),
        })

    for id_, creator, fire_s, content, is_priv, is_rec, rk, ra, rb, rc in rows:
        fire = datetime.strptime(fire_s, "%Y-%m-%d %H:%M:%S")
        is_recurring = int(is_rec or 0) and int(rk or 0) > 0
        if not is_recurring:
            if month_start <= fire <= month_end:
                place(id_, creator, fire_s, content, is_priv, is_rec, rk, ra, rb, rc, fire)
            continue
        occ = fire if fire > now else ga._next_recurring_fire(fire, now, int(rk), int(ra), int(rb), int(rc))
        guard = 0
        while occ <= month_end and guard < 10000:
            if occ >= month_start:
                place(id_, creator, fire_s, content, is_priv, is_rec, rk, ra, rb, rc, occ)
            occ = ga._next_recurring_fire(occ, occ, int(rk), int(ra), int(rb), int(rc))
            guard += 1

    for items in days.values():
        items.sort(key=lambda x: (x["time"], x["id"]))
    return {"month": month, "days": days, "min_lead_minutes": 5}
```

注意：`id_` 作为 `place` 首参显式传入，不做闭包捕获。

`webapp/alarms/app.py`：import 区加 `import re`、`from fastapi import Query`，router 注册前加：

```python
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
```

`from webapp.alarms.alarm_service import ...` 行追加 `calendar_month`，并新增路由：

```python
@router.get("/api/me/calendar")
def api_calendar(
    user_id: Annotated[str, Depends(get_current_user_id)],
    month: str = Query(...),
):
    if not _MONTH_RE.match(month):
        raise HTTPException(status_code=400, detail="month 须为 YYYY-MM")
    return calendar_month(user_id, month)
```

`core/onebot_client.py`：`resolve_display_name` 函数定义上方加装饰器（与 `resolve_avatar_url` 同款；日历每请求按创建者解析，不缓存会 HTTP 风暴）：

```python
@lru_cache(maxsize=4096)
def resolve_display_name(user_id: str) -> str:
```

- [ ] **Step 4: 运行进程内测试通过**

Run: `python -m pytest test/test_alarm_calendar.py -v`
Expected: 8 passed

- [ ] **Step 5: 写脚本式 API 测试（HTTP 层）**

创建 `test/scripts/check_alarm_calendar_api.py`（模式照抄 `check_activities_api.py`）：

```python
"""日程日历 API 行为测试：鉴权、month 校验、展开下发、隐私边界。

独立进程运行: python test/scripts/check_alarm_calendar_api.py
（pytest 由 test/test_webapp_api_suites.py 子进程纳入统一回归）
"""

import os
import sqlite3
import tempfile

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_cal_test_")
_db = os.path.join(_tmp, "test.db")
os.environ["BOTERO_DB_PATH"] = _db

_conn = sqlite3.connect(_db)
_cur = _conn.cursor()
from core.database_manager import init_schema  # noqa: E402
init_schema(_conn, _cur)
_conn.commit()
_conn.close()

from datetime import datetime, timedelta  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from core.database_manager import DbManager  # noqa: E402
from webapp.app import app  # noqa: E402

client = TestClient(app)
DB = DbManager()  # 模块级强引用：避免临时 DbManager() 被共享连接关闭
ME, OTHER = "111", "222"
H = {"Authorization": "Bearer " + make_login_key(ME)}
JH = {"Content-Type": "application/json", **H}
OH = {"Authorization": "Bearer " + make_login_key(OTHER)}

import webapp.alarms.alarm_service as svc  # noqa: E402
svc.resolve_display_name = lambda uid: "用户" + str(uid)


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


fail = 0
NEXT_MONTH = (datetime.now().replace(day=1) + timedelta(days=32)).replace(day=1)
MKEY = NEXT_MONTH.strftime("%Y-%m")
FIRE = NEXT_MONTH.replace(day=10, hour=8, minute=0)

# —— 鉴权与参数校验 ——
r = client.get(f"/api/me/calendar?month={MKEY}")
check("未登录 401", r.status_code == 401)
r = client.get("/api/me/calendar?month=2026-13", headers=H)
check("month 非法 400", r.status_code == 400, r.text)
r = client.get("/api/me/calendar?month=2026-9", headers=H)
check("month 非两位 400", r.status_code == 400)

# —— 展开下发与隐私 ——
DB.alarm.add(int(ME), FIRE, "我的群闹钟", group_id=123, is_private=False)
DB.alarm.add(int(OTHER), FIRE.replace(hour=9), "别人的群闹钟", group_id=123, is_private=False)
DB.alarm.add(int(OTHER), FIRE.replace(hour=10), "别人的私聊", group_id=None, is_private=True)
DB.alarm.add(int(ME), FIRE.replace(hour=11), "我的每天", recur=(1, 1, 0, 0))

r = client.get(f"/api/me/calendar?month={MKEY}", headers=H)
data = r.json()
key = FIRE.strftime("%Y-%m-%d")
names = [it["content"] for it in data["days"].get(key, [])]
check("日历 200 且含我的条目", r.status_code == 200 and "我的群闹钟" in names)
check("含别人的群闹钟且非本人标记", "别人的群闹钟" in names and any(
    it["content"] == "别人的群闹钟" and not it["is_mine"] and it["scope"] == "group"
    for it in data["days"][key]))
check("他人私聊闹钟不下发", "别人的私聊" not in names)
check("循环闹钟同日展开", "我的每天" in names)
next_key = (FIRE + timedelta(days=1)).strftime("%Y-%m-%d")
check("循环闹钟次日展开", next_key in data["days"])
check("同日按时间排序", [it["time"] for it in data["days"][key]]
      == sorted(it["time"] for it in data["days"][key]))

print(f"\n{'全部通过' if fail == 0 else f'{fail} 项失败'}")
sys.exit(1 if fail else 0)
```

- [ ] **Step 6: 运行脚本确认通过**

Run: `python test/scripts/check_alarm_calendar_api.py`
Expected: 全部 ok，退出码 0

- [ ] **Step 7: 更新 specs/web-gallery.md API 表**

`### 闹钟（alarms 模块）` 的端点表新增两行（表格式照现有）：

```markdown
| `GET` | `/api/me/calendar?month=YYYY-MM` | 必须 | 月历展开（自己的 + 全部群闹钟；循环向前展开） |
| `PUT` | `/api/me/alarms/{id}` | 必须 | 编辑闹钟（仅创建者；重新解析规则与范围） |
```

（PUT 行此任务先占位登记，Task 2 实现；若不想提前登记，可挪到 Task 2 一并加——选择：**挪到 Task 2**，本任务只加 calendar 行。）

- [ ] **Step 8: 全量回归 + 提交**

Run: `python -m pytest`
Expected: 全部通过

```bash
git add webapp/alarms/alarm_service.py webapp/alarms/app.py core/onebot_client.py test/test_alarm_calendar.py test/scripts/check_alarm_calendar_api.py specs/web-gallery.md
git commit -m "feat(日程): 服务端月历展开与日历 API"
```

---

### Task 2: scope 字段 + `PUT /api/me/alarms/{id}` 编辑

**Files:**
- Modify: `webapp/alarms/alarm_service.py`（`create_alarm` 加 scope；新增 `update_alarm`；`_format_alarm_row` 输出结构化 recur 字段）
- Modify: `webapp/alarms/app.py`（`AlarmCreateIn.scope`；PUT 路由）
- Modify: `test/test_alarm_calendar.py`（编辑语义用例）
- Modify: `test/scripts/check_alarm_calendar_api.py`（scope/PUT/权限用例）
- Modify: `specs/web-gallery.md`（PUT 行 + POST 说明）

**Interfaces:**
- Consumes: Task 1 全部；`_build_alarm_body(payload)`、`ga._parse_create_body(body)`（现有）
- Produces: `create_alarm(user_id, payload)`（payload 可含 `scope: "private"|"group"`，默认 private）；`update_alarm(user_id: str, alarm_id: int, payload: dict) -> {"id": int, "message": str}`；列表项/日历项均含 `recur_kind/recur_a/recur_b`（前端编辑预填用）

- [ ] **Step 1: 写失败测试（进程内编辑语义）**

`test/test_alarm_calendar.py` 追加测试类：

```python
class UpdateAlarmTest(unittest.TestCase):
    def setUp(self):
        db = DbManager()
        db.cur.execute("DELETE FROM group_alarms")
        db.conn.commit()
        self.me, self.other = "10001", "10002"

    def test_update_recomputes_rule_and_keeps_id(self):
        fire = datetime.now() + timedelta(days=1)
        aid = DbManager().alarm.add(int(self.me), fire, "旧内容")
        new_fire = datetime.now() + timedelta(days=2)
        out = alarm_service.update_alarm(self.me, aid, {
            "content": "新内容", "schedule_type": "once_date",
            "date": new_fire.strftime("%Y-%m-%d"), "time": "09:30",
            "scope": "private",
        })
        self.assertEqual(out["id"], aid)  # 编号不变
        db = DbManager()
        db.cur.execute(
            "SELECT content, fire_at, is_private FROM group_alarms WHERE id = ?", (aid,))
        content, fire_at, is_priv = db.cur.fetchone()
        self.assertEqual(content, "新内容")
        self.assertTrue(fire_at.startswith(new_fire.strftime("%Y-%m-%d")))
        self.assertEqual(int(is_priv), 1)

    def test_scope_flip_group_to_private(self):
        fire = datetime.now() + timedelta(days=1)
        aid = DbManager().alarm.add(int(self.me), fire, "群", group_id=123, is_private=False)
        alarm_service.update_alarm(self.me, aid, {
            "content": "群", "schedule_type": "once_date",
            "date": fire.strftime("%Y-%m-%d"), "time": "20:00", "scope": "private",
        })
        db = DbManager()
        db.cur.execute("SELECT is_private, group_id FROM group_alarms WHERE id = ?", (aid,))
        is_priv, gid = db.cur.fetchone()
        self.assertEqual((int(is_priv), int(gid)), (1, 0))

    def test_non_creator_rejected(self):
        fire = datetime.now() + timedelta(days=1)
        aid = DbManager().alarm.add(int(self.other), fire, "别人的")
        with self.assertRaises(ValueError):
            alarm_service.update_alarm(self.me, aid, {
                "content": "改", "schedule_type": "once_today", "time": "23:50",
            })
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest test/test_alarm_calendar.py -v`
Expected: 新增 3 例 FAIL（`update_alarm` 不存在）

- [ ] **Step 3: 实现 scope + update_alarm**

`alarm_service.py` 的 `create_alarm` 中，`body = _build_alarm_body(payload)` 之后插入：

```python
    scope = str(payload.get("scope") or "private")
    if scope not in ("private", "group"):
        raise ValueError("提醒范围须为 private 或 group")
```

`db.alarm.add(...)` 调用改为：

```python
    aid = db.alarm.add(
        int(user_id),
        fire,
        clean_content,
        group_id=GROUP_ID if scope == "group" else None,
        is_private=scope != "group",
        recur=recur,
    )
```

文件末尾追加：

```python
def update_alarm(user_id: str, alarm_id: int, payload: dict[str, Any]) -> dict:
    body = _build_alarm_body(payload)
    scope = str(payload.get("scope") or "private")
    if scope not in ("private", "group"):
        raise ValueError("提醒范围须为 private 或 group")
    ga = _load_group_alarm()
    parsed = ga._parse_create_body(body)
    if isinstance(parsed, str):
        raise ValueError(parsed)

    fire, clean_content, recur = parsed
    db = DbManager()
    db.cur.execute(
        "SELECT id FROM group_alarms WHERE id = ? AND creator_user_id = ? AND fired = 0",
        (int(alarm_id), int(user_id)),
    )
    if not db.cur.fetchone():
        raise ValueError("修改失败：编号不存在、已触发或不是你创建的闹钟")

    if recur:
        k, a, b, c = recur
        rec, rk, ra, rb, rc = 1, k, a, b, c
    else:
        rec = rk = ra = rb = rc = 0
    # ponytail: 与 bot advance() 并发时最后写赢；出现丢更新再加 fire_at 前置条件比对
    db.cur.execute(
        """
        UPDATE group_alarms
        SET fire_at = ?, content = ?, is_private = ?, group_id = ?,
            is_recurring = ?, recur_kind = ?, recur_a = ?, recur_b = ?, recur_c = ?
        WHERE id = ? AND creator_user_id = ? AND fired = 0
        """,
        (fire.strftime("%Y-%m-%d %H:%M:%S"), clean_content,
         0 if scope == "group" else 1, GROUP_ID if scope == "group" else 0,
         rec, rk, ra, rb, rc, int(alarm_id), int(user_id)),
    )
    db.conn.commit()
    return {
        "id": int(alarm_id),
        "message": (
            f"已修改闹钟 #{alarm_id}，将于 {fire.strftime('%Y-%m-%d %H:%M')} 提醒你："
            f"「{clean_content}」"
        ),
    }
```

`_format_alarm_row` 返回 dict 增加（编辑预填结构化字段）：

```python
        "recur_kind": int(rk or 0),
        "recur_a": int(ra or 0),
        "recur_b": int(rb or 0),
```

`app.py`：`AlarmCreateIn` 加字段 `scope: str = "private"`；import 行追加 `update_alarm`；新增路由：

```python
@router.put("/api/me/alarms/{alarm_id}")
def api_alarms_update(
    alarm_id: int,
    body: AlarmCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _or_400(update_alarm, user_id, alarm_id, body.model_dump())
```

- [ ] **Step 4: 进程内测试通过**

Run: `python -m pytest test/test_alarm_calendar.py -v`
Expected: 11 passed

- [ ] **Step 5: 脚本式测试追加 HTTP 层用例**

`test/scripts/check_alarm_calendar_api.py` 的 `sys.exit` 前追加：

```python
# —— scope 与编辑（Task 2）——
tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

r = client.post("/api/me/alarms", headers=JH, json={
    "content": "网页群闹钟", "schedule_type": "once_date", "date": tomorrow, "time": "21:00",
    "scope": "group",
})
gid_new = r.json().get("id")
db_cur = DB.cur
db_cur.execute("SELECT is_private, group_id FROM group_alarms WHERE id = ?", (gid_new,))
is_priv, gid_val = db_cur.fetchone()
check("POST scope=group 写群字段", r.status_code == 200 and int(is_priv) == 0
      and int(gid_val) == 296470819, r.text)

r = client.post("/api/me/alarms", headers=JH, json={
    "content": "网页私聊闹钟", "schedule_type": "once_date", "date": tomorrow, "time": "21:30",
})
priv_new = r.json().get("id")
db_cur.execute("SELECT is_private FROM group_alarms WHERE id = ?", (priv_new,))
check("POST 默认 private", int(db_cur.fetchone()[0]) == 1)

r = client.put(f"/api/me/alarms/{gid_new}", headers=JH, json={
    "content": "改成每天群提醒", "schedule_type": "daily", "time": "08:05", "scope": "group",
})
check("PUT 200", r.status_code == 200 and r.json().get("id") == gid_new, r.text)
db_cur.execute("SELECT content, recur_kind, recur_a FROM group_alarms WHERE id = ?", (gid_new,))
content_v, rk_v, ra_v = db_cur.fetchone()
check("PUT 重算规则", content_v == "改成每天群提醒" and int(rk_v) == 1 and int(ra_v) == 1)

r = client.put(f"/api/me/alarms/{gid_new}", headers={"Content-Type": "application/json", **OH},
               json={"content": "抢改", "schedule_type": "daily", "time": "01:00"})
check("PUT 非创建者 400", r.status_code == 400)

r = client.put(f"/api/me/alarms/{gid_new}", headers=JH, json={
    "content": "转私聊", "schedule_type": "daily", "time": "08:05", "scope": "private",
})
db_cur.execute("SELECT is_private, group_id FROM group_alarms WHERE id = ?", (gid_new,))
is_priv2, gid2 = db_cur.fetchone()
check("PUT 群转私聊字段翻转", int(is_priv2) == 1 and int(gid2) == 0)
```

（GROUP_ID 断言用字面 296470819：脚本未设 `BOTERO_GROUP_ID`，取 config 默认值。）

- [ ] **Step 6: 运行脚本 + specs + 全量回归 + 提交**

Run: `python test/scripts/check_alarm_calendar_api.py` → 全部 ok

`specs/web-gallery.md` 闹钟端点表加：

```markdown
| `PUT` | `/api/me/alarms/{id}` | 必须 | 编辑闹钟（仅创建者；重算规则，支持私聊/群互转） |
```

POST 行说明改为「创建闹钟（`scope`: private/group，默认 private）」。

Run: `python -m pytest` → 全部通过

```bash
git add webapp/alarms/alarm_service.py webapp/alarms/app.py test/test_alarm_calendar.py test/scripts/check_alarm_calendar_api.py specs/web-gallery.md
git commit -m "feat(日程): 闹钟编辑与私聊/群范围"
```

---

### Task 3: 前端日程页三件套（手写月历 + 表单 + 列表 + 悬浮窗）

**Files:**
- Create: `webapp/static/schedule.html`
- Create: `webapp/static/schedule.css`
- Create: `webapp/static/schedule.js`
- Create: `test/test_schedule_render.js`（node DOM stub，自动纳入回归）

**Interfaces:**
- Consumes: Task 1/2 的 API（`GET /api/me/calendar?month=`、`GET /api/me/alarms`、`POST/PUT/DELETE /api/me/alarms[/{id}]`）；`/shared/auth.js` 的 `GalleryAuth`（`isLoggedIn/load/headers/refreshMe/login/clear`）；`/shared/nav.js`、`/shared/motion.js`
- Produces: 页面 `/profile/schedule` 的完整静态实现（Task 4 接线）；日历项字段 `id/time/content/date/is_mine/scope/is_recurring/recur_kind/recur_a/recur_b/recur_desc/creator_name`

- [ ] **Step 1: 写 schedule.css**

（alarms.css 全量迁移 + 日历网格/悬浮窗样式，旧文件 Task 4 删除）：

```css
/* 日程页专属样式（闹钟表单部分自 alarms.css 迁移） */

/* —— 月历 —— */
.cal-toolbar {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.7rem;
}
.cal-toolbar h2 { margin: 0; flex: 1; text-align: center; }
.cal-nav-btn {
  padding: 0.3rem 0.8rem;
  border-radius: 8px;
  border: 1px solid var(--rule);
  background: var(--paper-card);
  color: var(--ink);
  font: inherit;
  cursor: pointer;
}
.cal-nav-btn:hover { border-color: var(--accent); }

.cal-week-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
  margin-bottom: 6px;
  text-align: center;
  font-size: 0.78rem;
  color: var(--ink-soft);
}

.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}

.cal-cell {
  min-height: 5.4rem;
  padding: 0.3rem;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: var(--paper-card);
  cursor: pointer;
  overflow: hidden;
  text-align: left;
  font: inherit;
}
.cal-cell.dim { opacity: 0.35; }
.cal-cell.past { opacity: 0.45; pointer-events: none; }
.cal-cell.today { border-color: var(--accent); }
.cal-cell.selected {
  background: color-mix(in srgb, var(--accent) 16%, transparent);
  border-color: var(--accent);
}
.cal-cell-num { font-size: 0.8rem; color: var(--ink-soft); }

.cal-chip {
  display: block;
  margin-top: 2px;
  padding: 0.05rem 0.3rem;
  border-radius: 5px;
  border-left: 3px solid var(--rule);
  background: color-mix(in srgb, var(--rule) 22%, transparent);
  font-size: 0.72rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}
.cal-chip.mine {
  border-left-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 18%, transparent);
}
.cal-chip.more { border-left-color: transparent; color: var(--ink-soft); }

/* —— 闹钟表单（自 alarms.css 迁移，类名不变）—— */
.alarm-form h2,
.alarm-list + h2 { margin-top: 0; }
.alarm-field { display: flex; flex-direction: column; gap: 0.35rem; }
.alarm-field-block { margin-top: 0.85rem; }
.alarm-field-label { font-size: 0.82rem; color: var(--ink-soft); }
.alarm-fields { margin-top: 0.85rem; }
.alarm-fields-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
  gap: 0.65rem 0.85rem;
}
.alarm-field-hint { margin: 0.65rem 0 0; }
.alarm-type-grid { display: flex; flex-wrap: wrap; gap: 0.45rem; }
.alarm-type-btn,
.weekday-btn {
  padding: 0.38rem 0.75rem;
  border-radius: 999px;
  border: 1px solid var(--rule);
  background: var(--paper-card);
  color: var(--ink);
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.alarm-type-btn:hover,
.weekday-btn:hover { border-color: var(--accent); }
.alarm-type-btn.active,
.weekday-btn.active {
  background: color-mix(in srgb, var(--accent) 22%, transparent);
  border-color: var(--accent);
  color: var(--accent-soft);
}
.weekday-group { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.weekday-btn { min-width: 2.2rem; text-align: center; padding-inline: 0.55rem; }
.alarm-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.65rem 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--rule);
  background: var(--paper-card);
  color: var(--ink);
  font: inherit;
}
.alarm-input-sm { padding: 0.5rem 0.65rem; }
.alarm-actions { margin-top: 1rem; display: flex; justify-content: flex-end; gap: 0.5rem; }

/* —— 闹钟列表（自 alarms.css 迁移）—— */
.alarm-list { display: flex; flex-direction: column; gap: 0.65rem; margin-top: 0.75rem; }
.alarm-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  border-radius: 10px;
  border: 1px solid var(--rule);
  background: var(--paper-card);
  cursor: pointer;
}
.alarm-item-main { flex: 1; min-width: 0; }
.alarm-meta { margin: 0; font-size: 0.78rem; color: var(--ink-soft); }
.alarm-content { margin: 0.35rem 0 0; font-size: 0.92rem; word-break: break-word; }

/* —— 详情/当日悬浮窗 —— */
.alarm-dlg-body p { margin: 0.3rem 0; }
.alarm-dlg-badge {
  display: inline-block;
  padding: 0.05rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--rule);
  font-size: 0.75rem;
  color: var(--ink-soft);
}
.day-row-btn {
  display: block;
  width: 100%;
  text-align: left;
  padding: 0.45rem 0.6rem;
  border: none;
  border-bottom: 1px solid var(--rule);
  background: transparent;
  font: inherit;
  cursor: pointer;
}
.day-row-btn:hover { background: color-mix(in srgb, var(--accent) 10%, transparent); }
```

- [ ] **Step 2: 写 schedule.html**

（结构照 alarms.html，换标题/主容器/两个新 dialog，加 profile 子导航；`day-dialog` 样式来自共享 profile.css）：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>日程</title>
  <script src="/shared/theme.js"></script>
  <link rel="stylesheet" href="/shared/base.css" />
  <link rel="stylesheet" href="/shared/motion.css" />
  <link rel="stylesheet" href="/shared/profile.css" />
  <link rel="stylesheet" href="/static/schedule.css" />
</head>
<body>
  <header class="toolbar profile-toolbar">
    <nav class="profile-nav">
      <a href="/profile">主页</a>
      <a href="/profile/checkin">打卡</a>
      <a href="/profile/schedule" class="active">日程</a>
      <a href="/profile/shop">商店</a>
      <a href="/profile/settings">设置</a>
    </nav>
    <div class="auth-area" id="authArea"></div>
  </header>

  <main class="profile-main" id="scheduleMain">
    <p class="loading-msg">加载中…</p>
  </main>

  <dialog id="loginDialog" class="login-dialog">
    <form method="dialog" id="loginForm">
      <h2>个人中心登录</h2>
      <p class="login-hint">请向机器人私聊发送 <code>/图库密钥</code> 获取密钥</p>
      <input type="password" id="loginKey" placeholder="粘贴登录密钥" autocomplete="off" required />
      <p class="login-error hidden" id="loginError"></p>
      <div class="login-actions">
        <button type="button" id="loginCancel">取消</button>
        <button type="submit" class="primary">登录</button>
      </div>
    </form>
  </dialog>

  <dialog id="alarmDialog" class="day-dialog">
    <div class="day-dialog-header">
      <h3>闹钟详情</h3>
      <button type="button" id="alarmDlgClose" aria-label="关闭">×</button>
    </div>
    <div class="alarm-dlg-body" id="alarmDlgBody"></div>
    <div class="alarm-actions" id="alarmDlgActions">
      <button type="button" class="btn-sm" id="alarmDlgCancel">取消闹钟</button>
      <button type="button" class="btn-sm primary" id="alarmDlgEdit">编辑</button>
    </div>
  </dialog>

  <dialog id="dayDialog" class="day-dialog">
    <div class="day-dialog-header">
      <h3 id="dayDlgTitle">当日闹钟</h3>
      <button type="button" id="dayDlgClose" aria-label="关闭">×</button>
    </div>
    <div id="dayDlgList"></div>
  </dialog>

  <script src="/shared/auth.js?v=3"></script>
  <script src="/shared/motion.js"></script>
  <script src="/shared/nav.js"></script>
  <script src="/static/schedule.js"></script>
</body>
</html>
```

- [ ] **Step 3: 写 schedule.js（完整文件）**

```javascript
const scheduleMain = document.getElementById("scheduleMain");
const loginDialog = document.getElementById("loginDialog");
const loginForm = document.getElementById("loginForm");
const loginKey = document.getElementById("loginKey");
const loginError = document.getElementById("loginError");
const loginCancel = document.getElementById("loginCancel");
const alarmDialog = document.getElementById("alarmDialog");
const dayDialog = document.getElementById("dayDialog");

const SCHEDULE_TYPES = [
  { id: "once_date", label: "指定日期" },
  { id: "once_relative", label: "相对时间" },
  { id: "once_today", label: "今天" },
  { id: "daily", label: "每天" },
  { id: "interval_days", label: "每 N 天" },
  { id: "weekly", label: "每周" },
  { id: "monthly", label: "每月" },
  { id: "yearly", label: "每年" },
];

const WEEKDAYS = [
  { value: 1, label: "一" }, { value: 2, label: "二" }, { value: 3, label: "三" },
  { value: 4, label: "四" }, { value: 5, label: "五" }, { value: 6, label: "六" },
  { value: 7, label: "日" },
];

var formState = { scheduleType: "daily", weekday: 1, minLeadMinutes: 5, scope: "private", editingId: null, seeds: null };
var calState = { year: 0, month: 0, data: { month: "", days: {} }, selectedDate: null };
var listItems = [];
// ponytail: 上面三个用 var 而非 const/let——浏览器 classic script 顶层行为一致，
// 且 node DOM stub 测试（eval 本文件）才能在 eval 外访问 formState 做断言

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function pad2(n) { return String(n).padStart(2, "0"); }
function fmtKey(y, m, d) { return `${y}-${pad2(m)}-${pad2(d)}`; }
function todayKey() { const t = new Date(); return fmtKey(t.getFullYear(), t.getMonth() + 1, t.getDate()); }

// —— 认证 / 提示（与旧闹钟页一致）——
function openLoginDialog() {
  loginError.classList.add("hidden");
  if (!loginDialog.open) loginDialog.showModal();
}
function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    scheduleMain.innerHTML = "<p class='empty-hint center'>请先登录</p>";
    openLoginDialog();
    return false;
  }
  return true;
}
function renderAuthChip() {
  const area = document.getElementById("authArea");
  if (!area) return;
  area.innerHTML = "";
  const session = GalleryAuth.load();
  if (!session || !session.token) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-login";
    btn.textContent = "登录";
    btn.addEventListener("click", openLoginDialog);
    area.appendChild(btn);
    return;
  }
  const link = document.createElement("a");
  link.className = "user-chip";
  link.href = "/profile/schedule";
  const img = document.createElement("img");
  img.src = session.avatar_url || "";
  img.alt = session.display_name;
  img.onerror = () => { img.style.display = "none"; };
  const wrap = document.createElement("span");
  wrap.innerHTML = `<strong>${escapeHtml(session.display_name)}</strong><br><span class="uid">${session.user_id}</span>`;
  link.append(img, wrap);
  area.appendChild(link);
}
function showToast(msg, isError = false) {
  let toast = document.getElementById("scheduleToast");
  if (!toast) {
    toast = document.createElement("p");
    toast.id = "scheduleToast";
    toast.className = "settings-toast";
    scheduleMain.prepend(toast);
  }
  toast.textContent = msg;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 3500);
}

// —— 表单（自 alarms.js 移植 + 范围开关 + 编辑模式）——
function defaultTimeValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() + 30);
  return `${pad2(now.getHours())}:${pad2(now.getMinutes())}`;
}
function defaultDateValue() {
  const now = new Date();
  return fmtKey(now.getFullYear(), now.getMonth() + 1, now.getDate());
}
function fieldRow(label, inputEl) {
  const row = document.createElement("label");
  row.className = "alarm-field";
  const span = document.createElement("span");
  span.className = "alarm-field-label";
  span.textContent = label;
  row.append(span, inputEl);
  return row;
}
function makeNumberInput(id, placeholder, min = 0, max = null) {
  const input = document.createElement("input");
  input.type = "number";
  input.id = id;
  input.className = "alarm-input alarm-input-sm";
  input.placeholder = placeholder;
  input.min = String(min);
  if (max != null) input.max = String(max);
  input.value = "0";
  return input;
}
function makeTimeInput(id, value) {
  const input = document.createElement("input");
  input.type = "time";
  input.id = id;
  input.className = "alarm-input alarm-input-sm";
  input.value = value || defaultTimeValue();
  return input;
}
function makeDateInput(id, value) {
  const input = document.createElement("input");
  input.type = "date";
  input.id = id;
  input.className = "alarm-input alarm-input-sm";
  input.value = value || defaultDateValue();
  return input;
}
function renderScheduleFields(container) {
  container.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "alarm-fields-grid";
  const type = formState.scheduleType;
  const seeds = formState.seeds || {};

  if (type === "once_date") {
    grid.append(fieldRow("日期", makeDateInput("alarmDate", seeds.date)), fieldRow("时刻", makeTimeInput("alarmTime", seeds.time)));
  } else if (type === "once_relative") {
    grid.append(
      fieldRow("年", makeNumberInput("alarmYears", "0")),
      fieldRow("月", makeNumberInput("alarmMonths", "0")),
      fieldRow("日", makeNumberInput("alarmDays", "0")),
      fieldRow("小时", makeNumberInput("alarmHours", "0")),
      fieldRow("分钟", makeNumberInput("alarmMinutes", "30"))
    );
    const hint = document.createElement("p");
    hint.className = "preview-hint alarm-field-hint";
    hint.textContent = "至少填写一项；合计须距当前至少 5 分钟。";
    container.append(grid, hint);
    return;
  } else if (type === "once_today") {
    grid.append(fieldRow("时刻", makeTimeInput("alarmTime", seeds.time)));
  } else if (type === "daily" || type === "monthly" || type === "yearly") {
    if (type === "monthly") {
      const day = makeNumberInput("alarmDay", "15", 1, 31);
      day.value = String(seeds.day || 1);
      grid.append(fieldRow("每月第几天", day));
    }
    if (type === "yearly") {
      const month = makeNumberInput("alarmMonth", "6", 1, 12);
      month.value = String(seeds.month || 1);
      const day = makeNumberInput("alarmDay", "1", 1, 31);
      day.value = String(seeds.day || 1);
      grid.append(fieldRow("月", month), fieldRow("日", day));
    }
    grid.append(fieldRow("时刻", makeTimeInput("alarmTime", seeds.time)));
  } else if (type === "interval_days") {
    const interval = makeNumberInput("alarmInterval", "3", 1);
    interval.value = String(seeds.interval || 3);
    grid.append(fieldRow("间隔天数", interval), fieldRow("时刻", makeTimeInput("alarmTime", seeds.time)));
  } else if (type === "weekly") {
    const group = document.createElement("div");
    group.className = "weekday-group";
    group.id = "alarmWeekdayGroup";
    for (const wd of WEEKDAYS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "weekday-btn";
      btn.textContent = wd.label;
      btn.dataset.value = String(wd.value);
      if (wd.value === formState.weekday) btn.classList.add("active");
      btn.addEventListener("click", () => {
        formState.weekday = wd.value;
        group.querySelectorAll(".weekday-btn").forEach((el) => {
          el.classList.toggle("active", Number(el.dataset.value) === wd.value);
        });
      });
      group.appendChild(btn);
    }
    const wrap = document.createElement("div");
    wrap.className = "alarm-field alarm-field-block";
    const label = document.createElement("span");
    label.className = "alarm-field-label";
    label.textContent = "星期";
    wrap.append(label, group);
    grid.append(wrap, fieldRow("时刻", makeTimeInput("alarmTime", seeds.time)));
  }
  container.appendChild(grid);
}
function setScheduleType(type) {
  formState.scheduleType = type;
  document.querySelectorAll(".alarm-type-btn[data-type]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.type === type);
  });
  const fields = document.getElementById("alarmFields");
  if (fields) renderScheduleFields(fields);
}
function setScope(scope) {
  formState.scope = scope;
  document.querySelectorAll(".alarm-type-btn[data-scope]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.scope === scope);
  });
}
function updateFormModeUi() {
  const title = document.getElementById("alarmFormTitle");
  const submit = document.getElementById("alarmSubmitBtn");
  const abort = document.getElementById("alarmAbortBtn");
  if (!title) return;
  if (formState.editingId) {
    title.textContent = `编辑闹钟 #${formState.editingId}`;
    submit.textContent = "保存修改";
    abort.classList.remove("hidden");
  } else {
    title.textContent = "新建闹钟";
    submit.textContent = "创建闹钟";
    abort.classList.add("hidden");
  }
}
function renderCreateForm() {
  const section = document.createElement("section");
  section.className = "alarm-form settings-section";
  section.innerHTML = `
    <h2 id="alarmFormTitle">新建闹钟</h2>
    <p class="preview-hint">触发时刻须距当前至少 ${formState.minLeadMinutes} 分钟；「群内公开」的闹钟会在群里提醒所有人。</p>
    <label class="alarm-field alarm-field-block">
      <span class="alarm-field-label">提醒内容</span>
      <input type="text" id="alarmContent" class="alarm-input" maxlength="200" placeholder="例如：起床、交报告" />
    </label>
    <div class="alarm-field alarm-field-block">
      <span class="alarm-field-label">触发方式</span>
      <div class="alarm-type-grid" id="alarmTypeGrid"></div>
    </div>
    <div id="alarmFields" class="alarm-fields"></div>
    <div class="alarm-field alarm-field-block">
      <span class="alarm-field-label">提醒范围</span>
      <div class="alarm-type-grid" id="alarmScopeGrid"></div>
    </div>
    <div class="alarm-actions">
      <button type="button" class="btn-sm hidden" id="alarmAbortBtn">放弃编辑</button>
      <button type="button" class="btn-sm primary" id="alarmSubmitBtn">创建闹钟</button>
    </div>
  `;
  const grid = section.querySelector("#alarmTypeGrid");
  for (const item of SCHEDULE_TYPES) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "alarm-type-btn";
    btn.dataset.type = item.id;
    btn.textContent = item.label;
    if (item.id === formState.scheduleType) btn.classList.add("active");
    btn.addEventListener("click", () => { formState.seeds = null; setScheduleType(item.id); });
    grid.appendChild(btn);
  }
  const scopeGrid = section.querySelector("#alarmScopeGrid");
  for (const opt of [{ id: "private", label: "仅我" }, { id: "group", label: "群内公开" }]) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "alarm-type-btn";
    btn.dataset.scope = opt.id;
    btn.textContent = opt.label;
    if (opt.id === formState.scope) btn.classList.add("active");
    btn.addEventListener("click", () => setScope(opt.id));
    scopeGrid.appendChild(btn);
  }
  renderScheduleFields(section.querySelector("#alarmFields"));
  section.querySelector("#alarmSubmitBtn").addEventListener("click", submitAlarm);
  section.querySelector("#alarmAbortBtn").addEventListener("click", resetCreateForm);
  return section;
}
function readFormPayload() {
  const content = (document.getElementById("alarmContent")?.value || "").trim();
  const payload = { content, schedule_type: formState.scheduleType, scope: formState.scope };
  const timeEl = document.getElementById("alarmTime");
  if (timeEl) payload.time = timeEl.value;
  const type = formState.scheduleType;
  if (type === "once_date") {
    payload.date = document.getElementById("alarmDate")?.value || "";
  } else if (type === "once_relative") {
    payload.years = Number(document.getElementById("alarmYears")?.value || 0);
    payload.months = Number(document.getElementById("alarmMonths")?.value || 0);
    payload.days = Number(document.getElementById("alarmDays")?.value || 0);
    payload.hours = Number(document.getElementById("alarmHours")?.value || 0);
    payload.minutes = Number(document.getElementById("alarmMinutes")?.value || 0);
  } else if (type === "interval_days") {
    payload.interval_days = Number(document.getElementById("alarmInterval")?.value || 0);
  } else if (type === "weekly") {
    payload.weekday = formState.weekday;
  } else if (type === "monthly" || type === "yearly") {
    payload.day = Number(document.getElementById("alarmDay")?.value || 0);
    if (type === "yearly") payload.month = Number(document.getElementById("alarmMonth")?.value || 0);
  }
  return payload;
}
function resetCreateForm() {
  formState.editingId = null;
  formState.seeds = null;
  formState.scope = "private";
  const content = document.getElementById("alarmContent");
  if (content) content.value = "";
  setScheduleType("daily");
  setScope("private");
  updateFormModeUi();
}
function ruleFromItem(item) {
  // 编辑预填：服务端结构化 recur 字段 → 表单类型与种子值
  if (!item.is_recurring) return { type: "once_date", seeds: { date: item.date, time: item.time } };
  const k = item.recur_kind, a = item.recur_a || 0, b = item.recur_b || 0;
  if (k === 1) return a === 1
    ? { type: "daily", seeds: { time: item.time } }
    : { type: "interval_days", seeds: { interval: a, time: item.time } };
  if (k === 2) return { type: "weekly", seeds: { weekday: a, time: item.time } };
  if (k === 3) return { type: "yearly", seeds: { month: a, day: b, time: item.time } };
  if (k === 4) return { type: "monthly", seeds: { day: a, time: item.time } };
  return { type: "once_date", seeds: { date: item.date, time: item.time } };
}
function enterEdit(item) {
  formState.editingId = item.id;
  formState.seeds = null;
  const { type, seeds } = ruleFromItem(item);
  if (seeds.weekday) formState.weekday = seeds.weekday;
  const content = document.getElementById("alarmContent");
  if (content) content.value = item.content;
  setScheduleType(type);
  formState.seeds = seeds;
  renderScheduleFields(document.getElementById("alarmFields"));
  formState.seeds = null;
  setScope(item.scope === "group" ? "group" : "private");
  updateFormModeUi();
  document.getElementById("alarmFormTitle")?.scrollIntoView({ behavior: "smooth", block: "start" });
}
async function submitAlarm() {
  const btn = document.getElementById("alarmSubmitBtn");
  const payload = readFormPayload();
  if (!payload.content) { showToast("请填写提醒内容", true); return; }
  btn.disabled = true;
  const oldText = btn.textContent;
  btn.textContent = "提交中…";
  try {
    const url = formState.editingId ? `/api/me/alarms/${formState.editingId}` : "/api/me/alarms";
    const res = await fetch(url, {
      method: formState.editingId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "提交失败");
    resetCreateForm();
    showToast(data.message || "已保存");
    await loadAll();
  } catch (err) {
    showToast(err.message || "提交失败", true);
  } finally {
    btn.disabled = false;
    btn.textContent = oldText;
    updateFormModeUi();
  }
}

// —— 日历 ——
function shiftMonth(delta) {
  const d = new Date(calState.year, calState.month - 1 + delta, 1);
  calState.year = d.getFullYear();
  calState.month = d.getMonth() + 1;
  calState.selectedDate = null;
  loadCalendar();
}
function goToday() {
  const t = new Date();
  calState.year = t.getFullYear();
  calState.month = t.getMonth() + 1;
  calState.selectedDate = null;
  loadCalendar();
}
async function loadCalendar() {
  const key = `${calState.year}-${pad2(calState.month)}`;
  const res = await fetch(`/api/me/calendar?month=${key}`, { headers: GalleryAuth.headers() });
  if (res.status === 401) { GalleryAuth.clear(); requireAuth(); return; }
  if (!res.ok) { showToast("日历加载失败", true); return; }
  calState.data = await res.json();
  renderCalendar();
}
function renderCalendar() {
  let host = document.getElementById("calendarSection");
  if (!host) {
    host = document.createElement("section");
    host.className = "settings-section";
    host.id = "calendarSection";
  }
  host.innerHTML = "";
  const y = calState.year, m = calState.month;

  const toolbar = document.createElement("div");
  toolbar.className = "cal-toolbar";
  const prev = document.createElement("button");
  prev.type = "button"; prev.className = "cal-nav-btn"; prev.textContent = "‹";
  prev.addEventListener("click", () => shiftMonth(-1));
  const next = document.createElement("button");
  next.type = "button"; next.className = "cal-nav-btn"; next.textContent = "›";
  next.addEventListener("click", () => shiftMonth(1));
  const title = document.createElement("h2");
  title.textContent = `${y} 年 ${m} 月`;
  const todayBtn = document.createElement("button");
  todayBtn.type = "button"; todayBtn.className = "cal-nav-btn"; todayBtn.textContent = "今天";
  todayBtn.addEventListener("click", goToday);
  toolbar.append(prev, title, next, todayBtn);
  host.appendChild(toolbar);

  const weekRow = document.createElement("div");
  weekRow.className = "cal-week-row";
  for (const wd of ["一", "二", "三", "四", "五", "六", "日"]) {
    const cell = document.createElement("span");
    cell.textContent = wd;
    weekRow.appendChild(cell);
  }
  host.appendChild(weekRow);

  const grid = document.createElement("div");
  grid.className = "cal-grid";
  const first = new Date(y, m - 1, 1);
  const offset = (first.getDay() + 6) % 7; // 周一起始
  const tk = todayKey();
  for (let i = 0; i < 42; i++) {
    const d = new Date(y, m - 1, 1 - offset + i);
    const key = fmtKey(d.getFullYear(), d.getMonth() + 1, d.getDate());
    const cell = document.createElement("div");
    cell.className = "cal-cell";
    cell.dataset.date = key;
    if (d.getMonth() !== m - 1) cell.classList.add("dim");
    if (key < tk) cell.classList.add("past");
    if (key === tk) cell.classList.add("today");
    if (key === calState.selectedDate) cell.classList.add("selected");

    const num = document.createElement("span");
    num.className = "cal-cell-num";
    num.textContent = String(d.getDate());
    cell.appendChild(num);

    const items = calState.data.days[key] || [];
    const shown = items.slice(0, 3);
    for (const item of shown) cell.appendChild(makeChip(item));
    if (items.length > 3) {
      const more = document.createElement("span");
      more.className = "cal-chip more";
      more.textContent = `+${items.length - 3} 更多`;
      more.addEventListener("click", (e) => { e.stopPropagation(); openDayDialog(key); });
      cell.appendChild(more);
    }
    cell.addEventListener("click", () => selectDay(key));
    grid.appendChild(cell);
  }
  host.appendChild(grid);
  return host;
}
function makeChip(item) {
  const chip = document.createElement("span");
  chip.className = "cal-chip " + (item.is_mine ? "mine" : "other");
  chip.textContent = `${item.time} ${item.content}`;
  chip.title = `${item.time} ${item.content}（${item.creator_name}）`;
  chip.addEventListener("click", (e) => { e.stopPropagation(); openAlarmDialog(item); });
  return chip;
}
function selectDay(key) {
  calState.selectedDate = key;
  renderCalendar();
  formState.editingId = null;
  formState.seeds = null;
  updateFormModeUi();
  setScheduleType("once_date");
  const dateEl = document.getElementById("alarmDate");
  if (dateEl) dateEl.value = key;
  document.getElementById("alarmFormTitle")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

// —— 悬浮窗 ——
function scopeBadge(scope) {
  return scope === "group" ? "群内公开" : "仅我";
}
function openAlarmDialog(item) {
  alarmDialog._item = item;
  const rule = item.is_recurring
    ? `${item.recur_desc} · ${item.time}`
    : `${item.date} ${item.time}`;
  const body = document.getElementById("alarmDlgBody");
  body.innerHTML = `
    <p><strong>${escapeHtml(item.content)}</strong></p>
    <p>创建人：${escapeHtml(item.creator_name)}${item.is_mine ? "（我）" : ""}</p>
    <p>触发：${escapeHtml(rule)}</p>
    <p><span class="alarm-dlg-badge">${scopeBadge(item.scope)}</span>
       ${item.is_recurring ? `<span class="alarm-dlg-badge">${escapeHtml(item.recur_desc)}</span>` : ""}</p>
  `;
  document.getElementById("alarmDlgActions").classList.toggle("hidden", !item.is_mine);
  if (!alarmDialog.open) alarmDialog.showModal();
}
function openDayDialog(key) {
  const items = calState.data.days[key] || [];
  const list = document.getElementById("dayDlgList");
  list.innerHTML = "";
  for (const item of items) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "day-row-btn";
    row.innerHTML = `<span class="cal-chip ${item.is_mine ? "mine" : "other"}" style="display:inline-block;">${escapeHtml(item.time)}</span>
      ${escapeHtml(item.content)} <span style="color:var(--ink-soft);font-size:0.78rem;">${escapeHtml(item.creator_name)}</span>`;
    row.addEventListener("click", () => { dayDialog.close(); openAlarmDialog(item); });
    list.appendChild(row);
  }
  document.getElementById("dayDlgTitle").textContent = `当日闹钟（${items.length}）`;
  if (!dayDialog.open) dayDialog.showModal();
}
document.getElementById("alarmDlgClose").addEventListener("click", () => alarmDialog.close());
document.getElementById("dayDlgClose").addEventListener("click", () => dayDialog.close());
document.getElementById("alarmDlgEdit").addEventListener("click", () => {
  const item = alarmDialog._item;
  alarmDialog.close();
  if (item) enterEdit(item);
});
document.getElementById("alarmDlgCancel").addEventListener("click", async () => {
  const item = alarmDialog._item;
  alarmDialog.close();
  if (!item) return;
  if (!confirm(`确定取消闹钟 #${item.id}？`)) return;
  try {
    const res = await fetch(`/api/me/alarms/${item.id}`, { method: "DELETE", headers: GalleryAuth.headers() });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "取消失败");
    showToast(data.message || "已取消");
    await loadAll();
  } catch (err) {
    showToast(err.message || "取消失败", true);
  }
});

// —— 列表（旧页列表迁移：行点击进详情）——
function renderAlarmList() {
  const section = document.createElement("section");
  section.className = "settings-section";
  section.innerHTML = "<h2>待触发闹钟</h2>";
  if (!listItems.length) {
    const empty = document.createElement("p");
    empty.className = "empty-hint center";
    empty.textContent = "你还没有待触发的闹钟";
    section.appendChild(empty);
    return section;
  }
  const list = document.createElement("div");
  list.className = "alarm-list";
  for (const item of listItems) {
    const card = document.createElement("article");
    card.className = "alarm-item";
    card.dataset.reveal = "";
    const metaParts = [`#${item.id}`, item.scope === "group" ? "群内公开" : "仅我"];
    if (item.recur_desc) metaParts.push(item.recur_desc);
    metaParts.push(item.fire_at);
    card.innerHTML = `
      <div class="alarm-item-main">
        <p class="alarm-meta">${escapeHtml(metaParts.join(" · "))}</p>
        <p class="alarm-content">${escapeHtml(item.content)}</p>
      </div>
    `;
    card.addEventListener("click", () => openAlarmDialog({
      ...item,
      date: String(item.fire_at).slice(0, 10),
      time: String(item.fire_at).slice(11, 16),
      is_mine: true,
    }));
    list.appendChild(card);
  }
  section.appendChild(list);
  return section;
}

// —— 组装与启动 ——
function renderAll() {
  scheduleMain.innerHTML = "";
  scheduleMain.appendChild(renderCalendar());
  scheduleMain.appendChild(renderCreateForm());
  scheduleMain.appendChild(renderAlarmList());
  updateFormModeUi();
}
async function loadAll() {
  const [calRes, listRes] = await Promise.all([
    fetch(`/api/me/calendar?month=${calState.year}-${pad2(calState.month)}`, { headers: GalleryAuth.headers() }),
    fetch("/api/me/alarms", { headers: GalleryAuth.headers() }),
  ]);
  if (calRes.status === 401 || listRes.status === 401) { GalleryAuth.clear(); requireAuth(); return; }
  calState.data = await calRes.json();
  const listData = await listRes.json();
  listItems = listData.items || [];
  formState.minLeadMinutes = listData.min_lead_minutes || 5;
  renderAll();
}

loginCancel.addEventListener("click", () => loginDialog.close());
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.classList.add("hidden");
  try {
    await GalleryAuth.login(loginKey.value);
    loginDialog.close();
    loginKey.value = "";
    renderAuthChip();
    loadAll();
  } catch (err) {
    loginError.textContent = err.message || "登录失败";
    loginError.classList.remove("hidden");
  }
});

(function boot() {
  const t = new Date();
  calState.year = t.getFullYear();
  calState.month = t.getMonth() + 1;
  GalleryAuth.refreshMe().finally(() => {
    renderAuthChip();
    if (requireAuth()) loadAll();
  });
})();
```

- [ ] **Step 4: 写 node DOM stub 测试**

创建 `test/test_schedule_render.js`（模式照 `test_settings_render.js`；冻结 Date 保证确定性）：

```javascript
// 最小 DOM stub 验证 schedule.js：
// 月历网格 42 格、周一起始偏移、过去日 past、今天 today、
// 我的/别人的 chip 类名、+N 折叠、点格子预填表单日期。
const fs = require("fs");

const FIXED = new Date(2026, 8, 15, 10, 0, 0); // 2026-09-15 周二
class FakeDate extends Date {
  constructor(...a) { a.length ? super(...a) : super(FIXED.getTime()); }
  static now() { return FIXED.getTime(); }
}

const ALL_ELS = [];
function makeEl(tag) {
  const el = {
    tagName: tag, id: "", type: "", className: "", textContent: "", value: "", name: "",
    disabled: false, checked: false, children: [], dataset: {}, style: {}, _html: "", _listeners: {},
    setAttribute(k, v) { this.attributes = this.attributes || {}; this.attributes[k] = v; },
    addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => this.children.push(c)); },
    prepend(c) { this.children.unshift(c); return c; },
    querySelector(sel) { return fromHtml(sel.replace("#", "")); },
    querySelectorAll() { return []; },
    showModal() { this.open = true; },
    close() { this.open = false; },
    scrollIntoView() {},
  };
  Object.defineProperty(el, "innerHTML", {
    get() { return el._html; },
    set(v) { el._html = v; el.children.length = 0; },
  });
  el.classList = {
    _s: new Set(),
    add(c) { this._s.add(c); },
    remove(...cs) { cs.forEach((c) => this._s.delete(c)); },
    toggle(c, on) { if (on) this._s.add(c); else this._s.delete(c); },
    contains(c) { return this._s.has(c); },
  };
  ALL_ELS.push(el);
  return el;
}

const els = {};
for (const id of ["scheduleMain", "loginDialog", "loginForm", "loginKey", "loginError",
  "loginCancel", "alarmDialog", "dayDialog", "alarmDlgClose", "dayDlgClose",
  "alarmDlgEdit", "alarmDlgCancel", "alarmDlgBody", "alarmDlgActions", "dayDlgList", "dayDlgTitle", "authArea"]) {
  els[id] = makeEl(id === "loginForm" ? "form" : id.endsWith("Dialog") ? "dialog" : "div");
  els[id].id = id;
}

global.Date = FakeDate;
global.location = { hostname: "127.0.0.1", pathname: "/profile/schedule" };
// 从 innerHTML 片段回建带 id 的元素（缓存），供 getElementById/querySelector 使用
const HTML_ELS = {};
function fromHtml(id) {
  if (els[id]) return els[id];
  if (HTML_ELS[id]) return HTML_ELS[id];
  const direct = ALL_ELS.find((e) => e.id === id);
  if (direct) return direct; // createElement 建的真实节点直接返回，读写不丢
  for (const el of ALL_ELS) {
    if (el._html && new RegExp(`id="${id}"`).test(el._html)) {
      const stub = makeEl("div");
      stub.id = id;
      HTML_ELS[id] = stub;
      return stub;
    }
  }
  return null;
}

global.document = { createElement: makeEl, getElementById: fromHtml };

const CAL_DAYS = {
  "2026-09-15": [
    { id: 1, time: "08:00", content: "我的每天", date: "2026-09-15", is_mine: true, scope: "private",
      is_recurring: true, recur_kind: 1, recur_a: 1, recur_b: 0, recur_desc: "每天", creator_name: "我" },
    { id: 2, time: "09:00", content: "别人的群", date: "2026-09-15", is_mine: false, scope: "group",
      is_recurring: false, recur_kind: 0, recur_a: 0, recur_b: 0, recur_desc: null, creator_name: "别人" },
    { id: 3, time: "10:00", content: "第三条", date: "2026-09-15", is_mine: true, scope: "group",
      is_recurring: false, recur_kind: 0, recur_a: 0, recur_b: 0, recur_desc: null, creator_name: "我" },
    { id: 4, time: "11:00", content: "第四条", date: "2026-09-15", is_mine: true, scope: "private",
      is_recurring: false, recur_kind: 0, recur_a: 0, recur_b: 0, recur_desc: null, creator_name: "我" },
  ],
};
global.fetch = async (path) => {
  if (path.startsWith("/api/me/calendar")) {
    return { ok: true, status: 200, json: async () => ({ month: "2026-09", days: CAL_DAYS, min_lead_minutes: 5 }) };
  }
  if (path === "/api/me/alarms") {
    return { ok: true, status: 200, json: async () => ({ items: [], min_lead_minutes: 5 }) };
  }
  return { ok: false, status: 404, json: async () => ({}) };
};
global.GalleryAuth = {
  isLoggedIn: () => true,
  load: () => ({ token: "t", user_id: "1", display_name: "测试", avatar_url: "" }),
  headers: () => ({}),
  refreshMe: async () => ({}),
};
global.window = { addEventListener() {} };
global.confirm = () => true;

eval(fs.readFileSync("webapp/static/schedule.js", "utf8"));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }
const byClass = (cls) => ALL_ELS.filter((e) => e.classList && e.classList.contains(cls));

(async () => {
  await wait(150); // boot → loadAll → renderAll

  // 1. 网格 42 格，2026-09-01 为周二 → 首格 2026-08-31（周一）dim
  const cells = byClass("cal-cell");
  check("月历 42 格", cells.length === 42);
  check("首格为上月末且 dim", cells[0].dataset.date === "2026-08-31" && cells[0].classList.contains("dim"));

  // 2. 过去日 past、今天 today
  const cellOf = (key) => cells.find((c) => c.dataset.date === key);
  check("过去日 past", cellOf("2026-09-01").classList.contains("past"));
  check("今天 today", cellOf("2026-09-15").classList.contains("today"));

  // 3. chip：3 条上限 + mine/other 类名
  const chips = cellOf("2026-09-15").children.filter((c) => c.classList.contains("cal-chip"));
  check("chip 最多 3 条 + +N 折叠", chips.length === 4 && chips[3].classList.contains("more") && chips[3].textContent === "+1 更多");
  check("我的 chip mine", chips[0].classList.contains("mine"));
  check("别人的 chip other", chips[1].classList.contains("other"));

  // 4. 点未来日空白 → 预填 once_date + 日期（selectDay 会重建日历，重新取节点）
  const target = cellOf("2026-09-20");
  const click = target._listeners.click[0];
  await click();
  const cellsAfter = byClass("cal-cell");
  const dateInput = [...ALL_ELS].reverse().find((e) => e.id === "alarmDate");
  check("点格预填指定日期", formState.scheduleType === "once_date" && dateInput && dateInput.value === "2026-09-20");
  check("选中格高亮", cellsAfter.find((c) => c.dataset.date === "2026-09-20").classList.contains("selected"));

  // 5. 我的 chip 点击 → 详情悬浮窗含编辑入口
  const mineChip = chips[0];
  await mineChip._listeners.click[0]();
  check("详情悬浮窗打开", els.alarmDialog.open === true);
  check("我的闹钟显示编辑入口", !els.alarmDlgActions.classList.contains("hidden"));
  check("详情含创建人", els.alarmDlgBody._html.includes("我（"));

  // 6. 别人的闹钟 → 编辑入口隐藏
  await chips[1]._listeners.click[0]();
  check("别人的闹钟隐藏编辑入口", els.alarmDlgActions.classList.contains("hidden"));

  process.exit(fail ? 1 : 0);
})();
```

- [ ] **Step 5: 运行 DOM 测试确认通过**

Run: `node test/test_schedule_render.js`
Expected: 全部 ok，退出码 0（若 stub 缺方法按报错补齐 stub，不改 schedule.js 语义）

- [ ] **Step 6: 全量回归 + 提交**

Run: `python -m pytest`（含 node DOM 套件自动发现）
Expected: 全部通过

```bash
git add webapp/static/schedule.html webapp/static/schedule.css webapp/static/schedule.js test/test_schedule_render.js
git commit -m "feat(日程): 日历式日程页前端"
```

---

### Task 4: 路由接线、导航切换、旧页退役、文档与版本

**Files:**
- Modify: `webapp/alarms/app.py`（`/alarms` 302；`GET /profile/schedule`）
- Modify: `core/web/static/nav.js`
- Modify: `webapp/static/profile.html`、`webapp/static/checkin.html`、`webapp/static/shop.html`、`webapp/static/settings.html`（子导航加日程）
- Modify: `webapp/timeline/entries.json`
- Delete: `webapp/static/alarms.html`、`webapp/static/alarms.js`、`webapp/static/alarms.css`
- Modify: `test/scripts/check_alarm_calendar_api.py`（路由断言）
- Modify: `CHANGELOG.md`、`core/config.py`、`specs/web-gallery.md`

**Interfaces:**
- Consumes: Task 3 的 `schedule.html`
- Produces: `/profile/schedule` 页面可达；`/alarms` 302 → `/profile/schedule`；全站导航入口指向新页

- [ ] **Step 1: 脚本测试追加路由断言（失败先行）**

`test/scripts/check_alarm_calendar_api.py` 的 `sys.exit` 前追加：

```python
# —— 路由与页面（Task 4）——
r = client.get("/alarms", follow_redirects=False)
check("旧 /alarms 302", r.status_code == 302 and r.headers.get("location") == "/profile/schedule")
r = client.get("/profile/schedule")
check("未登录页面 302 登录", r.status_code == 302 and "/login" in r.headers.get("location", ""))
r = client.get("/profile/schedule", headers=H)
check("日程页 200", r.status_code == 200 and "日程" in r.text)
```

Run: `python test/scripts/check_alarm_calendar_api.py`
Expected: 新增 3 项 FAIL（路由未接）

- [ ] **Step 2: 接线路由**

`webapp/alarms/app.py`：import 行 `from fastapi.responses import FileResponse` 改为 `from fastapi.responses import FileResponse, RedirectResponse`；`alarms_page` 函数整体替换为：

```python
@router.get("/profile/schedule")
def schedule_page():
    page = STATIC_DIR / "schedule.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)


@router.get("/alarms")
def alarms_page():
    """旧闹钟页：302 到日程页（保留书签兼容）。"""
    return RedirectResponse("/profile/schedule", status_code=302)
```

- [ ] **Step 3: 导航四处切换 + 删旧三件套**

`core/web/static/nav.js`：`{ label: "闹钟", path: "/alarms" }` → `{ label: "日程", path: "/profile/schedule" }`

`webapp/static/profile.html`、`checkin.html`、`shop.html`、`settings.html`：`<nav class="profile-nav">` 内打卡链接之后插入：

```html
      <a href="/profile/schedule">日程</a>
```

`webapp/timeline/entries.json`：「闹钟」项改为：

```json
    "name": "日程",
    "desc": "日历式日程与闹钟管理",
    "url": "/profile/schedule"
```

删除：`webapp/static/alarms.html`、`webapp/static/alarms.js`、`webapp/static/alarms.css`

```bash
git rm webapp/static/alarms.html webapp/static/alarms.js webapp/static/alarms.css
```

- [ ] **Step 4: 路由断言通过**

Run: `python test/scripts/check_alarm_calendar_api.py`
Expected: 全部 ok

- [ ] **Step 5: 文档与版本**

`core/config.py`：`BOTERO_VERSION = "1.31.0"` → `"1.32.0"`

`CHANGELOG.md`：`## [未发布]` 节之前插入：

```markdown
## [1.32.0] - 2026-09-01

### 新增

- **日程日历页**：个人中心新增「日程」页（`/profile/schedule`），以月历展示自己与群内所有人的闹钟，重复闹钟自动展开填充；点日期快速添加，点闹钟查看详情（创建人/内容/规则），自己的闹钟可编辑（支持仅我/群内公开互转）与取消；网页新建闹钟可选「仅我 / 群内公开」。旧闹钟页 `/alarms` 重定向至新页，闹钟列表保留在新页底部
```

`specs/web-gallery.md`：
- 模块表（`| 闹钟 | alarms | /alarms | 闹钟 CRUD |`）改为 `| 日程/闹钟 | alarms | /profile/schedule（旧 /alarms 302） | 月历展开 + 闹钟 CRUD |`
- 页面前缀清单中 `/alarms` 替换为 `/profile/schedule`；第 321 行附近页面清单表 `alarms | /alarms 闹钟管理` 同步改
- `### 闹钟（alarms 模块）` 小节开头补一行说明：页面为 `/profile/schedule`（日历 + 表单 + 列表），`GET /api/me/calendar?month=YYYY-MM` 返回按日展开结果（自己的 + 全部群闹钟，循环只向前展开）

`kb/QUICK_REFERENCE.md`：grep 确认无 `/alarms` 引用则不动（预检已确认无）。

- [ ] **Step 6: 全量回归 + 提交**

Run: `python -m pytest`
Expected: 全部通过（含脚本式与 node DOM 套件）

```bash
git add webapp/alarms/app.py core/web/static/nav.js webapp/static/profile.html webapp/static/checkin.html webapp/static/shop.html webapp/static/settings.html webapp/timeline/entries.json test/scripts/check_alarm_calendar_api.py CHANGELOG.md core/config.py specs/web-gallery.md
git commit -m "feat(日程): 日程页上线并替换旧闹钟页"
```

（`git rm` 已暂存删除；本 commit 为用户可见变更，CHANGELOG 与版本号随行。）

---

## 自审记录

- **Spec 覆盖**：D1（隐私查询 + is_mine 标记）→ Task 1；D2（点格预填/过去置灰）→ Task 3；D3（scope 开关 + 互转）→ Task 2/3；D4（302/导航四处/模块不搬家）→ Task 4；D5（手写月历）→ Task 3；D6（服务端展开）→ Task 1；编辑悬浮窗 → Task 2/3；列表保留 → Task 3（renderAlarmList）；边界（并发最后写赢、追平、历史不回溯、隐私、时区）→ Task 1/2 实现 + 测试；测试/文档清单 → 各 Task Step。
- **占位符扫描**：无 TBD/TODO；所有代码块为完整可落地内容。
- **类型一致性**：`calendar_month(user_id: str, month: str) -> dict`、`update_alarm(user_id, alarm_id, payload)`、日历项字段（含 `date/recur_kind/recur_a/recur_b`）在 Task 1（服务端）、Task 3（前端消费与 node 测试桩数据）三处一致；`place()` 的 `id_` 以首参显式传入（无闭包捕获）。
