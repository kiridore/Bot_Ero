import sqlite3


TABLES_USER_ID = [
    "checkin_records",
    "user_assets",
    "user_titles",
    "user_title_state",
    "user_equipped_titles",
    "user_lottery_profile",
    "user_lottery_stats",
    "user_weekly_streak_reward_claims",
    "user_attendance_reward_claims",
    "user_lottery_daily_stats",
    "user_remedy_usage",
    "shop_user_buffs",
    "guestbook_likes",
    "immortal_lottery_bets",
    "quest_progress",
    "quest_completion_stats",
    "quest_weekly_clears",
]

TABLES_CREATOR_USER_ID = [
    "group_alarms",
    "guestbook_entries",
]


def purge_user(conn: sqlite3.Connection, user_id: int | str) -> dict[str, int]:
    deleted = {}
    uid_int = int(user_id)
    uid_str = str(uid_int)

    for table in TABLES_USER_ID:
        conn.execute(f"DELETE FROM {table} WHERE user_id IN (?, ?)", (uid_int, uid_str))
        deleted[table] = conn.total_changes

    for table in TABLES_CREATOR_USER_ID:
        col = "creator_user_id" if table == "group_alarms" else "author_user_id"
        conn.execute(f"DELETE FROM {table} WHERE {col} IN (?, ?)", (uid_int, uid_str))
        deleted[table] = conn.total_changes

    conn.commit()
    return deleted


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m core.db.purge_user <user_id>")
        sys.exit(1)

    user_id = sys.argv[1]
    conn = sqlite3.connect("data.db")
    conn.execute("PRAGMA foreign_keys=ON")
    result = purge_user(conn, user_id)
    print(f"Deleted rows for user {user_id}:")
    for table, count in result.items():
        if count:
            print(f"  {table}: {count}")
    conn.close()
