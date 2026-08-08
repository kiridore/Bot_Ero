"""直播间模块：播放 SRS HTTP-FLV 流（live.littlero.tech/live/livestream.flv）+ 观众在场。"""

import os
import threading
import time
from typing import Annotated
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.onebot_client import resolve_display_name
from core.web.auth_deps import get_optional_user_id
from webapp import STATIC_DIR

router = APIRouter()

# 直播流地址（方案 A 状态探测与页面播放同源 URL；环境变量可覆盖，便于本地联调）
LIVE_FLV_URL = os.environ.get("BOTERO_LIVE_FLV_URL", "https://live.littlero.tech/live/livestream.flv")
PROBE_TIMEOUT_SECONDS = 2.0
PROBE_READ_BYTES = 4096

# —— 观众在场（进程内存态；webapp 恒为单 worker 单进程，无需跨进程存储） ——
PRESENCE_TTL_SECONDS = 75      # 超过该时长无心跳视为离开
HEARTBEAT_MIN_INTERVAL = 10    # 同一 client 心跳最小间隔（防刷）

_presence: dict[str, dict] = {}
_presence_lock = threading.Lock()


class HeartbeatIn(BaseModel):
    client_id: str


def _prune_presence(now: float) -> None:
    for cid in [
        cid for cid, v in _presence.items() if now - v["last_seen"] > PRESENCE_TTL_SECONDS
    ]:
        _presence.pop(cid, None)


def _stream_online() -> bool:
    """数据流探测（方案 A）：请求 FLV 流并读取前几秒，收到任意字节视为在线。

    - 直播中：SRS 立即下发 FLV 头与 GOP 数据 → True
    - 未开播：SRS 挂住连接不下发数据 → 读超时 → False
    - 链路故障/404：异常 → False
    """
    try:
        with urlopen(LIVE_FLV_URL, timeout=PROBE_TIMEOUT_SECONDS) as resp:
            return bool(resp.read(PROBE_READ_BYTES))
    except Exception:
        return False


@router.get("/api/live/status")
def live_status():
    return {"online": _stream_online()}


@router.post("/api/live/heartbeat")
def live_heartbeat(
    body: HeartbeatIn,
    user_id: Annotated[str | None, Depends(get_optional_user_id)],
):
    """观众心跳：登录态（Bearer token）解析昵称，匿名仅记 client_id。"""
    cid = body.client_id.strip()
    if not cid or len(cid) > 64:
        return {"ok": False}
    now = time.time()
    with _presence_lock:
        _prune_presence(now)
        prev = _presence.get(cid)
        if prev is not None and now - prev["last_seen"] < HEARTBEAT_MIN_INTERVAL:
            prev["last_seen"] = now  # 保活；身份信息保持原样
        else:
            _presence[cid] = {
                "user_id": user_id,
                "name": resolve_display_name(user_id) if user_id else None,
                "last_seen": now,
            }
    return {"ok": True}


@router.get("/api/live/viewers")
def live_viewers():
    """当前观众列表：已登录按 user_id 去重显示昵称，匿名单个显示。

    返回: {"viewers": [{"name": str, "member": bool}...], "count": int}
    """
    now = time.time()
    with _presence_lock:
        _prune_presence(now)
        members: dict[str, str] = {}
        anonymous: list[str] = []
        for cid, v in _presence.items():
            if v["user_id"]:
                members.setdefault(v["user_id"], v["name"] or v["user_id"])
            else:
                anonymous.append(f"匿名观众 #{cid[:4]}")
    viewers = [{"name": name, "member": True} for name in members.values()]
    viewers += [{"name": name, "member": False} for name in anonymous]
    viewers.sort(key=lambda it: (not it["member"], it["name"]))
    return {"viewers": viewers, "count": len(viewers)}


@router.get("/live")
def live_page():
    page = STATIC_DIR / "live.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少直播间页面")
    return FileResponse(page)
