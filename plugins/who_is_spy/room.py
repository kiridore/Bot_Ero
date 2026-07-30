import random
import string
from datetime import datetime

from core.logger import logger
import core.context as context


def _generate_room_id() -> str:
    chars = string.ascii_uppercase + string.digits
    with context.game_lock:
        existing = set(context.game_rooms.keys())
    for _ in range(100):
        rid = ''.join(random.choices(chars, k=4))
        if rid not in existing:
            return rid
    raise RuntimeError("无法生成房间号")


GAME_TYPES = frozenset({"卧底"})


def create_room(group_id: int, creator_id: int, game_type: str = "卧底", max_players: int = 6) -> str:
    rid = _generate_room_id()
    min_players = max(3, max_players - 2)
    room = {
        "room_id": rid,
        "game_type": game_type,
        "group_id": group_id,
        "creator_id": str(creator_id),
        "max_players": max_players,
        "min_players": min_players,
        "players": {},
        "phase": "waiting",
        "round_num": 0,
        "history": [],
        "civilian_word": "",
        "spy_word": "",
        "created_at": datetime.now().timestamp(),
        "ready_descriptions": {},
        "votes": {},
        "word_history": [],
    }
    with context.game_lock:
        context.game_rooms[rid] = room
    return rid


def get_room(room_id: str) -> dict | None:
    with context.game_lock:
        return context.game_rooms.get(room_id)


def remove_room(room_id: str):
    with context.game_lock:
        context.game_rooms.pop(room_id, None)


def add_player(room_id: str, user_id: int, nickname: str) -> str:
    uid = str(user_id)
    with context.game_lock:
        for r in context.game_rooms.values():
            if uid in r["players"]:
                return f"你已在房间 {r['room_id']} 中，请先 /离开或/退出"
        room = context.game_rooms.get(room_id)
        if not room:
            return "房间不存在"
        if room["phase"] != "waiting":
            return "游戏已开始，无法加入"
        if uid in room["players"]:
            return "你已在房间中"
        if len(room["players"]) >= room["max_players"]:
            return "房间已满"
        n = len(room["players"]) + 1
        alias = f"{n}号"
        room["players"][uid] = {
            "user_id": uid,
            "nickname": nickname,
            "alias": alias,
            "word": "",
            "role": "",
            "alive": True,
        }
    return f"已加入 {room['game_type']} 房间 {room_id}（{n}/{room['max_players']}），你的代号是 {alias}"


def remove_player(room_id: str, user_id: int) -> str:
    uid = str(user_id)
    with context.game_lock:
        room = context.game_rooms.get(room_id)
        if not room:
            return "房间不存在"
        if uid not in room["players"]:
            return "你不在这个房间中"
        if room["phase"] == "waiting":
            del room["players"][uid]
            for i, pid in enumerate(room["players"], 1):
                room["players"][pid]["alias"] = f"{i}号"
            if not room["players"]:
                context.game_rooms.pop(room_id, None)
                return "房间已解散"
            if uid == room["creator_id"]:
                new_creator = list(room["players"].keys())[0]
                old_alias = room["players"][new_creator]["alias"]
                room["creator_id"] = new_creator
            return f"已退出房间 {room_id}，房主已转移给 {old_alias}"
        room["players"][uid]["alive"] = False
    return "已退出房间（游戏中退出，自动视为弃权出局）"


def find_player_room(user_id: int) -> dict | None:
    uid = str(user_id)
    with context.game_lock:
        for r in context.game_rooms.values():
            if uid in r["players"]:
                return r
    return None


def get_player(room: dict, user_id: int) -> dict | None:
    return room["players"].get(str(user_id))


def list_rooms(group_id: int) -> list[dict]:
    result = []
    with context.game_lock:
        for r in context.game_rooms.values():
            if r["group_id"] == group_id:
                result.append(dict(r))
    return result
