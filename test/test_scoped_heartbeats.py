"""config-unification 任务组3：心跳按部署许可与所属群/账号过滤（AC03）。

直接驱动真实插件的到期扫描；所有数据在临时 DB。
"""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import config
from core import context as runtime_context
from core.database_manager import DbManager


class _HeartbeatCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = config.DB_PATH
        config.DB_PATH = Path(self._tmp.name) / "hb.db"
        self._old_allowed = runtime_context.ALLOWED_PLUGINS
        self.db = DbManager()
        self.api = Mock()

    def tearDown(self):
        self.db.conn.close()
        config.DB_PATH = self._old_db
        runtime_context.ALLOWED_PLUGINS = self._old_allowed
        self._tmp.cleanup()

    def _enable(self, plugin, group_id=None, user_id=None):
        if group_id is not None:
            self.db.conn.execute(
                "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)",
                (group_id, plugin))
        else:
            self.db.conn.execute(
                "INSERT OR IGNORE INTO user_plugin_config (user_id, plugin_name, enabled) VALUES (?, ?, 1)",
                (user_id, plugin))
        self.db.conn.commit()

    def _group_id(self):
        return int(config.DEFAULT_GROUP_ID) if config.DEFAULT_GROUP_ID else 424242


class AlarmScopeTest(_HeartbeatCase):
    def _run(self):
        from plugins.group_alarm import GroupAlarmPlugin
        p = GroupAlarmPlugin.__new__(GroupAlarmPlugin)
        p.dbmanager, p.api = self.db, self.api
        p._handle_meta_due()

    def _fired(self, aid):
        return self.db.conn.execute("SELECT fired FROM group_alarms WHERE id=?", (aid,)).fetchone()[0]

    def test_due_alarm_only_fires_for_enabled_scope(self):
        past = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        on = self.db.alarm.add(7, datetime.now() - timedelta(minutes=5), "群内提醒", group_id=100)
        off = self.db.alarm.add(7, datetime.now() - timedelta(minutes=5), "别群提醒", group_id=200)
        priv_on = self.db.alarm.add(8, datetime.now() - timedelta(minutes=5), "私聊提醒", is_private=True)
        self._enable("group_alarm", group_id=100)
        self._enable("group_alarm", user_id=8)
        self.db.conn.execute("UPDATE group_alarms SET fire_at=? ", (past,))
        self.db.conn.commit()
        self._run()
        self.assertEqual(self._fired(on), 1)
        self.assertEqual(self._fired(off), 0)     # 不发送、不标记
        self.assertEqual(self._fired(priv_on), 1)
        groups_sent = [c.args[1]["group_id"] for c in self.api.call_api.call_args_list
                       if c.args[0] == "send_group_msg"]
        self.assertEqual(groups_sent, [100])
        privs_sent = [c.args[1]["user_id"] for c in self.api.call_api.call_args_list
                      if c.args[0] == "send_private_msg"]
        self.assertEqual(privs_sent, [8])

    def test_recurring_alarm_not_advanced_when_disabled(self):
        self.db.alarm.add(7, datetime.now() - timedelta(days=8), "每周提醒", group_id=300,
                          recur=(2, 1, 0, 0))  # 每周循环
        self._run()  # 300 群未启用
        row = self.db.conn.execute(
            "SELECT fired, fire_at FROM group_alarms WHERE group_id=300").fetchone()
        self.assertEqual(row[0], 0)
        self._enable("group_alarm", group_id=300)
        self._run()  # 重新开启后按原到期规则处理积压
        row2 = self.db.conn.execute(
            "SELECT fired, recur_kind FROM group_alarms WHERE group_id=300").fetchone()
        self.assertIn(row2[0], (0, 1))  # 循环闹钟触发后推进而非置 fired
        self.assertEqual(row2[1], 2)
        fired_any = self.api.call_api.call_args_list  # 已产生发送
        self.assertTrue(fired_any)

    def test_deployment_forbidden_alarm_never_fires(self):
        runtime_context.ALLOWED_PLUGINS = frozenset({"menu"})
        self.db.alarm.add(7, datetime.now() - timedelta(minutes=5), "提醒", group_id=100)
        self._enable("group_alarm", group_id=100)  # 局部开启不能突破部署禁止
        self._run()
        self.assertEqual(
            self.db.conn.execute("SELECT fired FROM group_alarms").fetchone()[0], 0)


class ActivityScopeTest(_HeartbeatCase):
    def _run(self):
        from plugins.activity import ActivityTimerPlugin
        p = ActivityTimerPlugin.__new__(ActivityTimerPlugin)
        p.dbmanager, p.api = self.db, self.api
        p._scan()

    def _add_activity(self, gid):
        self.db.conn.execute(
            """INSERT INTO activities (group_id, type, title, status, created_by,
               signup_deadline, created_at) VALUES (?, 'match', 't', 'open', '1', ?, ?)""",
            (gid, (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.db.conn.commit()
        return self.db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_signup_deadline_only_processed_for_enabled_group(self):
        a_on = self._add_activity(100)
        a_off = self._add_activity(200)
        self._enable("activity", group_id=100)
        self._run()
        st_on = self.db.conn.execute("SELECT status FROM activities WHERE id=?", (a_on,)).fetchone()[0]
        st_off = self.db.conn.execute("SELECT status FROM activities WHERE id=?", (a_off,)).fetchone()[0]
        self.assertNotEqual(st_on, "open")        # 已开始或因人数不足取消：状态推进
        self.assertEqual(st_off, "open")          # 关闭群：状态不动


class ImmortalScopeTest(_HeartbeatCase):
    def _run(self):
        from plugins.immortal_lottery import ImmortalLotteryPlugin
        p = ImmortalLotteryPlugin.__new__(ImmortalLotteryPlugin)
        p.dbmanager, p.api = self.db, self.api
        p._handle_draw_tick()

    def test_disabled_group_not_settled_and_bets_kept(self):
        from plugins.immortal_lottery.helpers import _sunday_draw_period_monday, _period_key_from_monday
        from plugins.immortal_lottery import _now_bj
        pk = _period_key_from_monday(_sunday_draw_period_monday(_now_bj().date()))
        for gid in (100, 200):
            self.db.conn.execute(
                "INSERT INTO immortal_lottery_bets (group_id, period_key, user_id, digits, bet_bj_date, created_at)"
                " VALUES (?, ?, 5, '1234', '2026-01-01', ?)",
                (gid, pk, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.db.conn.commit()
        self._enable("immortal_lottery", group_id=100)
        self._run()
        results = {row[0] for row in self.db.conn.execute(
            "SELECT group_id FROM immortal_lottery_results").fetchall()}
        self.assertIn(100, results)
        self.assertNotIn(200, results)  # 未开奖
        kept = self.db.conn.execute(
            "SELECT COUNT(*) FROM immortal_lottery_bets WHERE group_id=200").fetchone()[0]
        self.assertEqual(kept, 1)       # 已付注单保留，不退款不清空


class AnnouncementScopeTest(_HeartbeatCase):
    def test_shop_refreshes_but_no_announcement_when_target_group_off(self):
        from plugins.redeem_shop import ShopWeeklyRotationPlugin
        from core.message_output import MessageOutput
        target = self._group_id()
        sent = []
        p = ShopWeeklyRotationPlugin.__new__(ShopWeeklyRotationPlugin)
        p.dbmanager, p.api = self.db, self.api
        p.operation = Mock()
        p.operation.output = MessageOutput(lambda r: sent.append(r) or 1, ("group", target))
        p.submit_message = lambda *a: sent.append(a)
        p.handle()
        shelf = self.db.conn.execute("SELECT COUNT(*) FROM shop_stock").fetchone()
        self.assertGreater(shelf[0], 0)   # 货架照常刷新（固定功能商品至少入库）
        self.assertEqual(sent, [])        # 目标群未启用：不发公告
        self._enable("redeem_shop", group_id=target)
        p.handle()
        self.assertTrue(sent)             # 启用后照常公告

    def test_ff_news_skips_fetch_without_effective_target(self):
        from plugins.ff_news import FfNewsPlugin
        self._enable("ff_news", group_id=self._group_id())
        p = FfNewsPlugin.__new__(FfNewsPlugin)
        p.dbmanager, p.api = self.db, self.api
        p._fetch_payload = Mock()
        p._handle_hourly()
        p._fetch_payload.assert_called_once()  # 目标群开启：照常抓取
        p2 = FfNewsPlugin.__new__(FfNewsPlugin)
        p2.dbmanager, p2.api = self.db, self.api
        p2._fetch_payload = Mock()
        self.db.conn.execute("DELETE FROM group_plugin_config WHERE plugin_name='ff_news'")
        self.db.conn.commit()
        p2._handle_hourly()
        p2._fetch_payload.assert_not_called()  # 关闭：不请求官网

    def test_forum_posts_not_marked_when_target_group_off(self):
        from plugins.forum_notify import ForumNotifyPlugin
        target = self._group_id()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.conn.execute(
            "INSERT INTO forum_posts (author_user_id, type, title, body_json, created_at, updated_at)"
            " VALUES ('1', 'post', '新帖', '', ?, ?)", (now, now))
        self.db.conn.commit()
        p = ForumNotifyPlugin.__new__(ForumNotifyPlugin)
        p.dbmanager, p.api = self.db, self.api
        p.handle()
        self.api.send_msg.assert_not_called()
        self.assertIsNone(self.db.conn.execute(
            "SELECT notified_at FROM forum_posts").fetchone()[0])  # 未标记已通知
        self._enable("forum_notify", group_id=target)
        p.handle()
        self.api.send_msg.assert_called()
        self.assertIsNotNone(self.db.conn.execute(
            "SELECT notified_at FROM forum_posts").fetchone()[0])

    def test_weekly_report_skipped_when_target_group_off(self):
        from plugins.weekly_report import WeeklyReportPlugin
        target = self._group_id()
        p = WeeklyReportPlugin.__new__(WeeklyReportPlugin)
        p.dbmanager, p.api = self.db, self.api
        p._generate_week("2026-01-05 08:00:00", "2026-01-12 08:00:00")
        self.assertEqual(self.db.conn.execute(
            "SELECT COUNT(*) FROM weekly_reports").fetchone()[0], 0)  # 未生成
        self.api.send_msg.assert_not_called()
        self._enable("weekly_report", group_id=target)
        p._generate_week("2026-01-05 08:00:00", "2026-01-12 08:00:00")
        # 无消息数据时允许生成空周报行，但不得向目标群发送
        self.api.send_msg.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
