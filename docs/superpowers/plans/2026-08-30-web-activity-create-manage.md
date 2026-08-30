# Web 端活动创建与管理页面 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 webapp 活动模块新增"发起活动"页面与仅活动创建人可见的"活动管理"页面及配套 API。

**Architecture:** Web 只写共享 SQLite，QQ 通知全部借道 bot 心跳——"开始" = 写 `signup_deadline=now`、running 的"提前结束" = 写 `deadline=now`，bot 进程的 `ActivityTimerPlugin`（≥60s 轮询）会走现成的 `_start_activity`/截止收尾路径补发全部私聊+群通知。bot 侧零改动、DB 零新表零迁移。创建成功的群公告文案由服务端生成，用户手动复制贴群。

**Tech Stack:** FastAPI（同步 `def` 路由）+ Pydantic v2 + 共享 `core.database_manager.DbManager` + 原生 JS 静态页（`GalleryAuth` 鉴权）。

**Spec:** 本文件头部《设计决策》节（源自 2026-08-30 对话确认，无独立 spec 文档）。

## 设计决策（已与用户逐条确认）

1. **通知方案 C + B1**：Web 创建不发 QQ 消息；创建成功页给可复制公告文案（服务端单一来源生成）。Web"开始"=`signup_deadline=now`，"提前结束"(running)=`deadline=now`，均由 bot 心跳 ≤60s 内代发通知。"取消"(open)=直接写 `status='cancelled'`（bot 群内取消同样无通知）。
2. **编辑范围**：`open` 可改 标题/描述/报名截止/截止/每人限时；`running` 可改 标题/描述/截止（延长）。其余字段/状态拒绝。
3. **群固定** `DEFAULT_GROUP_ID`（`core/context.py`，值 296470819），不做选择器。
4. **不做**：成员管理（踢人/转让）、outbox 通知桥、bot 侧任何改动、DB schema 变更。
5. **权限**：`created_by == 登录QQ号` 或 `SUPER_USER`（`core/base.py`，`[1057613133]`），与 bot 端 `/活动 开始|结束` 权限一致。owner 校验必须在服务端。

## Global Constraints

- **路由必须同步 `def`**，不用 `async def`（webapp 现有风格；async 仅限 middleware）。
- **No f-string SQL**：只用现有 `DbManager.activity.*` 方法（`?` 参数化），本计划唯一 SQL 改动是 `core/db/activity.py::list_activities` 的 SELECT 列清单加一列 `a.created_by`。
- **认证依赖唯一来源** `core.web.auth_deps.get_current_user_id`，禁止复制。
- **禁止 webapp import plugins.***（会触发 `plugins/__init__.py` 全量 walk 导入）。公告文案/时长格式化在 webapp 侧独立实现。
- **静态文件名全局唯一**（`webapp/static/` 平铺合并）：新文件 `activities_new.html/js`、`activities_manage.html/js` 已确认无冲突。
- **路由顺序**：`GET /activities/new` 必须注册在 `GET /activities/{activity_id}` **之前**（FastAPI 先匹配先注册，`new` 会撞 int 校验返回 422）。`webapp/app.py` 中 activities_router 仍是最后 include（`specs/web-gallery.md` 已注明原因，勿动）。
- **测试**：行为测试放 `test/scripts/check_activities_api.py`（模块级自校验脚本，失败退出码非 0；放进目录即被 `test/test_webapp_api_suites.py` 子进程自动纳入回归）。模板参照 `test/scripts/check_forum_edit_api.py`：临时 DB + `init_schema` + `TestClient` + `make_login_key` 真实鉴权链路。
- **Commit**：中文 Conventional Commits；代码+行为测试+spec 同 commit；CHANGELOG + `core/config.py::BOTERO_VERSION` bump（minor）放最后的 `chore(版本)` commit（项目既有惯例，参照 34296bf）。
- **测试前置**：跑任何 pytest/check 脚本前确认工作区干净；conftest 已把 `BOTERO_*` 数据路径重定向到临时目录，不会触碰真实 data.db。
- **静态页引用版本**：auth.js 带 `?v=3` 查询串，新页面照抄。

---

### Task 1: 活动管理 API（创建/编辑/开始/结束/取消/公告文案）

**Files:**
- Modify: `webapp/activities/app.py`（新增 6 个端点 + 辅助函数）
- Modify: `core/db/activity.py:152-170`（`list_activities` SELECT 加 `a.created_by`）
- Create: `test/scripts/check_activities_api.py`
- Modify: `specs/web-gallery.md`（§活动 路由表加 6 行）

**Interfaces:**
- Consumes: `DbManager.activity.create_activity(group_id, type_, title, description, created_by, hours_per_user, deadline, signup_deadline) -> int`；`get_activity(id) -> dict|None`（含 `members` 列表与 `created_by`）；`get_active_activity(group_id)`；`get_members(id)`；`update_activity(id, **fields)`；`get_member(id, uid)`；`add_member(id, uid, nickname)` —— 均已存在，勿改签名。
- Produces（后续 Task 依赖的准确契约）:
  - `POST /api/activities` body `{"type":"relay|match","title":str,"description":str|null,"hours_per_user":float>0,"signup_deadline":str|null,"deadline":str|null}`（extra=forbid）→ `{"ok":true,"id":int,"announce":str}`
  - `PATCH /api/activities/{id}` body 同上字段全可选 → `{"ok":true}`
  - `POST /api/activities/{id}/start` → `{"ok":true,"note":"已请求开始，约 1 分钟内生效并通知所有成员"}`
  - `POST /api/activities/{id}/finish` → `{"ok":true,"note":"已请求提前结束，约 1 分钟内生效，未提交成员将记为未交"}`
  - `POST /api/activities/{id}/cancel` → `{"ok":true}`
  - `GET /api/activities/{id}/announce`（登录+owner）→ `{"announce":str}`
  - 日期入参格式 `"YYYY-MM-DD HH:MM"` 或 `"YYYY-MM-DD HH:MM:SS"`，库内/出参恒为 `"YYYY-MM-DD HH:MM:SS"`。
  - `GET /api/activities` 列表项新增 `created_by` 字段（Task 3/4 前端入口用）。

- [ ] **Step 1: 写失败的行为测试脚本**

创建 `test/scripts/check_activities_api.py`（完整文件，直接落地）：

```python
"""活动创建/管理 API 行为测试：鉴权、owner 校验、创建校验、编辑白名单、B1 动作语义。

独立进程运行: python test/scripts/check_activities_api.py
（pytest 由 test/test_webapp_api_suites.py 子进程纳入统一回归）
"""

import os
import sqlite3
import tempfile

# 必须在 import core.config / webapp 之前重定向 DB
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_activity_test_")
_db = os.path.join(_tmp, "test.db")
os.environ["BOTERO_DB_PATH"] = _db

_conn = sqlite3.connect(_db)
_cur = _conn.cursor()
from core.database_manager import init_schema  # noqa: E402
init_schema(_conn, _cur)
_conn.commit()
_conn.close()

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from core.database_manager import DbManager  # noqa: E402
from webapp.app import app  # noqa: E402

client = TestClient(app)
OWNER, OTHER, SUPER = "111", "222", "1057613133"
OH = {"Authorization": "Bearer " + make_login_key(OWNER), "Content-Type": "application/json"}
OTH = {"Authorization": "Bearer " + make_login_key(OTHER), "Content": "application/json"}
SH = {"Authorization": "Bearer " + make_login_key(SUPER), "Content": "application/json"}


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


fail = 0

FUTURE = "2099-01-01 20:00"
FUTURE2 = "2099-02-01 20:00"

# —— 创建 ——
r = client.post("/api/activities", json={"type": "relay", "title": "接龙一"})
check("未登录创建 401", r.status_code == 401)
r = client.post("/api/activities", headers=OH, json={"type": "match", "title": "匹配一"})
check("匹配缺截止 400", r.status_code == 400, r.text)
r = client.post("/api/activities", headers=OH, json={
    "type": "relay", "title": "接龙一", "deadline": "2000-01-01 20:00"})
check("过去截止 400", r.status_code == 400, r.text)
r = client.post("/api/activities", headers=OH, json={
    "type": "relay", "title": "接龙一", "deadline": "not-a-date"})
check("截止格式错 400", r.status_code == 400, r.text)
r = client.post("/api/activities", headers=OH, json={
    "type": "match", "title": "匹配一", "deadline": FUTURE,
    "signup_deadline": FUTURE2, "description": "描述", "hours_per_user": 24})
check("匹配创建 200", r.status_code == 200, r.text)
mid = r.json().get("id")
check("返回 id 与公告", isinstance(mid, int) and "匹配下家" in r.json().get("announce", ""))
r = client.post("/api/activities", headers=OH, json={"type": "relay", "title": "接龙二"})
check("每群唯一进行中 409", r.status_code == 409, r.text)

# —— 公告查询 ——
r = client.get(f"/api/activities/{mid}/announce", headers=OTH)
check("非 owner 查公告 403", r.status_code == 403)
r = client.get(f"/api/activities/{mid}/announce", headers=OH)
check("owner 查公告 200", r.status_code == 200 and "活动发起" in r.json().get("announce", ""))

# —— 编辑 ——
r = client.patch(f"/api/activities/{mid}", headers=OTH, json={"title": "抢改"})
check("非 owner 编辑 403", r.status_code == 403)
r = client.patch(f"/api/activities/{mid}", headers=OH, json={
    "title": "匹配一改", "description": "新描述", "signup_deadline": FUTURE, "deadline": FUTURE2})
check("open 编辑 200", r.status_code == 200, r.text)
r = client.get(f"/api/activities/{mid}")
check("编辑生效", r.json().get("title") == "匹配一改" and r.json().get("description") == "新描述")
r = client.patch(f"/api/activities/{mid}", headers=OH, json={"hours_per_user": 0})
check("hours<=0 拒绝", r.status_code == 422, r.text)
r = client.patch(f"/api/activities/{mid}", headers=OH, json={"deadline": "2000-01-01 20:00"})
check("编辑过去截止 400", r.status_code == 400, r.text)
r = client.patch(f"/api/activities/{mid}", headers=OH, json={"nope": 1})
check("未知字段 422", r.status_code == 422, r.text)

# —— 取消后可再创建 ——
r = client.post(f"/api/activities/{mid}/cancel", headers=OH)
check("owner 取消 200", r.status_code == 200, r.text)
r = client.post(f"/api/activities/{mid}/cancel", headers=OH)
check("重复取消 409", r.status_code == 409)
r = client.post("/api/activities", headers=OH, json={
    "type": "relay", "title": "接龙二", "hours_per_user": 48,
    "signup_deadline": FUTURE, "deadline": FUTURE2})
check("取消后创建 200", r.status_code == 200, r.text)
rid = r.json()["id"]
check("接龙公告含限时", "48 小时" in r.json().get("announce", ""))
r = client.get("/api/activities")
check("列表含 created_by", any(a.get("created_by") == OWNER for a in r.json()["items"]))

# —— 开始（B1：signup_deadline=now）——
r = client.post(f"/api/activities/{rid}/start", headers=OTH)
check("非 owner 开始 403", r.status_code == 403)
r = client.post(f"/api/activities/{rid}/start", headers=OH)
check("接龙 0 人开始 409", r.status_code == 409, r.text)
DbManager().activity.add_member(rid, "333", "成员甲")
r = client.post(f"/api/activities/{rid}/start", headers=OH)
check("开始 200", r.status_code == 200, r.text)
r = client.get(f"/api/activities/{rid}")
check("signup_deadline 已置为当前", r.json().get("status") == "open"
      and r.json().get("signup_deadline", "9999") <= __import__("time").strftime("%Y-%m-%d %H:%M:%S"))
r = client.post(f"/api/activities/{rid}/start", headers=OH)
check("重复开始仍 open 200（幂等）", r.status_code == 200)

# 直接置 running 验证 running 态规则（心跳在测试进程不存在）
DbManager().activity.update_activity(rid, status="running")
r = client.patch(f"/api/activities/{rid}", headers=OH, json={"signup_deadline": FUTURE})
check("running 改报名截止 400", r.status_code == 400, r.text)
r = client.patch(f"/api/activities/{rid}", headers=OH, json={"hours_per_user": 72})
check("running 改限时 400", r.status_code == 400, r.text)
r = client.patch(f"/api/activities/{rid}", headers=OH, json={"title": "接龙二改", "deadline": FUTURE2})
check("running 改标题/截止 200", r.status_code == 200, r.text)
r = client.patch(f"/api/activities/{rid}", headers=SH, json={"title": "超管改"})
check("超管可编辑 200", r.status_code == 200, r.text)

# —— 提前结束（B1：deadline=now）——
r = client.post(f"/api/activities/{rid}/finish", headers=OTH)
check("非 owner 结束 403", r.status_code == 403)
r = client.post(f"/api/activities/{rid}/finish", headers=OH)
check("提前结束 200", r.status_code == 200, r.text)
r = client.get(f"/api/activities/{rid}")
check("deadline 已置为当前", r.json().get("deadline", "9999") <= __import__("time").strftime("%Y-%m-%d %H:%M:%S"))
DbManager().activity.update_activity(rid, status="finished")
r = client.patch(f"/api/activities/{rid}", headers=OH, json={"title": "x"})
check("finished 后编辑 409", r.status_code == 409)
r = client.post(f"/api/activities/{rid}/finish", headers=OH)
check("finished 后结束 409", r.status_code == 409)

# —— 匹配活动开始需 ≥2 人 ——
r = client.post("/api/activities", headers=OH, json={
    "type": "match", "title": "匹配二", "deadline": FUTURE})
mid2 = r.json()["id"]
DbManager().activity.add_member(mid2, "333", "成员甲")
r = client.post(f"/api/activities/{mid2}/start", headers=OH)
check("匹配 1 人开始 409", r.status_code == 409, r.text)
DbManager().activity.add_member(mid2, "444", "成员乙")
r = client.post(f"/api/activities/{mid2}/start", headers=OH)
check("匹配 2 人开始 200", r.status_code == 200, r.text)

# —— 404 ——
r = client.patch("/api/activities/99999", headers=OH, json={"title": "x"})
check("编辑不存在 404", r.status_code == 404)

print(f"\n{'ALL PASS' if fail == 0 else f'{fail} FAILED'}")
sys.exit(1 if fail else 0)
```

注意：测试里"重复开始仍 open 200（幂等）"一条——`start` 对 open 活动重复调用只是把 `signup_deadline` 再刷成 now，无副作用，故设计为幂等 200。

- [ ] **Step 2: 运行确认失败**

Run: `python test/scripts/check_activities_api.py`
Expected: FAIL —— 大量用例 404/405（端点不存在），退出码 1。

- [ ] **Step 3: 实现 `webapp/activities/app.py` 全部端点**

在文件头部 import 区追加：

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.base import SUPER_USER
from core.context import DEFAULT_GROUP_ID
```

（原 `from typing import Annotated`、`Depends`、`get_current_user_id` 已存在。）在现有路由定义之前加辅助与模型：

```python
# —— 写入辅助 ——


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _require_owner(act: dict, user_id: str) -> None:
    """与 bot 端 /活动 开始|结束 权限一致：创建人或 SUPER_USER。"""
    if str(act["created_by"]) != user_id and int(user_id) not in SUPER_USER:
        raise HTTPException(status_code=403, detail="仅活动创建人可管理")


def _parse_future_deadline(raw: str | None, label: str) -> str | None:
    """None/空串→None；解析 'YYYY-MM-DD HH:MM[:SS]' 且必须晚于当前，否则 400。返回完整格式。"""
    if not raw:
        return None
    parsed = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(raw, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        raise HTTPException(status_code=400, detail=f"{label}格式错误，应为 YYYY-MM-DD HH:MM")
    if parsed <= datetime.now():
        raise HTTPException(status_code=400, detail=f"{label}必须晚于当前时间")
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _format_duration(hours: float) -> str:
    """48→'2 天'；36→'36 小时'。与插件侧 format_duration 显示一致（webapp 不能 import plugins）。"""
    return f"{int(hours // 24)} 天" if hours % 24 == 0 else f"{hours:g} 小时"


def _announcement(act: dict) -> str:
    """创建人复制到群里的公告文案（服务端单一来源）。"""
    kind = "接龙" if act["type"] == "relay" else "匹配下家"
    lines = [f"【活动发起】{kind}「{act['title']}」（#{act['id']}）"]
    if act["type"] == "relay":
        lines.append(f"每人限时 {_format_duration(act['hours_per_user'] or 48)}")
    if act.get("deadline"):
        lines.append(f"截止：{act['deadline']}")
    if act.get("description"):
        lines.append(f"描述：{act['description']}")
    if act.get("signup_deadline"):
        lines.append(f"报名截止：{act['signup_deadline']}（到点自动开始）")
    lines.append("回复 /活动 加入 报名，报名完成后由创建人 /活动 开始")
    return "\n".join(lines)


class ActivityCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(pattern="^(relay|match)$")
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    hours_per_user: float = Field(default=48.0, gt=0)
    signup_deadline: str | None = None
    deadline: str | None = None


class ActivityEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    hours_per_user: float | None = Field(default=None, gt=0)
    signup_deadline: str | None = None
    deadline: str | None = None


_EDITABLE = {
    "open": {"title", "description", "hours_per_user", "signup_deadline", "deadline"},
    "running": {"title", "description", "deadline"},
}
_FIELD_LABEL = {"title": "标题", "description": "描述", "hours_per_user": "每人限时",
                "signup_deadline": "报名截止", "deadline": "截止时间"}
```

在 `api_activities`（列表）之后追加端点（`GET /activities/new` 页面路由在 Task 2 加，注意届时插在 `activity_detail_page` 之前）：

```python
@router.post("/api/activities")
def api_create_activity(body: ActivityCreateIn,
                        user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    if db.activity.get_active_activity(DEFAULT_GROUP_ID):
        raise HTTPException(status_code=409, detail="本群已有进行中的活动")
    if body.type == "match" and not body.deadline:
        raise HTTPException(status_code=400, detail="匹配活动必须设定截止时间")
    deadline = _parse_future_deadline(body.deadline, "截止时间")
    signup_deadline = _parse_future_deadline(body.signup_deadline, "报名截止")
    hours = body.hours_per_user if body.type == "relay" else None  # 与插件创建一致：匹配不存限时
    aid = db.activity.create_activity(
        DEFAULT_GROUP_ID, body.type, body.title.strip(), body.description, user_id,
        hours_per_user=hours, deadline=deadline, signup_deadline=signup_deadline)
    return {"ok": True, "id": aid, "announce": _announcement(db.activity.get_activity(aid))}


@router.get("/api/activities/{activity_id}/announce")
def api_activity_announce(activity_id: int,
                          user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    _require_owner(act, user_id)
    return {"announce": _announcement(act)}


@router.patch("/api/activities/{activity_id}")
def api_edit_activity(activity_id: int, body: ActivityEditIn,
                      user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    _require_owner(act, user_id)
    if act["status"] not in _EDITABLE:
        raise HTTPException(status_code=409, detail="活动已结束，无法编辑")
    provided = {k for k, v in body.model_dump().items() if v is not None}
    rejected = provided - _EDITABLE[act["status"]]
    if rejected:
        raise HTTPException(
            status_code=400,
            detail="当前状态不能修改：" + "、".join(sorted(_FIELD_LABEL[k] for k in rejected)))
    fields = {}
    if body.title is not None:
        fields["title"] = body.title.strip()
    if body.description is not None:
        fields["description"] = body.description
    if body.hours_per_user is not None:
        fields["hours_per_user"] = body.hours_per_user
    if body.signup_deadline is not None:
        fields["signup_deadline"] = _parse_future_deadline(body.signup_deadline, "报名截止")
    if body.deadline is not None:
        fields["deadline"] = _parse_future_deadline(body.deadline, "截止时间")
    if fields:
        db.activity.update_activity(activity_id, **fields)
    return {"ok": True}


@router.post("/api/activities/{activity_id}/start")
def api_start_activity(activity_id: int,
                       user_id: Annotated[str, Depends(get_current_user_id)]):
    """open → 写 signup_deadline=当前时间；bot 心跳 ≤60s 内自动开始并补发全部私聊/群通知。幂等。"""
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    _require_owner(act, user_id)
    if act["status"] != "open":
        raise HTTPException(status_code=409, detail="活动不在报名中，无法开始")
    members = db.activity.get_members(activity_id)
    if act["type"] == "relay" and len(members) < 1:
        raise HTTPException(status_code=409, detail="接龙活动至少需要 1 人报名")
    if act["type"] == "match" and len(members) < 2:
        raise HTTPException(status_code=409, detail="匹配活动至少需要 2 人报名")
    if act.get("deadline") and act["deadline"] <= _now():  # 与插件 _start_activity 预检一致
        raise HTTPException(status_code=409, detail="截止时间已过，无法开始活动")
    db.activity.update_activity(activity_id, signup_deadline=_now())
    return {"ok": True, "note": "已请求开始，约 1 分钟内生效并通知所有成员"}


@router.post("/api/activities/{activity_id}/finish")
def api_finish_activity(activity_id: int,
                        user_id: Annotated[str, Depends(get_current_user_id)]):
    """running → 写 deadline=当前时间；bot 心跳 ≤60s 内收尾：未交者置 missed、归档、群公告。"""
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    _require_owner(act, user_id)
    if act["status"] != "running":
        raise HTTPException(status_code=409, detail="活动不在进行中，无法提前结束")
    db.activity.update_activity(activity_id, deadline=_now())
    return {"ok": True, "note": "已请求提前结束，约 1 分钟内生效，未提交成员将记为未交"}


@router.post("/api/activities/{activity_id}/cancel")
def api_cancel_activity(activity_id: int,
                        user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    _require_owner(act, user_id)
    if act["status"] != "open":
        raise HTTPException(status_code=409, detail="活动已开始，不能取消（可提前结束）")
    db.activity.update_activity(activity_id, status="cancelled")
    return {"ok": True}
```

- [ ] **Step 4: `list_activities` 加 created_by 列**

`core/db/activity.py::list_activities` 的 SELECT 列清单 `" a.signup_deadline, a.deadline,"` 行改为：

```python
            " a.created_by, a.signup_deadline, a.deadline,"
```

- [ ] **Step 5: 运行测试脚本确认全过**

Run: `python test/scripts/check_activities_api.py`
Expected: 末行 `ALL PASS`，退出码 0。

- [ ] **Step 6: 全量回归**

Run: `pytest`
Expected: 全部通过（新脚本被 `test_webapp_api_suites.py` 自动纳入）。

- [ ] **Step 7: 更新 spec 并提交**

`specs/web-gallery.md` §活动（`activities` 模块）路由表追加（格式照现有行）：

```
| `POST` | `/api/activities` | 必须 | 创建活动（type/title/description/hours_per_user/signup_deadline/deadline；匹配必带截止、日期须未来、每群唯一进行中）→ {ok,id,announce=可复制群公告文案}。群固定 DEFAULT_GROUP_ID，created_by=登录用户 |
| `PATCH` | `/api/activities/{id}` | 必须 | 创建人/超管编辑：open 可改 标题/描述/每人限时/报名截止/截止，running 仅 标题/描述/截止；他字段 400，结束后 409 |
| `POST` | `/api/activities/{id}/start` | 必须 | 仅 open；人数预检（接龙≥1 匹配≥2）后写 signup_deadline=now，bot 心跳 ≤60s 自动开始并通知（B1 方案，幂等） |
| `POST` | `/api/activities/{id}/finish` | 必须 | 仅 running；写 deadline=now，bot 心跳 ≤60s 收尾（未交置 missed+归档+群公告） |
| `POST` | `/api/activities/{id}/cancel` | 必须 | 仅 open；直接置 cancelled（与群内取消一致，无通知） |
| `GET` | `/api/activities/{id}/announce` | 必须 | 创建人/超管获取群公告文案（单一来源生成） |
```

同表 `GET /api/activities` 行的说明末尾追加"含 created_by"。

```bash
git add webapp/activities/app.py core/db/activity.py test/scripts/check_activities_api.py specs/web-gallery.md
git commit -m "feat(活动): Web 端活动创建与管理 API（通知借道心跳）"
```

---

### Task 2: 发起活动页面

**Files:**
- Modify: `webapp/activities/app.py`（加 `GET /activities/new` 页面路由，**必须放在 `activity_detail_page` 之前**）
- Create: `webapp/static/activities_new.html`
- Create: `webapp/static/activities_new.js`
- Modify: `test/scripts/check_activities_api.py`（追加页面路由断言）
- Modify: `specs/web-gallery.md`（§静态页面表加一行）

**Interfaces:**
- Consumes: Task 1 的 `POST /api/activities`（`{ok,id,announce}`）；`GalleryAuth.headers()`（`/shared/auth.js` 全局，现有 API：`isLoggedIn()/headers()/load()/renderAuth(el)`）。
- Produces: 页面路由 `GET /activities/new` → 200 HTML；成功创建后跳转链接目标 `/activities/{id}/manage`（Task 3 实现）。

- [ ] **Step 1: 追加失败的页面路由断言**

`test/scripts/check_activities_api.py` 末段（`print(f"\n...")` 之前）追加：

```python
# —— 页面路由（登录门控由 middleware 处理，Bearer 可过）——
r = client.get("/activities/new", headers=OH, follow_redirects=False)
check("发起页 200", r.status_code == 200 and "text/html" in r.headers.get("content-type", ""))
r = client.get("/activities/new", follow_redirects=False)
check("发起页未登录 302", r.status_code == 302)
```

- [ ] **Step 2: 运行确认失败**

Run: `python test/scripts/check_activities_api.py`
Expected: `发起页 200` 一条 FAIL（404，路由不存在），退出码 1。

- [ ] **Step 3: 加页面路由**

`webapp/activities/app.py` 中、**`activities_page` 之后、`activity_detail_page` 之前**插入：

```python
@router.get("/activities/new")
def activity_new_page():
    page = STATIC_DIR / "activities_new.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)
```

- [ ] **Step 4: 创建 `webapp/static/activities_new.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>发起活动</title>
  <link rel="stylesheet" href="/shared/base.css" />
  <link rel="stylesheet" href="/shared/motion.css" />
  <link rel="stylesheet" href="/shared/profile.css" />
  <style>
    .form-card { background: var(--paper-card); border: 1px solid var(--rule); border-radius: 10px; padding: 16px; max-width: 640px; margin: 0 auto; }
    .form-row { margin-bottom: 14px; display: flex; flex-direction: column; gap: 6px; }
    .form-row > label { font-size: 14px; color: var(--ink); }
    .form-row input[type=text], .form-row input[type=number], .form-row input[type=datetime-local], .form-row textarea {
      padding: 8px 10px; border: 1px solid var(--rule); border-radius: 8px; font-size: 14px;
      background: transparent; color: inherit; font-family: inherit;
    }
    .radio-row { display: flex; gap: 18px; }
    .radio-row label { display: flex; align-items: center; gap: 6px; font-size: 14px; }
    .radio-row input { accent-color: var(--accent); }
    .btn-primary { padding: 9px 18px; border: none; border-radius: 8px; background: var(--accent); color: #fff; font-size: 14px; cursor: pointer; }
    .btn-primary:disabled { opacity: .6; cursor: default; }
    .btn-ghost { padding: 9px 18px; border: 1px solid var(--rule); border-radius: 8px; background: transparent; color: inherit; font-size: 14px; cursor: pointer; text-decoration: none; display: inline-block; }
    .announce-box { white-space: pre-wrap; background: var(--paper-card); border: 1px dashed var(--rule); border-radius: 8px; padding: 12px; font-size: 14px; margin: 12px 0; }
    .msg { font-size: 13px; margin-top: 8px; min-height: 18px; }
    .msg.err { color: var(--red); }
    .msg.ok { color: var(--gold); }
    .muted { color: var(--ink-soft); font-size: 13px; }
  </style>
</head>
<body>
  <header class="toolbar profile-toolbar">
    <div class="auth-area" id="authArea"></div>
  </header>

  <main class="profile-main">
    <section id="createForm" class="form-card">
      <h2>发起活动</h2>
      <div class="form-row">
        <label>类型</label>
        <div class="radio-row">
          <label><input type="radio" name="actType" value="relay" checked />接龙</label>
          <label><input type="radio" name="actType" value="match" />匹配下家</label>
        </div>
      </div>
      <div class="form-row">
        <label for="title">标题 *</label>
        <input type="text" id="title" maxlength="100" placeholder="如：端午自由创作" />
      </div>
      <div class="form-row">
        <label for="description">描述</label>
        <textarea id="description" rows="3" maxlength="500" placeholder="活动说明（可选）"></textarea>
      </div>
      <div class="form-row" id="hoursRow">
        <label for="hours">每人限时（小时，默认 48）</label>
        <input type="number" id="hours" min="0.5" step="0.5" value="48" />
      </div>
      <div class="form-row">
        <label for="signupDeadline">报名截止（到点自动开始，可选）</label>
        <input type="datetime-local" id="signupDeadline" />
      </div>
      <div class="form-row">
        <label for="deadline">截止时间 <span id="deadlineMust" hidden style="color: var(--red)">（匹配必填）</span></label>
        <input type="datetime-local" id="deadline" />
      </div>
      <button class="btn-primary" id="submitBtn">创建活动</button>
      <p class="msg" id="msg"></p>
      <p class="muted">创建成功后复制公告文案发到群里，大家回复「/活动 加入」报名。</p>
    </section>

    <section id="createOk" class="form-card" hidden>
      <h2>创建成功</h2>
      <p class="muted">把下面的公告复制到群里，通知大家报名：</p>
      <div class="announce-box" id="announceBox"></div>
      <button class="btn-primary" id="copyBtn">复制公告</button>
      <p class="msg" id="copyMsg"></p>
      <p style="margin-top: 16px">
        <a class="btn-ghost" id="manageLink" href="#">前往管理页</a>
        <a class="btn-ghost" href="/activities">返回活动列表</a>
      </p>
    </section>
  </main>

  <script src="/shared/auth.js?v=3"></script>
  <script src="/shared/motion.js"></script>
  <script src="/shared/nav.js"></script>
  <script src="/static/activities_new.js"></script>
</body>
</html>
```

- [ ] **Step 5: 创建 `webapp/static/activities_new.js`**

```javascript
(function () {
  const msgEl = document.getElementById("msg");
  const formSection = document.getElementById("createForm");
  const okSection = document.getElementById("createOk");

  function showMsg(text, ok) {
    msgEl.textContent = text;
    msgEl.className = "msg " + (ok ? "ok" : "err");
  }

  // 匹配必填截止、限时仅接龙显示
  document.querySelectorAll("input[name=actType]").forEach(function (r) {
    r.addEventListener("change", function () {
      const isMatch = document.querySelector("input[name=actType]:checked").value === "match";
      document.getElementById("deadlineMust").hidden = !isMatch;
      document.getElementById("hoursRow").style.display = isMatch ? "none" : "";
    });
  });

  function toServerTime(localValue) {
    // datetime-local "2026-08-30T20:00" → "2026-08-30 20:00"；空值原样返回
    return localValue ? localValue.replace("T", " ") : "";
  }

  document.getElementById("submitBtn").addEventListener("click", async function () {
    if (!GalleryAuth.isLoggedIn()) { showMsg("请先登录", false); return; }
    const type = document.querySelector("input[name=actType]:checked").value;
    const title = document.getElementById("title").value.trim();
    if (!title) { showMsg("请填写标题", false); return; }
    const deadline = toServerTime(document.getElementById("deadline").value);
    if (type === "match" && !deadline) { showMsg("匹配活动必须设定截止时间", false); return; }
    const body = { type: type, title: title, deadline: deadline || null };
    const desc = document.getElementById("description").value.trim();
    if (desc) body.description = desc;
    const signup = toServerTime(document.getElementById("signupDeadline").value);
    if (signup) body.signup_deadline = signup;
    if (type === "relay") body.hours_per_user = Number(document.getElementById("hours").value) || 48;
    this.disabled = true;
    showMsg("提交中…", true);
    try {
      const res = await fetch("/api/activities", {
        method: "POST", headers: GalleryAuth.headers(),
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { showMsg(data.detail || "创建失败", false); return; }
      document.getElementById("announceBox").textContent = data.announce;
      document.getElementById("manageLink").href = "/activities/" + data.id + "/manage";
      formSection.hidden = true;
      okSection.hidden = false;
    } catch {
      showMsg("网络错误，请重试", false);
    } finally {
      this.disabled = false;
    }
  });

  document.getElementById("copyBtn").addEventListener("click", async function () {
    const text = document.getElementById("announceBox").textContent;
    const copyMsg = document.getElementById("copyMsg");
    try {
      await navigator.clipboard.writeText(text);
      copyMsg.textContent = "已复制";
      copyMsg.className = "msg ok";
    } catch {
      copyMsg.textContent = "复制失败，请手动选择文本复制";
      copyMsg.className = "msg err";
    }
  });

  GalleryAuth.renderAuth(document.getElementById("authArea"));
})();
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python test/scripts/check_activities_api.py`
Expected: `ALL PASS`。

- [ ] **Step 7: 手动验证页面**

Run: `python -m webapp` 后浏览器访问 `http://127.0.0.1:8765/activities/new`：
登录 → 选"接龙"填标题提交 → 看到公告文案与复制按钮 → 复制公告 → 点"前往管理页"（此时 404 属预期，Task 3 实现）；再建"匹配"不填截止 → 前端拦截提示；未登录直接访问 → 302 到 /login。验证完删掉测试活动（进 SQLite 或等 Task 3 的取消按钮）。

- [ ] **Step 8: spec + 提交**

`specs/web-gallery.md` §静态页面表（`activities` 行附近）加一行：

```
| `activities` | `/activities/new` 活动发起页（类型/标题/描述/每人限时/报名截止/截止；匹配必填截止；成功后展示可复制群公告文案）；登录门控 |
```

```bash
git add webapp/activities/app.py webapp/static/activities_new.html webapp/static/activities_new.js test/scripts/check_activities_api.py specs/web-gallery.md
git commit -m "feat(活动): Web 端活动发起页"
```

---

### Task 3: 活动管理页面（仅创建人）

**Files:**
- Modify: `webapp/activities/app.py`（加 `GET /activities/{activity_id}/manage` 页面路由）
- Create: `webapp/static/activities_manage.html`
- Create: `webapp/static/activities_manage.js`
- Modify: `test/scripts/check_activities_api.py`（追加断言）
- Modify: `specs/web-gallery.md`（静态页面表加一行）

**Interfaces:**
- Consumes: Task 1 全部 API；`GET /api/activities/{id}`（已存在，公开，返回含 `created_by/members/status/type/hours_per_user/signup_deadline/deadline/description/title`）；`GalleryAuth`。
- Produces: 页面路由 `GET /activities/{activity_id}/manage`（Task 2 创建成功页与 Task 4 列表入口链接到此）。

- [ ] **Step 1: 追加失败的页面路由断言**

`test/scripts/check_activities_api.py` 页面路由段追加：

```python
r = client.get(f"/activities/{rid}/manage", headers=OH, follow_redirects=False)
check("管理页 200", r.status_code == 200 and "text/html" in r.headers.get("content-type", ""))
r = client.get("/activities/99999/manage", headers=OH)
check("管理页不存在 404", r.status_code == 404)
```

- [ ] **Step 2: 运行确认失败**

Run: `python test/scripts/check_activities_api.py`
Expected: `管理页 200` FAIL（404）。

- [ ] **Step 3: 加页面路由**

`webapp/activities/app.py` 中 `activity_detail_page` 之前插入：

```python
@router.get("/activities/{activity_id}/manage")
def activity_manage_page(activity_id: int):
    db = DbManager()
    if db.activity.get_activity(activity_id) is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    page = STATIC_DIR / "activities_manage.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)
```

- [ ] **Step 4: 创建 `webapp/static/activities_manage.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>活动管理</title>
  <link rel="stylesheet" href="/shared/base.css" />
  <link rel="stylesheet" href="/shared/motion.css" />
  <link rel="stylesheet" href="/shared/profile.css" />
  <style>
    .form-card { background: var(--paper-card); border: 1px solid var(--rule); border-radius: 10px; padding: 16px; max-width: 640px; margin: 0 auto 16px; }
    .form-row { margin-bottom: 14px; display: flex; flex-direction: column; gap: 6px; }
    .form-row > label { font-size: 14px; color: var(--ink); }
    .form-row input[type=text], .form-row input[type=number], .form-row input[type=datetime-local], .form-row textarea {
      padding: 8px 10px; border: 1px solid var(--rule); border-radius: 8px; font-size: 14px;
      background: transparent; color: inherit; font-family: inherit;
    }
    .btn-primary { padding: 9px 18px; border: none; border-radius: 8px; background: var(--accent); color: #fff; font-size: 14px; cursor: pointer; }
    .btn-danger { padding: 9px 18px; border: none; border-radius: 8px; background: var(--red); color: #fff; font-size: 14px; cursor: pointer; }
    .btn-ghost { padding: 9px 18px; border: 1px solid var(--rule); border-radius: 8px; background: transparent; color: inherit; font-size: 14px; cursor: pointer; text-decoration: none; display: inline-block; }
    .btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px; }
    .announce-box { white-space: pre-wrap; background: var(--paper-card); border: 1px dashed var(--rule); border-radius: 8px; padding: 12px; font-size: 14px; margin: 12px 0; }
    .msg { font-size: 13px; margin-top: 8px; min-height: 18px; }
    .msg.err { color: var(--red); }
    .msg.ok { color: var(--gold); }
    .muted { color: var(--ink-soft); font-size: 13px; }
    .member-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .member-chip { background: var(--paper-card); border-radius: 999px; padding: 2px 10px; font-size: 12px; color: var(--ink-soft); }
    .status-badge { font-size: 12px; padding: 1px 8px; border-radius: 999px; whitespace: nowrap; }
    .badge-open { background: var(--accent-soft); color: var(--accent-ink); }
    .badge-running { background: var(--paper); color: var(--accent-ink); }
    .badge-done { background: var(--rule); color: var(--ink-soft); }
    .badge-cancelled { background: var(--paper); color: var(--red); }
  </style>
</head>
<body>
  <header class="toolbar profile-toolbar">
    <div class="auth-area" id="authArea"></div>
  </header>

  <main class="profile-main">
    <section id="denyCard" class="form-card" hidden>
      <h2 id="denyTitle">仅活动创建人可管理</h2>
      <p class="muted">你不是本活动的创建人。</p>
      <p><a class="btn-ghost" id="denyBack" href="/activities">返回活动列表</a></p>
    </section>

    <section id="manageCard" class="form-card" hidden>
      <h2>活动管理 <span id="statusBadge"></span></h2>
      <div class="form-row">
        <label for="mTitle">标题</label>
        <input type="text" id="mTitle" maxlength="100" />
      </div>
      <div class="form-row">
        <label for="mDesc">描述</label>
        <textarea id="mDesc" rows="3" maxlength="500"></textarea>
      </div>
      <div class="form-row" id="mHoursRow">
        <label for="mHours">每人限时（小时）</label>
        <input type="number" id="mHours" min="0.5" step="0.5" />
      </div>
      <div class="form-row" id="mSignupRow">
        <label for="mSignup">报名截止</label>
        <input type="datetime-local" id="mSignup" />
      </div>
      <div class="form-row">
        <label for="mDeadline">截止时间</label>
        <input type="datetime-local" id="mDeadline" />
      </div>
      <div class="btn-row">
        <button class="btn-primary" id="saveBtn">保存修改</button>
      </div>
      <p class="msg" id="msg"></p>

      <h3 style="font-size:15px">报名成员（<span id="memberCount">0</span> 人）</h3>
      <div class="member-list" id="memberList"></div>
      <p class="muted">报名在 QQ 群内回复「/活动 加入」。</p>

      <div id="announceBlock" hidden>
        <h3 style="font-size:15px">群公告文案</h3>
        <div class="announce-box" id="announceBox"></div>
        <button class="btn-ghost" id="copyBtn">复制</button>
      </div>

      <div class="btn-row" id="actionRow"></div>
    </section>
  </main>

  <script src="/shared/auth.js?v=3"></script>
  <script src="/shared/motion.js"></script>
  <script src="/shared/nav.js"></script>
  <script src="/static/activities_manage.js"></script>
</body>
</html>
```

- [ ] **Step 5: 创建 `webapp/static/activities_manage.js`**

```javascript
(function () {
  const TYPE_LABEL = { relay: "接龙", match: "匹配下家" };
  const STATUS_LABEL = { open: "报名中", running: "进行中", finished: "已结束", cancelled: "已取消" };
  const MEMBER_STATUS_ICON = { done: "✓", skipped: "跳过", missed: "未交", left: "退出", pending: "…" };
  const SUPER_USER_IDS = ["1057613133"];

  const id = location.pathname.split("/")[2];
  const msgEl = document.getElementById("msg");
  let actCache = null;

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function showMsg(text, ok) {
    msgEl.textContent = text;
    msgEl.className = "msg " + (ok ? "ok" : "err");
  }

  function toLocalTime(serverValue) {
    // "2099-01-01 20:00:00" → "2099-01-01T20:00"；空返回 ""
    return serverValue ? serverValue.slice(0, 16).replace(" ", "T") : "";
  }

  function toServerTime(localValue) {
    return localValue ? localValue.replace("T", " ") : "";
  }

  async function api(path, method, body) {
    const res = await fetch(path, {
      method: method, headers: GalleryAuth.headers(),
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "操作失败");
    return data;
  }

  function isOwner(act) {
    const session = GalleryAuth.load();
    const uid = session && session.user_id;
    return String(act.created_by) === String(uid) || SUPER_USER_IDS.includes(String(uid));
  }

  function renderActions(act) {
    const row = document.getElementById("actionRow");
    row.innerHTML = "";
    const mk = function (text, cls, handler, hint) {
      const btn = document.createElement("button");
      btn.className = cls; btn.textContent = text;
      btn.addEventListener("click", handler);
      row.appendChild(btn);
      if (hint) {
        const p = document.createElement("p");
        p.className = "muted"; p.textContent = hint;
        row.appendChild(p);
      }
    };
    if (act.status === "open") {
      mk("开始活动", "btn-primary", function () {
        if (!confirm("开始后系统约 1 分钟内通知所有成员，确认开始？")) return;
        api("/api/activities/" + id + "/start", "POST").then(
          d => showMsg(d.note || "已请求开始", true), e => showMsg(e.message, false));
      }, "约 1 分钟内生效（等待机器人心跳）");
      mk("取消活动", "btn-danger", function () {
        if (!confirm("取消后无法恢复，确认取消？")) return;
        api("/api/activities/" + id + "/cancel", "POST").then(
          () => { showMsg("已取消", true); load(); }, e => showMsg(e.message, false));
      });
    } else if (act.status === "running") {
      mk("提前结束", "btn-danger", function () {
        if (!confirm("未提交成员将记为未交并归档，约 1 分钟生效，确认结束？")) return;
        api("/api/activities/" + id + "/finish", "POST").then(
          d => showMsg(d.note || "已请求结束", true), e => showMsg(e.message, false));
      }, "约 1 分钟内生效（等待机器人心跳）");
    }
  }

  function render(act) {
    actCache = act;
    const badge = document.getElementById("statusBadge");
    const cls = act.status === "open" ? "badge-open" : act.status === "running" ? "badge-running"
      : act.status === "finished" ? "badge-done" : "badge-cancelled";
    badge.innerHTML = '<span class="status-badge ' + cls + '">' + (STATUS_LABEL[act.status] || act.status) + "</span>";

    const editable = act.status === "open" || act.status === "running";
    ["mTitle", "mDesc", "mDeadline"].forEach(function (elId) {
      document.getElementById(elId).disabled = !editable;
    });
    document.getElementById("mHoursRow").style.display = act.type === "relay" ? "" : "none";
    document.getElementById("mSignupRow").style.display = act.status === "open" ? "" : "none";
    document.getElementById("mHours").disabled = act.status !== "open";
    document.getElementById("mSignup").disabled = act.status !== "open";
    document.getElementById("saveBtn").disabled = !editable;

    document.getElementById("mTitle").value = act.title || "";
    document.getElementById("mDesc").value = act.description || "";
    document.getElementById("mHours").value = act.hours_per_user || 48;
    document.getElementById("mSignup").value = toLocalTime(act.signup_deadline);
    document.getElementById("mDeadline").value = toLocalTime(act.deadline);

    document.getElementById("memberCount").textContent = act.members.length;
    document.getElementById("memberList").innerHTML = act.members.map(function (m) {
      return '<span class="member-chip">' + (m.seq || "·") + ". " + escapeHtml(m.nickname)
        + " " + (MEMBER_STATUS_ICON[m.status] || "") + "</span>";
    }).join("");

    document.getElementById("announceBlock").hidden = act.status !== "open";
    renderActions(act);
  }

  async function loadAnnounce() {
    try {
      const d = await api("/api/activities/" + id + "/announce", "GET");
      document.getElementById("announceBox").textContent = d.announce;
    } catch { /* 非创建人拿不到，隐藏块即可 */ }
  }

  async function load() {
    if (!GalleryAuth.isLoggedIn()) {
      document.getElementById("denyTitle").textContent = "请先登录";
      document.getElementById("denyCard").hidden = false;
      return;
    }
    try {
      const res = await fetch("/api/activities/" + id);
      if (!res.ok) {
        document.getElementById("denyTitle").textContent = "活动不存在";
        document.getElementById("denyCard").hidden = false;
        return;
      }
      const act = await res.json();
      if (!isOwner(act)) {
        document.getElementById("denyCard").hidden = false;
        return;
      }
      document.getElementById("manageCard").hidden = false;
      render(act);
      if (act.status === "open") await loadAnnounce();
    } catch {
      showMsg("加载失败", false);
    }
  }

  document.getElementById("saveBtn").addEventListener("click", async function () {
    const body = { title: document.getElementById("mTitle").value.trim() };
    if (!body.title) { showMsg("标题不能为空", false); return; }
    const desc = document.getElementById("mDesc").value.trim();
    if (desc) body.description = desc;
    const dl = toServerTime(document.getElementById("mDeadline").value);
    if (dl) body.deadline = dl;
    if (actCache && actCache.status === "open") {
      const su = toServerTime(document.getElementById("mSignup").value);
      if (su) body.signup_deadline = su;
      if (actCache.type === "relay") body.hours_per_user = Number(document.getElementById("mHours").value) || 48;
    }
    try {
      await api("/api/activities/" + id, "PATCH", body);
      showMsg("已保存", true);
      await load();
    } catch (e) { showMsg(e.message, false); }
  });

  document.getElementById("copyBtn").addEventListener("click", async function () {
    try {
      await navigator.clipboard.writeText(document.getElementById("announceBox").textContent);
      showMsg("已复制", true);
    } catch { showMsg("复制失败，请手动选择文本", false); }
  });

  GalleryAuth.renderAuth(document.getElementById("authArea"));
  load();
  setInterval(load, 15000); // 开始终止动作后观察状态跳转（bot 心跳 ≤60s 生效）
})();
```

说明：`SUPER_USER_IDS` 前端硬编码仅用于决定是否**显示**管理 UI，真正的权限在服务端 `_require_owner`；若 `SUPER_USER` 变更需同步（与 `core/base.py` 一致）。登录但非创建人时显示拒绝卡片（公开详情接口不泄露管理能力）。

- [ ] **Step 6: 运行测试确认通过**

Run: `python test/scripts/check_activities_api.py`
Expected: `ALL PASS`。

- [ ] **Step 7: 手动验证页面**

`python -m webapp` 起服务：
1. 用 Task 2 手动验证创建的活动进管理页（创建人账号）→ 编辑字段保存 → 改群公告块文案随编辑刷新。
2. 非创建人账号访问 `/activities/{id}/manage` → 拒绝卡片。
3. 群里 `/活动 加入` 拉人后点"开始活动" → ~1 分钟内 QQ 群收到开始公告、接龙第一棒收到私聊（bot 进程需在跑）→ 管理页 15s 轮询自动变为"进行中"、操作区变"提前结束"。
4. running 态确认：报名截止/限时输入框隐藏或禁用，改截止可保存。
5. 点"提前结束" → ~1 分钟内群收到结束归档公告 → 页面变"已结束"只读。

- [ ] **Step 8: spec + 提交**

`specs/web-gallery.md` §静态页面表加一行：

```
| `activities` | `/activities/{activity_id}/manage` 活动管理页（仅创建人/超管，其余显示拒绝卡片）：open 编辑标题/描述/限时/报名截止/截止 + 开始/取消，running 编辑标题/描述/截止 + 提前结束，15s 轮询状态；open 常驻群公告文案复制；开始/结束借道心跳约 1 分钟生效 |
```

```bash
git add webapp/activities/app.py webapp/static/activities_manage.html webapp/static/activities_manage.js test/scripts/check_activities_api.py specs/web-gallery.md
git commit -m "feat(活动): Web 端活动管理页（仅创建人）"
```

---

### Task 4: 列表/详情入口接线 + 版本收尾

**Files:**
- Modify: `webapp/static/activities.html`（"进行中的活动"区块标题旁加发起按钮）
- Modify: `webapp/static/activities.js`（进行中卡片对创建人加"管理"链接）
- Modify: `webapp/static/activities_detail.js`（详情页对创建人加"管理"链接）
- Modify: `CHANGELOG.md`、`core/config.py`（BOTERO_VERSION）、`roadmap.md`
- Modify: `specs/web-gallery.md`（activities 页面行补充入口描述）

**Interfaces:**
- Consumes: Task 1 的列表 `created_by` 字段；Task 2/3 的页面路由。

- [ ] **Step 1: 列表页发起按钮**

`webapp/static/activities.html` 中：

```html
    <section class="activity-section" id="activeSection">
      <h2>进行中的活动</h2>
```

改为：

```html
    <section class="activity-section" id="activeSection">
      <div style="display:flex; align-items:center; justify-content:space-between">
        <h2 style="margin:0">进行中的活动</h2>
        <a class="member-chip" href="/activities/new" style="text-decoration:none">＋ 发起活动</a>
      </div>
```

（`member-chip` 胶囊样式复用；内联样式与该文件现有轻量做法一致。）

- [ ] **Step 2: 进行中卡片加管理入口**

`webapp/static/activities.js::loadActiveActivities` 中：

```javascript
      <div class="member-list">
```

之前插入一行（`active.map` 模板内）：

```javascript
      ${a.created_by != null && String(a.created_by) === String(myUid)
        ? `<a class="member-chip member-me" href="/activities/${a.id}/manage" style="text-decoration:none">⚙ 管理</a>`
        : ""}
```

- [ ] **Step 3: 详情页加管理入口**

`webapp/static/activities_detail.js::loadDetail` 中构建 `rows` 后（`const isRunning = act.status === "running";` 行附近）追加：

```javascript
  const isOwner = session && myUid && String(act.created_by) === String(myUid);
```

并在标题行（`infoRow("标题", ...)` 的值内）追加管理链接——把标题行改为：

```javascript
    infoRow("标题", `<strong>${escapeHtml(act.title)}</strong>${statusBadge(act.status)}`
      + (isOwner && (act.status === "open" || act.status === "running")
        ? ` <a href="/activities/${act.id}/manage">管理</a>` : "")),
```

（`session`/`myUid` 变量在该函数内已存在，直接复用。）

- [ ] **Step 4: 手动验证入口**

刷新 `/activities`：创建人视角进行中卡片带"⚙ 管理"；非创建人无。详情页同理。发起按钮跳发起页。

- [ ] **Step 5: 全量回归**

Run: `pytest`
Expected: 全部通过。

- [ ] **Step 6: CHANGELOG + 版本 + roadmap + spec 收尾**

`core/config.py`：`BOTERO_VERSION` minor +1（如 `1.26.0`，以当前文件实际值为准递增）。
`CHANGELOG.md` 顶部新增节（日期为实际提交日）：

```markdown
## [1.26.0] - 2026-08-30

### 新增

- 活动：Web 端「发起活动」页（`/activities/new`），创建成功生成可复制群公告文案
- 活动：Web 端活动管理页（`/activities/{id}/manage`，仅创建人/超管）：报名期编辑参数、开始（借道机器人心跳约 1 分钟生效并通知全员）、取消；进行期延长截止、提前结束
- 活动：活动列表/详情页对创建人显示管理入口
```

`roadmap.md` 里程碑区加一行（格式照现有行）：

```markdown
- 活动创建与管理搬到 Web 端（发起页 + 创建人管理页，通知借道心跳）
```

`specs/web-gallery.md` §静态页面 `activities` 行的描述末尾追加"；创建人卡片/详情带管理入口，列表页带发起入口"。

- [ ] **Step 7: 提交**

```bash
git add webapp/static/activities.html webapp/static/activities.js webapp/static/activities_detail.js specs/web-gallery.md
git commit -m "feat(活动): 列表与详情页接入活动管理入口"
git add CHANGELOG.md core/config.py roadmap.md
git commit -m "chore(版本): 1.26.0 Web 端活动创建与管理"
```

---

## Self-Review 记录

- **Spec 覆盖**：设计决策 1（C+B1）→ Task 1 动作端点 + Task 2 公告文案；决策 2（编辑范围）→ Task 1 PATCH 白名单 + Task 3 表单禁用；决策 3（固定群）→ `DEFAULT_GROUP_ID`；决策 4（不做）→ 无对应任务；决策 5（权限）→ `_require_owner` + 服务端测试。无缺口。
- **占位符**：无 TBD/“适当处理”；全部代码块可直接落地。唯二运行时确认项（BOTERO_VERSION 当前值、提交日期）已在步骤内注明"以实际为准"。
- **类型一致性**：`_parse_future_deadline(raw,label)->str|None`、`_require_owner(act,user_id)`、`_announcement(act)->str` 在 Task 1 定义、Task 2/3 仅经 HTTP 消费；前端 `GalleryAuth.headers()/load()/isLoggedIn()/renderAuth()` 均为 `webapp/static/activities.js` 已验证存在的 API。
- **路由顺序**：`/activities/new` 与 `/activities/{id}/manage` 均要求插在 `activity_detail_page` 之前，已在 Task 2/3 步骤中显式标注。
