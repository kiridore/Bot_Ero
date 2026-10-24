"""投票真实状态、显示及并发回归；conftest隔离配置，API为替身。"""
from collections import Counter
from itertools import product
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import context
from plugins.who_is_spy import WhoIsSpyPlugin, game, relay


def make_room():
    return {'room_id': 'VOTE', 'phase': 'playing_vote', 'round_num': 1,
            'votes': {}, 'history': [], 'ready_descriptions': {},
            'players': {str(100 + n): {'user_id': str(100 + n), 'alias': f'{n}号',
                        'alive': True, 'role': 'spy' if n == 4 else 'civilian'}
                        for n in range(1, 5)}}


def test_highest_all_81_valid_four_player_ballots(monkeypatch):
    monkeypatch.setattr(game.random, 'choice', lambda candidates: candidates[0])
    for targets in product(*[[n for n in range(1, 5) if n != voter] for voter in range(1, 5)]):
        room = make_room()
        for uid, target in zip(room['players'], targets):
            ready = game.collect_vote(room, uid, str(target))
            assert ready is True or ready is False
        assert ready is True
        counts = Counter(room['votes'].values())
        eliminated = game.tally_votes(room)
        assert counts[eliminated] == max(counts.values()), (targets, counts, eliminated)
        assert [uid for uid, p in room['players'].items() if not p['alive']] == [eliminated]
        assert room['history'][0]['eliminated'] == eliminated
        assert room['history'][0]['vote_counts'] == counts
        api = Mock()
        relay.broadcast_vote_result(api, room, eliminated)
        message = api.call_api.call_args_list[0].args[1]['message'][0]['data']['text']
        alias = room['players'][eliminated]['alias']
        assert f'{alias} {counts[eliminated]}票 ← 出局' in message
        assert f'{alias} 被投票出局！' in message


@pytest.mark.parametrize('raw,expected', [('1', '101'), ('1号', '101'), ('①', '101'),
                                         (' 1 ', '101'), ('10', '110'), ('⑩', '110')])
def test_number_exact_alias_with_ten_first(raw, expected):
    room = make_room()
    room['players'] = {'110': {'user_id': '110', 'alias': '10号', 'alive': True}, **room['players']}
    assert game.collect_vote(room, '102', raw) is False
    assert room['votes']['102'] == expected


def test_number_validation_still_rejects_invalid_self_dead_and_duplicate():
    room = make_room()
    assert game.collect_vote(room, '101', 'bad') == '请回复玩家编号（如 1 / ①）'
    assert game.collect_vote(room, '101', '99') == '无效的编号，请输入正确编号'
    assert game.collect_vote(room, '101', '1') == '不能投给自己'
    room['players']['102']['alive'] = False
    assert game.collect_vote(room, '101', '2') == '无效的编号，请输入正确编号'
    assert game.collect_vote(room, '102', '1') == '你已出局'
    assert not room['votes']
    assert game.collect_vote(room, '101', '3') is False
    assert game.collect_vote(room, '101', '4') == '你已经投过票了'
    assert room['votes'] == {'101': '103'}


def test_completion_uses_alive_voters_not_old_total():
    room = make_room()
    room['votes'] = {'101': '102', '102': '101'}
    room['players']['101']['alive'] = False
    assert game.collect_vote(room, '103', '2') is False  # 104尚未投票，退出者旧票不顶替
    assert game.collect_vote(room, '104', '2') is True


def test_completion_next_round_accepts_fresh_votes():
    room = make_room()
    room['votes'] = {'101': '102', '102': '101', '103': '101'}
    assert game.collect_vote(room, '104', '1') is True
    game.tally_votes(room)
    game.advance_to_describe(room)
    game.advance_to_voting(room)
    assert room['votes'] == {}
    assert game.collect_vote(room, '102', '3') is False
    assert game.collect_vote(room, '103', '2') is False
    assert game.collect_vote(room, '104', '2') is True


def run_pair(first, second, paused, release):
    errors = []
    second_done = Event()
    def guarded(fn, done=None):
        try:
            fn()
        except BaseException as exc:
            errors.append(exc)
        finally:
            if done is not None:
                done.set()
    a = Thread(target=guarded, args=(first,), name='vote-first', daemon=True)
    b = Thread(target=guarded, args=(second, second_done), name='vote-second', daemon=True)
    try:
        a.start()
        assert paused.wait(3), '第一个收票线程未到指定位置'
        b.start()
        second_done.wait(.3)  # 旧代码允许第二个线程先完成，新锁必须等待第一个
    finally:
        release.set()
        a.join(5)
        if b.ident is not None:
            b.join(5)
    assert not a.is_alive() and not b.is_alive(), '收票死锁'
    assert not errors, errors


def test_concurrent_last_votes_settle_once_through_real_handler(monkeypatch):
    room = make_room()
    paused, release = Event(), Event()
    class PausedVotes(dict):
        def __setitem__(self, uid, target):
            super().__setitem__(uid, target)
            if uid == '103':
                paused.set()
                assert release.wait(3)
    room['votes'] = PausedVotes({'101': '102', '102': '101'})
    monkeypatch.setattr(context, 'game_rooms', {'VOTE': room})
    def handle(uid):
        plugin = WhoIsSpyPlugin.__new__(WhoIsSpyPlugin)
        plugin.bot_event = SimpleNamespace(user_id=uid)
        plugin._game_room_id, plugin._input_text = 'VOTE', '1'
        plugin.api = Mock()
        plugin._handle_game_input()
    run_pair(lambda: handle(103), lambda: handle(104), paused, release)
    assert len(room['history']) == 1
    assert room['history'][0]['round_num'] == 1
    assert room['history'][0]['eliminated'] == '101'
    assert room['round_num'] == 2
    assert room['phase'] == 'playing_describe'


def test_concurrent_duplicate_voter_cannot_overwrite_first_vote():
    from threading import current_thread
    room = make_room()
    paused, release = Event(), Event()
    class PausedPlayers(dict):
        def items(self):
            if current_thread().name == 'vote-first':
                paused.set()
                assert release.wait(3)
            return super().items()
    room['players'] = PausedPlayers(room['players'])
    results = {}
    def cast(key, target):
        results[key] = game.collect_vote(room, '103', target)
    run_pair(lambda: cast('first', '1'), lambda: cast('second', '2'), paused, release)
    assert results == {'first': False, 'second': '你已经投过票了'}
    assert room['votes'] == {'103': '101'}


def test_highest_tie_real_handler_preserves_zero_vote_players(monkeypatch):
    room = make_room()
    room['votes'] = {'101': '102', '102': '101', '103': '101'}
    monkeypatch.setattr(context, 'game_rooms', {'VOTE': room})
    monkeypatch.setattr(game.random, 'choice', lambda candidates: candidates[0])
    plugin = WhoIsSpyPlugin.__new__(WhoIsSpyPlugin)
    plugin.bot_event = SimpleNamespace(user_id=104)
    plugin._game_room_id, plugin._input_text = 'VOTE', '2'
    plugin.api = Mock()
    plugin._handle_game_input()
    assert room['history'][0]['eliminated'] in {'101', '102'}
    assert room['players']['103']['alive'] and room['players']['104']['alive']
    assert room['round_num'] == 2 and room['phase'] == 'playing_describe'


def test_completion_network_sends_do_not_hold_game_lock(monkeypatch):
    room = make_room()
    room['votes'] = {'101': '102', '102': '101', '103': '101'}
    monkeypatch.setattr(context, 'game_rooms', {'VOTE': room})
    def send(*args, **kwargs):
        assert context.game_lock.acquire(blocking=False), '发送期间占用全局游戏锁'
        context.game_lock.release()
        return {'status': 'ok', 'retcode': 0}
    plugin = WhoIsSpyPlugin.__new__(WhoIsSpyPlugin)
    plugin.bot_event = SimpleNamespace(user_id=104)
    plugin._game_room_id, plugin._input_text = 'VOTE', '1'
    plugin.api = Mock()
    plugin.api.send_msg.side_effect = send
    plugin.api.call_api.side_effect = send
    plugin._handle_game_input()
    assert room['round_num'] == 2
    assert plugin.api.call_api.called
