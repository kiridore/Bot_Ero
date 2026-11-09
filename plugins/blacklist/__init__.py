"""仅超级用户管理；启用限制后的群封禁由统一入口先行拦截。"""
import sqlite3

from core.base import CommandPlugin
from core import config
from core.blacklist import protected_accounts, response_result
from core.cq import text
from core.logger import logger
from core.utils import register_plugin


@register_plugin
class BlacklistPlugin(CommandPlugin):
    name = 'blacklist'
    description = '超级用户管理用户和群黑名单。'
    COMMANDS = '/黑名单'
    USAGE = ('用法：/黑名单 添加 用户|群 <号码> [原因]；'
             '/黑名单 解除|查询 用户|群 <号码>；/黑名单 列表 [页码]')

    def match(self, event_type='message'):
        if getattr(self.operation, 'blacklist_special', False):
            return self.bot_event.raw.get('post_type') in ('request', 'notice')
        return self.super_user() and super().match(event_type)

    @staticmethod
    def _number(value):
        if len(value) > 19 or not value.isdecimal():
            return None
        number = int(value)
        return number if 0 < number <= 9223372036854775807 else None

    @staticmethod
    def _format(row):
        scope, target, reason, created, operator = row
        protected = scope == 'user' and target in protected_accounts()
        return (f"{'用户' if scope == 'user' else '群'} {target}"
                f"{'（当前为受保护账号）' if protected else ''}\n"
                f"原因：{reason or '未填写'}\n添加时间：{created}\n"
                f"操作者：{operator if operator is not None else '未知（旧记录）'}")

    def handle(self):
        if getattr(self.operation, 'blacklist_special', False):
            self._restricted_event()
            return
        try:
            reply = self._command()
        except sqlite3.Error:
            logger.exception('黑名单管理数据库操作失败（操作者 %s）', self.bot_event.user_id)
            reply = '黑名单操作失败，请检查日志后重试；本次未确认成功。'
        self.submit_message(text(reply))

    def _restricted_event(self):
        raw = self.bot_event.raw
        gid, uid = raw.get('group_id'), raw.get('user_id')
        if raw.get('post_type') == 'notice':
            if type(gid) is not int or gid <= 0:
                return
            if raw.get('notice_type') == 'group_decrease':
                self.dbmanager.community.mark_group_removed(gid)
            elif raw.get('notice_type') == 'group_increase':
                self.dbmanager.community.record_group_join(gid, raw.get('operator_id') or uid)
            return  # 只维护生命周期事实，不发群欢迎或激活业务
        flag = raw.get('flag')
        if type(uid) is not int or uid <= 0 or not isinstance(flag, str) or not flag:
            logger.warning('封禁请求缺少有效账号或凭证，不调用拒绝接口')
            return
        if raw.get('request_type') == 'friend':
            try:
                result = response_result(self.api.call_api('set_friend_add_request', {
                    'flag': flag, 'approve': False, 'remark': '',
                }))
            except Exception:
                logger.exception('封禁账号 %s 的好友拒绝接口异常，结果未知', uid)
                return
            logger.info('封禁账号 %s 的好友拒绝结果：%s；不自动重试', uid, result)
            return
        if type(gid) is not int or gid <= 0 or raw.get('sub_type') != 'invite':
            return
        db = self.dbmanager.community
        db.upsert_request(gid, uid, flag, 'invite')
        row = self.dbmanager.conn.execute('SELECT * FROM group_requests WHERE flag = ?', (flag,)).fetchone()
        if row['status'] != 'pending' or row['remote_state'] != 'none':
            logger.info('封禁群申请 %s 已有处理记录，重复事件不自动重发拒绝', row['id'])
            return
        try:
            db.reserve_review(row['id'], False, config.COMMUNITY_MAX_GROUPS)
        except ValueError:
            logger.info('封禁群申请 %s 已由其他操作处理，不重复拒绝', row['id'])
            return
        try:
            result = response_result(self.api.call_api('set_group_add_request', {
                'flag': flag, 'sub_type': 'invite', 'approve': False, 'reason': '',
            }))
        except Exception:
            logger.exception('封禁群申请 %s 拒绝接口异常，保留未知结果', row['id'])
            result = 'unknown'
        db.record_review_result(row['id'], result)
        if result == 'ok':
            db.complete_review(row['id'])
        logger.info('封禁群申请 %s 拒绝结果：%s；不自动重试', row['id'], result)

    def _command(self):
        args = self.args
        db = self.dbmanager.community
        if args and args[0] == '列表' and len(args) <= 2:
            page = self._number(args[1]) if len(args) == 2 else 1
            if page is None or page > 922337203685477580:
                return self.USAGE
            rows = db.list_bans(page)
            if not rows:
                return f'黑名单第{page}页：无记录。'
            lines = [f'黑名单第{page}页（每页10条）']
            lines.extend(self._format(row) for row in rows[:10])
            if len(rows) > 10:
                lines.append(f'下一页：/黑名单 列表 {page + 1}')
            return '\n\n'.join(lines)
        if len(args) < 3 or args[0] not in ('添加', '解除', '查询') or args[1] not in ('用户', '群'):
            return self.USAGE
        action, label = args[:2]
        target = self._number(args[2])
        if target is None or (action != '添加' and len(args) != 3):
            return self.USAGE
        scope = 'user' if label == '用户' else 'group'
        if action == '添加':
            if scope == 'user' and target in protected_accounts():
                return '不能拉黑机器人自身或当前超级用户。'
            reason = ' '.join(args[3:]) or None
            added = db.ban(scope, target, reason, operator_id=self.bot_event.user_id)
            return f"{label}{target}{'已加入黑名单' if added else '已在黑名单中，保留原记录'}。"
        if action == '解除':
            removed = db.unban(scope, target)
            return f"{label}{target}{'已解除黑名单限制' if removed else '未在黑名单中'}。"
        row = db.get_ban(scope, target)
        return self._format(row) if row is not None else f'{label}{target}未在黑名单中。'
