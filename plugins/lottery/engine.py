"""单次抽奖的原子结算：扣费、道具、次数、奖品、画像和来源记录一起提交。"""
import json
import random

from core.db.rewards import RewardManager
from plugins.lottery.rewards import draw_reward

COST = 1
FREE_DRAW_HINT = "本次抽卡免费（今日首抽）"


def max_draw(db, user_id, today, shop_enabled=True):
    return ((5 if db.checkin.has_on_date(user_id, today) else 2)
            + (db.shop.draw_bonus(user_id, today) if shop_enabled else 0))


def perform_draw(db, payload, shop_enabled):
    uid, today, source = payload["user_id"], payload["today"], payload["source_operation"]
    with RewardManager(db.conn).transaction():
        if db.conn.execute("SELECT 1 FROM lottery_operation_receipts WHERE source_operation = ?", (source,)).fetchone():
            return {"status": "duplicate"}
        count = db.lottery.draw_count(uid, today)
        limit = max_draw(db, uid, today, shop_enabled)
        if count >= limit:
            outcome = {"status": "limit", "count": count, "limit": limit,
                       "checked_in": db.checkin.has_on_date(uid, today)}
        else:
            free = count == 0
            waiver = not free and shop_enabled and db.shop.waiver_remaining(uid) > 0
            exempt = bool(waiver and random.random() < 0.3)
            cost = 0 if free or exempt else COST
            if cost and not db.points.spend(uid, cost, commit=False):
                outcome = {"status": "insufficient", "points": db.points.get(uid)}
            else:
                if waiver:
                    db.shop.pop_waiver(uid, commit=False)
                if cost:
                    db.lottery.add_spent(uid, cost, commit=False)
                db.lottery.add_draw(uid, today, commit=False)
                result = draw_reward(db, uid, commit=False)
                profile = db.lottery.profile(uid)
                zero = profile["zero_streak"]
                duplicate = profile["duplicate_count"]
                max_zero, ten, zeros = profile["max_zero_streak"], profile["has_hit_ten"], profile["total_zeros"]
                if result["type"] == "points":
                    amount = result["value"]
                    db.points.adjust(uid, amount, commit=False)
                    zero = zero + 1 if amount == 0 else 0
                    zeros += int(amount == 0)
                    max_zero = max(max_zero, zero)
                    ten = int(bool(ten or amount == 10))
                elif result["type"] in ("title_new", "title_duplicate", "title_none"):
                    zero = 0
                    duplicate += int(result["type"] == "title_duplicate")
                db.lottery.upsert_profile(uid, profile["draw_count"] + 1, duplicate, zero, max_zero, ten, zeros, commit=False)
                db.lottery.insert_draw_log(uid, result["type"], result.get("value"), result.get("rarity"), zero, commit=False)
                outcome = {"status": "ok", "result": result, "free": free, "exempt": exempt, "cost": cost}
        db.conn.execute("INSERT INTO lottery_operation_receipts (source_operation, user_id, outcome) VALUES (?, ?, ?)",
                        (source, uid, json.dumps(outcome, ensure_ascii=False)))
        return outcome
