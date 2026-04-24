from core import context
from core.base import Plugin
from core.utils import register_plugin


def _flatten_message_content(message, group_id: int) -> str:
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


def _sender_display_name(bot_event) -> str:
    sender = bot_event.sender
    if isinstance(sender, dict):
        card = sender.get("card")
        nick = sender.get("nickname")
        name = (str(card).strip() if card else "") or (str(nick).strip() if nick else "")
        if name:
            return name
    uid = bot_event.user_id
    return str(uid) if uid is not None else ""


@register_plugin
class MessageActivityLogPlugin(Plugin):
    """每条消息触发：仅群聊写入内存缓冲并累计发言次数入库。"""

    name = "message_activity_log"
    description = "记录群聊最近消息（含正文摘要）与用户群环境累计发言次数（无指令触发）。"

    def match(self, message_type):
        if message_type != "message":
            return False
        return self.bot_event.post_type == "message"

    def handle(self):
        if not self.bot_event.is_group:
            return

        user_id = self.bot_event.user_id
        group_id = self.bot_event.group_id
        if user_id is None or group_id is None:
            return

        uid = int(user_id)
        gid = int(group_id)
        ts = self.bot_event.time
        ts_int = int(ts) if ts is not None else 0
        username = _sender_display_name(self.bot_event) or str(uid)
        body = _flatten_message_content(self.bot_event.message, gid)

        raw_mid = self.bot_event.message_id
        mid = int(raw_mid) if raw_mid is not None else -1

        dq = context.group_qq_message_history[gid]
        if dq.maxlen is not None and len(dq) >= dq.maxlen:
            old = dq.popleft()
            if old.message_id >= 0:
                context.qq_msg_by_group_message_id.pop((gid, old.message_id), None)

        msg = context.QQMsg(
            message_id=mid,
            user_id=uid,
            timestamp=ts_int,
            username=username,
            content=body,
        )
        dq.append(msg)
        if mid >= 0:
            context.qq_msg_by_group_message_id[(gid, mid)] = msg

        self.dbmanager.increment_user_total_message_count(uid, 1)
