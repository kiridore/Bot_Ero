import os
import json

import core.context as context

STATUS_LABEL = {
    "done": "已完成",
    "skipped": "超时跳过",
    "missed": "未提交",
    "left": "已退出",
    "pending": "未完成",
}


def archive_dir(activity_id: int) -> str:
    return f"{context.python_data_path}/activity_archive/{activity_id}"


def image_path(activity_id: int, seq: int, n: int, ext: str) -> str:
    return f"{archive_dir(activity_id)}/imgs/img_{seq}_{n}{ext}"


def _member_block(m) -> list[str]:
    lines = [f"## {m['nickname']}（{m['user_id']}）"]
    if m["submitted_at"]:
        lines.append(f"- 提交时间：{m['submitted_at']}")
    lines.append(f"- 状态：{STATUS_LABEL.get(m['status'], m['status'])}")
    if m["status"] == "done":
        if m["content"]:
            lines.append("")
            lines.append(m["content"])
        try:
            imgs = json.loads(m["images"]) if m["images"] else []
        except (TypeError, ValueError):
            imgs = []
        for name in imgs:
            lines.append("")
            lines.append(f"![图片](imgs/{name})")
    lines.append("")
    return lines


def archive_activity(activity: dict, members: list[dict]):
    """写 meta.json + relay.md/match.md。图片已在提交时落盘，此处仅引用。"""
    d = archive_dir(activity["id"])
    os.makedirs(f"{d}/imgs", exist_ok=True)

    meta = {
        "id": activity["id"],
        "group_id": activity["group_id"],
        "type": activity["type"],
        "title": activity["title"],
        "theme": activity.get("theme"),
        "created_at": activity["created_at"],
        "finished_at": activity.get("finished_at"),
        "members": [
            {
                "user_id": m["user_id"],
                "nickname": m["nickname"],
                "seq": m["seq"],
                "status": m["status"],
                "submitted_at": m.get("submitted_at"),
            }
            for m in sorted(members, key=lambda x: x["seq"])
        ],
    }
    with open(f"{d}/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    is_match = activity["type"] == "match"
    lines = ["# 活动归档", ""]
    lines.append(f"- 标题：{activity['title']}")
    lines.append(f"- 类型：{'匹配下家' if is_match else '接龙'}")
    if activity.get("theme"):
        lines.append(f"- 主题：{activity['theme']}")
    lines.append(f"- 开始：{activity['created_at']}")
    lines.append(f"- 结束：{activity.get('finished_at')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    title = "作品" if is_match else "接力"
    for i, m in enumerate(sorted(members, key=lambda x: x["seq"]), 1):
        lines.append(f"## {title} {i}")
        lines += _member_block(m)

    md_name = "match.md" if is_match else "relay.md"
    with open(f"{d}/{md_name}", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
