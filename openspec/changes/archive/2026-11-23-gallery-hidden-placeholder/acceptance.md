# 验收记录

环境：`master`（起点 `4d6a361`，`BOTERO_VERSION 2.4.1 → 2.4.2`），Windows 开发机，2026-11-23。bot 进程与数据库零改动；社区版/私有版共用同一实现。

| AC | 验证命令 | 结果 | 证据 |
|---|---|---|---|
| AC01 | `python test/scripts/check_gallery_privacy.py` 的 `text`/`hidden` 段 | ✅ | `ok - text: 非作者仍看到卡片`、`ok - text: 图片位两支 URL 为空串 ('', '')`、`ok - text: has_file 仍按磁盘文件为 true True`、`ok - text: 卡片信息（昵称/日期）照常下发 ('32870101', '2026-09-02 12:00:00')`；`hidden` 同构四段通过；脚本 `PASS: 0 failures`、退出码 0（共 32 条 `ok`） |
| AC02 | 同上脚本的 `total`/分页段 | ✅ | `ok - text: total 不扣除占位卡 total=2 items=2`、`ok - 分页: total 为全部记录数（含占位卡） total=3`、`ok - 分页: 第一页 2 条且 has_more items=2 has_more=True`、`ok - 分页: 第二页 1 条且无更多 items=1 has_more=False`、`ok - 分页: 每页 total 一致 3/3` |
| AC03 | 同上脚本的 `show`/`blur`/作者视角段 | ✅ | `ok - show: thumbnail_url 为原缩略图 /thumb/32870101/a_group.png`、`ok - show: image_url 为原图 /media/32870101/a_group.png`、`ok - blur: thumbnail_url 为模糊图 /thumb/32870101/a_group.png?blur=1`、`ok - blur: image_url 也是模糊图（不给 /media/）`、`ok - blur: 作者本人仍是原图 ('/thumb/32870101/a_group.png','/media/32870101/a_group.png')`、`ok - 分流: 私聊 blur → 私聊模糊` / `对调后群聊模糊` |
| AC04 | `node test/test_gallery_render.js` | ✅ | 14 条 `ok`、退出码 0：`ok - 三条记录都出卡片（含图片不可见的两条） 3`、`ok - 空 URL 渲染占位块`、`ok - 占位文案为「图片仅作者可见」`、`ok - 空 URL 不渲染 <img>`、`ok - 空 URL 卡片信息仍在（昵称+时间）`、`ok - 空 URL 不绑定灯箱点击`、`ok - 点占位卡灯箱保持关闭`、`ok - 点 show 卡打开灯箱`、`ok - 灯箱指向原图`、`ok - blur 态渲染 <img> 且是模糊图` |
| AC05 | `python test/scripts/check_profile_checkins.py`；`check_special_filename_media.py`；`check_webapp_api_contract.py` | ✅ | 依次 `exit 0 / 17 ok / PASS: 0 failures`、`exit 0 / 11 ok / PASS: 0 failures`、`exit 0 / 30 ok`（`/api/checkins` 字段集未变，`app/openapi/openapi.json` 无需刷新） |
| AC06 | `python -m pytest -q` | ✅ | `1060 passed, 18528 warnings in 355.81s (0:05:55)`，0 failed；新增 `test_gallery_render.js` 由 `test/test_dom_render_suites.py` 自动发现 |
| AC07 | `rg -n '空字符串' specs/web-gallery.md docs/webapp-api.md`；`rg -n '图片级不可见' specs/conventions.md` | ✅ | `specs/web-gallery.md:460` 图库口径改写（`text`/`hidden` 照常下发、两支 URL 空字符串、占位并注明图片仅作者可见、`total` 计入）+ `:461` 新增「图库与时间线的差异（所有者裁决）」；`docs/webapp-api.md:66` 同步；`specs/conventions.md:264` 由「业务不可见 ≠ 占位」改写为「条目级不可见 ≠ 图片级不可见」 |
| AC08 | `grep -n 'BOTERO_VERSION = "2.4.2"' core/config.py`；`sed -n '1,25p' CHANGELOG.md` | ✅ | `core/config.py:17:BOTERO_VERSION = "2.4.2"`；`CHANGELOG.md:9:## [2.4.2]`，三条：行为变化、与时间线的差异是故意的、App 自动出占位但文案待补 |
| AC09 | `openspec validate 2026-11-23-gallery-hidden-placeholder --strict`；`openspec archive ... --yes`；`openspec validate checkin-gallery --strict` | ✅ | 见下方「归档记录」 |

## 行为验证说明

- **条目不再剔除**：`keep` 谓词与 repository 的 `keep` 参数一并删除，`fetch_checkins_paginated` 回到 2.4.0 形态（保留 `CheckinImage.is_private`，状态判定仍需要）。`total`/`has_more` 因此回到全量口径，`page_size=2` 两页 `3` 条即 AC02 的断言。
- **图片位三态**：`show`/作者本人 → `/thumb/…` + `/media/…`；`blur` → 两支 `/thumb/…?blur=1`；`text`/`hidden` → 两支 `""`。前端 `appendCard` 用 `Boolean(item.thumbnail_url || item.image_url)` 分流，空串时渲染 `.card-placeholder`（`aspect-ratio: 3 / 4`，与 App 的 `_fallbackAspectRatio` 对齐）且不绑定 `click`，因此灯箱不会打开（AC04 直接断言点击后 `#lightbox` 仍是 `hidden`）。
- **契约零变化**：`CheckinItemOut` 字段集未动，`thumbnail_url`/`image_url` 只是新增一种取值（空串，改动前永不为空）。因此不需要刷新 `app/openapi/openapi.json`、不需要重跑 App 生成客户端。
- **App 侧结论（`specs/conventions.md` 双端一致约束）**：`app/lib/features/gallery/auth_image.dart` 的 `build()` 在 `url.isEmpty` 时返回占位灰块，`checkin_card.dart` 传入 `thumbnailUrl.isEmpty ? imageUrl : thumbnailUrl`——空串在 App 上天然渲染 3:4 占位块、卡片（昵称+时间）保留，**功能已对齐，无需 App 逻辑改动**。差的只有「图片仅作者可见」文案与 `app/test/` 用例，需在 `app/openspec/` 建提案并随 App 版本 `0.22.1 → 0.22.2` 落地；本次主仓库 commit 不含子模块指针。
- **时间线不动**：`hidden` 事件对非作者仍完全不下发（2.2.0 起的既定语义）。两端口径差异已写入 `specs/web-gallery.md`，避免后来者「顺手统一」。

## 实施路径（便于复核 diff）

- `webapp/gallery/repository.py`：删除 `keep` 参数、`Callable` import 与切片前过滤分支（净 -6 行）。
- `webapp/gallery/app.py`：删除 `keep` 谓词；图片位改为按态三分支（`blur` / `text|hidden` / 其余原样）。
- `webapp/static/gallery.js`：`appendCard` 增加 `hasImage` 分流与 `.card-placeholder` 渲染，灯箱只对 `hasImage` 绑定。
- `core/web/static/base.css`：新增 `.card-placeholder`（`aspect-ratio: 3 / 4`、`--tint` 底、居中文字、`cursor: default`）。
- `test/test_gallery_render.js`（新增，14 断言）、`test/scripts/check_gallery_privacy.py`（`text`/`hidden` 与分页段改写，32 断言）。

## 归档记录

- `openspec validate 2026-11-23-gallery-hidden-placeholder --strict`：`Change '2026-11-23-gallery-hidden-placeholder' is valid`。
- `openspec archive 2026-11-23-gallery-hidden-placeholder --yes`：`Specs updated successfully`，`checkin-gallery` 能力 `+1 added / -1 removed`（旧 Requirement「图库按查看者应用作者打卡显示设置」被移除，新 Requirement「图库全量下发打卡条目并按查看者决定图片位」替代）。
- `openspec validate checkin-gallery --strict`：`Specification 'checkin-gallery' is valid`（非阻断 INFO：Requirement 文本 >500 字符，四态映射需在同一条内枚举故保留）。
- 归档与实现同一 commit；未提交 `app/` 子模块指针（App 侧仅需文案与用例跟进，已写入 proposal 的 Scope 与 CHANGELOG）。
