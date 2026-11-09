"""任务5.4：实际命令/定时插件只提交输出，业务与消息内容保持可验证。"""
from unittest.mock import Mock

import pytest

from core import config
from core.database_manager import DbManager
from core.event import Event
from core.plugin_dispatch import Operation
from core.message_output import MessageOutput
from plugins.title import TitlePlugin
from plugins.title.defs import TITLE_DEFS
from plugins.weekly_quest import WeeklyQuestPlugin, WeeklyQuestResetPlugin
from plugins.redeem_shop import RedeemShopPlugin, ShopManualRefreshPlugin, ShopWeeklyRotationPlugin


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "commands.db")
    value = DbManager()
    yield value
    value.conn.close()


def run(cls, db, command=None, target=("group", 10), extra=None, fail_send=False, enabled=None):
    raw = {"post_type": "message", "user_id": 42, "message_id": 1,
           "message": [{"type": "text", "data": {"text": command or ""}}] + (extra or [])}
    if target and target[0] == "group":
        raw["group_id"] = target[1]
    plugin = cls.__new__(cls)
    plugin.bot_event, plugin.dbmanager = Event(raw), db
    plugin.api = Mock()
    sent = []

    def send(request):
        sent.append(request)
        if fail_send:
            raise TimeoutError("internal-timeout")
        return 1

    op = Operation(enabled or {}, MessageOutput(send, target), subscriptions=[])
    plugin.operation = op
    if command is not None and hasattr(cls, "COMMANDS"):
        assert plugin.match("message")
    op.execute(cls.__module__.split(".")[1], plugin.handle)
    assert sent == []  # 处理期间没有真实发送
    plugin.api.send_msg.assert_not_called()
    plugin.api.send_forward_msg.assert_not_called()
    op.finish()
    count = len(sent)
    op.finish()
    assert len(sent) == count
    return sent, op


def body(request):
    return request.content if request.kind == "text" else "".join(
        seg["data"]["text"] for seg in request.content if seg["type"] == "text"
    )


@pytest.mark.parametrize("command,expected", [
    ("/称号", "用法："), ("/称号 当前", "没有装备"), ("/称号 随机", "没有可随机装备"),
    ("/称号一览", "还没有解锁"), ("/称号 详情", "请使用"), ("/称号 查看", "请使用"),
    ("/称号 999999", "没有这个称号编号"), ("/称号 不存在", "无法识别"),
    ("/称号 卸下", "已卸下"),
])
def test_title_command_branches(db, command, expected):
    sent, op = run(TitlePlugin, db, command)
    assert not op.failures
    assert expected in body(sent[-1])


@pytest.mark.parametrize("target", [("group", 10), ("private", 42)])
def test_title_owned_list_details_equip_and_random(db, target):
    tid = next(iter(TITLE_DEFS))
    db.titles.unlock(42, tid)
    sent, op = run(TitlePlugin, db, "/称号一览", target)
    assert sent[0].kind == "forward" and sent[0].target == target
    assert TITLE_DEFS[tid]["name"] in body(sent[0])
    for command, expected in ((f"/称号 详情 {tid}", "说明："), (f"/称号 {tid}", "已装备"),
                              (f"/称号 {tid}", "称号已装备"), ("/称号 随机", "已装备")):
        sent, op = run(TitlePlugin, db, command, target)
        assert not op.failures
        assert expected in body(sent[-1])


def test_weekly_query_and_cleanup(db):
    sent, op = run(WeeklyQuestPlugin, db, "/周常")
    assert len(sent) == 1 and sent[0].kind == "text"
    assert "打个卡先" in body(sent[0]) and "猛猛上瘾" in body(sent[0])
    db.quest.upsert_progress(42, 1, "2000-01-03", 1)
    sent, op = run(WeeklyQuestResetPlugin, db, target=None)
    assert not sent and not op.failures
    assert not db.quest.progress(42, "2000-01-03")


def test_shop_query_purchase_and_invalid_product(db):
    db.shop.replace_shelf({"fn_checkin_boost": -1})
    db.points.set(42, 10)
    sent, op = run(RedeemShopPlugin, db, "/商店", ("private", 42))
    assert sent[0].kind == "forward" and "fn_checkin_boost" in body(sent[0])
    sent, op = run(RedeemShopPlugin, db, "/商店 fn_checkin_boost", fail_send=True)
    assert not op.failures and len(sent) == 1
    assert "兑换成功" in body(sent[0])
    assert db.points.get(42) == 8 and db.shop.luck_remaining(42) == 10
    sent, op = run(RedeemShopPlugin, db, "/商店 nonexistent")
    assert "未知商品" in body(sent[0])


@pytest.mark.parametrize("cls,target", [(ShopManualRefreshPlugin, ("group", 10)),
                                        (ShopWeeklyRotationPlugin, ("group", 10)),
                                        (ShopWeeklyRotationPlugin, None)])
def test_shop_refresh_and_no_default_destination(db, cls, target):
    if target:
        # 目标群启用 redeem_shop 后才发公告（config-unification：公告检查目的地开关）
        db.conn.execute(
            "INSERT OR IGNORE INTO group_plugin_config VALUES (?, 'redeem_shop')", (target[1],))
        db.conn.commit()
    sent, op = run(cls, db, target=target)
    assert not op.failures
    assert db.shop.all_stock()
    assert len(sent) == (1 if target else 0)
    if sent:
        assert "已刷新" in body(sent[0])


def test_shop_title_purchase_respects_title_switch_before_spending(db):
    from plugins.redeem_shop.logic import title_price_from_def
    tid = next(iter(TITLE_DEFS))
    product = f"title_{tid}"
    db.shop.replace_shelf({product: 2})
    db.points.set(42, 20)
    before = list(db.conn.iterdump())
    sent, op = run(RedeemShopPlugin, db, f"/商店 {product}")
    assert not op.failures and "称号功能已关闭" in body(sent[0])
    assert list(db.conn.iterdump()) == before
    sent, op = run(RedeemShopPlugin, db, f"/商店 {product}", enabled={"title": True})
    assert not op.failures and "兑换成功" in body(sent[0])
    assert db.titles.has(42, tid)
    assert db.points.get(42) == 20 - title_price_from_def(TITLE_DEFS[tid])
    assert db.shop.stock(product) == 1


def test_shop_failures_do_not_expose_internal_details(db, monkeypatch):
    import plugins.redeem_shop as shop
    monkeypatch.setattr(shop, "weekly_refresh_shop_shelf", Mock(side_effect=RuntimeError("secret-internal-error")))
    sent, op = run(ShopManualRefreshPlugin, db)
    assert op.failures == ["redeem_shop"]
    assert "处理失败" in body(sent[0]) and "secret" not in body(sent[0])
    db.shop.replace_shelf({"fn_checkin_boost": -1})
    db.points.set(42, 10)
    monkeypatch.setattr(db.shop, "redeem", lambda *args: (False, "secret-internal-error"))
    sent, op = run(RedeemShopPlugin, db, "/商店 fn_checkin_boost")
    assert "请联系管理员" in body(sent[0]) and "secret" not in body(sent[0])
