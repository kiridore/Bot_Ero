"""社区准入数据层（M1 T1.1）：注册账号、群登记、加群申请队列、黑名单。

纯数据层：只存取事实，不做事件拦截与业务判断；四种部署共用，空表 = 零行为影响。
契约见 openspec/specs/community-access-registry/spec.md（提案 community-access-tables）。
"""
from datetime import datetime

import sqlite3


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class CommunityManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    # —— 注册账号 ——————————————————————————————

    def register_user(self, user_id) -> bool:
        """幂等：已注册返回 False，且不改首次注册时间。"""
        self.cur.execute(
            "INSERT OR IGNORE INTO user_accounts (user_id, created_at) VALUES (?, ?)",
            (int(user_id), _now()),
        )
        self.conn.commit()
        return self.cur.rowcount > 0

    def is_registered(self, user_id) -> bool:
        self.cur.execute(
            "SELECT 1 FROM user_accounts WHERE user_id = ?", (int(user_id),))
        return self.cur.fetchone() is not None

    def agree_eula(self, user_id, eula_version: str) -> bool:
        """记录注册与协议同意凭证；已注册返回 False 且绝不改写首次时间（幂等）。"""
        uid = int(user_id)
        self.cur.execute(
            "SELECT 1 FROM user_accounts WHERE user_id = ?", (uid,))
        if self.cur.fetchone() is not None:
            self.conn.commit()
            return False
        now = _now()
        self.cur.execute(
            "INSERT INTO user_accounts (user_id, created_at, eula_version, agreed_at)"
            " VALUES (?, ?, ?, ?)",
            (uid, now, str(eula_version), now))
        self.conn.commit()
        return True

    # —— 群登记 ——————————————————————————————————

    def activate_group(self, group_id, name=None, invited_by=None) -> None:
        """幂等激活；removed→active 不清除首次 approved_at 与审核历史。"""
        gid = int(group_id)
        self.cur.execute(
            "INSERT INTO group_registry (group_id, name, invited_by, approved_at, status)"
            " VALUES (?, ?, ?, ?, 'active')"
            " ON CONFLICT(group_id) DO UPDATE SET status = 'active'",
            (gid, name, int(invited_by) if invited_by is not None else None, _now()),
        )
        self.conn.commit()

    def mark_group_removed(self, group_id) -> None:
        """被移出群：仅改状态，保留全部记录。"""
        self.cur.execute(
            "UPDATE group_registry SET status = 'removed' WHERE group_id = ?",
            (int(group_id),))
        self.conn.commit()

    def is_group_active(self, group_id) -> bool:
        self.cur.execute(
            "SELECT 1 FROM group_registry WHERE group_id = ? AND status = 'active'",
            (int(group_id),))
        return self.cur.fetchone() is not None

    def iter_active_groups(self) -> list[int]:
        self.cur.execute(
            "SELECT group_id FROM group_registry WHERE status = 'active' ORDER BY group_id")
        return [row[0] for row in self.cur.fetchall()]

    # —— 加群申请队列 ——————————————————————————

    def upsert_request(self, group_id, user_id, flag: str, sub_type: str) -> bool:
        """同一凭证（flag）去重；返回 False 表示队列中已存在。"""
        try:
            self.cur.execute(
                "INSERT INTO group_requests (group_id, user_id, flag, sub_type, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (int(group_id), int(user_id), str(flag), str(sub_type), _now()),
            )
        except sqlite3.IntegrityError:  # flag 唯一索引 / 主键碰撞
            self.conn.rollback()
            return False
        self.conn.commit()
        return True

    def pending_requests(self) -> list[sqlite3.Row]:
        self.cur.execute(
            "SELECT group_id, user_id, flag, sub_type, created_at FROM group_requests"
            " WHERE status = 'pending' ORDER BY created_at")
        return self.cur.fetchall()

    def resolve_request(self, group_id, user_id, created_at: str, approve: bool) -> bool:
        """仅 pending 可裁决；终态行永不再变。"""
        self.cur.execute(
            "UPDATE group_requests SET status = ?"
            " WHERE group_id = ? AND user_id = ? AND created_at = ? AND status = 'pending'",
            ("approved" if approve else "rejected", int(group_id), int(user_id), created_at),
        )
        self.conn.commit()
        return self.cur.rowcount > 0

    # —— 黑名单 ——————————————————————————————————

    def ban(self, scope: str, target_id, reason: str | None = None) -> None:
        """幂等；重复拉黑不报错、不改首次时间（OR IGNORE 语义）。"""
        self.cur.execute(
            "INSERT OR IGNORE INTO blacklist (scope, target_id, reason, created_at)"
            " VALUES (?, ?, ?, ?)",
            (scope, int(target_id), reason, _now()),
        )
        self.conn.commit()

    def unban(self, scope: str, target_id) -> bool:
        self.cur.execute(
            "DELETE FROM blacklist WHERE scope = ? AND target_id = ?",
            (scope, int(target_id)))
        self.conn.commit()
        return self.cur.rowcount > 0

    def is_banned(self, scope: str, target_id) -> bool:
        self.cur.execute(
            "SELECT 1 FROM blacklist WHERE scope = ? AND target_id = ?",
            (scope, int(target_id)))
        return self.cur.fetchone() is not None
