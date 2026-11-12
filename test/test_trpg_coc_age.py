"""COC 7th 年龄调整：年龄表、MOV 公式、应用/撤销与一致性校验。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg import coc


def _card(**over):
    card = {
        "rules": "coc7th", "char_name": "哈维", "age": 45,
        "str_score": 63, "con_score": 57, "siz_score": 45, "dex_score": 55,
        "app_score": 55, "int_score": 85, "pow_score": 65, "edu_score": 60,
        "skills": {}, "weapons": [], "inventory": [], "assets": {}, "occupation_choices": {},
    }
    card.update(over)
    return card


def _roller(values):
    """按给定顺序返回掷骰结果。"""
    sequence = iter(values)
    return lambda low, high: next(sequence)


class TestAgeBands(unittest.TestCase):
    def test_band_boundaries(self):
        cases = {
            15: ("15-19", ("str", "siz"), 5, 0, 0, -5, True),
            19: ("15-19", ("str", "siz"), 5, 0, 0, -5, True),
            20: ("20-39", (), 0, 0, 1, 0, False),
            39: ("20-39", (), 0, 0, 1, 0, False),
            40: ("40-49", ("str", "con", "dex"), 5, 5, 2, 0, False),
            49: ("40-49", ("str", "con", "dex"), 5, 5, 2, 0, False),
            50: ("50-59", ("str", "con", "dex"), 10, 10, 3, 0, False),
            60: ("60-69", ("str", "con", "dex"), 20, 15, 4, 0, False),
            70: ("70-79", ("str", "con", "dex"), 40, 20, 4, 0, False),
            80: ("80-89", ("str", "con", "dex"), 80, 25, 4, 0, False),
            90: ("90+", ("str", "con", "dex"), 80, 25, 4, 0, False),
        }
        for age, expected in cases.items():
            info = coc.age_adjustment(age)
            got = (info["band"], tuple(info["phy"]), info["phy_quota"], info["app"],
                   info["edu_checks"], info["edu_fixed"], info["luck_best"])
            self.assertEqual(got, expected, f"{age} 岁")

    def test_out_of_range(self):
        self.assertIsNone(coc.age_adjustment(0))
        self.assertIsNone(coc.age_adjustment(14))
        self.assertIsNone(coc.age_adjustment(100))
        self.assertIsNone(coc.age_adjustment("abc"))

    def test_mov_formula(self):
        cases = {0: 0, 15: 0, 39: 0, 40: 1, 49: 1, 50: 2, 80: 5, 89: 5, 90: 6, 99: 6}
        for age, penalty in cases.items():
            self.assertEqual(coc.age_mov_penalty(age), penalty, f"{age} 岁")


class TestApply(unittest.TestCase):
    def test_apply_40s(self):
        changed = coc.apply_age_adjust(
            _card(), {"str": -3, "con": -2, "dex": 0},
            roll=_roller([71, 4, 40]))
        self.assertEqual(changed["str_score"], 60)
        self.assertEqual(changed["con_score"], 55)
        self.assertEqual(changed["app_score"], 50)
        self.assertEqual(changed["edu_score"], 64)   # 71>60 得 4；40 不大于 64
        record = changed["age_adjust"]
        self.assertEqual(record["kind"], "applied")
        self.assertEqual(record["band"], "40-49")
        self.assertEqual(record["phy"], {"str": -3, "con": -2, "dex": 0})
        self.assertEqual(record["app"], -5)
        self.assertEqual(record["edu"]["rolls"], [{"roll": 71, "gain": 4}, {"roll": 40, "gain": 0}])
        self.assertEqual(record["before"], {"str": 63, "con": 57, "dex": 55, "app": 55})

    def test_edu_capped_at_99(self):
        changed = coc.apply_age_adjust(
            _card(age=50, edu_score=99), {"str": -10, "con": 0, "dex": 0},
            roll=_roller([100, 10, 100, 10, 100, 10]))
        self.assertEqual(changed["edu_score"], 99)

    def test_15_19_uses_str_and_siz(self):
        changed = coc.apply_age_adjust(
            _card(age=17, edu_score=60), {"str": -5, "siz": 0}, roll=_roller([]))
        self.assertEqual(changed["str_score"], 58)
        self.assertEqual(changed["siz_score"], 45)
        self.assertEqual(changed["edu_score"], 55)          # 定值 -5，不掷成长
        self.assertEqual(changed["age_adjust"]["edu"]["checks"], 0)
        self.assertEqual(changed["age_adjust"]["app"], 0)

    def test_20s_only_edu_check(self):
        changed = coc.apply_age_adjust(
            _card(age=25, edu_score=70), {}, roll=_roller([80, 6]))
        self.assertEqual(changed["edu_score"], 76)
        self.assertEqual(changed["age_adjust"]["phy"], {})
        self.assertEqual(changed["age_adjust"]["app"], 0)

    def test_sum_mismatch(self):
        with self.assertRaises(ValueError) as ctx:
            coc.apply_age_adjust(_card(), {"str": -3, "con": 0, "dex": 0}, roll=_roller([]))
        self.assertIn("体能合计应扣 5 点，当前为 3 点", str(ctx.exception))

    def test_positive_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            coc.apply_age_adjust(_card(), {"str": -8, "con": 3, "dex": 0}, roll=_roller([]))
        self.assertIn("0 或负数", str(ctx.exception))

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            coc.apply_age_adjust(_card(age=30), {"str": -5}, roll=_roller([]))
        self.assertIn("只能填", str(ctx.exception))

    def test_attribute_floor(self):
        with self.assertRaises(ValueError) as ctx:
            coc.apply_age_adjust(_card(app_score=3), {"str": -5, "con": 0, "dex": 0}, roll=_roller([]))
        self.assertIn("外貌扣减后为 -2", str(ctx.exception))

    def test_undo_restores(self):
        merged = dict(_card(), **coc.apply_age_adjust(
            _card(), {"str": -5, "con": 0, "dex": 0}, roll=_roller([10, 0, 10, 0])))
        restored = coc.undo_age_adjust(merged)
        self.assertEqual(restored, {"str_score": 63, "con_score": 57, "dex_score": 55,
                                    "app_score": 55, "edu_score": 60})

    def test_undo_without_record(self):
        with self.assertRaises(ValueError):
            coc.undo_age_adjust(_card())


class TestValidate(unittest.TestCase):
    def _applied(self, **over):
        card = _card(**over)
        return dict(card, **coc.apply_age_adjust(card, {"str": -5, "con": 0, "dex": 0},
                                                roll=_roller([10, 0, 10, 0])))

    def test_applied_is_valid(self):
        self.assertEqual(coc.validate(self._applied()), [])

    def test_missing_record_is_allowed(self):
        self.assertEqual(coc.validate(_card()), [])
        self.assertEqual(coc.age_adjust_problems(_card()), [])

    def test_skipped_is_allowed(self):
        card = _card(age_adjust={"kind": "skipped", "age": 45, "band": "40-49"})
        self.assertEqual(coc.validate(card), [])

    def test_age_changed_after_apply(self):
        card = self._applied()
        card["age"] = 50
        problems = coc.age_adjust_problems(card)
        self.assertEqual(len(problems), 1)
        self.assertIn("年龄已从 45 改为 50", problems[0])

    def test_manual_attribute_edit_rejected(self):
        card = self._applied()
        card["str_score"] += 3
        problems = coc.age_adjust_problems(card)
        self.assertEqual(len(problems), 1)
        self.assertIn("请勿手工修改力量", problems[0])

    def test_manual_app_edit_rejected(self):
        card = self._applied()
        card["app_score"] += 1
        self.assertIn("外貌", coc.age_adjust_problems(card)[0])

    def test_manual_edu_edit_rejected(self):
        card = self._applied()
        card["edu_score"] += 1
        self.assertIn("教育", coc.age_adjust_problems(card)[0])

    def test_tampered_quota(self):
        card = self._applied()
        card["age_adjust"]["phy"] = {"str": -1, "con": 0, "dex": 0}
        problems = coc.age_adjust_problems(card)
        self.assertIn("体能合计应扣 5 点，当前为 1 点", problems[0])

    def test_age_range(self):
        self.assertEqual(coc.age_adjust_problems(_card(age=14)), ["年龄应在 15-99 之间"])
        self.assertEqual(coc.age_adjust_problems(_card(age=0)), [])
        self.assertEqual(coc.age_adjust_problems(_card(age="abc")), ["年龄必须是整数"])

    def test_bad_record(self):
        self.assertEqual(coc.age_adjust_problems(_card(age_adjust={"kind": "?"})),
                         ["年龄调整记录格式不正确"])


class TestFinalize(unittest.TestCase):
    def test_mov_uses_new_formula(self):
        self.assertEqual(coc.finalize(_card(age=90))["mov"],
                         max(coc.base_mov(63, 55, 45) - 6, 0))
        self.assertEqual(coc.finalize(_card(age=39))["mov"], coc.base_mov(63, 55, 45))

    def test_payload_shape(self):
        bands = coc.age_bands_payload()
        self.assertEqual(len(bands), 8)
        self.assertEqual(bands[0]["phy_labels"], ["力量", "体型"])
        self.assertEqual(bands[1]["phy"], [])
