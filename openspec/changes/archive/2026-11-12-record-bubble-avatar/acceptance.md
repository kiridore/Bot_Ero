# 气泡头像与实时名称 — 验收记录

实施分支：`master`；版本 1.79.6。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 头像图片 | `test_trpg_records_dom.js`「有头像的参与者用 QQ 头像图片」：`rebuildNickMap` 注入 `avatar_url` 后气泡头像是 `IMG.trpg-avatar` 且 `src` 含 `qlogo.cn` | 通过 |
| AC02 头像回落 | 「没有头像时回落名字首字」：无头像地址时渲染 `DIV.trpg-avatar`，内容为首字 | 通过 |
| AC03 名称格式 | 「名字行显示角色名（实时名称）」：`艾拉（老张（实时））`；「无角色卡时名字只显示昵称」：`小王` | 通过 |
| AC04 接口字段 | `check_trpg_records_api.py`「参与人带 display_name/avatar_url」：每位参与者都含这两个字段且 `display_name` 非空 | 通过 |
| AC05 文档与归档 | 全量 `pytest` → **790 passed**（5:07）；`openspec validate trpg-record-web --strict` valid；`CHANGELOG [1.79.6]` 与 `BOTERO_VERSION = "1.79.6"` 一致 | 通过 |

## 实测与裁定

- **取法统一**：`resolve_display_name` / `resolve_avatar_url` 与时间线用的是同一对函数（`lru_cache` 缓存），并发用 `ThreadPoolExecutor(16)`，只对详情接口生效。
- **不写回**：`_participants_with_identity` 返回参与者副本，`meta.json` 保持原样——记录是历史数据，不该因为改名而漂移。
- **回落链**：头像 → 首字色块；名字 → 消息自带昵称 → QQ 号。OneBot 不可达时接口仍 200。
- **未做**：列表页（记录行）不解析头像/昵称，避免每次打开列表发一轮 HTTP。
