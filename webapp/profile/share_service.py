"""打卡分享卡组装：查记录 → 头像/统计 → PIL 合成 PNG 字节。"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from core import context
from core.database_manager import DbManager
from core.gen_image.checkin_share_card import build_checkin_share_card
from core.onebot_client import resolve_avatar_url, resolve_display_name
from webapp.gallery.repository import fetch_checkin_by_id

logger = logging.getLogger(__name__)


def _fetch_avatar(user_id: str) -> Image.Image | None:
    cache_path = Path(context.python_data_path) / "avatar_cache" / f"share_{user_id}.png"
    if cache_path.is_file():
        try:
            cached = Image.open(cache_path)
            cached.load()
            return cached
        except Exception:
            logger.warning("分享卡头像缓存损坏，改走下载 user=%s", user_id, exc_info=True)
    url = resolve_avatar_url(user_id)
    if not url:
        return None
    try:
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        im = Image.open(BytesIO(r.content))
        im.load()
        rgb = im.convert("RGB")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(cache_path, format="PNG")
        return rgb
    except Exception:
        logger.warning("分享卡头像获取失败 user=%s", user_id, exc_info=True)
        return None


def build_share_png(record_id: int, user_id: str) -> bytes | None:
    """记录不存在/非本人/无本地文件/图损坏 → None（路由层转 404）。"""
    rec = fetch_checkin_by_id(record_id)
    if rec is None or rec.user_id != str(user_id) or rec.image_path is None:
        return None
    try:
        photo = Image.open(rec.image_path)
        photo.load()
    except Exception:
        logger.warning("分享卡打卡图读取失败 record=%s path=%s", record_id, rec.image_path, exc_info=True)
        return None

    db = DbManager()
    streaks = db.checkin.streaks(int(user_id))
    card = build_checkin_share_card(
        display_name=resolve_display_name(user_id),
        checkin_date=rec.checkin_date,
        photo=photo,
        avatar=_fetch_avatar(user_id),
        streak_days=streaks["current_daily"],
        total_images=db.checkin.count_images(int(user_id)),
    )
    buf = BytesIO()
    card.save(buf, format="PNG")
    return buf.getvalue()
