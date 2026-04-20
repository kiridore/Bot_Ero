from __future__ import annotations


def github_green_level(val: int) -> tuple[int, int, int]:
    """按 GitHub 贡献图风格取色；val==-1 表示补卡日。"""
    if val == -1:
        return (255, 223, 186)
    if val == 0:
        return (235, 237, 240)
    colors = [
        (198, 228, 139),
        (123, 201, 111),
        (35, 154, 59),
        (25, 97, 39),
    ]
    if val - 1 > 3:
        return colors[3]
    return colors[val - 1]
