# 打卡图库对非作者应用打卡隐私设置（2.4.1）

## Why

所有者原始指令（不得改写）：

> 目前在时间线使用隐私设定配置后，非作者看到的图片会根据隐私设置变化，但是在打卡图库里，仍然显示的是原图。现在希望打卡图库中非作者查看时，各类图片的显示情况与时间线一致

所有者裁决（回答格式 `Q1:A Q2:A Q3:A Q4:按推荐`）：

- **Q1:A** 只改图库下发（`/api/checkins`），`/thumb/{user,}{filename}`、`/media/{user}/{filename}` 媒体路由**不做**服务端强制（保持现状：带凭证即可取原图）。不做 Q1:B 的「判定下沉到媒体接口」，也因此不波及周报封面与时间线前端（Q3 随之不适用）。
- **Q2:A** `text` 态在图库对非作者**不下发该条目**（图库条目只有图片，没有「仅打卡信息」可展示的文字内容），`total`/`has_more` 同步扣除；不做占位卡片。
- **Q4** 分支 `master`，版本 `2.4.0 → 2.4.1`（行为修复，patch）。

现状事实（已核实，2026-11-23，HEAD `1552bda` / `BOTERO_VERSION 2.4.0`）：

- 时间线四态判定的唯一实现在 `webapp/timeline/app.py::_visibility_ctx` + `_serialize_rows`：`hidden` 事件对非作者不下发、`blur` 给非作者图片 URL 追加 `?blur=1`、`text` 剥图并附 `images_hidden: true`、作者本人一律原图。
- 图库完全没读隐私设置：`webapp/gallery/app.py::api_checkins` 对每条记录直接返回 `_thumb_url()` / `_media_url()`；`/thumb`、`/media` 只校验路径落在 `IMAGE_ROOT` 下，不看查看者。`specs/web-gallery.md` 现状也明确写着「图库页 `/gallery` 不受此设置影响」——即本次要修掉的已记录缺口。
- 设置读取有唯一入口 `core/user_settings.py::checkin_display(user_id) -> {"private": state, "group": state}`，图库可直接复用，无需新表、迁移、回填。
- 类型维度可精确对齐：`checkin_records.is_private`（私聊/网页打卡 = 1，群聊 = 0，`core/db/_base.py` 迁移补列 `DEFAULT 0`；网页打卡由 `webapp/profile/checkin_service.py` 固定写 1）与时间线事件 `data.private` 同源；历史行取 0 = 群聊，与时间线「无 `data.private` 标记按群聊」的回落一致。
- 共用数据层：`fetch_checkins_paginated` 的两个调用方是图库（任意查看者，本次要过滤）与个人中心 `/api/me/checkins`（`user_id` 来自登录凭证，永远是自己，不受影响）。

## What Changes

- `webapp/gallery/repository.py`：
  - `CheckinImage` 增加 `is_private: bool = False`（默认值保持既有构造点兼容），三处查询补选 `is_private` 列。
  - `fetch_checkins_paginated` 增加可选 `keep: Callable[[CheckinImage], bool] | None = None`，在**分页切片之前**过滤，使 `total` 与 `has_more` 只统计保留项（不传时行为与现在完全一致）。
- `webapp/gallery/app.py::api_checkins`：
  - 路由新增 `Depends(get_current_user_id)` 取查看者（该端点本就在登录门控内，未登录仍是 401，行为不变）。
  - 按「查看者是否作者 + 该记录 `is_private`」取作者 `checkin_display()` 的对应态（每作者每页只读一次设置，走内存缓存）：
    - 作者本人：全部下发，URL 不变（`text`/`hidden` 的记录也照常可见）。
    - 非作者 + `show`：与现状完全一致（`/thumb/…`、`/media/…`）。
    - 非作者 + `blur`：`thumbnail_url` 与 `image_url` **都**为 `/thumb/<作者>/<文件名>?blur=1`（不提供任何原图路径，点开大图看到的也是模糊图，与时间线「模糊图不穿透原图」一致）。
    - 非作者 + `text` / `hidden`：条目不下发。
  - 响应模型 `CheckinListOut` / `CheckinItemOut` **零字段变更**（不改 OpenAPI 契约快照）。
- 新增回归脚本 `test/scripts/check_gallery_privacy.py`（独立进程，`_env.write_config` 生成临时配置与数据根，不触真实 `server_data`/`data.db`）：四态 × 作者/非作者 × 私聊/群聊分流 × `total`/`has_more` × 媒体路由不变。
- 文档：`specs/web-gallery.md` 的「时间线打卡隐私」约束删去「图库页 `/gallery` 不受此设置影响」，新增图库侧规则（同一设置的图库表现、作者不过滤、媒体直链不强制）；`docs/webapp-api.md` 的 `GET /api/checkins` 行写明按查看者下发。
- 版本：`core/config.py::BOTERO_VERSION` `2.4.0 → 2.4.1`；`CHANGELOG.md` 顶部新增 `[2.4.1]` 节。
- **不做**：不改 `/thumb`、`/media` 路由（Q1:A 裁决）——因此非作者手工构造原图 URL 仍可取图，这是与时间线当前强度一致的既有边界，写入 `specs/web-gallery.md` 的已知边界；不改时间线前后端；不改周报封面（`cover.images[].url` 仍是原缩略图）；不改个人中心 `/api/me/*`；不改 Flutter 客户端；不改数据库 schema；不新增设置项、不改设置页；不动 `app/` 子模块指针。

## Capabilities

### Added Capabilities

- `checkin-gallery`：打卡图库（`GET /api/checkins`）对查看者的可见性语义——作者本人全部可见、非作者按作者 `checkin_display()` 的对应类型状态得到原图 / 模糊缩略图 / 不可见三种结果，`total`/`has_more` 只统计可见项。

（`openspec/specs` 下无图库相关能力；`webapp-api-contract` 只管契约生成与分页/错误形态，不承载图库可见性语义，故新建 `checkin-gallery` 并只改它。）

## Scope and Compatibility

- **社区版与私有版两者一致**：改动只在 webapp 读侧，无 edition 分支、无配置项差异。
- **契约兼容**：响应字段、路径、状态码、分页参数全部不变，只改变 `blur`/`text`/`hidden` 态下非作者看到的**取值与条数**；作者视角与 `show` 态输出与改动前逐字节一致。OpenAPI 快照无需刷新（`CheckinItemOut` 字段集未变）。
- **部署与旧数据**：无 schema 变更、无迁移、无回填；历史 `checkin_records` 行 `is_private` 缺列时由 `core/db/_base.py` 既有迁移补为 0（群聊），与时间线回落一致。bot 进程零改动。
- **行为变化（有意）**：非作者在 `/gallery` 看到的条目数可能少于改动前（`text`/`hidden` 态的他人打卡不再出现）；`blur` 态他人打卡在网格与大图里都是模糊图。`total` 由「全部打卡图数」变为「当前查看者可见的打卡图数」；页面文案「共 N 张」随之为可见数。
- **已知边界（沿用并公示）**：媒体路由不做服务端强制，非作者若已持有/构造 `/media/<作者>/<文件名>` 直链仍可取原图；本次按 Q1:A 裁决不动它。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 | `python test/scripts/check_gallery_privacy.py` 的 `blur` 段 | 非作者 `GET /api/checkins` 中该作者条目 `thumbnail_url == image_url == /thumb/<作者>/<文件名>?blur=1`（`image_url` 不含 `/media/`）；同一记录在作者视角两支 URL 均无 `blur=1`；脚本退出码 0 |
| AC02 | 同上脚本的 `text` / `hidden` 段 | 非作者响应不含该作者条目（`items` 中该作者条目数 0）；该作者唯一打卡时非作者 `total == 0`、`has_more == false`；作者视角同一条目仍下发（`text`/`hidden` 各 1 条） |
| AC03 | 同上脚本的 `show` 段 | 非作者 `thumbnail_url` 以 `/thumb/` 开头不带 query、`image_url` 以 `/media/` 开头不带 query，与改动前一致 |
| AC04 | 同上脚本的类型分流段 | 同一作者私聊=`blur`、群聊=`show` 时：私聊条目两支 URL 带 `blur=1`、群聊条目原图；反向设置（私聊=`show`、群聊=`blur`）结果对调——证明两类独立取态 |
| AC05 | 同上脚本的 `total`/分页段 | 作者 A 有 3 条打卡（show/blur/text 各 1）时：非作者 `total == 2`、`items` 长度 2；`page_size=1` 时逐页合计恰为 2 且 `has_more` 在最后一页为 `false`（过滤发生在切片前，不可出现空页） |
| AC06 | `python test/scripts/check_profile_checkins.py`；`python test/scripts/check_special_filename_media.py` | 两脚本退出码 0：`/api/me/checkins` 本人视角条目/URL 不变；`/thumb/{u}/{f}?blur=1` 200、`/media/{u}/{f}` 200 原图 |
| AC07 | `python test/scripts/check_webapp_api_contract.py` | 退出码 0；`/api/checkins` 响应 schema 与改动前一致（无新增/删除字段），列表分页形态仍是 `items/total/page/page_size/has_more` |
| AC08 | `python -m pytest -q` | 全量通过（0 failed；新脚本由 `test/test_webapp_api_suites.py` 子进程自动纳入） |
| AC09 | `rg -n '图库口径' specs/web-gallery.md`；`rg -n 'api/checkins' docs/webapp-api.md` | `specs/web-gallery.md` 不再出现「图库页 `/gallery` 不受此设置影响」，新增图库侧四态规则、作者不过滤、过滤在切片前、媒体直链不强制（已知边界）；`docs/webapp-api.md` 的 `GET /api/checkins` 行写明按查看者下发与三态结果 |
| AC10 | `rg -n 'BOTERO_VERSION = "2.4.1"' core/config.py`；`sed -n '1,25p' CHANGELOG.md` | 版本号为 `2.4.1`；CHANGELOG 顶部 `[2.4.1]` 节描述本次行为变化与已知边界 |
| AC11 | `openspec validate 2026-11-23-gallery-privacy --strict`；`openspec archive 2026-11-23-gallery-privacy --yes`；`openspec validate checkin-gallery --strict` | 归档前 `is valid`；归档后 `openspec/specs/checkin-gallery/spec.md` 存在且 `is valid`；归档与实现同一 commit |
