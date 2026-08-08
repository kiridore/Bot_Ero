"""直播间模块：播放 SRS HTTP-FLV 流（live.littlero.tech/live/livestream.flv）。"""

import os
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from webapp import STATIC_DIR

router = APIRouter()

# 直播流地址（方案 A 状态探测与页面播放同源 URL；环境变量可覆盖，便于本地联调）
LIVE_FLV_URL = os.environ.get("BOTERO_LIVE_FLV_URL", "https://live.littlero.tech/live/livestream.flv")
PROBE_TIMEOUT_SECONDS = 2.0
PROBE_READ_BYTES = 4096


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


@router.get("/live")
def live_page():
    page = STATIC_DIR / "live.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少直播间页面")
    return FileResponse(page)
