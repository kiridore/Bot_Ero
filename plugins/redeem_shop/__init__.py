"""
积分商店插件入口：周刷新、管理员手动刷新、用户兑换。
功能向效果存于 shop_user_buffs 表，由打卡/抽卡插件消费。
"""

from __future__ import annotations

from core.base import Plugin, TimedHeartbeatPlugin
from core.cq import at, text
from core.logger import logger
from core.utils import register_plugin
from plugins.title import get_title_def

from .logic import (
    SHOP_ITEMS,
    ShopApply,
    format_shop_shelf_lines,
    format_shop_weekly_announcement,
    refresh_shop_items_from_database,
    weekly_refresh_shop_shelf,
)


@register_plugin
class ShopWeeklyRotationPlugin(TimedHeartbeatPlugin):
    name = "shop_weekly_rotation"
    description = "每周一 8:00 刷新积分商店并在群内公告本周货架。"

    RUN_AT = "08:00"
    RUN_WEEKDAYS = [1]

    def match(self, event_type):
        return self.should_run_on_heartbeat(event_type)

    def handle(self):
        try:
            picked = weekly_refresh_shop_shelf(self.dbmanager)
            logger.info(
                "积分商店已刷新（本周随机称号 %s 个）：%s",
                len(picked),
                picked,
            )
            self.api.send_msg(text(format_shop_weekly_announcement(self.dbmanager)))
        except Exception as e:
            logger.exception("积分商店周刷新失败: %s", e)


@register_plugin
class ShopManualRefreshPlugin(Plugin):
    name = "shop_manual_refresh"
    description = "管理员指令：立刻刷新积分商店货架。"

    def match(self, event_type):
        return (
            event_type == "message"
            and self.admin_user()
            and self.on_full_match("/刷新商店")
        )

    def handle(self):
        if self.bot_event.user_id is None:
            return
        uid = self.bot_event.user_id
        try:
            picked = weekly_refresh_shop_shelf(self.dbmanager)
            logger.info("管理员手动刷新积分商店（随机称号 id）：%s", picked)
            self.api.send_msg(
                at(uid),
                text(f"商店已刷新。本周随机上架称号（共 {len(picked)} 个）：{picked}"),
            )
        except Exception as e:
            logger.exception("管理员刷新商店失败: %s", e)
            self.api.send_msg(at(uid), text(f"刷新失败：{e}"))


@register_plugin
class RedeemShopPlugin(Plugin):
    name = "redeem_shop"
    description = "使用积分兑换商店称号或权益。"

    def match(self, event_type):
        return event_type == "message" and self.on_command("/商店")

    def _format_list(self) -> str:
        lines = ["—— 积分商店 ——", "用法：/商店 <商品id>", ""]
        shelf = format_shop_shelf_lines(self.dbmanager)
        if not shelf:
            lines.append("本周暂无上架商品（每周一 8:00 刷新）。")
            lines.append("")
            lines.append("发送 /商店 <商品id> 兑换。")
            return "\n".join(lines).rstrip()
        lines.extend(shelf)
        lines.append("发送 /商店 <商品id> 兑换。")
        return "\n".join(lines).rstrip()

    def handle(self):
        if self.bot_event.user_id is None:
            return
        user_id = self.bot_event.user_id
        args = [p for p in (getattr(self, "args", []) or []) if p]
        refresh_shop_items_from_database(self.dbmanager)

        if len(args) < 2:
            self.api.send_forward_msg([text(self._format_list())])
            return

        product_id = args[1].strip()
        if product_id not in SHOP_ITEMS:
            self.api.send_msg(at(user_id), text(f"未知商品 id：{product_id}，发送 /商店 查看列表。"))
            return

        meta = SHOP_ITEMS[product_id]
        cost = int(meta["cost"])
        apply_fn: ShopApply = meta["apply"]
        if apply_fn is None:
            self.api.send_msg(at(user_id), text("该商品未配置发放逻辑。"))
            return

        points = self.dbmanager.points.get(user_id)
        if points < cost:
            self.api.send_msg(
                at(user_id),
                text(f"积分不足：需要 {cost}，当前 {points}。"),
            )
            return

        uid = user_id
        if product_id.startswith("title_"):
            try:
                tid = int(product_id.split("_", 1)[1])
            except (ValueError, IndexError):
                tid = None
            if tid is not None and self.dbmanager.titles.has(uid, tid):
                self.api.send_msg(at(user_id), text("你已拥有该称号，无需重复兑换。"))
                return

        def grant() -> None:
            apply_fn(self)

        ok, err = self.dbmanager.shop.redeem(product_id, user_id, cost, grant)
        if not ok:
            self.api.send_msg(at(user_id), text(f"兑换失败：{err}"))
            return

        rest = self.dbmanager.points.get(user_id)
        tip = meta.get("success_tip")
        if isinstance(tip, str) and tip.strip():
            try:
                msg = tip.format(rest=rest)
            except (KeyError, IndexError, ValueError):
                msg = tip
        elif product_id.startswith("title_"):
            try:
                tid = int(product_id.split("_", 1)[1])
                tdef = get_title_def(tid) or {}
                name = tdef.get("name", "?")
                msg = f"兑换成功，称号「{name}」已解锁。剩余积分 {rest}。"
            except (ValueError, IndexError):
                msg = f"兑换成功，剩余积分 {rest}。"
        else:
            msg = f"兑换成功，剩余积分 {rest}。"
        self.api.send_msg(at(user_id), text(msg))