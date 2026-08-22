"""前端 DOM 渲染回归：子进程运行 ``test/test_*.js``（node 最小 DOM stub）。

议事厅（列表/详情/新建入口/编辑预填）、登录态、导航、时间线等页面的渲染逻辑
均以此方式验证（浏览器不可用环境的前端回归手段，见 kb/CONVENTIONS.md 模式 3）。
用例以项目根为 cwd（内部按相对路径读取 ``webapp/static/`` 与 ``core/web/static/``）。

新增用例只需放入 ``test/test_*.js``（自校验、失败时 ``process.exit(1)``），
本模块自动发现，无需登记。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JS_SUITES = sorted((Path(__file__).resolve().parent).glob("test_*.js"))


def test_dom_render_suites_exist():
    """用例目录非空，防止 glob 失配导致回归静默消失。"""
    assert JS_SUITES, f"未发现任何 DOM 渲染用例：{Path(__file__).resolve().parent}"


@pytest.mark.parametrize("script", JS_SUITES, ids=[p.name for p in JS_SUITES])
def test_dom_render_suite(script: Path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("未安装 node，跳过 DOM 渲染回归")
    proc = subprocess.run(
        [node, str(script)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"{script.name} 退出码 {proc.returncode}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
