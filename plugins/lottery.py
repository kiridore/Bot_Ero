import random

from core import utils
from core.base import Plugin
from core.cq import at, text
from plugins.title import get_lottery_title_ids, get_title_def


class LotteryPlugin(Plugin):
    COST = 1
    DUP_REBATE = {"common": 1, "rare": 2, "legendary": 3}

    def match(self, message_type):
        return self.on_full_match("/抽奖")

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
        points = self.dbmanager.get_user_point(user_id)
        if points < self.COST:
            self.api.send_msg(at(user_id), text("抽奖需要1点积分，你现在只有{}点喵".format(points)))
            return

        # 先扣抽奖门票
        utils.add_user_point(self.dbmanager, user_id, -self.COST)
        result = self.draw_reward(user_id)

        if result["type"] == "points":
            reward = result["value"]
            utils.add_user_point(self.dbmanager, user_id, reward)
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
            title_id = result["value"]
            title_data = get_title_def(title_id) or {"name": "未知称号", "rarity": "unknown"}
            self.api.send_msg(
                at(user_id),
                text("*摇骰子* 居然抽到了……解锁称号 [{}] {} ({})！\n本次消耗：1积分\n当前积分：{}".format(title_id, title_data["name"], title_data["rarity"], now_points)),
            )
            return

        if result["type"] == "title_duplicate":
            title_id = result["value"]
            title_data = get_title_def(title_id) or {"name": "未知称号", "rarity": "unknown"}
            rebate = result.get("rebate", 0)
            self.api.send_msg(
                at(user_id),
                text("*摇骰子* 居然抽到了……已拥有称号 [{}] {} ({})！\n已返还{}积分。\n当前积分：{}".format(title_id, title_data["name"], title_data["rarity"], rebate, now_points))
            )
            return

        if result["type"] == "title_none":
            self.api.send_msg(
                at(user_id),
                text("*摇骰子* 居然抽到了……{}称号位！\n当前没有可抽取的该稀有度称号。\n当前积分：{}".format(result["rarity"], now_points)),
            )
            return

        self.api.send_msg(
            at(user_id),
            text("*摇骰子* 居然抽到了……{}！\n本次消耗：1积分\n当前积分：{}".format(result["value"], now_points)),
        )
