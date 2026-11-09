from datetime import datetime

from core.base import CommandPlugin
from core.cq import at, text
from core.utils import register_plugin
from plugins.lottery.engine import max_draw


@register_plugin
class LotteryPlugin(CommandPlugin):
    name = 'lottery'
    description = '执行抽卡抽奖并发放奖励或称号。'
    COMMANDS = ("/抽奖", "/抽獎", "/抽卡", "/抽卡消费", "/抽卡消費", "/一键抽奖", "/一鍵抽獎")

    def _extract_target_user_id(self, default_user_id):
        for seg in self.bot_event.message:
            if seg.get("type") == "at":
                qq = seg.get("data", {}).get("qq")
                if qq and qq != "all":
                    return int(qq)
        return int(default_user_id)

    def handle(self):
        uid = self.bot_event.user_id
        if uid is None:
            return
        if self.cmd in ("/抽卡消费", "/抽卡消費"):
            target = self._extract_target_user_id(uid)
            spent = self.dbmanager.lottery.spent(target)
            self.submit_message(at(uid), text(f"用户 {target} 累计抽卡消费：{spent} 积分"))
            return
        if not self.feature_enabled("title"):
            self.submit_message(text("称号功能已关闭，暂时无法抽奖。请联系超级用户开启称号功能。"))
            return
        today = datetime.now().strftime("%Y-%m-%d")
        count = self.dbmanager.lottery.draw_count(uid, today)
        limit = max_draw(self.dbmanager, uid, today, self.feature_enabled("redeem_shop"))
        bulk = self.cmd in ("/一键抽奖", "/一鍵抽獎")
        gid = self.bot_event.group_id
        scope = f"group:{gid}" if gid is not None else f"private:{uid}"
        mid = self.bot_event.message_id
        command_key = f"lottery:{scope}:{uid}:{mid if mid is not None else self.operation.id}"
        self.publish_event(
            "lottery.draw.requested", today=today, bulk=bulk, index=1,
            remaining=max(1, limit - count) if bulk else 1,
            command_key=command_key, source_operation=command_key + ":1",
            output={"kind": "forward_text" if bulk else "text", "merge": command_key if bulk else None,
                    "node": 1 if bulk else None},
        )
