"""系统插件：全群消息日志（独立库 message_log.db，永久保留）。"""

from __future__ import annotations

from datetime import datetime

from core.base import BOT_QQ, Plugin
from core.db.message_log import IMAGE_PLACEHOLDER, MessageLogManager
from core.utils import register_plugin


@register_plugin
class MessageLoggerPlugin(Plugin):
    name = "message_logger"
    description = "记录所有群消息到独立库，供周报聚合使用"

    def match(self, event_type: str = "message") -> bool:
        return event_type == "message" and self.bot_event.is_group

    @staticmethod
    def _sent_at(ts: int | float | None) -> str:
        if ts:
            try:
                return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError, OverflowError):
                pass
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def handle(self):
        try:
            user_id = self.bot_event.user_id
            group_id = self.bot_event.group_id
            if user_id is None or group_id is None:
                return
            if str(user_id) == BOT_QQ:
                return

            text_parts: list[str] = []
            has_image = 0
            reply_to_msg_id: int | None = None
            for seg in self.bot_event.message or []:
                if not isinstance(seg, dict):
                    continue
                seg_type = seg.get("type")
                data = seg.get("data", {}) or {}
                if seg_type == "text":
                    text_parts.append(str(data.get("text", "")))
                elif seg_type == "image":
                    has_image = 1
                elif seg_type == "reply":
                    raw_id = data.get("id")
                    if raw_id is not None and reply_to_msg_id is None:
                        try:
                            reply_to_msg_id = int(raw_id)
                        except (TypeError, ValueError):
                            pass
                # at/xml/json/face 等段落不进入 text
            msg_id = self.bot_event.message_id
            if msg_id is None:
                return
            msg_text = "".join(text_parts)
            if not msg_text and has_image:
                msg_text = IMAGE_PLACEHOLDER
            db = MessageLogManager()
            try:
                db.insert(
                    group_id=int(group_id),
                    user_id=int(user_id),
                    msg_id=int(msg_id),
                    sent_at=self._sent_at(self.bot_event.time),
                    text=msg_text,
                    has_image=has_image,
                    reply_to_msg_id=reply_to_msg_id,
                )
            finally:
                db.close()
        except Exception:
            from core.logger import logger

            logger.exception("消息日志写入失败")
