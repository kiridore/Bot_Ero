import os
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import core.context as runtime_context
from core.base import BOT_QQ, Plugin
from core.cq import text
from plugins.bot_menu_text import BOT_MENU_TEXT


# 环境变量支持：
# - DEEPSEEK_API_KEY / LLM_API_KEY
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY", "")
LLM_API_URL = "https://api.deepseek.com/chat/completions"
LLM_MODEL = "deepseek-chat"
CHAT_HISTORY_LIMIT = 300
DEFAULT_SYSTEM_PROMPT = "你是小埃同学，一个简洁、友好的群聊助手。"


def _load_system_prompt():
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "core",
        "llm",
        "prompts",
        "chat_prompt.md",
    )
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
            if prompt:
                return prompt
    except OSError:
        pass
    return DEFAULT_SYSTEM_PROMPT


SYSTEM_PROMPT = _load_system_prompt()

MENU_AND_COMMANDS_APPEND = (
    "\n\n---\n## 本机器人支持的指令（与群内发送 /菜单 时显示的内容一致）\n"
    + BOT_MENU_TEXT
)

FULL_SYSTEM_PROMPT = SYSTEM_PROMPT

# 已有插件指令（避免被 LLM 误接管）
KNOWN_COMMANDS = {
    "/菜单", "/打卡", "/档案", "/本周打卡图", "/ALL", "/补卡", "/单日补卡", "/撤回打卡",
    "/抽奖", "/抽卡消费", "/随机参考", "/排名", "/rank", "/称号", "/称号一览", "/今日发言统计",
    "/本周板油", "/群头衔", "/全体成员", "/超级补卡", "/数据备份", "/系统状态",
    "/更新", "/发金币", "/reload", "/占卜", "/贷款", "/总结聊天",
}


class LLMChatPlugin(Plugin):
    _http_session = None

    @classmethod
    def _get_http_session(cls):
        if cls._http_session is None:
            session = requests.Session()
            retry = Retry(
                total=3,
                connect=3,
                read=2,
                backoff_factor=1.0,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset(["POST"]),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            cls._http_session = session
        return cls._http_session

    def _extract_text(self):
        message = self.context.get("message", [])
        parts = []
        for seg in message:
            if seg.get("type") == "text":
                parts.append(seg.get("data", {}).get("text", ""))
        return "".join(parts).strip()

    def _has_at_bot(self):
        bot = str(BOT_QQ)
        for seg in self.context.get("message", []):
            if seg.get("type") == "at":
                qq = seg.get("data", {}).get("qq")
                if str(qq) == bot:
                    return True
        return False

    def _get_sender_name(self):
        sender = self.context.get("sender", {})
        return sender.get("card") or sender.get("nickname") or str(self.context.get("user_id", "未知用户"))

    def _get_sender_id(self):
        sender = self.context.get("sender", {})
        return sender.get("user_id")

    def _get_event_time_str(self):
        ts = self.context.get("time")
        if isinstance(ts, int):
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _append_chat_record(self, msg, user_name=None):
        if not msg:
            return
        sender_name = user_name or self._get_sender_name()
        sender_id = 3915014383 if user_name else self._get_sender_id()
        line = "[{}({})]({}): {}".format(sender_name, sender_id, self._get_event_time_str(), msg)
        runtime_context.recent_chat_records.append(line)
        if len(runtime_context.recent_chat_records) > CHAT_HISTORY_LIMIT:
            runtime_context.recent_chat_records = runtime_context.recent_chat_records[-CHAT_HISTORY_LIMIT:]

    def _build_chat_history_text(self):
        return "\n".join(runtime_context.recent_chat_records[-CHAT_HISTORY_LIMIT:])

    def match(self, message_type):
        if message_type != "message":
            return False
        msg = self._extract_text()
        at_bot = self._has_at_bot()
        if not msg and not at_bot:
            return False
        if msg:
            self._append_chat_record(msg)
        else:
            self._append_chat_record("[@小埃同学]")

        if msg == "/总结聊天":
            self._mode = "summarize"
            self._use_recent_context = True
            return True

        if msg.startswith("小埃"):
            self._mode = "chat"
            self._prompt_text = msg
            self._use_recent_context = True
            return True

        if msg.startswith("/"):
            cmd = msg.split(" ")[0]
            if cmd not in KNOWN_COMMANDS:
                self._mode = "chat"
                self._prompt_text = msg
                self._use_recent_context = True
                return True

        if at_bot:
            self._mode = "chat"
            self._prompt_text = msg if msg else ""
            self._use_recent_context = True
            return True

        return False

    def _call_llm(self, user_text, include_recent_chat=False):
        if not LLM_API_KEY.strip():
            return "未检测到 API Key，请先设置环境变量 DEEPSEEK_API_KEY（或 LLM_API_KEY）。"

        user_prompt = user_text
        if include_recent_chat:
            chat_history = self._build_chat_history_text()
            if chat_history:
                user_prompt = (
                    "以下是最近群聊记录（按时间排序）：\n"
                    f"{chat_history}\n\n"
                    "请结合上下文回复下面这句：\n"
                    f"{user_text}"
                )

        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": FULL_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 1.1,
        }
        print(
            "[LLM DEBUG] prompt:\n"
            f"[system]\n{FULL_SYSTEM_PROMPT}\n\n"
            f"[user]\n{user_prompt}\n"
            "------------------------------"
        )
        try:
            resp = self._get_http_session().post(
                LLM_API_URL,
                headers=headers,
                json=payload,
                timeout=(10, 60),
            )
            if resp.status_code != 200:
                return f"LLM 调用失败，HTTP {resp.status_code}：{resp.text[:200]}"
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.ConnectTimeout:
            return "LLM 连接超时（无法连到 DeepSeek）。请检查网络/代理后重试。"
        except requests.exceptions.ReadTimeout:
            return "LLM 响应超时（服务处理过慢）。请稍后重试。"
        except requests.exceptions.RequestException as e:
            return f"LLM 网络异常：{e}"
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
            self._append_chat_record(answer, user_name="小埃同学")
            return

        answer = self._call_llm(
            self._prompt_text,
            include_recent_chat=getattr(self, "_use_recent_context", False),
        )
        self.api.send_msg(text(answer))
        self._append_chat_record(answer, user_name="小埃同学")
