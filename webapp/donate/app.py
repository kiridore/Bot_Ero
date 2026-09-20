"""赞赏页子应用：展示站长手动上传到 donate 目录（config paths.donate）的收款码图片。

目录扫描即展示（jpg/jpeg/png/webp/gif），无管理后台、无数据库；
图片经 /donate/media/ 提供，全站登录门控内。
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from core import config
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

router = APIRouter()

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _list_images() -> list[str]:
    root = Path(str(config.DONATE_DIR))
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES)


@router.get("/api/donate/images")
def api_donate_images(user_id: Annotated[str, Depends(get_current_user_id)]):
    return {"images": _list_images()}


@router.get("/donate/media/{filename}")
def donate_media(filename: str, user_id: Annotated[str, Depends(get_current_user_id)]):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法路径")
    path = Path(str(config.DONATE_DIR)) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(path)


@router.get("/donate")
def donate_page():
    page = STATIC_DIR / "donate.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)
