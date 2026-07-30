from core.cq import text
from core.api import ApiWrapper


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
