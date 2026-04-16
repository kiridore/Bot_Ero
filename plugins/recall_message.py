from core.base import Plugin
from core.cq import text


from core.utils import register_plugin
@register_plugin
class RecallMessagePlugin(Plugin):
    """回复自己发出的某条消息后发送 /撤回，由机器人代为撤回（不校验消息年龄，由协议与权限决定成败）。"""

    name = 'recall_message'
    description = '撤回用户自己回复指定的消息。'

    def match(self, message_type):
        if message_type != "message":
            return False
        if self.context.get("message_type") not in ("group", "private"):
            return False

        has_reply = False
        has_cmd = False
        for seg in self.context.get("message", []):
            if seg.get("type") == "reply":
                has_reply = True
            if seg.get("type") == "text":
                parts = seg.get("data", {}).get("text", "").strip().split(None, 1)
                if parts and parts[0] == "/撤回":
                    has_cmd = True
        return has_reply and has_cmd

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

    @staticmethod
    def _sender_user_id(msg_data: dict):
        if not msg_data:
            return None
        uid = msg_data.get("user_id")
        if uid is not None:
            return uid
        sender = msg_data.get("sender")
        if isinstance(sender, dict):
            return sender.get("user_id")
        return None

    def handle(self):
        reply_id = self._extract_reply_id()
        if reply_id is None:
            self.api.send_msg(text("请先回复要撤回的那条消息，再发送 /撤回"))
            return

        reply_data = self.api.get_msg(reply_id)
        if not reply_data:
            self.api.send_msg(text("获取被回复消息失败，可能太久远或已被删除喵~"))
            return

        sender_id = self._sender_user_id(reply_data)
        operator_id = self.context.get("user_id")
        if sender_id is None or operator_id is None:
            self.api.send_msg(text("无法确认消息发送者，撤回已取消喵~"))
            return
        if str(sender_id) != str(operator_id):
            self.api.send_msg(text("只能撤回你自己发送的消息喵~"))
            return

        if self.api.delete_msg(reply_id):
            return
        self.api.send_msg(text("撤回失败，可能没有权限或由协议限制喵~"))
