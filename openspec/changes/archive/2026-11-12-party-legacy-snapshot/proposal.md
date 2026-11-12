# 准备名单：旧快照按当前角色卡补展示字段

## Why

所有者反馈：准备名单里第一个人 `· 埃洛Erodis → 桐島 英二` 后面的括号没了，其余三人正常显示（`（酒保 · 27岁）` 等）。

原因：1.81.1 才在准备快照里写入 `rules` / `occupation` / `age`。更早准备的快照没有这三个字段，`_card_suffix()` 于是按 DND 渲染，而快照里的 `race`/`class_name` 为空、`level` 缺省 0 → 三者全空 → 不显示括号。名单按 `prepared_at` 升序排列，最早准备的那个人正好排第一，所以只有它没有括号。

## What Changes

- `plugins/trpg_session/__init__.py` 新增 `_display_snapshot(snap)`：快照缺 `rules` 时，按 `char_id`（回落到当前角色卡）读取实时角色卡，补上 `rules`/`race`/`class_name`/`level`/`occupation`/`age` 供展示；卡已删除时原样返回（不显示括号）。
- 名单渲染改用 `_card_suffix(_display_snapshot(snap))`。快照本身不写盘，`pending.json` 与准备语义不变。

## Capabilities

### Modified Capabilities

- `trpg-party-roster`：准备名单的角色卡括号。

## Scope and Compatibility

- 只影响渲染：新快照（有 `rules`）原样返回，不触发任何读卡。
- 旧快照不需要重新 `/跑团 准备`，也不会被改写；下次真正准备时自然写入完整字段。
- 无数据库变更、无新增依赖；版本 1.83.1。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 COC 旧快照 | `python -m pytest test/test_trpg_session.py -q -k legacy` | 无 `rules` 的旧快照 + 当前 COC 卡 → `（酒保 · 27岁）` |
| AC02 DND 旧快照 | 同上 | 无 `rules` 的旧快照 + 当前 DND 卡 → `（人类 战士 Lv.3）` |
| AC03 卡已删除 | 同上 | 取不到卡时返回原快照 → 括号为空且不报错 |
| AC04 新快照不变 | 同上 | 有 `rules` 的快照原样返回（同一对象） |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate trpg-party-roster --strict`；归档与实现同一 commit | `CHANGELOG [1.83.1]` 与 `BOTERO_VERSION` 一致 |
