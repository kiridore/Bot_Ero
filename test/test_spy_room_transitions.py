from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event as ThreadEvent
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.database_manager import DbManager
from plugins.who_is_spy import WhoIsSpyPlugin
from plugins.who_is_spy.room import GameService
from plugins.who_is_spy.relay import GameMessenger
from test.spy_helpers import game_env, new_room, seed, output


def parallel_inputs(room, uids, body, phase):
    barrier = Barrier(len(uids))
    def submit(uid):
        db = DbManager()
        try:
            p = WhoIsSpyPlugin.__new__(WhoIsSpyPlugin)
            p.dbmanager, p.api = db, Mock()
            p.api.call_api.return_value = {'status': 'ok', 'retcode': 0}
            p.bot_event = SimpleNamespace(user_id=uid)
            p._mode, p._record_id, p._input_text = 'game_input', room['record_id'], body
            p._expected = (room['round_num'], phase)
            barrier.wait(timeout=5)
            p.handle()
        finally:
            db.conn.close()
    with ThreadPoolExecutor(max_workers=len(uids)) as pool:
        futures = [pool.submit(submit, uid) for uid in uids]
        for f in futures:
            f.result(timeout=10)


def test_last_two_votes_real_handlers_settle_once(game_env):
    room = new_room(game_env)
    seed(game_env, room, phase='playing_vote', votes={'101': '102', '102': '101'})
    parallel_inputs(room, (103, 104), '1', 'playing_vote')
    saved = game_env.service.get(room['room_id'])
    assert len(saved['history']) == 1 and saved['round_num'] == 2
    assert saved['history'][0]['eliminated'] == '101'


def test_duplicate_final_vote_cannot_become_next_description(game_env):
    room = new_room(game_env)
    seed(game_env, room, phase='playing_vote', votes={'101': '102', '102': '101', '103': '101'})
    parallel_inputs(room, (104, 104), '1', 'playing_vote')
    saved = game_env.service.get(room['room_id'])
    assert len(saved['history']) == 1 and saved['round_num'] == 2
    assert saved['ready_descriptions'] == {}


def test_last_two_descriptions_advance_once(game_env):
    room = new_room(game_env)
    seed(game_env, room, ready_descriptions={'101': '甲', '102': '乙'})
    parallel_inputs(room, (103, 104), '描述', 'playing_describe')
    saved = game_env.service.get(room['room_id'])
    assert saved['phase'] == 'playing_vote' and saved['round_num'] == 1
    assert len(saved['ready_descriptions']) == 4 and saved['votes'] == {}


def test_leave_rechecks_remaining_descriptions_and_invalidates_target_votes(game_env):
    room = new_room(game_env, n=5)
    seed(game_env, room, ready_descriptions={str(uid): '描述' for uid in (102, 103, 104, 105)})
    result = game_env.service.leave(101)
    assert result.room['phase'] == 'playing_vote'
    seed(game_env, result.room, votes={'103': '102', '104': '105', '105': '104'})
    result = game_env.service.leave(102)
    assert result.room['phase'] == 'playing_vote'
    assert result.room['votes'] == {'104': '105', '105': '104'}  # 投给退出者的票重投
    assert not result.room['history']
    result = game_env.service.input(room['record_id'], 103, '5')
    assert len(result.room['history']) == 1
    assert set(result.room['history'][0]['participants']) == {'103', '104', '105'}


def test_leave_and_final_vote_race_has_one_settlement(game_env):
    room = new_room(game_env)
    seed(game_env, room, phase='playing_vote', votes={'101': '104', '102': '103', '104': '103'})
    barrier = Barrier(2)
    def run(leaving):
        db = DbManager()
        try:
            service = GameService(db)
            barrier.wait(timeout=5)
            try:
                return service.leave(101) if leaving else service.input(room['record_id'], 103, '4', (1, 'playing_vote'))
            except ValueError:
                return None  # 另一事件已结束本局
        finally:
            db.conn.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, b) for b in (True, False)]
        for f in futures:
            f.result(timeout=10)
    saved = game_env.db.who_is_spy.get_internal(room['record_id'])
    assert saved['status'] == 'finished'
    assert len(saved['snapshot']['history']) <= 1
    assert all(r[0] == 1 for r in game_env.db.conn.execute('SELECT total_games FROM user_game_stats'))


def test_network_wait_does_not_block_other_rooms(game_env):
    first = new_room(game_env)
    pending = game_env.service.input(first['record_id'], 101, '描述')
    entered, release = ThreadEvent(), ThreadEvent()
    def delayed_delivery():
        api = Mock()
        def send(*args, **kwargs):
            entered.set()
            assert release.wait(5)
            return {'status': 'ok', 'retcode': 0}
        api.call_api.side_effect = send
        GameMessenger(api).emit([('describe', pending.room)])
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(delayed_delivery)
        try:
            assert entered.wait(3)
            second = game_env.service.create(200, 999, 4, 'other-room')
            assert second.room['record_id'] != first['record_id']
        finally:
            release.set()
        task.result(timeout=8)


def test_complete_two_round_game_from_real_commands(game_env):
    created = game_env.run('/创建游戏 卧底 4', gid=100)
    assert '已创建' in output(created)
    record = game_env.db.who_is_spy.active_in_group(100)[0]
    code = record['room_code']
    for uid in range(101, 105):
        assert '已加入' in output(game_env.run('/加入 ' + code, uid=uid))
    game_env.run('/开始 ' + code, gid=100)
    for uid in range(101, 105):
        game_env.run('第一轮描述', uid=uid)
    for uid, vote in ((101, '2'), (102, '1'), (103, '1'), (104, '1')):
        game_env.run(vote, uid=uid)
    for uid in (102, 103, 104):
        game_env.run('第二轮描述', uid=uid)
    for uid, vote in ((102, '4'), (103, '4'), (104, '2')):
        game_env.run(vote, uid=uid)
    saved = game_env.db.who_is_spy.get_internal(record['record_id'])
    assert saved['status'] == 'finished' and saved['winner'] == 'civilian'
    assert len(saved['snapshot']['history']) == 2
    assert game_env.service.current(101) is None
    assert '正常结束' in output(game_env.run('/游戏记录'))
    assert game_env.db.conn.execute('SELECT COUNT(*) FROM user_game_stats WHERE total_games=1').fetchone()[0] == 4


def test_outgoing_message_event_is_not_player_input(game_env):
    from core.event import Event
    room = new_room(game_env)
    p = WhoIsSpyPlugin.__new__(WhoIsSpyPlugin)
    p.dbmanager = game_env.db
    p.bot_event = Event({'post_type': 'message_sent', 'message_type': 'private', 'user_id': 101,
                         'message': [{'type': 'text', 'data': {'text': '机器人自己的提示'}}]})
    assert not p.match('message')
    assert game_env.service.get(room['room_id'])['ready_descriptions'] == {}


def test_failed_join_does_not_publish_state_or_confirmation(game_env):
    room = game_env.service.create(100, 101, 4, 'failure').room
    game_env.db.conn.execute("""CREATE TRIGGER reject_join BEFORE INSERT ON spy_game_participants
                              BEGIN SELECT RAISE(ABORT, 'join failure'); END""")
    game_env.db.conn.commit()
    api = game_env.run('/加入 ' + room['room_id'], uid=102)
    assert '未确认成功' in output(api) and '已加入' not in output(api)
    assert not api.call_api.called
    assert game_env.service.get(room['room_id'])['players'] == {}
    assert game_env.db.who_is_spy.list_records(user_id=102) == ([], False)
