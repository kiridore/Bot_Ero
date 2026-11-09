"""打卡历史全勤奖励的撤销，独立于是否允许产生新的打卡奖励。"""
from datetime import datetime, timedelta

from core.database_manager import DbManager
from core.db.rewards import RewardManager
from core.plugin_dispatch import subscribe
from core.utils import get_monday_to_monday


@subscribe("checkin.completed", "checkin", order=30)
def award_attendance(operation, payload):
    if not payload["is_first"]:
        return
    dt = datetime.fromisoformat(payload["reward_at"])
    month_start = dt.replace(day=1)
    month_end = (month_start.replace(year=dt.year + 1, month=1) if dt.month == 12
                 else month_start.replace(month=dt.month + 1))
    db = DbManager()
    try:
        rewards = RewardManager(db.conn)
        with rewards.transaction():
            days = db.checkin.count_days(payload["user_id"], month_start.strftime("%Y-%m-%d 00:00:00"),
                                        month_end.strftime("%Y-%m-%d 00:00:00"))
            if days < (month_end - month_start).days:
                return
            awarded = rewards.grant_attendance(
                payload["user_id"], "full_month_weekly_check", payload["week_start"],
                payload["source_operation"], source_scope=payload.get("source_scope", ""),
            )
        if awarded:
            operation.output.submit("当月全勤奖励 +1", merge="checkin-rewards", order=25)
    finally:
        db.conn.close()


@subscribe("checkin.retracted", "checkin", order=20, cleanup=True)
def revoke_attendance(operation, payload):
    db = DbManager()
    try:
        uid = payload["user_id"]
        dt = datetime.fromisoformat(payload["removed_at"])
        rewards = RewardManager(db.conn)
        with rewards.transaction():
            start, end = get_monday_to_monday(dt)
            if not db.checkin.search_user_range(uid, start, end, limit=1):
                rewards.revoke_attendance(uid, "full_month_weekly_check", start.split(" ")[0],
                                          payload["source_operation"])

            # 保留现有自然周00:00口径，不在事务迁移时顺便改玩法边界。
            week_start = dt.date() - timedelta(days=dt.weekday())
            week_end = week_start + timedelta(days=7)
            days = db.checkin.count_days(uid, week_start.strftime("%Y-%m-%d 00:00:00"),
                                        week_end.strftime("%Y-%m-%d 00:00:00"))
            if days < 7:
                rows = db.conn.execute("""
                    SELECT reward_type, period_key FROM user_attendance_reward_claims
                    WHERE user_id = ? AND reward_type = 'full_week_daily'
                    AND period_key >= ? AND period_key < ?
                """, (uid, week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"))).fetchall()
                for reward_type, period in rows:
                    rewards.revoke_attendance(uid, reward_type, period, payload["source_operation"])

            month_start = dt.replace(day=1)
            month_end = (month_start.replace(year=dt.year + 1, month=1) if dt.month == 12
                         else month_start.replace(month=dt.month + 1))
            days = db.checkin.count_days(uid, month_start.strftime("%Y-%m-%d 00:00:00"),
                                        month_end.strftime("%Y-%m-%d 00:00:00"))
            if days < (month_end - month_start).days:
                rows = db.conn.execute("""
                    SELECT reward_type, period_key FROM user_attendance_reward_claims
                    WHERE user_id = ? AND reward_type = 'full_month_weekly_check' AND period_key LIKE ?
                """, (uid, month_start.strftime("%Y-%m") + "%")).fetchall()
                for reward_type, period in rows:
                    rewards.revoke_attendance(uid, reward_type, period, payload["source_operation"])
    finally:
        db.conn.close()
