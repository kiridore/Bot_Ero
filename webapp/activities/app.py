"""活动子应用：接龙与匹配活动的作品归档。"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from core import config
from core.base import SUPER_USER
from core.config import ACTIVITY_ROOT
from core.context import DEFAULT_GROUP_ID
from core.database_manager import DbManager
from core.onebot_client import resolve_display_name
from core.tiptap import tiptap_to_plain
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
    kind = {"relay": "接龙", "match": "匹配下家", "collect": "征集"}.get(act["type"], act["type"])
    lines = [f"【活动发起】{kind}「{act['title']}」（#{act['id']}）"]
    if act["type"] == "relay":
        lines.append(f"每人限时 {_format_duration(act['hours_per_user'] or 48)}")
    if act.get("deadline"):
        lines.append(f"截止：{act['deadline']}")
    if act.get("description"):
        lines.append(f"描述：{tiptap_to_plain(act['description'])}")
    if act.get("signup_deadline"):
        lines.append(f"报名截止：{act['signup_deadline']}（到点自动开始）")
    lines.append("回复 /活动 加入 报名，报名完成后由创建人 /活动 开始")
    return "\n".join(lines)


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


def _save_submission_images(activity_id: int, seq: int, files: list[tuple[bytes, str | None]], start: int = 1) -> list[str]:
    """存 ACTIVITY_ROOT/<id>/imgs/<seq>-<n>.<ext>（web 命名；bot 为 img_<seq>_<n><ext>，互不冲突）；
    增量追加：命名从 start 续编（start = 现有图片最大序号 + 1），不覆盖旧文件；限制同打卡。"""
    if len(files) > config.CHECKIN_MAX_IMAGES:
        raise ValueError(f"单次最多上传 {config.CHECKIN_MAX_IMAGES} 张图片")
    folder = ACTIVITY_ROOT / str(activity_id) / "imgs"
    saved = []
    for n, (data, mime_raw) in enumerate(files, start):
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


_WEB_IMG_RE = re.compile(r"^(\d+)-(\d+)\.\w+$")


def _next_img_number(seq: int, images: list[str]) -> int:
    """现有 web 命名 {seq}-{n}.ext 的最大 n + 1（bot 命名 img_* 不参与，前缀不同天然不冲突）。"""
    max_n = 0
    for name in images:
        m = _WEB_IMG_RE.match(name)
        if m and int(m.group(1)) == seq:
            max_n = max(max_n, int(m.group(2)))
    return max_n + 1


def _delete_submission_images(activity_id: int, names: list[str]) -> None:
    """删除已落盘图片文件；name 来自成员 images 列表（服务端生成），仍做路径穿越防护。"""
    folder = ACTIVITY_ROOT / str(activity_id) / "imgs"
    for name in names:
        try:
            p = (folder / name).resolve()
            p.relative_to(ACTIVITY_ROOT.resolve())
        except ValueError:
            continue
        p.unlink(missing_ok=True)


class ActivityCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(pattern="^(relay|match|collect)$")
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=4000)  # TipTap JSON 字符串
    hours_per_user: float = Field(default=48.0, gt=0)
    signup_deadline: str | None = None
    deadline: str | None = None


class ActivityEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=4000)  # TipTap JSON 字符串
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
    if body.type in ("match", "collect") and not body.deadline:
        raise HTTPException(status_code=400, detail="匹配与征集活动必须设定截止时间")
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="标题不能为空")
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
        if not body.title.strip():
            raise HTTPException(status_code=400, detail="标题不能为空")
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


@router.post("/api/activities/{activity_id}/join")
def api_activity_join(activity_id: int,
                      user_id: Annotated[str, Depends(get_current_user_id)]):
    """加入报名中的活动（与 bot /活动 加入 同语义：open 期、重复加入拒、昵称经 OneBot 解析）。"""
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    if act["status"] != "open":
        raise HTTPException(status_code=409, detail="活动不在报名中，无法加入")
    if any(str(m["user_id"]) == user_id for m in act["members"]):
        raise HTTPException(status_code=409, detail="你已加入该活动")
    db.activity.add_member(activity_id, user_id, resolve_display_name(user_id) or user_id)
    return {"ok": True, "members": len(act["members"]) + 1}


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
    if act["type"] == "collect" and len(members) < 1:
        raise HTTPException(status_code=409, detail="征集活动至少需要 1 人报名")
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
    removed: list[str] = Form(default=[]),
):
    """增量提交：content 覆盖文本，files 追加到末尾（续编号），removed 从现有列表移除；可任意组合。"""
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    me, reason = _submission_state(user_id, act, act["members"])
    if reason is not None:
        raise HTTPException(status_code=409, detail=_BLOCK_TEXT.get(reason, "无法提交"))
    text = (content or "").strip()
    # get_activity 已把 members[].images json.loads 成 list（见 core/db/activity.py:49）
    current = me.get("images") or []
    if not isinstance(current, list):
        current = []
    if any(name not in current for name in removed):
        raise HTTPException(status_code=400, detail="无效的图片参数")
    payloads = [(await f.read(), f.content_type) for f in (files or [])]
    try:
        # 与 bot 同语义：先全部存盘成功再写库，任一失败整体不生效
        saved = _save_submission_images(
            activity_id, me["seq"], payloads, _next_img_number(me["seq"], current)
        ) if payloads else []
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not text and not saved and not removed:
        raise HTTPException(status_code=400, detail="请附上作品（文字或图片）")
    _delete_submission_images(activity_id, removed)
    images = [n for n in current if n not in removed] + saved
    db.activity.update_member(
        activity_id, user_id, status="done", content=text or None,
        images=json.dumps(images) if images else None, submitted_at=_now())
    return {"ok": True, "updated": me["status"] == "done"}


@router.get("/api/me/activities")
def api_my_activities(user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    return {"items": db.activity.get_my_activities(user_id)}


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


def _assert_under_activity_root(path: Path) -> None:
    try:
        path.resolve().relative_to(ACTIVITY_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="禁止访问") from exc


@router.get("/archive/{activity_id}/media/{filename}")
def serve_activity_media(activity_id: int, filename: str,
                         user_id: Annotated[str, Depends(get_current_user_id)]):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法路径")
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    # 隐私：进行中限「该文件所属序号的成员 / 创建人 / 超管」；结束后归档公开。命名两种：web「{seq}-{n}.ext」/ bot「img_{seq}_{n}.ext」
    if act["status"] != "finished":
        m = re.match(r"^(?:(\d+)-|img_(\d+)_)", filename)
        seq = int(m.group(1) or m.group(2)) if m else None
        allowed = (
            seq is not None
            and any(str(mem["user_id"]) == user_id and mem["seq"] == seq for mem in act["members"])
        ) or str(act["created_by"]) == user_id or int(user_id) in SUPER_USER
        if not allowed:
            raise HTTPException(status_code=403, detail="活动进行中，仅作品本人可查看")
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


@router.get("/activities/new")
def activity_new_page():
    page = STATIC_DIR / "activities_new.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)


@router.get("/activities/{activity_id}/manage")
def activity_manage_page(activity_id: int):
    db = DbManager()
    if db.activity.get_activity(activity_id) is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    page = STATIC_DIR / "activities_manage.html"
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
