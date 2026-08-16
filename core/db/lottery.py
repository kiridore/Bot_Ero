from datetime import datetime, timedelta
import sqlite3


class LotteryManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def draw_count(self, user_id, stat_date):
        self.cur.execute("""
            SELECT draw_count
            FROM user_lottery_daily_stats
            WHERE stat_date = ? AND user_id = ?
        """, (stat_date, int(user_id)))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])

    def add_draw(self, user_id, stat_date, inc=1):
        self.cur.execute("""
            INSERT INTO user_lottery_daily_stats (stat_date, user_id, draw_count)
            VALUES (?, ?, ?)
            ON CONFLICT(stat_date, user_id) DO UPDATE SET draw_count = draw_count + excluded.draw_count
        """, (stat_date, int(user_id), int(inc)))
        self.conn.commit()

    def add_spent(self, user_id, amount):
        self.cur.execute("""
            INSERT INTO user_lottery_stats (user_id, total_spent)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET total_spent = total_spent + excluded.total_spent
        """, (int(user_id), int(amount)))
        self.conn.commit()

    def spent(self, user_id):
        self.cur.execute("""
            SELECT total_spent
            FROM user_lottery_stats
            WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])

    def profile(self, user_id):
        self.cur.execute("""
            SELECT draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten, total_zeros
            FROM user_lottery_profile
            WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        if not row:
            return {
                "draw_count": 0,
                "duplicate_count": 0,
                "zero_streak": 0,
                "max_zero_streak": 0,
                "has_hit_ten": 0,
                "total_zeros": 0,
            }
        return {
            "draw_count": int(row[0]),
            "duplicate_count": int(row[1]),
            "zero_streak": int(row[2]),
            "max_zero_streak": int(row[3]),
            "has_hit_ten": int(row[4]),
            "total_zeros": int(row[5]),
        }

    def upsert_profile(self, user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten, total_zeros):
        self.cur.execute("""
            INSERT INTO user_lottery_profile (user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten, total_zeros)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                draw_count = excluded.draw_count,
                duplicate_count = excluded.duplicate_count,
                zero_streak = excluded.zero_streak,
                max_zero_streak = excluded.max_zero_streak,
                has_hit_ten = excluded.has_hit_ten,
                total_zeros = excluded.total_zeros
        """, (
            int(user_id),
            int(draw_count),
            int(duplicate_count),
            int(zero_streak),
            int(max_zero_streak),
            int(has_hit_ten),
            int(total_zeros),
        ))
        self.conn.commit()

    def weekly_draw_count(self, user_id, week_start_str):
        ws = datetime.strptime(week_start_str, "%Y-%m-%d %H:%M:%S")
        we = ws + timedelta(days=7)
        self.cur.execute("""
            SELECT COALESCE(SUM(draw_count), 0)
            FROM user_lottery_daily_stats
            WHERE user_id = ? AND stat_date >= ? AND stat_date < ?
        """, (int(user_id), ws.strftime("%Y-%m-%d"), we.strftime("%Y-%m-%d")))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])


    # —— 周报抽奖流水 ——

    def insert_draw_log(self, user_id, result_type, value=None, rarity=None, zero_streak_after=0):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute("""
            INSERT INTO lottery_draw_log (user_id, drawn_at, result_type, value, rarity, zero_streak_after)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (int(user_id), ts, str(result_type), value, rarity, int(zero_streak_after)))
        self.conn.commit()

    def weekly_draw_totals(self, start_date, end_date):
        """按自然日统计周内抽奖：返回 (总抽数, 参与人数)。"""
        self.cur.execute("""
            SELECT COALESCE(SUM(draw_count), 0), COUNT(DISTINCT user_id)
            FROM user_lottery_daily_stats
            WHERE stat_date >= ? AND stat_date < ?
        """, (str(start_date), str(end_date)))
        row = self.cur.fetchone()
        if not row:
            return 0, 0
        return int(row[0] or 0), int(row[1] or 0)

    def weekly_top_drawer(self, start_date, end_date):
        self.cur.execute("""
            SELECT user_id, SUM(draw_count) AS total
            FROM user_lottery_daily_stats
            WHERE stat_date >= ? AND stat_date < ?
            GROUP BY user_id
            ORDER BY total DESC, user_id ASC
            LIMIT 1
        """, (str(start_date), str(end_date)))
        row = self.cur.fetchone()
        if not row:
            return None
        return {"user_id": int(row[0]), "count": int(row[1])}

    def weekly_lucky_from_log(self, start: str, end: str) -> list[dict]:
        """周内欧皇：points=10 或 title_new 且 rarity=legendary。"""
        self.cur.execute("""
            SELECT user_id, result_type, value, rarity, COUNT(*) AS hits
            FROM lottery_draw_log
            WHERE drawn_at >= ? AND drawn_at < ?
              AND ((result_type = 'points' AND value = 10)
                   OR (result_type = 'title_new' AND rarity = 'legendary'))
            GROUP BY user_id, result_type, value, rarity
            ORDER BY hits DESC, user_id ASC
        """, (start, end))
        rows = self.cur.fetchall()
        out = []
        for user_id, result_type, value, rarity, hits in rows:
            hit = "points_10" if result_type == "points" else "legendary_title"
            out.append({
                "user_id": int(user_id),
                "hit": hit,
                "hits": int(hits),
                "title_id": value if result_type == "title_new" else None,
            })
        return out

    def weekly_unlucky_from_log(self, start: str, end: str) -> dict | None:
        """周内非酋：本周连续零奖励最长者（含跨周界的连零，按最近 draw 计算重叠段）。"""
        # 先收集所有在 [start, end) 内有抽奖记录的用户
        self.cur.execute("""
            SELECT DISTINCT user_id FROM lottery_draw_log
            WHERE drawn_at >= ? AND drawn_at < ?
        """, (start, end))
        user_ids = [int(r[0]) for r in self.cur.fetchall()]
        best = None
        for uid in user_ids:
            self.cur.execute("""
                SELECT drawn_at, result_type, value FROM lottery_draw_log
                WHERE user_id = ?
                ORDER BY drawn_at ASC, id ASC
            """, (uid,))
            rows = self.cur.fetchall()
            # 计算与 [start, end) 重叠的最长连续 points=0 段
            cur_streak = 0
            max_overlap = 0
            for drawn_at, result_type, value in rows:
                is_zero = result_type == "points" and int(value or 0) == 0
                if is_zero:
                    cur_streak += 1
                    if drawn_at < end and drawn_at >= start:
                        max_overlap = max(max_overlap, cur_streak)
                    elif drawn_at < start:
                        # 仅在窗口前累积，不在窗口内结算
                        pass
                    elif drawn_at >= end:
                        # 超出窗口；如果窗口起点仍在当前连零段内，则补算已覆盖的窗口部分
                        break
                else:
                    if drawn_at >= end:
                        break
                    cur_streak = 0
            if max_overlap > 0:
                if best is None or max_overlap > best["zero_streak"]:
                    best = {"user_id": uid, "zero_streak": max_overlap}
        return best
