# 数值指令目标与空值健壮性 — 验收记录

实施分支：`master`；版本 1.82.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 消息段 @ | `TestTargetFormats::test_at_segment`：at 段 →「田宫的HP已回满」，目标卡 HP 变 10 | 通过 |
| AC02 文本 @ | `test_at_in_text`（`.hp 满 @100000002`）与 `test_at_in_text_without_space`（`.hp 满@100000002`）都作用在目标身上 | 通过 |
| AC03 空值 | `test_null_current_values`：`current_hp/mp/san` 为 None 时 `.hp -2`→10→8、`.mp -3`→13→10、`.san -1`→65→64 | 通过 |
| AC04 提示 | `test_has_cards_but_no_current`：`_resolve_target` 抛「还没设置当前角色卡」 | 通过 |
| AC05 文档与归档 | 全量 `pytest` → **856 passed**（5:11）；`openspec validate trpg-vitals --strict` valid；`CHANGELOG [1.82.2]` 与 `BOTERO_VERSION = "1.82.2"` 一致 | 通过 |

## 实测与裁定

- **复现**：把 at 拼进文本时 `_at_target()` 返回 None → 目标退化为发送者；`.hp 满@QQ` 还会让「满@QQ」整体进入数值解析并报「请带上正负号」。
- **空值崩溃**：`dict.get(key, default)` 在键存在且值为 `None` 时返回 `None`，`vitals.clamp(None, …)` 抛 `TypeError` → 被 `except Exception` 兜成「指令处理出错」。这正是 1.82.1 引入可空字段后的连带影响。
- **SAN 缺省值**：原来取 `max_san`（99−克苏鲁神话），比初始意志（POW）高，会让「从未扣过 SAN 的卡」显示出 99；改为 `min(意志, 上限)`。
- **测试 QQ 号长度**：文本兜底要求 5–12 位，测试里原本的 3 位 ID 会被拒，故把 `DM_ID/PLAYER_ID` 换成 9 位。
- **未做**：文本兜底不认 `@昵称`（只认数字），避免误伤正文；也不做「@all」批量改值。
