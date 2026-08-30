"""活动子应用：接龙与匹配活动的作品归档。"""

from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from core.base import SUPER_USER
from core.config import ACTIVITY_ROOT
from core.context import DEFAULT_GROUP_ID
from core.database_manager import DbManager
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

router = APIRouter()

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


@router.get("/api/activities")
def api_activities():
    db = DbManager()
    return {"items": db.activity.list_activities()}


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


@router.get("/api/me/activities")
def api_my_activities(user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    return {"items": db.activity.get_my_activities(user_id)}


@router.get("/api/activities/{activity_id}")
def api_activity_detail(activity_id: int):
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    for m in act["members"]:
        m["images"] = [
            f"/archive/{activity_id}/media/{name}" for name in m.get("images", [])
        ]
    return act


def _assert_under_activity_root(path: Path) -> None:
    try:
        path.resolve().relative_to(ACTIVITY_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="禁止访问") from exc


@router.get("/archive/{activity_id}/media/{filename}")
def serve_activity_media(activity_id: int, filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法路径")
    path = ACTIVITY_ROOT / str(activity_id) / "imgs" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    _assert_under_activity_root(path)
    return FileResponse(path)


@router.get("/activities")
def activities_page():
    page = STATIC_DIR / "activities.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)


@router.get("/activities/{activity_id}")
def activity_detail_page(activity_id: int):
    db = DbManager()
    if db.activity.get_activity(activity_id) is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    page = STATIC_DIR / "activities_detail.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少活动详情页")
    return FileResponse(page)
