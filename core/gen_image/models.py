from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonalRecordStats:
    """与 /档案 文本展示一致的一组统计，用于绘制档案卡片。"""

    year: int
    total_distinct_days: int
    total_checkin_images: int
    current_weekly: int
    longest_weekly: int
    current_daily: int
    longest_daily: int
    points: int
