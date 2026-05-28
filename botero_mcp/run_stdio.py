#!/usr/bin/env python3
"""BotEro MCP stdio 入口（用绝对路径调用，不依赖 cwd 与 python -m）。

示例（LLM / Cursor 与 BotEro 不在同一目录时）::

    C:\\Python314\\python.exe F:/Coding/Python/project/BotEro/botero_mcp/run_stdio.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 在导入 botero_mcp 包之前，把 BotEro 项目根加入 sys.path
_BOTERO_ROOT = Path(__file__).resolve().parent.parent
_root = str(_BOTERO_ROOT)
if _root not in sys.path:
    sys.path.insert(0, _root)

from botero_mcp.entry import main

if __name__ == "__main__":
    main()
