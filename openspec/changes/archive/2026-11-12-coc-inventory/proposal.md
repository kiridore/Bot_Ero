# COC 随身物品（装备 / 背包）

## Why

新卡（`docs/COC7空白卡CY26.3.xlsx` 人物卡 77–94 行）有「随身物品」表：状态 / 部位 / 物品名称 / 背包格。我们完全没有这块——玩家没法记录带什么、穿什么，`.ra`、资产、查看页都看不到随身物品。

## What Changes

- 卡片新增 `inventory: [{status, slot, name, slots}]`（最多 40 行）。
- 校验：名称必填、≤30 字、不区分大小写去重；状态必须是「装备 / 携带 / 背包」之一（可空）；背包格 0–20 的整数（可空）。
- `/api/trpg/coc/options` 下发 `inventory_statuses`；`CharacterIn`/`CharOut` 增加 `inventory`。
- 建卡页新增「随身物品」表格：状态下拉、部位文本框、名称、背包格数字框、删除按钮、添加按钮，底部按状态统计件数与合计格数。
- 查看页按状态分组列出（`装备：防弹背心（躯干／2 格）`）并显示总件数与总格数。
- `/跑团 角色 查看` 增加「装备」行：前 6 件（带状态）+ 「共 N 件 · M 格」，超过 6 件用「…」。
- 跑团记录快照新增 `inventory_count` / `inventory_slots`（不存明细，避免 `meta.json` 膨胀）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：随身物品字段、校验与展示。

## Scope and Compatibility

- 全新字段，旧卡没有 `inventory` 时视为空表，不迁移、不报错。
- 背包格只做统计，不设硬上限（规则里容量与体格相关，硬编码容易冲突）。
- 部位是自由文本（新卡没有枚举，锁死会经常选不到）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 校验 | `python -m pytest test/test_trpg_coc.py -q -k Inventory` | 名称必填、去重、状态三态、格数 0–20、最多 40 行；合法条目通过 |
| AC02 摘要 | 同上 | `inventory_summary` 返回件数与总格数；`format_sheet` 输出「装备：…（状态）…」与「共 N 件 · M 格」，超过 6 件截断并加「…」 |
| AC03 接口 | `python test/scripts/check_trpg_coc_api.py` | 带物品的卡可保存并原样回传；非法状态 400；options 下发三个状态 |
| AC04 页面 | `node test/test_trpg_coc_view_dom.js`；人工看 `/trpg/coc` | 查看页按状态分组并显示合计；建卡页有表格、添加/删除与实时合计 |
| AC05 快照 | `python -m pytest test/test_trpg_snapshots.py -q -k Inventory` | 快照含件数与总格数；非数字格数按 0 |
| AC06 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.81.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
