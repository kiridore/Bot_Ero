"""小埃周报模块：归档 API + 报纸页面。"""

from __future__ import annotations

from copy import deepcopy
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from core.config import GROUP_ID
from core.database_manager import DbManager
from core.user_settings import display_identity, identity_public
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

router = APIRouter()


def _display_report(data: dict, viewer_id: str) -> dict:
    """仅改响应副本的身份字段；正文不是可按昵称替换的身份引用。"""
    out = deepcopy(data)

    def valid_user_id(value) -> bool:
        return isinstance(value, (str, int)) and str(value).isascii() and str(value).isdigit()

    lottery = out.get("lottery")
    immortal = lottery.get("immortal") if isinstance(lottery, dict) else None
    if isinstance(immortal, dict) and isinstance(immortal.get("winners"), list):
        for winner in immortal["winners"]:
            if isinstance(winner, dict) and not valid_user_id(winner.get("user_id")):
                winner["name"] = "身份资料缺失"

    def display_names(value) -> None:
        if isinstance(value, dict):
            if "user_id" in value and "name" in value:
                value["name"] = (
                    display_identity(value["user_id"], viewer_id, value["name"], None)[0]
                    if valid_user_id(value["user_id"]) else "身份资料缺失"
                )
            for child in value.values():
                display_names(child)
        elif isinstance(value, list):
            for child in value:
                display_names(child)

    display_names(out)
    headline = out.get("headline", {})
    if headline.get("kind") != "immortal_jackpot":
        return out
    lottery = data.get("lottery")
    immortal = lottery.get("immortal") if isinstance(lottery, dict) else None
    tiers = {2: "三等奖(2A)", 3: "二等奖(3A)", 4: "一等奖(4A)"}

    def digits_valid(value) -> bool:
        return isinstance(value, str) and len(value) == 4 and value.isascii() and value.isdigit()

    valid = (isinstance(immortal, dict) and digits_valid(immortal.get("digits"))
             and type(immortal.get("pool")) is int and immortal["pool"] >= 0
             and isinstance(immortal.get("winners"), list))
    if valid:
        for winner in immortal["winners"]:
            if not (isinstance(winner, dict)
                    and valid_user_id(winner.get("user_id"))
                    and isinstance(winner.get("name"), str)
                    and digits_valid(winner.get("digits"))
                    and winner.get("tier") == tiers.get(sum(
                        a == b for a, b in zip(immortal["digits"], winner["digits"])
                    )) and winner.get("tier") in tiers.values()):
                valid = False
                break
    if not valid:
        out["headline"] = {
            "kind": "immortal_jackpot", "title": "仙人彩历史头条",
            "body": "历史头条缺少身份资料，暂不展示详情。", "stats": [],
        }
        return out
    winners = immortal["winners"]
    if not any(str(w["user_id"]) != str(viewer_id) and not identity_public(w["user_id"]) for w in winners):
        return out
    winners = out["lottery"]["immortal"]["winners"]
    jackpot = [w for w in winners if w["tier"] in (tiers[3], tiers[4])]
    hit_names = "、".join(f'{w["name"]}（{w["digits"]}）' for w in (jackpot or winners))
    digits, pool = immortal["digits"], immortal["pool"]
    if jackpot:
        headline["body"] = f"本期开奖号码 {digits}，{hit_names} 命中大奖！"
        headline["stats"] = [
            {"label": "开奖号码", "value": digits},
            {"label": "大奖得主", "value": hit_names},
            {"label": "总奖池", "value": pool},
        ]
    else:
        headline["body"] = f"本期开奖号码 {digits}，无人命中大奖，{len(winners)} 注命中三等奖，奖池滚存。"
        headline["stats"] = [
            {"label": "开奖号码", "value": digits},
            {"label": "中奖注数", "value": len(winners)},
            {"label": "中奖名单", "value": hit_names},
            {"label": "总奖池", "value": pool},
        ]
    return out


@router.get("/api/weekly")
def api_weekly_list(_user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    reports = db.weekly.list(int(GROUP_ID))
    items = []
    for r in reports:
        data = _display_report(r["data_json"], _user_id)
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
    return _display_report(row["data_json"], _user_id)


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
