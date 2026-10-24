from test.spy_helpers import game_env, new_room, seed, private_output
from plugins.who_is_spy.relay import format_record_summary


def test_live_and_historical_rounds_use_same_roster(game_env):
    room = new_room(game_env)
    seed(game_env, room, phase='playing_vote', votes={'101': '102', '102': '101', '103': '101'})
    first = game_env.run('1', uid=104)
    assert '1号 3票 ← 出局' in private_output(first, 102)
    room = game_env.service.get(room['room_id'])
    seed(game_env, room, phase='playing_vote', votes={'102': '104', '103': '104'})
    second = game_env.run('2', uid=104)
    # 结束消息含过去回合，单独取本轮投票广播检验。
    messages = [c.args[1]['message'][0]['data']['text'] for c in second.call_api.call_args_list
                if c.args[0] == 'send_private_msg' and c.args[1]['user_id'] == 101]
    vote = next(m for m in messages if m.startswith('第2轮 投票结果'))
    assert '1号' not in vote
    assert '4号 2票 ← 出局' in vote
    record = game_env.db.who_is_spy.detail(room['record_id'], user_id=101)
    body = format_record_summary(record)
    round2 = body.split('──── 第2轮 ────')[1]
    assert '1号' not in round2
    assert '4号 2票 ← 出局' in round2
    assert record['snapshot']['history'][0]['participants']['101'] == '1号'
