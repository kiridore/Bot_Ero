"""网页端打卡：保存图片并执行与 QQ 指令相同的结算逻辑。"""

from __future__ import annotations

import importlib.util
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from core.database_manager import DbManager
from core.utils import add_user_point, get_monday_to_monday

from checkin_gallery import config

_TITLE_MODULE_PATH = Path(__file__).resolve().parent.parent / "plugins" / "title.py"

_ALLOWED_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _load_title_helpers():
    spec = importlib.util.spec_from_file_location("botero_title_checkin", _TITLE_MODULE_PATH)
    if spec is None or spec.loader is None:
        return None, None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "evaluate_and_unlock_titles", None), getattr(mod, "get_title_def", None)


def get_checkin_status(user_id: str) -> dict:
    db = DbManager()
    start_date, end_date = get_monday_to_monday()
    rows = db.checkin.search_user_range(user_id, start_date, end_date)
    real_rows = [r for r in rows if r[3] != "remedy_checkin"]
    streaks = db.checkin.streaks(user_id)
    return {
        "week_start": start_date.split(" ")[0],
        "week_end": end_date.split(" ")[0],
        "week_image_count": len(real_rows),
        "is_first_this_week": len(real_rows) == 0,
        "streaks": streaks,
        "max_images": config.CHECKIN_MAX_IMAGES,
        "max_bytes": config.CHECKIN_MAX_BYTES,
    }


def _save_one_image(user_id: str, data: bytes, content_type: str | None) -> str:
    mime = (content_type or "").split(";")[0].strip().lower()
    ext = _ALLOWED_MIME.get(mime)
    if ext is None:
        raise ValueError("仅支持 JPG / PNG / WebP / GIF 图片")
    if len(data) > config.CHECKIN_MAX_BYTES:
        raise ValueError(f"单张图片不能超过 {config.CHECKIN_MAX_BYTES // (1024 * 1024)} MB")

    folder = config.IMAGE_ROOT / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"web{uuid.uuid4().hex}{ext}"
    dest = folder / name
    dest.write_bytes(data)
    return name


def save_uploaded_images(user_id: str, files: list[tuple[bytes, str | None]]) -> list[str]:
    if not files:
        raise ValueError("请至少上传一张图片")
    if len(files) > config.CHECKIN_MAX_IMAGES:
        raise ValueError(f"单次最多上传 {config.CHECKIN_MAX_IMAGES} 张图片")
    return [_save_one_image(user_id, data, mime) for data, mime in files]


def perform_checkin(user_id: str, image_names: list[str]) -> dict:
    if not image_names:
        raise ValueError("没有可收录的图片")

    db = DbManager()
    evaluate_fn, get_title_def = _load_title_helpers()
    start_date, end_date = get_monday_to_monday()
    before = db.checkin.search_user_range(user_id, start_date, end_date)
    is_first = len(before) == 0

    db.checkin.insert(user_id, image_names, message_id=None)

    checkin_luck_bonus = 0
    if db.shop.pop_luck(user_id):
        if random.random() < 0.1:
            checkin_luck_bonus = 1

    unlocked_ids: list[int] = []
    if evaluate_fn:
        unlocked_ids = evaluate_fn(db, user_id, datetime.now())

    checkin_list = db.checkin.search_user_range(user_id, start_date, end_date)
    streak_res = db.checkin.streaks(user_id)

    bonus_total = 0
    bonus_lines: list[str] = []
    week_start = start_date.split(" ")[0]
    now_dt = datetime.now()

    natural_week_start = now_dt - timedelta(days=now_dt.weekday())
    natural_week_end = natural_week_start + timedelta(days=7)
    week_full_days = db.checkin.count_days(
        user_id,
        f"{natural_week_start.strftime('%Y-%m-%d')} 00:00:00",
        f"{natural_week_end.strftime('%Y-%m-%d')} 00:00:00",
    )
    if week_full_days >= 7 and db.checkin.claim_attendance(
        user_id, "full_week_daily", now_dt.strftime("%Y-%m-%d"), 1
    ):
        bonus_total += 1
        bonus_lines.append("自然周全勤奖励 +1")

    month_start = now_dt.replace(day=1)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1, day=1)
    month_full_days = db.checkin.count_days(
        user_id,
        month_start.strftime("%Y-%m-%d 00:00:00"),
        next_month_start.strftime("%Y-%m-%d 00:00:00"),
    )
    month_days = (next_month_start - month_start).days
    if is_first and month_full_days >= month_days and db.checkin.claim_attendance(
        user_id, "full_month_weekly_check", week_start, 1
    ):
        bonus_total += 1
        bonus_lines.append("当月全勤奖励 +1")

    if is_first:
        bonus_total += 1
        bonus_lines.append("当周首次打卡奖励 +1")

    if checkin_luck_bonus:
        bonus_total += checkin_luck_bonus
        bonus_lines.append("打卡增强：概率奖励 +1")

    if bonus_total > 0:
        add_user_point(db, user_id, bonus_total)

    unlocked_titles = []
    for tid in unlocked_ids:
        data = (get_title_def(tid) if get_title_def else None) or {
            "name": "未知称号",
            "rarity": "unknown",
            "description": "无",
        }
        unlocked_titles.append(
            {
                "id": tid,
                "name": data["name"],
                "rarity": data.get("rarity", "unknown"),
                "description": data.get("description", ""),
            }
        )

    summary_lines = [f"收录了 {len(image_names)} 张图片"]
    if is_first:
        summary_lines.append("完成本周首次打卡")
    else:
        summary_lines.append(f"本周已累计 {len(checkin_list)} 张图")
    if bonus_lines:
        summary_lines.extend(bonus_lines)
    if streak_res["current_weekly"] > 1:
        summary_lines.append(f"已连续打卡 {streak_res['current_weekly']} 周")

    return {
        "success": True,
        "image_count": len(image_names),
        "is_first_this_week": is_first,
        "week_total_images": len(checkin_list),
        "bonus_total": bonus_total,
        "bonus_lines": bonus_lines,
        "unlocked_titles": unlocked_titles,
        "streaks": streak_res,
        "summary": "\n".join(summary_lines),
    }
