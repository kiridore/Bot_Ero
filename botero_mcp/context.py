from __future__ import annotations

from botero_mcp import config


def resolve_user_id(user_id: str | None) -> str:
    raw = (user_id or "").strip() or config.DEFAULT_USER_ID
    if not raw:
        raise ValueError(
            "请传入 user_id，或设置环境变量 BOTERO_MCP_DEFAULT_USER_ID（QQ 号）"
        )
    if not str(raw).isdigit():
        raise ValueError("user_id 须为数字 QQ 号")
    return str(raw)
