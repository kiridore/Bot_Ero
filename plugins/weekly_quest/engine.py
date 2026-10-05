"""周常任务引擎（玩法规则域）——从 core/utils.py 迁入（社区版 T0.5，函数体逐字等价）。

数据层在 core/db/quest.py；周界口径 get_monday_to_monday（周一 08:00）见 core/utils.py。
"""
from core.utils import add_user_point, get_monday_to_monday

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

def on_quest_trigger(db, user_id, trigger_type):
    week_key = get_quest_week_key()
    if trigger_type == "checkin":
        start, end = get_monday_to_monday()
        count = db.checkin.count_days(user_id, start, end)
    else:
        start, _ = get_monday_to_monday()
        count = db.lottery.weekly_draw_count(user_id, start)
    completed = []
    for q in QUEST_DEFS:
        if q["trigger"] != trigger_type:
            continue
        db.quest.upsert_progress(user_id, q["id"], week_key, count)
        if count >= q["goal"] and db.quest.claim_reward(user_id, q["id"], week_key):
            add_user_point(db, user_id, q["reward"])
            db.quest.increment_completion(user_id)
            completed.append({"name": q["name"], "reward": q["reward"]})
    # 检查是否本周所有任务全清
    progress = db.quest.progress(user_id, week_key)
    if progress and all(progress.get(q["id"], {}).get("completed") for q in QUEST_DEFS):
        db.quest.record_clear(user_id, week_key)
    return completed

def on_quest_rollback(db, user_id, trigger_type):
    week_key = get_quest_week_key()
    start, end = get_monday_to_monday()
    count = db.checkin.count_days(user_id, start, end)
    revoked = []
    for q in QUEST_DEFS:
        if q["trigger"] != trigger_type:
            continue
        db.quest.upsert_progress(user_id, q["id"], week_key, count)
        if count < q["goal"] and db.quest.revoke_reward(user_id, q["id"], week_key):
            add_user_point(db, user_id, -q["reward"])
            revoked.append(q)
    return revoked
