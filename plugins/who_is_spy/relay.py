import json
import os
from datetime import datetime

from core.cq import text
from core.api import ApiWrapper
from core.logger import logger


def _alive_list(room: dict) -> list[dict]:
    return [p for p in room["players"].values() if p["alive"]]


def broadcast(api: ApiWrapper, room: dict, message: list[dict]):
    for p in room["players"].values():
        if not p["alive"]:
            continue
        try:
            api.call_api("send_private_msg", {
                "user_id": int(p["user_id"]),
                "message": message,
            })
        except Exception:
            pass


def broadcast_descriptions(api: ApiWrapper, room: dict):
    descs = room["ready_descriptions"]
    alive = _alive_list(room)
    lines = [f"第{room['round_num']}轮 描述汇总："]
    for p in alive:
        txt = descs.get(p["user_id"], "（未描述）")
        lines.append(f"{p['alias']} \"{txt}\"")
    msg = text("\n".join(lines))
    broadcast(api, room, [msg])


def broadcast_vote_instructions(api: ApiWrapper, room: dict):
    alive = _alive_list(room)
    names = "  ".join(f"{p['alias']}" for p in alive)
    msg = text(
        f"第{room['round_num']}轮 投票阶段\n"
        f"请投票选出卧底，发送代号即可（如 1 号就回复 1）\n"
        f"存活玩家：{names}"
    )
    broadcast(api, room, [msg])


def broadcast_describe_instructions(api: ApiWrapper, room: dict):
    alive = _alive_list(room)
    names = "  ".join(f"{p['alias']}" for p in alive)
    msg = text(
        f"第{room['round_num']}轮 描述阶段\n"
        f"请用一句话描述你的词条（不能直接说出词）\n"
        f"存活玩家：{names}"
    )
    broadcast(api, room, [msg])


def broadcast_vote_result(api: ApiWrapper, room: dict, eliminated_uid: str):
    alive = _alive_list(room)
    vote_counts: dict[str, int] = {}
    for v in room["votes"].values():
        vote_counts[v] = vote_counts.get(v, 0) + 1
    lines = [f"第{room['round_num']}轮 投票结果："]
    for p in alive:
        cnt = vote_counts.get(p["user_id"], 0)
        marker = " ← 出局" if p["user_id"] == eliminated_uid else ""
        lines.append(f"{p['alias']} {cnt}票{marker}")
    lines.append("")
    elim = room["players"][eliminated_uid]
    lines.append(f"{elim['alias']} 的角色是：{'卧底' if elim['role'] == 'spy' else '平民'}")
    lines.append(f"他的词条是：{elim['word']}")
    if elim["role"] == "spy":
        lines.append(f"平民词条是：{room['civilian_word']}")
    msg = text("\n".join(lines))
    broadcast(api, room, [msg])


def broadcast_game_over(api: ApiWrapper, room: dict, winner: str):
    winner_label = "平民" if winner == "civilian" else "卧底"
    lines = [f"游戏结束！{winner_label}胜利！", ""]
    pid_to_alias = sorted(
        ((p["alias"], int(pid), p) for pid, p in room["players"].items()),
        key=lambda x: int(x[1]),
    )
    lines.append("身份揭晓：")
    for alias, uid, p in pid_to_alias:
        role_label = "平民" if p["role"] == "civilian" else "卧底"
        lines.append(f"{alias} {p['nickname']} - {role_label} - \"{p['word']}\"")
    broadcast(api, room, [text("\n".join(lines))])


def build_forward_nodes(room: dict) -> list[dict]:
    nodes = []
    nodes.append({
        "type": "node",
        "data": {
            "user_id": "0",
            "nickname": "系统",
            "content": [text("谁是卧底 游戏记录")],
        },
    })
    p_info = "\n".join(
        f"{p['alias']} {p['nickname']}"
        for _, p in sorted(room["players"].items(), key=lambda x: int(x[0]))
    )
    nodes.append({
        "type": "node",
        "data": {
            "user_id": "0",
            "nickname": "系统",
            "content": [text(f"玩家列表：\n{p_info}")],
        },
    })
    nodes.append({
        "type": "node",
        "data": {
            "user_id": "0",
            "nickname": "系统",
            "content": [text(f"平民词条：{room['civilian_word']}    卧底词条：{room['spy_word']}")],
        },
    })
    for rec in room["history"]:
        rn = rec["round_num"]
        nodes.append({
            "type": "node",
            "data": {
                "user_id": "0",
                "nickname": "系统",
                "content": [text(f"──── 第{rn}轮 ────")],
            },
        })
        for uid, desc in rec.get("descriptions", {}).items():
            p = room["players"].get(uid, {})
            nodes.append({
                "type": "node",
                "data": {
                    "user_id": uid,
                    "nickname": p.get("alias", "?"),
                    "content": [text(f"描述：{desc}")],
                },
            })
        elim = rec.get("eliminated")
        if elim:
            p = room["players"].get(elim, {})
            nodes.append({
                "type": "node",
                "data": {
                    "user_id": "0",
                    "nickname": "系统",
                    "content": [text(f"{p.get('alias', '?')} 出局 - {'卧底' if p.get('role') == 'spy' else '平民'}")],
                },
            })
    winner_label = "平民" if room.get("_winner") == "civilian" else "卧底"
    nodes.append({
        "type": "node",
        "data": {
            "user_id": "0",
            "nickname": "系统",
            "content": [text(f"{winner_label}胜利！")],
        },
    })
    return nodes


def send_forward_to_group(api: ApiWrapper, group_id: int, nodes: list[dict]):
    api.call_api("send_group_forward_msg", {
        "group_id": group_id,
        "messages": nodes,
    })


def save_game_record(room: dict):
    record = {
        "room_id": room["room_id"],
        "game_type": room.get("game_type", "卧底"),
        "group_id": room["group_id"],
        "created_at": room.get("created_at", 0),
        "ended_at": datetime.now().timestamp(),
        "winner": room.get("_winner", ""),
        "civilian_word": room.get("civilian_word", ""),
        "spy_word": room.get("spy_word", ""),
        "players": [
            {"user_id": p["user_id"], "nickname": p["nickname"],
             "alias": p["alias"], "role": p["role"], "word": p["word"]}
            for p in room["players"].values()
        ],
        "history": room.get("history", []),
    }
    base = f"server_data/game_records/{room['group_id']}"
    os.makedirs(base, exist_ok=True)
    path = f"{base}/{room['room_id']}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("保存游戏记录失败")


def get_saved_records(group_id: int) -> list[dict]:
    base = f"server_data/game_records/{group_id}"
    if not os.path.isdir(base):
        return []
    records = []
    for fname in os.listdir(base):
        if not fname.endswith(".json"):
            continue
        path = f"{base}/{fname}"
        try:
            with open(path, "r", encoding="utf-8") as f:
                records.append(json.load(f))
        except Exception:
            logger.exception(f"读取游戏记录失败: {path}")
    records.sort(key=lambda r: r.get("ended_at", 0), reverse=True)
    return records


def format_record_summary(data: dict) -> str:
    ts = datetime.fromtimestamp(data.get("ended_at", 0)).strftime("%Y-%m-%d %H:%M")
    winner_label = "平民" if data.get("winner") == "civilian" else "卧底"
    n = len(data.get("players", []))
    lines = [
        f"游戏记录：{data.get('room_id', '?')}",
        f"游戏类型：{data.get('game_type', '?')}",
        f"结束时间：{ts}",
        f"参与人数：{n}",
        f"胜负结果：{winner_label}胜利",
        f"平民词条：{data.get('civilian_word', '?')}",
        f"卧底词条：{data.get('spy_word', '?')}",
        "",
        "玩家身份：",
    ]
    for p in data.get("players", []):
        role_label = "平民" if p.get("role") == "civilian" else "卧底"
        lines.append(f"  {p.get('alias', '?')} {p.get('nickname', '?')} - {role_label} - \"{p.get('word', '')}\"")
    lines.append("")
    for rec in data.get("history", []):
        rn = rec.get("round_num", 0)
        lines.append(f"──── 第{rn}轮 ────")
        uid_to_alias = {p["user_id"]: p["alias"] for p in data.get("players", [])}
        for uid, desc in rec.get("descriptions", {}).items():
            alias = uid_to_alias.get(uid, "?")
            lines.append(f"  {alias} \"{desc}\"")
        elim = rec.get("eliminated", "")
        counts = rec.get("vote_counts", {})
        if counts:
            parts = []
            for uid, alias in uid_to_alias.items():
                c = counts.get(uid, 0)
                marker = " (出局)" if uid == elim else ""
                parts.append(f"{alias} {c}票{marker}")
            lines.append(f"  投票结果：{'  '.join(parts)}")
        if elim:
            p = next((x for x in data.get("players", []) if x["user_id"] == elim), {})
            lines.append(f"  → {p.get('alias', '?')} 出局 - {'卧底' if p.get('role') == 'spy' else '平民'}")
        lines.append("")
    return "\n".join(lines)
