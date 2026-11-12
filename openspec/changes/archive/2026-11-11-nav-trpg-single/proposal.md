# 顶部导航合并跑团入口

## Why

顶部导航同时有「跑团」（`/trpg`）与「跑团记录」（`/trpg/records`）两个入口，而这两个页面**本来就有页内页签**「车卡 / 跑团记录」互相切换——顶层重复了一份，且「跑团记录」占据一个本可以留给其它分区的槽位。

## What Changes

- `core/web/static/nav.js`：删除「跑团记录」项，只保留「跑团 → `/trpg`」。最长前缀匹配逻辑不动，`/trpg/records`、`/trpg/coc`、`/trpg/levelup/*` 都会点亮「跑团」。
- `webapp/timeline/entries.json`：主页网格里「跑团」与「跑团记录」两张卡合并为一张，描述改为「车卡、跑团记录与角色卡查看」。
- 页内页签（车卡 / 跑团记录）保持不变，仍是进入记录列表的唯一入口。

## Capabilities

### New Capabilities

- `web-navigation`：站点顶部导航与主页网格的分区入口。

## Scope and Compatibility

- 只删入口、不改路由：`/trpg/records`、`/trpg/records/<群>/<目录>`、`/trpg/coc`、`/trpg/levelup/<编号>` 全部照旧可访问。
- 主页网格少一张卡，其余条目的顺序与内容不变。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 导航唯一入口 | `node test/test_nav_render.js` | 导航中 `href="/trpg"` 出现 1 次，且不含 `href="/trpg/records"` |
| AC02 记录页高亮 | `node test/test_trpg_records_dom.js` | 访问 `/trpg/records` 时顶部高亮项是 `/trpg`，且只有一个高亮项 |
| AC03 页内页签仍在 | 同上 | 记录页仍有「车卡 / 跑团记录」页签且记录页签为 active |
| AC04 主页网格合并 | 人工看主页 | 只剩一张「跑团」卡，点击进入 `/trpg`，可再点页签去记录 |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate web-navigation --strict` | 全量回归绿；`CHANGELOG [1.76.1]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
