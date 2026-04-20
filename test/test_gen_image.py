from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 运行 unittest 后在此目录查看生成的 PNG（与线上 personal_records 子目录结构一致）
GEN_IMAGE_OUTPUT = PROJECT_ROOT / "test" / "gen_image_output"

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None


class TestHeatmapColors(unittest.TestCase):
    """不依赖 Pillow，可单独验证配色逻辑。"""

    def test_github_green_level(self):
        from core.gen_image.heatmap_colors import github_green_level

        self.assertEqual(github_green_level(-1), (255, 223, 186))
        self.assertEqual(github_green_level(0), (235, 237, 240))
        self.assertEqual(github_green_level(1)[0], 198)


@unittest.skipUnless(PILImage is not None, "需要安装 Pillow（pip install pillow）")
class TestGenImage(unittest.TestCase):
    """档案图 / 热力图生成：结果写入 test/gen_image_output 供人工查看。"""

    @classmethod
    def setUpClass(cls):
        GEN_IMAGE_OUTPUT.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _blank_year_data() -> list[int]:
        """与插件一致：366 格，全 0 表示无打卡。"""
        return [0] * 366

    def _assert_png_file(self, path: Path) -> None:
        self.assertTrue(path.is_file(), f"未生成文件: {path}")
        self.assertGreater(path.stat().st_size, 100, f"文件过小: {path}")
        with PILImage.open(path) as loaded:
            self.assertEqual(loaded.format, "PNG")

    def test_render_year_heatmap(self):
        from core.gen_image.year_heatmap import render_year_heatmap

        data = self._blank_year_data()
        with_heading = render_year_heatmap(2024, data, include_heading=True)
        compact = render_year_heatmap(2024, data, include_heading=False)
        self.assertEqual(with_heading.mode, "RGB")
        self.assertEqual(compact.mode, "RGB")
        self.assertGreater(with_heading.height, compact.height)

        p1 = GEN_IMAGE_OUTPUT / "heatmap_2024_with_heading.png"
        p2 = GEN_IMAGE_OUTPUT / "heatmap_2024_compact.png"
        with_heading.save(p1, format="PNG")
        compact.save(p2, format="PNG")
        self._assert_png_file(p1)
        self._assert_png_file(p2)

    def test_build_personal_record_image(self):
        from core.gen_image.models import PersonalRecordStats
        from core.gen_image.profile_card import build_personal_record_image

        stats = PersonalRecordStats(
            year=2024,
            total_distinct_days=0,
            total_checkin_images=0,
            current_weekly=0,
            longest_weekly=0,
            current_daily=0,
            longest_daily=0,
            points=0,
        )
        img = build_personal_record_image(2024, self._blank_year_data(), stats)
        self.assertEqual(img.mode, "RGB")
        self.assertGreater(img.width, 200)
        self.assertGreater(img.height, 200)

        path = GEN_IMAGE_OUTPUT / "profile_card_built_2024.png"
        img.save(path, format="PNG")
        self._assert_png_file(path)

    def test_build_personal_record_with_avatar_and_footer(self):
        from core.gen_image.models import PersonalRecordStats
        from core.gen_image.profile_card import FOOTER_TEXT, build_personal_record_image

        stats = PersonalRecordStats(
            year=2024,
            total_distinct_days=3,
            total_checkin_images=5,
            current_weekly=1,
            longest_weekly=2,
            current_daily=1,
            longest_daily=2,
            points=42,
        )
        avatar = PILImage.new("RGB", (128, 96), (80, 120, 200))
        img = build_personal_record_image(
            2024,
            self._blank_year_data(),
            stats,
            user_display_name="档案图测试昵称",
            avatar=avatar,
        )
        self.assertEqual(img.mode, "RGB")
        path = GEN_IMAGE_OUTPUT / "profile_card_with_avatar_2024.png"
        img.save(path, format="PNG")
        self._assert_png_file(path)
        self.assertIn("Power by", FOOTER_TEXT)

    def test_save_personal_record_png_writes_file(self):
        from core.gen_image.models import PersonalRecordStats
        from core.gen_image.profile_card import build_personal_record_image, save_personal_record_png

        stats = PersonalRecordStats(
            year=2024,
            total_distinct_days=1,
            total_checkin_images=2,
            current_weekly=1,
            longest_weekly=2,
            current_daily=3,
            longest_daily=4,
            points=100,
        )
        img = build_personal_record_image(2024, self._blank_year_data(), stats)
        with patch("core.gen_image.profile_card.context.python_data_path", str(GEN_IMAGE_OUTPUT)):
            path_str = save_personal_record_png(424242, img)
        path = Path(path_str)
        self.assertTrue(path_str.endswith("424242_calendar_heatmap_monthly.png"))
        self._assert_png_file(path)
        with PILImage.open(path) as loaded:
            self.assertEqual(loaded.size, img.size)

    def test_gen_personal_record_card_end_to_end(self):
        from core.gen_image import PersonalRecordStats, gen_personal_record_card

        stats = PersonalRecordStats(
            year=2023,
            total_distinct_days=10,
            total_checkin_images=20,
            current_weekly=1,
            longest_weekly=5,
            current_daily=1,
            longest_daily=3,
            points=50,
        )
        data = self._blank_year_data()
        with patch("core.gen_image.profile_card.context.python_data_path", str(GEN_IMAGE_OUTPUT)):
            path_str = gen_personal_record_card(2023, data, 777001, stats)
        path = Path(path_str)
        self.assertIn("personal_records", path_str.replace("\\", "/"))
        self._assert_png_file(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
