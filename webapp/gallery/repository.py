import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from webapp.gallery import config
from webapp.gallery.config import REMEDY_MARKER


@dataclass(frozen=True)
class CheckinImage:
    id: int
    user_id: str
    checkin_date: str
    content: str
    image_path: Optional[Path]


def _normalize_image_name(content: str) -> str:
    return content.replace("{", "").replace("}", "").replace("-", "")


def resolve_image_path(user_id: str | int, content: str) -> Optional[Path]:
    image_name = _normalize_image_name(content)
    folder = config.IMAGE_ROOT / str(user_id)
    for name in (image_name, image_name.lower()):
        candidate = folder / name
        if candidate.is_file():
            return candidate
    return None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_user_ids() -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT CAST(user_id AS TEXT) AS user_id
            FROM checkin_records
            WHERE content != ?
            ORDER BY user_id
            """,
            (REMEDY_MARKER,),
        ).fetchall()
    return [r["user_id"] for r in rows]


def _build_where(
    user_id: Optional[str],
    year: Optional[int],
) -> tuple[str, list]:
    clauses = ["content != ?"]
    params: list = [REMEDY_MARKER]
    if user_id is not None:
        clauses.append("CAST(user_id AS TEXT) = ?")
        params.append(str(user_id))
    if year is not None:
        clauses.append("checkin_date BETWEEN ? AND ?")
        params.extend((f"{year}-01-01 00:00:00", f"{year}-12-31 23:59:59"))
    return " AND ".join(clauses), params


def fetch_checkins_paginated(
    *,
    user_id: Optional[str] = None,
    year: Optional[int] = None,
    page: int = 1,
    page_size: int = 40,
    only_with_file: bool = True,
) -> tuple[list[CheckinImage], int, bool]:
    """分页查询；仅含本地图片时通过游标式扫描满足 offset/limit。"""
    where, params = _build_where(user_id, year)
    sql = f"""
        SELECT id, user_id, checkin_date, content
        FROM checkin_records
        WHERE {where}
        ORDER BY checkin_date DESC, id DESC
    """
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    if not only_with_file:
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        slice_rows = rows[start:end]
        items = [
            CheckinImage(
                id=r["id"],
                user_id=str(r["user_id"]),
                checkin_date=r["checkin_date"],
                content=r["content"],
                image_path=resolve_image_path(r["user_id"], r["content"]),
            )
            for r in slice_rows
        ]
        return items, total, end < total

    matched: list[CheckinImage] = []
    for row in rows:
        path = resolve_image_path(row["user_id"], row["content"])
        if path is None:
            continue
        matched.append(
            CheckinImage(
                id=row["id"],
                user_id=str(row["user_id"]),
                checkin_date=row["checkin_date"],
                content=row["content"],
                image_path=path,
            )
        )

    total = len(matched)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = matched[start:end]
    return page_items, total, end < total


def fetch_user_year_rows(user_id: str, year: int) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT id, user_id, checkin_date, content
            FROM checkin_records
            WHERE CAST(user_id AS TEXT) = ?
            AND checkin_date BETWEEN ? AND ?
            ORDER BY checkin_date ASC
            """,
            (str(user_id), f"{year}-01-01 00:00:00", f"{year}-12-31 23:59:59"),
        ).fetchall()


def fetch_user_settlement_day(
    user_id: str,
    day_key: str,
    *,
    only_with_file: bool = True,
) -> list[CheckinImage]:
    from webapp.gallery.dates import settlement_day_range

    start, end = settlement_day_range(day_key)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, checkin_date, content
            FROM checkin_records
            WHERE CAST(user_id AS TEXT) = ?
            AND content != ?
            AND checkin_date BETWEEN ? AND ?
            ORDER BY checkin_date ASC, id ASC
            """,
            (str(user_id), REMEDY_MARKER, start, end),
        ).fetchall()
    items: list[CheckinImage] = []
    for row in rows:
        path = resolve_image_path(row["user_id"], row["content"])
        if only_with_file and path is None:
            continue
        items.append(
            CheckinImage(
                id=row["id"],
                user_id=str(row["user_id"]),
                checkin_date=row["checkin_date"],
                content=row["content"],
                image_path=path,
            )
        )
    return items
