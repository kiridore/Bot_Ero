"""奖励记录与积分同事务提交。回调只能执行本连接上的 SQL，不能自行提交或发送消息。"""
from contextlib import contextmanager

from core.db.points import PointsManager


class RewardManager:
    def __init__(self, conn):
        self.conn = conn
        self._depth = 0

    @contextmanager
    def transaction(self):
        if self._depth:
            # 同一消费者可提交多笔奖励；即使调用方捕获异常，失败子操作也必须回滚。
            self.conn.execute("SAVEPOINT reward_nested")
            try:
                yield
            except BaseException:
                self.conn.execute("ROLLBACK TO reward_nested")
                self.conn.execute("RELEASE reward_nested")
                raise
            else:
                self.conn.execute("RELEASE reward_nested")
            return
        # 不悄悄提交调用方未完成的业务，也不让“发奖成功”依赖未知外层事务。
        if self.conn.in_transaction:
            raise RuntimeError("奖励处理前必须完成当前数据库事务")
        self.conn.execute("BEGIN IMMEDIATE")
        self._depth = 1
        try:
            yield
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        finally:
            self._depth = 0

    def grant(self, plugin, user_id, reward_key, source_operation, amount,
              *, source_scope="", update_state=None):
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise ValueError("奖励积分必须为非负整数")
        uid = str(user_id)
        with self.transaction():
            old = self.conn.execute("""
                SELECT id FROM plugin_reward_records
                WHERE plugin_name = ? AND user_id = ? AND reward_key = ?
                AND (revoked_at IS NULL OR source_operation = ?)
            """, (plugin, uid, reward_key, source_operation)).fetchone()
            if old:
                return False
            # 旧领取记录已存在时由业务回调返回 False，不补造一次新的发奖。
            if update_state is not None and update_state(self.conn) is False:
                return False
            self.conn.execute("""
                INSERT INTO plugin_reward_records
                (plugin_name, user_id, reward_key, source_operation, source_scope, amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (plugin, uid, reward_key, source_operation, source_scope, amount))
            PointsManager(self.conn).adjust(uid, amount, commit=False)
            return True

    def revoke(self, plugin, user_id, reward_key, source_operation, *, update_state=None):
        uid = str(user_id)
        with self.transaction():
            row = self.conn.execute("""
                SELECT id, amount FROM plugin_reward_records
                WHERE plugin_name = ? AND user_id = ? AND reward_key = ? AND revoked_at IS NULL
            """, (plugin, uid, reward_key)).fetchone()
            if row is None:
                return None  # 与金额为 0 的已发奖励区分，兼容层据此处理旧记录
            if update_state is not None and update_state(self.conn) is False:
                return None
            self.conn.execute("""
                UPDATE plugin_reward_records SET revoked_at = CURRENT_TIMESTAMP, revoke_operation = ?
                WHERE id = ? AND revoked_at IS NULL
            """, (source_operation, row[0]))
            PointsManager(self.conn).adjust(uid, -row[1], commit=False)
            return row[1]

    def has_history(self, plugin, user_id, reward_key):
        """新记录已接管的业务不能再次走旧记录扣分路径。"""
        return self.conn.execute("""
            SELECT 1 FROM plugin_reward_records
            WHERE plugin_name = ? AND user_id = ? AND reward_key = ? LIMIT 1
        """, (plugin, str(user_id), reward_key)).fetchone() is not None
