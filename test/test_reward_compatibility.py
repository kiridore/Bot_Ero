"""真实周常引擎的新旧领取、故障和撤销兼容。所有数据均在临时数据库。"""
import sqlite3
from types import SimpleNamespace

import pytest

from core.db._base import init_schema
from core.db.checkin import CheckinManager
from core.db.points import PointsManager
from core.db.quest import QuestManager
from core.db.rewards import RewardManager
from plugins.weekly_quest import engine


@pytest.fixture
def db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    init_schema(conn, conn.cursor())
    monkeypatch.setattr(engine, "get_monday_to_monday", lambda: ("2026-10-05 08:00:00", "2026-10-12 08:00:00"))
    obj = SimpleNamespace(conn=conn, checkin=CheckinManager(conn), points=PointsManager(conn), quest=QuestManager(conn))
    yield obj
    conn.close()


def seed(db, count=1):
    db.conn.executemany("INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)",
                       [(1, f"2026-10-{day:02} 12:00:00", "test.png") for day in range(5, 5 + count)])
    db.conn.commit()


def remove(db):
    db.conn.execute("DELETE FROM checkin_records WHERE user_id = 1")
    db.conn.commit()


def test_legacy_claim_is_not_repaid_and_only_revoked_once(db):
    seed(db)
    week = engine.get_quest_week_key()
    db.quest.upsert_progress(1, 1, week, 1)
    assert db.quest.claim_reward(1, 1, week)
    db.points.set(1, 1)
    assert engine.on_quest_trigger(db, 1, "checkin", source_operation="a") == []
    assert db.conn.execute("SELECT COUNT(*) FROM plugin_reward_records").fetchone()[0] == 0
    remove(db)
    assert [q["id"] for q in engine.on_quest_rollback(db, 1, "checkin")] == [1]
    assert db.points.get(1) == 0
    assert engine.on_quest_rollback(db, 1, "checkin") == []
    assert db.points.get(1) == 0


def test_new_claim_requalifies_without_double_revoke_or_history_changes(db):
    seed(db)
    assert engine.on_quest_trigger(db, 1, "checkin", source_operation="a")
    db.quest.record_clear(1, engine.get_quest_week_key())
    db.conn.execute("INSERT INTO user_titles VALUES ('1', 201, '2026-10-05')")
    db.conn.commit()
    db.points.set(1, 0)  # 奖励已花掉，仍按旧规则扣回，不截断到零。
    remove(db)
    assert engine.on_quest_rollback(db, 1, "checkin", source_operation="undo-a")
    assert db.points.get(1) == -1
    assert engine.on_quest_rollback(db, 1, "checkin", source_operation="undo-again") == []
    assert db.points.get(1) == -1
    assert db.quest.completion(1) == 1
    assert db.quest.clear_count(1) == 1
    assert db.conn.execute("SELECT COUNT(*) FROM user_titles").fetchone()[0] == 1
    seed(db)
    assert engine.on_quest_trigger(db, 1, "checkin", source_operation="a") == []
    assert engine.on_quest_trigger(db, 1, "checkin", source_operation="b")
    assert db.points.get(1) == 0
    assert db.quest.completion(1) == 2


def test_attendance_new_then_legacy_claim_same_period(db):
    rewards = RewardManager(db.conn)
    assert rewards.grant_attendance(1, "full_month_weekly_check", "2026-10-05", "new-a")
    assert rewards.revoke_attendance(1, "full_month_weekly_check", "2026-10-05", "undo-a") == 1
    assert db.points.get(1) == 0
    # 模拟未迁移的网页入口重新合法领取同一周期：不能因曾有新记录就漏扣。
    assert db.checkin.claim_attendance(1, "full_month_weekly_check", "2026-10-05", 1)
    db.points.adjust(1, 1)
    assert rewards.revoke_attendance(1, "full_month_weekly_check", "2026-10-05", "undo-legacy") == 1
    assert rewards.revoke_attendance(1, "full_month_weekly_check", "2026-10-05", "undo-repeat") == 0
    assert db.points.get(1) == 0
    assert db.conn.execute("SELECT COUNT(*) FROM plugin_reward_records").fetchone()[0] == 1
    assert rewards.grant_attendance(1, "full_month_weekly_check", "2026-10-05", "new-b")
    assert db.points.get(1) == 1


def test_old_attendance_is_not_repaid_or_fabricated(db):
    assert db.checkin.claim_attendance(1, "full_week_daily", "2026-10-11", 1)
    db.points.set(1, 0)  # 已消费旧奖励，保留旧规则允许扣至负数。
    rewards = RewardManager(db.conn)
    assert not rewards.grant_attendance(1, "full_week_daily", "2026-10-11", "duplicate")
    assert rewards.revoke_attendance(1, "full_week_daily", "2026-10-11", "undo") == 1
    assert db.points.get(1) == -1
    assert rewards.revoke_attendance(1, "full_week_daily", "2026-10-11", "again") == 0
    assert db.conn.execute("SELECT COUNT(*) FROM plugin_reward_records").fetchone()[0] == 0


def test_legacy_repeated_undo_cannot_revoke_later_legacy_claim(db):
    rewards = RewardManager(db.conn)
    for source in ("old", "later"):
        assert db.checkin.claim_attendance(1, "full_week_daily", "2026-10-11", 1)
        db.points.adjust(1, 1)
        if source == "later":
            assert rewards.revoke_attendance(1, "full_week_daily", "2026-10-11", "old-undo") == 0
            assert db.points.get(1) == 1
        assert rewards.revoke_attendance(1, "full_week_daily", "2026-10-11", source + "-undo") == 1
    assert db.points.get(1) == 0
    assert db.conn.execute("SELECT COUNT(*) FROM plugin_reward_records").fetchone()[0] == 0
    assert db.conn.execute("SELECT COUNT(*) FROM plugin_reward_reversals").fetchone()[0] == 2


def test_attendance_revoke_failure_restores_claim_record_and_balance(db, monkeypatch):
    rewards = RewardManager(db.conn)
    rewards.grant_attendance(1, "full_month_weekly_check", "2026-10-05", "new")
    original = PointsManager.adjust

    def fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("扣分后中断")

    monkeypatch.setattr(PointsManager, "adjust", fail)
    with pytest.raises(RuntimeError):
        rewards.revoke_attendance(1, "full_month_weekly_check", "2026-10-05", "undo")
    assert db.points.get(1) == 1
    assert db.conn.execute("SELECT COUNT(*) FROM user_attendance_reward_claims").fetchone()[0] == 1
    assert rewards.has_active("checkin", 1, "attendance:full_month_weekly_check:2026-10-05")


def test_quest_legacy_reclaim_after_new_history_is_revoked(db):
    seed(db)
    engine.on_quest_trigger(db, 1, "checkin", source_operation="new")
    remove(db)
    engine.on_quest_rollback(db, 1, "checkin")
    assert db.quest.claim_reward(1, 1, engine.get_quest_week_key())
    db.points.adjust(1, 1)
    assert engine.on_quest_rollback(db, 1, "checkin")
    assert db.points.get(1) == 0
    assert engine.on_quest_rollback(db, 1, "checkin") == []


def test_failure_after_first_reward_rolls_back_entire_handler(db, monkeypatch):
    seed(db, 3)
    original = db.quest.increment_completion
    calls = []

    def fail_second(user, *, commit=True):
        calls.append(user)
        original(user, commit=commit)
        if len(calls) == 2:
            raise RuntimeError("第二个奖励失败")

    monkeypatch.setattr(db.quest, "increment_completion", fail_second)
    with pytest.raises(RuntimeError):
        engine.on_quest_trigger(db, 1, "checkin", source_operation="a")
    assert db.conn.execute("SELECT COUNT(*) FROM plugin_reward_records").fetchone()[0] == 0
    assert db.quest.progress(1, engine.get_quest_week_key()) == {}
    assert db.quest.completion(1) == 0
    assert db.conn.execute("SELECT COUNT(*) FROM user_assets").fetchone()[0] == 0
    assert db.conn.execute("SELECT COUNT(*) FROM checkin_records").fetchone()[0] == 3
