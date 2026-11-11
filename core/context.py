# 一些全局运行时数据
from datetime import datetime
from typing import TYPE_CHECKING
import sqlite3
import time
from threading import Lock

if TYPE_CHECKING:
    from core.base import Plugin

script_start_time = datetime.now()
from core import config as _config
from core.logger import logger
from core.trpg import records

llonebot_data_path = _config.LLONEBOT_DATA_PATH    # 使用api是用这个地址（config.yaml）
python_data_path = _config.PYTHON_DATA_PATH        # 在python脚本中访问用这个地址（config.yaml）
onebot_qq_volume = _config.ONEBOT_QQ_VOLUME
startup_changelog_sent = True
plugin_registry: list[type["Plugin"]] = []
DEFAULT_GROUP_ID = _config.DEFAULT_GROUP_ID  # 固定群号（config.yaml bot.default_group）

# 系统级插件（不可按群禁用，始终运行）
SYSTEM_PLUGINS = frozenset({
    "menu",
    "group_manager",
    "startup_changelog",
    "backup",
    "update",
    "auto_friend",
    "welcome",
    "message_logger",
})

# 跑团录制状态（进程内；启动时由 trpg_session.recover_recordings() 从磁盘重建）
recording_lock = Lock()
recording_sessions: dict[int, dict] = {}      # group_id → {"start": datetime, "messages": list, "participants": dict, ...}
RECORDING_ALLOWED_PLUGINS = frozenset({"trpg_dice", "trpg_session", "trpg_char", "trpg_vitals"})

# 当前游戏规则系统（跑团骰子检定用），未来规则切换功能修改此值
GAME_SYSTEM = "dnd5e"

# 卧底游戏
game_lock = Lock()

def is_group_recording(group_id: int) -> bool:
    return group_id in recording_sessions

def get_recording_session(group_id: int) -> dict | None:
    return recording_sessions.get(group_id)

def is_plugin_allowed_during_recording(key: str) -> bool:
    return key in RECORDING_ALLOWED_PLUGINS

def _session_record_dir(group_id: int, session: dict):
    # 录制目录由 trpg_session 建立时写入 session["dir"]；未写入时按开始时间推算
    return session.get("dir") or records.record_dir(group_id, records.start_dir_name(session["start"]))

def record_bot_message(group_id: int, nickname: str, text: str, secret: bool = False) -> None:
    """录制期间把机器人自己的发言写入 messages.jsonl；无录制时静默返回。"""
    try:
        with recording_lock:
            session = recording_sessions.get(group_id)
            if not session:
                return
            bot_id = str(_config.BOT_QQ)
            entry = {
                "time": int(time.time()),
                "sender_type": "bot",
                "user_id": bot_id,
                "nickname": nickname,
                "char_name": "",
                "role": session.get("roles", {}).get(bot_id, ""),
                "segments": [{"type": "text", "text": text}],
            }
            if secret:
                entry["secret"] = True
            path = _session_record_dir(group_id, session)
            records.append_message(path, entry)
            if bot_id not in session["participants"]:
                session["participants"][bot_id] = {"nickname": nickname, "user_id": bot_id, "char_name": ""}
                meta = records.read_meta(path)
                if meta is not None:
                    meta["participants"] = list(session["participants"].values())
                    records.rewrite_meta(path, meta)
    except Exception:
        logger.exception("机器人消息入档失败")

def plugin_key(plugin_cls: type["Plugin"]) -> str:
    return plugin_cls.__module__.split(".", 1)[1]

def is_plugin_enabled(plugin_cls: type["Plugin"], group_id: int | None) -> bool:
    key = plugin_key(plugin_cls)
    if key in SYSTEM_PLUGINS:
        return True
    gid = group_id if group_id is not None else 0
    try:
        conn = sqlite3.connect(str(_config.DB_PATH))
        cur = conn.execute(
            "SELECT 1 FROM group_plugin_config WHERE group_id = ? AND plugin_name = ?",
            (gid, key)
        )
        enabled = cur.fetchone() is not None
        conn.close()
        return enabled
    except sqlite3.Error:
        return True
