"""小埃周报模块：归档 API + 报纸页面。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from core.config import GROUP_ID
from core.database_manager import DbManager
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

router = APIRouter()


@router.get("/api/weekly")
def api_weekly_list(_user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    reports = db.weekly.list(int(GROUP_ID))
    items = []
    for r in reports:
        data = r["data_json"]
        period = data.get("period", {})
        headline = data.get("headline", {})
        items.append({
            "week_key": r["week_key"],
            "issue": period.get("issue"),
            "start": period.get("start"),
            "end": period.get("end"),
            "total_messages": period.get("total_messages"),
            "headline_title": headline.get("title"),
        })
    return {"items": items}


@router.get("/api/weekly/{week_key}")
def api_weekly_detail(week_key: str, _user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    row = db.weekly.get(week_key, int(GROUP_ID))
    if row is None:
        raise HTTPException(status_code=404, detail="该期周报不存在")
    return row["data_json"]


@router.get("/weekly")
def weekly_latest():
    db = DbManager()
    reports = db.weekly.list(int(GROUP_ID))
    if not reports:
        raise HTTPException(status_code=404, detail="暂无周报")
    return RedirectResponse(url=f"/weekly/{reports[0]['week_key']}")


@router.get("/weekly/{week_key}")
def weekly_page(week_key: str):
    page = STATIC_DIR / "weekly.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少周报静态页面")
    return FileResponse(page)
