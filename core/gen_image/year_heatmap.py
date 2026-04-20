from __future__ import annotations

import datetime
import math
from typing import Sequence

from PIL import Image, ImageDraw

from core.gen_image.fonts import load_font, text_width
from core.gen_image.heatmap_colors import github_green_level

CELL = 18
PAD = 4
MONTH_PAD_X = 40
MONTH_PAD_Y = 40
BG = (245, 245, 245)
LEFT_MARGIN = 80
TOP_MARGIN = 60
MONTH_LABEL_OFFSET = 20
GRID_TOP_EXTRA = 50
GRID_TOP_EXTRA_COMPACT = 40


def _month_grids(year: int, data: Sequence[int]) -> dict[int, tuple[datetime.date, list[int]]]:
    months: dict[int, tuple[datetime.date, list[int]]] = {}
    idx = 0
    for month in range(1, 13):
        start = datetime.date(year, month, 1)
        if month != 12:
            month_days = (datetime.date(year, month + 1, 1) - start).days
        else:
            month_days = (datetime.date(year + 1, 1, 1) - start).days
        months[month] = (start, list(data[idx : idx + month_days]))
        idx += month_days
    return months


def _month_size(month_start: datetime.date, month_vals: list[int]) -> tuple[int, int]:
    first_wd = month_start.weekday()
    total_cells = len(month_vals) + first_wd
    weeks = math.ceil(total_cells / 7)
    w = weeks * (CELL + PAD) - PAD
    h = 7 * (CELL + PAD) - PAD
    return w, h


def render_year_heatmap(year: int, data: Sequence[int], *, include_heading: bool = True) -> Image.Image:
    """生成仅含年度热力图（12 个月网格）。include_heading=False 时用于嵌入档案卡片，省略顶部标题。"""
    top_margin = TOP_MARGIN
    grid_top = GRID_TOP_EXTRA
    if not include_heading:
        top_margin = 48
        grid_top = GRID_TOP_EXTRA_COMPACT

    months_data = _month_grids(year, data)
    month_widths: dict[int, int] = {}
    month_heights: dict[int, int] = {}
    for m, (ms, vals) in months_data.items():
        w, h = _month_size(ms, vals)
        month_widths[m] = w
        month_heights[m] = h

    cols, rows = 3, 4
    width = (
        sum(max(month_widths[m] for m in range(c + 1, 13, cols)) for c in range(cols))
        + (cols - 1) * MONTH_PAD_X
    )
    height = (
        sum(
            max(month_heights[m] for m in range(r * cols + 1, min(r * cols + cols + 1, 13)))
            for r in range(rows)
        )
        + (rows - 1) * MONTH_PAD_Y
    )
    width += LEFT_MARGIN
    height += top_margin

    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    font_month = load_font(16)
    font_title = load_font(20)

    if include_heading:
        title = f"{year} 打卡热力图"
        tw = text_width(draw, title, font_title)
        draw.text(((width - tw) / 2, 10), title, font=font_title, fill=(50, 50, 50))

    for month in range(1, 13):
        grid_col = (month - 1) % cols
        grid_row = (month - 1) // cols
        x0 = (
            sum(max(month_widths[m] for m in range(c + 1, 13, cols)) for c in range(grid_col))
            + grid_col * MONTH_PAD_X
            + 40
        )
        y0 = (
            sum(
                max(month_heights[m] for m in range(r * cols + 1, min(r * cols + cols + 1, 13)))
                for r in range(grid_row)
            )
            + grid_row * MONTH_PAD_Y
            + grid_top
        )

        month_start, month_vals = months_data[month]
        first_wd = month_start.weekday()
        month_label = f"{month}月"
        draw.text((x0, y0 - MONTH_LABEL_OFFSET), month_label, font=font_month, fill=(80, 80, 80))

        day_i = 0
        for week in range(math.ceil((len(month_vals) + first_wd) / 7)):
            for dow in range(7):
                if week == 0 and dow < first_wd:
                    continue
                if day_i >= len(month_vals):
                    break
                val = month_vals[day_i]
                color = github_green_level(val)
                rx = x0 + week * (CELL + PAD)
                ry = y0 + dow * (CELL + PAD)
                draw.rounded_rectangle(
                    [rx, ry, rx + CELL, ry + CELL],
                    radius=4,
                    fill=color,
                    outline=(220, 220, 220),
                )
                day_i += 1

    return image
