from types import SimpleNamespace
from unittest.mock import Mock

from core import config, context
from test.test_blacklist_management import management
from test.test_blacklist_tasks import enable


def test_news_and_report_do_not_fetch_or_generate_for_blocked_group(management, monkeypatch):
    import plugins.ff_news as news
    import plugins.weekly_report as weekly
    _, db, _, _ = management
    monkeypatch.setattr(config, 'DEFAULT_GROUP_ID', 100)
    monkeypatch.setattr(weekly, 'GROUP_ID', 100)
    for key in ('ff_news', 'weekly_report'):
        enable(db, key, gid=100)
    db.community.ban('group', 100)
    plugin = news.FfNewsPlugin.__new__(news.FfNewsPlugin)
    plugin.api, plugin.dbmanager, plugin._fetch_payload = Mock(), db, Mock()
    plugin._handle_hourly()
    plugin._fetch_payload.assert_not_called()
    plugin.api.send_msg.assert_not_called()
    report = weekly.WeeklyReportPlugin.__new__(weekly.WeeklyReportPlugin)
    report.api, report.dbmanager = Mock(), db
    report._generate_week('2026-10-12 08:00:00', '2026-10-19 08:00:00')
    assert db.conn.execute('SELECT COUNT(*) FROM weekly_reports').fetchone()[0] == 0
    report.api.send_msg.assert_not_called()


def test_forum_each_post_checked_but_global_poll_cleanup_continues(management, monkeypatch):
    import plugins.forum_notify as forum
    _, db, _, _ = management
    monkeypatch.setattr(config, 'DEFAULT_GROUP_ID', 100)
    emit = Mock()
    monkeypatch.setattr(forum, 'emit_event', emit)
    enable(db, 'forum_notify', gid=100)
    plugin = forum.ForumNotifyPlugin.__new__(forum.ForumNotifyPlugin)
    plugin.api = Mock()
    posts = Mock()
    posts.list_unnotified_posts.return_value = [(1, 'post', 'a', None), (2, 'post', 'b', None)]
    posts.list_expired_polls.return_value = [(3, 'poll')]
    posts.close_poll.return_value = True
    plugin.dbmanager = SimpleNamespace(forum=posts)
    plugin.api.send_msg.side_effect = lambda *args: db.community.ban('group', 100)
    plugin.handle()
    assert plugin.api.send_msg.call_count == 1
    posts.mark_notified.assert_called_once_with(1)  # 已获准帖仍完成，第二帖保留
    posts.close_poll.assert_called_once_with(3)
    emit.assert_called_once()


def test_backup_maintains_images_but_suppresses_summary(management, monkeypatch):
    import plugins.backup as backup
    _, db, _, _ = management
    monkeypatch.setattr(config, 'DEFAULT_GROUP_ID', 100)
    db.community.ban('group', 100)
    db.checkin.insert(42, ['test.png'], message_id=1)
    ensure = Mock(return_value='exists')
    monkeypatch.setattr(backup, 'ensure_checkin_image', ensure)
    plugin = backup.BackupPlugin.__new__(backup.BackupPlugin)
    plugin.api, plugin.dbmanager = Mock(), db
    plugin.bot_event = SimpleNamespace(raw={'meta_event_type': 'heartbeat'})
    plugin.handle()
    ensure.assert_called_once()
    plugin.api.send_msg.assert_not_called()


def test_shop_refreshes_stock_without_blocked_announcement(management):
    from plugins.redeem_shop import ShopWeeklyRotationPlugin
    from core.message_output import MessageOutput
    from core.plugin_dispatch import Operation
    _, db, _, _ = management
    enable(db, 'redeem_shop', gid=100)
    db.community.ban('group', 100)
    sent = []
    plugin = ShopWeeklyRotationPlugin.__new__(ShopWeeklyRotationPlugin)
    plugin.dbmanager = db
    plugin.operation = Operation({'redeem_shop': True}, MessageOutput(lambda r: sent.append(r), ('group', 100)))
    plugin.handle()
    plugin.operation.finish()
    assert db.conn.execute('SELECT COUNT(*) FROM shop_stock').fetchone()[0] > 0
    assert not sent


def test_startup_suppressed_without_claiming_sent(management, monkeypatch):
    from plugins.startup_changelog import StartupChangelogPlugin
    _, db, _, _ = management
    monkeypatch.setattr(config, 'DEFAULT_GROUP_ID', 100)
    monkeypatch.setattr(context, 'DEFAULT_GROUP_ID', 100)
    monkeypatch.setattr(context, 'startup_changelog_sent', False)
    db.community.ban('group', 100)
    plugin = StartupChangelogPlugin.__new__(StartupChangelogPlugin)
    plugin.api = Mock()
    plugin.handle()
    assert not context.startup_changelog_sent
    plugin.api.send_msg.assert_not_called()
    db.community.unban('group', 100)
    plugin.handle()
    assert context.startup_changelog_sent
    plugin.api.send_msg.assert_called_once()
