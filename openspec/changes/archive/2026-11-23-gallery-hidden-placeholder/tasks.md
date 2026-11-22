# 实施与验收任务

## 1. 数据层（`webapp/gallery/repository.py`）
- [x] 1.1 删除 `fetch_checkins_paginated` 的 `keep` 参数与切片前过滤，恢复 2.4.0 的形态；保留 `CheckinImage.is_private`（状态判定仍需要）。对应 AC02。

## 2. 路由层（`webapp/gallery/app.py`）
- [x] 2.1 `api_checkins` 撤掉 `keep` 谓词，所有记录都下发；`total`/`has_more` 回到全量口径。对应 AC02。
- [x] 2.2 图片位映射：作者本人与 `show` → `/thumb/…` + `/media/…`；`blur` → 两支 `/thumb/…?blur=1`；`text`/`hidden` → 两支空字符串。对应 AC01、AC03。

## 3. 前端（`webapp/static/gallery.js`、`core/web/static/base.css`）
- [x] 3.1 `appendCard` 增加空 URL 分支：渲染 `.card-placeholder`（文案「图片仅作者可见」），不绑定灯箱点击；非空 URL 保持原逻辑。对应 AC04。
- [x] 3.2 `base.css` 新增 `.card-placeholder`（`aspect-ratio: 3 / 4`、`--tint` 底、居中文字、`cursor: default`）。对应 AC04。

## 4. 测试
- [x] 4.1 `test/scripts/check_gallery_privacy.py`：`text`/`hidden` 段改为「条目存在 + 两支 URL 空串 + `has_file` true」；`total`/分页段改为全量口径；`show`/`blur`/作者视角段保持。对应 AC01、AC02、AC03。
- [x] 4.2 新增 `test/test_gallery_render.js`（node DOM stub）：空 URL → 占位卡且无灯箱；非空 URL → `<img>` + 灯箱。对应 AC04、AC06。
- [x] 4.3 既有脚本回归：`check_profile_checkins.py`、`check_special_filename_media.py`、`check_webapp_api_contract.py`。对应 AC05。
- [x] 4.4 全量 `python -m pytest -q`。对应 AC06。

## 5. 文档与版本
- [x] 5.1 `specs/web-gallery.md`：图库口径改写为「卡片照常下发，`text`/`hidden` 的图片位为空字符串、客户端画占位并注明图片仅作者可见」。对应 AC07。
- [x] 5.2 `specs/conventions.md`：双端一致约束把「业务不可见 ≠ 占位」改写为「条目级不可见不下发 / 图片级不可见下发卡片 + 空 URL 占位」。对应 AC07。
- [x] 5.3 `docs/webapp-api.md`：`GET /api/checkins` 行补 `text`/`hidden` 态空 URL 说明。对应 AC07。
- [x] 5.4 `core/config.py::BOTERO_VERSION` `2.4.1 → 2.4.2`；`CHANGELOG.md` 顶部新增 `[2.4.2]` 节。对应 AC08。

## 6. 验收与交付
- [x] 6.1 逐条执行 AC01–AC09，命令与结果记入 `acceptance.md`。对应 AC01–AC09。
- [x] 6.2 `openspec validate 2026-11-23-gallery-hidden-placeholder --strict` → `openspec archive ... --yes` → `openspec validate checkin-gallery --strict`；归档与实现同一 commit（不提交 `app/` 子模块指针）。对应 AC09。
