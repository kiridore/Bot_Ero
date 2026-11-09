"""只读查询：同一份目标状态用于插件行和功能包统计，不参与修改设置。"""
import sqlite3
from pathlib import Path

from core import config, context
from core.db.community import CommunityManager
from core.db.plugin_settings import enabled_plugins
from core.logger import logger


def query_text(scope, target, packs, show_packs=False):
    label = '私聊公共默认' if scope == 'defaults' else f'用户{target}的私聊' if scope == 'user' else f'群{target}'
    lines = [label + ('功能包状态：' if show_packs else '插件状态：')]
    try:
        conn = sqlite3.connect(Path(config.DB_PATH).resolve().as_uri() + '?mode=ro', uri=True)
        try:
            conn.execute('BEGIN')  # 一个查询内的设置、来源和准入状态保持一致
            settings = enabled_plugins(conn, group_id=target if scope == 'group' else None,
                                       user_id=target if scope == 'user' else None)
            overrides = dict(conn.execute(
                'SELECT plugin_name, enabled FROM user_plugin_config WHERE user_id = ?',
                (str(target),))) if scope == 'user' else {}
            community = CommunityManager(conn)
            restriction = ''
            if scope == 'group' and config.GROUP_REVIEW_REQUIRE and not community.is_group_active(target):
                restriction = '群未批准'
            if (scope == 'user' and config.REGISTER_REQUIRE and not context.is_super_user(target)
                    and not community.is_registered(target)):
                restriction = '账号未注册'
        finally:
            conn.close()
    except Exception:
        logger.exception('读取插件查询状态失败 scope=%s target=%s', scope, target)
        return '\n'.join(lines + ['无法确认当前状态，请检查日志后重试；本次未修改设置。'])

    keys = sorted({context.plugin_key(cls) for cls in context.plugin_registry})
    states = {}
    for key in keys:
        system = key in context.SYSTEM_PLUGINS
        saved = system or bool(settings.get(key, False))
        reason = ''
        if not context.plugin_allowed(key):
            reason = '部署未开放'
        elif restriction == '群未批准':
            reason = restriction  # 群消息全部限制，生命周期例外不代表命令可用
        elif restriction == '账号未注册' and key not in context.REGISTRATION_ALLOWLIST:
            reason = restriction
        states[key] = saved and not reason
        if not show_packs:
            origin = '系统插件' if system else ('单独设置' if key in overrides else '沿用默认') if scope == 'user' else ''
            if reason:
                detail = reason + ('；已保存开启设置' if saved and not system else '')
                if origin:
                    detail += '；' + origin
                lines.append(f'🚫 {key}（{detail}）')
            else:
                icon = '🔒' if system else '✅' if saved else '❌'
                lines.append(f'{icon} {key}' + (f'（{origin}）' if origin else ''))
    if show_packs:
        for name, pack in packs.items():
            members = set(pack['plugins'])
            excluded = {key for key in members if not context.plugin_allowed(key)}
            counted = members - excluded - context.SYSTEM_PLUGINS
            total = len(counted)
            on = sum(states.get(key, False) for key in counted)
            if not total:
                icon = '🚫' if excluded or restriction else '🔒'
                detail = '无可计数业务成员'
                if members and members <= context.SYSTEM_PLUGINS and not excluded:
                    detail += '；仅系统插件'
            else:
                icon = '❌' if not on else '✅' if on == total else '⚡'
                detail = '默认开启' if scope == 'defaults' else '实际可用'
            if excluded:
                detail += f'；部署未开放{len(excluded)}项'
            if restriction:
                detail += '；' + restriction
            lines.append(f'{icon} {name} ({on}/{total})（{detail}）')
        lines.append('系统插件不参与功能包计数，仍受部署和准入规则限制。')
    if scope == 'defaults':
        lines.append('没有该插件单独设置的账号继承这里的设置；这不是某个账号的实际可用状态。')
    elif scope == 'user':
        lines.append('修改此账号请指定 用户 <账号>；私聊无目标开启/关闭仍修改私聊公共默认，影响继承账号。')
    lines.append('可用仅指部署、准入与插件开关允许，不代表所有子指令权限或业务条件均满足。')
    return '\n'.join(lines)
