"""黑名单基础阶段：旧表兼容、读快照、写入与准入原子排序；尚未接入业务入口。"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import sqlite3
from threading import Event

import pytest

from core import config
from core.blacklist import admit, capture, coordination_lock
from core.database_manager import DbManager


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'blacklist.db')
    manager = DbManager()
    yield manager
    manager.conn.close()


def test_record_operator_idempotence_and_legacy_calls(db):
    assert db.community.ban('user', 10, 'first', operator_id=99)
    before = tuple(db.conn.execute('SELECT * FROM blacklist').fetchone())
    assert not db.community.ban('user', 10, 'second', operator_id=88)
    assert tuple(db.conn.execute('SELECT * FROM blacklist').fetchone()) == before
    assert db.community.ban('group', 10, 'legacy')
    assert db.conn.execute("SELECT operator_id FROM blacklist WHERE scope='group'").fetchone()[0] is None
    assert db.community.unban('user', 10)
    assert not db.community.unban('user', 10)
    assert db.community.is_banned('group', 10)


def test_old_schema_migration_preserves_records(tmp_path, monkeypatch):
    path = tmp_path / 'old.db'
    monkeypatch.setattr(config, 'DB_PATH', path)
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE blacklist(scope TEXT, target_id INTEGER, reason TEXT, created_at TEXT, PRIMARY KEY(scope,target_id))')
        conn.execute("INSERT INTO blacklist VALUES ('user', 10, 'old', '2000-01-01')")
    for _ in range(2):
        manager = DbManager()
        assert tuple(manager.conn.execute('SELECT * FROM blacklist').fetchone()) == ('user', 10, 'old', '2000-01-01', None)
        manager.conn.close()


def test_migration_failure_preserves_legacy_blacklist(tmp_path):
    from core.db._base import init_schema
    conn = sqlite3.connect(tmp_path / 'failed-migration.db')
    conn.execute('CREATE TABLE blacklist(scope TEXT, target_id INTEGER, reason TEXT, created_at TEXT, PRIMARY KEY(scope,target_id))')
    conn.execute("INSERT INTO blacklist VALUES ('user', 10, 'old', '2000-01-01')")
    conn.commit()
    conn.set_authorizer(lambda action, a, b, *_: sqlite3.SQLITE_DENY
                        if action == sqlite3.SQLITE_ALTER_TABLE and b == 'blacklist' else sqlite3.SQLITE_OK)
    with pytest.raises(sqlite3.DatabaseError):
        init_schema(conn, conn.cursor())
    conn.rollback()
    assert tuple(conn.execute('SELECT * FROM blacklist').fetchone()) == ('user', 10, 'old', '2000-01-01')
    conn.set_authorizer(None)
    init_schema(conn, conn.cursor())
    assert tuple(conn.execute('SELECT * FROM blacklist').fetchone()) == ('user', 10, 'old', '2000-01-01', None)
    conn.close()


def test_failed_write_rolls_back_and_releases_lock(db):
    db.conn.execute("CREATE TRIGGER fail_ban BEFORE INSERT ON blacklist BEGIN SELECT RAISE(ABORT, 'failure'); END")
    db.conn.commit()
    with pytest.raises(sqlite3.DatabaseError):
        db.community.ban('user', 10, operator_id=99)
    assert not db.community.is_banned('user', 10)
    # 独立线程仍能获得锁，事务异常没有遗留占用。
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(lambda: admit(enabled=True, user_id=10)).result(timeout=5) is not None


def test_snapshot_read_only_protection_and_scope(db):
    db.community.ban('user', 10)
    db.community.ban('group', 20)
    snapshot = capture(enabled=True, protected_users=[10])
    assert not snapshot.blocks(user_id=10)
    assert snapshot.blocks(group_id=20)
    assert not snapshot.blocks(group_id=10)
    assert db.community.is_banned('user', 10)  # 保护不删除历史
    with pytest.raises(FrozenInstanceError):
        snapshot.users = frozenset()
    assert admit(enabled=True, user_id=10) is None
    assert admit(enabled=False, user_id=10, group_id=20) is not None


def test_read_failure_is_not_empty_allowlist(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'missing.db')
    with pytest.raises(sqlite3.OperationalError):
        admit(enabled=True, user_id=10)
    assert not config.DB_PATH.exists()
    assert admit(enabled=False, user_id=10) is not None


def test_concurrent_ban_does_not_interrupt_old_admission(db):
    admitted = Event()
    banned = Event()

    def operation():
        snap = admit(enabled=True, user_id=10)
        assert snap is not None
        admitted.set()
        assert banned.wait(5)
        assert not snap.blocks(user_id=10)  # 已获准步骤使用旧快照完成
        return True

    def ban():
        assert admitted.wait(5)
        manager = DbManager()
        try:
            manager.community.ban('user', 10, operator_id=99)
        finally:
            manager.conn.close()
        banned.set()
        assert admit(enabled=True, user_id=10) is None

    with ThreadPoolExecutor(max_workers=2) as pool:
        old = pool.submit(operation)
        new = pool.submit(ban)
        new.result(timeout=10)
        assert old.result(timeout=10)


def test_waiting_admission_cannot_use_precommit_state(db):
    waiting = Event()
    def operation():
        waiting.set()
        return admit(enabled=True, user_id=10)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with coordination_lock:
            result = pool.submit(operation)
            assert waiting.wait(5)
            db.community.ban('user', 10)
        assert result.result(timeout=5) is None
