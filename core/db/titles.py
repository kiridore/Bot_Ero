from datetime import datetime
import sqlite3


class TitlesManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def list(self, user_id):
        self.cur.execute("""
            SELECT title_id
            FROM user_titles
            WHERE user_id = ?
            ORDER BY title_id ASC
        """, (str(user_id),))
        return [row[0] for row in self.cur.fetchall()]

    def unlock(self, user_id, title_id, commit: bool = True):
        self.cur.execute("""
            INSERT OR IGNORE INTO user_titles (user_id, title_id, unlocked_at)
            VALUES (?, ?, ?)
        """, (str(user_id), int(title_id), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        inserted = self.cur.rowcount > 0
        if commit:
            self.conn.commit()
        return inserted

    def has(self, user_id, title_id):
        self.cur.execute("""
            SELECT 1
            FROM user_titles
            WHERE user_id = ? AND title_id = ?
            LIMIT 1
        """, (str(user_id), int(title_id)))
        return self.cur.fetchone() is not None

    def equipped(self, user_id):
        titles = self.equipped_all(user_id)
        if len(titles) == 0:
            return None
        return titles[0]

    def equipped_all(self, user_id):
        self.cur.execute("""
            SELECT title_id
            FROM user_equipped_titles
            WHERE user_id = ?
            ORDER BY slot ASC
        """, (str(user_id),))
        return [row[0] for row in self.cur.fetchall()]

    def equip(self, user_id, title_id, max_count=3):
        user_id = str(user_id)
        title_id = int(title_id)
        equipped = self.equipped_all(user_id)
        if title_id in equipped:
            return False, "already"
        if len(equipped) >= max_count:
            return False, "full"

        used_slots = set()
        self.cur.execute("""
            SELECT slot
            FROM user_equipped_titles
            WHERE user_id = ?
        """, (user_id,))
        for row in self.cur.fetchall():
            used_slots.add(int(row[0]))

        slot = 1
        while slot in used_slots:
            slot += 1

        self.cur.execute("""
            INSERT INTO user_equipped_titles (user_id, slot, title_id)
            VALUES (?, ?, ?)
        """, (user_id, slot, title_id))
        self.conn.commit()
        return True, "ok"

    def clear_equipped(self, user_id):
        self.cur.execute("""
            DELETE FROM user_equipped_titles
            WHERE user_id = ?
        """, (str(user_id),))
        self.conn.commit()

    def set_equipped(self, user_id, title_id):
        user_id = str(user_id)
        self.clear_equipped(user_id)
        if title_id is not None:
            self.equip(user_id, int(title_id), max_count=3)
