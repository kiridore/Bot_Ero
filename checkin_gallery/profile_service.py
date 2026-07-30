"""个人主页数据：热力图、称号进度等。"""

from __future__ import annotations

import calendar
import datetime as dt

import importlib.util
from pathlib import Path

from core import utils as core_utils
from core.database_manager import DbManager

from checkin_gallery.onebot_client import resolve_avatar_url, resolve_display_name

_TITLE_MODULE_PATH = Path(__file__).resolve().parent.parent / "plugins" / "title.py"


def _load_title_defs() -> dict:
    spec = importlib.util.spec_from_file_location("botero_title_defs", _TITLE_MODULE_PATH)
    if spec is None or spec.loader is None:
        return {}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "TITLE_DEFS", {})


TITLE_DEFS = _load_title_defs()
from checkin_gallery.repository import fetch_user_year_rows


def _level_from_count(count: int, is_remedy: bool) -> int:
    if is_remedy:
        return -1
    if count <= 0:
        return 0
    if count == 1:
        return 1
    if count == 2:
        return 2
    if count == 3:
        return 3
    return 4


def build_year_heatmap(user_id: str, year: int) -> list[dict]:
    rows = fetch_user_year_rows(user_id, year)
    days_in_year = 366 if calendar.isleap(year) else 365
    counts = [0] * days_in_year
    remedy_flags = [False] * days_in_year

    for row in rows:
        idx = core_utils.day_of_year(row["checkin_date"]) - 1
        if idx < 0 or idx >= days_in_year:
            continue
        if row["content"] == "remedy_checkin":
            remedy_flags[idx] = True
            counts[idx] = 0
        else:
            counts[idx] += 1

    out: list[dict] = []
    for i in range(days_in_year):
        d = dt.date(year, 1, 1) + dt.timedelta(days=i)
        is_remedy = remedy_flags[i]
        cnt = counts[i]
        out.append(
            {
                "date": d.isoformat(),
                "count": cnt,
                "level": _level_from_count(cnt, is_remedy),
                "is_remedy": is_remedy,
            }
        )
    return out


def _condition_progress(tid: int, ctx: dict) -> tuple[float, float, str]:
    total_days = ctx["total_days"]
    draw_count = ctx["draw_count"]
    dup = ctx["duplicate_count"]
    max_zero = ctx["max_zero_streak"]
    hit_ten = ctx["has_hit_ten"]
    title_cnt = ctx["title_count"]

    mapping: dict[int, tuple] = {
        206: (total_days, 365, "累计打卡天"),
        207: (total_days, 200, "累计打卡天"),
        208: (total_days, 100, "累计打卡天"),
        209: (total_days, 30, "累计打卡天"),
        222: (title_cnt, 10, "已解锁称号数"),
        223: (title_cnt, 20, "已解锁称号数"),
        224: (title_cnt, 30, "已解锁称号数"),
        227: (dup, 1, "重复称号次数"),
        228: (dup, 10, "重复称号次数"),
        229: (dup, 100, "重复称号次数"),
        230: (draw_count, 1, "累计抽奖次数"),
        231: (draw_count, 10, "累计抽奖次数"),
        232: (draw_count, 25, "累计抽奖次数"),
        233: (draw_count, 50, "累计抽奖次数"),
        234: (draw_count, 100, "累计抽奖次数"),
        235: (hit_ten, 1, "抽到10积分"),
        236: (max_zero, 3, "连续空抽"),
        237: (max_zero, 10, "连续空抽"),
    }
    if tid in mapping:
        cur, tgt, hint = mapping[tid]
        return float(min(cur, tgt)), float(tgt), hint
    return 0.0, 1.0, "达成条件后解锁"


def build_title_list(user_id: str, db: DbManager) -> list[dict]:
    unlocked = set(db.titles.list(user_id))
    equipped = set(db.titles.equipped_all(user_id))
    profile = db.lottery.profile(user_id)
    spent = db.lottery.spent(user_id)
    ctx = {
        "total_days": db.checkin.count_all_days(user_id),
        "draw_count": max(profile["draw_count"], spent),
        "duplicate_count": profile["duplicate_count"],
        "max_zero_streak": profile["max_zero_streak"],
        "has_hit_ten": profile["has_hit_ten"],
        "title_count": len(unlocked),
    }

    items: list[dict] = []
    for tid in sorted(TITLE_DEFS.keys()):
        data = TITLE_DEFS[tid]
        ut = data.get("unlock_type", "unknown")
        is_unlocked = tid in unlocked
        if ut == "lottery":
            current, target = (1.0, 1.0) if is_unlocked else (0.0, 1.0)
            hint = "通过抽奖解锁"
        else:
            current, target, hint = _condition_progress(tid, ctx)
            if is_unlocked:
                current, target = target, target
        progress = 1.0 if is_unlocked else (current / target if target > 0 else 0.0)
        progress = max(0.0, min(1.0, progress))
        items.append(
            {
                "id": tid,
                "name": data["name"],
                "rarity": data.get("rarity", "unknown"),
                "description": data.get("description", ""),
                "unlock_type": ut,
                "unlocked": is_unlocked,
                "equipped": tid in equipped,
                "progress": round(progress, 4),
                "progress_current": int(current),
                "progress_target": int(target),
                "progress_hint": hint,
            }
        )
    return items


def build_profile(user_id: str, year: int | None = None) -> dict:
    if year is None:
        year = dt.date.today().year
    db = DbManager()
    streaks = db.checkin.streaks(user_id)
    unlocked_ids = db.titles.list(user_id)
    return {
        "user_id": str(user_id),
        "display_name": resolve_display_name(str(user_id)),
        "avatar_url": resolve_avatar_url(str(user_id)),
        "year": year,
        "points": db.points.get(user_id),
        "streaks": streaks,
        "titles_unlocked": len(unlocked_ids),
        "titles_total": len(TITLE_DEFS),
        "heatmap": build_year_heatmap(str(user_id), year),
        "titles": build_title_list(user_id, db),
    }
