from __future__ import annotations

import os
import sys
import tempfile
import unittest
from io import BytesIO
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


@unittest.skipUnless(PILImage is not None, "需要安装 Pillow（pip install pillow）")
class TestFetchAvatarCachedLogic(unittest.TestCase):
    """不依赖网络与真实 server_data：patch 下载源与缓存目录。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="avatar_cache_test_")
        self.addCleanup(self._tmp.cleanup)
        self.cache_root = Path(self._tmp.name)

    def _avatar_bytes(self, color=(200, 30, 30), size=(64, 48)):
        im = PILImage.new("RGB", size, color)
        buf = BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()

    def _write_source(self, data: bytes) -> str:
        src = self.cache_root / "avatar_src.png"
        src.write_bytes(data)
        return str(src)

    def _patch_cache(self):
        from core.gen_image import avatar_helper
        return patch.object(avatar_helper.context, "python_data_path", self._tmp.name)

    def test_download_success_writes_cache(self):
        from core.gen_image.avatar_helper import fetch_avatar_cached

        payload = self._avatar_bytes()
        url = "file://" + self._write_source(payload)  # 本地文件当下载源

        class _Api:
            def get_qq_avatar(self, user_id):
                return url

        with self._patch_cache():
            im = fetch_avatar_cached(_Api(), 987001)
        self.assertIsNotNone(im)
        cache = self.cache_root / "avatar_cache" / "987001.png"
        self.assertTrue(cache.is_file())
        with PILImage.open(cache) as loaded:
            self.assertEqual(loaded.size, (64, 48))

    def test_download_failure_falls_back_to_cache(self):
        from core.gen_image.avatar_helper import fetch_avatar_cached

        cache = self.cache_root / "avatar_cache" / "987002.png"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(self._avatar_bytes((30, 200, 30)))

        class _Api:
            def get_qq_avatar(self, user_id):
                return ""  # 模拟 API 失败

        with self._patch_cache():
            im = fetch_avatar_cached(_Api(), 987002)
        self.assertIsNotNone(im)
        self.assertEqual(im.size, (64, 48))

    def test_total_failure_returns_none(self):
        from core.gen_image.avatar_helper import fetch_avatar_cached

        class _Api:
            def get_qq_avatar(self, user_id):
                raise RuntimeError("api down")

        with self._patch_cache():
            self.assertIsNone(fetch_avatar_cached(_Api(), 987003))


@unittest.skipUnless(PILImage is not None, "需要安装 Pillow（pip install pillow）")
class TestRankCard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="rank_card_test_")
        self.addCleanup(self._tmp.cleanup)
        self.out_root = Path(self._tmp.name)

    def _assert_png_file(self, path: Path) -> None:
        self.assertTrue(path.is_file(), f"未生成文件: {path}")
        self.assertGreater(path.stat().st_size, 100, f"文件过小: {path}")
        with PILImage.open(path) as loaded:
            self.assertEqual(loaded.format, "PNG")

    def _render_basic(self):
        from core.gen_image.rank_card import RankRow, render_rank_card

        rows = [
            RankRow(rank=1, name="「画师」阿囡", detail="114514分",
                    avatar=PILImage.new("RGB", (96, 96), (212, 175, 55))),
            RankRow(rank=2, name="板油二号", detail="1919分", avatar=None),
            RankRow(rank=3, name="很长的名字" * 8, detail="810分", avatar=None),
        ]
        return render_rank_card("积分排行榜", "TOP 3", rows)

    def test_render_basic(self):
        img = self._render_basic()
        self.assertEqual(img.mode, "RGB")
        self.assertEqual(img.width, 620)
        self.assertGreater(img.height, 200)  # 高度随字体度量浮动，下界只验整体结构已渲染
        path = GEN_IMAGE_OUTPUT / "rank_card_basic.png"
        img.save(path, format="PNG")
        self._assert_png_file(path)

    def test_render_week_board_many_rows(self):
        from core.gen_image.rank_card import RankRow, render_rank_card

        rows = [
            RankRow(rank=i, name=f"板油{i:02d}", detail=f"2026-08-{(i % 28) + 1:02d} 09:12:34")
            for i in range(1, 31)
        ]
        img = render_rank_card("本周打卡板油", "2026-08-31 ~ 2026-09-07 · 共 30 名板油完成打卡", rows)
        self.assertGreater(img.height, 1000)  # 30 行 + 头像行的最小高度保障
        path = GEN_IMAGE_OUTPUT / "rank_card_week_board.png"
        img.save(path, format="PNG")
        self._assert_png_file(path)

    def test_save_rank_png_rotates_files(self):
        from core.gen_image import rank_card as rank_card_module
        from core.gen_image.rank_card import RankRow, render_rank_card, save_rank_png

        with patch.object(rank_card_module.context, "python_data_path", self._tmp.name):
            img = self._render_basic()
            py1, send1 = save_rank_png("points_rank", img)
            img2 = render_rank_card(
                "标题", "副标题",
                [RankRow(rank=1, name="乙", detail="2分")],
            )
            py2, send2 = save_rank_png("points_rank", img2)

        self.assertFalse(Path(py1).is_file())  # 旧图已被清理
        self.assertTrue(Path(py2).is_file())
        self.assertNotEqual(py1, py2)
        self.assertIn("rank_cards", send2)
        self.assertIn("points_rank_", Path(py2).name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
