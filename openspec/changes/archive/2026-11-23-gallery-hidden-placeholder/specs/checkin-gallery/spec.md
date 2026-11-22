# checkin-gallery Specification

## Purpose

打卡图库（`GET /api/checkins` + `/gallery` 页面）向登录用户展示全站打卡图片墙：偏移分页、按作者/年份过滤、条目携带缩略图与原图相对路径。图库按「作者设置 × 打卡类型 × 查看者身份」动态决定每条记录的图片位形态（原图 / 模糊图 / 空），全部记录都会下发；媒体路由（`/thumb/`、`/media/`）不在本能力范围内。

## REMOVED Requirements

### Requirement: 图库按查看者应用作者打卡显示设置

**Reason**: 所有者裁决改为「卡片照常下发、图片位换成占位」：`text`/`hidden` 态不再从 `/api/checkins` 剔除条目，因此该要求的「该记录 MUST NOT 出现在响应中」「`total`/`has_more` 只统计可见记录」「过滤发生在切片之前」三条与本裁决冲突，整条重述。

**Migration**: 非作者在 `text`/`hidden` 态收到条目但 `thumbnail_url`/`image_url` 均为空字符串，客户端渲染占位并注明「图片仅作者可见」；`total`/`has_more` 统计全部条目。其余三态（作者本人 / `show` / `blur`）与媒体路由边界的语义在替代要求中原样保留。

## ADDED Requirements

### Requirement: 图库全量下发打卡条目并按查看者决定图片位

`GET /api/checkins` SHALL 对**每一条**打卡记录下发条目（不得因作者设置而剔除条目），并按查看者身份决定图片位的形态。记录的打卡类型 MUST 由 `checkin_records.is_private` 判定（1 = 私聊/网页打卡，0 = 群聊），状态 MUST 取自作者的 `core/user_settings.py::checkin_display()` 对应类型值（`show|blur|text|hidden`，缺省 `show`，读取失败或非法值按 `show`）：

- 查看者 = 作者：`thumbnail_url` 为 `/thumb/<作者>/<文件名>`、`image_url` 为 `/media/<作者>/<文件名>`，不带 query（`text`/`hidden` 的记录亦然）。
- 查看者 ≠ 作者且状态为 `show`：同作者视角，两支 URL 指向原图，不带 query。
- 查看者 ≠ 作者且状态为 `blur`：`thumbnail_url` 与 `image_url` SHALL 均为 `/thumb/<作者>/<文件名>?blur=1`，MUST NOT 下发任何指向 `/media/` 的路径。
- 查看者 ≠ 作者且状态为 `text` 或 `hidden`：`thumbnail_url` 与 `image_url` SHALL 均为**空字符串**，条目的 `id`/`user_id`/`display_name`/`checkin_date`/`has_file` MUST 照常下发（非作者可看到「谁在哪天打了卡」，但拿不到任何图片地址）。

`total` 与 `has_more` SHALL 统计全部下发条目（含图片位为空的占位条目），不得因状态为 `text`/`hidden` 而扣减。响应字段集（`items/total/page/page_size/has_more`、条目 `id/user_id/display_name/checkin_date/thumbnail_url/image_url/has_file`）MUST 保持不变；`has_file` 语义仍是「文件是否存在于磁盘」，与查看者是否有权查看无关。

媒体路由 `/thumb/{user_id}/{filename}` 与 `/media/{user_id}/{filename}` MUST NOT 因本要求改变行为：本能力只约束下发内容，不强制直链访问（非作者持直链仍可取原图的既有边界保留）。

#### Scenario: 模糊态两支 URL 都是模糊图

- **WHEN** 作者把群聊打卡设为 `blur`，另一位登录用户请求 `GET /api/checkins`
- **THEN** 该作者每条记录的 `thumbnail_url` 与 `image_url` 均为 `/thumb/<作者>/<文件名>?blur=1`，响应中不含 `/media/` 路径；作者本人请求同一接口时两支 URL 分别指向 `/thumb/` 与 `/media/` 且不带 query

#### Scenario: 隐藏态与纯文字态下发占位卡片

- **WHEN** 作者有 3 条打卡（私聊 `text`、群聊 `hidden`、群聊 `show`），另一位登录用户请求 `GET /api/checkins?user_id=<作者>`
- **THEN** 响应 `items` 恰 3 条、`total` 为 3；其中 `text` 与 `hidden` 两条的 `thumbnail_url` 与 `image_url` 均为 `""`、`display_name` 与 `checkin_date` 非空、`has_file` 为 `true`；`show` 那条两支 URL 分别以 `/thumb/` 与 `/media/` 开头

#### Scenario: 两类打卡各取自己的设置

- **WHEN** 同一作者把私聊打卡设为 `blur`、群聊打卡设为 `show`
- **THEN** 非作者看到的私聊记录两支 URL 带 `blur=1`，群聊记录两支 URL 不带 query；把两项设置对调后结果随之对调

#### Scenario: 分页统计包含占位条目

- **WHEN** 作者有 3 条打卡（`show`/`blur`/`text` 各 1），非作者以 `page_size=1` 逐页请求 `GET /api/checkins?user_id=<作者>`
- **THEN** 每页 `total` 均为 3，三页各返回 1 条，末页 `has_more` 为 false；不存在空页

#### Scenario: 客户端以占位表达图片不可见

- **WHEN** 客户端收到 `thumbnail_url` 与 `image_url` 均为空串的图库条目
- **THEN** 卡片照常渲染（作者昵称与打卡时间），图片位渲染占位并注明「图片仅作者可见」，不打开图片灯箱

#### Scenario: 媒体路由行为不变

- **WHEN** 任意登录用户请求 `/thumb/<作者>/<文件名>?blur=1` 与 `/media/<作者>/<文件名>`
- **THEN** 两者均返回 200 对应图片，与本次变更前一致
