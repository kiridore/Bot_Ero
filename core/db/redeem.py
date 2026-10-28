import sqlite3
from datetime import datetime


class RedeemManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def claim_in_transaction(self, user_id, code) -> bool:
        """事务内原子占位：首次使用返回 True；该用户已用过返回 False。

        调用方负责提交/回滚——占位与奖励发放必须同事务，失败整体回滚
        （redeem-code-web：取代旧 claim/release 两段式，中途崩溃不再留脏占位）。
        """
        self.cur.execute(
            "INSERT OR IGNORE INTO redeem_code_usage (user_id, code, used_at) VALUES (?, ?, ?)",
            (int(user_id), code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        return self.cur.rowcount > 0

    def history(self, user_id) -> list[tuple]:
        self.cur.execute(
            "SELECT code, used_at FROM redeem_code_usage"
            " WHERE user_id = ? ORDER BY used_at DESC, code",
            (int(user_id),),
        )
        return self.cur.fetchall()
