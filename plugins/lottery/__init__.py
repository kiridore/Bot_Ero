import random
from datetime import datetime

from core import utils
from core.base import BOT_QQ, NICKNAME, CommandPlugin
from core.cq import at, text
from core.utils import on_quest_trigger, register_plugin
from plugins.title import get_title_def, evaluate_and_unlock_titles

from .rewards import draw_reward


@register_plugin
class LotteryPlugin(CommandPlugin):
    name = 'lottery'
    description = '执行抽卡抽奖并发放奖励或称号。'

    COST = 1
    FREE_DRAW_HINT = "本次抽卡免费（今日首抽）"
    COMMANDS = ("/抽奖", "/抽獎", "/抽卡", "/抽卡消费", "/抽卡消費", "/一键抽奖", "/一鍵抽獎")

    def _extract_target_user_id(self, default_user_id):
        for seg in self.bot_event.message:
            if seg.get("type") == "at":
                qq = seg.get("data", {}).get("qq")
                if qq and qq != "all":
                    return int(qq)
        return int(default_user_id)

    def _format_unlocked_titles(self, unlocked_ids):
        lines = ["解锁新称号："]
        for tid in unlocked_ids:
            data = get_title_def(tid) or {"name": "未知称号", "rarity": "unknown", "description": "无"}
            lines.append(f"[{tid}] 「{data['name']}」 ({data['rarity']}) - {data['description']}")
        return "\n".join(lines)

    def _max_draw(self, user_id, today):
        has_checkin_today = self.dbmanager.checkin.has_on_date(user_id, today)
        extra_shop_draws = self.dbmanager.shop.draw_bonus(user_id, today)
        return (5 if has_checkin_today else 2) + extra_shop_draws

    def _perform_single_draw(self, user_id, today):
        """执行一次抽奖：费用结算 → 发放奖励 → 称号/周常评估。

        返回 {"ok": True, "texts": [解锁通知?, 主结果, 周常通知?]}（保持原发送顺序）
        或 {"ok": False, "points": 当前积分}（积分不足，未扣费未抽奖）。
        """
        draw_count = self.dbmanager.lottery.draw_count(user_id, today)
        free_daily = draw_count == 0
        points = self.dbmanager.points.get(user_id)
        payment_exempt = False
        if not free_daily:
            rem = self.dbmanager.shop.waiver_remaining(user_id)
            if rem > 0:
                if random.random() < 0.3:
                    payment_exempt = True
                if not payment_exempt and points < self.COST:
                    return {"ok": False, "points": points}
                self.dbmanager.shop.pop_waiver(user_id)
            else:
                if points < self.COST:
                    return {"ok": False, "points": points}
            if not payment_exempt:
                utils.add_user_point(self.dbmanager, user_id, -self.COST)
                self.dbmanager.lottery.add_spent(user_id, self.COST)
        self.dbmanager.lottery.add_draw(user_id, today, 1)
        # ponytail: silent quest trigger, users check progress via /周常
        completed = on_quest_trigger(self.dbmanager, user_id, "lottery")
        cost_paid = 0 if free_daily else (0 if payment_exempt else self.COST)
        draw_cost_hint = (
            self.FREE_DRAW_HINT
            if free_daily
            else ("抽奖增强：本次不消耗积分" if payment_exempt else "本次消耗：1积分")
        )
        result = draw_reward(self.dbmanager, user_id)
        profile = self.dbmanager.lottery.profile(user_id)
        draw_count = profile["draw_count"] + 1
        duplicate_count = profile["duplicate_count"]
        zero_streak = profile["zero_streak"]
        max_zero_streak = profile["max_zero_streak"]
        has_hit_ten = profile["has_hit_ten"]
        total_zeros = profile["total_zeros"]

        texts = []
        if free_daily:
            free_mid = "{}\n".format(self.FREE_DRAW_HINT)
        elif payment_exempt:
            free_mid = "抽奖增强：本次不消耗积分\n"
        else:
            free_mid = ""

        if result["type"] == "points":
            reward = result["value"]
            utils.add_user_point(self.dbmanager, user_id, reward)
            if reward == 0:
                zero_streak += 1
                total_zeros += 1
                if zero_streak > max_zero_streak:
                    max_zero_streak = zero_streak
            else:
                zero_streak = 0
            if reward == 10:
                has_hit_ten = 1
            self.dbmanager.lottery.upsert_profile(
                user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten, total_zeros
            )
            unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
            if unlocked:
                texts.append(self._format_unlocked_titles(unlocked))
            net = reward - cost_paid
            now_points = self.dbmanager.points.get(user_id)
            if reward == 0:
                texts.append(
                    "*摇骰子* 居然什么都没有抽到呢……\n本次净变化：{}积分\n{}当前积分：{}".format(
                        net, free_mid, now_points
                    )
                )
            else:
                texts.append(
                    "*摇骰子* 居然抽到了……{}点积分！\n本次净变化：{}积分\n{}当前积分：{}".format(
                        reward, net, free_mid, now_points
                    )
                )
        else:
            now_points = self.dbmanager.points.get(user_id)
            if result["type"] == "title_new":
                zero_streak = 0
                self.dbmanager.lottery.upsert_profile(
                    user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten, total_zeros
                )
                unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
                if unlocked:
                    texts.append(self._format_unlocked_titles(unlocked))
                title_id = result["value"]
                title_data = get_title_def(title_id) or {"name": "未知称号", "rarity": "unknown"}
                texts.append(
                    "*摇骰子* 居然抽到了……解锁称号 [{}] 「{}」 ({})！\n{}\n当前积分：{}".format(
                        title_id, title_data["name"], title_data["rarity"], draw_cost_hint, now_points
                    )
                )
            elif result["type"] == "title_duplicate":
                duplicate_count += 1
                zero_streak = 0
                self.dbmanager.lottery.upsert_profile(
                    user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten, total_zeros
                )
                unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
                if unlocked:
                    texts.append(self._format_unlocked_titles(unlocked))
                title_id = result["value"]
                title_data = get_title_def(title_id) or {"name": "未知称号", "rarity": "unknown"}
                rebate = result.get("rebate", 0)
                texts.append(
                    "*摇骰子* 居然抽到了……已拥有称号 [{}] 「{}」 ({})！\n已返还{}积分。\n{}当前积分：{}".format(
                        title_id, title_data["name"], title_data["rarity"], rebate, free_mid, now_points
                    )
                )
            elif result["type"] == "title_none":
                zero_streak = 0
                self.dbmanager.lottery.upsert_profile(
                    user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten, total_zeros
                )
                unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
                if unlocked:
                    texts.append(self._format_unlocked_titles(unlocked))
                texts.append(
                    "*摇骰子* 居然抽到了……{}称号位！\n当前没有可抽取的该稀有度称号。\n{}当前积分：{}".format(
                        result["rarity"], free_mid, now_points
                    )
                )
            else:
                texts.append(
                    "*摇骰子* 居然抽到了……{}！\n{}\n当前积分：{}".format(
                        result["value"], draw_cost_hint, now_points
                    )
                )

        if completed:
            names = " | ".join(f"{q['name']} +{q['reward']}" for q in completed)
            texts.append(f"🎯 {names}")

        return {"ok": True, "texts": texts}

    def _handle_single_draw(self, user_id):
        today = datetime.now().strftime("%Y-%m-%d")
        draw_count = self.dbmanager.lottery.draw_count(user_id, today)
        has_checkin_today = self.dbmanager.checkin.has_on_date(user_id, today)
        max_draw = self._max_draw(user_id, today)
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
        outcome = self._perform_single_draw(user_id, today)
        if not outcome["ok"]:
            self.api.send_msg(
                at(user_id),
                text("抽奖需要1点积分，你现在只有{}点喵".format(outcome["points"])),
            )
            return
        self.api.send_msg(at(user_id), text(outcome["texts"][0]))
        for extra in outcome["texts"][1:]:
            self.api.send_msg(text(extra))

    def _forward_node(self, text_body: str) -> dict:
        """合并转发单条子消息节点（OneBot11 格式：user_id/nickname/content）。"""
        return {
            "type": "node",
            "data": {
                "user_id": int(BOT_QQ),
                "nickname": NICKNAME,
                "content": [text(text_body)],
            },
        }

    def _handle_bulk_draw(self, user_id):
        today = datetime.now().strftime("%Y-%m-%d")
        has_checkin_today = self.dbmanager.checkin.has_on_date(user_id, today)
        max_draw = self._max_draw(user_id, today)
        draw_count = self.dbmanager.lottery.draw_count(user_id, today)
        remaining = max_draw - draw_count
        if remaining <= 0:
            self.api.send_msg(
                at(user_id),
                text("今天抽卡次数已用完（{}/{}）。{}。".format(
                    draw_count,
                    max_draw,
                    "你今天已打卡，可抽5次" if has_checkin_today else "今日未打卡，默认可抽2次",
                )),
            )
            return
        nodes = []
        done = 0
        for _ in range(remaining):
            outcome = self._perform_single_draw(user_id, today)
            if not outcome["ok"]:
                nodes.append(self._forward_node(
                    "积分不足，停止抽奖（已完成 {} 次，剩余 {} 次未抽）。当前积分：{}".format(
                        done, remaining - done, outcome["points"]
                    )
                ))
                break
            done += 1
            # 每次抽奖一条子消息：解锁通知 + 主结果 + 周常通知
            nodes.append(self._forward_node("\n".join(outcome["texts"])))
        nodes.insert(0, self._forward_node("🎲 一键抽奖完成：共 {} 次".format(done)))
        self.api.send_forward_nodes(nodes)

    def handle(self):
        if self.bot_event.user_id == None:
            return
        user_id = self.bot_event.user_id
        if self.cmd in ("/抽卡消费", "/抽卡消費"):
            target_user_id = self._extract_target_user_id(user_id)
            spent = self.dbmanager.lottery.spent(target_user_id)
            self.api.send_msg(at(user_id), text(f"用户 {target_user_id} 累计抽卡消费：{spent} 积分"))
            return
        if self.cmd in ("/一键抽奖", "/一鍵抽獎"):
            self._handle_bulk_draw(user_id)
            return
        self._handle_single_draw(user_id)
