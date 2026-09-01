"""日历展开逻辑（webapp.alarms.alarm_service.calendar_month）进程内测试。

conftest 已将 BOTERO_DB_PATH 重定向到会话临时库；resolve_display_name 打桩避免真实 HTTP。
"""

import unittest
from datetime import datetime, timedelta
from calendar import monthrange

from core.database_manager import DbManager
import webapp.alarms.alarm_service as alarm_service

alarm_service.resolve_display_name = lambda uid: f"用户{uid}"


def _month_of(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


class CalendarExpandTest(unittest.TestCase):
    def setUp(self):
        db = DbManager()
        db.cur.execute("DELETE FROM group_alarms")
        db.conn.commit()
        self.me, self.other = "10001", "10002"

    def _add(self, uid, fire, content, recur=None, is_private=True, group_id=None):
        db = DbManager()
        return db.alarm.add(int(uid), fire, content, group_id=group_id, is_private=is_private, recur=recur)

    def test_single_shot_lands_on_day(self):
        fire = datetime.now() + timedelta(minutes=30)
        self._add(self.me, fire, "单次")
        data = alarm_service.calendar_month(self.me, _month_of(fire))
        key = fire.strftime("%Y-%m-%d")
        self.assertIn(key, data["days"])
        item = data["days"][key][0]
        self.assertEqual(item["time"], fire.strftime("%H:%M"))
        self.assertTrue(item["is_mine"])
        self.assertEqual(item["scope"], "private")
        self.assertFalse(item["is_recurring"])

    def test_daily_recurring_no_history(self):
        fire = (datetime.now() + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        self._add(self.me, fire, "吃药", recur=(1, 1, 0, 0))
        data = alarm_service.calendar_month(self.me, _month_of(fire))
        tomorrow = fire.strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertIn(tomorrow, data["days"])  # 从 fire_at 向前展开
        self.assertNotIn(today, data["days"])  # 历史不回溯
        if (fire + timedelta(days=1)).month == fire.month:
            self.assertIn((fire + timedelta(days=1)).strftime("%Y-%m-%d"), data["days"])

    def test_weekly_steps_seven_days(self):
        now = datetime.now()
        delta = (2 - now.weekday()) % 7 or 7  # 下一个周三，至少明天
        fire = (now + timedelta(days=delta)).replace(hour=9, minute=30, second=0, microsecond=0)
        self._add(self.me, fire, "周会", recur=(2, 3, 0, 0))
        data = alarm_service.calendar_month(self.me, _month_of(fire))
        self.assertIn(fire.strftime("%Y-%m-%d"), data["days"])
        nxt = fire + timedelta(days=7)
        if nxt.month == fire.month:
            self.assertIn(nxt.strftime("%Y-%m-%d"), data["days"])

    def test_monthly_clamps_short_next_month(self):
        # 找一个「31 天月且下月不足 31 天」的未来月份
        y, m = datetime.now().year, datetime.now().month
        for _ in range(24):
            if monthrange(y, m)[1] == 31 and monthrange(y + (m == 12), m % 12 + 1)[1] < 31:
                break
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        fire = datetime(y, m, 31, 12, 0)
        if fire <= datetime.now():  # 保险：再推一年
            fire = datetime(y + 1, m, 31, 12, 0)
            y += 1
        self._add(self.me, fire, "月末", recur=(4, 31, 0, 0))
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        data = alarm_service.calendar_month(self.me, f"{ny:04d}-{nm:02d}")
        clamped = f"{ny:04d}-{nm:02d}-{monthrange(ny, nm)[1]:02d}"
        self.assertIn(clamped, data["days"])  # 31 → 下月末钳位

    def test_yearly_clamps_feb29(self):
        y = datetime.now().year + 1
        while not (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)):
            y += 1
        fire = datetime(y, 2, 29, 12, 0)
        self._add(self.me, fire, "四年一度", recur=(3, 2, 29, 0))
        data = alarm_service.calendar_month(self.me, f"{y + 1}-02")
        self.assertIn(f"{y + 1}-02-28", data["days"])  # 2/29 → 次年 2/28 钳位

    def test_fire_next_month_leaves_current_empty(self):
        now = datetime.now()
        ny, nm = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
        fire = datetime(ny, nm, 15, 10, 0)
        self._add(self.me, fire, "每天", recur=(1, 1, 0, 0))
        data = alarm_service.calendar_month(self.me, now.strftime("%Y-%m"))
        self.assertEqual(data["days"], {})  # fire_at 在下月 → 本月无条目

    def test_privacy_others_private_hidden(self):
        fire = datetime.now() + timedelta(hours=2)
        key = fire.strftime("%Y-%m-%d")
        self._add(self.other, fire, "别人的私聊", recur=None, is_private=True)
        self._add(self.other, fire.replace(minute=30), "别人的群", recur=None, is_private=False, group_id=123)
        data = alarm_service.calendar_month(self.me, _month_of(fire))
        contents = [it["content"] for it in data["days"].get(key, [])]
        self.assertNotIn("别人的私聊", contents)  # 他人私聊永不下发
        self.assertIn("别人的群", contents)
        other_item = next(it for it in data["days"][key] if it["content"] == "别人的群")
        self.assertFalse(other_item["is_mine"])
        self.assertEqual(other_item["scope"], "group")
        self.assertEqual(other_item["creator_name"], f"用户{self.other}")

    def test_sorted_by_time(self):
        fire = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        self._add(self.me, fire.replace(hour=20), "晚")
        self._add(self.me, fire.replace(hour=8), "早")
        data = alarm_service.calendar_month(self.me, _month_of(fire))
        items = data["days"][fire.strftime("%Y-%m-%d")]
        self.assertEqual([i["content"] for i in items], ["早", "晚"])


class UpdateAlarmTest(unittest.TestCase):
    def setUp(self):
        db = DbManager()
        db.cur.execute("DELETE FROM group_alarms")
        db.conn.commit()
        self.me, self.other = "10001", "10002"

    def test_update_recomputes_rule_and_keeps_id(self):
        fire = datetime.now() + timedelta(days=1)
        db = DbManager()  # 持有引用：临时 DbManager 链式取属性后 __del__ 会提前关连接
        aid = db.alarm.add(int(self.me), fire, "旧内容")
        new_fire = datetime.now() + timedelta(days=2)
        out = alarm_service.update_alarm(self.me, aid, {
            "content": "新内容", "schedule_type": "once_date",
            "date": new_fire.strftime("%Y-%m-%d"), "time": "09:30",
            "scope": "private",
        })
        self.assertEqual(out["id"], aid)  # 编号不变
        db = DbManager()
        db.cur.execute(
            "SELECT content, fire_at, is_private FROM group_alarms WHERE id = ?", (aid,))
        content, fire_at, is_priv = db.cur.fetchone()
        self.assertEqual(content, "新内容")
        self.assertTrue(fire_at.startswith(new_fire.strftime("%Y-%m-%d")))
        self.assertEqual(int(is_priv), 1)

    def test_scope_flip_group_to_private(self):
        fire = datetime.now() + timedelta(days=1)
        db = DbManager()
        aid = db.alarm.add(int(self.me), fire, "群", group_id=123, is_private=False)
        alarm_service.update_alarm(self.me, aid, {
            "content": "群", "schedule_type": "once_date",
            "date": fire.strftime("%Y-%m-%d"), "time": "20:00", "scope": "private",
        })
        db = DbManager()
        db.cur.execute("SELECT is_private, group_id FROM group_alarms WHERE id = ?", (aid,))
        is_priv, gid = db.cur.fetchone()
        self.assertEqual((int(is_priv), int(gid)), (1, 0))

    def test_non_creator_rejected(self):
        fire = datetime.now() + timedelta(days=1)
        db = DbManager()
        aid = db.alarm.add(int(self.other), fire, "别人的")
        with self.assertRaises(ValueError):
            alarm_service.update_alarm(self.me, aid, {
                "content": "改", "schedule_type": "once_today", "time": "23:50",
            })


if __name__ == "__main__":
    unittest.main()
