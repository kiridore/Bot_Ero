"""
积分商店：商品定义在内存 SHOP_ITEMS；库存仅在数据库 shop_stock。
"""

from __future__ import annotations

from typing import Any, Callable

from core.base import Plugin
from core.cq import at, text
from core.utils import register_plugin
from plugins.title import get_title_def


ShopApply = Callable[["RedeemShopPlugin"], None]

SHOP_ITEMS: dict[str, dict[str, Any]] = {
    "title_43": {
        "description": "解锁稀有称号「卷」",
        "cost": 40,
        "initial_stock": 10,
        "apply": None,
    },
    "title_51": {
        "description": "解锁传奇称号「我还没有睡饱」",
        "cost": 120,
        "initial_stock": 3,
        "apply": None,
    },
    "points_pack": {
        "description": "小额积分包（支付10积分，到账10积分）",
        "cost": 10,
        "initial_stock": -1,
        "apply": None,
    },
}


def _grant_title(plugin: "RedeemShopPlugin", title_id: int) -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    if plugin.dbmanager.has_title(uid, title_id):
        raise RuntimeError("你已拥有该称号")
    if not plugin.dbmanager.unlock_title(uid, title_id, commit=False):
        raise RuntimeError("称号发放失败")


def _grant_points_pack(plugin: "RedeemShopPlugin", bonus: int) -> None:
    uid = plugin.bot_event.user_id
    if uid is None:
        raise RuntimeError("无法识别用户")
    plugin.dbmanager.adjust_user_points(uid, bonus, commit=False)


def _wire_applies() -> None:
    SHOP_ITEMS["title_43"]["apply"] = lambda p: _grant_title(p, 43)
    SHOP_ITEMS["title_51"]["apply"] = lambda p: _grant_title(p, 51)
    SHOP_ITEMS["points_pack"]["apply"] = lambda p: _grant_points_pack(p, 10)


_wire_applies()

_shop_stock_ready = False


def _ensure_shop_rows(db) -> None:
    global _shop_stock_ready
    if _shop_stock_ready:
        return
    for pid, meta in SHOP_ITEMS.items():
        db.ensure_shop_stock(pid, int(meta["initial_stock"]))
    _shop_stock_ready = True


def _stock_label(db, product_id: str) -> str:
    n = db.get_shop_stock(product_id)
    if n is None:
        return "未上架"
    if n == -1:
        return "不限"
    return str(n)


@register_plugin
class RedeemShopPlugin(Plugin):
    name = "redeem_shop"
    description = "使用积分兑换商店称号或权益。"

    def match(self, event_type):
        return event_type == "message" and self.on_command("/兑换")

    def _format_list(self) -> str:
        _ensure_shop_rows(self.dbmanager)
        lines = ["—— 积分商店 ——", "用法：/兑换 <商品id>", ""]
        for pid in sorted(SHOP_ITEMS.keys()):
            meta = SHOP_ITEMS[pid]
            cost = meta["cost"]
            desc = meta["description"]
            stock = _stock_label(self.dbmanager, pid)
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
        _ensure_shop_rows(self.dbmanager)

        if len(args) < 2:
            self.api.send_msg(at(user_id), text(self._format_list()))
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
        elif product_id == "points_pack":
            msg = f"兑换成功，积分已入账。剩余积分 {rest}。"
        else:
            msg = f"兑换成功，剩余积分 {rest}。"
        self.api.send_msg(at(user_id), text(msg))
