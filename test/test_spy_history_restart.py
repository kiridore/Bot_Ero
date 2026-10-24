"""新历史重启中断；真实main启动入口使用WebSocket替身，禁止网络和面板启动。"""
import runpy
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from core import api, config, context
from core.database_manager import DbManager
from plugins.who_is_spy.history import recover_interrupted_games


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'restart.db')
    db = DbManager()
    try:
        yield db.who_is_spy
    finally:
        db.conn.close()


def create(store, code):
    with store.transaction():
        return store.create(request_key=code, room_code=code, group_id=100,
                            created_at=1, snapshot={'phase': 'waiting'})


def advance(store, rec, status):
    with store.transaction():
        store.save(rec['record_id'], rec['revision'], status=status,
                   snapshot={'phase': 'playing_vote', 'secret': 'do-not-broadcast'},
                   participants=[{'user_id': '11', 'joined_at': 1, 'participated': True,
                                  'state': 'playing' if status == 'playing' else 'finished'}],
                   started_at=2, ended_at=3 if status == 'finished' else None,
                   winner='civilian' if status == 'finished' else None)
    return store.get_internal(rec['record_id'])


def test_restart_marks_open_only_without_awards_or_restoring_rooms(history):
    waiting = create(history, 'WAIT')
    playing = advance(history, create(history, 'PLAY'), 'playing')
    finished = advance(history, create(history, 'DONE'), 'finished')
    history.conn.execute('INSERT INTO user_assets (user_id, points) VALUES (?, ?)', ('11', 10))
    history.conn.commit()
    titles_before = history.conn.execute('SELECT * FROM user_titles').fetchall()
    assert recover_interrupted_games() == 2
    for rec in (waiting, playing):
        saved = history.get_internal(rec['record_id'])
        assert saved['status'] == 'interrupted'
        assert saved['winner'] is None and saved['ended_at'] is not None
        assert saved['snapshot'] == rec['snapshot']  # 留存崩溃前快照，不伪造完成状态
    assert history.get_internal(finished['record_id']) == finished
    assert recover_interrupted_games() == 0
    assert history.conn.execute('SELECT points FROM user_assets WHERE user_id = ?', ('11',)).fetchone()[0] == 10
    assert history.conn.execute('SELECT * FROM user_titles').fetchall() == titles_before
    assert history.active_for_user(11) is None
    assert create(history, 'WAIT')['record_id'] == waiting['record_id']  # 同请求重试不能复活旧局
    with history.transaction():
        newer = history.create(request_key='new-request', room_code='WAIT', group_id=100,
                               created_at=9, snapshot={})
    assert newer['record_id'] != waiting['record_id']  # 中断释放活跃房间号


def test_restart_failure_rolls_back_and_propagates(history):
    first = create(history, 'ONE1')
    second = create(history, 'TWO2')
    history.conn.execute("""CREATE TRIGGER reject_spy_interrupt BEFORE UPDATE ON spy_game_records
                           WHEN OLD.room_code = 'TWO2'
                           BEGIN SELECT RAISE(ABORT, 'injected recovery failure'); END""")
    history.conn.commit()
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        recover_interrupted_games()
    assert history.get_internal(first['record_id'])['status'] == 'waiting'
    assert history.get_internal(second['record_id'])['status'] == 'waiting'


def test_real_main_recovers_once_before_websocket_not_on_reconnect(history, monkeypatch):
    pending = create(history, 'PEND')
    panel = ModuleType('core.web_panel')
    panel.start_panel = Mock()
    monkeypatch.setitem(sys.modules, 'core.web_panel', panel)
    monkeypatch.setattr(api, 'echo', getattr(api, 'echo', None), raising=False)
    monkeypatch.setattr(api, 'WS_APP', getattr(api, 'WS_APP', None), raising=False)
    monkeypatch.setattr(context, 'script_start_time', context.script_start_time)
    monkeypatch.setattr('time.sleep', lambda _: None)
    from plugins.who_is_spy import history as lifecycle
    recover = Mock(wraps=lifecycle.recover_interrupted_games)
    monkeypatch.setattr(lifecycle, 'recover_interrupted_games', recover)
    class FinishedTest(Exception):
        pass
    class FakeWebSocket:
        def __init__(self, *args, **kwargs):
            assert history.get_internal(pending['record_id'])['status'] == 'interrupted'
            self.new = None
        def run_forever(self):
            if self.new is None:
                self.new = create(history, 'LIVE')
                return  # 模拟掉线重连
            assert history.get_internal(self.new['record_id'])['status'] == 'waiting'
            raise FinishedTest
    monkeypatch.setattr('websocket.WebSocketApp', FakeWebSocket)
    with pytest.raises(FinishedTest):
        runpy.run_path('main.py', run_name='__main__')
    assert recover.call_count == 1


def test_old_json_is_not_read_or_changed(history, tmp_path, monkeypatch):
    from plugins.who_is_spy import relay
    old = tmp_path / 'server_data' / 'game_records' / '100' / 'OLD1.json'
    old.parent.mkdir(parents=True)
    old.write_bytes(b'{broken legacy record')
    assert not hasattr(relay, 'get_saved_records')  # 新实现已删除旧文件读取入口
    assert recover_interrupted_games() == 0
    assert history.list_records(group_id=100) == ([], False)
    assert old.read_bytes() == b'{broken legacy record'
    assert history.conn.execute('SELECT COUNT(*) FROM spy_game_records').fetchone()[0] == 0
