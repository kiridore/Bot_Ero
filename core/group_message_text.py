"""群聊 OneBot 11 message 段扁平化为可读文本（供统计、话题划分等复用）。"""

from __future__ import annotations

from core import context


def group_message_has_user_text(message, group_id: int) -> bool:
    """是否存在用户输入的纯文本段（非空 strip）。

    纯图片、仅转发、仅 @、仅表情等无 ``type=='text'`` 且有效正文的，返回 False，
    不参与话题划分 / 向量计算（避免用占位符串做 embedding）。
    """
    if isinstance(message, str):
        return bool(message.strip())
    if not isinstance(message, list):
        return False
    for seg in message:
        if not isinstance(seg, dict):
            continue
        if seg.get("type") != "text":
            continue
        data = seg.get("data") or {}
        raw = data.get("text", "")
        if isinstance(raw, str) and raw.strip():
            return True
        if raw is not None and not isinstance(raw, str) and str(raw).strip():
            return True
    return False


def flatten_group_message_content(message, group_id: int) -> str:
    """将 OneBot 11 message 数组转为可读文本（非文本段用占位符）。"""
    if isinstance(message, str):
        return message.strip()
    if not isinstance(message, list):
        return ""

    parts: list[str] = []
    for seg in message:
        if not isinstance(seg, dict):
            continue
        seg_type = seg.get("type")
        data = seg.get("data") or {}
        if seg_type == "text":
            parts.append(str(data.get("text", "")))
        elif seg_type == "image":
            parts.append("[图片]")
        elif seg_type == "at":
            qq = data.get("qq", "")
            parts.append(f"[@{qq}]")
        elif seg_type == "face":
            parts.append("[表情]")
        elif seg_type == "reply":
            reply_text = ""
            rid = data.get("id")
            if rid is not None:
                try:
                    ref = context.lookup_qq_msg(group_id, int(rid))
                    if ref is not None:
                        reply_text = ref.content
                except (TypeError, ValueError):
                    pass
            if not reply_text:
                t = data.get("text")
                if isinstance(t, str):
                    reply_text = t.strip()
                elif t is not None:
                    reply_text = str(t).strip()
            parts.append(f"[reply: {reply_text}]")
        elif seg_type == "forward":
            parts.append("[转发消息]")
        elif seg_type in ("json", "xml"):
            parts.append("[卡片消息]")
        elif seg_type in ("record", "video", "voice"):
            parts.append(f"[{seg_type}]")
        elif seg_type:
            parts.append(f"[{seg_type}]")

    return "".join(parts).strip()
