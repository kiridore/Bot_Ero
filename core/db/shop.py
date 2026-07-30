from datetime import datetime, timedelta
import sqlite3


class ShopManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def ensure_stock(self, product_id: str, default_stock: int):
        self.cur.execute("""
            INSERT OR IGNORE INTO shop_stock (product_id, stock)
            VALUES (?, ?)
        """, (str(product_id), int(default_stock)))
        self.conn.commit()

    def stock(self, product_id: str):
        self.cur.execute("""
            SELECT stock FROM shop_stock WHERE product_id = ?
        """, (str(product_id),))
        row = self.cur.fetchone()
        return None if row is None else int(row[0])

    def all_stock(self):
        self.cur.execute("""
            SELECT product_id, stock FROM shop_stock
            ORDER BY product_id ASC
        """)
        return [(str(row[0]), int(row[1])) for row in self.cur.fetchall()]

    def replace_shelf(self, product_stocks: dict[str, int]):
        self.cur.execute("BEGIN IMMEDIATE")
        try:
            self.cur.execute("DELETE FROM shop_stock")
            for pid, stock in product_stocks.items():
                self.cur.execute("""
                    INSERT INTO shop_stock (product_id, stock)
                    VALUES (?, ?)
                """, (str(pid), int(stock)))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def ensure_buff(self, user_id: int, commit: bool = True):
        self.cur.execute("""
            INSERT OR IGNORE INTO shop_user_buffs (
                user_id, checkin_luck_remaining, lottery_waiver_remaining
            )
            VALUES (?, 0, 0)
        """, (int(user_id),))
        if commit:
            self.conn.commit()

    def set_draw_pack(self, user_id: int, until_date_str: str, commit: bool = True):
        self.ensure_buff(user_id, commit=False)
        self.cur.execute("""
            UPDATE shop_user_buffs SET extra_draw_pack_until = ?
            WHERE user_id = ?
        """, (str(until_date_str), int(user_id)))
        if commit:
            self.conn.commit()

    def draw_bonus(self, user_id: int, today_str: str) -> int:
        self.cur.execute("""
            SELECT extra_draw_pack_until FROM shop_user_buffs WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        if not row or row[0] is None:
            return 0
        until = str(row[0]).strip()
        if len(until) >= 10:
            until = until[:10]
        if today_str <= until:
            return 2
        return 0

    def add_luck(self, user_id: int, delta: int, commit: bool = True):
        self.ensure_buff(user_id, commit=False)
        d = int(delta)
        self.cur.execute("""
            UPDATE shop_user_buffs SET checkin_luck_remaining = checkin_luck_remaining + ?
            WHERE user_id = ?
        """, (d, int(user_id)))
        if commit:
            self.conn.commit()

    def luck_remaining(self, user_id: int) -> int:
        self.cur.execute("""
            SELECT checkin_luck_remaining FROM shop_user_buffs WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        return 0 if not row or row[0] is None else int(row[0])

    def pop_luck(self, user_id: int, commit: bool = True) -> bool:
        self.cur.execute("""
            UPDATE shop_user_buffs SET checkin_luck_remaining = checkin_luck_remaining - 1
            WHERE user_id = ? AND checkin_luck_remaining > 0
        """, (int(user_id),))
        ok = self.cur.rowcount > 0
        if commit:
            self.conn.commit()
        return ok

    def add_waiver(self, user_id: int, delta: int, commit: bool = True):
        self.ensure_buff(user_id, commit=False)
        self.cur.execute("""
            UPDATE shop_user_buffs SET lottery_waiver_remaining = lottery_waiver_remaining + ?
            WHERE user_id = ?
        """, (int(delta), int(user_id)))
        if commit:
            self.conn.commit()

    def waiver_remaining(self, user_id: int) -> int:
        self.cur.execute("""
            SELECT lottery_waiver_remaining FROM shop_user_buffs WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        return 0 if not row or row[0] is None else int(row[0])

    def pop_waiver(self, user_id: int, commit: bool = True) -> bool:
        self.cur.execute("""
            UPDATE shop_user_buffs SET lottery_waiver_remaining = lottery_waiver_remaining - 1
            WHERE user_id = ? AND lottery_waiver_remaining > 0
        """, (int(user_id),))
        ok = self.cur.rowcount > 0
        if commit:
            self.conn.commit()
        return ok

    def clear_draw_count(self, user_id: int, stat_date: str, commit: bool = True):
        self.cur.execute("""
            DELETE FROM user_lottery_daily_stats WHERE user_id = ? AND stat_date = ?
        """, (int(user_id), str(stat_date)))
        if commit:
            self.conn.commit()

    def redeem(self, product_id: str, user_id, cost: int, grant_fn) -> tuple:
        product_id = str(product_id)
        user_id_s = str(user_id)
        cost = int(cost)
        self.cur.execute("BEGIN IMMEDIATE")
        try:
            self.cur.execute(
                "INSERT OR IGNORE INTO user_assets (user_id, points) VALUES (?, 0)",
                (user_id_s,),
            )
            self.cur.execute("SELECT points FROM user_assets WHERE user_id = ?", (user_id_s,))
            row = self.cur.fetchone()
            points = 0 if row is None or row[0] is None else int(row[0])
            if points < cost:
                self.conn.rollback()
                return False, "积分不足"

            self.cur.execute("SELECT stock FROM shop_stock WHERE product_id = ?", (product_id,))
            srow = self.cur.fetchone()
            if srow is None:
                self.conn.rollback()
                return False, "商品不存在"
            stock = int(srow[0])
            if stock == 0:
                self.conn.rollback()
                return False, "库存不足"
            if stock > 0:
                self.cur.execute(
                    "UPDATE shop_stock SET stock = stock - 1 WHERE product_id = ? AND stock > 0",
                    (product_id,),
                )
                if self.cur.rowcount == 0:
                    self.conn.rollback()
                    return False, "库存不足"
            elif stock != -1:
                self.conn.rollback()
                return False, "库存数据异常"

            self.cur.execute(
                "UPDATE user_assets SET points = points - ? WHERE user_id = ? AND points >= ?",
                (cost, user_id_s, cost),
            )
            if self.cur.rowcount == 0:
                self.conn.rollback()
                return False, "积分不足"
            try:
                grant_fn()
            except Exception as e:
                self.conn.rollback()
                return False, str(e) or "发放失败"
            self.conn.commit()
            return True, "ok"
        except Exception as e:
            self.conn.rollback()
            return False, str(e) or "兑换失败"
