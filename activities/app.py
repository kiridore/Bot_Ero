"""活动子应用：接龙与匹配活动的作品归档。"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from core.config import ACTIVITY_ROOT
from core.database_manager import DbManager
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

router = APIRouter()


@router.get("/api/activities")
def api_activities():
    db = DbManager()
    return {"items": db.activity.list_activities()}


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


@router.get("/{activity_id}")
def activity_detail_page(activity_id: int):
    db = DbManager()
    if db.activity.get_activity(activity_id) is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    page = STATIC_DIR / "activities_detail.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少活动详情页")
    return FileResponse(page)
