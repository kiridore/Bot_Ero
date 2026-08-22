"""pytest 全局夹具与安全隔离。

本文件在 pytest 收集任何测试模块**之前**导入——在进程内首次 import core 之前
强制把全部 ``BOTERO_*`` 数据路径重定向到会话级临时目录，保证 ``pytest`` 回归
永不触碰真实 ``data.db`` / ``server_data/``（``core.config`` 在模块首次 import
时求值冻结环境变量，各测试文件模块级的 ``os.environ`` 赋值在统一进程下无效，
隔离必须在此处前置完成，见 kb/CONVENTIONS.md 陷阱：--db 启动参数不生效）。

布局约定：
- ``test/test_*.py``           进程内用例（unittest 风格，pytest 原生运行）
- ``test/scripts/check_*.py``  脚本式集成套件（模块级顺序执行，依赖独立进程
  拿全新临时 DB），由 ``test/test_webapp_api_suites.py`` 以子进程方式纳入回归，
  仍可单独 ``python test/scripts/check_<name>.py`` 运行
- ``test/test_*.js``           node 最小 DOM stub 渲染用例（含论坛 DOM 回归），
  由 ``test/test_dom_render_suites.py`` 以子进程方式纳入回归
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# —— 数据路径安全隔离（必须先于任何 core 导入执行）——
_TMP_DIR = tempfile.mkdtemp(prefix="botero_pytest_")
os.environ["BOTERO_DB_PATH"] = os.path.join(_TMP_DIR, "data.db")
os.environ["BOTERO_MESSAGE_LOG_DB_PATH"] = os.path.join(_TMP_DIR, "message_log.db")
for _key in (
    "BOTERO_IMAGE_ROOT",
    "BOTERO_TRPG_CHARS_ROOT",
    "BOTERO_USER_SETTINGS_ROOT",
    "BOTERO_ACTIVITY_ROOT",
    "BOTERO_FORUM_IMAGES_ROOT",
    "BOTERO_THUMB_CACHE",
):
    _sub = os.path.join(_TMP_DIR, _key.removeprefix("BOTERO_").lower())
    os.makedirs(_sub, exist_ok=True)
    os.environ[_key] = _sub
# OneBot HTTP 指向必然拒绝连接的地址：昵称/头像解析立即失败降级，避免测试等待网络超时
os.environ.setdefault("BOTERO_ONEBOT_HTTP", "http://127.0.0.1:1")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database_manager import init_schema  # noqa: E402

# 会话级兜底库：进程内若有代码经 DbManager/core.config 触达默认库，落在此处且带全量 schema
_conn = sqlite3.connect(os.environ["BOTERO_DB_PATH"])
init_schema(_conn, _conn.cursor())
_conn.commit()
_conn.close()

# LLM 子系统已弃用，test_llm.py 真实调用外部计费 API（需 DEEPSEEK_API_KEY 且有余额），
# 不纳入常规回归；仍可单独运行：python -m pytest test/test_llm.py
collect_ignore = ["test_llm.py"]
