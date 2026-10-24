from datetime import datetime

from core.base import Plugin
from core.cq import text
from core.logger import logger
from core.utils import register_plugin
from plugins.who_is_spy.room import GameService, GAME_TYPES, GameResult
from plugins.who_is_spy.relay import GameMessenger, STATUS_NAMES, format_record_summary, forward_nodes

COMMANDS = frozenset({'/创建游戏', '/开始', '/加入', '/离开', '/退出', '/状态', '/放弃', '/房间列表', '/游戏记录'})


def positive_number(value):
    if len(value) > 12 or not value.isdecimal() or int(value) < 1:
        raise ValueError('编号和页码必须是正整数')
    return int(value)


@register_plugin
class WhoIsSpyPlugin(Plugin):
    name = 'who_is_spy'
    description = '谁是卧底：私聊匿名游戏、出局观战及参与历史'

    def _first_text(self):
        for seg in self.bot_event.message:
            if seg.get('type') == 'text':
                return seg.get('data', {}).get('text', '').strip()
        return ''

    def match(self, event_type='message'):
        if event_type != 'message' or self.bot_event.raw.get('post_type') != 'message' or self.bot_event.user_id is None:
            return False
        body = self._first_text()
        if not body:
            return False
        parts = body.split()
        if parts[0] in COMMANDS:
            self._mode, self._cmd, self._args = 'command', parts[0], parts[1:]
            return True
        if self.bot_event.is_private:
            room = GameService(self.dbmanager).current(self.bot_event.user_id)
            if room and room['status'] == 'playing':
                self._mode, self._input_text = 'game_input', body
                self._record_id = room['record_id']
                self._expected = (room['round_num'], room['phase'])
                return True
        return False

    def _reply(self, body, forward=False):
        try:
            result = self.api.send_forward_nodes(forward_nodes(body)) if forward else self.api.send_msg(text(body))
            if not result:
                logger.warning('卧底回复发送失败，不重执行业务')
        except Exception:
            logger.exception('卧底回复发送异常，不重执行业务')

    def handle(self):
        try:
            result = self._handle_command() if self._mode == 'command' else self._handle_game_input()
        except ValueError as exc:
            self._reply(str(exc))
            return
        except Exception:
            logger.exception('卧底操作失败')
            self._reply('本次操作未确认成功，请稍后重试或联系管理员。')
            return
        if isinstance(result, GameResult):
            if result.reply:
                self._reply(result.reply)
            GameMessenger(self.api, self.dbmanager.who_is_spy).emit(result.events)

    def _handle_game_input(self):
        return GameService(self.dbmanager).input(self._record_id, self.bot_event.user_id,
                                                self._input_text, self._expected)

    def _handle_command(self):
        cmd, args = self._cmd, self._args
        uid, gid = self.bot_event.user_id, self.bot_event.group_id
        service = GameService(self.dbmanager)
        if cmd == '/游戏记录':
            return self._history(args, uid, gid)
        if cmd == '/创建游戏':
            if gid is None:
                raise ValueError('请在群聊创建游戏')
            if not args or args[0] not in GAME_TYPES or len(args) > 2:
                raise ValueError('用法：/创建游戏 卧底 [人数]（4-10人）')
            try:
                maximum = max(4, min(10, int(args[1]))) if len(args) == 2 else 6
            except ValueError:
                raise ValueError('人数必须为数字（4-10）')
            mid = self.bot_event.message_id
            if mid is None:
                raise ValueError('无法识别创建请求，请重新发送')
            key = f"{gid}:{uid}:{self.bot_event.raw.get('time', 0)}:{mid}"
            return service.create(gid, uid, maximum, key)
        if cmd == '/加入':
            if gid is not None or len(args) != 1:
                raise ValueError('请私聊发送 /加入 <房间号>')
            sender = self.bot_event.sender or {}
            nickname = sender.get('card') or sender.get('nickname') or f'用户{uid}'
            return service.join(args[0], uid, nickname)
        if cmd in ('/开始', '/放弃'):
            if gid is None or len(args) != 1:
                raise ValueError(f'请在所属群发送 {cmd} <房间号>')
            if cmd == '/开始':
                return service.start(args[0], uid, gid)
            return service.cancel(args[0], uid, gid, self.super_user())
        if cmd in ('/退出', '/离开'):
            if args:
                raise ValueError('用法：/退出 或 /离开')
            return service.leave(uid)
        if cmd == '/状态':
            if len(args) > 1:
                raise ValueError('用法：/状态 [房间号]')
            room = service.get(args[0]) if args else service.current(uid)
            if not room:
                raise ValueError('房间不存在，或你不在房间中')
            if gid is not None and gid != room['group_id'] or gid is None and (
                    str(uid) not in room['members'] or room['members'][str(uid)]['left_at'] is not None):
                raise ValueError('不能查看此房间')
            alive = sum(p['alive'] for p in room['players'].values())
            watching = sum(not p['alive'] and not p.get('left') for p in room['players'].values())
            body = f"房间 {room['room_id']}｜记录 #{room['record_id']}\n状态：{STATUS_NAMES[room['status']]}\n存活：{alive}，观战：{watching}\n轮次：{room['round_num']}"
            if room['status'] == 'waiting':
                body += '\n' + '\n'.join(f"{p['alias']} {p['nickname']}" + ('（房主）' if pid == room['creator_id'] else '') for pid, p in room['players'].items())
            self._reply(body)
        elif cmd == '/房间列表':
            if gid is None or args:
                raise ValueError('请在群聊发送 /房间列表')
            rows = self.dbmanager.who_is_spy.active_in_group(gid)
            self._reply('\n'.join(f"{r['room_code']}｜记录 #{r['record_id']}｜{STATUS_NAMES[r['status']]}" for r in rows) or '该群没有活跃房间')

    def _history(self, args, uid, gid):
        scope = {'group_id': gid} if gid is not None else {'user_id': uid}
        store = self.dbmanager.who_is_spy
        if len(args) == 2 and args[0] == '查看':
            record = store.detail(positive_number(args[1]), **scope)
            if record is None:
                raise ValueError('记录不存在或不可查看')
            self._reply(format_record_summary(record, user_id=uid if gid is None else None), forward=True)
            return
        if not args:
            page = 1
        elif args[0] == '列表' and len(args) in (1, 2):
            page = positive_number(args[1]) if len(args) == 2 else 1
        else:
            raise ValueError('用法：/游戏记录 列表 [页码] 或 /游戏记录 查看 <记录编号>；不再按旧房间号查询')
        rows, more = store.list_records(page=page, **scope)
        lines = [f"{'本群' if gid is not None else '本人参与'}游戏记录｜第{page}页"]
        for rec in rows:
            label = STATUS_NAMES[rec['status']]
            if rec['winner']:
                label += '，' + ('平民' if rec['winner'] == 'civilian' else '卧底') + '胜'
            if rec.get('participation_state') == 'left':
                label += '（本人已退出，不计本局获胜）'
            lines.append(f"#{rec['record_id']}｜{datetime.fromtimestamp(rec['created_at']):%m-%d %H:%M}｜房间 {rec['room_code']}｜{label}")
        if not rows:
            lines.append('本页暂无新系统记录；旧JSON不纳入查询。')
        if more:
            lines.append(f'下一页：/游戏记录 列表 {page + 1}')
        lines.append('详情：/游戏记录 查看 <记录编号>')
        self._reply('\n'.join(lines))
