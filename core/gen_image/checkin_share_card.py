"""打卡分享卡片：浅色卡 + contain 照片区。

极端宽高比（全景横图/超长截图）不裁剪：原图 contain 缩放进 1000×[240,1250]
照片区，空隙用放大模糊的同图背景铺满，成品宽恒 1080、总高有上界（spec D4/D5）。
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from core.config import NICKNAME
from core.gen_image.avatar_helper import raster_circle_avatar_on_rgb
from core.gen_image.fonts import load_font, text_width, truncate_text

CARD_BG = (245, 245, 245)
TEXT_MAIN = (45, 45, 45)
TEXT_DIM = (110, 110, 110)
INITIAL_BG = (225, 228, 233)

CARD_W = 1080
H_PAD = 40
V_PAD_TOP = 36
AVATAR_SIZE = 96
AVATAR_GAP = 20
NAME_SIZE = 40
DATE_SIZE = 28
STATS_SIZE = 30
FOOTER_SIZE = 26

PHOTO_BOX_W = CARD_W - H_PAD * 2  # 1000
PHOTO_BOX_H_MAX = 1250
PHOTO_BOX_H_MIN = 240
PHOTO_TOP_GAP = 24
NAME_DATE_GAP = 12
STATS_PAD_V = 28
FOOTER_PAD_TOP = 16
FOOTER_PAD_BOTTOM = 32

_WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
FOOTER_TEXT = f"Power by {NICKNAME}"


def _flatten_rgb(photo: Image.Image) -> Image.Image:
    """EXIF 摆正 + alpha 合成到白底，输出 RGB（spec D8）。"""
    img = ImageOps.exif_transpose(photo)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(base, rgba)
    return img.convert("RGB")


def _photo_block(photo: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """模糊放大同图铺底 + contain 前景居中（微信分享卡惯例）。"""
    bg = ImageOps.fit(photo, (box_w, box_h), method=Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(1.08)
    ratio = min(box_w / photo.width, box_h / photo.height)
    fg_size = (max(1, round(photo.width * ratio)), max(1, round(photo.height * ratio)))
    fg = photo.resize(fg_size, Image.Resampling.LANCZOS)
    bg.paste(fg, ((box_w - fg_size[0]) // 2, (box_h - fg_size[1]) // 2))
    return bg


def _format_date(checkin_date: str) -> str:
    try:
        d = dt.datetime.strptime(checkin_date, "%Y-%m-%d %H:%M:%S")
        return f"{d:%Y-%m-%d} {_WEEKDAYS[d.weekday()]} {d:%H:%M}"
    except ValueError:
        return checkin_date


def _initial_avatar_tile(name: str) -> Image.Image:
    tile = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), INITIAL_BG)
    font = load_font(44)
    draw = ImageDraw.Draw(tile)
    ch = (name or "?").strip()[:1] or "?"
    w = text_width(draw, ch, font)
    bbox = draw.textbbox((0, 0), ch, font=font)
    draw.text(((AVATAR_SIZE - w) / 2, (AVATAR_SIZE - bbox[3]) / 2), ch, font=font, fill=TEXT_MAIN)
    return tile


def build_checkin_share_card(
    *,
    display_name: str,
    checkin_date: str,
    photo: Image.Image,
    avatar: Optional[Image.Image] = None,
    streak_days: int = 0,
    total_images: int = 0,
) -> Image.Image:
    photo_rgb = _flatten_rgb(photo)

    font_name = load_font(NAME_SIZE)
    font_date = load_font(DATE_SIZE)
    font_stats = load_font(STATS_SIZE)
    font_footer = load_font(FOOTER_SIZE)
    probe = Image.new("RGB", (1, 1), CARD_BG)
    draw_probe = ImageDraw.Draw(probe)

    name = truncate_text(
        draw_probe,
        (display_name or "").strip() or "打卡用户",
        font_name,
        float(CARD_W - H_PAD * 2 - AVATAR_SIZE - AVATAR_GAP),
    )
    date_str = _format_date(checkin_date)

    name_h = draw_probe.textbbox((0, 0), "名字", font=font_name)[3]
    date_h = draw_probe.textbbox((0, 0), date_str, font=font_date)[3]
    header_h = max(AVATAR_SIZE, name_h + NAME_DATE_GAP + date_h)

    contain_h = round(PHOTO_BOX_W * photo_rgb.height / photo_rgb.width)
    box_h = min(max(contain_h, PHOTO_BOX_H_MIN), PHOTO_BOX_H_MAX)

    stats_line = f"连续打卡 {streak_days} 天 · 累计 {total_images} 张"
    stats_h = draw_probe.textbbox((0, 0), stats_line, font=font_stats)[3]
    footer_h = draw_probe.textbbox((0, 0), FOOTER_TEXT, font=font_footer)[3]

    total_h = (
        V_PAD_TOP
        + header_h
        + PHOTO_TOP_GAP
        + box_h
        + STATS_PAD_V
        + stats_h
        + STATS_PAD_V
        + FOOTER_PAD_TOP
        + footer_h
        + FOOTER_PAD_BOTTOM
    )

    card = Image.new("RGB", (CARD_W, total_h), CARD_BG)
    draw = ImageDraw.Draw(card)

    avatar_src = avatar if avatar is not None else _initial_avatar_tile(display_name)
    circ = raster_circle_avatar_on_rgb(avatar_src, AVATAR_SIZE, background=CARD_BG)
    card.paste(circ, (H_PAD, V_PAD_TOP))

    text_x = H_PAD + AVATAR_SIZE + AVATAR_GAP
    draw.text((text_x, V_PAD_TOP), name, font=font_name, fill=TEXT_MAIN)
    draw.text((text_x, V_PAD_TOP + name_h + NAME_DATE_GAP), date_str, font=font_date, fill=TEXT_DIM)

    photo_y = V_PAD_TOP + header_h + PHOTO_TOP_GAP
    card.paste(_photo_block(photo_rgb, PHOTO_BOX_W, box_h), (H_PAD, photo_y))

    stats_y = photo_y + box_h + STATS_PAD_V
    draw.text((H_PAD, stats_y), stats_line, font=font_stats, fill=TEXT_DIM)

    footer_w = text_width(draw, FOOTER_TEXT, font_footer)
    footer_y = stats_y + stats_h + STATS_PAD_V + FOOTER_PAD_TOP
    draw.text((CARD_W - H_PAD - footer_w, footer_y), FOOTER_TEXT, font=font_footer, fill=TEXT_DIM)

    return card
