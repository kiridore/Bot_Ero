# 参团角色卡不列 DM 与观察者

## Why

1.98.3 只把观察者从「参团角色卡」里去掉，DM 的卡仍会列出。DM 同样是以群身份在场、不扮演角色，把他的卡放进「参团角色卡」同样会被误读成「DM 也参团演出了」。

## What Changes

- `webapp/static/trpg_record.js::renderSheets` 的过滤条件从 `p.role !== "ob"` 改为 `!isStaffRole(p.role)`（`dm` / `ob` 都排除），复用 1.89.2 定义的 `isStaffRole()`。
- 测试：三参与（DM / 玩家 / 观察者）时折叠栏只剩 1 条——玩家的；另加两条断言「DM 的卡不出现」「玩家的卡仍在」。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：参团角色卡区块的成员范围（收紧到只列玩家）。

## Scope and Compatibility

- 只影响这一个折叠栏；DM 的消息气泡、观战席样式、角色卡本身都不变，卡片仍可从 `/trpg` 车卡列表打开。
- 无数据库变更；版本 1.98.4。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 只列玩家 | `node test/test_trpg_records_dom.js` | 三人参与时折叠栏 1 条，且是玩家的卡 |
| AC02 DM 不列 | 同上 | 列表里没有 DM 的链接 |
| AC03 观察者不列 | 同上 | 列表里没有观察者的链接 |
| AC04 全量回归 | `python -m pytest -q` | 全绿 |
| AC05 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.98.4]` 与 `BOTERO_VERSION` 一致 |
