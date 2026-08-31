from __future__ import annotations

import glob
import os
import time
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw

from core import context
from core.gen_image.avatar_helper import raster_circle_avatar_on_rgb
from core.gen_image.fonts import load_font, text_width, truncate_text

CARD_BG = (245, 245, 245)
TEXT_MAIN = (45, 45, 45)
TEXT_DIM = (110, 110, 110)
TEXT_VALUE = (55, 55, 55)
SEPARATOR = (225, 225, 225)
AVATAR_PLACEHOLDER = (215, 215, 215)

CARD_WIDTH = 620
H_PAD = 28
V_PAD_TOP = 24
TITLE_SIZE = 22
SUBTITLE_SIZE = 14
SUBTITLE_GAP = 6
LIST_TOP_GAP = 18
ROW_GAP = 10
AVATAR_SIZE = 40
RANK_COL_W = 36
ROW_TEXT_GAP = 12
RANK_SIZE = 16
NAME_SIZE = 16
DETAIL_SIZE = 14
FOOTER_SIZE = 12
FOOTER_TEXT = "Power by 小埃同学"
FOOTER_PAD_TOP = 16
FOOTER_PAD_BOTTOM = 14
# 前三名奖牌色：金银铜，其余主文字色
MEDAL_COLORS = {1: (196, 154, 34), 2: (130, 130, 134), 3: (176, 115, 57)}


@dataclass(frozen=True)
class RankRow:
    rank: int
    name: str
    detail: str
    avatar: Optional[Image.Image] = None


def _line_height(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def render_rank_card(
    title: str,
    subtitle: str,
    rows: list[RankRow],
    footer: str = FOOTER_TEXT,
) -> Image.Image:
    """标题 + 副标题 + 若干行（排名/头像/名称/右侧 detail）+ 页脚的自适应竖卡。"""
    font_title = load_font(TITLE_SIZE)
    font_subtitle = load_font(SUBTITLE_SIZE)
    font_rank = load_font(RANK_SIZE)
    font_name = load_font(NAME_SIZE)
    font_detail = load_font(DETAIL_SIZE)
    font_footer = load_font(FOOTER_SIZE)

    probe = Image.new("RGB", (1, 1), CARD_BG)
    draw_probe = ImageDraw.Draw(probe)

    title_h = _line_height(draw_probe, title, font_title)
    subtitle_h = _line_height(draw_probe, subtitle, font_subtitle) if subtitle else 0
    row_h = max(AVATAR_SIZE, _line_height(draw_probe, "样", font_name))
    footer_h = _line_height(draw_probe, footer, font_footer)

    content_w = CARD_WIDTH - H_PAD * 2
    body_height = 0
    if rows:
        body_height = len(rows) * row_h + (len(rows) - 1) * ROW_GAP

    height = (
        V_PAD_TOP + title_h + SUBTITLE_GAP + subtitle_h + LIST_TOP_GAP
        + body_height + FOOTER_PAD_TOP + footer_h + FOOTER_PAD_BOTTOM
    )

    img = Image.new("RGB", (CARD_WIDTH, int(height)), CARD_BG)
    draw = ImageDraw.Draw(img)

    y = V_PAD_TOP
    draw.text((H_PAD, y), title, font=font_title, fill=TEXT_MAIN)
    y += title_h + SUBTITLE_GAP
    if subtitle:
        draw.text((H_PAD, y), subtitle, font=font_subtitle, fill=TEXT_DIM)
    y += subtitle_h + LIST_TOP_GAP

    for i, row in enumerate(rows):
        cy = y + row_h / 2  # 行垂直中线
        x = H_PAD
        # 排名列（右对齐数字，前三奖牌色）
        rank_str = str(row.rank)
        rank_w = text_width(draw, rank_str, font_rank)
        rank_color = MEDAL_COLORS.get(row.rank, TEXT_VALUE)
        draw.text((x + RANK_COL_W - rank_w, cy - _line_height(draw, rank_str, font_rank) / 2),
                  rank_str, font=font_rank, fill=rank_color)
        x += RANK_COL_W + ROW_TEXT_GAP
        # 头像（无则灰圆占位）
        if row.avatar is not None:
            avatar_im = raster_circle_avatar_on_rgb(row.avatar, AVATAR_SIZE, background=CARD_BG)
            img.paste(avatar_im, (int(x), int(cy - AVATAR_SIZE / 2)))
        else:
            draw.ellipse(
                (x, cy - AVATAR_SIZE / 2, x + AVATAR_SIZE, cy + AVATAR_SIZE),
                fill=AVATAR_PLACEHOLDER,
            )
        x += AVATAR_SIZE + ROW_TEXT_GAP
        # detail 右对齐，name 在剩余宽度内截断
        detail_w = text_width(draw, row.detail, font_detail)
        draw.text((CARD_WIDTH - H_PAD - detail_w, cy - _line_height(draw, row.detail, font_detail) / 2),
                  row.detail, font=font_detail, fill=TEXT_DIM)
        name_max = content_w - RANK_COL_W - ROW_TEXT_GAP - AVATAR_SIZE - ROW_TEXT_GAP - detail_w - 8
        name_str = truncate_text(draw, row.name, font_name, max(60, name_max))
        draw.text((x, cy - _line_height(draw, name_str, font_name) / 2),
                  name_str, font=font_name, fill=TEXT_MAIN)
        y += row_h
        if i < len(rows) - 1:
            draw.line((H_PAD, y + ROW_GAP / 2, CARD_WIDTH - H_PAD, y + ROW_GAP / 2),
                      fill=SEPARATOR, width=1)
            y += ROW_GAP

    footer_w = text_width(draw, footer, font_footer)
    draw.text(((CARD_WIDTH - footer_w) / 2, height - FOOTER_PAD_BOTTOM - footer_h),
              footer, font=font_footer, fill=TEXT_DIM)
    return img


def save_rank_png(kind: str, image_obj: Image.Image) -> tuple[str, str]:
    """写入时间戳唯一文件并清理同 kind 旧图；返回 (python 侧路径, OneBot 发送用路径)。

    文件名必须唯一：cq.image() 的 cache 参数是空操作，固定名会被 QQ 端按文件名缓存旧图。
    """
    out_dir = f"{context.python_data_path}/rank_cards"
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(f"{out_dir}/{kind}_*.png"):
        try:
            os.remove(old)
        except OSError:
            pass
    fname = f"{kind}_{int(time.time() * 1000)}.png"
    path = f"{out_dir}/{fname}"
    image_obj.save(path)
    return path, f"{context.llonebot_data_path}/rank_cards/{fname}"
