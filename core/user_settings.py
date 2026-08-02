"""通用个人设置存储层（绑定 QQ 号，bot 与 web 双进程共用）。

每用户一个 JSON 文件：server_data/user_settings/<user_id>.json
文件不存在 = 全默认值。各功能自行约定键名，深合并写入。

原子写（tmp + os.replace）防止出现写了一半的文件；每用户进程内锁
防止同进程并发读改写丢失更新；跨进程并发未加锁——写频率可忽略，属可接受风险。

已约定键：
    privacy.char_public: bool  是否允许他人查看我的角色卡（缺省 True）
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path

SETTINGS_ROOT = Path(os.environ.get("BOTERO_USER_SETTINGS_ROOT", "server_data/user_settings"))

_LOCKS: dict[str, threading.Lock] = {}


def _lock_for(user_id) -> threading.Lock:
    # ponytail: 每用户一锁，随用户数增长；群规模机器人可接受，量级上升再换全局锁或文件锁
    return _LOCKS.setdefault(str(user_id), threading.Lock())


def _settings_path(user_id) -> Path:
    uid = str(user_id).strip()
    if not uid.isdigit():
        raise ValueError(f"非法用户 ID: {user_id!r}")
    return SETTINGS_ROOT / uid


def _read(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def get_settings(user_id) -> dict:
    return _read(_settings_path(user_id))


def update_settings(user_id, patch: dict) -> dict:
    path = _settings_path(user_id)
    with _lock_for(user_id):
        merged = _deep_merge(_read(path), patch)
        _write(path, merged)
    return merged


def privacy_public(user_id) -> bool:
    return bool(get_settings(user_id).get("privacy", {}).get("char_public", True))
