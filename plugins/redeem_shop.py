"""
积分商店：数据库 shop_stock 为唯一货架；内存 SHOP_ITEMS 由库表同步。

每周一 8:00 清空后：随机上架 4 个称号（库存各 2，售价按稀有度 common=3 / rare=6 / legendary=10），
并合并固定功能商品（FIXED_FUNCTION_ITEMS）。

功能向效果存于 shop_user_buffs 表，由打卡/抽卡插件消费。
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any, Callable

from core.base import Plugin, TimedHeartbeatPlugin
from core.cq import at, text
from core.logger import logger
from core.utils import register_plugin
from plugins.title import TITLE_DEFS, get_title_def

ShopApply = Callable[["RedeemShopPlugin"], None]

SHOP_ITEMS: dict[str, dict[str, Any]] = {}

WEEKLY_TITLE_STOCK = 2

TITLE_PRICE_BY_RARITY = {
    "common": 3,
    "rare": 6,
    "legendary": 10,
}


def title_price_from_def(tdef: dict[str, Any] | None) -> int:
    r = (tdef or {}).get("rarity") or "common"
    if isinstance(r, str):
        r = r.strip().lower()
    return int(TITLE_PRICE_BY_RARITY.get(r, TITLE_PRICE_BY_RARITY["common"]))


def _grant_title(plugin: "RedeemShopPlugin", title_id: int) -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    if plugin.dbmanager.has_title(uid, title_id):
        raise RuntimeError("你已拥有该称号")
    if not plugin.dbmanager.unlock_title(uid, title_id, commit=False):
        raise RuntimeError("称号发放失败")


def _grant_extra_draw_pack(plugin: "RedeemShopPlugin") -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    # 7 个自然日（含今日），至 6 天后 23:59:59 前均有效，按日期串比较
    until = (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")
    plugin.dbmanager.set_extra_draw_pack_until(uid, until, commit=False)


def _grant_checkin_boost(plugin: "RedeemShopPlugin") -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    plugin.dbmanager.add_shop_checkin_luck(uid, 10, commit=False)


def _grant_lottery_waiver(plugin: "RedeemShopPlugin") -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    plugin.dbmanager.add_shop_lottery_waiver(uid, 10, commit=False)


def _grant_lottery_refresh(plugin: "RedeemShopPlugin") -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    today = datetime.now().strftime("%Y-%m-%d")
    plugin.dbmanager.clear_lottery_draw_count_for_date(uid, today, commit=False)


FIXED_FUNCTION_ITEMS: dict[str, dict[str, Any]] = {
    "fn_extra_draw_pack": {
        "description": "额外抽卡补充包（7 天内每日 +2 次额外抽卡额度）",
        "cost": 6,
        "stock": -1,
        "apply": _grant_extra_draw_pack,
        "success_tip": "兑换成功，已获得额外抽卡补充（7 日有效）。剩余积分 {rest}。",
    },
    "fn_checkin_boost": {
        "description": "打卡增强（接下来 10 次打卡，每次 10% 概率 +1 积分）",
        "cost": 2,
        "stock": -1,
        "apply": _grant_checkin_boost,
        "success_tip": "兑换成功，打卡增强次数已入账。剩余积分 {rest}。",
    },
    "fn_lottery_boost": {
        "description": "抽奖增强（接下来 10 次付费抽奖，每次 30% 不消耗积分）",
        "cost": 3,
        "stock": -1,
        "apply": _grant_lottery_waiver,
        "success_tip": "兑换成功，抽奖增强次数已入账。剩余积分 {rest}。",
    },
    "fn_lottery_refresh": {
        "description": "抽奖刷新（立刻清空今日已用抽卡次数）",
        "cost": 1,
        "stock": -1,
        "apply": _grant_lottery_refresh,
        "success_tip": "兑换成功，今日抽卡次数已重置。剩余积分 {rest}。",
    },
}


def _fixed_shop_stock_mapping() -> dict[str, int]:
    out: dict[str, int] = {}
    for pid, meta in FIXED_FUNCTION_ITEMS.items():
        out[pid] = int(meta["stock"])
    return out


def refresh_shop_items_from_database(db) -> None:
    """根据 shop_stock 重建内存中的 SHOP_ITEMS（进程重启后与数据库一致）。"""
    global SHOP_ITEMS
    rows = db.get_all_shop_stock()
    SHOP_ITEMS.clear()
    for pid, _stock in rows:
        pid = str(pid)
        if pid.startswith("title_"):
            try:
                tid = int(pid.split("_", 1)[1])
            except (ValueError, IndexError):
                continue
            tdef = get_title_def(tid) or {}
            nm = tdef.get("name", "?")
            rarity = (tdef.get("rarity") or "common")
            if isinstance(rarity, str):
                rarity = rarity.strip().lower()
            rc = {"common": "普通", "rare": "稀有", "legendary": "传奇"}.get(rarity, str(rarity))
            cost = title_price_from_def(tdef)
            SHOP_ITEMS[pid] = {
                "description": f"解锁称号「{nm}」（{rc}）",
                "cost": cost,
                "initial_stock": int(_stock),
                "apply": (lambda p, tt=tid: _grant_title(p, tt)),
            }
            continue
        if pid in FIXED_FUNCTION_ITEMS:
            meta = FIXED_FUNCTION_ITEMS[pid]
            SHOP_ITEMS[pid] = {
                "description": str(meta["description"]),
                "cost": int(meta["cost"]),
                "initial_stock": int(_stock),
                "apply": meta["apply"],
                "success_tip": meta.get("success_tip"),
            }


def weekly_refresh_shop_shelf(db) -> list[int]:
    """清空商店：随机 4 个称号 + 固定功能商品，并同步内存。"""
    all_ids = list(TITLE_DEFS.keys())
    mapping: dict[str, int] = dict(_fixed_shop_stock_mapping())
    picked: list[int] = []
    if all_ids:
        k = min(4, len(all_ids))
        picked = random.sample(all_ids, k=k)
        for tid in picked:
            mapping[f"title_{tid}"] = WEEKLY_TITLE_STOCK
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
                "积分商店已刷新（本周随机称号 %s 个）：%s",
                len(picked),
                picked,
            )
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
