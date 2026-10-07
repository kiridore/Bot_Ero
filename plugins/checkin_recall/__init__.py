from datetime import datetime

from core.base import Plugin
from core.cq import at, text
from core.timeline_client import retract_event
from core.utils import register_plugin


@register_plugin
class CheckinRecallPlugin(Plugin):
    """群成员撤回打卡消息时删除其图片记录，并通知奖励插件核算历史奖励。"""

    name = 'auto_rollback_recalled_checkin'
    description = '在打卡消息被撤回时自动删除对应记录。'

    def match(self, event_type):
        if event_type != "notice":
            return False
        return self.bot_event.notice_type == "group_recall"

    def handle(self):
        user_id = self.bot_event.user_id
        raw_mid = self.bot_event.message_id
        if user_id is None or raw_mid is None:
            return
        try:
            message_id = int(raw_mid)
        except (TypeError, ValueError):
            return
        target_rows = self.dbmanager.checkin.get_by_msg(user_id, message_id)
        if not target_rows:
            return
        dt = datetime.strptime(target_rows[0][2], "%Y-%m-%d %H:%M:%S")
        deleted = self.dbmanager.checkin.delete_by_msg(user_id, message_id)
        if deleted <= 0:
            return
        retract_event(
            "checkin", dedup_key="checkin:%s:%s:%s" % (user_id, dt.strftime("%Y-%m-%d"), message_id)
        )
        self.publish_event("checkin.retracted", removed_at=dt.isoformat())
        self.submit_message(
            at(user_id), text("已撤销你撤回的那条打卡消息对应的记录（含{}张图）".format(deleted)),
        )
