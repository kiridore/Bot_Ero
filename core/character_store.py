"""角色卡 JSON 文件存储层（bot 与 web 双进程共用）。

存储布局：
    server_data/trpg_chars/<user_id>/meta.json        # {"current_id": 3, "order": [1,2,3]}
    server_data/trpg_chars/<user_id>/<char_id>.json   # 单个角色完整数据（任意嵌套 dict）

所有写入均为原子写（tmp + os.replace），跨进程并发安全。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CHARS_ROOT = Path(os.environ.get("BOTERO_TRPG_CHARS_ROOT", "server_data/trpg_chars"))


def _validate_user_id(user_id) -> str:
    uid = str(user_id).strip()
    if not uid.isdigit():
        raise ValueError(f"非法用户 ID: {user_id!r}")
    return uid


def _validate_char_id(char_id) -> int:
    try:
        cid = int(char_id)
    except (TypeError, ValueError):
        raise ValueError(f"非法角色 ID: {char_id!r}") from None
    if cid <= 0:
        raise ValueError(f"非法角色 ID: {char_id!r}")
    return cid


def _user_dir(user_id) -> Path:
    return CHARS_ROOT / _validate_user_id(user_id)


def _char_path(user_id, char_id) -> Path:
    return _user_dir(user_id) / str(_validate_char_id(char_id))


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _load_meta(user_id) -> dict:
    meta = _read_json(_user_dir(user_id) / "meta.json")
    meta.setdefault("current_id", None)
    meta.setdefault("order", [])
    return meta


def _save_meta(user_id, meta: dict) -> None:
    _write_json(_user_dir(user_id) / "meta.json", meta)


def list_chars(user_id) -> list[dict]:
    meta = _load_meta(user_id)
    out = []
    for cid in meta["order"]:
        data = get_char(user_id, cid)
        if data:
            out.append(data)
    return out


def get_char(user_id, char_id) -> dict | None:
    path = _char_path(user_id, char_id)
    if not path.is_file():
        return None
    data = _read_json(path)
    if not data:
        return None
    data["id"] = _validate_char_id(char_id)
    data["user_id"] = _validate_user_id(user_id)
    return data


def get_current(user_id) -> dict | None:
    cid = _load_meta(user_id)["current_id"]
    return get_char(user_id, cid) if cid is not None else None


def create_char(user_id, data: dict) -> int:
    uid = _validate_user_id(user_id)
    meta = _load_meta(uid)
    next_id = max(meta["order"], default=0) + 1
    meta["order"].append(next_id)
    if meta["current_id"] is None:
        meta["current_id"] = next_id
    _write_json(_char_path(uid, next_id), data)
    _save_meta(uid, meta)
    return next_id


def update_char(user_id, char_id, data: dict) -> None:
    path = _char_path(user_id, char_id)
    if not path.is_file():
        raise ValueError("角色不存在")
    _write_json(path, data)


def delete_char(user_id, char_id) -> None:
    uid = _validate_user_id(user_id)
    cid = _validate_char_id(char_id)
    path = _char_path(uid, cid)
    if path.is_file():
        path.unlink()
    meta = _load_meta(uid)
    if cid in meta["order"]:
        meta["order"].remove(cid)
    if meta["current_id"] == cid:
        meta["current_id"] = meta["order"][0] if meta["order"] else None
        if meta["current_id"] is None:
            meta.pop("current_id", None)
    _save_meta(uid, meta)


def set_current(user_id, char_id) -> None:
    uid = _validate_user_id(user_id)
    cid = _validate_char_id(char_id)
    if not _char_path(uid, cid).is_file():
        raise ValueError("角色不存在")
    meta = _load_meta(uid)
    meta["current_id"] = cid
    _save_meta(uid, meta)
