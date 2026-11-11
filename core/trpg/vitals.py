"""跑团数值变动：HP / SAN / MP 的边界与格式化。

只做纯计算与文本，不做存储——写入由调用方（插件）通过 character_store 完成。
"""

from __future__ import annotations


def clamp(value: int, maximum: int) -> int:
    """截断到 0..maximum；maximum 小于 0 时按 0 处理。"""
    return max(0, min(int(value), max(int(maximum), 0)))


def parse_amount(text: str):
    """解析 `+3` / `-5` / `满`；无法识别返回 None。`满` 返回 "full"。"""
    raw = (text or "").strip()
    if not raw:
        return None
    if raw in ("满", "滿", "回满"):
        return "full"
    try:
        return int(raw)
    except ValueError:
        return None


def format_change(label: str, before: int, after: int, detail: str = "") -> str:
    """「HP 20 → 15（-5）」；detail 已是可读的算式（如 `-1d6=4`）时直接用它。"""
    if detail:
        return f"{label} {before} → {after}（{detail}）"
    delta = after - before
    sign = "+" if delta > 0 else ""
    return f"{label} {before} → {after}（{sign}{delta}）"
