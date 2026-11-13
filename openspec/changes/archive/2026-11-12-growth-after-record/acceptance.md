# 结束后可结算成长 — 验收记录

实施分支：`master`；版本 1.88.3。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 结束后可结算 | `TestGrowth::test_settles_after_recording_ended`：`强制开始` → `结束`（`current_rule` 已回落 `dnd5e`）后 `/跑团 成长` 正常结算，`growth` 落到卡上 | 通过 |
| AC02 录制中仍门控 | `test_refused_under_dnd_recording`：DND 录制中提示「幕间成长需要 COC 7th」，标记保留 | 通过 |
| AC03 无录制跟随卡片 | `test_no_recording_follows_card_rule`：无录制、群规则未设置时 COC 卡照常结算 | 通过 |
| AC04 全量回归 | `python -m pytest -q` → **920 passed**（5:13） | 通过 |
| AC05 文档与归档 | `openspec validate coc-skill-growth --strict` valid；`CHANGELOG [1.88.3]` 与 `BOTERO_VERSION = "1.88.3"` 一致 | 通过 |

## 现场复现（修复前）

```
录制中成长: 哈维 的幕间成长（1 项）· 侦察：D100=90 > 25 → +10
结束后 current_rule: dnd5e
结束后成长: 本团规则是 DND 5E，幕间成长需要 COC 7th   ← 卡上勾还在，但结算被拒
```

## 裁定

- **为什么成长标记不会丢**：`.ra` 成功时通过 `store.update_char()` 直接写角色卡 JSON，与录制记录、`meta.json` 无关。
- **为什么问题只在「结束后」出现**：`_start_session` 调 `party.clear_all()` 删掉 `pending.json`（准备名单与规则都在这份文件里），结束录制不会重建它。
- **为什么不改持久化**：把群规则另存一份属于「群设置」范畴，与本缺陷无关；按卡片规则结算已足够且更符合「成长是卡片级操作」。
- **遗留**：若一场团结束后没结算、直接开下一场，同一技能仍只有一个勾（规则上是每次幕间一次机会），补结算时只掷一次。
