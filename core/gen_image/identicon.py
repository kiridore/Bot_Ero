"""网站与 bot 共用的确定性几何头像，不访问网络或写磁盘。"""

from PIL import Image, ImageDraw

from core.user_settings import anonymous_name


def generate_identicon(user_id: str | int) -> Image.Image:
    """返回固定 128×128 RGB 图；有限图案不保证所有 QQ 互不相同。"""
    digest = bytes.fromhex(anonymous_name(user_id))
    foreground = tuple(48 + channel % 144 for channel in digest[:3])
    pattern = int.from_bytes(digest, "big")
    image = Image.new("RGB", (128, 128), (240, 240, 240))
    draw = ImageDraw.Draw(image)
    for row in range(5):
        for col in range(3):
            if pattern & (1 << (row * 3 + col)):
                for mirrored_col in {col, 4 - col}:
                    x, y = 14 + mirrored_col * 20, 14 + row * 20
                    draw.rectangle((x, y, x + 19, y + 19), fill=foreground)
    return image
