"""单抽/一键抽奖经真实通知处理，覆盖原子结算、开关、重放和输出。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from unittest.mock import Mock

import pytest

from core import config
from core.database_manager import DbManager
from core.event import Event
from core.message_output import MessageOutput
from core.plugin_dispatch import Operation
from plugins.lottery import LotteryPlugin, engine


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "lottery-events.db")
    monkeypatch.setattr(engine, "draw_reward", lambda *args, **kwargs: {"type": "points", "value": 2})
    value = DbManager()
    value.points.set(42, 0)
    yield value
    value.conn.close()


def run(db, command="/一键抽奖", mid=1, disabled=(), private=False):
    raw = {"user_id": 42, "message_id": mid, "post_type": "message", "message": [
        {"type": "text", "data": {"text": command}},
    ]}
    if not private:
        raw["group_id"] = 10
    sent = []
    op = Operation({key: key not in disabled for key in ("lottery", "title", "weekly_quest", "redeem_shop")},
                   MessageOutput(lambda r: sent.append(r) or 1, ("private", 42) if private else ("group", 10)))
    p = LotteryPlugin.__new__(LotteryPlugin)
    p.bot_event, p.dbmanager, p.operation, p.api = Event(raw), db, op, Mock()
    assert p.match("message")
    assert op.execute("lottery", p.handle)
    assert not sent
    op.finish()
    p.api.send_msg.assert_not_called()
    p.api.send_forward_nodes.assert_not_called()
    return op, sent


def node_text(node):
    return node["data"]["content"][0]["data"]["text"]


@pytest.mark.parametrize("private", [False, True])
def test_bulk_quest_results_stay_in_each_draw_node(db, private):
    db.checkin.insert(42, ["test.png"])
    op, sent = run(db, private=private)
    assert not op.failures
    assert len(sent) == 1 and sent[0].kind == "nodes"
    nodes = sent[0].content
    assert len(nodes) == 6
    assert "共 5 次" in node_text(nodes[0])
    assert "🎯 随便抽抽 +1" in node_text(nodes[3])
    assert "当前积分：5" in node_text(nodes[3])
    assert node_text(nodes[3]).index("摇骰子") < node_text(nodes[3]).index("🎯")
    assert all("🎯" not in node_text(nodes[i]) for i in (1, 2, 4, 5))
    assert db.points.get(42) == 7
    assert db.lottery.spent(42) == 4
    assert db.conn.execute("SELECT COUNT(*) FROM lottery_operation_receipts").fetchone()[0] == 5


@pytest.mark.parametrize("edition", ["private", "community"])
def test_plugin_switch_behavior_is_shared_across_editions(db, monkeypatch, edition):
    monkeypatch.setattr(config, "EDITION", edition)
    db.checkin.insert(42, ["test.png"])
    op, sent = run(db, disabled=("weekly_quest", "redeem_shop"))
    assert not op.failures
    assert db.points.get(42) == 6
    assert db.conn.execute("SELECT COUNT(*) FROM quest_progress").fetchone()[0] == 0
    assert len(sent) == 1 and len(sent[0].content) == 6


def test_disable_quest_does_not_change_draws_or_grant_quest_rewards(db):
    db.checkin.insert(42, ["test.png"])
    op, sent = run(db, disabled=("weekly_quest",))
    assert not op.failures
    assert db.points.get(42) == 6
    assert db.conn.execute("SELECT COUNT(*) FROM quest_progress").fetchone()[0] == 0
    assert all("🎯" not in node_text(node) for node in sent[0].content)


def test_disable_shop_does_not_consume_waiver_or_extra_quota(db):
    db.shop.add_waiver(42, 10)
    db.shop.set_draw_pack(42, datetime.now().strftime("%Y-%m-%d"))
    op, sent = run(db, disabled=("redeem_shop",))
    assert not op.failures
    assert db.lottery.draw_count(42, datetime.now().strftime("%Y-%m-%d")) == 2
    assert db.shop.waiver_remaining(42) == 10
    assert db.lottery.spent(42) == 1


def test_repeated_command_does_not_redraw_or_retrigger_rewards(db):
    run(db)
    before = list(db.conn.iterdump())
    op, sent = run(db)
    assert not op.failures
    assert list(db.conn.iterdump()) == before
    assert len(sent) == 1 and "已处理" in sent[0].content


def test_second_draw_failure_rolls_back_cost_and_preserves_first_result(db, monkeypatch):
    calls = []
    def draw(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("secret internal failure")
        return {"type": "points", "value": 2}
    monkeypatch.setattr(engine, "draw_reward", draw)
    op, sent = run(db)
    assert op.failures == ["lottery"]
    assert len(calls) == 2
    assert db.points.get(42) == 2
    assert db.lottery.spent(42) == 0
    assert db.lottery.profile(42)["draw_count"] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM lottery_draw_log").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM lottery_operation_receipts").fetchone()[0] == 1
    assert sent[0].kind == "nodes" and "共 1 次" in node_text(sent[0].content[0])
    assert "secret" not in str([r.content for r in sent])


def test_receipt_failure_rolls_back_every_draw_write(db):
    db.points.set(42, 5)
    db.conn.execute("""CREATE TRIGGER reject_lottery_receipt BEFORE INSERT ON lottery_operation_receipts
                      BEGIN SELECT RAISE(ABORT, 'receipt failure'); END""")
    db.conn.commit()
    op, sent = run(db, command="/抽奖")
    assert op.failures == ["lottery"]
    assert db.points.get(42) == 5
    assert db.lottery.draw_count(42, datetime.now().strftime("%Y-%m-%d")) == 0
    assert db.conn.execute("SELECT COUNT(*) FROM lottery_draw_log").fetchone()[0] == 0
    assert db.conn.execute("SELECT COUNT(*) FROM quest_progress").fetchone()[0] == 0


def test_quest_failure_does_not_stop_draws_or_title_processing(db, monkeypatch):
    from plugins.weekly_quest import events
    monkeypatch.setattr(events, "on_quest_trigger", Mock(side_effect=RuntimeError("internal quest error")))
    op, sent = run(db)
    assert op.failures == ["weekly_quest", "weekly_quest"]
    assert db.points.get(42) == 3
    assert len(sent[0].content) == 3 and sent[0].kind == "nodes"
    assert "internal quest error" not in str([r.content for r in sent])


def test_real_title_prize_and_duplicate_rebate(db, monkeypatch):
    from plugins.lottery import rewards
    monkeypatch.setattr(engine, "draw_reward", rewards.draw_reward)
    monkeypatch.setattr(rewards.random, "random", lambda: 0.85)
    monkeypatch.setattr(rewards.random, "choice", lambda items: items[0])
    op, sent = run(db, command="/抽奖")
    assert not op.failures and db.titles.list(42)
    assert "解锁称号" in str([r.content for r in sent])
    db.points.set(42, 5)
    op, sent = run(db, command="/抽奖", mid=2)
    assert not op.failures
    assert "已拥有称号" in str([r.content for r in sent])
    assert db.points.get(42) == 5  # 第二抽扣1，普通重复称号返1
    assert db.lottery.profile(42)["duplicate_count"] == 1


def test_concurrent_distinct_commands_cannot_exceed_daily_limit(db):
    barrier = Barrier(3)
    today = datetime.now().strftime("%Y-%m-%d")
    def draw(index):
        local = DbManager()
        try:
            barrier.wait(timeout=10)
            return engine.perform_draw(local, {"user_id": 42, "today": today,
                "source_operation": f"concurrent:{index}"}, False)["status"]
        finally:
            local.conn.close()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(draw, index) for index in range(3)]
        assert sorted(f.result() for f in futures) == ["limit", "ok", "ok"]
    assert db.lottery.draw_count(42, today) == 2
    assert db.points.get(42) == 3


def test_duplicate_source_across_threads_draws_once(db):
    barrier = Barrier(2)
    payload = {"user_id": 42, "today": datetime.now().strftime("%Y-%m-%d"), "source_operation": "same"}
    def draw():
        local = DbManager()
        try:
            barrier.wait(timeout=10)
            return engine.perform_draw(local, payload, False)["status"]
        finally:
            local.conn.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(draw) for _ in range(2)]
        assert sorted(f.result() for f in futures) == ["duplicate", "ok"]
    assert db.points.get(42) == 2
    assert db.lottery.draw_count(42, payload["today"]) == 1
