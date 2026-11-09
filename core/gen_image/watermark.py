"""纯 Pillow 单主体图片水印；身份与开关由调用方决定。"""

from PIL import Image, ImageDraw

from core.gen_image.fonts import load_font, truncate_text

ANGLE = 45
ALPHA = 64
TILE_GAP = 48
MAX_NAME_CHARS = 128


def apply_watermark(image: Image.Image, text: str) -> Image.Image:
    """返回新图：半透明白字旋转 45°，相邻行错开半个横向周期。"""
    if not text.strip():
        return image.copy()
    font = load_font(max(12, image.width // 24))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    # 先限长度再按图宽截断，避免长昵称导致字体测量或旋转画布无界增长。
    label = text[:MAX_NAME_CHARS] + ("…" if len(text) > MAX_NAME_CHARS else "")
    label = truncate_text(probe, label, font, max(1, image.width // 2))
    left, top, right, bottom = probe.textbbox((0, 0), label, font=font)
    tile = Image.new("RGBA", (max(1, right - left), max(1, bottom - top)))
    ImageDraw.Draw(tile).text((-left, -top), label, font=font, fill=(255, 255, 255, ALPHA))
    tile = tile.rotate(ANGLE, resample=Image.Resampling.BICUBIC, expand=True)
    step_x, step_y = tile.width + TILE_GAP, tile.height + TILE_GAP
    overlay = Image.new("RGBA", image.size)
    for row, y in enumerate(range(-tile.height, image.height, step_y)):
        offset = (row % 2) * (step_x // 2)
        for x in range(-step_x + offset, image.width, step_x):
            overlay.alpha_composite(tile, (x, y))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert(image.mode)
