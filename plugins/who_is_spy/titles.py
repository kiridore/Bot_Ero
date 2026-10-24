"""卧底正常结算的统计及称号；与结束记录共用调用方事务。"""
GAME_TITLE_THRESHOLDS = [
    ('total_games', 10, 301), ('total_games', 50, 302), ('total_games', 100, 303),
    ('total_wins', 10, 304), ('total_wins', 50, 305),
    ('civilian_wins', 10, 306), ('civilian_wins', 50, 307),
    ('spy_wins', 10, 308), ('spy_wins', 50, 309),
]


def grant_game_titles(dbmanager, user_id, role, winner, *, left=False):
    conn = dbmanager.conn
    if not conn.in_transaction:
        raise RuntimeError('游戏奖励必须与结束记录同事务')
    uid = str(user_id)
    won = int(not left and role == winner)
    conn.execute('''
        INSERT INTO user_game_stats (user_id, total_games, total_wins, civilian_wins, spy_wins)
        VALUES (?, 1, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET total_games = total_games + 1,
            total_wins = total_wins + excluded.total_wins,
            civilian_wins = civilian_wins + excluded.civilian_wins,
            spy_wins = spy_wins + excluded.spy_wins
    ''', (uid, won, won if role == 'civilian' else 0, won if role == 'spy' else 0))
    row = conn.execute('SELECT total_games, total_wins, civilian_wins, spy_wins FROM user_game_stats WHERE user_id = ?', (uid,)).fetchone()
    stats = dict(zip(('total_games', 'total_wins', 'civilian_wins', 'spy_wins'), row))
    newly = []
    for key, threshold, tid in GAME_TITLE_THRESHOLDS:
        if left and key != 'total_games':
            continue
        if stats[key] >= threshold and not dbmanager.titles.has(uid, tid):
            dbmanager.titles.unlock(uid, tid, commit=False)
            newly.append(tid)
    if newly:
        from plugins.title.logic import evaluate_and_unlock_titles
        newly.extend(evaluate_and_unlock_titles(dbmanager, uid, commit=False))
    return newly
