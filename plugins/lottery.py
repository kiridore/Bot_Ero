import random
from datetime import datetime

from core import utils
from core.base import Plugin
from core.cq import at, text
from plugins.title import get_lottery_title_ids, get_title_def, evaluate_and_unlock_titles


from core.utils import register_plugin
@register_plugin
class LotteryPlugin(Plugin):
    name = 'lottery'
    description = '执行抽卡抽奖并发放奖励或称号。'

    COST = 1
    DUP_REBATE = {"common": 1, "rare": 2, "legendary": 3}
    FREE_DRAW_HINT = "本次抽卡免费（今日首抽）"

    def match(self, message_type):
        if self.on_full_match_any("/抽奖", "/抽獎") or self.on_full_match("/抽卡"):
            return True
        return self.on_command_any("/抽卡消费", "/抽卡消費")

    def _extract_target_user_id(self, default_user_id):
        for seg in self.bot_event.message:
            if seg.get("type") == "at":
                qq = seg.get("data", {}).get("qq")
                if qq and qq != "all":
                    return int(qq)
        return int(default_user_id)

    def draw_title_by_rarity(self, user_id, rarity):
        candidates = []
        for tid in get_lottery_title_ids():
            data = get_title_def(tid) or {}
            if data.get("rarity") == rarity:
                candidates.append(tid)

        if not candidates:
            return {"type": "title_none", "rarity": rarity}

        title_id = random.choice(candidates)
        if self.dbmanager.has_title(user_id, title_id):
            rebate = self.DUP_REBATE.get(rarity, 0)
            if rebate > 0:
                utils.add_user_point(self.dbmanager, user_id, rebate)
            return {"type": "title_duplicate", "value": title_id, "rarity": rarity, "rebate": rebate}

        self.dbmanager.unlock_title(user_id, title_id)
        return {"type": "title_new", "value": title_id, "rarity": rarity}

    def draw_reward(self, user_id):
        roll = random.random() * 100
        table = [
            (40.0, {"type": "points", "value": 0}),
            (28.0, {"type": "points", "value": 1}),
            (10.0, {"type": "points", "value": 2}),
            (6.0, {"type": "points", "value": 3}),
            (3.0, {"type": "points", "value": 5}),
            (0.8, {"type": "points", "value": 8}),
            (0.2, {"type": "points", "value": 10}),
            (9.0, {"type": "title_roll", "rarity": "common"}),
            (2.0, {"type": "title_roll", "rarity": "rare"}),
            (1.0, {"type": "title_roll", "rarity": "legendary"}),
        ]

        threshold = 0.0
        for prob, reward in table:
            threshold += prob
            if roll < threshold:
                if reward["type"] == "points":
                    return reward
                return self.draw_title_by_rarity(user_id, reward["rarity"])
        return {"type": "points", "value": 0}

    def _send_unlocked_titles_notice(self, user_id, unlocked_ids):
        if not unlocked_ids:
            return
        lines = ["解锁新称号："]
        for tid in unlocked_ids:
            data = get_title_def(tid) or {"name": "未知称号", "rarity": "unknown", "description": "无"}
            lines.append(f"[{tid}] 「{data['name']}」 ({data['rarity']}) - {data['description']}")
        self.api.send_msg(at(user_id), text("\n".join(lines)))

    def handle(self):
        if self.bot_event.user_id == None:
            return
        user_id = self.bot_event.user_id
        args = getattr(self, "args", None)
        if args and args[0] in ("/抽卡消费", "/抽卡消費"):
            target_user_id = self._extract_target_user_id(user_id)
            spent = self.dbmanager.get_lottery_spent(target_user_id)
            self.api.send_msg(at(user_id), text(f"用户 {target_user_id} 累计抽卡消费：{spent} 积分"))
            return

        today = datetime.now().strftime("%Y-%m-%d")
        draw_count = self.dbmanager.get_lottery_draw_count(user_id, today)
        has_checkin_today = self.dbmanager.has_checkin_on_date(user_id, today)
        extra_shop_draws = self.dbmanager.get_shop_extra_draw_bonus(user_id, today)
        max_draw = (5 if has_checkin_today else 2) + extra_shop_draws
        if draw_count >= max_draw:
            self.api.send_msg(
                at(user_id),
                text("今天抽卡次数已用完（{}/{}）。{}。".format(
                    draw_count,
                    max_draw,
                    "你今天已打卡，可抽5次" if has_checkin_today else "今日未打卡，默认可抽2次",
                )),
            )
            return

        free_daily = draw_count == 0
        points = self.dbmanager.get_user_point(user_id)
        payment_exempt = False
        if not free_daily:
            rem = self.dbmanager.get_shop_lottery_waiver_remaining(user_id)
            if rem > 0:
                if random.random() < 0.3:
                    payment_exempt = True
                if not payment_exempt and points < self.COST:
                    self.api.send_msg(at(user_id), text("抽奖需要1点积分，你现在只有{}点喵".format(points)))
                    return
                self.dbmanager.pop_shop_lottery_waiver_slot(user_id)
            else:
                if points < self.COST:
                    self.api.send_msg(at(user_id), text("抽奖需要1点积分，你现在只有{}点喵".format(points)))
                    return
            if not payment_exempt:
                utils.add_user_point(self.dbmanager, user_id, -self.COST)
                self.dbmanager.add_lottery_spent(user_id, self.COST)
        self.dbmanager.add_lottery_draw_count(user_id, today, 1)
        cost_paid = 0 if free_daily else (0 if payment_exempt else self.COST)
        draw_cost_hint = (
            self.FREE_DRAW_HINT
            if free_daily
            else ("抽奖增强：本次不消耗积分" if payment_exempt else "本次消耗：1积分")
        )
        result = self.draw_reward(user_id)
        profile = self.dbmanager.get_user_lottery_profile(user_id)
        draw_count = profile["draw_count"] + 1
        duplicate_count = profile["duplicate_count"]
        zero_streak = profile["zero_streak"]
        max_zero_streak = profile["max_zero_streak"]
        has_hit_ten = profile["has_hit_ten"]

        if result["type"] == "points":
            reward = result["value"]
            utils.add_user_point(self.dbmanager, user_id, reward)
            if reward == 0:
                zero_streak += 1
                if zero_streak > max_zero_streak:
                    max_zero_streak = zero_streak
            else:
                zero_streak = 0
            if reward == 10:
                has_hit_ten = 1
            self.dbmanager.upsert_user_lottery_profile(
                user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten
            )
            unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
            self._send_unlocked_titles_notice(user_id, unlocked)
            net = reward - cost_paid
            now_points = self.dbmanager.get_user_point(user_id)
            if free_daily:
                free_mid = "{}\n".format(self.FREE_DRAW_HINT)
            elif payment_exempt:
                free_mid = "抽奖增强：本次不消耗积分\n"
            else:
                free_mid = ""
            if reward == 0:
                self.api.send_msg(
                    at(user_id),
                    text(
                        "*摇骰子* 居然什么都没有抽到呢……\n本次净变化：{}积分\n{}当前积分：{}".format(
                            net, free_mid, now_points
                        )
                    ),
                )
            else:
                self.api.send_msg(
                    at(user_id),
                    text(
                        "*摇骰子* 居然抽到了……{}点积分！\n本次净变化：{}积分\n{}当前积分：{}".format(
                            reward, net, free_mid, now_points
                        )
                    ),
                )
            return

        now_points = self.dbmanager.get_user_point(user_id)
        if result["type"] == "title_new":
            zero_streak = 0
            self.dbmanager.upsert_user_lottery_profile(
                user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten
            )
            unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
            self._send_unlocked_titles_notice(user_id, unlocked)
            title_id = result["value"]
            title_data = get_title_def(title_id) or {"name": "未知称号", "rarity": "unknown"}
            self.api.send_msg(
                at(user_id),
                text("*摇骰子* 居然抽到了……解锁称号 [{}] 「{}」 ({})！\n{}\n当前积分：{}".format(title_id, title_data["name"], title_data["rarity"], draw_cost_hint, now_points)),
            )
            return

        if result["type"] == "title_duplicate":
            duplicate_count += 1
            zero_streak = 0
            self.dbmanager.upsert_user_lottery_profile(
                user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten
            )
            unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
            self._send_unlocked_titles_notice(user_id, unlocked)
            title_id = result["value"]
            title_data = get_title_def(title_id) or {"name": "未知称号", "rarity": "unknown"}
            rebate = result.get("rebate", 0)
            if free_daily:
                free_mid = "{}\n".format(self.FREE_DRAW_HINT)
            elif payment_exempt:
                free_mid = "抽奖增强：本次不消耗积分\n"
            else:
                free_mid = ""
            self.api.send_msg(
                at(user_id),
                text(
                    "*摇骰子* 居然抽到了……已拥有称号 [{}] 「{}」 ({})！\n已返还{}积分。\n{}当前积分：{}".format(
                        title_id, title_data["name"], title_data["rarity"], rebate, free_mid, now_points
                    )
                ),
            )
            return

        if result["type"] == "title_none":
            zero_streak = 0
            self.dbmanager.upsert_user_lottery_profile(
                user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten
            )
            unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
            self._send_unlocked_titles_notice(user_id, unlocked)
            if free_daily:
                free_mid = "{}\n".format(self.FREE_DRAW_HINT)
            elif payment_exempt:
                free_mid = "抽奖增强：本次不消耗积分\n"
            else:
                free_mid = ""
            self.api.send_msg(
                at(user_id),
                text(
                    "*摇骰子* 居然抽到了……{}称号位！\n当前没有可抽取的该稀有度称号。\n{}当前积分：{}".format(
                        result["rarity"], free_mid, now_points
                    )
                ),
            )
            return

        self.api.send_msg(
            at(user_id),
            text("*摇骰子* 居然抽到了……{}！\n{}\n当前积分：{}".format(result["value"], draw_cost_hint, now_points)),
        )
