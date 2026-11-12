# 参团角色卡快照 — 验收记录

实施分支：`master`；版本 1.74.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 快照内容 | `test_trpg_snapshots.py`：DND 快照 `level=3`、`hp=30`、`current_hp=22`、`prof_bonus=2`、含熟练技能；COC 快照 `current_san=40`、`san=65`、`skills["侦察"]=45`；`notes`/`equipment` 不进快照 | 通过 |
| AC02 结束补写 | `attach_end_snapshots`：有 `char_id` 补 `sheet_end` 并刷新 `char_name`；删卡跳过且不抛错；无 `char_id` 时 `get_char` 未被调用 | 通过 |
| AC03 开录写入 | `test_trpg_session.py::TestSheetSnapshots`：开录后含 `char_id` 与 `sheet_start.level=3`；结束前把卡升到 4 级并改 HP，`sheet_end.level=4`；删卡后保留 `sheet_start`、无 `sheet_end` | 通过 |
| AC04 页面 | `trpg_record.html` 新增 `#sheetBox` 折叠区；`renderSheets` 输出「开始 / 结束」两行与「本场变化：Lv 3→4，HP上限 30→38…」；无快照时 `hidden` | 代码层通过，视觉待确认 |
| AC05 文档与归档 | 全量 `pytest` → **733 passed**（4:43）；`openspec validate trpg-session-recording --strict` valid；`CHANGELOG [1.74.0]` 与 `BOTERO_VERSION = "1.74.0"` 一致 | 通过 |

## 实测与裁定

- **快照时机**：开录时（含中途首次发言）、结束时（`finalize_record` 统一覆盖 `/跑团 记录 结束`、群解散、7 天超时三条路径）。
- **体积**：COC 技能表最多 80 项，6 人两份约几十 KB，可接受。
- **容错**：`finalize_record` 里快照异常被吞掉，只有 `end` 一定写入——记录不会因为快照失败卡在「录制中」。
- **未做**：快照不进入 `record.md` 与 `.ra` 输出；旧记录不回填。
