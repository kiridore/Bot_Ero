from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw, ImageOps


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
