import requests
from datetime import datetime

import core.context as runtime_context
from core.base import Plugin
from core.cq import text


# TODO: 在这里填写你的 LLM 配置
LLM_API_KEY = ""
LLM_API_URL = "https://api.deepseek.com/chat/completions"
LLM_MODEL = "deepseek-chat"
SYSTEM_PROMPT = "你是小埃同学，一个简洁、友好的群聊助手。"

# 已有插件指令（避免被 LLM 误接管）
KNOWN_COMMANDS = {
    "/菜单", "/打卡", "/档案", "/本周打卡图", "/ALL", "/补卡", "/单日补卡", "/撤回打卡",
    "/抽奖", "/抽卡消费", "/排名", "/rank", "/称号", "/称号一览", "/今日发言统计",
    "/本周板油", "/群头衔", "/全体成员", "/超级补卡", "/数据备份", "/系统状态",
    "/更新", "/发金币", "/reload", "/占卜", "/贷款", "/总结聊天",
}


class LLMChatPlugin(Plugin):
    def _extract_text(self):
        message = self.context.get("message", [])
        parts = []
        for seg in message:
            if seg.get("type") == "text":
                parts.append(seg.get("data", {}).get("text", ""))
        return "".join(parts).strip()

    def _get_sender_name(self):
        sender = self.context.get("sender", {})
        return sender.get("card") or sender.get("nickname") or str(self.context.get("user_id", "未知用户"))

    def _get_event_time_str(self):
        ts = self.context.get("time")
        if isinstance(ts, int):
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _append_chat_record(self, msg):
        if not msg:
            return
        line = "{{{}}}({}):{}".format(self._get_sender_name(), self._get_event_time_str(), msg)
        runtime_context.recent_chat_records.append(line)
        if len(runtime_context.recent_chat_records) > 200:
            runtime_context.recent_chat_records = runtime_context.recent_chat_records[-200:]

    def _build_chat_history_text(self):
        return "\n".join(runtime_context.recent_chat_records[-200:])

    def match(self, message_type):
        if message_type != "message":
            return False
        msg = self._extract_text()
        if not msg:
            return False
        self._append_chat_record(msg)

        if msg == "/总结聊天":
            self._mode = "summarize"
            return True

        if msg.startswith("小埃同学"):
            self._mode = "chat"
            self._prompt_text = msg[len("小埃同学"):].strip()
            if self._prompt_text == "":
                self._prompt_text = "你好"
            return True

        if msg.startswith("/"):
            cmd = msg.split(" ")[0]
            if cmd not in KNOWN_COMMANDS:
                self._mode = "chat"
                self._prompt_text = msg
                return True

        return False

    def _call_llm(self, user_text):
        if not LLM_API_KEY.strip():
            return "LLM_API_KEY 还没有配置喵，请先在插件里填写。"

        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.7,
        }
        try:
            resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code != 200:
                return f"LLM 调用失败，HTTP {resp.status_code}"
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"LLM 调用异常：{e}"

    def handle(self):
        if getattr(self, "_mode", "") == "summarize":
            chat_blob = self._build_chat_history_text()
            prompt = (
                "请总结以下聊天记录的主要话题、结论、待办和情绪走势，"
                "输出为简洁中文要点。\n\n"
                + chat_blob
            )
            answer = self._call_llm(prompt)
            self.api.send_msg(text(answer))
            return

        answer = self._call_llm(self._prompt_text)
        self.api.send_msg(text(answer))
