import random

from plugins.title import get_lottery_title_ids, get_title_def

DUP_REBATE = {"common": 1, "rare": 2, "legendary": 3}


def draw_title_by_rarity(dbmanager, user_id, rarity, *, commit=True):
    candidates = []
    for tid in get_lottery_title_ids():
        data = get_title_def(tid) or {}
        if data.get("rarity") == rarity:
            candidates.append(tid)

    if not candidates:
        return {"type": "title_none", "rarity": rarity}

    title_id = random.choice(candidates)
    if dbmanager.titles.has(user_id, title_id):
        rebate = DUP_REBATE.get(rarity, 0)
        if rebate > 0:
            dbmanager.points.adjust(user_id, rebate, commit=commit)
        return {"type": "title_duplicate", "value": title_id, "rarity": rarity, "rebate": rebate}

    dbmanager.titles.unlock(user_id, title_id, commit=commit)
    return {"type": "title_new", "value": title_id, "rarity": rarity}


# ponytail: odds hardcoded; tune via config if balance changes needed
REWARD_TABLE = [
    (31.0, {"type": "points", "value": 0}),
    (28.0, {"type": "points", "value": 1}),
    (10.0, {"type": "points", "value": 2}),
    (6.0, {"type": "points", "value": 3}),
    (3.0, {"type": "points", "value": 5}),
    (0.8, {"type": "points", "value": 8}),
    (0.2, {"type": "points", "value": 10}),
    (12.0, {"type": "title_roll", "rarity": "common"}),
    (5.0, {"type": "title_roll", "rarity": "rare"}),
    (4.0, {"type": "title_roll", "rarity": "legendary"}),
]


def draw_reward(dbmanager, user_id, *, commit=True):
    roll = random.random() * 100
    threshold = 0.0
    for prob, reward in REWARD_TABLE:
        threshold += prob
        if roll < threshold:
            if reward["type"] == "points":
                return reward
            return draw_title_by_rarity(dbmanager, user_id, reward["rarity"], commit=commit)
    return {"type": "points", "value": 0}