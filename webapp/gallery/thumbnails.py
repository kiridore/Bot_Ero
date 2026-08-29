import hashlib
from pathlib import Path

from PIL import Image, ImageFilter

from webapp.gallery import config


def _cache_path(source: Path) -> Path:
    digest = hashlib.sha256(str(source.resolve()).encode()).hexdigest()[:32]
    return config.THUMB_CACHE_DIR / f"{digest}.jpg"


def _to_rgb(im: Image.Image) -> Image.Image:
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, (17, 17, 17))
        rgba = im.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[3])
        return bg
    if im.mode == "P" and "transparency" in im.info:
        return _to_rgb(im.convert("RGBA"))
    if im.mode != "RGB":
        return im.convert("RGB")
    return im


def ensure_thumbnail(source: Path) -> Path:
    """生成或返回已缓存的 JPEG 缩略图路径。"""
    cache = _cache_path(source)
    if cache.is_file():
        try:
            if cache.stat().st_mtime >= source.stat().st_mtime:
                return cache
        except OSError:
            pass

    config.THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as im:
        im = _to_rgb(im)
        im.thumbnail(
            (config.THUMB_MAX_WIDTH, config.THUMB_MAX_HEIGHT),
            Image.Resampling.LANCZOS,
        )
        im.save(
            cache,
            "JPEG",
            quality=config.THUMB_JPEG_QUALITY,
            optimize=True,
        )
    return cache


def ensure_blurred(thumb: Path) -> Path:
    """缩略图的高斯模糊版（独立 blur- 前缀缓存，不覆盖缩略图本身）。
    ponytail: 模糊缩略图而非原图——时间线展示尺寸即缩略图，防泄漏足够；
    radius 12 为一眼不可辨的固定值，需要更强再配化。"""
    blurred = thumb.parent / f"blur-{thumb.name}"
    if blurred.is_file() and blurred.stat().st_mtime >= thumb.stat().st_mtime:
        return blurred
    with Image.open(thumb) as im:
        _to_rgb(im).filter(ImageFilter.GaussianBlur(radius=12)).save(
            blurred, "JPEG", quality=config.THUMB_JPEG_QUALITY
        )
    return blurred
