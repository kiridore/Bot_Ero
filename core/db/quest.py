from datetime import datetime
import sqlite3


class QuestManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def upsert_progress(self, user_id, quest_id, week_key, progress, *, commit=True):
        self.cur.execute("""
            INSERT INTO quest_progress (user_id, quest_id, week_key, progress)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, quest_id, week_key) DO UPDATE SET progress = excluded.progress
        """, (str(user_id), int(quest_id), str(week_key), int(progress)))
        if commit:
            self.conn.commit()

    def claim_reward(self, user_id, quest_id, week_key, *, commit=True):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute("""
            UPDATE quest_progress SET completed = 1, claimed_at = ?
            WHERE user_id = ? AND quest_id = ? AND week_key = ? AND claimed_at IS NULL
        """, (now, str(user_id), int(quest_id), str(week_key)))
        ok = self.cur.rowcount > 0
        if commit:
            self.conn.commit()
        return ok

    def revoke_reward(self, user_id, quest_id, week_key, *, commit=True):
        self.cur.execute("""
            UPDATE quest_progress SET completed = 0, claimed_at = NULL
            WHERE user_id = ? AND quest_id = ? AND week_key = ? AND claimed_at IS NOT NULL
        """, (str(user_id), int(quest_id), str(week_key)))
        ok = self.cur.rowcount > 0
        if commit:
            self.conn.commit()
        return ok

    def progress(self, user_id, week_key):
        self.cur.execute("""
            SELECT quest_id, progress, completed FROM quest_progress
            WHERE user_id = ? AND week_key = ?
        """, (str(user_id), str(week_key)))
        return {row[0]: {"progress": row[1], "completed": row[2]} for row in self.cur.fetchall()}

    def cleanup_old(self, current_week_key):
        self.cur.execute("DELETE FROM quest_progress WHERE week_key < ?", (str(current_week_key),))
        self.conn.commit()

    def increment_completion(self, user_id, *, commit=True):
        self.cur.execute("""
            INSERT INTO quest_completion_stats (user_id, total_completions) VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET total_completions = total_completions + 1
        """, (str(user_id),))
        if commit:
            self.conn.commit()

    def completion(self, user_id):
        self.cur.execute("SELECT total_completions FROM quest_completion_stats WHERE user_id = ?", (str(user_id),))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])

    def record_clear(self, user_id, week_key, *, commit=True):
        self.cur.execute("""
            INSERT OR IGNORE INTO quest_weekly_clears (user_id, week_key, cleared_at)
            VALUES (?, ?, ?)
        """, (str(user_id), str(week_key), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        ok = self.cur.rowcount > 0
        if commit:
            self.conn.commit()
        return ok

    def clear_count(self, user_id):
        self.cur.execute("SELECT COUNT(*) FROM quest_weekly_clears WHERE user_id = ?", (str(user_id),))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])
