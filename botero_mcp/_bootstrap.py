"""将项目根目录加入 sys.path，并统一 DbManager / 图库的数据库路径。"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_sqlite_connect = sqlite3.connect
_db_configured = False


def bootstrap() -> Path:
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return PROJECT_ROOT


def configure_database() -> Path:
    """让 core.DbManager 的 data.db 与 BOTERO_DB_PATH（图库 repository）一致。"""
    global _db_configured
    db = Path(os.environ.get("BOTERO_DB_PATH", str(PROJECT_ROOT / "data.db"))).resolve()
    os.environ["BOTERO_DB_PATH"] = str(db)
    os.chdir(db.parent)

    if _db_configured:
        return db

    db_str = str(db)

    def _connect(database, *args, **kwargs):
        if database == "data.db":
            return _sqlite_connect(db_str, *args, **kwargs)
        return _sqlite_connect(database, *args, **kwargs)

    sqlite3.connect = _connect  # type: ignore[assignment]
    _db_configured = True
    return db
