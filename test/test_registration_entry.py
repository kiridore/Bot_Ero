"""公开模板 + 真实事件入口，子进程隔离所有配置、注册表及数据。"""
import ast
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _exercise(case):
    from core import config, context, base, api, text_pack
    from core.database_manager import DbManager
    from core.db.plugin_settings import set_user_plugins
    from core.plugin_dispatch import Operation
    from core.message_output import MessageOutput
    from core.logger import logger
    # 必须先确认路径，再导入可能初始化数据库的插件。
    for path in (config.DB_PATH, config.MESSAGE_LOG_DB_PATH):
        assert Path(path).resolve().is_relative_to(config.CONFIG_PATH.parent)
    import plugins
    from plugins.menu import MenuPlugin
    from plugins.register import RegisterPlugin, _SESSIONS
    from plugins.auto_friend import AutoFriendPlugin
    from plugins.welcome import WelcomePlugin
    from plugins.checkin import CheckinPlugin
    context.validate_deployment_policy()
    context.plugin_registry = [AutoFriendPlugin, WelcomePlugin, RegisterPlugin, MenuPlugin, CheckinPlugin]
    source = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
    functions = [n for n in source.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('plugin_pool', 'resolve_event_type')]
    sent = Mock(return_value=1)
    namespace = dict(runtime_context=context, Operation=Operation, MessageOutput=MessageOutput,
                     send_request=sent, logger=logger)
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'main.py', 'exec'), namespace)
    remote = Mock()
    remote.send_private_msg.return_value = remote.send_forward_msg.return_value = 1
    uid = 987654321
    assert not context.is_super_user(uid)
    db = DbManager()

    def deliver(raw):
        raw = dict(time=1700000000, self_id=int(config.BOT_QQ), user_id=uid, **raw)
        namespace['plugin_pool'](raw, namespace['resolve_event_type'](raw))

    def message(command, **extra):
        deliver(dict(post_type='message', message_type='private', sub_type='friend', message_id=7,
                     message=[{'type': 'text', 'data': {'text': command}}], **extra))

    def unchanged():
        assert not db.community.is_registered(uid)
        assert not db.conn.execute('SELECT * FROM user_plugin_config').fetchall()
        assert uid not in _SESSIONS

    with patch.object(base, 'ApiWrapper', return_value=remote), patch.object(api, 'ApiWrapper', return_value=remote), \
            patch.object(CheckinPlugin, 'handle') as checkin, patch.object(RegisterPlugin, '_pause'):
        if case == 'menu_entry':
            for command in ('/菜单', '/菜單'):
                remote.reset_mock()
                message(command)
                remote.send_forward_msg.assert_called_once()
                out = str(remote.send_forward_msg.call_args)
                assert '/注册' in out and '/菜单' in out and '/打卡' not in out
                remote.send_private_msg.assert_not_called()
                unchanged()
            assert context.plugin_key(MenuPlugin) in context.REGISTRATION_ALLOWLIST
        elif case == 'boundary':
            set_user_plugins(db.conn, uid, ['checkin'], True)
            message('/打卡'); message('/打卡')
            checkin.assert_not_called()
            remote.send_private_msg.assert_called_once()
            # 允许集合不能突破部署禁止。
            context.ALLOWED_PLUGINS = context.ALLOWED_PLUGINS - {'menu'}
            # 正常配置禁止与system冲突；这里直接模拟运行状态以验证多层检查。
            context.SYSTEM_PLUGINS = context.SYSTEM_PLUGINS - {'menu'}
            remote.reset_mock(); message('/菜单')
            remote.send_forward_msg.assert_not_called()
        elif case == 'boundary_compatibility':
            set_user_plugins(db.conn, uid, ['checkin'], True)
            db.community.register_user(uid)
            message('/打卡'); assert checkin.call_count == 1
            db.conn.execute('DELETE FROM user_accounts'); db.conn.commit()
            config.REGISTER_REQUIRE = False
            message('/打卡'); assert checkin.call_count == 2
            config.REGISTER_REQUIRE = True
            config.SUPER_USER = [uid]
            message('/打卡'); assert checkin.call_count == 3
            config.SUPER_USER = []
            db.community.activate_group(100)
            db.conn.execute("INSERT INTO group_plugin_config VALUES (100, 'checkin')"); db.conn.commit()
            message('/打卡', group_id=100); assert checkin.call_count == 4
        elif case == 'welcome_flow':
            assert {'welcome', 'auto_friend', 'register'} <= context.SYSTEM_PLUGINS
            assert 'welcome' in context.ALLOWED_PLUGINS
            deliver(dict(post_type='request', request_type='friend', comment='', flag='test-flag', via='test'))
            remote.set_friend_add_request.assert_called_once_with('test-flag')
            remote.send_private_msg.assert_not_called()
            remote.send_forward_msg.assert_not_called()
            unchanged()
            deliver(dict(post_type='notice', notice_type='friend_add'))
            remote.set_friend_add_request.assert_called_once()
            remote.send_private_msg.assert_called_once()
            assert remote.send_private_msg.call_args.args[0]['data']['text'] == text_pack.get_text(
                'welcome.friend_add', WelcomePlugin._DEFAULT_TEXT)
            unchanged()
            remote.reset_mock(); message('/注册')
            remote.send_forward_msg.assert_called_once()
            assert uid in _SESSIONS and not db.community.is_registered(uid)
            assert not db.conn.execute('SELECT * FROM user_plugin_config').fetchall()
        elif case == 'welcome_flow_disabled':
            context.ALLOWED_PLUGINS = context.ALLOWED_PLUGINS - {'welcome'}
            context.SYSTEM_PLUGINS = context.SYSTEM_PLUGINS - {'welcome'}
            deliver(dict(post_type='notice', notice_type='friend_add'))
            remote.send_private_msg.assert_not_called()
            unchanged()
        else:
            raise AssertionError(case)
        assert not sent.call_args_list  # 此范围无奖励或其他通知输出
    db.conn.close()


@pytest.mark.parametrize('case', ['menu_entry', 'boundary', 'boundary_compatibility', 'welcome_flow', 'welcome_flow_disabled'])
def test_registration_entry(tmp_path, case):
    from test.scripts._env import write_config
    data = yaml.safe_load((ROOT / 'config.public.example.yaml').read_text(encoding='utf-8'))
    data['paths'] = {key: str(tmp_path / value) for key, value in data['paths'].items()}
    data['bot']['python_data_path'] = str(tmp_path / 'server_data')
    data['bot']['llonebot_data_path'] = str(tmp_path / 'onebot_data')
    data['bot']['feature_packs_file'] = str(ROOT / 'feature_packs_public.yaml')
    data['bot']['text_pack'] = str(ROOT / 'text_packs/community.yaml')
    data['register']['eula_file'] = str(ROOT / 'docs/eula/v1.md')
    data['thumbs']['cache_dir'] = str(tmp_path / 'thumb_cache')
    data['onebot'] = {'http_url': '', 'token': ''}
    data['timeline'] = {'url': '', 'token': ''}
    write_config(str(tmp_path), **data)
    env = dict(os.environ, BOTERO_CONFIG=str(tmp_path / 'config.yaml'), PYTHONIOENCODING='utf-8')
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), case], cwd=ROOT,
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    _exercise(sys.argv[1])
