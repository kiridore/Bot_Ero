"""Web 子应用共享认证依赖（单进程合并后唯一权威副本）。"""

from typing import Annotated

from fastapi import Header, HTTPException

from core.auth import verify_login_key


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    uid = verify_login_key(authorization[7:].strip())
    if uid is None:
        raise HTTPException(status_code=401, detail="密钥无效")
    return uid


def get_optional_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return verify_login_key(authorization[7:].strip())
