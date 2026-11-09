"""打卡道具由商店订阅处理；道具消耗与随机奖励同事务完成。"""
import random

from core.database_manager import DbManager
from core.db.rewards import RewardManager
from core.plugin_dispatch import subscribe


@subscribe("checkin.completed", "redeem_shop", order=10)
def checkin_luck(operation, payload):
    db = DbManager()
    try:
        rewards = RewardManager(db.conn)
        uid, source = payload["user_id"], payload["source_operation"]
        key = "checkin_luck:" + source
        with rewards.transaction():
            if rewards.has_history("redeem_shop", uid, key):
                return
            used = db.shop.pop_luck(uid, commit=False)
            won = used and random.random() < 0.1
            rewards.grant("redeem_shop", uid, key, source, int(won),
                          source_scope=payload.get("source_scope", ""))
        if won:
            operation.output.submit("打卡增强：概率奖励 +1", merge="checkin-rewards", order=30)
    finally:
        db.conn.close()
