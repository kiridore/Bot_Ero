from core.base import Plugin
from core.cq import text


class GroupEssencePlugin(Plugin):
    """回复某条群消息后发送 /加精 或 /删除精华，设置或移除群精华。"""

    def _command_kind(self):
        for seg in self.context.get("message", []):
            if seg.get("type") != "text":
                continue
            parts = seg.get("data", {}).get("text", "").strip().split(None, 1)
            if not parts:
                continue
            if parts[0] == "/加精":
                return "set"
            if parts[0] == "/删除精华":
                return "delete"
        return None

    def match(self, message_type):
        if message_type != "message":
            return False
        if self.context.get("message_type") != "group":
            return False

        has_reply = False
        for seg in self.context.get("message", []):
            if seg.get("type") == "reply":
                has_reply = True
                break
        return has_reply and self._command_kind() is not None

    def _extract_reply_id(self):
        for seg in self.context.get("message", []):
            if seg.get("type") != "reply":
                continue
            data = seg.get("data") or {}
            msg_id = data.get("id")
            if msg_id is None:
                continue
            try:
                return int(msg_id)
            except (TypeError, ValueError):
                return None
        return None

    def handle(self):
        kind = self._command_kind()
        reply_id = self._extract_reply_id()
        if reply_id is None:
            if kind == "delete":
                self.api.send_msg(text("请先回复要取消精华的那条消息，再发送 /删除精华"))
            else:
                self.api.send_msg(text("请先回复要加精的那条消息，再发送 /加精"))
            return

        if kind == "delete":
            if self.api.delete_essence_msg(reply_id):
                return
            self.api.send_msg(text("取消精华失败，可能该消息不在精华中或由协议限制喵~"))
            return

        if self.api.set_essence_msg(reply_id):
            self.api.send_msg(text("已设为群精华喵~"))
            return
        self.api.send_msg(text("加精失败，可能消息过旧、类型不支持或由协议限制喵~"))
