# checkin-gallery Specification

## Purpose

打卡图库（`GET /api/checkins` + `/gallery` 页面）向登录用户展示全站打卡图片墙：偏移分页、按作者/年份过滤、条目携带缩略图与原图相对路径。图库按「作者设置 × 打卡类型 × 查看者身份」动态决定每条记录是否下发、图片是否模糊，口径与时间线打卡隐私一致；媒体路由（`/thumb/`、`/media/`）不在本能力范围内。

## ADDED Requirements

### Requirement: 图库按查看者应用作者打卡显示设置

`GET /api/checkins` SHALL 按查看者身份决定每条记录的形态。记录的打卡类型 MUST 由 `checkin_records.is_private` 判定（1 = 私聊/网页打卡，0 = 群聊），状态 MUST 取自作者的 `core/user_settings.py::checkin_display()` 对应类型值（`show|blur|text|hidden`，缺省 `show`，读取失败或非法值按 `show`）：

- 查看者 = 作者：全部记录原样下发，两支 URL 不带任何隐私参数（`text`/`hidden` 的记录也可见）。
- 查看者 ≠ 作者且状态为 `show`：`thumbnail_url` 为 `/thumb/<作者>/<文件名>`、`image_url` 为 `/media/<作者>/<文件名>`，不带 query。
- 查看者 ≠ 作者且状态为 `blur`：`thumbnail_url` 与 `image_url` SHALL 均为 `/thumb/<作者>/<文件名>?blur=1`，MUST NOT 下发任何指向 `/media/` 的路径。
- 查看者 ≠ 作者且状态为 `text` 或 `hidden`：该记录 MUST NOT 出现在响应中。

过滤 MUST 发生在分页切片之前，使 `total` 与 `has_more` 只统计当前查看者可见的记录；MUST NOT 出现「某页被过滤成空但 `has_more` 仍为 true」或页码错位。响应字段集（`items/total/page/page_size/has_more`、条目 `id/user_id/display_name/checkin_date/thumbnail_url/image_url/has_file`）MUST 保持不变。

媒体路由 `/thumb/{user_id}/{filename}` 与 `/media/{user_id}/{filename}` MUST NOT 因本要求改变行为：本能力只约束下发内容，不强制直链访问（非作者持直链仍可取原图的既有边界保留）。

#### Scenario: 非作者看到模糊图与大图都是模糊图

- **WHEN** 作者把群聊打卡设为 `blur`，另一位登录用户请求 `GET /api/checkins`
- **THEN** 该作者每条记录的 `thumbnail_url` 与 `image_url` 均为 `/thumb/<作者>/<文件名>?blur=1`，响应中不含 `/media/` 路径；作者本人请求同一接口时两支 URL 分别指向 `/thumb/` 与 `/media/` 且不带 query

#### Scenario: 非作者看不到 text 与 hidden 记录

- **WHEN** 作者有 3 条打卡（私聊 `text`、群聊 `hidden`、群聊 `show`），另一位登录用户请求 `GET /api/checkins?user_id=<作者>`
- **THEN** 响应 `items` 恰 1 条（`show` 那条）、`total` 为 1、`has_more` 为 false；作者本人请求同一接口得到 3 条

#### Scenario: 两类打卡各取自己的设置

- **WHEN** 同一作者把私聊打卡设为 `blur`、群聊打卡设为 `show`
- **THEN** 非作者看到的私聊记录两支 URL 带 `blur=1`，群聊记录两支 URL 不带 query；把两项设置对调后结果随之对调

#### Scenario: 过滤发生在切片之前

- **WHEN** 作者有 3 条打卡（`show`/`blur`/`text` 各 1），非作者以 `page_size=1` 逐页请求 `GET /api/checkins?user_id=<作者>`
- **THEN** 第一页 `total` 为 2 且返回 1 条、`has_more` 为 true；第二页返回 1 条、`has_more` 为 false；不存在空页

#### Scenario: 媒体路由行为不变

- **WHEN** 任意登录用户请求 `/thumb/<作者>/<文件名>?blur=1` 与 `/media/<作者>/<文件名>`
- **THEN** 两者均返回 200 对应图片，与本次变更前一致
