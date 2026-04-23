"""群聊消息话题划分：每条群消息量化为向量并归入 topic 或新建 topic。"""

from __future__ import annotations

from core.base import Plugin
from core.group_topic_service import GroupTopicService
from core.utils import register_plugin


# @register_plugin
class GroupTopicSegmentPlugin(Plugin):
    name = "group_topic_segment"
    description = "群聊话题向量划分（无指令触发，依赖 Embedder）。"

    def match(self, message_type):
        if message_type != "message":
            return False
        return self.bot_event.post_type == "message"

    def handle(self) -> None:
        if not self.bot_event.is_group:
            return
        user_id = self.bot_event.user_id
        group_id = self.bot_event.group_id
        if user_id is None or group_id is None:
            return
        uid = int(user_id)
        gid = int(group_id)
        raw_mid = self.bot_event.message_id
        mid = int(raw_mid) if raw_mid is not None else -1

        svc = GroupTopicService.from_db_manager(self.dbmanager)
        svc.on_group_message(gid, uid, mid, self.bot_event.message)
