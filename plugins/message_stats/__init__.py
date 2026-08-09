from datetime import datetime, timedelta

from core.base import Plugin, BOT_QQ
from core.cq import text, at
from core.logger import logger
from core.utils import register_plugin, get_monday_to_monday
from plugins.title import evaluate_and_unlock_titles
from plugins.title.defs import TITLE_DEFS

# (统计键, 阈值, 称号 ID)，模块级便于测试 monkeypatch
MESSAGE_TITLE_THRESHOLDS = [
    ("day_count", 100, 401),
    ("day_count", 300, 402),
    ("week_count", 300, 403),
    ("week_active_days", 5, 404),
    ("month_count", 1000, 405),
    ("month_active_days", 28, 406),
    ("year_count", 10000, 407),
    ("year_active_days", 300, 408),
    ("total_count", 10000, 409),
    ("total_count", 50000, 410),
]


def _stat_date(now: datetime) -> str:
    """08:00 日界线对齐的自然日，与 get_monday_to_monday 的周边界严格对齐。"""
    return (now - timedelta(hours=8)).strftime("%Y-%m-%d")


def _period_windows(now: datetime) -> tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]]:
    """返回 (今日, 本周, 本月, 今年) 的 [start, end) 半开区间，日期为 "YYYY-MM-DD"。"""
    d = _stat_date(now)
    day = (d, (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d"))
    ws, we = get_monday_to_monday()
    week = (ws.split()[0], we.split()[0])
    ms = (now - timedelta(hours=8)).replace(day=1)
    if ms.month == 12:
        nm = ms.replace(year=ms.year + 1, month=1)
    else:
        nm = ms.replace(month=ms.month + 1)
    month = (ms.strftime("%Y-%m-%d"), nm.strftime("%Y-%m-%d"))
    y = (now - timedelta(hours=8)).year
    year = (f"{y:04d}-01-01", f"{y + 1:04d}-01-01")
    return day, week, month, year


def evaluate_message_titles(dbmanager, user_id, group_id) -> list[int]:
    """按当前群统计求值发言活跃称号；阈值单调，无需等周期结算，解锁幂等。"""
    uid = int(user_id)
    gid = int(group_id)
    now = datetime.now()
    day, week, month, year = _period_windows(now)
    d = day[0]
    stats = {
        "day_count": dbmanager.message_stats.day_count(gid, uid, d),
        "week_count": dbmanager.message_stats.range_stats(gid, uid, *week)[0],
        "week_active_days": dbmanager.message_stats.range_stats(gid, uid, *week)[1],
        "month_count": dbmanager.message_stats.range_stats(gid, uid, *month)[0],
        "month_active_days": dbmanager.message_stats.range_stats(gid, uid, *month)[1],
        "year_count": dbmanager.message_stats.range_stats(gid, uid, *year)[0],
        "year_active_days": dbmanager.message_stats.range_stats(gid, uid, *year)[1],
        "total_count": dbmanager.message_stats.total_count(uid),
    }
    newly = []
    for key, threshold, tid in MESSAGE_TITLE_THRESHOLDS:
        if stats[key] >= threshold and not dbmanager.titles.has(uid, tid):
            if dbmanager.titles.unlock(uid, tid):
                newly.append(tid)
    if newly:
        evaluate_and_unlock_titles(dbmanager, uid)  # 级联进度称号（222-226 称号收藏家等）
    return newly


@register_plugin
class MessageStatsPlugin(Plugin):
    name = "message_stats"
    description = "统计群友每日/每周/每月/每年发言量与活跃天数，达标解锁发言活跃称号。"

    def match(self, event_type="message") -> bool:
        if event_type != "message":
            return False
        gid = self.bot_event.group_id
        uid = self.bot_event.user_id
        if gid is not None and uid is not None and str(uid) != BOT_QQ:
            return True  # 群消息：计数（计数在 handle 中，match 无副作用）
        return self._is_stats_command()  # 指令：查询

    def handle(self):
        try:
            gid = self.bot_event.group_id
            uid = self.bot_event.user_id
            if gid is not None and uid is not None and str(uid) != BOT_QQ:
                self._count_and_eval(gid, uid)
            if self._is_stats_command():
                self._reply_stats()
        except Exception:
            logger.exception("message_stats 处理失败")

    def _first_text(self) -> str:
        for seg in self.bot_event.message:
            if seg.get("type") == "text":
                return seg.get("data", {}).get("text", "").strip()
        return ""

    def _is_stats_command(self) -> bool:
        parts = self._first_text().split()
        return bool(parts) and parts[0] in ("/发言统计", "/發言統計")

    def _count_and_eval(self, gid, uid):
        d = _stat_date(datetime.now())
        self.dbmanager.message_stats.increment_day(gid, uid, d)
        self.dbmanager.message_stats.increment_total(uid)
        newly = evaluate_message_titles(self.dbmanager, uid, gid)
        if newly:
            lines = ["解锁新称号："]
            for tid in newly:
                lines.append(f"[{tid}] 「{TITLE_DEFS[tid]['name']}」")
            self.api.send_msg(at(uid), text("\n".join(lines)))

    def _target_user_id_from_at(self):
        for seg in self.bot_event.message:
            if seg.get("type") == "at":
                qq = seg.get("data", {}).get("qq")
                if qq and qq != "all":
                    return int(qq)
        return None

    def _sender_display_name(self) -> str:
        sender = self.bot_event.sender
        if sender and isinstance(sender, dict):
            return sender.get("card") or sender.get("nickname") or f"QQ{self.bot_event.user_id}"
        return f"QQ{self.bot_event.user_id}"

    def _reply_stats(self):
        if self.bot_event.group_id is None:
            self.api.send_msg(text("本指令需在群内使用喵"))
            return
        gid = self.bot_event.group_id
        target = self._target_user_id_from_at()
        if target is None:
            if self.bot_event.user_id is None:
                return
            target = self.bot_event.user_id
        uid = int(target)
        day, week, month, year = _period_windows(datetime.now())
        day_count = self.dbmanager.message_stats.day_count(gid, uid, day[0])
        week_count, week_days = self.dbmanager.message_stats.range_stats(gid, uid, *week)
        month_count, month_days = self.dbmanager.message_stats.range_stats(gid, uid, *month)
        year_count, year_days = self.dbmanager.message_stats.range_stats(gid, uid, *year)
        total = self.dbmanager.message_stats.total_count(uid)
        day_active = 1 if day_count > 0 else 0
        name = self._sender_display_name()
        reply = (
            f"{name} 的发言统计（本群）\n"
            f"今日：{day_count} 条 | 活跃 {day_active} 天\n"
            f"本周：{week_count} 条 | 活跃 {week_days} 天\n"
            f"本月：{month_count} 条 | 活跃 {month_days} 天\n"
            f"今年：{year_count} 条 | 活跃 {year_days} 天\n"
            f"累计：{total} 条（全群）"
        )
        self.api.send_msg(text(reply))
