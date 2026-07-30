from datetime import datetime
import secrets
import sqlite3


class ImmortalManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def issue_code(self, group_id: int, period_key: str) -> str:
        gid = int(group_id)
        pk = str(period_key)
        self.cur.execute(
            "SELECT issue_code FROM immortal_lottery_issue WHERE group_id = ? AND period_key = ?",
            (gid, pk),
        )
        row = self.cur.fetchone()
        if row and row[0]:
            return str(row[0])
        compact = pk.replace("-", "")
        for _ in range(48):
            tail = secrets.token_hex(4).upper()
            code = f"XR-{compact}-{tail}"
            self.cur.execute(
                """
                INSERT OR IGNORE INTO immortal_lottery_issue (group_id, period_key, issue_code)
                VALUES (?, ?, ?)
                """,
                (gid, pk, code),
            )
            if self.cur.rowcount > 0:
                self.conn.commit()
                return code
            self.cur.execute(
                "SELECT issue_code FROM immortal_lottery_issue WHERE group_id = ? AND period_key = ?",
                (gid, pk),
            )
            row2 = self.cur.fetchone()
            if row2 and row2[0]:
                return str(row2[0])
        raise RuntimeError("immortal_lottery: failed to allocate issue_code")

    def ensure_carry(self, group_id: int, commit: bool = True):
        self.cur.execute(
            """
            INSERT OR IGNORE INTO immortal_lottery_carry (group_id, carry_4a, carry_3a, carry_2a)
            VALUES (?, 0, 0, 0)
            """,
            (int(group_id),),
        )
        if commit:
            self.conn.commit()

    def carry(self, group_id: int) -> tuple[int, int, int]:
        self.cur.execute(
            "SELECT carry_4a, carry_3a, carry_2a FROM immortal_lottery_carry WHERE group_id = ?",
            (int(group_id),),
        )
        row = self.cur.fetchone()
        if not row:
            return (0, 0, 0)
        return (int(row[0] or 0), int(row[1] or 0), int(row[2] or 0))

    def set_carry(
        self, group_id: int, carry_4a: int, carry_3a: int, carry_2a: int, commit: bool = True
    ):
        self.ensure_carry(group_id, commit=False)
        self.cur.execute(
            """
            UPDATE immortal_lottery_carry
            SET carry_4a = ?, carry_3a = ?, carry_2a = ?
            WHERE group_id = ?
            """,
            (int(carry_4a), int(carry_3a), int(carry_2a), int(group_id)),
        )
        if commit:
            self.conn.commit()

    def has_result(self, group_id: int, period_key: str) -> bool:
        self.cur.execute(
            "SELECT 1 FROM immortal_lottery_results WHERE group_id = ? AND period_key = ? LIMIT 1",
            (int(group_id), str(period_key)),
        )
        return self.cur.fetchone() is not None

    def insert_result(
        self, group_id: int, period_key: str, winning_digits: str, bet_total: int, drawn_at: str
    ):
        self.cur.execute(
            """
            INSERT INTO immortal_lottery_results (group_id, period_key, winning_digits, bet_total, drawn_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(group_id), str(period_key), str(winning_digits), int(bet_total), str(drawn_at)),
        )
        self.conn.commit()

    def finalize_draw(
        self,
        group_id: int,
        period_key: str,
        winning_digits: str,
        bet_total: int,
        drawn_at: str,
        new_carry_4a: int,
        new_carry_3a: int,
        new_carry_2a: int,
        payouts,
    ) -> bool:
        gid = int(group_id)
        pk = str(period_key)
        self.cur.execute("BEGIN IMMEDIATE")
        try:
            self.cur.execute(
                "SELECT 1 FROM immortal_lottery_results WHERE group_id = ? AND period_key = ? LIMIT 1",
                (gid, pk),
            )
            if self.cur.fetchone():
                self.conn.rollback()
                return False
            self.cur.execute(
                """
                INSERT INTO immortal_lottery_results (group_id, period_key, winning_digits, bet_total, drawn_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (gid, pk, str(winning_digits), int(bet_total), str(drawn_at)),
            )
            self.cur.execute(
                """
                INSERT OR IGNORE INTO immortal_lottery_carry (group_id, carry_4a, carry_3a, carry_2a)
                VALUES (?, 0, 0, 0)
                """,
                (gid,),
            )
            self.cur.execute(
                """
                UPDATE immortal_lottery_carry
                SET carry_4a = ?, carry_3a = ?, carry_2a = ?
                WHERE group_id = ?
                """,
                (int(new_carry_4a), int(new_carry_3a), int(new_carry_2a), gid),
            )
            for uid, amt in payouts:
                a = int(amt)
                if a <= 0:
                    continue
                uid_s = str(int(uid))
                self.cur.execute(
                    "INSERT OR IGNORE INTO user_assets (user_id, points) VALUES (?, 0)", (uid_s,)
                )
                self.cur.execute(
                    "UPDATE user_assets SET points = points + ? WHERE user_id = ?",
                    (a, uid_s),
                )
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def period_stats(self, group_id: int, period_key: str) -> dict:
        self.cur.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT user_id), COALESCE(SUM(LENGTH(digits)), 0)
            FROM immortal_lottery_bets
            WHERE group_id = ? AND period_key = ?
            """,
            (int(group_id), str(period_key)),
        )
        row = self.cur.fetchone()
        n_bets = 0 if not row else int(row[0] or 0)
        n_users = 0 if not row else int(row[1] or 0)
        return {"bet_count": n_bets, "distinct_users": n_users, "bet_points": n_bets}

    def list_bets(self, group_id: int, period_key: str):
        self.cur.execute(
            """
            SELECT id, user_id, digits FROM immortal_lottery_bets
            WHERE group_id = ? AND period_key = ?
            ORDER BY created_at ASC, id ASC
            """,
            (int(group_id), str(period_key)),
        )
        return [(int(r[0]), int(r[1]), str(r[2])) for r in self.cur.fetchall()]

    def groups_for_draw(self, period_key: str) -> list[int]:
        self.cur.execute(
            """
            SELECT DISTINCT group_id FROM immortal_lottery_bets WHERE period_key = ?
            UNION
            SELECT group_id FROM immortal_lottery_carry
            WHERE COALESCE(carry_4a, 0) + COALESCE(carry_3a, 0) + COALESCE(carry_2a, 0) > 0
            """,
            (str(period_key),),
        )
        return [int(r[0]) for r in self.cur.fetchall() if r[0] is not None]

    def try_place_bet(
        self, group_id: int, period_key: str, user_id: int, digits: str, bet_bj_date: str, cost: int = 1
    ) -> tuple[bool, str]:
        user_id_s = str(int(user_id))
        cost = int(cost)
        self.cur.execute("BEGIN IMMEDIATE")
        try:
            self.cur.execute(
                """
                SELECT 1 FROM immortal_lottery_bets
                WHERE group_id = ? AND user_id = ? AND bet_bj_date = ?
                LIMIT 1
                """,
                (int(group_id), int(user_id), str(bet_bj_date)),
            )
            if self.cur.fetchone():
                self.conn.rollback()
                return False, "今日已在本群下过注（北京时间每日最多 1 注）。"

            self.cur.execute(
                """
                INSERT OR IGNORE INTO immortal_lottery_carry (group_id, carry_4a, carry_3a, carry_2a)
                VALUES (?, 0, 0, 0)
                """,
                (int(group_id),),
            )
            self.cur.execute(
                "INSERT OR IGNORE INTO user_assets (user_id, points) VALUES (?, 0)", (user_id_s,)
            )
            self.cur.execute("SELECT points FROM user_assets WHERE user_id = ?", (user_id_s,))
            row = self.cur.fetchone()
            pts = 0 if not row or row[0] is None else int(row[0])
            if pts < cost:
                self.conn.rollback()
                return False, "积分不足（每注消耗 1 积分）。"

            self.cur.execute(
                """
                UPDATE user_assets SET points = points - ?
                WHERE user_id = ? AND points >= ?
                """,
                (cost, user_id_s, cost),
            )
            if self.cur.rowcount == 0:
                self.conn.rollback()
                return False, "积分不足（每注消耗 1 积分）。"

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cur.execute(
                """
                INSERT INTO immortal_lottery_bets (group_id, period_key, user_id, digits, bet_bj_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (int(group_id), str(period_key), int(user_id), str(digits), str(bet_bj_date), ts),
            )
            self.conn.commit()
            return True, "ok"
        except Exception as e:
            self.conn.rollback()
            return False, str(e) or "下注失败"
