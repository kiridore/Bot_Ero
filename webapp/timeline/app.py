"""社区时间线模块（Event Server）：收事件 / 撤回 / 查询渲染 + entries 数据源。

协议见 specs/timeline-protocol.md。Event Server 不解析 data、不理解业务：
只做协议校验、存储（幂等）、按协议渲染。
"""

import json
import re
from urllib.parse import quote, unquote
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

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
    """打卡事件四态可见性上下文：hidden（仅作者自见）/ blur（图 URL 改写）/ text（对非作者剥图）。

    事件粒度：类型 = data.private ? private : group，态取自作者 checkin_display()[类型]，
    同作者两类可各自独立成态；每作者每页只读一次设置。states 为同一遍历产出的
    事件 id → 作者设置原值，供与查看者无关的 checkin_state 使用。"""
    hidden: set[str] = set()
    blur_ids: set[str] = set()
    text_ids: set[str] = set()
    states: dict[str, str] = {}
    actor_states: dict[str, dict[str, str]] = {}
    for eid, source, actor_key, data_raw in entries:
        if source != "checkin":
            continue
        if actor_key not in actor_states:
            actor_states[actor_key] = user_settings.checkin_display(actor_key)
        data = _loads(data_raw)
        is_private = isinstance(data, dict) and bool(data.get("private"))
        state = actor_states[actor_key]["private" if is_private else "group"]
        states[eid] = state
        if state == "hidden":
            hidden.add(eid)
        elif state == "blur":
            blur_ids.add(eid)
        elif state == "text":
            text_ids.add(eid)
    return {"hidden": hidden, "blur": blur_ids, "text": text_ids, "states": states}


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


# —— 事件输出模型 ——
class ActorOut(BaseModel):
    id: str
    qq: str | None = None
    display_name: str
    avatar_url: str


class TargetOut(BaseModel):
    type: str | None = None
    url: str | None = None


class EventOut(BaseModel):
    """self_only/images_hidden 为条件键，由 extra="allow" 透传（无键 ≠ null）。

    checkin_state 显式声明以便生成客户端；非打卡事件无该键——路由用
    response_model_exclude_unset 保持条件键语义（值总是作者设置原值，与查看者无关）。"""

    model_config = ConfigDict(extra="allow")

    seq: int
    id: str
    source: str
    received_at: str
    actor: ActorOut
    target: TargetOut | None = None
    title: str
    description: str | None = None
    data: Any = None
    unread: bool
    checkin_state: str | None = None


class UserOut(BaseModel):
    name: str
    avatar: str


class EventAckOut(BaseModel):
    ok: bool
    inserted: bool


class EventDeletedOut(BaseModel):
    ok: bool
    deleted: bool


class TimelineFeedOut(BaseModel):
    events: list[EventOut]
    users: dict[str, UserOut]
    next_cursor: str | None = None


class TimelinePollOut(BaseModel):
    count: int


class TimelineNewOut(BaseModel):
    events: list[EventOut]
    users: dict[str, UserOut]
    next_after: int | None = None


class ReadOut(BaseModel):
    ok: bool
    remaining: int


# —— 导航数据模型（entries.json 同构）——
class NavLink(BaseModel):
    label: str
    url: str | None = None
    copy_text: str | None = Field(default=None, alias="copy")


class NavEntry(BaseModel):
    name: str
    desc: str
    url: str | None = None
    badge: str | None = None
    span: int | None = None
    links: list[NavLink] | None = None


# —— Event Server 端点 ——
@router.post("/api/timeline/events", response_model=EventAckOut)
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


@router.delete("/api/timeline/events/by-key", response_model=EventDeletedOut)
def delete_event_by_key(
    source: str = Query(...),
    key: str = Query(...),
    _: None = Depends(_require_event_token),
):
    db = DbManager()
    deleted = db.timeline.delete_by_key(source, key)
    return {"ok": True, "deleted": deleted}


@router.delete("/api/timeline/events/{event_id}", response_model=EventDeletedOut)
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
    viewer_id/vis 提供时按作者隐私设置处理：被隐藏打卡仅作者自见（self_only），
    模糊态打卡图片对非作者改写 blur=1 URL，text 态打卡对非作者剥离图片
    并附 images_hidden: true（仅当事件本就含图；无图事件不加标记）。"""
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
        if isinstance(data, dict) and isinstance(data.get("images"), list):
            # 存量事件存的是未编码 URL（文件名含 % [ ] 等会被 Caddy 400）；
            # quote(unquote()) 幂等：raw 与已编码输入都得到同一定全编码结果
            data = {**data, "images": [
                quote(unquote(u), safe="/?=&") for u in data["images"]
            ]}
        self_only = False
        images_hidden = False
        # 与查看者无关：作者设置原值，viewer_id 为 None 时也照常输出
        checkin_state = vis["states"].get(eid) if vis is not None and source == "checkin" else None
        if vis is not None and viewer_id is not None and source == "checkin":
            if eid in vis["hidden"] and actor_key == str(viewer_id):
                self_only = True  # 被隐藏的打卡：作者自见
            if actor_key != str(viewer_id) and isinstance(data, dict):
                if eid in vis["blur"] and isinstance(data.get("images"), list):
                    data = dict(data)
                    data["images"] = [
                        u + ("&" if "?" in u else "?") + "blur=1" for u in data["images"]
                    ]
                elif eid in vis["text"] and isinstance(data.get("images"), list) and data["images"]:
                    data = dict(data)
                    data["images"] = []
                    images_hidden = True
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
            **({"images_hidden": True} if images_hidden else {}),
            **({"checkin_state": checkin_state} if checkin_state else {}),
        })
    return events, users


@router.get("/api/timeline", response_model=TimelineFeedOut, response_model_exclude_unset=True)
def timeline_feed(
    user_id: Annotated[str, Depends(get_current_user_id)],
    cursor: str | None = Query(default=None),
    page_size: int = Query(default=_PAGE_SIZE_DEFAULT, ge=1, le=_PAGE_SIZE_MAX),
):
    """时间线查询（登录可见，游标式信息流）。服务端解析占位符与昵称头像（并发，冷缓存首屏提速）。"""
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
        need = page_size + 1 - len(vis_rows)
        batch = db.timeline.page(cur_pos, need)
        if not batch:
            has_more = False  # 空页必然取尽；沿用上一轮的 True 会令下方 batch[-1] 对空表取下标（P1）
            break
        vis = _visibility_ctx(_vis_full(r) for r in batch)
        for r in batch:
            if _visible_entry(_vis_full(r), user_id, vis):
                vis_rows.append(r)
        if len(vis_rows) > page_size:
            has_more = True
            break
        if len(batch) < need:  # 数据库取尽
            has_more = False
            break
        cur_pos = (batch[-1][3], batch[-1][1])
        has_more = True
    vis_rows = vis_rows[:page_size]

    vis = _visibility_ctx(_vis_full(r) for r in vis_rows)
    read_ids = db.timeline.read_event_ids(user_id, [r[1] for r in vis_rows]) if vis_rows else set()
    events, users = _serialize_rows(vis_rows, watermark, read_ids, viewer_id=user_id, vis=vis)

    next_cursor = None
    if has_more:
        last = vis_rows[-1] if vis_rows else batch[-1]  # 全被过滤时用已取到的最后一条作续读游标
        next_cursor = f"{last[3]}|{last[1]}"
    return {"events": events, "users": users, "next_cursor": next_cursor}


@router.get("/api/timeline/poll", response_model=TimelinePollOut)
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


@router.get("/api/timeline/new", response_model=TimelineNewOut, response_model_exclude_unset=True)
def timeline_new(
    user_id: Annotated[str, Depends(get_current_user_id)],
    after: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=_PAGE_SIZE_DEFAULT, ge=1, le=_PAGE_SIZE_MAX),
):
    """拉取比 max(after, 水印) 更新且无回执的事件。数据库按 rowid ASC 取最老一批
    （避免 >100 条时跳项），响应内倒为 feed 的新→旧顺序；next_after 供客户端循环。"""
    db = DbManager()
    watermark = db.timeline.get_or_init_watermark(user_id)
    lower = max(after or 0, watermark)
    fetched = db.timeline.page_unread_after(user_id, lower, page_size + 1)
    has_more = len(fetched) > page_size
    fetched = fetched[:page_size]
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


@router.post("/api/timeline/read", response_model=ReadOut)
def timeline_read(
    body: ReadEventsIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """上报逐卡已读回执；remaining 为该用户剩余未读事件数。未知/重复/已撤回 id 安全忽略。"""
    db = DbManager()
    remaining = db.timeline.mark_read_events(user_id, body.event_ids)
    return {"ok": True, "remaining": remaining}


# —— 侧边栏导航数据源（唯一入口维护点）——
@router.get("/api/nav", response_model=list[NavEntry])
def nav_entries():
    path = TIMELINE_DIR / "entries.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="导航数据不存在")
    return json.loads(path.read_text(encoding="utf-8"))
