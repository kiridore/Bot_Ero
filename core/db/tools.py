"""工具箱：网页链接收藏（标题/简介/URL），公开可浏览，登录后可添加。"""

from datetime import datetime


class ToolsManager:
    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()

    @staticmethod
    def _like_escape(q: str) -> str:
        return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def list_tools(self, q: str | None = None) -> list[dict]:
        base = (
            "SELECT id, title, description, url, domain, created_by, created_at "
            "FROM tools_links"
        )
        query = (q or "").strip()
        if not query:
            self.cur.execute(base + " ORDER BY id DESC")
        else:
            escaped = self._like_escape(query)
            pattern = f"%{escaped}%"
            self.cur.execute(
                base
                + " WHERE (title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' "
                "OR url LIKE ? ESCAPE '\\') ORDER BY id DESC",
                (pattern, pattern, pattern),
            )
        rows = self.cur.fetchall()
        return [
            {
                "id": int(row[0]),
                "title": row[1],
                "description": row[2],
                "url": row[3],
                "domain": row[4],
                "created_by": row[5],
                "created_at": row[6],
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
