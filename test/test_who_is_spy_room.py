"""原退出回归迁到真实持久房间，保留非房主退出/房主转移/空房解散三项断言。"""
from test.spy_helpers import game_env


def waiting(env):
    room = env.service.create(100, 111, 4, 'room').room
    env.service.join(room['room_id'], 111, '甲')
    env.service.join(room['room_id'], 222, '乙')
    return room


def test_member_exit_waiting_no_crash(game_env):
    room = waiting(game_env)
    result = game_env.service.leave(222)
    assert '已退出房间' in result.reply
    assert '111' in result.room['players'] and '222' not in result.room['players']
    assert game_env.db.who_is_spy.detail(room['record_id'], user_id=222)


def test_creator_exit_transfers_room(game_env):
    room = waiting(game_env)
    game_env.service.leave(111)
    current = game_env.service.get(room['room_id'])
    assert current['creator_id'] == '222'
    assert current['players']['222']['alias'] == '1号'


def test_last_player_disbands(game_env):
    room = waiting(game_env)
    game_env.service.leave(222)
    game_env.service.leave(111)
    assert game_env.db.who_is_spy.active_room(room['room_id']) is None
    assert game_env.db.who_is_spy.get_internal(room['record_id'])['status'] == 'cancelled'
