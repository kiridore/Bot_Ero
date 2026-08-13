"""工具箱：网页链接收藏（标题/简介/URL），公开可浏览，登录后可添加。"""

from datetime import datetime
import sqlite3


class ToolsManager:
    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()

    @staticmethod
    def _like_escape(q: str) -> str:
        return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _link_tags_map(self) -> dict[int, list[str]]:
        """一次查询返回 {link_id: [tag names]}，避免 N+1。无 tag 的行缺省为 []。"""
        self.cur.execute(
            """
            SELECT lt.link_id,
                   (SELECT GROUP_CONCAT(t.name, ',')
                    FROM tools_link_tags lt2
                    JOIN tools_tags t ON lt2.tag_id = t.id
                    WHERE lt2.link_id = lt.link_id
                    ORDER BY lt2.tag_id)
            FROM tools_link_tags lt
            GROUP BY lt.link_id
            """
        )
        return {
            int(link_id): (names.split(",") if names else [])
            for link_id, names in self.cur.fetchall()
        }

    def list_tools(
        self,
        q: str | None = None,
        sort: str = "time",
        order: str = "desc",
        tag: str | None = None,
    ) -> list[dict]:
        base = (
            "SELECT id, title, description, url, domain, created_by, created_at, click_count "
            "FROM tools_links"
        )
        clauses: list[str] = []
        params: list[str] = []

        query = (q or "").strip()
        if query:
            escaped = self._like_escape(query)
            pattern = f"%{escaped}%"
            clauses.append(
                "(title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' "
                "OR url LIKE ? ESCAPE '\\')"
            )
            params.extend([pattern, pattern, pattern])

        tag = (tag or "").strip()
        if tag:
            clauses.append(
                "id IN (SELECT lt.link_id FROM tools_link_tags lt "
                "JOIN tools_tags t ON lt.tag_id = t.id WHERE t.name = ?)"
            )
            params.append(tag)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        direction = "ASC" if order == "asc" else "DESC"
        if sort == "hot":
            order_by = f"click_count {direction}, id DESC"
        else:
            order_by = f"id {direction}"
        self.cur.execute(base + where + f" ORDER BY {order_by}", params)
        rows = self.cur.fetchall()

        tags_map = self._link_tags_map()
        return [
            {
                "id": int(row[0]),
                "title": row[1],
                "description": row[2],
                "url": row[3],
                "domain": row[4],
                "created_by": row[5],
                "created_at": row[6],
                "click_count": int(row[7]),
                "tags": tags_map.get(int(row[0]), []),
            }
            for row in rows
        ]

    def add_tool(self, user_id: str, title: str, description: str, url: str, domain: str) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            "INSERT INTO tools_links (title, description, url, domain, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, description, url, domain, user_id, now),
        )
        self.conn.commit()
        return int(self.cur.lastrowid)

    def delete_tool(self, user_id: str, tool_id: int) -> dict:
        """删除自己提交的链接。返回 {"status": "ok" | "not_found" | "forbidden"}。"""
        self.cur.execute("SELECT created_by FROM tools_links WHERE id = ?", (int(tool_id),))
        row = self.cur.fetchone()
        if row is None:
            return {"status": "not_found"}
        if row[0] != user_id:
            return {"status": "forbidden"}
        self.cur.execute("DELETE FROM tools_links WHERE id = ?", (int(tool_id),))
        self.conn.commit()
        return {"status": "ok"}

    def update_tool(
        self,
        user_id: str,
        tool_id: int,
        title: str,
        description: str,
        url: str,
        domain: str,
        tag_names: list[str],
    ) -> dict:
        """修改自己提交的链接（tag 整体替换为 tag_names）。返回 {"status": "ok" | "not_found" | "forbidden"}。"""
        self.cur.execute("SELECT created_by FROM tools_links WHERE id = ?", (int(tool_id),))
        row = self.cur.fetchone()
        if row is None:
            return {"status": "not_found"}
        if row[0] != user_id:
            return {"status": "forbidden"}
        self.cur.execute(
            "UPDATE tools_links SET title = ?, description = ?, url = ?, domain = ? WHERE id = ?",
            (title, description, url, domain, int(tool_id)),
        )
        self.cur.execute("DELETE FROM tools_link_tags WHERE link_id = ?", (int(tool_id),))
        self.conn.commit()
        self.add_link_tags(int(tool_id), tag_names, user_id)
        return {"status": "ok"}

    def register_click(self, tool_id: int) -> int | None:
        """点击计数原子自增。返回最新计数；链接不存在返回 None。"""
        self.cur.execute(
            "UPDATE tools_links SET click_count = click_count + 1 WHERE id = ?",
            (int(tool_id),),
        )
        if self.cur.rowcount == 0:
            self.conn.commit()
            return None
        self.cur.execute("SELECT click_count FROM tools_links WHERE id = ?", (int(tool_id),))
        clicks = int(self.cur.fetchone()[0])
        self.conn.commit()
        return clicks

    def get_or_create_tag(self, name: str, created_by: str) -> int:
        """create-or-get 返回 tag id。并发竞态由 UNIQUE 约束兜底。"""
        clean = name.strip()
        self.cur.execute("SELECT id FROM tools_tags WHERE name = ?", (clean,))
        row = self.cur.fetchone()
        if row is not None:
            return int(row[0])
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.cur.execute(
                "INSERT INTO tools_tags (name, created_by, created_at) VALUES (?, ?, ?)",
                (clean, created_by, now),
            )
        except sqlite3.IntegrityError:
            self.conn.commit()
        else:
            self.conn.commit()
            return int(self.cur.lastrowid)
        self.cur.execute("SELECT id FROM tools_tags WHERE name = ?", (clean,))
        return int(self.cur.fetchone()[0])

    def add_link_tags(self, link_id: int, tag_names: list[str], created_by: str) -> None:
        """为链接挂 tag，幂等。tag 名已由调用方清洗去重。"""
        seen: set[str] = set()
        for name in tag_names:
            clean = name.strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            tag_id = self.get_or_create_tag(clean, created_by)
            self.cur.execute(
                "INSERT OR IGNORE INTO tools_link_tags (link_id, tag_id) VALUES (?, ?)",
                (int(link_id), tag_id),
            )
        self.conn.commit()
