from __future__ import annotations

from core.gen_image.models import PersonalRecordStats
from core.gen_image.profile_card import build_personal_record_image, save_personal_record_png
from core.gen_image.year_heatmap import render_year_heatmap

__all__ = [
    "PersonalRecordStats",
    "build_personal_record_image",
    "gen_personal_record_card",
    "gen_year_heatmap",
    "render_year_heatmap",
    "save_personal_record_png",
]


def gen_personal_record_card(
    year: int,
    day_checkin_count: list[int],
    user_id: int,
    stats: PersonalRecordStats,
) -> str:
    """生成完整档案图并保存，返回写入的 PNG 路径（相对/与原先一致）。"""
    img = build_personal_record_image(year, day_checkin_count, stats)
    return save_personal_record_png(user_id, img)


def gen_year_heatmap(year: int, day_checkin_count: list[int], user_id: int) -> None:
    """兼容旧调用：仅热力图、无统计区。新代码请使用 gen_personal_record_card。"""
    img = render_year_heatmap(year, day_checkin_count, include_heading=True)
    save_personal_record_png(user_id, img)
