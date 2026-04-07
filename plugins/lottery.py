import random
from datetime import datetime

from core import utils
from core.base import Plugin
from core.cq import at, text
from plugins.title import get_lottery_title_ids, get_title_def, evaluate_and_unlock_titles


class LotteryPlugin(Plugin):
    COST = 1
    DUP_REBATE = {"common": 1, "rare": 2, "legendary": 3}

    def match(self, message_type):
        if self.on_full_match("/抽奖"):
            return True
        return self.on_command("/抽卡消费")

    def _extract_target_user_id(self, default_user_id):
        for seg in self.context.get("message", []):
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
            (30.0, {"type": "points", "value": 0}),
            (30.0, {"type": "points", "value": 1}),
            (10.0, {"type": "points", "value": 2}),
            (6.0, {"type": "points", "value": 3}),
            (3.0, {"type": "points", "value": 5}),
            (0.8, {"type": "points", "value": 8}),
            (0.2, {"type": "points", "value": 10}),
            (15.0, {"type": "title_roll", "rarity": "common"}),
            (4.0, {"type": "title_roll", "rarity": "rare"}),
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

    def handle(self):
        user_id = self.context["user_id"]
        args = getattr(self, "args", None)
        if args and args[0] == "/抽卡消费":
            target_user_id = self._extract_target_user_id(user_id)
            spent = self.dbmanager.get_lottery_spent(target_user_id)
            self.api.send_msg(at(user_id), text(f"用户 {target_user_id} 累计抽卡消费：{spent} 积分"))
            return

        today = datetime.now().strftime("%Y-%m-%d")
        draw_count = self.dbmanager.get_lottery_draw_count(user_id, today)
        has_checkin_today = self.dbmanager.has_checkin_on_date(user_id, today)
        max_draw = 5 if has_checkin_today else 2
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

        points = self.dbmanager.get_user_point(user_id)
        if points < self.COST:
            self.api.send_msg(at(user_id), text("抽奖需要1点积分，你现在只有{}点喵".format(points)))
            return

        # 先扣抽奖门票
        utils.add_user_point(self.dbmanager, user_id, -self.COST)
        self.dbmanager.add_lottery_spent(user_id, self.COST)
        self.dbmanager.add_lottery_draw_count(user_id, today, 1)
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
            evaluate_and_unlock_titles(self.dbmanager, user_id)
            net = reward - self.COST
            now_points = self.dbmanager.get_user_point(user_id)
            if reward == 0:
                self.api.send_msg(
                    at(user_id),
                    text("*摇骰子* 居然什么都没有抽到呢……\n本次净变化：{}积分\n当前积分：{}".format(net, now_points)),
                )
            else:
                self.api.send_msg(
                    at(user_id),
                    text("*摇骰子* 居然抽到了……{}点积分！\n本次净变化：{}积分\n当前积分：{}".format(reward, net, now_points)),
                )
            return

        now_points = self.dbmanager.get_user_point(user_id)
        if result["type"] == "title_new":
            zero_streak = 0
            self.dbmanager.upsert_user_lottery_profile(
                user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten
            )
            evaluate_and_unlock_titles(self.dbmanager, user_id)
            title_id = result["value"]
            title_data = get_title_def(title_id) or {"name": "未知称号", "rarity": "unknown"}
            self.api.send_msg(
                at(user_id),
                text("*摇骰子* 居然抽到了……解锁称号 [{}] 「{}」 ({})！\n本次消耗：1积分\n当前积分：{}".format(title_id, title_data["name"], title_data["rarity"], now_points)),
            )
            return

        if result["type"] == "title_duplicate":
            duplicate_count += 1
            zero_streak = 0
            self.dbmanager.upsert_user_lottery_profile(
                user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten
            )
            evaluate_and_unlock_titles(self.dbmanager, user_id)
            title_id = result["value"]
            title_data = get_title_def(title_id) or {"name": "未知称号", "rarity": "unknown"}
            rebate = result.get("rebate", 0)
            self.api.send_msg(
                at(user_id),
                text("*摇骰子* 居然抽到了……已拥有称号 [{}] 「{}」 ({})！\n已返还{}积分。\n当前积分：{}".format(title_id, title_data["name"], title_data["rarity"], rebate, now_points))
            )
            return

        if result["type"] == "title_none":
            zero_streak = 0
            self.dbmanager.upsert_user_lottery_profile(
                user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten
            )
            evaluate_and_unlock_titles(self.dbmanager, user_id)
            self.api.send_msg(
                at(user_id),
                text("*摇骰子* 居然抽到了……{}称号位！\n当前没有可抽取的该稀有度称号。\n当前积分：{}".format(result["rarity"], now_points)),
            )
            return

        self.api.send_msg(
            at(user_id),
            text("*摇骰子* 居然抽到了……{}！\n本次消耗：1积分\n当前积分：{}".format(result["value"], now_points)),
        )
