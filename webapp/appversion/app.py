"""App 内更新清单子应用：GET /api/app/version。

清单由 config.yaml `app_update` 段驱动（APK 托管在外部对象存储，本服务不托管二进制）。
未配置（缺段或 apk_url 为空）返回 404，客户端静默跳过；
配置非法返回 500 + 字段级 detail，但不阻塞进程启动。
"""

import re
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import config
from core.web.auth_deps import get_current_user_id

router = APIRouter()

_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")


class AppVersionOut(BaseModel):
    version: str
    version_code: int
    apk_url: str
    sha256: str
    size: int
    notes: str
    min_supported_version_code: int
    published_at: str


def _int(cfg: dict, key: str) -> int:
    raw = cfg.get(key)
    if raw is None or raw == "":
        return 0
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise HTTPException(status_code=500, detail=f"app_update.{key} 必须是整数")
    try:
        return int(raw)
    except ValueError:
        raise HTTPException(status_code=500, detail=f"app_update.{key} 必须是整数") from None


def _manifest(cfg) -> dict:
    if not isinstance(cfg, dict):
        raise HTTPException(status_code=500, detail="app_update 配置必须是映射")
    apk_url = str(cfg.get("apk_url") or "").strip()
    if not apk_url:
        raise HTTPException(status_code=404, detail="未配置应用更新")
    split = urlsplit(apk_url)
    if split.scheme not in ("http", "https") or not split.netloc:
        raise HTTPException(status_code=500, detail="app_update.apk_url 必须是 http(s) 绝对直链")
    sha256 = str(cfg.get("sha256") or "").strip()
    if sha256 and not _SHA256_RE.fullmatch(sha256):
        raise HTTPException(status_code=500, detail="app_update.sha256 必须是 64 位十六进制")
    version = str(cfg.get("version") or "").strip()
    if not version:
        raise HTTPException(status_code=500, detail="app_update.version 不能为空")
    version_code = _int(cfg, "version_code")
    if version_code <= 0:
        raise HTTPException(status_code=500, detail="app_update.version_code 必须是正整数")
    size = _int(cfg, "size")
    if size < 0:
        raise HTTPException(status_code=500, detail="app_update.size 不能为负数")
    min_supported = _int(cfg, "min_supported_version_code")
    if min_supported < 0:
        raise HTTPException(
            status_code=500, detail="app_update.min_supported_version_code 不能为负数"
        )
    return {
        "version": version,
        "version_code": version_code,
        "apk_url": apk_url,
        "sha256": sha256.lower(),
        "size": size,
        "notes": str(cfg.get("notes") or ""),
        "min_supported_version_code": min_supported,
        "published_at": str(cfg.get("published_at") or ""),
    }


@router.get("/api/app/version", response_model=AppVersionOut)
def api_app_version(user_id: Annotated[str, Depends(get_current_user_id)]):
    return _manifest(config.APP_UPDATE)
