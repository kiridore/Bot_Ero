# 参团角色卡不列观察者

## Why

记录详情页的「参团角色卡（开始 / 结束）」会列出所有有角色卡或快照的参与者，包括观察者。观察者是观战席上的人，不在舞台上，把他的卡放进「参团角色卡」会让人以为他也参团演出了。

## What Changes

- `webapp/static/trpg_record.js::renderSheets`：过滤条件加上 `p.role !== "ob"`，观察者即使有卡/快照也不列。
- 测试：`test_trpg_records_dom.js` 断言条目从 3 变 2，且列表里没有观察者的链接、DM 的仍在。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：参团角色卡区块的成员范围。

## Scope and Compatibility

- 只影响这一个折叠栏；消息气泡里的观战席样式不变，观察者的卡仍可从 `/trpg` 车卡列表打开。
- DM 的角色卡照常显示（本轮只按要求排除观察者）。
- 无数据库变更；版本 1.98.3。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 不列观察者 | `node test/test_trpg_records_dom.js` | 三人参与（DM / 玩家 / 观察者）时折叠栏只有 2 条，且没有观察者的链接 |
| AC02 DM 仍显示 | 同上 | 列表里仍有 DM 的角色卡链接 |
| AC03 全量回归 | `python -m pytest -q` | 全绿 |
| AC04 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.98.3]` 与 `BOTERO_VERSION` 一致 |
