from __future__ import annotations

import os
import sys
from typing import Union

from PIL import ImageFont

FontType = Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]


def load_font(size: int) -> FontType:
    """优先加载支持中文的系统字体，失败则回退到 PIL 默认位图字体。"""
    candidates: list[str] = []
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        candidates.extend(
            [
                os.path.join(windir, "Fonts", "msyh.ttc"),
                os.path.join(windir, "Fonts", "msyhbd.ttc"),
                os.path.join(windir, "Fonts", "simhei.ttf"),
            ]
        )
    candidates.extend(
        [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "msyh.ttc",
            "simhei.ttf",
            "arial.ttf",
        ]
    )
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def text_width(draw, text: str, font: FontType) -> float:
    if hasattr(draw, "textlength"):
        return float(draw.textlength(text, font=font))
    bbox = draw.textbbox((0, 0), text, font=font)
    return float(bbox[2] - bbox[0])
