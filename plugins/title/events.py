"""称号插件独立处理打卡通知；关闭称号时不评估或发放新称号。"""
from datetime import datetime

from core.cq import at, text
from core.database_manager import DbManager
from core.db.rewards import RewardManager
from core.plugin_dispatch import subscribe
from plugins.title.logic import evaluate_and_unlock_titles, get_title_def


@subscribe("checkin.completed", "title", order=20)
def checkin_completed(operation, payload):
    db = DbManager()
    try:
        with RewardManager(db.conn).transaction():
            unlocked = evaluate_and_unlock_titles(
                db, payload["user_id"], datetime.fromisoformat(payload["checkin_at"]), commit=False,
            )
        if unlocked:
            lines = ["解锁新称号："]
            for tid in unlocked:
                data = get_title_def(tid) or {"name": "未知称号", "rarity": "unknown", "description": "无"}
                lines.append(f"[{tid}] 「{data['name']}」 ({data['rarity']}) - {data['description']}")
            operation.output.submit([at(payload["user_id"]), text("\n".join(lines))], kind="segments", order=10)
    finally:
        db.conn.close()
