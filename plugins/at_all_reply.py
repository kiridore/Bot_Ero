from core.base import Plugin
from core.cq import at_all, text


from core.utils import register_plugin
@register_plugin
class AtAllReplyPlugin(Plugin):
    name = 'at_all_reply'
    description = '回复指定消息并艾特全体成员转发内容。'

    COMMAND = "/全体成员"

    def match(self, message_type):
        if message_type != "message":
            return False
        if not self.context.get("group_id"):
            return False

        has_reply = False
        has_command = False
        for seg in self.context.get("message", []):
            if seg.get("type") == "reply":
                has_reply = True
            if seg.get("type") == "text":
                if seg.get("data", {}).get("text", "").strip() == self.COMMAND:
                    has_command = True
        return has_reply and has_command

    def _extract_reply_id(self):
        for seg in self.context.get("message", []):
            if seg.get("type") == "reply":
                msg_id = seg.get("data", {}).get("id")
                if msg_id is not None:
                    return int(msg_id)
        return None

    def _flatten_message_text(self, message):
        if isinstance(message, str):
            return message.strip()
        if not isinstance(message, list):
            return ""

        texts = []
        for seg in message:
            seg_type = seg.get("type")
            if seg_type == "text":
                texts.append(seg.get("data", {}).get("text", ""))
            elif seg_type == "image":
                texts.append("[图片]")
            elif seg_type == "at":
                qq = seg.get("data", {}).get("qq", "")
                texts.append(f"[@{qq}]")
        return "".join(texts).strip()

    def handle(self):
        reply_id = self._extract_reply_id()
        if reply_id is None:
            self.api.send_msg(text("请先回复一条消息，再发送 /全体成员"))
            return

        reply_data = self.api.get_msg(reply_id)
        if not reply_data:
            self.api.send_msg(text("获取被回复消息失败了喵~"))
            return

        reply_text = self._flatten_message_text(reply_data.get("message"))
        if not reply_text:
            reply_text = reply_data.get("raw_message", "").strip()
        if not reply_text:
            reply_text = "（这条消息没有可展示的文本内容）"

        self.api.send_msg(at_all(), text(" "), text(reply_text))
