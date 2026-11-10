"""通过 OneBot HTTP 接口解析 QQ 昵称（群名片优先）。"""

from functools import lru_cache

import requests

from core.config import GROUP_ID, ONEBOT_HTTP_URL, ONEBOT_TOKEN


# OneBot HTTP 通常在本地/内网，MUST NOT 跟随 HTTP(S)_PROXY（进程级代理会把内部调用掠去导致 502/超时）
_session = requests.Session()
_session.trust_env = False


def _member_display_name(data: dict, user_id: str) -> str:
    card = (data.get("card") or "").strip()
    if card:
        return card
    nick = (data.get("nickname") or "").strip()
    if nick:
        return nick
    return str(user_id)


def _call_onebot(action: str, params: dict, timeout: float = 8) -> dict | None:
    base = ONEBOT_HTTP_URL.rstrip("/")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if ONEBOT_TOKEN:
        headers["Authorization"] = f"Bearer {ONEBOT_TOKEN}"

    for url, body in (
        (f"{base}/{action}", params),
        (base, {"action": action, "params": params}),
    ):
        try:
            resp = _session.post(url, json=body, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("status") == "ok":
                payload = data.get("data")
                return payload if isinstance(payload, dict) else {}
        except (requests.RequestException, ValueError):
            continue
    return None


def resolve_group_name(group_id) -> str:
    """取群名；接口不可用时返回空串（调用方 MUST NOT 因此中断录制）。"""
    try:
        gid = int(group_id)
    except (TypeError, ValueError):
        return ""
    # 群名只是展示用：用短超时，避免录制开始被不可达的 OneBot HTTP 拖住（两种 URL 写法各试一次）
    data = _call_onebot("get_group_info", {"group_id": gid}, timeout=3)
    if not data:
        return ""
    return str(data.get("group_name") or "")


@lru_cache(maxsize=4096)
def resolve_display_name(user_id: str) -> str:
    uid = str(user_id)
    try:
        qq = int(uid)
    except ValueError:
        return uid

    if GROUP_ID:
        info = _call_onebot(
            "get_group_member_info",
            {"group_id": GROUP_ID, "user_id": qq, "no_cache": False},
        )
        if info:
            return _member_display_name(info, uid)

    info = _call_onebot("get_stranger_info", {"user_id": qq, "no_cache": False})
    if info:
        return _member_display_name(info, uid)

    return uid


@lru_cache(maxsize=4096)
def resolve_avatar_url(user_id: str) -> str:
    try:
        qq = int(user_id)
    except ValueError:
        return ""
    data = _call_onebot("get_qq_avatar", {"user_id": qq})
    if not data:
        return ""
    return str(data.get("url") or "")
