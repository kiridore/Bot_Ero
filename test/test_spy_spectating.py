import pytest
from unittest.mock import Mock
from test.spy_helpers import game_env, new_room, seed, private_output, output
from plugins.who_is_spy.relay import GameMessenger


def eliminated(env):
    room = new_room(env)
    seed(env, room, phase='playing_vote', votes={'101': '102', '102': '101', '103': '101'})
    api = env.run('1', uid=104)
    return env.service.get(room['room_id']), api


def test_spectator_receives_descriptions_and_phase_but_cannot_play(game_env):
    room, api = eliminated(game_env)
    assert '继续观战' in private_output(api, 101)
    assert '观战：第2轮进入描述阶段' in private_output(api, 101)
    before = game_env.db.who_is_spy.get_internal(room['record_id'])
    assert '不能发言或投票' in output(game_env.run('我要投票', uid=101))
    assert game_env.db.who_is_spy.get_internal(room['record_id']) == before
    for uid in (102, 103, 104):
        api = game_env.run('描述内容', uid=uid)
    viewed = private_output(api, 101)
    assert '描述汇总' in viewed and '进入投票阶段，无需提交' in viewed
    assert '请投票选出卧底' not in viewed


def test_exit_stops_even_delayed_notifications_and_releases_room(game_env):
    room, _ = eliminated(game_env)
    with pytest.raises(ValueError, match='已在房间'):
        game_env.service.join(room['room_id'], 101, '本人')
    result = game_env.service.leave(101)
    assert game_env.service.current(101) is None
    next_room = game_env.service.create(200, 101, 4, 'second').room
    game_env.service.join(next_room['room_id'], 101, '本人')
    assert game_env.service.current(101)['record_id'] == next_room['record_id']
    api = Mock()
    api.call_api.return_value = {'status': 'ok', 'retcode': 0}
    GameMessenger(api, game_env.db.who_is_spy).emit([('describe', room), *result.events])
    assert private_output(api, 101) == ''
    assert game_env.db.who_is_spy.detail(room['record_id'], user_id=101) is not None


def test_prestart_rejoin_preserves_one_membership(game_env):
    room = new_room(game_env, start=False)
    original = room['members']['102']['joined_at']
    game_env.service.leave(102)
    game_env.service.join(room['room_id'], 102, '重新加入')
    room = game_env.service.start(room['room_id'], 101, 100).room
    assert room['members']['102']['joined_at'] == original
    assert room['members']['102']['participated']
    assert game_env.db.conn.execute('SELECT COUNT(*) FROM spy_game_participants WHERE user_id = ?', ('102',)).fetchone()[0] == 1
