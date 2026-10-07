"""周常任务引擎：进度、奖励记录、积分及统计在同一奖励事务完成。

数据层在 core/db/quest.py；周界口径 get_monday_to_monday（周一 08:00）见 core/utils.py。
"""
from uuid import uuid4

from core.utils import get_monday_to_monday
from core.db.rewards import RewardManager

# ponytail: quest defs hardcoded, add admin-created quests later if needed
QUEST_DEFS = [
    {"id": 1, "name": "打个卡先", "trigger": "checkin", "goal": 1, "reward": 1},
    {"id": 2, "name": "三连打卡", "trigger": "checkin", "goal": 3, "reward": 2},
    {"id": 3, "name": "一周都打了", "trigger": "checkin", "goal": 7, "reward": 3},
    {"id": 4, "name": "随便抽抽", "trigger": "lottery", "goal": 3, "reward": 1},
    {"id": 5, "name": "猛猛上瘾", "trigger": "lottery", "goal": 7, "reward": 2},
    {"id": 6, "name": "抽卡享受者", "trigger": "lottery", "goal": 15, "reward": 5},
]

def get_quest_week_key():
    return get_monday_to_monday()[0].split(" ")[0]

def on_quest_trigger(db, user_id, trigger_type, *, source_operation=None, source_scope=""):
    rewards = RewardManager(db.quest.conn)
    source_operation = source_operation or uuid4().hex
    week_key = get_quest_week_key()
    completed = []
    with rewards.transaction():
        start, end = get_monday_to_monday()
        count = (db.checkin.count_days(user_id, start, end) if trigger_type == "checkin"
                 else db.lottery.weekly_draw_count(user_id, start))
        for q in QUEST_DEFS:
            if q["trigger"] != trigger_type:
                continue
            db.quest.upsert_progress(user_id, q["id"], week_key, count, commit=False)
            if count < q["goal"]:
                continue
            def claim(conn, quest=q):
                return db.quest.claim_reward(user_id, quest["id"], week_key, commit=False)
            if rewards.grant("weekly_quest", user_id, f"{week_key}:{q['id']}",
                             source_operation, q["reward"], source_scope=source_scope, update_state=claim):
                db.quest.increment_completion(user_id, commit=False)
                completed.append({"name": q["name"], "reward": q["reward"]})
        progress = db.quest.progress(user_id, week_key)
        if progress and all(progress.get(q["id"], {}).get("completed") for q in QUEST_DEFS):
            db.quest.record_clear(user_id, week_key, commit=False)
    return completed


def on_quest_rollback(db, user_id, trigger_type, *, source_operation=None):
    rewards = RewardManager(db.quest.conn)
    source_operation = source_operation or uuid4().hex
    week_key = get_quest_week_key()
    revoked = []
    with rewards.transaction():
        start, end = get_monday_to_monday()
        count = db.checkin.count_days(user_id, start, end)
        existing = db.quest.progress(user_id, week_key)
        for q in QUEST_DEFS:
            if q["trigger"] != trigger_type or q["id"] not in existing:
                continue
            db.quest.upsert_progress(user_id, q["id"], week_key, count, commit=False)
            if count >= q["goal"]:
                continue
            key = f"{week_key}:{q['id']}"
            def revoke(conn, quest=q):
                return db.quest.revoke_reward(user_id, quest["id"], week_key, commit=False)
            if rewards.has_history("weekly_quest", user_id, key):
                amount = rewards.revoke("weekly_quest", user_id, key, source_operation, update_state=revoke)
                if amount is not None:
                    revoked.append(q)
            elif revoke(db.quest.conn):
                # 旧领取没有来源记录：只撤销已领取状态，不补造历史发奖。
                db.points.adjust(user_id, -q["reward"], commit=False)
                revoked.append(q)
    return revoked
