"""Web 子应用共享认证依赖（单进程合并后唯一权威副本）。

登录凭证两个来源，优先级：Authorization: Bearer 头 → 根域 cookie
（页面导航带不了 header，cookie 是服务端页面门控的唯一凭据）。
"""

from typing import Annotated

from fastapi import Header, HTTPException, Request

from core.auth import verify_login_key

AUTH_COOKIE_NAME = "botero_key"


def _resolve_token(request: Request, authorization: str | None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    return request.cookies.get(AUTH_COOKIE_NAME)


def get_current_user_id(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    token = _resolve_token(request, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    uid = verify_login_key(token)
    if uid is None:
        raise HTTPException(status_code=401, detail="密钥无效")
    return uid


def get_optional_user_id(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    token = _resolve_token(request, authorization)
    if not token:
        return None
    return verify_login_key(token)
