"""社区时间线模块（Event Server）：收事件 / 撤回 / 查询渲染 + entries 数据源。

协议见 specs/timeline-protocol.md。Event Server 不解析 data、不理解业务：
只做协议校验、存储（幂等）、按协议渲染。
"""

import json
import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.config import TIMELINE_TOKEN
from core.database_manager import DbManager
from core.onebot_client import resolve_avatar_url, resolve_display_name
from core.web.auth_deps import get_current_user_id

router = APIRouter()

TIMELINE_DIR = Path(__file__).resolve().parent

_PLACEHOLDER_RE = re.compile(r"\{id:(\d+)\}")
_PAGE_SIZE_DEFAULT = 50
_PAGE_SIZE_MAX = 100
UNBOUND_LABEL = "未绑定玩家"


# —— 事件输入模型 ——
class ActorIn(BaseModel):
    id: str = Field(min_length=1)
    qq: str | None = None


class TargetIn(BaseModel):
    type: str | None = "url"
    url: str | None = None


class DisplayIn(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None


class EventIn(BaseModel):
    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    actor: ActorIn
    target: TargetIn | None = None
    display: DisplayIn
    data: Any = None
    dedup_key: str | None = None


def _require_event_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """系统间事件令牌鉴权（与用户登录密钥不同）。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少事件令牌")
    if authorization[7:].strip() != TIMELINE_TOKEN:
        raise HTTPException(status_code=401, detail="事件令牌无效")


def _validate_event(body: EventIn) -> None:
    if not body.id.startswith(f"{body.source}:"):
        raise HTTPException(status_code=422, detail="id 必须以 <source>: 开头")
    if body.actor.qq is not None:
        try:
            body.actor.qq = str(int(body.actor.qq))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="actor.qq 必须是 QQ 号")
    if body.target and body.target.url:
        if not (
            body.target.url.startswith(("http://", "https://"))
            or body.target.url.startswith("/")
        ):
            raise HTTPException(
                status_code=422,
                detail="target.url 必须是 http(s) 链接或站内相对路径（以 / 开头）",
            )


def _loads(raw: str | None):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


# —— Event Server 端点 ——
@router.post("/api/timeline/events")
def post_event(
    body: EventIn,
    _: None = Depends(_require_event_token),
):
    _validate_event(body)
    db = DbManager()
    inserted = db.timeline.insert(
        event_id=body.id,
        source=body.source,
        actor_id=body.actor.id,
        actor_qq=body.actor.qq,
        target_type=(body.target.type if body.target else None),
        target_url=(body.target.url if body.target else None),
        title=body.display.title,
        description=body.display.description,
        data=json.dumps(body.data, ensure_ascii=False) if body.data is not None else None,
        dedup_key=body.dedup_key,
    )
    return {"ok": True, "inserted": inserted}


@router.delete("/api/timeline/events/by-key")
def delete_event_by_key(
    source: str = Query(...),
    key: str = Query(...),
    _: None = Depends(_require_event_token),
):
    db = DbManager()
    deleted = db.timeline.delete_by_key(source, key)
    return {"ok": True, "deleted": deleted}


@router.delete("/api/timeline/events/{event_id}")
def delete_event(
    event_id: str,
    _: None = Depends(_require_event_token),
):
    db = DbManager()
    deleted = db.timeline.delete_by_id(event_id)
    return {"ok": True, "deleted": deleted}


@router.get("/api/timeline")
def timeline_feed(
    _user_id: Annotated[str, Depends(get_current_user_id)],
    cursor: str | None = Query(default=None),
    limit: int = Query(default=_PAGE_SIZE_DEFAULT, ge=1, le=_PAGE_SIZE_MAX),
):
    """时间线查询（登录可见）。服务端解析占位符与昵称头像。"""
    cur = None
    if cursor:
        if "|" not in cursor:
            raise HTTPException(status_code=422, detail="游标格式错误")
        received_at, event_id = cursor.rsplit("|", 1)
        cur = (received_at, event_id)

    db = DbManager()
    rows = db.timeline.page(cur, limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]

    events = []
    users: dict[str, dict] = {}
    for row in rows:
        (eid, source, received_at, actor_id, actor_qq, target_type, target_url,
         title, description, data_raw, _dedup_key) = row
        if actor_qq:
            name, avatar = resolve_display_name(actor_qq), resolve_avatar_url(actor_qq)
        else:
            name, avatar = UNBOUND_LABEL, ""
        users.setdefault(str(actor_qq or actor_id), {"name": name, "avatar": avatar})
        events.append({
            "id": eid,
            "source": source,
            "received_at": received_at,
            "actor": {
                "id": actor_id,
                "qq": actor_qq,
                "display_name": name,
                "avatar_url": avatar,
            },
            "target": ({"type": target_type, "url": target_url} if target_url else None),
            "title": title,
            "description": description,
            "data": _loads(data_raw),
        })
        for text_field in (title, description or ""):
            for m in _PLACEHOLDER_RE.finditer(text_field):
                uid = m.group(1)
                if uid not in users:
                    users[uid] = {
                        "name": resolve_display_name(uid),
                        "avatar": resolve_avatar_url(uid),
                    }

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = f"{last[2]}|{last[0]}"
    return {"events": events, "users": users, "next_cursor": next_cursor}


# —— 侧边栏导航数据源（原导航主页 entries.json，唯一入口维护点）——
@router.get("/entries.json")
def entries():
    return FileResponse(TIMELINE_DIR / "entries.json")
