"""社区准入数据层（M1 T1.1）：注册账号、群登记、加群申请队列、黑名单。

纯数据层：只存取事实，不做事件拦截与业务判断；四种部署共用，空表 = 零行为影响。
契约见 openspec/specs/community-access-registry/spec.md（提案 community-access-tables）。
"""
from datetime import datetime

import sqlite3
from uuid import uuid4


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
        with self.conn:
            self.conn.execute(
                "UPDATE group_registry SET status = 'removed' WHERE group_id = ?", (int(group_id),))
            self.conn.execute(
                "UPDATE group_requests SET joined = 0, remote_state = 'unknown' WHERE group_id = ?"
                " AND status IN ('pending', 'processing', 'uncertain')", (int(group_id),))

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
        self.cur.execute(
            "INSERT INTO group_requests (group_id, user_id, flag, sub_type, created_at)"
            " VALUES (?, ?, ?, ?, ?) ON CONFLICT(flag) DO NOTHING",
            (int(group_id), int(user_id), str(flag), str(sub_type), _now()),
        )
        inserted = self.cur.rowcount > 0
        self.conn.commit()
        return inserted

    def pending_requests(self) -> list[sqlite3.Row]:
        self.cur.execute(
            "SELECT * FROM group_requests"
            " WHERE status IN ('pending', 'processing', 'uncertain') ORDER BY id")
        return self.cur.fetchall()

    def resolve_request(self, group_id, user_id, created_at: str, approve: bool) -> bool:
        """仅 pending 可裁决；终态行永不再变。"""
        # 兼容旧接口，但秒级定位有歧义时不得一次修改多个请求。
        matches = self.conn.execute(
            "SELECT id FROM group_requests WHERE group_id = ? AND user_id = ?"
            " AND created_at = ? AND status = 'pending'",
            (int(group_id), int(user_id), created_at)).fetchall()
        if len(matches) != 1:
            return False
        self.cur.execute(
            "UPDATE group_requests SET status = ? WHERE id = ? AND status = 'pending'",
            ("approved" if approve else "rejected", matches[0][0]),
        )
        self.conn.commit()
        return self.cur.rowcount > 0

    def record_group_join(self, group_id, operator_id) -> bool:
        """确认机器人已在群内；已有邀请更新事实，否则建立手动待审记录。"""
        gid = int(group_id)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if self.is_group_active(gid):
                self.conn.commit()
                return False
            open_rows = self.conn.execute(
                "SELECT id FROM group_requests WHERE group_id = ?"
                " AND status IN ('pending', 'processing', 'uncertain')", (gid,)).fetchall()
            if open_rows:
                self.conn.execute(
                    "UPDATE group_requests SET joined = 1 WHERE group_id = ?"
                    " AND status IN ('pending', 'processing', 'uncertain')", (gid,))
            else:
                self.conn.execute(
                    "INSERT INTO group_requests (kind, joined, group_id, user_id, flag, sub_type, created_at)"
                    " VALUES ('manual', 1, ?, ?, ?, 'manual', ?)",
                    (gid, int(operator_id), 'manual:' + uuid4().hex, _now()))
            self.conn.commit()
            return not open_rows
        except Exception:
            self.conn.rollback()
            raise

    def reserve_review(self, request_id, approve: bool, max_groups: int) -> sqlite3.Row:
        """原子预留审批及容量。processing/uncertain占名额，重试不得盲目再调远端。"""
        if type(max_groups) is not int or max_groups < 1:
            raise ValueError("群数上限必须是正整数")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT * FROM group_requests WHERE id = ?", (int(request_id),)).fetchone()
            if row is None or row['status'] != 'pending':
                raise ValueError("申请不存在或已经处理；处理中及结果未知的申请需先确认状态")
            gid = row['group_id']
            if approve:
                if self.is_banned('group', gid) or self.is_banned('user', row['user_id']):
                    raise ValueError("群或邀请人在黑名单中")
                if self.is_group_active(gid):
                    raise ValueError("群已激活")
                occupied = {r[0] for r in self.conn.execute(
                    "SELECT group_id FROM group_registry WHERE status = 'active' UNION"
                    " SELECT group_id FROM group_requests"
                    " WHERE status IN ('processing', 'uncertain') AND decision = 'approve'")}
                if gid in occupied:
                    raise ValueError("同一群已有审批正在处理")
                if len(occupied) >= max_groups:
                    raise ValueError("群数已达上限")
            self.conn.execute(
                "UPDATE group_requests SET status = 'processing', decision = ?, remote_state = 'unknown'"
                " WHERE id = ?", ('approve' if approve else 'reject', row['id']))
            self.conn.commit()
            return self.conn.execute("SELECT * FROM group_requests WHERE id = ?", (row['id'],)).fetchone()
        except Exception:
            self.conn.rollback()
            raise

    def record_review_result(self, request_id, result: str) -> None:
        """ok/failed/unknown为远端结果；记录成功后本地失败可直接继续提交，不再调API。"""
        if result not in ('ok', 'failed', 'unknown'):
            raise ValueError("非法审批结果")
        status = 'pending' if result == 'failed' else 'uncertain'
        self.conn.execute(
            "UPDATE group_requests SET remote_state = ?, status = ?"
            " WHERE id = ? AND status IN ('processing', 'uncertain')",
            (result, status, int(request_id)))
        self.conn.commit()

    def complete_review(self, request_id, plugins=()) -> bool:
        """本地终态、激活和播种同事务；只接受成功远端结果或确认已入群的本地审批。"""
        members = tuple(plugins)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute("SELECT * FROM group_requests WHERE id = ?", (int(request_id),)).fetchone()
            if row is None or row['status'] in ('approved', 'rejected'):
                self.conn.commit()
                return False
            if row['status'] not in ('processing', 'uncertain'):
                raise ValueError("申请尚未开始审批")
            approve = row['decision'] == 'approve'
            local = bool(row['joined']) if approve else row['kind'] == 'manual'
            if row['remote_state'] != 'ok' and not local:
                raise ValueError("远端结果尚未确认，不允许标记成功")
            if approve:
                self.conn.execute(
                    "INSERT INTO group_registry (group_id, invited_by, approved_at, status)"
                    " VALUES (?, ?, ?, 'active') ON CONFLICT(group_id) DO UPDATE SET status = 'active'",
                    (row['group_id'], row['user_id'], _now()))
                self.conn.executemany(
                    "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)",
                    [(row['group_id'], name) for name in members])
            self.conn.execute(
                "UPDATE group_requests SET status = ? WHERE id = ?",
                ('approved' if approve else 'rejected', row['id']))
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

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
