"""分享卡头像：磁盘缓存 + 同源代理（DOM 转图需同源，QQ CDN 无 CORS 头）。"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from core import context
from core.onebot_client import resolve_avatar_url

logger = logging.getLogger(__name__)


def cached_avatar_path(user_id: str) -> Path | None:
    """命中/写满 avatar_cache/share_{uid}.png 并返回路径；任何失败返回 None。"""
    cache_path = Path(context.python_data_path) / "avatar_cache" / f"share_{user_id}.png"
    if cache_path.is_file():
        try:
            with Image.open(cache_path) as im:
                im.load()
            return cache_path
        except Exception:
            cache_path.unlink(missing_ok=True)  # 损坏缓存：删掉走重下
    url = resolve_avatar_url(user_id)
    if not url:
        return None
    try:
        if url.startswith("file://"):  # 测试钩子，同 avatar_helper 先例
            content = Path(url.removeprefix("file://")).read_bytes()
        else:
            r = requests.get(url, timeout=6)
            r.raise_for_status()
            content = r.content
        im = Image.open(BytesIO(content))
        im.load()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # ponytail: 固定名并发冷写可交错，靠命中校验自愈兜底
        tmp = cache_path.with_suffix(".tmp")  # 原子写：先落 .tmp 再替换
        im.convert("RGB").save(tmp, format="PNG")
        tmp.replace(cache_path)
        return cache_path
    except Exception:
        logger.warning("分享卡头像获取失败 user=%s", user_id, exc_info=True)
        return None
