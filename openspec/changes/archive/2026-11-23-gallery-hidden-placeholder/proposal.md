# 图库隐藏态改为「卡片保留 + 图片占位」（2.4.2）

## Why

所有者原始指令（不得改写）：

> 我的意思是，我需要进行这样的改动。之前的改动是个人隐私设置隐藏打卡图后，在打卡图库里非作者将完全看不到这张图，包括卡片，现在我希望在打卡图库里能显示这次打卡的卡片，但是图片换成占位图

即：2.4.1 把 `text`/`hidden` 态的条目整体从 `/api/checkins` 剔除（所有者当时裁决 Q2:A），现在改为**卡片照常下发、图片位换成占位**——非作者能看到「谁在哪天打了卡」，但看不到图片本体。

现状事实（已核实，2026-11-23，HEAD `4d6a361` / `BOTERO_VERSION 2.4.1`）：

- `webapp/gallery/app.py::api_checkins` 用 `keep` 谓词在分页切片前把 `text`/`hidden` 条目剔除，`total` 同步减少；repository 的 `keep` 参数就是为它引入的。
- `webapp/static/gallery.js::appendCard` 无条件 `img.src = item.thumbnail_url || item.image_url` 并绑定灯箱点击；网页端没有任何「占位卡」渲染路径。
- App 侧 `app/lib/features/gallery/auth_image.dart::AuthImage` 在 `url.isEmpty` 时**已经**渲染占位灰块（`errorBuilder`/空串分支），`app/lib/features/gallery/checkin_card.dart` 的图片位是 `AuthImage(url: thumbnailUrl.isEmpty ? imageUrl : thumbnailUrl)`——因此「下发空 URL ⇒ App 自动出灰块」。但 App 没有「图片仅作者可见」文案，需在 `app/` 独立提案跟进（`specs/conventions.md` 双端一致约束要求）。
- `has_file` 字段在两端 UI 均未消费（仅生成模型里存在），本次不动它的语义（文件是否存在）。
- `specs/conventions.md:264` 的双端一致约束现有条目「业务不可见 ≠ 占位」与本次裁决冲突，需同 commit 改写为「条目级不可见不下发 / 图片级不可见下发卡片 + 空 URL 占位」。

## What Changes

- `webapp/gallery/app.py::api_checkins`：撤掉 `keep` 过滤（所有记录都下发），改为按态决定**图片位**——
  - 作者本人：两支 URL 原样；
  - 非作者 `show`：`/thumb/…` + `/media/…`；
  - 非作者 `blur`：两支 URL 均为 `/thumb/…?blur=1`（不变）；
  - 非作者 `text` / `hidden`：`thumbnail_url` 与 `image_url` 均为**空字符串**（`""`），条目的 `id/user_id/display_name/checkin_date/has_file` 照常下发。
- `webapp/gallery/repository.py`：删除 `keep` 参数（唯一调用方已不再需要），保留 `CheckinImage.is_private`（状态判定仍要用）。
- `webapp/static/gallery.js`：`appendCard` 增加空 URL 分支——渲染 `.card` + `.card-placeholder`（文案「图片仅作者可见」），且**不绑定灯箱点击**；非空 URL 走原逻辑。
- `core/web/static/base.css`：新增 `.card-placeholder` 样式（`aspect-ratio: 3 / 4`、`--tint` 底、居中提示文字），与 App 的 3:4 占位块比例一致。
- 新增 `test/test_gallery_render.js`（node + 现有 DOM stub 套路）：空 URL 渲染占位卡且无灯箱绑定；非空 URL 渲染 `<img>`。
- `test/scripts/check_gallery_privacy.py`：`text`/`hidden` 的断言从「条目不出现」改为「条目存在且两支 URL 为空串、`has_file` 为 true」，`total`/分页断言改为包含占位卡的全量口径。
- 文档：`specs/web-gallery.md` 的「图库口径」改写；`specs/conventions.md` 双端一致约束第 264 行改写（条目级 vs 图片级不可见）；`docs/webapp-api.md` 的 `GET /api/checkins` 行补「`text`/`hidden` 态下发空 URL」。
- 版本 `2.4.1 → 2.4.2`（行为修正，patch）；`CHANGELOG.md` 新增 `[2.4.2]` 节。
- **不做**：不改时间线（`hidden` 事件对非作者仍不下发）；不改媒体路由（Q1:A 既有边界）；不改 `CheckinItemOut` 字段集（不新增 `image_hidden`，用空 URL 表达，因此 `app/openapi/openapi.json` 与 App 生成代码无需刷新）；不改 `has_file` 语义；不改 `app/` 子模块（文案对齐见下方 App 侧结论）。

## Capabilities

### Modified Capabilities

- `checkin-gallery`（2.4.1 已建立的图库可见性能力）：REMOVED 既有 Requirement「图库按查看者应用作者打卡显示设置」——它的「该记录 MUST NOT 出现在响应中」「`total` 只统计可见记录」「过滤发生在切片之前」与本裁决冲突，整条重述；ADDED「图库全量下发打卡条目并按查看者决定图片位」——四态映射（作者本人 / `show` / `blur` 不变，`text`/`hidden` 下发空 URL）+ `total` 全量口径 + 媒体路由边界不变。

## Scope and Compatibility

- **社区版与私有版两者一致**：改动只在 webapp 读侧与前端渲染，无 edition 分支、无配置差异。
- **契约兼容**：`CheckinItemOut` 字段集不变，只有取值语义新增一种（`thumbnail_url`/`image_url` 可为空串；改动前永不为空）。OpenAPI 快照无需刷新，App 生成客户端无需重跑。
- **行为变化（有意）**：`/gallery` 的「共 N 张」恢复为全量打卡数（含占位卡）；非作者看到 `text`/`hidden` 打卡的卡片，但图片位是占位块且**无法打开灯箱**。时间线口径不变（`hidden` 事件仍对非作者完全不下发），两端的差异是所有者本次明确要求的结果。
- **App 侧结论（按 `specs/conventions.md` 双端一致约束）**：服务端下发空 URL 后，App 图库**已自动**出占位灰块（`AuthImage` 空串分支）并保留卡片（`CheckinCard` 的昵称+时间）。缺的是同一文案「图片仅作者可见」与 `app/test/` 用例，需在 `app/openspec/` 建提案、随 App 版本 `0.22.1 → 0.22.2` 落地；主仓库本次只改子模块外的代码，不改子模块指针。
- **部署与旧数据**：无 schema 变更、无迁移、无回填。bot 进程零改动。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 | `python test/scripts/check_gallery_privacy.py` 的 `text`/`hidden` 段 | 非作者响应**含**该条目，`thumbnail_url == ""`、`image_url == ""`、`has_file == true`，`display_name`/`checkin_date` 照常非空；脚本 `PASS: 0 failures`、退出码 0 |
| AC02 | 同上脚本的 `total`/分页段 | 该段作者 3 条打卡（私聊 `text`、群聊 `hidden`、另一作者 `show` 视具体构造）时非作者 `total` 等于**全部**记录数（不再是可见子集），`page_size=1` 逐页合计等于 `total`、末页 `has_more` 为 false |
| AC03 | 同上脚本的 `show`/`blur`/作者视角段 | 作者本人两支 URL 为 `/thumb/…`+`/media/…` 无 query；非作者 `show` 同款；非作者 `blur` 两支 URL 均为 `/thumb/…?blur=1` |
| AC04 | `node test/test_gallery_render.js` | 空 URL 条目渲染 `.card` 且含 `.card-placeholder`（文本「图片仅作者可见」）、未绑定灯箱点击；非空 URL 条目渲染 `<img>`、点击打开灯箱；退出码 0 |
| AC05 | `python test/scripts/check_profile_checkins.py`；`python test/scripts/check_special_filename_media.py`；`python test/scripts/check_webapp_api_contract.py` | 三脚本退出码 0：`/api/me/checkins` 本人视角不变；媒体路由不变；`/api/checkins` schema 未变 |
| AC06 | `python -m pytest -q` | 全量通过（0 failed；`test_gallery_render.js` 由 `test/test_dom_render_suites.py` 自动纳入） |
| AC07 | `rg -n '空字符串' specs/web-gallery.md docs/webapp-api.md`；`rg -n '图片级不可见' specs/conventions.md` | 三份文档都改到：`specs/web-gallery.md` 图库口径写明 `text`/`hidden` 下发空 URL 与客户端占位；`docs/webapp-api.md` 的 `/api/checkins` 行同义；`specs/conventions.md` 双端一致约束把「业务不可见 ≠ 占位」改写为「条目级不可见不下发 / 图片级不可见下发卡片 + 空 URL 占位」 |
| AC08 | `grep -n 'BOTERO_VERSION = "2.4.2"' core/config.py`；`sed -n '1,25p' CHANGELOG.md` | 版本 2.4.2；CHANGELOG 顶部 `[2.4.2]` 节说明「隐藏态改为占位卡片」与时间线口径差异 |
| AC09 | `openspec validate 2026-11-23-gallery-hidden-placeholder --strict`；`openspec archive ... --yes`；`openspec validate checkin-gallery --strict` | 归档前 valid；归档后 `checkin-gallery` 规范含改写后的 Requirement 且 valid；归档与实现同一 commit |
