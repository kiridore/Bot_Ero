from core import config, command_rate_limit
from test.test_blacklist_management import management


def test_banned_account_cross_scopes_silent_before_budget(management):
    run, db, hits, cls = management
    db.community.ban('user', 42)
    for gid in (None, 100, 200):
        assert run('/测试', uid=42, gid=gid) == ''
    assert not hits
    assert 42 not in command_rate_limit.limiter._windows
    run('/测试', uid=43, gid=100)
    assert len(hits) == 1


def test_group_does_not_block_member_other_locations(management):
    run, db, hits, cls = management
    db.community.ban('group', 100)
    run('/测试', uid=42, gid=100)
    assert not hits
    run('/测试', uid=42, gid=200)
    run('/测试', uid=42)
    assert len(hits) == 2


def test_disabled_preserves_message_behavior(management, monkeypatch):
    run, db, hits, cls = management
    db.community.ban('user', 42)
    db.community.ban('group', 100)
    monkeypatch.setattr(config, 'BLACKLIST_ENABLED', False)
    run('/测试', uid=42, gid=100)
    assert len(hits) == 1


def test_read_failure_refuses_new_work(management, monkeypatch, tmp_path):
    run, db, hits, cls = management
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'missing.db')
    assert run('/测试', uid=42) == ''
    assert not hits and 42 not in command_rate_limit.limiter._windows
    assert not config.DB_PATH.exists()
