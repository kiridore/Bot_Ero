"""群审核任务组2/3/4：隔离数据库、真实插件和模拟OneBot结果，不访问真实QQ。"""
from unittest.mock import Mock

import pytest

from core import config, context
from core.database_manager import DbManager
from core.event import Event
from core.message_output import MessageOutput
from core.plugin_dispatch import Operation
from plugins.group_review import GroupReviewPlugin
import plugins.group_review as review


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'review.db')
    monkeypatch.setattr(config, 'GROUP_REVIEW_REQUIRE', True)
    monkeypatch.setattr(config, 'GROUP_REVIEW_DEFAULT_PACK', '基础包')
    monkeypatch.setattr(config, 'COMMUNITY_MAX_GROUPS', 1)
    monkeypatch.setattr(context, 'ALLOWED_PLUGINS', None)
    monkeypatch.setattr(context, 'SYSTEM_PLUGINS', frozenset({'group_review', 'menu', 'group_manager'}))
    db = DbManager()
    sent, api = [], Mock()
    api.call_api.return_value = {'status': 'ok', 'retcode': 0, 'data': None}
    def run(raw, admin=True):
        p = GroupReviewPlugin.__new__(GroupReviewPlugin)
        p.bot_event, p.dbmanager, p.api = Event(raw), db, api
        p.super_user = lambda: admin
        target = ('group', raw['group_id']) if raw.get('group_id') else ('private', raw.get('user_id', 7))
        op = Operation({'group_review': True}, MessageOutput(lambda r: sent.append(r) or 1, target))
        p.operation = op
        before = db.conn.total_changes
        matched = p.match('notice' if raw.get('post_type') == 'notice' else 'message')
        assert db.conn.total_changes == before  # match纯判断
        if matched:
            op.execute('group_review', p.handle)
            op.finish()
        return p, matched
    yield db, sent, api, run
    db.conn.close()


def invite(gid=100, flag='one', subtype='invite'):
    return {'post_type': 'request', 'request_type': 'group', 'sub_type': subtype,
            'group_id': gid, 'user_id': 42, 'self_id': 999, 'flag': flag}


def notice(kind='group_increase', uid=999, gid=100):
    return {'post_type': 'notice', 'notice_type': kind, 'user_id': uid,
            'self_id': 999, 'operator_id': 42, 'group_id': gid}


def command(message):
    return {'post_type': 'message', 'message_type': 'private', 'user_id': 7,
            'message': [{'type': 'text', 'data': {'text': message}}]}


def contents(sent):
    return '\n'.join(str(r.content) for r in sent)


def test_invite_dedupe_and_ignore_member_add(env):
    db, sent, api, run = env
    assert not run(invite(subtype='add'))[1]
    run(invite()); run(invite())
    assert len(db.community.pending_requests()) == 1
    assert len(sent) == len(config.SUPER_USER)
    api.call_api.assert_not_called()


def test_only_bot_join_and_leave_update_registry(env):
    db, sent, api, run = env
    assert not run(notice(uid=42))[1]
    malformed = {'post_type': 'notice', 'notice_type': 'group_decrease', 'group_id': 100}
    assert not run(malformed)[1]
    assert not db.community.pending_requests()
    run(notice()); run(notice())
    assert len(db.community.pending_requests()) == 1
    row = db.community.pending_requests()[0]
    assert row['kind'] == 'manual'
    run(command('/审核 100 通过'))
    assert db.community.is_group_active(100)
    api.call_api.assert_not_called()
    run(notice('group_decrease', uid=42))
    assert db.community.is_group_active(100)
    run(notice('group_decrease'))
    assert not db.community.is_group_active(100)
    assert db.conn.execute('SELECT COUNT(*) FROM group_plugin_config').fetchone()[0] > 0


def test_normal_users_cannot_query_or_approve(env):
    db, sent, api, run = env
    run(invite()); sent.clear()
    run(command('/待审'), admin=False)
    run(command('/审核 100 通过'), admin=False)
    assert not sent and not db.community.is_group_active(100)
    api.call_api.assert_not_called()


def test_approve_and_no_duplicate_welcome(env):
    db, sent, api, run = env
    run(invite()); sent.clear()
    run(command('/审核 100 通过'))
    assert db.community.is_group_active(100)
    api.call_api.assert_called_once_with('set_group_add_request', {
        'flag': 'one', 'sub_type': 'invite', 'approve': True, 'reason': ''})
    assert len([r for r in sent if r.target == ('group', 100)]) == 1
    run(command('/审核 100 通过'))
    assert api.call_api.call_count == 1
    assert len([r for r in sent if r.target == ('group', 100)]) == 1


def test_output_failure_keeps_queue_and_approved_state(env, monkeypatch):
    db, sent, api, run = env
    flush = MessageOutput.flush
    def fail_delivery(output):
        output.send = Mock(return_value=0)
        return flush(output)
    monkeypatch.setattr(MessageOutput, 'flush', fail_delivery)
    run(invite())
    assert len(db.community.pending_requests()) == 1
    run(command('/审核 100 通过'))
    assert db.community.is_group_active(100)
    run(command('/审核 100 通过'))
    assert api.call_api.call_count == 1


def test_manual_reject_no_fake_flag_or_quit(env):
    db, sent, api, run = env
    run(notice())
    run(command('/审核 100 拒绝'))
    assert not db.community.is_group_active(100)
    assert db.community.pending_requests() == []
    api.call_api.assert_not_called()
    assert '不自动退群' in contents(sent)


@pytest.mark.parametrize('response, state', [({}, 'uncertain'),
    ({'status': 'failed', 'retcode': 100}, 'pending'),
    ({'status': 'async', 'retcode': 1}, 'uncertain')])
def test_remote_not_confirmed_does_not_activate(env, response, state):
    db, sent, api, run = env
    run(invite()); api.call_api.return_value = response
    run(command('/审核 100 通过'))
    assert not db.community.is_group_active(100)
    assert db.community.pending_requests()[0]['status'] == state
    assert not [r for r in sent if r.target == ('group', 100)]


def test_unknown_then_confirm_join_resumes_without_reapprove(env):
    db, sent, api, run = env
    run(invite()); api.call_api.return_value = {}
    run(command('/审核 100 通过'))
    api.call_api.return_value = {'status': 'ok', 'retcode': 0, 'data': [{'group_id': 100}]}
    run(command('/审核 100 通过'))
    assert db.community.is_group_active(100)
    assert [c.args[0] for c in api.call_api.call_args_list] == ['set_group_add_request', 'get_group_list']


def test_unknown_rejection_is_not_inferred_from_group_absence(env):
    db, sent, api, run = env
    run(invite()); api.call_api.return_value = {}
    run(command('/审核 100 拒绝')); run(command('/审核 100 拒绝'))
    assert db.community.pending_requests()[0]['status'] == 'uncertain'
    assert api.call_api.call_count == 1


def test_multi_request_requires_explicit_id(env):
    db, sent, api, run = env
    run(invite()); run(invite(flag='two'))
    run(command('/审核 100 通过'))
    api.call_api.assert_not_called()
    assert '多条' in contents(sent)
    rid = db.community.pending_requests()[0]['id']
    run(command(f'/审核 100 通过 {rid}'))
    assert db.community.is_group_active(100)


def test_local_failure_resumes_without_remote_call(env):
    db, sent, api, run = env
    run(invite())
    db.conn.execute("CREATE TRIGGER stop_seed BEFORE INSERT ON group_plugin_config BEGIN SELECT RAISE(ABORT,'failed'); END")
    db.conn.commit()
    run(command('/审核 100 通过'))
    assert not db.community.is_group_active(100)
    assert db.community.pending_requests()[0]['remote_state'] == 'ok'
    db.conn.execute('DROP TRIGGER stop_seed'); db.conn.commit()
    run(command('/审核 100 通过'))
    assert db.community.is_group_active(100)
    assert api.call_api.call_count == 1


@pytest.mark.parametrize('scope', ['user', 'group'])
def test_banned_invite_auto_rejected(env, scope):
    db, sent, api, run = env
    db.community.ban(scope, 42 if scope == 'user' else 100)
    run(invite())
    assert db.community.pending_requests() == []
    assert not db.community.is_group_active(100)
    assert api.call_api.call_args.args[1]['approve'] is False


def test_capacity_rejection_and_recheck_at_approval(env):
    db, sent, api, run = env
    run(invite())
    db.community.activate_group(200)
    run(command('/审核 100 通过'))
    api.call_api.assert_not_called()
    assert '上限' in contents(sent)
    run(invite(300, 'two'))
    assert api.call_api.call_args.args[1]['approve'] is False


def test_concurrent_commands_do_not_overfill_capacity(env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    db, sent, api, run = env
    run(invite(100, 'one')); run(invite(200, 'two'))
    barrier = Barrier(2)
    def approve(gid):
        local = DbManager()
        try:
            p = GroupReviewPlugin.__new__(GroupReviewPlugin)
            p.bot_event, p.dbmanager, p.api = Event(command(f'/审核 {gid} 通过')), local, api
            p.super_user = lambda: True
            p.operation = Operation({'group_review': True}, MessageOutput(lambda r: 1, ('private', 7)))
            assert p.match('message')
            barrier.wait(timeout=10)
            p.handle()
            p.operation.finish()
        finally:
            local.conn.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(approve, gid) for gid in (100, 200)]
        for result in results:
            result.result(timeout=20)
    assert len(db.community.iter_active_groups()) == 1
    assert api.call_api.call_count == 1


def test_scope_gate_blocks_system_and_old_enabled_settings(env, monkeypatch):
    db, sent, api, run = env
    db.conn.execute("INSERT INTO group_plugin_config VALUES (100,'group_alarm')"); db.conn.commit()
    assert not context.effective_for_scope('group_alarm', group_id=100)
    assert not context.effective_for_scope('menu', group_id=100)
    assert context.group_event_gate({'group_id': 100}) == frozenset({'group_review'})
    assert context.plugin_settings_snapshot(100) == {'group_review': True}
    db.community.activate_group(100)
    assert context.effective_for_scope('group_alarm', group_id=100)
    assert context.group_event_gate({'group_id': 100}) is None
    db.community.mark_group_removed(100)
    assert not context.effective_for_scope('group_alarm', group_id=100)
    monkeypatch.setattr(config, 'GROUP_REVIEW_REQUIRE', False)
    assert context.effective_for_scope('group_alarm', group_id=100)
    assert context.group_event_gate({'group_id': 100}) is None
    assert not run(invite(300, 'off'))[1]


def test_real_main_loop_blocks_business_but_keeps_lifecycle(env, monkeypatch):
    import ast
    from pathlib import Path
    from core.logger import logger
    db, sent, api, run = env
    seen = []
    class Business:
        __module__ = 'plugins.business'
        def __init__(self, raw):
            self.raw = raw
        def match(self, event_type):
            seen.append('business-match')
            return True
        def handle(self):
            seen.append('business-handle')
    class Lifecycle(Business):
        __module__ = 'plugins.group_review'
        def match(self, event_type):
            seen.append('review')
            return False
    monkeypatch.setattr(context, 'plugin_registry', [Business, Lifecycle])
    db.conn.execute("INSERT INTO group_plugin_config VALUES (100,'business')"); db.conn.commit()
    source = ast.parse((Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8'))
    function = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'plugin_pool')
    namespace = {'runtime_context': context, 'Operation': Operation, 'MessageOutput': MessageOutput,
                 'send_request': lambda r: 1, 'logger': logger}
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'main.py', 'exec'), namespace)
    namespace['plugin_pool']({'post_type': 'message', 'group_id': 100, 'user_id': 7}, 'message')
    assert seen == []
    namespace['plugin_pool'](notice(), 'notice')
    assert seen == ['review']
    seen.clear()
    db.community.activate_group(100)
    namespace['plugin_pool']({'post_type': 'message', 'group_id': 100, 'user_id': 7}, 'message')
    assert seen == ['business-match', 'business-handle', 'review']


def test_real_alarm_keeps_due_record_until_group_approved(env):
    from datetime import datetime, timedelta
    from plugins.group_alarm import GroupAlarmPlugin
    db, sent, api, run = env
    db.conn.execute("INSERT INTO group_plugin_config VALUES (100,'group_alarm')"); db.conn.commit()
    db.alarm.add(7, datetime.now() - timedelta(days=1), '提醒', group_id=100)
    p = GroupAlarmPlugin.__new__(GroupAlarmPlugin)
    p.api, p.dbmanager = api, db
    p._handle_meta_due()
    assert db.conn.execute('SELECT fired FROM group_alarms').fetchone()[0] == 0
    api.call_api.assert_not_called()
    db.community.activate_group(100)
    p._handle_meta_due()
    assert db.conn.execute('SELECT fired FROM group_alarms').fetchone()[0] == 1
    assert api.call_api.call_args.args[1]['group_id'] == 100


def test_shared_backup_and_startup_do_not_notify_unapproved_default_group(env, monkeypatch):
    from plugins.backup import BackupPlugin
    from plugins.startup_changelog import StartupChangelogPlugin
    db, sent, api, run = env
    monkeypatch.setattr(config, 'DEFAULT_GROUP_ID', 100)
    monkeypatch.setattr(context, 'DEFAULT_GROUP_ID', 100)
    monkeypatch.setattr(context, 'startup_changelog_sent', False)
    monkeypatch.setattr(context, 'SYSTEM_PLUGINS', frozenset({'backup', 'startup_changelog'}))
    for cls in (BackupPlugin, StartupChangelogPlugin):
        p = cls.__new__(cls)
        p.api, p.dbmanager = api, db
        p.bot_event = Event({'post_type': 'meta_event', 'meta_event_type': 'heartbeat'})
        p.handle()
    api.send_msg.assert_not_called()
    assert context.startup_changelog_sent is False


def test_group_messages_cannot_use_review_as_management_backdoor(env):
    db, sent, api, run = env
    assert context.group_event_gate({'post_type': 'message', 'group_id': 100}) == frozenset()


def test_configuration_and_policy_validation(env, monkeypatch):
    from copy import deepcopy
    db, sent, api, run = env
    raw = deepcopy(config._RAW)
    for value in (0, -1, True, '1'):
        raw['community'] = {'max_groups': value}
        assert any('max_groups' in e for e in config.validate_config(raw))
    raw['community'] = {'max_groups': 1}
    for section in (False, [], {'require': 'true'}, {'default_pack': ''}):
        raw['group_review'] = section
        assert any('group_review' in e for e in config.validate_config(raw))
    raw['group_review'] = {'require': True, 'default_pack': '基础包'}
    assert not config.validate_config(raw)
    import plugins
    context.validate_deployment_policy()
    monkeypatch.setattr(context, 'SYSTEM_PLUGINS', frozenset({'menu', 'group_manager'}))
    with pytest.raises(SystemExit, match='group_review'):
        context.validate_deployment_policy()
    monkeypatch.setattr(context, 'SYSTEM_PLUGINS', frozenset({'menu', 'group_manager', 'group_review'}))
    monkeypatch.setattr(config, 'GROUP_REVIEW_DEFAULT_PACK', '不存在')
    with pytest.raises(SystemExit, match='default_pack'):
        context.validate_deployment_policy()


def test_seed_scope_is_single_group_and_preserves_old_settings(env):
    db, sent, api, run = env
    db.conn.execute("INSERT INTO group_plugin_config VALUES (100,'title')"); db.conn.commit()
    run(invite()); run(command('/审核 100 通过'))
    assert db.conn.execute("SELECT COUNT(*) FROM group_plugin_config WHERE group_id=100 AND plugin_name='title'").fetchone()[0] == 1
    assert db.conn.execute('SELECT COUNT(*) FROM group_plugin_config WHERE group_id=200').fetchone()[0] == 0
    assert not db.community.is_registered(42)
    assert '恢复生效' in contents(sent)


@pytest.mark.parametrize('message', ['/审核', '/审核 错误 通过', '/审核 100 随便', '/审核 100 通过 错误', '/审核 999 通过'])
def test_invalid_or_missing_request_never_approves(env, message):
    db, sent, api, run = env
    run(invite())
    run(command(message))
    api.call_api.assert_not_called()
    assert not db.community.is_group_active(100)


def test_auto_rejection_failure_stays_recoverable(env):
    db, sent, api, run = env
    db.community.ban('group', 100)
    api.call_api.return_value = {'status': 'failed', 'retcode': 100}
    run(invite())
    assert db.community.pending_requests()[0]['status'] == 'pending'
    api.call_api.return_value = {'status': 'ok', 'retcode': 0}
    run(command('/审核 100 拒绝'))
    assert not db.community.pending_requests()
    assert not db.community.is_group_active(100)


def test_exception_result_and_rejoin_require_new_approval(env):
    db, sent, api, run = env
    run(invite())
    api.call_api.side_effect = TimeoutError('simulated')
    run(command('/审核 100 通过'))
    assert db.community.pending_requests()[0]['status'] == 'uncertain'
    run(notice())
    api.call_api.side_effect = None
    run(command('/审核 100 通过'))
    assert db.community.is_group_active(100)
    assert api.call_api.call_count == 1
    run(notice('group_decrease'))
    run(invite(flag='again'))
    assert not db.community.is_group_active(100)
    run(command('/审核 100 通过'))
    assert db.community.is_group_active(100)


def test_parallel_scope_and_edition_invariance(env, monkeypatch):
    db, sent, api, run = env
    for gid in (100, 200):
        db.conn.execute("INSERT INTO group_plugin_config VALUES (?, 'group_alarm')", (gid,))
    db.conn.execute("INSERT INTO user_plugin_config VALUES (42, 'group_alarm', 1)")
    db.conn.commit()
    db.community.activate_group(100)
    for edition in ('private', 'community', 'arbitrary'):
        monkeypatch.setattr(config, 'EDITION', edition)
        assert context.effective_for_scope('group_alarm', group_id=100)
        assert not context.effective_for_scope('group_alarm', group_id=200)
        assert context.effective_for_scope('group_alarm', user_id=42)
    registered = {context.plugin_key(cls) for cls in context.plugin_registry}
    monkeypatch.setattr(context, 'ALLOWED_PLUGINS', frozenset(registered - {'checkin'}))
    with pytest.raises(SystemExit, match='default_pack'):
        context.validate_deployment_policy()


def test_scope_read_failure_fails_closed(env, monkeypatch):
    db, sent, api, run = env
    db.conn.execute('DROP TABLE group_registry'); db.conn.commit()
    assert not context.group_business_allowed(100)
    assert context.group_event_gate({'group_id': 100}) == frozenset({'group_review'})
