"""新卧底历史数据基础；只使用pytest会话中的临时数据库。"""
import sqlite3

import pytest

from core import config
from core.database_manager import DbManager


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'spy-history.db')
    db = DbManager()
    try:
        yield db.who_is_spy
    finally:
        db.conn.close()


def create(store, key='message-1', room='ABCD', group=100, at=1):
    with store.transaction():
        return store.create(request_key=key, room_code=room, group_id=group,
                            created_at=at, snapshot={'phase': 'waiting', 'history': []})


def member(uid, *, state='waiting', participated=False, joined=2, left=None):
    return dict(user_id=str(uid), joined_at=joined, left_at=left,
                state=state, participated=participated)


def save(store, rec, members, *, status='waiting', **kwargs):
    with store.transaction():
        revision = store.save(rec['record_id'], rec['revision'], status=status,
                              snapshot={'phase': status}, participants=members, **kwargs)
    result = store.get_internal(rec['record_id'])
    assert result['revision'] == revision
    return result


def test_create_idempotent_and_reused_room_code_does_not_overwrite(store):
    first = create(store)
    assert create(store)['record_id'] == first['record_id']
    first = save(store, first, [], status='cancelled', ended_at=3)
    second = create(store, key='message-2', room='ABCD', at=4)
    assert second['record_id'] != first['record_id']
    assert store.get_internal(first['record_id'])['status'] == 'cancelled'
    assert store.get_internal(second['record_id'])['status'] == 'waiting'


def test_create_retry_cannot_reuse_key_for_another_group(store):
    create(store)
    with pytest.raises(ValueError):
        create(store, group=200)


def test_save_requires_explicit_transaction(store):
    with pytest.raises(RuntimeError, match='事务'):
        store.create(request_key='x', room_code='AAAA', group_id=100,
                     created_at=1, snapshot={})
    assert store.list_records(group_id=100) == ([], False)


def test_participation_survives_prestart_exit_and_rejoin(store):
    rec = create(store)
    rec = save(store, rec, [member(11)])
    rec = save(store, rec, [member(11, state='left', left=3)])
    rows, more = store.list_records(user_id=11)
    assert not more and len(rows) == 1
    assert rows[0]['participation_state'] == 'left'
    assert rows[0]['participated'] == 0
    rec = save(store, rec, [member(11, joined=4)])
    rows, _ = store.list_records(user_id=11)
    assert len(rows) == 1 and rows[0]['joined_at'] == 2  # 首次加入不被覆盖
    assert rows[0]['left_at'] is None
    assert rows[0]['participation_state'] == 'waiting'
    assert store.conn.execute('SELECT COUNT(*) FROM spy_game_participants').fetchone()[0] == 1


def test_partial_snapshot_keeps_former_participant_membership(store):
    rec = create(store)
    rec = save(store, rec, [member(11, state='left', left=3), member(22)])
    rec = save(store, rec, [member(22, state='playing', participated=True)],
               status='playing', started_at=4)
    assert store.detail(rec['record_id'], user_id=11) is not None
    assert store.list_records(user_id=11)[0][0]['participation_state'] == 'left'


def test_queries_restrict_user_group_and_page_without_snapshot_leak(store):
    for n in range(12):
        rec = create(store, key=f'message-{n}', room=f'R{n:03}', at=n)
        save(store, rec, [member(11)])
    other = create(store, key='other', room='ELSE', group=200, at=20)
    save(store, other, [member(22)])
    first, more = store.list_records(user_id=11)
    second, more2 = store.list_records(user_id=11, page=2)
    assert len(first) == 10 and more
    assert len(second) == 2 and not more2
    assert [r['created_at'] for r in first] == list(range(11, 1, -1))
    assert all('snapshot' not in r and 'snapshot_json' not in r for r in first)
    assert store.detail(other['record_id'], user_id=11) is None
    assert store.detail(other['record_id'], group_id=100) is None
    assert store.detail(other['record_id'], group_id=200)['record_id'] == other['record_id']
    assert store.detail(first[0]['record_id'], user_id=11) is not None
    assert store.list_records(user_id="11' OR 1=1 --") == ([], False)
    assert store.list_records(user_id=11, page=3) == ([], False)


@pytest.mark.parametrize('kwargs', [{}, {'group_id': 1, 'user_id': 2},
                                    {'user_id': 1, 'page': 0}, {'user_id': 1, 'page': True},
                                    {'user_id': 1, 'page': 10**30}])
def test_invalid_query_scope_or_page_rejected(store, kwargs):
    with pytest.raises(ValueError):
        store.list_records(**kwargs)


def test_stale_revision_and_terminal_record_cannot_be_written_again(store):
    original = create(store)
    rec = save(store, original, [member(11)])
    with pytest.raises(ValueError, match='变更|结束'):
        save(store, original, [])
    rec = save(store, rec, [member(11, state='playing', participated=True)],
               status='playing', started_at=3)
    rec = save(store, rec, [member(11, state='finished', participated=True)],
               status='finished', started_at=3, ended_at=4, winner='civilian')
    with pytest.raises(ValueError, match='变更|结束'):
        save(store, rec, [], status='waiting')
    assert store.get_internal(rec['record_id']) == rec


def test_transaction_failure_rolls_back_record_members_and_other_writes(store):
    rec = create(store)
    store.conn.execute("""CREATE TRIGGER reject_second_spy_member BEFORE INSERT ON spy_game_participants
                         WHEN NEW.user_id = '22' BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction():
            store.conn.execute('INSERT INTO user_assets (user_id, points) VALUES (?, ?)', ('11', 5))
            store.save(rec['record_id'], 0, status='waiting', snapshot={'changed': True},
                       participants=[member(11), member(22)])
    assert store.get_internal(rec['record_id']) == rec
    assert store.list_records(user_id=11) == ([], False)
    assert store.conn.execute('SELECT COUNT(*) FROM user_assets').fetchone()[0] == 0
    assert not store.conn.in_transaction


def test_nested_transaction_rejected_without_committing_outer_work(store):
    with pytest.raises(RuntimeError, match='事务'):
        with store.transaction():
            store.create(request_key='outer', room_code='AAAA', group_id=1, created_at=1, snapshot={})
            with store.transaction():
                pass
    assert store.list_records(group_id=1) == ([], False)


def test_finished_record_requires_winner_and_start(store):
    rec = create(store)
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        save(store, rec, [], status='finished', ended_at=5)
    assert store.get_internal(rec['record_id']) == rec


def test_concurrent_creates_share_one_record(store):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from core.db.who_is_spy import WhoIsSpyManager
    barrier = Barrier(2)
    def attempt():
        conn = sqlite3.connect(str(config.DB_PATH), timeout=5)
        try:
            manager = WhoIsSpyManager(conn)
            barrier.wait(timeout=3)
            return create(manager)['record_id']
        finally:
            conn.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        ids = [f.result(timeout=8) for f in futures]
    assert ids[0] == ids[1]
    assert store.conn.execute('SELECT COUNT(*) FROM spy_game_records').fetchone()[0] == 1


def test_concurrent_snapshots_cannot_overwrite_each_other(store):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from core.db.who_is_spy import WhoIsSpyManager
    rec = create(store)
    barrier = Barrier(2)
    def attempt(uid):
        conn = sqlite3.connect(str(config.DB_PATH), timeout=5)
        try:
            manager = WhoIsSpyManager(conn)
            barrier.wait(timeout=3)
            try:
                save(manager, rec, [member(uid)])
                return uid
            except ValueError:
                return None
        finally:
            conn.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, uid) for uid in (11, 22)]
        winners = [f.result(timeout=8) for f in futures]
    assert sum(uid is not None for uid in winners) == 1
    assert store.get_internal(rec['record_id'])['revision'] == 1
    actual = store.conn.execute('SELECT user_id FROM spy_game_participants').fetchall()
    assert [row[0] for row in actual] == [str(next(uid for uid in winners if uid is not None))]


def test_playing_record_cannot_return_to_waiting(store):
    rec = create(store)
    rec = save(store, rec, [member(11, state='playing', participated=True)],
               status='playing', started_at=3)
    with pytest.raises(ValueError):
        save(store, rec, [member(11)])
    assert store.get_internal(rec['record_id']) == rec


def test_schema_reinitialization_does_not_interrupt_games(store):
    from core.db._base import init_schema
    rec = create(store)
    init_schema(store.conn, store.conn.cursor())
    assert store.get_internal(rec['record_id']) == rec
