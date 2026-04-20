# 一些全局运行时数据
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, DefaultDict, Deque, Optional

if TYPE_CHECKING:
    from core.base import Plugin

script_start_time = datetime.now()
llonebot_data_path = "/app/llonebot/server_data"    # 使用api是用这个地址
python_data_path = "./server_data"                  # 在python脚本中访问用这个地址
onebot_qq_volume = "/var/lib/docker/volumes/onebot_qq_volume/_data"
startup_changelog_sent = False
recent_chat_records = []
plugin_registry: list[type["Plugin"]] = []
DEFAULT_GROUP_ID = 296470819 # 在这里填写你想固定使用的群号

GROUP_MESSAGE_HISTORY_MAX = 1000


@dataclass(frozen=True)
class QQMsg:
    """群聊单条消息摘要（供内存环形缓冲等使用）。"""

    message_id: int
    user_id: int
    timestamp: int
    username: str
    content: str


# 群号 -> 最近若干条 QQMsg（每群最多 GROUP_MESSAGE_HISTORY_MAX 条）
group_qq_message_history: DefaultDict[int, Deque[QQMsg]] = defaultdict(
    lambda: deque(maxlen=GROUP_MESSAGE_HISTORY_MAX)
)

# (群号, message_id) -> 当前缓冲内对应 QQMsg（与 group_qq_message_history 同步维护）
qq_msg_by_group_message_id: dict[tuple[int, int], QQMsg] = {}


def lookup_qq_msg(group_id: int, message_id: int) -> Optional[QQMsg]:
    """在内存缓冲内按群号与 message_id 查找消息；仅能找到仍在环形缓冲中的记录。"""
    return qq_msg_by_group_message_id.get((int(group_id), int(message_id)))
