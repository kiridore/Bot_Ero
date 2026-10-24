"""卧底集成测试共用的临时库与QQ替身。"""
from itertools import count
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import config
from core.database_manager import DbManager
from core.event import Event
from plugins.who_is_spy import WhoIsSpyPlugin, game
from plugins.who_is_spy.room import GameService


@pytest.fixture
def game_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'game.db')
    def assign(room):
        room['civilian_word'], room['spy_word'] = '苹果', '梨子'
        for n, p in enumerate(room['players'].values(), 1):
            p.update(alias=f'{n}号', role='spy' if n == len(room['players']) else 'civilian',
                     word='梨子' if n == len(room['players']) else '苹果')
        return True
    monkeypatch.setattr(game, 'assign_words', assign)
    db = DbManager()
    ids = count(100)
    def run(body, uid=101, gid=None):
        api = Mock()
        api.call_api.return_value = {'status': 'ok', 'retcode': 0}
        api.send_msg.return_value = api.send_forward_nodes.return_value = 1
        raw = dict(post_type='message', message_type='private' if gid is None else 'group',
                   user_id=uid, message_id=next(ids), time=1000,
                   message=[{'type': 'text', 'data': {'text': body}}], sender={'nickname': f'用户{uid}'})
        if gid is not None:
            raw['group_id'] = gid
        p = WhoIsSpyPlugin.__new__(WhoIsSpyPlugin)
        p.api, p.dbmanager, p.bot_event = api, db, Event(raw)
        if p.match('message'):
            p.handle()
        return api
    try:
        yield SimpleNamespace(db=db, service=GameService(db), run=run, tmp=tmp_path)
    finally:
        db.conn.close()


def new_room(env, n=4, group=100, start=True, key='create'):
    result = env.service.create(group, 101, max(4, n), key)
    code = result.room['room_id']
    for uid in range(101, 101 + n):
        env.service.join(code, uid, f'玩家{uid}')
    return env.service.start(code, 101, group).room if start else env.service.get(code)


def seed(env, room, **updates):
    room = env.service.get(room['room_id'])
    room.update(updates)
    with env.db.who_is_spy.transaction():
        env.db.who_is_spy.save(room['record_id'], room['revision'], status=room['status'],
                             snapshot=room, participants=list(room['members'].values()),
                             started_at=room['started_at'], ended_at=room['ended_at'], winner=room.get('_winner'))
    return env.service.get(room['room_id'])


def text_of(value):
    if isinstance(value, dict):
        if value.get('type') == 'text':
            return value['data']['text']
        return '\n'.join(text_of(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return '\n'.join(text_of(v) for v in value)
    return ''


def output(api):
    return '\n'.join(text_of(call.args) for method in (api.send_msg, api.send_forward_nodes, api.call_api)
                     for call in method.call_args_list)


def private_output(api, uid):
    return '\n'.join(text_of(call.args[1]['message']) for call in api.call_api.call_args_list
                     if call.args[0] == 'send_private_msg' and call.args[1]['user_id'] == uid)
