from datetime import datetime

from core import context, config, plugin_dispatch
from core.db.rewards import RewardManager
from plugins.checkin_recall import CheckinRecallPlugin
from plugins.checkin.events import revoke_attendance
from test.test_blacklist_management import management


def test_true_recall_cleans_history_silently_without_new_rewards(management, monkeypatch):
    run, db, _, _ = management
    monkeypatch.setattr(context, 'plugin_registry', [CheckinRecallPlugin])
    monkeypatch.setattr(config, 'GROUP_REVIEW_REQUIRE', True)  # 未批准群也不能阻止该历史清理例外
    monkeypatch.setattr('plugins.checkin_recall.retract_event', lambda *a, **kw: None)
    grants = []
    monkeypatch.setattr(plugin_dispatch, '_subscriptions', [
        plugin_dispatch.Subscription('checkin.retracted', 'checkin', revoke_attendance, cleanup=True),
        plugin_dispatch.Subscription('checkin.retracted', 'probe', lambda *a: grants.append(True)),
    ])
    db.checkin.insert(42, ['test.png'], message_id=100)
    dt = datetime.strptime(db.checkin.get_by_msg(42, 100)[0][2], '%Y-%m-%d %H:%M:%S')
    RewardManager(db.conn).grant_attendance(42, 'full_week_daily', dt.strftime('%Y-%m-%d'), 'first')
    assert db.points.get(42) == 1
    db.community.ban('user', 42)
    db.community.ban('group', 100)
    assert db.checkin.get_by_msg(42, 100)  # 拉黑本身不删除
    assert run('/撤回打卡', uid=42, gid=100) == ''
    assert db.checkin.get_by_msg(42, 100)
    raw = dict(post_type='notice', notice_type='group_recall', user_id=42, group_id=100,
               message_id=100, self_id=999, operator_id=42)
    assert run.raw(raw) == ''
    assert not db.checkin.get_by_msg(42, 100)
    assert db.points.get(42) == 0
    assert not grants
    assert run.raw(raw) == ''
    assert db.points.get(42) == 0


def test_cleanup_never_bypasses_deployment_or_fake_message(management, monkeypatch):
    run, db, _, _ = management
    monkeypatch.setattr(context, 'plugin_registry', [CheckinRecallPlugin])
    monkeypatch.setattr(context, 'ALLOWED_PLUGINS', frozenset({'blacklist', 'probe'}))
    db.checkin.insert(42, ['test.png'], message_id=100)
    db.community.ban('user', 42)
    raw = dict(post_type='notice', notice_type='group_recall', user_id=42, group_id=100, message_id=100)
    assert run.raw(raw) == ''
    assert db.checkin.get_by_msg(42, 100)
    monkeypatch.setattr(context, 'ALLOWED_PLUGINS', None)
    raw['post_type'] = 'message'
    assert run.raw(raw) == ''
    assert db.checkin.get_by_msg(42, 100)
