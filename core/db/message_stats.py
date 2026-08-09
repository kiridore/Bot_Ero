import sqlite3


class MessageStatsManager:
    """群发言统计读写层。

    stat_date 为 08:00 日界线对齐的自然日：``(now - timedelta(hours=8)).strftime("%Y-%m-%d")``，
    与 ``get_monday_to_monday()`` 的周边界严格对齐。
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def increment_day(self, group_id, user_id, stat_date):
        self.cur.execute("""
            INSERT INTO group_daily_message_stats (stat_date, group_id, user_id, message_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(stat_date, group_id, user_id)
            DO UPDATE SET message_count = message_count + 1
        """, (stat_date, int(group_id), int(user_id)))
        self.conn.commit()

    def increment_total(self, user_id):
        self.cur.execute("""
            INSERT INTO user_total_message_count (user_id, message_count)
            VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                message_count = message_count + 1
        """, (int(user_id),))
        self.conn.commit()

    def day_count(self, group_id, user_id, stat_date) -> int:
        self.cur.execute("""
            SELECT message_count FROM group_daily_message_stats
            WHERE stat_date = ? AND group_id = ? AND user_id = ?
        """, (stat_date, int(group_id), int(user_id)))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])

    def range_stats(self, group_id, user_id, start_date, end_date_exclusive) -> tuple[int, int]:
        """返回 (消息总数, 活跃天数=distinct stat_date 数)。区间 [start, end)。"""
        self.cur.execute("""
            SELECT COALESCE(SUM(message_count), 0), COUNT(DISTINCT stat_date)
            FROM group_daily_message_stats
            WHERE group_id = ? AND user_id = ? AND stat_date >= ? AND stat_date < ?
        """, (int(group_id), int(user_id), start_date, end_date_exclusive))
        row = self.cur.fetchone()
        return (0, 0) if row is None else (int(row[0]), int(row[1]))

    def total_count(self, user_id) -> int:
        self.cur.execute("""
            SELECT message_count FROM user_total_message_count WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])
