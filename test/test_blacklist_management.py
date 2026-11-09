import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

from core import config, context, base, command_rate_limit
from core.database_manager import DbManager
from core.message_output import MessageOutput
from core.plugin_dispatch import Operation
from plugins.blacklist import BlacklistPlugin


@pytest.fixture
def management(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'blacklist.db')
    monkeypatch.setattr(config, 'BLACKLIST_ENABLED', True)
    monkeypatch.setattr(config, 'SUPER_USER', [99])
    monkeypatch.setattr(config, 'BOT_QQ', '999')
    monkeypatch.setattr(base, 'SUPER_USER', [99])
    monkeypatch.setattr(config, 'REGISTER_REQUIRE', False)
    monkeypatch.setattr(config, 'GROUP_REVIEW_REQUIRE', False)
    monkeypatch.setattr(config, 'COMMAND_LIMIT_PER_MINUTE', 20)
    monkeypatch.setattr(command_rate_limit, 'limiter', command_rate_limit.CommandRateLimiter())
    monkeypatch.setattr(context, 'ALLOWED_PLUGINS', None)
    monkeypatch.setattr(context, 'SYSTEM_PLUGINS', frozenset({'blacklist', 'probe'}))
    monkeypatch.setattr(context, 'is_group_recording', lambda gid: False)
    monkeypatch.setattr(base, 'ApiWrapper', Mock())
    db = DbManager()
    hits = []

    class Probe(base.CommandPlugin):
        __module__ = 'plugins.probe'
        COMMANDS = '/测试'

        def handle(self):
            hits.append(self.operation.blacklist_snapshot)

    monkeypatch.setattr(context, 'plugin_registry', [BlacklistPlugin, Probe])
    output = []
    source = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'plugin_pool')
    ns = dict(runtime_context=context, Operation=Operation, MessageOutput=MessageOutput,
              send_request=lambda req: output.append(req.content) or 1, logger=Mock())
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), ns)

    def raw_run(raw):
        output.clear()
        event_type = 'notice' if raw.get('post_type') == 'notice' else 'message'
        ns['plugin_pool'](raw, event_type)
        return '\n'.join(str(item) for item in output)

    def run(msg, uid=99, gid=None):
        raw = dict(post_type='message', user_id=uid, message_id=1,
                   message=[{'type': 'text', 'data': {'text': msg}}], message_type='private')
        if gid is not None:
            raw.update(group_id=gid, message_type='group')
        return raw_run(raw)

    run.raw = raw_run
    yield run, db, hits, Probe
    db.conn.close()


def test_commands_add_query_duplicate_remove(management):
    run, db, hits, cls = management
    assert '已加入' in run('/黑名单 添加 用户 42 原因有 空格')
    row = db.community.get_ban('user', 42)
    assert row[2] == '原因有 空格' and row[4] == 99
    assert '保留原记录' in run('/黑名单 添加 用户 42 新原因')
    assert db.community.get_ban('user', 42) == row
    assert '原因有 空格' in run('/黑名单 查询 用户 42')
    run('/黑名单 添加 群 42')
    assert '已解除' in run('/黑名单 解除 用户 42')
    assert db.community.is_banned('group', 42)
    assert '未在' in run('/黑名单 解除 用户 42')


def test_commands_permissions_pagination_and_invalid(management):
    run, db, hits, cls = management
    assert run('/黑名单 添加 用户 42', uid=7) == ''
    assert run('/黑名单 列表', uid=7) == ''
    assert not db.community.is_banned('user', 42)
    for uid in range(1, 12):
        db.community.ban('user', uid, 'legacy')
    out = run('/黑名单 列表')
    assert '下一页' in out and '未知（旧记录）' in out
    assert '下一页' not in run('/黑名单 列表 2')
    assert '无记录' in run('/黑名单 列表 3')
    for msg in ('/黑名单 列表 0', '/黑名单 添加 用户 -1', '/黑名单 添加 账号 42',
                '/黑名单 查询 用户 42 多余', '/黑名单 添加 用户 ' + '9' * 100):
        assert '用法' in run(msg)


def test_protection_accounts_and_blocked_group(management):
    run, db, hits, cls = management
    for uid in (99, 999):
        assert '不能拉黑' in run(f'/黑名单 添加 用户 {uid}')
        assert not db.community.is_banned('user', uid)
    db.community.ban('user', 99)
    assert '受保护' in run('/黑名单 查询 用户 99')
    run('/测试'); assert len(hits) == 1
    db.community.ban('group', 100)
    assert run('/测试', gid=100) == '' and len(hits) == 1
    assert run('/黑名单 解除 群 100', gid=100) == ''
    assert '已解除' in run('/黑名单 解除 群 100')
    assert db.community.is_banned('user', 99)


def test_commands_write_failure_not_success(management):
    run, db, hits, cls = management
    db.conn.execute("CREATE TRIGGER fail_ban BEFORE INSERT ON blacklist BEGIN SELECT RAISE(ABORT, 'test'); END")
    db.conn.commit()
    out = run('/黑名单 添加 用户 42')
    assert '失败' in out and '已加入' not in out
    assert not db.community.is_banned('user', 42)
