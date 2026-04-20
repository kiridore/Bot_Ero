"""
积分商店：商品以 title_<id> 存在 shop_stock；内存 SHOP_ITEMS 由数据库同步。
每周一 8:00 清空货架并从 title.TITLE_DEFS 随机上架 4 个称号（4 积分、库存 2）。
"""

from __future__ import annotations

import random
from typing import Any, Callable

from core.base import Plugin, TimedHeartbeatPlugin
from core.cq import at, text
from core.logger import logger
from core.utils import register_plugin
from plugins.title import TITLE_DEFS, get_title_def


ShopApply = Callable[["RedeemShopPlugin"], None]

SHOP_ITEMS: dict[str, dict[str, Any]] = {}

WEEKLY_TITLE_COST = 4
WEEKLY_TITLE_STOCK = 2


def _grant_title(plugin: "RedeemShopPlugin", title_id: int) -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    if plugin.dbmanager.has_title(uid, title_id):
        raise RuntimeError("你已拥有该称号")
    if not plugin.dbmanager.unlock_title(uid, title_id, commit=False):
        raise RuntimeError("称号发放失败")


def refresh_shop_items_from_database(db) -> None:
    """根据 shop_stock 重建内存中的 SHOP_ITEMS（进程重启后与数据库一致）。"""
    global SHOP_ITEMS
    rows = db.get_all_shop_stock()
    SHOP_ITEMS.clear()
    for pid, _stock in rows:
        if not str(pid).startswith("title_"):
            continue
        try:
            tid = int(str(pid).split("_", 1)[1])
        except (ValueError, IndexError):
            continue
        tdef = get_title_def(tid) or {}
        nm = tdef.get("name", "?")
        SHOP_ITEMS[pid] = {
            "description": f"解锁称号「{nm}」",
            "cost": WEEKLY_TITLE_COST,
            "initial_stock": int(_stock),
            "apply": (lambda p, tt=tid: _grant_title(p, tt)),
        }


def weekly_refresh_shop_shelf(db) -> list[int]:
    """清空商店，随机选 4 个称号上架（固定售价与库存），并同步内存。"""
    all_ids = list(TITLE_DEFS.keys())
    if not all_ids:
        db.replace_entire_shop_shelf({})
        refresh_shop_items_from_database(db)
        return []
    k = min(4, len(all_ids))
    picked = random.sample(all_ids, k=k)
    mapping = {f"title_{tid}": WEEKLY_TITLE_STOCK for tid in picked}
    db.replace_entire_shop_shelf(mapping)
    refresh_shop_items_from_database(db)
    return picked


@register_plugin
class ShopWeeklyRotationPlugin(TimedHeartbeatPlugin):
    name = "shop_weekly_rotation"
    description = "每周一 8:00 刷新积分商店称号上架。"

    RUN_AT = "08:00"
    RUN_WEEKDAYS = [1]

    def match(self, event_type):
        return self.should_run_on_heartbeat(event_type)

    def handle(self):
        try:
            picked = weekly_refresh_shop_shelf(self.dbmanager)
            logger.info(
                "积分商店已刷新（本周 %s 个称号）：%s",
                len(picked),
                picked,
            )
        except Exception as e:
            logger.exception("积分商店周刷新失败: %s", e)


@register_plugin
class RedeemShopPlugin(Plugin):
    name = "redeem_shop"
    description = "使用积分兑换商店称号或权益。"

    def match(self, event_type):
        return event_type == "message" and self.on_command("/兑换")

    def _format_list(self) -> str:
        refresh_shop_items_from_database(self.dbmanager)
        lines = ["—— 积分商店 ——", "用法：/兑换 <商品id>", ""]
        if not SHOP_ITEMS:
            lines.append("本周暂无上架商品（每周一 8:00 刷新）。")
            lines.append("")
            lines.append("发送 /兑换 <商品id> 兑换。")
            return "\n".join(lines).rstrip()
        for pid in sorted(SHOP_ITEMS.keys()):
            meta = SHOP_ITEMS[pid]
            cost = meta["cost"]
            desc = meta["description"]
            stock_n = self.dbmanager.get_shop_stock(pid)
            if stock_n is None:
                stock = "未上架"
            elif stock_n == -1:
                stock = "不限"
            else:
                stock = str(stock_n)
            lines.append(f"[{pid}] {desc}")
            lines.append(f"    售价 {cost} 积分｜剩余 {stock}")
            lines.append("")
        lines.append("发送 /兑换 <商品id> 兑换。")
        return "\n".join(lines).rstrip()

    def handle(self):
        if self.bot_event.user_id is None:
            return
        user_id = self.bot_event.user_id
        args = [p for p in (getattr(self, "args", []) or []) if p]
        refresh_shop_items_from_database(self.dbmanager)

        if len(args) < 2:
            self.api.send_forward_msg([at(user_id), text(self._format_list())])
            return

        product_id = args[1].strip()
        if product_id not in SHOP_ITEMS:
            self.api.send_msg(at(user_id), text(f"未知商品 id：{product_id}，发送 /兑换 查看列表。"))
            return

        meta = SHOP_ITEMS[product_id]
        cost = int(meta["cost"])
        apply_fn: ShopApply = meta["apply"]
        if apply_fn is None:
            self.api.send_msg(at(user_id), text("该商品未配置发放逻辑。"))
            return

        points = self.dbmanager.get_user_point(user_id)
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
            if tid is not None and self.dbmanager.has_title(uid, tid):
                self.api.send_msg(at(user_id), text("你已拥有该称号，无需重复兑换。"))
                return

        def grant() -> None:
            apply_fn(self)

        ok, err = self.dbmanager.redeem_shop_item(product_id, user_id, cost, grant)
        if not ok:
            self.api.send_msg(at(user_id), text(f"兑换失败：{err}"))
            return

        rest = self.dbmanager.get_user_point(user_id)
        if product_id.startswith("title_"):
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
