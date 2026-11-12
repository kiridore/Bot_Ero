# `/跑团 角色 查看` 按规则输出 — 验收记录

实施分支：`master`；版本 1.81.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 COC 卡 | `TestViewByRules::test_coc_card_uses_coc_format`：输出含「HP」「伤害加值」「药剂师」，不含「Lv.」「熟练加值」 | 通过 |
| AC02 DND 卡 | `test_dnd_card_unchanged`：含「Lv.」，不含「伤害加值」 | 通过 |
| AC03 旧卡 | `test_missing_rules_treated_as_dnd`：无 `rules` 按 DND 输出 | 通过 |
| AC04 文档与归档 | 全量 `pytest` → **844 passed**（5:09）；`openspec validate trpg-character-card --strict` valid；`CHANGELOG [1.81.2]` 与 `BOTERO_VERSION = "1.81.2"` 一致 | 通过 |

## 实测与裁定

- **根因**：`plugins/trpg_char/__init__.py::_handle_view` 固定调用 `char_logic.format_sheet`（DND），而 `core/trpg/coc.py::format_sheet` 早已存在却无人调用；`/跑团 角色 列表` 在 1.66 就按规则区分了，查看漏了。
- **分发点**：新增模块级 `format_card()`，一处判断规则，避免以后其它调用点再各写一遍。
- **未做**：`/跑团 角色 列表` 的文案未统一到 `format_card`（它只需要单行摘要，不需要整张卡）。
