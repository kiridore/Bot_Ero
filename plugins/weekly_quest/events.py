"""周常通过内部通知接收打卡和撤回，不由打卡插件直接调用业务函数。"""
from core.database_manager import DbManager
from core.plugin_dispatch import subscribe
from plugins.weekly_quest.engine import on_quest_trigger, on_quest_rollback


@subscribe("checkin.completed", "weekly_quest", order=40)
def checkin_completed(operation, payload):
    db = DbManager()
    try:
        completed = on_quest_trigger(
            db, payload["user_id"], "checkin",
            source_operation=payload["source_operation"],
            source_scope=payload.get("source_scope", ""),
        )
        if completed:
            names = " | ".join(f"{q['name']} +{q['reward']}" for q in completed)
            operation.output.submit("🎯 " + names, merge="checkin-rewards", order=40)
    finally:
        db.conn.close()


@subscribe("checkin.retracted", "weekly_quest", order=40, cleanup=True)
def checkin_retracted(operation, payload):
    # cleanup 绕过新奖励开关，但引擎仅撤销实际领取且已不满足条件的奖励。
    db = DbManager()
    try:
        on_quest_rollback(db, payload["user_id"], "checkin", source_operation=payload["source_operation"])
    finally:
        db.conn.close()
