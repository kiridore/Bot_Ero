"""文案包加载（社区版 T0.8）：覆盖/缺键/空值回落 + 坏包降级 + 社区包静态断言。"""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

import core.text_pack as text_pack
from core.text_pack import get_text

BUILTIN = "内置菜单"


class TestGetText(unittest.TestCase):
    """mock _pack 六向：覆盖/缺键/空串/null/非字符串/NICKNAME 替换。"""

    def test_override(self):
        with mock.patch.object(text_pack, "_pack", {"menu_text": "社区菜单"}):
            self.assertEqual(get_text("menu_text", BUILTIN), "社区菜单")

    def test_missing_key_falls_back(self):
        with mock.patch.object(text_pack, "_pack", {"other": "x"}):
            self.assertEqual(get_text("menu_text", BUILTIN), BUILTIN)

    def test_empty_value_falls_back(self):
        for bad in ("", "   ", None, 42, ["a"]):
            with self.subTest(bad=bad):
                with mock.patch.object(text_pack, "_pack", {"menu_text": bad}):
                    self.assertEqual(get_text("menu_text", BUILTIN), BUILTIN)

    def test_nickname_placeholder_replaced(self):
        with mock.patch.object(text_pack, "_pack", {"menu_text": "{NICKNAME}你好"}), \
                mock.patch.object(text_pack.config, "NICKNAME", "阿埃"):
            self.assertEqual(get_text("menu_text", BUILTIN), "阿埃你好")

    def test_stray_braces_survive(self):
        with mock.patch.object(text_pack, "_pack", {"menu_text": "a{b}c"}):
            self.assertEqual(get_text("menu_text", BUILTIN), "a{b}c")


class TestBadPackDegrades(unittest.TestCase):
    """坏包（缺失/语法错/非映射）→ WARNING + 空 _pack，不崩。"""

    def _reload_with(self, content: str | None):
        path = Path(tempfile.mkstemp(suffix=".yaml")[1])
        if content is not None:
            path.write_text(content, encoding="utf-8")
        with mock.patch.object(text_pack.config, "TEXT_PACK", str(path)):
            with self.assertLogs("core.text_pack", level="WARNING"):
                importlib.reload(text_pack)
        try:
            self.assertEqual(text_pack._pack, {})
            self.assertEqual(text_pack.get_text("menu_text", BUILTIN), BUILTIN)
        finally:
            importlib.reload(text_pack)  # 还原（TEXT_PACK 已退出 mock）

    def test_missing_file(self):
        self._reload_with(None)

    def test_invalid_yaml(self):
        self._reload_with("menu_text: [unclosed")

    def test_non_mapping_top_level(self):
        self._reload_with("- a\n- b\n")


class TestCommunityPack(unittest.TestCase):
    """社区包静态断言：结构化菜单后不再整段覆盖，逐条覆盖需中性化。"""

    def setUp(self):
        self.pack = yaml.safe_load(Path("text_packs/community.yaml").read_text(encoding="utf-8"))

    def test_no_legacy_menu_text(self):
        self.assertNotIn("menu_text", self.pack)

    def test_overrides_are_strings(self):
        for key, value in self.pack.items():
            self.assertTrue(key.startswith("menu."), f"非菜单覆盖键：{key}")
            self.assertIsInstance(value, str)

    def test_no_private_jargon(self):
        for key, value in self.pack.items():
            for word in ("FF14", "FF新闻", "喵", "板油"):
                self.assertNotIn(word, value, f"社区文案含私域词：{key}")


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
