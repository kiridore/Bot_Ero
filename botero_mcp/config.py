from __future__ import annotations

import os
from pathlib import Path

from botero_mcp._bootstrap import PROJECT_ROOT


def _path_from_env(key: str, default: Path) -> Path:
    raw = os.environ.get(key)
    return Path(raw) if raw else default


DB_PATH = _path_from_env("BOTERO_DB_PATH", PROJECT_ROOT / "data.db")
DEFAULT_USER_ID = (os.environ.get("BOTERO_MCP_DEFAULT_USER_ID") or "").strip() or None
