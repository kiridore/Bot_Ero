"""只发送已提交的结果；退出者不再接收主动私聊，未结束记录不揭晓。"""
from datetime import datetime

from core import config
from core.cq import text
from core.logger import logger

STATUS_NAMES = {'waiting': '未开始', 'playing': '进行中', 'finished': '正常结束',
                'cancelled': '已解散（无胜负）', 'interrupted': '因重启中断（无胜负）'}


def vote_lines(rec):
    counts, eliminated = rec['vote_counts'], rec['eliminated']
    return [f"{alias} {counts.get(uid, 0)}票" + (' ← 出局' if uid == eliminated else '')
            for uid, alias in rec['participants'].items()]


def format_record_summary(data, user_id=None, *, include_rounds=True):
    room = data['snapshot']
    lines = [f"游戏记录 #{data['record_id']}｜房间 {data['room_code']}",
             f"状态：{STATUS_NAMES[data['status']]}",
             f"创建时间：{datetime.fromtimestamp(data['created_at']):%Y-%m-%d %H:%M}"]
    if data['ended_at'] is not None:
        lines.append(f"结束时间：{datetime.fromtimestamp(data['ended_at']):%Y-%m-%d %H:%M}")
    member = room.get('members', {}).get(str(user_id)) if user_id is not None else None
    if member and member['left_at'] is not None:
        lines.append('本人：已退出；未开局退出不计参赛，开局后退出不计本局获胜')
    if data['status'] == 'finished':
        lines.extend(['', f"胜负结果：{'平民' if data['winner'] == 'civilian' else '卧底'}胜利",
                      f"平民词条：{room['civilian_word']}", f"卧底词条：{room['spy_word']}", '玩家身份：'])
        for p in room['players'].values():
            lines.append(f"{p['alias']} {p['nickname']} - {'平民' if p['role'] == 'civilian' else '卧底'} - {p['word']}"
                         + ('（主动退出，不计获胜）' if p.get('left') else ''))
    else:
        lines.append('身份和词条仅在正常结束后揭晓。')
    for rec in room.get('history', []) if include_rounds else ():
        lines.extend(['', f"──── 第{rec['round_num']}轮 ────"])
        for uid, description in rec.get('descriptions', {}).items():
            alias = rec['participants'].get(uid)
            if alias is not None:
                lines.append(f'{alias}：{description}')
        lines.extend(vote_lines(rec))
    return '\n'.join(lines)


def forward_nodes(body):
    return [{'type': 'node', 'data': {'uin': int(config.BOT_QQ), 'name': '游戏记录',
             'content': [text(block)]}} for block in body.split('\n\n') if block]


class GameMessenger:
    def __init__(self, api, store=None):
        self.api, self.store = api, store

    def send(self, action, params):
        try:
            response = self.api.call_api(action, params)
            if not isinstance(response, dict) or response.get('status') != 'ok' or response.get('retcode') != 0:
                logger.warning('卧底消息发送失败，action=%s；业务已提交，不自动重试', action)
        except Exception:
            logger.exception('卧底消息发送异常，业务已提交，不自动重试')

    def private(self, room, uid, body):
        if room['players'][str(uid)].get('left'):
            return
        if self.store is not None:
            try:
                if not self.store.can_receive(room['record_id'], uid):
                    return  # 早先已排定的通知也不能发送给现在已退出者
            except Exception:
                logger.exception('无法确认卧底接收者状态，跳过该私聊')
                return
        self.send('send_private_msg', {'user_id': int(uid), 'message': [text(body)]})

    def broadcast(self, room, body, *, audience='all'):
        for uid, p in room['players'].items():
            if audience == 'alive' and not p['alive'] or audience == 'spectators' and p['alive']:
                continue
            self.private(room, uid, body)

    def group(self, room, body):
        self.send('send_group_msg', {'group_id': int(room['group_id']), 'message': [text(body)]})

    def result(self, room, eliminated):
        rec = room['history'][-1]
        self.broadcast(room, '\n'.join([f"第{rec['round_num']}轮 投票结果：", *vote_lines(rec), '',
                                        f"{room['players'][eliminated]['alias']} 被投票出局！"]))
        self.private(room, eliminated, '你已出局，将继续观战本局，不能发言或投票；发送 /退出 可离开房间。')

    def emit(self, events):
        for kind, room in events:
            if kind == 'started':
                spies = sum(p['role'] == 'spy' for p in room['players'].values())
                self.group(room, f"游戏开始！本局 {len(room['players'])} 人参与，{spies} 个卧底，{len(room['players']) - spies} 个平民\n请查看私聊中的词条")
                for uid, p in room['players'].items():
                    self.private(room, uid, f"{p['alias']}，你的词条：{p['word']}\n请按后续提示描述和投票，不要直接说出词条。")
            elif kind in ('describe', 'vote'):
                names = '  '.join(p['alias'] for p in room['players'].values() if p['alive'])
                phase = '描述' if kind == 'describe' else '投票'
                prompt = '请用一句话描述你的词条（不能直接说出词）' if kind == 'describe' else '请投票选出卧底，发送代号即可；已投票无需重投'
                self.broadcast(room, f"第{room['round_num']}轮 {phase}阶段\n{prompt}\n存活玩家：{names}", audience='alive')
                self.broadcast(room, f"观战：第{room['round_num']}轮进入{phase}阶段，无需提交。\n存活玩家：{names}", audience='spectators')
            elif kind == 'descriptions':
                body = [f"第{room['round_num']}轮 描述汇总："]
                body.extend(f"{room['players'][uid]['alias']}：{value}" for uid, value in room['ready_descriptions'].items())
                self.broadcast(room, '\n'.join(body))
            elif kind == 'result':
                self.result(room, room['history'][-1]['eliminated'])
            elif kind == 'left':
                self.broadcast(room, '有玩家退出房间；若正在投票，其选票及投给他的选票已作废，尚未有效投票者请重新提交。')
                self.group(room, f"房间 {room['room_id']} 有玩家退出")
            elif kind == 'joined':
                self.group(room, f"房间 {room['room_id']} 当前 {len(room['players'])}/{room['max_players']} 人")
            elif kind == 'cancelled':
                self.broadcast(room, f"房间 {room['room_id']} 已解散，无胜负结果；可用 /游戏记录 查询参与经历")
                self.group(room, f"房间 {room['room_id']} 已解散，无胜负结果")
            elif kind == 'finished':
                record = dict(record_id=room['record_id'], room_code=room['room_id'], status='finished',
                              winner=room['_winner'], created_at=room['created_at'], ended_at=room['ended_at'], snapshot=room)
                body = format_record_summary(record)
                self.broadcast(room, format_record_summary(record, include_rounds=False)
                               + f"\n完整记录：/游戏记录 查看 {room['record_id']}")
                from plugins.title.defs import TITLE_DEFS
                for uid, titles in room.get('_new_titles', {}).items():
                    if titles:
                        self.private(room, uid, '获得称号：' + ' '.join(TITLE_DEFS[tid]['name'] for tid in titles))
                self.send('send_group_forward_msg', {'group_id': int(room['group_id']), 'messages': forward_nodes(body)})


def broadcast_vote_result(api, room, eliminated_uid):
    GameMessenger(api).result(room, eliminated_uid)
