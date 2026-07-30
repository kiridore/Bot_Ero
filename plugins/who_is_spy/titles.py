import sqlite3
from core.logger import logger
from core.database_manager import DbManager

GAME_TITLE_THRESHOLDS = [
    ("total_games", 10, 301),
    ("total_games", 50, 302),
    ("total_games", 100, 303),
    ("total_wins", 10, 304),
    ("total_wins", 50, 305),
    ("civilian_wins", 10, 306),
    ("civilian_wins", 50, 307),
    ("spy_wins", 10, 308),
    ("spy_wins", 50, 309),
]


def _ensure_stats_table():
    conn = sqlite3.connect("data.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_game_stats (
            user_id TEXT PRIMARY KEY,
            total_games INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            civilian_wins INTEGER DEFAULT 0,
            spy_wins INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


def grant_game_titles(dbmanager: DbManager, user_id: str, role: str, winner: str):
    _ensure_stats_table()
    uid = str(user_id)
    is_winner = role == winner
    civ_win = 1 if role == "civilian" and is_winner else 0
    spy_win = 1 if role == "spy" and is_winner else 0

    conn = sqlite3.connect("data.db")
    conn.execute("""
        INSERT INTO user_game_stats (user_id, total_games, total_wins, civilian_wins, spy_wins)
        VALUES (?, 1, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            total_games = total_games + 1,
            total_wins = total_wins + ?,
            civilian_wins = civilian_wins + ?,
            spy_wins = spy_wins + ?
    """, (uid, 1 if is_winner else 0, civ_win, spy_win, 1 if is_winner else 0, civ_win, spy_win))
    conn.commit()

    row = conn.execute(
        "SELECT total_games, total_wins, civilian_wins, spy_wins FROM user_game_stats WHERE user_id = ?",
        (uid,)
    ).fetchone()
    conn.close()

    if not row:
        return []

    stats = {"total_games": row[0], "total_wins": row[1], "civilian_wins": row[2], "spy_wins": row[3]}
    newly = []

    for stat_key, threshold, tid in GAME_TITLE_THRESHOLDS:
        if stats[stat_key] >= threshold and not dbmanager.titles.has(uid, tid):
            dbmanager.titles.unlock(uid, tid)
            newly.append(tid)

    if newly:
        from plugins.title import evaluate_and_unlock_titles
        evaluate_and_unlock_titles(dbmanager, uid)

    return newly
