"""MCP stdio 启动逻辑（供 run_stdio.py / python -m botero_mcp 共用）。"""

from __future__ import annotations

import argparse
import os

from botero_mcp._bootstrap import bootstrap, configure_database
from botero_mcp.config import DB_PATH, DEFAULT_USER_ID


def main(argv: list[str] | None = None) -> None:
    bootstrap()

    parser = argparse.ArgumentParser(description="BotEro MCP 服务（stdio）")
    parser.add_argument("--db", default=None, help="data.db 绝对或相对路径")
    args = parser.parse_args(argv)

    if args.db:
        os.environ["BOTERO_DB_PATH"] = os.path.abspath(args.db)

    configure_database()

    db = os.environ.get("BOTERO_DB_PATH", str(DB_PATH))
    print(f"BotEro MCP | 数据库: {db}", flush=True)
    if DEFAULT_USER_ID:
        print(f"BotEro MCP | 默认 user_id: {DEFAULT_USER_ID}", flush=True)
    else:
        print(
            "BotEro MCP | 未设置 BOTERO_MCP_DEFAULT_USER_ID，工具调用需显式传入 user_id",
            flush=True,
        )

    from botero_mcp.server import mcp

    mcp.run()
