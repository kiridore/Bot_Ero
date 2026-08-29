"""社区时间线模块（Event Server）：收事件 / 撤回 / 查询渲染 + entries 数据源。

协议见 specs/timeline-protocol.md。Event Server 不解析 data、不理解业务：
只做协议校验、存储（幂等）、按协议渲染。
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.config import TIMELINE_TOKEN
from core.database_manager import DbManager
from core import user_settings
from core.onebot_client import resolve_avatar_url, resolve_display_name
from core.web.auth_deps import get_current_user_id

router = APIRouter()

TIMELINE_DIR = Path(__file__).resolve().parent

_PLACEHOLDER_RE = re.compile(r"\{id:(\d+)\}")
_PAGE_SIZE_DEFAULT = 50
_PAGE_SIZE_MAX = 100
_RESOLVE_WORKERS = 16  # 昵称/头像并发解析线程数（OneBot HTTP 局域网，16 并发安全）
UNBOUND_LABEL = "未绑定玩家"
_FEED_FETCH_PAGES = 5  # ponytail: 跨隐藏事件连续带的补页上限，5×(limit+1) 条连续隐藏后该页少给，下轮翻页补上


# —— 打卡隐私读侧过滤（作者 JSON 设置 × 事件 data.private，历史无标记=公开）——

def _vis_full(row: tuple):
    """page()/page_unread_after() 12 列行 → (eid, source, actor_key, data_raw)。"""
    return row[1], row[2], str(row[5] or row[4]), row[10]


def _vis_light(row: tuple):
    """rows_unread_after() 6 列轻量行 → 同上。"""
    return row[1], row[2], str(row[4] or row[3]), row[5]


def _visibility_ctx(entries) -> dict:
    """计算隐藏事件 id 集与需模糊图片的作者集。每作者每页只读一次设置。"""
    hidden: set[str] = set()
    blur_authors: set[str] = set()
    actor_flags: dict[str, tuple[bool, bool]] = {}
    for eid, source, actor_key, data_raw in entries:
        if source != "checkin":
            continue
        if actor_key not in actor_flags:
            actor_flags[actor_key] = (
                user_settings.private_checkin_public(actor_key),
                user_settings.checkin_image_public(actor_key),
            )
        private_public, image_public = actor_flags[actor_key]
        if not image_public:
            blur_authors.add(actor_key)  # 该作者全部打卡图对非作者模糊
        if not private_public:
            data = _loads(data_raw)
            if isinstance(data, dict) and data.get("private"):
                hidden.add(eid)
    return {"hidden": hidden, "blur": blur_authors}


def _visible_entry(entry: tuple, viewer_id, vis: dict) -> bool:
    """隐藏事件仅作者本人可见。"""
    eid, _source, actor_key, _data = entry
    return not (eid in vis["hidden"] and actor_key != str(viewer_id))


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


def _serialize_rows(rows: list[tuple], watermark: int, read_ids: set[str],
                     viewer_id: str | None = None, vis: dict | None = None):
    """两遍组装：收集需解析用户（actor + 占位符）→ 并发解析昵称/头像 → 事件 dict。
    首列 rowid 作为 seq 暴露给客户端（顶部事件锚点）；unread = seq > 水印 且无回执。
    viewer_id/vis 提供时按作者隐私设置处理：被隐藏私聊打卡仅作者自见（self_only），
    模糊作者的打卡图片对非作者改写 blur=1 URL。"""
    need: set[str] = set()
    unbound_keys: set[str] = set()
    for row in rows:
        (_seq, _eid, _source, _received_at, actor_id, actor_qq, _tt, _tu,
         title, description, _data_raw, _dedup_key) = row
        if actor_qq:
            need.add(str(actor_qq))
        else:
            unbound_keys.add(str(actor_id))
        for text_field in (title, description or ""):
            for m in _PLACEHOLDER_RE.finditer(text_field):
                need.add(m.group(1))

    # 并发解析昵称+头像（resolve_* 带 lru_cache；OneBot HTTP 串行是首屏耗时主因）
    users: dict[str, dict] = {}
    if need:
        with ThreadPoolExecutor(max_workers=_RESOLVE_WORKERS) as pool:
            for uid, name, avatar in pool.map(
                lambda uid: (uid, resolve_display_name(uid), resolve_avatar_url(uid)),
                sorted(need),
            ):
                users[uid] = {"name": name, "avatar": avatar}
    for uid in unbound_keys:
        users[uid] = {"name": UNBOUND_LABEL, "avatar": ""}

    events = []
    for row in rows:
        (seq, eid, source, received_at, actor_id, actor_qq, target_type, target_url,
         title, description, data_raw, _dedup_key) = row
        actor_key = str(actor_qq or actor_id)
        if actor_qq:
            name = users[str(actor_qq)]["name"]
            avatar = users[str(actor_qq)]["avatar"]
        else:
            name, avatar = UNBOUND_LABEL, ""
        data = _loads(data_raw)
        self_only = False
        if vis is not None and viewer_id is not None and source == "checkin":
            if eid in vis["hidden"] and actor_key == str(viewer_id):
                self_only = True  # 被隐藏的私聊打卡：作者自见
            if (actor_key in vis["blur"] and actor_key != str(viewer_id)
                    and isinstance(data, dict) and isinstance(data.get("images"), list)):
                data = dict(data)
                data["images"] = [
                    u + ("&" if "?" in u else "?") + "blur=1" for u in data["images"]
                ]
        events.append({
            "seq": seq,
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
            "data": data,
            "unread": seq > watermark and eid not in read_ids,
            **({"self_only": True} if self_only else {}),
        })
    return events, users


@router.get("/api/timeline")
def timeline_feed(
    user_id: Annotated[str, Depends(get_current_user_id)],
    cursor: str | None = Query(default=None),
    limit: int = Query(default=_PAGE_SIZE_DEFAULT, ge=1, le=_PAGE_SIZE_MAX),
):
    """时间线查询（登录可见）。服务端解析占位符与昵称头像（并发，冷缓存首屏提速）。"""
    cur = None
    if cursor:
        if "|" not in cursor:
            raise HTTPException(status_code=422, detail="游标格式错误")
        received_at, event_id = cursor.rsplit("|", 1)
        cur = (received_at, event_id)

    db = DbManager()
    watermark = db.timeline.get_or_init_watermark(user_id)
    # 可见性过滤在 Python 侧（作者设置存 JSON 文件，无法下推 SQL）；
    # 逐页补取直到填满 limit 或取尽（隐藏事件连续带的补页上限见 _FEED_FETCH_PAGES）
    vis_rows: list[tuple] = []
    cur_pos = cur
    has_more = False
    batch: list[tuple] = []
    for _ in range(_FEED_FETCH_PAGES):
        need = limit + 1 - len(vis_rows)
        batch = db.timeline.page(cur_pos, need)
        if not batch:
            has_more = False  # 空页必然取尽；沿用上一轮的 True 会令下方 batch[-1] 对空表取下标（P1）
            break
        vis = _visibility_ctx(_vis_full(r) for r in batch)
        for r in batch:
            if _visible_entry(_vis_full(r), user_id, vis):
                vis_rows.append(r)
        if len(vis_rows) > limit:
            has_more = True
            break
        if len(batch) < need:  # 数据库取尽
            has_more = False
            break
        cur_pos = (batch[-1][3], batch[-1][1])
        has_more = True
    vis_rows = vis_rows[:limit]

    vis = _visibility_ctx(_vis_full(r) for r in vis_rows)
    read_ids = db.timeline.read_event_ids(user_id, [r[1] for r in vis_rows]) if vis_rows else set()
    events, users = _serialize_rows(vis_rows, watermark, read_ids, viewer_id=user_id, vis=vis)

    next_cursor = None
    if has_more:
        last = vis_rows[-1] if vis_rows else batch[-1]  # 全被过滤时用已取到的最后一条作续读游标
        next_cursor = f"{last[3]}|{last[1]}"
    return {"events": events, "users": users, "next_cursor": next_cursor}


@router.get("/api/timeline/poll")
def timeline_poll(
    user_id: Annotated[str, Depends(get_current_user_id)],
    after: int | None = Query(default=None, ge=1),
):
    """轻量轮询：返回比 max(after, 水印) 更新且无回执的事件数（不解析昵称/不返回卡片）。"""
    db = DbManager()
    watermark = db.timeline.get_or_init_watermark(user_id)
    lower = max(after or 0, watermark)
    rows = db.timeline.rows_unread_after(user_id, lower)
    vis = _visibility_ctx(_vis_light(r) for r in rows)
    count = sum(1 for r in rows if _visible_entry(_vis_light(r), user_id, vis))
    return {"count": count}


@router.get("/api/timeline/new")
def timeline_new(
    user_id: Annotated[str, Depends(get_current_user_id)],
    after: int | None = Query(default=None, ge=1),
    limit: int = Query(default=_PAGE_SIZE_DEFAULT, ge=1, le=_PAGE_SIZE_MAX),
):
    """拉取比 max(after, 水印) 更新且无回执的事件。数据库按 rowid ASC 取最老一批
    （避免 >100 条时跳项），响应内倒为 feed 的新→旧顺序；next_after 供客户端循环。"""
    db = DbManager()
    watermark = db.timeline.get_or_init_watermark(user_id)
    lower = max(after or 0, watermark)
    fetched = db.timeline.page_unread_after(user_id, lower, limit + 1)
    has_more = len(fetched) > limit
    fetched = fetched[:limit]
    vis = _visibility_ctx(_vis_full(r) for r in fetched)
    rows = [r for r in fetched if _visible_entry(_vis_full(r), user_id, vis)]

    # page_unread_after 已排除回执，此处全部 unread
    events, users = _serialize_rows(rows, watermark, set(), viewer_id=user_id, vis=vis)
    events.reverse()  # rowid ASC（最老在前）→ feed 新→旧

    # next_after 取自含隐藏行的已消费批次：被过滤的事件对查看者永不返回，直接跨过
    next_after = None
    if has_more and fetched:
        next_after = fetched[-1][0]
    return {"events": events, "users": users, "next_after": next_after}


class ReadEventsIn(BaseModel):
    event_ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/api/timeline/read")
def timeline_read(
    body: ReadEventsIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """上报逐卡已读回执；remaining 为该用户剩余未读事件数。未知/重复/已撤回 id 安全忽略。"""
    db = DbManager()
    remaining = db.timeline.mark_read_events(user_id, body.event_ids)
    return {"ok": True, "remaining": remaining}


# —— 侧边栏导航数据源（原导航主页 entries.json，唯一入口维护点）——
@router.get("/entries.json")
def entries():
    return FileResponse(TIMELINE_DIR / "entries.json")
