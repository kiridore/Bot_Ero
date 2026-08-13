"""工具箱子应用：网页链接收藏，公开可浏览，登录后可添加。"""

from typing import Annotated
from urllib.parse import urlsplit

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from core.database_manager import DbManager
from core.onebot_client import resolve_avatar_url, resolve_display_name
from core.timeline_client import emit_event, retract_event
from core.web.auth_deps import get_current_user_id, get_optional_user_id
from webapp import STATIC_DIR
from webapp.tools.icon import fetch_icon

router = APIRouter()

NOT_FOUND_TTL = timedelta(days=7)  # 负缓存：无图标域名 7 天后重试


class ToolCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    description: str = Field(default="", max_length=200)
    url: str = Field(max_length=2048)
    tags: list[str] = Field(default_factory=list)


def _validate_url(url: str) -> str:
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("URL 需以 http:// 或 https:// 开头")
    return url


def _or_400(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/tools")
def api_tools_list(
    viewer_id: Annotated[str | None, Depends(get_optional_user_id)],
    q: str | None = Query(default=None, max_length=100),
    sort: str = Query(default="time", pattern="^(time|hot)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    tag: str | None = Query(default=None, max_length=20),
):
    db = DbManager()
    items = db.tools.list_tools(q, sort=sort, order=order, tag=tag)
    for item in items:
        uid = item["created_by"]
        item["created_by_name"] = resolve_display_name(uid)
        item["created_by_avatar"] = resolve_avatar_url(uid)
    return {"items": items}


def _clean_tags(tags: list[str]) -> list[str]:
    """清洗 tag：strip、去空、≤20 字、去重、≤10 个。非法抛 ValueError。"""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        name = raw.strip()
        if not name:
            continue
        if len(name) > 20:
            raise ValueError("tag 名不能超过 20 字")
        if name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    if len(cleaned) > 10:
        raise ValueError("最多 10 个 tag")
    return cleaned


@router.get("/api/tools/icon")
def api_tools_icon(
    viewer_id: Annotated[str | None, Depends(get_optional_user_id)],
    domain: str = Query(min_length=1, max_length=253),
):
    """卡片图标：服务端解析（favicon.ico → 首页 link rel=icon）+ 入库缓存。公开。
    仅允许已收录链接的域名；无图标 404；负缓存 7 天。"""
    db = DbManager()
    if not db.tools.domain_exists(domain):
        raise HTTPException(status_code=404, detail="无此域名")
    cached = db.tools.get_icon(domain)
    if cached is not None:
        if cached.get("not_found"):
            fetched_at = datetime.strptime(cached["fetched_at"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - fetched_at < NOT_FOUND_TTL:
                raise HTTPException(status_code=404, detail="无图标")
        else:
            return Response(
                content=cached["bytes"],
                media_type=cached["content_type"],
                headers={"Cache-Control": "public, max-age=86400"},
            )
    data = fetch_icon(domain)
    if data is None:
        db.tools.put_icon_not_found(domain)
        raise HTTPException(status_code=404, detail="无图标")
    db.tools.put_icon(domain, data[0], data[1])
    return Response(
        content=data[0],
        media_type=data[1],
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/api/tools/tags")
def api_tools_tags(
    viewer_id: Annotated[str | None, Depends(get_optional_user_id)],
):
    """全部 tag 及使用数量（仅 count > 0，按数量降序）。公开。"""
    db = DbManager()
    rows = db.tools.list_tags_with_counts()
    return {"tags": [{"name": r[1], "count": int(r[2])} for r in rows]}


@router.post("/api/tools")
def api_tools_add(
    body: ToolCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    url = _or_400(_validate_url, body.url)
    domain = urlsplit(url).netloc.lower()
    tags = _or_400(_clean_tags, body.tags)
    db = DbManager()
    tool_id = _or_400(
        db.tools.add_tool,
        user_id,
        body.title.strip(),
        body.description.strip(),
        url,
        domain,
    )
    if tags:
        db.tools.add_link_tags(tool_id, tags, user_id)
    emit_event(
        source="tools",
        actor_id=user_id,
        actor_qq=user_id,
        title=f"{{id:{user_id}}} 在工具箱提交了「{body.title.strip()}」",
        description=body.description.strip() or None,
        target_url=url,
        dedup_key=f"tools_link:{tool_id}",
    )
    return {"ok": True, "id": tool_id}


@router.post("/api/tools/{tool_id}/click")
def api_tools_click(
    tool_id: int,
    viewer_id: Annotated[str | None, Depends(get_optional_user_id)],
):
    """公开：浏览者点击卡片即计数，无需登录。"""
    db = DbManager()
    clicks = db.tools.register_click(tool_id)
    if clicks is None:
        raise HTTPException(status_code=404, detail="链接不存在")
    return {"ok": True, "clicks": clicks}


@router.put("/api/tools/{tool_id}")
def api_tools_update(
    tool_id: int,
    body: ToolCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    url = _or_400(_validate_url, body.url)
    domain = urlsplit(url).netloc.lower()
    tags = _or_400(_clean_tags, body.tags)
    db = DbManager()
    result = db.tools.update_tool(
        user_id,
        tool_id,
        body.title.strip(),
        body.description.strip(),
        url,
        domain,
        tags,
    )
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="链接不存在")
    if result["status"] == "forbidden":
        raise HTTPException(status_code=403, detail="只能修改自己提交的链接")
    # 撤回旧时间线事件并以同 dedup_key 重发（feed 展示最新内容）
    retract_event(source="tools", dedup_key=f"tools_link:{tool_id}")
    emit_event(
        source="tools",
        actor_id=user_id,
        actor_qq=user_id,
        title=f"{{id:{user_id}}} 在工具箱提交了「{body.title.strip()}」",
        description=body.description.strip() or None,
        target_url=url,
        dedup_key=f"tools_link:{tool_id}",
    )
    return {"ok": True, "id": tool_id}


@router.delete("/api/tools/{tool_id}")
def api_tools_delete(
    tool_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    result = db.tools.delete_tool(user_id, tool_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="链接不存在")
    if result["status"] == "forbidden":
        raise HTTPException(status_code=403, detail="只能删除自己提交的链接")
    retract_event(source="tools", dedup_key=f"tools_link:{tool_id}")
    return {"ok": True}


@router.get("/tools")
def tools_page():
    page = STATIC_DIR / "tools.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)
