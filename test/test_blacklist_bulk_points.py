from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import base, config, context
from core.db.community import CommunityManager
from core.db.points import PointsManager
from plugins.grant_points_all import GrantPointsAllPlugin
from test.test_blacklist_management import management


def prepare(management, monkeypatch):
    run, db, _, _ = management
    monkeypatch.setattr(context, 'plugin_registry', [GrantPointsAllPlugin])
    monkeypatch.setattr(context, 'SYSTEM_PLUGINS', frozenset({'grant_points_all'}))
    db.points.set(42, 10)
    db.points.set(43, 10)
    return run, db, base.ApiWrapper.return_value


@pytest.mark.parametrize('amount', [5, -5])
def test_bulk_positive_and_negative_skip_banned_and_count_actual(management, monkeypatch, amount):
    run, db, api = prepare(management, monkeypatch)
    db.community.ban('user', 42)
    run(f'/发金币 {amount}')
    assert db.points.get(42) == 10
    assert db.points.get(43) == 10 + amount
    api.send_msg.assert_called_once()
    assert api.send_msg.call_args.args[0]['data']['text'] == f'已给 1 位用户发放 {amount} 点积分'


def test_bulk_snapshot_is_not_changed_mid_operation(management, monkeypatch):
    run, db, api = prepare(management, monkeypatch)
    db.community.ban('user', 42)
    original = PointsManager.grant_all
    changed = []
    def grant(self, amount, **kwargs):
        if not changed:
            manager = CommunityManager(self.conn)
            manager.unban('user', 42)
            manager.ban('user', 43)
            changed.append(True)
        return original(self, amount, **kwargs)
    monkeypatch.setattr(PointsManager, 'grant_all', grant)
    run('/发金币 5')
    assert db.points.get(42) == 10  # 获准时被封，不因中途解除加入
    assert db.points.get(43) == 15  # 获准后新增封禁，本次仍完成
    run('/发金币 5')
    assert db.points.get(42) == 15
    assert db.points.get(43) == 15


def test_bulk_failure_rolls_back_all_accounts_and_no_success_reply(management, monkeypatch):
    run, db, api = prepare(management, monkeypatch)
    db.conn.execute("CREATE TRIGGER fail_second BEFORE UPDATE ON user_assets "
                    "WHEN NEW.user_id='43' BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    db.conn.commit()
    out = run('/发金币 5')
    assert db.points.get(42) == db.points.get(43) == 10
    api.send_msg.assert_not_called()
    assert '处理失败' in out


def test_bulk_disabled_and_protected_account(management, monkeypatch):
    run, db, api = prepare(management, monkeypatch)
    db.points.set(99, 10)
    db.community.ban('user', 99)  # 旧记录不能封住当前超管
    db.community.ban('user', 42)
    run('/发金币 -2')
    assert db.points.get(99) == db.points.get(43) == 8
    assert db.points.get(42) == 10
    monkeypatch.setattr(config, 'BLACKLIST_ENABLED', False)
    run('/发金币 -2')
    assert db.points.get(42) == 8
    assert db.points.get(99) == db.points.get(43) == 6


def test_bulk_missing_snapshot_refuses_when_enabled(management):
    _, db, _, _ = management
    db.points.set(42, 10)
    plugin = GrantPointsAllPlugin.__new__(GrantPointsAllPlugin)
    plugin.args, plugin.dbmanager, plugin.api = ['5'], db, Mock()
    plugin.operation = SimpleNamespace(blacklist_snapshot=None)
    with pytest.raises(RuntimeError, match='快照'):
        plugin.handle()
    assert db.points.get(42) == 10
    plugin.api.send_msg.assert_not_called()


def test_bulk_all_excluded_counts_zero(management, monkeypatch):
    run, db, api = prepare(management, monkeypatch)
    db.community.ban('user', 42)
    db.community.ban('user', 43)
    run('/发金币 5')
    assert db.points.get(42) == db.points.get(43) == 10
    assert '已给 0 位用户' in api.send_msg.call_args.args[0]['data']['text']
