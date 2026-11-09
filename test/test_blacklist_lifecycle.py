import pytest

from core import base, config, context
from plugins.blacklist import BlacklistPlugin
from plugins.auto_friend import AutoFriendPlugin
from plugins.welcome import WelcomePlugin
from plugins.group_review import GroupReviewPlugin
from test.test_blacklist_management import management


def setup_plugins(monkeypatch):
    monkeypatch.setattr(context, 'plugin_registry', [BlacklistPlugin, AutoFriendPlugin, WelcomePlugin, GroupReviewPlugin])
    monkeypatch.setattr(context, 'SYSTEM_PLUGINS', frozenset({'blacklist', 'auto_friend', 'welcome', 'group_review'}))
    api = base.ApiWrapper.return_value
    api.call_api.return_value = {'status': 'ok', 'retcode': 0}
    return api


def request(uid=42, gid=None, flag='invite'):
    raw = dict(post_type='request', request_type='friend', user_id=uid, self_id=999, flag=flag)
    if gid is not None:
        raw.update(request_type='group', sub_type='invite', group_id=gid)
    return raw


def test_friend_rejection_and_no_welcome(management, monkeypatch):
    run, db, _, _ = management
    api = setup_plugins(monkeypatch)
    db.community.ban('user', 42)
    assert run.raw(request()) == ''
    api.call_api.assert_called_once_with('set_friend_add_request', {'flag': 'invite', 'approve': False, 'remark': ''})
    api.set_friend_add_request.assert_not_called()
    assert run.raw(dict(post_type='notice', notice_type='friend_add', user_id=42, self_id=999)) == ''
    api.send_private_msg.assert_not_called()
    run.raw(request(uid=43))
    api.set_friend_add_request.assert_called_once()  # 未被封者仍由auto_friend处理
    assert not db.community.is_registered(42)


@pytest.mark.parametrize('response,state', [({'status': 'ok', 'retcode': 0}, 'rejected'),
                                          ({'status': 'failed', 'retcode': 1}, 'pending'),
                                          ({}, 'uncertain')])
def test_group_reject_result_and_no_auto_retry(management, monkeypatch, response, state):
    run, db, _, _ = management
    api = setup_plugins(monkeypatch)
    api.call_api.return_value = response
    db.community.ban('group', 100)
    assert run.raw(request(gid=100)) == ''
    row = db.conn.execute('SELECT * FROM group_requests').fetchone()
    assert row['status'] == state
    assert not db.community.is_group_active(100)
    run.raw(request(gid=100))
    assert api.call_api.call_count == 1
    assert api.call_api.call_args.args[1]['approve'] is False
    api.send_msg.assert_not_called()


def test_lifecycle_exception_and_read_failure_do_not_report_success(management, monkeypatch):
    run, db, _, _ = management
    api = setup_plugins(monkeypatch)
    api.call_api.side_effect = RuntimeError('network failed')
    db.community.ban('user', 42)
    run.raw(request(gid=100))
    row = db.conn.execute('SELECT * FROM group_requests').fetchone()
    assert row['status'] == 'uncertain' and row['remote_state'] == 'unknown'
    assert not db.community.is_group_active(100)
    run.raw(request(gid=100)); assert api.call_api.call_count == 1
    run.raw(request())  # 一次好友拒绝异常，不自动重试
    assert api.call_api.call_count == 2


def test_blocked_group_own_join_leave_still_recorded(management, monkeypatch):
    run, db, _, _ = management
    api = setup_plugins(monkeypatch)
    db.community.activate_group(100)
    db.community.ban('group', 100)
    raw = dict(post_type='notice', notice_type='group_decrease', group_id=100,
               user_id=999, self_id=999, operator_id=42)
    assert run.raw(raw) == ''
    assert not db.community.is_group_active(100)
    raw['notice_type'] = 'group_increase'
    assert run.raw(raw) == ''
    assert db.community.pending_requests()
    assert not db.community.is_group_active(100)
    api.send_msg.assert_not_called()
    api.send_private_msg.assert_not_called()


def test_lifecycle_fact_survives_policy_read_error(management, monkeypatch):
    run, db, hits, _ = management
    setup_plugins(monkeypatch)
    db.community.activate_group(100)
    def fail(**kwargs):
        raise RuntimeError('cannot read blacklist')
    monkeypatch.setattr('core.blacklist.capture', fail)
    assert run.raw(dict(post_type='notice', notice_type='group_decrease', group_id=100,
                        user_id=999, self_id=999)) == ''
    assert not db.community.is_group_active(100)
    assert run('/测试', uid=42) == ''
    assert not hits


def test_rejected_event_database_failure_is_silent(management, monkeypatch):
    from core.db.community import CommunityManager
    run, db, _, _ = management
    setup_plugins(monkeypatch)
    db.community.ban('group', 100)
    def fail(*a, **kw):
        raise RuntimeError('database write failed')
    monkeypatch.setattr(CommunityManager, 'mark_group_removed', fail)
    assert run.raw(dict(post_type='notice', notice_type='group_decrease', group_id=100,
                        user_id=999, self_id=999)) == ''


def test_other_inviter_and_super_protection_and_old_behavior(management, monkeypatch):
    run, db, _, _ = management
    api = setup_plugins(monkeypatch)
    monkeypatch.setattr(config, 'GROUP_REVIEW_REQUIRE', True)
    db.community.ban('user', 42)
    db.community.ban('user', 99)  # 历史超管记录不导致启用新规则时拒绝
    run.raw(request(uid=43, gid=100, flag='other'))
    run.raw(request(uid=99, gid=101, flag='protected'))
    assert len(db.community.pending_requests()) == 2
    api.call_api.assert_not_called()
    monkeypatch.setattr(config, 'BLACKLIST_ENABLED', False)
    run.raw(request(uid=42, gid=102, flag='old'))
    assert api.call_api.call_count == 1  # 旧群审核仍会拒绝
    assert api.call_api.call_args.args[1]['approve'] is False
