# 一些全局运行时数据
from collections import defaultdict, deque
from datetime import datetime
from typing import TYPE_CHECKING, DefaultDict, Deque, Optional

if TYPE_CHECKING:
    from core.base import Plugin

script_start_time = datetime.now()
llonebot_data_path = "/app/llonebot/server_data"    # 使用api是用这个地址
python_data_path = "./server_data"                  # 在python脚本中访问用这个地址
onebot_qq_volume = "/var/lib/docker/volumes/onebot_qq_volume/_data"
startup_changelog_sent = False
RECENT_CHAT_RECORDS_MAX = 200
recent_chat_records: DefaultDict[int, Deque[dict]] = defaultdict(
    lambda: deque(maxlen=RECENT_CHAT_RECORDS_MAX)
)
plugin_registry: list[type["Plugin"]] = []
DEFAULT_GROUP_ID = 296470819 # 在这里填写你想固定使用的群号


def _format_record_time(ts) -> str:
    if ts is None:
        return "?"
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return str(ts)
    return str(ts)


def get_recent_chat_records(group_id: int, limit: Optional[int] = None) -> list[dict]:
    """读取指定群最近聊天记录（按时间从旧到新）。"""
    records = list(recent_chat_records.get(int(group_id), ()))
    if limit is None or limit <= 0:
        return records
    return records[-limit:]


def get_last_chat_record(group_id: int) -> Optional[dict]:
    """读取指定群最后一条聊天记录。"""
    records = recent_chat_records.get(int(group_id))
    if not records:
        return None
    return records[-1]


def format_chat_record(record: dict, include_group_id: bool = False) -> str:
    """把单条聊天记录格式化为易读文本。"""
    ts = record.get("time")
    time_text = _format_record_time(ts)
    nickname = str(record.get("nickname") or "未知用户")
    user_id = str(record.get("user_id") or "?")
    message_id = str(record.get("message_id") or "?")
    plain_text = str(record.get("plain_text") or "").strip()
    text = plain_text if plain_text else "[非文本消息]"

    prefix = f"[{time_text}]"
    if include_group_id:
        prefix += f"[群:{record.get('group_id', '?')}]"
    return f"{prefix} {nickname}({user_id}) #{message_id}: {text}"


def format_recent_chat_records(
    group_id: int, limit: int = 20, include_group_id: bool = False
) -> str:
    """把指定群最近聊天记录批量格式化为多行文本。"""
    records = get_recent_chat_records(group_id, limit=limit)
    if not records:
        return ""
    return "\n".join(
        format_chat_record(record, include_group_id=include_group_id)
        for record in records
    )
