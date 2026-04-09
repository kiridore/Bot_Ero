from openai import OpenAI
from collections import deque
import os

# =========================
#  LLM 无状态调用器
# =========================
class LLM:
    def __init__(self, api_key=None, base_url=None, model=None):
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
        base_url = base_url or "https://api.deepseek.com"
        model = model or "deepseek-chat"
        if not api_key:
            raise ValueError("Missing API key: set DEEPSEEK_API_KEY or LLM_API_KEY")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=False
        )
        return response.choices[0].message.content


# =========================
#  群聊天缓冲（用于总结）
# =========================
class GroupBuffer:
    def __init__(self, max_messages=200):
        self.buffer = deque(maxlen=max_messages)

    def add(self, user, content):
        self.buffer.append((user, content))

    def dump_text(self):
        return "\n".join([f"{u}: {c}" for u, c in self.buffer])


# =========================
#  多轮对话容器
# =========================
class Conversation:
    def __init__(self, max_rounds=6):
        self.history = []
        self.max_rounds = max_rounds

    def add_user(self, content):
        self.history.append({"role": "user", "content": content})

    def add_assistant(self, content):
        self.history.append({"role": "assistant", "content": content})

    def build(self, system_prompt):
        return [{"role": "system", "content": system_prompt}] + self.history

    def trim(self):
        self.history = self.history[-self.max_rounds * 2:]

    def clear(self):
        self.history = []


# =========================
#  状态机
# =========================
class BotState:
    def __init__(self):
        self.state = "IDLE"  # IDLE / ACTIVE / COOLDOWN
        self.active_user = None
        self.rounds = 0
        self.cooldown_until = 0


