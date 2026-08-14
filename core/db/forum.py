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
                    poll_anonymous=False, poll_allow_multi=False, poll_deadline=None):
        """创建帖子。polls: list[str]，tag_ids: list[int]。返回 post_id。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            """
            INSERT INTO forum_posts
                (author_user_id, type, title, body_json, status, pinned,
                 created_at, updated_at, poll_anonymous, poll_allow_multi, poll_deadline)
            VALUES (?, ?, ?, ?, 'open', 0, ?, ?, ?, ?, ?)
            """,
            (author_user_id, type_, title, body_json or "",
             now, now, int(bool(poll_anonymous)), int(bool(poll_allow_multi)),
             poll_deadline),
        )
        post_id = self.cur.lastrowid
        if polls and type_ == "poll":
            for idx, text in enumerate(polls):
                self.cur.execute(
                    "INSERT INTO forum_poll_options (post_id, text, ord) VALUES (?, ?, ?)",
                    (post_id, text, idx),
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
            "SELECT * FROM forum_posts WHERE id = ? AND status != 'deleted'", (post_id,)
        )
        row = self.cur.fetchone()
        if not row:
            return None
        post = self._row_to_post(row)
        return {
            **post,
            "tags": self.get_post_tag_names(post_id),
            "poll_options": self.list_poll_options(post_id),
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

    def _row_to_post(self, row):
        cols = ("id", "author_user_id", "type", "title", "body_json", "status", "pinned",
                "created_at", "updated_at", "notified_at",
                "poll_anonymous", "poll_allow_multi", "poll_deadline")
        return dict(zip(cols, row))

    def get_post_tag_names(self, post_id):
        self.cur.execute(
            "SELECT t.name FROM forum_post_tags pt "
            "JOIN forum_tags t ON pt.tag_id = t.id WHERE pt.post_id = ? ORDER BY t.name",
            (post_id,),
        )
        return [r[0] for r in self.cur.fetchall()]

    # —— Comments ——

    def create_comment(self, post_id, author_user_id, body_text):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            "INSERT INTO forum_comments (post_id, author_user_id, body_text, created_at) "
            "VALUES (?, ?, ?, ?)",
            (post_id, author_user_id, body_text, now),
        )
        cid = self.cur.lastrowid
        self.conn.commit()
        return cid

    def list_comments(self, post_id, cursor=None, limit=30):
        sql = (
            "SELECT id, post_id, author_user_id, body_text, created_at, status "
            "FROM forum_comments WHERE post_id = ? AND status != 'deleted'"
        )
        params = [post_id]
        if cursor:
            sql += " AND id < ?"
            params.append(cursor)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit + 1)
        self.cur.execute(sql, params)
        return self.cur.fetchall()

    def delete_comment(self, comment_id, author_user_id):
        self.cur.execute(
            "DELETE FROM forum_comments WHERE id = ? AND author_user_id = ?",
            (comment_id, author_user_id),
        )
        ok = self.cur.rowcount > 0
        self.conn.commit()
        return ok

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

    # —— Poll options / votes ——

    def list_poll_options(self, post_id):
        self.cur.execute(
            "SELECT id, text, ord FROM forum_poll_options WHERE post_id = ? ORDER BY ord",
            (post_id,),
        )
        return self.cur.fetchall()

    def vote(self, post_id, option_id, user_id):
        """投票。返回 (ok, error_code)。UNIQUE 约束保证一人一票。"""
        # 校验帖子存在且为 poll 且 open
        self.cur.execute(
            "SELECT type, status, poll_deadline FROM forum_posts WHERE id = ?",
            (post_id,),
        )
        row = self.cur.fetchone()
        if not row:
            return False, "not_found"
        type_, status, deadline = row
        if type_ != "poll":
            return False, "not_poll"
        if status != "open":
            return False, "closed"
        if deadline and deadline <= datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
            return False, "expired"
        # 校验选项属于该帖
        self.cur.execute(
            "SELECT post_id FROM forum_poll_options WHERE id = ?", (option_id,)
        )
        opt = self.cur.fetchone()
        if not opt or opt[0] != post_id:
            return False, "invalid_option"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.cur.execute(
                "INSERT INTO forum_poll_votes (poll_id, option_id, user_id, created_at) VALUES (?, ?, ?, ?)",
                (post_id, option_id, user_id, now),
            )
            self.conn.commit()
            return True, None
        except sqlite3.IntegrityError:
            self.conn.commit()
            return False, "duplicate"

    def get_vote_counts(self, poll_id):
        """返回 [(option_id, text, ord, count), ...]"""
        self.cur.execute(
            """
            SELECT o.id, o.text, o.ord,
                   (SELECT COUNT(*) FROM forum_poll_votes v WHERE v.option_id = o.id) AS cnt
            FROM forum_poll_options o WHERE o.post_id = ?
            ORDER BY o.ord
            """,
            (poll_id,),
        )
        return self.cur.fetchall()

    def get_user_vote(self, poll_id, user_id):
        self.cur.execute(
            "SELECT option_id FROM forum_poll_votes WHERE poll_id = ? AND user_id = ?",
            (poll_id, user_id),
        )
        row = self.cur.fetchone()
        return row[0] if row else None

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
