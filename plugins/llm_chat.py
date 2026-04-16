from core.base import BOT_QQ, NICKNAME, Plugin
from core.cq import reply, text
from core.llm.llm import chat_assistant_reply


from core.utils import register_plugin
# @register_plugin
class LLMChatPlugin(Plugin):
    name = 'llm_chat'
    description = '在被提及时调用 LLM 生成回复。'

    def _extract_text(self) -> str:
        parts: list[str] = []
        for seg in self.context.get("message", []):
            if seg.get("type") == "text":
                parts.append(seg.get("data", {}).get("text", ""))
        return "".join(parts).strip()

    def _has_at_bot(self) -> bool:
        bot = str(BOT_QQ)
        for seg in self.context.get("message", []):
            if seg.get("type") == "at":
                qq = seg.get("data", {}).get("qq")
                if str(qq) == bot:
                    return True
        return False

    def _should_reply(self, msg: str) -> bool:
        if self._has_at_bot():
            return True
        if NICKNAME and NICKNAME in msg:
            return True
        if "小埃" in msg:
            return True
        return False

    def match(self, message_type):
        if message_type != "message":
            return False
        msg = self._extract_text()
        if not self._should_reply(msg):
            return False
        self._user_text = msg
        return True

    def handle(self):
        user_content = (getattr(self, "_user_text", None) or "").strip()
        if not user_content and self._has_at_bot():
            user_content = "你好"

        answer = chat_assistant_reply(user_content)

        msg_id = self.context.get("message_id")
        msg_id_str = str(msg_id).strip() if msg_id is not None else ""
        if msg_id_str and msg_id_str != "0":
            self.api.send_msg(reply(msg_id_str), text(answer))
        else:
            self.api.send_msg(text(answer))
