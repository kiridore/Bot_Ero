"""议事厅存储层：帖子/评论/标签/投票选项/投票。

字段命名：长文存 Tiptap JSON 文本（`body_json`），评论存纯文本（`body_text`）。
所有日期字段均为 `"YYYY-MM-DD HH:MM:SS"` 或 `YYYY-MM-DD`（本地时间）。
"""

from datetime import datetime
import sqlite3


class ForumManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    # —— Posts ——

    def create_post(self, author_user_id, type_, title, body_json,
                    polls=None, tag_ids=None,
                    poll_anonymous=False, poll_deadline=None):
        """创建帖子。

        polls: list[dict]，每个子投票 = {"title": str, "allow_multi": bool, "options": list[str]}。
        tag_ids: list[int]。返回 post_id。
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            """
            INSERT INTO forum_posts
                (author_user_id, type, title, body_json, status, pinned,
                 created_at, updated_at, poll_anonymous, poll_deadline)
            VALUES (?, ?, ?, ?, 'open', 0, ?, ?, ?, ?)
            """,
            (author_user_id, type_, title, body_json or "",
             now, now, int(bool(poll_anonymous)), poll_deadline),
        )
        post_id = self.cur.lastrowid
        if polls and type_ == "poll":
            for pidx, poll in enumerate(polls):
                self.cur.execute(
                    "INSERT INTO forum_polls (post_id, title, allow_multi, ord) VALUES (?, ?, ?, ?)",
                    (post_id, poll.get("title", ""), int(bool(poll.get("allow_multi"))), pidx),
                )
                poll_id = self.cur.lastrowid
                for oidx, text in enumerate(poll.get("options") or []):
                    self.cur.execute(
                        "INSERT INTO forum_poll_options (poll_id, text, ord) VALUES (?, ?, ?)",
                        (poll_id, text, oidx),
                    )
        if tag_ids:
            for tid in tag_ids:
                self.cur.execute(
                    "INSERT INTO forum_post_tags (post_id, tag_id) VALUES (?, ?)",
                    (post_id, tid),
                )
        self.conn.commit()
        return post_id

    def get_post(self, post_id):
        self.cur.execute(
            "SELECT id, author_user_id, type, title, body_json, status, pinned, "
            "created_at, updated_at, notified_at, poll_anonymous, poll_deadline "
            "FROM forum_posts WHERE id = ? AND status != 'deleted'",
            (post_id,),
        )
        row = self.cur.fetchone()
        if not row:
            return None
        post = dict(zip(
            ("id", "author_user_id", "type", "title", "body_json", "status", "pinned",
             "created_at", "updated_at", "notified_at", "poll_anonymous", "poll_deadline"),
            row,
        ))
        return {
            **post,
            "tags": self.get_post_tag_names(post_id),
        }


    def update_post(self, post_id, author_user_id, title=None, body_json=None, tag_ids=None):
        """编辑帖子。仅作者可调用；type/polls 不可改；tag_ids=None 表示不动，[] 表示清空。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sets = ["updated_at = ?"]
        params = [now]
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if body_json is not None:
            sets.append("body_json = ?")
            params.append(body_json)
        params.extend([post_id, author_user_id])
        self.cur.execute(
            f"UPDATE forum_posts SET {', '.join(sets)} WHERE id = ? AND author_user_id = ? AND status != 'deleted'",
            params,
        )
        if self.cur.rowcount == 0:
            self.conn.commit()
            return False
        if tag_ids is not None:
            self.cur.execute("DELETE FROM forum_post_tags WHERE post_id = ?", (post_id,))
            for tid in tag_ids:
                self.cur.execute(
                    "INSERT INTO forum_post_tags (post_id, tag_id) VALUES (?, ?)", (post_id, tid)
                )
            self.purge_orphan_tags()
        self.conn.commit()
        return True

    def delete_post(self, post_id, author_user_id):
        """硬删除（级联删除评论/选项/投票/标签关联通过 FK CASCADE）。"""
        self.cur.execute(
            "DELETE FROM forum_posts WHERE id = ? AND author_user_id = ?",
            (post_id, author_user_id),
        )
        ok = self.cur.rowcount > 0
        if ok:
            self.purge_orphan_tags()
        self.conn.commit()
        return ok

    def list_posts(self, tag=None, type_=None, cursor=None, limit=20):
        """列表：置顶优先，再按时间倒序。tag: 按 tag 名精确过滤。cursor: 上次返回的 last_id（用于下一页）。"""
        cols = ("id", "author_user_id", "type", "title", "status", "pinned",
                "created_at", "updated_at", "poll_deadline")
        sql = f"SELECT {', '.join(cols)} FROM forum_posts WHERE status != 'deleted'"
        params = []
        if type_:
            sql += " AND type = ?"
            params.append(type_)
        if tag:
            sql += (
                " AND id IN (SELECT pt.post_id FROM forum_post_tags pt "
                "JOIN forum_tags t ON pt.tag_id = t.id WHERE t.name = ?)"
            )
            params.append(tag)
        if cursor:
            sql += " AND id < ?"
            params.append(cursor)
        sql += " ORDER BY pinned DESC, id DESC LIMIT ?"
        params.append(limit + 1)
        self.cur.execute(sql, params)
        rows = self.cur.fetchall()
        return rows  # 路由层截断 + 取 next_cursor

    def count_today_announces(self, user_id):
        """今日（本地自然日）公告数（用于每日 1 次限制）。"""
        today = datetime.now().strftime("%Y-%m-%d")
        self.cur.execute(
            "SELECT COUNT(*) FROM forum_posts "
            "WHERE author_user_id = ? AND type = 'announce' "
            "AND substr(created_at, 1, 10) = ?",
            (user_id, today),
        )
        return self.cur.fetchone()[0]

    def get_post_tag_names(self, post_id):
        self.cur.execute(
            "SELECT t.name FROM forum_post_tags pt "
            "JOIN forum_tags t ON pt.tag_id = t.id WHERE pt.post_id = ? ORDER BY t.name",
            (post_id,),
        )
        return [r[0] for r in self.cur.fetchall()]

    # —— Comments ——

    _COMMENT_COLS = ("id, post_id, author_user_id, body_text, status, created_at, "
                     "edited_at, parent_id, root_id")

    def get_comment(self, comment_id):
        self.cur.execute(
            f"SELECT {self._COMMENT_COLS} FROM forum_comments WHERE id = ?",
            (comment_id,),
        )
        row = self.cur.fetchone()
        return dict(zip(
            ("id", "post_id", "author_user_id", "body_text", "status", "created_at",
             "edited_at", "parent_id", "root_id"),
            row,
        )) if row else None

    def create_comment(self, post_id, author_user_id, body_text, parent_id=None):
        """创建评论；parent_id 指向同帖存活评论时为回复。返回新评论 dict 或 None（父非法）。"""
        root_id = None
        if parent_id is not None:
            parent = self.get_comment(parent_id)
            if not parent or parent["post_id"] != post_id or parent["status"] == "deleted":
                return None
            root_id = parent["root_id"] if parent["root_id"] is not None else parent["id"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            "INSERT INTO forum_comments (post_id, author_user_id, body_text, created_at, parent_id, root_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (post_id, author_user_id, body_text, now, parent_id, root_id),
        )
        cid = self.cur.lastrowid
        self.conn.commit()
        return self.get_comment(cid)

    def list_comment_threads(self, post_id, cursor=None, limit=30):
        """两级线程：顶层评论 id DESC keyset 分页，每条附全部回复（id ASC）。
        返回 (threads, has_more, total)；threads 元素 = 顶层 dict + 'replies' 列表。
        软删占位（status='deleted' 但仍有存活回复）也会返回，前端渲染占位。"""
        where = (
            "post_id = ? AND parent_id IS NULL AND (status != 'deleted' OR EXISTS ("
            "SELECT 1 FROM forum_comments c2 WHERE c2.root_id = forum_comments.id "
            "AND c2.status != 'deleted'))"
        )
        params = [post_id]
        if cursor:
            where += " AND id < ?"
            params.append(cursor)
        self.cur.execute(
            f"SELECT {self._COMMENT_COLS} FROM forum_comments "
            f"WHERE {where} ORDER BY id DESC LIMIT ?",
            (*params, limit + 1),
        )
        rows = self.cur.fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        self.cur.execute(
            "SELECT COUNT(*) FROM forum_comments WHERE post_id = ? AND status != 'deleted'",
            (post_id,),
        )
        total = self.cur.fetchone()[0]
        keys = ("id", "post_id", "author_user_id", "body_text", "status", "created_at",
                "edited_at", "parent_id", "root_id")
        threads = [dict(zip(keys, r), replies=[]) for r in rows]
        if rows:
            placeholders = ", ".join("?" for _ in rows)
            self.cur.execute(
                f"SELECT {self._COMMENT_COLS} FROM forum_comments "
                f"WHERE root_id IN ({placeholders}) AND (status != 'deleted' OR EXISTS ("
                "SELECT 1 FROM forum_comments c3 WHERE c3.parent_id = forum_comments.id "
                "AND c3.status != 'deleted')) ORDER BY id ASC",
                tuple(r[0] for r in rows),
            )
            replies = self.cur.fetchall()
            by_root = {t["id"]: t["replies"] for t in threads}
            for r in replies:
                by_root.setdefault(r[8], []).append(dict(zip(keys, r)))
        return threads, has_more, total

    def update_comment(self, comment_id, author_user_id, body_text):
        """编辑自己的评论：刷新 body_text 与 edited_at。成功返回新 dict，失败 None。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            "UPDATE forum_comments SET body_text = ?, edited_at = ? "
            "WHERE id = ? AND author_user_id = ? AND status != 'deleted'",
            (body_text, now, comment_id, author_user_id),
        )
        if self.cur.rowcount == 0:
            self.conn.commit()
            return None
        self.conn.commit()
        return self.get_comment(comment_id)

    def delete_comment(self, comment_id, author_user_id):
        """删除自己的评论。有存活回复时软删（占位保回复链），否则硬删。
        返回 'hard' / 'soft' / None（非本人或不存在）。"""
        self.cur.execute(
            "SELECT id FROM forum_comments WHERE id = ? AND author_user_id = ? AND status != 'deleted'",
            (comment_id, author_user_id),
        )
        if not self.cur.fetchone():
            self.conn.commit()
            return None
        # 直接子回复（parent_id）或整串后代（root_id，顶层评论时覆盖孙回复）
        self.cur.execute(
            "SELECT COUNT(*) FROM forum_comments "
            "WHERE (parent_id = ? OR root_id = ?) AND status != 'deleted'",
            (comment_id, comment_id),
        )
        has_children = self.cur.fetchone()[0] > 0
        if has_children:
            self.cur.execute(
                "UPDATE forum_comments SET status = 'deleted', body_text = '' WHERE id = ?",
                (comment_id,),
            )
            mode = "soft"
        else:
            self.cur.execute("DELETE FROM forum_comments WHERE id = ?", (comment_id,))
            mode = "hard"
        self.conn.commit()
        return mode

    # —— Tags ——

    def create_tag(self, name, created_by):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.cur.execute(
                "INSERT INTO forum_tags (name, created_by, created_at) VALUES (?, ?, ?)",
                (name.strip(), created_by, now),
            )
        except sqlite3.IntegrityError:
            self.conn.commit()
            return None
        tid = self.cur.lastrowid
        self.conn.commit()
        return tid

    def list_tags_with_counts(self):
        self.cur.execute(
            """
            SELECT t.id, t.name, t.created_at,
                   (SELECT COUNT(*) FROM forum_post_tags pt
                    JOIN forum_posts p ON pt.post_id = p.id
                    WHERE pt.tag_id = t.id AND p.status != 'deleted') AS post_count
            FROM forum_tags t
            WHERE t.id IN (SELECT DISTINCT tag_id FROM forum_post_tags)
            ORDER BY post_count DESC, t.name
            """
        )
        return self.cur.fetchall()

    def purge_orphan_tags(self):
        """删除无任何帖子引用的悬空 tag（引用计数 0）。在删帖/改 tag 后调用。"""
        self.cur.execute(
            "DELETE FROM forum_tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM forum_post_tags)"
        )

    # —— Polls / options / votes ——

    def get_polls(self, post_id, user_id=None):
        """返回帖子下全部子投票（含选项票数）；user_id 提供时附带该用户已投选项 id 列表。"""
        self.cur.execute(
            "SELECT id, title, allow_multi FROM forum_polls WHERE post_id = ? ORDER BY ord, id",
            (post_id,),
        )
        polls = []
        for poll_id, title, allow_multi in self.cur.fetchall():
            self.cur.execute(
                "SELECT id, text, ord FROM forum_poll_options WHERE poll_id = ? ORDER BY ord, id",
                (poll_id,),
            )
            options = []
            for oid, text, ord_ in self.cur.fetchall():
                self.cur.execute(
                    "SELECT COUNT(*) FROM forum_poll_votes WHERE option_id = ?", (oid,)
                )
                count = self.cur.fetchone()[0]
                options.append({"id": oid, "text": text, "ord": ord_, "count": count})
            my_vote = []
            if user_id is not None:
                self.cur.execute(
                    "SELECT option_id FROM forum_poll_votes WHERE poll_id = ? AND user_id = ? ORDER BY option_id",
                    (poll_id, user_id),
                )
                my_vote = [r[0] for r in self.cur.fetchall()]
            polls.append({
                "id": poll_id,
                "title": title,
                "allow_multi": bool(allow_multi),
                "options": options,
                "my_vote": my_vote,
            })
        return polls

    def vote(self, post_id, poll_id, option_ids, user_id):
        """对某个子投票投票。返回 (ok, error_code)。

        option_ids: 要投的选项 id 列表（单选恰 1 个，多选 >=1 个）。
        单选一人一票（应用层校验）；多选可投多个选项，同选项不重复（UNIQUE 兜底）。
        """
        option_ids = list(dict.fromkeys(option_ids))  # 去重保序
        if not option_ids:
            return False, "no_option"
        self.cur.execute(
            "SELECT fp.id, fp.allow_multi, p.type, p.status, p.poll_deadline "
            "FROM forum_polls fp JOIN forum_posts p ON p.id = fp.post_id "
            "WHERE fp.id = ? AND fp.post_id = ?",
            (poll_id, post_id),
        )
        row = self.cur.fetchone()
        if not row:
            return False, "not_found"
        _, allow_multi, type_, status, deadline = row
        if type_ != "poll":
            return False, "not_poll"
        if status != "open":
            return False, "closed"
        if deadline and deadline <= datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
            return False, "expired"
        if not allow_multi and len(option_ids) > 1:
            return False, "too_many"
        # 校验全部选项都属于该子投票
        for oid in option_ids:
            self.cur.execute(
                "SELECT id FROM forum_poll_options WHERE poll_id = ? AND id = ?",
                (poll_id, oid),
            )
            if not self.cur.fetchone():
                return False, "invalid_option"
        # 单选：一人一票（已有任意投票即重复）
        if not allow_multi:
            self.cur.execute(
                "SELECT COUNT(*) FROM forum_poll_votes WHERE poll_id = ? AND user_id = ?",
                (poll_id, user_id),
            )
            if self.cur.fetchone()[0] > 0:
                return False, "duplicate"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inserted = 0
        try:
            for oid in option_ids:
                self.cur.execute(
                    "INSERT OR IGNORE INTO forum_poll_votes (poll_id, option_id, user_id, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (poll_id, oid, user_id, now),
                )
                inserted += self.cur.rowcount
            self.conn.commit()
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "duplicate"
        if inserted == 0:
            return False, "duplicate"
        return True, None

    def close_poll(self, post_id):
        """手动/自动关闭投票。返回 True 表示状态从 open 变为 closed。"""
        self.cur.execute(
            "UPDATE forum_posts SET status = 'closed' WHERE id = ? AND type = 'poll' AND status = 'open'",
            (post_id,),
        )
        ok = self.cur.rowcount > 0
        self.conn.commit()
        return ok

    # —— Bot 通知用 ——

    def list_unnotified_posts(self, limit=10):
        self.cur.execute(
            "SELECT id, type, title, author_user_id FROM forum_posts "
            "WHERE notified_at IS NULL AND status != 'deleted' "
            "ORDER BY id ASC LIMIT ?",
            (limit,),
        )
        return self.cur.fetchall()

    def mark_notified(self, post_id):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            "UPDATE forum_posts SET notified_at = ? WHERE id = ?", (now, post_id)
        )
        self.conn.commit()

    def list_expired_polls(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            "SELECT id, title FROM forum_posts "
            "WHERE type = 'poll' AND status = 'open' "
            "AND poll_deadline IS NOT NULL AND poll_deadline <= ?",
            (now,),
        )
        return self.cur.fetchall()
