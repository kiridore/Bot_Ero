import json
import random
import os

from core.logger import logger


def _load_words() -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), "words.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("加载卧底词库失败")
        return []


def assign_words(room: dict) -> bool:
    words = _load_words()
    if not words:
        return False

    used = room.get("word_history", [])
    candidates = [w for w in words if w["civilian"] not in used]
    if not candidates:
        candidates = words

    pair = random.choice(candidates)
    room["civilian_word"] = pair["civilian"]
    room["spy_word"] = pair["spy"]
    room["word_history"].append(pair["civilian"])
    if len(room["word_history"]) > 10:
        room["word_history"] = room["word_history"][-10:]

    total = len(room["players"])
    if total <= 5:
        spy_count = 1
    elif total <= 8:
        spy_count = random.choice([1, 2])
    else:
        spy_count = 2

    pids = list(room["players"].keys())
    random.shuffle(pids)
    spy_ids = set(pids[:spy_count])

    for pid in pids:
        p = room["players"][pid]
        if pid in spy_ids:
            p["role"] = "spy"
            p["word"] = pair["spy"]
        else:
            p["role"] = "civilian"
            p["word"] = pair["civilian"]

    aliases = [f"{i}号" for i in range(1, total + 1)]
    random.shuffle(aliases)
    for pid, alias in zip(pids, aliases):
        room["players"][pid]["alias"] = alias

    return True


def start_game(room: dict) -> str:
    if room["phase"] != "waiting":
        return "游戏已开始"
    if len(room["players"]) < room.get("min_players", 3):
        return f"人数不足，至少需要 {room.get('min_players', 3)} 人"
    if not assign_words(room):
        return "词库加载失败，无法开始游戏"

    room["phase"] = "playing_describe"
    room["round_num"] = 1
    room["ready_descriptions"] = {}
    room["votes"] = {}
    return "ok"


def collect_description(room: dict, user_id: str, text_body: str) -> bool | str:
    if room["phase"] != "playing_describe":
        return "当前不是描述阶段"
    p = room["players"].get(user_id)
    if not p or not p["alive"]:
        return "你已出局"
    if user_id in room["ready_descriptions"]:
        return "你已经描述过了"

    room["ready_descriptions"][user_id] = text_body

    alive = [pid for pid, pp in room["players"].items() if pp["alive"]]
    if len(room["ready_descriptions"]) >= len(alive):
        return True
    return "ok"


def advance_to_voting(room: dict):
    room["phase"] = "playing_vote"
    room["votes"] = {}


CIRCLED = {"①": 1, "②": 2, "③": 3, "④": 4, "⑤": 5, "⑥": 6, "⑦": 7, "⑧": 8, "⑨": 9, "⑩": 10}


def _parse_vote(raw: str) -> int | None:
    raw = raw.strip()
    if raw in CIRCLED:
        return CIRCLED[raw]
    raw = raw.rstrip("号").strip()
    try:
        return int(raw)
    except ValueError:
        return None


def collect_vote(room: dict, user_id: str, raw: str) -> bool | str:
    if room["phase"] != "playing_vote":
        return "当前不是投票阶段"
    p = room["players"].get(user_id)
    if not p or not p["alive"]:
        return "你已出局"
    if user_id in room["votes"]:
        return "你已经投过票了"

    target_num = _parse_vote(raw)
    if target_num is None:
        return "请回复玩家编号（如 1 / ①）"

    target = None
    for pid, pp in room["players"].items():
        if pp["alive"] and pp["alias"].startswith(str(target_num)):
            target = pid
            break
    if not target:
        return "无效的编号，请输入正确编号"
    if target == user_id:
        return "不能投给自己"

    room["votes"][user_id] = target
    alive = [pid for pid, pp in room["players"].items() if pp["alive"]]
    if len(room["votes"]) >= len(alive):
        return True
    return "ok"


def tally_votes(room: dict) -> str:
    counts: dict[str, int] = {}
    for voted_uid in room["votes"].values():
        counts[voted_uid] = counts.get(voted_uid, 0) + 1

    max_votes = max(counts.values()) if counts else 0
    tied = [uid for uid, c in counts.items() if c == max_votes]

    if len(tied) == 1:
        eliminated = tied[0]
    else:
        alive = [pid for pid, pp in room["players"].items() if pp["alive"]]
        not_voted = [uid for uid in alive if uid not in counts]
        if not_voted:
            eliminated = random.choice(not_voted)
        else:
            eliminated = random.choice(tied)

    room["players"][eliminated]["alive"] = False

    rec = {
        "round_num": room["round_num"],
        "descriptions": dict(room["ready_descriptions"]),
        "votes": dict(room["votes"]),
        "vote_counts": counts,
        "eliminated": eliminated,
    }
    room["history"].append(rec)
    return eliminated


def check_winner(room: dict) -> str | None:
    alive = [p for p in room["players"].values() if p["alive"]]
    spies = [p for p in alive if p["role"] == "spy"]
    civilians = [p for p in alive if p["role"] == "civilian"]
    if not spies:
        return "civilian"
    if len(spies) >= len(civilians):
        return "spy"
    return None


def advance_to_describe(room: dict):
    room["round_num"] += 1
    room["phase"] = "playing_describe"
    room["ready_descriptions"] = {}
