import os
import json
import threading
import queue
import requests
from datetime import datetime
from typing import Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import core.context as runtime_context
from core.logger import logger
from core.base import BOT_QQ, Plugin
from core.cq import text, reply
from plugins.bot_menu_text import BOT_MENU_TEXT


# 环境变量支持：
# - DEEPSEEK_API_KEY / LLM_API_KEY
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY", "")
LLM_API_URL = "https://api.deepseek.com/chat/completions"
LLM_MODEL = "deepseek-reasoner"
CHAT_HISTORY_LIMIT = 300
DEFAULT_SYSTEM_PROMPT = "你是小埃同学，一个简洁、友好的群聊助手。"
MEMORY_DIR_NAME = "llm_memory"
MEMORY_SUMMARY_TRIGGER_EVERY = 300
MEMORY_USER_TRIGGER_EVERY = 50
GROUP_SUMMARY_MAX_CHARS = 1800


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
    _memory_lock = threading.Lock()
    _memory_job_q = queue.Queue()
    _memory_worker_started = False

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

    @staticmethod
    def _get_memory_dir():
        base_dir = getattr(runtime_context, "python_data_path", "./server_data") or "./server_data"
        mem_dir = os.path.join(base_dir, MEMORY_DIR_NAME)
        os.makedirs(mem_dir, exist_ok=True)
        return mem_dir

    @classmethod
    def _group_memory_path(cls, group_id: int):
        return os.path.join(cls._get_memory_dir(), f"group_{int(group_id)}.json")

    @classmethod
    def _load_group_memory(cls, group_id: int):
        path = cls._group_memory_path(group_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"[llm_memory] failed to load {path}: {e}")
        return {
            "group_id": int(group_id),
            "last_300": [],
            "summary_buffer": [],
            "since_last_summary": 0,
            "summary_pending": False,
            "group_summary": "",
            "group_summary_updated_at": "",
            "user_counters": {},  # user_id -> count since last profile update
            "user_pending": {},   # user_id -> bool
            "user_profiles": {},  # user_id -> {name, profile, updated_at}
        }

    @classmethod
    def _save_group_memory(cls, group_id: int, data: dict):
        path = cls._group_memory_path(group_id)
        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception as e:
            logger.warning(f"[llm_memory] failed to save {path}: {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def _get_group_id(self) -> int:
        gid = self.context.get("group_id")
        if not gid:
            gid = self.context.get("default_group_id")
        try:
            return int(gid) if gid else 0
        except Exception:
            return 0

    @classmethod
    def _ensure_memory_worker(cls):
        if cls._memory_worker_started:
            return
        cls._memory_worker_started = True
        t = threading.Thread(target=cls._memory_worker_loop, daemon=True)
        t.start()

    @classmethod
    def _memory_worker_loop(cls):
        while True:
            job = cls._memory_job_q.get()
            try:
                if not isinstance(job, dict):
                    continue
                job_type = job.get("type")
                if job_type == "summarize_300":
                    cls._process_summarize_job(job)
                elif job_type == "user_profile_50":
                    cls._process_user_profile_job(job)
            except Exception as e:
                logger.warning(f"[llm_memory] worker job failed: {e}")
            finally:
                try:
                    cls._memory_job_q.task_done()
                except Exception:
                    pass

    def _extract_text(self):
        message = self.context.get("message", [])
        parts = []
        for seg in message:
            if seg.get("type") == "text":
                parts.append(seg.get("data", {}).get("text", ""))
            elif seg.get("type") == "at":
                parts.append("[{}:{}]".format(seg.get("type", "unknow"), seg.get("data", {}).get("qq", "unkonw_qq")))
            elif seg.get("type") == "repley":
                parts.append("[{}:{}]".format(seg.get("type", "unknow"), seg.get("data", {}).get("id", "unknow_msg_id")))
            else:
                parts.append("[{}]".format(seg.get("type", "unknow")))

        return "".join(parts).strip()

    def _persist_message(self, msg: str, user_name: Optional[str] = None, user_id: Optional[int] = None):
        if not msg:
            return
        group_id = self._get_group_id()
        if not group_id:
            return

        sender_name = user_name or self._get_sender_name()
        sender_id = int(user_id) if user_id is not None else (3915014383 if user_name else self._get_sender_id())
        ts = self.context.get("time")
        if not isinstance(ts, int):
            ts = int(datetime.now().timestamp())
        msg_id = self.context.get("message_id")

        record = {
            "user_id": int(sender_id) if sender_id is not None else 0,
            "user_name": str(sender_name),
            "ts": int(ts),
            "text": str(msg),
            "message_id": int(msg_id) if isinstance(msg_id, int) else 0,
        }

        self._ensure_memory_worker()

        with self._memory_lock:
            mem = self._load_group_memory(group_id)
            last_300 = mem.get("last_300") or []
            if not isinstance(last_300, list):
                last_300 = []
            last_300.append(record)
            if len(last_300) > CHAT_HISTORY_LIMIT:
                last_300 = last_300[-CHAT_HISTORY_LIMIT:]
            mem["last_300"] = last_300

            summary_buffer = mem.get("summary_buffer") or []
            if not isinstance(summary_buffer, list):
                summary_buffer = []
            summary_buffer.append(record)
            if len(summary_buffer) > MEMORY_SUMMARY_TRIGGER_EVERY:
                summary_buffer = summary_buffer[-MEMORY_SUMMARY_TRIGGER_EVERY:]
            mem["summary_buffer"] = summary_buffer

            mem["since_last_summary"] = int(mem.get("since_last_summary") or 0) + 1

            # 只累计真实用户（排除机器人）
            if sender_id and str(sender_id) != str(BOT_QQ):
                uid_key = str(int(sender_id))
                user_counters = mem.get("user_counters") or {}
                if not isinstance(user_counters, dict):
                    user_counters = {}
                user_counters[uid_key] = int(user_counters.get(uid_key) or 0) + 1
                mem["user_counters"] = user_counters

            # 触发群摘要（每 300 条）
            if (
                int(mem.get("since_last_summary") or 0) >= MEMORY_SUMMARY_TRIGGER_EVERY
                and not bool(mem.get("summary_pending"))
                and len(last_300) >= CHAT_HISTORY_LIMIT
            ):
                mem["summary_pending"] = True
                mem["since_last_summary"] = 0
                snapshot = list((mem.get("summary_buffer") or [])[-MEMORY_SUMMARY_TRIGGER_EVERY:])
                mem["summary_buffer"] = []
                self._memory_job_q.put(
                    {
                        "type": "summarize_300",
                        "group_id": int(group_id),
                        "prev_summary": str(mem.get("group_summary") or ""),
                        "messages": snapshot,
                    }
                )

            # 触发成员画像（累计 50 条）
            if sender_id and str(sender_id) != str(BOT_QQ):
                uid_key = str(int(sender_id))
                user_counters = mem.get("user_counters") or {}
                user_pending = mem.get("user_pending") or {}
                if not isinstance(user_pending, dict):
                    user_pending = {}
                if int(user_counters.get(uid_key) or 0) >= MEMORY_USER_TRIGGER_EVERY and not bool(user_pending.get(uid_key)):
                    user_pending[uid_key] = True
                    mem["user_pending"] = user_pending

                    # 从最近 300 条里筛选该成员最近发言
                    selected = []
                    for r in reversed(last_300):
                        if str(r.get("user_id")) == uid_key:
                            selected.append(r)
                            if len(selected) >= MEMORY_USER_TRIGGER_EVERY:
                                break
                    selected.reverse()
                    if selected:
                        self._memory_job_q.put(
                            {
                                "type": "user_profile_50",
                                "group_id": int(group_id),
                                "user_id": int(sender_id),
                                "user_name": str(sender_name),
                                "messages": selected,
                            }
                        )

            self._save_group_memory(group_id, mem)

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
        msg_id = self.context.get("message_id")
        if not isinstance(msg_id, int):
            msg_id = 0
        line = "[{}({})]({}): {} [message_id={}]".format(
            sender_name,
            sender_id,
            self._get_event_time_str(),
            msg,
            msg_id,
        )
        runtime_context.recent_chat_records.append(line)
        if len(runtime_context.recent_chat_records) > CHAT_HISTORY_LIMIT:
            runtime_context.recent_chat_records = runtime_context.recent_chat_records[-CHAT_HISTORY_LIMIT:]
        # 新持久化记忆：按群落盘 + 触发后台摘要/画像
        try:
            self._persist_message(msg, user_name=user_name, user_id=sender_id)
        except Exception as e:
            logger.warning(f"[llm_memory] persist_message failed: {e}")

    def _build_chat_history_text(self):
        return "\n".join(runtime_context.recent_chat_records[-CHAT_HISTORY_LIMIT:])

    @staticmethod
    def _build_reply_with_trigger(trigger_text: str, answer_text: str):
        trigger = (trigger_text or "").strip() or "（空消息/@触发）"
        answer = (answer_text or "").strip()
        return f"唤起信息：{trigger}\n\n{answer}"

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

        if ("小埃同学" in msg) or ("小埃" in msg):
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

        dynamic_system_prompt = FULL_SYSTEM_PROMPT
        try:
            group_id = self._get_group_id()
            uid = self._get_sender_id()
            dynamic_system_prompt = self._build_dynamic_system_prompt(group_id, uid)
        except Exception:
            pass

        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": dynamic_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 1.3,
        }
        # print(
        #     "[LLM DEBUG] prompt:\n"
        #     f"[system]\n{FULL_SYSTEM_PROMPT}\n\n"
        #     f"[user]\n{user_prompt}\n"
        #     "------------------------------"
        # )
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

    @classmethod
    def _call_llm_api(cls, system_prompt: str, user_prompt: str, temperature: float = 0.7):
        if not LLM_API_KEY.strip():
            raise RuntimeError("missing api key")
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(temperature),
        }
        resp = cls._get_http_session().post(
            LLM_API_URL,
            headers=headers,
            json=payload,
            timeout=(10, 120),
        )
        if resp.status_code != 200:
            raise RuntimeError(f"http {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def _build_dynamic_system_prompt(self, group_id: int, user_id: Optional[int]):
        if not group_id:
            return FULL_SYSTEM_PROMPT
        with self._memory_lock:
            mem = self._load_group_memory(group_id)
        group_summary = (mem.get("group_summary") or "").strip()

        profile_txt = ""
        if user_id:
            profiles = mem.get("user_profiles") or {}
            p = profiles.get(str(int(user_id))) if isinstance(profiles, dict) else None
            if isinstance(p, dict):
                profile_txt = (p.get("profile") or "").strip()

        def _clip(s: str, n: int):
            s = s or ""
            return s if len(s) <= n else s[:n] + "…"

        if not group_summary and not profile_txt:
            return FULL_SYSTEM_PROMPT

        memory_block = "\n\n---\n"
        if group_summary:
            memory_block += "## 群组实时记忆（群摘要）\n" + _clip(group_summary, 1200) + "\n"
        if profile_txt:
            memory_block += "\n## 当前对话者画像（独立记忆）\n" + _clip(profile_txt, 800) + "\n"

        return FULL_SYSTEM_PROMPT + memory_block

    @staticmethod
    def _memory_extract_prompt_300_incremental(prev_summary: str, raw_dialogue: str):
        prev_summary = (prev_summary or "").strip()
        prev_block = prev_summary if prev_summary else "（暂无历史摘要）"
        return (
            "# Role: 记忆沉淀处理器\n"
            "## Task\n"
            "基于已有群摘要与新增的 300 条原始对话，生成增量更新后的后端记忆：\n\n"
            "### 已有群摘要（上一版）\n"
            + prev_block
            + "\n\n"
            "### Part 1: 群组事件摘要 (Group History)\n"
            "- 你需要在已有摘要基础上增量更新，而不是从零重写。\n"
            "- 提取新增对话中的核心事件（如：谁发起了挑战、群内气氛变化、重要的梗）。\n"
            "- 语气客观简练。\n\n"
            "### Part 2: 成员增量画像 (User Specific)\n"
            "- 识别活跃成员：[用户名1], [用户名2]...\n"
            "- 为每个活跃成员更新以下标签：\n"
            "  - [情感连接]: 对小埃是友好、吐槽还是冷淡。\n"
            "  - [成员关系]: 他和谁联系比较多，他们处于什么状态。\n\n"
            "  - [个人信息]: 他是谁，被怎么称呼，提到的生活细节（如“在加班”、“明天考试”）。\n\n"
            "### 输出格式要求\n"
            "请严格输出 JSON（不要代码块），形如：\n"
            "{\n"
            '  "group_history": "...",\n'
            '  "user_specific": [\n'
            '    {"user_id": 123, "user_name": "xxx", "emotion_connection": "...", "personal_info": "..."}\n'
            "  ]\n"
            "}\n\n"
            "以下是新增原始对话（按时间顺序）：\n"
            + raw_dialogue
        )

    @staticmethod
    def _memory_extract_prompt_user(user_name: str, user_id: int, raw_dialogue: str, existing_profile: str):
        existing_profile = (existing_profile or "").strip()
        prefix = ""
        if existing_profile:
            prefix = f"该成员当前已有画像（供你增量更新，不要复述无关内容）：\n{existing_profile}\n\n"
        return (
            "# Role: 记忆沉淀处理器\n"
            "## Task\n"
            f"阅读该成员最近的发言片段，为成员画像做增量更新。\n\n"
            f"{prefix}"
            f"目标成员：{user_name}({user_id})\n\n"
            "请输出 JSON（不要代码块）：\n"
            "{\n"
            '  "user_id": 123,\n'
            '  "user_name": "xxx",\n'
            '  "emotion_connection": "...",\n'
            '  "personal_info": "..."\n'
            "}\n\n"
            "以下是该成员的发言片段（按时间顺序）：\n"
            + raw_dialogue
        )

    @staticmethod
    def _strip_json_fence(s: str):
        s = (s or "").strip()
        if s.startswith("```"):
            # 去掉 ```json ... ```
            lines = s.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                return "\n".join(lines[1:-1]).strip()
        return s

    @staticmethod
    def _limit_text(s: str, max_chars: int):
        s = (s or "").strip()
        if max_chars <= 0:
            return ""
        if len(s) <= max_chars:
            return s
        # 保留尾部最新内容，避免旧事件长期占用空间
        return "…\n" + s[-(max_chars - 2):]

    @classmethod
    def _process_summarize_job(cls, job: dict):
        group_id = int(job.get("group_id") or 0)
        prev_summary = str(job.get("prev_summary") or "")
        messages = job.get("messages") or []
        if not group_id or not isinstance(messages, list) or len(messages) == 0:
            return

        raw_lines = []
        for r in messages:
            if not isinstance(r, dict):
                continue
            ts = r.get("ts")
            try:
                ts_str = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                ts_str = ""
            uname = r.get("user_name") or "未知用户"
            uid = r.get("user_id") or 0
            txt = (r.get("text") or "").replace("\n", " ").strip()
            raw_lines.append(f"[{uname}({uid})]({ts_str}): {txt}")
        raw_dialogue = "\n".join(raw_lines[-CHAT_HISTORY_LIMIT:])

        system_prompt = "你是一个严谨的后端记忆抽取器。输出必须是可解析 JSON。"
        user_prompt = cls._memory_extract_prompt_300_incremental(prev_summary, raw_dialogue)
        try:
            out = cls._call_llm_api(system_prompt, user_prompt, temperature=0.6)
            out_json = json.loads(cls._strip_json_fence(out))
            group_history = (out_json.get("group_history") or "").strip()
            user_specific = out_json.get("user_specific") or []
        except Exception as e:
            logger.warning(f"[llm_memory] summarize parse failed: {e}")
            group_history = ""
            user_specific = []

        with cls._memory_lock:
            mem = cls._load_group_memory(group_id)
            if group_history:
                mem["group_summary"] = cls._limit_text(group_history, GROUP_SUMMARY_MAX_CHARS)
                mem["group_summary_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 摘要生成时：顺便更新活跃成员画像 & 重置计数
            if isinstance(user_specific, list):
                profiles = mem.get("user_profiles") or {}
                if not isinstance(profiles, dict):
                    profiles = {}
                counters = mem.get("user_counters") or {}
                if not isinstance(counters, dict):
                    counters = {}
                pending = mem.get("user_pending") or {}
                if not isinstance(pending, dict):
                    pending = {}

                for u in user_specific:
                    if not isinstance(u, dict):
                        continue
                    uid = u.get("user_id")
                    if uid is None:
                        continue
                    uid_key = str(int(uid))
                    uname = str(u.get("user_name") or "")
                    emotion = str(u.get("emotion_connection") or "").strip()
                    pinfo = str(u.get("personal_info") or "").strip()
                    profile_txt = ""
                    if emotion:
                        profile_txt += f"[情感连接] {emotion}\n"
                    if pinfo:
                        profile_txt += f"[个人信息] {pinfo}\n"
                    if profile_txt.strip():
                        profiles[uid_key] = {
                            "name": uname,
                            "profile": profile_txt.strip(),
                            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    counters[uid_key] = 0
                    pending[uid_key] = False

                mem["user_profiles"] = profiles
                mem["user_counters"] = counters
                mem["user_pending"] = pending

            mem["summary_pending"] = False
            cls._save_group_memory(group_id, mem)

    @classmethod
    def _process_user_profile_job(cls, job: dict):
        group_id = int(job.get("group_id") or 0)
        user_id = int(job.get("user_id") or 0)
        user_name = str(job.get("user_name") or "")
        messages = job.get("messages") or []
        if not group_id or not user_id or not isinstance(messages, list) or len(messages) == 0:
            return

        raw_lines = []
        for r in messages:
            if not isinstance(r, dict):
                continue
            ts = r.get("ts")
            try:
                ts_str = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                ts_str = ""
            txt = (r.get("text") or "").replace("\n", " ").strip()
            raw_lines.append(f"({ts_str}) {txt}")
        raw_dialogue = "\n".join(raw_lines)

        with cls._memory_lock:
            mem = cls._load_group_memory(group_id)
            profiles = mem.get("user_profiles") or {}
            existing_profile = ""
            if isinstance(profiles, dict):
                p = profiles.get(str(int(user_id)))
                if isinstance(p, dict):
                    existing_profile = str(p.get("profile") or "")

        system_prompt = "你是一个严谨的后端记忆抽取器。输出必须是可解析 JSON。"
        user_prompt = cls._memory_extract_prompt_user(user_name, user_id, raw_dialogue, existing_profile)
        try:
            out = cls._call_llm_api(system_prompt, user_prompt, temperature=0.4)
            out_json = json.loads(cls._strip_json_fence(out))
            emotion = str(out_json.get("emotion_connection") or "").strip()
            pinfo = str(out_json.get("personal_info") or "").strip()
            uname = str(out_json.get("user_name") or user_name).strip() or user_name
        except Exception as e:
            logger.warning(f"[llm_memory] user profile parse failed: {e}")
            emotion = ""
            pinfo = ""
            uname = user_name

        with cls._memory_lock:
            mem = cls._load_group_memory(group_id)
            uid_key = str(int(user_id))
            profiles = mem.get("user_profiles") or {}
            if not isinstance(profiles, dict):
                profiles = {}

            profile_txt = ""
            if emotion:
                profile_txt += f"[情感连接] {emotion}\n"
            if pinfo:
                profile_txt += f"[个人信息] {pinfo}\n"
            if profile_txt.strip():
                profiles[uid_key] = {
                    "name": uname,
                    "profile": profile_txt.strip(),
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            mem["user_profiles"] = profiles

            counters = mem.get("user_counters") or {}
            if not isinstance(counters, dict):
                counters = {}
            counters[uid_key] = 0
            mem["user_counters"] = counters

            pending = mem.get("user_pending") or {}
            if not isinstance(pending, dict):
                pending = {}
            pending[uid_key] = False
            mem["user_pending"] = pending

            cls._save_group_memory(group_id, mem)

    def handle(self):
        if getattr(self, "_mode", "") == "summarize":
            chat_blob = self._build_chat_history_text()
            prompt = (
                "请总结以下聊天记录的主要话题、结论、待办和情绪走势，"
                "输出为简洁中文要点。\n\n"
                + chat_blob
            )
            answer = self._call_llm(prompt)
            final_answer = self._build_reply_with_trigger("/总结聊天", answer)
            msg_id = self.context.get("message_id")
            msg_id_str = str(msg_id).strip() if msg_id is not None else ""
            if msg_id_str and msg_id_str != "0":
                self.api.send_msg(reply(msg_id_str), text(final_answer))
            else:
                self.api.send_msg(text(final_answer))
            self._append_chat_record(final_answer, user_name="小埃同学")
            return

        answer = self._call_llm(
            self._prompt_text,
            include_recent_chat=getattr(self, "_use_recent_context", False),
        )
        final_answer = self._build_reply_with_trigger(getattr(self, "_prompt_text", ""), answer)
        msg_id = self.context.get("message_id")
        msg_id_str = str(msg_id).strip() if msg_id is not None else ""
        if msg_id_str and msg_id_str != "0":
            self.api.send_msg(reply(msg_id_str), text(final_answer))
        else:
            self.api.send_msg(text(final_answer))
        self._append_chat_record(final_answer, user_name="小埃同学")
