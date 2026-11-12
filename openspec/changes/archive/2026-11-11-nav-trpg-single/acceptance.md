# 顶部导航合并跑团入口 — 验收记录

实施分支：`master`；版本 1.76.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 导航唯一入口 | `test_nav_render.js`：`href="/trpg"` 出现 1 次；不含 `href="/trpg/records"` | 通过 |
| AC02 记录页高亮 | `test_trpg_records_dom.js`：`/trpg/records` 下高亮项为 `/trpg`，且只有 1 个高亮项 | 通过 |
| AC03 页内页签仍在 | 同一用例：记录页「车卡 / 跑团记录」页签存在，记录页签为 active | 通过 |
| AC04 主页网格合并 | `entries.json` 中 trpg 相关条目只剩 `/trpg`，`desc` 为「车卡、跑团记录与角色卡查看」 | 通过（视觉待确认） |
| AC05 文档与归档 | 全量 `pytest` → **753 passed**（4:42）；`openspec validate web-navigation --strict` valid；`CHANGELOG [1.76.1]` 与 `BOTERO_VERSION = "1.76.1"` 一致 | 通过 |

## 实测与裁定

- **未改路由**：`/trpg/records`、`/trpg/records/<群>/<目录>`、`/trpg/coc`、`/trpg/levelup/<编号>` 全部照旧，只是顶层入口收敛。
- **高亮逻辑未动**：`nav.js` 原有的最长前缀匹配保留——以后若再加 `/trpg/xxx` 子路径，仍然点亮「跑团」。
- **测试改动**：`test_trpg_records_dom.js` 原先断言「nav 含跑团记录入口 + 高亮 /trpg/records」，与新规则冲突，已改为断言「顶层没有跑团记录入口 + 高亮 /trpg」。
