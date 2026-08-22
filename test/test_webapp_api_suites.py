"""脚本式集成套件回归：子进程运行 ``test/scripts/check_*.py``。

这些套件是模块级顺序执行的长链路行为测试（webapp API + 全新临时 DB + 真实
FastAPI TestClient），依赖**独立进程**才能各自拿到干净的 ``BOTERO_DB_PATH``
（``core.config`` 首次 import 冻结路径，见 test/conftest.py 说明），因此不能
作为 pytest 用例进程内收集，由本模块以子进程方式纳入统一回归。

新增套件只需放入 ``test/scripts/check_*.py``（模块级自校验、失败时退出码非 0），
本模块自动发现，无需登记。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUITES_DIR = Path(__file__).resolve().parent / "scripts"
SUITES = sorted(SUITES_DIR.glob("check_*.py"))


def test_webapp_api_suites_exist():
    """套件目录非空，防止 glob 失配导致回归静默消失。"""
    assert SUITES, f"未发现任何脚本式套件：{SUITES_DIR}"


@pytest.mark.parametrize("script", SUITES, ids=[p.name for p in SUITES])
def test_webapp_api_suite(script: Path):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"{script.name} 退出码 {proc.returncode}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
