"""任务1.1：冻结既有奖励数值和结果，不从待测常量计算期望值。"""
import sqlite3
from types import SimpleNamespace

import pytest

from core.db._base import init_schema
from core.db.checkin import CheckinManager
from core.db.lottery import LotteryManager
from core.db.points import PointsManager
from core.db.quest import QuestManager
from core.db.titles import TitlesManager
from plugins.lottery import rewards as lottery_rewards
from plugins.weekly_quest import engine


@pytest.fixture
def db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    init_schema(conn, conn.cursor())
    monkeypatch.setattr(engine, "get_monday_to_monday", lambda: ("2026-10-05 08:00:00", "2026-10-12 08:00:00"))
    value = SimpleNamespace(conn=conn, checkin=CheckinManager(conn), lottery=LotteryManager(conn),
                            points=PointsManager(conn), quest=QuestManager(conn), titles=TitlesManager(conn))
    value.points.set(42, 0)
    yield value
    conn.close()


def test_checkin_weekly_rewards_baseline(db):
    db.conn.executemany("INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)",
                       [(42, f"2026-10-{day:02} 12:00:00", "test") for day in range(5, 12)])
    db.conn.commit()
    assert engine.on_quest_trigger(db, 42, "checkin") == [
        {"name": "打个卡先", "reward": 1},
        {"name": "三连打卡", "reward": 2},
        {"name": "一周都打了", "reward": 3},
    ]
    assert db.points.get(42) == 6
    assert db.quest.completion(42) == 3
    assert engine.on_quest_trigger(db, 42, "checkin") == []
    db.conn.execute("DELETE FROM checkin_records")
    db.conn.commit()
    assert [q["id"] for q in engine.on_quest_rollback(db, 42, "checkin")] == [1, 2, 3]
    assert db.points.get(42) == 0
    assert db.quest.completion(42) == 3


def test_lottery_weekly_rewards_baseline(db):
    db.lottery.add_draw(42, "2026-10-06", 15)
    assert engine.on_quest_trigger(db, 42, "lottery") == [
        {"name": "随便抽抽", "reward": 1},
        {"name": "猛猛上瘾", "reward": 2},
        {"name": "抽卡享受者", "reward": 5},
    ]
    assert db.points.get(42) == 8
    assert db.quest.completion(42) == 3


def test_shop_prices_and_stock_baseline():
    from plugins.redeem_shop.logic import TITLE_PRICE_BY_RARITY, WEEKLY_TITLE_STOCK, FIXED_FUNCTION_ITEMS
    assert TITLE_PRICE_BY_RARITY == {"common": 3, "rare": 6, "legendary": 10}
    assert WEEKLY_TITLE_STOCK == 2
    assert {key: item["cost"] for key, item in FIXED_FUNCTION_ITEMS.items()} == {
        "fn_extra_draw_pack": 6, "fn_checkin_boost": 2, "fn_lottery_boost": 3, "fn_lottery_refresh": 1,
    }


def test_lottery_distribution_baseline():
    assert lottery_rewards.REWARD_TABLE == [
        (31.0, {"type": "points", "value": 0}),
        (28.0, {"type": "points", "value": 1}),
        (10.0, {"type": "points", "value": 2}),
        (6.0, {"type": "points", "value": 3}),
        (3.0, {"type": "points", "value": 5}),
        (0.8, {"type": "points", "value": 8}),
        (0.2, {"type": "points", "value": 10}),
        (12.0, {"type": "title_roll", "rarity": "common"}),
        (5.0, {"type": "title_roll", "rarity": "rare"}),
        (4.0, {"type": "title_roll", "rarity": "legendary"}),
    ]


@pytest.mark.parametrize("rarity,refund", [("common", 1), ("rare", 2), ("legendary", 3)])
def test_duplicate_title_refund_baseline(db, monkeypatch, rarity, refund):
    monkeypatch.setattr(lottery_rewards.random, "choice", lambda items: items[0])
    first = lottery_rewards.draw_title_by_rarity(db, 42, rarity)
    assert first["type"] == "title_new"
    second = lottery_rewards.draw_title_by_rarity(db, 42, rarity)
    assert second == {"type": "title_duplicate", "value": first["value"], "rarity": rarity, "rebate": refund}
    assert db.points.get(42) == refund
