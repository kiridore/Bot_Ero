from __future__ import annotations

import os

from PIL import Image, ImageDraw

from core import context
from core.gen_image.fonts import load_font, text_width
from core.gen_image.models import PersonalRecordStats
from core.gen_image.year_heatmap import render_year_heatmap

CARD_BG = (245, 245, 245)
TEXT_MAIN = (45, 45, 45)
TEXT_DIM = (95, 95, 95)
SEPARATOR = (210, 210, 210)
H_PAD = 28
V_PAD_TOP = 22
LINE_GAP = 5
SECTION_GAP = 12
HEATMAP_GAP = 20
SEP_GAP = 10


def _stats_lines(stats: PersonalRecordStats) -> list[str]:
    return [
        "打卡记录",
        f"总次数({stats.year}): {stats.total_distinct_days}",
        f"打卡图({stats.year}): {stats.total_checkin_images}张",
        "------",
        f"当前连击（周）: {stats.current_weekly}",
        f"最长连击（周）: {stats.longest_weekly}",
        f"当前连击（日）: {stats.current_daily}",
        f"最长连击（日）: {stats.longest_daily}",
        f"点数: {stats.points}",
    ]


def _line_height(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def build_personal_record_image(
    year: int,
    day_checkin_count: list[int],
    stats: PersonalRecordStats,
) -> Image.Image:
    """拼接档案统计区与年度热力图。"""
    heatmap = render_year_heatmap(year, day_checkin_count, include_heading=False)

    font_head = load_font(22)
    font_body = load_font(15)
    probe = Image.new("RGB", (1, 1), CARD_BG)
    draw_probe = ImageDraw.Draw(probe)

    card_title = f"{stats.year} 年打卡档案"
    lines = _stats_lines(stats)

    inner_w = text_width(draw_probe, card_title, font_head)
    for line in lines:
        inner_w = max(inner_w, text_width(draw_probe, line, font_body))

    stats_width = int(inner_w + H_PAD * 2)
    width = max(stats_width, heatmap.width)

    head_h = _line_height(draw_probe, card_title, font_head)
    body_heights = [_line_height(draw_probe, ln, font_body) for ln in lines]
    body_block = sum(body_heights) + LINE_GAP * max(0, len(lines) - 1)
    text_block_end = V_PAD_TOP + head_h + SECTION_GAP + body_block
    sep_y = text_block_end + SEP_GAP
    stats_bottom = sep_y + SEP_GAP
    total_h = stats_bottom + HEATMAP_GAP + heatmap.height

    out = Image.new("RGB", (width, total_h), CARD_BG)
    draw = ImageDraw.Draw(out)

    tx = (width - text_width(draw, card_title, font_head)) / 2
    draw.text((tx, V_PAD_TOP), card_title, font=font_head, fill=TEXT_MAIN)
    y = V_PAD_TOP + head_h + SECTION_GAP
    lx = H_PAD
    for i, line in enumerate(lines):
        color = TEXT_DIM if line == "------" else TEXT_MAIN
        draw.text((lx, y), line, font=font_body, fill=color)
        y += body_heights[i] + (LINE_GAP if i < len(lines) - 1 else 0)

    draw.line([(H_PAD, sep_y), (width - H_PAD, sep_y)], fill=SEPARATOR, width=1)

    hx = (width - heatmap.width) // 2
    hy = stats_bottom + HEATMAP_GAP
    out.paste(heatmap, (hx, hy))
    return out


def save_personal_record_png(user_id: int, image_obj: Image.Image) -> str:
    out_dir = f"{context.python_data_path}/personal_records"
    os.makedirs(out_dir, exist_ok=True)
    path = f"{out_dir}/{user_id}_calendar_heatmap_monthly.png"
    image_obj.save(path)
    return path
