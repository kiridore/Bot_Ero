# 活动详情页个人提交与网页提交 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 活动详情页显示自己的提交（进行中即可见、可更新）+ 网页端提交作品表单；relay 推进由 activity_timer 心跳补发；详情 API 隐私剥离。

**Architecture:** webapp/activities 原地扩展（me/submit 两个端点 + detail 剥离，multipart 照打卡先例）；bot 侧仅 plugins/activity/__init__.py 提取 `_relay_catchup` 并在 `_scan` 接线（webapp 无消息通道，推进补发 ≤60s）；前端 activities_detail.js 内嵌我的提交区块+表单。

**Tech Stack:** FastAPI（multipart 路由 async，照 `api_checkin_submit` 先例）+ SQLite + 原生 JS；测试 = `test/scripts/check_activities_api.py` 扩展 + 新进程内 `test/test_activity_relay_catchup.py` + 新 node DOM `test/test_activities_detail_render.js`（均被现有回归自动发现）。

**Spec:** `docs/superpowers/specs/2026-09-02-activity-web-submit-design.md`（决策 D1–D6）

## Global Constraints

- bot 进程禁 async/await（timer 改动为同步）；webapp multipart 上传路由用 async（打卡页先例）
- SQL 一律 `?` 参数化；`webapp` 不 import `plugins`（当前棒判定 webapp 内重实现；timer 测试 import plugins 合法）
- 图片限制复用打卡常量：`config.CHECKIN_MAX_IMAGES`（9）/ `config.CHECKIN_MAX_BYTES`（10MB）/ JPG·PNG·WebP·GIF
- 图片存 `ACTIVITY_ROOT/<id>/imgs/<seq>-<n>.<ext>`，**先全部存盘成功再写库**，更新=覆盖式（content/images 整体替换，旧文件留磁盘）
- Commit 中文 + Conventional Commits，4 个逻辑 commit；Task 4 含 CHANGELOG `[1.34.0]` + `BOTERO_VERSION = "1.34.0"`
- 测试统一 `pytest`（基线已知失败：`test_backup_summary.py` 3 例日期相关，与本计划无关）

---

### Task 1: 服务端 me/submit 端点 + 详情 API 隐私剥离

**Files:**
- Modify: `webapp/activities/app.py`
- Modify: `test/scripts/check_activities_api.py`（`print(f"\n{'ALL PASS'...")` 前追加）

**Interfaces:**
- Consumes: `db.activity.get_activity/get_members/add_member/set_ring/update_member/update_activity`（已存在）；`config.CHECKIN_MAX_IMAGES/CHECKIN_MAX_BYTES`、`ACTIVITY_ROOT`（已 import）；`get_activity` 返回的 `members[].images` **已是解析后的列表**
- Produces: `GET /api/activities/{id}/me` → `{"member": {...,"images":["/archive/..."]}|null, "can_submit": bool, "block_reason": str|null, "block_text": str|null}`；`POST /api/activities/{id}/submit`（multipart `content` + `files`）→ `{"ok":true,"updated":bool}`，不可提交 409、图片问题/空作品 400；`GET /api/activities/{id}` 加登录身份依赖且非 finished 剥离他人 `content/images/submitted_at`（Task 3 前端消费）

- [ ] **Step 1: check 脚本追加失败测试**

在 `test/scripts/check_activities_api.py` 的 `# —— 页面路由` 块之前插入（沿用现有 OWNER/OTHER/DB 模式；`FUTURE/FUTURE2`、`check()` 已有）：

```python
# —— 网页提交：me / submit / 隐私剥离 ——
import json as _json  # noqa: E402
import time as _time  # noqa: E402

H333 = {"Authorization": "Bearer " + make_login_key("333")}
H444 = {"Authorization": "Bearer " + make_login_key("444")}
DB.activity.update_activity(mid2, status="cancelled")  # 让出唯一进行中名额
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

r = client.post("/api/activities", headers=OH, json={
    "type": "relay", "title": "接龙三", "hours_per_user": 48, "deadline": FUTURE2})
rid3 = r.json()["id"]
DB.activity.add_member(rid3, "333", "成员甲")
DB.activity.add_member(rid3, "444", "成员乙")
DB.activity.set_ring(rid3, [("333", None, 1), ("444", None, 2)])
DB.activity.update_activity(rid3, status="running")
DB.activity.update_member(rid3, "333", received_at=_time.strftime("%Y-%m-%d %H:%M:%S"))

r = client.get(f"/api/activities/{rid3}/me", headers=H333)
check("me 当前棒可提交", r.status_code == 200 and r.json()["can_submit"] is True
      and r.json()["block_reason"] is None, r.text)
r = client.get(f"/api/activities/{rid3}/me", headers=H444)
check("me 非当前棒 not_my_turn", r.json()["block_reason"] == "not_my_turn")
r = client.get(f"/api/activities/{rid3}/me", headers=OH)
check("me 非成员 not_member", r.json()["member"] is None and r.json()["block_reason"] == "not_member")
r = client.get(f"/api/activities/99999/me", headers=OH)
check("me 不存在 404", r.status_code == 404)

r = client.post(f"/api/activities/{rid3}/submit", headers=H444, data={"content": "抢跑"})
check("submit 非轮到 409", r.status_code == 409 and "轮到你" in r.json().get("detail", ""), r.text)
r = client.post(f"/api/activities/{rid3}/submit", headers=H333, data={})
check("submit 空作品 400", r.status_code == 400, r.text)
r = client.post(f"/api/activities/{rid3}/submit", headers=H333,
                files=[("files", ("a.txt", b"hello", "text/plain"))], data={"content": "x"})
check("submit 非图片类型 400", r.status_code == 400, r.text)

r = client.post(f"/api/activities/{rid3}/submit", headers=H333,
                files=[("files", ("a.png", PNG, "image/png")),
                       ("files", ("b.png", PNG, "image/png"))],
                data={"content": "我的文字作品"})
check("submit 成功", r.status_code == 200 and r.json() == {"ok": True, "updated": False}, r.text)
from core.config import ACTIVITY_ROOT as _AR  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
check("图片落盘命名", (_Path(_AR) / str(rid3) / "imgs" / "1-1.png").is_file()
      and (_Path(_AR) / str(rid3) / "imgs" / "1-2.png").is_file())
m333 = DB.activity.get_member(rid3, "333")
check("提交写库", m333["status"] == "done" and m333["content"] == "我的文字作品"
      and _json.loads(m333["images"]) == ["1-1.png", "1-2.png"])

r = client.post(f"/api/activities/{rid3}/submit", headers=H333, data={"content": "改成纯文字"})
check("submit 更新覆盖", r.json() == {"ok": True, "updated": True}, r.text)
check("更新后 images 清空", _json.loads(DB.activity.get_member(rid3, "333")["images"]) == [])

r = client.get(f"/api/activities/{rid3}", headers=H333)
me_row = next(m for m in r.json()["members"] if m["user_id"] == "333")
other_row = next(m for m in r.json()["members"] if m["user_id"] == "444")
check("进行中他人作品剥离", other_row["content"] is None and other_row["images"] == []
      and other_row["submitted_at"] is None)
check("进行中本人保留", me_row["content"] == "改成纯文字")

DB.activity.update_member(rid3, "444", status="missed")
r = client.post(f"/api/activities/{rid3}/submit", headers=H444, data={"content": "补交"})
check("missed 提交 409", r.status_code == 409 and "截止" in r.json().get("detail", ""))
DB.activity.update_member(rid3, "444", status="pending")
DB.activity.update_activity(rid3, status="finished")
r = client.post(f"/api/activities/{rid3}/submit", headers=H444, data={"content": "x"})
check("finished 提交 409", r.status_code == 409)
r = client.get(f"/api/activities/{rid3}", headers=H444)
done_row = next(m for m in r.json()["members"] if m["user_id"] == "333")
check("finished 后归档公开", done_row["content"] == "改成纯文字"
      and done_row["images"] == [f"/archive/{rid3}/media/1-1.png", f"/archive/{rid3}/media/1-2.png"])

DB.activity.update_activity(rid3, status="cancelled")  # 让位给匹配用例
r = client.post("/api/activities", headers=OH, json={
    "type": "match", "title": "匹配三", "deadline": FUTURE2})
mid3 = r.json()["id"]
DB.activity.add_member(mid3, "333", "成员甲")
DB.activity.add_member(mid3, "444", "成员乙")
DB.activity.set_ring(mid3, [("333", "444", 1), ("444", "333", 2)])
DB.activity.update_activity(mid3, status="running")
r = client.get(f"/api/activities/{mid3}/me", headers=H444)
check("match 无轮次限制", r.json()["can_submit"] is True, r.text)
r = client.post(f"/api/activities/{mid3}/submit", headers=H444, data={"content": "任意时刻"})
check("match 提交 200", r.status_code == 200 and r.json()["updated"] is False, r.text)
```

- [ ] **Step 2: 运行确认失败**

Run: `python -X utf8 test/scripts/check_activities_api.py`
Expected: 新增 check 全部 FAIL（me/submit 路由 404），旧用例仍 ok

- [ ] **Step 3: 实现（app.py）**

import 区调整：`from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile`，顶部加 `import json`，`from core import config`。

`_announcement` 函数之后追加：

```python
# —— 网页端提交（与 bot /提交 语义对齐）——

_ALLOWED_MIME = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
_BLOCK_TEXT = {
    "not_started": "活动未开始或已取消",
    "finished": "活动已结束",
    "missed": "已截止或被跳过，无法提交",
    "left": "你已退出活动",
    "not_my_turn": "还未轮到你提交",
}


def _current_turn(members: list[dict]) -> dict | None:
    """与 plugins/activity/logic.current_turn 同语义（webapp 不 import plugins）。"""
    for m in sorted(members, key=lambda x: x["seq"]):
        if m["status"] == "pending":
            return m
    return None


def _submission_state(user_id: str, act: dict, members: list[dict]):
    """返回 (me_member|None, block_reason|None)，规则与 bot _handle_submit 对齐。"""
    me = next((m for m in members if str(m["user_id"]) == user_id), None)
    if me is None:
        return None, "not_member"
    if act["status"] != "running":
        return me, "finished" if act["status"] == "finished" else "not_started"
    if me["status"] == "left":
        return me, "left"
    if me["status"] in ("missed", "skipped"):
        return me, "missed"
    if me["status"] == "pending" and act["type"] == "relay":
        cur = _current_turn(members)
        if not cur or str(cur["user_id"]) != user_id:
            return me, "not_my_turn"
    return me, None


def _save_submission_images(activity_id: int, seq: int, files: list[tuple[bytes, str | None]]) -> list[str]:
    """存 ACTIVITY_ROOT/<id>/imgs/<seq>-<n>.<ext>（与 bot 命名一致）；限制同打卡。"""
    if len(files) > config.CHECKIN_MAX_IMAGES:
        raise ValueError(f"单次最多上传 {config.CHECKIN_MAX_IMAGES} 张图片")
    folder = ACTIVITY_ROOT / str(activity_id) / "imgs"
    saved = []
    for n, (data, mime_raw) in enumerate(files, 1):
        mime = (mime_raw or "").split(";")[0].strip().lower()
        ext = _ALLOWED_MIME.get(mime)
        if ext is None:
            raise ValueError("仅支持 JPG / PNG / WebP / GIF 图片")
        if len(data) > config.CHECKIN_MAX_BYTES:
            raise ValueError(f"单张图片不能超过 {config.CHECKIN_MAX_BYTES // (1024 * 1024)} MB")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{seq}-{n}{ext}").write_bytes(data)
        saved.append(f"{seq}-{n}{ext}")
    return saved
```

路由区追加（放 `api_my_activities` 之前）：

```python
@router.get("/api/activities/{activity_id}/me")
def api_activity_me(activity_id: int,
                    user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    me, reason = _submission_state(user_id, act, act["members"])
    member = None
    if me:
        member = {
            "status": me["status"], "seq": me["seq"],
            "content": me.get("content"), "submitted_at": me.get("submitted_at"),
            "images": [f"/archive/{activity_id}/media/{n}" for n in (me.get("images") or [])],
        }
    return {"member": member, "can_submit": reason is None,
            "block_reason": reason, "block_text": _BLOCK_TEXT.get(reason)}


@router.post("/api/activities/{activity_id}/submit")
async def api_activity_submit(
    activity_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
    content: str = Form(""),
    files: list[UploadFile] | None = File(None),
):
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    me, reason = _submission_state(user_id, act, act["members"])
    if reason is not None:
        raise HTTPException(status_code=409, detail=_BLOCK_TEXT.get(reason, "无法提交"))
    text = (content or "").strip()
    payloads = [(await f.read(), f.content_type) for f in (files or [])]
    try:
        # ponytail: 与 bot 同语义——先全部存盘成功再写库，任一失败整体不生效；更新=覆盖（旧文件留磁盘）
        saved = _save_submission_images(activity_id, me["seq"], payloads) if payloads else []
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not text and not saved:
        raise HTTPException(status_code=400, detail="请附上作品（文字或图片）")
    was_done = me["status"] == "done"
    db.activity.update_member(
        activity_id, user_id, status="done", content=text or None,
        images=json.dumps(saved) if saved else None, submitted_at=_now())
    return {"ok": True, "updated": was_done}
```

`api_activity_detail` 整体替换为（加身份依赖 + 剥离）：

```python
@router.get("/api/activities/{activity_id}")
def api_activity_detail(activity_id: int,
                        user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    for m in act["members"]:
        m["images"] = [
            f"/archive/{activity_id}/media/{name}" for name in m.get("images", [])
        ]
        # 隐私：进行中不外发他人提交内容（finished 后归档公开）
        if act["status"] != "finished" and str(m["user_id"]) != user_id:
            m["content"] = None
            m["images"] = []
            m["submitted_at"] = None
    return act
```

- [ ] **Step 4: 运行脚本确认通过**

Run: `python -X utf8 test/scripts/check_activities_api.py`
Expected: 全部 ok（含旧用例），退出码 0

- [ ] **Step 5: 全量回归 + 提交**

Run: `python -m pytest test/test_webapp_api_suites.py -q` → 通过（基线 3 失败除外，跑全套见 Task 4）

```bash
git add webapp/activities/app.py test/scripts/check_activities_api.py
git commit -m "feat(活动): 网页提交端点与详情隐私剥离"
```

---

### Task 2: bot `_relay_catchup` 补推进 + timer 接线

**Files:**
- Modify: `plugins/activity/__init__.py`
- Create: `test/test_activity_relay_catchup.py`

**Interfaces:**
- Consumes: 现有模块级 `_announce_group/_relay_advance/_finish_activity`（本文件）；`logic.current_turn/last_done`
- Produces: `_relay_catchup(api, db, act: dict, members: list[dict]) -> bool`（True=已补推进/收尾）；`_scan` relay 分支先调它

- [ ] **Step 1: 写失败测试**

创建 `test/test_activity_relay_catchup.py`：

```python
"""网页接力提交的补推进逻辑（plugins/activity._relay_catchup）进程内测试。"""

import unittest
from datetime import datetime

from core.database_manager import DbManager
from plugins.activity import _relay_catchup


class StubApi:
    def __init__(self):
        self.calls = []

    def call_api(self, action, params):
        self.calls.append((action, params))
        return 0


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class RelayCatchupTest(unittest.TestCase):
    def setUp(self):
        db = DbManager()
        db.cur.execute("DELETE FROM activity_members")
        db.cur.execute("DELETE FROM activities")
        db.conn.commit()
        self.db = DbManager()
        self.api = StubApi()

    def _mk_relay(self, members_spec):
        aid = self.db.activity.create_activity(
            123, "relay", "接力", None, "999", hours_per_user=48)
        self.db.activity.update_activity(aid, status="running")
        for uid, nick, seq, status, recv in members_spec:
            self.db.activity.add_member(aid, uid, nick)
            fields = {"seq": seq, "status": status}
            if status == "done":
                fields["content"] = f"{uid} 的作品"
                fields["submitted_at"] = _now()
            if recv:
                fields["received_at"] = recv
            self.db.activity.update_member(aid, uid, **fields)
        return aid

    def test_web_submit_advances_next(self):
        aid = self._mk_relay([
            ("111", "甲", 1, "done", _now()),      # 网页提交：done 但未推进
            ("222", "乙", 2, "pending", None),      # 未激活
        ])
        act = self.db.activity.get_activity(aid)
        ok = _relay_catchup(self.api, self.db, act, act["members"])
        self.assertTrue(ok)
        m2 = self.db.activity.get_member(aid, "222")
        self.assertIsNotNone(m2["received_at"], "下一棒应被激活")
        self.db.cur.execute("SELECT status FROM activities WHERE id = ?", (aid,))
        self.assertEqual(self.db.cur.fetchone()[0], "running")
        actions = [c[0] for c in self.api.calls]
        self.assertIn("send_group_msg", actions)

    def test_activated_chain_untouched(self):
        aid = self._mk_relay([
            ("111", "甲", 1, "done", _now()),
            ("222", "乙", 2, "pending", _now()),   # 已激活（bot 流程）
        ])
        act = self.db.activity.get_activity(aid)
        self.assertFalse(_relay_catchup(self.api, self.db, act, act["members"]))
        self.assertEqual(self.api.calls, [])

    def test_chain_tail_finishes(self):
        aid = self._mk_relay([
            ("111", "甲", 1, "done", _now()),
            ("222", "乙", 2, "done", None),         # 链尾网页提交：无 pending
        ])
        act = self.db.activity.get_activity(aid)
        self.assertTrue(_relay_catchup(self.api, self.db, act, act["members"]))
        self.db.cur.execute("SELECT status FROM activities WHERE id = ?", (aid,))
        self.assertEqual(self.db.cur.fetchone()[0], "finished")

    def test_no_done_predecessor_noop(self):
        aid = self._mk_relay([
            ("111", "甲", 1, "pending", None),      # 开始即异常态：不动作
            ("222", "乙", 2, "pending", None),
        ])
        act = self.db.activity.get_activity(aid)
        self.assertFalse(_relay_catchup(self.api, self.db, act, act["members"]))
        self.assertEqual(self.api.calls, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest test/test_activity_relay_catchup.py -v`
Expected: FAIL — `_relay_catchup` 不存在（ImportError）

- [ ] **Step 3: 实现**

`plugins/activity/__init__.py` 模块级，放 `_finish_activity` 函数之后：

```python
def _relay_catchup(api, db, act: dict, members: list[dict]) -> bool:
    """网页端提交的补推进：当前棒 pending 且未激活（received_at 空）且上一棒已完成。

    bot 端 /提交 即时推进不会进入此分支；活动开始时 seq1 由 _relay_advance 激活，
    「未激活且无已完成前驱」为不可能态，返回 False 不动作。链尾（无 pending）经网页
    提交时直接收尾归档。
    """
    from .logic import current_turn, last_done
    cur = current_turn(members)
    if cur is None:
        last = max(members, key=lambda m: m["seq"], default=None)
        if last is None or last["status"] != "done":
            return False
        _announce_group(api, act["group_id"], f"{last['nickname']} 完成接力")
        _finish_activity(api, db, act)
        return True
    if cur.get("received_at"):
        return False
    prev = last_done(members, cur["seq"])
    if not prev:
        return False
    _announce_group(api, act["group_id"], f"{prev['nickname']} 完成接力")
    if not _relay_advance(api, db, act, members, prev["seq"]):
        _finish_activity(api, db, act)
    return True
```

`ActivityTimerPlugin._scan` 的 relay 分支替换为（原 `cur = current_turn(members)` + `if cur and is_timeout(...)` 块整体改写）：

```python
            if act["type"] == "relay":
                if _relay_catchup(self.api, self.dbmanager, act, members):
                    members = self.dbmanager.activity.get_members(act["id"])
                else:
                    cur = current_turn(members)
                    if cur and is_timeout(cur.get("received_at"), now, act.get("hours_per_user") or 0):
                        self.dbmanager.activity.update_member(
                            act["id"], cur["user_id"], status="skipped")
                        self._announce_group(act["group_id"], f"{cur['nickname']} 超时未完成，跳过")
                        members = self.dbmanager.activity.get_members(act["id"])
                        if not _relay_advance(self.api, self.dbmanager, act, members, cur["seq"]):
                            _finish_activity(self.api, self.dbmanager, act)
```

- [ ] **Step 4: 测试通过 + 提交**

Run: `python -m pytest test/test_activity_relay_catchup.py -v` → 4 passed
Run: `python -m pytest test/test_webapp_api_suites.py -q` → 无回归

```bash
git add plugins/activity/__init__.py test/test_activity_relay_catchup.py
git commit -m "feat(活动): 接力网页提交心跳补推进"
```

---

### Task 3: 前端我的提交区块 + 提交表单

**Files:**
- Modify: `webapp/static/activities_detail.js`
- Modify: `webapp/static/activities_detail.html`（内嵌样式追加）
- Create: `test/test_activities_detail_render.js`

**Interfaces:**
- Consumes: Task 1 的 me/submit API；现有 `.work-content/.work-img/.muted/.detail-section` 样式与 `escapeHtml`
- Produces: 详情页「我的提交」+「提交作品」两区块（member=null 时隐藏）；`REASON_TEXT` 文案映射

- [ ] **Step 1: 写 node DOM 失败测试**

创建 `test/test_activities_detail_render.js`（stub 模式照 `test_settings_render.js`；activities_detail.js 用 innerHTML 模板渲染，getElementById 从 HTML 片段回建）：

```javascript
// 最小 DOM stub 验证 activities_detail.js：
// 我的提交区块（文字+图+可更新徽章）、can_submit 表单态、not_my_turn 原因态、非成员隐藏。
const fs = require("fs");

const ALL_ELS = [];
function makeEl(tag) {
  const el = {
    tagName: tag, id: "", type: "", className: "", textContent: "", value: "",
    children: [], dataset: {}, style: {}, _html: "", _listeners: {},
    addEventListener(t, f) { (el._listeners[t] = el._listeners[t] || []).push(f); },
    appendChild(c) { el.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => el.children.push(c)); },
    querySelector() { return null; },
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

const mainEl = makeEl("main");
mainEl.id = "detailMain";
const authArea = makeEl("div");
authArea.id = "authArea";
const els = { detailMain: mainEl, authArea, submitForm: null };
global.document = {
  createElement: makeEl,
  getElementById(id) {
    if (els[id]) return els[id];
    for (const el of ALL_ELS) {
      if (el.id === id) return el;
      if (el._html && new RegExp(`id="${id}"`).test(el._html)) {
        const stub = makeEl("div");
        stub.id = id;
        els[id] = stub;
        return stub;
      }
    }
    return null;
  },
};

global.location = { pathname: "/activities/3", search: "" };
const myUid = "333";
let meData = {
  member: { status: "done", seq: 1, content: "我的文字作品", submitted_at: "2026-09-02 10:00:00",
            images: ["/archive/3/media/1-1.png"] },
  can_submit: true, block_reason: null, block_text: null,
};
let actData = {
  id: 3, type: "relay", title: "接龙三", status: "running", hours_per_user: 48,
  members: [
    { user_id: "333", nickname: "成员甲", seq: 1, status: "done", content: "我的文字作品",
      images: ["/archive/3/media/1-1.png"], submitted_at: "2026-09-02 10:00:00" },
    { user_id: "444", nickname: "成员乙", seq: 2, status: "pending", images: [], content: null },
  ],
};
const posts = [];
global.fetch = async (path, options = {}) => {
  if (path === "/api/activities/3") return { ok: true, status: 200, json: async () => actData };
  if (path === "/api/activities/3/me") return { ok: true, status: 200, json: async () => meData };
  if (path.endsWith("/submit")) { posts.push(options); return { ok: true, status: 200, json: async () => ({ ok: true, updated: true }) }; }
  return { ok: false, status: 404, json: async () => ({}) };
};
global.GalleryAuth = {
  isLoggedIn: () => true,
  load: () => ({ token: "t", user_id: myUid, display_name: "甲", avatar_url: "" }),
  headers: () => ({}),
  renderAuth() {},
};
global.window = { addEventListener() {} };
global.FormData = class { constructor() { this._d = {}; } append(k, v) { this._d[k] = v; } };
global.confirm = () => true;
global.alert = () => {};

eval(fs.readFileSync("webapp/static/activities_detail.js", "utf8"));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

(async () => {
  await wait(150);
  const html = mainEl._html;

  // 1. 我的提交区块：内容 + 图片 + 可更新徽章
  check("含我的提交区块", html.includes("我的提交"));
  check("显示我的文字", html.includes("我的文字作品"));
  check("显示我的图片", html.includes("/archive/3/media/1-1.png"));
  check("可更新徽章", /已提交|可更新/.test(html));

  // 2. can_submit=true → 表单渲染（textarea + file + 按钮）
  check("含提交表单", html.includes("提交作品") && /textarea|work-input/.test(html));

  // 3. not_my_turn → 原因替代表单
  meData = { member: { status: "pending", seq: 2, content: null, submitted_at: null, images: [] },
             can_submit: false, block_reason: "not_my_turn", block_text: "还未轮到你提交" };
  actData.members[0].status = "done";
  loadDetail();
  await wait(100);
  const html2 = mainEl._html;
  check("原因提示替代表单", html2.includes("还未轮到你提交") && !/id="submitBtn"/.test(html2));

  // 4. not_member → 两块隐藏
  meData = { member: null, can_submit: false, block_reason: "not_member", block_text: null };
  loadDetail();
  await wait(100);
  const html3 = mainEl._html;
  check("非成员隐藏提交区", !html3.includes("我的提交") && !html3.includes("提交作品"));

  process.exit(fail ? 1 : 0);
})();
```

- [ ] **Step 2: 运行确认失败**

Run: `node test/test_activities_detail_render.js`
Expected: FAIL（「含我的提交区块」等断言红）

- [ ] **Step 3: 实现（js + html）**

`activities_detail.js`：
(a) `let actCache = null;` 行后追加：

```javascript
let meCache = null;
const REASON_TEXT = {
  not_started: "活动未开始，开始后才能提交",
  finished: "活动已结束",
  missed: "已截止或被跳过，无法提交",
  left: "你已退出活动",
  not_my_turn: "还未轮到你提交",
};

function mySubmissionBlock(me) {
  if (!me || !me.member) return "";
  const m = me.member;
  return `
    <section class="detail-section">
      <h2>我的提交${m.status === "done" ? "（已提交，可更新）" : ""}</h2>
      ${m.submitted_at ? `<div class="muted">${m.submitted_at}</div>` : ""}
      ${m.content ? `<p class="work-content">${escapeHtml(m.content)}</p>` : ""}
      ${m.images.map((u) => `<img class="work-img" src="${u}">`).join("")}
      ${m.status === "pending" && me.can_submit ? '<div class="muted">尚未提交</div>' : ""}
    </section>`;
}

function submitBlock(me) {
  if (!me || !me.member) return "";
  if (!me.can_submit) {
    return `
    <section class="detail-section">
      <h2>提交作品</h2>
      <p class="muted">${escapeHtml(me.block_text || REASON_TEXT[me.block_reason] || "当前无法提交")}</p>
    </section>`;
  }
  return `
    <section class="detail-section">
      <h2>提交作品</h2>
      <textarea id="myContent" class="work-input" rows="3" maxlength="2000"
        placeholder="作品文字（与图片至少一项）">${escapeHtml(me.member.content || "")}</textarea>
      <input type="file" id="myFiles" class="work-input" accept="image/*" multiple />
      <div class="submit-row">
        <button type="button" id="submitBtn" class="primary">提交</button>
        <span id="submitHint" class="muted"></span>
      </div>
    </section>`;
}

async function submitWork() {
  const btn = document.getElementById("submitBtn");
  const hint = document.getElementById("submitHint");
  const content = (document.getElementById("myContent")?.value || "").trim();
  const files = document.getElementById("myFiles")?.files || [];
  if (!content && !files.length) { hint.textContent = "请附上作品（文字或图片）"; return; }
  const fd = new FormData();
  fd.append("content", content);
  for (const f of files) fd.append("files", f);
  btn.disabled = true;
  btn.textContent = "提交中…";
  try {
    const res = await fetch(`/api/activities/${actCache.id}/submit`, {
      method: "POST", headers: GalleryAuth.headers(), body: fd,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "提交失败");
    hint.textContent = data.updated ? "已更新提交" : "提交成功";
    await loadDetail();
  } catch (err) {
    hint.textContent = err.message || "提交失败";
  } finally {
    btn.disabled = false;
    btn.textContent = "提交";
  }
}
```

(b) `loadDetail` 改造——`const res = await fetch(...)` 单拉改并行，渲染入口拼装两块并绑事件。原函数体改为：

```javascript
async function loadDetail() {
  const id = location.pathname.split("/")[2];
  const [res, meRes] = await Promise.all([
    fetch(`/api/activities/${id}`, { headers: GalleryAuth.headers() }),
    fetch(`/api/activities/${id}/me`, { headers: GalleryAuth.headers() }),
  ]);
  if (!res.ok) {
    mainEl.innerHTML = '<p class="loading-msg">加载失败</p>';
    return;
  }
  actCache = await res.json();
  meCache = meRes.ok ? await meRes.json() : { member: null, can_submit: false, block_reason: "not_member" };
  renderDetail();
}
```

（保持原 `loadDetail` 内对 `renderDetail` 的调用方式不变：若原函数直接内联渲染，则把渲染主体抽成 `renderDetail()` 供 `submitWork` 重入；`renderDetail` 末尾 `mainEl.innerHTML = ...` 的模板里，在参加人员 section 之后、worksBlock 之前插入 `${mySubmissionBlock(meCache)}${submitBlock(meCache)}`，随后追加事件绑定：`const sb = document.getElementById("submitBtn"); if (sb) sb.addEventListener("click", submitWork);`）

(c) 底部启动区 `loadDetail();` 保持不变。

`activities_detail.html` 内嵌 `<style>` 追加：

```css
    .work-input {
      width: 100%; box-sizing: border-box; margin-top: 8px; padding: 10px 12px;
      border: 1px solid var(--rule); border-radius: 8px;
      background: var(--paper-card); color: var(--ink); font: inherit;
    }
    .submit-row { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
    .submit-row .primary {
      border: 1px solid var(--accent); background: var(--accent-soft);
      color: var(--accent-ink); border-radius: 8px; padding: 8px 18px; cursor: pointer;
    }
    .submit-row .primary:disabled { opacity: 0.5; cursor: default; }
```

- [ ] **Step 4: node 测试通过**

Run: `node test/test_activities_detail_render.js`
Expected: 8 项全 ok（stub 缺方法按报错补 stub，不改页面语义；若页面 JS 语义有真 bug 修 JS 并记录）

- [ ] **Step 5: 回归 + 提交**

Run: `python -m pytest test/test_dom_render_suites.py -q` → 全过

```bash
git add webapp/static/activities_detail.js webapp/static/activities_detail.html test/test_activities_detail_render.js
git commit -m "feat(活动): 详情页我的提交区块与网页提交表单"
```

---

### Task 4: 文档、版本与全量回归

**Files:**
- Modify: `CHANGELOG.md`、`core/config.py`、`specs/web-gallery.md`、`kb/PLUGIN_CATALOG.md`

- [ ] **Step 1: 版本与 CHANGELOG**

`core/config.py`：`BOTERO_VERSION = "1.34.0"`。

`CHANGELOG.md` 顶部（`[未发布]` 节之前）插入：

```markdown
## [1.34.0] - 2026-09-02

### 新增

- **活动网页提交**：活动详情页新增「我的提交」与「提交作品」区块——进行中即可查看/更新自己的已提交作品（文字+图片），网页直接提交（图片规则同打卡：≤9 张、单张 ≤10MB、JPG/PNG/WebP/GIF），接力轮次、截止、退出等规则与 QQ 提交一致；接力经网页提交后由心跳在 1 分钟内补发推进与通知
- **详情隐私**：活动进行中，详情 API 不再下发其他成员的作品内容（本人与已结束归档不受影响）
```

- [ ] **Step 2: specs 与 kb**

`specs/web-gallery.md` 活动模块 API 表追加：

```markdown
| `GET` | `/api/activities/{id}/me` | 必须 | 我的成员态与提交（can_submit/block_reason） |
| `POST` | `/api/activities/{id}/submit` | 必须 | 网页提交作品（multipart，规则同 QQ /提交） |
```

detail 行说明补「进行中剥离他人作品字段」。

`kb/PLUGIN_CATALOG.md` `activity_timer` 行职责末尾加「网页接力提交补推进」。

- [ ] **Step 3: 全量回归 + 提交**

Run: `python -m pytest`（预期仅基线 3 失败）；`node test/test_activities_detail_render.js` ok

```bash
git add CHANGELOG.md core/config.py specs/web-gallery.md kb/PLUGIN_CATALOG.md
git commit -m "docs(活动): 网页提交版本与文档收尾"
```

---

## 自审记录

- **Spec 覆盖**：D1→Task 3；D2→Task 1（detail 剥离+测试）；D3→Task 1（_submission_state 全矩阵+测试）；D4→Task 2（catchup+链尾收尾）；D5→Task 3（toast/hint 反馈）；D6→Task 1（_save_submission_images）。
- **占位符扫描**：Task 3 Step 3(b) 有一处「保持原函数调用方式不变」的适配性描述——因实现者需对照原 148 行文件改造 loadDetail，代码骨架已给全（并行拉取 + renderDetail 抽取 + 插块 + 绑事件），不构成 TBD。
- **类型一致性**：me 响应 `{member,can_submit,block_reason,block_text}` 在 Task 1（服务端）、Task 3（前端与 node 桩）三处一致；`_relay_catchup(api, db, act, members) -> bool` 在 Task 2 定义并测试；`get_activity` 的 members[].images 已是列表（me 端点直接 map，submit 端点写库用 json.dumps 字符串——与表存储一致）。
- **预检**：check 脚本测试先用完 relay 再取消让位 match（`每群唯一进行中` 409 约束已处理）；`update_member(**fields)` 写 None 即清空（覆盖式更新的前提，已核 core/db/activity.py）。
