from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import config, context
from core.blacklist import BlacklistSnapshot
from test.test_blacklist_management import management


def test_unban_preserves_registration_and_plugin_settings(management, monkeypatch):
    run, db, hits, _ = management
    monkeypatch.setattr(config, 'REGISTER_REQUIRE', True)
    monkeypatch.setattr(context, 'SYSTEM_PLUGINS', frozenset({'blacklist'}))
    db.conn.execute("INSERT INTO user_plugin_config VALUES (42, 'probe', 0)")
    db.conn.commit()
    db.community.ban('user', 42)
    run('/测试', uid=42)
    assert not hits
    assert '已解除' in run('/黑名单 解除 用户 42')
    assert not db.community.is_registered(42)
    run('/测试', uid=42)
    assert not hits
    db.community.register_user(42)
    run('/测试', uid=42)
    assert not hits  # 不改变原关闭设置
    assert db.conn.execute("SELECT enabled FROM user_plugin_config WHERE user_id=42 AND plugin_name='probe'").fetchone()[0] == 0
    db.conn.execute("UPDATE user_plugin_config SET enabled=1 WHERE user_id=42 AND plugin_name='probe'")
    db.conn.commit()
    run('/测试', uid=42)
    assert len(hits) == 1


def test_unban_does_not_approve_group(management, monkeypatch):
    run, db, hits, _ = management
    monkeypatch.setattr(config, 'GROUP_REVIEW_REQUIRE', True)
    db.community.ban('group', 100)
    assert '已解除' in run('/黑名单 解除 群 100')
    run('/测试', uid=42, gid=100)
    assert not hits and not db.community.is_group_active(100)
    db.community.activate_group(100)
    run('/测试', uid=42, gid=100)
    assert len(hits) == 1


@pytest.mark.parametrize('cmd', ['/超级补卡', '/超级单日补卡', '/补卡', '/单日补卡'])
def test_admin_cannot_create_new_checkin_for_banned_recipient(management, cmd):
    from plugins.remedy_checkin import RemedyCheckinPlugin
    _, db, _, _ = management
    plugin = RemedyCheckinPlugin.__new__(RemedyCheckinPlugin)
    plugin.bot_event = SimpleNamespace(user_id=99)
    plugin.admin_user = lambda: True
    plugin.cmd, plugin.args = cmd, ['2020-01-01', '42']
    plugin.api, plugin.dbmanager = Mock(), db
    plugin.operation = SimpleNamespace(blacklist_snapshot=BlacklistSnapshot(users=frozenset({42})))
    db.points.set(42, 20)
    plugin.handle()
    assert db.points.get(42) == 20
    assert db.conn.execute('SELECT COUNT(*) FROM checkin_records').fetchone()[0] == 0
    plugin.api.send_msg.assert_not_called()


@pytest.mark.parametrize('explicit', [True, False])
def test_private_activity_submission_does_not_bypass_group_ban(management, explicit):
    from plugins.activity import ActivityPlugin
    plugin = ActivityPlugin.__new__(ActivityPlugin)
    plugin.bot_event = SimpleNamespace(user_id=42)
    plugin.operation = SimpleNamespace(blacklist_snapshot=BlacklistSnapshot(groups=frozenset({100})))
    plugin.dbmanager, plugin.api = Mock(), Mock()
    activity = {'id': 1, 'group_id': 100}
    plugin.dbmanager.activity.get_running_activity_for_user_and_id.return_value = activity
    plugin.dbmanager.activity.get_running_activities_for_user.return_value = [activity]
    plugin._handle_submit(['1'] if explicit else [])
    plugin.dbmanager.activity.update_member.assert_not_called()
    plugin.dbmanager.activity.get_member.assert_not_called()
    plugin.api.send_msg.assert_not_called()


@pytest.mark.parametrize('command', ['/加入', '/退出', '/状态', None])
def test_private_spy_room_operations_respect_group_ban(management, monkeypatch, command):
    import plugins.who_is_spy as spy
    room = {'group_id': 100, 'room_id': 'test', 'phase': 'playing_vote'}
    monkeypatch.setattr(spy, 'get_room', lambda _: room)
    monkeypatch.setattr(spy, 'find_player_room', lambda _: room)
    add, remove, vote = Mock(), Mock(), Mock()
    monkeypatch.setattr(spy, 'add_player', add)
    monkeypatch.setattr(spy, 'remove_player', remove)
    monkeypatch.setattr(spy, 'collect_vote', vote)
    plugin = spy.WhoIsSpyPlugin.__new__(spy.WhoIsSpyPlugin)
    plugin.bot_event = SimpleNamespace(user_id=42, group_id=None)
    plugin.operation = SimpleNamespace(blacklist_snapshot=BlacklistSnapshot(groups=frozenset({100})))
    plugin.api = Mock()
    plugin._cmd, plugin._args = command, ['test']
    plugin._game_room_id, plugin._input_text = 'test', '1'
    if command is None:
        plugin._handle_game_input()
    else:
        plugin._handle_command()
    add.assert_not_called()
    remove.assert_not_called()
    vote.assert_not_called()
    plugin.api.send_msg.assert_not_called()
