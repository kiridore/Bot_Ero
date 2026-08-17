# 社区时间线事件协议

> 交叉引用：[`README.md`](README.md)、[`architecture.md`](architecture.md)、[`database.md`](database.md)、[`web-gallery.md`](web-gallery.md)
> 设计文档：[`docs/archive/superpowers/specs/2026-08-10-timeline-design.md`](../docs/archive/superpowers/specs/2026-08-10-timeline-design.md)
> 最后更新：2026-08-10

## 概述

各系统（bot 插件、外部服务器）向 Event Server 发送统一格式事件，Event Server 存储后由时间线页面渲染。设计原则：

- **Event Server 不关心事件从哪来，不理解业务逻辑**——只校验协议、存库、按协议渲染。
- 事件发送方负责判断「什么值得上时间线」并构造 `display` 文案。
- 用户身份一律以 QQ 号（user_id）为准；外部系统（mc、狼人杀等）通过绑定关联到 QQ，绑定功能未上线前显示降级文案。

## Constraint: 事件结构

发送方 POST 的事件 JSON **MUST** 符合以下结构（`id`/`source`/`actor`/`display.title` 必填，其余可选）：

```json
{
  "id": "checkin:3f2a9c…",
  "source": "checkin",
  "actor": { "id": "123456", "qq": "123456" },
  "target": { "type": "url", "url": "https://littlero.tech/profile/checkin" },
  "display": {
    "title": "{id:123456} 完成打卡",
    "description": "本周第 5 天"
  },
  "data": {},
  "dedup_key": "checkin:123456:2026-08-10"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | MUST | 发送方生成，格式 `<source>:<uuid>`；同一 source 下全局唯一，用于幂等 |
| `source` | MUST | 事件来源稳定标识（v1 注册：`checkin`、`forum`、`tools`；`quest`、`title` 已停用）；新增 source 需在本文档注册 |
| `actor.id` | MUST | 发送方体系内参与者 id；QQ 相关系统传 user_id |
| `actor.qq` | CAN | 已绑定/已知的 QQ 号；接收方据此解析昵称头像 |
| `target.type` | CAN | 自由格式标签，仅作未来样式定制，接收方不据此做逻辑判断 |
| `target.url` | CAN | 存在且为 http(s) 链接或站内相对路径（以 `/` 开头）时，时间线渲染「>>详情」按钮；缺失则不渲染 |
| `display.title` | MUST | 动作文案，可含 `{id:<user_id>}` 占位符（见占位符约束） |
| `display.description` | CAN | 补充说明，同样支持占位符 |
| `data` | CAN | 任意 JSON，Event Server **MUST NOT** 解析或索引 |
| `dedup_key` | CAN | 业务自然键，同一 source 下唯一；撤回/回滚按它定位 |

**MUST NOT**：协议不含 `timestamp`（服务器收件时打 `received_at`）、不含 `icon`、不含发送方自定义顶层字段。

## Constraint: 发送与幂等

- 端点：`POST /api/timeline/events`，鉴权 `Authorization: Bearer <BOTERO_EVENT_TOKEN>`（系统间共享密钥，与用户登录密钥不同；单一来源 `scripts/botero.env`）。
- 服务器收件时生成 `received_at`；展示、排序均以 `received_at` 为准，与发送方时钟无关。
- 幂等：`(source, id)` 与 `(source, dedup_key)` 唯一；重复提交 **MUST** 被静默忽略（INSERT OR IGNORE），不报错、不覆盖。
- 发送方 **MUST** best-effort 发送：失败仅记日志，**MUST NOT** 阻塞业务主流程、**MUST NOT** 重试风暴（单次发送至多重试一次）。

## Constraint: 占位符解析

`display.title`/`display.description` 可含 `{id:<user_id>}` 占位符，由接收方在 **GET 渲染时** 解析，不在存储时展开：

- 占位符中的 id **MUST** 是 QQ 号——接收方只能解析 QQ 用户。
- 解析结果：昵称 + 头像（`core.onebot_client.resolve_display_name` / `resolve_avatar_url`）。
- 无法解析（非 QQ 号、未绑定）→ 渲染「未绑定玩家」。
- 发送方想在文案中显示外部系统玩家名：**MUST NOT** 用占位符，直接写死文本，或等绑定功能后改用占位符。

## Constraint: 撤回（硬删除）

- 撤回 = 硬删除，无「已撤回」占位、无墓碑。
- 两条路径：
  - `DELETE /api/timeline/events/{id}`——按事件 id；
  - `DELETE /api/timeline/events/by-key?source=<source>&key=<dedup_key>`——按业务自然键（**业务回滚专用**，发送方无需追踪事件 id）。
- 鉴权：`BOTERO_EVENT_TOKEN`；删除时 source 必须匹配事件自身的 source。
- **业务回滚 MUST 联动删除对应事件**：`/撤回打卡`、打卡消息撤回 → 删 `checkin` 事件。硬删除后同日重打卡可重新入列（新 id、新 dedup_key 行）。

## Constraint: 查询与渲染

- `GET /api/timeline?cursor=<received_at|id>&limit=<n>`，鉴权为用户登录密钥（`get_current_user_id`），未登录 401。
- 排序 `received_at DESC, id DESC`；**keyset 游标分页**（硬删除下 offset 分页会错位，**MUST NOT** 用 offset）。
- 渲染降级顺序：`actor.qq` 存在 → 解析昵称头像；否则查绑定表（v1 无绑定表）→ 「未绑定玩家」。
- 事件卡片 `display.title`/`description` 中占位符按「占位符解析」约束逐一代换（同批按 user_id 去重解析）。

## Constraint: 卡片媒体（`data.images`）

`data` 整体仍由 Event Server 透传不解析，但渲染层按以下**展示约定**读取：

- 发送方 CAN 在 `data` 提供 `images` 键（图片 URL 数组），时间线卡片据此渲染缩略图条：

```json
"data": { "images": ["/thumb/123456/abc.image", "/thumb/123456/def.image"] }
```

- 渲染约定：每个 URL 渲染为卡片内缩略图；URL 以 `/thumb/` 开头时，点击跳转的原图为同路径替换 `/media/` 的 URL（展示约定，非业务判断）；其他 http(s) URL 直接作为链接目标。
- 图片的生成、存在性、尺寸校验由**发送方**负责；Event Server 不校验图片内容。
- v1 提供者：`checkin` 事件按图库缩略图约定构造 `/thumb/<user_id>/<slug>`（slug = 文件名去 `{}` 与 `-`）；发送方在**事件发出前**将图片下载到 `record_images/<user_id>/`（打卡时即时落盘，08:00 备份任务兜底补下载），保证时间线渲染时 URL 可用。

## Constraint: 已注册 source 与 dedup_key 约定

| source | 发送方 | 事件含义 | dedup_key 约定 |
|---|---|---|---|
| `checkin` | `plugins/checkin` | 完成打卡 | `checkin:<user_id>:<YYYY-MM-DD>:<message_id>`（message_id 为当次 /打卡 消息 id；**同一天多次打卡各成一条**，撤回按同 key 定位） |
| `forum` | `webapp/forum` | 发帖 / 编辑 / 评论 / 投票关闭 | `forum_post:<post_id>` / `forum_comment:<comment_id>` / `forum_poll_close:<post_id>`（删帖/删评论按同 key 撤回；编辑=撤回旧事件并按同 key 重发最新内容，不产生新事件） |
| `tools` | `webapp/tools` | 提交 / 删除工具链接 | `tools_link:<tool_id>`（删除时按同 key 撤回事件） |

> `quest`（周常任务完成）因触发频繁，自 2026-08-10 起**不再发送到时间线**（`core/utils.py::on_quest_trigger` 已移除发送/回滚接线）；如需恢复需重新在本表注册并约定 dedup_key。
> `title`（解锁称号）自 2026-08-11 起**不再发送到时间线**（`plugins/title.logic::evaluate_and_unlock_titles` 已移除发送接线）；如需恢复需重新在本表注册并约定 dedup_key。

新增 source **MUST** 在本表注册并约定 dedup_key 格式，且文档更新与代码同一 commit。

## 反模式

- **DO NOT** 把 `display.title` 烘焙发送方侧解析好的昵称（QQ 改名后永远旧数据）——用 `{id:}` 占位符让接收方渲染时解析。
- **DO NOT** 在 Event Server 维护「已知 target.type 列表」或据此做业务判断。
- **DO NOT** 用 offset 分页。
- **DO NOT** 让发送方失败重试阻塞主线程或无限重试。
- **DO NOT** 在协议字段外塞自定义顶层键（放 `data`）。
