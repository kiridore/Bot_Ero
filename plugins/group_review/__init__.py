"""邀请、机器人自身进退群及超级用户审批。网络调用不持有数据库事务。"""
from threading import RLock

from core import config, context
from core.base import CommandPlugin
from core.cq import text
from core.feature_packs import FEATURE_PACKS
from core.logger import logger
from core.text_pack import get_text
from core.utils import register_plugin

_review_lock = RLock()
_STATUS_TEXT = {'pending': '待审', 'processing': '正在处理或需恢复', 'uncertain': '结果待核实'}
_REMOTE_TEXT = {'none': '尚未调用', 'ok': '已确认成功', 'failed': '已确认失败', 'unknown': '结果未知'}


def response_result(response):
    if not isinstance(response, dict):
        return 'unknown'
    if response.get('status') == 'ok' and type(response.get('retcode')) is int and response['retcode'] == 0:
        return 'ok'
    if response.get('status') == 'failed' and type(response.get('retcode')) is int and response['retcode'] != 0:
        return 'failed'
    return 'unknown'


@register_plugin
class GroupReviewPlugin(CommandPlugin):
    name = 'group_review'
    description = '群邀请和入群审核，仅超级用户审批'
    COMMANDS = ('/待审', '/审核')

    def match(self, event_type='message'):
        if not config.GROUP_REVIEW_REQUIRE:
            return False
        raw = self.bot_event.raw
        if raw.get('post_type') == 'request':
            return raw.get('request_type') == 'group' and raw.get('sub_type') == 'invite'
        if raw.get('post_type') == 'notice':
            return (raw.get('notice_type') in ('group_increase', 'group_decrease')
                    and type(raw.get('user_id')) is int and type(raw.get('self_id')) is int
                    and raw['user_id'] == raw['self_id'])
        return super().match(event_type)

    def _notify_admins(self, message):
        for uid in config.SUPER_USER:
            self.submit_message(text(message), target=('private', uid))

    def _row(self, request_id):
        return self.dbmanager.conn.execute('SELECT * FROM group_requests WHERE id = ?', (request_id,)).fetchone()

    def _remote(self, row, approve, reason=''):
        try:
            result = response_result(self.api.call_api('set_group_add_request', {
                'flag': row['flag'], 'sub_type': 'invite', 'approve': approve, 'reason': reason,
            }))
        except Exception:
            logger.exception('申请 %s 审批接口异常，结果未知', row['id'])
            result = 'unknown'
        self.dbmanager.community.record_review_result(row['id'], result)
        return result

    def handle(self):
        raw = self.bot_event.raw
        with _review_lock:
            if raw.get('post_type') == 'request':
                self._invite(raw)
            elif raw.get('post_type') == 'notice':
                self._notice(raw)
            elif self.super_user():
                self._command()

    def _invite(self, raw):
        gid, inviter, flag = raw.get('group_id'), raw.get('user_id'), raw.get('flag')
        if type(gid) is not int or type(inviter) is not int or not isinstance(flag, str) or not flag:
            logger.warning('群邀请缺少有效群号、邀请人或凭证，不审批')
            return
        db = self.dbmanager.community
        if not db.upsert_request(gid, inviter, flag, 'invite'):
            return
        row = self.dbmanager.conn.execute('SELECT * FROM group_requests WHERE flag = ?', (flag,)).fetchone()
        occupied = self.dbmanager.conn.execute(
            "SELECT COUNT(*) FROM (SELECT group_id FROM group_registry WHERE status='active' UNION"
            " SELECT group_id FROM group_requests WHERE status IN ('processing','uncertain') AND decision='approve')"
        ).fetchone()[0]
        reason = ''
        if db.is_banned('group', gid) or db.is_banned('user', inviter):
            reason = '群或邀请人在黑名单中'
        elif occupied >= config.COMMUNITY_MAX_GROUPS:
            reason = '群数已达上限'
        if not reason:
            self._notify_admins(f'收到群 {gid} 邀请（邀请人 {inviter}，申请编号 {row["id"]}），请用 /待审 查看')
            return
        db.reserve_review(row['id'], False, config.COMMUNITY_MAX_GROUPS)
        result = self._remote(row, False, reason)
        if result == 'ok':
            db.complete_review(row['id'])
        self._notify_admins(f'群 {gid} 申请 {row["id"]} 自动拒绝原因：{reason}；接口结果：{_REMOTE_TEXT[result]}')
        if result == 'ok' and reason == '群数已达上限':
            self.submit_message(text('暂时无法接入新的群，请联系维护者。'), target=('private', inviter))

    def _notice(self, raw):
        gid = raw.get('group_id')
        if type(gid) is not int:
            return
        db = self.dbmanager.community
        if raw['notice_type'] == 'group_decrease':
            db.mark_group_removed(gid)
            self._notify_admins(f'机器人已离开群 {gid}，群登记已停止；历史数据保留')
        elif db.record_group_join(gid, raw.get('operator_id') or raw['user_id']):
            self._notify_admins(f'机器人已进入未批准群 {gid}，暂不运行业务，请用 /待审 补审')

    def _command(self):
        db = self.dbmanager.community
        if self.cmd == '/待审':
            rows = db.pending_requests()
            lines = [f'编号 {r["id"]}：群 {r["group_id"]}，邀请人 {r["user_id"]}，'
                     f'{r["created_at"]}，{"已在群内" if r["kind"] == "manual" else "邀请请求"}，'
                     f'{_STATUS_TEXT[r["status"]]}，远端{_REMOTE_TEXT[r["remote_state"]]}'
                     for r in rows]
            self.submit_message(text('\n'.join(lines) if lines else '没有待处理群申请'))
            return
        if (len(self.args) not in (2, 3) or not self.args[0].isdecimal()
                or self.args[1] not in ('通过', '拒绝')
                or (len(self.args) == 3 and not self.args[2].isdecimal())):
            self.submit_message(text('用法：/审核 <群号> 通过|拒绝 [申请编号]；同群有多条申请时必须指定编号'))
            return
        gid, approve = int(self.args[0]), self.args[1] == '通过'
        rows = [r for r in db.pending_requests() if r['group_id'] == gid]
        if len(self.args) == 3:
            rows = [r for r in rows if r['id'] == int(self.args[2])]
        if len(rows) != 1:
            self.submit_message(text('申请不存在或有多条；请先 /待审 并指定准确申请编号'))
            return
        row = rows[0]
        decision = 'approve' if approve else 'reject'
        if approve:
            if db.is_banned('group', gid) or db.is_banned('user', row['user_id']):
                self.submit_message(text('群或邀请人在黑名单中，不能批准'))
                return
            other_groups = self.dbmanager.conn.execute(
                "SELECT COUNT(*) FROM (SELECT group_id FROM group_registry WHERE status='active' UNION"
                " SELECT group_id FROM group_requests WHERE status IN ('processing','uncertain') AND decision='approve')"
                " WHERE group_id != ?", (gid,)).fetchone()[0]
            if other_groups >= config.COMMUNITY_MAX_GROUPS:
                self.submit_message(text('群数已达上限，不能批准或恢复激活'))
                return
        if row['status'] == 'pending':
            try:
                row = db.reserve_review(row['id'], approve, config.COMMUNITY_MAX_GROUPS)
            except ValueError as exc:
                self.submit_message(text(str(exc)))
                return
            if row['kind'] == 'invite' and not (approve and row['joined']):
                result = self._remote(row, approve)
                if result != 'ok':
                    self.submit_message(text('远端明确失败，可再次审批' if result == 'failed'
                                             else '远端结果未知，保留待确认状态；请勿反复同意邀请'))
                    return
        elif row['decision'] != decision:
            self.submit_message(text('原审批方向不能变更；请先确认远端结果'))
            return
        row = self._row(row['id'])
        if row['remote_state'] != 'ok' and not (not approve and row['kind'] == 'manual' or approve and row['joined']):
            # 成功进群事实只能证明批准；群列表缺失不能证明拒绝成功。
            if not approve or not self._confirm_join(gid):
                self.submit_message(text('无法确认审批结果，仍未激活；请检查QQ端和日志后联系维护者'))
                return
            db.record_group_join(gid, row['user_id'])
        if approve:
            pack = FEATURE_PACKS[config.GROUP_REVIEW_DEFAULT_PACK]
            names = [name for name in pack['plugins'] if context.plugin_allowed(name)]
        else:
            names = []
        try:
            done = db.complete_review(row['id'], names)
        except Exception:
            logger.exception('申请 %s 远端已处理但本地登记失败，可重试本地提交', row['id'])
            self.submit_message(text('本地登记失败，结果已保留；请再次执行相同审批，不会重复已确认的远端操作'))
            return
        if done:
            self.submit_message(text(
                f'群 {gid} 已批准并开启基础功能；已有其他插件开关记录保留，可能恢复生效，请用 /插件 列表 群 {gid} 核对'
                if approve else f'群 {gid} 申请已拒绝'))
            if approve:
                self.submit_message(text(get_text('group_review.welcome', '本群已接入打卡服务，/菜单 查看可用功能')),
                                    target=('group', gid))
            elif row['kind'] == 'manual':
                self.submit_message(text('机器人已经在群内，本次只拒绝激活，不自动退群'))

    def _confirm_join(self, gid):
        try:
            response = self.api.call_api('get_group_list', {'no_cache': True})
            if response_result(response) != 'ok' or not isinstance(response.get('data'), list):
                return False
            return any(isinstance(item, dict) and item.get('group_id') == gid for item in response['data'])
        except Exception:
            logger.exception('核实群 %s 入群事实失败', gid)
            return False
