import pytest
from test.spy_helpers import game_env, new_room, seed, output


def prepared(env):
    room = new_room(env, n=5)
    env.service.leave(102)
    room = env.service.get(room['room_id'])
    room['players']['101']['alive'] = False  # 已淘汰但留房观战
    room = seed(env, room, players=room['players'], phase='playing_vote', votes={'103': '105', '104': '105'})
    env.db.conn.executemany('INSERT INTO user_game_stats VALUES (?, 9, 9, 9, 0)', [('101',), ('102',)])
    env.db.conn.commit()
    return room


def test_spectator_wins_departed_counts_only_participation_and_no_repeat(game_env):
    room = prepared(game_env)
    game_env.run('3', uid=105)
    store = game_env.db.who_is_spy
    assert store.get_internal(room['record_id'])['status'] == 'finished'
    stats = {str(r[0]): tuple(r[1:]) for r in game_env.db.conn.execute('SELECT user_id, total_games, total_wins, civilian_wins FROM user_game_stats')}
    assert stats['101'] == (10, 10, 10)
    assert stats['102'] == (10, 9, 9)
    assert {301, 304, 306} <= set(game_env.db.titles.list(101))
    assert game_env.db.titles.has(102, 301)
    assert not game_env.db.titles.has(102, 304) and not game_env.db.titles.has(102, 306)
    with pytest.raises(ValueError):
        game_env.service.input(room['record_id'], 105, '3')
    assert tuple(game_env.db.conn.execute('SELECT total_games, total_wins FROM user_game_stats WHERE user_id=?', ('101',)).fetchone()) == (10, 10)


def test_rewards_failure_rolls_back_final_record_ballot_stats_and_titles(game_env):
    room = prepared(game_env)
    before = game_env.db.who_is_spy.get_internal(room['record_id'])
    game_env.db.conn.execute("""CREATE TRIGGER fail_spy_stats BEFORE INSERT ON user_game_stats
                              WHEN NEW.user_id='105' BEGIN SELECT RAISE(ABORT, 'reward failure'); END""")
    game_env.db.conn.commit()
    api = game_env.run('3', uid=105)
    assert '未确认成功' in output(api)
    assert game_env.db.who_is_spy.get_internal(room['record_id']) == before
    assert not game_env.db.titles.list(101)
    assert tuple(game_env.db.conn.execute('SELECT total_games, total_wins FROM user_game_stats WHERE user_id=?', ('101',)).fetchone()) == (9, 9)
    game_env.db.conn.execute('DROP TRIGGER fail_spy_stats')
    game_env.db.conn.commit()
    game_env.run('3', uid=105)
    assert game_env.db.who_is_spy.get_internal(room['record_id'])['status'] == 'finished'


def test_unstarted_exit_cancel_and_restart_do_not_grant_stats(game_env):
    from plugins.who_is_spy.history import recover_interrupted_games
    room = new_room(game_env, start=False)
    game_env.service.leave(101)
    game_env.service.cancel(room['room_id'], 102, 100)  # 等待阶段房主转移
    assert game_env.db.who_is_spy.detail(room['record_id'], user_id=101)
    room = new_room(game_env, key='interrupt')
    recover_interrupted_games()
    assert game_env.db.conn.execute('SELECT COUNT(*) FROM user_game_stats').fetchone()[0] == 0


def test_private_or_forward_send_failure_does_not_repeat_rewards(game_env):
    from plugins.who_is_spy.relay import GameMessenger
    room = prepared(game_env)
    result = game_env.service.input(room['record_id'], 105, '3')
    from unittest.mock import Mock
    api = Mock()
    api.call_api.side_effect = RuntimeError('offline')
    GameMessenger(api, game_env.db.who_is_spy).emit(result.events)
    assert game_env.db.who_is_spy.get_internal(room['record_id'])['status'] == 'finished'
    assert tuple(game_env.db.conn.execute('SELECT total_games, total_wins FROM user_game_stats WHERE user_id=?', ('101',)).fetchone()) == (10, 10)
