# 准备名单按规则显示角色卡信息

## Why

`/跑团` 准备名单里每张卡后面固定拼「（种族 职业 Lv.等级）」，这是 DND 专用字段。调查员卡没有种族和职业等级，于是显示成：

```
· 埃洛Erodis → 桐島 英二（? ? Lv.1）
```

两个问号加一个无意义的 `Lv.1`，玩家会以为是数据没读到。

## What Changes

- `/跑团 准备` 快照新增 `rules`、`occupation`、`age` 三个字段（DND 字段保持不动）。
- 名单渲染改为按规则拼接：
  - `coc7th` →「（药剂师 · 28岁）」，没有职业时「（无职业）」
  - `dnd5e` →「（人类 战士 Lv.3）」，三个字段都为空且等级为 1 时不显示括号
- 旧快照（无 `rules`）按 DND 处理，并同样在信息为空时省略括号，不再出现 `?`。

## Capabilities

### Modified Capabilities

- `trpg-party-roster`：准备名单的角色卡描述。

## Scope and Compatibility

- 仅影响展示，准备状态与录制流程不变。
- 旧 `pending.json` 里的快照没有新字段，渲染时回落到 DND 分支且不再显示问号；玩家重新准备一次即写入新字段。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 COC 卡片 | `python -m pytest test/test_trpg_session.py -q -k PreparedCardSuffix` | `rules=coc7th` + 药剂师 + 28 岁 →「（药剂师 · 28岁）」；无职业 →「（无职业）」 |
| AC02 DND 卡片 | 同上 | 人类/战士/3 级 →「（人类 战士 Lv.3）」；全空且 1 级 → 空串 |
| AC03 旧快照 | 同上 | 没有 `rules` 的快照按 DND 处理，全空时不显示括号 |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate trpg-party-roster --strict` | 全量回归绿；`CHANGELOG [1.81.1]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
