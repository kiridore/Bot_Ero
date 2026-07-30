GAME_TITLE_IDS = {
    "first_game": 301,
    "civilian_win": 302,
    "spy_win": 303,
}


def grant_game_titles(dbmanager, user_id: str, role: str, winner: str):
    newly = []
    uid = user_id

    if not dbmanager.titles.has(uid, GAME_TITLE_IDS["first_game"]):
        dbmanager.titles.unlock(uid, GAME_TITLE_IDS["first_game"])
        newly.append(GAME_TITLE_IDS["first_game"])

    if role == "civilian" and winner == "civilian":
        if not dbmanager.titles.has(uid, GAME_TITLE_IDS["civilian_win"]):
            dbmanager.titles.unlock(uid, GAME_TITLE_IDS["civilian_win"])
            newly.append(GAME_TITLE_IDS["civilian_win"])

    if role == "spy" and winner == "spy":
        if not dbmanager.titles.has(uid, GAME_TITLE_IDS["spy_win"]):
            dbmanager.titles.unlock(uid, GAME_TITLE_IDS["spy_win"])
            newly.append(GAME_TITLE_IDS["spy_win"])

    if newly:
        from plugins.title import evaluate_and_unlock_titles
        evaluate_and_unlock_titles(dbmanager, uid)

    return newly
