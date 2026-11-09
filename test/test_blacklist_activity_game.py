from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from core.blacklist import BlacklistSnapshot
from test.test_blacklist_management import management
from test.test_blacklist_tasks import enable


def test_activity_pauses_blocked_group_and_recovers(management):
    from plugins.activity import ActivityTimerPlugin
    _, db, _, _ = management
    past = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    for gid in (100, 200):
        db.conn.execute("INSERT INTO activities (group_id,type,title,status,created_by,signup_deadline,created_at)"
                        " VALUES (?, 'match', 'test', 'open', '42', ?, ?)", (gid, past, past))
        enable(db, 'activity', gid=gid)
    db.community.ban('group', 100)
    plugin = ActivityTimerPlugin.__new__(ActivityTimerPlugin)
    plugin.dbmanager, plugin.api = db, Mock()
    plugin._scan()
    assert dict(db.conn.execute('SELECT group_id,status FROM activities')) == {100: 'open', 200: 'cancelled'}
    db.community.unban('group', 100)
    plugin._scan()
    assert dict(db.conn.execute('SELECT group_id,status FROM activities')) == {100: 'cancelled', 200: 'cancelled'}


def test_activity_start_and_finish_share_one_admission(management, monkeypatch):
    import plugins.activity as activity
    _, db, _, _ = management
    past = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    db.conn.execute("INSERT INTO activities (group_id,type,title,status,created_by,signup_deadline,deadline,created_at)"
                    " VALUES (100, 'match', 'test', 'open', '42', ?, ?, ?)", (past, past, past))
    enable(db, 'activity', gid=100)
    stages = []
    def start(api, manager, act):
        stages.append('start')
        manager.community.ban('group', 100)
        manager.activity.update_activity(act['id'], status='running')
    def finish(api, manager, act):
        assert not api.blacklist_snapshot.blocks(group_id=100)
        stages.append('finish')
        manager.activity.update_activity(act['id'], status='finished')
    monkeypatch.setattr(activity, '_start_activity', start)
    monkeypatch.setattr(activity, '_finish_activity', finish)
    plugin = activity.ActivityTimerPlugin.__new__(activity.ActivityTimerPlugin)
    plugin.dbmanager, plugin.api = db, Mock()
    plugin._scan()
    assert stages == ['start', 'finish']
    assert db.community.is_banned('group', 100)


def test_activity_private_notifications_use_fixed_snapshot(management):
    from plugins.activity import _send_private
    _, db, _, _ = management
    api = Mock()
    api.blacklist_snapshot = BlacklistSnapshot(users=frozenset({42}))
    db.community.ban('user', 43)  # 不能改变已经获准的快照
    _send_private(api, 42, {'type': 'text', 'data': {'text': 'x'}})
    _send_private(api, 43, {'type': 'text', 'data': {'text': 'x'}})
    assert api.call_api.call_count == 1
    assert api.call_api.call_args.args[1]['user_id'] == 43


def test_spy_settlement_records_stats_but_no_free_title_or_private_notice(management):
    from plugins.who_is_spy.relay import GameMessenger
    from plugins.who_is_spy.titles import grant_game_titles
    _, db, _, _ = management
    for uid in ('42', '43'):
        db.conn.execute('INSERT INTO user_game_stats (user_id,total_games,total_wins,civilian_wins,spy_wins)'
                        ' VALUES (?,9,9,9,0)', (uid,))
    db.conn.commit()
    snapshot = BlacklistSnapshot(users=frozenset({42}))

    # 结算：被封账号战绩照记（阈值 10 → 称号 306），但不解锁新称号
    db.conn.execute('BEGIN')
    blocked = grant_game_titles(db, '42', 'civilian', 'civilian',
                                allow_titles=not snapshot.blocks(user_id=42))
    opened = grant_game_titles(db, '43', 'civilian', 'civilian',
                               allow_titles=not snapshot.blocks(user_id=43))
    db.conn.commit()
    assert blocked == [] and not db.titles.has('42', 306)
    assert opened and db.titles.has('43', 306)
    assert db.conn.execute(
        "SELECT total_games FROM user_game_stats WHERE user_id='42'").fetchone()[0] == 10

    # 主动私聊：被封账号跳过，未封账号照常发送
    api = Mock()
    api.blacklist_snapshot = snapshot
    messenger = GameMessenger(api)
    room = {'record_id': 'test', 'players': {'42': {'left': False}, '43': {'left': False}}}
    messenger.private(room, 43, '通知')
    messenger.private(room, 42, '通知')
    assert api.call_api.call_count == 1
    assert api.call_api.call_args.args[1]['user_id'] == 43
    assert list(db.conn.execute('SELECT civilian_wins FROM user_game_stats ORDER BY user_id'))[0][0] == 10
