"""社区时间线事件发送助手（bot 侧）。

best-effort：发送/撤回失败仅记日志，绝不抛出、绝不阻塞业务主流程。
协议见 specs/timeline-protocol.md。
"""

import logging
from uuid import uuid4

import requests

from core.config import TIMELINE_TOKEN, TIMELINE_URL

logger = logging.getLogger(__name__)

_EVENT_PATH = "/api/timeline/events"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {TIMELINE_TOKEN}",
        "Content-Type": "application/json",
    }


def _post(payload: dict) -> None:
    for attempt in (1, 2):  # 至多重试一次
        try:
            resp = requests.post(
                f"{TIMELINE_URL}{_EVENT_PATH}", json=payload, headers=_headers(), timeout=5
            )
            resp.raise_for_status()
            return
        except Exception:
            if attempt == 2:
                logger.exception("时间线事件发送失败: %s", payload.get("id"))


def _request(method: str, url: str, **kwargs) -> None:
    for attempt in (1, 2):
        try:
            resp = requests.request(method, url, headers=_headers(), timeout=5, **kwargs)
            resp.raise_for_status()
            return
        except Exception:
            if attempt == 2:
                logger.exception("时间线请求失败: %s %s", method, url)


def emit_event(
    source: str,
    actor_id,
    actor_qq=None,
    title: str = "",
    description: str | None = None,
    target_url: str | None = None,
    target_type: str = "url",
    data: dict | None = None,
    dedup_key: str | None = None,
) -> None:
    """向 Event Server 发送事件。id 由本函数生成（<source>:<uuid>），天然幂等。"""
    payload: dict = {
        "id": f"{source}:{uuid4().hex}",
        "source": source,
        "actor": {"id": str(actor_id)},
        "display": {"title": title},
    }
    if actor_qq is not None:
        payload["actor"]["qq"] = str(actor_qq)
    if description:
        payload["display"]["description"] = description
    if target_url:
        payload["target"] = {"type": target_type or "url", "url": target_url}
    if data is not None:
        payload["data"] = data
    if dedup_key:
        payload["dedup_key"] = dedup_key
    _post(payload)


def retract_event(source: str, dedup_key: str | None = None, event_id: str | None = None) -> None:
    """撤回事件（硬删除）。dedup_key 或 event_id 二选一；业务回滚走 dedup_key。"""
    if dedup_key:
        _request(
            "delete",
            f"{TIMELINE_URL}{_EVENT_PATH}/by-key",
            params={"source": source, "key": dedup_key},
        )
    elif event_id:
        _request("delete", f"{TIMELINE_URL}{_EVENT_PATH}/{event_id}")
    else:
        logger.warning("retract_event: dedup_key 与 event_id 均为空，忽略")
