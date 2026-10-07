"""通过真实打卡插件和周常消费者验证开关与关闭后的奖励撤销。"""
from datetime import datetime
from unittest.mock import Mock

import pytest

from core import config, context
from core.database_manager import DbManager
from core.db.plugin_settings import set_user_plugins
from core.db.rewards import RewardManager
from core.db.points import PointsManager
from core.db.checkin import CheckinManager
from core.utils import get_monday_to_monday
from core.event import Event
from core.message_output import MessageOutput
from core.plugin_dispatch import Operation
from plugins.checkin import CheckinPlugin
from plugins.roll_back import RollbackCheckinPlugin
from plugins.checkin_recall import CheckinRecallPlugin
from plugins.weekly_quest import events  # 注册实际消费者


@pytest.fixture
def db(tmp_path, monkeypatch):
    import plugins.checkin as checkin
    import plugins.roll_back as rollback
    import plugins.checkin_recall as recall
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "integration.db")
    monkeypatch.setattr(checkin, "ensure_checkin_image", lambda *args: True)
    monkeypatch.setattr(checkin, "emit_event", lambda **kwargs: None)
    monkeypatch.setattr(rollback, "retract_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(recall, "retract_event", lambda *args, **kwargs: None)
    database = DbManager()
    yield database
    database.conn.close()


def run_plugin(cls, db, *, gid=10, uid=42, mid=100, message=None):
    raw = {"post_type": "message", "message_type": "private" if gid is None else "group",
           "user_id": uid, "message_id": mid, "message": message or [
               {"type": "text", "data": {"text": "/打卡"}},
               {"type": "image", "data": {"file": "test.png"}},
           ]}
    if gid is not None:
        raw["group_id"] = gid
    if cls is CheckinRecallPlugin:
        raw.update(post_type="notice", notice_type="group_recall")
    sent = []
    op = Operation(context.plugin_settings_snapshot(gid, uid), MessageOutput(
        lambda r: sent.append(r) or 1, ("group", gid) if gid is not None else ("private", uid)))
    plugin = cls.__new__(cls)
    plugin.bot_event = Event(raw)
    plugin.dbmanager = db
    plugin.api = Mock()
    plugin.api.get_image.return_value = ""
    plugin.operation = op
    assert op.execute(context.plugin_key(cls), plugin.handle)
    op.finish()
    assert not op.failures
    return op, sent


def enable_quest(db, gid=10):
    db.conn.execute("INSERT OR IGNORE INTO group_plugin_config VALUES (?, 'weekly_quest')", (gid,))
    db.conn.commit()


def points(db):
    row = db.conn.execute("SELECT points FROM user_assets WHERE user_id = '42'").fetchone()
    return row[0] if row else 0


def test_disable_quest_only_stops_new_quest_rewards(db):
    _, sent = run_plugin(CheckinPlugin, db)
    assert points(db) == 0
    assert db.conn.execute("SELECT COUNT(*) FROM checkin_records").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM quest_progress").fetchone()[0] == 0
    assert len(sent) == 1 and sent[0].kind == "segments"  # 仍正常回复打卡结果
    enable_quest(db)
    assert points(db) == 0  # 开启本身不补发
    _, sent = run_plugin(CheckinPlugin, db, mid=101)
    assert points(db) == 1
    assert [r.content for r in sent if r.kind == "text"] == ["🎯 打个卡先 +1"]


def test_disable_private_override_does_not_affect_group(db):
    enable_quest(db, 0)
    enable_quest(db, 10)
    set_user_plugins(db.conn, 42, ["weekly_quest"], False)
    run_plugin(CheckinPlugin, db, gid=None)
    assert points(db) == 0
    run_plugin(CheckinPlugin, db, mid=102)
    assert points(db) == 1


def test_disable_title_and_shop_does_not_consume_buff_or_unlock(db, monkeypatch):
    from plugins.redeem_shop import events as shop_events
    db.shop.add_luck(42, 2)
    monkeypatch.setattr(shop_events.random, "random", lambda: 0)
    run_plugin(CheckinPlugin, db)
    assert db.shop.luck_remaining(42) == 2
    assert db.titles.list(42) == []
    db.conn.execute("INSERT INTO group_plugin_config VALUES (10, 'redeem_shop')")
    db.conn.commit()
    _, sent = run_plugin(CheckinPlugin, db, mid=101)
    assert db.shop.luck_remaining(42) == 1
    assert points(db) == 1
    assert any(r.content == "打卡增强：概率奖励 +1" for r in sent)
    run_plugin(CheckinPlugin, db, mid=101)  # 重复来源不能再次消耗道具或发奖
    assert db.shop.luck_remaining(42) == 1
    assert points(db) == 1


def test_title_evaluation_precedes_new_quest_completion(db):
    enable_quest(db)
    db.conn.execute("INSERT INTO group_plugin_config VALUES (10, 'title')")
    db.conn.commit()
    for _ in range(4):
        db.quest.increment_completion(42)
    run_plugin(CheckinPlugin, db)
    assert db.quest.completion(42) == 5
    assert not db.titles.has(42, 238)  # 保持先评估称号、再增加本次周常次数的旧顺序
    run_plugin(CheckinPlugin, db, mid=102)
    assert db.titles.has(42, 238)


def test_recalled_multi_image_message_revokes_once_while_quest_disabled(db):
    enable_quest(db)
    run_plugin(CheckinPlugin, db, message=[
        {"type": "text", "data": {"text": "/打卡"}},
        {"type": "image", "data": {"file": "one.png"}},
        {"type": "image", "data": {"file": "two.png"}},
    ])
    assert points(db) == 1
    db.conn.execute("DELETE FROM group_plugin_config WHERE plugin_name = 'weekly_quest'")
    db.conn.commit()
    _, sent = run_plugin(CheckinRecallPlugin, db)
    assert points(db) == 0
    assert db.conn.execute("SELECT COUNT(*) FROM checkin_records").fetchone()[0] == 0
    assert "含2张图" in sent[0].content[1]["data"]["text"]
    _, sent = run_plugin(CheckinRecallPlugin, db)
    assert not sent
    assert points(db) == 0


@pytest.mark.parametrize("plugin_cls", [RollbackCheckinPlugin, CheckinRecallPlugin])
def test_mixed_old_new_attendance_revoked_once_by_either_entry(db, plugin_cls):
    run_plugin(CheckinPlugin, db)
    today = datetime.now().strftime("%Y-%m-%d")
    week = get_monday_to_monday()[0].split(" ")[0]
    assert db.checkin.claim_attendance(42, "full_week_daily", today, 1)
    db.points.adjust(42, 1)
    assert RewardManager(db.conn).grant_attendance(42, "full_month_weekly_check", week, "new-month")
    assert points(db) == 2
    # 两个奖励插件都没有开启，旧奖励清理仍执行。
    run_plugin(plugin_cls, db)
    assert points(db) == 0
    assert db.conn.execute("SELECT COUNT(*) FROM user_attendance_reward_claims").fetchone()[0] == 0
    run_plugin(plugin_cls, db)
    assert points(db) == 0


def test_attendance_keeps_existing_week_and_month_boundaries(db):
    from plugins.checkin.events import revoke_attendance
    for kind, period in (("full_week_daily", "2026-10-04"),
                         ("full_week_daily", "2026-10-05"),
                         ("full_month_weekly_check", "2026-09-28")):
        assert db.checkin.claim_attendance(42, kind, period, 1)
        db.points.adjust(42, 1)
    op = Operation({}, MessageOutput(lambda r: 1, ("private", 42)))
    assert op.execute("checkin", lambda: revoke_attendance(op, {
        "user_id": 42, "removed_at": "2026-10-05T07:00:00", "source_operation": "boundary",
    }))
    # 08:00业务周为空，撤销上周起点的月奖励；自然周仍从00:00开始。
    assert points(db) == 1
    assert [tuple(row) for row in db.conn.execute("SELECT reward_type, period_key FROM user_attendance_reward_claims")] == [
        ("full_week_daily", "2026-10-04"),
    ]


def test_monthly_reward_failure_does_not_stop_quest_or_remove_checkin(db, monkeypatch):
    from core.plugin_dispatch import Subscription
    from plugins.checkin.events import award_attendance
    from plugins.weekly_quest.events import checkin_completed
    db.checkin.insert(42, ["saved.png"], message_id=100)
    original_count = CheckinManager.count_days
    original_grant = RewardManager.grant_attendance

    def full_month(self, uid, start, end):
        return 31 if start.endswith("00:00:00") else original_count(self, uid, start, end)

    def fail_after_grant(self, *args, **kwargs):
        original_grant(self, *args, **kwargs)
        raise RuntimeError("全勤奖励中途失败")

    monkeypatch.setattr(CheckinManager, "count_days", full_month)
    monkeypatch.setattr(RewardManager, "grant_attendance", fail_after_grant)
    sent = []
    op = Operation({"checkin": True, "weekly_quest": True}, MessageOutput(
        lambda r: sent.append(r) or 1, ("private", 42)), subscriptions=[
            Subscription("checkin.completed", "checkin", award_attendance, 30),
            Subscription("checkin.completed", "weekly_quest", checkin_completed, 40),
        ])
    now = datetime.now()
    op.publish("checkin.completed", {"user_id": 42, "is_first": True,
        "reward_at": now.isoformat(), "week_start": get_monday_to_monday()[0].split(" ")[0],
        "source_operation": "test-month-failure", "source_scope": "private:42"})
    op.finish()
    assert op.failures == ["checkin"]
    assert db.conn.execute("SELECT COUNT(*) FROM checkin_records").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM user_attendance_reward_claims").fetchone()[0] == 0
    assert points(db) == 1  # 只有成功的周常奖励
    assert not any(r.content == "当月全勤奖励 +1" for r in sent)
    assert any(r.content == "🎯 打个卡先 +1" for r in sent)


def test_attendance_cleanup_failure_does_not_partially_refund(db, monkeypatch):
    from plugins.checkin.events import revoke_attendance
    now = datetime.now()
    week = get_monday_to_monday()[0].split(" ")[0]
    rewards = RewardManager(db.conn)
    rewards.grant_attendance(42, "full_month_weekly_check", week, "month")
    rewards.grant_attendance(42, "full_week_daily", now.strftime("%Y-%m-%d"), "week")
    original = PointsManager.adjust
    attempts = []

    def fail_second(self, uid, delta, commit=True):
        original(self, uid, delta, commit=commit)
        attempts.append(delta)
        if len(attempts) == 2:
            raise RuntimeError("第二笔撤销失败")

    monkeypatch.setattr(PointsManager, "adjust", fail_second)
    op = Operation({}, MessageOutput(lambda r: 1, ("private", 42)))
    assert not op.execute("checkin", lambda: revoke_attendance(op, {
        "user_id": 42, "removed_at": now.isoformat(), "source_operation": "undo",
    }))
    assert points(db) == 2
    assert db.conn.execute("SELECT COUNT(*) FROM user_attendance_reward_claims").fetchone()[0] == 2
    assert db.conn.execute("SELECT COUNT(*) FROM plugin_reward_records WHERE revoked_at IS NULL").fetchone()[0] == 2


def test_disabled_quest_still_revokes_real_reward(db):
    enable_quest(db)
    run_plugin(CheckinPlugin, db)
    assert points(db) == 1
    db.conn.execute("DELETE FROM group_plugin_config WHERE plugin_name = 'weekly_quest'")
    db.conn.commit()
    run_plugin(RollbackCheckinPlugin, db, mid=200, message=[{"type": "text", "data": {"text": "/撤回打卡"}}])
    assert points(db) == 0
    assert db.conn.execute("SELECT revoked_at FROM plugin_reward_records").fetchone()[0] is not None
    run_plugin(RollbackCheckinPlugin, db, mid=201, message=[{"type": "text", "data": {"text": "/撤回打卡"}}])
    assert points(db) == 0
