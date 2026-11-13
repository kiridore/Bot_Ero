"""通过 OneBot HTTP 接口解析 QQ 昵称（群名片优先）。"""

import time
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


def _call_onebot(action: str, params: dict, timeout: float = 8):
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
                # 群成员列表等接口返回数组，字典以外的返回一律视为空
                return payload if isinstance(payload, (dict, list)) else {}
        except (requests.RequestException, ValueError):
            continue
    return None


def resolve_group_name(group_id) -> str:
    """取群名；接口不可用时返回空串（调用方 MUST NOT 因此中断流程）。"""
    try:
        gid = int(group_id)
    except (TypeError, ValueError):
        return ""
    # 群名只是展示用：用短超时，避免录制开始被不可达的 OneBot HTTP 拖住（两种 URL 写法各试一次）
    data = _call_onebot("get_group_info", {"group_id": gid}, timeout=3)
    if not data:
        return ""
    return str(data.get("group_name") or "")


def fetch_group_members(group_id, timeout: float = 5) -> list[dict] | None:
    """群成员名单：返回 [{user_id, nickname, is_robot}]；接口不可用返回 None。

    None 与「群里没人」区分，调用方据此拒绝开团而不是把群当空群。
    timeout 给 webapp 这类页面路径用更短的值，避免 OneBot 不可达时拖住请求。
    """
    try:
        gid = int(group_id)
    except (TypeError, ValueError):
        return None
    data = _call_onebot("get_group_member_list", {"group_id": gid, "no_cache": False}, timeout=timeout)
    if not isinstance(data, list):
        return None
    members = []
    for item in data:
        if not isinstance(item, dict) or item.get("user_id") is None:
            continue
        uid = str(item["user_id"])
        name = (item.get("card_or_nickname") or item.get("card") or item.get("nickname") or "").strip()
        members.append({"user_id": uid, "nickname": name or uid, "is_robot": bool(item.get("is_robot"))})
    return members


def fetch_group_list() -> set[int] | None:
    """机器人所在的群号集合；接口不可用返回 None（不能当成“一个群都没有”）。"""
    data = _call_onebot("get_group_list", {}, timeout=5)
    if not isinstance(data, list):
        return None
    groups = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            groups.add(int(item["group_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    return groups


_NAME_TTL_OK = 60      # 命中
_NAME_TTL_FAIL = 30    # 未命中（接口不可用时不至于每次请求都等超时）
_member_name_cache: dict[tuple[int, int], tuple[float, str]] = {}


def resolve_group_member_name(group_id, user_id, use_cache: bool = True) -> str:
    """取某个群的成员显示名（名片优先，其次 QQ 昵称）；取不到返回空串。

    webapp 每次打开名单都会问一次，所以带 TTL 缓存：成功 60 秒、失败 30 秒，
    避免 OneBot 不可达时每个请求都卡在超时上。
    """
    try:
        gid, uid = int(group_id), int(user_id)
    except (TypeError, ValueError):
        return ""
    key = (gid, uid)
    now = time.time()
    if use_cache:
        cached = _member_name_cache.get(key)
        if cached:
            age = now - cached[0]
            if age < (_NAME_TTL_OK if cached[1] else _NAME_TTL_FAIL):
                return cached[1]
    info = _call_onebot("get_group_member_info",
                        {"group_id": gid, "user_id": uid, "no_cache": True}, timeout=2)
    name = ""
    if info:
        name = str(info.get("card") or "").strip() or str(info.get("nickname") or "").strip()
    _member_name_cache[key] = (now, name)
    return name


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
