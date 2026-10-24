from test.spy_helpers import game_env, new_room, seed, output, private_output


def test_start_and_unfinished_queries_do_not_reveal_roles(game_env):
    room = new_room(game_env, start=False)
    api = game_env.run('/开始 ' + room['room_id'], gid=100)
    assert '1 个卧底，3 个平民' in output(api)
    for uid, word in ((101, '苹果'), (104, '梨子')):
        body = private_output(api, uid)
        assert f'你的词条：{word}' in body
        assert '你的角色' not in body and '你的阵营' not in body
        assert ('梨子' if word == '苹果' else '苹果') not in body
    for command in ('/状态', f"/游戏记录 查看 {room['record_id']}"):
        body = output(game_env.run(command, uid=104))
        assert '苹果' not in body and '梨子' not in body
        assert '玩家身份' not in body and 'spy' not in body


def test_cancel_command_sends_one_group_confirmation(game_env):
    room = new_room(game_env)
    api = game_env.run('/放弃 ' + room['room_id'], gid=100)
    api.send_msg.assert_not_called()
    groups = [c for c in api.call_api.call_args_list if c.args[0] == 'send_group_msg']
    assert len(groups) == 1
    assert '无胜负结果' in output(api)


def test_cancelled_and_interrupted_never_reveal_secrets(game_env):
    from plugins.who_is_spy.history import recover_interrupted_games
    first = new_room(game_env)
    game_env.service.cancel(first['room_id'], 101, 100)
    second = new_room(game_env, key='second')
    recover_interrupted_games()
    for room in (first, second):
        body = output(game_env.run(f"/游戏记录 查看 {room['record_id']}"))
        assert '无胜负' in body and '胜利' not in body
        assert '苹果' not in body and '梨子' not in body


def test_finished_reveals_but_never_pushes_to_departed_player(game_env):
    room = new_room(game_env, n=5)
    game_env.service.leave(101)
    room = game_env.service.get(room['room_id'])
    seed(game_env, room, phase='playing_vote', votes={'102': '105', '103': '105', '104': '105'})
    api = game_env.run('2', uid=105)
    assert private_output(api, 101) == ''
    assert '玩家身份' in private_output(api, 102)
    assert '完整记录：/游戏记录 查看' in private_output(api, 102)
    assert '──── 第' not in private_output(api, 102)  # 私聊结局不重复发送长复盘
    body = output(game_env.run(f"/游戏记录 查看 {room['record_id']}", uid=101))
    assert '苹果' in body and '梨子' in body
    assert '本人：已退出' in body
