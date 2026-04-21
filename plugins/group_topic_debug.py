"""超级用户：本群话题划分调试输出。"""

from __future__ import annotations

from core.base import Plugin
from core.cq import text
from core.utils import register_plugin


def _one_line(s: str, max_len: int = 72) -> str:
    t = (s or "").replace("\r", " ").replace("\n", " ").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _format_topics_report(group_id: int, db) -> str:
    topics = db.list_group_chat_topics_for_debug(group_id)
    recent = db.list_recent_topic_assignments(group_id, limit=35)

    lines: list[str] = [
        f"【话题统计】群 {group_id}",
        f"Topic 总数: {len(topics)}",
        "---------- 各 Topic ----------",
    ]
    if not topics:
        lines.append("（尚无 topic 数据，多发几条群消息后再试）")
    else:
        for t in topics:
            tid = t["topic_id"]
            mc = t["message_count"]
            ar = t["assigned_rows"]
            ap = _one_line(t["anchor_preview"], 64)
            mismatch = " ⚠表内条数≠归属行" if mc != ar else ""
            lines.append(
                f"#{tid} | 质心计数={mc} | 归属消息行={ar}{mismatch}\n"
                f"  预览: {ap}\n"
                f"  更新: {t['updated_at']}"
            )

    lines.extend(["", "---------- 最近划分记录 ----------"])
    if not recent:
        lines.append("（无归属消息记录）")
    else:
        for r in recent:
            sim = r["similarity"]
            sim_s = "新建" if sim is None else f"{float(sim):.3f}"
            prev = _one_line(r["content_preview"], 48)
            lines.append(
                f"T{r['topic_id']} mid={r['message_id']} uid={r['user_id']} sim={sim_s}\n  {prev}"
            )

    body = "\n".join(lines)
    max_chars = 3200
    if len(body) > max_chars:
        body = body[: max_chars - 20] + "\n…(已截断，topic 过多时请缩小查询范围后续再加分页)"
    return body


@register_plugin
class GroupTopicDebugPlugin(Plugin):
    name = "group_topic_debug"
    description = "超级用户：本群话题划分统计（调试用）。"

    def match(self, message_type: str) -> bool:
        if message_type != "message":
            return False
        if not self.super_user() or not self.bot_event.is_group:
            return False
        return self.on_full_match_any("/话题统计", "/topic_topics")

    def handle(self) -> None:
        gid = self.bot_event.group_id
        if gid is None:
            return
        report = _format_topics_report(int(gid), self.dbmanager)
        self.api.send_forward_msg(text(report))
