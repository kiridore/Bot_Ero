# 准备名单角色卡描述 — 验收记录

实施分支：`master`；版本 1.81.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 COC 卡片 | `TestPreparedCardSuffix::test_coc_shows_occupation_and_age`：药剂师 + 28 →「（药剂师 · 28岁）」；`test_coc_without_occupation`：→「（无职业）」 | 通过 |
| AC02 DND 卡片 | `test_dnd_shows_race_class_level`：→「（人类 战士 Lv.3）」；`test_dnd_empty_fields_omitted`：全空 1 级 → 空串 | 通过 |
| AC03 旧快照 | `test_legacy_snapshot_without_rules`：无 `rules` 且全空 → 空串；有值 → 正常括号 | 通过 |
| AC04 文档与归档 | 全量 `pytest` → **840 passed**（5:13）；`openspec validate trpg-party-roster --strict` valid；`CHANGELOG [1.81.1]` 与 `BOTERO_VERSION = "1.81.1"` 一致 | 通过 |

## 实测与裁定

- **根因**：`_card_segments` 固定拼 `（{race} {class_name} Lv.{level}）`，而 COC 卡没有 `race`/`class_name`，`level` 默认为 1 —— 于是「? ? Lv.1」。
- **快照扩展**：准备时一并存 `rules`/`occupation`/`age`，渲染时不依赖在线查询角色卡。
- **旧数据**：1.63 之前的快照没有 `rules`，按 DND 分支处理；三项为空且等级 1 时省略括号，避免历史数据继续显示问号。
- **未做**：名单里仍未显示卡的规则名（例如「COC 7th」），因为整个准备中卡片已经标明本团规则。
