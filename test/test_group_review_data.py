"""群审核数据基础：旧表迁移、唯一请求、容量预留及原子登记。"""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.db._base import init_schema, _migrate_group_requests
from core.db.community import CommunityManager


@pytest.fixture
def db(tmp_path):
    conn = sqlite3.connect(tmp_path / 'review.db', timeout=10)
    conn.row_factory = sqlite3.Row
    init_schema(conn, conn.cursor())
    yield CommunityManager(conn)
    conn.close()


def request(db, gid=100, flag='one'):
    assert db.upsert_request(gid, 42, flag, 'invite')
    return db.conn.execute('SELECT id FROM group_requests WHERE flag = ?', (flag,)).fetchone()[0]


def test_same_second_requests_have_distinct_ids(db):
    first = request(db)
    second = request(db, flag='two')
    assert first != second
    db.conn.execute("UPDATE group_requests SET created_at = '2026-01-01 00:00:00'")
    db.conn.commit()
    assert not db.resolve_request(100, 42, '2026-01-01 00:00:00', True)
    assert len(db.pending_requests()) == 2
    assert not db.upsert_request(200, 43, 'one', 'invite')


def test_manual_join_is_local_and_deduplicated(db):
    assert db.record_group_join(100, 42)
    assert not db.record_group_join(100, 42)
    row = db.pending_requests()[0]
    assert row['kind'] == 'manual' and row['joined'] == 1
    db.reserve_review(row['id'], True, 1)
    assert db.complete_review(row['id'], ['checkin'])
    assert db.is_group_active(100)
    assert not db.record_group_join(100, 42)
    assert not db.complete_review(row['id'], ['checkin'])


def test_invite_join_notification_preserves_request(db):
    rid = request(db)
    assert not db.record_group_join(100, 7)
    assert len(db.pending_requests()) == 1
    db.reserve_review(rid, True, 1)
    assert db.complete_review(rid, ['checkin'])


def test_unknown_result_keeps_slot_and_cannot_complete(db):
    rid = request(db)
    db.reserve_review(rid, True, 1)
    db.record_review_result(rid, 'unknown')
    with pytest.raises(ValueError, match='尚未确认'):
        db.complete_review(rid, ['checkin'])
    second = request(db, 200, 'two')
    with pytest.raises(ValueError, match='上限'):
        db.reserve_review(second, True, 1)
    with pytest.raises(ValueError, match='已经处理'):
        db.reserve_review(rid, True, 1)
    assert not db.is_group_active(100)


def test_failed_remote_result_can_retry_and_frees_capacity(db):
    rid = request(db)
    db.reserve_review(rid, True, 1)
    db.record_review_result(rid, 'failed')
    assert db.pending_requests()[0]['status'] == 'pending'
    db.reserve_review(rid, True, 1)
    db.record_review_result(rid, 'ok')
    assert db.complete_review(rid, ['checkin'])


def test_local_failure_rolls_back_all_but_retains_remote_success(db):
    rid = request(db)
    db.reserve_review(rid, True, 1)
    db.record_review_result(rid, 'ok')
    db.conn.execute("""CREATE TRIGGER reject_seed BEFORE INSERT ON group_plugin_config
                        BEGIN SELECT RAISE(ABORT, 'seed failed'); END""")
    db.conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.complete_review(rid, ['checkin'])
    assert not db.is_group_active(100)
    assert db.pending_requests()[0]['remote_state'] == 'ok'
    assert db.conn.execute('SELECT COUNT(*) FROM group_plugin_config').fetchone()[0] == 0
    db.conn.execute('DROP TRIGGER reject_seed')
    db.conn.commit()
    assert db.complete_review(rid, ['checkin'])
    assert db.pending_requests() == []


def test_bans_checked_before_reservation(db):
    rid = request(db)
    db.ban('user', 42)
    with pytest.raises(ValueError, match='黑名单'):
        db.reserve_review(rid, True, 1)
    db.unban('user', 42)
    db.ban('group', 100)
    with pytest.raises(ValueError, match='黑名单'):
        db.reserve_review(rid, True, 1)
    assert db.pending_requests()[0]['status'] == 'pending'


def test_manual_rejection_does_not_delete_data(db):
    db.record_group_join(100, 42)
    rid = db.pending_requests()[0]['id']
    db.conn.execute("INSERT INTO group_plugin_config VALUES (100, 'checkin')")
    db.conn.commit()
    db.reserve_review(rid, False, 1)
    assert db.complete_review(rid)
    assert not db.is_group_active(100)
    assert db.conn.execute('SELECT COUNT(*) FROM group_plugin_config').fetchone()[0] == 1
    assert not db.complete_review(rid)


def test_removed_group_cannot_complete_stale_success(db):
    rid = request(db)
    db.reserve_review(rid, True, 1)
    db.record_review_result(rid, 'ok')
    db.record_group_join(100, 42)
    db.mark_group_removed(100)
    with pytest.raises(ValueError, match='尚未确认'):
        db.complete_review(rid, ['checkin'])


def test_concurrent_reservations_cannot_exceed_capacity(db):
    ids = [request(db, 100, 'one'), request(db, 200, 'two')]
    filename = db.conn.execute('PRAGMA database_list').fetchone()[2]
    barrier = Barrier(2)
    def reserve(rid):
        conn = sqlite3.connect(filename, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            barrier.wait(timeout=10)
            try:
                CommunityManager(conn).reserve_review(rid, True, 1)
                return 'reserved'
            except ValueError:
                return 'full'
        finally:
            conn.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, ids)) == ['full', 'reserved']


def test_migration_failure_rolls_back_rename_and_copy(tmp_path):
    conn = sqlite3.connect(tmp_path / 'failure.db')
    conn.executescript("""
        CREATE TABLE group_requests (
            group_id INTEGER NOT NULL, user_id INTEGER NOT NULL, flag TEXT NOT NULL,
            sub_type TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY (group_id, user_id, created_at));
        CREATE UNIQUE INDEX idx_group_requests_flag ON group_requests(flag);
        INSERT INTO group_requests VALUES (100, 42, 'keep', 'invite', 'pending', 'old');
    """)
    def deny_drop(action, arg1, arg2, database, source):
        return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_DROP_TABLE else sqlite3.SQLITE_OK
    try:
        conn.set_authorizer(deny_drop)
        with pytest.raises(sqlite3.DatabaseError):
            _migrate_group_requests(conn, conn.cursor())
        conn.set_authorizer(None)
        assert 'id' not in {r[1] for r in conn.execute('PRAGMA table_info(group_requests)')}
        assert conn.execute('SELECT flag FROM group_requests').fetchone()[0] == 'keep'
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='group_requests_legacy'").fetchone()
        _migrate_group_requests(conn, conn.cursor())
        assert conn.execute('SELECT id, flag FROM group_requests').fetchone() == (1, 'keep')
    finally:
        conn.close()


def test_old_schema_migration_preserves_terminal_history(tmp_path):
    conn = sqlite3.connect(tmp_path / 'legacy.db')
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE group_requests (
            group_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            flag TEXT NOT NULL, sub_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
            PRIMARY KEY (group_id, user_id, created_at));
        CREATE UNIQUE INDEX idx_group_requests_flag ON group_requests(flag);
        INSERT INTO group_requests VALUES (100, 42, 'old', 'invite', 'approved', '2026-01-01');
    """)
    try:
        init_schema(conn, conn.cursor())
        init_schema(conn, conn.cursor())
        row = conn.execute('SELECT * FROM group_requests').fetchone()
        assert row['flag'] == 'old' and row['status'] == 'approved' and row['id'] > 0
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        manager = CommunityManager(conn)
        assert manager.upsert_request(100, 42, 'new', 'invite')
        assert not manager.upsert_request(200, 7, 'old', 'invite')
    finally:
        conn.close()
