"""通过 OneBot HTTP 接口解析 QQ 昵称（群名片优先）。"""

from functools import lru_cache

import requests

from checkin_gallery import config


def _member_display_name(data: dict, user_id: str) -> str:
    card = (data.get("card") or "").strip()
    if card:
        return card
    nick = (data.get("nickname") or "").strip()
    if nick:
        return nick
    return str(user_id)


def _call_onebot(action: str, params: dict) -> dict | None:
    base = config.ONEBOT_HTTP_URL.rstrip("/")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if config.ONEBOT_TOKEN:
        headers["Authorization"] = f"Bearer {config.ONEBOT_TOKEN}"

    for url, body in (
        (f"{base}/{action}", params),
        (base, {"action": action, "params": params}),
    ):
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("status") == "ok":
                payload = data.get("data")
                return payload if isinstance(payload, dict) else {}
        except (requests.RequestException, ValueError):
            continue
    return None


@lru_cache(maxsize=4096)
def resolve_display_name(user_id: str) -> str:
    uid = str(user_id)
    try:
        qq = int(uid)
    except ValueError:
        return uid

    if config.GROUP_ID:
        info = _call_onebot(
            "get_group_member_info",
            {"group_id": config.GROUP_ID, "user_id": qq, "no_cache": False},
        )
        if info:
            return _member_display_name(info, uid)

    info = _call_onebot("get_stranger_info", {"user_id": qq, "no_cache": False})
    if info:
        return _member_display_name(info, uid)

    return uid
