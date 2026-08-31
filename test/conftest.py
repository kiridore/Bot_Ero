"""pytest 全局夹具与安全隔离。

本文件在 pytest 收集任何测试模块**之前**导入——在进程内首次 import core 之前
生成临时 ``config.yaml`` 并经 ``BOTERO_CONFIG`` 指向它，全部数据路径落在会话级
临时目录，保证 ``pytest`` 回归永不触碰真实 ``data.db`` / ``server_data/``
（``core.config`` 在模块首次 import 时求值冻结配置，各测试文件模块级的
``os.environ`` 赋值在统一进程下无效，隔离必须在此处前置完成，
见 kb/CONVENTIONS.md 陷阱：配置在 import 时冻结）。

布局约定：
- ``test/test_*.py``           进程内用例（unittest 风格，pytest 原生运行）
- ``test/scripts/check_*.py``  脚本式集成套件（模块级顺序执行，依赖独立进程
  拿全新临时配置），由 ``test/test_webapp_api_suites.py`` 以子进程方式纳入回归，
  仍可单独运行 ``python test/scripts/check_<name>.py``
- ``test/test_*.js``           node 最小 DOM stub 渲染用例（含论坛 DOM 回归），
  由 ``test/test_dom_render_suites.py`` 子进程纳入回归
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# —— 数据路径安全隔离（必须先于任何 core 导入执行）——
# 生成临时 config.yaml 并经 BOTERO_CONFIG 指向它，全部数据路径落在会话临时目录，
# 保证 pytest 回归永不触碰真实 data.db / server_data/。
_TMP_DIR = tempfile.mkdtemp(prefix="botero_pytest_")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))  # 复用 _env helper
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(_TMP_DIR)
_DB_PATH = os.path.join(_TMP_DIR, "data.db")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database_manager import init_schema  # noqa: E402

# 会话级兜底库：进程内若有代码经 DbManager/core.config 触达默认库，落在此处且带全量 schema
_conn = sqlite3.connect(_DB_PATH)
init_schema(_conn, _conn.cursor())
_conn.commit()
_conn.close()

# LLM 子系统已弃用，test_llm.py 真实调用外部计费 API（需 DEEPSEEK_API_KEY 且有余额），
# 不纳入常规回归；仍可单独运行：python -m pytest test/test_llm.py
collect_ignore = ["test_llm.py"]
