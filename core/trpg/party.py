"""跑团开团前状态：群角色标记与准备名单。

存放于 ``server_data/trpg_records/<群号>/pending.json``（与记录目录同根）。
写入用临时文件 + ``os.replace`` 原子替换；读取失败、损坏或版本不符按空名单处理，
不抛异常——准备状态丢失的代价只是重新准备一次，不值得让指令崩掉。
"""

import json
import os
from pathlib import Path

from core.logger import logger
import core.context as runtime_context
from core.trpg import records
from core.trpg.game_systems import DEFAULT_RULE

PENDING_NAME = "pending.json"
PENDING_VERSION = 1


def pending_path(group_id) -> Path:
    return records.group_dir(group_id) / PENDING_NAME


def default_pending(group_id) -> dict:
    return {"version": PENDING_VERSION, "group_id": group_id, "group_name": "",
            "roles": {}, "prepared": {}, "rules": DEFAULT_RULE}


def read_pending(group_id) -> dict:
    path = pending_path(group_id)
    empty = default_pending(group_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return empty
    except (OSError, ValueError):
        logger.warning("跑团准备状态读取失败，按空名单处理：%s", path)
        return empty
    if not isinstance(data, dict) or data.get("version") != PENDING_VERSION:
        return empty
    if not isinstance(data.get("roles"), dict) or not isinstance(data.get("prepared"), dict):
        return empty
    # 旧文件没有 rules / group_name 字段：补默认值，不强制重写盘
    if not isinstance(data.get("rules"), str) or not data["rules"]:
        data["rules"] = DEFAULT_RULE
    if not isinstance(data.get("group_name"), str):
        data["group_name"] = ""
    return data


def set_group_name(group_id, name: str) -> None:
    """把群名记进 pending.json：网页准备名单只能读文件，取不到 OneBot。"""
    name = str(name or "").strip()
    if not name:
        return
    data = read_pending(group_id)
    if data.get("group_name") == name:
        return
    data["group_name"] = name
    write_pending(group_id, data)


def write_pending(group_id, data: dict) -> None:
    path = pending_path(group_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def set_role(group_id, user_id, role: str, nickname: str = "") -> dict:
    """设置用户在本群的角色；role 为 "dm"/"ob"。DM 唯一，设新 DM 会顶掉旧 DM。

    昵称单独存 ``role_names``：DM/观察者不准备，没有准备快照可回落，
    网页准备名单要显示人话而不是 QQ 号。
    """
    data = read_pending(group_id)
    uid = str(user_id)
    if role == "dm":
        for other in [k for k, v in data["roles"].items() if v == "dm" and k != uid]:
            data["roles"].pop(other)
            data.setdefault("role_names", {}).pop(other, None)
    data["roles"][uid] = role
    names = data.setdefault("role_names", {})
    if nickname:
        names[uid] = nickname
    else:
        names.pop(uid, None)
    write_pending(group_id, data)
    return data


def clear_role(group_id, user_id) -> dict:
    data = read_pending(group_id)
    data["roles"].pop(str(user_id), None)
    data.setdefault("role_names", {}).pop(str(user_id), None)
    write_pending(group_id, data)
    return data


def set_prepared(group_id, user_id, snapshot: dict) -> dict:
    data = read_pending(group_id)
    data["prepared"][str(user_id)] = snapshot
    write_pending(group_id, data)
    return data


def clear_prepared(group_id, user_id) -> dict:
    data = read_pending(group_id)
    data["prepared"].pop(str(user_id), None)
    write_pending(group_id, data)
    return data


def clear_all(group_id) -> None:
    """开录成功后丢弃准备状态（本场团已开始）。"""
    try:
        pending_path(group_id).unlink()
    except FileNotFoundError:
        return


def set_rule(group_id, rule: str) -> dict:
    data = read_pending(group_id)
    data["rules"] = rule
    write_pending(group_id, data)
    return data


def current_rule(group_id) -> str:
    """本群当前生效的游戏规则。

    录制中以记录里的规则为准（开录后 pending.json 会被清空）；
    未录制时读准备状态；都没有则回默认规则。
    """
    if group_id is None:
        return DEFAULT_RULE
    session = runtime_context.get_recording_session(group_id)
    if session:
        return session.get("rules") or DEFAULT_RULE
    return read_pending(group_id)["rules"]
