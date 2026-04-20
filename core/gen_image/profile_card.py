from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw

from core import context
from core.gen_image.avatar_helper import raster_circle_avatar_on_rgb
from core.gen_image.fonts import load_font, text_width, truncate_text
from core.gen_image.models import PersonalRecordStats
from core.gen_image.year_heatmap import render_year_heatmap

CARD_BG = (245, 245, 245)
TEXT_MAIN = (45, 45, 45)
TEXT_DIM = (110, 110, 110)
TEXT_VALUE = (55, 55, 55)
SEPARATOR = (210, 210, 210)
H_PAD = 28
V_PAD_TOP = 22
LINE_GAP = 6
SECTION_GAP = 12
HEATMAP_GAP = 20
SEP_GAP = 10

SECTION_TITLE_SIZE = 13
BODY_SIZE = 15
BLOCK_GAP = 14
AFTER_SECTION_TITLE = 5

AVATAR_SIZE = 56
AVATAR_GAP = 12
NAME_FONT_SIZE = 16
FOOTER_TEXT = "Power by 小埃同学"
FOOTER_FONT_SIZE = 12
FOOTER_PAD_TOP = 10
FOOTER_PAD_BOTTOM = 14


def _build_row_plan(stats: PersonalRecordStats) -> list[tuple]:
    """分区 + 留白分隔；不使用字符型分隔线。"""
    return [
        ("section", "打卡概览"),
        ("pad", AFTER_SECTION_TITLE),
        ("kv", f"总打卡天数（{stats.year}）", f"{stats.total_distinct_days} 天"),
        ("pad", LINE_GAP),
        ("kv", f"打卡图张数（{stats.year}）", f"{stats.total_checkin_images} 张"),
        ("pad", BLOCK_GAP),
        ("section", "连击统计"),
        ("pad", AFTER_SECTION_TITLE),
        (
            "plain",
            f"周连击    当前 {stats.current_weekly}    最长 {stats.longest_weekly}",
        ),
        ("pad", LINE_GAP),
        (
            "plain",
            f"日连击    当前 {stats.current_daily}    最长 {stats.longest_daily}",
        ),
        ("pad", BLOCK_GAP),
        ("kv", "点数", str(stats.points)),
    ]


def _line_height(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _row_heights(
    plan: list[tuple],
    draw_probe: ImageDraw.ImageDraw,
    font_section,
    font_body,
) -> list[int]:
    hs: list[int] = []
    for row in plan:
        k = row[0]
        if k == "section":
            hs.append(_line_height(draw_probe, row[1], font_section))
        elif k == "pad":
            hs.append(row[1])
        elif k == "kv":
            hs.append(
                max(
                    _line_height(draw_probe, row[1], font_body),
                    _line_height(draw_probe, row[2], font_body),
                )
            )
        elif k == "plain":
            hs.append(_line_height(draw_probe, row[1], font_body))
        else:
            hs.append(0)
    return hs


def _draw_plan(
    draw: ImageDraw.ImageDraw,
    width: int,
    y0: float,
    plan: list[tuple],
    heights: list[int],
    font_section,
    font_body,
) -> float:
    y = y0
    for row, h in zip(plan, heights):
        k = row[0]
        if k == "section":
            draw.text((H_PAD, y), row[1], font=font_section, fill=TEXT_DIM)
        elif k == "pad":
            pass
        elif k == "kv":
            left, right = row[1], row[2]
            draw.text((H_PAD, y), left, font=font_body, fill=TEXT_MAIN)
            rw = text_width(draw, right, font_body)
            draw.text((width - H_PAD - rw, y), right, font=font_body, fill=TEXT_VALUE)
        elif k == "plain":
            draw.text((H_PAD, y), row[1], font=font_body, fill=TEXT_MAIN)
        y += h
    return y


def build_personal_record_image(
    year: int,
    day_checkin_count: list[int],
    stats: PersonalRecordStats,
    *,
    user_display_name: Optional[str] = None,
    avatar: Optional[Image.Image] = None,
) -> Image.Image:
    """拼接档案统计区与年度热力图；可选左上角头像与昵称，底部版权信息。"""
    heatmap = render_year_heatmap(year, day_checkin_count, include_heading=False)

    font_head = load_font(22)
    font_body = load_font(BODY_SIZE)
    font_section = load_font(SECTION_TITLE_SIZE)
    font_name = load_font(NAME_FONT_SIZE)
    font_footer = load_font(FOOTER_FONT_SIZE)
    probe = Image.new("RGB", (1, 1), CARD_BG)
    draw_probe = ImageDraw.Draw(probe)

    card_title = f"{stats.year} 年打卡档案"
    plan = _build_row_plan(stats)

    inner_w = text_width(draw_probe, card_title, font_head)
    for row in plan:
        k = row[0]
        if k == "section":
            inner_w = max(inner_w, text_width(draw_probe, row[1], font_section))
        elif k == "kv":
            inner_w = max(
                inner_w,
                text_width(draw_probe, row[1], font_body)
                + text_width(draw_probe, row[2], font_body)
                + 24,
            )
        elif k == "plain":
            inner_w = max(inner_w, text_width(draw_probe, row[1], font_body))

    stats_width = int(inner_w + H_PAD * 2)
    width = max(stats_width, heatmap.width)

    name_str = (user_display_name or "").strip()
    show_avatar = avatar is not None
    show_name = bool(name_str)

    if show_avatar:
        header_before_title = AVATAR_SIZE + SECTION_GAP
    elif show_name:
        header_before_title = _line_height(draw_probe, name_str, font_name) + SECTION_GAP
    else:
        header_before_title = 0

    title_start = V_PAD_TOP + header_before_title

    head_h = _line_height(draw_probe, card_title, font_head)
    row_heights = _row_heights(plan, draw_probe, font_section, font_body)
    body_block = sum(row_heights)
    text_block_end = title_start + head_h + SECTION_GAP + body_block
    sep_y = text_block_end + SEP_GAP
    stats_bottom = sep_y + SEP_GAP

    footer_line_h = _line_height(draw_probe, FOOTER_TEXT, font_footer)
    footer_block = FOOTER_PAD_TOP + footer_line_h + FOOTER_PAD_BOTTOM
    total_h = stats_bottom + HEATMAP_GAP + heatmap.height + footer_block

    out = Image.new("RGB", (width, total_h), CARD_BG)
    draw = ImageDraw.Draw(out)

    if show_avatar:
        circ = raster_circle_avatar_on_rgb(avatar, AVATAR_SIZE, background=CARD_BG)
        out.paste(circ, (H_PAD, V_PAD_TOP))
        if show_name:
            name_max = width - (H_PAD + AVATAR_SIZE + AVATAR_GAP + H_PAD)
            name_draw = truncate_text(draw, name_str, font_name, float(name_max))
            ny = V_PAD_TOP + (AVATAR_SIZE - _line_height(draw, name_draw, font_name)) // 2
            draw.text((H_PAD + AVATAR_SIZE + AVATAR_GAP, ny), name_draw, font=font_name, fill=TEXT_MAIN)
    elif show_name:
        name_max = width - 2 * H_PAD
        name_draw = truncate_text(draw, name_str, font_name, float(name_max))
        draw.text((H_PAD, V_PAD_TOP), name_draw, font=font_name, fill=TEXT_MAIN)

    tx = (width - text_width(draw, card_title, font_head)) / 2
    draw.text((tx, title_start), card_title, font=font_head, fill=TEXT_MAIN)

    y_stats = float(title_start + head_h + SECTION_GAP)
    _draw_plan(draw, width, y_stats, plan, row_heights, font_section, font_body)

    draw.line([(H_PAD, sep_y), (width - H_PAD, sep_y)], fill=SEPARATOR, width=1)

    hx = (width - heatmap.width) // 2
    hy = stats_bottom + HEATMAP_GAP
    out.paste(heatmap, (hx, hy))

    fy = total_h - FOOTER_PAD_BOTTOM - footer_line_h
    ftw = text_width(draw, FOOTER_TEXT, font_footer)
    draw.text(((width - ftw) / 2, fy), FOOTER_TEXT, font=font_footer, fill=(150, 150, 150))

    return out


def save_personal_record_png(user_id: int, image_obj: Image.Image) -> str:
    out_dir = f"{context.python_data_path}/personal_records"
    os.makedirs(out_dir, exist_ok=True)
    path = f"{out_dir}/{user_id}_calendar_heatmap_monthly.png"
    image_obj.save(path)
    return path
