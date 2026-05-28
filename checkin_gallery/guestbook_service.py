"""网页留言簿：匿名展示，登录后可留言与点赞。"""

from __future__ import annotations

from datetime import datetime

from core.database_manager import DbManager

MAX_CONTENT_LEN = 500
PAGE_SIZE_DEFAULT = 30
PAGE_SIZE_MAX = 100


def list_entries(
    viewer_user_id: str | None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), PAGE_SIZE_MAX))
    offset = (page - 1) * page_size
    viewer = int(viewer_user_id) if viewer_user_id else None

    db = DbManager()
    db.cur.execute("SELECT COUNT(*) FROM guestbook_entries")
    total = int(db.cur.fetchone()[0])

    db.cur.execute(
        """
        SELECT e.id, e.content, e.created_at,
               (SELECT COUNT(*) FROM guestbook_likes l WHERE l.entry_id = e.id) AS like_count
        FROM guestbook_entries e
        ORDER BY like_count DESC, e.created_at DESC, e.id DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )
    rows = db.cur.fetchall()

    items: list[dict] = []
    for eid, content, created_at, like_count in rows:
        liked = False
        if viewer is not None:
            db.cur.execute(
                "SELECT 1 FROM guestbook_likes WHERE entry_id = ? AND user_id = ?",
                (int(eid), viewer),
            )
            liked = db.cur.fetchone() is not None
        items.append(
            {
                "id": int(eid),
                "content": content,
                "created_at": (created_at or "")[:16],
                "like_count": int(like_count or 0),
                "liked": liked,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": offset + len(items) < total,
        "max_content_len": MAX_CONTENT_LEN,
    }


def post_entry(user_id: str, content: str) -> dict:
    text = (content or "").strip()
    if not text:
        raise ValueError("留言不能为空")
    if len(text) > MAX_CONTENT_LEN:
        raise ValueError(f"留言不能超过 {MAX_CONTENT_LEN} 字")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = DbManager()
    db.cur.execute(
        "INSERT INTO guestbook_entries (author_user_id, content, created_at) VALUES (?, ?, ?)",
        (int(user_id), text, now),
    )
    db.conn.commit()
    return {"message": "留言已发布", "id": int(db.cur.lastrowid)}


def like_entry(user_id: str, entry_id: int) -> dict:
    db = DbManager()
    db.cur.execute(
        "SELECT author_user_id FROM guestbook_entries WHERE id = ?",
        (int(entry_id),),
    )
    row = db.cur.fetchone()
    if not row:
        raise ValueError("留言不存在")

    uid = int(user_id)
    if int(row[0]) == uid:
        raise ValueError("不能给自己的留言点赞")

    db.cur.execute(
        "SELECT 1 FROM guestbook_likes WHERE entry_id = ? AND user_id = ?",
        (int(entry_id), uid),
    )
    if db.cur.fetchone():
        raise ValueError("你已经点过赞了")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.cur.execute(
        "INSERT INTO guestbook_likes (entry_id, user_id, created_at) VALUES (?, ?, ?)",
        (int(entry_id), uid, now),
    )
    db.conn.commit()

    db.cur.execute(
        "SELECT COUNT(*) FROM guestbook_likes WHERE entry_id = ?",
        (int(entry_id),),
    )
    count = int(db.cur.fetchone()[0])
    return {"message": "已点赞", "like_count": count, "liked": True}
