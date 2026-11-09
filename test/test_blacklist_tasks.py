from datetime import datetime, timedelta
from unittest.mock import Mock

from core import config
from test.test_blacklist_management import management


def enable(db, plugin, gid=None, uid=None):
    if gid is not None:
        db.conn.execute('INSERT OR IGNORE INTO group_plugin_config VALUES (?, ?)', (gid, plugin))
    else:
        db.conn.execute('INSERT OR REPLACE INTO user_plugin_config VALUES (?, ?, 1)', (uid, plugin))
    db.conn.commit()


def alarm_plugin(db):
    from plugins.group_alarm import GroupAlarmPlugin
    plugin = GroupAlarmPlugin.__new__(GroupAlarmPlugin)
    plugin.dbmanager, plugin.api = db, Mock()
    return plugin


def test_alarm_scope_pause_and_recovery_without_duplicate(management):
    _, db, _, _ = management
    past = datetime.now() - timedelta(minutes=5)
    blocked_private = db.alarm.add(42, past, 'private', is_private=True)
    blocked_group = db.alarm.add(43, past, 'group', group_id=100)
    normal_group = db.alarm.add(42, past, 'public', group_id=200)
    for gid in (100, 200):
        enable(db, 'group_alarm', gid=gid)
    enable(db, 'group_alarm', uid=42)
    db.community.ban('user', 42)
    db.community.ban('group', 100)
    plugin = alarm_plugin(db)
    plugin._handle_meta_due()
    rows = dict(db.conn.execute('SELECT id, fired FROM group_alarms'))
    assert rows == {blocked_private: 0, blocked_group: 0, normal_group: 1}
    assert plugin.api.call_api.call_count == 1
    assert plugin.api.call_api.call_args.args[1]['group_id'] == 200
    db.community.unban('user', 42)
    db.community.unban('group', 100)
    plugin._handle_meta_due()
    assert all(fired for _, fired in db.conn.execute('SELECT id, fired FROM group_alarms'))
    assert plugin.api.call_api.call_count == 3
    plugin._handle_meta_due()
    assert plugin.api.call_api.call_count == 3
    assert not db.community.is_registered(42)  # 解除和任务恢复不替账号注册
    assert not db.community.is_group_active(100)


def test_unban_does_not_override_plugin_or_group_approval(management, monkeypatch):
    _, db, _, _ = management
    past = datetime.now() - timedelta(minutes=5)
    db.alarm.add(42, past, 'private', is_private=True)
    db.alarm.add(42, past, 'group', group_id=100)
    enable(db, 'group_alarm', uid=42)
    enable(db, 'group_alarm', gid=100)
    db.community.ban('user', 42)
    db.community.ban('group', 100)
    db.community.unban('user', 42)
    db.community.unban('group', 100)
    db.conn.execute("UPDATE user_plugin_config SET enabled=0 WHERE user_id=42 AND plugin_name='group_alarm'")
    db.conn.commit()
    monkeypatch.setattr(config, 'GROUP_REVIEW_REQUIRE', True)
    plugin = alarm_plugin(db)
    plugin._handle_meta_due()
    assert all(row[0] == 0 for row in db.conn.execute('SELECT fired FROM group_alarms'))
    plugin.api.call_api.assert_not_called()


def test_recurring_alarm_keeps_time_when_blocked(management):
    _, db, _, _ = management
    db.alarm.add(42, datetime.now() - timedelta(days=8), 'recurring', group_id=100, recur=(2, 1, 0, 0))
    enable(db, 'group_alarm', gid=100)
    db.community.ban('group', 100)
    before = tuple(db.conn.execute('SELECT fired, fire_at FROM group_alarms').fetchone())
    plugin = alarm_plugin(db)
    plugin._handle_meta_due()
    assert tuple(db.conn.execute('SELECT fired, fire_at FROM group_alarms').fetchone()) == before
    plugin.api.call_api.assert_not_called()
    db.community.unban('group', 100)
    plugin._handle_meta_due()
    assert db.conn.execute('SELECT fire_at FROM group_alarms').fetchone()[0] != before[1]
    assert plugin.api.call_api.call_count == 1


def test_each_alarm_admitted_separately_but_started_record_finishes(management):
    _, db, _, _ = management
    first = db.alarm.add(42, datetime.now() - timedelta(days=8), 'first', group_id=100, recur=(2, 1, 0, 0))
    second = db.alarm.add(42, datetime.now() - timedelta(days=7), 'second', group_id=100)
    enable(db, 'group_alarm', gid=100)
    old_time = db.conn.execute('SELECT fire_at FROM group_alarms WHERE id=?', (first,)).fetchone()[0]
    plugin = alarm_plugin(db)
    def ban_during_send(*args):
        db.community.ban('group', 100)
        return {'status': 'ok', 'retcode': 0}
    plugin.api.call_api.side_effect = ban_during_send
    plugin._handle_meta_due()
    assert plugin.api.call_api.call_count == 1
    assert db.conn.execute('SELECT fire_at FROM group_alarms WHERE id=?', (first,)).fetchone()[0] != old_time
    assert db.conn.execute('SELECT fired FROM group_alarms WHERE id=?', (second,)).fetchone()[0] == 0


def test_task_read_error_preserves_record_and_disabled_config_compatible(management, monkeypatch):
    _, db, _, _ = management
    db.alarm.add(42, datetime.now() - timedelta(minutes=5), 'private', is_private=True)
    enable(db, 'group_alarm', uid=42)
    plugin = alarm_plugin(db)
    with monkeypatch.context() as patch:
        def fail(**kw):
            raise RuntimeError('read failed')
        patch.setattr('core.blacklist.capture', fail)
        plugin._handle_meta_due()
    assert db.conn.execute('SELECT fired FROM group_alarms').fetchone()[0] == 0
    plugin.api.call_api.assert_not_called()
    db.community.ban('user', 42)
    monkeypatch.setattr(config, 'BLACKLIST_ENABLED', False)
    plugin._handle_meta_due()
    assert db.conn.execute('SELECT fired FROM group_alarms').fetchone()[0] == 1


def lottery_setup(db, monkeypatch):
    import plugins.immortal_lottery as lottery
    monkeypatch.setattr(lottery, '_now_bj', lambda: datetime(2026, 10, 18, 20, 0))
    monkeypatch.setattr(lottery, '_name', lambda uid: str(uid))  # 不调用真实OneBot昵称接口
    monkeypatch.setattr(lottery.random, 'randint', lambda a, b: 0)
    period = '2026-10-12'
    for gid, uid in ((100, 41), (200, 42), (300, 43)):
        enable(db, 'immortal_lottery', gid=gid)
        db.points.set(uid, 10)
        assert db.immortal.try_place_bet(gid, period, uid, '0000', '2026-10-12')[0]
        db.immortal.set_carry(gid, 99)
    plugin = lottery.ImmortalLotteryPlugin.__new__(lottery.ImmortalLotteryPlugin)
    plugin.dbmanager, plugin.api = db, Mock()
    return plugin, period


def test_paid_draw_preserves_blocked_participant_rights_and_pauses_group(management, monkeypatch):
    _, db, _, _ = management
    plugin, period = lottery_setup(db, monkeypatch)
    db.community.ban('group', 100)
    db.community.ban('user', 42)
    plugin._handle_draw_tick()
    assert not db.immortal.has_result(100, period)
    assert db.points.get(41) == 9 and db.immortal.carry(100) == 99
    assert db.immortal.list_bets(100, period)
    assert db.immortal.has_result(200, period) and db.immortal.has_result(300, period)
    assert db.points.get(42) == db.points.get(43) > 9
    amounts = [db.points.get(uid) for uid in (41, 42, 43)]
    plugin._handle_draw_tick()
    assert [db.points.get(uid) for uid in (41, 42, 43)] == amounts
    assert {call.args[1]['group_id'] for call in plugin.api.call_api.call_args_list} == {200, 300}
    db.community.unban('group', 100)
    plugin._handle_draw_tick()  # 仍在原开奖窗口，恢复后处理一次
    assert db.points.get(41) == db.points.get(43)
    before = db.points.get(41)
    plugin._handle_draw_tick()
    assert db.points.get(41) == before


def test_draw_admitted_before_ban_keeps_finishing(management, monkeypatch):
    _, db, _, _ = management
    plugin, period = lottery_setup(db, monkeypatch)
    original = plugin._run_single_group_draw
    def ban_then_draw(gid, pk):
        db.community.ban('group', gid)
        original(gid, pk)
    monkeypatch.setattr(plugin, '_run_single_group_draw', ban_then_draw)
    plugin._handle_draw_tick()
    assert all(db.immortal.has_result(gid, period) for gid in (100, 200, 300))
    assert all(db.points.get(uid) > 9 for uid in (41, 42, 43))
