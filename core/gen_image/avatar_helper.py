from __future__ import annotations

from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageChops, ImageDraw, ImageOps

from core import context


def raster_circle_avatar_on_rgb(
    im: Image.Image,
    size: int,
    *,
    background: tuple[int, int, int] = (245, 245, 245),
) -> Image.Image:
    """将任意头像裁成圆形，合成到与档案卡一致的 RGB 底图上。"""
    fitted = ImageOps.fit(
        im.convert("RGBA"),
        (size, size),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    circle = Image.new("L", (size, size), 0)
    ImageDraw.Draw(circle).ellipse((0, 0, size - 1, size - 1), fill=255)
    alpha = fitted.split()[3]
    alpha = ImageChops.multiply(alpha, circle)
    fitted = fitted.copy()
    fitted.putalpha(alpha)
    out = Image.new("RGB", (size, size), background)
    out.paste(fitted, (0, 0), fitted.split()[3])
    return out


def fetch_avatar_cached(api, user_id) -> Image.Image | None:
    """尝试下载最新头像；成功则写入磁盘缓存，任何失败回退读缓存，再失败返回 None。"""
    cache_path = Path(context.python_data_path) / "avatar_cache" / f"{user_id}.png"
    url = ""
    try:
        url = api.get_qq_avatar(user_id) or ""
    except Exception:
        url = ""
    if url:
        try:
            if url.startswith("file://"):  # 测试用本地文件源；生产为 http(s)
                content = Path(url.removeprefix("file://")).read_bytes()
            else:
                r = requests.get(url, timeout=8)
                r.raise_for_status()
                content = r.content
            im = Image.open(BytesIO(content))
            im.load()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            im.convert("RGB").save(cache_path, format="PNG")
            return im
        except Exception:
            pass
    try:
        if cache_path.is_file():
            return Image.open(cache_path)
    except Exception:
        pass
    return None
