# 当前值清零修复 — 验收记录

实施分支：`master`；版本 1.82.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 新建初始化 | `check_trpg_coc_api.py`：新建后 `current_hp=10`、`current_mp=13`、`current_san=65`（上限） | 通过 |
| AC02 编辑不清零 | 同脚本「编辑不清零当前值」：不带 `current_*` 的 PUT 后三项仍为 10/13/65 | 通过 |
| AC03 显式 0 保留 | 「显式 0 保留」：`current_hp=0` 的 PUT 后仍为 0 | 通过 |
| AC04 `.mp` | `TestMp`：`.mp -3` → `MP 13 → 10`；`.mp 满` 回满 13；DND 卡提示 COC 专用 | 通过 |
| AC05 文档与归档 | 全量 `pytest` → **851 passed**（5:11）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.82.1]` 与 `BOTERO_VERSION = "1.82.1"` 一致 | 通过 |

## 实测与裁定

- **根因**：`CharacterIn` 的 `current_*` 默认 0，建卡页不提交这三个字段。新建时旧的 `if not data.get(key)` 把 0 当缺省、按上限初始化（侥幸正确）；编辑 PUT 没有补偿，0 直接覆盖真值，`finalize` 的 `_clamp_or(0, …)` 又让 0 永远生效。
- **修复方式**：字段改 `int | None = None`，新建走 `_fill_current_values`（按规则上限）、编辑走 `_keep_current_values`（沿用原值），显式 0 保留。
- **已有卡片**：0 与「未设置」在 JSON 里没有区别，自动迁移会误伤真正的濒死/昏迷状态，因此不迁移；用 `.hp 满` / `.san 满` / `.mp 满` 手动恢复。
- **新增 `.mp`**：与 `.san` 同构（含施加目标权限、规则门控、写入记录），补齐 MP 的恢复手段。
- **未做**：网页端仍不能直接改当前值（沿用 1.69 的「运行时数值只在群里改」约定）。
