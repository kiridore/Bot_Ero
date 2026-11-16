"""`.ti` 疯狂发作：表Ⅶ 即时症状、表Ⅸ/Ⅹ 抽取、写卡、权限与规则门控。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg import madness
from test.test_trpg_vitals import DM_ID, GROUP_ID, PLAYER_ID, VitalsBase, _coc_card, _dnd_card


class TestTables(unittest.TestCase):
    """数据完整性：三条表都要齐、编号连续、没有残留译注标记。"""

    def test_immediate_symptoms(self):
        self.assertEqual(len(madness.IMMEDIATE_SYMPTOMS), 10)
        self.assertEqual([s["roll"] for s in madness.IMMEDIATE_SYMPTOMS], list(range(1, 11)))
        self.assertEqual(len({s["key"] for s in madness.IMMEDIATE_SYMPTOMS}), 10)
        for item in madness.IMMEDIATE_SYMPTOMS:
            self.assertTrue(item["name"] and item["description"], item)

    def test_phobias_and_manias(self):
        for table in (madness.PHOBIAS, madness.MANIAS):
            self.assertEqual(len(table), 100)
            self.assertEqual([i["roll"] for i in table], list(range(1, 101)))
            for item in table:
                self.assertTrue(item["name"] and item["latin"] and item["description"], item)
                for mark in "①②③④⑤⑥⑦⑧⑨⑩":
                    self.assertNotIn(mark, item["name"], item)

    def test_lookup(self):
        self.assertEqual(madness.immediate_symptom(4)["name"], "偏执")
        self.assertEqual(madness.phobia(1)["name"], "洗澡恐惧症")
        self.assertEqual(madness.mania(100)["name"], "喜兽癖")
        self.assertIsNone(madness.immediate_symptom(11))
        self.assertIsNone(madness.phobia(0))


class TestInsanity(VitalsBase):
    rule = "coc7th"

    def test_paranoia_output(self):
        self.install({PLAYER_ID: _coc_card()})
        out = self.invoke(".ti", user_id=PLAYER_ID, rolls=[4, 42, 7, 5])
        self.assertIn("陷入疯狂发作", out)
        self.assertIn("D10=4 → 偏执", out)
        self.assertIn("症状持续 1D10 轮 → 7 轮", out)
        self.assertIn("临时性疯狂持续 1D10 小时 → 5 小时", out)
        self.assertIn("由守秘人裁定", out)

    def test_dependence_uses_background(self):
        self.install({PLAYER_ID: _coc_card(
            social_background={"significant_people": "爱丽丝，未婚妻"})})
        out = self.invoke(".ti", user_id=PLAYER_ID, rolls=[5, 42, 3, 6])
        self.assertIn("人际依赖", out)
        self.assertIn("卡上的「重要之人」：爱丽丝，未婚妻", out)

    def test_phobia_written_to_card(self):
        self.install({PLAYER_ID: _coc_card(social_background={"phobias": ""})})
        out = self.invoke(".ti", user_id=PLAYER_ID, rolls=[9, 30, 7, 5])
        self.assertIn("牙科恐惧症（Dentophobia）", out)
        self.assertIn("已记入角色卡", out)
        self.assertEqual(self.cards[PLAYER_ID]["social_background"]["phobias"], "牙科恐惧症")

    def test_mania_appends(self):
        self.install({PLAYER_ID: _coc_card(social_background={"phobias": "幽闭恐惧症"})})
        self.invoke(".ti", user_id=PLAYER_ID, rolls=[10, 100, 2, 9])
        self.assertEqual(self.cards[PLAYER_ID]["social_background"]["phobias"], "幽闭恐惧症、喜兽癖")

    def test_matches_command(self):
        ctx = self._ctx(".ti")
        from plugins.trpg_vitals import TrpgVitalsPlugin
        plugin = TrpgVitalsPlugin(ctx)
        self.assertTrue(plugin.match("message"))

    def _ctx(self, text):
        from test.helper import make_group_message
        return make_group_message(text, user_id=PLAYER_ID)

    def test_dnd_card_refused(self):
        self.install({PLAYER_ID: _dnd_card()})
        out = self.invoke(".ti", user_id=PLAYER_ID, rule="dnd5e", rolls=[4, 42, 7, 5])
        self.assertIn("COC 7th", out)

    def test_other_target_needs_dm(self):
        self.install({PLAYER_ID: _coc_card(), DM_ID: _coc_card()})
        # 玩家给自己的同伴掷（目标不是本人）→ 拒绝
        out = self.invoke(f".ti @{DM_ID}", user_id=PLAYER_ID, rolls=[4, 42, 7, 5])
        self.assertIn("只有 DM", out)

    def test_dm_can_target_others(self):
        self.install({PLAYER_ID: _coc_card(), DM_ID: _coc_card()})
        out = self.invoke(f".ti @{PLAYER_ID}", user_id=DM_ID,
                          roles={DM_ID: "dm"}, rolls=[4, 42, 7, 5])
        self.assertIn("D10=4 → 偏执", out)


class TestRecording(unittest.TestCase):
    def test_reply_is_recorded(self):
        with patch("plugins.trpg_vitals.runtime_context.record_bot_message") as recorded:
            from plugins.trpg_vitals import TrpgVitalsPlugin
            from test.helper import make_group_message
            ctx = make_group_message(".ti", user_id=PLAYER_ID)
            plugin = TrpgVitalsPlugin(ctx)
            from test.helper import MockApiWrapper
            plugin.api = MockApiWrapper(ctx)
            card = _coc_card(id=1, user_id=PLAYER_ID)
            with patch("plugins.trpg_vitals.store.get_current", return_value=card), \
                 patch("plugins.trpg_vitals.store.update_char"), \
                 patch("plugins.trpg_vitals.party.current_rule", return_value="coc7th"), \
                 patch("plugins.trpg_vitals.random.randint", side_effect=[4, 42, 7, 5]):
                plugin.handle()
        self.assertTrue(recorded.called)
        self.assertIn("偏执", recorded.call_args[0][2])
