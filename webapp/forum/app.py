"""议事厅子应用：长文/公告/投票/评论（统一登录鉴权）。"""

import json
import re
from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.timeline_client import emit_event, retract_event
from core.web.auth_deps import get_current_user_id
from core.onebot_client import resolve_avatar_url, resolve_display_name
from core.database_manager import DbManager
from core.config import FORUM_IMAGE_MAX_BYTES, FORUM_IMAGES_ROOT
from webapp import STATIC_DIR

router = APIRouter()

EXCERPT_LONG = 150   # 长文/公告节选长度
EXCERPT_COMMENT = 80  # 评论节选长度


def _author_fields(user_id) -> dict:
    """作者展示字段：昵称 + 头像（OneBot 解析，失败降级回 id）。"""
    uid = str(user_id)
    return {
        "author_name": resolve_display_name(uid),
        "author_avatar": resolve_avatar_url(uid),
    }


def _tiptap_to_plain(doc: Any) -> str:
    """递归遍历 Tiptap document JSON，提取所有 text 节点的文本，空白归一。"""
    if isinstance(doc, dict):
        if doc.get("type") == "text":
            return doc.get("text", "")
        return " ".join(_tiptap_to_plain(v) for v in doc.get("content", []) if v is not None)
    if isinstance(doc, list):
        return " ".join(_tiptap_to_plain(item) for item in doc if item is not None)
    return ""


def _excerpt(body_json_str: str, max_len: int) -> str:
    """从 Tiptap JSON 字符串提取纯文本节选（max_len 字 + …）。JSON 解析失败返回空串。"""
    if not body_json_str:
        return ""
    try:
        doc = json.loads(body_json_str)
    except (TypeError, ValueError):
        return ""
    text = _tiptap_to_plain(doc).strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"


_ALLOWED_IMAGE_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _save_forum_image(data: bytes, content_type: str | None) -> str:
    """校验并保存议事厅正文图片，返回文件名（uuid，不可枚举）。"""
    mime = (content_type or "").split(";")[0].strip().lower()
    ext = _ALLOWED_IMAGE_MIME.get(mime)
    if ext is None:
        raise ValueError("仅支持 JPG / PNG / WebP / GIF 图片")
    if len(data) > FORUM_IMAGE_MAX_BYTES:
        raise ValueError(f"图片不能超过 {FORUM_IMAGE_MAX_BYTES // (1024 * 1024)} MB")

    FORUM_IMAGES_ROOT.mkdir(parents=True, exist_ok=True)
    name = f"f{uuid4().hex}{ext}"
    (FORUM_IMAGES_ROOT / name).write_bytes(data)
    return name


def _upload_or_400(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _emit_post_event(post: dict) -> None:
    """帖子创建/编辑后向时间线发事件。best-effort。"""
    title_verb = {
        "post": "在议事厅发布了长文",
        "announce": "发布了公告",
        "poll": "发起了投票",
    }.get(post["type"], "在议事厅发布了内容")
    title = f"{{id:{post['author_user_id']}}} {title_verb}「{post['title']}」"
    desc = _excerpt(post.get("body_json") or "", EXCERPT_LONG) if post["type"] != "poll" else ""
    emit_event(
        source="forum",
        actor_id=str(post["author_user_id"]),
        actor_qq=str(post["author_user_id"]),
        title=title,
        description=desc,
        target_url=f"/forum/{post['id']}",
        dedup_key=f"forum_post:{post['id']}",
    )


def _emit_comment_event(comment: dict, post: dict) -> None:
    title = f"{{id:{comment['author_user_id']}}} 在「{post['title']}」回复了"
    desc = comment.get("body_text", "")[:EXCERPT_COMMENT]
    if len(comment.get("body_text", "")) > EXCERPT_COMMENT:
        desc += "…"
    emit_event(
        source="forum",
        actor_id=str(comment["author_user_id"]),
        actor_qq=str(comment["author_user_id"]),
        title=title,
        description=desc,
        target_url=f"/forum/{comment['post_id']}",
        dedup_key=f"forum_comment:{comment['id']}",
    )


# —— 输入模型 ——

class PollOptionIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class PostCreateIn(BaseModel):
    type: str = Field(pattern="^(post|announce|poll)$")
    title: str = Field(min_length=1, max_length=200)
    body_json: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    polls: list[PollOptionIn] = Field(default_factory=list)
    poll_anonymous: bool = False
    poll_deadline: str | None = None  # "YYYY-MM-DD HH:MM:SS"


class PostUpdateIn(BaseModel):
    title: str | None = None
    body_json: str | None = None
    tags: list[str] | None = None  # None=不动，[]=清空


class CommentCreateIn(BaseModel):
    body_text: str = Field(min_length=1, max_length=2000)


class VoteIn(BaseModel):
    option_id: int


class TagCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)


# —— 路由 ——

@router.get("/api/forum/posts")
def list_posts(
    user_id: Annotated[str, Depends(get_current_user_id)],
    tag: str | None = Query(default=None),
    type: str | None = Query(default=None, pattern="^(post|announce|poll)$"),
    cursor: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
):
    db = DbManager()
    rows = db.forum.list_posts(tag=tag, type_=type, cursor=cursor, limit=limit)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1][0] if has_more and rows else None
    items = []
    for r in rows:
        cols = ("id", "author_user_id", "type", "title", "status", "pinned", "created_at", "updated_at", "poll_deadline")
        item = dict(zip(cols, r))
        item.update(_author_fields(item["author_user_id"]))
        items.append(item)
    return {"items": items, "next_cursor": next_cursor}


@router.post("/api/forum/posts")
def create_post(
    body: PostCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    # 公告每日 1 次限制
    if body.type == "announce":
        if db.forum.count_today_announces(user_id) >= 1:
            raise HTTPException(status_code=429, detail="今天已经发过公告了，每人每天至多 1 条")
    # 投票至少 2 个选项
    if body.type == "poll" and len(body.polls) < 2:
        raise HTTPException(status_code=400, detail="投票至少需要 2 个选项")
    # 截止时间格式校验
    deadline = body.poll_deadline
    if deadline:
        try:
            datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise HTTPException(status_code=400, detail="poll_deadline 格式错误，应为 YYYY-MM-DD HH:MM:SS")
        # 截止必须未来
        if deadline <= datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
            raise HTTPException(status_code=400, detail="截止时间必须在未来")
    # tags：按名查/建
    tag_ids = []
    for name in body.tags:
        name = name.strip()
        if not name:
            continue
        self_cur = db.conn.cursor()
        self_cur.execute("SELECT id FROM forum_tags WHERE name = ?", (name,))
        row = self_cur.fetchone()
        if row:
            tag_ids.append(row[0])
        else:
            tid = db.forum.create_tag(name, user_id)
            if tid:
                tag_ids.append(tid)
    # 选项文本
    poll_texts = [p.text for p in body.polls] if body.polls else None
    # 写入
    pid = db.forum.create_post(
        author_user_id=user_id,
        type_=body.type,
        title=body.title,
        body_json=body.body_json,
        polls=poll_texts,
        tag_ids=tag_ids or None,
        poll_anonymous=body.poll_anonymous,
        poll_allow_multi=False,  # v1 不做多选
        poll_deadline=deadline,
    )
    post = db.forum.get_post(pid)
    _emit_post_event(post)
    return {"ok": True, "id": pid}


@router.post("/api/forum/images")
async def api_forum_image_upload(
    user_id: Annotated[str, Depends(get_current_user_id)],
    file: UploadFile = File(...),
):
    data = await file.read()
    name = _upload_or_400(_save_forum_image, data, file.content_type)
    return {"url": f"/forum/media/{name}"}


@router.get("/api/forum/posts/{post_id}")
def get_post(
    post_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    post = db.forum.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post.update(_author_fields(post["author_user_id"]))
    # 投票选项：附带票数 + 当前用户投票
    my_vote = None
    if post["type"] == "poll":
        post["vote_counts"] = [
            {"id": r[0], "text": r[1], "ord": r[2], "count": r[3]}
            for r in db.forum.get_vote_counts(post_id)
        ]
        my_vote = db.forum.get_user_vote(post_id, user_id)
    post["my_vote"] = my_vote
    # tag 名数组已包含
    return post


@router.patch("/api/forum/posts/{post_id}")
def update_post(
    post_id: int,
    body: PostUpdateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    # 校验作者
    existing = db.forum.get_post(post_id)
    if not existing:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if str(existing["author_user_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="只能编辑自己的帖子")
    # tags 解析
    tag_ids = None
    if body.tags is not None:
        tag_ids = []
        for name in body.tags:
            name = name.strip()
            if not name:
                continue
            c = db.conn.cursor()
            c.execute("SELECT id FROM forum_tags WHERE name = ?", (name,))
            row = c.fetchone()
            if row:
                tag_ids.append(row[0])
            else:
                tid = db.forum.create_tag(name, user_id)
                if tid:
                    tag_ids.append(tid)
    ok = db.forum.update_post(
        post_id, user_id,
        title=body.title,
        body_json=body.body_json,
        tag_ids=tag_ids,
    )
    if not ok:
        raise HTTPException(status_code=403, detail="只能编辑自己的帖子")
    return {"ok": True}


@router.delete("/api/forum/posts/{post_id}")
def delete_post(
    post_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    ok = db.forum.delete_post(post_id, user_id)
    if not ok:
        raise HTTPException(status_code=403, detail="只能删除自己的帖子")
    retract_event(source="forum", dedup_key=f"forum_post:{post_id}")
    return {"ok": True}


@router.get("/api/forum/posts/{post_id}/comments")
def list_comments(
    post_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
    cursor: int | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
):
    db = DbManager()
    rows = db.forum.list_comments(post_id, cursor=cursor, limit=limit)
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = []
    for r in rows:
        item = {"id": r[0], "post_id": r[1], "author_user_id": r[2],
                "body_text": r[3], "created_at": r[4], "status": r[5]}
        item.update(_author_fields(item["author_user_id"]))
        items.append(item)
    next_cursor = items[-1]["id"] if has_more and items else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/api/forum/posts/{post_id}/comments")
def create_comment(
    post_id: int,
    body: CommentCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    post = db.forum.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    cid = db.forum.create_comment(post_id, user_id, body.body_text.strip())
    db.conn.commit()
    comment = {"id": cid, "post_id": post_id, "author_user_id": user_id,
               "body_text": body.body_text.strip(), "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    _emit_comment_event(comment, post)
    return {"ok": True, "id": cid}


@router.delete("/api/forum/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    ok = db.forum.delete_comment(comment_id, user_id)
    if not ok:
        raise HTTPException(status_code=403, detail="只能删除自己的评论")
    retract_event(source="forum", dedup_key=f"forum_comment:{comment_id}")
    return {"ok": True}


@router.post("/api/forum/posts/{post_id}/vote")
def vote(
    post_id: int,
    body: VoteIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    ok, err = db.forum.vote(post_id, body.option_id, user_id)
    if ok:
        return {"ok": True}
    code_map = {
        "not_found": (404, "帖子不存在"),
        "not_poll": (400, "该帖不是投票"),
        "closed": (422, "投票已结束"),
        "expired": (422, "投票已截止"),
        "invalid_option": (400, "投票选项无效"),
        "duplicate": (409, "你已经投过这个投票"),
    }
    sc, msg = code_map.get(err, (500, "投票失败"))
    raise HTTPException(status_code=sc, detail=msg)


@router.post("/api/forum/posts/{post_id}/close")
def close_poll(
    post_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    post = db.forum.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if str(post["author_user_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="只能关闭自己的投票")
    if post["type"] != "poll":
        raise HTTPException(status_code=400, detail="该帖不是投票")
    closed = db.forum.close_poll(post_id)
    if closed:
        emit_event(
            source="forum",
            actor_id=str(user_id),
            actor_qq=str(user_id),
            title=f"投票「{post['title']}」已结束",
            target_url=f"/forum/{post_id}",
            dedup_key=f"forum_poll_close:{post_id}",
        )
    return {"ok": True, "closed": closed}


@router.get("/api/forum/tags")
def list_tags(
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    rows = db.forum.list_tags_with_counts()
    return {"tags": [{"id": r[0], "name": r[1], "created_at": r[2], "post_count": r[3]} for r in rows]}


@router.post("/api/forum/tags")
def create_tag(
    body: TagCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    tid = db.forum.create_tag(body.name, user_id)
    if tid is None:
        raise HTTPException(status_code=409, detail="tag 名已存在")
    return {"ok": True, "id": tid}


# —— 页面 ——

def _serve(name: str):
    path = STATIC_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=500, detail=f"缺少静态页面 {name}")
    return FileResponse(path)


@router.get("/forum")
def forum_page():
    return _serve("forum.html")


@router.get("/forum/new")
def forum_new_page():
    return _serve("forum_new.html")


@router.get("/forum/tags")
def forum_tags_page():
    return _serve("forum_tags.html")


@router.get("/forum/media/{filename}")
def forum_media(filename: str):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法路径")
    path = FORUM_IMAGES_ROOT / filename
    try:
        path.resolve().relative_to(FORUM_IMAGES_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="禁止访问") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(path)


@router.get("/forum/{post_id}")
def forum_detail_page(post_id: int):
    return _serve("forum_detail.html")
