"""打卡分享卡生成：尺寸上界与宽高比约束（spec D4/D5/D8）。"""

import unittest

from PIL import Image

from core.gen_image.checkin_share_card import (
    CARD_W,
    PHOTO_BOX_H_MAX,
    _flatten_rgb,
    build_checkin_share_card,
)


def _photo(w, h, mode="RGB"):
    fill = (120, 160, 200, 0) if mode == "RGBA" else (120, 160, 200)  # RGBA=全透明，用于验白底合成
    return Image.new(mode, (w, h), fill)


def _build(photo):
    return build_checkin_share_card(
        display_name="测试用户",
        checkin_date="2026-09-12 14:23:11",
        photo=photo,
        streak_days=3,
        total_images=42,
    )


class BuildCheckinShareCardTest(unittest.TestCase):
    def test_width_fixed_height_bounded_square(self):
        card = _build(_photo(2000, 2000))
        self.assertEqual(card.width, CARD_W)
        self.assertLessEqual(card.height, 1700)

    def test_extreme_panorama_bounded(self):
        card = _build(_photo(8000, 400))
        self.assertEqual(card.width, CARD_W)
        self.assertLessEqual(card.height, 1700)

    def test_extreme_tall_bounded(self):
        card = _build(_photo(600, 6000))
        self.assertEqual(card.width, CARD_W)
        self.assertLessEqual(card.height, 1700)

    def test_height_monotonic_then_clamped(self):
        # 照片区随图变高而变高，触顶后被 PHOTO_BOX_H_MAX 钳制
        h_wide = _build(_photo(1000, 500)).height
        h_square = _build(_photo(1000, 1000)).height
        h_tall = _build(_photo(1000, 1240)).height
        h_taller = _build(_photo(500, 1500)).height
        h_max = _build(_photo(500, 4000)).height
        self.assertLess(h_wide, h_square)
        self.assertLess(h_square, h_tall)
        self.assertEqual(h_taller, h_max)  # 500x1500 与 500x4000 都触顶 1250（contain 3000/8000 均 > 1250）
        self.assertLess(h_tall, h_taller)

    def test_alpha_png_flattened_to_rgb(self):
        card = _build(_photo(300, 200, "RGBA"))
        self.assertEqual(card.mode, "RGB")
        self.assertLessEqual(card.height, 1700)
        # 直接钉死白底合成语义：全透明 RGBA 展平后应得纯白（黑底错误实现会在此暴露）
        flat = _flatten_rgb(_photo(4, 4, "RGBA"))
        self.assertEqual(flat.mode, "RGB")
        self.assertEqual(flat.getpixel((0, 0)), (255, 255, 255))

    def test_box_max_constant(self):
        self.assertEqual((CARD_W, PHOTO_BOX_H_MAX), (1080, 1250))


if __name__ == "__main__":
    unittest.main()
