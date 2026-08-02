"""通用个人设置存储层（绑定 QQ 号，bot 与 web 双进程共用）。

每用户一个 JSON 文件：server_data/user_settings/<user_id>.json
文件不存在 = 全默认值。各功能自行约定键名，深合并写入。

已约定键：
    privacy.char_public: bool  是否允许他人查看我的角色卡（缺省 True）
"""

from __future__ import annotations

import json
import os
from pathlib import Path

SETTINGS_ROOT = Path(os.environ.get("BOTERO_USER_SETTINGS_ROOT", "server_data/user_settings"))


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
    tmp = path.with_suffix(".tmp")
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
    merged = _deep_merge(_read(path), patch)
    _write(path, merged)
    return merged


def privacy_public(user_id) -> bool:
    return bool(get_settings(user_id).get("privacy", {}).get("char_public", True))
