"""网页端积分商店（与 plugins/redeem_shop 逻辑一致，避免导入 plugins 包）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from core.database_manager import DbManager

from core.title_defs import TITLE_DEFS

TITLE_PRICE_BY_RARITY = {
    "common": 3,
    "rare": 6,
    "legendary": 10,
}

RARITY_LABEL = {"common": "普通", "rare": "稀有", "legendary": "传奇"}

GrantFn = Callable[[DbManager, str | int], None]

FIXED_ITEMS: dict[str, dict] = {
    "fn_extra_draw_pack": {
        "description": "额外抽卡补充包（7 天内每日 +2 次额外抽卡额度）",
        "cost": 6,
        "success_tip": "兑换成功，已获得额外抽卡补充（7 日有效）。剩余积分 {rest}。",
    },
    "fn_checkin_boost": {
        "description": "打卡增强（接下来 10 次打卡，每次 10% 概率 +1 积分）",
        "cost": 2,
        "success_tip": "兑换成功，打卡增强次数已入账。剩余积分 {rest}。",
    },
    "fn_lottery_boost": {
        "description": "抽奖增强（接下来 10 次付费抽奖，每次 30% 不消耗积分）",
        "cost": 3,
        "success_tip": "兑换成功，抽奖增强次数已入账。剩余积分 {rest}。",
    },
    "fn_lottery_refresh": {
        "description": "抽奖刷新（立刻清空今日已用抽卡次数）",
        "cost": 1,
        "success_tip": "兑换成功，今日抽卡次数已重置。剩余积分 {rest}。",
    },
}


def title_price_from_def(tdef: dict | None) -> int:
    r = (tdef or {}).get("rarity") or "common"
    if isinstance(r, str):
        r = r.strip().lower()
    return int(TITLE_PRICE_BY_RARITY.get(r, TITLE_PRICE_BY_RARITY["common"]))


def _grant_title(db: DbManager, user_id, title_id: int) -> None:
    if db.titles.has(user_id, title_id):
        raise RuntimeError("你已拥有该称号")
    if not db.titles.unlock(user_id, title_id, commit=False):
        raise RuntimeError("称号发放失败")


def _grant_extra_draw_pack(db: DbManager, user_id) -> None:
    until = (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")
    db.shop.set_draw_pack(user_id, until, commit=False)


def _grant_checkin_boost(db: DbManager, user_id) -> None:
    db.shop.add_luck(user_id, 10, commit=False)


def _grant_lottery_waiver(db: DbManager, user_id) -> None:
    db.shop.add_waiver(user_id, 10, commit=False)


def _grant_lottery_refresh(db: DbManager, user_id) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    db.shop.clear_draw_count(user_id, today, commit=False)


FIXED_GRANTS: dict[str, GrantFn] = {
    "fn_extra_draw_pack": _grant_extra_draw_pack,
    "fn_checkin_boost": _grant_checkin_boost,
    "fn_lottery_boost": _grant_lottery_waiver,
    "fn_lottery_refresh": _grant_lottery_refresh,
}


def _stock_label(stock_n: int | None) -> str:
    if stock_n is None:
        return "未上架"
    if stock_n == -1:
        return "不限"
    return str(stock_n)


def _build_catalog(db: DbManager) -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    for pid, _stock in db.shop.all_stock():
        pid = str(pid)
        if pid.startswith("title_"):
            try:
                tid = int(pid.split("_", 1)[1])
            except (ValueError, IndexError):
                continue
            tdef = TITLE_DEFS.get(tid) or {}
            nm = tdef.get("name", "?")
            rarity = (tdef.get("rarity") or "common")
            if isinstance(rarity, str):
                rarity = rarity.strip().lower()
            rc = RARITY_LABEL.get(rarity, str(rarity))
            catalog[pid] = {
                "description": f"解锁称号「{nm}」（{rc}）",
                "cost": title_price_from_def(tdef),
                "title_id": tid,
                "kind": "title",
                "success_tip": None,
            }
        elif pid in FIXED_ITEMS:
            meta = FIXED_ITEMS[pid]
            catalog[pid] = {
                "description": str(meta["description"]),
                "cost": int(meta["cost"]),
                "kind": "function",
                "success_tip": meta.get("success_tip"),
            }
    return catalog


def get_shop(user_id: str) -> dict:
    db = DbManager()
    catalog = _build_catalog(db)
    points = db.points.get(user_id)
    items: list[dict] = []

    for pid in sorted(catalog.keys()):
        meta = catalog[pid]
        stock_n = db.shop.stock(pid)
        owned = False
        if meta.get("kind") == "title":
            owned = db.titles.has(user_id, meta["title_id"])
        can_buy = stock_n is not None and stock_n != 0 and not owned
        items.append(
            {
                "id": pid,
                "description": meta["description"],
                "cost": meta["cost"],
                "stock": stock_n,
                "stock_label": _stock_label(stock_n),
                "owned": owned,
                "can_buy": can_buy and points >= meta["cost"],
                "affordable": points >= meta["cost"],
            }
        )

    return {
        "points": points,
        "items": items,
        "refresh_hint": "称号货架每周一 8:00 刷新；功能商品常驻。",
    }


def _success_message(product_id: str, meta: dict, rest: int) -> str:
    tip = meta.get("success_tip")
    if isinstance(tip, str) and tip.strip():
        try:
            return tip.format(rest=rest)
        except (KeyError, IndexError, ValueError):
            return tip
    if meta.get("kind") == "title":
        tid = meta.get("title_id")
        tdef = TITLE_DEFS.get(tid) or {}
        name = tdef.get("name", "?")
        return f"兑换成功，称号「{name}」已解锁。剩余积分 {rest}。"
    return f"兑换成功，剩余积分 {rest}。"


def redeem_shop_item(user_id: str, product_id: str) -> dict:
    product_id = product_id.strip()
    db = DbManager()
    catalog = _build_catalog(db)
    if product_id not in catalog:
        raise ValueError("未知商品，请刷新页面后重试")

    meta = catalog[product_id]
    cost = int(meta["cost"])
    points = db.points.get(user_id)
    if points < cost:
        raise ValueError(f"积分不足：需要 {cost}，当前 {points}。")

    if meta.get("kind") == "title":
        tid = meta["title_id"]
        if db.titles.has(user_id, tid):
            raise ValueError("你已拥有该称号，无需重复兑换")

        def grant() -> None:
            _grant_title(db, user_id, tid)

    elif product_id in FIXED_GRANTS:
        apply_fn = FIXED_GRANTS[product_id]

        def grant() -> None:
            apply_fn(db, user_id)

    else:
        raise ValueError("该商品暂不可兑换")

    ok, err = db.shop.redeem(product_id, user_id, cost, grant)
    if not ok:
        raise ValueError(err or "兑换失败")

    rest = db.points.get(user_id)
    return {
        "success": True,
        "product_id": product_id,
        "message": _success_message(product_id, meta, rest),
        "points": rest,
    }
