import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

from core import config, context
from core.base import Plugin, CommandPlugin
from core.event import Event
from core.message_output import MessageOutput
from core.plugin_dispatch import Operation
from core import command_rate_limit as rate


@pytest.fixture
def entry(monkeypatch):
    now = [0.0]
    limiter = rate.CommandRateLimiter(lambda: now[0])
    monkeypatch.setattr(rate, 'limiter', limiter)
    monkeypatch.setattr(config, 'COMMAND_LIMIT_PER_MINUTE', 20)
    monkeypatch.setattr(config, 'REGISTER_REQUIRE', False)
    monkeypatch.setattr(config, 'GROUP_REVIEW_REQUIRE', False)
    monkeypatch.setattr(context, 'ALLOWED_PLUGINS', None)
    monkeypatch.setattr(context, 'is_group_recording', lambda gid: False)
    calls = []
    output = []
    enabled = {'a': True, 'b': True, 'observer': True}

    class First(CommandPlugin):
        __module__ = 'plugins.a'
        COMMANDS = ('/测试', '.r', '/批量')

        def __init__(self, raw):
            self.bot_event = Event(raw)
            self.operation = raw['_operation']

        def match(self, event_type):
            result = super().match(event_type)
            calls.append(('match', 'a', result))
            return result

        def handle(self):
            calls.append(('handle', 'a', self.args))
            if self.cmd == '/批量':
                for _ in range(10):
                    calls.append(('internal',))

    class Second(First):
        __module__ = 'plugins.b'

        def match(self, event_type):
            # 断言前一个handle没有被预匹配方案延后。
            result = CommandPlugin.match(self, event_type)
            if result and any(c[:2] == ('handle', 'a') for c in calls):
                calls.append(('order',))
            return result

        def handle(self):
            calls.append(('handle', 'b', self.args))

    class Observer(First):
        __module__ = 'plugins.observer'

        def match(self, event_type):
            return True

        def is_command(self):
            return False

        def handle(self):
            calls.append(('observe',))

    monkeypatch.setattr(context, 'plugin_registry', [First, Second, Observer])
    monkeypatch.setattr(context, 'plugin_settings_snapshot', lambda *a: dict(enabled))
    source = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    fn = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'plugin_pool')
    sender = Mock(side_effect=lambda req: output.append(req) or 1)
    scope = dict(runtime_context=context, Operation=Operation, MessageOutput=MessageOutput,
                 send_request=sender, logger=Mock())
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'main.py', 'exec'), scope)

    def run(command='/测试', uid=123, gid=None, post_type='message', event_type='message'):
        raw = dict(post_type=post_type, user_id=uid, message_id=1, message_type='private',
                   message=[{'type': 'text', 'data': {'text': command}}])
        if gid is not None:
            raw.update(group_id=gid, message_type='group')
        scope['plugin_pool'](raw, event_type)

    return run, calls, output, enabled, now, limiter, First, sender


def test_counting_cross_scope_and_multi_plugin(entry):
    run, calls, output, enabled, now, limiter, first, sender = entry
    for i in range(20):
        run('.r', gid=[None, 10, 20][i % 3])
    assert len(limiter._windows[123]) == 20
    assert len([c for c in calls if c[0] == 'handle']) == 40
    assert ('order',) in calls
    calls.clear(); run()
    assert not any(c[0] == 'handle' for c in calls)
    assert ('observe',) in calls
    run(uid=124)
    assert len(limiter._windows[124]) == 1


def test_counting_ignored_and_batch(entry):
    run, calls, output, enabled, now, limiter, first, sender = entry
    run('普通聊天'); run('/不存在')
    enabled['a'] = enabled['b'] = False
    run(); enabled['a'] = enabled['b'] = True
    run(post_type='request'); run(post_type='notice', event_type='notice'); run(post_type='meta_event', event_type='meta')
    assert not limiter._windows
    calls.clear(); run('/批量')
    assert len(limiter._windows[123]) == 1
    assert calls.count(('internal',)) == 10


def test_rejection_failure_still_consumes_and_admin_not_exempt(entry, monkeypatch):
    run, calls, output, enabled, now, limiter, first, sender = entry
    monkeypatch.setattr(config, 'SUPER_USER', [123])
    monkeypatch.setattr(config, 'COMMAND_LIMIT_PER_MINUTE', 1)
    def fail(self):
        calls.append(('failed',))
        raise ValueError('test failure')
    monkeypatch.setattr(first, 'handle', fail)
    run(); assert len(limiter._windows[123]) == 1
    calls.clear(); run()
    assert not any(c[0] in ('failed', 'handle', 'internal') for c in calls)


def test_reminder_destination_interval_rounding_and_failure(entry, monkeypatch):
    run, calls, output, enabled, now, limiter, first, sender = entry
    monkeypatch.setattr(config, 'COMMAND_LIMIT_PER_MINUTE', 1)
    run(); now[0] = 0.1; run(gid=10)
    assert output[-1].target == ('group', 10)
    assert output[-1].content[0]['type'] == 'at'
    assert '60秒后' in str(output[-1].content)
    run(gid=20); run(); assert len(output) == 1
    now[0] = 10.1; run()
    assert output[-1].target == ('private', 123)
    assert len(output[-1].content) == 1
    assert '50秒后' in str(output[-1].content)
    sender.side_effect = RuntimeError('send failed')
    now[0] = 20.1; run(); n = sender.call_count
    run(); assert sender.call_count == n
    assert len(limiter._windows[123]) == 1


def test_rejection_disabled_preserves_match_handle_order(entry, monkeypatch):
    run, calls, output, enabled, now, limiter, first, sender = entry
    monkeypatch.setattr(config, 'COMMAND_LIMIT_PER_MINUTE', 0)
    for _ in range(22):
        run()
    assert not limiter._windows and not output
    assert len([c for c in calls if c[0] == 'handle']) == 44


def test_counting_inventory_covers_every_registered_plugin():
    import plugins
    from core.base import Plugin, CommandPlugin
    ordinary = {'AutoFriendPlugin', 'WelcomePlugin', 'CheckinRecallPlugin', 'MessageLoggerPlugin',
                'ForumNotifyPlugin', 'StartupChangelogPlugin', 'WeeklyReportPlugin',
                'ShopWeeklyRotationPlugin', 'WeeklyQuestResetPlugin', 'ActivityTimerPlugin'}
    custom = {'ActivityPlugin', 'AtAllReplyPlugin', 'BackupPlugin', 'DicePlugin', 'FfNewsPlugin',
              'GroupAlarmPlugin', 'GroupEssencePlugin', 'ImmortalLotteryPlugin', 'MonitorPlugin',
              'RecallMessagePlugin', 'ShopManualRefreshPlugin', 'TrpgCharPlugin', 'TrpgPlugin', 'UpdatePlugin'}
    mixed = {'WhoIsSpyPlugin', 'TrpgSessionPlugin'}
    seen = set()
    for cls in context.plugin_registry:
        name = cls.__name__
        if issubclass(cls, CommandPlugin):
            assert cls.IS_COMMAND
        elif name in custom:
            assert cls.IS_COMMAND
            seen.add(name)
        elif name in mixed:
            assert cls.is_command is not Plugin.is_command
            seen.add(name)
        else:
            assert name in ordinary, f'新增插件必须先明确指令分类：{name}'
            assert not cls.IS_COMMAND
            seen.add(name)
    assert seen == ordinary | custom | mixed


def test_counting_real_non_slash_commands():
    from plugins.dice import DicePlugin
    from plugins.immortal_lottery import ImmortalLotteryPlugin
    for cls, msg in [(DicePlugin, '.r1d6'), (ImmortalLotteryPlugin, '下注 1234')]:
        plugin = cls.__new__(cls)
        plugin.bot_event = Event({'post_type': 'message', 'user_id': 123,
                                 'message': [{'type': 'text', 'data': {'text': msg}}]})
        assert plugin.match('message')
        assert plugin.is_command()


def test_counting_real_mixed_classification():
    from plugins.who_is_spy import WhoIsSpyPlugin
    from plugins.trpg_session import TrpgSessionPlugin
    spy = WhoIsSpyPlugin.__new__(WhoIsSpyPlugin)
    spy._mode = 'game_input'; assert not spy.is_command()
    spy._mode = 'command'; assert spy.is_command()
    session = TrpgSessionPlugin.__new__(TrpgSessionPlugin)
    for msg, expected in [('普通记录', False), ('.dm', True), ('/跑团记录 开始', True), ('.ob', True)]:
        session.bot_event = Event({'message': [{'type': 'text', 'data': {'text': msg}}]})
        assert session.is_command() == expected
