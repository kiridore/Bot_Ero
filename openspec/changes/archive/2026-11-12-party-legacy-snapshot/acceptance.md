# 旧快照展示 — 验收记录

实施分支：`master`；版本 1.83.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 COC 旧快照 | `test_legacy_snapshot_uses_live_card`：无 `rules` 的旧快照 + 当前 COC 卡（酒保/27）→ `（酒保 · 27岁）` | 通过 |
| AC02 DND 旧快照 | `test_legacy_snapshot_dnd_card` → `（人类 战士 Lv.3）` | 通过 |
| AC03 卡已删除 | `test_legacy_snapshot_without_card` → 括号为空、不抛异常 | 通过 |
| AC04 新快照不变 | `test_new_snapshot_not_touched` → 同一对象返回（不读卡） | 通过 |
| AC05 全量回归 | `python -m pytest -q` → **888 passed**（5:10） | 通过 |
| AC06 文档与归档 | `openspec validate trpg-party-roster --strict` valid；`CHANGELOG [1.83.1]` 与 `BOTERO_VERSION = "1.83.1"` 一致；同一 commit 归档 | 通过 |

## 根因

`_card_suffix()` 对缺 `rules` 的快照走 DND 分支，而旧快照没有 `race`/`class_name`、`level` 缺省 0，三者全空时按设计不显示括号。名单按 `prepared_at` 升序，最早准备的人排第一，所以只有第一个人没有括号。

## 修法

展示时才补字段，不写盘、不需要重新准备；新快照完全不受影响。
