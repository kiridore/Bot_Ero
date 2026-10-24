"""房间状态以SQLite快照为准；事务内只变更状态，提交后才发送消息。"""
from copy import deepcopy
from dataclasses import dataclass, field
import random
import string
import time

from plugins.who_is_spy import game
from plugins.who_is_spy.titles import grant_game_titles

GAME_TYPES = frozenset({'卧底'})


@dataclass
class GameResult:
    room: dict
    reply: str
    events: list = field(default_factory=list)


class GameService:
    def __init__(self, db):
        self.db = db
        self.store = db.who_is_spy

    @staticmethod
    def unpack(rec):
        if rec is None:
            raise ValueError('房间不存在或已结束')
        room = rec['snapshot']
        room.update(record_id=rec['record_id'], revision=rec['revision'], status=rec['status'])
        return room

    def current(self, uid):
        rec = self.store.active_for_user(uid)
        return self.unpack(rec) if rec else None

    def get(self, code):
        return self.unpack(self.store.active_room(code))

    def _owner(self, room, uid, gid, super_user=False):
        if room['group_id'] != gid:
            raise ValueError('该房间不属于本群')
        if room['creator_id'] != str(uid) and not super_user:
            raise ValueError('只有房主才能操作此房间')

    def create(self, gid, uid, maximum, request_key):
        with self.store.transaction():
            existing = self.store.by_request(request_key)
            if existing:
                if existing['group_id'] != gid:
                    raise ValueError('创建请求所属群不符')
                room = self.unpack(existing)
                return GameResult(room, f"本次请求已有记录 #{room['record_id']}，房间 {room['room_id']}")
            for _ in range(100):
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                if self.store.active_room(code) is None:
                    break
            else:
                raise ValueError('无法生成房间号')
            room = dict(room_id=code, group_id=gid, creator_id=str(uid), game_type='卧底',
                        max_players=maximum, min_players=max(3, maximum - 2), players={}, members={},
                        phase='waiting', status='waiting', round_num=0, history=[],
                        civilian_word='', spy_word='', created_at=time.time(), started_at=None,
                        ended_at=None, ready_descriptions={}, votes={}, word_history=[])
            rec = self.store.create(request_key=request_key, room_code=code, group_id=gid,
                                    created_at=room['created_at'], snapshot=room)
            room.update(record_id=rec['record_id'], revision=rec['revision'])
        return GameResult(room, f'「卧底」房间 {code} 已创建（{maximum}人局），记录 #{room["record_id"]}\n'
                          f'请私聊机器人发送 /加入 {code} 加入\n输入 /开始 {code} 开始游戏')

    def _commit(self, room, reply, events):
        for uid, member in room['members'].items():
            if member['left_at'] is not None:
                member['state'] = 'left'
            elif room['status'] in ('finished', 'cancelled'):
                member['state'] = 'finished'
            elif room['status'] == 'playing':
                member['state'] = 'playing' if room['players'][uid]['alive'] else 'spectating'
            else:
                member['state'] = 'waiting'
        revision = self.store.save(room['record_id'], room['revision'], status=room['status'],
                                   snapshot=room, participants=list(room['members'].values()),
                                   started_at=room['started_at'], ended_at=room['ended_at'],
                                   winner=room.get('_winner'))
        room['revision'] = revision
        if room['status'] == 'finished':
            awards = {}
            for uid, p in room['players'].items():
                if room['members'][uid]['participated']:
                    awards[uid] = grant_game_titles(self.db, uid, p['role'], room['_winner'], left=p.get('left', False))
            for kind, snapshot in events:
                if kind == 'finished':
                    snapshot['_new_titles'] = awards
        return GameResult(room, reply, events)

    def join(self, code, uid, nickname):
        uid = str(uid)
        with self.store.transaction():
            previous = self.current(uid)
            if previous:
                raise ValueError(f"你已在房间 {previous['room_id']} 中，请先 /退出")
            room = self.get(code)
            if room['status'] != 'waiting':
                raise ValueError('游戏已开始，无法加入')
            if len(room['players']) >= room['max_players']:
                raise ValueError('房间已满')
            alias = f"{len(room['players']) + 1}号"
            room['players'][uid] = dict(user_id=uid, nickname=nickname, alias=alias, word='', role='', alive=True, left=False)
            first = room['members'].get(uid, {}).get('joined_at', time.time())
            room['members'][uid] = dict(user_id=uid, nickname=nickname, joined_at=first, left_at=None, participated=False, state='waiting')
            return self._commit(room, f'已加入卧底房间 {code}，你的代号是 {alias}', [('joined', deepcopy(room))])

    def start(self, code, uid, gid):
        with self.store.transaction():
            room = self.get(code)
            self._owner(room, uid, gid)
            result = game.start_game(room)
            if result != 'ok':
                raise ValueError(result)
            room['status'], room['started_at'] = 'playing', time.time()
            for pid in room['players']:
                room['members'][pid]['participated'] = True
            return self._commit(room, '', [('started', deepcopy(room)), ('describe', deepcopy(room))])

    def cancel(self, code, uid, gid, super_user=False):
        with self.store.transaction():
            room = self.get(code)
            self._owner(room, uid, gid, super_user)
            self._cancel(room)
            return self._commit(room, '', [('cancelled', deepcopy(room))])

    @staticmethod
    def _cancel(room):
        room.update(status='cancelled', phase='cancelled', ended_at=time.time())

    @staticmethod
    def _finish(room, winner, events):
        room.update(status='finished', phase='game_over', ended_at=time.time(), _winner=winner)
        events.append(('finished', deepcopy(room)))

    def _advance(self, room, events):
        alive = [uid for uid, p in room['players'].items() if p['alive']]
        if not alive:
            self._cancel(room)
            events.append(('cancelled', deepcopy(room)))
            return
        winner = game.check_winner(room)
        if winner:
            self._finish(room, winner, events)
        elif room['phase'] == 'playing_describe' and all(uid in room['ready_descriptions'] for uid in alive):
            events.append(('descriptions', deepcopy(room)))
            game.advance_to_voting(room)
            events.append(('vote', deepcopy(room)))
        elif room['phase'] == 'playing_vote' and all(uid in room['votes'] for uid in alive):
            game.tally_votes(room)
            events.append(('result', deepcopy(room)))
            winner = game.check_winner(room)
            if winner:
                self._finish(room, winner, events)
            else:
                game.advance_to_describe(room)
                events.append(('describe', deepcopy(room)))

    def leave(self, uid):
        uid = str(uid)
        with self.store.transaction():
            room = self.current(uid)
            if not room:
                raise ValueError('你不在任何房间中')
            room['members'][uid]['left_at'] = time.time()
            if room['status'] == 'waiting':
                del room['players'][uid]
                for n, p in enumerate(room['players'].values(), 1):
                    p['alias'] = f'{n}号'
                if not room['players']:
                    self._cancel(room)
                elif uid == room['creator_id']:
                    room['creator_id'] = next(iter(room['players']))
                events = [('cancelled' if room['status'] == 'cancelled' else 'left', deepcopy(room))]
            else:
                room['players'][uid].update(alive=False, left=True)
                room['ready_descriptions'].pop(uid, None)
                room['votes'] = {voter: target for voter, target in room['votes'].items() if voter != uid and target != uid}
                events = [('left', deepcopy(room))]
                self._advance(room, events)
                if len(events) == 1 and room['phase'] == 'playing_vote':
                    events.append(('vote', deepcopy(room)))
            return self._commit(room, f"已退出房间 {room['room_id']}，停止观战；历史参与记录保留", events)

    def input(self, record_id, uid, body, expected=None):
        uid = str(uid)
        with self.store.transaction():
            room = self.unpack(self.store.get_internal(record_id))
            if room['status'] != 'playing':
                raise ValueError('本局当前不能提交游戏输入')
            if expected and expected != (room['round_num'], room['phase']):
                raise ValueError('游戏阶段已更新，请按最新提示操作')
            p = room['players'].get(uid)
            if not p or p.get('left'):
                raise ValueError('你已退出本局')
            if not p['alive']:
                raise ValueError('你正在观战，不能发言或投票；可发送 /退出 离开')
            if room['phase'] == 'playing_describe':
                result = game.collect_description(room, uid, body)
                reply = '描述已记录，等待其他玩家...'
            else:
                result = game.collect_vote(room, uid, body)
                reply = '投票已记录，等待其他玩家...'
            if isinstance(result, str):
                raise ValueError(result)
            events = []
            self._advance(room, events)
            return self._commit(room, reply, events)
