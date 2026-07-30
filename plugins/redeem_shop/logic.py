"""
积分商店货架与刷新逻辑：数据库 shop_stock 为唯一货架；内存 SHOP_ITEMS 由库表同步。
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable

from plugins.title import TITLE_DEFS, get_title_def

if TYPE_CHECKING:
    from . import RedeemShopPlugin

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
    if plugin.dbmanager.titles.has(uid, title_id):
        raise RuntimeError("你已拥有该称号")
    if not plugin.dbmanager.titles.unlock(uid, title_id, commit=False):
        raise RuntimeError("称号发放失败")


def _grant_extra_draw_pack(plugin: "RedeemShopPlugin") -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    # 7 个自然日（含今日），至 6 天后 23:59:59 前均有效，按日期串比较
    until = (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")
    plugin.dbmanager.shop.set_draw_pack(uid, until, commit=False)


def _grant_checkin_boost(plugin: "RedeemShopPlugin") -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    plugin.dbmanager.shop.add_luck(uid, 10, commit=False)


def _grant_lottery_waiver(plugin: "RedeemShopPlugin") -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    plugin.dbmanager.shop.add_waiver(uid, 10, commit=False)


def _grant_lottery_refresh(plugin: "RedeemShopPlugin") -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    today = datetime.now().strftime("%Y-%m-%d")
    plugin.dbmanager.shop.clear_draw_count(uid, today, commit=False)


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
    rows = db.shop.all_stock()
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
    db.shop.replace_shelf(mapping)
    refresh_shop_items_from_database(db)
    return picked


def format_shop_shelf_lines(db) -> list[str]:
    """返回本周货架每条商品的文案行（含空行分隔）。"""
    refresh_shop_items_from_database(db)
    lines: list[str] = []
    for pid in sorted(SHOP_ITEMS.keys()):
        meta = SHOP_ITEMS[pid]
        cost = meta["cost"]
        desc = meta["description"]
        stock_n = db.shop.stock(pid)
        if stock_n is None:
            stock = "未上架"
        elif stock_n == -1:
            stock = "不限"
        else:
            stock = str(stock_n)
        lines.append(f"[{pid}] {desc}")
        lines.append(f"    售价 {cost} 积分｜剩余 {stock}")
        lines.append("")
    return lines


def format_shop_weekly_announcement(db) -> str:
    """每周刷新后发到群里的公告文案。"""
    shelf = format_shop_shelf_lines(db)
    lines = [
        "积分商店已刷新~",
        "发送 /商店 查看完整列表，或 /商店 <商品id> 兑换。（方括号里的是商品id）",
        "",
        "—— 本周货架 ——",
    ]
    if shelf:
        lines.extend(shelf)
    else:
        lines.append("本周暂无上架商品。")
    return "\n".join(lines).rstrip()