"""管理仪表盘子应用：插件启停与配置编辑（仅超级用户）。"""

import os
import shutil
import sqlite3
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core import config
from core.context import SYSTEM_PLUGINS
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

router = APIRouter()


def _require_super(user_id: str) -> None:
    if int(user_id) not in config.SUPER_USER:
        raise HTTPException(status_code=403, detail="仅超级用户")


def _plugin_keys() -> set[str]:
    """文件系统枚举 plugins/（包目录 + 裸 .py）；webapp 不 import plugins。"""
    root = config.PROJECT_ROOT / "plugins"
    keys = set()
    if root.is_dir():
        for p in sorted(root.iterdir()):
            if p.name.startswith("__"):
                continue
            if p.is_dir() and (p / "__init__.py").is_file():
                keys.add(p.name)
            elif p.is_file() and p.suffix == ".py":
                keys.add(p.stem)
    return keys


def _scope_label(gid: int) -> str:
    return "私聊" if gid == 0 else f"群 {gid}"


def _enabled_set(gid: int) -> set[str]:
    conn = sqlite3.connect(str(config.DB_PATH))
    rows = conn.execute(
        "SELECT plugin_name FROM group_plugin_config WHERE group_id = ?", (int(gid),)
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


class PluginToggleIn(BaseModel):
    group_id: int = Field(ge=0)
    plugin_key: str = Field(min_length=1, max_length=100)
    enabled: bool


class ConfigIn(BaseModel):
    yaml: str = Field(min_length=1)


@router.get("/api/admin/plugins/scopes")
def api_admin_scopes(user_id: Annotated[str, Depends(get_current_user_id)]):
    _require_super(user_id)
    conn = sqlite3.connect(str(config.DB_PATH))
    gids = [r[0] for r in conn.execute(
        "SELECT DISTINCT group_id FROM group_plugin_config").fetchall()]
    conn.close()
    seen = {0, config.DEFAULT_GROUP_ID, *gids}
    scopes = [
        {"group_id": g, "label": _scope_label(g), "is_default": g == config.DEFAULT_GROUP_ID}
        for g in sorted(seen)
    ]
    return {"scopes": scopes}


@router.get("/api/admin/plugins")
def api_admin_plugins(group_id: int, user_id: Annotated[str, Depends(get_current_user_id)]):
    _require_super(user_id)
    enabled = _enabled_set(group_id)
    plugins = [
        {"key": k, "enabled": k in enabled, "system": k in SYSTEM_PLUGINS}
        for k in sorted(_plugin_keys())
    ]
    return {"group_id": group_id, "label": _scope_label(group_id),
            "is_default": group_id == config.DEFAULT_GROUP_ID, "plugins": plugins}


@router.put("/api/admin/plugins")
def api_admin_toggle(body: PluginToggleIn, user_id: Annotated[str, Depends(get_current_user_id)]):
    _require_super(user_id)
    if body.plugin_key in SYSTEM_PLUGINS:
        raise HTTPException(status_code=400, detail="系统插件不可禁用")
    if body.plugin_key not in _plugin_keys():
        raise HTTPException(status_code=400, detail=f"插件不存在：{body.plugin_key}")
    conn = sqlite3.connect(str(config.DB_PATH))
    if body.enabled:
        conn.execute(
            "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)",
            (body.group_id, body.plugin_key),
        )
    else:
        conn.execute(
            "DELETE FROM group_plugin_config WHERE group_id = ? AND plugin_name = ?",
            (body.group_id, body.plugin_key),
        )
    conn.commit()
    conn.close()
    return {"ok": True, "key": body.plugin_key, "enabled": body.enabled}


def _validate_config(text: str) -> None:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"YAML 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="配置顶层必须是键值映射")
    for dotted in config._REQUIRED:
        section, _, key = dotted.partition(".")
        value = (data.get(section) or {}).get(key)
        if value is None or value == "" or value == []:
            raise HTTPException(status_code=400, detail=f"缺少必填配置项 {dotted}")


@router.get("/api/admin/config")
def api_admin_config_get(user_id: Annotated[str, Depends(get_current_user_id)]):
    _require_super(user_id)
    text = config.CONFIG_PATH.read_text(encoding="utf-8")
    return {"yaml": text, "path": config.CONFIG_PATH.name, "restart_hint": True}


@router.put("/api/admin/config")
def api_admin_config_put(body: ConfigIn, user_id: Annotated[str, Depends(get_current_user_id)]):
    _require_super(user_id)
    _validate_config(body.yaml)
    path = config.CONFIG_PATH
    if path.is_file():
        shutil.copyfile(path, Path(str(path) + ".bak"))
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(body.yaml, encoding="utf-8")
    os.replace(tmp, path)
    return {"ok": True}
