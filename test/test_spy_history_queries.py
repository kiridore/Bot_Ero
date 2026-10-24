import pytest
from test.spy_helpers import game_env, new_room, output


def test_real_command_user_group_detail_and_legacy_syntax(game_env):
    room = new_room(game_env, start=False)
    assert f"#{room['record_id']}" in output(game_env.run('/游戏记录'))
    assert '本人参与' in output(game_env.run('/游戏记录'))
    assert '本群' in output(game_env.run('/游戏记录', uid=999, gid=100))
    assert '不可查看' in output(game_env.run(f"/游戏记录 查看 {room['record_id']}", uid=999))
    assert '不可查看' in output(game_env.run(f"/游戏记录 查看 {room['record_id']}", gid=200))
    assert '未开始' in output(game_env.run(f"/游戏记录 查看 {room['record_id']}", gid=100))
    assert '不再按旧房间号查询' in output(game_env.run('/游戏记录 ' + room['room_id']))


@pytest.mark.parametrize('suffix', ['列表 0', '列表 -1', '列表 abc', '查看 0', '查看 9'*20, '列表 1 extra', '查看'])
def test_bad_query_does_not_leak_or_write(game_env, suffix):
    api = game_env.run('/游戏记录 ' + suffix)
    assert output(api)
    assert game_env.db.conn.execute('SELECT COUNT(*) FROM spy_game_records').fetchone()[0] == 0


def test_real_pagination_and_own_history_includes_cancelled_experiences(game_env):
    for n in range(11):
        room = game_env.service.create(100, 101, 4, f'page-{n}').room
        game_env.service.join(room['room_id'], 101, '本人')
        game_env.service.leave(101)
    first = output(game_env.run('/游戏记录'))
    assert first.count('｜房间 ') == 10 and '下一页：/游戏记录 列表 2' in first
    second = output(game_env.run('/游戏记录 列表 2'))
    assert second.count('｜房间 ') == 1 and '已解散' in second
    assert '本人已退出' in second and '卧底胜' not in second
