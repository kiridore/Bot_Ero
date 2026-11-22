# 验收记录

环境：`master`（起点 `1552bda`，`BOTERO_VERSION 2.4.0 → 2.4.1`），Windows 开发机，2026-11-23。bot 进程与数据库零改动；社区版/私有版共用同一实现。

| AC | 验证命令 | 结果 | 证据 |
|---|---|---|---|
| AC01 | `python test/scripts/check_gallery_privacy.py` 的 `blur` 段 | ✅ | `ok - blur: thumbnail_url 为模糊图 /thumb/32870101/a_group.png?blur=1`、`ok - blur: image_url 也是模糊图（不给 /media/） /thumb/32870101/a_group.png?blur=1`、`ok - blur: 作者本人仍是原图 ('/thumb/32870101/a_group.png', '/media/32870101/a_group.png')`；脚本 `PASS: 0 failures`，退出码 0（共 26 条 `ok`） |
| AC02 | 同上脚本的 `text` / `hidden` 段 | ✅ | `ok - text: 非作者看不到该条目`、`ok - text: 非作者 total 只算可见项 total=1 items=1 has_more=False`、`ok - text: 作者本人仍看到该条目 total=2`；`hidden` 三段同构通过 |
| AC03 | 同上脚本的 `show` 段 | ✅ | `ok - show: thumbnail_url 为原缩略图 /thumb/32870101/a_group.png`、`ok - show: image_url 为原图 /media/32870101/a_group.png`、`ok - show: 私聊记录同样原图 /media/32870101/a_private.png` |
| AC04 | 同上脚本的类型分流段 | ✅ | `ok - 分流: 私聊 blur → 私聊模糊 /thumb/32870101/a_private.png?blur=1`、`ok - 分流: 群聊 show → 群聊原图 /media/32870101/a_group.png`、`ok - 分流: 对调后私聊原图`、`ok - 分流: 对调后群聊模糊 /thumb/32870101/a_group.png?blur=1` |
| AC05 | 同上脚本的 `total`/分页段 | ✅ | `ok - 分页: 非作者 total 为可见总数 total=2`、`ok - 分页: 第一页 1 条且 has_more items=1 has_more=True`、`ok - 分页: 第二页 1 条且无更多 items=1 has_more=False`、`ok - 分页: 两页合计等于 total 2/2` |
| AC06 | `python test/scripts/check_profile_checkins.py`；`python test/scripts/check_special_filename_media.py` | ✅ | 前者 `PASS: 0 failures`；后者 `PASS: 0 failures`（含 `ok - media 200 png`、`ok - thumb 200`、`ok - profile image_url encoded`）。新脚本另含 `ok - 媒体: 模糊缩略图端点 200`、`ok - 媒体: 原图端点行为不变（已知边界） 200`、`ok - 个人中心: 本人列表仍是原图 200` |
| AC07 | `python test/scripts/check_webapp_api_contract.py` | ✅ | 输出 `全部通过`，退出码 0；`/api/checkins` 响应字段集未变（未新增/删除字段，分页形态仍 `items/total/page/page_size/has_more`），`app/openapi/openapi.json` 无需刷新 |
| AC08 | `python -m pytest -q` | ✅ | `1059 passed, 18527 warnings in 352.02s (0:05:52)`，0 failed；单跑 `test/test_webapp_api_suites.py::test_webapp_api_suite[check_gallery_privacy.py]` → `1 passed`，确认新脚本被自动发现纳入回归 |
| AC09 | `rg -n '图库口径' specs/web-gallery.md`；`rg -n 'api/checkins' docs/webapp-api.md` | ✅ | `specs/web-gallery.md:460` 新增「图库口径（与时间线同一设置、同一判定函数）」、`:461` 新增「媒体直链不强制（已知边界）」；原文「图库页 `/gallery` 不受此设置影响」已删除（`rg -n '不受此设置影响' specs/web-gallery.md` 无命中）。`docs/webapp-api.md:66` 行补「按查看者应用作者打卡显示设置：作者本人全部可见（原图）；非作者 `show` 原图、`blur` 两支 URL 均为 `/thumb/…?blur=1`、`text`/`hidden` 条目不下发，`total` 只统计可见项」 |
| AC10 | `grep -n 'BOTERO_VERSION = "2.4.1"' core/config.py`；`sed -n '1,20p' CHANGELOG.md` | ✅ | `core/config.py:17:BOTERO_VERSION = "2.4.1"`；`CHANGELOG.md:9:## [2.4.1]`，三条描述行为变化（图库遵守显示设置、`total` 只数可见项、媒体直链已知边界） |
| AC11 | `openspec validate 2026-11-23-gallery-privacy --strict`；`openspec archive 2026-11-23-gallery-privacy --yes`；`openspec validate checkin-gallery --strict` | ✅ | 见下方「归档记录」 |

## 行为验证说明

- **与时间线同源而非同构复制**：图库的类型判定读 `checkin_records.is_private`（bot 打卡插件与网页打卡都写的同一标记，与时间线事件的 `data.private` 同源），状态判定调 `core/user_settings.py::checkin_display()` 的同一个函数——图库没有自己的四态实现，因此不存在两处口径漂移。
- **作者视角零变化**：`keep` 谓词对 `item.user_id == viewer_id` 恒真，输出分支对作者不加 `?blur=1`；脚本以作者身份断言 `text`/`hidden` 记录仍下发、URL 仍是 `/thumb/` + `/media/`。
- **过滤位置**：`fetch_checkins_paginated` 的 `keep` 在构造 `CheckinImage` 的同一循环里、`total` 计算与 `[start:end]` 切片之前执行，因此 AC05 的逐页断言（`page_size=1` 两页合计恰为 `total`）能通过——若过滤放在响应组装层，第二页会出现空页或 `has_more` 卡在 true。
- **不传 `keep` 的调用方（个人中心 `/api/me/checkins`）**：行为逐字节不变，由 `check_profile_checkins.py`（AC06）与全量回归（AC08）双重覆盖。
- **Q1:A 裁决的已知边界**：媒体路由 `/thumb`、`/media` 本次未加查看者判定，脚本用 `ok - 媒体: 原图端点行为不变（已知边界） 200` 把该边界固化为断言（防止有人误以为已被拦），并写入 `specs/web-gallery.md`。将来收紧时改这一对路由即可，图库侧无需再动。

## 实施路径（便于复核 diff）

- `webapp/gallery/repository.py`：`CheckinImage` 增 `is_private`；`fetch_checkins_paginated` 增 `keep` 并在切片前过滤；两个分页分支合并为一次构造+过滤循环（原 `only_with_file=False` 分支的 `resolve_image_path` 行为保留）。
- `webapp/gallery/app.py`：`api_checkins` 增 `Depends(get_current_user_id)`、请求级作者设置缓存、`keep` 谓词、`blur` 态双 URL 改写；响应模型与参数未变。
- `test/scripts/check_gallery_privacy.py`（新增）：26 条断言覆盖 show/blur/text/hidden × 作者/非作者 × 类型分流 × total/分页 × 媒体路由不变 × 个人中心不变。

## 归档记录

- `openspec validate 2026-11-23-gallery-privacy --strict`：`Change '2026-11-23-gallery-privacy' is valid`（另有非阻断警告：Why 节超 1000 字符——按仓库惯例保留所有者原话与现状事实清单，不做删减）。
- `openspec archive 2026-11-23-gallery-privacy --yes`：`Specs updated successfully`，新建能力规范 `openspec/specs/checkin-gallery/spec.md`（Requirement: 图库按查看者应用作者打卡显示设置，5 scenarios），变更目录移入 `openspec/changes/archive/2026-11-23-gallery-privacy/`。
- `openspec validate checkin-gallery --strict`：`Specification 'checkin-gallery' is valid`（非阻断 INFO：Requirement 文本 >500 字符，因需在同一条内枚举四态规则故保留）。
- 归档与实现同一 commit；未提交 `app/` 子模块指针（本次无 API schema 变化，OpenAPI 快照未刷新）。
