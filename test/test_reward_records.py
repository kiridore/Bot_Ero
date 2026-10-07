import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest

from core.db._base import init_schema
from core.db.points import PointsManager
from core.db.rewards import RewardManager


@pytest.fixture
def conn():
    db = sqlite3.connect(":memory:")
    init_schema(db, db.cursor())
    yield db
    db.close()


def balance(conn):
    row = conn.execute("SELECT points FROM user_assets WHERE user_id = '1'").fetchone()
    return row[0] if row else 0


def test_grant_revoke_repeat_and_requalify(conn):
    rewards = RewardManager(conn)
    assert rewards.grant("weekly_quest", 1, "quest:1:week", "checkin:1", 2)
    assert not rewards.grant("weekly_quest", 1, "quest:1:week", "checkin:2", 2)
    assert balance(conn) == 2
    assert rewards.revoke("weekly_quest", 1, "quest:1:week", "recall:1") == 2
    assert rewards.revoke("weekly_quest", 1, "quest:1:week", "recall:1") is None
    assert balance(conn) == 0
    assert rewards.has_history("weekly_quest", 1, "quest:1:week")
    assert not rewards.grant("weekly_quest", 1, "quest:1:week", "checkin:1", 2)
    assert rewards.grant("weekly_quest", 1, "quest:1:week", "checkin:3", 2)
    assert balance(conn) == 2
    assert conn.execute("SELECT COUNT(*) FROM plugin_reward_records").fetchone()[0] == 2


def test_failure_rolls_back_state_and_points(conn):
    rewards = RewardManager(conn)

    def state(db):
        db.execute("INSERT INTO group_plugin_config VALUES (1, 'test_state')")

    original = PointsManager.adjust

    def fail_after_write(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("数据库写入之后失败")

    with patch.object(PointsManager, "adjust", fail_after_write), pytest.raises(RuntimeError):
        rewards.grant("p", 1, "r", "op", 3, update_state=state)
    assert balance(conn) == 0
    assert conn.execute("SELECT COUNT(*) FROM plugin_reward_records").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM group_plugin_config").fetchone()[0] == 0


def test_revoke_failure_is_atomic(conn):
    rewards = RewardManager(conn)
    rewards.grant("p", 1, "r", "op", 3)
    with patch.object(PointsManager, "adjust", side_effect=RuntimeError), pytest.raises(RuntimeError):
        rewards.revoke("p", 1, "r", "undo")
    assert balance(conn) == 3
    assert conn.execute("SELECT revoked_at FROM plugin_reward_records").fetchone()[0] is None


def test_concurrent_grant_and_revoke(tmp_path):
    path = tmp_path / "rewards.db"
    db = sqlite3.connect(path)
    init_schema(db, db.cursor())
    db.close()

    def batch(revoke=False):
        barrier = Barrier(2)

        def run(number):
            db = sqlite3.connect(path, timeout=5)
            try:
                rewards = RewardManager(db)
                barrier.wait(timeout=5)
                if revoke:
                    return rewards.revoke("p", 1, "r", f"undo:{number}")
                return rewards.grant("p", 1, "r", f"op:{number}", 3)
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, i) for i in range(2)]
            return [f.result() for f in futures]

    assert sorted(batch()) == [False, True]
    assert sorted(batch(True), key=lambda x: x is None) == [3, None]
    db = sqlite3.connect(path)
    try:
        assert balance(db) == 0
    finally:
        db.close()


def test_no_accidental_commit_of_callers_transaction(conn):
    conn.execute("INSERT INTO group_plugin_config VALUES (1, 'not_committed')")
    with pytest.raises(RuntimeError):
        RewardManager(conn).grant("p", 1, "r", "op", 3)
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM group_plugin_config").fetchone()[0] == 0


def test_legacy_claim_rejected_without_fabricating_grant(conn):
    assert not RewardManager(conn).grant("p", 1, "r", "op", 3, update_state=lambda db: False)
    assert balance(conn) == 0
    assert conn.execute("SELECT COUNT(*) FROM plugin_reward_records").fetchone()[0] == 0
