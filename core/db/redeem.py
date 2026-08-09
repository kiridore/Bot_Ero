import sqlite3
from datetime import datetime


class RedeemManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def claim(self, user_id, code) -> bool:
        """原子占位：首次使用返回 True；该用户已用过返回 False。"""
        self.cur.execute(
            "INSERT OR IGNORE INTO redeem_code_usage (user_id, code, used_at) VALUES (?, ?, ?)",
            (int(user_id), code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        inserted = self.cur.rowcount > 0
        self.conn.commit()
        return inserted

    def release(self, user_id, code) -> None:
        """回调失败时回滚占位，允许用户重试。"""
        self.cur.execute(
            "DELETE FROM redeem_code_usage WHERE user_id = ? AND code = ?",
            (int(user_id), code),
        )
        self.conn.commit()
