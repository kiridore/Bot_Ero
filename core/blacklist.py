"""黑名单写入与操作获准的协调边界；业务执行不持有此锁。"""
from dataclasses import dataclass
from threading import RLock


coordination_lock = RLock()


@dataclass(frozen=True)
class BlacklistSnapshot:
    users: frozenset[int] = frozenset()
    groups: frozenset[int] = frozenset()

    def blocks(self, *, user_id=None, group_id=None):
        return ((user_id is not None and int(user_id) in self.users)
                or (group_id is not None and int(group_id) in self.groups))


@dataclass(frozen=True)
class EventAccess:
    snapshot: BlacklistSnapshot | None = None
    only_plugins: frozenset[str] | None = None
    cleanup_only: bool = False


def response_result(response):
    if not isinstance(response, dict):
        return 'unknown'
    if response.get('status') == 'ok' and type(response.get('retcode')) is int and response['retcode'] == 0:
        return 'ok'
    if response.get('status') == 'failed' and type(response.get('retcode')) is int and response['retcode'] != 0:
        return 'failed'
    return 'unknown'


def is_bot_lifecycle(raw):
    return (raw.get('post_type') == 'notice'
            and raw.get('notice_type') in ('group_increase', 'group_decrease')
            and type(raw.get('user_id')) is int and type(raw.get('self_id')) is int
            and type(raw.get('group_id')) is int and raw['group_id'] > 0
            and raw['user_id'] == raw['self_id'])


def event_access(raw):
    """拒绝返回None；例外仅限定具体插件，不能让其他业务借notice/request绕过。"""
    from core import config
    if raw.get('post_type') not in ('message', 'notice', 'request'):
        return EventAccess()
    with coordination_lock:
        snapshot = capture(enabled=config.BLACKLIST_ENABLED, protected_users=protected_accounts())
        if not snapshot.blocks(user_id=raw.get('user_id'), group_id=raw.get('group_id')):
            return EventAccess(snapshot)
        if raw.get('post_type') == 'notice':
            if (raw.get('notice_type') == 'group_recall'
                    and type(raw.get('group_id')) is int and type(raw.get('user_id')) is int
                    and type(raw.get('message_id')) is int):
                return EventAccess(snapshot, frozenset({'checkin_recall'}), True)
            if is_bot_lifecycle(raw):
                return EventAccess(snapshot, frozenset({'blacklist'}))
        if raw.get('post_type') == 'request' and (raw.get('request_type') == 'friend' or (
                raw.get('request_type') == 'group' and raw.get('sub_type') == 'invite')):
            return EventAccess(snapshot, frozenset({'blacklist'}))
        return None


def protected_accounts():
    from core import config
    return frozenset(int(uid) for uid in (*config.SUPER_USER, config.BOT_QQ))


def capture(*, enabled: bool, protected_users=()) -> BlacklistSnapshot:
    """一次新操作的不可变封禁事实；读取失败向调用方传播，不能伪装成空表。

    必须在同一锁内新建连接和读取，避免复用其他事务的旧读视图。
    仅提供事实；新操作必须通过admit在锁内完成判断，不直接用capture替代准入。
    """
    if not enabled:
        return BlacklistSnapshot()
    import sqlite3
    from pathlib import Path
    from core import config
    with coordination_lock:
        conn = sqlite3.connect(Path(config.DB_PATH).resolve().as_uri() + '?mode=ro', uri=True)
        try:
            rows = conn.execute('SELECT scope, target_id FROM blacklist').fetchall()
        finally:
            conn.close()
        protected = {int(uid) for uid in protected_users}
        return BlacklistSnapshot(
            frozenset(int(uid) for scope, uid in rows if scope == 'user' and int(uid) not in protected),
            frozenset(int(uid) for scope, uid in rows if scope == 'group'),
        )


def operation_snapshot(operation):
    """跨账号业务复用已获准快照；启用限制却缺少快照时不得退回到全部允许。"""
    from core import config
    if not config.BLACKLIST_ENABLED:
        return BlacklistSnapshot()
    snapshot = getattr(operation, 'blacklist_snapshot', None)
    if not isinstance(snapshot, BlacklistSnapshot):
        raise RuntimeError('操作缺少黑名单准入快照')
    return snapshot


def admit_task(plugin, task_id, *, user_id=None, group_id=None):
    """每条后台记录开始前单独获准；拒绝/读取失败都保留原任务，不占用业务锁。"""
    from core import config
    from core.logger import logger
    try:
        snapshot = admit(enabled=config.BLACKLIST_ENABLED, protected_users=protected_accounts(),
                         user_id=user_id, group_id=group_id)
    except Exception:
        logger.exception('黑名单读取失败，保留任务 %s/%s（群 %s 用户 %s）',
                         plugin, task_id, group_id, user_id)
        return None
    if snapshot is None:
        logger.info('黑名单限制，保留任务 %s/%s（群 %s 用户 %s）',
                    plugin, task_id, group_id, user_id)
    return snapshot


def admit(*, enabled: bool, protected_users=(), user_id=None, group_id=None):
    """锁内获准，返回操作快照；None=拒绝。错误仍传播，业务调用方必须拒绝执行。"""
    with coordination_lock:
        snapshot = capture(enabled=enabled, protected_users=protected_users)
        return None if snapshot.blocks(user_id=user_id, group_id=group_id) else snapshot
