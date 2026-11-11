"""COC 职业本职技能数据与职业点归属校验。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg import coc, coc_data


def _card(**over):
    card = {
        "rules": "coc7th", "char_name": "田宫真莉", "occupation": "会计师",
        "age": 28, "luck": 50, "credit_rating": 50,
        "str_score": 60, "con_score": 55, "siz_score": 45, "dex_score": 55,
        "app_score": 60, "int_score": 85, "pow_score": 65, "edu_score": 70,
        "current_hp": 10, "current_san": 65,
        "skills": {},
    }
    card.update(over)
    return card


STRUCT = {
    "会计师": {
        "required": ["会计", "法律", "图书馆使用", "聆听", "说服", "侦察"],
        "choices": [{"count": 2, "from": "*"}],
    },
    "摄影师": {
        "required": ["技艺:摄影", "侦察", "聆听"],
        "choices": [{"count": 2, "from": ["魅惑", "话术", "恐吓", "说服"]}],
    },
    "无名者": {"required": [], "choices": [{"count": 8, "from": "*"}]},
    "工匠": {"required": ["技艺:*", "侦察"], "choices": [{"count": 2, "from": ["魅惑", "话术"]}]},
    "赏金猎人": {"required": ["法律", "侦察"], "choices": [{"count": 1, "from": ["格斗:*", "射击:*"]}],
             "free": 0},
}


class TestOccupationData(unittest.TestCase):
    """数据完整性：每个真实职业都有结构化条目，且技能名都能对上技能表。"""

    def test_every_occupation_has_entry(self):
        missing = [
            name for seq, name, _, _, _, _ in coc_data.OCCUPATIONS
            if seq >= 2 and coc.occupation_slots(seq) is None
        ]
        self.assertEqual(missing, [], f"缺少结构化本职技能：{missing[:5]}")

    def test_skill_names_are_canonical(self):
        bad = []
        for seq, name, _, _, _, _ in coc_data.OCCUPATIONS:
            struct = coc.occupation_slots(seq)
            if not struct:
                continue
            names = list(struct.get("required") or [])
            for choice in struct.get("choices") or []:
                if choice.get("from") != "*":
                    names.extend(choice.get("from") or [])
            for skill in names:
                if not coc.skill_name_ok(skill):
                    bad.append((name, skill))
        self.assertEqual(bad, [], f"技能名对不上技能表：{bad[:5]}")

    def test_slot_count_within_limit(self):
        bad = []
        for seq, name, _, _, _, _ in coc_data.OCCUPATIONS:
            struct = coc.occupation_slots(seq)
            if not struct:
                continue
            total = len(struct.get("required") or []) + sum(
                int(c.get("count") or 0) for c in struct.get("choices") or [])
            if not 1 <= total <= 8:
                bad.append((name, total))
        self.assertEqual(bad, [], f"本职技能数量不在 1-8：{bad[:5]}")

    def test_no_duplicate_required(self):
        bad = []
        for seq, name, _, _, _, _ in coc_data.OCCUPATIONS:
            struct = coc.occupation_slots(seq) or {}
            required = struct.get("required") or []
            if len(required) != len(set(required)):
                bad.append(name)
        self.assertEqual(bad, [], f"固定项有重复：{bad[:5]}")


class TestOccupationalPoints(unittest.TestCase):
    def _problems(self, card):
        name = card.get("occupation") or ""
        struct = STRUCT.get(name)
        info = {"seq": -1, "name": name, "credit_min": 0, "credit_max": 99, "formula": "", "own_skills": ""}
        with patch("core.trpg.coc.occupation_by_name", return_value=info if name else None),                 patch("core.trpg.coc.occupation_slots", return_value=struct):
            return coc.occupational_point_problems(card)

    def test_required_skill_allowed(self):
        card = _card(skills={"会计": {"base": 5, "occupation": 40}})
        self.assertEqual(self._problems(card), [])

    def test_alias_matches_required(self):
        card = _card(skills={"侦查": {"base": 25, "occupation": 20}})
        self.assertEqual(self._problems(card), [])

    def test_outside_lists_rejected(self):
        card = _card(occupation="摄影师", skills={"攀爬": {"base": 20, "occupation": 10}})
        problems = self._problems(card)
        self.assertTrue(any("不是摄影师的本职技能" in p for p in problems), problems)

    def test_free_pool_quota(self):
        ok = _card(skills={"摄影": {"base": 5, "occupation": 10}, "攀爬": {"base": 20, "occupation": 10}})
        self.assertEqual(self._problems(ok), [])
        over = _card(skills={
            "摄影": {"base": 5, "occupation": 10},
            "攀爬": {"base": 20, "occupation": 10},
            "游泳": {"base": 20, "occupation": 10},
        })
        self.assertTrue(self._problems(over))

    def test_named_pool(self):
        ok = _card(occupation="摄影师",
                   skills={"魅惑": {"base": 15, "occupation": 20}, "话术": {"base": 5, "occupation": 20}})
        self.assertEqual(self._problems(ok), [])
        outside = _card(occupation="摄影师", skills={"攀爬": {"base": 20, "occupation": 20}})
        self.assertTrue(self._problems(outside))
        too_many = _card(occupation="摄影师", skills={
            "魅惑": {"base": 15, "occupation": 10},
            "话术": {"base": 5, "occupation": 10},
            "恐吓": {"base": 15, "occupation": 10},
        })
        self.assertTrue(self._problems(too_many))

    def test_category_wildcard_matches_any_specialty(self):
        for skill in ("技艺:摄影", "技艺:烹饪", "技艺:伪造证件"):
            card = _card(occupation="工匠", skills={skill: {"base": 5, "occupation": 20}})
            self.assertEqual(self._problems(card), [], skill)

    def test_wildcard_does_not_match_other_category(self):
        card = _card(occupation="工匠", skills={"科学:生物学": {"base": 1, "occupation": 20}})
        self.assertTrue(self._problems(card))

    def test_pool_wildcard_matches_specialty(self):
        for skill in ("格斗:斗殴", "格斗:剑", "射击:步枪"):
            card = _card(occupation="赏金猎人", skills={skill: {"base": 25, "occupation": 40}})
            self.assertEqual(self._problems(card), [], skill)

    def test_pool_wildcard_rejects_other_category(self):
        card = _card(occupation="赏金猎人", skills={"技艺:摄影": {"base": 5, "occupation": 20}})
        self.assertTrue(self._problems(card))

    def test_no_occupation_skips(self):
        card = _card(occupation="", skills={"攀爬": {"base": 20, "occupation": 10}})
        self.assertEqual(self._problems(card), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
