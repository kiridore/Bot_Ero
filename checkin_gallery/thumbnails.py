import hashlib
from pathlib import Path

from PIL import Image

from checkin_gallery import config


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
