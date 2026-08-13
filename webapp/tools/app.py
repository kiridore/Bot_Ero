"""工具箱子应用：网页链接收藏，公开可浏览，登录后可添加。"""

from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.database_manager import DbManager
from core.onebot_client import resolve_avatar_url, resolve_display_name
from core.timeline_client import emit_event
from core.web.auth_deps import get_current_user_id, get_optional_user_id
from webapp import STATIC_DIR

router = APIRouter()


class ToolCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    description: str = Field(default="", max_length=200)
    url: str = Field(max_length=2048)


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
):
    db = DbManager()
    items = db.tools.list_tools(q)
    for item in items:
        uid = item["created_by"]
        item["created_by_name"] = resolve_display_name(uid)
        item["created_by_avatar"] = resolve_avatar_url(uid)
    return {"items": items}


@router.post("/api/tools")
def api_tools_add(
    body: ToolCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    url = _or_400(_validate_url, body.url)
    domain = urlsplit(url).netloc.lower()
    db = DbManager()
    tool_id = _or_400(
        db.tools.add_tool,
        user_id,
        body.title.strip(),
        body.description.strip(),
        url,
        domain,
    )
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


@router.get("/tools")
def tools_page():
    page = STATIC_DIR / "tools.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)
