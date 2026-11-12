# 实施与验收任务

- [x] 1.1 `webapp/trpg/app.py`：`_enrich_participants` / `_participants_with_identity`，详情接口返回 `display_name`、`avatar_url`。对应 AC04。
- [x] 1.2 `webapp/static/trpg_record.js`：`renderAvatar`（img + 回落）、`displayName` 用实时名称、`rebuildNickMap` 记录头像。对应 AC01–AC03。
- [x] 1.3 `webapp/static/trpg.css`：`.trpg-avatar` 支持图片。对应 AC01。
- [x] 1.4 测试：DOM 用例 3 条断言 + 记录 API 断言。对应 AC01–AC04。
- [x] 1.5 `CHANGELOG [1.79.6]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC05。
