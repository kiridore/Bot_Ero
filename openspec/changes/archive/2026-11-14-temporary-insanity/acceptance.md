# `.ti` 疯狂发作 — 验收记录

实施分支：`master`；版本 1.99.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 数据完整 | `test/test_trpg_insanity.py::TestTables`：表Ⅶ 10 条、表Ⅸ/Ⅹ 各 100 条、编号连续、名称/拉丁/描述齐全、无 ①② 残留 | 通过 |
| AC02 掷表查表 | `test_lookup`：4→偏执、1→洗澡恐惧症、100→喜兽癖；越界 None | 通过 |
| AC03 基本回执 | `test_paranoia_output`：含症状、描述、7 轮、5 小时、由守秘人裁定 | 通过 |
| AC04 人际依赖 | `test_dependence_uses_background` | 通过 |
| AC05 恐惧写卡 | `test_phobia_written_to_card`：牙科恐惧症写入 `social_background.phobias` | 通过 |
| AC06 狂躁追加 | `test_mania_appends`：`幽闭恐惧症、喜兽癖` | 通过 |
| AC07 规则门控 | `test_dnd_card_refused` | 通过 |
| AC08 权限 | `test_other_target_needs_dm` / `test_dm_can_target_others` | 通过 |
| AC09 指令匹配 | `test_matches_command` | 通过 |
| AC10 写入记录 | `TestRecording::test_reply_is_recorded`：`record_bot_message` 被调用且含「偏执」 | 通过 |
| AC11 全量回归 | `python -m pytest -q` → **975 passed**（5:15） | 通过 |
| AC12 文档与归档 | `openspec validate trpg-madness --strict` valid；菜单与 `kb/DICE_GUIDE.md` 已加 `.ti`；`CHANGELOG [1.99.0]` 与 `BOTERO_VERSION = "1.99.0"` 一致；同一 commit 归档 | 通过 |

## 回执样例（实测）

```
哈维 陷入疯狂发作（表Ⅶ 即时症状）
· D10=9 → 恐惧
  从表Ⅸ恐惧症状表骰 D100（或由守秘人选择）得到一个恐惧源
· 表Ⅸ 恐惧症状表 D100=30 → 牙科恐惧症（Dentophobia）
  对牙医的恐惧。
· 已记入角色卡「背景 · 恐惧症和狂躁症」（恐惧症）
· 症状持续 1D10 轮 → 7 轮
· 临时性疯狂持续 1D10 小时 → 5 小时（整段是否适用由守秘人裁定）
```

## 数据来源与校对

- 表Ⅶ/Ⅸ/Ⅹ 全部取自 `docs/COC7th守密人核心规则书.pdf` 第八章（表Ⅶ p141）。
- 抽取后去掉：页码行、页眉「Call of Cthulhu 7th Edition」「第八章 理智」、译注①②、「（原文如此，存疑…）」说明；名字里的 ①②③ 一并去掉（牙科恐惧症① → 牙科恐惧症）。
- 已知保留：表Ⅹ 第 34 与 95 条原文都叫「抓挠癖」（拉丁名不同：Dermatillomania / Titillomaniac），按原文保留。

## 未做

- 表Ⅷ「总结症状」（远离同伴时的长时段发作）、不定性疯狂、`疯狂中` 状态标记与惩罚骰。
- 自动判定「理智损失 ≥5 → 智力检定」——按需求保持人工触发。
